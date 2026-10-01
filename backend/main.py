from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
import os
import time
import json
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

# Anonymous callers get a tighter budget than authenticated ones on every
# write endpoint. Chat is stricter still (see `rate_limit_policy`).
ANONYMOUS_DEFAULT_LIMIT = 10


def rate_limit_identity(request: Request) -> tuple[str, bool]:
    """Return (rate-limit bucket, is_authenticated).

    Only a token that actually *decodes* counts as authentication. The previous
    check tested for the literal `Bearer ` prefix, so attaching a garbage token
    upgraded an anonymous caller to the authenticated chat budget (30/min
    instead of 5/min) while still being bucketed by IP — a self-service bypass.

    Both the Authorization header and the session cookie are accepted, and
    neither value is ever written to a log or a store.
    """
    candidates = []
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and auth[7:].strip():
        candidates.append(auth[7:].strip())
    cookie = request.cookies.get("ecoquery_access_token", "")
    if cookie:
        candidates.append(cookie)

    for candidate in candidates:
        try:
            payload = jwt.decode(candidate, SECRET_KEY, algorithms=[ALGORITHM])
        except JWTError:
            continue
        subject = payload.get("sub")
        if subject:
            return str(subject), True

    host = request.client.host if request.client else "anonymous"
    return host, False


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
        subject, authenticated = rate_limit_identity(request)
        key = f"{subject}:{request.method}:{request.url.path}"
        limit = applied_limit
        if request.url.path.startswith("/api/chat"):
            limit = 5 if not authenticated else applied_limit
        elif not authenticated:
            limit = min(applied_limit, ANONYMOUS_DEFAULT_LIMIT)
        applied_limit = limit
        allowed, remaining = await rate_limiter.allow(key, limit, RATE_LIMIT_DURATION)
        now = time.time()
        if not allowed:
            resp = JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Try again later.",
                    "error_code": "RATE_LIMITED",
                    "message": f"Too many requests. Try again in {RATE_LIMIT_DURATION} seconds.",
                    "success": False,
                },
            )
            resp.headers["X-RateLimit-Limit"] = str(limit)
            resp.headers["X-RateLimit-Remaining"] = "0"
            resp.headers["X-RateLimit-Reset"] = str(int(now + RATE_LIMIT_DURATION))
            resp.headers["Retry-After"] = str(RATE_LIMIT_DURATION)
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

# Origins are an explicit allowlist only. A broad regex (e.g. any *.vercel.app)
# would let any Vercel project read credentialed responses, so we deliberately
# do not configure allow_origin_regex. Every deployed frontend origin must be
# listed in ALLOWED_ORIGINS. The middleware itself is registered last (see
# below) so that it is the *outermost* one and every response we generate —
# including 413/429/403 — carries the CORS headers a browser needs to read it.

app.middleware("http")(rate_limit_middleware)


async def security_headers_middleware(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.cookies.get("ecoquery_access_token"):
        origin = request.headers.get("Origin", "")
        # Cookie-authenticated writes must come from a known origin. Mirrors the
        # CORS allowlist exactly — no wildcard suffix matching.
        if origin and origin not in configured_origins:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=403, content={"detail": "CSRF origin rejected"})
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.middleware("http")(security_headers_middleware)


# ── Request body size limit ──────────────────────────────────────────────────
# Starlette will buffer an unbounded request body, so a single chunked POST
# could exhaust a worker. 25 MB accommodates the documented 3 × 5 MB images
# plus JSON overhead while still capping abuse.
MAX_REQUEST_BODY_BYTES = 25_000_000
BODY_TOO_LARGE_MESSAGE = (
    f"Request body is too large (limit {MAX_REQUEST_BODY_BYTES // 1_000_000} MB)."
)


def _body_too_large_payload() -> bytes:
    return json.dumps({
        "detail": BODY_TOO_LARGE_MESSAGE,
        "error_code": "PAYLOAD_TOO_LARGE",
        "message": BODY_TOO_LARGE_MESSAGE,
        "success": False,
    }).encode()


class RequestBodyTooLarge(Exception):
    def __init__(self, limit: int):
        super().__init__(f"request body exceeds {limit} bytes")
        self.limit = limit


class BodySizeLimitMiddleware:
    """Reject oversized bodies before they are read into memory.

    `Content-Length` is checked first, which covers normal clients for free.
    Clients that omit it (chunked encoding) are caught by a counting wrapper
    around `receive`, so the limit holds either way. Because this sits between
    ServerErrorMiddleware and ExceptionMiddleware, an oversized body is turned
    into a clean 413 JSON response instead of an unhandled 500.
    """

    def __init__(self, app, max_bytes: int = MAX_REQUEST_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def _reject(self, send) -> None:
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(_body_too_large_payload())).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": _body_too_large_payload()})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        declared = headers.get("content-length", "")
        if declared.isdigit() and int(declared) > self.max_bytes:
            await self._reject(send)
            return

        received = 0
        response_started = False

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise RequestBodyTooLarge(self.max_bytes)
            return message

        async def tracking_send(message):
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except RequestBodyTooLarge:
            logger.warning(
                "Rejected oversized request body on %s (limit %s bytes)",
                scope.get("path", "?"),
                self.max_bytes,
            )
            if not response_started:
                await self._reject(send)
            # Otherwise the response is already committed and all we can do is
            # stop reading; the ASGI server closes the connection.


# Registered last so it is the outermost middleware after CORS (see below).
app.add_middleware(BodySizeLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(configured_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global error handling ────────────────────────────────────────────────────
# The client only ever receives a stable, human-readable payload. Stack traces
# and exception text (which can carry connection strings or key fragments) are
# logged server-side only.
def _status_error_code(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }.get(status_code, "REQUEST_FAILED")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Keep `detail` (the frontend reads it) while adding a machine-readable code.

    Registered against Starlette's base class so router-level 404s are covered
    too — FastAPI's own HTTPException subclasses it.
    """
    detail = exc.detail
    message = detail if isinstance(detail, str) else str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": detail,
            "error_code": _status_error_code(exc.status_code),
            "message": message,
            "success": False,
        },
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic failures become a single readable sentence, not a raw dump."""
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    field = location or "request body"
    message = first.get("msg", "is invalid")
    return JSONResponse(
        status_code=422,
        content={
            "detail": f"Invalid value for {field}: {message}",
            "error_code": "VALIDATION_ERROR",
            "message": f"Invalid value for {field}: {message}",
            "success": False,
            "fields": [
                {
                    "field": ".".join(str(p) for p in err.get("loc", ())),
                    "message": err.get("msg", "is invalid"),
                }
                for err in exc.errors()[:5]
            ],
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all: log the traceback, return a clean 500."""
    logger.error(
        "Unhandled error on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Something went wrong on our side. Please try again.",
            "error_code": "INTERNAL_ERROR",
            "message": "Something went wrong on our side. Please try again.",
            "success": False,
        },
    )

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
