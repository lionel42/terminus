from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.domain import (
    create_container,
    create_measurement,
    create_sample,
    random_id,
)

API = settings.API_V1_STR


def test_create_sample(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    container = create_container(db)
    sample_id = random_id()
    r = client.post(
        f"{API}/samples/",
        headers=superuser_token_headers,
        json={
            "id": sample_id.upper(),
            "container_id": container.id.upper(),
            "filled_at": "2026-03-01T10:00:00+01:00",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["id"] == sample_id
    assert data["container_id"] == container.id
    # Stored and returned in UTC
    assert data["filled_at"].startswith("2026-03-01T09:00:00")


def test_create_sample_unknown_container(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{API}/samples/",
        headers=superuser_token_headers,
        json={
            "id": random_id(),
            "container_id": random_id(),
            "filled_at": "2026-03-01T10:00:00Z",
        },
    )
    assert r.status_code == 422


def test_create_sample_naive_datetime_rejected(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    container = create_container(db)
    r = client.post(
        f"{API}/samples/",
        headers=superuser_token_headers,
        json={
            "id": random_id(),
            "container_id": container.id,
            "filled_at": "2026-03-01T10:00:00",
        },
    )
    assert r.status_code == 422


def test_same_filling_time_conflicts(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    existing = create_sample(db)
    r = client.post(
        f"{API}/samples/",
        headers=superuser_token_headers,
        json={
            "id": random_id(),
            "container_id": existing.container_id,
            "filled_at": existing.filled_at.isoformat(),
        },
    )
    assert r.status_code == 409


def test_container_history_and_current_sample(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    container = create_container(db)
    r = client.get(
        f"{API}/containers/{container.id}/current-sample",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404

    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    first = create_sample(db, container=container, filled_at=t0)
    second = create_sample(db, container=container, filled_at=t0 + timedelta(days=7))

    r = client.get(
        f"{API}/containers/{container.id}/samples", headers=superuser_token_headers
    )
    assert r.status_code == 200
    assert r.json()["count"] == 2
    assert [s["id"] for s in r.json()["data"]] == [second.id, first.id]

    r = client.get(
        f"{API}/containers/{container.id}/current-sample",
        headers=superuser_token_headers,
    )
    assert r.json()["id"] == second.id


def test_list_samples_filters(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    container = create_container(db)
    t0 = datetime(2030, 1, 1, tzinfo=UTC)
    early = create_sample(db, container=container, filled_at=t0)
    late = create_sample(db, container=container, filled_at=t0 + timedelta(days=30))

    r = client.get(
        f"{API}/samples/",
        headers=superuser_token_headers,
        params={
            "container_id": container.id,
            "filled_from": (t0 + timedelta(days=1)).isoformat(),
        },
    )
    assert r.status_code == 200
    assert [s["id"] for s in r.json()["data"]] == [late.id]
    assert early.id not in [s["id"] for s in r.json()["data"]]


def test_update_and_delete_sample(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    sample = create_sample(db)
    r = client.patch(
        f"{API}/samples/{sample.id}",
        headers=superuser_token_headers,
        json={"description": "leaky valve"},
    )
    assert r.status_code == 200
    assert r.json()["description"] == "leaky valve"

    measured = create_sample(db)
    create_measurement(db, sample=measured)
    r = client.delete(f"{API}/samples/{measured.id}", headers=superuser_token_headers)
    assert r.status_code == 409

    r = client.delete(f"{API}/samples/{sample.id}", headers=superuser_token_headers)
    assert r.status_code == 200
