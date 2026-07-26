# EcoQuery

**Carbon-aware AI query routing** — intelligently route LLM queries to the most eco-friendly model and data center region without sacrificing quality. Built for the Smart India Hackathon.

## Features

- **Smart Routing** — Routes each query to the optimal model based on query complexity and real-time regional carbon intensity (Electricity Maps API)
- **15 Models Across 3 Tiers** — Green (local/Groq/lightweight), Balanced, Performance (GPT-4.5, Claude Opus)
- **Provider Integrity Verification** — TPS-based detection of model substitution (e.g., GPT-4.5 served as GPT-4o-mini)
- **Real-time Dashboard** — Live WebSocket feed, analytics charts (Recharts), CO₂ savings tracking, API cost breakdown
- **JWT Auth** — Email/password + Google OAuth + password reset + role-based admin panel
- **Audit Ledger** — Every query logged to MongoDB with verification status, carbon impact, and cost
- **Teams & Orgs** — Shared API keys, member management, org-level routing
- **Admin Panel** — User management, role toggling, system stats, search + pagination
- **Code Splitting** — React.lazy + Suspense (main chunk 265 KB gzipped)
- **PWA** — Offline service worker, manifest for installable app
- **Toast Notifications** — Animated toast system replacing `alert()`
- **Accessible** — aria-labels, form labels, semantic HTML
- **Responsive** — Mobile breakpoints at 768px and 480px

## Architecture

```
eco-carbon/
├── frontend/                  # React 19 SPA (Vite 8)
│   ├── src/
│   │   ├── components/        # Navbar, Footer, LiveDemo, ErrorBoundary, Skeleton, ConfirmModal, ProfileMenu
│   │   ├── context/           # AuthContext, ToastContext
│   │   ├── pages/             # Dashboard, Login, Signup, Profile, Admin, About, Contact, Pricing, etc.
│   │   └── test/              # 26 tests (vitest + testing-library)
│   ├── public/                # manifest.json, sw.js, Whitepaper.pdf
│   └── package.json
├── backend/                   # FastAPI server
│   ├── main.py                # App entry, CORS, rate limiting, request logging, lifespan
│   ├── auth.py                # User model, JWT, password hashing, MongoDB auth_db
│   ├── routers/
│   │   ├── auth.py            # Login, signup, Google OAuth, profile, password reset
│   │   ├── chat.py            # Carbon-routed chat endpoint + verification + ledger
│   │   ├── admin.py           # User management, system stats
│   │   ├── orgs.py            # Organizations, invites, shared keys
│   │   ├── analytics.py       # Time-series analytics, CSV/JSON export
│   │   ├── webhooks.py        # Webhook CRUD + event firing
│   │   └── misc.py            # Models, health, audit log, user stats, cert, WebSocket
│   ├── carbon.py              # Electricity Maps API client (8 regions)
│   ├── router.py              # Model/region selection logic
│   ├── classifier.py          # Heuristic + optional ML query classification
│   ├── verifier.py            # TPS-based provider integrity checks
│   ├── ledger.py              # MongoDB audit trail
│   ├── email_service.py       # SMTP email with console mock fallback
│   ├── websocket_manager.py   # Per-user WebSocket broadcast
│   ├── models.py              # 15 model definitions with carbon scores
│   └── schemas.py             # Pydantic request/response models
├── .github/workflows/deploy.yml  # CI/CD (Vercel + Render)
├── render.yaml                # Render Blueprint
├── vercel.json                # Vercel config
└── .env                       # API keys (not committed)
```

## Quick Start

### Prerequisites

- Node.js 22+
- Python 3.12+
- MongoDB (recommended — some features degrade without it)

### Setup

```bash
git clone <repo-url>
cd eco-carbon

# Backend
cd backend
pip install -r requirements.txt
cd ..

# Frontend
cd frontend
npm install
cd ..
```

### Environment (.env)

```env
JWT_SECRET=your-secret-key-change-in-production
OPENAI_API_KEY=sk-or-...         # OpenRouter key (auto-detected)
ELECTRICITY_MAPS_API_KEY=em_...  # Optional — mock data without it
MONGODB_URL=mongodb://localhost:27017/ecoquery  # Optional
GOOGLE_CLIENT_ID=...             # Optional — Google OAuth
GOOGLE_CLIENT_SECRET=...         # Optional — Google OAuth

### Run

```bash
# Terminal 1 — Backend (port 8000)
cd backend && uvicorn main:app --reload

# Terminal 2 — Frontend (port 5173)
cd frontend && npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

## Tests

```bash
# Frontend (26 tests)
cd frontend && npm test

# Backend
cd backend && python -m pytest --maxfail=1 -v
```

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/signup` | No | Create account |
| `POST` | `/api/auth/login` | No | Sign in |
| `GET` | `/api/auth/google` | No | Google OAuth redirect |
| `GET` | `/api/auth/me` | Yes | Current user profile |
| `PATCH` | `/api/auth/profile` | Yes | Update display name |
| `PATCH` | `/api/auth/password` | Yes | Change password |
| `DELETE` | `/api/auth/account` | Yes | Delete account |
| `POST` | `/api/auth/forgot-password` | No | Send reset email |
| `POST` | `/api/auth/reset-password` | No | Reset with token |
| `POST` | `/api/chat` | No | Carbon-routed query |
| `GET` | `/api/models` | No | List 15 models |
| `GET` | `/api/health` | No | Deep health (MongoDB + EM API) |
| `GET` | `/api/audit` | Yes | Paginated audit log |
| `GET` | `/api/user/stats` | Yes | User aggregate stats |
| `GET` | `/api/user/certificate` | Yes | Green badge data |
| `GET` | `/api/user/api-key` | Yes | Get API key |
| `POST` | `/api/user/api-key` | Yes | Generate new API key |
| `GET` | `/api/user/analytics` | Yes | Time-series analytics |
| `GET` | `/api/user/export` | Yes | Export CSV/JSON |
| `POST` | `/api/orgs/create` | Yes | Create organization |
| `GET` | `/api/orgs` | Yes | List user orgs |
| `GET` | `/api/orgs/{id}` | Yes | Org details |
| `POST` | `/api/orgs/{id}/invite` | Yes | Invite member |
| `DELETE` | `/api/orgs/{id}/members/{email}` | Yes | Remove member |
| `POST` | `/api/orgs/{id}/api-key` | Yes | Generate org key |
| `POST` | `/api/webhooks` | Yes | Create webhook |
| `GET` | `/api/webhooks` | Yes | List webhooks |
| `DELETE` | `/api/webhooks/{id}` | Yes | Delete webhook |
| `GET` | `/api/admin/users` | Admin | List users (paginated) |
| `GET` | `/api/admin/stats` | Admin | System stats |
| `PATCH` | `/api/admin/users/{email}` | Admin | Update role/status |
| `WS` | `/ws?token=` | Yes | Real-time query events |

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `JWT_SECRET` | **Yes** | JWT signing secret |
| `OPENAI_API_KEY` | **Yes** | OpenAI or OpenRouter (sk-or-) key |
| `ELECTRICITY_MAPS_API_KEY` | No | Real carbon data (mock fallback) |
| `MONGODB_URL` | No | MongoDB URI (default: `mongodb://localhost:27017/ecoquery`) |
| `GOOGLE_CLIENT_ID` | No | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | No | Google OAuth secret |
| `SMTP_HOST` | No | SMTP for password reset emails |
| `SMTP_PORT` | No | Default: 587 |
| `SMTP_USER` | No | SMTP username |
| `SMTP_PASS` | No | SMTP password |
| `FRONTEND_URL` | No | For reset links (default: `http://localhost:5173`) |

## Deployment

### Frontend → Vercel

1. Push repo to GitHub
2. Import project in Vercel → set root to `frontend/`
3. Add env var `VITE_API_URL` pointing to your Render backend URL
4. Deploy

### Backend → Render

1. Connect GitHub repo to Render
2. Use `render.yaml` (Blueprints) or create a Web Service manually:
   - Runtime: Python
   - Build: `pip install -r backend/requirements.txt`
   - Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
3. Set all env vars from the table above
4. Deploy

### CI/CD (GitHub Actions)

Push to `main` automatically runs lint + tests, then deploys frontend to Vercel and backend to Render. Requires `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, and `RENDER_DEPLOY_HOOK_URL` in GitHub secrets.

## Tech Stack

**Frontend:** React 19, Vite 8, TypeScript, Framer Motion, Lucide Icons, React Router 7, Recharts, Vitest + Testing Library

**Backend:** FastAPI, Uvicorn, OpenAI SDK, Motor (MongoDB), python-jose (JWT), bcrypt, httpx

**ML:** DistilBERT zero-shot classification via HuggingFace Transformers (optional — heuristic fallback built-in)

**Infrastructure:** Vercel (frontend), Render (backend), MongoDB Atlas, Electricity Maps API, OpenRouter API
