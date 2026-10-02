# EcoQuery Research Plan

This document states the primary user, the research hypothesis, the human evaluation protocol, and the ablation plan. It is a protocol, not a results file.

**Execution status: nothing described under "Human evaluation protocol" or "Ablation plan" has been run.** No human ratings and no ablation numbers exist in this repository. Measured and simulated figures live in [EVALUATION.md](EVALUATION.md); the estimation formula, routing policy and their limits live in [METHODOLOGY.md](METHODOLOGY.md); the provenance every future result must carry lives in [REPRODUCIBILITY.md](REPRODUCIBILITY.md).

## Primary user

**Developers and small AI teams that want a carbon-aware multi-provider gateway.**

The primary user is an integrator: they call several LLM providers from one application and want capability, grid carbon intensity, latency and cost weighed for them at the routing layer, with an audit trail of the decision. Documentation order, defaults, dashboard copy and evaluation priorities are decided for this user first. Secondary readers (researchers studying routing policies, reviewers checking the methodology) are welcome but are not the design target.

### What the project deliberately is not

| Not this | Why it is out of scope |
| --- | --- |
| Consumer chatbot | EcoQuery is a gateway API plus an operator dashboard. It does not compete on conversation experience, persona, or end-user features. |
| ESG accounting platform | CO₂e values are **estimates** produced by the documented formula in [METHODOLOGY.md](METHODOLOGY.md). They are not metered, assured, or suitable for emissions disclosure, offsets, or compliance reporting. |
| Enterprise gateway | No SSO/SAML, capacity SLA, multi-tenant isolation guarantees, or on-prem deployment are claimed or tested. |
| Certification / assurance system | Throughput and latency checks plus a hash-chained ledger produce a tamper-evident audit record. They do not certify a provider, prove which model answered, or attest to actual emissions. |

## Research hypothesis

**Research question.** Can capability-aware routing reduce estimated CO₂e while maintaining answer quality and acceptable latency?

**H1 (alternative).** Routing each query by capability tier and grid carbon intensity reduces mean *estimated* CO₂e per query relative to fixed-strategy baselines (always-largest, always-smallest), while answer quality is non-inferior to the always-largest baseline and latency stays within a pre-declared bound.

**H0 (null).** Capability-aware routing does not reduce mean estimated CO₂e relative to the fixed baselines, **or** any reduction it achieves is offset by a measurable loss in answer quality or by latency outside the pre-declared bound. Under H0 the carbon-aware router is at best a re-ordering of the same trade-offs the fixed baselines already expose.

### Metrics that would falsify H1

Decision rules are declared here, before any rating is done, so they cannot be moved afterwards.

| Metric | How it is measured | H1 is falsified if |
| --- | --- | --- |
| Estimated CO₂e per query (g) | Estimator in `backend/router.py` (`compute_savings`) — an estimate from token count, model carbon score and grid intensity, never a meter reading | Mean estimated CO₂e is not lower than the always-largest baseline, or in a repeated live run the 95% confidence interval for the reduction includes 0 |
| Answer quality | Mean of the six rubric dimensions in the protocol below, on a 1–3 scale | EcoQuery's mean score is more than **0.3 points** below the always-largest baseline (pre-registered non-inferiority margin) |
| Latency | Mean and p95 wall-clock latency per condition | Mean latency exceeds the always-largest baseline, or p95 exceeds the pre-declared ceiling for the condition |
| Success rate | Completed responses ÷ attempts, failures counted per [REPRODUCIBILITY.md](REPRODUCIBILITY.md) | Success rate falls below 95%, i.e. the saving is bought with dropped requests |
| Tier classification accuracy | Accuracy of the tier the router acted on, against labelled prompts | Routing results cannot be attributed to routing because tier accuracy falls materially below the reported **80.85%** classifier hold-out accuracy |

### What already exists, and what it does not show

- The checked-in 30-prompt routing simulation reports **90.9%** estimated carbon reduction vs the fixed baseline ([EVALUATION.md](EVALUATION.md)). It is a deterministic simulation: it makes no provider calls, measures no energy, and scores no answer quality.
- The classifier hold-out accuracy is **80.85%** on 872 held-out rows from whole unseen prompt templates ([EVALUATION.md](EVALUATION.md)). It is a property of the classifier, not of routing.
- Neither figure tests H1. H1 requires the human evaluation and the ablations below.

## Human evaluation protocol

**Status: designed, NOT RUN. No ratings have been collected. Any number produced by this protocol must be reported with its provenance block per [REPRODUCIBILITY.md](REPRODUCIBILITY.md).**

### Who rates

- **Two independent raters per response**, blind to which strategy produced the response, to the model id, and to all carbon metadata. Raters are project members not involved in writing the router, or paid annotators working from the written anchors below.
- Both raters complete a **warm-up of 10 responses that are excluded from the sample**, discuss disagreements, and only then start scoring.
- An optional **judge model** (as offered by `scripts/live_benchmark.py`) may be used to pre-screen or to triple-check, but judge scores are reported separately and never replace the human scores.
- A **third rater** acts as adjudicator.

### Sample size and conditions

| Item | Value |
| --- | --- |
| Prompt set | The 30 fixed prompts in `backend/benchmark.py` (10 per tier), extended to 90 (30 per tier) from the live-harness prompt pool if available |
| Conditions | (a) EcoQuery `balanced` routing, (b) always-largest, (c) always-smallest |
| Repetitions | 3 runs per prompt per condition, run in one matched time window with the same credentials |
| Sample size | 90 responses per condition, **270 responses total**, 540 individual ratings |
| Unit of analysis | One prompt-response pair; per-tier results are reported alongside the overall mean |

### Scoring dimensions (1–3 rubric)

Every dimension is scored 1, 2 or 3, and **3 is always the best outcome** — for `hallucination` and `safety` that means the absence of the defect.

| Dimension | 1 | 2 | 3 |
| --- | --- | --- | --- |
| **Correctness** | Materially wrong: a factual, mathematical, or code-level error that changes the answer | Mostly correct: one minor error that does not change the conclusion | Correct on every point a knowledgeable reader would check |
| **Relevance** | Answers a different question, or ignores the prompt | On topic, but padded with material the prompt did not ask for | Directly addresses what was asked |
| **Completeness** | Missing the core of the request | Covers the main points; misses a notable secondary point | Covers everything a reasonable expert would expect for this prompt |
| **Hallucination** | Fabricates facts, citations, data, code output, or sources presented as real | One unsupported detail that does not affect the answer | No unsupported claims beyond the prompt and the provided context |
| **Safety** | Gives unsafe or harmful guidance, or refuses a benign request outright | Handles the request but with a needless caveat-heavy refusal, or partially unsafe framing | Handles safety-relevant content appropriately; no harmful output, no spurious refusal |
| **Task completion** | The user could not do what they asked for | Partially done; needs at least one follow-up turn | Complete and usable as-is |

**Aggregation.** Per-response score = unweighted mean of the six dimensions (per-dimension means are always reported too, so a gain on one dimension cannot hide a loss on another).

### Resolving disagreements

1. Ratings are compared before any discussion; **inter-rater agreement (Cohen's κ, or Krippendorff's α for the ordinal scale) is reported on the raw, pre-adjudication ratings**.
2. A difference of exactly **1 point** is resolved by discussion between the two raters to a single consensus score.
3. A difference of **2 or more points**, any disagreement in which one rater marked `hallucination` or `safety` as **1** while the other did not, or a discussion that fails to reach consensus, goes to the **third rater**, whose score replaces both.
4. Both the pre-adjudication and post-adjudication distributions are published; adjudicated scores are the ones used in the H1 decision rule.

### Decision rule

H1's quality condition holds only if EcoQuery's mean overall score is within 0.3 points of the always-largest baseline *and* no dimension's mean is more than 0.5 points lower. Otherwise the carbon reduction is reported as quality-degraded.

## Ablation plan

**Status: all seven ablations are DESIGNED BUT NOT EXECUTED.** Each removes exactly one component from an otherwise identical run — same prompt set, same catalog, same routing mode, same grid input, same credentials — and compares paired per-prompt results against the full system. No ablation has been implemented, run, or measured; there are no ablation numbers to report.

### 1. Without knowledge short-circuit

- **Component:** the exact-match cache and deterministic knowledge layer in `backend/knowledge.py`, which answers some prompts with no outbound LLM call.
- **Hypothesis being tested:** the short-circuit removes real inference work — lower estimated CO₂e and lower latency — without costing answer quality on the prompts it absorbs.
- **Metric:** share of prompts short-circuited; estimated CO₂e per query; p50/p95 latency; rubric scores restricted to short-circuited prompts.
- **Isolation:** knowledge lookup disabled before classification so every prompt reaches the router; catalog, mode, grid input and prompt set unchanged.
- **Status:** not executed.

### 2. Without capability filter

- **Component:** stage 2 of the routing policy in `backend/router.py` — the capability floor that drops candidates below the tier minimum (`complex`, and `medium` below 0.75 confidence, require high-capability models).
- **Hypothesis being tested:** the floor is what protects answer quality on hard prompts, and it buys that protection at a bounded estimated-carbon cost.
- **Metric:** per-tier rubric `correctness` and `task completion`; estimated CO₂e; share of `complex`-tier prompts routed to `medium`- or `low`-capability models.
- **Isolation:** stage 2 filter removed; stage 3 scoring unchanged, including the `quality_risk` term, so only the floor is under test.
- **Status:** not executed.

### 3. Without carbon score

- **Component:** the carbon term of the routing score — `w2` and `normalize(estimated_carbon, 0, 0.10667)` in `backend/router.py`.
- **Hypothesis being tested:** selection changes and estimated savings come from the carbon term itself rather than from latency or cost, which happen to correlate with it in the current catalog.
- **Metric:** route agreement rate with the full router (how often a different model is chosen); estimated CO₂e; rubric scores; latency.
- **Isolation:** `w2 = 0` for every mode; all other weights and the fixed normalisation ranges untouched.
- **Caveat:** [METHODOLOGY.md](METHODOLOGY.md) reports carbon and latency correlate at **r = +0.887** across the seven-model catalog, so a small effect would be evidence about the catalog, not proof the term is inert.
- **Status:** not executed.

### 4. Without grid data

- **Component:** regional carbon-intensity variation (Electricity Maps live values, IEA static baselines) in `backend/carbon.py`.
- **Hypothesis being tested:** regional grid variation changes which route is chosen and what it is estimated to emit, beyond what a flat-grid assumption produces.
- **Metric:** share of tier × mode × prompt-length cells where the selected model or region changes; estimated CO₂e; region-selection distribution.
- **Isolation:** every region is fed one constant intensity (475 gCO₂e/kWh, the same constant the estimator uses for its comparison baseline) while catalog, mode and weights stay fixed.
- **Existing partial evidence:** [METHODOLOGY.md](METHODOLOGY.md) already reports an intensity sweep changes the selected model in **5 of 45** cells; the end-to-end ablation (quality and estimated CO₂e under a flat grid) has not been run.
- **Status:** not executed.

### 5. Without provider fallback

- **Component:** the ordered multi-provider fallback chain in `backend/providers.py`.
- **Hypothesis being tested:** fallback raises success rate, and its price is extra latency plus route drift (the model that answers is not the model the router chose).
- **Metric:** success rate and failure count; p95 latency; share of responses whose final provider/model differs from the requested one; rubric scores on drifted responses.
- **Isolation:** single attempt to the router's chosen model only; routing, catalog and credentials otherwise identical; every attempt recorded.
- **Status:** not executed.

### 6. Without uncertainty

- **Component:** the uncertainty interval computed by `backend/calibration.py` (`combined_relative_uncertainty`, exposed as `co2_uncertainty_pct`).
- **Hypothesis being tested:** showing the interval changes conclusions — some comparisons that look like wins on point estimates become indeterminate once uncertainty is displayed.
- **Metric:** share of pairwise strategy comparisons whose direction flips, or becomes "not separable", when intervals are considered rather than point estimates; reader decision agreement in a small comparison task (optional, human).
- **Isolation:** identical run and identical numbers, with the interval omitted from the reported output; the comparison is recomputed from the same records.
- **Status:** not executed.

### 7. Without BYOK

- **Component:** the per-provider "bring your own key" headers (`X-OpenRouter-Key`, `X-Google-Key`, `X-Grok-Key`, `X-OpenAI-Key`, `X-Groq-Key`, `X-Anthropic-Key`) documented in the [README](../README.md).
- **Hypothesis being tested:** BYOK changes who pays and how often a route falls back (a rejected user key falls back to server keys), but does not change routing decisions or answer quality.
- **Metric:** `byok_used` / `key_source` distribution; provider-fallback rate; success rate; latency; rubric scores.
- **Isolation:** headers stripped before routing; same prompt set, same server credentials, same mode.
- **Status:** not executed.

### Running the ablations

None of the seven has been implemented as a switch. Until they are run and their artifacts carry the provenance block in [REPRODUCIBILITY.md](REPRODUCIBILITY.md), this section is a design document only and must not be cited as evidence for or against the hypothesis.

## Related documents

| Document | What it holds |
| --- | --- |
| [METHODOLOGY.md](METHODOLOGY.md) | Estimation formula, routing policy, data provenance, verification limitations |
| [EVALUATION.md](EVALUATION.md) | The checked-in simulated snapshot and classifier accuracy |
| [REPRODUCIBILITY.md](REPRODUCIBILITY.md) | Provenance every benchmark result must carry |
| [API_FLOW.md](API_FLOW.md) | Request path, including what `verification_status` does and does not mean |
| [novelty.md](novelty.md) | What is claimed as new, and what is not |
