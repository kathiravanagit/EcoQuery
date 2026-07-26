from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from datetime import datetime, timezone
import secrets
import os
import httpx
from jose import JWTError, jwt

from auth import SECRET_KEY, ALGORITHM, get_current_user
from ledger import ledger
from models import CARBON_MODELS
from websocket_manager import ws_manager
router = APIRouter(tags=["misc"])


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
    openai_key = os.getenv("OPENAI_API_KEY", "")
    checks["openrouter_configured"] = openai_key.startswith("sk-or-")
    checks["openai_configured"] = bool(openai_key) and not openai_key.startswith("sk-or-")
    if not checks["ledger_connected"] or not checks["auth_db_connected"]:
        checks["status"] = "degraded"
    return checks


@router.get("/api/audit")
async def get_audit(current_user: dict = Depends(get_current_user), limit: int = 50, skip: int = 0):
    try:
        records = await ledger.get_audit_log(limit=limit, skip=skip, user_email=current_user["email"])
        return {"records": records, "count": len(records)}
    except Exception as e:
        import logging
        logger = logging.getLogger("EcoQuery.misc")
        logger.error(f"Audit endpoint error: {e}", exc_info=True)
        return {"records": [], "count": 0, "error": str(e)}


@router.get("/api/stats")
async def get_stats():
    return await ledger.get_stats()


@router.get("/api/user/stats")
async def get_user_stats(current_user: dict = Depends(get_current_user)):
    records = await ledger.get_audit_log(limit=1000, skip=0, user_email=current_user["email"])
    total = len(records)
    co2 = sum(r.get("co2_saved_vs_baseline", 0) for r in records)
    cost = sum(r.get("api_cost", 0) for r in records)
    queries_by_tier: dict[str, int] = {}
    for r in records:
        t = r.get("tier", "unknown")
        queries_by_tier[t] = queries_by_tier.get(t, 0) + 1
    return {
        "total_queries": total,
        "total_co2_saved_g": round(co2, 3),
        "total_api_cost": round(cost, 6),
        "queries_by_tier": queries_by_tier,
        "latest_queries": records[:10]
    }


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


@router.get("/api/user/certificate")
async def get_certificate(current_user: dict = Depends(get_current_user)):
    records = await ledger.get_audit_log(limit=10000, skip=0, user_email=current_user["email"])
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
