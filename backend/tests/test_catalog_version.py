"""
Catalog versioning and validation.

The point of `catalog_version` is that a change to CARBON_MODELS changes
every routing number the project quotes, so a benchmark artifact that does not
pin it cannot distinguish a regression from a catalog edit. These tests prove
the digest is stable under reformatting and sensitive to real edits, that the
validator actually catches each defect class, and that the CLI's exit codes
are the ones CI will act on.
"""

import copy
import json
import os
import subprocess
import sys

import pytest

from catalog_version import (
    CARBON_MODELS,
    CAPABILITIES,
    REQUIRED_FIELDS,
    TIERS,
    catalog_version,
    validate_catalog,
)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── The shipped catalog must be sound ────────────────────────────────────────

def test_the_shipped_catalog_validates_clean():
    assert validate_catalog() == []


def test_version_reports_the_real_entry_count_and_a_sha256():
    version = catalog_version()
    assert version["entry_count"] == len(CARBON_MODELS)
    assert version["digest"].startswith("sha256:")
    assert len(version["digest"]) == len("sha256:") + 64


# ── Digest behaviour ─────────────────────────────────────────────────────────

def test_digest_is_stable_across_calls():
    assert catalog_version()["digest"] == catalog_version()["digest"]


def test_reformatting_does_not_move_the_digest():
    """Indentation and key order are not content -- otherwise a pure style
    edit would look like a catalog change to every downstream artifact."""
    reformatted = [dict(reversed(list(m.items()))) for m in CARBON_MODELS]
    assert catalog_version(reformatted) == catalog_version(CARBON_MODELS)


def test_editing_a_model_moves_the_digest():
    edited = copy.deepcopy(CARBON_MODELS)
    edited[0]["carbon_score"] = edited[0]["carbon_score"] + 1
    assert catalog_version(edited)["digest"] != catalog_version()["digest"]


def test_adding_a_model_changes_both_digest_and_count():
    added = copy.deepcopy(CARBON_MODELS) + [{
        "id": "example:free", "provider": "Example", "tier": "green",
        "carbon_score": 4, "capability": "low",
        "openrouter_id": "example/example:free",
        "description": "probe", "supports_images": False,
    }]
    assert catalog_version(added)["entry_count"] == len(CARBON_MODELS) + 1
    assert catalog_version(added)["digest"] != catalog_version()["digest"]


def test_key_order_and_whitespace_are_not_content():
    """The digest is over canonical JSON, not over the source file."""
    import hashlib

    expected = hashlib.sha256(
        json.dumps(CARBON_MODELS, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()
    assert catalog_version()["digest"] == f"sha256:{expected}"


# ── Validator catches each defect class ──────────────────────────────────────

def test_a_non_dict_entry_is_reported_not_raised():
    broken = [CARBON_MODELS[0], "not-a-model"]
    assert any("expected a dict" in p for p in validate_catalog(broken, check_tables=False))


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_every_required_field_is_enforced(field):
    broken = copy.deepcopy(CARBON_MODELS)
    del broken[0][field]
    assert any(field in p for p in validate_catalog(broken, check_tables=False))


def test_duplicate_ids_are_rejected():
    broken = copy.deepcopy(CARBON_MODELS)
    broken[1]["id"] = broken[0]["id"]
    broken[1]["openrouter_id"] = broken[0]["openrouter_id"]
    assert any("duplicate" in p for p in validate_catalog(broken, check_tables=False))


def test_a_paid_model_is_rejected():
    """models.py documents free tier; a paid entry silently bills users."""
    broken = copy.deepcopy(CARBON_MODELS)
    broken[0]["openrouter_id"] = "nvidia/nemotron-3-ultra-550b-a55b"
    problems = validate_catalog(broken, check_tables=False)
    assert any("not a ':free' model" in p for p in problems)
    # and the id/openrouter_id spelling contract with verifier._threshold_key
    assert any("last segment" in p for p in problems)


@pytest.mark.parametrize("field,value", [
    ("carbon_score", 0),
    ("carbon_score", -3),
    ("carbon_score", True),
    ("carbon_score", "high"),
    ("capability", "extreme"),
    ("tier", "emerald"),
    ("supports_images", "yes"),
])
def test_out_of_domain_values_are_rejected(field, value):
    broken = copy.deepcopy(CARBON_MODELS)
    broken[0][field] = value
    problems = validate_catalog(broken, check_tables=False)
    assert problems, f"{field}={value!r} was accepted"


def test_domain_constants_are_not_wider_than_the_router_expects():
    assert set(CAPABILITIES) == {"low", "medium", "high"}
    assert set(TIERS) == {"green", "balanced", "performance"}


def test_an_empty_catalog_is_rejected():
    assert validate_catalog([], check_tables=False) != []


# ── Cross-module references ──────────────────────────────────────────────────

def test_removing_one_model_breaks_every_reference_to_it():
    """One deletion should surface as one problem per consumer, not one."""
    trimmed = [m for m in CARBON_MODELS if m["id"] != "qwen3.8-27b:free"]
    problems = validate_catalog(trimmed)
    assert any("VISION_MODEL" in p for p in problems), "vision model gone unreported"
    assert any("MODEL_LATENCY" in p for p in problems)
    assert any("MODEL_COST_MAP" in p for p in problems)
    assert any("FALLBACK_MODELS" in p for p in problems)


def test_cross_module_checks_can_be_skipped():
    trimmed = [m for m in CARBON_MODELS if m["id"] != "qwen3.8-27b:free"]
    assert validate_catalog(trimmed, check_tables=False) == []


def test_shape_only_checks_still_run_without_the_tables():
    broken = copy.deepcopy(CARBON_MODELS)
    broken[0]["capability"] = "extreme"
    assert validate_catalog(broken, check_tables=False) != []


# ── CLI ──────────────────────────────────────────────────────────────────────

def _run_cli(*args):
    return subprocess.run(
        [sys.executable, os.path.join(BACKEND_DIR, "validate_models.py"), *args],
        capture_output=True, text=True, cwd=BACKEND_DIR, timeout=120,
    )


def test_cli_passes_on_the_shipped_catalog():
    result = _run_cli("--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["problems"] == []
    assert payload["version"]["entry_count"] == len(CARBON_MODELS)


def test_cli_fails_when_the_catalog_is_invalid(monkeypatch, capsys):
    """CI acts on the exit code, so it has to be 1 -- not a printed warning."""
    import validate_models

    monkeypatch.setattr(validate_models, "validate_catalog", lambda *a, **k: ["boom"])
    assert validate_models.main([]) == 1
    assert "boom" in capsys.readouterr().err


def test_cli_json_mode_reports_failure_and_returns_one(monkeypatch, capsys):
    import validate_models

    monkeypatch.setattr(validate_models, "validate_catalog", lambda *a, **k: ["boom"])
    assert validate_models.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["problems"] == ["boom"]


def test_cli_is_quiet_on_success(monkeypatch, capsys):
    import validate_models

    assert validate_models.main(["--quiet"]) == 0
    assert capsys.readouterr().out == ""


# ── The artifact the digest exists to protect ────────────────────────────────

def test_the_checked_in_benchmark_artifact_pins_its_catalog():
    """A digest nothing is checked against is not versioning.

    `benchmark_results.json` quotes routing numbers that `CARBON_MODELS`
    produced, so the two have to agree. Editing models.py without re-running
    the benchmark leaves an artifact claiming a catalog it was never computed
    against -- exactly the confusion the digest exists to prevent.
    """
    path = os.path.join(BACKEND_DIR, "benchmark_results.json")
    with open(path, encoding="utf-8") as handle:
        artifact = json.load(handle)

    provenance = artifact.get("provenance")
    assert provenance, "benchmark_results.json has no provenance block"
    assert provenance["catalog_version"] == catalog_version(), (
        "benchmark_results.json was computed against a different catalog than "
        "the one now in models.py. Re-run `python benchmark.py` so the numbers "
        "and the catalog they describe agree."
    )
    assert provenance["prompt_set_hash"].startswith("sha256:")
    assert provenance["prompt_count"] > 0
    assert provenance["git_commit"]
    assert provenance["routing_modes"], "the strategies behind the numbers are unnamed"
    assert provenance["provider_model_ids"], "the models benchmarked are unnamed"
    assert provenance["environment"]["python"]
