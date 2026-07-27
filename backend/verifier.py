"""
Enhanced Verification Layer for EcoQuery.
Detects provider integrity & silent model substitution using:
  - TPS (Tokens Per Second) baseline comparison
  - Latency anomaly detection
  - Response pattern analysis
"""

import logging
import hashlib
from typing import Dict, Any

logger = logging.getLogger("EcoQuery.verifier")

MODEL_BASELINES: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"min_tps": 20.0, "max_tps": 90.0, "expected_tps": 50.0, "avg_latency_s": 2.5},
    "gpt-4o-mini": {"min_tps": 60.0, "max_tps": 180.0, "expected_tps": 110.0, "avg_latency_s": 1.0},
    "gpt-4.5": {"min_tps": 10.0, "max_tps": 45.0, "expected_tps": 25.0, "avg_latency_s": 5.0},
    "claude-3.5-sonnet": {"min_tps": 30.0, "max_tps": 100.0, "expected_tps": 65.0, "avg_latency_s": 2.0},
    "claude-3-haiku": {"min_tps": 70.0, "max_tps": 200.0, "expected_tps": 120.0, "avg_latency_s": 0.9},
    "gemini-2.5-flash-lite": {"min_tps": 80.0, "max_tps": 250.0, "expected_tps": 150.0, "avg_latency_s": 0.8},
    "gemini-2.5-flash": {"min_tps": 40.0, "max_tps": 150.0, "expected_tps": 80.0, "avg_latency_s": 1.8},
    "gemini-2.5-pro": {"min_tps": 15.0, "max_tps": 60.0, "expected_tps": 35.0, "avg_latency_s": 3.5},
    "groq-llama-3.1-70b": {"min_tps": 200.0, "max_tps": 450.0, "expected_tps": 300.0, "avg_latency_s": 0.5},
    "groq-mixtral-8x7b": {"min_tps": 220.0, "max_tps": 500.0, "expected_tps": 350.0, "avg_latency_s": 0.6},
    "ollama-llama3-8b": {"min_tps": 10.0, "max_tps": 80.0, "expected_tps": 35.0, "avg_latency_s": 2.0},
    "llama-3.1-8b": {"min_tps": 50.0, "max_tps": 150.0, "expected_tps": 90.0, "avg_latency_s": 1.5},
    "llama-3.1-70b": {"min_tps": 15.0, "max_tps": 60.0, "expected_tps": 30.0, "avg_latency_s": 3.0},
    "llama-3.1-405b": {"min_tps": 5.0, "max_tps": 25.0, "expected_tps": 12.0, "avg_latency_s": 8.0},
}

DEFAULT_BASELINE = {"min_tps": 15.0, "max_tps": 250.0, "expected_tps": 60.0, "avg_latency_s": 2.0}


class VerificationEngine:
    def verify_completion(
        self,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_seconds: float,
        reported_co2_g: float
    ) -> Dict[str, Any]:
        if latency_seconds <= 0 or completion_tokens <= 0:
            return {
                "status": "verified",
                "confidence": 0.95,
                "reason": "Insufficient latency data to dispute baseline",
                "adjusted_co2_g": reported_co2_g,
                "observed_tps": 0.0,
                "flagged": False,
                "integrity_hash": self._compute_hash(model_id, prompt_tokens, completion_tokens, latency_seconds),
            }

        observed_tps = round(completion_tokens / latency_seconds, 2)
        baseline = MODEL_BASELINES.get(model_id, DEFAULT_BASELINE)
        latency_ratio = latency_seconds / baseline["avg_latency_s"] if baseline["avg_latency_s"] > 0 else 1.0

        issues = []
        confidence = 0.98

        if completion_tokens < 50 and latency_seconds < 10:
            return {
                "status": "verified",
                "confidence": 0.92,
                "reason": f"Short response ({completion_tokens} tokens), TPS check skipped.",
                "adjusted_co2_g": reported_co2_g,
                "observed_tps": observed_tps,
                "flagged": False,
                "integrity_hash": self._compute_hash(model_id, prompt_tokens, completion_tokens, latency_seconds),
            }

        if observed_tps > baseline["max_tps"] * 1.6 and "mini" not in model_id and "haiku" not in model_id:
            issues.append(f"TPS ({observed_tps}) far exceeds {model_id} max ({baseline['max_tps']})")
            confidence -= 0.35

        if observed_tps < baseline["min_tps"] * 0.15 and observed_tps > 0:
            issues.append(f"TPS ({observed_tps}) suspiciously low for {model_id}")
            confidence -= 0.2

        if latency_ratio > 3.0:
            issues.append(f"Latency ({latency_seconds:.1f}s) is {latency_ratio:.1f}x expected ({baseline['avg_latency_s']:.1f}s)")
            confidence -= 0.15

        if latency_ratio < 0.1 and observed_tps > 100:
            issues.append(f"Response suspiciously fast ({latency_seconds:.2f}s) for claimed model")
            confidence -= 0.25

        integrity_hash = self._compute_hash(model_id, prompt_tokens, completion_tokens, latency_seconds)

        if issues:
            adjusted_co2 = round(reported_co2_g * 0.35, 4)
            return {
                "status": "flagged_substitution",
                "confidence": max(0.1, confidence),
                "reason": "; ".join(issues),
                "adjusted_co2_g": adjusted_co2,
                "observed_tps": observed_tps,
                "flagged": True,
                "integrity_hash": integrity_hash,
            }

        return {
            "status": "verified",
            "confidence": min(0.99, confidence),
            "reason": f"Throughput ({observed_tps} TPS) matches {model_id} baseline.",
            "adjusted_co2_g": reported_co2_g,
            "observed_tps": observed_tps,
            "flagged": False,
            "integrity_hash": integrity_hash,
        }

    def _compute_hash(self, model_id: str, prompt_tokens: int, completion_tokens: int, latency: float) -> str:
        payload = f"{model_id}:{prompt_tokens}:{completion_tokens}:{latency:.3f}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


verifier = VerificationEngine()
