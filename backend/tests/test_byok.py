"""
Bring-your-own-key (`X-OpenRouter-Key` / `X-Google-Key` / `X-Grok-Key`, plus
the original `X-Provider-Key` + `X-Provider` form).

The contract under test: caller-supplied keys are accepted per provider, used
for the outbound call, take precedence over that provider's server keys, fall
back to them if rejected, and are never written to the key store, the usage
ledger, the response cache or a log line. `key_source` reports ownership of
each provider's key without echoing a credential.
"""

import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import providers as providers_mod
from providers import (
    BYOK_SENTINEL_ID,
    ProviderRouter,
    _with_byok,
    extract_byok_keys,
    provider_router,
)

SENTINEL = "sk-byok-DO-NOT-LEAK-8f3a"
GOOGLE_SENTINEL = "AIza-DO-NOT-LEAK-91b2"
GROK_SENTINEL = "xai-DO-NOT-LEAK-c3d4"
SERVER_KEY = "sk-server-77aa"


async def _chat(model_id, messages, byok_keys=None, max_tokens=16):
    """Invoke the *real* implementation.

    conftest's autouse fixture patches `provider_router.chat_completion`, so
    the method is called unbound to bypass that patch.
    """
    return await ProviderRouter.chat_completion(
        provider_router, model_id, messages, max_tokens, byok_keys=byok_keys
    )


def _stream(model_id, messages, byok_keys=None, max_tokens=16):
    """Not `async def`: `stream_completion` is an async generator function, so
    this returns the generator itself rather than a coroutine."""
    return ProviderRouter.stream_completion(
        provider_router, model_id, messages, max_tokens, byok_keys=byok_keys
    )


def _collect(agen):
    async def drain():
        out = []
        async for item in agen:
            out.append(item)
        return out

    return asyncio.run(drain())


async def _ok(api_key, base_url, target_model, messages, max_tokens):
    return {"content": f"reply via {api_key}", "usage": {"completion_tokens": 3}}


# ── Header parsing ───────────────────────────────────────────────────────────

def test_absent_headers_yield_no_keys():
    assert extract_byok_keys(None) == {}
    assert extract_byok_keys({}) == {}
    assert extract_byok_keys({"X-Provider-Key": "   "}) == {}
    assert extract_byok_keys({"X-OpenRouter-Key": "", "X-Google-Key": "  "}) == {}


def test_openrouter_shorthand():
    assert extract_byok_keys({"X-OpenRouter-Key": SENTINEL}) == {
        "openrouter": SENTINEL
    }


def test_every_per_provider_header_is_read_at_once():
    """The whole point of the multi-provider form: three keys can ride the
    same request, so whichever provider the router lands on has the caller's
    credential waiting for it."""
    supplied = extract_byok_keys({
        "X-OpenRouter-Key": SENTINEL,
        "X-Google-Key": GOOGLE_SENTINEL,
        "X-Grok-Key": GROK_SENTINEL,
    })
    assert supplied == {
        "openrouter": SENTINEL,
        "google": GOOGLE_SENTINEL,
        "grok": GROK_SENTINEL,
    }


def test_grok_header_is_not_a_groq_provider():
    """Grok (xAI) and GroqCloud are unrelated companies. A `X-Grok-Key` must
    land on the xAI bucket and must never invent a `groq` provider that has no
    base URL — sending a Groq credential to api.x.ai would fail confusingly."""
    supplied = extract_byok_keys({"X-Grok-Key": GROK_SENTINEL})
    assert supplied == {"grok": GROK_SENTINEL}
    assert "groq" not in supplied


def test_generic_header_names_its_provider():
    assert extract_byok_keys({"X-Provider-Key": SENTINEL, "X-Provider": "google"}) == {
        "google": SENTINEL,
    }


def test_unknown_provider_falls_back_to_the_default():
    assert extract_byok_keys({"X-Provider-Key": SENTINEL, "X-Provider": "notreal"}) == {
        "openrouter": SENTINEL,
    }


def test_grok_is_an_accepted_byok_provider():
    """A provider missing from PROVIDER_BASE_URLS is silently rejected here,
    so `X-Provider: grok` would quietly fall back to the server's OpenRouter
    key instead of using the caller's xAI credential."""
    assert extract_byok_keys({"X-Provider-Key": SENTINEL, "X-Provider": "grok"}) == {
        "grok": SENTINEL,
    }


def test_an_oversized_header_is_treated_as_absent():
    assert extract_byok_keys({"X-Provider-Key": "x" * 513}) == {}


def test_one_oversized_key_does_not_discard_the_others():
    """Each header is validated on its own: a bad Google key must not throw
    away a perfectly good OpenRouter key on the same request."""
    supplied = extract_byok_keys({
        "X-Google-Key": "x" * 513,
        "X-OpenRouter-Key": SENTINEL,
    })
    assert supplied == {"openrouter": SENTINEL}


def test_the_specific_header_wins_over_the_generic_form():
    assert extract_byok_keys({
        "X-OpenRouter-Key": SENTINEL,
        "X-Provider-Key": "sk-generic",
        "X-Provider": "openrouter",
    }) == {"openrouter": SENTINEL}


def test_generic_and_specific_headers_can_target_different_providers():
    supplied = extract_byok_keys({
        "X-Google-Key": GOOGLE_SENTINEL,
        "X-Provider-Key": SENTINEL,
        "X-Provider": "grok",
    })
    assert supplied == {"google": GOOGLE_SENTINEL, "grok": SENTINEL}


# ── Injection into the key rotation ──────────────────────────────────────────

def test_byok_is_prepended_so_it_is_tried_before_server_keys():
    keys, server_count, injected = _with_byok(
        {"openrouter": [{"id": "k1", "key_value": SERVER_KEY}]},
        {"openrouter": SENTINEL},
    )
    assert injected is True
    assert server_count == 1
    bucket = keys["openrouter"]
    assert bucket[0]["id"] == BYOK_SENTINEL_ID
    assert bucket[0]["key_value"] == SENTINEL
    assert bucket[1]["key_value"] == SERVER_KEY


def test_each_key_lands_in_its_own_provider_bucket():
    keys, _server_count, injected = _with_byok(
        {
            "openrouter": [{"id": "k1", "key_value": SERVER_KEY}],
            "google": [{"id": "k2", "key_value": "g-server"}],
        },
        {"openrouter": SENTINEL, "google": GOOGLE_SENTINEL},
    )
    assert injected is True
    assert keys["openrouter"][0]["key_value"] == SENTINEL
    assert keys["openrouter"][1]["key_value"] == SERVER_KEY
    assert keys["google"][0]["key_value"] == GOOGLE_SENTINEL
    assert keys["google"][1]["key_value"] == "g-server"


def test_a_provider_with_no_supplied_key_is_left_alone():
    keys, _count, injected = _with_byok(
        {"grok": [{"id": "k3", "key_value": "x-server"}]},
        {"openrouter": SENTINEL},
    )
    assert injected is True
    assert keys["grok"] == [{"id": "k3", "key_value": "x-server"}]
    assert keys["openrouter"][0]["key_value"] == SENTINEL


def test_without_byok_the_rotation_is_untouched():
    original = {"openrouter": [{"id": "k1", "key_value": SERVER_KEY}]}
    keys, server_count, injected = _with_byok(original, None)
    assert keys is original
    assert server_count == 1
    assert injected is False


def test_empty_byok_map_leaves_the_rotation_untouched():
    original = {"openrouter": [{"id": "k1", "key_value": SERVER_KEY}]}
    keys, _count, injected = _with_byok(original, {})
    assert keys is original
    assert injected is False


def test_server_key_count_zero_when_only_the_caller_has_a_key():
    _keys, server_count, injected = _with_byok({}, {"openrouter": SENTINEL})
    assert server_count == 0
    assert injected is True


# ── key_source metadata ──────────────────────────────────────────────────────

def test_key_source_reports_ownership_per_provider(caplog):
    with patch.object(providers_mod.key_manager, "get_all_providers_keys",
                      return_value={"openrouter": [{"id": "k1", "key_value": SERVER_KEY}]}), \
         patch.object(providers_mod.key_manager, "log_usage", MagicMock()), \
         patch.object(provider_router, "_call_provider", _ok), \
         caplog.at_level(logging.DEBUG):
        result = asyncio.run(_chat(
            "openai/gpt-4o-mini", [{"role": "user", "content": "hi"}],
            byok_keys={"google": GOOGLE_SENTINEL},
        ))

    lineage = result["provider_lineage"]
    assert lineage["key_source"] == {
        "openrouter": "server",
        "google": "user",
        "grok": "none",
    }
    # Ownership only — no credential may be echoed back to the caller.
    assert GOOGLE_SENTINEL not in json.dumps(lineage)
    assert SENTINEL not in caplog.text


def test_key_source_marks_the_serving_provider_when_it_is_the_callers():
    with patch.object(providers_mod.key_manager, "get_all_providers_keys", return_value={}), \
         patch.object(providers_mod.key_manager, "log_usage", MagicMock()), \
         patch.object(provider_router, "_call_provider", _ok):
        result = asyncio.run(_chat(
            "openai/gpt-4o-mini", [{"role": "user", "content": "hi"}],
            byok_keys={"openrouter": SENTINEL},
        ))

    lineage = result["provider_lineage"]
    assert lineage["final_provider"] == "openrouter"
    assert lineage["byok_used"] is True
    assert lineage["key_source"]["openrouter"] == "user"
    assert json.dumps(lineage).find(SENTINEL) == -1


# ── Runtime behaviour ────────────────────────────────────────────────────────

def test_successful_byok_call_reports_it_without_leaking_the_key(caplog):
    log_usage = MagicMock()
    with patch.object(providers_mod.key_manager, "get_all_providers_keys", return_value={}), \
         patch.object(providers_mod.key_manager, "log_usage", log_usage), \
         patch.object(provider_router, "_call_provider", _ok), \
         caplog.at_level(logging.DEBUG):
        result = asyncio.run(_chat("openai/gpt-4o-mini", [{"role": "user", "content": "hi"}],
                                   byok_keys={"google": SENTINEL}))

    assert result["content"] == f"reply via {SENTINEL}"
    assert result["provider_lineage"]["byok_used"] is True
    # A supplied key must never be billed to (or recorded against) the store.
    assert not any(call.args and call.args[0] == BYOK_SENTINEL_ID
                   for call in log_usage.call_args_list)
    assert SENTINEL not in caplog.text


def test_byok_failure_falls_back_to_the_server_key(caplog):
    server_calls = []

    def router(api_key, base_url, target_model, messages, max_tokens):
        if api_key == SENTINEL:
            # Provider SDK errors can quote the credential.
            raise RuntimeError(f"401 Incorrect API key provided: {api_key}")
        server_calls.append(api_key)
        return _ok(api_key, base_url, target_model, messages, max_tokens)

    log_usage = MagicMock()
    mark_inactive = MagicMock()
    with patch.object(providers_mod.key_manager, "get_all_providers_keys",
                      return_value={"openrouter": [{"id": "k1", "key_value": SERVER_KEY}]}), \
         patch.object(providers_mod.key_manager, "log_usage", log_usage), \
         patch.object(providers_mod.key_manager, "mark_key_inactive", mark_inactive), \
         patch.object(provider_router, "_call_provider", router), \
         caplog.at_level(logging.DEBUG):
        result = asyncio.run(_chat("openai/gpt-4o-mini", [{"role": "user", "content": "hi"}],
                                   byok_keys={"openrouter": SENTINEL}))

    assert server_calls == [SERVER_KEY]
    assert result["provider_lineage"]["byok_used"] is False
    # The rejected supplied key never reaches a log line or a deactivation.
    assert SENTINEL not in caplog.text
    assert not any(call.args and call.args[0] == BYOK_SENTINEL_ID
                   for call in log_usage.call_args_list)
    assert not any(call.args and call.args[0] == BYOK_SENTINEL_ID
                   for call in mark_inactive.call_args_list)


def test_a_rejected_key_on_one_provider_does_not_block_another(caplog):
    """The caller's Google key is bad; their OpenRouter key is not. Only the
    broken credential should fall through to server keys."""
    def router(api_key, base_url, target_model, messages, max_tokens):
        if api_key == GOOGLE_SENTINEL:
            raise RuntimeError(f"401 Incorrect API key provided: {api_key}")
        return _ok(api_key, base_url, target_model, messages, max_tokens)

    with patch.object(providers_mod.key_manager, "get_all_providers_keys",
                      return_value={
                          "openrouter": [{"id": "k1", "key_value": SERVER_KEY}],
                          "google": [{"id": "k2", "key_value": "g-server"}],
                      }), \
         patch.object(providers_mod.key_manager, "log_usage", MagicMock()), \
         patch.object(provider_router, "_call_provider", router), \
         caplog.at_level(logging.DEBUG):
        result = asyncio.run(_chat(
            "openai/gpt-4o-mini", [{"role": "user", "content": "hi"}],
            byok_keys={"google": GOOGLE_SENTINEL, "openrouter": SENTINEL},
        ))

    assert result["content"] == f"reply via {SENTINEL}"
    assert result["provider_lineage"]["final_provider"] == "openrouter"
    assert result["provider_lineage"]["key_source"]["google"] == "user"
    assert GOOGLE_SENTINEL not in caplog.text
    assert SENTINEL not in caplog.text


def test_rejected_byok_with_no_server_fallback_is_named_explicitly(caplog):
    def router(api_key, base_url, target_model, messages, max_tokens):
        raise RuntimeError(f"401 Incorrect API key provided: {api_key}")

    with patch.object(providers_mod.key_manager, "get_all_providers_keys", return_value={}), \
         patch.object(providers_mod.key_manager, "log_usage", MagicMock()), \
         patch.object(provider_router, "_call_provider", router), \
         caplog.at_level(logging.DEBUG):
        with pytest.raises(RuntimeError) as exc:
            asyncio.run(_chat("openai/gpt-4o-mini", [{"role": "user", "content": "hi"}],
                              byok_keys={"openrouter": SENTINEL}))

    payload = json.loads(str(exc.value))
    assert payload["error_code"] == "PROVIDER_KEY_REJECTED"
    assert "supplied API key" in payload["message"]
    assert SENTINEL not in str(exc.value)
    assert SENTINEL not in caplog.text


def test_streaming_reuses_the_same_contract(caplog):
    class FakeClient:
        def __init__(self, api_key=None, base_url=None, timeout=None):
            self.api_key = api_key
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self._create)
            )

        async def _create(self, **kwargs):
            # Provider SDK errors can quote the credential.
            raise RuntimeError(f"401 Incorrect API key provided: {self.api_key}")

    caplog_text = ""

    with patch.object(providers_mod.key_manager, "get_all_providers_keys", return_value={}), \
         patch.object(providers_mod.key_manager, "log_usage", MagicMock()), \
         patch.object(providers_mod, "AsyncOpenAI", FakeClient), \
         caplog.at_level(logging.DEBUG):
        with pytest.raises(RuntimeError) as exc:
            _collect(_stream("openai/gpt-4o-mini", [{"role": "user", "content": "hi"}],
                             byok_keys={"openrouter": SENTINEL}))
        caplog_text = caplog.text

    payload = json.loads(str(exc.value))
    assert payload["error_code"] == "PROVIDER_KEY_REJECTED"
    assert SENTINEL not in str(exc.value)
    assert SENTINEL not in caplog_text


def test_streaming_success_carries_key_source():
    class FakeClient:
        def __init__(self, api_key=None, base_url=None, timeout=None):
            self.api_key = api_key
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self._create)
            )

        async def _create(self, **kwargs):
            async def gen():
                yield SimpleNamespace(choices=[SimpleNamespace(
                    delta=SimpleNamespace(content="hello")
                )])
            return gen()

    with patch.object(providers_mod.key_manager, "get_all_providers_keys", return_value={}), \
         patch.object(providers_mod.key_manager, "log_usage", MagicMock()), \
         patch.object(providers_mod, "AsyncOpenAI", FakeClient):
        events = _collect(_stream(
            "openai/gpt-4o-mini", [{"role": "user", "content": "hi"}],
            byok_keys={"google": GOOGLE_SENTINEL},
        ))

    lineage = next(e["provider_lineage"] for e in events if "provider_lineage" in e)
    assert lineage["byok_used"] is True
    assert lineage["key_source"] == {
        "openrouter": "none",
        "google": "user",
        "grok": "none",
    }
    assert GOOGLE_SENTINEL not in json.dumps(lineage)


# ── On the wire ──────────────────────────────────────────────────────────────

def test_the_http_response_carries_key_source():
    """`_build_metadata` rebuilds lineage from a fixed list of fields, so a key
    added to `provider_lineage` alone never reaches the client. This is the
    test that keeps `byok_used` and `key_source` actually on the wire.

    The knowledge and cache branches return early with no lineage at all —
    correctly, since no provider call happened — so the message has to reach
    the LLM branch for the assertion to mean anything.
    """
    from fastapi.testclient import TestClient

    from main import app

    lineage = {
        "requested_provider": "openrouter",
        "requested_model": "m",
        "attempted_providers": [],
        "final_provider": "google",
        "final_model": "gm",
        "fallback_reason": None,
        "success": True,
        "byok_used": True,
        "key_source": {"openrouter": "server", "google": "user", "grok": "none"},
    }
    provider_response = {
        "content": "Test provider response",
        "usage": {"prompt_tokens": 5, "completion_tokens": 4},
        "provider_lineage": lineage,
    }
    chat_mock = AsyncMock(return_value=provider_response)

    with patch("classifier.classifier.classify",
               return_value={"tier": "simple", "confidence": 0.85, "method": "test-mock"}), \
         patch("carbon.get_carbon_optimal_region",
               return_value={"region": "eu-north-1", "energy_source": "Hydro/Wind",
                             "carbon_intensity_g_kwh": 18.5,
                             "estimated_savings_g_co2": 1.2, "method": "test-mock"}), \
         patch("providers.provider_router.chat_completion", new=chat_mock):
        with TestClient(app) as client:
            resp = client.post("/api/chat",
                               json={"message": "Zqvx7 explain the frimble protocol in one line"},
                               headers={"X-Google-Key": GOOGLE_SENTINEL})

    assert resp.status_code == 200, resp.text
    # The header actually reached the provider call for this request only.
    assert chat_mock.call_args.kwargs["byok_keys"] == {"google": GOOGLE_SENTINEL}
    metadata = resp.json()["metadata"]
    assert metadata["answer_source"] == "llm", "knowledge/cache answered; nothing to assert"
    assert metadata["final_provider"] == "google"
    assert metadata["byok_used"] is True
    assert metadata["key_source"] == {
        "openrouter": "server",
        "google": "user",
        "grok": "none",
    }
    # Ownership only — the credential that was sent must not come back.
    assert GOOGLE_SENTINEL not in resp.text
