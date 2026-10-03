"""Per-provider circuit breaker for the fallback chain.

A provider that is down costs every request the latency of a doomed call
before the chain moves on. Under load that compounds: each request pays the
timeout, so the requests behind it queue up paying it too, and one broken
vendor becomes the whole service's tail latency.

The breaker lets a request skip a provider that has failed recently and go
straight to the next one, then reopens the door after a cooldown so recovery
is found by ordinary traffic rather than by a separate probe.

The rule that matters more than any threshold: **an open breaker must never
be able to stop every provider from being tried.** Skipping them all would
fail the request with nothing attempted, no success possible to reset
anything, and no route to recovery -- an outage we cause ourselves out of a
fault that was merely partial. So a breaker whose cooldown has elapsed goes
half-open and admits one trial, and if every candidate is still tripped the
least recently failed one is tried anyway. Failing the request is always
available; it is the choice we must not make before we have to.

Scope, so nothing here reads as more than it is:

- Per process and in memory. Two workers do not share a view, and a restart
  clears it, so each worker rediscovers recovery on its own traffic.
- A trip is a routing decision, not a health verdict. It records that *this
  process* could not get an answer, not that the vendor is down.

Set PROVIDER_BREAKER_THRESHOLD=0 to disable the whole thing.
"""

from __future__ import annotations

import logging
import time
from threading import Lock

from shared import _env_number

logger = logging.getLogger("EcoQuery.circuit_breaker")

CLOSED = "closed"
OPEN = "open"
HALF_OPEN = "half_open"

# Three failures says "not a blip" without needing a streak long enough that
# every request has already paid the timeout several times over. A minute of
# cooldown is short enough to recover quickly and long enough that a retry
# storm does not immediately re-trip it.
DEFAULT_THRESHOLD = 3.0
DEFAULT_COOLDOWN_S = 60.0
# How long a trial call may take to report back before it is assumed lost.
DEFAULT_TRIAL_TIMEOUT_S = 120.0

THRESHOLD = int(_env_number("PROVIDER_BREAKER_THRESHOLD", DEFAULT_THRESHOLD, 0.0, 100.0))
COOLDOWN_S = _env_number("PROVIDER_BREAKER_COOLDOWN_S", DEFAULT_COOLDOWN_S, 1.0, 3600.0)
TRIAL_TIMEOUT_S = _env_number(
    "PROVIDER_BREAKER_TRIAL_TIMEOUT_S", DEFAULT_TRIAL_TIMEOUT_S, 1.0, 3600.0
)


def is_outage(exc: BaseException) -> bool:
    """Whether an exception says the provider did not serve us.

    Keyed on every exception, a breaker would trip on a request we wrote
    badly: a 400 for an unsupported model, a refusal, a validation failure.
    Dropping that provider for *every* model afterwards is a far larger
    error than the one that started it, so only failures to serve count.

    429 does count. It is not the provider being down, it is the provider
    asking us to stop -- and moving on is the entire job of the chain.
    """
    status = getattr(exc, "status_code", None)
    if status is None:
        # No status: a timeout, a refused connection, a truncated body. The
        # provider did not answer, which is precisely this module's business.
        return True
    try:
        return status == 429 or not (400 <= status < 500)
    except TypeError:
        # An attribute we cannot reason about should not be able to keep a
        # dead provider in the rotation by accident.
        return True


class _ProviderState:
    """One provider's view of the world.

    The defaults mean "never seen", which is the same as healthy: a provider
    we have not failed on is one we should try.
    """

    __slots__ = ("status", "failures", "opened_at", "trial_started_at", "forced")

    def __init__(self) -> None:
        self.status = CLOSED
        self.failures = 0
        self.opened_at = 0.0
        self.trial_started_at = 0.0
        # How often the safety valve reached for this provider. Visible in
        # the health endpoint because it means every provider was tripped.
        self.forced = 0


class CircuitBreaker:
    """TTL-free state machine over provider names. No TTL: a success closes it."""

    def __init__(self, threshold: int = THRESHOLD,
                 cooldown_s: float = COOLDOWN_S,
                 trial_timeout_s: float = TRIAL_TIMEOUT_S):
        self.threshold = int(threshold)
        self.cooldown_s = float(cooldown_s)
        self.trial_timeout_s = float(trial_timeout_s)
        self._lock = Lock()
        self._states: dict[str, _ProviderState] = {}

    @property
    def enabled(self) -> bool:
        return self.threshold >= 1

    def _state(self, provider: str) -> _ProviderState:
        state = self._states.get(provider)
        if state is None:
            state = _ProviderState()
            self._states[provider] = state
        return state

    def _may_attempt(self, provider: str, now: float) -> bool:
        """Called with the lock held."""
        state = self._state(provider)
        if state.status == CLOSED:
            return True

        if state.status == HALF_OPEN:
            # One trial at a time -- otherwise every request during the
            # recovery window would pile onto the provider we are testing.
            if now - state.trial_started_at <= self.trial_timeout_s:
                return False
            # The trial never reported back: the request that owned it was
            # cancelled or died. Without this the provider would stay out of
            # the rotation forever, punished by something that never actually
            # proved it unhealthy.
            state.trial_started_at = now
            return True

        # OPEN
        if now - state.opened_at < self.cooldown_s:
            return False
        state.status = HALF_OPEN
        state.trial_started_at = now
        return True

    def partition(self, providers: list[str]) -> tuple[list[str], list[str]]:
        """Split candidates into ``(allowed, tripped)``, first-seen order kept.

        `allowed` is never empty when the input is not -- see the safety
        valve. Duplicates are collapsed, since a provider appears once per
        key in `_attempt_order` and must only be considered once here.
        """
        if not providers:
            return [], []
        unique = list(dict.fromkeys(providers))
        if not self.enabled:
            return unique, []

        allowed: list[str] = []
        tripped: list[str] = []
        with self._lock:
            now = time.monotonic()
            for provider in unique:
                (allowed if self._may_attempt(provider, now) else tripped).append(provider)

            if not allowed and tripped:
                # Safety valve. Skipping every candidate would fail the
                # request with nothing attempted and no success possible to
                # close anything -- so try the one that failed longest ago,
                # the closest to opening on its own.
                chosen = min(tripped, key=lambda p: self._state(p).opened_at)
                tripped.remove(chosen)
                allowed.append(chosen)
                state = self._state(chosen)
                state.forced += 1
                logger.warning(
                    "every provider is tripped; forcing a call to %s anyway", chosen
                )
        return allowed, tripped

    def record_success(self, provider: str) -> None:
        if not self.enabled:
            return
        with self._lock:
            state = self._state(provider)
            reopened = state.status != CLOSED
            state.status = CLOSED
            state.failures = 0
            state.opened_at = 0.0
            state.trial_started_at = 0.0
            if reopened:
                logger.info("circuit closed for provider %s", provider)

    def record_failure(self, provider: str) -> None:
        if not self.enabled:
            return
        with self._lock:
            state = self._state(provider)
            state.failures += 1
            was = state.status

            if was == HALF_OPEN:
                # The trial failed: back out, and restart the cooldown from
                # now rather than inheriting an expiry that was nearly due.
                state.status = OPEN
                state.opened_at = time.monotonic()
                logger.warning(
                    "circuit reopened for provider %s: the trial call failed", provider
                )
                return

            if state.failures >= self.threshold:
                state.status = OPEN
                state.opened_at = time.monotonic()
                if was != OPEN:
                    logger.warning(
                        "circuit opened for provider %s after %d consecutive "
                        "failures; skipping it for %.0fs",
                        provider, state.failures, self.cooldown_s,
                    )

    def snapshot(self) -> dict[str, dict]:
        """What an operator needs, and nothing that is a secret."""
        with self._lock:
            now = time.monotonic()
            out: dict[str, dict] = {}
            for provider in sorted(self._states):
                state = self._states[provider]
                entry: dict = {"status": state.status}
                if state.status == OPEN:
                    entry["retry_in_s"] = round(max(0.0, self.cooldown_s - (now - state.opened_at)), 1)
                entry["consecutive_failures"] = state.failures
                if state.forced:
                    entry["forced_attempts"] = state.forced
                out[provider] = entry
            return out

    def reset(self) -> None:
        with self._lock:
            self._states.clear()


# Shared across requests: the point is that the *next* request finds what the
# last one learned.
provider_breaker = CircuitBreaker()
