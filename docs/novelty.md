# EcoQuery Novelty Claims

## What EcoQuery Adds
EcoQuery's contribution is an integration of existing techniques into a **carbon-aware, capability-aware routing layer**. It does not claim to invent the individual components.

## Primary research question

Can capability-aware carbon routing reduce estimated CO₂e while preserving answer quality and acceptable latency?

### 1. Zero-Emission Knowledge Layer
EcoQuery uses an exact-match cache and a deterministic knowledge layer for common questions. This can avoid external LLM inference; a `0 g` direct estimate does not mean total application electricity is zero.

### 2. Multi-Source Grid Intensity Integration
EcoQuery uses available regional carbon-intensity data from Electricity Maps or static baselines. Any reduction is an estimate based on the selected baseline, not a verified provider hardware measurement.

### 3. Objective Routing Modes
Users can select the implemented modes `green`, `balanced`, `quality`, `fast`, and `low-cost`, which weigh carbon cost against latency, financial cost, and model capability requirements.

### 4. Transparent Carbon Metadata
EcoQuery returns explicitly labelled carbon estimates with every API response. This includes:
- **Baseline comparison**: The emissions avoided vs. a standard unoptimized route.
- **Uncertainty Bounds**: Min/Max bounds recognizing the estimation variance.
- **Provider Lineage**: Transparent reporting of fallback paths if a provider fails.

## Limitations

- Cloud-provider hardware energy is not directly measurable by EcoQuery.
- Provider region may be inferred rather than disclosed.
- Carbon values depend on token estimation, calibration data, and grid-source freshness.
- Verification is behavioral and audit-oriented, not cryptographic proof of model identity.
- Live benchmark quality scores and carbon values require provider access and repeated experiments.
