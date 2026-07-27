# EcoQuery

**Carbon-Aware AI Query Routing & Integrity Verification**

A consumer-side middleware that optimizes LLM API requests for environmental sustainability by routing queries to the greenest available data center in real-time, while independently verifying that the requested model wasn't silently substituted.

**Live:** [eco2query.vercel.app](https://eco2query.vercel.app) · **Backend:** [ecoquery.onrender.com](https://ecoquery.onrender.com)

---

## Problem Statement

LLM API calls consume significant energy, with carbon intensity varying 30x across regions (13 g/kWh in Sweden vs 380 g/kWh in Virginia). No existing solution provides consumers with:
1. Real-time carbon-aware routing across multiple LLM providers
2. Independent verification that the requested model was actually used
3. Actionable environmental impact metrics

## Solution

EcoQuery sits between your application and LLM providers. It:
- Classifies query complexity to match optimal model tier
- Queries real-time power grid carbon intensity across 13 regions
- Routes to the greenest suitable data center
- Verifies response integrity via TPS analysis and SHA-256 hashing
- Logs everything to a tamper-proof audit trail
- Translates CO₂ savings into real-world equivalents

---

## Key Features

### Carbon-Aware Routing
- **Real-time data**: Electricity Maps API (300+ zones) + IEA 2024 static baselines
- **13 regions**: Ireland, London, Paris, Frankfurt, Stockholm, N. Virginia, N. California, Oregon, Mumbai, Tokyo, Singapore, Montreal, São Paulo
- **Routing modes**: Eco (carbon-first) or Performance (latency-first)
- **Energy profiling**: Hydro/Wind/Solar breakdown per region

### Integrity Verification
- **TPS analysis**: Measures token-per-second throughput
- **Latency verification**: Compares response time against baselines
- **Integrity hashing**: SHA-256 hash of verification parameters
- **Short-response handling**: Skips verification for <50 tokens to prevent false positives

### Dashboard & Gamification
- **Real-time feed**: WebSocket updates for every routed query
- **CO₂ equivalents**: Trees absorbed, driving km, LED hours, phone charges
- **8 badge types**: First Step → Planet Guardian progression
- **Leaderboard**: Ranked by CO₂ saved
- **Analytics**: Line charts (queries over time), pie charts (tier distribution)

### Enterprise Features
- **Organizations**: Create teams, invite members, manage roles
- **Role-based access**: Admin, member, viewer roles
- **Org sustainability reports**: Aggregate team carbon savings
- **Org dashboard**: Team-wide statistics and model usage

### Compliance & Reporting
- **GHG Protocol**: Scope 3 alignment for downstream AI usage
- **ISO 14064-1**: Carbon accounting methodology
- **Audit trail**: Immutable ledger with SHA-256 hash chain
- **Export**: CSV, JSON, PDF sustainability reports

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      EcoQuery System                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │  User   │───▶│  Frontend    │───▶│  Backend API     │   │
│  │ Query   │    │  React/Vite  │    │  FastAPI          │   │
│  └─────────┘    └──────────────┘    └────────┬─────────┘   │
│                                               │             │
│                                    ┌──────────▼──────────┐  │
│                                    │   Query Pipeline    │  │
│                                    │                     │  │
│                                    │ 1. Classifier       │  │
│                                    │ 2. Carbon Estimator │  │
│                                    │ 3. Model Router     │  │
│                                    │ 4. Response Verify  │  │
│                                    │ 5. Audit Logging    │  │
│                                    └──────────┬──────────┘  │
│                                               │             │
│                    ┌──────────────────────────┼──────────┐  │
│                    │                          │          │  │
│              ┌─────▼─────┐  ┌────────────────▼┐  ┌─────▼──┐│
│              │Electricity│  │  OpenRouter API │  │MongoDB ││
│              │ Maps API  │  │  (LLM Providers)│  │ Atlas  ││
│              └───────────┘  └─────────────────┘  └────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | React 19, Vite 8, TypeScript | SPA with code splitting |
| UI | Framer Motion, Recharts, Lucide | Animations, charts, icons |
| Backend | FastAPI, Uvicorn | Async Python API |
| Database | MongoDB Atlas | Audit ledger, user auth |
| Caching | Redis (optional) + in-memory | Carbon intensity cache |
| APIs | Electricity Maps, OpenRouter | Carbon data, LLM routing |
| Auth | JWT + Google OAuth | Secure authentication |
| CI/CD | GitHub Actions | Lint, test, deploy |
| Deploy | Vercel + Render | Frontend + Backend |

---

## API Reference

### Core Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Carbon-routed query (accepts `mode: eco\|performance`) |
| `GET` | `/api/models` | List 15 models with carbon scores |
| `GET` | `/api/carbon/regions` | Real-time carbon intensity across 13 regions |
| `GET` | `/api/health` | Deep health check (MongoDB + Electricity Maps) |

### User Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/auth/signup` | Create account (auto-verified) |
| `POST` | `/api/auth/login` | Sign in with JWT |
| `GET` | `/api/auth/google` | Google OAuth redirect |
| `POST` | `/api/auth/forgot-password` | Request password reset |
| `POST` | `/api/auth/reset-password` | Reset password with token |
| `GET` | `/api/user/stats` | User query statistics |
| `GET` | `/api/user/badges` | Earned gamification badges |
| `GET` | `/api/user/certificate` | Downloadable certificate |
| `GET` | `/api/user/sustainability-report` | GHG-aligned report |
| `POST` | `/api/user/api-key` | Generate API key |
| `GET` | `/api/user/export` | Export queries (CSV/JSON) |

### Analytics Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/analytics` | Daily breakdown, tier/model distribution |
| `GET` | `/api/leaderboard` | Top users by CO₂ saved |
| `GET` | `/api/audit` | Recent query records |

### Organization Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/orgs/create` | Create organization |
| `GET` | `/api/orgs` | List user's organizations |
| `GET` | `/api/orgs/{id}` | Get organization details |
| `POST` | `/api/orgs/{id}/invite` | Invite member |
| `GET` | `/api/orgs/{id}/sustainability` | Org sustainability report |
| `GET` | `/api/orgs/{id}/dashboard` | Org dashboard |
| `GET` | `/api/orgs/{id}/members/roles` | Member roles |

### Admin Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/admin/users` | List all users |
| `GET` | `/api/admin/stats` | System-wide statistics |
| `POST` | `/api/admin/users/{email}/role` | Update user role |

### WebSocket

| Protocol | Path | Description |
|----------|------|-------------|
| `WS` | `/ws?token=` | Real-time query routing events |

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- MongoDB Atlas account (free tier works)
- OpenRouter API key (for LLM routing)

### Installation

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

### Required Environment Variables

```env
# Backend (.env)
JWT_SECRET=your-random-secret-string
OPENAI_API_KEY=sk-or-...           # OpenRouter key
ELECTRICITY_MAPS_API_KEY=em_...    # Optional (uses static fallback)
MONGODB_URL=mongodb+srv://...      # Optional (degrades without)
ALLOWED_ORIGINS=https://eco2query.vercel.app,http://localhost:5173
GOOGLE_CLIENT_ID=...               # Optional (Google OAuth)
GOOGLE_CLIENT_SECRET=...           # Optional (Google OAuth)
GOOGLE_REDIRECT_URI=...            # Optional (Google OAuth)
REDIS_URL=redis://...              # Optional (in-memory fallback)
```

### Frontend Environment Variables

```env
# Frontend (.env or Vercel dashboard)
VITE_API_URL=http://localhost:8000  # Development
VITE_API_URL=https://ecoquery.onrender.com  # Production
```

---

## Testing

```bash
# Frontend (26 tests)
cd frontend
npm test

# Backend
cd backend
python -m pytest --maxfail=1 -v
```

---

## Deployment

### Vercel (Frontend)
1. Connect GitHub repository
2. Set Root Directory: `frontend`
3. Build Command: `npm run build`
4. Output Directory: `dist`
5. Add environment variable: `VITE_API_URL`

### Render (Backend)
1. Connect GitHub repository
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add all environment variables from `.env.example`

### CI/CD Pipeline
Push to `main` → GitHub Actions runs:
1. **Backend:** `ruff` lint + `pytest`
2. **Frontend:** `typecheck` + `vitest` tests
3. **Deploy:** Vercel (frontend) + Render (backend)

---

## Patent Claims

See [PATENT_CLAIMS.md](PATENT_CLAIMS.md) for detailed patent claims and technical novelty.

### Core Novelty
1. **Carbon-Aware Routing**: Dynamic routing based on real-time power grid carbon intensity
2. **Integrity Verification**: TPS-based model substitution detection without provider cooperation
3. **Multi-Source Aggregation**: Real-time API + static baseline fallback for resilient carbon estimation
4. **Impact Translation**: Converting CO₂ savings to tangible real-world equivalents

---

## Impact Metrics

| Metric | Value |
|--------|-------|
| Regions covered | 13 |
| Carbon intensity range | 13–380 g CO₂/kWh |
| Models supported | 15 |
| Badge types | 8 |
| Frontend tests | 26 |
| API endpoints | 35+ |

---

## Team

Built for Smart India Hackathon 2025

---

## License

MIT
