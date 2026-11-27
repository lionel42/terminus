"""Compound-specific behaviour: identifiers, status, aliases, boiling points."""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import cas_is_valid
from tests.utils.domain import create_compound, create_measurement, random_id

API = settings.API_V1_STR


def test_cas_checksum() -> None:
    assert cas_is_valid("75-69-4")  # CFC-11
    assert cas_is_valid("7732-18-5")  # water
    assert not cas_is_valid("75-69-5")
    assert not cas_is_valid("7569-4")


def test_create_with_identifiers(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    body = {
        "id": random_id(),
        "industrial_name": "CFC-11",
        "iupac_name": "trichloro(fluoro)methane",
        "formula": "CCl3F",
        "status": "measured",
        "cas_number": " 75-69-4 ",
        "pubchem_cid": 6389,
        "inchikey": "cyrmsutzvyginf-uhfffaoysa-n",
        "inchi": "InChI=1S/CCl3F/c2-1(3,4)5",
        "smiles": "C(F)(Cl)(Cl)Cl",
        "wikidata_id": "q423000",
        "molar_mass": 137.36,
    }
    r = client.post(f"{API}/compounds/", headers=superuser_token_headers, json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["cas_number"] == "75-69-4"
    assert data["inchikey"] == "CYRMSUTZVYGINF-UHFFFAOYSA-N"
    assert data["wikidata_id"] == "Q423000"
    assert data["status"] == "measured"
    assert data["aliases"] == [] and data["boiling_points"] == []


def test_invalid_identifiers_rejected(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    for field, value in [
        ("cas_number", "75-69-5"),
        ("inchikey", "NOT-A-KEY"),
        ("wikidata_id", "37129"),
        ("status", "maybe"),
        ("pubchem_cid", 0),
    ]:
        r = client.post(
            f"{API}/compounds/",
            headers=superuser_token_headers,
            json={"id": random_id(), field: value},
        )
        assert r.status_code == 422, (field, r.text)


def test_update_clears_and_sets_status(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    compound = create_compound(db)
    url = f"{API}/compounds/{compound.id}"
    r = client.patch(url, headers=superuser_token_headers, json={"status": "target"})
    assert r.json()["status"] == "target"
    assert r.json()["iupac_name"] == "test compound"
    r = client.patch(
        url, headers=superuser_token_headers, json={"status": None, "unit": ""}
    )
    assert r.json()["status"] is None
    assert r.json()["unit"] is None


def test_filter_and_search(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    compound = create_compound(db)
    alias = f"Freon {random_id()}"
    client.patch(
        f"{API}/compounds/{compound.id}",
        headers=superuser_token_headers,
        json={"status": "suspect"},
    )
    client.post(
        f"{API}/compounds/{compound.id}/aliases",
        headers=superuser_token_headers,
        json={"alias": alias},
    )
    r = client.get(
        f"{API}/compounds/",
        headers=superuser_token_headers,
        params={"q": alias.upper()[-8:]},
    )
    assert [c["id"] for c in r.json()["data"]] == [compound.id]
    assert r.json()["data"][0]["aliases"][0]["alias"] == alias

    r = client.get(
        f"{API}/compounds/",
        headers=superuser_token_headers,
        params={"status": "suspect", "limit": 1000},
    )
    assert compound.id in [c["id"] for c in r.json()["data"]]
    assert {c["status"] for c in r.json()["data"]} == {"suspect"}


def test_aliases(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    first, second = create_compound(db), create_compound(db)
    alias = f"Refrigerant {random_id()}"
    url = f"{API}/compounds/{first.id}/aliases"

    r = client.post(url, headers=normal_user_token_headers, json={"alias": alias})
    assert r.status_code == 403

    r = client.post(url, headers=superuser_token_headers, json={"alias": alias})
    assert r.status_code == 200, r.text
    alias_id = r.json()["id"]

    # Unique over all compounds, ignoring case
    r = client.post(
        f"{API}/compounds/{second.id}/aliases",
        headers=superuser_token_headers,
        json={"alias": alias.upper()},
    )
    assert r.status_code == 409

    r = client.post(url, headers=superuser_token_headers, json={"alias": "  "})
    assert r.status_code == 422

    # Resolve by alias (any case)
    r = client.get(
        f"{API}/compounds/resolve",
        headers=normal_user_token_headers,
        params={"name": alias.lower()},
    )
    assert r.status_code == 200
    assert r.json()["id"] == first.id

    # Deleting through the wrong compound is a 404
    r = client.delete(
        f"{API}/compounds/{second.id}/aliases/{alias_id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404
    r = client.delete(f"{url}/{alias_id}", headers=superuser_token_headers)
    assert r.status_code == 200
    r = client.get(f"{API}/compounds/{first.id}", headers=superuser_token_headers)
    assert r.json()["aliases"] == []


def test_resolve(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    compound = create_compound(db)
    industrial = f"HFC-{random_id()}"
    client.patch(
        f"{API}/compounds/{compound.id}",
        headers=superuser_token_headers,
        json={"industrial_name": industrial},
    )
    for name in (compound.id.upper(), industrial.lower()):
        r = client.get(
            f"{API}/compounds/resolve",
            headers=superuser_token_headers,
            params={"name": name},
        )
        assert r.status_code == 200, name
        assert r.json()["id"] == compound.id
    r = client.get(
        f"{API}/compounds/resolve",
        headers=superuser_token_headers,
        params={"name": "does not exist"},
    )
    assert r.status_code == 404


def test_boiling_points(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    compound = create_compound(db)
    url = f"{API}/compounds/{compound.id}/boiling-points"
    body = {
        "temperature_c": 23.7,
        "source": "PubChem: HSDB",
        "reference_url": "https://pubchem.ncbi.nlm.nih.gov/compound/6389",
        "note": "23.7 °C @760 [mm Hg]",
    }
    r = client.post(url, headers=superuser_token_headers, json=body)
    assert r.status_code == 200, r.text
    bp_id = r.json()["id"]

    for bad in (
        {**body, "temperature_c": -300},
        {**body, "source": ""},
        {**body, "reference_url": "javascript:alert(1)"},
    ):
        r = client.post(url, headers=superuser_token_headers, json=bad)
        assert r.status_code == 422, bad

    r = client.get(f"{API}/compounds/{compound.id}", headers=superuser_token_headers)
    assert [bp["temperature_c"] for bp in r.json()["boiling_points"]] == [23.7]

    r = client.delete(f"{url}/{bp_id}", headers=superuser_token_headers)
    assert r.status_code == 200
    r = client.delete(f"{url}/{bp_id}", headers=superuser_token_headers)
    assert r.status_code == 404


def test_delete_cascades_reference_data(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    compound = create_compound(db)
    base = f"{API}/compounds/{compound.id}"
    client.post(
        f"{base}/aliases",
        headers=superuser_token_headers,
        json={"alias": f"x{random_id()}"},
    )
    client.post(
        f"{base}/boiling-points",
        headers=superuser_token_headers,
        json={"temperature_c": 1, "source": "test"},
    )
    r = client.delete(base, headers=superuser_token_headers)
    assert r.status_code == 200
    assert client.get(base, headers=superuser_token_headers).status_code == 404


def test_delete_used_compound_keeps_aliases(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    compound = create_compound(db)
    create_measurement(db, compounds=[compound])
    base = f"{API}/compounds/{compound.id}"
    client.post(
        f"{base}/aliases",
        headers=superuser_token_headers,
        json={"alias": f"x{random_id()}"},
    )
    r = client.delete(base, headers=superuser_token_headers)
    assert r.status_code == 409
    r = client.get(base, headers=superuser_token_headers)
    assert len(r.json()["aliases"]) == 1


def test_search_underscore_is_literal(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    stem = random_id()
    for compound_id in (f"{stem}_air", f"{stem}xair"):
        r = client.post(
            f"{API}/compounds/",
            headers=superuser_token_headers,
            json={"id": compound_id, "unit": "ppt"},
        )
        assert r.status_code == 200, r.text
    r = client.get(
        f"{API}/compounds/",
        headers=superuser_token_headers,
        params={"q": f"{stem}_air"},
    )
    assert [c["id"] for c in r.json()["data"]] == [f"{stem}_air"]
    r = client.get(
        f"{API}/compounds/", headers=superuser_token_headers, params={"q": f"{stem}%"}
    )
    assert r.json()["count"] == 0
