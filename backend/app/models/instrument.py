from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.common import LowerId, id_column

if TYPE_CHECKING:
    from app.models.measurement import Measurement


class InstrumentBase(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1024)


class Instrument(InstrumentBase, table=True):
    id: str = id_column(primary_key=True)
    # passive_deletes="all": never null out/delete children from Python; the
    # database foreign key refuses deleting a parent that is still referenced.
    measurements: list[Measurement] = Relationship(
        back_populates="instrument", passive_deletes="all"
    )


class InstrumentCreate(InstrumentBase):
    id: LowerId


class InstrumentUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1024)


class InstrumentPublic(InstrumentBase):
    id: str


class InstrumentsPublic(SQLModel):
    data: list[InstrumentPublic]
    count: int
