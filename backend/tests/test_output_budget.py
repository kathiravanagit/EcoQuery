"""The output budget actually sent to a provider, and what counts as a pass.

Two ways a request could come back empty and be misreported:

* `max_output_tokens` was caller-controlled down to 1, and a reasoning model
  can spend a small budget thinking. Measured against the live providers:
  gemini-flash-latest returned content=None at max_tokens 8, 16 and 32 and only
  produced text from 64, while llama-4-scout answered at every budget. The
  floor keeps that from ever being requested.
* `check_health` counted a non-empty `choices` list as a passing completion
  test at max_tokens=5, so a provider that answered with no text was reported
  healthy.
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import providers as providers_mod
import routers.chat as chat_module
from providers import ProviderRouter, provider_router
from routers.chat import MIN_OUTPUT_TOKENS, _effective_max_tokens


# ── Caller-chosen budget ─────────────────────────────────────────────────────

def test_floor_blocks_the_measured_starvation_zone():
    """Anything at or below the zone where Gemini answered with no text."""
    for requested in (1, 8, 16, 32, MIN_OUTPUT_TOKENS - 1):
        assert _effective_max_tokens(requested) == MIN_OUTPUT_TOKENS


def test_floor_sits_above_where_text_began_appearing():
    # 32 produced nothing, 64 produced text.
    assert MIN_OUTPUT_TOKENS > 32


def test_floor_never_inflates_a_legitimate_request():
    assert _effective_max_tokens(None) == 200      # the default
    assert _effective_max_tokens(600) == 600
    assert _effective_max_tokens(4000) == 4000     # schema maximum


def test_both_chat_endpoints_apply_the_floor():
    """Guard against one of the two call sites drifting back to a bare `or 200`."""
    source = Path(chat_module.__file__).read_text(encoding="utf-8")
    assert source.count("_effective_max_tokens(req.max_output_tokens)") == 2
    assert "req.max_output_tokens or 200" not in source


# ── Health probe ─────────────────────────────────────────────────────────────

def _run_health(content, choices=True):
    """Run the real `check_health` against a stubbed provider.

    Returns `(health, request_kwargs)` so the caller can assert on what the
    probe actually asked for.
    """
    seen = {}

    class FakeClient:
        def __init__(self, api_key=None, base_url=None, timeout=None):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        async def _create(self, **kwargs):
            seen.update(kwargs)
            choices_list = []
            if choices:
                choices_list = [SimpleNamespace(message=SimpleNamespace(content=content))]
            return SimpleNamespace(choices=choices_list)

    with patch.object(providers_mod.key_manager, "get_active_keys",
                      return_value=[{"id": "k", "key_value": "server-key"}]), \
         patch.object(providers_mod, "AsyncOpenAI", FakeClient):
        health = asyncio.run(ProviderRouter.check_health(provider_router))
    return health, seen


def test_health_probe_asks_for_a_budget_that_can_produce_text():
    _health, seen = _run_health("hello")
    assert seen["max_tokens"] >= 64
    assert seen["max_tokens"] > 5


def test_health_reports_a_clean_pass_when_text_comes_back():
    health, _seen = _run_health("hello")
    assert set(health) == {"openrouter", "google", "grok"}
    for status in health.values():
        assert status["configured"] is True
        assert status["authenticated"] is True
        assert status["completion_test"] is True
        assert status["failure_reason"] is None


def test_health_does_not_call_an_empty_reply_a_pass():
    """Choices present but no text: authenticated, yet not a completed test."""
    health, _seen = _run_health("")
    for status in health.values():
        assert status["authenticated"] is True
        assert status["completion_test"] is False
        assert status["failure_reason"] == "EmptyContent"


def test_health_handles_a_response_with_no_choices():
    health, _seen = _run_health(None, choices=False)
    for status in health.values():
        assert status["authenticated"] is True
        assert status["completion_test"] is False
        assert status["failure_reason"] == "EmptyContent"


def test_health_carries_the_http_status_in_the_failure_reason():
    """A bare exception type cannot tell "bad key" from "valid key, account
    has no credits" — which is precisely how xAI answers a working credential
    on an uncredited team, and an operator has to tell those apart."""

    class Forbidden(Exception):
        status_code = 403

    class RejectingClient:
        def __init__(self, api_key=None, base_url=None, timeout=None):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        async def _create(self, **kwargs):
            raise Forbidden("Your newly created team doesn't have any credits")

    with patch.object(providers_mod.key_manager, "get_active_keys",
                      return_value=[{"id": "k", "key_value": "server-key"}]), \
         patch.object(providers_mod, "AsyncOpenAI", RejectingClient):
        health = asyncio.run(ProviderRouter.check_health(provider_router))

    assert set(health) == {"openrouter", "google", "grok"}
    for status in health.values():
        assert status["configured"] is True
        assert status["completion_test"] is False
        assert status["failure_reason"] == "Forbidden(403)"
