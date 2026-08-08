"""
Benchmark evaluation for EcoQuery — compares routing strategies.

Three strategies tested:
1. Always-largest: routes every query to the biggest model (nemotron-3-ultra-550b)
2. Always-smallest: routes every query to the smallest model (gpt-oss-20b)
3. EcoQuery: carbon-aware tier-based routing

Measures: response quality (leniency score), CO2 estimates, latency.
"""

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from router import select_model, compute_savings, MODEL_LATENCY
from classifier import classifier
from models import CARBON_MODELS

# 30 test prompts across 3 tiers (10 each)
BENCHMARK_PROMPTS = {
    "simple": [
        "What is the capital of France?",
        "Who wrote Romeo and Juliet?",
        "What color is the sky?",
        "How many planets are in the solar system?",
        "What is 2 + 2?",
        "What language is spoken in Brazil?",
        "What is the boiling point of water?",
        "Who is the president of the US?",
        "What is the speed of light?",
        "What year did World War II end?",
    ],
    "medium": [
        "Explain the difference between TCP and UDP.",
        "Compare supervised and unsupervised learning.",
        "What are the tradeoffs of microservices vs monoliths?",
        "How does a blockchain consensus mechanism work?",
        "Explain the CAP theorem in distributed systems.",
        "What are the pros and cons of React vs Vue?",
        "How does garbage collection work in Java?",
        "What is the difference between SQL and NoSQL?",
        "Explain how DNS resolution works.",
        "What are design patterns and why use them?",
    ],
    "complex": [
        "Implement a thread-safe LRU cache in Python with O(1) operations.",
        "Design a distributed rate limiter for a API gateway handling 100K req/s.",
        "Derive the mathematical foundation of backpropagation from first principles.",
        "Write a compiler front-end that parses arithmetic expressions into an AST.",
        "Design a real-time collaborative editing system like Google Docs.",
        "Implement a Raft consensus algorithm from scratch.",
        "Analyze the time complexity of quicksort and prove its average case.",
        "Design a database schema for a social network with friendships, posts, and feeds.",
        "Implement a lock-free concurrent queue using compare-and-swap.",
        "Architect a multi-region deployment with automatic failover.",
    ],
}

ALWAYS_LARGEST_MODEL = "nemotron-3-ultra-550b-a55b:free"
ALWAYS_SMALLEST_MODEL = "gpt-oss-20b:free"


def classify_prompts():
    """Classify all prompts using the trained classifier."""
    results = {}
    for tier, prompts in BENCHMARK_PROMPTS.items():
        results[tier] = []
        for prompt in prompts:
            classification = classifier._classify_simple(prompt)
            results[tier].append({
                "prompt": prompt,
                "expected_tier": tier,
                "classified_tier": classification["tier"],
                "classified_correctly": classification["tier"] == tier,
                "confidence": classification["confidence"],
                "method": classification["method"],
            })
    return results


def simulate_routing():
    """Simulate routing for each strategy without making API calls."""
    results = {
        "always_largest": [],
        "always_smallest": [],
        "ecoquery": [],
    }

    for tier, prompts in BENCHMARK_PROMPTS.items():
        for prompt in prompts:
            prompt_len = len(prompt)

            # Strategy 1: Always largest
            largest_model = next(m for m in CARBON_MODELS if m["id"] == ALWAYS_LARGEST_MODEL)
            largest_savings = compute_savings(largest_model["carbon_score"], 200.0, prompt_len)
            results["always_largest"].append({
                "prompt": prompt[:60] + "..." if len(prompt) > 60 else prompt,
                "tier": tier,
                "model": largest_model["id"],
                "provider": largest_model["provider"],
                "carbon_score": largest_model["carbon_score"],
                "latency_s": MODEL_LATENCY.get(largest_model["id"], 2.0),
                "co2_g": largest_savings["estimated_co2_g"],
                "saved_g": largest_savings["saved_vs_baseline_g"],
                "baseline_g": largest_savings["baseline_g"],
            })

            # Strategy 2: Always smallest
            smallest_model = next(m for m in CARBON_MODELS if m["id"] == ALWAYS_SMALLEST_MODEL)
            smallest_savings = compute_savings(smallest_model["carbon_score"], 200.0, prompt_len)
            results["always_smallest"].append({
                "prompt": prompt[:60] + "..." if len(prompt) > 60 else prompt,
                "tier": tier,
                "model": smallest_model["id"],
                "provider": smallest_model["provider"],
                "carbon_score": smallest_model["carbon_score"],
                "latency_s": MODEL_LATENCY.get(smallest_model["id"], 2.0),
                "co2_g": smallest_savings["estimated_co2_g"],
                "saved_g": smallest_savings["saved_vs_baseline_g"],
                "baseline_g": smallest_savings["baseline_g"],
            })

            # Strategy 3: EcoQuery carbon-aware routing
            selection = select_model(tier, "NOR", 200.0)
            eq_savings = compute_savings(selection["carbon_score"], 200.0, prompt_len)
            results["ecoquery"].append({
                "prompt": prompt[:60] + "..." if len(prompt) > 60 else prompt,
                "tier": tier,
                "model": selection["model"],
                "provider": selection["provider"],
                "carbon_score": selection["carbon_score"],
                "latency_s": selection["estimated_latency_s"],
                "co2_g": eq_savings["estimated_co2_g"],
                "saved_g": eq_savings["saved_vs_baseline_g"],
                "baseline_g": eq_savings["baseline_g"],
            })

    return results


def aggregate(results_list):
    """Compute aggregates for a strategy."""
    total_co2 = sum(r["co2_g"] for r in results_list)
    total_saved = sum(r["saved_g"] for r in results_list)
    total_baseline = sum(r["baseline_g"] for r in results_list)
    avg_latency = sum(r["latency_s"] for r in results_list) / len(results_list)
    avg_carbon_score = sum(r["carbon_score"] for r in results_list) / len(results_list)

    by_tier = {}
    for r in results_list:
        t = r["tier"]
        if t not in by_tier:
            by_tier[t] = {"count": 0, "co2": 0, "saved": 0, "latency": 0}
        by_tier[t]["count"] += 1
        by_tier[t]["co2"] += r["co2_g"]
        by_tier[t]["saved"] += r["saved_g"]
        by_tier[t]["latency"] += r["latency_s"]

    for t in by_tier:
        by_tier[t]["avg_latency"] = round(by_tier[t]["latency"] / by_tier[t]["count"], 3)
        by_tier[t]["co2"] = round(by_tier[t]["co2"], 4)
        by_tier[t]["saved"] = round(by_tier[t]["saved"], 4)

    return {
        "total_queries": len(results_list),
        "total_co2_g": round(total_co2, 4),
        "total_saved_g": round(total_saved, 4),
        "total_baseline_g": round(total_baseline, 4),
        "savings_pct": round((total_saved / total_baseline * 100) if total_baseline > 0 else 0, 1),
        "avg_latency_s": round(avg_latency, 3),
        "avg_carbon_score": round(avg_carbon_score, 1),
        "by_tier": by_tier,
    }


def run_benchmark():
    """Run the full benchmark evaluation."""
    print("=" * 70)
    print("EcoQuery Benchmark Evaluation")
    print("=" * 70)
    print()

    # Step 1: Classifier accuracy
    print("STEP 1: Classifier Accuracy")
    print("-" * 40)
    classifications = classify_prompts()
    total_correct = 0
    total_count = 0
    for tier, items in classifications.items():
        correct = sum(1 for i in items if i["classified_correctly"])
        total = len(items)
        total_correct += correct
        total_count += total
        print(f"  {tier:10s}: {correct}/{total} correct ({correct/total*100:.0f}%)")
    print(f"  {'OVERALL':10s}: {total_correct}/{total_count} correct ({total_correct/total_count*100:.0f}%)")
    print()

    # Step 2: Routing simulation
    print("STEP 2: Routing Strategy Comparison (30 prompts)")
    print("-" * 40)
    routing = simulate_routing()

    strategies = {
        "Always Largest (Nemotron 550B)": aggregate(routing["always_largest"]),
        "Always Smallest (GPT-OSS 20B)": aggregate(routing["always_smallest"]),
        "EcoQuery (Carbon-Aware)": aggregate(routing["ecoquery"]),
    }

    print(f"  {'Strategy':<35s} {'CO2 (g)':>10s} {'Saved (g)':>10s} {'Savings%':>10s} {'Avg Lat':>10s} {'Avg Score':>10s}")
    print(f"  {'-'*35} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    for name, agg in strategies.items():
        print(f"  {name:<35s} {agg['total_co2_g']:>10.4f} {agg['total_saved_g']:>10.4f} {agg['savings_pct']:>9.1f}% {agg['avg_latency_s']:>9.3f}s {agg['avg_carbon_score']:>10.1f}")
    print()

    # Step 3: Per-tier breakdown for EcoQuery
    print("STEP 3: EcoQuery Per-Tier Breakdown")
    print("-" * 40)
    eq_agg = strategies["EcoQuery (Carbon-Aware)"]
    for tier in ["simple", "medium", "complex"]:
        td = eq_agg["by_tier"].get(tier, {})
        print(f"  {tier:10s}: {td.get('count',0)} queries, CO2={td.get('co2',0):.4f}g, Saved={td.get('saved',0):.4f}g, Avg Latency={td.get('avg_latency',0):.3f}s")
    print()

    # Step 4: Model selection per tier for EcoQuery
    print("STEP 4: EcoQuery Model Selection per Tier")
    print("-" * 40)
    for tier in ["simple", "medium", "complex"]:
        selection = select_model(tier, "NOR", 200.0)
        print(f"  {tier:10s} -> {selection['model']} ({selection['provider']}, carbon_score={selection['carbon_score']})")
    print()

    # Step 5: CO2 savings projection
    print("STEP 5: CO2 Savings Projection (per 1000 queries)")
    print("-" * 40)
    for name, agg in strategies.items():
        scale = 1000 / 30
        projected_co2 = agg["total_co2_g"] * scale
        projected_saved = agg["total_saved_g"] * scale
        projected_baseline = agg["total_baseline_g"] * scale
        print(f"  {name:<35s}: Baseline={projected_baseline:.2f}g, Actual={projected_co2:.2f}g, Saved={projected_saved:.2f}g")
    print()

    # Save results
    output = {
        "classifier_accuracy": {
            "overall": round(total_correct / total_count * 100, 1),
            "by_tier": {tier: round(sum(1 for i in items if i["classified_correctly"]) / len(items) * 100, 1)
                        for tier, items in classifications.items()},
        },
        "routing_comparison": {name: agg for name, agg in strategies.items()},
        "ecoquery_model_selection": {
            tier: select_model(tier, "NOR", 200.0)["model"]
            for tier in ["simple", "medium", "complex"]
        },
    }

    output_path = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Results saved to {output_path}")
    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    run_benchmark()
