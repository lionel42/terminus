"""Shared building blocks for models: string ids and generic API schemas."""

from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BeforeValidator, StringConstraints
from sqlalchemy import Dialect, String
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel

# Ids of domain objects (compounds, containers, samples, ...) are user-chosen
# alphanumeric strings, always stored lower case.
ID_MAX_LENGTH = 64
ID_PATTERN = r"^[a-z0-9]+$"
# Ids are plain ASCII: 1 byte per char and fast binary comparisons in MySQL
ID_COLLATION = "ascii_bin"


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


class LowerString(TypeDecorator[str]):
    """VARCHAR that lower-cases every value sent to the database.

    Applies to inserts/updates *and* to query parameters, so
    `session.get(Container, "ABC1")` finds the row stored as "abc1".
    This guarantees lower case in the DB even when a table model is built
    directly (which skips Pydantic validation).
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return str(value).lower()


def _normalize_id(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().lower()
    return value


# Pydantic side: normalize then validate ids received through the API.
LowerId = Annotated[
    str,
    BeforeValidator(_normalize_id),
    StringConstraints(min_length=1, max_length=ID_MAX_LENGTH, pattern=ID_PATTERN),
]


def id_column(**kwargs: Any) -> Any:
    """Field() for a lower-case string id column (primary or foreign key)."""
    return Field(
        sa_type=LowerString(ID_MAX_LENGTH, collation=ID_COLLATION),
        max_length=ID_MAX_LENGTH,
        **kwargs,
    )


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
