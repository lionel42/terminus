from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import col, func, select

from app.api.deps import SessionDep, get_current_user
from app.api.helpers import SUPERUSER_ONLY, delete_or_409, ensure_new, get_or_404
from app.models import (
    Compound,
    CompoundCreate,
    CompoundPublic,
    CompoundsPublic,
    CompoundUpdate,
    Message,
)

router = APIRouter(
    prefix="/compounds",
    tags=["compounds"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/", response_model=CompoundsPublic)
def read_compounds(
    session: SessionDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> Any:
    """List compounds."""
    count = session.exec(select(func.count()).select_from(Compound)).one()
    statement = select(Compound).order_by(col(Compound.id)).offset(skip).limit(limit)
    compounds = session.exec(statement).all()
    return CompoundsPublic(
        data=[CompoundPublic.model_validate(c) for c in compounds], count=count
    )


@router.get("/{compound_id}", response_model=CompoundPublic)
def read_compound(session: SessionDep, compound_id: str) -> Any:
    """Get a compound by id."""
    return get_or_404(session, Compound, compound_id)


@router.post("/", dependencies=SUPERUSER_ONLY, response_model=CompoundPublic)
def create_compound(session: SessionDep, compound_in: CompoundCreate) -> Any:
    """Create a compound."""
    ensure_new(session, Compound, compound_in.id)
    compound = Compound.model_validate(compound_in)
    session.add(compound)
    session.commit()
    session.refresh(compound)
    return compound


@router.patch(
    "/{compound_id}", dependencies=SUPERUSER_ONLY, response_model=CompoundPublic
)
def update_compound(
    session: SessionDep, compound_id: str, compound_in: CompoundUpdate
) -> Any:
    """Update a compound."""
    compound = get_or_404(session, Compound, compound_id)
    compound.sqlmodel_update(compound_in.model_dump(exclude_unset=True))
    session.add(compound)
    session.commit()
    session.refresh(compound)
    return compound


@router.delete("/{compound_id}", dependencies=SUPERUSER_ONLY)
def delete_compound(session: SessionDep, compound_id: str) -> Message:
    """Delete a compound (only if no measurement result uses it)."""
    compound = get_or_404(session, Compound, compound_id)
    delete_or_409(session, compound, "Compound is used by measurement results")
    return Message(message="Compound deleted successfully")
