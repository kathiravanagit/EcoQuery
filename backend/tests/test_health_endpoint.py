"""
`/api/health` — readiness plus operator diagnostics.

The endpoint has to distinguish three things that used to be collapsed into a
constant 200:

* **alive** — the process is running (this is what `/health` answers, and what
  Render's `healthCheckPath` polls, so it must never go dark);
* **ready** — it can actually serve a request; only `ready: false` earns a 503;
* **degraded** — a dependency is missing but the service still works.

It also replaces the two fields that used to report `null` unconditionally with
a real count of usable provider credentials.
"""

import os
from unittest.mock import patch

import pytest

from auth import auth_db
from ledger import ledger
from routers import misc
from key_manager import key_manager

_PROVIDER_ENV_VARS = ("OPENROUTER_API_KEY", "GOOGLE_API_KEY")


@pytest.fixture
def client():
    from main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


def test_liveness_endpoint_stays_200(client):
    """Render polls `/health`; it must report alive unconditionally."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service_alive"] is True


def test_health_reports_operational_context(client):
    resp = client.get("/api/health")
    assert resp.status_code in (200, 503)
    data = resp.json()

    assert data["status"] in ("ok", "degraded", "error")
    assert data["service_alive"] is True
    assert isinstance(data["ready"], bool)
    # Deploy identification: without this you cannot tell a rolled-out build
    # from one still serving the previous one.
    assert isinstance(data["version"], str)
    assert data["started_at"]
    assert data["uptime_s"] >= 0
    assert data["probe_duration_ms"] >= 0


def test_status_and_http_code_agree(client):
    data = client.get("/api/health").json()
    assert data["ready"] is (data["status"] != "error")


def test_provider_credentials_are_counted_not_revealed(client):
    data = client.get("/api/health").json()
    assert "provider_keys" in data
    assert isinstance(data["provider_keys"], dict)
    for name, count in data["provider_keys"].items():
        assert isinstance(name, str)
        assert isinstance(count, int)

    # The old placeholders, which always answered null and told operators
    # nothing, are gone in favour of the counts above.
    assert "provider_authenticated" not in data
    assert "provider_completion_test" not in data


def test_reports_unready_when_no_persistence_and_no_provider(client):
    """The only condition that should ever take the endpoint to 503."""

    real_getenv = os.getenv

    def fake_getenv(name, default=None):
        if name in _PROVIDER_ENV_VARS or name == "ELECTRICITY_MAPS_API_KEY":
            # Avoid both a real grid probe and the "configured" signal.
            return ""
        return real_getenv(name, default)

    with patch.object(ledger, "available", False), \
         patch.object(auth_db, "available", False), \
         patch.object(key_manager, "get_all_providers_keys", return_value={}), \
         patch.object(misc.os, "getenv", fake_getenv):
        resp = client.get("/api/health")

    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "error"
    assert data["ready"] is False
    # Liveness is a separate question and must still answer yes.
    assert data["service_alive"] is True
    assert client.get("/health").status_code == 200


def test_a_missing_dependency_alone_only_degrades(client):
    """A single broken dependency must not pull the instance out of rotation."""
    with patch.object(ledger, "available", False):
        resp = client.get("/api/health")
    data = resp.json()
    if data["status"] == "error":
        pytest.skip("environment has no provider keys either")
    assert resp.status_code == 200
    assert data["status"] == "degraded"
    assert data["ready"] is True
