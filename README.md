# EcoQuery

Carbon-aware AI query routing — route every LLM query to the greenest model and data center in real-time.

**Live:** [eco2query.vercel.app](https://eco2query.vercel.app) · **Backend:** [ecoquery.onrender.com](https://ecoquery.onrender.com)

## What It Does

EcoQuery sits between your app and LLM providers. It classifies query complexity, picks the lowest-carbon model+region pair, verifies the response wasn't silently substituted, and logs everything to a tamper-proof audit trail.

**Routing Modes:**
- **Eco Mode** — carbon-first, picks greenest model/region
- **Performance Mode** — latency-first, picks fastest model

## Key Features

| Feature | How |
|---|---|
| Carbon-aware routing | Real-time Electricity Maps API + IEA static baselines (8 regions) |
| Query classification | LLM-powered classifier (gpt-4o-mini) with heuristic fallback |
| Model substitution detection | TPS/latency baseline comparison + SHA-256 integrity hashing |
| Audit ledger | Every query logged to MongoDB with verification status |
| Gamification | 8 badge types, leaderboard ranked by CO₂ saved |
| Sustainability reports | GHG Protocol Scope 3, ISO 14064-1 aligned, downloadable |
| Dashboard | Real-time WebSocket feed, analytics charts, tier breakdown pie chart |

## Tech Stack

| Layer | Stack |
|---|---|
| Frontend | React 19, Vite 8, TypeScript, Framer Motion, Recharts |
| Backend | FastAPI, Uvicorn, Motor (MongoDB), python-jose (JWT) |
| Data | MongoDB Atlas, Electricity Maps API, OpenRouter API |
| Deploy | Vercel (frontend), Render (backend), GitHub Actions CI/CD |

## Quick Start

```bash
git clone https://github.com/kathiravanagit/EcoQuery.git
cd eco-carbon

# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

**Required env vars** (backend `.env`):
```
JWT_SECRET=your-secret
OPENAI_API_KEY=sk-or-...          # OpenRouter key
ELECTRICITY_MAPS_API_KEY=em_...   # Optional (mock fallback)
MONGODB_URL=mongodb+srv://...     # Optional (degrades without)
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/chat` | Carbon-routed query (accepts `mode: eco|performance`) |
| `GET` | `/api/models` | List 15 models with carbon scores |
| `GET` | `/api/health` | Deep health (MongoDB + Electricity Maps) |
| `GET` | `/api/analytics` | Daily breakdown, tier/model distribution |
| `GET` | `/api/leaderboard` | Top users by CO₂ saved |
| `GET` | `/api/user/sustainability-report` | GHG-aligned exportable report |
| `GET` | `/api/user/badges` | Earned gamification badges |
| `POST` | `/api/contact` | Submit contact form |
| `WS` | `/ws?token=` | Real-time query events |
| `POST` | `/api/auth/signup` | Create account |
| `POST` | `/api/auth/login` | Sign in |
| `GET` | `/api/auth/google` | Google OAuth |

Full list: 35+ endpoints across auth, chat, admin, orgs, webhooks.

## CI/CD

Push to `main` → GitHub Actions runs:
1. **Backend:** `ruff` lint + `pytest`
2. **Frontend:** `typecheck` + `vitest` tests
3. **Deploy:** Vercel (frontend) + Render (backend)

## Testing

```bash
cd frontend && npm test    # 26 tests (vitest + testing-library)
cd backend && python -m pytest --maxfail=1 -v
```

## License

MIT
