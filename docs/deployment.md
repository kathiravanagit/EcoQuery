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
- **Revision identity:** `/api/health` resolves `APP_VERSION`/Render's commit
  metadata and otherwise the checked-out Git revision. It no longer reports
  `dev` as a production version. Record the returned `version` with deploy
  and incident logs.
- **Provider deadline:** `PROVIDER_TIMEOUT_SECONDS` defaults to 25 seconds and
  is clamped to the platform-safe 5–25 second range. This leaves time for
  provider failover before Render closes a request. The streaming client also
  retries only transport failures with the same idempotency key.

### Provider Fallback Behavior
EcoQuery seamlessly routes across providers. Failover order is `openrouter` → `google` → `grok`: OpenRouter's catalogue models are free, the Google failover is cheap, and xAI's Grok is billed per token, so the paid provider is only reached when both free routes fail. Grok is a failover rather than a selectable model — it never appears in the model catalogue. If every provider fails, the system returns a 503 error with structured JSON and lineage. The frontend gracefully handles this or automatically retries with a fallback provider.

### Independent provider verification

Provider configuration is not evidence that a key can complete a request.
`python scripts/provider_diagnostics.py` performs a redacted, one-shot
completion probe and reports `ok`, `empty_response`, or a typed failure
without printing credentials. The manual GitHub Actions workflow
**Provider completion probes** runs the same check with the
`OPENROUTER_API_KEY`, `GOOGLE_API_KEY`, and `GROK_API_KEY` repository secrets
and fails unless all three independently return text. Run it after rotating
keys or changing provider model configuration.

### Credential cleanup

The local `backend/keys.db` file is intentionally ignored and must never be
copied into a deployment artifact. Remove any historical copy and rotate every
credential that appeared in it; the application reseeds only the current
environment credentials at startup. A fresh deployment should start with no
local database file and secrets supplied by Render.

### Carbon and energy provenance

Cloud emissions remain estimates: provider energy telemetry is not available to
EcoQuery. Electricity Maps values are labelled live only when that zone
successfully answers; otherwise the API explicitly labels the IEA 2024 static
baseline or a stale cached observation. Local NVML/RAPL readings are measured
only as a counter delta between the request's opening and closing samples;
without an opening counter they are rejected rather than attributing lifetime
GPU energy to one request. Zero-energy measurements carry zero uncertainty
instead of a contradictory nonzero relative band.

## 4. Backup & Restore

### Taking a backup

```bash
bash scripts/backup-mongo.sh          # needs mongodump and MONGODB_URL
```

Writes `backups/ecoquery_<timestamp>/` (gzip). `backups/` is gitignored, so a
dump never enters the repository.

The script refuses to start without `MONGODB_URL`, and fails if the dump
contains no collections. Both checks exist because `mongodump` exits `0`
whether it wrote a database or nothing at all — an empty backup and a healthy
one are indistinguishable from `$?` alone.

### Testing that backups restore

```bash
python scripts/verify_backup_restore.py     # needs mongodump + mongorestore
```

Exit `0` means the round trip held; `1` means it did not; `2` means the drill
could not run at all. It runs in CI on every push (`backup-restore-drill`).

The drill seeds a throwaway database with documents shaped like the real ones
plus their indexes, dumps it with the same `mongodump` the runbook uses,
**drops the source**, restores into a second throwaway database, and compares
every document and index field for field. Dropping the source first is what
makes the test meaningful: from that moment the dump is the only copy that
can possibly answer for the data.

Scope, stated plainly so this does not read as more than it is:

- It proves the **procedure** round-trips — tools, flags, gzip path, index
  metadata, namespace remapping.
- It does **not** prove that a particular file under `backups/` is complete.
  That artifact came from production and the drill never reads production
  data. To validate a specific dump, restore it into a scratch database and
  count what comes back.
- It cannot touch `ecoquery`. Both databases have fixed names
  (`ecoquery_drill_src` / `ecoquery_drill_dst`), `--db` overrides whatever
  database the URI carries, and the restore remaps namespaces with
  `--nsFrom`/`--nsTo`. A non-loopback server additionally requires
  `--allow-remote`.

### Restoring — a human decision

This overwrites live data. Rehearse it before you need it; a restore
rehearsed for the first time during an incident is a second incident.

```bash
mongorestore --uri="$MONGODB_URL" --gzip --drop --dir=backups/ecoquery_<timestamp>
mongosh "$MONGODB_URL" --eval 'db.users.countDocuments()'
```

`--drop` is load-bearing rather than a convenience flag. Without it every
document fails on a duplicate `_id`, and `mongorestore` reports
*0 restored / N failed* while still exiting `0` — success on the terminal,
nothing in the database. Count afterwards regardless of what it printed.
