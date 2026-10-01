# EcoQuery Methodology

## Scope

EcoQuery is a consumer-side routing and audit layer. It runs before a request reaches an external model provider and chooses a model and carbon-intensity region using information available to the application. It does not control provider data centers and cannot directly meter their hardware.

## Estimated CO2e calculation

The carbon value shown by EcoQuery is an estimate, not a direct measurement of electricity consumed by one request:

```text
Estimated CO2e (g) = Estimated inference energy (kWh) x Grid carbon intensity (gCO2e/kWh)
```

The current estimator performs these steps:

1. Estimate tokens from the prompt length: `max(10, int(prompt_characters / 4 x 2.5))`.
2. Scale the versioned calibration record (`CALIBRATION_VERSION`) and its assumed energy rate by the selected model carbon score relative to a score of 3.
3. Multiply estimated energy by the selected region's grid intensity.
4. Calculate a comparison baseline using `0.001 kWh per 1,000 tokens` and `475 gCO2e/kWh`.

The implementation is in `backend/router.py` (`compute_savings`). The uncertainty interval combines named relative components for token estimation, model energy, grid intensity, provider-region inference, and fallback behavior. These calibration values are engineering assumptions and should be replaced with confidence intervals from measured workloads before formal emissions accounting. Results should therefore be reported as estimated CO2e and compared consistently, not presented as metered consumption.

## Carbon-data provenance

Carbon intensity is resolved in this order:

1. Electricity Maps latest carbon-intensity data when `ELECTRICITY_MAPS_API_KEY` is configured and the request succeeds.
2. IEA 2024 static regional baselines when the live API is unavailable or unconfigured.
3. A mock fallback only when no usable regional data is available.

The API response and audit metadata expose the method/source where available (`electricity-maps-api`, `iea-static-baselines`, or `mock-fallback`). This provenance matters because a live value and an annual baseline have different uncertainty. Measurement status is separately labelled `measured`, `provider_reported`, or `estimated`.

## Routing policy

EcoQuery routes each request through these stages:

1. Classify the request as simple, medium, or complex.
2. Drop candidates below the capability floor for that tier (`complex`, and `medium` below 0.75 confidence, require high-capability models).
3. Score every surviving candidate with the weighted sum below, using the selected region's grid carbon intensity.
4. Select the lowest-scoring candidate.
5. Estimate CO2e using the selected model and the current greenest region.

The selected model includes a human-readable reason, and the route metadata includes the tier, model, provider, region, energy source, carbon intensity, and carbon-data method. Supported modes are `green`, `balanced`, `quality`, `fast`, and `low-cost`. This is not a universal claim that the route is best for every objective: a carbon-weighted choice can be slower or more expensive.

The score is:

```text
total_score = w1 * quality_risk
            + w2 * estimated_carbon
            + w3 * latency
            + w4 * cost
            + w5 * provider_risk
```

`(w1, w2, w3, w4, w5)` are selected by mode: `green` (1, 5, 1, 1, 1), `balanced` (2, 2, 1, 1, 1), `fast` (1, 1, 5, 1, 1), `quality` (5, 1, 1, 1, 1), and `low-cost` (1, 1, 1, 5, 1). Lower is better.

The five terms are **not normalized** before weighting, so each term's raw magnitude matters as much as its weight. Measured across realistic inputs: `quality_risk` is 0, 5, or 10; `latency` is 1.0–2.5; `provider_risk` is 1.0 or 2.0; `cost` is 0.001–0.010; and `estimated_carbon` ranges from 0.0002 to about 1.7. Because `prompt_length` is `len(message)`, the carbon term scales linearly with the message's character count and the grid's carbon intensity: a short prompt on a clean grid contributes under 0.01, while a long prompt on a carbon-intensive grid can reach `latency`'s scale. The weights above are therefore not directly comparable across terms, and a change of mode does not always change which model wins.

## Evaluation protocol

The repository includes `backend/benchmark.py`, which evaluates 30 fixed prompts across simple, medium, and complex tiers. It compares:

- Always-largest model
- Always-smallest model
- EcoQuery carbon-aware routing

The simulator reports total and average estimated CO2e, average latency, carbon score, and per-tier results. This is a routing estimate, not proof of production energy savings because it does not make matched provider calls or measure hardware power. A stronger experiment should use the same prompt set and repeated runs for each strategy, record successful requests and latency, and report:

| Metric | Baseline | EcoQuery |
| --- | ---: | ---: |
| Queries completed | measured | measured |
| Total estimated CO2e (g) | measured | measured |
| Average latency (s) | measured | measured |
| Successful requests (%) | measured | measured |
| Carbon reduction (%) | - | `(baseline - EcoQuery) / baseline * 100` |

Report the sample size, model versions, region-data source, date, failures, and uncertainty. Do not describe simulated estimates as experimental measurements.

For live matched-provider evaluation, run `python scripts/live_benchmark.py --runs 3 --output benchmark-live.json` with a provider secret configured. The harness uses 100 prompts, compares EcoQuery, always-smallest, always-largest, random, and non-carbon-aware strategies, and reports mean, median, p95, standard deviation, 95% confidence intervals, quality scores, token counts, failures, and optional judge-model scores. It does not claim hardware energy measurement; carbon values must be joined from response metadata for emissions analysis.

The current checked-in snapshot is summarized in [EVALUATION.md](EVALUATION.md).

## Provider fallback and audit limitations

Provider fallback can change the actual model or provider after the initial route is selected. Responses expose requested model/provider, attempted provider records with redacted failure reasons, final model/provider, and latency. Provider keys themselves are never included in this lineage. A record contains:

```text
requested model/provider
actual model/provider
fallback: yes/no
failure reason/status
final carbon estimate and data source
```

This is a record of *which* provider answered, not a measurement of the energy it consumed. Audit consumers should treat provider identity and carbon values as the final observed application route rather than as metered hardware data.

## Model-integrity verification

TPS, latency, and response-pattern checks are behavioral signals. They can flag a response that looks inconsistent with estimated model thresholds, but they cannot cryptographically prove which model generated the response. SHA-256 hashes make the recorded metadata tamper-evident when combined with the hash-chained ledger; they do not prove model identity.

The accurate claim is:

> EcoQuery performs model-integrity verification using observable response characteristics such as token throughput and latency, combined with cryptographic hashing for audit integrity.

## Catalog and external-service uncertainty

The model catalog is exposed through `/api/models` and should be refreshed as provider availability, versions, capabilities, pricing, and rate limits change. Electricity Maps and model-provider outages are handled with fallbacks, but fallback use should remain visible in the UI and audit export. These limitations are part of the evaluation rather than reasons to hide uncertainty.

## Security and deployment limitations

Provider credentials are encrypted at rest with `KEY_ENCRYPTION_KEY`; the tracked legacy `backend/keys.db` file has been removed from the current repository index. If it ever contained real credentials, operators must revoke and rotate those credentials and rewrite repository history separately. Production also requires Redis for distributed rate limiting, while local development may use the documented fallback limiter.

Raw prompt text is redacted from new ledger entries by default. Operators must explicitly set `STORE_QUERY_TEXT=true` when retention is required and should pair that setting with documented retention, export, and deletion controls.
