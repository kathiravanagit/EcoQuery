"""
Global error handling contract.

Every failure the client sees must be a stable JSON payload with `detail` (which
the frontend reads), a machine-readable `error_code`, and a human message —
never a stack trace or raw exception text, which can carry connection details.
"""

import pytest
from fastapi import Request
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestHttpErrorsAreStructured:
    def test_unknown_route_returns_structured_json(self, client):
        resp = client.get("/api/definitely-not-a-route")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]
        assert body["error_code"] == "NOT_FOUND"
        assert body["success"] is False

    def test_detail_is_preserved_for_the_frontend(self, client):
        """AuthContext reads err.detail directly — it must stay a plain string."""
        resp = client.post("/api/chat", json={"message": "hi"})
        assert resp.status_code in {200, 401, 402, 429}
        if resp.status_code == 401:
            assert isinstance(resp.json()["detail"], str)

    def test_validation_error_is_a_readable_sentence(self, client):
        resp = client.post("/api/chat", json={"message": ""})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error_code"] == "VALIDATION_ERROR"
        assert "message" in body
        # Must not be the raw pydantic error dump.
        assert "ctx" not in body

    def test_validation_error_names_the_offending_field(self, client):
        resp = client.post("/api/chat", json={"routing_mode": "nonsense", "message": "hi"})
        assert resp.status_code == 422
        body = resp.json()
        assert "routing_mode" in body["message"] or "routing_mode" in str(body.get("fields"))


class TestNoStackTracesLeak:
    def test_unhandled_exception_returns_clean_500(self):
        from main import app

        async def boom(request: Request):
            raise RuntimeError("secret-connection-string mongodb://user:pass@internal")

        app.add_api_route("/api/_boom", boom, methods=["GET"])
        try:
            # raise_server_exceptions=False so the handler's response is returned
            # rather than the exception being re-raised by the test client.
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get("/api/_boom")
        finally:
            app.router.routes[:] = [
                r for r in app.router.routes if getattr(r, "path", "") != "/api/_boom"
            ]

        assert resp.status_code == 500
        text = resp.text
        assert "secret-connection-string" not in text
        assert "Traceback" not in text
        assert 'File "' not in text
        body = resp.json()
        assert body["error_code"] == "INTERNAL_ERROR"
        assert body["detail"]

    def test_audit_error_does_not_echo_exception_text(self, client, monkeypatch):
        from ledger import ledger

        async def _raise(*args, **kwargs):
            raise RuntimeError("connection string leaked from backend")

        monkeypatch.setattr(ledger, "get_audit_log", _raise)
        resp = client.get("/api/audit")
        # Either unauthenticated (401) or a handled failure — never the raw text.
        assert "connection string leaked" not in resp.text


class TestProviderFailuresAreUserFacing:
    def test_provider_error_payload_has_no_traceback(self, client, monkeypatch):
        from providers import provider_router

        async def _fail(*args, **kwargs):
            raise RuntimeError('{"success": false, "error_code": "PROVIDER_UNAVAILABLE", "message": "All configured providers failed to process this request."}')

        monkeypatch.setattr(provider_router, "chat_completion", _fail)
        # A distinctive prompt so the knowledge/response caches cannot answer it
        # and the request actually reaches the provider.
        resp = client.post("/api/chat", json={"message": "Explain quantum entanglement in 200 words please"})
        assert resp.status_code >= 500
        assert "Traceback" not in resp.text
        assert "File \"" not in resp.text
        body = resp.json()
        assert body.get("error_code")
        assert body.get("message")
