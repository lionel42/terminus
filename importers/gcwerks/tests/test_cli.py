"""The command line against a fake terminus server."""

import json
from pathlib import Path

import httpx
import pytest

from terminus_gcwerks import cli
from terminus_gcwerks.client import TerminusClient
from terminus_gcwerks.convert import Flag


class FakeTerminus:
    """The routes the importer calls, with in-memory data."""

    def __init__(self) -> None:
        self.instruments = {"jfj-medusa"}
        self.compounds: dict[str, dict] = {"cfc12": {"id": "cfc12"}}
        self.aliases = {"cfc-12": "cfc12"}  # name (lower) -> id
        self.containers: dict[str, dict] = {"j-290": {"id": "j-290"}}
        self.samples: dict[str, dict] = {}
        self.measurements: dict[str, dict] = {}
        self.flags = [{"name": f.name, "value": int(f)} for f in Flag]
        self.calls: list[str] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api/v1")
        self.calls.append(f"{request.method} {path}")
        if request.headers.get("Authorization") != "Bearer secret":
            return httpx.Response(401, json={"detail": "Not authenticated"})
        if request.method == "GET":
            kind, _, key = path.strip("/").partition("/")
            if kind == "compounds" and key == "resolve":
                name = request.url.params["name"].lower()
                found = self.aliases.get(name) or (name if name in self.compounds else None)
                if found:
                    return httpx.Response(200, json={"id": found})
            elif kind == "measurements" and key == "flags":
                return httpx.Response(200, json=self.flags)
            elif kind == "instruments" and key in self.instruments:
                return httpx.Response(200, json={"id": key})
            elif kind == "compounds" and key in self.compounds:
                return httpx.Response(200, json=self.compounds[key])
            elif kind == "containers" and key in self.containers:
                return httpx.Response(200, json=self.containers[key])
            elif kind == "samples" and key in self.samples:
                return httpx.Response(200, json=self.samples[key])
            return httpx.Response(404, json={"detail": "Not found"})
        body = json.loads(request.content)
        if path == "/compounds/":
            self.compounds[body["id"]] = body
        elif path.startswith("/compounds/") and path.endswith("/aliases"):
            self.aliases[body["alias"].lower()] = path.split("/")[2]
        elif path == "/containers/":
            self.containers[body["id"]] = body
        elif path == "/samples/":
            assert body["container_id"] in self.containers
            self.samples[body["id"]] = body
        elif path == "/measurements/import":
            report = {"created": 0, "skipped": 0, "replaced": 0}
            for m in body:
                assert m["sample_id"] is None or m["sample_id"] in self.samples
                assert all(r["compound_id"] in self.compounds for r in m["results"])
                key = m["measured_at"]
                if key in self.measurements:
                    mode = request.url.params["mode"]
                    report["skipped" if mode == "skip" else "replaced"] += 1
                    if mode == "skip":
                        continue
                else:
                    report["created"] += 1
                self.measurements[key] = m
            return httpx.Response(200, json=report)
        return httpx.Response(200, json=body)


@pytest.fixture
def server() -> FakeTerminus:
    return FakeTerminus()


def run(server: FakeTerminus, gcdir: Path, *extra: str) -> int:
    args = cli.parse_args(
        [str(gcdir), "--instrument", "jfj-medusa", "--url", "http://terminus", *extra]
    )
    client = TerminusClient(
        "http://terminus", token="secret", transport=httpx.MockTransport(server.handle)
    )
    return cli.run(args, client)


def test_import(server, gcdir, capsys, caplog):
    assert run(server, gcdir) == 0
    out = capsys.readouterr().out
    assert "measurements: 4 ({'created': 4, 'skipped': 0, 'replaced': 0})" in out
    assert "flagged: 1 runs and 2 results" in out
    assert "compounds registered: 2" in out

    # new gases: registered, with the GCwerks name as alias when it is not the id
    assert server.compounds["n2o"]["description"].startswith("Registered from the GCwerks")
    assert server.aliases["m+p-xylene"] == "m_p-xylene"
    assert "n2o" not in server.aliases
    assert "2 gases registered as new compounds: N2O, m+p-xylene" in caplog.text

    # E-223: sample and container created, filled at the ports log fill date
    assert server.samples["e-223"]["filled_at"] == "2024-11-01T00:00:00Z"
    assert server.containers["e-223"]["kind"] == "cylinder"
    # J-290: its container existed, only the sample is created
    assert server.containers["j-290"] == {"id": "j-290"}
    assert server.samples["j-290"]["container_id"] == "j-290"

    std = server.measurements["2025-01-01T00:13:00Z"]
    assert std["type"] == "standard" and std["sample_id"] == "e-223"
    assert std["results"][0]["compound_id"] == "cfc12"
    tert = server.measurements["2025-01-02T00:13:00Z"]
    assert (tert["flags"], tert["flag_comment"]) == (Flag.INVALID, "F: valve not turned")

    # a second import skips what is there and creates nothing
    calls = len(server.calls)
    assert run(server, gcdir) == 0
    assert "'skipped': 4" in capsys.readouterr().out
    assert not any(c.startswith("POST /samples") for c in server.calls[calls:])
    assert not any(c.startswith("POST /compounds") for c in server.calls[calls:])
    assert run(server, gcdir, "--mode", "replace") == 0
    assert "'replaced': 4" in capsys.readouterr().out


def test_dry_run_writes_nothing(server, gcdir, capsys):
    assert run(server, gcdir, "--dry-run", "--types", "std,tert,air") == 0
    out = capsys.readouterr().out
    assert "measurements: 4 (dry run)" in out and "compounds registered: 2" in out
    assert not any(c.startswith("POST") for c in server.calls)
    assert server.samples == {} and server.measurements == {}


def test_dates_and_gases(server, gcdir, capsys):
    assert run(server, gcdir, "--from", "2025-01-02", "--to", "2025-01-20") == 0
    assert sorted(server.measurements) == ["2025-01-02T00:13:00Z", "2025-01-20T11:00:00Z"]
    assert run(server, gcdir, "--gas", "CFC-12", "--mode", "replace") == 0
    assert {r["compound_id"] for m in server.measurements.values() for r in m["results"]} == {
        "cfc12"
    }
    with pytest.raises(ValueError, match="HFC-999"):
        run(server, gcdir, "--gas", "HFC-999")
    with pytest.raises(FileNotFoundError, match="no results file"):
        run(server, gcdir, "--from", "2030-01-01")


def test_no_new_compounds(server, gcdir, capsys, caplog):
    assert run(server, gcdir, "--no-new-compounds") == 0
    assert "gases left out: 2" in capsys.readouterr().out
    assert set(server.compounds) == {"cfc12"}


def test_existing_id_not_reused(server, gcdir, caplog):
    # a compound n2o exists, but resolving the name N2O does not find it
    server.compounds["n2o"] = {"id": "n2o"}

    def resolve_not_n2o(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/resolve") and request.url.params["name"] == "N2O":
            return httpx.Response(404, json={"detail": "Not found"})
        return server.handle(request)

    args = cli.parse_args([str(gcdir), "--instrument", "jfj-medusa", "--url", "http://t"])
    transport = httpx.MockTransport(resolve_not_n2o)
    client = TerminusClient("http://t", token="secret", transport=transport)
    assert cli.run(args, client) == 0
    assert "the compound 'n2o' exists but is not named 'N2O'" in caplog.text
    assert all(
        r["compound_id"] != "n2o" for m in server.measurements.values() for r in m["results"]
    )


def test_flags_must_match(server, gcdir):
    server.flags[0]["value"] = 64
    with pytest.raises(cli.TerminusError, match="INVALID"):
        run(server, gcdir)


def test_unknown_instrument(server, gcdir):
    server.instruments = set()
    with pytest.raises(cli.TerminusError, match="instrument 'jfj-medusa' not found"):
        run(server, gcdir)


def test_batches(server, gcdir):
    assert run(server, gcdir, "--batch-size", "1") == 0
    assert server.calls.count("POST /measurements/import") == 4


def test_parse_args_errors(monkeypatch):
    monkeypatch.delenv("TERMINUS_URL", raising=False)
    with pytest.raises(SystemExit):
        cli.parse_args(["/gc", "--instrument", "i"])  # no url
    with pytest.raises(SystemExit):
        cli.parse_args(["/gc", "--instrument", "i", "--url", "u", "--from", "2025-02-01",
                        "--to", "2025-01-01"])  # fmt: skip


def test_login(server):
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/login/access-token"):
            assert b"username=a%40b.c" in request.content
            return httpx.Response(200, json={"access_token": "secret"})
        return server.handle(request)

    client = TerminusClient("http://terminus", transport=httpx.MockTransport(handle))
    client.login("a@b.c", "pw")
    assert client.get("/instruments/jfj-medusa") == {"id": "jfj-medusa"}


def test_run_without_type(server, tmp_path, monkeypatch, capsys):
    import conftest

    runs = conftest.RUNS.copy()
    runs.loc[0, "type"] = ""  # std.5: typed by its name
    monkeypatch.setattr(conftest, "RUNS", runs)
    gcdir = conftest.write_gcdir(tmp_path / "gcdir")
    assert run(server, gcdir) == 0
    assert "measurements: 4 " in capsys.readouterr().out
    assert server.measurements["2025-01-01T00:13:00Z"]["type"] == "standard"


@pytest.mark.parametrize("dry_run", [True, False])
def test_same_new_compound_id(server, caplog, dry_run):
    args = cli.parse_args(["/gc", "--instrument", "i", "--url", "http://t"])
    args.dry_run = dry_run
    client = TerminusClient(
        "http://t", token="secret", transport=httpx.MockTransport(server.handle)
    )
    compounds, created, left_out = cli.resolve_compounds(
        client, ["m+p-xylene", "m p-xylene"], args, "gc"
    )
    assert (compounds, created, left_out) == (
        {"m+p-xylene": "m_p-xylene"},
        ["m+p-xylene"],
        ["m p-xylene"],
    )
    assert "is the one of gas 'm+p-xylene'" in caplog.text


def test_server_unreachable(gcdir, monkeypatch, caplog):
    monkeypatch.setenv("TERMINUS_TOKEN", "secret")
    # nothing listens on port 9 (discard) of localhost
    assert cli.main([str(gcdir), "--instrument", "i", "--url", "http://127.0.0.1:9"]) == 1
    assert "terminus server http://127.0.0.1:9: ConnectError" in caplog.text
