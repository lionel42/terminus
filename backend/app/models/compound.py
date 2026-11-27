"""Compounds and their reference data: aliases, identifiers, boiling points."""

import re
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from pydantic import field_validator
from sqlmodel import Field, Relationship, SQLModel

from app.models.common import LowerId, id_column

if TYPE_CHECKING:
    from app.models.measurement import MeasurementResult


class CompoundStatus(StrEnum):
    MEASURED = "measured"  # quantified routinely
    TARGET = "target"  # wanted, not (yet) quantified
    SUSPECT = "suspect"  # tentatively identified


# Plain VARCHAR like MeasurementType: adding a status needs no migration
COMPOUND_STATUS_SA = sa.Enum(
    CompoundStatus,
    native_enum=False,
    create_constraint=False,
    length=16,
    values_callable=lambda enum: [member.value for member in enum],
)

CAS_RE = re.compile(r"^(\d{2,7})-(\d{2})-(\d)$")
INCHIKEY_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
WIKIDATA_RE = re.compile(r"^Q\d+$")


def cas_is_valid(cas: str) -> bool:
    """Check the format and the check digit of a CAS registry number."""
    match = CAS_RE.match(cas)
    if not match:
        return False
    digits = (match.group(1) + match.group(2))[::-1]
    checksum = sum(int(d) * (i + 1) for i, d in enumerate(digits)) % 10
    return checksum == int(match.group(3))


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


# --- Compound ---


class CompoundBase(SQLModel):
    # Official nomenclature (not aliases): industrial / ASHRAE designation
    # such as "CFC-11", "HCFC-22", "HFC-134a", "Halon-1211", and IUPAC name.
    industrial_name: str | None = Field(default=None, max_length=64, index=True)
    iupac_name: str | None = Field(default=None, max_length=1024)
    formula: str | None = Field(default=None, max_length=64)
    # Unit of the reported concentration, e.g. "ppm", "ppb", "ppt"
    unit: str | None = Field(default=None, max_length=32)
    # None: not given
    status: CompoundStatus | None = Field(
        default=None, sa_type=COMPOUND_STATUS_SA, index=True
    )
    description: str | None = Field(default=None, max_length=1024)

    # Identifiers
    cas_number: str | None = Field(default=None, max_length=16, index=True)
    pubchem_cid: int | None = Field(default=None, ge=1, index=True)
    inchikey: str | None = Field(default=None, max_length=27, index=True)
    inchi: str | None = Field(default=None, max_length=2048)
    smiles: str | None = Field(default=None, max_length=1024)
    wikidata_id: str | None = Field(default=None, max_length=16)
    # g/mol
    molar_mass: float | None = Field(default=None, gt=0)

    @field_validator(
        "industrial_name",
        "iupac_name",
        "formula",
        "unit",
        "description",
        "inchi",
        "smiles",
        mode="before",
    )
    @classmethod
    def _strip(cls, value: Any) -> Any:
        return _blank_to_none(value)

    @field_validator("cas_number", mode="before")
    @classmethod
    def _check_cas(cls, value: Any) -> Any:
        value = _blank_to_none(value)
        if value is not None and not cas_is_valid(value):
            raise ValueError("invalid CAS number (format or check digit)")
        return value

    @field_validator("inchikey", mode="before")
    @classmethod
    def _check_inchikey(cls, value: Any) -> Any:
        value = _blank_to_none(value)
        if value is not None:
            value = value.upper()
            if not INCHIKEY_RE.match(value):
                raise ValueError("invalid InChIKey")
        return value

    @field_validator("wikidata_id", mode="before")
    @classmethod
    def _check_wikidata(cls, value: Any) -> Any:
        value = _blank_to_none(value)
        if value is not None:
            value = value.upper()
            if not WIKIDATA_RE.match(value):
                raise ValueError("invalid Wikidata id, expected e.g. Q37129")
        return value


class Compound(CompoundBase, table=True):
    id: str = id_column(primary_key=True)
    # passive_deletes="all": never null out/delete children from Python; the
    # database foreign key refuses deleting a parent that is still referenced.
    results: list[MeasurementResult] = Relationship(
        back_populates="compound", passive_deletes="all"
    )
    # Reference data goes away with the compound (ON DELETE CASCADE)
    aliases: list[CompoundAlias] = Relationship(
        back_populates="compound", cascade_delete=True, passive_deletes=True
    )
    boiling_points: list[CompoundBoilingPoint] = Relationship(
        back_populates="compound", cascade_delete=True, passive_deletes=True
    )


class CompoundCreate(CompoundBase):
    id: LowerId


class CompoundUpdate(CompoundBase):
    """Every field is optional: send only what changes, null clears."""


class CompoundPublic(CompoundBase):
    id: str


# --- Aliases: other names (trade names, synonyms, in-house labels) ---


class CompoundAliasBase(SQLModel):
    alias: str = Field(min_length=1, max_length=255)

    @field_validator("alias", mode="before")
    @classmethod
    def _strip(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class CompoundAlias(CompoundAliasBase, table=True):
    __tablename__ = "compound_alias"

    id: int | None = Field(default=None, primary_key=True)
    # Unique over all compounds: an alias names exactly one compound.
    # The default MySQL collation compares case-insensitively.
    alias: str = Field(max_length=255, unique=True)
    compound_id: str = id_column(
        foreign_key="compound.id", ondelete="CASCADE", index=True
    )
    compound: Compound = Relationship(back_populates="aliases")


class CompoundAliasCreate(CompoundAliasBase):
    pass


class CompoundAliasPublic(CompoundAliasBase):
    id: int
    compound_id: str


# --- Boiling points, each with its source ---


class BoilingPointBase(SQLModel):
    # At normal pressure (760 mmHg) unless stated in `note`
    temperature_c: float = Field(ge=-273.15)
    # e.g. "PubChem: Hazardous Substances Data Bank (HSDB)", "CRC Handbook"
    source: str = Field(min_length=1, max_length=255)
    reference_url: str | None = Field(default=None, max_length=2048)
    # Free text, e.g. the original value "74.7 °F at 760 mmHg (NTP, 1992)"
    note: str | None = Field(default=None, max_length=1024)

    @field_validator("source", "reference_url", "note", mode="before")
    @classmethod
    def _strip(cls, value: Any) -> Any:
        return _blank_to_none(value)

    @field_validator("reference_url")
    @classmethod
    def _check_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("http://", "https://")):
            raise ValueError("reference_url must start with http:// or https://")
        return value


class CompoundBoilingPoint(BoilingPointBase, table=True):
    __tablename__ = "compound_boiling_point"

    id: int | None = Field(default=None, primary_key=True)
    compound_id: str = id_column(
        foreign_key="compound.id", ondelete="CASCADE", index=True
    )
    compound: Compound = Relationship(back_populates="boiling_points")


class BoilingPointCreate(BoilingPointBase):
    pass


class BoilingPointPublic(BoilingPointBase):
    id: int
    compound_id: str


# --- Responses ---


class CompoundPublicWithDetails(CompoundPublic):
    aliases: list[CompoundAliasPublic] = []
    boiling_points: list[BoilingPointPublic] = []


class CompoundsPublic(SQLModel):
    data: list[CompoundPublicWithDetails]
    count: int
