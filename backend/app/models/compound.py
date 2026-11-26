from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.common import LowerId, id_column

if TYPE_CHECKING:
    from app.models.measurement import MeasurementResult


class CompoundBase(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    formula: str | None = Field(default=None, max_length=64)
    # Unit of the reported concentration, e.g. "ppm", "ppb", "ppt"
    unit: str | None = Field(default=None, max_length=32)
    description: str | None = Field(default=None, max_length=1024)


class Compound(CompoundBase, table=True):
    id: str = id_column(primary_key=True)
    # passive_deletes="all": never null out/delete children from Python; the
    # database foreign key refuses deleting a parent that is still referenced.
    results: list[MeasurementResult] = Relationship(
        back_populates="compound", passive_deletes="all"
    )


class CompoundCreate(CompoundBase):
    id: LowerId


class CompoundUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    formula: str | None = Field(default=None, max_length=64)
    unit: str | None = Field(default=None, max_length=32)
    description: str | None = Field(default=None, max_length=1024)


class CompoundPublic(CompoundBase):
    id: str


class CompoundsPublic(SQLModel):
    data: list[CompoundPublic]
    count: int
