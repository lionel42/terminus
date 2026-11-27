"""Quality flags of measurements and results, stored as a bit mask.

A measurement has flags that apply to all its results (e.g. a valve problem
during the run); a result has the flags of that compound only (e.g. a peak
not integrated). A value is unusable when either has an UNUSABLE bit.

The bits are independent of the instrument software; each importer maps its
own flags to them (see importers/gcwerks for GCwerks). Never renumber a bit:
the numbers are stored in the database. Add new ones at the end.
"""

from enum import IntFlag

from pydantic import BaseModel


class QualityFlag(IntFlag):
    INVALID = 1 << 0
    AUTO_REJECTED = 1 << 1
    SUSPECT = 1 << 2
    NOT_IN_CALIBRATION = 1 << 3
    POLLUTION = 1 << 4
    FROM_HEIGHT = 1 << 5


FLAG_DESCRIPTIONS: dict[QualityFlag, str] = {
    QualityFlag.INVALID: "Rejected by a person; do not use.",
    QualityFlag.AUTO_REJECTED: (
        "Rejected by the automatic checks of the instrument software"
        " (e.g. a standard out of its tolerance); do not use."
    ),
    QualityFlag.SUSPECT: "Questionable; check before use.",
    QualityFlag.NOT_IN_CALIBRATION: "A standard measurement left out of the calibration.",
    QualityFlag.POLLUTION: "Pollution event: not background air.",
    QualityFlag.FROM_HEIGHT: "The concentration is from the peak height, not the area.",
}

UNUSABLE = QualityFlag.INVALID | QualityFlag.AUTO_REJECTED
"""Bits that make a value unusable."""
ALL_FLAGS = int(sum(QualityFlag))  # every known bit


def check_flags(value: int) -> int:
    """Pydantic validator: only known bits."""
    unknown = value & ~ALL_FLAGS  # a plain int: ~ of an IntFlag keeps known bits only
    if unknown:
        raise ValueError(f"unknown flag bits: {unknown} (known: {ALL_FLAGS})")
    return value


class FlagInfo(BaseModel):
    name: str
    value: int
    description: str
    unusable: bool


def flag_infos() -> list[FlagInfo]:
    return [
        FlagInfo(
            name=flag.name or "",
            value=int(flag),
            description=FLAG_DESCRIPTIONS[flag],
            unusable=bool(flag & UNUSABLE),
        )
        for flag in QualityFlag
    ]
