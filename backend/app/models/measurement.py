from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from pydantic import AwareDatetime, BaseModel
from pydantic import Field as PydanticField
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.models.common import LowerId, id_column

if TYPE_CHECKING:
    from app.models.compound import Compound
    from app.models.instrument import Instrument
    from app.models.sample import Sample


class MeasurementType(StrEnum):
    AIR = "air"  # ambient air measured directly, no Sample
    BLANK = "blank"
    TANK = "tank"
    STANDARD = "standard"
    LABAIR = "labair"
    TEST = "test"


# Stored as a plain VARCHAR (not a MySQL ENUM): adding a value to
# MeasurementType needs no database migration.
MEASUREMENT_TYPE_SA = sa.Enum(
    MeasurementType,
    native_enum=False,
    create_constraint=False,
    length=32,
    values_callable=lambda enum: [member.value for member in enum],
)


# --- Per-compound results of a measurement (one chromatogram peak) ---


class MeasurementResultBase(SQLModel):
    area: float | None = None
    height: float | None = None
    retention_time: float | None = None
    concentration: float | None = None


class MeasurementResult(MeasurementResultBase, table=True):
    __tablename__ = "measurement_result"

    measurement_id: int = Field(
        foreign_key="measurement.id", primary_key=True, ondelete="CASCADE"
    )
    compound_id: str = id_column(foreign_key="compound.id", primary_key=True)
    measurement: Measurement = Relationship(back_populates="results")
    compound: Compound = Relationship(back_populates="results")


class MeasurementResultCreate(MeasurementResultBase):
    compound_id: LowerId


class MeasurementResultPublic(MeasurementResultBase):
    compound_id: str


# --- Measurement: one chromatography run on an instrument ---


class MeasurementBase(SQLModel):
    type: MeasurementType = Field(sa_type=MEASUREMENT_TYPE_SA, index=True)
    measured_at: AwareDatetime = Field(index=True)
    description: str | None = Field(default=None, max_length=1024)


class Measurement(MeasurementBase, table=True):
    """A run on an instrument. `sample_id` is set when the run analysed the
    content of a container (a Sample); it is empty e.g. for direct air."""

    # An instrument runs one thing at a time; also guards against re-importing
    # the same run twice.
    __table_args__ = (UniqueConstraint("instrument_id", "measured_at"),)

    id: int | None = Field(default=None, primary_key=True)
    instrument_id: str = id_column(foreign_key="instrument.id", index=True)
    sample_id: str | None = id_column(
        default=None, foreign_key="sample.id", index=True, nullable=True
    )
    instrument: Instrument = Relationship(back_populates="measurements")
    # Optional["Sample"], not `Sample | None`: SQLAlchemy cannot resolve a
    # union containing a forward reference to a class in another module.
    sample: Optional["Sample"] = Relationship(back_populates="measurements")  # noqa: UP037, UP045
    results: list[MeasurementResult] = Relationship(
        back_populates="measurement", cascade_delete=True
    )


class MeasurementCreate(MeasurementBase):
    instrument_id: LowerId
    sample_id: LowerId | None = None
    # Optional: create the per-compound results in the same request
    results: list[MeasurementResultCreate] = []


class MeasurementUpdate(SQLModel):
    type: MeasurementType | None = None
    instrument_id: LowerId | None = None
    sample_id: LowerId | None = None
    measured_at: AwareDatetime | None = None
    description: str | None = Field(default=None, max_length=1024)


class MeasurementPublic(MeasurementBase):
    id: int
    instrument_id: str
    sample_id: str | None


class MeasurementPublicWithResults(MeasurementPublic):
    results: list[MeasurementResultPublic] = []


class MeasurementsPublic(SQLModel):
    data: list[MeasurementPublic]
    count: int


# --- Query filters (used as query parameters) ---


class MeasurementFilters(BaseModel):
    instrument_id: LowerId | None = None
    type: MeasurementType | None = None
    sample_id: LowerId | None = None
    container_id: LowerId | None = None
    measured_from: AwareDatetime | None = None
    measured_to: AwareDatetime | None = None


class ResultFilters(MeasurementFilters):
    compound_id: LowerId | None = None


# FastAPI expands a model into separate query parameters only when it is the
# endpoint's single query parameter, hence pagination lives in these models.
class MeasurementQuery(MeasurementFilters):
    skip: int = PydanticField(default=0, ge=0)
    limit: int = PydanticField(default=100, ge=1, le=1000)


class ResultQuery(ResultFilters):
    skip: int = PydanticField(default=0, ge=0)
    limit: int = PydanticField(default=1000, ge=1, le=100_000)


# --- Bulk import ---


class ImportMode(StrEnum):
    SKIP = "skip"  # keep the measurement already in the DB
    REPLACE = "replace"  # overwrite it (fields and results) with the imported one


class MeasurementImportReport(SQLModel):
    created: int
    skipped: int
    replaced: int


# --- Flat result rows, ready for analysis/plotting ---


class ResultRow(SQLModel):
    measurement_id: int
    measured_at: datetime
    type: MeasurementType
    instrument_id: str
    sample_id: str | None
    container_id: str | None
    compound_id: str
    area: float | None
    height: float | None
    retention_time: float | None
    concentration: float | None


class ResultRowsPublic(SQLModel):
    data: list[ResultRow]
    count: int
