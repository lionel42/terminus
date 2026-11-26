import csv
import io

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.domain import (
    create_compound,
    create_instrument,
    create_measurement,
    create_sample,
)

API = settings.API_V1_STR


def test_read_results_flat_rows(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    instrument = create_instrument(db)
    c1, c2 = create_compound(db), create_compound(db)
    sample = create_sample(db)
    m1 = create_measurement(
        db, instrument=instrument, sample=sample, compounds=[c1, c2]
    )
    m2 = create_measurement(db, instrument=instrument, compounds=[c1])

    r = client.get(
        f"{API}/results/",
        headers=normal_user_token_headers,
        params={"instrument_id": instrument.id},
    )
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 3

    r = client.get(
        f"{API}/results/",
        headers=normal_user_token_headers,
        params={"instrument_id": instrument.id, "compound_id": c1.id},
    )
    rows = r.json()["data"]
    assert r.json()["count"] == 2
    assert {row["measurement_id"] for row in rows} == {m1.id, m2.id}
    by_measurement = {row["measurement_id"]: row for row in rows}
    assert by_measurement[m1.id]["container_id"] == sample.container_id
    assert by_measurement[m2.id]["container_id"] is None
    assert by_measurement[m1.id]["compound_id"] == c1.id
    # Oldest first
    times = [row["measured_at"] for row in rows]
    assert times == sorted(times)


def test_read_results_csv(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    instrument = create_instrument(db)
    compound = create_compound(db)
    create_measurement(db, instrument=instrument, compounds=[compound])

    r = client.get(
        f"{API}/results/csv",
        headers=normal_user_token_headers,
        params={"instrument_id": instrument.id},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 1
    assert rows[0]["compound_id"] == compound.id
    assert rows[0]["instrument_id"] == instrument.id
    assert rows[0]["concentration"] == "10.0"
