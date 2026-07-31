from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import time
import logging
from jose import JWTError, jwt

from auth import auth_db, SECRET_KEY, ALGORITHM
from ledger import ledger
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EcoQuery")

RATE_LIMIT_DURATION = 60
RATE_LIMIT_MAX = 30
_rate_store: dict[str, list[float]] = {}


def rate_limit_key(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = jwt.decode(auth[7:], SECRET_KEY, algorithms=[ALGORITHM])
            return payload.get("sub", request.client.host or "unknown")
        except JWTError:
            pass
    return request.client.host or "unknown"


async def rate_limit_middleware(request: Request, call_next):
    remaining = RATE_LIMIT_MAX
    if request.url.path.startswith("/api/") and request.method != "GET":
        key = rate_limit_key(request)
        now = time.time()
        window = _rate_store.setdefault(key, [])
        window[:] = [t for t in window if now - t < RATE_LIMIT_DURATION]
        remaining = max(0, RATE_LIMIT_MAX - len(window))
        if len(window) >= RATE_LIMIT_MAX:
            from fastapi.responses import JSONResponse
            resp = JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})
            resp.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_MAX)
            resp.headers["X-RateLimit-Remaining"] = "0"
            resp.headers["X-RateLimit-Reset"] = str(int(now + RATE_LIMIT_DURATION))
            return resp
        window.append(now)
    start = time.time()
    response = await call_next(request)
    elapsed = round((time.time() - start) * 1000)
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed}ms)")
    if request.url.path.startswith("/api/"):
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_MAX)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + RATE_LIMIT_DURATION))
    return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting EcoQuery backend...")

    required_vars = ["JWT_SECRET", "OPENAI_API_KEY"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        logger.warning(f"Missing env vars: {', '.join(missing)}")

    await ledger.connect()
    await auth_db.connect()

    em_key = os.getenv("ELECTRICITY_MAPS_API_KEY", "")
    if em_key:
        logger.info("Electricity Maps API key found — real-time carbon data enabled")
    else:
        logger.info("No Electricity Maps API key — using mock carbon data")

    yield
    logger.info("Shutting down EcoQuery backend...")

app = FastAPI(title="EcoQuery Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(rate_limit_middleware)

# ─── Include Routers ──────────────────────────────────────────────
from routers.auth import router as auth_router
from routers.orgs import router as orgs_router
from routers.analytics import router as analytics_router
from routers.webhooks import router as webhooks_router
from routers.admin import router as admin_router
from routers.chat import router as chat_router
from routers.misc import router as misc_router
from routers.proxy import router as proxy_router
from routers.ollama import router as ollama_router

app.include_router(auth_router)
app.include_router(orgs_router)
app.include_router(analytics_router)
app.include_router(webhooks_router)
app.include_router(admin_router)
app.include_router(chat_router)
app.include_router(misc_router)
app.include_router(proxy_router)
app.include_router(ollama_router)


@app.get("/")
async def root():
    return {"message": "EcoQuery API — see /docs for Swagger UI or visit http://localhost:5173 for the frontend"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
