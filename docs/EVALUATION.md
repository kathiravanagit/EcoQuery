# EcoQuery Evaluation Snapshot

This snapshot is generated from the checked-in `backend/benchmark_results.json` artifact and represents the deterministic routing simulator, not a wattmeter measurement or a live-provider experiment.

## 30-prompt routing simulation

| Strategy | Queries | Estimated CO2e (g) | Average latency (s) | Estimated carbon reduction vs fixed baseline |
| --- | ---: | ---: | ---: | ---: |
| Always largest | 30 | 0.0922 | 2.000 | 77.6% |
| Always smallest | 30 | 0.0114 | 1.000 | 97.2% |
| EcoQuery carbon-aware | 30 | 0.0409 | 1.333 | 90.0% |

The simulation shows the policy tradeoff: EcoQuery uses a larger model for higher-capability tiers, so it is not expected to beat an always-smallest strategy on estimated CO2e alone. Its purpose is to satisfy the classifier's capability requirement while choosing the lowest-carbon suitable candidate.

## EcoQuery model choices in this snapshot

| Query tier | Selected model |
| --- | --- |
| Simple | `gpt-oss-20b:free` |
| Medium | `gemma-4-31b:free` |
| Complex | `nemotron-3-super-120b-a12b:free` |

## Reproducible run

From the repository root:

```bash
cd backend
python benchmark.py
```

The benchmark uses 10 fixed prompts per tier, a fixed regional intensity input, model latency constants, and the estimator in `backend/router.py`. It does not call external providers, measure actual hardware energy, or verify answer quality. For a research-grade production experiment, run matched prompts repeatedly against each strategy and report success rate, latency distribution, model/version, carbon-data source, failures, and uncertainty intervals.
