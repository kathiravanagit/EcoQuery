import sys
import os
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from main import app
from auth import get_current_user
from ledger import ledger

FAKE_RECORDS = [
    {
        "timestamp": "2026-09-20T10:00:00+00:00",
        "query": "[redacted]",
        "tier": "simple",
        "model_used": "green-model",
        "model_tier": "green",
        "region": "eu-north-1",
        "co2_estimated": 0.05,
        "co2_saved_vs_baseline": 0.45,
        "api_cost": 0.0001,
        "latency_seconds": 0.5,
        "verification_status": "verified",
    },
    {
        "timestamp": "2026-09-21T11:00:00+00:00",
        "query": "[redacted]",
        "tier": "complex",
        "model_used": "perf-model",
        "model_tier": "performance",
        "region": "us-east-1",
        "co2_estimated": 0.30,
        "co2_saved_vs_baseline": 0.10,
        "api_cost": 0.0005,
        "latency_seconds": 1.2,
        "verification_status": "verified",
    },
]


@pytest.fixture
def authed_client():
    app.dependency_overrides[get_current_user] = lambda: {
        "email": "emitted@example.com",
        "display_name": "Emitted Test",
    }
    with patch.object(ledger, "get_audit_log", new_callable=AsyncMock) as mock_log:
        mock_log.return_value = (list(FAKE_RECORDS), len(FAKE_RECORDS))
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


def test_user_stats_reports_actual_co2_emitted(authed_client):
    resp = authed_client.get("/api/user/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_co2_emitted_g"] == pytest.approx(0.35)
    # saved total must remain intact
    assert data["total_co2_saved_g"] == pytest.approx(0.55)


def test_user_analytics_buckets_report_co2_emitted(authed_client):
    resp = authed_client.get("/api/user/analytics")
    assert resp.status_code == 200
    data = resp.json()
    buckets = {b["period"]: b for b in data["data"]}
    assert buckets["2026-09-20"]["co2_emitted_g"] == pytest.approx(0.05)
    assert buckets["2026-09-21"]["co2_emitted_g"] == pytest.approx(0.30)
    assert buckets["2026-09-20"]["co2_saved_g"] == pytest.approx(0.45)


def test_sustainability_report_includes_emitted(authed_client):
    resp = authed_client.get("/api/user/sustainability-report")
    assert resp.status_code == 200
    summary = resp.json()["summary"]
    assert summary["total_co2_emitted_g"] == pytest.approx(0.35)
    assert summary["total_co2_saved_g"] == pytest.approx(0.55)


def test_certificate_includes_emitted(authed_client):
    resp = authed_client.get("/api/user/certificate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_co2_emitted_g"] == pytest.approx(0.35)


def test_ledger_stats_schema_includes_emitted():
    import asyncio
    prev = ledger.available
    ledger.available = False
    try:
        stats = asyncio.run(ledger.get_stats())
    finally:
        ledger.available = prev
    assert "total_co2_emitted_g" in stats
    assert "total_co2_saved_g" in stats
