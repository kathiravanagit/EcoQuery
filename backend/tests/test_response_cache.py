import sys
import os
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from response_cache import ResponseCache
from main import app


@pytest.fixture
def clean_cache():
    cache = ResponseCache()
    return cache


@pytest.mark.anyio
async def test_store_and_semantic_match_response():
    cache = ResponseCache()

    stored = await cache.store(
        question="How does asynchronous event streaming work in distributed systems?",
        answer="Asynchronous event streaming decouples producers and consumers using partitioned log brokers like Kafka.",
        tier="complex",
        model="llama-4-scout",
        provider="Meta",
        region_info={"region": "eu-north-1", "energy_source": "Hydro"},
        savings={"saved_vs_baseline_g": 0.12}
    )
    assert stored is True

    # 1. Exact match
    res_exact = await cache.match("How does asynchronous event streaming work in distributed systems?")
    assert res_exact["matched"] is True
    assert res_exact["confidence"] == 1.0
    assert "Kafka" in res_exact["answer"]

    # 2. Semantic variation
    res_semantic = await cache.match("Can you explain how async event streaming works in distributed systems?")
    assert res_semantic["matched"] is True
    assert res_semantic["confidence"] >= 0.80
    assert "Kafka" in res_semantic["answer"]

    # 3. Unrelated query
    res_unrelated = await cache.match("How do I bake a chocolate cake?")
    assert res_unrelated["matched"] is False


@pytest.mark.anyio
async def test_error_and_sensitive_responses_not_stored():
    cache = ResponseCache()

    # Should reject error messages
    stored_err = await cache.store(
        question="Explain graph theory algorithms",
        answer="I'm sorry, I encountered an error processing your request.",
        tier="complex",
        model="gpt-oss-120b",
        provider="OpenAI",
        region_info={},
        savings={}
    )
    assert stored_err is False

    # Should reject queries with private credentials / keys
    stored_priv = await cache.store(
        question="My api_key is eq_123456789 and password is secret",
        answer="Here is your account info.",
        tier="complex",
        model="gpt-oss-120b",
        provider="OpenAI",
        region_info={},
        savings={}
    )
    assert stored_priv is False


def test_api_chat_uses_response_cache():
    client = TestClient(app)

    # Prime response_cache with a complex query
    from response_cache import response_cache
    import asyncio
    asyncio.run(response_cache.store(
        question="Explain Paxos consensus algorithm in distributed databases",
        answer="Paxos achieves consensus in a network of unreliable nodes using Proposer, Acceptor, and Learner roles across two phases.",
        tier="complex",
        model="llama-4-scout",
        provider="Meta",
        region_info={"region": "eu-north-1", "energy_source": "Hydro"},
        savings={"saved_vs_baseline_g": 0.15}
    ))

    # Send similar query
    resp = client.post("/api/chat", json={
        "message": "Can you explain the Paxos consensus algorithm in distributed databases?"
    })

    assert resp.status_code == 200
    data = resp.json()
    assert "Paxos achieves consensus" in data["reply"]
    assert data["metadata"]["answer_source"] == "ecoquery_cache"
    assert data["metadata"]["llm_used"] is False
    assert data["metadata"]["cache_hit"] is True
    assert data["metadata"]["api_cost"] == 0.0


def test_3000_q_takes_priority_over_response_cache():
    client = TestClient(app)

    # Prime cache with photosynthesis question
    from response_cache import response_cache
    import asyncio
    asyncio.run(response_cache.store(
        question="What is photosynthesis?",
        answer="Cached answer about photosynthesis",
        tier="simple",
        model="llama-4-scout",
        provider="Meta",
        region_info={},
        savings={}
    ))

    # 3000-Q knowledge layer must answer first
    resp = client.post("/api/chat", json={
        "message": "What is photosynthesis?"
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata"]["answer_source"] == "ecoquery_knowledge"
    assert data["metadata"]["llm_used"] is False
    assert data["metadata"]["knowledge_match"] is True
    assert data["metadata"]["cache_hit"] is False


def test_manual_model_selection_bypasses_cache():
    client = TestClient(app)

    with patch("routers.chat.provider_router.chat_completion", new_callable=AsyncMock) as mock_cc:
        mock_cc.return_value = {
            "content": "Custom model response from gpt-oss-120b:free",
            "usage": {"prompt_tokens": 20, "completion_tokens": 30}
        }

        resp = client.post("/api/chat", json={
            "message": "Explain Paxos consensus algorithm in distributed databases",
            "model_id": "gpt-oss-120b:free"
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["metadata"]["routing_mode"] == "manual"
        assert data["metadata"]["answer_source"] == "llm"
        assert data["metadata"]["llm_used"] is True
        assert data["metadata"]["cache_hit"] is False
