"""Provider key seeding, and the three-provider failover order.

The key store is a file that outlives a configuration change, so seeding has to
reconcile with the environment on *every* start rather than only on the first.
Otherwise editing ``GOOGLE_API_KEY`` does nothing until ``keys.db`` is deleted
by hand, and the OpenRouter failover keeps calling the previous — often
quota-exhausted — credential.

Reconciliation has to stay idempotent in both directions: it must not duplicate
a row on every boot, and it must not revive a key that a provider rejection
deliberately deactivated.
"""

import sqlite3

import pytest

from key_manager import KeyManager
from providers import PROVIDER_BASE_URLS, PROVIDER_FALLBACK_MODELS, PROVIDER_FALLBACK_ORDER

_SECRET = "unit-test-secret-0123456789abcdef"
_PROVIDER_ENV_VARS = (
    "OPENROUTER_API_KEY",
    "OPENROUTER_API_KEY_2",
    "GOOGLE_API_KEY",
    "GROK_API_KEY",
)


@pytest.fixture
def env(monkeypatch):
    """A provider environment the test owns completely, plus a fixed secret."""
    for name in _PROVIDER_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    # The store has to be encrypted with something the test can reproduce
    # across "restarts" (a second KeyManager on the same file).
    monkeypatch.setenv("KEY_ENCRYPTION_KEY", _SECRET)
    return monkeypatch


def _restart(db_path):
    """Simulate a process restart: same store, seeding runs again."""
    return KeyManager(db_path=str(db_path))


def test_failover_order_is_openrouter_then_google_then_grok():
    """Every provider EcoQuery can fail over to, in the order it promises.

    Grok sits last on purpose: OpenRouter's catalogue is free and the Google
    failover is cheap, while xAI bills per token — a paid provider must never
    be tried ahead of a free one.
    """
    assert PROVIDER_FALLBACK_ORDER == ("openrouter", "google", "grok")
    assert PROVIDER_FALLBACK_ORDER[-1] == "grok"
    assert sorted(PROVIDER_BASE_URLS) == ["google", "grok", "openrouter"]
    assert sorted(PROVIDER_FALLBACK_MODELS) == ["google", "grok"]
    # Grok cannot take an OpenRouter slug (`vendor/model`), so it needs a model
    # of its own — exactly as Google does. It also has to be non-empty: an
    # empty `GROK_MODEL=` is indistinguishable from a valid setting to
    # `os.getenv(k, default)` and would send a blank model id.
    assert PROVIDER_FALLBACK_MODELS["grok"]
    assert "/" not in PROVIDER_FALLBACK_MODELS["grok"]
    assert PROVIDER_BASE_URLS["grok"] == "https://api.x.ai/v1"


def test_env_keys_are_seeded_into_an_empty_store(tmp_path, env):
    env.setenv("OPENROUTER_API_KEY", "or-test")
    env.setenv("GOOGLE_API_KEY", "g-test")

    manager = KeyManager(db_path=str(tmp_path / "keys.db"))
    grouped = manager.get_all_providers_keys()

    assert sorted(grouped) == ["google", "openrouter"]
    assert [k["key_value"] for k in grouped["openrouter"]] == ["or-test"]
    assert [k["key_value"] for k in grouped["google"]] == ["g-test"]


def test_restarting_does_not_duplicate_rows(tmp_path, env):
    env.setenv("OPENROUTER_API_KEY", "or-test")
    env.setenv("GOOGLE_API_KEY", "g-test")
    db_path = tmp_path / "keys.db"

    KeyManager(db_path=str(db_path))
    manager = _restart(db_path)

    with manager.get_connection() as conn:
        rows = conn.execute("SELECT provider, key_value FROM api_keys").fetchall()
    assert len(rows) == 2


def test_changed_env_key_is_picked_up_on_next_start(tmp_path, env):
    """The whole point: rotating GOOGLE_API_KEY must take effect."""
    env.setenv("OPENROUTER_API_KEY", "or-test")
    env.setenv("GOOGLE_API_KEY", "google-old")
    db_path = tmp_path / "keys.db"
    KeyManager(db_path=str(db_path))

    env.setenv("GOOGLE_API_KEY", "google-new")
    manager = _restart(db_path)

    stored = [k["key_value"] for k in manager.get_active_keys("google")]
    assert "google-new" in stored


def test_deactivated_key_is_not_reinserted_or_revived(tmp_path, env):
    """A key a provider rejected stays rejected across restarts."""
    env.setenv("GOOGLE_API_KEY", "google-test")
    db_path = tmp_path / "keys.db"

    manager = KeyManager(db_path=str(db_path))
    key_id = manager.get_active_keys("google")[0]["id"]
    manager.mark_key_inactive(key_id)

    restarted = _restart(db_path)

    assert restarted.get_active_keys("google") == []
    with restarted.get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM api_keys WHERE provider = 'google'"
        ).fetchone()[0]
    assert count == 1


def test_unreadable_rows_do_not_shadow_an_env_key(tmp_path, env):
    """A row that cannot be decrypted is skipped at runtime, so the credential
    from the environment has to be inserted beside it — otherwise the failover
    has no usable key at all."""
    db_path = tmp_path / "keys.db"
    manager = KeyManager(db_path=str(db_path))
    with manager.get_connection() as conn:
        conn.execute(
            "INSERT INTO api_keys (id, key_value, provider) VALUES (?, ?, ?)",
            ("dead-row", "enc:unreadable", "google"),
        )
        conn.commit()

    env.setenv("GOOGLE_API_KEY", "google-fresh")
    restarted = _restart(db_path)

    usable = [k["key_value"] for k in restarted.get_active_keys("google")]
    assert usable == ["google-fresh"]


def test_grok_env_key_is_seeded(tmp_path, env):
    """Grok is a real provider now, so its credential must reach the store.

    It used to be deliberately inert, which meant adding `GROK_API_KEY` to
    `.env` had no effect at all and the failover never saw it.
    """
    env.setenv("GROK_API_KEY", "grok-test")
    env.setenv("OPENROUTER_API_KEY", "or-test")

    manager = KeyManager(db_path=str(tmp_path / "keys.db"))

    grouped = manager.get_all_providers_keys()
    assert sorted(grouped) == ["grok", "openrouter"]
    assert [k["key_value"] for k in grouped["grok"]] == ["grok-test"]


def test_store_rows_cannot_be_read_back_as_plaintext(tmp_path, env):
    """Credentials are written encrypted and returned decrypted, never both."""
    env.setenv("GOOGLE_API_KEY", "google-test")
    manager = KeyManager(db_path=str(tmp_path / "keys.db"))

    with manager.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        stored = conn.execute("SELECT key_value FROM api_keys").fetchone()["key_value"]

    assert stored.startswith("enc:")
    assert "google-test" not in stored
