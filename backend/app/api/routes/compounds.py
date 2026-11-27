from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, func, or_, select

from app.api.deps import SessionDep, get_current_user
from app.api.helpers import SUPERUSER_ONLY, delete_or_409, ensure_new, get_or_404
from app.models import (
    BoilingPointCreate,
    BoilingPointPublic,
    Compound,
    CompoundAlias,
    CompoundAliasCreate,
    CompoundAliasPublic,
    CompoundBoilingPoint,
    CompoundCreate,
    CompoundPublicWithDetails,
    CompoundsPublic,
    CompoundStatus,
    CompoundUpdate,
    Message,
)

router = APIRouter(
    prefix="/compounds",
    tags=["compounds"],
    dependencies=[Depends(get_current_user)],
)

WITH_DETAILS = (
    selectinload(Compound.aliases),  # type: ignore[arg-type]
    selectinload(Compound.boiling_points),  # type: ignore[arg-type]
)


def _details(compound: Compound) -> CompoundPublicWithDetails:
    return CompoundPublicWithDetails.model_validate(
        compound,
        update={
            "aliases": sorted(compound.aliases, key=lambda a: a.alias.lower()),
            "boiling_points": compound.boiling_points,
        },
    )


@router.get("/", response_model=CompoundsPublic)
def read_compounds(
    session: SessionDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    status: CompoundStatus | None = None,
    q: Annotated[
        str | None,
        Query(
            max_length=255,
            description="Substring of the id, names, CAS number or an alias",
        ),
    ] = None,
) -> Any:
    """List compounds with their aliases and boiling points."""
    conditions: list[Any] = []
    if status is not None:
        conditions.append(Compound.status == status)
    if q and q.strip():
        # autoescape: "_" and "%" (allowed in ids) match themselves
        text = q.strip()
        alias_match = (
            select(CompoundAlias.id)
            .where(CompoundAlias.compound_id == Compound.id)
            .where(col(CompoundAlias.alias).icontains(text, autoescape=True))
            .exists()
        )
        conditions.append(
            or_(
                col(Compound.id).icontains(text.lower(), autoescape=True),
                col(Compound.industrial_name).icontains(text, autoescape=True),
                col(Compound.iupac_name).icontains(text, autoescape=True),
                col(Compound.formula).icontains(text, autoescape=True),
                col(Compound.cas_number).icontains(text, autoescape=True),
                alias_match,
            )
        )
    count = session.exec(
        select(func.count()).select_from(Compound).where(*conditions)
    ).one()
    statement = (
        select(Compound)
        .where(*conditions)
        .options(*WITH_DETAILS)
        .order_by(col(Compound.id))
        .offset(skip)
        .limit(limit)
    )
    compounds = session.exec(statement).all()
    return CompoundsPublic(data=[_details(c) for c in compounds], count=count)


def _resolve(session: Session, name: str) -> Compound | None:
    name = name.strip()
    if not name:
        return None
    compound = session.get(Compound, name)
    if compound is not None:
        return compound
    alias = session.exec(
        select(CompoundAlias).where(CompoundAlias.alias == name)
    ).first()
    if alias is not None:
        return alias.compound
    for column in (
        Compound.industrial_name,
        Compound.cas_number,
        Compound.inchikey,
        Compound.iupac_name,
    ):
        compound = session.exec(select(Compound).where(column == name)).first()
        if compound is not None:
            return compound
    return None


@router.get("/resolve", response_model=CompoundPublicWithDetails)
def resolve_compound(
    session: SessionDep, name: Annotated[str, Query(min_length=1, max_length=255)]
) -> Any:
    """Find the compound named `name`.

    Tries, in order: id, alias, industrial name, CAS number, InChIKey,
    IUPAC name (case-insensitive).
    """
    compound = _resolve(session, name)
    if compound is None:
        raise HTTPException(status_code=404, detail=f"No compound named '{name}'")
    return _details(compound)


@router.get("/{compound_id}", response_model=CompoundPublicWithDetails)
def read_compound(session: SessionDep, compound_id: str) -> Any:
    """Get a compound by id, with its aliases and boiling points."""
    return _details(get_or_404(session, Compound, compound_id))


@router.post("/", dependencies=SUPERUSER_ONLY, response_model=CompoundPublicWithDetails)
def create_compound(session: SessionDep, compound_in: CompoundCreate) -> Any:
    """Create a compound."""
    ensure_new(session, Compound, compound_in.id)
    compound = Compound.model_validate(compound_in)
    session.add(compound)
    session.commit()
    session.refresh(compound)
    return _details(compound)


@router.patch(
    "/{compound_id}",
    dependencies=SUPERUSER_ONLY,
    response_model=CompoundPublicWithDetails,
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
    return _details(compound)


@router.delete("/{compound_id}", dependencies=SUPERUSER_ONLY)
def delete_compound(session: SessionDep, compound_id: str) -> Message:
    """Delete a compound with its aliases and boiling points (only if no
    measurement result uses it)."""
    compound = get_or_404(session, Compound, compound_id)
    delete_or_409(session, compound, "Compound is used by measurement results")
    return Message(message="Compound deleted successfully")


# --- Aliases ---


@router.post(
    "/{compound_id}/aliases",
    dependencies=SUPERUSER_ONLY,
    response_model=CompoundAliasPublic,
)
def create_alias(
    session: SessionDep, compound_id: str, alias_in: CompoundAliasCreate
) -> Any:
    """Add an alias. Aliases are unique over all compounds (ignoring case)."""
    compound = get_or_404(session, Compound, compound_id)
    existing = session.exec(
        select(CompoundAlias).where(CompoundAlias.alias == alias_in.alias)
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Alias '{existing.alias}' already names "
            f"compound '{existing.compound_id}'",
        )
    alias = CompoundAlias(alias=alias_in.alias, compound_id=compound.id)
    session.add(alias)
    try:
        session.commit()
    except IntegrityError:  # concurrent insert, or a collation-level duplicate
        session.rollback()
        raise HTTPException(
            status_code=409, detail=f"Alias '{alias_in.alias}' already exists"
        )
    session.refresh(alias)
    return alias


@router.delete("/{compound_id}/aliases/{alias_id}", dependencies=SUPERUSER_ONLY)
def delete_alias(session: SessionDep, compound_id: str, alias_id: int) -> Message:
    """Remove an alias."""
    alias = session.get(CompoundAlias, alias_id)
    if alias is None or alias.compound_id != compound_id.lower():
        raise HTTPException(status_code=404, detail="CompoundAlias not found")
    session.delete(alias)
    session.commit()
    return Message(message="Alias deleted successfully")


# --- Boiling points ---


@router.post(
    "/{compound_id}/boiling-points",
    dependencies=SUPERUSER_ONLY,
    response_model=BoilingPointPublic,
)
def create_boiling_point(
    session: SessionDep, compound_id: str, boiling_point_in: BoilingPointCreate
) -> Any:
    """Add a boiling point with its source."""
    compound = get_or_404(session, Compound, compound_id)
    boiling_point = CompoundBoilingPoint.model_validate(
        boiling_point_in, update={"compound_id": compound.id}
    )
    session.add(boiling_point)
    session.commit()
    session.refresh(boiling_point)
    return boiling_point


@router.delete(
    "/{compound_id}/boiling-points/{boiling_point_id}", dependencies=SUPERUSER_ONLY
)
def delete_boiling_point(
    session: SessionDep, compound_id: str, boiling_point_id: int
) -> Message:
    """Remove a boiling point."""
    boiling_point = session.get(CompoundBoilingPoint, boiling_point_id)
    if boiling_point is None or boiling_point.compound_id != compound_id.lower():
        raise HTTPException(status_code=404, detail="Boiling point not found")
    session.delete(boiling_point)
    session.commit()
    return Message(message="Boiling point deleted successfully")
