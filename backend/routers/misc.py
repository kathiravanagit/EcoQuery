from fastapi import APIRouter, Depends, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from datetime import datetime, timezone
from hashlib import sha256
import secrets
import os
import time
import asyncio
import httpx
from jose import JWTError, jwt

from auth import SECRET_KEY, ALGORITHM, get_current_user, get_admin_user
from ledger import ledger
from models import CARBON_MODELS
from websocket_manager import ws_manager
from carbon import get_carbon_optimal_region
router = APIRouter(tags=["misc"])

# Set once at import so `/api/health` can report whether this process is a
# fresh deploy or one that has been serving for days.
_PROCESS_STARTED_AT = time.time()


class ContactRequest(BaseModel):
    name: str
    email: str
    message: str


@router.post("/api/contact")
async def contact(req: ContactRequest):
    if ledger.available and ledger.db is not None:
        await ledger.db.contacts.insert_one({
            "name": req.name,
            "email": req.email,
            "message": req.message,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "read": False,
        })
    return {"success": True, "message": "Message received! We'll get back to you within 24 hours."}


@router.get("/api/contacts")
async def get_contacts(current_user: dict = Depends(get_admin_user)):
    if not ledger.available or ledger.db is None:
        return {"messages": [], "count": 0}
    cursor = ledger.db.contacts.find().sort("created_at", -1).limit(100)
    messages = await cursor.to_list(100)
    for m in messages:
        m["_id"] = str(m["_id"])
    return {"messages": messages, "count": len(messages)}


async def _get_api_key(email: str) -> str:
    from auth import auth_db
    if auth_db.available and auth_db.collection is not None:
        user = await auth_db.collection.find_one({"email": email}, {"api_key": 1})
        return (user or {}).get("api_key", "")
    return ""


async def _set_api_key(email: str, key: str):
    from auth import auth_db
    if auth_db.available and auth_db.collection is not None:
        await auth_db.collection.update_one({"email": email}, {"$set": {"api_key": key}})


@router.get("/api/models")
async def get_models():
    return {"models": CARBON_MODELS}


@router.get("/api/carbon/regions")
async def get_carbon_regions():
    region = await get_carbon_optimal_region()
    return region


@router.get("/health")
async def service_health():
    """Minimal liveness endpoint for Render and load balancers."""
    return {"status": "ok", "service_alive": True}


@router.get("/api/health")
async def health(response: Response):
    """Readiness and diagnostics for operators and load balancers.

    Returns 200 while the process can still serve traffic (even if a
    dependency is degraded) and **503 only when nothing works** — no
    persistence *and* no provider — so a balancer can pull an instance
    without restarting it over a transient blip. Every probe is time-bounded
    (see the 3 s cap on the grid-data call) so a hung upstream cannot hang the
    health check itself.
    """
    from auth import auth_db
    from key_manager import key_manager
    from circuit_breaker import provider_breaker

    probe_started = time.perf_counter()
    checks = {
        "status": "ok",
        "service_alive": True,
        "ready": True,
        "version": os.getenv("APP_VERSION", "dev"),
        "started_at": datetime.fromtimestamp(_PROCESS_STARTED_AT, tz=timezone.utc).isoformat(),
        "uptime_s": round(time.time() - _PROCESS_STARTED_AT, 1),
        "database_connected": bool(ledger.available and auth_db.available),
        "carbon_source_reachable": False,
        "provider_configured": any(os.getenv(key) for key in ("OPENROUTER_API_KEY", "GOOGLE_API_KEY")),
        "ledger_connected": ledger.available,
        "auth_db_connected": auth_db.available,
    }
    if auth_db.available:
        try:
            await auth_db.client.admin.command("ping")
            checks["mongo_ping"] = "ok"
        except Exception:
            checks["mongo_ping"] = "error"
    em_key = os.getenv("ELECTRICITY_MAPS_API_KEY", "")
    checks["electricity_maps_configured"] = bool(em_key)
    if em_key:
        try:
            async def _probe() -> int:
                async with httpx.AsyncClient(timeout=3) as client:
                    r = await client.get(
                        "https://api.electricitymap.org/v3/carbon-intensity/latest?zone=SE",
                        headers={"auth-token": em_key},
                        timeout=httpx.Timeout(3),
                    )
                    return r.status_code

            status = await asyncio.wait_for(_probe(), timeout=3)
            checks["electricity_maps_reachable"] = status == 200
            checks["carbon_source_reachable"] = status == 200
        except Exception:
            checks["electricity_maps_reachable"] = False
    or_key = os.getenv("OPENROUTER_API_KEY", "")
    checks["openrouter_configured"] = or_key.startswith("sk-or-")

    # How many usable credentials each provider actually has. This replaces the
    # two fields that used to report `null` unconditionally: the answer is
    # cheap to read and is what determines whether a chat can be served.
    # Only counts are reported — never a key or a prefix of one.
    try:
        grouped = key_manager.get_all_providers_keys()
        checks["provider_keys"] = {name: len(items) for name, items in grouped.items()}
    except Exception:
        checks["provider_keys"] = {}
    # Per-provider breakers, so an operator can see that a vendor is being
    # skipped without reconstructing it from logs. Empty until this process
    # has actually tried one: no evidence, no verdict.
    checks["provider_circuit_breakers"] = provider_breaker.snapshot()
    checks["provider_ready"] = bool(
        any(checks["provider_keys"].values()) or checks["provider_configured"]
    )

    database_connected = bool(ledger.available and auth_db.available)
    if not database_connected or not checks["provider_ready"]:
        checks["status"] = "degraded"
    # Nothing can be authenticated or recorded *and* no model can be called:
    # the API cannot complete a single request, so fail readiness outright.
    if not database_connected and not checks["provider_ready"]:
        checks["status"] = "error"
        checks["ready"] = False

    if not checks["ready"]:
        response.status_code = 503
    checks["probe_duration_ms"] = round((time.perf_counter() - probe_started) * 1000, 1)
    return checks


@router.get("/api/admin/provider-health")
async def provider_health(current_user: dict = Depends(get_admin_user)):
    from providers import provider_router
    return await provider_router.check_health()


@router.get("/api/audit")
async def get_audit(
    current_user: dict = Depends(get_current_user),
    limit: int = 50,
    skip: int = 0,
    q: str = "",
    model: str = "",
    tier: str = "",
    sort: str = "timestamp",
    date_from: str = "",
    date_to: str = "",
):
    try:
        records, total = await ledger.get_audit_log(
            limit=limit, skip=skip, user_email=current_user["email"],
            q=q, model=model, tier=tier, sort=sort,
            date_from=date_from, date_to=date_to,
        )
        return {"records": records, "count": len(records), "total": total}
    except Exception as e:
        import logging
        logger = logging.getLogger("EcoQuery.misc")
        # Full traceback stays server-side; the raw exception text can carry
        # connection details and must not reach the client.
        logger.error(f"Audit endpoint error: {e}", exc_info=True)
        return {
            "records": [],
            "count": 0,
            "total": 0,
            "error": "The audit log could not be read right now. Please try again.",
        }


@router.get("/api/audit/verify")
async def verify_audit_chain(current_user: dict = Depends(get_current_user)):
    return await ledger.verify_user_chain(current_user["email"])


@router.get("/api/stats")
async def get_stats():
    return await ledger.get_stats()


@router.get("/api/analytics")
async def get_analytics(current_user: dict = Depends(get_current_user), days: int = 30):
    return await ledger.get_analytics(user_email=current_user["email"], days=days)


def _leaderboard_label(email: str, display_name: str) -> str:
    """Public label for one leaderboard row. Never the address itself.

    `/api/leaderboard` needs no credentials, so returning `user_email` next to
    that person's activity would let anyone enumerate who uses the service.
    A display name is what a leaderboard should show — but signup accepts any
    free text and the Google fallback uses the address as the name, so anything
    that looks like an address falls through to a non-reversible handle.
    """
    name = (display_name or "").strip()
    if name and "@" not in name:
        return name[:40]
    return "user_" + sha256(email.encode("utf-8")).hexdigest()[:8]


@router.get("/api/leaderboard")
async def get_leaderboard():
    """Top users by CO₂ saved, de-identified.

    Addresses stay server-side; only the display name (or a stable handle when
    there is no usable name) is published alongside the aggregate.
    """
    rows = await ledger.get_leaderboard(limit=20)
    addresses = [row["email"] for row in rows]

    names: dict[str, str] = {}
    if addresses:
        # Imported lazily like the other auth_db reads in this module.
        from auth import auth_db

        if auth_db.available and auth_db.collection is not None:
            docs = await auth_db.collection.find(
                {"email": {"$in": addresses}},
                {"email": 1, "display_name": 1},
            ).to_list(len(addresses))
            names = {
                doc["email"]: doc.get("display_name", "")
                for doc in docs
                if doc.get("email")
            }

    return {
        "leaderboard": [
            {
                "user": _leaderboard_label(row["email"], names.get(row["email"], "")),
                "total_co2_saved_g": row["total_co2_saved_g"],
                "total_queries": row["total_queries"],
            }
            for row in rows
        ]
    }


@router.get("/api/user/badges")
async def get_user_badges(current_user: dict = Depends(get_current_user)):
    badges = await ledger.get_user_badges(current_user["email"])
    return {"badges": badges}


@router.get("/api/user/stats")
async def get_user_stats(current_user: dict = Depends(get_current_user)):
    records, _ = await ledger.get_audit_log(limit=1000, skip=0, user_email=current_user["email"])
    total = len(records)
    co2 = sum(r.get("co2_saved_vs_baseline", 0) for r in records)
    co2_emitted = sum(r.get("co2_estimated", 0) for r in records)
    cost = sum(r.get("api_cost", 0) for r in records)
    queries_by_tier: dict[str, int] = {}
    queries_by_model: dict[str, int] = {}
    total_latency = 0.0
    flagged = 0
    for r in records:
        t = r.get("tier", "unknown")
        queries_by_tier[t] = queries_by_tier.get(t, 0) + 1
        m = r.get("model_used", "unknown")
        queries_by_model[m] = queries_by_model.get(m, 0) + 1
        total_latency += r.get("latency_seconds", 0)
        if r.get("verification_status") == "flagged_substitution":
            flagged += 1
    return {
        "total_queries": total,
        "total_co2_saved_g": round(co2, 3),
        "total_co2_emitted_g": round(co2_emitted, 3),
        "total_api_cost": round(cost, 6),
        "avg_latency_s": round(total_latency / total, 3) if total else 0,
        "queries_by_tier": queries_by_tier,
        "queries_by_model": queries_by_model,
        "flagged_queries": flagged,
        "latest_queries": records[:10]
    }


@router.get("/api/user/sustainability-report")
async def get_sustainability_report(current_user: dict = Depends(get_current_user)):
    records, _ = await ledger.get_audit_log(limit=10000, skip=0, user_email=current_user["email"])
    total = len(records)
    total_co2 = sum(r.get("co2_saved_vs_baseline", 0) for r in records)
    total_co2_emitted = sum(r.get("co2_estimated", 0) for r in records)
    total_cost = sum(r.get("api_cost", 0) for r in records)
    green = sum(1 for r in records if r.get("model_tier") == "green")
    balanced = sum(1 for r in records if r.get("model_tier") == "balanced")
    performance = sum(1 for r in records if r.get("model_tier") == "performance")
    regions = {}
    for r in records:
        reg = r.get("region", "unknown")
        regions[reg] = regions.get(reg, 0) + 1
    models = {}
    for r in records:
        model = r.get("model_used", "unknown")
        models[model] = models.get(model, 0) + 1

    report = {
        "report_title": "EcoQuery Sustainability Report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "user": current_user.get("display_name", current_user["email"]),
        "email": current_user["email"],
        "period": f"Last {total} queries",
        "summary": {
            "total_queries": total,
            "total_co2_saved_g": round(total_co2, 4),
            "total_co2_saved_kg": round(total_co2 / 1000, 6),
            "total_co2_emitted_g": round(total_co2_emitted, 4),
            "total_co2_emitted_kg": round(total_co2_emitted / 1000, 6),
            "total_api_cost_usd": round(total_cost, 6),
            "green_query_percent": round((green / total * 100), 1) if total else 0,
            "avg_queries_per_day": round(total / 30, 1),
        },
        "query_distribution": {
            "green_tier": green,
            "balanced_tier": balanced,
            "performance_tier": performance,
        },
        "region_usage": regions,
        "model_usage": models,
        "environmental_impact": {
            "co2_equivalent": f"{round(total_co2 * 1000, 1)} mg CO₂ saved",
            "trees_equivalent_days": round(total_co2 / 21.0, 6),
            "car_km_equivalent": round(total_co2 / 0.21, 2),
            "smartphone_charges": round(total_co2 / 0.008, 1),
            "led_bulb_hours": round(total_co2 / 0.01, 0),
            "flight_minutes": round(total_co2 / 255.0, 4),
        },
        "ghg_protocol_alignment": {
            "scope": "Scope 3 (Downstream value chain)",
            "category": "Cloud computing carbon footprint reduction",
            "methodology": (
                "Per-query grid carbon intensity: Electricity Maps where the live "
                "feed answered, IEA 2024 annual baselines otherwise. Totals are "
                "modelled estimates summed over stored queries, not metered energy."
            ),
            "verification": "TPS-based model substitution detection with integrity hashing",
            "standard": "Aligned with ISO 14064-1 GHG accounting",
        },
        "text_report": (
            f"{'='*50}\n"
            f"  EcoQuery Sustainability Report\n"
            f"{'='*50}\n"
            f"  User: {current_user.get('display_name', current_user['email'])}\n"
            f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"{'='*50}\n\n"
            f"  QUERIES ROUTED: {total}\n"
            f"  CO₂ EMITTED: {round(total_co2_emitted, 4)}g ({round(total_co2_emitted/1000, 6)} kg)\n"
            f"  CO₂ SAVED: {round(total_co2, 4)}g ({round(total_co2/1000, 6)} kg)\n"
            f"  API COST: ${round(total_cost, 6)}\n"
            f"  GREEN QUERY RATE: {round((green / total * 100), 1) if total else 0}%\n\n"
            f"  TIER BREAKDOWN:\n"
            f"    Green: {green} | Balanced: {balanced} | Performance: {performance}\n\n"
            f"  ENVIRONMENTAL EQUIVALENTS:\n"
            f"    Trees absorbed (days): {round(total_co2 / 21.0, 6)}\n"
            f"    Car travel saved: {round(total_co2 / 0.21, 2)} km\n"
            f"    Smartphone charges: {round(total_co2 / 0.008, 1)}\n"
            f"    LED bulb hours: {round(total_co2 / 0.01, 0)}\n"
            f"    Flight minutes avoided: {round(total_co2 / 255.0, 4)}\n\n"
            f"  GHG PROTOCOL: Scope 3, ISO 14064-1 aligned\n"
            f"  VERIFICATION: TPS-based integrity check with SHA-256 hashing\n"
            f"{'='*50}\n"
        )
    }
    return report


@router.post("/api/user/api-key")
async def generate_api_key(current_user: dict = Depends(get_current_user)):
    key = f"eq_{secrets.token_hex(24)}"
    await _set_api_key(current_user["email"], key)
    return {"api_key": key, "message": "Use this key in the Authorization header: Bearer <key>"}


@router.get("/api/user/api-key")
async def get_api_key(current_user: dict = Depends(get_current_user)):
    key = await _get_api_key(current_user["email"])
    if not key:
        return {"api_key": "", "message": "No API key generated yet. POST /api/user/api-key to create one."}
    return {"api_key": key}


@router.post("/api/user/api-key/revoke")
async def revoke_api_key(current_user: dict = Depends(get_current_user)):
    await _set_api_key(current_user["email"], "")
    return {"message": "API key revoked."}


@router.get("/api/user/api-key/stats")
async def get_api_key_stats(current_user: dict = Depends(get_current_user)):
    records, _ = await ledger.get_audit_log(limit=10000, skip=0, user_email=current_user["email"])
    total = len(records)
    co2 = sum(r.get("co2_saved_vs_baseline", 0) for r in records)
    cost = sum(r.get("api_cost", 0) for r in records)
    return {
        "queries": total,
        "co2_saved_g": round(co2, 3),
        "cost": round(cost, 6),
    }


@router.get("/api/user/certificate")
async def get_certificate(current_user: dict = Depends(get_current_user)):
    records, _ = await ledger.get_audit_log(limit=10000, skip=0, user_email=current_user["email"])
    total_queries = len(records)
    total_co2 = sum(r.get("co2_saved_vs_baseline", 0) for r in records)
    total_co2_emitted = sum(r.get("co2_estimated", 0) for r in records)
    green_queries = sum(1 for r in records if r.get("model_tier") == "green")
    return {
        "user": current_user["email"],
        "display_name": current_user.get("display_name", ""),
        "total_queries": total_queries,
        "total_co2_saved_g": round(total_co2, 3),
        "total_co2_emitted_g": round(total_co2_emitted, 3),
        "green_query_percent": round((green_queries / total_queries * 100), 1) if total_queries else 0,
        "certificate": (
            f"EcoQuery Celebrates You!\n"
            f"========================\n"
            f"User: {current_user.get('display_name', current_user['email'])}\n"
            f"Email: {current_user['email']}\n"
            f"Queries Routed: {total_queries}\n"
            f"CO\u2082 Emitted: {round(total_co2_emitted, 3)}g\n"
            f"CO\u2082 Saved: {round(total_co2, 3)}g\n"
            f"Green Query Rate: {round((green_queries / total_queries * 100), 1) if total_queries else 0}%\n"
            f"Issued: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"\nEvery query you route through EcoQuery makes a difference.\n"
            f"Thank you for choosing a greener AI!\n"
        )
    }


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    token = ws.query_params.get("token", "")
    if not token:
        await ws.close(code=4001)
        return
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_email = payload.get("sub", "")
        if not user_email:
            await ws.close(code=4001)
            return
    except JWTError:
        await ws.close(code=4001)
        return
    await ws_manager.connect(ws, user_email)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws, user_email)
