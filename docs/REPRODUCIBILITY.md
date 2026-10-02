# EcoQuery Reproducibility

A benchmark number without provenance is a claim nobody can check. This document specifies the provenance every EcoQuery benchmark result must carry, the artifact shape that records it, and the gap between that specification and what the repository writes today.

## Required provenance fields

Every benchmark artifact — the output of `backend/benchmark.py`, of `scripts/live_benchmark.py`, and of any future ablation run described in [RESEARCH.md](RESEARCH.md) — must record all of the following.

| Field | What it records | How to produce it |
| --- | --- | --- |
| `git_commit` | Full SHA of the checkout that produced the run, plus `git_dirty` and a hash of the uncommitted diff when dirty | `git rev-parse HEAD`; report `git_dirty: true` rather than silently running on a modified tree |
| `prompt_set_hash` | SHA-256 of the canonical prompt set: a JSON array of `{"id", "prompt", "tier"}` objects in file order, UTF-8, `ensure_ascii=False`, separators `(",", ":")` | Hash the serialization, not the file bytes, so line endings and formatting cannot change the digest |
| `provider_model_ids` | Requested provider/model and, per attempt, the provider/model that actually answered | Taken from the response lineage (`requested`, `final`, `fallback`) already emitted by the API |
| `catalog_version` | Digest and entry count of the model catalog the router scored against (`CARBON_MODELS` in `backend/models.py`) | SHA-256 over the same canonical JSON treatment, plus `entry_count`; a catalog edit changes every routing number, so it must be pinned |
| `carbon_data_timestamp` | UTC timestamp at which the grid-intensity values were fetched, plus `carbon_data_source` (`electricity-maps-api`, `iea-static-baselines`, `mock-fallback`) and the regions used | Read from the carbon layer at run start; a live value and an annual baseline carry different uncertainty and must not be conflated |
| `routing_mode_settings` | Mode name (`green`, `balanced`, `quality`, `fast`, `low-cost`), the weight vector `(w1..w5)`, capability-floor configuration, fallback enabled/disabled, and the baseline definition used for any savings percentage | Dump the resolved configuration, not just the mode name — defaults move |
| `repetitions` | Runs per prompt per condition, plus `deterministic: true/false` | The simulator is deterministic and reports `repetitions: 1, deterministic: true`; live runs report the actual `--runs` count |
| `environment` | Python version, OS/arch, dependency-set digest (`requirements.txt`), harness script and its version, `mode: "simulated" \| "live"`, and which optional services were present (Electricity Maps key, Redis) | Record presence booleans only; never record secret values |
| `failure_count` | Attempts that errored or returned empty content, alongside `attempted_count` and `succeeded_count` | Failures must be counted, not dropped: a strategy that fails half its requests must not look cleaner than one that completes |
| `quality_rubric_version` | Identifier and digest of the rubric used for any quality score, plus judge model id and judge prompt version when a judge model was used | Reference the rubric section in [RESEARCH.md](RESEARCH.md); a rubric edit invalidates comparison with earlier scores |

### Also required when quality is reported

- Rater count, pre-adjudication agreement, and adjudication method (see [RESEARCH.md](RESEARCH.md) § Human evaluation protocol).
- Sample size per condition, expressed as responses and as individual ratings.

## Artifact schema

The provenance block is a top-level `provenance` object in the written artifact:

```json
{
  "provenance": {
    "schema_version": "1.0",
    "generated_at": "2026-01-01T00:00:00Z",
    "git_commit": "0000000000000000000000000000000000000000",
    "git_dirty": false,
    "diff_hash": null,
    "prompt_set_hash": "sha256:…",
    "prompt_set_size": 30,
    "provider_model_ids": {
      "requested": [{"provider": "openrouter", "model": "nemotron-3-super-120b-a12b:free"}],
      "final": [{"provider": "openrouter", "model": "nemotron-3-super-120b-a12b:free"}]
    },
    "catalog_version": {"digest": "sha256:…", "entry_count": 7},
    "carbon_data_timestamp": "2026-01-01T00:00:00Z",
    "carbon_data_source": "iea-static-baselines",
    "carbon_regions_used": ["NO1", "DE", "IN"],
    "routing_mode_settings": {
      "mode": "balanced",
      "weights": [2, 2, 1, 1, 1],
      "capability_floor": "enabled",
      "provider_fallback": "enabled",
      "baseline_g_per_kwh": 475
    },
    "repetitions": 3,
    "deterministic": false,
    "environment": {
      "python": "3.11.x",
      "platform": "…",
      "requirements_digest": "sha256:…",
      "harness": "scripts/live_benchmark.py",
      "harness_version": "…",
      "mode": "live",
      "services": {"electricity_maps": true, "redis": false}
    },
    "attempted_count": 300,
    "succeeded_count": 297,
    "failure_count": 3,
    "quality_rubric_version": "docs/RESEARCH.md#scoring-dimensions-13-rubric@sha256:…",
    "judge_model_id": null
  },
  "results": {
    "…condition summaries…"
  }
}
```

Field-level schema, in the terms the audit checks:

```text
provenance.git_commit            string   required   full 40-char SHA
provenance.prompt_set_hash       string   required   "sha256:" + hex digest of canonical prompt JSON
provenance.provider_model_ids    object   required   requested and final provider/model per attempt
provenance.catalog_version       object   required   digest + entry_count of CARBON_MODELS
provenance.carbon_data_timestamp string   required   UTC ISO-8601 fetch time of grid-intensity data
provenance.carbon_data_source    enum     required   electricity-maps-api | iea-static-baselines | mock-fallback
provenance.routing_mode_settings object   required   mode, weights, capability floor, fallback, baseline
provenance.repetitions           integer  required   runs per prompt per condition (>= 1)
provenance.environment           object   required   interpreter, platform, dependency digest, harness, mode
provenance.failure_count         integer  required   errored/empty attempts (0 must be written explicitly)
provenance.quality_rubric_version string  required   rubric id + digest; judge model id when a judge scored
```

A result published without a complete `provenance` block is not a benchmark result; it is an illustration.

## Current state of the artifact

**`backend/benchmark_results.json` now carries a `provenance` block.** Its top-level keys today:

| Top-level key | Contents |
| --- | --- |
| `classifier_accuracy` | Overall and per-tier accuracy, method, prompt count |
| `routing_comparison` | Per-strategy totals: queries, estimated CO₂e (g), savings %, average latency, carbon score, per-tier breakdown |
| `ecoquery_model_selection` | The model id chosen per tier |
| `provenance` | `git_commit`, `catalog_version` (digest + entry count), `prompt_count`, `prompt_set_hash`, `provider_model_ids`, `routing_modes`, `environment`, `generated_at` |

Still missing from the artifact: `carbon_data_timestamp`, `carbon_data_source`, `repetitions`, `failure_count`, `quality_rubric_version`. `scripts/live_benchmark.py` writes `prompt_count`, `runs`, `summary` and `records` — it reports a `failure_rate` inside `summary` but no commit, catalog, or carbon-data provenance.

The missing fields above are missing because `benchmark.py` cannot state them without inventing a value; they are recorded here rather than filled in with a plausible one.

Consequences, stated plainly:

- **90.9%** estimated carbon reduction vs the fixed baseline, and the classifier hold-out accuracy of **80.85%**, are now attributable to a specific commit, catalog and prompt set from the artifact alone.
- `catalog_version` is pinned in `provenance` and re-checked by `tests/test_catalog_version.py`: editing `models.py` without re-running the benchmark fails the test with instructions to re-run it. The digest itself is printed and enforced by `npm run validate:models` and the `Validate model catalog` CI step.
- Without `carbon_data_timestamp` and `carbon_data_source`, a live run mixing an Electricity Maps value with an IEA annual baseline is indistinguishable from a run using one source throughout.
- Without `failure_count`, a strategy that errored is scored only on its survivors.
- Without `repetitions`, a single pass can be mistaken for a repeated experiment.

## Minimum bar before publishing a number

1. Run on a clean checkout and record `git_commit` (or record `git_dirty: true` plus the diff hash).
2. Write the full `provenance` block alongside the results.
3. Report repetitions and the deterministic/simulated flag; never present a deterministic simulation as a repeated experiment.
4. Report failures as counts, not as excluded rows.
5. Re-run `python benchmark.py` after any router or catalog change and state which `catalog_version` the quoted numbers came from.
6. Quote estimated CO₂e as **estimated**; do not describe simulated or estimated values as measurements (see [METHODOLOGY.md](METHODOLOGY.md) § Evaluation protocol).

## Related documents

| Document | What it holds |
| --- | --- |
| [RESEARCH.md](RESEARCH.md) | Hypothesis, human evaluation rubric, ablation plan |
| [EVALUATION.md](EVALUATION.md) | The current checked-in snapshot and how to regenerate it |
| [METHODOLOGY.md](METHODOLOGY.md) | Estimation formula, routing policy, provenance and verification limits |
