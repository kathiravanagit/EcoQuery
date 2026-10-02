"""
Tenant scoping of the per-user ledger reads.

`get_audit_log` and `get_analytics` both used to treat `user_email=""` as
"no filter", so a caller that dropped the argument silently received every
tenant's records instead of failing. These tests pin the guard and confirm
the query is always scoped.
"""

import asyncio

import pytest

from ledger import VerificationLedger


def _docs():
    return [
        {
            "_id": "id-a",
            "user_email": "alice@example.com",
            "query": "what is grid intensity?",
            "model_used": "gpt-4o-mini",
            "tier": "green",
            "timestamp": "2026-10-01T10:00:00+00:00",
            "co2_saved_vs_baseline": 1.0,
        },
        {
            "_id": "id-b",
            "user_email": "bob@example.com",
            "query": "summarise this file",
            "model_used": "claude-3-5-haiku-latest",
            "tier": "balanced",
            "timestamp": "2026-10-01T11:00:00+00:00",
            "co2_saved_vs_baseline": 2.0,
        },
    ]


def _matches(doc: dict, query: dict) -> bool:
    """Scalar equality plus ISO `$gte` -- the only filters these tests use."""
    for key, expected in query.items():
        if isinstance(expected, dict) and "$gte" in expected:
            if doc.get(key, "") < expected["$gte"]:
                return False
        elif isinstance(expected, dict):
            raise NotImplementedError(f"fixture does not implement filter {key!r}")
        elif doc.get(key) != expected:
            return False
    return True


class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, *args, **kwargs):
        return self

    def skip(self, n):
        self._docs = self._docs[n:]
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    async def to_list(self, length=None):
        return list(self._docs)


class _FakeAggCursor:
    async def to_list(self, length=None):
        return []


class _FakeCollection:
    def __init__(self, docs):
        self.docs = docs
        self.last_match = None

    def find(self, query):
        return _FakeCursor([d for d in self.docs if _matches(d, query)])

    async def count_documents(self, query):
        return len([d for d in self.docs if _matches(d, query)])

    def aggregate(self, pipeline):
        match = pipeline[0].get("$match", {}) if pipeline else {}
        self.last_match = match
        return _FakeAggCursor()


def _ledger_with(docs):
    instance = VerificationLedger()
    instance.available = True
    instance.collection = _FakeCollection(docs)
    return instance


class TestEmptyTenantIsRejected:
    def test_get_audit_log_requires_a_user_email(self):
        with pytest.raises(ValueError, match="user_email"):
            asyncio.run(_ledger_with(_docs()).get_audit_log(user_email=""))

    def test_blank_user_email_is_also_rejected(self):
        with pytest.raises(ValueError, match="user_email"):
            asyncio.run(_ledger_with(_docs()).get_audit_log(user_email="   "))

    def test_get_analytics_requires_a_user_email(self):
        with pytest.raises(ValueError, match="user_email"):
            asyncio.run(_ledger_with(_docs()).get_analytics(user_email=""))

    def test_guard_fires_even_when_the_database_is_unavailable(self):
        # The old code returned `[], 0` here before ever looking at the query,
        # so the empty-email path failed open rather than closed.
        offline = VerificationLedger()
        assert offline.available is False
        with pytest.raises(ValueError, match="user_email"):
            asyncio.run(offline.get_audit_log(user_email=""))


class TestRecordsAreTenantScoped:
    def test_only_the_requested_tenants_records_come_back(self):
        records, total = asyncio.run(
            _ledger_with(_docs()).get_audit_log(user_email="alice@example.com")
        )
        assert total == 1
        assert {r["user_email"] for r in records} == {"alice@example.com"}

    def test_unknown_tenant_returns_empty_rather_than_everything(self):
        records, total = asyncio.run(
            _ledger_with(_docs()).get_audit_log(user_email="nobody@example.com")
        )
        assert records == []
        assert total == 0

    def test_analytics_aggregates_on_the_tenant(self):
        collection = _FakeCollection(_docs())
        instance = VerificationLedger()
        instance.available = True
        instance.collection = collection

        asyncio.run(instance.get_analytics(user_email="alice@example.com"))

        assert collection.last_match.get("user_email") == "alice@example.com"

    def test_anonymous_writes_remain_allowed(self):
        # Only reads are guarded. Anonymous chats record with an empty owner on
        # purpose (chat.py passes user_email straight through), and
        # verify_user_chain("") reads that same bucket back.
        instance = VerificationLedger()
        instance.available = False
        instance.collection = None

        asyncio.run(instance.record_query({"query": "q"}, user_email=""))

        assert "" in instance._last_hash_by_user
