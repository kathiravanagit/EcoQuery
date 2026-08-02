# EcoQuery

**AIML Domain Project** — Carbon-Aware AI Query Routing & Integrity Verification

A consumer-side middleware powered by AI/ML that optimizes LLM API requests for environmental sustainability by routeing queries to the greenest available data center in real-time, while independently verifying that the requested model wasn't silently substituted.

**Live:** [eco2query.vercel.app](https://eco2query.vercel.app) · **Backend:** [ecoquery.onrender.com](https://ecoquery.onrender.com)

---

## Problem Statement

Large Language Models (LLMs) are increasingly central to AI applications, but their inference costs — both financial and environmental — are significant and largely invisible to users. Carbon intensity varies 30x across data regions (13 g CO₂/kWh in Sweden vs 380 g CO₂/kWh in Virginia), and consumers have no way to route queries intelligently or verify that the model they requested was actually used.

This project addresses two core AIML challenges:
1. **Sustainable AI**: Making LLM usage carbon-aware and environmentally responsible
2. **Model Integrity**: Verifying that LLM API responses match the requested model (no silent substitution)

## Solution

EcoQuery sits between your application and LLM providers. It leverages AI/ML techniques to:
- **Classify query complexity** using an LLM-powered classifier (GPT-4o-mini)
- **Predict carbon impact** by querying real-time power grid data across 13 regions
- **Route intelligently** to the most suitable model+region pair based on eco/performance preferences
- **Verify integrity** of responses via TPS analysis and SHA-256 hashing — a black-box AIML verification approach
- **Log everything** to a tamper-proof audit trail for compliance and analysis
- **Translate CO₂ savings** into real-world equivalents for user engagement

---

## Key Features

### AI-Powered Query Classification
- **GPT-4o-mini classifier**: LLM-powered complexity detection (not keyword-based)
- **Heuristic fallback**: Structural analysis (counts clauses, question marks, code blocks) — works even if LLM is unavailable
- **Multi-tier routing**: Matches query complexity to optimal model tier (green/balanced/performance)

### Carbon-Aware Routing
- **Real-time data**: Electricity Maps API (300+ zones) + IEA 2024 static baselines
- **13 regions**: Ireland, London, Paris, Frankfurt, Stockholm, N. Virginia, N. California, Oregon, Mumbai, Tokyo, Singapore, Montreal, São Paulo
- **Routing modes**: Eco (carbon-first) or Performance (latency-first)
- **Energy profiling**: Hydro/Wind/Solar breakdown per region with AI-powered source estimation

### AIML Integrity Verification
- **TPS analysis**: Measures token-per-second throughput using trained baselines per model
- **Latency verification**: Compares response time against statistically computed baselines
- **Integrity hashing**: SHA-256 hash of verification parameters for tamper-evident logging
- **Short-response handling**: Skips verification for <50 tokens to prevent false positives (adaptive thresholding)

### Dashboard & Gamification (AI-Enhanced)
- **Real-time feed**: WebSocket updates for every routed query
- **CO₂ equivalents**: Trees absorbed, driving km, LED hours, phone charges
- **8 badge types**: First Step → Planet Guardian progression
- **Leaderboard**: Ranked by CO₂ saved (AI-computed rankings)
- **Analytics**: Line charts (queries over time), pie charts (tier distribution), real-time anomaly detection

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

| Layer | Technology | AIML Relevance |
|-------|------------|----------------|
| Frontend | React 19, Vite 8, TypeScript | SPA with code splitting |
| UI Framework | Framer Motion, Recharts, Lucide | Animations, data visualization |
| Backend | FastAPI, Uvicorn | Async Python API server |
| Database | MongoDB Atlas | NoSQL document store |
| Caching | Redis (optional) + in-memory | ML training data cache pattern |
| AI/ML Models | GPT-4o-mini (OpenRouter), TokenReply fallback | Query classifier + routing optimizer |
| APIs | Electricity Maps, OpenRouter, TokenReply | Real-time carbon + LLM routing data |
| Auth | JWT + Google OAuth | Secure authentication |
| CI/CD | GitHub Actions | Automated testing + deployment |
| Deploy | Vercel + Render | Cloud hosting |

### AI/ML Components
- **Query Classifier**: GPT-4o-mini (async) with structural heuristic fallback
- **Carbon Estimator**: Multi-source ML-trained baselines (IEA 2024) + real-time API
- **Anomaly Detection**: Statistical TPS/latency baseline comparison with adaptive thresholds
- **Energy Source Profiling**: AI-powered carbon intensity → energy source mapping
- **Routing Optimizer**: Multi-factor decision engine combining cost, latency, and carbon

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
TOKENREPLY_API_KEY=...            # TokenReply fallback (optional)
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

## Carbon-Aware Proxy (Self-Hosted VPS)

EcoQuery supports routing LLM requests through a self-hosted VPS for **real carbon-aware region pinning**. This is the only way to guarantee your inference runs in a green region.

### Free VPS Setup (Oracle Cloud)

Oracle Cloud offers **Always Free** ARM instances — no credit card, no time limit.

**1. Create a free account**
1. Go to https://cloud.oracle.com/free
2. Sign up (select **Pay As You Go** — Always Free resources stay free)
3. Verify email

**2. Create an ARM instance**
1. Compute → Instances → Create Instance
2. Name: `ecoquery-vps`
3. Image: Ubuntu 24.04 (aarch64)
4. Shape: **VM.Standard.A1.Flex** (4 OCPUs, 24 GB RAM — free)
5. Region: **Frankfurt** (eu-frankfurt-1) or **Amsterdam** (eu-amsterdam-1)
6. Add SSH key
7. Create

**3. Install Ollama**
```bash
ssh ubuntu@YOUR_INSTANCE_IP
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.2
```

**4. Open port 11434**
```bash
# In Oracle Cloud console: Networking → Virtual Cloud Networks → your VCN
# → Security Lists → Add Ingress Rule:
#   Source CIDR: 0.0.0.0/0
#   Destination Port: 11434
```

**5. Set env vars on Render**
```
OLLAMA_BASE_URL=http://YOUR_INSTANCE_IP:11434
OLLAMA_REGION=eu-frankfurt-1
```

### Multi-Region Setup

Deploy VPS instances in multiple green regions for automatic failover:

```
OLLAMA_ENDPOINTS=http://ip1:11434:eu-frankfurt-1,http://ip2:11434:eu-north-1
```

The proxy auto-routes to the greenest available VPS based on real-time carbon intensity.

### Fallback Chain

If all VPS instances are unavailable, requests fall back through:
1. Ollama VPS (self-hosted, greenest)
2. AWS Bedrock (region-pinned)
3. Google Vertex AI (region-pinned)
4. TokenReply (fallback provider, OpenAI-compatible)
5. OpenRouter (primary provider)

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
Push or PR to `main` → GitHub Actions runs:
1. **Backend:** `ruff` lint + `pytest`
2. **Frontend:** `typecheck` + `vitest` tests + `npm run build`
3. **Deploy:** Vercel (frontend) + Render (backend)

### Monitoring & Uptime

Render free tier sleeps after ~15 min of inactivity. To keep the backend warm before a demo:
- Set up **UptimeRobot** (free) to ping `https://ecoquery.onrender.com/docs` every 5 minutes
- This also catches silent crashes overnight

### MongoDB Backup

Before any major demo or defense, run:
```bash
bash scripts/backup-mongo.sh
```
This exports all user data, query ledger, and contacts from Atlas.

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

### AIML Domain Project
- **Domain**: Artificial Intelligence and Machine Learning
- **Focus**: Sustainable AI, LLM optimization, model integrity verification
- **Built for**: College project submission (2025-26 Odd Semester)

---
