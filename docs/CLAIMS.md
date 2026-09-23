# Claims ledger

| Claim | Evidence | Confidence | Known limitation |
|---|---|---|---|
| EcoQuery estimates carbon impact from model, token, and grid inputs | `backend/carbon.py`, `docs/METHODOLOGY.md` | medium | Estimate, not metered electricity |
| Provider substitution is detected from behavioral signals | `backend/verifier.py`, `backend/experiments/verifier_eval.py` | target until labeled corpus is run | Not cryptographic model identity |
| Region-vs-model savings can be compared | `backend/experiments/live_routing.py` | target until live artifact exists | Provider availability and grid data vary |
