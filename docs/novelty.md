# EcoQuery Novelty Claims

## What EcoQuery Adds
Unlike standard LLM routing which optimizes purely for cost or latency, EcoQuery introduces a **carbon-first, capability-aware routing algorithm**. 

### 1. Zero-Emission Knowledge Layer
EcoQuery uses an exact-match cache and a deterministic knowledge layer for 3,000+ common sustainability questions. This means that a large portion of simple queries are resolved locally with **0g of direct emissions**, avoiding LLM inference entirely.

### 2. Multi-Source Grid Intensity Integration
EcoQuery actively tracks regional carbon intensity (g CO₂/kWh) using the Electricity Maps API, falling back to IEA baselines. We route requests to data centers located in regions currently powered by renewables, reducing inference emissions by up to 90% without requiring users to change providers.

### 3. Objective Routing Modes
Users can select routing modes such as "Green", "Balanced", and "Quality", which weigh carbon cost against latency, financial cost, and model capability requirements.

### 4. Transparent Carbon Metadata
EcoQuery returns scientifically grounded carbon estimates with every API response. This includes:
- **Baseline comparison**: The emissions avoided vs. a standard unoptimized route.
- **Uncertainty Bounds**: Min/Max bounds recognizing the estimation variance.
- **Provider Lineage**: Transparent reporting of fallback paths if a provider fails.
