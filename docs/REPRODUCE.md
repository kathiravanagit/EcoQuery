# Reproduce

Prerequisites: Python 3.12+, Node.js 22+, and the pinned dependencies.

```text
make test
make experiment
python scripts/generate_evaluation.py experiments/results/YYYY-MM-DD/summary.json
```

Live experiments require `LIVE_EXPERIMENT=1`, provider credentials in the environment, and record the run date, model/provider identifiers, and carbon-data source per sample. `EXPERIMENT_MOCK=1` is only for pipeline smoke tests and must not be used for report claims.
