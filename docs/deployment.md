# EcoQuery Deployment Guide

This guide distinguishes between Local, Demo, and Production environments.

## 1. Local Development
Run the app locally with live reloading for both frontend and backend.

**Environment variables (`.env` at the repository root — `backend/main.py` loads `../.env`, not `backend/.env`):**
```
MONGODB_URL=mongodb://localhost:27017/ecoquery
JWT_SECRET=local_secret_key
KEY_ENCRYPTION_KEY=local-development-secret
REDIS_URL=redis://localhost:6379/0
OPENROUTER_API_KEY=your_key
GOOGLE_API_KEY=your_key
GROK_API_KEY=your_key
```

**Run Commands:**
```bash
# Terminal 1: Backend
cd backend && uvicorn main:app --reload

# Terminal 2: Frontend
cd frontend && npm run dev
```

## 2. Demo Environment (Render / Vercel Free Tiers)
For quick sharing without strict SLAs.
- **Backend (Render):** Uses `render.yaml`. Connects to MongoDB Atlas Free Tier.
- **Frontend (Vercel):** Connects to the Render backend URL.
- **Config:** Mocked API responses can be enabled via `ECO_QUERY_TESTING=1` to save API costs.

## 3. Production Environment
Production requires secure secrets management and robust infrastructure.
- **Backend:** ECS or Google Cloud Run for auto-scaling.
- **Database:** MongoDB Atlas Dedicated cluster.
- **Security:** Secrets MUST be stored in a vault or Render secrets. Production requires a strong `JWT_SECRET` and real MongoDB/provider credentials. Set `KEY_ENCRYPTION_KEY` (32+ characters) for dedicated provider-key encryption; if it is omitted on Render, the API falls back to `JWT_SECRET`. Set `REDIS_URL` for distributed rate limiting; without it the process limiter is used. Rotate any credentials that appeared in old Git history.

### Provider Fallback Behavior
EcoQuery seamlessly routes across providers. Failover order is `openrouter` → `google` → `grok`: OpenRouter's catalogue models are free, the Google failover is cheap, and xAI's Grok is billed per token, so the paid provider is only reached when both free routes fail. Grok is a failover rather than a selectable model — it never appears in the model catalogue. If every provider fails, the system returns a 503 error with structured JSON and lineage. The frontend gracefully handles this or automatically retries with a fallback provider.
