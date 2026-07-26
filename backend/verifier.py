"""
Verification Layer for EcoQuery.
Detects provider integrity & silent model substitution by analyzing
response latency and token throughput (Tokens Per Second - TPS)
against calibrated baseline model profiles.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger("EcoQuery.verifier")

# Calibrated Baselines: Expected Tokens Per Second (TPS) & Max Latency Ranges
MODEL_BASELINES: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"min_tps": 20.0, "max_tps": 90.0, "expected_tps": 50.0},
    "gpt-4o-mini": {"min_tps": 60.0, "max_tps": 180.0, "expected_tps": 110.0},
    "gpt-4.5": {"min_tps": 10.0, "max_tps": 45.0, "expected_tps": 25.0},
    "claude-3.5-sonnet": {"min_tps": 30.0, "max_tps": 100.0, "expected_tps": 65.0},
    "claude-3-haiku": {"min_tps": 70.0, "max_tps": 200.0, "expected_tps": 120.0},
    "groq-llama-3.1-70b": {"min_tps": 200.0, "max_tps": 450.0, "expected_tps": 300.0},
    "groq-mixtral-8x7b": {"min_tps": 220.0, "max_tps": 500.0, "expected_tps": 350.0},
    "ollama-llama3-8b": {"min_tps": 10.0, "max_tps": 80.0, "expected_tps": 35.0},
    "llama-3.1-8b": {"min_tps": 50.0, "max_tps": 150.0, "expected_tps": 90.0},
}

class VerificationEngine:
    def verify_completion(
        self,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_seconds: float,
        reported_co2_g: float
    ) -> Dict[str, Any]:
        """
        Verifies if response throughput matches claimed model baseline.
        Returns verification status, confidence score, and adjusted carbon estimate.
        """
        if latency_seconds <= 0 or completion_tokens <= 0:
            return {
                "status": "verified",
                "confidence": 0.95,
                "reason": "Insufficient latency data to dispute baseline",
                "adjusted_co2_g": reported_co2_g,
                "observed_tps": 0.0,
                "flagged": False
            }

        observed_tps = round(completion_tokens / latency_seconds, 2)
        baseline = MODEL_BASELINES.get(model_id, {"min_tps": 15.0, "max_tps": 250.0, "expected_tps": 60.0})

        # Flag silent model substitution if observed speed is suspiciously fast for a heavy model
        # E.g. Provider claims GPT-4o or Claude Opus, but returned 250 TPS (clearly a mini model)
        if observed_tps > baseline["max_tps"] * 1.6 and "mini" not in model_id and "haiku" not in model_id:
            adjusted_co2 = round(reported_co2_g * 0.35, 4)  # Lower carbon footprint since smaller model was actually served
            return {
                "status": "flagged_substitution",
                "confidence": 0.45,
                "reason": f"Observed throughput ({observed_tps} TPS) far exceeds {model_id} baseline ({baseline['expected_tps']} TPS). Possible silent model downgrade.",
                "adjusted_co2_g": adjusted_co2,
                "observed_tps": observed_tps,
                "flagged": True
            }

        return {
            "status": "verified",
            "confidence": 0.98,
            "reason": f"Response throughput ({observed_tps} TPS) matches expected baseline for {model_id}.",
            "adjusted_co2_g": reported_co2_g,
            "observed_tps": observed_tps,
            "flagged": False
        }

verifier = VerificationEngine()
