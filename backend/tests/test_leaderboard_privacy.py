"""The leaderboard is unauthenticated, so nothing it returns may identify a user.

Regression coverage for the raw `user_email` leak: the endpoint used to publish
each account's address next to that person's query count and CO₂ totals, which
lets anyone enumerate who uses the service.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("classifier.classifier.classify") as mock_classify:
        mock_classify.return_value = {
            "tier": "simple",
            "confidence": 0.85,
            "method": "test-mock",
        }
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


ROWS = [
    {"email": "alice@example.com", "total_co2_saved_g": 1.5, "total_queries": 3},
    {"email": "bob@example.org", "total_co2_saved_g": 0.5, "total_queries": 1},
]


def _auth_db_returning(display_names):
    """An auth_db stand-in whose find().to_list() yields the given accounts."""
    docs = [{"email": email, "display_name": name} for email, name in display_names.items()]
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=docs)
    db = MagicMock()
    db.available = True
    db.collection.find.return_value = cursor
    return db


def _auth_db_unavailable():
    db = MagicMock()
    db.available = False
    return db


def _get(client, auth_db):
    with patch("routers.misc.ledger.get_leaderboard", new=AsyncMock(return_value=ROWS)):
        with patch("auth.auth_db", auth_db):
            return client.get("/api/leaderboard")


def test_never_publishes_an_address(client):
    resp = _get(client, _auth_db_returning({"alice@example.com": "Alice"}))

    assert resp.status_code == 200
    assert "alice@example.com" not in resp.text
    assert "bob@example.org" not in resp.text

    rows = resp.json()["leaderboard"]
    assert len(rows) == 2
    assert all("email" not in row for row in rows)


def test_shows_the_display_name(client):
    resp = _get(client, _auth_db_returning({"alice@example.com": "Alice"}))
    rows = resp.json()["leaderboard"]

    assert rows[0]["user"] == "Alice"
    # No account record -> stable non-reversible handle, still no address.
    assert rows[1]["user"].startswith("user_")
    assert rows[1]["user"] != rows[0]["user"]


def test_address_shaped_display_name_is_not_published(client):
    """Signup accepts free text and the Google fallback uses the address as
    the name, so a display name can itself be an address."""
    resp = _get(
        client,
        _auth_db_returning({"alice@example.com": "alice@example.com"}),
    )

    assert resp.status_code == 200
    assert "alice@example.com" not in resp.text
    assert resp.json()["leaderboard"][0]["user"].startswith("user_")


def test_still_returns_aggregates_without_the_auth_db(client):
    resp = _get(client, _auth_db_unavailable())

    assert resp.status_code == 200
    assert "alice@example.com" not in resp.text

    rows = resp.json()["leaderboard"]
    assert [r["total_co2_saved_g"] for r in rows] == [1.5, 0.5]
    assert [r["total_queries"] for r in rows] == [3, 1]
    assert all(r["user"].startswith("user_") for r in rows)


def test_handle_is_stable_across_requests(client):
    first = _get(client, _auth_db_unavailable()).json()["leaderboard"][0]["user"]
    second = _get(client, _auth_db_unavailable()).json()["leaderboard"][0]["user"]

    assert first == second
