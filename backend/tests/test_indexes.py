"""
Index coverage for the fields every read path filters or sorts on.

MongoDB is not required for these: `ensure_indexes` is exercised against a
recording stand-in so the *declared* index set is pinned without a live
database, and failure tolerance is asserted separately — an index build must
never stop the service from starting.
"""

import asyncio

from auth import auth_db
from ledger import VerificationLedger


class FakeCollection:
    def __init__(self, fail: bool = False):
        self.calls = []
        self.fail = fail

    async def create_index(self, keys, **options):
        if self.fail:
            raise RuntimeError("index build failed")
        self.calls.append((list(keys), options.get("name", "")))


class FakeDB:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection())


def _audit_log_fields():
    ledger = VerificationLedger()
    ledger.collection = FakeCollection()
    ledger.badges_col = FakeCollection()
    ledger.db = FakeDB()
    asyncio.run(ledger.ensure_indexes())
    fields = set()
    for keys, _name in ledger.collection.calls:
        for field, _direction in keys:
            fields.add(field)
    return fields, ledger


def test_audit_log_covers_the_four_requested_fields():
    fields, _ledger = _audit_log_fields()
    # The API's user_id / model_id are stored as user_email / model_used.
    assert {"timestamp", "region", "model_used", "user_email"} <= fields


def test_default_audit_sort_is_covered_by_a_compound_index():
    """The hottest read filters on user_email *and* sorts newest-first; a bare
    single-field index would force a sort of every matching document."""
    _fields, ledger = _audit_log_fields()
    declared = [tuple(keys) for keys, _ in ledger.collection.calls]
    assert (("user_email", 1), ("timestamp", -1)) in declared


def test_badge_and_auxiliary_collections_are_indexed():
    _fields, ledger = _audit_log_fields()
    assert ledger.badges_col.calls[0][0] == [("email", 1)]
    assert "response_cache" in ledger.db.collections
    assert "contacts" in ledger.db.collections


def test_auth_lookup_keys_are_indexed():
    db = FakeDB()
    original = auth_db.db
    auth_db.db = db
    try:
        asyncio.run(auth_db.ensure_indexes())
    finally:
        auth_db.db = original

    users = {(field, opts) for keys, opts in db.collections["users"].calls
             for field, _ in keys}
    # user_id lookup plus the two sparse identity/provider keys
    assert ("email", "email_unique") in users
    assert ("google_id", "google_id") in users
    assert ("api_key", "api_key") in users

    assert db.collections["reset_tokens"].calls
    assert db.collections["oauth_codes"].calls
    org_fields = {field for keys, _ in db.collections["organizations"].calls
                  for field, _ in keys}
    assert {"id", "api_keys.key", "members"} <= org_fields


def test_a_failing_index_does_not_propagate():
    """`connect()` must still start the service if an index cannot be built."""
    ledger = VerificationLedger()
    ledger.collection = FakeCollection(fail=True)
    ledger.badges_col = FakeCollection()
    ledger.db = FakeDB()
    asyncio.run(ledger.ensure_indexes())  # must not raise


def test_ensure_indexes_is_a_noop_without_a_database():
    ledger = VerificationLedger()
    asyncio.run(ledger.ensure_indexes())  # must not raise
