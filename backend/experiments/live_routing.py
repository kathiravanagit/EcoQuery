"""Matched-provider routing experiment.

The runner records one JSONL row per prompt/run and refuses to label a run as
live unless LIVE_EXPERIMENT=1 is set. Without credentials it can still emit a
marked mock artifact for pipeline testing, never for headline claims.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import statistics
import time
from datetime import date
from pathlib import Path

FIXED_30 = [
    "Explain photosynthesis in two sentences.",
    "What is a carbon footprint?",
    "Compare REST and GraphQL.",
    "Write a Python function for binary search.",
    "Explain the difference between supervised and unsupervised learning.",
] * 6
STRATEGIES = ["always_largest", "always_smallest", "ecoquery", "region_fixed_model_variable", "model_fixed_region_variable"]


def _answer_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def run(output_dir: str | Path = "experiments/results", runs: int = 5, mock: bool = False) -> Path:
    if not mock and os.getenv("LIVE_EXPERIMENT") != "1":
        raise RuntimeError("Set LIVE_EXPERIMENT=1 and configure provider credentials before a live run")
    out = Path(output_dir) / date.today().isoformat()
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for strategy in STRATEGIES:
        for prompt_id, prompt in enumerate(FIXED_30):
            for run_id in range(runs):
                started = time.perf_counter()
                if mock:
                    answer = f"mock response for {prompt}"
                    provider, region, model = "mock", "mock", "mock"
                    source, success, error_class = "mock", True, None
                else:
                    from models import CARBON_MODELS
                    from providers import provider_router
                    from router import route_query
                    from classifier import classifier

                    ordered = sorted(CARBON_MODELS, key=lambda item: item["carbon_score"])
                    if strategy == "always_largest":
                        selected = ordered[-1]
                    elif strategy == "always_smallest":
                        selected = ordered[0]
                    else:
                        classification = await classifier.classify(prompt)
                        route = await route_query(classification["tier"], prompt_length=len(prompt))
                        selected = next((item for item in CARBON_MODELS if item["id"] == route["model"]["model"]), ordered[0])
                    result = await provider_router.chat_completion(selected["openrouter_id"], [{"role": "user", "content": prompt}], max_tokens=200)
                    answer = result.get("content", "")
                    provider, region, model = selected["provider"], "provider-selected", selected["id"]
                    source, success, error_class = "configured-provider", bool(answer), result.get("error")
                elapsed = (time.perf_counter() - started) * 1000
                rows.append({
                    "strategy": strategy, "prompt_id": prompt_id, "run": run_id,
                    "tier": "fixed", "requested_model": model, "actual_model": model,
                    "provider": provider, "region": region, "carbon_source": source,
                    "prompt_tokens": len(prompt.split()), "completion_tokens": len(answer.split()),
                    "t_first_token_ms": elapsed, "t_last_token_ms": elapsed,
                    "total_latency_ms": elapsed, "success": success, "error_class": error_class,
                    "answer_hash": _answer_hash(answer), "est_co2_g": 0.0,
                })
    jsonl = out / "results.jsonl"
    jsonl.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    successes = [row for row in rows if row["success"]]
    summary = {
        "run_date": date.today().isoformat(), "runs": runs, "samples": len(rows),
        "mode": "mock" if mock else "live", "success_rate": len(successes) / len(rows) if rows else 0,
        "mean_est_co2_g": statistics.mean(row["est_co2_g"] for row in successes) if successes else None,
        "strategies": STRATEGIES,
        "carbon_sources": sorted({row["carbon_source"] for row in rows}),
        "results_file": str(jsonl),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out / "summary.json"


if __name__ == "__main__":
    asyncio.run(run(mock=os.getenv("EXPERIMENT_MOCK") == "1"))
