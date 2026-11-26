"""Small helpers shared by the domain routers."""

from typing import Any

from fastapi import Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel

from app.api.deps import get_current_active_superuser

# Add to a path operation to restrict it to superusers:
#   @router.post("/", dependencies=SUPERUSER_ONLY)
SUPERUSER_ONLY = [Depends(get_current_active_superuser)]


def get_or_404[T: SQLModel](session: Session, model: type[T], key: Any) -> T:
    """Fetch by primary key or raise 404 (for ids in the URL path)."""
    obj = session.get(model, key)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj


def require_exists(session: Session, model: type[SQLModel], key: Any) -> None:
    """Raise 422 if a referenced object (an id in the request body) is missing."""
    if session.get(model, key) is None:
        raise HTTPException(
            status_code=422,
            detail=f"{model.__name__} '{key}' does not exist",
        )


def ensure_new(session: Session, model: type[SQLModel], key: Any) -> None:
    """Raise 409 if an object with this primary key already exists."""
    if session.get(model, key) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"{model.__name__} '{key}' already exists",
        )


def delete_or_409(session: Session, obj: SQLModel, detail: str) -> None:
    """Delete, turning a foreign-key violation into a 409 (still referenced)."""
    session.delete(obj)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=detail)
