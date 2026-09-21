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
2. Scale an assumed energy rate of `0.0002 kWh per 1,000 tokens` by the selected model carbon score relative to a score of 3.
3. Multiply estimated energy by the selected region's grid intensity.
4. Calculate a comparison baseline using `0.001 kWh per 1,000 tokens` and `475 gCO2e/kWh`.

The implementation is in `backend/router.py` (`compute_savings`). The constants are engineering assumptions and should be recalibrated against measured infrastructure data before being used for formal emissions accounting. Results should therefore be reported as estimated CO2e and compared consistently, not presented as metered consumption.

## Carbon-data provenance

Carbon intensity is resolved in this order:

1. Electricity Maps latest carbon-intensity data when `ELECTRICITY_MAPS_API_KEY` is configured and the request succeeds.
2. IEA 2024 static regional baselines when the live API is unavailable or unconfigured.
3. A mock fallback only when no usable regional data is available.

The API response and audit metadata expose the method/source where available (`electricity-maps-api`, `iea-static-baselines`, or `mock-fallback`). This provenance matters because a live value and an annual baseline have different uncertainty.

## Routing policy

EcoQuery currently uses a carbon-first policy:

1. Classify the request as simple, medium, or complex.
2. Filter models by the minimum capability required for that tier.
3. Prefer candidates with the lowest model carbon score.
4. Break ties using estimated latency.
5. Estimate CO2e using the selected model and the current greenest region.

The selected model includes a human-readable reason, and the route metadata includes the tier, model, provider, region, energy source, carbon intensity, and carbon-data method. This is not a universal claim that the route is best for every objective: a carbon-first choice can be slower or more expensive. A future balanced policy can use an explicit score such as:

```text
score = alpha * normalized_carbon + beta * normalized_latency + gamma * normalized_cost
```

with weights reported alongside each experiment.

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

The current checked-in snapshot is summarized in [EVALUATION.md](EVALUATION.md).

## Provider fallback and audit limitations

Provider fallback can change the actual model or provider after the initial route is selected. The current audit record captures the final model used and its recalculated model/region estimate when the application-level model fallback succeeds. Provider-level key fallback is handled inside `backend/providers.py` and is not yet surfaced as a complete requested-provider, actual-provider, failure-reason record in every streaming and non-streaming response.

Until that instrumentation is added, audit consumers should treat provider identity and carbon values as the final observed application route, not as a complete causal history of every failed attempt. A complete record should contain:

```text
requested model/provider
actual model/provider
fallback: yes/no
failure reason/status
final carbon estimate and data source
```

## Model-integrity verification

TPS, latency, and response-pattern checks are behavioral signals. They can flag a response that looks inconsistent with estimated model thresholds, but they cannot cryptographically prove which model generated the response. SHA-256 hashes make the recorded metadata tamper-evident when combined with the hash-chained ledger; they do not prove model identity.

The accurate claim is:

> EcoQuery performs model-integrity verification using observable response characteristics such as token throughput and latency, combined with cryptographic hashing for audit integrity.

## Catalog and external-service uncertainty

The model catalog is exposed through `/api/models` and should be refreshed as provider availability, versions, capabilities, pricing, and rate limits change. Electricity Maps and model-provider outages are handled with fallbacks, but fallback use should remain visible in the UI and audit export. These limitations are part of the evaluation rather than reasons to hide uncertainty.
