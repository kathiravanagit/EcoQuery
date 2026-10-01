"""
Bring-your-own-key (`X-Provider-Key` / `X-OpenRouter-Key`).

The contract under test: a caller-supplied key is used for the outbound call,
takes precedence over server keys, falls back to them if rejected, and is never
written to the key store, the usage ledger, the response cache or a log line.
"""

import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import providers as providers_mod
from providers import (
    BYOK_SENTINEL_ID,
    ProviderRouter,
    _with_byok,
    extract_byok_key,
    provider_router,
)

SENTINEL = "sk-byok-DO-NOT-LEAK-8f3a"
SERVER_KEY = "sk-server-77aa"


async def _chat(model_id, messages, byok=None, max_tokens=16):
    """Invoke the *real* implementation.

    conftest's autouse fixture patches `provider_router.chat_completion`, so
    the method is called unbound to bypass that patch.
    """
    return await ProviderRouter.chat_completion(
        provider_router, model_id, messages, max_tokens, byok=byok
    )


def _stream(model_id, messages, byok=None, max_tokens=16):
    """Not `async def`: `stream_completion` is an async generator function, so
    this returns the generator itself rather than a coroutine."""
    return ProviderRouter.stream_completion(
        provider_router, model_id, messages, max_tokens, byok=byok
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

def test_absent_headers_yield_none():
    assert extract_byok_key(None) is None
    assert extract_byok_key({}) is None
    assert extract_byok_key({"X-Provider-Key": "   "}) is None


def test_openrouter_shorthand():
    assert extract_byok_key({"X-OpenRouter-Key": SENTINEL}) == ("openrouter", SENTINEL)


def test_generic_header_names_its_provider():
    assert extract_byok_key({"X-Provider-Key": SENTINEL, "X-Provider": "google"}) == (
        "google",
        SENTINEL,
    )


def test_unknown_provider_falls_back_to_the_default():
    provider, key = extract_byok_key({"X-Provider-Key": SENTINEL, "X-Provider": "notreal"})
    assert provider == "openrouter"
    assert key == SENTINEL


def test_grok_is_an_accepted_byok_provider():
    """A provider missing from PROVIDER_BASE_URLS is silently rejected here,
    so `X-Provider: grok` would quietly fall back to the server's OpenRouter
    key instead of using the caller's xAI credential."""
    assert extract_byok_key({"X-Provider-Key": SENTINEL, "X-Provider": "grok"}) == (
        "grok",
        SENTINEL,
    )


def test_an_oversized_header_is_treated_as_absent():
    assert extract_byok_key({"X-Provider-Key": "x" * 513}) is None


# ── Injection into the key rotation ──────────────────────────────────────────

def test_byok_is_prepended_so_it_is_tried_before_server_keys():
    keys, server_count, injected = _with_byok(
        {"openrouter": [{"id": "k1", "key_value": SERVER_KEY}]},
        ("openrouter", SENTINEL),
    )
    assert injected is True
    assert server_count == 1
    bucket = keys["openrouter"]
    assert bucket[0]["id"] == BYOK_SENTINEL_ID
    assert bucket[0]["key_value"] == SENTINEL
    assert bucket[1]["key_value"] == SERVER_KEY


def test_without_byok_the_rotation_is_untouched():
    original = {"openrouter": [{"id": "k1", "key_value": SERVER_KEY}]}
    keys, server_count, injected = _with_byok(original, None)
    assert keys is original
    assert server_count == 1
    assert injected is False


def test_server_key_count_zero_when_only_the_caller_has_a_key():
    _keys, server_count, injected = _with_byok({}, ("openrouter", SENTINEL))
    assert server_count == 0
    assert injected is True


# ── Runtime behaviour ────────────────────────────────────────────────────────

def test_successful_byok_call_reports_it_without_leaking_the_key(caplog):
    log_usage = MagicMock()
    with patch.object(providers_mod.key_manager, "get_all_providers_keys", return_value={}), \
         patch.object(providers_mod.key_manager, "log_usage", log_usage), \
         patch.object(provider_router, "_call_provider", _ok), \
         caplog.at_level(logging.DEBUG):
        result = asyncio.run(_chat("openai/gpt-4o-mini", [{"role": "user", "content": "hi"}],
                                   byok=("google", SENTINEL)))

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
                                   byok=("openrouter", SENTINEL)))

    assert server_calls == [SERVER_KEY]
    assert result["provider_lineage"]["byok_used"] is False
    # The rejected supplied key never reaches a log line or a deactivation.
    assert SENTINEL not in caplog.text
    assert not any(call.args and call.args[0] == BYOK_SENTINEL_ID
                   for call in log_usage.call_args_list)
    assert not any(call.args and call.args[0] == BYOK_SENTINEL_ID
                   for call in mark_inactive.call_args_list)


def test_rejected_byok_with_no_server_fallback_is_named_explicitly(caplog):
    def router(api_key, base_url, target_model, messages, max_tokens):
        raise RuntimeError(f"401 Incorrect API key provided: {api_key}")

    with patch.object(providers_mod.key_manager, "get_all_providers_keys", return_value={}), \
         patch.object(providers_mod.key_manager, "log_usage", MagicMock()), \
         patch.object(provider_router, "_call_provider", router), \
         caplog.at_level(logging.DEBUG):
        with pytest.raises(RuntimeError) as exc:
            asyncio.run(_chat("openai/gpt-4o-mini", [{"role": "user", "content": "hi"}],
                              byok=("openrouter", SENTINEL)))

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
                             byok=("openrouter", SENTINEL)))
        caplog_text = caplog.text

    payload = json.loads(str(exc.value))
    assert payload["error_code"] == "PROVIDER_KEY_REJECTED"
    assert SENTINEL not in str(exc.value)
    assert SENTINEL not in caplog_text
