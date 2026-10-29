"""A stored API key must never come back out of the API in full.

Only the POST that creates a key returns it whole. The GET used to return the
stored value, so any reload put a live credential back on the page -- and with
it into screenshots, screen shares and anything scripted on the origin.
"""

import pytest
from fastapi.testclient import TestClient

from shared import mask_api_key

FULL_KEY = "eq_" + "0123456789abcdef" * 3


def test_mask_keeps_the_prefix_and_drops_the_secret():
    masked = mask_api_key(FULL_KEY)

    assert masked.startswith("eq_0123456")
    assert FULL_KEY not in masked
    assert set(masked[10:]) == {"*"}


def test_mask_of_empty_or_short_values_is_all_asterisks():
    assert mask_api_key("") == ""
    assert mask_api_key("eq_abc") == "******"


@pytest.fixture
def client(monkeypatch):
    """The real app, with the stored key stubbed and auth bypassed."""
    from routers import misc
    from auth import get_current_user
    from main import app

    async def stored(_email: str) -> str:
        return FULL_KEY

    monkeypatch.setattr(misc, "_get_api_key", stored)
    app.dependency_overrides[get_current_user] = lambda: {"email": "a@b.co"}
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_get_returns_the_masked_key_only(client):
    body = client.get("/api/user/api-key").json()

    assert body["api_key"] == mask_api_key(FULL_KEY)
    assert FULL_KEY not in str(body)


def test_generate_still_returns_the_whole_key(client, monkeypatch):
    """It has to: that response is the only chance to save it."""
    from routers import misc

    async def save(_email: str, _key: str):
        return None

    monkeypatch.setattr(misc, "_set_api_key", save)

    body = client.post("/api/user/api-key").json()

    assert body["api_key"].startswith("eq_")
    assert len(body["api_key"]) == 51


def test_org_listing_masks_every_stored_key(client, monkeypatch):
    from routers import orgs
    from shared import ORGANIZATIONS, ORG_API_KEYS

    async def no_collection():
        return None

    monkeypatch.setattr(orgs, "get_orgs_collection", no_collection)
    ORG_API_KEYS["org_test"] = [{"key": FULL_KEY, "created_at": "2026-01-01"}]
    ORGANIZATIONS["org_test"] = {
        "id": "org_test",
        "name": "Test",
        "owner": "a@b.co",
        "members": ["a@b.co"],
        "api_keys": ORG_API_KEYS["org_test"],
    }
    try:
        body = client.get("/api/orgs").json()
        keys = [k["key"] for org in body["orgs"] if org["id"] == "org_test" for k in org["api_keys"]]

        assert keys == [mask_api_key(FULL_KEY)]
        assert FULL_KEY not in str(body)
        # The live list that authenticates requests must be untouched.
        assert ORG_API_KEYS["org_test"][0]["key"] == FULL_KEY
    finally:
        ORGANIZATIONS.pop("org_test", None)
        ORG_API_KEYS.pop("org_test", None)
