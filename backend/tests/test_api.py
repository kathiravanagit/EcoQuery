import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    with patch("classifier.classifier.classify") as mock_classify:
        mock_classify.return_value = {
            "tier": "simple",
            "confidence": 0.85,
            "method": "test-mock"
        }
        with patch("carbon.get_carbon_optimal_region") as mock_carbon:
            mock_carbon.return_value = {
                "region": "eu-north-1",
                "energy_source": "Hydro/Wind",
                "carbon_intensity_g_kwh": 18.5,
                "estimated_savings_g_co2": 1.2,
                "method": "test-mock"
            }
            from main import app
            with TestClient(app) as c:
                yield c

def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "ledger_connected" in data

def test_chat_endpoint(client):
    resp = client.post("/api/chat", json={"message": "Hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert "metadata" in data
    assert "model_used" in data["metadata"]
    assert "co2_saved_g" in data["metadata"] or "co2_estimated_g" in data["metadata"]
    assert "tier" in data["metadata"]

def test_chat_empty_message(client):
    resp = client.post("/api/chat", json={"message": ""})
    assert resp.status_code == 422

def test_chat_long_message(client):
    msg = "a" * 5000
    resp = client.post("/api/chat", json={"message": msg})
    assert resp.status_code == 422


def test_stats_endpoint(client):
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_queries" in data


def test_models_endpoint(client):
    resp = client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert len(data["models"]) > 0


def test_carbon_regions_endpoint(client):
    resp = client.get("/api/carbon/regions")
    assert resp.status_code == 200
    data = resp.json()
    assert "region" in data
    assert "carbon_intensity_g_kwh" in data


def test_chat_stream_endpoint(client):
    resp = client.post("/api/chat/stream", json={"message": "Hello"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]


def test_chat_stream_with_model_override(client):
    resp = client.post("/api/chat/stream", json={"message": "Hello", "model_id": "gpt-4o-mini"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
