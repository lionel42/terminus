from collections import Counter
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import ColumnElement
from sqlmodel import Session, SQLModel, col, delete, func, select

from app.api.deps import SessionDep, get_current_user
from app.api.helpers import SUPERUSER_ONLY, get_or_404, require_exists
from app.models import (
    Compound,
    ImportMode,
    Instrument,
    Measurement,
    MeasurementCreate,
    MeasurementFilters,
    MeasurementImportReport,
    MeasurementPublic,
    MeasurementPublicWithResults,
    MeasurementQuery,
    MeasurementResult,
    MeasurementResultCreate,
    MeasurementsPublic,
    MeasurementUpdate,
    Message,
    Sample,
)

router = APIRouter(
    prefix="/measurements",
    tags=["measurements"],
    dependencies=[Depends(get_current_user)],
)


# --- Shared logic (also used by the results router) ---


def measurement_conditions(filters: MeasurementFilters) -> list[ColumnElement[bool]]:
    """SQL conditions on Measurement for the given filters."""
    conditions: list[ColumnElement[bool]] = []
    if filters.instrument_id is not None:
        conditions.append(col(Measurement.instrument_id) == filters.instrument_id)
    if filters.type is not None:
        conditions.append(col(Measurement.type) == filters.type)
    if filters.sample_id is not None:
        conditions.append(col(Measurement.sample_id) == filters.sample_id)
    if filters.container_id is not None:
        samples_of_container = select(Sample.id).where(
            col(Sample.container_id) == filters.container_id
        )
        conditions.append(col(Measurement.sample_id).in_(samples_of_container))
    if filters.measured_from is not None:
        conditions.append(col(Measurement.measured_at) >= filters.measured_from)
    if filters.measured_to is not None:
        conditions.append(col(Measurement.measured_at) <= filters.measured_to)
    return conditions


def _missing_ids(session: Session, model: type[SQLModel], ids: set[str]) -> list[str]:
    if not ids:
        return []
    id_column = col(model.id)  # type: ignore[attr-defined]
    existing = set(session.exec(select(id_column).where(id_column.in_(ids))).all())
    return sorted(ids - existing)


def _check_results(session: Session, results: list[MeasurementResultCreate]) -> None:
    duplicated = [
        c for c, n in Counter(r.compound_id for r in results).items() if n > 1
    ]
    if duplicated:
        raise HTTPException(
            status_code=422,
            detail=f"Compounds given more than once: {', '.join(sorted(duplicated))}",
        )
    missing = _missing_ids(session, Compound, {r.compound_id for r in results})
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Compounds do not exist: {', '.join(missing)}",
        )


def _ensure_run_free(
    session: Session, measurement: Measurement, exclude_id: int | None = None
) -> None:
    """An instrument runs one measurement at a given time."""
    statement = select(Measurement).where(
        col(Measurement.instrument_id) == measurement.instrument_id,
        col(Measurement.measured_at) == measurement.measured_at,
    )
    if exclude_id is not None:
        statement = statement.where(col(Measurement.id) != exclude_id)
    if session.exec(statement).first() is not None:
        raise HTTPException(
            status_code=409,
            detail="This instrument already has a measurement at that time",
        )


def _replace_results(
    session: Session, measurement_id: int, results: list[MeasurementResultCreate]
) -> None:
    session.exec(
        delete(MeasurementResult).where(
            col(MeasurementResult.measurement_id) == measurement_id
        )
    )
    for result in results:
        session.add(
            MeasurementResult.model_validate(
                result, update={"measurement_id": measurement_id}
            )
        )


def _with_results(session: Session, measurement: Measurement) -> Any:
    session.refresh(measurement)
    return MeasurementPublicWithResults.model_validate(measurement)


# --- Routes ---


@router.get("/", response_model=MeasurementsPublic)
def read_measurements(
    session: SessionDep,
    query: Annotated[MeasurementQuery, Query()],
) -> Any:
    """List measurements (without results), newest first, optionally filtered."""
    conditions = measurement_conditions(query)
    count = session.exec(
        select(func.count()).select_from(Measurement).where(*conditions)
    ).one()
    statement = (
        select(Measurement)
        .where(*conditions)
        .order_by(col(Measurement.measured_at).desc())
        .offset(query.skip)
        .limit(query.limit)
    )
    measurements = session.exec(statement).all()
    return MeasurementsPublic(
        data=[MeasurementPublic.model_validate(m) for m in measurements], count=count
    )


@router.get("/{measurement_id}", response_model=MeasurementPublicWithResults)
def read_measurement(session: SessionDep, measurement_id: int) -> Any:
    """Get a measurement with its per-compound results."""
    measurement = get_or_404(session, Measurement, measurement_id)
    return MeasurementPublicWithResults.model_validate(measurement)


@router.post(
    "/", dependencies=SUPERUSER_ONLY, response_model=MeasurementPublicWithResults
)
def create_measurement(session: SessionDep, measurement_in: MeasurementCreate) -> Any:
    """Create a measurement, optionally with its per-compound results."""
    require_exists(session, Instrument, measurement_in.instrument_id)
    if measurement_in.sample_id is not None:
        require_exists(session, Sample, measurement_in.sample_id)
    _check_results(session, measurement_in.results)

    measurement = Measurement.model_validate(
        measurement_in.model_dump(exclude={"results"})
    )
    _ensure_run_free(session, measurement)
    session.add(measurement)
    session.flush()  # assigns the auto-generated id
    assert measurement.id is not None
    _replace_results(session, measurement.id, measurement_in.results)
    session.commit()
    return _with_results(session, measurement)


@router.post(
    "/import", dependencies=SUPERUSER_ONLY, response_model=MeasurementImportReport
)
def import_measurements(
    session: SessionDep,
    measurements_in: list[MeasurementCreate],
    mode: ImportMode = ImportMode.SKIP,
) -> Any:
    """Bulk import, all or nothing.

    A measurement already in the database (same instrument and measured_at) is
    kept (`mode=skip`) or overwritten with its results (`mode=replace`).
    """
    missing = {
        "instruments": _missing_ids(
            session, Instrument, {m.instrument_id for m in measurements_in}
        ),
        "samples": _missing_ids(
            session,
            Sample,
            {m.sample_id for m in measurements_in if m.sample_id is not None},
        ),
        "compounds": _missing_ids(
            session,
            Compound,
            {r.compound_id for m in measurements_in for r in m.results},
        ),
    }
    if any(missing.values()):
        raise HTTPException(
            status_code=422,
            detail={"message": "Unknown references", "missing": missing},
        )
    runs = Counter((m.instrument_id, m.measured_at) for m in measurements_in)
    if any(n > 1 for n in runs.values()):
        raise HTTPException(
            status_code=422,
            detail="The same instrument and measured_at appear more than once",
        )
    for measurement_in in measurements_in:
        _check_results(session, measurement_in.results)

    report = MeasurementImportReport(created=0, skipped=0, replaced=0)
    for measurement_in in measurements_in:
        existing = session.exec(
            select(Measurement).where(
                col(Measurement.instrument_id) == measurement_in.instrument_id,
                col(Measurement.measured_at) == measurement_in.measured_at,
            )
        ).first()
        if existing is not None and mode == ImportMode.SKIP:
            report.skipped += 1
            continue
        if existing is not None:
            existing.sqlmodel_update(measurement_in.model_dump(exclude={"results"}))
            session.add(existing)
            measurement = existing
            report.replaced += 1
        else:
            measurement = Measurement.model_validate(
                measurement_in.model_dump(exclude={"results"})
            )
            session.add(measurement)
            report.created += 1
        session.flush()
        assert measurement.id is not None
        _replace_results(session, measurement.id, measurement_in.results)
    session.commit()
    return report


@router.patch(
    "/{measurement_id}",
    dependencies=SUPERUSER_ONLY,
    response_model=MeasurementPublicWithResults,
)
def update_measurement(
    session: SessionDep, measurement_id: int, measurement_in: MeasurementUpdate
) -> Any:
    """Update a measurement's fields (use PUT .../results for the results)."""
    measurement = get_or_404(session, Measurement, measurement_id)
    update = measurement_in.model_dump(exclude_unset=True)
    if update.get("instrument_id") is not None:
        require_exists(session, Instrument, update["instrument_id"])
    if update.get("sample_id") is not None:
        require_exists(session, Sample, update["sample_id"])
    measurement.sqlmodel_update(update)
    _ensure_run_free(session, measurement, exclude_id=measurement.id)
    session.add(measurement)
    session.commit()
    return _with_results(session, measurement)


@router.put(
    "/{measurement_id}/results",
    dependencies=SUPERUSER_ONLY,
    response_model=MeasurementPublicWithResults,
)
def replace_measurement_results(
    session: SessionDep,
    measurement_id: int,
    results_in: list[MeasurementResultCreate],
) -> Any:
    """Replace all per-compound results of a measurement (e.g. after reprocessing)."""
    measurement = get_or_404(session, Measurement, measurement_id)
    _check_results(session, results_in)
    assert measurement.id is not None
    _replace_results(session, measurement.id, results_in)
    session.commit()
    session.expire(measurement, ["results"])
    return _with_results(session, measurement)


@router.delete("/{measurement_id}", dependencies=SUPERUSER_ONLY)
def delete_measurement(session: SessionDep, measurement_id: int) -> Message:
    """Delete a measurement and its results."""
    measurement = get_or_404(session, Measurement, measurement_id)
    session.delete(measurement)
    session.commit()
    return Message(message="Measurement deleted successfully")
