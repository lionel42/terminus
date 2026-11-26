from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime
from sqlmodel import Session, col, func, select

from app.api.deps import SessionDep, get_current_user
from app.api.helpers import (
    SUPERUSER_ONLY,
    delete_or_409,
    ensure_new,
    get_or_404,
    require_exists,
)
from app.models import (
    Container,
    LowerId,
    Message,
    Sample,
    SampleCreate,
    SamplePublic,
    SamplesPublic,
    SampleUpdate,
)

router = APIRouter(
    prefix="/samples",
    tags=["samples"],
    dependencies=[Depends(get_current_user)],
)


def _ensure_filling_free(
    session: Session, sample: Sample, exclude_id: str | None = None
) -> None:
    """A container can only be filled once at a given instant."""
    statement = select(Sample).where(
        col(Sample.container_id) == sample.container_id,
        col(Sample.filled_at) == sample.filled_at,
    )
    if exclude_id is not None:
        statement = statement.where(col(Sample.id) != exclude_id)
    if session.exec(statement).first() is not None:
        raise HTTPException(
            status_code=409,
            detail="This container already has a sample filled at that time",
        )


@router.get("/", response_model=SamplesPublic)
def read_samples(
    session: SessionDep,
    container_id: LowerId | None = None,
    filled_from: AwareDatetime | None = None,
    filled_to: AwareDatetime | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> Any:
    """List samples, newest filling first, optionally filtered."""
    conditions = []
    if container_id is not None:
        conditions.append(col(Sample.container_id) == container_id)
    if filled_from is not None:
        conditions.append(col(Sample.filled_at) >= filled_from)
    if filled_to is not None:
        conditions.append(col(Sample.filled_at) <= filled_to)

    count = session.exec(
        select(func.count()).select_from(Sample).where(*conditions)
    ).one()
    statement = (
        select(Sample)
        .where(*conditions)
        .order_by(col(Sample.filled_at).desc())
        .offset(skip)
        .limit(limit)
    )
    samples = session.exec(statement).all()
    return SamplesPublic(
        data=[SamplePublic.model_validate(s) for s in samples], count=count
    )


@router.get("/{sample_id}", response_model=SamplePublic)
def read_sample(session: SessionDep, sample_id: str) -> Any:
    """Get a sample by id."""
    return get_or_404(session, Sample, sample_id)


@router.post("/", dependencies=SUPERUSER_ONLY, response_model=SamplePublic)
def create_sample(session: SessionDep, sample_in: SampleCreate) -> Any:
    """Record the filling of a container."""
    ensure_new(session, Sample, sample_in.id)
    require_exists(session, Container, sample_in.container_id)
    sample = Sample.model_validate(sample_in)
    _ensure_filling_free(session, sample)
    session.add(sample)
    session.commit()
    session.refresh(sample)
    return sample


@router.patch("/{sample_id}", dependencies=SUPERUSER_ONLY, response_model=SamplePublic)
def update_sample(session: SessionDep, sample_id: str, sample_in: SampleUpdate) -> Any:
    """Update a sample."""
    sample = get_or_404(session, Sample, sample_id)
    update = sample_in.model_dump(exclude_unset=True)
    if update.get("container_id") is not None:
        require_exists(session, Container, update["container_id"])
    sample.sqlmodel_update(update)
    _ensure_filling_free(session, sample, exclude_id=sample.id)
    session.add(sample)
    session.commit()
    session.refresh(sample)
    return sample


@router.delete("/{sample_id}", dependencies=SUPERUSER_ONLY)
def delete_sample(session: SessionDep, sample_id: str) -> Message:
    """Delete a sample (only if it has no measurements)."""
    sample = get_or_404(session, Sample, sample_id)
    delete_or_409(session, sample, "Sample has measurements")
    return Message(message="Sample deleted successfully")
