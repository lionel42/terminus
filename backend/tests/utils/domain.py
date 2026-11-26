import random
import string
from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from app.models import (
    Compound,
    Container,
    Instrument,
    Measurement,
    MeasurementResult,
    MeasurementType,
    Sample,
)


def random_id() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=12))


def random_time() -> datetime:
    """A random, timezone-aware time (unique enough to avoid collisions)."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return base + timedelta(seconds=random.randint(0, 10**9))


def create_compound(db: Session) -> Compound:
    compound = Compound(id=random_id(), name="Test compound", unit="ppb")
    db.add(compound)
    db.commit()
    db.refresh(compound)
    return compound


def create_instrument(db: Session) -> Instrument:
    instrument = Instrument(id=random_id(), name="Test instrument")
    db.add(instrument)
    db.commit()
    db.refresh(instrument)
    return instrument


def create_container(db: Session) -> Container:
    container = Container(id=random_id(), kind="flask")
    db.add(container)
    db.commit()
    db.refresh(container)
    return container


def create_sample(
    db: Session, container: Container | None = None, filled_at: datetime | None = None
) -> Sample:
    container = container or create_container(db)
    sample = Sample(
        id=random_id(),
        container_id=container.id,
        filled_at=filled_at or random_time(),
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample


def create_measurement(
    db: Session,
    *,
    instrument: Instrument | None = None,
    sample: Sample | None = None,
    compounds: list[Compound] | None = None,
    type: MeasurementType = MeasurementType.TANK,
) -> Measurement:
    instrument = instrument or create_instrument(db)
    measurement = Measurement(
        type=type,
        instrument_id=instrument.id,
        sample_id=sample.id if sample else None,
        measured_at=random_time(),
    )
    db.add(measurement)
    db.flush()
    assert measurement.id is not None
    for i, compound in enumerate(compounds or []):
        db.add(
            MeasurementResult(
                measurement_id=measurement.id,
                compound_id=compound.id,
                area=float(i + 1),
                concentration=float(10 * (i + 1)),
            )
        )
    db.commit()
    db.refresh(measurement)
    return measurement
