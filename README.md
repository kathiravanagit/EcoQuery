# EcoQuery

**Carbon-Aware AI Query Routing & Integrity Verification**

A consumer-side middleware that routes LLM API requests to the greenest available data center in real-time, while independently verifying that the requested model wasn't silently substituted.

**Live:** [eco2query.vercel.app](https://eco2query.vercel.app) · **Backend:** [ecoquery.onrender.com](https://ecoquery.onrender.com)

---

## Problem

LLM inference costs — both financial and environmental — are significant and invisible to users. Carbon intensity varies 30x across data regions (13 g CO₂/kWh in Sweden vs 380 g CO₂/kWh in Virginia), and consumers have no way to verify that the model they requested was actually used.

## Solution

EcoQuery sits between your application and LLM providers:

- **Classify** query complexity using an LLM-powered classifier
- **Predict** carbon impact via real-time power grid data across 13 regions
- **Route** to the greenest model+region pair automatically
- **Verify** response integrity via TPS analysis and SHA-256 hashing
- **Log** everything to a tamper-proof audit trail

---

## Features

| Feature | Description |
|---------|-------------|
| Query Classification | GPT-4o-mini classifier with heuristic fallback |
| Carbon-Aware Routing | Real-time Electricity Maps API + IEA 2024 baselines |
| Green Provider Selection | Scores cloud providers by real-time carbon intensity |
| Integrity Verification | TPS analysis, latency checks, SHA-256 hashing |
| Streaming Responses | SSE-based token streaming with carbon metadata |
| API Key Auth | `eq_*` tokens for programmatic access |
| Dashboard & Analytics | Real-time feed, CO₂ equivalents, charts, leaderboard |
| Gamification | 8 badge types, leaderboards, sustainability reports |
| Organization Support | Team workspaces with member roles |
| Multi-Provider Backend | OpenRouter, Anthropic, Gemini, OpenAI, Ollama VPS |

---

## Architecture

```
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
              ┌─────▼──────┐  ┌──────────────▼┐  ┌───────▼────┐
              │Electricity │  │  LLM Providers│  │  MongoDB   │
              │ Maps API   │  │  (OpenRouter) │  │  Atlas     │
              └────────────┘  └───────────────┘  └────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, Vite 8, TypeScript, Framer Motion, Recharts |
| Backend | FastAPI, Uvicorn, Python 3.10+ |
| Database | MongoDB Atlas |
| AI/ML | GPT-4o-mini classifier, Carbon intensity ML baselines |
| APIs | Electricity Maps, OpenRouter |
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

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- MongoDB Atlas (free tier works)
- OpenRouter API key

### Setup

```bash
git clone https://github.com/kathiravanagit/EcoQuery.git
cd eco-carbon

# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env  # Edit with your keys
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
OPENAI_API_KEY=sk-or-...              # OpenRouter key
ELECTRICITY_MAPS_API_KEY=em_...       # Optional (uses static fallback)
MONGODB_URL=mongodb+srv://...         # Optional (degrades without)
ALLOWED_ORIGINS=https://eco2query.vercel.app,http://localhost:5173

# Frontend
VITE_API_URL=http://localhost:8000     # Dev
VITE_API_URL=https://ecoquery.onrender.com  # Prod
```

---

## Testing

```bash
# Backend (121 tests)
cd backend
python -m pytest tests/ -q

# Frontend
cd frontend
npx tsc --noEmit
npx vitest run
npm run build
```

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
| Carbon range | 13–380 g CO₂/kWh |
| API endpoints | 30+ |
| Backend tests | 121 |
| Security level | A- |

---

## Team

**AIML Domain Project** — College project submission (2025-26 Odd Semester)

- **Domain**: Artificial Intelligence and Machine Learning
- **Focus**: Sustainable AI, LLM optimization, model integrity verification
