"""
Catalog versioning and validation.

`docs/REPRODUCIBILITY.md` requires every benchmark artifact to pin a
`catalog_version`. That requirement is not decorative: `CARBON_MODELS` drives
model selection, savings, the 90.9% estimated reduction figure and the 80.85%
classifier hold-out. A silent edit to it changes every number the project
quotes, and without a digest a re-run that disagrees with the checked-in
results cannot tell a real regression from a catalog that quietly moved.

`validate_catalog` states the same invariants `tests/test_model_catalog.py`
asserts, but as data rather than asserts, so they can be run outside pytest --
from CI, a pre-commit hook, or `npm run validate:models`. The test file stays
the specification; this is its runnable form, and a test pins the two together
so they cannot drift.
"""

import hashlib
import json

from models import CARBON_MODELS, FALLBACK_MODELS, VISION_MODEL

# Every field `select_model`, `chat.py` and `benchmark.py` read without a
# `.get()`, so a missing one is a KeyError at request time rather than a
# degraded value.
REQUIRED_FIELDS = (
    "id", "provider", "tier", "carbon_score", "capability",
    "openrouter_id", "description", "supports_images",
)

# `router.select_model` filters on these strings.
CAPABILITIES = ("low", "medium", "high")

# `model_tier` is written to the ledger and the dashboard buckets it into
# green / balanced / performance. A value outside that set is accepted by
# every read and then lands in no bucket at all.
TIERS = ("green", "balanced", "performance")


def _canonical(catalog: list) -> str:
    """Sort keys, drop whitespace, keep non-ASCII literal.

    Reformatting the file -- indentation, key order, a trailing newline -- must
    not move the digest, or the version would change on a pure style edit.
    Mirrors the canonicalisation `ledger._compute_ledger_hash` uses.
    """
    return json.dumps(
        catalog, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str,
    )


def catalog_version(catalog: list | None = None) -> dict:
    """`{"digest": "sha256:...", "entry_count": n}` for a provenance block."""
    catalog = CARBON_MODELS if catalog is None else catalog
    digest = hashlib.sha256(_canonical(catalog).encode("utf-8")).hexdigest()
    return {"digest": f"sha256:{digest}", "entry_count": len(catalog)}


def validate_catalog(catalog: list | None = None, *, check_tables: bool = True) -> list[str]:
    """Return every invariant violation found; `[]` means the catalog is sound.

    `check_tables` covers the cross-module references (latency table, cost map,
    fallback chain, vision and health-probe models). Those need imports from
    `router`, `providers` and `routers.chat`, so they can be skipped when only
    the shape of `models.py` itself matters.
    """
    catalog = CARBON_MODELS if catalog is None else catalog
    if not isinstance(catalog, list) or not catalog:
        return ["catalog must be a non-empty list of model entries"]

    problems: list[str] = []
    seen_ids: set = set()
    seen_openrouter_ids: set = set()

    for index, model in enumerate(catalog):
        label = f"entry {index}"
        if not isinstance(model, dict):
            problems.append(f"{label}: expected a dict, got {type(model).__name__}")
            continue
        label = str(model.get("id") or label)

        missing = [field for field in REQUIRED_FIELDS if field not in model]
        if missing:
            problems.append(f"{label}: missing required field(s) {', '.join(missing)}")

        model_id = model.get("id")
        if isinstance(model_id, str):
            if model_id in seen_ids:
                problems.append(f"{label}: duplicate id")
            seen_ids.add(model_id)

        openrouter_id = model.get("openrouter_id")
        if isinstance(openrouter_id, str):
            if openrouter_id in seen_openrouter_ids:
                problems.append(f"{label}: duplicate openrouter_id {openrouter_id!r}")
            seen_openrouter_ids.add(openrouter_id)

            if not openrouter_id.endswith(":free"):
                problems.append(
                    f"{label}: {openrouter_id!r} is not a ':free' model, but "
                    "models.py documents the catalog as free tier only"
                )
            # verifier._threshold_key strips the vendor prefix before looking a
            # threshold up, so a mismatched spelling silently finds nothing.
            if isinstance(model_id, str) and model_id != openrouter_id.split("/")[-1]:
                problems.append(
                    f"{label}: id {model_id!r} is not the last segment of "
                    f"openrouter_id {openrouter_id!r}; verification thresholds "
                    "would never be found for it"
                )

        score = model.get("carbon_score")
        if isinstance(score, bool) or not isinstance(score, int) or score <= 0:
            problems.append(f"{label}: carbon_score must be a positive int, got {score!r}")

        if "capability" in model and model["capability"] not in CAPABILITIES:
            problems.append(
                f"{label}: capability {model['capability']!r} is not one of {CAPABILITIES}"
            )

        if "tier" in model and model["tier"] not in TIERS:
            problems.append(f"{label}: tier {model['tier']!r} is not one of {TIERS}")

        if "supports_images" in model and not isinstance(model["supports_images"], bool):
            problems.append(
                f"{label}: supports_images must be a bool, got "
                f"{type(model['supports_images']).__name__}"
            )

    if check_tables:
        problems.extend(_cross_reference_problems(catalog, seen_ids, seen_openrouter_ids))

    return problems


def _cross_reference_problems(catalog: list, ids: set, openrouter_ids: set) -> list[str]:
    """Checks that only fail when a constant outside models.py goes stale."""
    from providers import HEALTH_PROBE_MODEL
    from router import MODEL_LATENCY
    from routers.chat import MODEL_COST_MAP

    problems: list[str] = []

    # chat.py looks the vision model up inside CARBON_MODELS to decide whether
    # image uploads are possible at all; an id that is not there disables vision.
    vision = next((m for m in catalog if isinstance(m, dict) and m.get("id") == VISION_MODEL), None)
    if vision is None:
        problems.append(
            f"VISION_MODEL {VISION_MODEL!r} is not a catalog id; chat.py would "
            "silently treat every image upload as unsupported"
        )
    elif not vision.get("supports_images"):
        problems.append(f"VISION_MODEL {VISION_MODEL!r} does not have supports_images=True")

    unknown_fallbacks = sorted(set(FALLBACK_MODELS) - openrouter_ids)
    if unknown_fallbacks:
        problems.append(
            f"FALLBACK_MODELS names ids absent from the catalog: {unknown_fallbacks}"
        )
    if len(FALLBACK_MODELS) != len(set(FALLBACK_MODELS)):
        problems.append("FALLBACK_MODELS contains duplicates")

    if HEALTH_PROBE_MODEL not in openrouter_ids:
        problems.append(
            f"HEALTH_PROBE_MODEL {HEALTH_PROBE_MODEL!r} is not a catalog model; "
            "the health probe would bill or fail for the wrong reason"
        )

    # A missing key here silently costs a free model the default rate and
    # reports real spend for it; a missing latency key reads as a default too.
    missing_latency = sorted(ids - set(MODEL_LATENCY))
    stale_latency = sorted(set(MODEL_LATENCY) - ids)
    if missing_latency:
        problems.append(f"MODEL_LATENCY has no entry for: {missing_latency}")
    if stale_latency:
        problems.append(f"MODEL_LATENCY lists ids not in the catalog: {stale_latency}")

    missing_cost = sorted(ids - set(MODEL_COST_MAP))
    stale_cost = sorted(set(MODEL_COST_MAP) - ids)
    if missing_cost:
        problems.append(f"MODEL_COST_MAP has no entry for: {missing_cost}")
    if stale_cost:
        problems.append(f"MODEL_COST_MAP lists ids not in the catalog: {stale_cost}")

    return problems
