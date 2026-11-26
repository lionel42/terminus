from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import col, func, select

from app.api.deps import SessionDep, get_current_user
from app.api.helpers import SUPERUSER_ONLY, delete_or_409, ensure_new, get_or_404
from app.models import (
    Instrument,
    InstrumentCreate,
    InstrumentPublic,
    InstrumentsPublic,
    InstrumentUpdate,
    Message,
)

router = APIRouter(
    prefix="/instruments",
    tags=["instruments"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/", response_model=InstrumentsPublic)
def read_instruments(
    session: SessionDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> Any:
    """List instruments."""
    count = session.exec(select(func.count()).select_from(Instrument)).one()
    statement = (
        select(Instrument).order_by(col(Instrument.id)).offset(skip).limit(limit)
    )
    instruments = session.exec(statement).all()
    return InstrumentsPublic(
        data=[InstrumentPublic.model_validate(i) for i in instruments], count=count
    )


@router.get("/{instrument_id}", response_model=InstrumentPublic)
def read_instrument(session: SessionDep, instrument_id: str) -> Any:
    """Get an instrument by id."""
    return get_or_404(session, Instrument, instrument_id)


@router.post("/", dependencies=SUPERUSER_ONLY, response_model=InstrumentPublic)
def create_instrument(session: SessionDep, instrument_in: InstrumentCreate) -> Any:
    """Create an instrument."""
    ensure_new(session, Instrument, instrument_in.id)
    instrument = Instrument.model_validate(instrument_in)
    session.add(instrument)
    session.commit()
    session.refresh(instrument)
    return instrument


@router.patch(
    "/{instrument_id}", dependencies=SUPERUSER_ONLY, response_model=InstrumentPublic
)
def update_instrument(
    session: SessionDep, instrument_id: str, instrument_in: InstrumentUpdate
) -> Any:
    """Update an instrument."""
    instrument = get_or_404(session, Instrument, instrument_id)
    instrument.sqlmodel_update(instrument_in.model_dump(exclude_unset=True))
    session.add(instrument)
    session.commit()
    session.refresh(instrument)
    return instrument


@router.delete("/{instrument_id}", dependencies=SUPERUSER_ONLY)
def delete_instrument(session: SessionDep, instrument_id: str) -> Message:
    """Delete an instrument (only if it has no measurements)."""
    instrument = get_or_404(session, Instrument, instrument_id)
    delete_or_409(session, instrument, "Instrument has measurements")
    return Message(message="Instrument deleted successfully")
