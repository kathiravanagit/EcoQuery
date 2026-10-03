"""Idempotency for POST /api/chat/stream.

The claim being tested is narrow and worth stating precisely: a *second* send
carrying the key of a *finished* one is answered from memory instead of from a
provider. Generation that never finished leaves nothing behind, so the retry
generates — there is no answer to replay.

The endpoint tests matter more than the store's own, because the ordering does:
the lookup has to happen after authentication and before routing, or a replay
either leaks across tenants or costs money it was meant to save.
"""

import json
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import providers as providers_mod
import routers.chat as chat_module
from idempotency import (
    DEFAULT_MAX_ENTRIES,
    IdempotencyStore,
    _env_number,
    idempotency_store,
    normalise_key,
)
from main import app
from schemas import ChatRequest

# Unanswerable from the 3000-Q knowledge base, so the run always reaches the
# LLM branch — the only branch that stores anything.
PROMPT = "Zqvx7 explain the frimble protocol in one line"

KEY = "idem-test-key-0001"

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


@pytest.fixture(autouse=True)
def _empty_store():
    """The store is process-global by design; tests must not inherit one."""
    idempotency_store.clear()
    yield
    idempotency_store.clear()


@contextmanager
def counting_provider(fail: bool = False):
    """Patch the provider with one that records how many times it was asked.

    Without this the whole feature could be deleted and a test that only
    checked the reply text would still pass, since a replay and a fresh
    generation produce the same answer.
    """
    calls = {"n": 0}

    async def stream(*args, **kwargs):
        calls["n"] += 1
        if fail:
            raise RuntimeError('{"error_code": "PROVIDER_UNAVAILABLE", "message": "down"}')
        # Numbered so a test can tell a replay from a fresh generation. All
        # copies of a fixed string look alike, and "the reply was correct" is
        # exactly the assertion the feature must not be allowed to pass on.
        yield {"token": f"Test provider response {calls['n']}"}
        yield {"provider_lineage": LINEAGE}

    with patch.object(providers_mod.provider_router, "stream_completion", stream):
        yield calls


def _send(client, key=None, prompt=PROMPT):
    headers = {"Idempotency-Key": key} if key else {}
    return client.post("/api/chat/stream", json={"message": prompt}, headers=headers)


def _frames(body: str):
    for line in body.splitlines():
        if line.startswith("data: "):
            try:
                yield json.loads(line[6:])
            except json.JSONDecodeError:
                continue


def _answer(body: str):
    """The text and metadata a consumer would end up rendering."""
    text = ""
    metadata = None
    for payload in _frames(body):
        if isinstance(payload, dict) and payload.get("token"):
            text += payload["token"]
        if isinstance(payload, dict) and payload.get("done"):
            metadata = payload.get("metadata")
    return text, metadata


# ── Key handling ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("0123456789abcdef", "0123456789abcdef"),
    ("  spaced-key-1234  ", "spaced-key-1234"),   # surrounding space tolerated
    ("abc-def_ghi", "abc-def_ghi"),
    ("a" * 128, "a" * 128),                        # upper bound inclusive
    ("a" * 8, "a" * 8),                            # lower bound inclusive
])
def test_a_plausible_key_is_accepted(raw, expected):
    assert normalise_key(raw) == expected


@pytest.mark.parametrize("raw", [
    None,
    12345,                    # not a string at all
    "",
    "   ",
    "short",                  # under the minimum
    "a" * 129,                # over the maximum
    "has spaces inside",      # interior whitespace
    "semicolon;drop",
    "quote\"inject",
    "unicode-é-key",
])
def test_an_unusable_key_is_ignored_rather_than_rejected(raw):
    """A hostile or broken key must not become an error: it simply gets no
    deduplication, exactly as if the header had never been sent."""
    assert normalise_key(raw) is None


# ── Store behaviour ──────────────────────────────────────────────────────────

def test_an_entry_round_trips():
    store = IdempotencyStore(ttl_s=60, max_entries=4)
    store.put("k-12345678", {"reply": "hi"})
    assert store.get("k-12345678") == {"reply": "hi"}


def test_an_unknown_key_returns_none():
    assert IdempotencyStore(ttl_s=60, max_entries=4).get("k-12345678") is None


def test_an_expired_entry_is_gone():
    store = IdempotencyStore(ttl_s=60, max_entries=4)
    store.put("k-12345678", {"reply": "hi"})
    # Back-dated rather than slept on: expiry is the behaviour under test, and
    # a negative TTL would take the shortcut of disabling the store outright.
    key, (stored_at, value) = next(iter(store._entries.items()))
    store._entries[key] = (stored_at - 61, value)
    assert store.get("k-12345678") is None


def test_a_disabled_store_never_records_anything():
    store = IdempotencyStore(ttl_s=0, max_entries=4)
    assert store.enabled is False
    store.put("k-12345678", {"reply": "hi"})
    assert store.get("k-12345678") is None


def test_a_zero_capacity_store_is_also_disabled():
    store = IdempotencyStore(ttl_s=60, max_entries=0)
    assert store.enabled is False


def test_the_oldest_entry_is_evicted_at_capacity():
    store = IdempotencyStore(ttl_s=60, max_entries=2)
    store.put("k-aaaaaaa1", {"i": 1})
    store.put("k-aaaaaaa2", {"i": 2})
    store.put("k-aaaaaaa3", {"i": 3})
    assert len(store) == 2
    assert store.get("k-aaaaaaa1") is None, "oldest should have been evicted"
    assert store.get("k-aaaaaaa3") == {"i": 3}


def test_an_accessed_entry_is_not_the_one_evicted():
    """LRU, not FIFO: a key being retried is the one most worth keeping."""
    store = IdempotencyStore(ttl_s=60, max_entries=2)
    store.put("k-aaaaaaa1", {"i": 1})
    store.put("k-aaaaaaa2", {"i": 2})
    store.get("k-aaaaaaa1")          # touch it
    store.put("k-aaaaaaa3", {"i": 3})
    assert store.get("k-aaaaaaa1") == {"i": 1}
    assert store.get("k-aaaaaaa2") is None


def test_the_capacity_ceiling_is_a_sane_number():
    assert 0 < DEFAULT_MAX_ENTRIES <= 100000


@pytest.mark.parametrize("raw,expected", [
    (None, 7.0),
    ("", 7.0),
    ("12", 12.0),
    ("-1", 7.0),        # negative refused
    ("999999", 7.0),    # above ceiling refused
    ("abc", 7.0),       # unparseable refused
])
def test_the_env_number_is_bounded(monkeypatch, raw, expected):
    """A bad variable must fall back, never stop the server from starting."""
    if raw is None:
        monkeypatch.delenv("IDEMPOTENCY_TTL_S", raising=False)
    else:
        monkeypatch.setenv("IDEMPOTENCY_TTL_S", raw)
    assert _env_number("IDEMPOTENCY_TTL_S", 7.0, 0.0, 3600.0) == expected


# ── The endpoint, where the ordering actually matters ────────────────────────

def test_a_completed_send_is_replayed_without_touching_a_provider():
    with TestClient(app) as client, counting_provider() as calls:
        first = _send(client, key=KEY)
        assert first.status_code == 200, first.text
        text_before, meta_before = _answer(first.text)
        assert text_before, "the first send should have produced an answer"
        assert meta_before.get("idempotent_replay") is not True
        assert calls["n"] == 1

        second = _send(client, key=KEY)
        assert second.status_code == 200, second.text

    assert calls["n"] == 1, "the replay must not reach the provider"
    text_after, meta_after = _answer(second.text)
    assert text_after == text_before, "a replay must render the identical reply"
    assert meta_after.get("idempotent_replay") is True
    assert meta_after.get("answer_source") == meta_before.get("answer_source")


def test_a_replay_happens_before_routing_and_classification():
    """Ordering: if classification runs, the lookup is in the wrong place and
    a replay costs the work it exists to avoid."""
    with TestClient(app) as client, counting_provider() as calls:
        _send(client, key=KEY)
        assert calls["n"] == 1

        with patch.object(chat_module.classifier, "classify",
                          side_effect=AssertionError("classified a replay")) as classify:
            replay = _send(client, key=KEY)

    assert replay.status_code == 200, replay.text
    assert classify.call_count == 0
    assert calls["n"] == 1


def test_without_a_key_every_send_generates():
    with TestClient(app) as client, counting_provider() as calls:
        _send(client)
        _send(client)
    assert calls["n"] == 2, "the feature must be opt-in, not a global cache"


def test_a_malformed_key_behaves_exactly_like_no_key():
    with TestClient(app) as client, counting_provider() as calls:
        for _ in range(3):
            _send(client, key="bad key!")     # rejected by normalise_key
    assert calls["n"] == 3
    assert idempotency_store.get("bad key!") is None


def test_a_reused_key_must_not_answer_a_different_question():
    """The key identifies a send, not a caller's whole session.

    Two different prompts under one key: the second has to be generated, or
    the user is shown the first prompt's answer to their second question — a
    confidently-presented wrong answer is worse than paying to generate twice.
    The same prompt under the same key then replays, which is the case the
    feature exists for.
    """
    with TestClient(app) as client, counting_provider() as calls:
        first = _send(client, key=KEY, prompt="Say alpha")
        second = _send(client, key=KEY, prompt="Say omega")
        replayed = _send(client, key=KEY, prompt="Say omega")

    first_text, first_meta = _answer(first.text)
    second_text, second_meta = _answer(second.text)
    replay_text, replay_meta = _answer(replayed.text)

    assert first_meta.get("idempotent_replay") is not True
    assert second_meta.get("idempotent_replay") is not True, "a different question must not replay"
    assert second_text != first_text, "the second question was answered with the first answer"
    assert calls["n"] == 2

    assert replay_meta.get("idempotent_replay") is True
    assert replay_text == second_text, "the same question under the same key replays"
    assert calls["n"] == 2, "the replay must not reach the provider"


def test_a_failed_send_stores_nothing_for_a_later_retry():
    """No terminal frame, no stored answer: the retry generates afresh rather
    than replaying a failure."""
    with TestClient(app) as client, counting_provider(fail=True) as calls:
        first = _send(client, key=KEY)
        assert first.status_code == 200
        _, meta = _answer(first.text)
        assert meta is None, "an errored stream must not emit a done frame"
        assert calls["n"] == 1

        assert idempotency_store.get(KEY) is None, "a failure must not be replayable"

        second = _send(client, key=KEY)
        assert second.status_code == 200
    assert calls["n"] == 2, "the retry has to generate: there was no answer"


def test_a_replay_cannot_bypass_the_access_check(monkeypatch):
    """Seed the store first, then disable anonymous access. The answer is
    already in memory — that must not make it retrievable."""
    idempotency_store.put(KEY, {"reply": "private", "metadata": {"answer_source": "llm"}})
    monkeypatch.setattr(chat_module, "_ALLOW_ANONYMOUS_CHAT_STREAM", False)

    with TestClient(app) as client:
        resp = _send(client, key=KEY)

    assert resp.status_code in (401, 403), resp.text
    assert "private" not in resp.text


def test_the_fingerprint_scopes_an_answer_to_its_caller():
    """The store is process-wide, so the caller is part of the identity.

    Same key and same prompt is not enough on its own: without the principal
    a tenant who obtained another's key would be served that tenant's answer.
    """
    req = ChatRequest(message=PROMPT)
    mine = chat_module._request_fingerprint(req, "alice@example.com")

    assert mine != chat_module._request_fingerprint(req, "bob@example.com"), \
        "two callers must not share an answer"
    assert mine == chat_module._request_fingerprint(req, "alice@example.com"), \
        "the digest must be stable, or a retry would never match"
    assert mine != chat_module._request_fingerprint(
        ChatRequest(message="a different question"), "alice@example.com"
    ), "two questions must not share an answer"


def access_as(principal: str):
    """Stand in for the access check, returning a chosen caller.

    The check itself belongs to `test_chat_access_policy`. What matters here
    is the caller's *identity*, which would otherwise need two real signed
    tokens to say anything about key scoping.
    """
    async def _require(request, *, allow_anonymous):
        return principal

    return _require


def test_a_key_is_not_shared_across_tenants(monkeypatch):
    with TestClient(app) as client, counting_provider() as calls:
        monkeypatch.setattr(chat_module, "_require_chat_access", access_as("alice@example.com"))
        alice = _send(client, key=KEY)
        monkeypatch.setattr(chat_module, "_require_chat_access", access_as("bob@example.com"))
        bob_first = _send(client, key=KEY)
        bob_again = _send(client, key=KEY)

    _, alice_meta = _answer(alice.text)
    bob_text, bob_meta = _answer(bob_first.text)
    replay_text, replay_meta = _answer(bob_again.text)

    assert alice_meta.get("idempotent_replay") is not True
    assert bob_meta.get("idempotent_replay") is not True, (
        "a second tenant must not be answered with the first tenant's reply"
    )
    assert calls["n"] == 2

    assert replay_meta.get("idempotent_replay") is True
    assert replay_text == bob_text, "the same tenant does then replay its own answer"
    assert calls["n"] == 2, "the replay must not reach the provider"


def test_a_send_with_a_previously_unused_key_is_recorded():
    with TestClient(app) as client, counting_provider() as calls:
        _send(client, key="idem-never-seen-1")
    assert calls["n"] == 1
    assert len(idempotency_store) == 1
