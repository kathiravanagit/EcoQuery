"""
In-process idempotency for POST /api/chat/stream.

A stream is bound to its connection: when the socket goes, `generate()` is
closed and the provider call is cancelled with it. So a client that loses the
response and sends again would otherwise pay for a second generation of the
same send. This store makes the second send cheap — if the first one reached a
finished answer, the answer is handed back instead of produced again.

Scope, stated plainly so the tests and the docs do not overclaim:

- It dedupes *completed* work. Generation that died with the socket leaves
  nothing behind and the retry generates afresh, which is correct — there is
  no answer to replay.
- It is per process and in memory. A restart loses it, and two instances would
  not share it. That is deliberate: the replies are transient and never
  persisted, so it does not undercut `STORE_QUERY_TEXT=false`.
- It covers retries of one send, not two concurrent sends of the same message.
  The chat surfaces already refuse to start a run while one is in flight, so
  that case is prevented at the source rather than resolved here.

Set `IDEMPOTENCY_TTL_S=0` to turn the whole thing off.
"""

import os
import time
from collections import OrderedDict
from threading import Lock

# How long a finished answer stays replayable. Long enough to outlive a flaky
# connection or a user noticing a blank bubble, short enough that a reply does
# not linger in memory indefinitely.
DEFAULT_TTL_S = 300.0

# Hard ceiling on entries so a caller cannot grow the process heap by sending
# unique keys. Oldest entry is evicted first.
DEFAULT_MAX_ENTRIES = 256

# Bounds on an acceptable key. A client id is opaque, not a secret, so this is
# shape validation only — enough to keep a malformed header from becoming an
# unbounded dict key, and nothing more.
MIN_KEY_LENGTH = 8
MAX_KEY_LENGTH = 128
_ALLOWED_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789-_"
)


def _env_number(name: str, default: float, low: float, high: float) -> float:
    """Read a bounded float. Anything unusable falls back rather than raises:
    a bad environment variable must not stop the server from starting."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if low <= value <= high else default


TTL_S = _env_number("IDEMPOTENCY_TTL_S", DEFAULT_TTL_S, 0.0, 86400.0)
MAX_ENTRIES = int(_env_number("IDEMPOTENCY_MAX_ENTRIES", float(DEFAULT_MAX_ENTRIES), 0.0, 100000.0))


def normalise_key(raw) -> str | None:
    """Return the key if it is usable, else `None`.

    An unusable key is treated as *no* key rather than as a bad request. This
    is an optimisation over an optional header; rejecting a caller for sending
    an odd one would turn a tolerant client into a broken one.
    """
    if not isinstance(raw, str):
        return None
    key = raw.strip()
    if not MIN_KEY_LENGTH <= len(key) <= MAX_KEY_LENGTH:
        return None
    if not all(char in _ALLOWED_CHARS for char in key):
        return None
    return key


class IdempotencyStore:
    """TTL-bounded LRU of finished streams.

    Ordered by access, not insertion, so the entries a caller is most likely to
    retry stay resident while the oldest ones fall off the front.
    """

    def __init__(self, ttl_s: float = TTL_S, max_entries: int = MAX_ENTRIES):
        self.ttl_s = ttl_s
        self.max_entries = max_entries
        self._lock = Lock()
        # key -> (monotonic timestamp, value)
        self._entries: "OrderedDict[str, tuple[float, dict]]" = OrderedDict()

    @property
    def enabled(self) -> bool:
        return self.ttl_s > 0 and self.max_entries > 0

    def get(self, key: str | None) -> dict | None:
        """Return the stored answer for `key`, or `None` if absent or expired."""
        if not key or not self.enabled:
            return None
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            stored_at, value = entry
            # Monotonic: a wall-clock step backwards must not pin an entry
            # forever, nor let one jump forward discard it early.
            if time.monotonic() - stored_at > self.ttl_s:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return value

    def put(self, key: str | None, value: dict) -> None:
        """Record a finished answer, evicting the least recently used entry."""
        if not key or not self.enabled:
            return
        with self._lock:
            self._entries[key] = (time.monotonic(), value)
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


# Shared across requests: the point is that a *second* request finds the first
# one's answer.
idempotency_store = IdempotencyStore()
