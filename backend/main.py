from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import time
import logging
import asyncio
from jose import JWTError, jwt
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from auth import auth_db, SECRET_KEY, ALGORITHM  # noqa: E402
from ledger import ledger  # noqa: E402
from routers.auth import router as auth_router  # noqa: E402
from routers.orgs import router as orgs_router  # noqa: E402
from routers.analytics import router as analytics_router  # noqa: E402
from routers.webhooks import router as webhooks_router  # noqa: E402
from routers.chat import router as chat_router  # noqa: E402
from routers.misc import router as misc_router  # noqa: E402
from rate_limit import rate_limiter  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EcoQuery")

RATE_LIMIT_DURATION = 60
def rate_limit_key(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = jwt.decode(auth[7:], SECRET_KEY, algorithms=[ALGORITHM])
            return payload.get("sub", request.client.host or "unknown")
        except JWTError:
            pass
    return request.client.host or "unknown"


def rate_limit_policy(path: str) -> int:
    if path.startswith("/api/chat"):
        return 30
    if path.startswith("/api/auth/login"):
        return 10
    if path.startswith(("/api/auth/signup", "/api/auth/forgot-password", "/api/contact")):
        return 5
    if "/api-key" in path:
        return 10
    return 30


async def rate_limit_middleware(request: Request, call_next):
    applied_limit = rate_limit_policy(request.url.path)
    remaining = applied_limit
    if request.url.path.startswith("/api/") and request.method != "GET":
        key = f"{rate_limit_key(request)}:{request.method}:{request.url.path}"
        limit = applied_limit
        if request.url.path.startswith("/api/chat") and not (
            request.headers.get("Authorization", "").startswith("Bearer ")
            or request.cookies.get("ecoquery_access_token")
        ):
            limit = 5
        applied_limit = limit
        allowed, remaining = await rate_limiter.allow(key, limit, RATE_LIMIT_DURATION)
        now = time.time()
        if not allowed:
            from fastapi.responses import JSONResponse
            resp = JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})
            resp.headers["X-RateLimit-Limit"] = str(limit)
            resp.headers["X-RateLimit-Remaining"] = "0"
            resp.headers["X-RateLimit-Reset"] = str(int(now + RATE_LIMIT_DURATION))
            return resp
    start = time.time()
    response = await call_next(request)
    elapsed = round((time.time() - start) * 1000)
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed}ms)")
    if request.url.path.startswith("/api/"):
        response.headers["X-RateLimit-Limit"] = str(applied_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + RATE_LIMIT_DURATION))
    return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting EcoQuery backend...")

    required_vars = ["JWT_SECRET", "MONGODB_URL"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        logger.error(f"Missing required env vars: {', '.join(missing)}")
        raise RuntimeError(f"Missing required production configuration: {', '.join(missing)}")

    redis_ready = await rate_limiter.connect()
    if os.getenv("RENDER") and not redis_ready:
        logger.warning("REDIS_URL is missing or unreachable; using in-process rate limiting")

    jwt_secret = os.getenv("JWT_SECRET", "")
    mongo_url = os.getenv("MONGODB_URL", "")
    if len(jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 characters")
    if any(value in mongo_url.lower() for value in ("placeholder", "your_", "localhost", "example.com")):
        raise RuntimeError("MONGODB_URL must point to a configured production database")
    encryption_key = os.getenv("KEY_ENCRYPTION_KEY") or jwt_secret
    if os.getenv("RENDER") and not os.getenv("KEY_ENCRYPTION_KEY"):
        logger.warning("KEY_ENCRYPTION_KEY is unset; encrypting provider keys with JWT_SECRET")
    if os.getenv("RENDER") and len(encryption_key) < 32:
        raise RuntimeError("KEY_ENCRYPTION_KEY (or JWT_SECRET fallback) must contain at least 32 characters")
        
    provider_keys = ["OPENROUTER_API_KEY", "GROK_API_KEY", "GOOGLE_API_KEY"]
    if not any(os.getenv(v) for v in provider_keys):
        logger.error("Missing all provider credentials")
        raise RuntimeError("Missing all provider credentials")

    await ledger.connect()
    await auth_db.connect()
    from response_cache import response_cache
    await response_cache.init_from_db()

    em_key = os.getenv("ELECTRICITY_MAPS_API_KEY", "")
    if em_key:
        logger.info("Electricity Maps API key found — real-time carbon data enabled")
    else:
        logger.info("No Electricity Maps API key — using mock carbon data")

    async def cleanup_otps():
        while True:
            await asyncio.sleep(300)
            from email_service import otp_store
            otp_store.cleanup()

    otp_task = asyncio.create_task(cleanup_otps())

    yield

    otp_task.cancel()
    await rate_limiter.close()
    logger.info("Shutting down EcoQuery backend...")

api_docs_enabled = os.getenv("ENABLE_API_DOCS", "false").lower() == "true"
app = FastAPI(
    title="EcoQuery Backend",
    lifespan=lifespan,
    docs_url="/docs" if api_docs_enabled else None,
    redoc_url="/redoc" if api_docs_enabled else None,
    openapi_url="/openapi.json" if api_docs_enabled else None,
)

configured_origins = {
    origin.strip().rstrip("/")
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
}
configured_origins.update({
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://eco2query.vercel.app",
})

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(configured_origins),
    allow_origin_regex=r"https://[a-zA-Z0-9-]+\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(rate_limit_middleware)


async def security_headers_middleware(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.cookies.get("ecoquery_access_token"):
        origin = request.headers.get("Origin", "")
        allowed = origin in configured_origins or origin.startswith("https://") and origin.endswith(".vercel.app")
        if origin and not allowed:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=403, content={"detail": "CSRF origin rejected"})
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


app.middleware("http")(security_headers_middleware)

app.include_router(auth_router)
app.include_router(orgs_router)
app.include_router(analytics_router)
app.include_router(webhooks_router)
app.include_router(chat_router)
app.include_router(misc_router)


@app.get("/")
async def root():
    docs_message = " Swagger UI: /docs." if api_docs_enabled else " API documentation is disabled in production."
    return {"message": f"EcoQuery API.{docs_message} Frontend: https://eco2query.vercel.app"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
