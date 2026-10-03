"""Per-provider circuit breaker: state machine, wiring, and the safety valve.

The safety-valve tests matter most. A breaker that can skip every candidate
turns a partial fault into a total outage of our own making — nothing
attempted, no success possible to close anything, no route back. So the suite
asserts that an open breaker still leaves a provider to try, and that a trial
call lost to a cancelled request does not pin a provider out of the rotation
forever.
"""

import asyncio
import json
import logging
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import providers as providers_mod
from circuit_breaker import CircuitBreaker, is_outage, provider_breaker
from providers import ProviderRouter, provider_router

MESSAGES = [{"role": "user", "content": "hi"}]


class FakeAPIError(Exception):
    """Mimics the provider SDK: some errors carry an HTTP status, some don't."""

    def __init__(self, status_code, text="provider error"):
        super().__init__(text)
        if status_code is not None:
            self.status_code = status_code


def _breaker(threshold=3, cooldown=60.0, trial_timeout=120.0):
    return CircuitBreaker(threshold=threshold, cooldown_s=cooldown,
                          trial_timeout_s=trial_timeout)


def _keys(*names):
    """Server keys for each named provider, so the router has someone to try."""
    return {name: [{"id": f"{name}-key", "key_value": f"value-for-{name}"}]
            for name in names}


async def _chat(keys, call):
    with patch.object(providers_mod.key_manager, "get_all_providers_keys",
                      return_value=keys), \
         patch.object(providers_mod.key_manager, "log_usage", MagicMock()), \
         patch.object(provider_router, "_call_provider", call):
        return await ProviderRouter.chat_completion(
            provider_router, "openai/gpt-4o-mini", MESSAGES, 1024
        )


async def _stream(keys):
    with patch.object(providers_mod.key_manager, "get_all_providers_keys",
                      return_value=keys), \
         patch.object(providers_mod.key_manager, "log_usage", MagicMock()), \
         patch.object(providers_mod, "AsyncOpenAI", _RecordingOpenAI):
        items = []
        async for item in ProviderRouter.stream_completion(
            provider_router, "openai/gpt-4o-mini", MESSAGES, 1024
        ):
            items.append(item)
        return items


async def _always_fails(api_key, base_url, target_model, messages, max_tokens):
    raise FakeAPIError(503, "service unavailable")


async def _always_works(api_key, base_url, target_model, messages, max_tokens):
    return {"content": "hello there", "usage": {"completion_tokens": 5}}


async def _bad_request(api_key, base_url, target_model, messages, max_tokens):
    # Wording avoids "401"/"403"/"invalid" so the key-deactivation branch in
    # the router is not what this test ends up exercising.
    raise FakeAPIError(400, "bad request")


def _chunk_stream(text):
    def _delta(content):
        return SimpleNamespace(content=content)

    async def _gen():
        for part in (text[:1], text[1:]):
            yield SimpleNamespace(choices=[SimpleNamespace(delta=_delta(part))])

    return _gen()


class _RecordingOpenAI:
    """Records which base_url every streaming attempt actually reached.

    `final_provider == google` alone would not prove a skip — it is also what
    you get when openrouter is tried, fails, and falls through. The list of
    reached base URLs is the evidence that it was never tried at all.
    """

    reached: list = []

    def __init__(self, api_key=None, base_url=None, timeout=None):
        self.base_url = base_url or ""
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    async def _create(self, **kwargs):
        _RecordingOpenAI.reached.append(self.base_url)
        if "openrouter" in self.base_url:
            raise FakeAPIError(503, "service unavailable")
        return _chunk_stream("hello from google")


# ── What counts as an outage ────────────────────────────────────────────────

@pytest.mark.parametrize("status", [None, 500, 502, 503, 429])
def test_failures_to_serve_count(status):
    assert is_outage(FakeAPIError(status)) is True


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_a_request_we_wrote_badly_does_not_trip(status):
    """Tripping on a 400 would drop that provider for *every* other model too,
    which is a far larger error than the one that started it."""
    assert is_outage(FakeAPIError(status)) is False


def test_an_uninterpretable_status_is_treated_as_a_failure_to_serve():
    assert is_outage(FakeAPIError("not-a-number")) is True


# ── State machine ───────────────────────────────────────────────────────────

def test_a_provider_we_have_not_failed_on_is_tried():
    allowed, tripped = _breaker().partition(["openrouter", "google"])
    assert allowed == ["openrouter", "google"]
    assert tripped == []


@pytest.mark.parametrize("failures,expect_tripped", [(1, False), (2, False), (3, True)])
def test_three_failures_trip_a_provider(failures, expect_tripped):
    cb = _breaker(threshold=3)
    for _ in range(failures):
        cb.record_failure("openrouter")
    _, tripped = cb.partition(["openrouter", "google"])
    assert ("openrouter" in tripped) is expect_tripped


def test_a_success_closes_it():
    cb = _breaker(threshold=3)
    for _ in range(3):
        cb.record_failure("openrouter")
    cb.record_success("openrouter")
    allowed, tripped = cb.partition(["openrouter", "google"])
    assert allowed == ["openrouter", "google"]
    assert tripped == []


def test_a_provider_appearing_once_per_key_is_considered_once():
    """`_attempt_order` yields one batch per key, so a tripped provider with
    two keys would otherwise show up twice in the skipped list."""
    cb = _breaker(threshold=1, cooldown=60.0)
    cb.record_failure("openrouter")
    allowed, tripped = cb.partition(["openrouter", "openrouter", "google"])
    assert tripped == ["openrouter"]
    assert allowed == ["google"]


def test_threshold_zero_disables_the_breaker():
    cb = _breaker(threshold=0)
    for _ in range(10):
        cb.record_failure("openrouter")
    assert cb.enabled is False
    assert cb.partition(["openrouter", "google"]) == (["openrouter", "google"], [])


def test_an_open_breaker_never_empties_the_candidate_list():
    """The bug this whole module is written to prevent: skipping every provider
    would fail the request with nothing attempted and no way to recover."""
    cb = _breaker(threshold=1, cooldown=60.0)
    cb.record_failure("openrouter")
    cb.record_failure("google")
    allowed, tripped = cb.partition(["openrouter", "google"])
    assert allowed, "the request must never be failed without a provider being tried"
    assert len(allowed) == 1, "the valve admits exactly one; the rest stay tripped"
    assert len(tripped) == 1


def test_the_forced_provider_is_the_one_that_failed_longest_ago():
    cb = _breaker(threshold=1, cooldown=60.0)
    cb.record_failure("openrouter")
    time.sleep(0.05)
    cb.record_failure("google")
    allowed, _ = cb.partition(["google", "openrouter"])
    assert allowed == ["openrouter"], "the closest to opening on its own goes first"


def test_a_tripped_provider_is_admitted_once_the_cooldown_elapses():
    cb = _breaker(threshold=1, cooldown=0.05, trial_timeout=60.0)
    cb.record_failure("openrouter")
    assert "openrouter" in cb.partition(["openrouter", "google"])[1]

    time.sleep(0.15)
    allowed, _ = cb.partition(["openrouter", "google"])
    assert "openrouter" in allowed, "the trial after the cooldown"
    assert "google" in allowed, "healthy providers are unaffected by a trip"


def test_half_open_admits_exactly_one_trial():
    cb = _breaker(threshold=1, cooldown=0.05, trial_timeout=60.0)
    cb.record_failure("openrouter")
    time.sleep(0.15)

    first_allowed, _ = cb.partition(["openrouter", "google"])
    assert "openrouter" in first_allowed, "the first request after the cooldown"

    second_allowed, second_tripped = cb.partition(["openrouter", "google"])
    assert "openrouter" not in second_allowed
    assert "openrouter" in second_tripped, "only one trial in flight at a time"


def test_a_successful_trial_closes_it():
    cb = _breaker(threshold=1, cooldown=0.05, trial_timeout=60.0)
    cb.record_failure("openrouter")
    time.sleep(0.15)
    assert "openrouter" in cb.partition(["openrouter", "google"])[0]

    cb.record_success("openrouter")
    allowed, tripped = cb.partition(["openrouter", "google"])
    assert "openrouter" in allowed
    assert "openrouter" not in tripped


def test_a_failed_trial_reopens_with_a_fresh_cooldown():
    cb = _breaker(threshold=1, cooldown=0.05, trial_timeout=60.0)
    cb.record_failure("openrouter")
    time.sleep(0.15)
    assert "openrouter" in cb.partition(["openrouter", "google"])[0]

    cb.record_failure("openrouter")
    _, tripped = cb.partition(["openrouter", "google"])
    assert "openrouter" in tripped, "straight back out, cooldown restarted"


def test_a_trial_that_never_reports_back_is_released():
    """A cancelled request owns the trial and never reports it. Without this
    the provider stays out of the rotation forever, punished by something
    that never proved it unhealthy."""
    cb = _breaker(threshold=1, cooldown=0.05, trial_timeout=0.1)
    cb.record_failure("openrouter")
    time.sleep(0.15)

    assert "openrouter" in cb.partition(["openrouter", "google"])[0]   # trial taken
    assert "openrouter" not in cb.partition(["openrouter", "google"])[0]  # reserved

    time.sleep(0.2)                                                    # timeout
    assert "openrouter" in cb.partition(["openrouter", "google"])[0], \
        "a lost trial must not pin the provider out of the rotation"


def test_opening_is_logged_once_rather_than_on_every_failure(caplog):
    cb = _breaker(threshold=2, cooldown=60.0)
    with caplog.at_level(logging.WARNING, logger="EcoQuery.circuit_breaker"):
        cb.record_failure("openrouter")
        cb.record_failure("openrouter")   # opens
        cb.record_failure("openrouter")   # already open — must not log again
    assert len([r for r in caplog.records if "circuit opened" in r.getMessage()]) == 1


def test_snapshot_reports_state_without_secrets():
    cb = _breaker(threshold=1, cooldown=60.0)
    cb.record_failure("openrouter")
    snap = cb.snapshot()
    assert snap["openrouter"]["status"] == "open"
    assert snap["openrouter"]["retry_in_s"] <= 60.0
    assert snap["openrouter"]["consecutive_failures"] == 1
    assert "key" not in json.dumps(snap).lower()


# ── Wiring: chat_completion ─────────────────────────────────────────────────

def test_a_failed_upstream_call_is_recorded_against_that_provider():
    with pytest.raises(RuntimeError):
        asyncio.run(_chat(_keys("openrouter"), _always_fails))
    snap = provider_breaker.snapshot()
    assert snap["openrouter"]["consecutive_failures"] == 1


def test_a_successful_call_records_success():
    result = asyncio.run(_chat(_keys("openrouter"), _always_works))
    assert result["provider_lineage"]["final_provider"] == "openrouter"
    assert provider_breaker.snapshot()["openrouter"]["status"] == "closed"


def test_a_400_does_not_trip_the_provider():
    with pytest.raises(RuntimeError):
        asyncio.run(_chat(_keys("openrouter"), _bad_request))
    snap = provider_breaker.snapshot().get("openrouter", {})
    assert snap.get("status", "closed") == "closed", \
        "a request we wrote badly must leave the provider in the rotation"
    assert snap.get("consecutive_failures", 0) == 0, \
        "it must not even be counted as a failure"


def test_a_tripped_provider_is_skipped_and_the_next_one_is_used():
    for _ in range(3):
        provider_breaker.record_failure("openrouter")

    result = asyncio.run(_chat(_keys("openrouter", "google"), _always_works))

    attempts = result["provider_lineage"]["attempted_providers"]
    assert attempts[0]["status"] == "skipped"
    assert attempts[0]["failure_reason"] == "CircuitOpen"
    assert result["provider_lineage"]["final_provider"] == "google"


def test_with_every_provider_tripped_the_request_is_still_attempted():
    """The safety valve, end to end. Everything tripped, and the answer is
    still produced rather than refused."""
    for name in ("openrouter", "google"):
        for _ in range(3):
            provider_breaker.record_failure(name)

    result = asyncio.run(_chat(_keys("openrouter", "google"), _always_works))

    statuses = [a["status"] for a in
                result["provider_lineage"]["attempted_providers"]]
    assert "success" in statuses, "the request must not die with nothing attempted"
    assert statuses.count("skipped") == 1, "exactly one is skipped, one is forced"
    assert any(e.get("forced_attempts") for e in provider_breaker.snapshot().values()), \
        "a forced call must be visible to an operator"


# ── Wiring: stream_completion ───────────────────────────────────────────────

def test_the_streaming_path_skips_a_tripped_provider():
    _RecordingOpenAI.reached = []
    for _ in range(3):
        provider_breaker.record_failure("openrouter")

    items = asyncio.run(_stream(_keys("openrouter", "google")))

    lineage = [i["provider_lineage"] for i in items if "provider_lineage" in i][0]
    assert lineage["attempted_providers"][0]["status"] == "skipped"
    assert lineage["final_provider"] == "google"
    assert not [url for url in _RecordingOpenAI.reached if "openrouter" in url], \
        "a tripped provider must never be dialled, not merely fail again"


# ── Observability ───────────────────────────────────────────────────────────

def test_the_health_endpoint_exposes_breaker_state():
    from main import app

    for _ in range(3):
        provider_breaker.record_failure("openrouter")
    with TestClient(app) as client:
        data = client.get("/api/health").json()

    breakers = data["provider_circuit_breakers"]
    assert breakers["openrouter"]["status"] == "open"
    assert breakers["openrouter"]["retry_in_s"] <= 60.0
