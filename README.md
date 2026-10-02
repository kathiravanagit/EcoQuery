<!-- markdownlint-disable MD022 MD032 MD036 MD040 MD060 -->

# EcoQuery

## Carbon-Aware AI Query Routing & Integrity Verification

A consumer-side middleware that selects a capable AI model using carbon-intensity data and records auditable routing provenance. Vercel hosts the frontend; the FastAPI API runs on Render. CO₂e values are estimates unless telemetry or provider-reported energy is available.

See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for the estimation formula, routing policy, evaluation protocol, data-source provenance, and verification limitations.

Production configuration requires MongoDB, a strong JWT secret (32+ characters), and at least one provider key. Set `KEY_ENCRYPTION_KEY` for dedicated provider-key encryption; Render can fall back to `JWT_SECRET` if it is omitted. Set `REDIS_URL` for distributed rate limiting. Provider credentials must be rotated if they were ever committed to repository history; removing the current database file does not rewrite old Git objects.

Run `python scripts/provider_diagnostics.py` inside the deployed environment to independently test OpenRouter, Google, and Grok credentials. If temporarily validating an optional BYOK credential, set its environment variable for the command (`OPENAI_API_KEY`, `GROQ_API_KEY`, or `ANTHROPIC_API_KEY`); those keys are not part of EcoQuery's server configuration. The diagnostic reports provider, model, status, latency, and redacted failure type without printing secrets.

**Live:** [eco2query.vercel.app](https://eco2query.vercel.app) · **Backend:** [ecoquery.onrender.com](https://ecoquery.onrender.com)

---

## Problem

LLM inference costs — both financial and environmental — are significant and invisible to users. Carbon intensity varies more than 50x across data regions (13 g CO₂/kWh on the Nordic grid vs 710 g CO₂/kWh on the Indian grid), and consumers have no way to verify that the model they requested was actually used.

## Solution

EcoQuery sits between your application and LLM providers:

- **Classify** query complexity using an LLM-powered classifier
- **Predict** carbon impact via real-time power grid data across 13 regions
- **Route** to the greenest model+region pair automatically
- **Verify** response integrity via TPS analysis and SHA-256 hashing
- **Log** everything to a hash-chained, tamper-evident audit trail

---

## Features

| Feature | Description |
|---------|-------------|
| Query Classification | Trained classifier with ML fallback and heuristic rules |
| Carbon-Aware Routing | Real-time Electricity Maps API + IEA 2024 baselines |
| Green Provider Selection | Scores cloud providers by real-time carbon intensity |
| Integrity Verification | TPS analysis, latency checks, SHA-256 hashing |
| Streaming Responses | SSE-based token streaming with carbon metadata |
| API Key Auth | `eq_*` tokens for programmatic access |
| Dashboard & Analytics | Real-time feed, CO₂ equivalents, charts, leaderboard |
| Gamification | 8 badge types, leaderboards, sustainability reports |
| Organization Support | Team workspaces with member roles |
| Inference Backend | OpenRouter-backed free-tier catalog with model fallback |

---

## Architecture

```text
┌────────────┐    ┌────────────┐    ┌──────────────────┐
│   User     │───▶│  Frontend  │───▶│  Backend API     │
│   Query    │    │  React/Vite│    │  FastAPI          │
└────────────┘    └────────────┘    └────────┬─────────┘
                                             │
                                  ┌──────────▼──────────┐
                                  │   Query Pipeline    │
                                  │ 1. Classifier       │
                                  │ 2. Carbon Estimator │
                                  │ 3. Green Router     │
                                  │ 4. Response Verify  │
                                  │ 5. Audit Logging    │
                                  └──────────┬──────────┘
                                             │
                    ┌────────────────────────┼────────────┐
                    │                        │            │
              ┌─────▼──────┐  ┌──────────────▼────────────────────┐  ┌───────▼────┐
              │Electricity │  │  LLM Providers                    │  │  MongoDB   │
              │ Maps API   │  │  (OpenRouter catalog + routes)   │  │  Atlas     │
              └────────────┘  └────────────────────────────────────┘  └────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, Vite 8, TypeScript, Framer Motion, Recharts |
| Backend | FastAPI, Uvicorn, Python 3.10+ |
| Database | MongoDB Atlas |
| AI/ML | Trained classifier, Carbon intensity ML baselines |
| APIs | Electricity Maps and OpenRouter |
| Auth | JWT + Google OAuth |
| CI/CD | GitHub Actions |
| Deploy | Vercel (frontend) + Render (backend) |

---

## API Endpoints

### Core

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Carbon-routed query |
| `POST` | `/api/chat/stream` | SSE streaming response |
| `GET` | `/api/models` | List available models |
| `GET` | `/api/carbon/regions` | Real-time carbon intensity |
| `GET` | `/api/health` | Deep health check |

`POST /api/chat` requires a `Bearer` token unless `ALLOW_ANONYMOUS_CHAT=true`.
`POST /api/chat/stream` accepts anonymous callers by default so the public
homepage demo works; set `ALLOW_ANONYMOUS_CHAT_STREAM=false` to require login
there too. Anonymous callers on either endpoint get the stricter rate limit.

### Auth & User

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/auth/signup` | Create account |
| `POST` | `/api/auth/login` | Sign in (JWT) |
| `GET` | `/api/auth/google` | Google OAuth |
| `POST` | `/api/auth/forgot-password` | Request reset |
| `POST` | `/api/auth/reset-password` | Reset with token |
| `GET` | `/api/user/stats` | Query statistics |
| `GET` | `/api/user/badges` | Earned badges |
| `GET` | `/api/user/certificate` | Downloadable certificate |
| `POST` | `/api/user/api-key` | Generate API key |
| `GET` | `/api/user/export` | Export queries (CSV/JSON) |

### Analytics & Orgs

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/analytics` | Daily breakdown, tier distribution |
| `GET` | `/api/leaderboard` | Top users by CO₂ saved |
| `POST` | `/api/orgs/create` | Create organization |
| `GET` | `/api/orgs/{id}/sustainability` | Org sustainability report |
| `WS` | `/ws?token=` | Real-time query events |

### Bring your own key (BYOK)

Both chat endpoints accept optional per-provider credentials, so you can bill
your own account instead of the server's keys. Supply as many as you like on
the same request — whichever provider the router lands on will find your
credential waiting for it:

| Header | Provider |
|--------|----------|
| `X-OpenRouter-Key` | `openrouter` |
| `X-Google-Key` | `google` |
| `X-Grok-Key` | `grok` — that is **xAI**; Groq (`gsk_…`) is an unrelated company |
| `X-OpenAI-Key` | `openai` |
| `X-Groq-Key` | `groq` |
| `X-Anthropic-Key` | `anthropic` |

The original single-key form is still accepted:

| Header | Meaning |
|--------|---------|
| `X-Provider-Key` | Key for the provider named in `X-Provider` (default `openrouter`) |
| `X-Provider` | Which provider the `X-Provider-Key` belongs to: `openrouter`, `google`, `grok`, `openai`, `groq` or `anthropic` |

```bash
curl -X POST https://ecoquery.onrender.com/api/chat/stream \
  -H "X-OpenRouter-Key: $MY_OPENROUTER_KEY" \
  -H "X-Google-Key: $MY_GOOGLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "How much CO2 does a chat query emit?"}'
```

Behaviour:

- Each supplied key is tried **before** any server key for *its* provider. If
  the provider rejects it, the request transparently falls back to that
  provider's server keys — you only get an error if both are exhausted, which
  is returned as `PROVIDER_KEY_REJECTED`. Keys are independent: a rejected
  Google key never stops your OpenRouter key from being used.
- Each key is used for that one outbound call and nothing else. None is ever
  written to the key store, the usage ledger, the response cache or a log
  line; a rejected key is logged as an exception type only, because provider
  SDK errors can quote the credential back.
- An empty or oversized (>512 characters) header is treated as absent, per
  header, so one malformed value cannot silently discard the others.
- The response metadata reports `byok_used` plus a `key_source` map:

  ```json
  {
    "byok_used": true,
    "final_provider": "google",
    "key_source": {"openrouter": "server", "google": "user", "grok": "none", "openai": "none", "groq": "none", "anthropic": "none"}
  }
  ```

  `key_source` gives the credential backing each provider *for that request* —
  `user`, `server` or `none` — while `final_provider` says which one actually
  served the call. Ownership values only; a credential is never echoed back.
- OpenAI, Groq and Anthropic responses use provider/model-specific blended cost
  estimates and a catalog carbon proxy. Their metadata sets
  `api_cost_is_estimate` and `carbon_estimate_is_approximate` to `true` and
  identifies the basis used for each estimate.
- Knowledge-base and cached answers make no outbound call, so neither field is
  emitted (and it costs you nothing).
- Requests that skip the LLM entirely are unaffected; the headers only matter
  when a provider is actually called.

In the browser, unauthenticated **Dashboard → Bring Your Own Keys** holds one
key per provider in `sessionStorage`, so they die with the tab. Authenticated
users can persist keys through the dashboard: the backend encrypts each key at
rest, scopes it to the account, and never returns the plaintext key to the
browser. They are attached automatically
as the headers above and can be switched off with *Prefer my keys when
available*.

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- MongoDB Atlas (free tier works)
- OpenRouter API key via `OPENROUTER_API_KEY`
- Google API key via `GOOGLE_API_KEY` (automatic failover)
- Grok API key via `GROK_API_KEY` (last-resort failover; xAI bills per token)
- For detailed deployment and provider config, see [docs/deployment.md](docs/deployment.md)

### Setup

```bash
git clone https://github.com/kathiravanagit/EcoQuery.git
cd ecoquery

# Create .env at the REPO ROOT (backend/main.py loads ../.env), not in backend/
cp .env.example .env  # Edit with your keys

# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

### Environment Variables

```env
# Backend
JWT_SECRET=your-random-secret
OPENROUTER_API_KEY=sk-or-...          # OpenRouter key (primary provider)
GOOGLE_API_KEY=...                    # Automatic failover when OpenRouter fails
GROK_API_KEY=xai-...                  # Last-resort failover (paid: xAI credit)
GROK_MODEL=grok-4-fast                # Optional: which xAI model Grok answers on
ELECTRICITY_MAPS_API_KEY=em_...       # Optional (uses static fallback)
MONGODB_URL=mongodb+srv://...         # Optional (degrades without)
ALLOWED_ORIGINS=https://eco2query.vercel.app,http://localhost:5173
ALLOW_ANONYMOUS_CHAT=false             # POST /api/chat (Bearer API) — locked by default
ALLOW_ANONYMOUS_CHAT_STREAM=true       # POST /api/chat/stream — public homepage demo

# Frontend (set exactly one)
VITE_API_URL=http://localhost:8000     # Dev
# VITE_API_URL=https://ecoquery.onrender.com  # Prod
```

---

## Testing

```bash
# Backend (150 tests)
cd backend
python -m pytest tests/ -q

# Frontend
cd frontend
npx tsc --noEmit
npx vitest run
npm run build
```

---

## Design Decisions

### Carbon estimates and evaluation

EcoQuery reports **estimated** CO2e, not directly metered electricity use. It estimates inference energy from token count and model carbon score, then applies the selected grid intensity:

```text
Estimated CO2e = Estimated inference energy (kWh) x Grid carbon intensity (gCO2e/kWh)
```

The repository's `backend/benchmark.py` compares carbon-aware routing with always-largest and always-smallest baselines across 30 fixed prompts. Its results are a reproducible routing simulation; production claims should use matched provider experiments with measured latency, success rate, data-source provenance, and uncertainty. Full methodology and limitations are documented in [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

### Removed Features (Intentional)

| Feature | Reason Removed |
|---------|---------------|
| Admin panel | Data accessible via MongoDB Atlas directly. Removed to reduce attack surface. |
| Smart router (`smart_router.py`) | Redundant with `green_provider.py` which uses real-time Electricity Maps data. Single routing path is simpler and more maintainable. |
| Temporal shifter (`temporal_shifter.py`) | Time-based routing added complexity without measurable carbon benefit. Green provider already picks the optimal region. |
| Carbon executor (`carbon_executor.py`) | Functionality merged into `green_provider.py`. Separate module was unnecessary abstraction. |
| TokenReply provider | Returned 524 Cloudflare timeouts consistently. Unreliable for production use. |
| PDF/document upload | Free OpenRouter models don't support PDF input. Only image uploads supported via vision models. |
| Eco/Performance mode toggle | The web UI no longer exposes a mode switch: requests use the API's default `balanced` mode, which weighs carbon against latency rather than forcing an eco-only route. Performance mode was confusing and undermined the core value proposition. |

### Pinned Dependencies

All backend dependencies are pinned to exact versions in `requirements.txt` to prevent breaking changes from upstream updates.

---

## Deployment

### Vercel (Frontend)
1. Connect GitHub repo
2. Root Directory: `frontend`
3. Build: `npm run build`
4. Output: `dist`
5. Env: `VITE_API_URL`

### Render (Backend)
1. Connect GitHub repo
2. Build: `pip install -r requirements.txt`
3. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add all env vars

### CI/CD
Push to `main` triggers GitHub Actions:
1. **Backend:** ruff lint + pytest
2. **Frontend:** typecheck + vitest + build
3. **Deploy:** Vercel + Render

---

## Impact

| Metric | Value |
|--------|-------|
| Regions | 13 |
| Carbon range | 13–710 g CO₂/kWh (static IEA baselines; live Electricity Maps values are typically 28–710) |
| API endpoints | 30+ |
| Backend tests | Run `pytest` in the configured backend environment |
| Security assessment | No independent security rating claimed |

---

## Team

**AIML Domain Project** — College project submission (2025-26 Odd Semester)

- **Domain**: Artificial Intelligence and Machine Learning
- **Focus**: Sustainable AI, LLM optimization, model integrity verification

<!-- markdownlint-enable MD022 MD032 MD036 MD040 MD060 -->
