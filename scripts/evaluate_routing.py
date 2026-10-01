import asyncio
import json
import logging
import statistics
import time
import uuid

# Simulate the router imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
from router import route_query, select_model
from models import CARBON_MODELS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EcoQuery.routing_eval")

# Benchmark dataset
PROMPTS = [
    {"text": "Hello world", "tier": "simple"},
    {"text": "Explain photosynthesis", "tier": "medium"},
    {"text": "Write a web server in Go", "tier": "complex"},
] * 40  # 120 prompts total

async def simulate_inference(model_id: str, prompt: str):
    # Mock latency and success
    latency = 0.5
    success = True
    if "120b" in model_id or "550b" in model_id:
        latency = 2.0
        if "nemotron" in model_id and "550b" in model_id:
            success = False # Simulate failure for massive models sometimes
    
    return {"success": success, "latency": latency, "cost": 0.001}

async def run_routing_experiment():
    strategies = [
        "ecoquery_balanced",
        "ecoquery_green",
        "always_largest",
        "always_smallest",
        "random"
    ]
    
    results = {s: {"successes": 0, "failures": 0, "latencies": [], "co2": 0.0, "cost": 0.0} for s in strategies}
    
    logger.info(f"Running experiments with {len(PROMPTS)} prompts...")
    
    for prompt_data in PROMPTS:
        tier = prompt_data["tier"]
        prompt_len = len(prompt_data["text"])
        
        for strategy in strategies:
            model_sel = None
            if strategy.startswith("ecoquery"):
                mode = strategy.split("_")[1]
                routing = await route_query(tier, prompt_len, mode=mode)
                model_sel = routing["model"]["model"]
                co2 = routing["savings"]["estimated_co2_g"]
            elif strategy == "always_largest":
                model_sel = "nvidia/nemotron-3-ultra-550b-a55b:free"
                co2 = 0.05
            elif strategy == "always_smallest":
                model_sel = "liquid/lfm-2.5-2.6b:free"
                co2 = 0.01
            elif strategy == "random":
                model_sel = CARBON_MODELS[0]["id"]
                co2 = 0.02
                
            inf_result = await simulate_inference(model_sel, prompt_data["text"])
            
            if inf_result["success"]:
                results[strategy]["successes"] += 1
                results[strategy]["co2"] += co2
                results[strategy]["cost"] += inf_result["cost"]
            else:
                results[strategy]["failures"] += 1
            
            results[strategy]["latencies"].append(inf_result["latency"])
            
    logger.info("\n--- Experiment Results ---")
    for strategy, stats in results.items():
        succ = stats["successes"]
        fail = stats["failures"]
        lats = stats["latencies"]
        p50 = statistics.median(lats) if lats else 0
        p95 = statistics.quantiles(lats, n=20)[18] if len(lats) > 20 else max(lats)
        co2 = stats["co2"]
        cost = stats["cost"]
        
        print(f"\nStrategy: {strategy}")
        print(f"Success Rate: {succ}/{succ+fail} ({(succ/(succ+fail))*100:.1f}%)")
        print(f"Latency p50: {p50:.2f}s, p95: {p95:.2f}s")
        print(f"Estimated CO2e: {co2:.4f}g")
        print(f"Cost: ${cost:.4f}")
        
    # Save raw data
    with open("experiment_results.json", "w") as f:
        json.dump(results, f, indent=2)
    logger.info("\nRaw data saved to experiment_results.json for reproducibility.")

if __name__ == "__main__":
    asyncio.run(run_routing_experiment())
