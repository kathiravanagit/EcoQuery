"""2x2 model/region ablation over an experiment JSONL artifact."""

from __future__ import annotations

import json
import statistics
from pathlib import Path


def summarize(results: str | Path, output: str | Path) -> dict:
    rows = [json.loads(line) for line in Path(results).read_text(encoding="utf-8").splitlines() if line.strip()]
    cells: dict[str, list[float]] = {}
    for row in rows:
        cell = row.get("ablation_cell")
        if cell:
            cells.setdefault(cell, []).append(float(row.get("est_co2_g", 0)))
    means = {cell: statistics.mean(values) for cell, values in cells.items() if values}
    result = {
        "cells": means,
        "interpretation": "Report main effects and interaction only when all four cells are populated.",
        "main_effect_model": None,
        "main_effect_region": None,
        "interaction": None,
    }
    if all(cell in means for cell in ("A", "B", "C", "D")):
        result["main_effect_model"] = ((means["B"] + means["D"]) / 2) - ((means["A"] + means["C"]) / 2)
        result["main_effect_region"] = ((means["C"] + means["D"]) / 2) - ((means["A"] + means["B"]) / 2)
        result["interaction"] = means["A"] - means["B"] - means["C"] + means["D"]
    Path(output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
