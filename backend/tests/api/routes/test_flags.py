"""Quality flags of measurements (whole run) and results (one compound)."""

from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import UNUSABLE, QualityFlag
from tests.utils.domain import create_compound, create_instrument, random_time

API = settings.API_V1_STR
INVALID = int(QualityFlag.INVALID)
SUSPECT = int(QualityFlag.SUSPECT)


def _create(
    client: TestClient, headers: dict[str, str], instrument_id: str, **fields: Any
) -> dict[str, Any]:
    payload = {
        "type": "air",
        "instrument_id": instrument_id,
        "measured_at": random_time().isoformat(),
        **fields,
    }
    r = client.post(f"{API}/measurements/", headers=headers, json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def test_flag_list(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{API}/measurements/flags", headers=normal_user_token_headers)
    assert r.status_code == 200, r.text
    flags = {f["name"]: f for f in r.json()}
    assert flags["INVALID"]["value"] == 1 and flags["INVALID"]["unusable"]
    assert not flags["SUSPECT"]["unusable"]
    assert all(f["description"] for f in flags.values())


def test_flags_default_and_validation(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    instrument = create_instrument(db)
    compound = create_compound(db)
    data = _create(
        client,
        superuser_token_headers,
        instrument.id,
        results=[{"compound_id": compound.id, "area": 1.0}],
    )
    assert data["flags"] == 0 and data["flag_comment"] is None
    assert data["results"][0]["flags"] == 0

    for flags in (-1, 1 << 30):
        r = client.post(
            f"{API}/measurements/",
            headers=superuser_token_headers,
            json={
                "type": "air",
                "instrument_id": instrument.id,
                "measured_at": random_time().isoformat(),
                "flags": flags,
            },
        )
        assert r.status_code == 422, flags


def test_set_and_filter_flags(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    instrument = create_instrument(db)
    c1, c2 = create_compound(db), create_compound(db)
    headers = superuser_token_headers
    results = [{"compound_id": c1.id, "area": 1.0}, {"compound_id": c2.id, "area": 2.0}]
    # a run flagged as a whole, and a run with one compound flagged
    bad_run = _create(
        client,
        headers,
        instrument.id,
        flags=INVALID,
        flag_comment="valve problem",
        results=results,
    )
    good_run = _create(
        client,
        headers,
        instrument.id,
        results=[
            {
                "compound_id": c1.id,
                "area": 1.0,
                "flags": SUSPECT,
                "flag_comment": "small",
            },
            {"compound_id": c2.id, "area": 2.0},
        ],
    )

    r = client.get(
        f"{API}/measurements/",
        headers=headers,
        params={"instrument_id": instrument.id, "exclude_flags": int(UNUSABLE)},
    )
    assert [m["id"] for m in r.json()["data"]] == [good_run["id"]]

    params = {"instrument_id": instrument.id}
    r = client.get(f"{API}/results/", headers=headers, params=params)
    rows = r.json()["data"]
    assert len(rows) == 4
    flagged = next(row for row in rows if row["measurement_id"] == bad_run["id"])
    assert flagged["measurement_flags"] == INVALID
    assert flagged["measurement_flag_comment"] == "valve problem"
    assert flagged["flags"] == 0

    # unusable: drops the flagged run; SUSPECT on a result: drops that result
    r = client.get(
        f"{API}/results/", headers=headers, params={**params, "exclude_flags": UNUSABLE}
    )
    assert r.json()["count"] == 2
    r = client.get(
        f"{API}/results/",
        headers=headers,
        params={**params, "exclude_flags": int(UNUSABLE | QualityFlag.SUSPECT)},
    )
    assert [
        (row["measurement_id"], row["compound_id"]) for row in r.json()["data"]
    ] == [(good_run["id"], c2.id)]


def test_update_flags(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    instrument = create_instrument(db)
    compound = create_compound(db)
    headers = superuser_token_headers
    data = _create(
        client,
        headers,
        instrument.id,
        results=[{"compound_id": compound.id, "area": 1.0}],
    )
    url = f"{API}/measurements/{data['id']}"

    r = client.patch(
        url, headers=headers, json={"flags": INVALID, "flag_comment": "leak"}
    )
    assert r.status_code == 200, r.text
    assert (r.json()["flags"], r.json()["flag_comment"]) == (INVALID, "leak")

    r = client.patch(
        f"{url}/results/{compound.id.upper()}",
        headers=headers,
        json={"flags": SUSPECT, "flag_comment": "shoulder"},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {**r.json(), "flags": SUSPECT, "flag_comment": "shoulder"}
    assert r.json()["area"] == 1.0  # the values are kept

    r = client.patch(
        f"{url}/results/{compound.id}", headers=headers, json={"flags": 1 << 20}
    )
    assert r.status_code == 422
    r = client.patch(f"{url}/results/nope", headers=headers, json={"flags": 0})
    assert r.status_code == 404


def test_normal_user_cannot_flag(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.patch(
        f"{API}/measurements/1/results/x", headers=normal_user_token_headers, json={}
    )
    assert r.status_code == 403


def test_unusable_flags_of_the_frontend() -> None:
    # frontend/src/lib/flags.ts UNUSABLE_FLAGS mirrors this value: change both
    assert int(UNUSABLE) == 0b11


def test_null_and_unknown_flags_rejected(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    instrument = create_instrument(db)
    compound = create_compound(db)
    headers = superuser_token_headers
    data = _create(
        client,
        headers,
        instrument.id,
        flags=INVALID,
        results=[{"compound_id": compound.id, "area": 1.0}],
    )
    url = f"{API}/measurements/{data['id']}"
    for target in (url, f"{url}/results/{compound.id}"):
        r = client.patch(target, headers=headers, json={"flags": None})
        assert r.status_code == 422, (target, r.text)
        # a comment alone leaves the flags as they are
        r = client.patch(target, headers=headers, json={"flag_comment": "x"})
        assert r.status_code == 200, r.text
    assert client.get(url, headers=headers).json()["flags"] == INVALID

    for path in ("measurements/", "results/"):
        r = client.get(
            f"{API}/{path}", headers=headers, params={"exclude_flags": 1 << 20}
        )
        assert r.status_code == 422, path


def test_replace_import_keeps_flags(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    instrument = create_instrument(db)
    c1, c2 = create_compound(db), create_compound(db)
    headers = superuser_token_headers
    run = {
        "type": "air",
        "instrument_id": instrument.id,
        "measured_at": random_time().isoformat(),
        "flags": int(QualityFlag.POLLUTION),
        "flag_comment": "P",
        "results": [
            {"compound_id": c1.id, "area": 1.0, "flag_comment": "H"},
            {"compound_id": c2.id, "area": 2.0},
        ],
    }
    r = client.post(f"{API}/measurements/import", headers=headers, json=[run])
    assert r.status_code == 200, r.text
    data = client.get(
        f"{API}/measurements/", headers=headers, params={"instrument_id": instrument.id}
    ).json()["data"][0]
    url = f"{API}/measurements/{data['id']}"
    # flagged in terminus by a person
    client.patch(url, headers=headers, json={"flags": INVALID, "flag_comment": "leak"})
    client.patch(
        f"{url}/results/{c1.id}",
        headers=headers,
        json={"flags": SUSPECT, "flag_comment": "shoulder"},
    )

    run["results"][0]["area"] = 5.0
    for _ in range(2):  # twice: the comments are not repeated
        r = client.post(
            f"{API}/measurements/import",
            headers=headers,
            params={"mode": "replace"},
            json=[run],
        )
        assert r.json()["replaced"] == 1, r.text
    data = client.get(url, headers=headers).json()
    assert data["flags"] == INVALID | QualityFlag.POLLUTION
    assert data["flag_comment"] == "leak; P"
    results = {r["compound_id"]: r for r in data["results"]}
    assert results[c1.id]["area"] == 5.0
    assert (results[c1.id]["flags"], results[c1.id]["flag_comment"]) == (
        SUSPECT,
        "shoulder; H",
    )
    assert (results[c2.id]["flags"], results[c2.id]["flag_comment"]) == (0, None)
