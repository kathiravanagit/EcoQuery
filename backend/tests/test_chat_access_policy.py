"""Auth policy for the two chat endpoints.

/api/chat and /api/chat/stream share one quota check but deliberately differ on
anonymous access: the direct endpoint is a documented API-key surface, while
the stream endpoint powers the public homepage demo. These tests pin both the
defaults and the gate itself so neither can drift silently again.
"""

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import routers.chat as chat_module  # noqa: E402
from routers.chat import _env_flag  # noqa: E402


@pytest.fixture
def client():
    with patch("classifier.classifier.classify") as mock_classify:
        mock_classify.return_value = {"tier": "simple", "confidence": 0.85, "method": "test-mock"}
        with patch("carbon.get_carbon_optimal_region") as mock_carbon:
            mock_carbon.return_value = {
                "region": "eu-north-1",
                "energy_source": "Hydro/Wind",
                "carbon_intensity_g_kwh": 18.5,
                "estimated_savings_g_co2": 1.2,
                "method": "test-mock",
            }
            from main import app
            with TestClient(app) as c:
                yield c


def test_direct_chat_defaults_to_locked():
    assert chat_module.DEFAULT_ALLOW_ANONYMOUS_CHAT is False


def test_stream_defaults_to_open_for_public_demo():
    assert chat_module.DEFAULT_ALLOW_ANONYMOUS_CHAT_STREAM is True


def test_env_flag_parsing():
    saved = os.environ.pop("ALLOW_ANONYMOUS_CHAT", None)
    try:
        assert _env_flag("ALLOW_ANONYMOUS_CHAT", False) is False
        assert _env_flag("ALLOW_ANONYMOUS_CHAT", True) is True
        os.environ["ALLOW_ANONYMOUS_CHAT"] = "true"
        assert _env_flag("ALLOW_ANONYMOUS_CHAT", False) is True
        os.environ["ALLOW_ANONYMOUS_CHAT"] = "TRUE"
        assert _env_flag("ALLOW_ANONYMOUS_CHAT", False) is True
        os.environ["ALLOW_ANONYMOUS_CHAT"] = "false"
        assert _env_flag("ALLOW_ANONYMOUS_CHAT", True) is False
        os.environ["ALLOW_ANONYMOUS_CHAT"] = "0"
        assert _env_flag("ALLOW_ANONYMOUS_CHAT", True) is False
    finally:
        if saved is None:
            os.environ.pop("ALLOW_ANONYMOUS_CHAT", None)
        else:
            os.environ["ALLOW_ANONYMOUS_CHAT"] = saved


def test_anonymous_direct_chat_rejected_when_locked(client, monkeypatch):
    monkeypatch.setattr(chat_module, "_ALLOW_ANONYMOUS_CHAT", False)
    resp = client.post("/api/chat", json={"message": "Hello"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authentication is required for the chat API"


def test_anonymous_direct_chat_allowed_when_enabled(client, monkeypatch):
    monkeypatch.setattr(chat_module, "_ALLOW_ANONYMOUS_CHAT", True)
    resp = client.post("/api/chat", json={"message": "Hello"})
    assert resp.status_code == 200
    assert "reply" in resp.json()


def test_anonymous_stream_rejected_when_disabled(client, monkeypatch):
    monkeypatch.setattr(chat_module, "_ALLOW_ANONYMOUS_CHAT_STREAM", False)
    resp = client.post("/api/chat/stream", json={"message": "Hello"})
    # Raised before the StreamingResponse starts, so clients get JSON, not a
    # half-open event stream.
    assert resp.status_code == 401
    assert "text/event-stream" not in resp.headers.get("content-type", "")
    assert resp.json()["detail"] == "Authentication is required for the chat API"


def test_anonymous_stream_allowed_by_default(client, monkeypatch):
    monkeypatch.setattr(chat_module, "_ALLOW_ANONYMOUS_CHAT_STREAM", True)
    resp = client.post("/api/chat/stream", json={"message": "Hello"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]


def test_both_endpoints_share_the_quota_check(client, monkeypatch):
    """The 100K token cap must apply to an authenticated caller regardless of
    which endpoint they hit — it lives in the shared helper, not per-route."""
    monkeypatch.setattr(chat_module, "_ALLOW_ANONYMOUS_CHAT", False)
    over_quota = {"email": "over@quota.test", "tokens_used": 100_000}
    with patch("routers.chat._resolve_user_email", new=AsyncMock(return_value="over@quota.test")), \
         patch("routers.chat.auth_db") as mock_auth:
        mock_auth.find_user_by_email = AsyncMock(return_value=over_quota)
        direct = client.post("/api/chat", json={"message": "Hello"})
        stream = client.post("/api/chat/stream", json={"message": "Hello"})
    assert direct.status_code == 402
    assert stream.status_code == 402
