import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def security_client(monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO_MODE", "false")
    from main import app
    with TestClient(app) as client:
        yield client


def test_anonymous_chat_is_rejected(security_client):
    response = security_client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 401


def test_api_key_hash_round_trip():
    from auth import hash_api_key, verify_api_key

    key = "eq_test_secret"
    digest = hash_api_key(key)
    assert digest != key
    assert verify_api_key(key, digest)
    assert not verify_api_key("eq_other_secret", digest)
