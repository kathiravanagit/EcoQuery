"""
Endpoint-level tenant isolation.

`test_ledger_scoping.py` proves the ledger refuses an unscoped read. This file
proves the HTTP layer actually passes the caller's address through: user A's
requests must never surface user B's records, whether a router forgot the
argument, dropped it, or passed something else.

Records are deliberately uneven -- Alice has two on different days, Bob one --
so "same answer for everyone" is detectable, not just "someone's data leaked".
"""

import json

import pytest
from fastapi.testclient import TestClient

from auth import get_current_user
from ledger import ledger
from main import app

ALICE = "alice@example.com"
BOB = "bob@example.com"


def _record(user, marker, day):
    return {
        "_id": f"{marker}-id",
        "user_email": user,
        "query": f"[redacted-{marker}]",
        "tier": "simple",
        "model_used": "green-model",
        "model_tier": "green",
        "region": "eu-north-1",
        "co2_estimated": 0.05,
        "co2_saved_vs_baseline": 0.45,
        "api_cost": 0.0001,
        "latency_seconds": 0.5,
        "verification_status": "verified",
        "timestamp": f"2026-09-{day}T10:00:00+00:00",
    }


DOCS = [
    _record(ALICE, "alice-a", "20"),
    _record(ALICE, "alice-b", "21"),
    _record(BOB, "bob-a", "22"),
]


def _matches(doc, query):
    """Scalar equality plus ISO `$gte` -- the filters these endpoints build."""
    for key, expected in query.items():
        if isinstance(expected, dict) and "$gte" in expected:
            if doc.get(key, "") < expected["$gte"]:
                return False
        elif isinstance(expected, dict):
            raise NotImplementedError(f"fixture does not implement filter {key!r}")
        elif doc.get(key) != expected:
            return False
    return True


class _Cursor:
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


class _AggCursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, length=None):
        return list(self._rows)


class _Collection:
    """Just enough Mongo to run the user-scoped reads under test."""

    def __init__(self, docs):
        self.docs = docs

    def find(self, query):
        return _Cursor([d for d in self.docs if _matches(d, query)])

    async def count_documents(self, query):
        return len([d for d in self.docs if _matches(d, query)])

    def aggregate(self, pipeline):
        match = pipeline[0].get("$match", {}) if pipeline else {}
        rows = [d for d in self.docs if _matches(d, match)]
        group = next((p["$group"] for p in pipeline if "$group" in p), None)
        if group is None:
            return _AggCursor([])
        key_expr = group.get("_id")
        if key_expr is None:
            buckets = {"all": rows}
        else:
            buckets = {}
            for row in rows:
                if isinstance(key_expr, dict) and "$substr" in key_expr:
                    key = row["timestamp"][:10]
                elif isinstance(key_expr, str) and key_expr.startswith("$"):
                    key = row.get(key_expr[1:])
                else:
                    raise NotImplementedError(f"fixture does not implement group {key_expr!r}")
                buckets.setdefault(key, []).append(row)
        out = [
            {
                "_id": key,
                "count": len(members),
                "co2_saved": sum(m.get("co2_saved_vs_baseline", 0) for m in members),
                "co2_emitted": sum(m.get("co2_estimated", 0) for m in members),
                "avg_latency": sum(m.get("latency_seconds", 0) for m in members) / len(members),
            }
            for key, members in buckets.items()
        ]
        return _AggCursor(out)


@pytest.fixture
def as_user():
    """A client whose authenticated identity can be swapped per assertion."""
    current = {"email": ALICE, "display_name": "Alice"}
    app.dependency_overrides[get_current_user] = lambda: dict(current)
    prev_available, prev_collection = ledger.available, ledger.collection

    with TestClient(app) as client:
        # The lifespan runs on entry and tries to connect; install after it.
        ledger.available = True
        ledger.collection = _Collection(DOCS)

        def swap(email):
            current["email"] = email
            current["display_name"] = email.split("@")[0].title()
            return client

        yield swap

    ledger.available = prev_available
    ledger.collection = prev_collection
    app.dependency_overrides.clear()


def test_audit_returns_only_the_callers_records(as_user):
    alice = as_user(ALICE).get("/api/audit").json()
    assert alice["total"] == 2
    assert {r["user_email"] for r in alice["records"]} == {ALICE}
    assert BOB not in json.dumps(alice)

    bob = as_user(BOB).get("/api/audit").json()
    assert bob["total"] == 1
    assert {r["user_email"] for r in bob["records"]} == {BOB}
    assert ALICE not in json.dumps(bob)


def test_user_stats_counts_only_the_callers_queries(as_user):
    assert as_user(ALICE).get("/api/user/stats").json()["total_queries"] == 2
    assert as_user(BOB).get("/api/user/stats").json()["total_queries"] == 1


def test_sustainability_report_names_and_counts_only_the_caller(as_user):
    report = as_user(ALICE).get("/api/user/sustainability-report").json()
    assert report["email"] == ALICE
    assert report["summary"]["total_queries"] == 2
    assert BOB not in json.dumps(report)

    report = as_user(BOB).get("/api/user/sustainability-report").json()
    assert report["email"] == BOB
    assert report["summary"]["total_queries"] == 1
    assert ALICE not in json.dumps(report)


def test_analytics_covers_only_the_callers_days(as_user):
    # Alice has two distinct days, Bob one -- an unscoped query returns three.
    assert len(as_user(ALICE).get("/api/analytics").json()["queries_by_day"]) == 2
    assert len(as_user(BOB).get("/api/analytics").json()["queries_by_day"]) == 1


def test_chain_verification_only_checks_the_callers_chain(as_user):
    assert as_user(ALICE).get("/api/audit/verify").json()["checked"] == 2
    assert as_user(BOB).get("/api/audit/verify").json()["checked"] == 1


def test_public_stats_stay_aggregate(as_user):
    """/api/stats is deliberately unauthenticated, so it must remain aggregate."""
    stats = as_user(ALICE).get("/api/stats").json()
    assert stats["total_queries"] == 3  # every tenant, by design
    assert ALICE not in json.dumps(stats)
    assert BOB not in json.dumps(stats)
