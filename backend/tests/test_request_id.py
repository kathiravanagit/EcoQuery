"""Correlation ids must be on every response, not only the successful ones.

An id attached only by the happy path is worse than no id at all, because the
responses worth tracing are the failures. So the tests below deliberately
exercise the paths that used to answer without one — a 429 from the rate
limiter, a 413 from the body-size guard, a CSRF 403, and the unhandled 500
that unwinds past every middleware — rather than asserting the header on a 200
and calling it covered.
"""

import logging

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from main import (
    MAX_REQUEST_BODY_BYTES,
    app,
    resolve_request_id,
)


def _id_of(response) -> str:
    return response.headers.get("X-Request-ID", "")


class _DenyAllRateLimiter:
    """Refuses everything, so a 429 needs one request instead of five.

    Carries the lifecycle methods too: whichever side of `TestClient` the
    swap happens on, lifespan startup and shutdown must not be the reason
    this test fails.
    """
    async def allow(self, key, limit, duration):
        return False, 0

    async def connect(self):
        return False

    async def close(self):
        return None


# ── The resolver ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("trace-abc-123", "trace-abc-123"),
    ("  trace-abc-123  ", "trace-abc-123"),      # trimmed, not discarded
    ("a" * 128, "a" * 128),                       # upper bound is inclusive
])
def test_a_well_formed_id_is_kept(raw, expected):
    """Rejecting a usable id would make a conforming client's id vanish."""
    assert resolve_request_id(raw) == expected


@pytest.mark.parametrize("raw", [
    None,
    "",
    "   ",
    "two words",       # whitespace is the injection surface: it is echoed
    "tab\tseparated",
    "x" * 129,         # over-long ids are refused reflection
])
def test_an_unusable_id_is_replaced_rather_than_reflected(raw):
    resolved = resolve_request_id(raw)
    assert resolved, "every request must end up with an id"
    assert len(resolved) <= 128
    assert not any(char.isspace() for char in resolved), \
        "an id we declined to trust must never be echoed into header or log"
    if isinstance(raw, str) and raw.strip():
        assert resolved != raw.strip()


def test_ids_are_fresh_each_time():
    """A constant fallback would silently make every request correlate to one id."""
    assert resolve_request_id(None) != resolve_request_id(None)


# ── The response paths ───────────────────────────────────────────────────────

def test_a_supplied_id_is_echoed_back():
    with TestClient(app) as client:
        resp = client.get("/api/health", headers={"X-Request-ID": "trace-supplied-1"})
    assert resp.status_code == 200
    assert _id_of(resp) == "trace-supplied-1"


def test_a_missing_id_is_generated():
    with TestClient(app) as client:
        resp = client.get("/api/health")
    assert _id_of(resp)
    assert not any(char.isspace() for char in _id_of(resp))


def test_a_rejected_id_is_not_echoed():
    """The one we refuse to trust must not come back out of the response."""
    with TestClient(app) as client:
        resp = client.get("/api/health", headers={"X-Request-ID": "two words"})
    assert resp.status_code == 200
    assert _id_of(resp) != "two words"
    assert " " not in _id_of(resp)


def test_a_404_carries_the_id():
    """HTTPExceptions are handled inside the middleware, so this is the easy path."""
    with TestClient(app) as client:
        resp = client.get("/api/no-such-route", headers={"X-Request-ID": "trace-404-1"})
    assert resp.status_code == 404
    assert _id_of(resp) == "trace-404-1"


def test_a_rate_limited_response_carries_the_id(monkeypatch):
    """The 429 used to return before the id was ever attached."""
    import main as main_module

    # Patched after startup: lifespan calls rate_limiter.connect(), and the
    # stand-in only needs to satisfy allow().
    with TestClient(app) as client:
        monkeypatch.setattr(main_module, "rate_limiter", _DenyAllRateLimiter())
        resp = client.post(
            "/api/chat",
            json={"message": "hello"},
            headers={"X-Request-ID": "trace-429-1"},
        )
    assert resp.status_code == 429, resp.text
    assert _id_of(resp) == "trace-429-1"


def test_a_csrf_rejection_carries_the_id():
    """Answered by a middleware nested *inside* the id middleware, so it must be
    covered by placement rather than by being patched in here too."""
    with TestClient(app) as client:
        resp = client.post(
            "/api/health",
            headers={
                "Cookie": "ecoquery_access_token=some-token",
                "Origin": "https://not-an-allowed-origin.example",
                "X-Request-ID": "trace-csrf-1",
            },
        )
    assert resp.status_code == 403, resp.text
    assert _id_of(resp) == "trace-csrf-1"


def test_an_oversized_body_carries_the_id():
    """413 comes from the body-size guard, which sits between the id middleware
    and the router — the other ordering claim worth testing end to end."""
    with TestClient(app) as client:
        resp = client.post(
            "/api/chat",
            content=b"x" * (MAX_REQUEST_BODY_BYTES + 1024),
            headers={
                "Content-Type": "application/json",
                "X-Request-ID": "trace-413-1",
            },
        )
    assert resp.status_code == 413, resp.status_code
    assert _id_of(resp) == "trace-413-1"


def test_an_unhandled_500_carries_the_id_in_header_body_and_log(caplog):
    """The one path that never returns through the id middleware: the exception
    unwinds straight past it, so the handler has to attach the id itself."""
    from main import app as live_app

    async def boom(request: Request):
        raise RuntimeError("boom")

    live_app.add_api_route("/api/_request_id_boom", boom, methods=["GET"])
    try:
        with TestClient(live_app, raise_server_exceptions=False) as client:
            resp = client.get("/api/_request_id_boom", headers={"X-Request-ID": "trace-500-1"})
    finally:
        live_app.router.routes[:] = [
            r for r in live_app.router.routes
            if getattr(r, "path", "") != "/api/_request_id_boom"
        ]

    assert resp.status_code == 500, resp.text
    assert _id_of(resp) == "trace-500-1"
    assert resp.json()["request_id"] == "trace-500-1"
    # Without this the traceback in the log cannot be tied to what the caller saw.
    assert any("request_id=trace-500-1" in record.getMessage() for record in caplog.records), \
        "the traceback must be logged under the same id the caller was given"


def test_an_unhandled_500_still_gets_an_id_when_the_middleware_never_ran(caplog):
    """If the failure occurs outside the id middleware there is no id on the
    request at all; the handler must invent one rather than omit it."""
    from main import app as live_app

    async def boom(request: Request):
        raise RuntimeError("boom without an id")

    live_app.add_api_route("/api/_request_id_boom_bare", boom, methods=["GET"])
    try:
        with TestClient(live_app, raise_server_exceptions=False) as client:
            resp = client.get("/api/_request_id_boom_bare")
    finally:
        live_app.router.routes[:] = [
            r for r in live_app.router.routes
            if getattr(r, "path", "") != "/api/_request_id_boom_bare"
        ]

    assert resp.status_code == 500
    assert _id_of(resp), "a 500 with no correlation id is one nobody can follow"
    assert resp.json()["request_id"] == _id_of(resp)


def test_the_access_log_carries_the_id(caplog):
    # pytest keeps the root logger at WARNING, so main's basicConfig is a
    # no-op and the INFO access line would otherwise never be recorded.
    caplog.set_level(logging.INFO, logger="EcoQuery")
    with TestClient(app) as client:
        client.get("/api/health", headers={"X-Request-ID": "trace-log-1"})

    access_lines = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("request completed")
    ]
    assert access_lines, "every completed request must produce one access-log line"
    assert any("request_id=trace-log-1" in line for line in access_lines)


def test_the_access_log_is_written_once_per_request(caplog):
    """Consolidating the log into the id middleware must not duplicate it —
    the rate limiter used to write its own line."""
    caplog.set_level(logging.INFO, logger="EcoQuery")
    caplog.clear()
    with TestClient(app) as client:
        client.get("/api/health", headers={"X-Request-ID": "trace-once-1"})

    matching = [
        record for record in caplog.records
        if "request_id=trace-once-1" in record.getMessage()
    ]
    assert len(matching) == 1, f"expected one access-log line, got {len(matching)}"
