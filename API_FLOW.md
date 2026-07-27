# EcoQuery API Flow

Plain-language walkthrough of how a query moves through the system.

## 1. User sends a query

```
POST /api/chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "Explain quantum computing",
  "mode": "eco"           // "eco" or "performance"
}
```

## 2. What happens inside the backend

### Step A — Classifier
The query is analyzed to decide how complex it is. Simple rules check:
- Word count (>80 words → complex)
- Presence of reasoning words ("explain", "compare", "why")
- Code blocks, math symbols

**Output:** `simple`, `medium`, or `complex`

### Step B — Carbon Estimator
The system fetches the latest carbon intensity (g CO₂/kWh) from 13 cloud regions:
- **Primary source:** Electricity Maps API (real-time grid data)
- **Fallback:** IEA 2024 annual averages (static)

The data is cached for 10 minutes (Redis or in-memory).

### Step C — Router
Based on query complexity + carbon data + selected mode:
- **Eco mode:** Pick the greenest region that has a suitable model
- **Performance mode:** Pick the fastest region with a suitable model

Available models: 15 across 4 providers (OpenAI, Anthropic, Google, Groq, Meta)

### Step D — LLM Call
The query is forwarded to OpenRouter API with the selected model + region.

### Step E — Verifier
The response is checked for model substitution:
- **TPS check:** Tokens per second compared against estimated thresholds for the requested model
- **Latency check:** Response time compared against expected range
- **Short-response skip:** Responses under 50 tokens are not checked (prevents false flags)
- **Hash:** SHA-256 hash of (model_id, tokens, latency) stored in audit log

### Step F — Audit Ledger
Everything is logged to MongoDB:
- Query text, model used, region, tier
- CO₂ saved vs baseline (475 g/kWh)
- API cost, latency, verification status
- Integrity hash

If the user has a WebSocket connection open, a real-time event is pushed to their Dashboard.

## 3. Response back to user

```json
{
  "response": "...",
  "model": "gemini-2.5-flash-lite",
  "region": "eu-north-1",
  "carbon_intensity": 13,
  "co2_saved_vs_baseline": 0.0048,
  "verification": "verified",
  "tier": "complex",
  "mode": "eco"
}
```

## 4. What the user sees

- **Hero page:** Target impact estimates (12.5 trees, 50 km, 1,250 LED hours)
- **Dashboard:** Real-time query feed via WebSocket, analytics charts, badges
- **Badges:** Auto-earned based on query count and CO₂ saved (8 badge types)
- **Sustainability report:** Downloadable GHG Protocol-aligned text report

## Key Endpoints

| Method | Path | What it does |
|--------|------|-------------|
| POST | /api/auth/signup | Create account |
| POST | /api/auth/login | Sign in |
| POST | /api/chat | Send a query (core endpoint) |
| GET | /api/models | List available models |
| GET | /api/carbon/regions | Current carbon intensity per region |
| GET | /api/user/stats | Your query statistics |
| GET | /api/user/badges | Your earned badges |
| GET | /api/leaderboard | Top users by CO₂ saved |
| GET | /api/user/sustainability-report | Download ESG report |
| WS | /ws?token= | Real-time query events |

## Data Sources

- **Carbon intensity:** Electricity Maps API (primary), IEA 2024 World Energy Outlook (fallback)
- **LLM models:** OpenRouter API (15 models across 4 providers)
- **User data:** MongoDB Atlas (free tier, 512 MB)
- **Cache:** Redis (optional, falls back to in-memory)
