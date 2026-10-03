#!/usr/bin/env python3
"""Prove a backup can be restored, not merely that one was written.

A backup that has never been restored is a hypothesis. It records that a
command exited zero on the day it ran, and says nothing about whether the
files inside it are usable, whether they hold the whole database, or whether
the indexes came back. This drill closes that gap end to end:

    1. seed a throwaway database with documents shaped like the real ones,
    2. dump it with the same `mongodump` the runbook uses,
    3. drop the source, so only the dump can possibly be left,
    4. restore into a *second* throwaway database,
    5. compare every document field for field, and every index,
    6. clean up after itself.

Nothing here can touch `ecoquery`. Both databases have fixed names beginning
`ecoquery_drill_`, `--db` overrides whatever database the URI carries, and the
restore remaps namespaces with --nsFrom/--nsTo rather than writing to the
URI's default.

Exit status is the contract:
    0   the round trip held
    1   it did not -- a document, collection or index differs
    2   the drill could not run (missing tools, unreachable server)

Usage:
    python scripts/verify_backup_restore.py
    python scripts/verify_backup_restore.py --allow-remote  # non-local server
    python scripts/verify_backup_restore.py --keep          # leave data behind
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from datetime import datetime, timezone

from pymongo import MongoClient

# Fixed names on purpose: a drill that derived them from a timestamp or a user
# could collide with real data on a second run, and a drill which can destroy
# something it did not create is worse than no drill.
SRC_DB = "ecoquery_drill_src"
DST_DB = "ecoquery_drill_dst"

# Collections the application actually writes, and the shape it writes them in.
# A drill over empty collections would pass while proving nothing about whether
# real fields survive the round trip.
_STAMP = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)
SEED: dict[str, list[dict]] = {
    "users": [
        {"email": "drill-alice@example.com", "tokens_used": 1500, "provider_preference": "green"},
        {"email": "drill-bob@example.com", "tokens_used": 0},
        {"email": "drill-carol@example.com", "tokens_used": 99999},
    ],
    "audit_log": [
        {"user_email": "drill-alice@example.com", "timestamp": _STAMP,
         "model_used": "gemini-flash-latest", "co2_g_saved": 0.42,
         "carbon_basis": "final-provider-region"},
        {"user_email": "drill-bob@example.com", "timestamp": _STAMP,
         "model_used": "qwen3.8-27b:free", "co2_g_saved": 0.31,
         "carbon_basis": "planned-grid"},
    ],
    "contacts": [
        {"name": "Drill Contact", "email": "drill@example.com",
         "created_at": _STAMP, "message": "this document must survive"},
    ],
    "user_badges": [
        {"user_email": "drill-alice@example.com", "badges": ["first-query", "green-week"]},
    ],
    "response_cache": [
        {"query": "what does an llm query cost", "response": {"answer": "x"}, "timestamp": _STAMP},
    ],
}

# Indexes are part of the backup even though nobody thinks of them as data.
# Restoring documents without them degrades the app silently -- queries still
# return, they just start scanning -- so they are asserted like anything else.
INDEXES = [
    ("users", {"email": 1}, {"unique": True}),
    ("audit_log", [("user_email", 1), ("timestamp", 1)], {}),
    ("contacts", [("created_at", -1)], {}),
]


def find_tool(name: str) -> str:
    """Locate a database tool, honouring MONGODB_TOOLS_BIN for a local install."""
    override = os.environ.get("MONGODB_TOOLS_BIN", "").strip()
    if override:
        candidate = os.path.join(override, name + (".exe" if os.name == "nt" else ""))
        if os.path.isfile(candidate):
            return candidate
    found = shutil.which(name)
    if found:
        return found
    # Written to stderr and exited with an explicit 2 rather than raised as a
    # string: SystemExit("message") reports status 1, which would make "the
    # drill could not run" indistinguishable from "the round trip failed".
    print(
        f"exit 2: `{name}` was not found.\n"
        "Install the MongoDB Database Tools (https://www.mongodb.com/try/download/database-tools)\n"
        "and either put them on PATH or set MONGODB_TOOLS_BIN to their directory.",
        file=sys.stderr,
    )
    raise SystemExit(2)


def run(tool: str, *args: str) -> str:
    """Run a tool and fail loudly with its output if it disagrees with us."""
    command = [tool, *args]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(
            f"exit 1: {' '.join(os.path.basename(c) for c in command)} failed "
            f"({result.returncode})\n{result.stdout.strip()}\n{result.stderr.strip()}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return (result.stdout + result.stderr).strip()


def snapshot(db) -> tuple[dict[str, dict], dict[str, dict]]:
    """Every document and every non-default index, keyed so a difference is locatable."""
    docs: dict[str, dict] = {}
    indexes: dict[str, dict] = {}
    for name in sorted(db.list_collection_names()):
        docs[name] = {str(d["_id"]): d for d in db[name].find()}
        indexes[name] = {
            spec["name"]: dict(spec["key"])
            for spec in db[name].list_indexes()
            if spec["name"] != "_id_"
        }
    return docs, indexes


def compare(before_docs, before_indexes, after_docs, after_indexes) -> list[str]:
    """Name exactly what did not survive, rather than reporting 'mismatch'."""
    problems: list[str] = []

    for coll in sorted(set(before_docs) - set(after_docs)):
        problems.append(f"collection `{coll}` is missing from the restore")
    for coll in sorted(set(after_docs) - set(before_docs)):
        problems.append(f"collection `{coll}` appears that was never in the backup")

    for coll in sorted(set(before_docs) & set(after_docs)):
        lost = sorted(set(before_docs[coll]) - set(after_docs[coll]))
        gained = sorted(set(after_docs[coll]) - set(before_docs[coll]))
        if lost:
            problems.append(f"`{coll}` lost {len(lost)} document(s): {', '.join(lost[:5])}")
        if gained:
            problems.append(f"`{coll}` gained {len(gained)} unexpected document(s): {', '.join(gained[:5])}")
        for doc_id in sorted(set(before_docs[coll]) & set(after_docs[coll])):
            if before_docs[coll][doc_id] != after_docs[coll][doc_id]:
                problems.append(f"`{coll}`.{doc_id} came back altered")

        missing_idx = sorted(set(before_indexes.get(coll, {})) - set(after_indexes.get(coll, {})))
        if missing_idx:
            problems.append(f"`{coll}` lost index(es): {', '.join(missing_idx)}")
        for idx in sorted(set(before_indexes.get(coll, {})) & set(after_indexes.get(coll, {}))):
            if before_indexes[coll][idx] != after_indexes[coll][idx]:
                problems.append(f"index `{coll}.{idx}` came back with a different key")

    return problems


def is_loopback(uri: str) -> bool:
    """True when the URI can only reach this machine."""
    try:
        host = urllib.parse.urlparse(uri.replace("mongodb+srv://", "mongodb://")).hostname
    except ValueError:
        return False
    return host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--allow-remote", action="store_true",
                        help="permit a non-loopback server (still only writes ecoquery_drill_*)")
    parser.add_argument("--keep", action="store_true",
                        help="leave the seeded databases in place for inspection")
    parser.add_argument("--uri", default=os.environ.get("MONGODB_URL", "mongodb://127.0.0.1:27017/"),
                        help="server to run against (default: local, or MONGODB_URL)")
    args = parser.parse_args()

    uri = args.uri
    if not is_loopback(uri) and not args.allow_remote:
        print(
            f"refusing: {uri} is not a loopback server.\n"
            "The drill only ever creates and drops ecoquery_drill_src/ecoquery_drill_dst,\n"
            "but running it against a shared cluster is still a decision worth making\n"
            "explicitly. Re-run with --allow-remote if that is what you meant.",
            file=sys.stderr,
        )
        return 2

    mongodump = find_tool("mongodump")
    mongorestore = find_tool("mongorestore")

    workdir = tempfile.mkdtemp(prefix="ecoquery-drill-")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
    except Exception as exc:  # noqa: BLE001 - the reason is the message
        print(f"exit 2: cannot reach {uri}\n{exc}", file=sys.stderr)
        return 2

    src, dst = client[SRC_DB], client[DST_DB]
    problems: list[str] = []
    try:
        # 1. Seed, with indexes, so the drill exercises what a real backup holds.
        client.drop_database(SRC_DB)
        client.drop_database(DST_DB)
        for name, docs in SEED.items():
            src[name].insert_many([dict(d) for d in docs])
        for name, keys, opts in INDEXES:
            src[name].create_index(keys, **opts)
        before_docs, before_indexes = snapshot(src)
        total = sum(len(v) for v in before_docs.values())
        print(f"==> seeded {SRC_DB}: {len(before_docs)} collections, {total} documents, "
              f"{sum(len(v) for v in before_indexes.values())} indexes")

        # 2. Dump exactly as the runbook does.
        run(mongodump, "--uri", uri, "--db", SRC_DB, "--out", workdir, "--gzip")
        print(f"==> mongodump -> {os.path.join(workdir, SRC_DB)}")

        # 3. Destroy the source. From here the only copy is the dump.
        client.drop_database(SRC_DB)
        assert SRC_DB not in client.list_database_names()
        print(f"==> dropped {SRC_DB}; only the dump remains")

        # 4. Restore, remapped into a different database name so the URI's own
        #    default database is never written to.
        #
        #    --dir is the dump *root*, not the database subdirectory inside it.
        #    Pointing it at the subdirectory makes mongorestore decline every
        #    file with "don't know what to do with file" and still exit 0 having
        #    restored nothing -- the exact silent failure this drill exists to
        #    catch, and the reason the comparison below rather than the exit
        #    code is what decides the verdict.
        run(mongorestore, "--uri", uri, "--nsFrom", f"{SRC_DB}.*",
            "--nsTo", f"{DST_DB}.*", "--gzip", "--dir", workdir)
        print(f"==> mongorestore -> {DST_DB}")

        # 5. Compare.
        after_docs, after_indexes = snapshot(dst)
        problems = compare(before_docs, before_indexes, after_docs, after_indexes)
        if problems:
            print("\nFAIL: the backup did not round trip")
            for problem in problems:
                print(f"  - {problem}")
        else:
            print(f"==> compare: {len(after_docs)} collections, "
                  f"{sum(len(v) for v in after_docs.values())} documents, "
                  f"{sum(len(v) for v in after_indexes.values())} indexes identical")
            print("PASS: backup round-tripped document for document, index for index")
    finally:
        if args.keep:
            print(f"kept: {SRC_DB} and {DST_DB} left in place (--keep)")
        else:
            client.drop_database(SRC_DB)
            client.drop_database(DST_DB)
        shutil.rmtree(workdir, ignore_errors=True)
        client.close()

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
