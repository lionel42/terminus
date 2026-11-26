from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app.core.config import settings
from app.models import MeasurementResult
from tests.utils.domain import (
    create_compound,
    create_instrument,
    create_measurement,
    create_sample,
    random_id,
    random_time,
)

API = settings.API_V1_STR


def _payload(db: Session, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "tank",
        "instrument_id": create_instrument(db).id,
        "measured_at": random_time().isoformat(),
    }
    payload.update(overrides)
    return payload


def test_create_measurement_with_results(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    sample = create_sample(db)
    ch4, n2o = create_compound(db), create_compound(db)
    payload = _payload(
        db,
        sample_id=sample.id.upper(),
        results=[
            {"compound_id": ch4.id.upper(), "area": 1.5, "concentration": 1950.2},
            {"compound_id": n2o.id, "area": 0.3},
        ],
    )
    r = client.post(
        f"{API}/measurements/", headers=superuser_token_headers, json=payload
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data["id"], int)
    assert data["sample_id"] == sample.id
    results = {res["compound_id"]: res for res in data["results"]}
    assert results[ch4.id]["concentration"] == 1950.2
    assert results[n2o.id]["concentration"] is None

    r = client.get(f"{API}/measurements/{data['id']}", headers=superuser_token_headers)
    assert r.status_code == 200
    assert len(r.json()["results"]) == 2


def test_create_air_measurement_without_sample(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    r = client.post(
        f"{API}/measurements/",
        headers=superuser_token_headers,
        json=_payload(db, type="air"),
    )
    assert r.status_code == 200, r.text
    assert r.json()["sample_id"] is None
    assert r.json()["type"] == "air"


def test_create_measurement_validation(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    compound = create_compound(db)
    bad_payloads = [
        _payload(db, type="bogus"),
        _payload(db, instrument_id=random_id()),
        _payload(db, sample_id=random_id()),
        _payload(db, results=[{"compound_id": random_id()}]),
        _payload(
            db,
            results=[
                {"compound_id": compound.id},
                {"compound_id": compound.id.upper()},
            ],
        ),
        _payload(db, measured_at="2026-01-01T10:00:00"),  # no timezone
    ]
    for payload in bad_payloads:
        r = client.post(
            f"{API}/measurements/", headers=superuser_token_headers, json=payload
        )
        assert r.status_code == 422, payload


def test_same_instrument_same_time_conflicts(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    payload = _payload(db)
    r = client.post(
        f"{API}/measurements/", headers=superuser_token_headers, json=payload
    )
    assert r.status_code == 200
    r = client.post(
        f"{API}/measurements/", headers=superuser_token_headers, json=payload
    )
    assert r.status_code == 409


def test_update_and_replace_results(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    c1, c2, c3 = create_compound(db), create_compound(db), create_compound(db)
    measurement = create_measurement(db, compounds=[c1, c2])

    r = client.patch(
        f"{API}/measurements/{measurement.id}",
        headers=superuser_token_headers,
        json={"type": "standard", "description": "cal run"},
    )
    assert r.status_code == 200
    assert r.json()["type"] == "standard"
    assert len(r.json()["results"]) == 2

    r = client.put(
        f"{API}/measurements/{measurement.id}/results",
        headers=superuser_token_headers,
        json=[{"compound_id": c3.id, "area": 42.0}],
    )
    assert r.status_code == 200, r.text
    assert [res["compound_id"] for res in r.json()["results"]] == [c3.id]


def test_delete_measurement_cascades_results(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    measurement = create_measurement(db, compounds=[create_compound(db)])
    r = client.delete(
        f"{API}/measurements/{measurement.id}", headers=superuser_token_headers
    )
    assert r.status_code == 200
    left = db.exec(
        select(MeasurementResult).where(
            col(MeasurementResult.measurement_id) == measurement.id
        )
    ).all()
    assert left == []


def test_list_measurements_filters(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    instrument = create_instrument(db)
    sample = create_sample(db)
    from_container = create_measurement(db, instrument=instrument, sample=sample)
    air = create_measurement(db, instrument=instrument, type="air")  # type: ignore[arg-type]

    r = client.get(
        f"{API}/measurements/",
        headers=superuser_token_headers,
        params={"instrument_id": instrument.id},
    )
    assert r.json()["count"] == 2

    r = client.get(
        f"{API}/measurements/",
        headers=superuser_token_headers,
        params={"container_id": sample.container_id},
    )
    assert [m["id"] for m in r.json()["data"]] == [from_container.id]

    r = client.get(
        f"{API}/measurements/",
        headers=superuser_token_headers,
        params={"instrument_id": instrument.id, "type": "air"},
    )
    assert [m["id"] for m in r.json()["data"]] == [air.id]


def test_import_skip_and_replace(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    instrument = create_instrument(db)
    compound = create_compound(db)
    runs = [
        {
            "type": "air",
            "instrument_id": instrument.id,
            "measured_at": random_time().isoformat(),
            "results": [{"compound_id": compound.id, "area": 1.0}],
        }
        for _ in range(3)
    ]
    r = client.post(
        f"{API}/measurements/import", headers=superuser_token_headers, json=runs
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"created": 3, "skipped": 0, "replaced": 0}

    # Re-import: skipped by default
    r = client.post(
        f"{API}/measurements/import", headers=superuser_token_headers, json=runs
    )
    assert r.json() == {"created": 0, "skipped": 3, "replaced": 0}

    # Replace with new values
    runs[0]["results"] = [{"compound_id": compound.id, "area": 99.0}]
    r = client.post(
        f"{API}/measurements/import",
        headers=superuser_token_headers,
        params={"mode": "replace"},
        json=runs[:1],
    )
    assert r.json() == {"created": 0, "skipped": 0, "replaced": 1}
    r = client.get(
        f"{API}/results/",
        headers=superuser_token_headers,
        params={
            "instrument_id": instrument.id,
            "measured_from": runs[0]["measured_at"],
            "measured_to": runs[0]["measured_at"],
        },
    )
    assert [row["area"] for row in r.json()["data"]] == [99.0]


def test_import_is_all_or_nothing(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    instrument = create_instrument(db)
    unknown = random_id()
    runs = [
        {
            "type": "air",
            "instrument_id": instrument.id,
            "measured_at": random_time().isoformat(),
        },
        {
            "type": "air",
            "instrument_id": unknown,
            "measured_at": random_time().isoformat(),
        },
    ]
    r = client.post(
        f"{API}/measurements/import", headers=superuser_token_headers, json=runs
    )
    assert r.status_code == 422
    assert r.json()["detail"]["missing"]["instruments"] == [unknown]

    r = client.get(
        f"{API}/measurements/",
        headers=superuser_token_headers,
        params={"instrument_id": instrument.id},
    )
    assert r.json()["count"] == 0


def test_normal_user_cannot_write(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    r = client.post(
        f"{API}/measurements/", headers=normal_user_token_headers, json=_payload(db)
    )
    assert r.status_code == 403
    r = client.post(
        f"{API}/measurements/import", headers=normal_user_token_headers, json=[]
    )
    assert r.status_code == 403
    r = client.get(f"{API}/measurements/", headers=normal_user_token_headers)
    assert r.status_code == 200
