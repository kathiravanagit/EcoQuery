"""In-memory shared stores and small helpers shared across the backend."""

import os

ORGANIZATIONS: dict = {}
ORG_INVITES: dict = {}
ORG_API_KEYS: dict = {}
WEBHOOKS: dict[str, list] = {}


def _env_number(name: str, default: float, low: float, high: float) -> float:
    """Read a bounded float. Anything unusable falls back rather than raises:
    a bad environment variable must not stop the server from starting.

    Bounds are checked after parsing so that "abc", "-1" and "999999" are all
    answered with `default` rather than with a value nobody wrote down.
    """
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if low <= value <= high else default
