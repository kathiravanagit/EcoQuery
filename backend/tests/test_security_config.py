"""
Security configuration that must hold in production.

Each of these was a review finding; they are pinned here so a later change to
middleware order or FastAPI kwargs cannot silently reopen them:

* API docs off unless explicitly enabled (the shipped default is `false`);
* an explicit CORS origin allowlist with no wildcard and no suffix matching;
* cookie-authenticated writes rejected outside that allowlist (CSRF);
* security headers on API responses.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from main import api_docs_enabled, app, configured_origins

REPO_ROOT = Path(__file__).resolve().parents[2]

# Always present in the allowlist (hardcoded alongside ALLOWED_ORIGINS).
ALLOWED_ORIGIN = "http://localhost:5173"
UNKNOWN_ORIGIN = "https://evil.example.com"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


# ── API docs ─────────────────────────────────────────────────────────────────

def test_shipped_default_keeps_api_docs_disabled():
    """`.env.example` is what a new deployment copies."""
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "ENABLE_API_DOCS=false" in env_example


def test_api_doc_routes_follow_the_enabled_flag(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        resp = client.get(path)
        if api_docs_enabled:
            assert resp.status_code == 200, f"{path} should be exposed"
        else:
            # Not mounted at all, so the 404 comes from our JSON handler.
            assert resp.status_code == 404, f"{path} must not be reachable"
            assert resp.json()["error_code"] == "NOT_FOUND"


# ── CORS ─────────────────────────────────────────────────────────────────────

def test_allowed_origin_is_echoed_not_wildcarded(client):
    resp = client.get("/api/models", headers={"Origin": ALLOWED_ORIGIN})
    assert resp.status_code == 200
    assert resp.headers.get("Access-Control-Allow-Origin") == ALLOWED_ORIGIN
    assert resp.headers.get("Access-Control-Allow-Origin") != "*"


def test_unlisted_origin_gets_no_cors_header(client):
    resp = client.get("/api/models", headers={"Origin": UNKNOWN_ORIGIN})
    assert resp.status_code == 200  # the request itself still succeeds
    assert "Access-Control-Allow-Origin" not in resp.headers


def test_no_suffix_wildcard_for_hosting_providers(client):
    """`allow_origin_regex` would let any Vercel project read these responses."""
    for origin in ("https://attacker.vercel.app", "https://attacker.onrender.com"):
        resp = client.get("/api/models", headers={"Origin": origin})
        assert "Access-Control-Allow-Origin" not in resp.headers, origin


def test_preflight_allowed_for_a_listed_origin(client):
    resp = client.options("/api/chat", headers={
        "Origin": ALLOWED_ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert resp.headers.get("Access-Control-Allow-Origin") == ALLOWED_ORIGIN
    assert "POST" in resp.headers.get("Access-Control-Allow-Methods", "")


def test_preflight_refused_for_an_unlisted_origin(client):
    resp = client.options("/api/chat", headers={
        "Origin": UNKNOWN_ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert "Access-Control-Allow-Origin" not in resp.headers


def test_allowlist_is_an_exact_set():
    assert UNKNOWN_ORIGIN not in configured_origins
    assert ALLOWED_ORIGIN in configured_origins
    assert not any(origin.endswith("*") for origin in configured_origins)


# ── CSRF for cookie-authenticated writes ─────────────────────────────────────

def test_cookie_authenticated_write_from_an_unknown_origin_is_rejected(client):
    resp = client.post(
        "/api/contact",
        json={"name": "a", "email": "a@b.co", "message": "hi"},
        headers={"Origin": UNKNOWN_ORIGIN, "Cookie": "ecoquery_access_token=x"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "CSRF origin rejected"


def test_cookie_authenticated_write_from_a_listed_origin_is_allowed(client):
    resp = client.post(
        "/api/contact",
        json={"name": "a", "email": "a@b.co", "message": "hi"},
        headers={"Origin": ALLOWED_ORIGIN, "Cookie": "ecoquery_access_token=x"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_reads_without_a_cookie_are_unaffected_by_csrf(client):
    resp = client.get("/api/models", headers={
        "Origin": UNKNOWN_ORIGIN,
        "Cookie": "ecoquery_access_token=x",
    })
    assert resp.status_code == 200


# ── Security headers ─────────────────────────────────────────────────────────

def test_api_responses_carry_security_headers(client):
    resp = client.get("/api/models")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert resp.headers.get("Strict-Transport-Security", "").startswith("max-age=31536000")
    assert "camera=()" in resp.headers.get("Permissions-Policy", "")


def test_error_responses_carry_the_same_headers(client):
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"


def test_cors_middleware_is_the_outermost_one():
    """It must be, or responses generated inside (413/429/403) lose the CORS
    headers a browser needs before it will surface the error to the caller."""
    from fastapi.middleware.cors import CORSMiddleware

    names = [m.cls.__name__ for m in app.user_middleware]
    assert names[0] == "CORSMiddleware"
    assert CORSMiddleware.__name__ in names
