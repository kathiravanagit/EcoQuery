# EcoQuery Evaluation Snapshot

This snapshot is generated from the checked-in `backend/benchmark_results.json` artifact and represents the deterministic routing simulator, not a wattmeter measurement or a live-provider experiment.

## 30-prompt routing simulation

| Strategy | Queries | Estimated CO2e (g) | Average latency (s) | Estimated carbon reduction vs fixed baseline |
| --- | ---: | ---: | ---: | ---: |
| Always largest | 30 | 0.0922 | 2.500 | 77.6% |
| Always smallest | 30 | 0.0114 | 0.900 | 97.2% |
| EcoQuery carbon-aware | 30 | 0.0374 | 1.533 | 90.9% |

The simulation shows the policy tradeoff: EcoQuery uses a larger model for higher-capability tiers, so it is not expected to beat an always-smallest strategy on estimated CO2e alone. Its purpose is to satisfy the classifier's capability requirement while choosing the lowest-carbon suitable candidate.

Relative to always-largest, the router cuts estimated CO2e by 59% (0.0922 g → 0.0374 g) while accepting 40% more latency (2.500 s → 1.533 s). Its average selected carbon score is 2.7, against 8.0 for the always-largest strategy.

## EcoQuery model choices (current catalog)

| Query tier | Selected model |
| --- | --- |
| Simple | `lfm-2.5-2.6b:free` |
| Medium | `north-mini-code:free` |
| Complex | `nemotron-3-super-120b-a12b:free` |

A `medium` query with classifier confidence below 0.75 is escalated to the
`complex` selection, since the router only trusts its own tier guess when the
classifier is confident.

This snapshot was regenerated against the current catalog and the normalized
scoring in `backend/router.py`, so the model ids above are live OpenRouter
ids rather than retired ones. Two things it still does not establish: it
contains no measured energy (see the limitations below), and the
`classifier_accuracy` block in `backend/benchmark_results.json` is unchanged
by a re-run — it stays a 30-prompt figure because accuracy depends on the
classifier itself, not on routing.

Re-run `python benchmark.py` after any change to the router or the catalog.

## Reproducible run

From the repository root:

```bash
cd backend
python benchmark.py
```

The benchmark uses 10 fixed prompts per tier, a fixed regional intensity input, model latency constants, and the estimator in `backend/router.py`. It does not call external providers, measure actual hardware energy, or verify answer quality. For a research-grade production experiment, run matched prompts repeatedly against each strategy and report success rate, latency distribution, model/version, carbon-data source, failures, and uncertainty intervals.

The live harness is `python scripts/live_benchmark.py --runs 3 --output benchmark-live.json`. It uses 100 prompts, actual provider calls, five strategies, optional judge-model quality scoring, and reports mean, median, p95, standard deviation, confidence intervals, failure rate, and carbon-estimate fields. It must be run in an environment with deliberately configured test credentials; no live results are claimed by this checked-in snapshot.
