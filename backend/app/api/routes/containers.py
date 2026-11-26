from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import col, func, select

from app.api.deps import SessionDep, get_current_user
from app.api.helpers import SUPERUSER_ONLY, delete_or_409, ensure_new, get_or_404
from app.models import (
    Container,
    ContainerCreate,
    ContainerPublic,
    ContainersPublic,
    ContainerUpdate,
    Message,
    Sample,
    SamplePublic,
    SamplesPublic,
)

router = APIRouter(
    prefix="/containers",
    tags=["containers"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/", response_model=ContainersPublic)
def read_containers(
    session: SessionDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> Any:
    """List containers."""
    count = session.exec(select(func.count()).select_from(Container)).one()
    statement = select(Container).order_by(col(Container.id)).offset(skip).limit(limit)
    containers = session.exec(statement).all()
    return ContainersPublic(
        data=[ContainerPublic.model_validate(c) for c in containers], count=count
    )


@router.get("/{container_id}", response_model=ContainerPublic)
def read_container(session: SessionDep, container_id: str) -> Any:
    """Get a container by id."""
    return get_or_404(session, Container, container_id)


@router.get("/{container_id}/samples", response_model=SamplesPublic)
def read_container_samples(
    session: SessionDep,
    container_id: str,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> Any:
    """Filling history of a container, newest first."""
    container = get_or_404(session, Container, container_id)
    where = col(Sample.container_id) == container.id
    count = session.exec(select(func.count()).select_from(Sample).where(where)).one()
    statement = (
        select(Sample)
        .where(where)
        .order_by(col(Sample.filled_at).desc())
        .offset(skip)
        .limit(limit)
    )
    samples = session.exec(statement).all()
    return SamplesPublic(
        data=[SamplePublic.model_validate(s) for s in samples], count=count
    )


@router.get("/{container_id}/current-sample", response_model=SamplePublic)
def read_container_current_sample(session: SessionDep, container_id: str) -> Any:
    """The sample currently in the container (the latest filling)."""
    container = get_or_404(session, Container, container_id)
    statement = (
        select(Sample)
        .where(col(Sample.container_id) == container.id)
        .order_by(col(Sample.filled_at).desc())
        .limit(1)
    )
    sample = session.exec(statement).first()
    if sample is None:
        raise HTTPException(status_code=404, detail="Container has never been filled")
    return sample


@router.post("/", dependencies=SUPERUSER_ONLY, response_model=ContainerPublic)
def create_container(session: SessionDep, container_in: ContainerCreate) -> Any:
    """Create a container."""
    ensure_new(session, Container, container_in.id)
    container = Container.model_validate(container_in)
    session.add(container)
    session.commit()
    session.refresh(container)
    return container


@router.patch(
    "/{container_id}", dependencies=SUPERUSER_ONLY, response_model=ContainerPublic
)
def update_container(
    session: SessionDep, container_id: str, container_in: ContainerUpdate
) -> Any:
    """Update a container."""
    container = get_or_404(session, Container, container_id)
    container.sqlmodel_update(container_in.model_dump(exclude_unset=True))
    session.add(container)
    session.commit()
    session.refresh(container)
    return container


@router.delete("/{container_id}", dependencies=SUPERUSER_ONLY)
def delete_container(session: SessionDep, container_id: str) -> Message:
    """Delete a container (only if it has no samples)."""
    container = get_or_404(session, Container, container_id)
    delete_or_409(session, container, "Container has samples")
    return Message(message="Container deleted successfully")
