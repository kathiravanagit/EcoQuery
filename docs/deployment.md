# EcoQuery Deployment Guide

This guide distinguishes between Local, Demo, and Production environments.

## 1. Local Development
Run the app locally with live reloading for both frontend and backend.

**Environment variables (`backend/.env`):**
```
MONGODB_URL=mongodb://localhost:27017/ecoquery
JWT_SECRET=local_secret_key
OPENROUTER_API_KEY=your_key
GROK_API_KEY=your_key
GOOGLE_API_KEY=your_key
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
- **Security:** Ensure `is_safe_url` is enabled for webhooks. Secrets MUST be stored in a vault (e.g. AWS Secrets Manager).

### Provider Fallback Behavior
EcoQuery seamlessly routes across providers. If a provider fails, the system returns a 503 error with structured JSON and lineage. The frontend gracefully handles this or automatically retries with a fallback provider.
