"""Generate docs/EVALUATION.md from an experiment summary artifact."""

import json
import sys
from pathlib import Path


summary = Path(sys.argv[1] if len(sys.argv) > 1 else "experiments/results/latest/summary.json")
data = json.loads(summary.read_text(encoding="utf-8"))
doc = Path("docs/EVALUATION.md")
doc.write_text(
    "# Evaluation\n\n"
    "This document is generated from an experiment artifact; it is not a hand-written result.\n\n"
    f"- Run date: `{data.get('run_date', 'unknown')}`\n"
    f"- Mode: `{data.get('mode', 'unknown')}`\n"
    f"- Samples: `{data.get('samples', 0)}`\n"
    f"- Success rate: `{data.get('success_rate', 0):.3f}`\n"
    f"- Carbon sources: `{', '.join(data.get('carbon_sources', []))}`\n",
    encoding="utf-8",
)
