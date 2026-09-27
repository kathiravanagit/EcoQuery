"""Live matched-provider benchmark for EcoQuery routing strategies.

This script requires configured provider credentials and is intentionally
opt-in. It never writes prompts or credentials to logs; results contain only
the prompt id and aggregate response metadata.

Run from the repository root:
    python scripts/live_benchmark.py --runs 3 --output benchmark-live.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import statistics
import sys
import time
from pathlib import Path

from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from router import select_model  # noqa: E402


MODEL_SMALL = os.getenv("BENCHMARK_SMALL_MODEL", "openai/gpt-oss-20b:free")
MODEL_LARGE = os.getenv("BENCHMARK_LARGE_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
MODEL_SCORES = {MODEL_SMALL: 1.0, MODEL_LARGE: 8.0}


def build_prompts() -> list[dict]:
    templates = [
        ("summarize", "Summarize the main idea of renewable energy in two sentences.", ["energy"]),
        ("explain", "Explain why unit tests help software teams, using one example.", ["test"]),
        ("compare", "Compare REST and GraphQL in a compact table.", ["REST", "GraphQL"]),
        ("algorithm", "Give pseudocode for binary search and state its time complexity.", ["binary", "log"]),
        ("security", "List three practical ways to protect an API from abuse.", ["rate", "auth"]),
        ("science", "Explain the water cycle for a high-school student.", ["water"]),
        ("planning", "Create a three-step plan for migrating a small service to containers.", ["step"]),
        ("math", "What is 17 multiplied by 19? Show the arithmetic.", ["323"]),
        ("writing", "Rewrite this sentence clearly: The report was made by the team yesterday.", ["team"]),
        ("debugging", "Name two likely causes of an HTTP 500 response and how to inspect them.", ["log"]),
    ]
    prompts = []
    for repetition in range(10):
        for kind, text, expected in templates:
            prompts.append({"id": f"{kind}-{repetition + 1:02d}", "text": f"{text} Context variant {repetition + 1}.", "expected": expected})
    return prompts


def quality_score(text: str, expected: list[str]) -> float:
    if not text:
        return 0.0
    lowered = text.lower()
    hits = sum(term.lower() in lowered for term in expected)
    return round(min(1.0, 0.5 + 0.5 * hits / max(1, len(expected))), 3)


def add_carbon_estimate(result: dict) -> None:
    tokens = max(10, result["prompt_tokens"] + result["completion_tokens"])
    score = MODEL_SCORES.get(result["model"], 3.0)
    result["estimated_co2_g"] = round((tokens / 1000.0) * 0.0002 * (score / 3.0) * 200.0, 6)
    result["baseline_co2_g"] = round((tokens / 1000.0) * 0.001 * 475.0, 6)
    result["estimated_co2_saved_g"] = round(max(0.0, result["baseline_co2_g"] - result["estimated_co2_g"]), 6)


def stats(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "mean": None, "median": None, "p95": None, "stdev": None, "confidence_interval_95": None}
    ordered = sorted(values)
    p95 = ordered[min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)]
    mean = statistics.mean(values)
    margin = 1.96 * (statistics.stdev(values) / math.sqrt(len(values))) if len(values) > 1 else 0.0
    return {
        "count": len(values),
        "mean": round(mean, 4),
        "median": round(statistics.median(values), 4),
        "p95": round(p95, 4),
        "stdev": round(statistics.stdev(values), 4) if len(values) > 1 else 0.0,
        "confidence_interval_95": [round(mean - margin, 4), round(mean + margin, 4)],
    }


async def call_model(client: AsyncOpenAI, model: str, prompt: str) -> dict:
    started = time.perf_counter()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        content = response.choices[0].message.content if response.choices else ""
        usage = response.usage
        return {
            "success": bool(content),
            "content": content or "",
            "latency_seconds": round(time.perf_counter() - started, 4),
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
            "failure_reason": None if content else "empty_response",
        }
    except Exception as exc:
        return {"success": False, "content": "", "latency_seconds": round(time.perf_counter() - started, 4), "prompt_tokens": 0, "completion_tokens": 0, "failure_reason": type(exc).__name__}


async def judge_quality(client: AsyncOpenAI, model: str, prompt: str, answer: str) -> float | None:
    result = await call_model(client, model, f"Score the answer from 0 to 10 for correctness and task completion. Return only the number.\nQuestion: {prompt}\nAnswer: {answer}")
    if not result["success"]:
        return None
    try:
        return round(max(0.0, min(1.0, float(result["content"].strip()) / 10.0)), 3)
    except ValueError:
        return None


async def main(runs: int, output: Path, judge_model: str | None = None) -> None:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is required for the live benchmark")
    client = AsyncOpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1", timeout=60.0)
    models = {"always-smallest": MODEL_SMALL, "always-largest": MODEL_LARGE, "non-carbon-aware": MODEL_LARGE}
    records = []
    prompts = build_prompts()
    for run in range(runs):
        for prompt in prompts:
            for strategy, model in models.items():
                result = await call_model(client, model, prompt["text"])
                result.update({"prompt_id": prompt["id"], "run": run + 1, "strategy": strategy, "model": model, "quality_score": quality_score(result["content"], prompt["expected"])})
                add_carbon_estimate(result)
                if judge_model and result["success"]:
                    result["judge_quality_score"] = await judge_quality(client, judge_model, prompt["text"], result["content"])
                records.append(result)
            random_model = random.choice([MODEL_SMALL, MODEL_LARGE])
            result = await call_model(client, random_model, prompt["text"])
            result.update({"prompt_id": prompt["id"], "run": run + 1, "strategy": "random", "model": random_model, "quality_score": quality_score(result["content"], prompt["expected"])})
            add_carbon_estimate(result)
            if judge_model and result["success"]:
                result["judge_quality_score"] = await judge_quality(client, judge_model, prompt["text"], result["content"])
            records.append(result)
            tier = "complex" if len(prompt["text"]) > 120 else "medium"
            selection = select_model(tier, "benchmark", 200.0, mode="balanced", confidence=1.0, prompt_length=len(prompt["text"]))
            eco_model = selection.get("openrouter_id") or selection["model"]
            result = await call_model(client, eco_model, prompt["text"])
            result.update({"prompt_id": prompt["id"], "run": run + 1, "strategy": "ecoquery", "model": eco_model, "quality_score": quality_score(result["content"], prompt["expected"])})
            add_carbon_estimate(result)
            if judge_model and result["success"]:
                result["judge_quality_score"] = await judge_quality(client, judge_model, prompt["text"], result["content"])
            records.append(result)

    summary = {}
    for strategy in sorted({record["strategy"] for record in records}):
        group = [record for record in records if record["strategy"] == strategy]
        successful = [record for record in group if record["success"]]
        summary[strategy] = {
            "requests": len(group),
            "successes": len(successful),
            "failure_rate": round(1 - len(successful) / len(group), 4) if group else None,
            "quality": stats([record["quality_score"] for record in successful]),
            "judge_quality": stats([record["judge_quality_score"] for record in successful if record.get("judge_quality_score") is not None]),
            "latency_seconds": stats([record["latency_seconds"] for record in successful]),
            "tokens": stats([record["prompt_tokens"] + record["completion_tokens"] for record in successful]),
            "estimated_co2_g": round(sum(record["estimated_co2_g"] for record in successful), 6),
            "estimated_co2_saved_g": round(sum(record["estimated_co2_saved_g"] for record in successful), 6),
        }
    output.write_text(json.dumps({"prompt_count": len(prompts), "runs": runs, "summary": summary, "records": records}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("benchmark-live.json"))
    parser.add_argument("--judge-model", default=os.getenv("BENCHMARK_JUDGE_MODEL"))
    args = parser.parse_args()
    asyncio.run(main(max(1, args.runs), args.output, args.judge_model))
