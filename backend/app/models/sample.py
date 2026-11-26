from typing import TYPE_CHECKING

from pydantic import AwareDatetime
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.models.common import LowerId, id_column

if TYPE_CHECKING:
    from app.models.container import Container
    from app.models.measurement import Measurement


class SampleBase(SQLModel):
    # When the air was filled into the container. The sample occupies the
    # container until the next sample's filled_at.
    filled_at: AwareDatetime = Field(index=True)
    description: str | None = Field(default=None, max_length=1024)


class Sample(SampleBase, table=True):
    """Air filled into a container at a given time."""

    # A container cannot be filled twice at the same instant
    __table_args__ = (UniqueConstraint("container_id", "filled_at"),)

    id: str = id_column(primary_key=True)
    container_id: str = id_column(foreign_key="container.id", index=True)
    container: Container = Relationship(back_populates="samples")
    # passive_deletes="all": never null out/delete children from Python; the
    # database foreign key refuses deleting a parent that is still referenced.
    measurements: list[Measurement] = Relationship(
        back_populates="sample", passive_deletes="all"
    )


class SampleCreate(SampleBase):
    id: LowerId
    container_id: LowerId


class SampleUpdate(SQLModel):
    container_id: LowerId | None = None
    filled_at: AwareDatetime | None = None
    description: str | None = Field(default=None, max_length=1024)


class SamplePublic(SampleBase):
    id: str
    container_id: str


class SamplesPublic(SQLModel):
    data: list[SamplePublic]
    count: int
