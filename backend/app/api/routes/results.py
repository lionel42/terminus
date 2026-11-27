"""Flat, read-only access to per-compound results, for analysis and plotting."""

import csv
import io
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from sqlmodel import Session, col, func, select

from app.api.deps import SessionDep, get_current_user
from app.api.routes.measurements import measurement_conditions
from app.models import (
    Measurement,
    MeasurementResult,
    ResultFilters,
    ResultQuery,
    ResultRow,
    ResultRowsPublic,
    Sample,
)

router = APIRouter(
    prefix="/results",
    tags=["results"],
    dependencies=[Depends(get_current_user)],
)


def _conditions(filters: ResultFilters) -> list[Any]:
    conditions: list[Any] = measurement_conditions(filters)
    if filters.compound_id is not None:
        conditions.append(col(MeasurementResult.compound_id) == filters.compound_id)
    if filters.exclude_flags is not None:
        conditions.append(
            col(MeasurementResult.flags).op("&")(filters.exclude_flags) == 0
        )
    return conditions


def _query_rows(
    session: Session, filters: ResultFilters, skip: int, limit: int | None
) -> list[ResultRow]:
    statement = (
        select(MeasurementResult, Measurement, Sample.container_id)
        .join(
            Measurement,
            col(MeasurementResult.measurement_id) == col(Measurement.id),
        )
        .outerjoin(Sample, col(Measurement.sample_id) == col(Sample.id))
        .where(*_conditions(filters))
        .order_by(col(Measurement.measured_at), col(MeasurementResult.compound_id))
        .offset(skip)
    )
    if limit is not None:
        statement = statement.limit(limit)
    rows = []
    for result, measurement, container_id in session.exec(statement).all():
        assert measurement.id is not None
        rows.append(
            ResultRow(
                measurement_id=measurement.id,
                measured_at=measurement.measured_at,
                type=measurement.type,
                instrument_id=measurement.instrument_id,
                sample_id=measurement.sample_id,
                container_id=container_id,
                compound_id=result.compound_id,
                area=result.area,
                height=result.height,
                retention_time=result.retention_time,
                concentration=result.concentration,
                flags=result.flags,
                flag_comment=result.flag_comment,
                measurement_flags=measurement.flags,
                measurement_flag_comment=measurement.flag_comment,
            )
        )
    return rows


@router.get("/", response_model=ResultRowsPublic)
def read_results(
    session: SessionDep,
    query: Annotated[ResultQuery, Query()],
) -> Any:
    """One row per (measurement, compound), oldest first, optionally filtered."""
    count = session.exec(
        select(func.count())
        .select_from(MeasurementResult)
        .join(
            Measurement,
            col(MeasurementResult.measurement_id) == col(Measurement.id),
        )
        .where(*_conditions(query))
    ).one()
    return ResultRowsPublic(
        data=_query_rows(session, query, query.skip, query.limit), count=count
    )


@router.get(
    "/csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "CSV file"}},
)
def read_results_csv(
    session: SessionDep, filters: Annotated[ResultFilters, Query()]
) -> Response:
    """Same rows as GET /results, as a CSV download (no pagination)."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(ResultRow.model_fields))
    writer.writeheader()
    for row in _query_rows(session, filters, skip=0, limit=None):
        writer.writerow(row.model_dump(mode="json"))
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="results.csv"'},
    )
