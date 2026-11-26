from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.common import LowerId, id_column

if TYPE_CHECKING:
    from app.models.sample import Sample


class ContainerBase(SQLModel):
    # e.g. "flask", "canister", "bag"
    kind: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=1024)


class Container(ContainerBase, table=True):
    """A reusable vessel. It holds one air sample at a time; `samples` is its
    filling history. The current sample is the one with the latest filled_at."""

    id: str = id_column(primary_key=True)
    # passive_deletes="all": never null out/delete children from Python; the
    # database foreign key refuses deleting a parent that is still referenced.
    samples: list[Sample] = Relationship(
        back_populates="container", passive_deletes="all"
    )


class ContainerCreate(ContainerBase):
    id: LowerId


class ContainerUpdate(SQLModel):
    kind: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=1024)


class ContainerPublic(ContainerBase):
    id: str


class ContainersPublic(SQLModel):
    data: list[ContainerPublic]
    count: int
