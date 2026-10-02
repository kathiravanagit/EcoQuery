"""SSE keepalive behaviour.

A provider can take several seconds to produce its first token. During that
window nothing is written, and to a reverse proxy that looks identical to an
abandoned connection -- Render and most CDNs reap idle sockets well inside a
slow time-to-first-token. The stream therefore has to emit something the proxy
counts as traffic while proving nothing at all to the consumer.

The keepalive is an SSE comment: a line beginning `:`. The specification says
parsers discard it, so it can appear on the wire without ever entering a
reply. These tests pin both halves of that claim -- it arrives, and it does
not arrive *as data*.
"""

import asyncio
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import providers as providers_mod
import routers.chat as chat_module
from main import app

# Cannot be answered from the 3000-Q knowledge base, so the run always
# reaches the LLM branch and its real streaming code.
SLOW_PROMPT = "Zqvx7 explain the frimble protocol in one line"

LINEAGE = {
    "requested_provider": "openrouter",
    "requested_model": "qwen3.8-27b:free",
    "attempted_providers": [],
    "final_provider": "google",
    "final_model": "gemini-flash-latest",
    "fallback_reason": "provider fallback",
    "success": True,
    "byok_used": False,
    "key_source": {"google": "server"},
}


def _stream(delay: float):
    """A provider that says nothing for `delay` seconds, then answers."""
    async def _gen(*args, **kwargs):
        await asyncio.sleep(delay)
        yield {"token": "hello there"}
        yield {"provider_lineage": LINEAGE}
    return _gen


def _post(monkeypatch, delay: float, heartbeat: float) -> str:
    monkeypatch.setattr(chat_module, "SSE_HEARTBEAT_S", heartbeat)
    with patch.object(providers_mod.provider_router, "stream_completion", _stream(delay)), \
         patch("classifier.classifier.classify",
               return_value={"tier": "simple", "confidence": 0.85, "method": "test-mock"}), \
         patch("router.get_carbon_optimal_region",
               return_value={"region": "gcp-europe-west1", "country": "Belgium",
                             "carbon_intensity_g_kwh": 100, "renewable_share": 0.99,
                             "energy_source": "Wind", "renewable_rank": 1,
                             "data_source": "Electricity Maps", "grid_timestamp": None,
                             "last_updated": None, "is_live": True, "stale": False}):
        with TestClient(app) as client:
            resp = client.post("/api/chat/stream",
                               json={"message": SLOW_PROMPT})
    assert resp.status_code == 200, resp.text
    return resp.text


def test_a_slow_provider_gets_comments_instead_of_dead_air(monkeypatch):
    body = _post(monkeypatch, delay=0.45, heartbeat=0.1)
    assert ": hb" in body, "no keepalive was sent during a silent provider wait"


def test_keepalives_never_reach_the_consumer_as_data(monkeypatch):
    """The comment must be invisible: no token, no metadata, no error frame."""
    body = _post(monkeypatch, delay=0.45, heartbeat=0.1)

    comment_frames = 0
    for frame in body.split("\n\n"):
        if not frame.strip():
            continue
        if frame.startswith(":"):
            comment_frames += 1
            assert "data:" not in frame, f"comment carried data: {frame!r}"
            continue
        assert not frame.lstrip().startswith(":")
        assert "hb" not in frame, f"keepalive leaked into a data frame: {frame!r}"

    assert comment_frames > 0


def test_the_reply_still_completes_and_the_tokens_are_intact(monkeypatch):
    """Keepalives interleaved with tokens must not disturb the reply."""
    body = _post(monkeypatch, delay=0.45, heartbeat=0.1)

    reply = ""
    metadata = None
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        payload = json.loads(line[6:])
        if isinstance(payload, dict) and payload.get("token"):
            reply += payload["token"]
        if isinstance(payload, dict) and payload.get("done"):
            metadata = payload["metadata"]

    assert reply == "hello there"
    assert metadata is not None, "stream never reached its terminal frame"
    assert metadata["answer_source"] == "llm"


def test_a_fast_provider_gets_no_keepalive(monkeypatch):
    """Silence is what triggers a keepalive; a prompt reply should add none."""
    body = _post(monkeypatch, delay=0.0, heartbeat=10.0)
    assert ": hb" not in body


def test_the_default_interval_is_a_sane_ten_seconds():
    assert chat_module.SSE_HEARTBEAT_S == chat_module.DEFAULT_SSE_HEARTBEAT_S
    assert chat_module.DEFAULT_SSE_HEARTBEAT_S == 10.0


@pytest.mark.parametrize("raw,expected", [
    (None, 10.0),        # unset falls back
    ("5", 5.0),
    ("0.5", 0.5),
    ("  7  ", 7.0),      # whitespace tolerated
    ("", 10.0),
    ("   ", 10.0),
    ("not-a-number", 10.0),
    ("0", 10.0),         # would spin
    ("-3", 10.0),        # would spin
    ("0.01", 10.0),      # faster than the timeout's own resolution, not a keepalive
    ("100000", 10.0),    # so large it is not a keepalive any more
])
def test_the_interval_is_parsed_defensively(monkeypatch, raw, expected):
    """A malformed env var must not stop the app from starting, and a hostile
    one must not be honoured: a zero interval spins, a huge one is no
    keepalive at all."""
    if raw is None:
        monkeypatch.delenv("SSE_HEARTBEAT_S", raising=False)
    else:
        monkeypatch.setenv("SSE_HEARTBEAT_S", raw)
    assert chat_module._env_seconds("SSE_HEARTBEAT_S", 10.0) == expected
