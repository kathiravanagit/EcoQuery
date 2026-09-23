import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from main import app
from knowledge import knowledge_base


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_knowledge_base_loaded():
    assert knowledge_base._is_loaded is True
    assert len(knowledge_base._questions) > 100
    assert len(knowledge_base._answers) == len(knowledge_base._questions)


def test_knowledge_exact_and_semantic_matching():
    # Direct exact question
    res1 = knowledge_base.match("What is photosynthesis?")
    assert res1["matched"] is True
    assert res1["confidence"] >= 0.8
    assert "sunlight" in res1["answer"].lower() or "glucose" in res1["answer"].lower()

    # Semantic variation: "Can you explain photosynthesis?"
    res2 = knowledge_base.match("Can you explain photosynthesis?")
    assert res2["matched"] is True
    assert res2["confidence"] >= 0.8
    assert "photosynthesis" in res2["answer"].lower()

    # Semantic variation: "What is solar energy?"
    res3 = knowledge_base.match("Can you tell me about solar energy?")
    assert res3["matched"] is True
    assert "solar" in res3["answer"].lower()

    # Definition lookup
    res4 = knowledge_base.match("Define recursion")
    assert res4["matched"] is True
    assert "recursion" in res4["answer"].lower() or "calls itself" in res4["answer"].lower()

    # Capital cities
    res5 = knowledge_base.match("What is the capital of Germany?")
    assert res5["matched"] is True
    assert "Berlin" in res5["answer"]

    # Math
    res6 = knowledge_base.match("What is 2 + 2?")
    assert res6["matched"] is True
    assert "4" in res6["answer"]


def test_knowledge_unmatched_low_confidence():
    unrelated = "Implement a distributed Raft consensus protocol in Rust with multi-datacenter failover"
    res = knowledge_base.match(unrelated)
    assert res["matched"] is False
    assert res["answer"] is None


def test_chat_direct_knowledge_zero_llm(client):
    resp = client.post("/api/chat", json={
        "message": "Can you explain photosynthesis?"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert len(data["reply"]) > 0
    assert "photosynthesis" in data["reply"].lower()

    meta = data["metadata"]
    assert meta["answer_source"] == "ecoquery_knowledge"
    assert meta["llm_used"] is False
    assert meta["knowledge_match"] is True
    assert meta["knowledge_confidence"] >= 0.7
    assert meta["routing_mode"] == "eco"
    assert meta["api_cost"] == 0.0
    assert meta["co2_estimated_g"] == 0.0


def test_chat_manual_model_selection_bypasses_knowledge(client):
    resp = client.post("/api/chat", json={
        "message": "What is photosynthesis?",
        "model_id": "deepseek-chat-v3-0324:free"
    })
    assert resp.status_code == 200
    data = resp.json()
    meta = data["metadata"]
    assert meta["routing_mode"] == "manual"
    assert meta["llm_used"] is True
    assert meta["knowledge_match"] is False
    assert meta["answer_source"] == "llm"


def test_chat_stream_knowledge_direct(client):
    resp = client.post("/api/chat/stream", json={
        "message": "What is photosynthesis?"
    })
    assert resp.status_code == 200
    content = resp.text
    assert "data: " in content
    assert "photosynthesis" in content.lower()
    assert "ecoquery_knowledge" in content
