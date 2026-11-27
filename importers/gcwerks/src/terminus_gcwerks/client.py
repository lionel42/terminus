"""The few terminus API calls the importer needs."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API = "/api/v1"


class TerminusError(RuntimeError):
    """An API call failed."""


class TerminusClient:
    """A terminus API session (superuser rights are needed to write).

    :param url: The terminus server, e.g. ``https://terminus.example.org``.
    :param token: An access token; or log in with :meth:`login`.
    :param transport: For tests (``httpx.MockTransport``).
    """

    def __init__(
        self,
        url: str,
        token: str | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 120,
    ) -> None:
        self.http = httpx.Client(
            base_url=url.rstrip("/") + API, transport=transport, timeout=timeout
        )
        if token:
            self.http.headers["Authorization"] = f"Bearer {token}"
        self._compounds: dict[str, str | None] = {}

    def __enter__(self) -> "TerminusClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.http.close()

    def _check(self, response: httpx.Response) -> Any:
        if response.is_error:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise TerminusError(
                f"{response.request.method} {response.request.url.path}:"
                f" {response.status_code} {detail}"
            )
        return response.json()

    def login(self, email: str, password: str) -> None:
        data = self._check(
            self.http.post("/login/access-token", data={"username": email, "password": password})
        )
        self.http.headers["Authorization"] = f"Bearer {data['access_token']}"

    def get(self, path: str, **params: Any) -> Any | None:
        """GET ``path``; None when it does not exist (404)."""
        response = self.http.get(path, params=params or None)
        if response.status_code == 404:
            return None
        return self._check(response)

    def post(self, path: str, json: Any, **params: Any) -> Any:
        return self._check(self.http.post(path, json=json, params=params or None))

    def resolve_compound(self, name: str) -> str | None:
        """The id of the compound named ``name`` (id, alias, industrial name, ...)."""
        if name not in self._compounds:
            compound = self.get("/compounds/resolve", name=name)
            self._compounds[name] = None if compound is None else compound["id"]
        return self._compounds[name]

    def create_compound(self, name: str, compound_id: str, description: str) -> None:
        """Register a compound, with ``name`` as an alias when it is not its id."""
        self.post("/compounds/", {"id": compound_id, "description": description})
        if name.strip().lower() != compound_id:
            self.post(f"/compounds/{compound_id}/aliases", {"alias": name})
        self._compounds[name] = compound_id

    def flags(self) -> dict[str, int]:
        """The quality flags of the server: name -> bit."""
        return {flag["name"]: flag["value"] for flag in self.get("/measurements/flags") or []}

    def ensure_sample(
        self, sample_id: str, filled_at: str, description: str, dry_run: bool = False
    ) -> str:
        """Create the sample (and its container of the same id) if missing.

        :return: ``"exists"``, ``"created"`` or ``"created with its container"``.
        """
        if self.get(f"/samples/{sample_id}") is not None:
            return "exists"
        created = "created"
        if self.get(f"/containers/{sample_id}") is None:
            created = "created with its container"
            if not dry_run:
                self.post(
                    "/containers/",
                    {"id": sample_id, "kind": "cylinder", "description": description},
                )
        if not dry_run:
            self.post(
                "/samples/",
                {
                    "id": sample_id,
                    "container_id": sample_id,
                    "filled_at": filled_at,
                    "description": description,
                },
            )
        return created

    def import_measurements(self, measurements: list[dict], mode: str) -> dict[str, int]:
        """``POST /measurements/import``: all or nothing."""
        return self.post("/measurements/import", measurements, mode=mode)
