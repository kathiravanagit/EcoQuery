"""Evaluate verifier predictions from a labeled JSONL corpus."""

from __future__ import annotations

import json
from pathlib import Path

from verifier import verifier


def evaluate(corpus: str | Path, output: str | Path) -> dict:
    rows = [json.loads(line) for line in Path(corpus).read_text(encoding="utf-8").splitlines() if line.strip()]
    matrix = {"true_positive": 0, "false_positive": 0, "true_negative": 0, "false_negative": 0}
    for row in rows:
        result = verifier.verify_completion(
            row["model_id"], row["prompt_tokens"], row["completion_tokens"],
            row.get("latency_seconds", 0), row.get("reported_co2_g", 0),
            row.get("t_first_token_s"), row.get("t_last_token_s"),
        )
        predicted = bool(result["flagged"])
        actual = bool(row["substituted"])
        key = ("true_" if predicted == actual else "false_") + ("positive" if predicted else "negative")
        matrix[key] += 1
    tp, fp = matrix["true_positive"], matrix["false_positive"]
    fn = matrix["false_negative"]
    result = {
        "samples": len(rows), "confusion_matrix": matrix,
        "precision": tp / (tp + fp) if tp + fp else 0,
        "recall": tp / (tp + fn) if tp + fn else 0,
        "false_positive_rate": fp / (fp + matrix["true_negative"]) if fp + matrix["true_negative"] else 0,
    }
    Path(output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
