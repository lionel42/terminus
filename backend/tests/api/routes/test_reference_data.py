"""CRUD behaviour shared by compounds, instruments and containers."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.domain import (
    create_compound,
    create_measurement,
    create_sample,
    random_id,
)

API = settings.API_V1_STR
ENDPOINTS = {
    "compounds": {"iupac_name": "methane", "unit": "ppb"},
    "instruments": {"name": "Medusa GC-MS"},
    "containers": {"kind": "flask"},
}
PARAMS = pytest.mark.parametrize("endpoint,payload", list(ENDPOINTS.items()))


@PARAMS
def test_create_lowercases_id(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    endpoint: str,
    payload: dict[str, str],
) -> None:
    raw_id = random_id().upper()
    r = client.post(
        f"{API}/{endpoint}/",
        headers=superuser_token_headers,
        json={"id": raw_id, **payload},
    )
    assert r.status_code == 200, r.text
    assert r.json()["id"] == raw_id.lower()

    # Lookup is case-insensitive
    r = client.get(f"{API}/{endpoint}/{raw_id}", headers=superuser_token_headers)
    assert r.status_code == 200
    assert r.json()["id"] == raw_id.lower()


@PARAMS
def test_create_duplicate_conflicts(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    endpoint: str,
    payload: dict[str, str],
) -> None:
    new_id = random_id()
    body = {"id": new_id, **payload}
    r = client.post(f"{API}/{endpoint}/", headers=superuser_token_headers, json=body)
    assert r.status_code == 200
    body["id"] = new_id.upper()
    r = client.post(f"{API}/{endpoint}/", headers=superuser_token_headers, json=body)
    assert r.status_code == 409


@pytest.mark.parametrize(
    "bad_id", ["has space", "dot.ted", "-x", "_x", "", "x" * 65, "cö2"]
)
def test_create_rejects_invalid_id(
    client: TestClient, superuser_token_headers: dict[str, str], bad_id: str
) -> None:
    r = client.post(
        f"{API}/compounds/", headers=superuser_token_headers, json={"id": bad_id}
    )
    assert r.status_code == 422


@PARAMS
def test_create_accepts_dash_and_underscore(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    endpoint: str,
    payload: dict[str, str],
) -> None:
    # GCwerks tank names, e.g. E-223-D2 or 14m_air
    raw_id = f"E-{random_id()}_D2"
    r = client.post(
        f"{API}/{endpoint}/",
        headers=superuser_token_headers,
        json={"id": raw_id, **payload},
    )
    assert r.status_code == 200, r.text
    assert r.json()["id"] == raw_id.lower()
    r = client.get(f"{API}/{endpoint}/{raw_id}", headers=superuser_token_headers)
    assert r.status_code == 200, r.text


@PARAMS
def test_list_update_delete(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    endpoint: str,
    payload: dict[str, str],
) -> None:
    new_id = random_id()
    client.post(
        f"{API}/{endpoint}/",
        headers=superuser_token_headers,
        json={"id": new_id, **payload},
    )

    r = client.get(
        f"{API}/{endpoint}/", headers=superuser_token_headers, params={"limit": 1000}
    )
    assert r.status_code == 200
    assert r.json()["count"] >= 1
    assert new_id in [obj["id"] for obj in r.json()["data"]]

    r = client.patch(
        f"{API}/{endpoint}/{new_id}",
        headers=superuser_token_headers,
        json={"description": "updated"},
    )
    assert r.status_code == 200
    assert r.json()["description"] == "updated"
    for key, value in payload.items():
        assert r.json()[key] == value  # untouched fields are kept

    r = client.delete(f"{API}/{endpoint}/{new_id}", headers=superuser_token_headers)
    assert r.status_code == 200
    r = client.get(f"{API}/{endpoint}/{new_id}", headers=superuser_token_headers)
    assert r.status_code == 404


@PARAMS
def test_normal_user_can_read_not_write(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    endpoint: str,
    payload: dict[str, str],
) -> None:
    r = client.get(f"{API}/{endpoint}/", headers=normal_user_token_headers)
    assert r.status_code == 200
    r = client.post(
        f"{API}/{endpoint}/",
        headers=normal_user_token_headers,
        json={"id": random_id(), **payload},
    )
    assert r.status_code == 403
    r = client.patch(
        f"{API}/{endpoint}/{random_id()}", headers=normal_user_token_headers, json={}
    )
    assert r.status_code == 403
    r = client.delete(
        f"{API}/{endpoint}/{random_id()}", headers=normal_user_token_headers
    )
    assert r.status_code == 403


@pytest.mark.parametrize("endpoint", list(ENDPOINTS))
def test_requires_login(client: TestClient, endpoint: str) -> None:
    r = client.get(f"{API}/{endpoint}/")
    assert r.status_code == 401


def test_delete_referenced_compound_conflicts(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    compound = create_compound(db)
    create_measurement(db, compounds=[compound])
    r = client.delete(f"{API}/compounds/{compound.id}", headers=superuser_token_headers)
    assert r.status_code == 409


def test_delete_filled_container_conflicts(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    sample = create_sample(db)
    r = client.delete(
        f"{API}/containers/{sample.container_id}", headers=superuser_token_headers
    )
    assert r.status_code == 409
