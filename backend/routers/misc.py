from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime, timezone
import secrets
import os
import httpx
from jose import JWTError, jwt

from auth import SECRET_KEY, ALGORITHM, get_current_user, get_admin_user
from ledger import ledger
from models import CARBON_MODELS
from websocket_manager import ws_manager
from carbon import get_carbon_optimal_region
router = APIRouter(tags=["misc"])


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


@router.get("/api/health")
async def health():
    from auth import auth_db
    checks = {
        "status": "ok",
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
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get("https://api.electricitymap.org/v3/carbon-intensity/latest?zone=SE", headers={"auth-token": em_key})
                checks["electricity_maps_reachable"] = r.status_code == 200
        except Exception:
            checks["electricity_maps_reachable"] = False
    or_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    checks["openrouter_configured"] = or_key.startswith("sk-or-")
    checks["openai_configured"] = bool(or_key) and not or_key.startswith("sk-or-")
    if not checks["ledger_connected"] or not checks["auth_db_connected"]:
        checks["status"] = "degraded"
    return checks


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
        logger.error(f"Audit endpoint error: {e}", exc_info=True)
        return {"records": [], "count": 0, "total": 0, "error": str(e)}


@router.get("/api/stats")
async def get_stats():
    return await ledger.get_stats()


@router.get("/api/analytics")
async def get_analytics(current_user: dict = Depends(get_current_user), days: int = 30):
    return await ledger.get_analytics(user_email=current_user["email"], days=days)


@router.get("/api/leaderboard")
async def get_leaderboard():
    return {"leaderboard": await ledger.get_leaderboard(limit=20)}


@router.get("/api/user/badges")
async def get_user_badges(current_user: dict = Depends(get_current_user)):
    badges = await ledger.get_user_badges(current_user["email"])
    return {"badges": badges}


@router.get("/api/user/stats")
async def get_user_stats(current_user: dict = Depends(get_current_user)):
    records, _ = await ledger.get_audit_log(limit=1000, skip=0, user_email=current_user["email"])
    total = len(records)
    co2 = sum(r.get("co2_saved_vs_baseline", 0) for r in records)
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
            "methodology": "Real-time grid carbon intensity via Electricity Maps API",
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
    green_queries = sum(1 for r in records if r.get("model_tier") == "green")
    return {
        "user": current_user["email"],
        "display_name": current_user.get("display_name", ""),
        "total_queries": total_queries,
        "total_co2_saved_g": round(total_co2, 3),
        "green_query_percent": round((green_queries / total_queries * 100), 1) if total_queries else 0,
        "certificate": (
            f"EcoQuery Celebrates You!\n"
            f"========================\n"
            f"User: {current_user.get('display_name', current_user['email'])}\n"
            f"Email: {current_user['email']}\n"
            f"Queries Routed: {total_queries}\n"
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
