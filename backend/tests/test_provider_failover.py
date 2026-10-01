"""OpenRouter -> Google failover, including a provider that answers with no text.

A provider can return `content: ""` — a safety block, or a `max_tokens` budget
a reasoning model spends before it emits anything (gemini-flash-latest returns
`content=None` at `max_tokens=16`). That used to fall through without being
recorded, so the caller was told "all configured providers failed" while
`provider_attempts` showed the provider as never tried — which reads as a
broken Google key when the key is fine.

These tests pin both halves: the failover has to happen, and every attempt has
to be visible afterwards.
"""

import asyncio
import json
import logging
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import providers as providers_mod
from providers import ProviderRouter, provider_router

OR_KEY = "sk-or-server-key"
GG_KEY = "google-server-key"
GROUPED = {
    "openrouter": [{"id": "or1", "key_value": OR_KEY}],
    "google": [{"id": "gg1", "key_value": GG_KEY}],
}
MSGS = [{"role": "user", "content": "hi"}]


# ── Invocation helpers (call the real implementation past conftest's patch) ───

def _chat(model_id="nvidia/nemotron-3-super-120b-a12b:free", max_tokens=16):
    return asyncio.run(
        ProviderRouter.chat_completion(provider_router, model_id, MSGS, max_tokens)
    )


def _stream(model_id="nvidia/nemotron-3-super-120b-a12b:free", max_tokens=16):
    """Not `async def`: returns the async generator itself."""
    return ProviderRouter.stream_completion(provider_router, model_id, MSGS, max_tokens)


def _collect(agen):
    async def drain():
        out = []
        async for item in agen:
            out.append(item)
        return out

    return asyncio.run(drain())


# ── Fake transports ──────────────────────────────────────────────────────────

async def _empty_openrouter(api_key, base_url, target_model, messages, max_tokens):
    """OpenRouter returns no text; Google answers."""
    if api_key == GG_KEY:
        return {"content": "OK from google", "usage": {"completion_tokens": 3}}
    return {"content": "", "usage": {"prompt_tokens": 8, "completion_tokens": 0}}


async def _always_empty(api_key, base_url, target_model, messages, max_tokens):
    return {"content": None, "usage": {"prompt_tokens": 8, "completion_tokens": 0}}


async def _openrouter_rejected(api_key, base_url, target_model, messages, max_tokens):
    if api_key == OR_KEY:
        raise RuntimeError("Error code: 401 - simulated provider rejection")
    return {"content": "OK from google", "usage": {"completion_tokens": 3}}


def _client_returning(api_key_texts):
    """Build an AsyncOpenAI stand-in that streams `api_key_texts[api_key]`."""

    class FakeClient:
        def __init__(self, api_key=None, base_url=None, timeout=None):
            self.api_key = api_key
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        async def _create(self, **kwargs):
            async def generate():
                for text in api_key_texts.get(self.api_key, []):
                    yield SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))]
                    )

            return generate()

    return FakeClient


def _patched(**overrides):
    """Common patch stack; every test stubs the store and the usage ledger."""
    defaults = {
        "get_all_providers_keys": MagicMock(return_value=GROUPED),
        "log_usage": MagicMock(),
        "mark_key_inactive": MagicMock(),
    }
    defaults.update(overrides)
    return [patch.object(providers_mod.key_manager, name, value)
            for name, value in defaults.items()]


def _enter(patches):
    stack = ExitStack()
    for p in patches:
        stack.enter_context(p)
    return stack


# ── Non-streaming ────────────────────────────────────────────────────────────

def test_no_text_from_openrouter_still_reaches_google(caplog):
    with _enter(_patched()), \
         patch.object(provider_router, "_call_provider", _empty_openrouter), \
         caplog.at_level(logging.WARNING):
        result = _chat()

    lineage = result["provider_lineage"]
    assert lineage["final_provider"] == "google"
    assert lineage["fallback_reason"] == "provider fallback"
    assert [(a["provider"], a["status"]) for a in lineage["attempted_providers"]] == [
        ("openrouter", "empty_response"),
        ("google", "success"),
    ]
    assert "returned no text" in caplog.text


def test_rejected_openrouter_still_reaches_google():
    with _enter(_patched()), \
         patch.object(provider_router, "_call_provider", _openrouter_rejected):
        result = _chat()

    lineage = result["provider_lineage"]
    assert lineage["final_provider"] == "google"
    assert [(a["provider"], a["status"]) for a in lineage["attempted_providers"]] == [
        ("openrouter", "failed"),
        ("google", "success"),
    ]


def test_every_provider_returning_no_text_is_reported_as_such():
    with _enter(_patched()), \
         patch.object(provider_router, "_call_provider", _always_empty):
        with pytest.raises(RuntimeError) as exc:
            _chat()

    payload = json.loads(str(exc.value))
    assert payload["error_code"] == "PROVIDER_UNAVAILABLE"
    # The whole point: a provider that answered with nothing must not look
    # like one that was never called.
    assert [(a["provider"], a["status"]) for a in payload["provider_attempts"]] == [
        ("openrouter", "empty_response"),
        ("google", "empty_response"),
    ]


def test_empty_response_is_logged_against_the_key(caplog):
    log_usage = MagicMock()
    with _enter(_patched(log_usage=log_usage)), \
         patch.object(provider_router, "_call_provider", _empty_openrouter), \
         caplog.at_level(logging.WARNING):
        _chat()

    assert any(len(call.args) > 4 and call.args[4] == "empty response"
               for call in log_usage.call_args_list)


# ── Streaming ────────────────────────────────────────────────────────────────

def test_stream_with_no_tokens_from_openrouter_falls_through_to_google():
    with _enter(_patched()), \
         patch.object(providers_mod, "AsyncOpenAI",
                      _client_returning({OR_KEY: [], GG_KEY: ["OK", " from", " google"]})):
        events = _collect(_stream())

    tokens = "".join(e["token"] for e in events if "token" in e)
    lineage = next(e["provider_lineage"] for e in events if "provider_lineage" in e)

    assert tokens == "OK from google"
    assert lineage["final_provider"] == "google"
    assert [(a["provider"], a["status"]) for a in lineage["attempted_providers"]] == [
        ("openrouter", "empty_response"),
        ("google", "success"),
    ]


def test_stream_where_no_provider_emits_anything_names_them_all():
    with _enter(_patched()), \
         patch.object(providers_mod, "AsyncOpenAI", _client_returning({OR_KEY: [], GG_KEY: []})):
        with pytest.raises(RuntimeError) as exc:
            _collect(_stream())

    payload = json.loads(str(exc.value))
    assert payload["error_code"] == "PROVIDER_UNAVAILABLE"
    assert [(a["provider"], a["status"]) for a in payload["provider_attempts"]] == [
        ("openrouter", "empty_response"),
        ("google", "empty_response"),
    ]


def test_stream_success_still_reports_no_fallback():
    """A first-choice success must not claim a fallback happened."""
    with _enter(_patched()), \
         patch.object(providers_mod, "AsyncOpenAI",
                      _client_returning({OR_KEY: ["hi"], GG_KEY: ["unused"]})):
        events = _collect(_stream())

    lineage = next(e["provider_lineage"] for e in events if "provider_lineage" in e)
    assert lineage["final_provider"] == "openrouter"
    assert lineage["fallback_reason"] is None
