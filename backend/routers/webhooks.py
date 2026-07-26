from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
import secrets
import logging
import httpx

from schemas import WebhookCreateRequest
from auth import get_current_user
from shared import WEBHOOKS

logger = logging.getLogger("EcoQuery.webhooks")
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("")
async def create_webhook(req: WebhookCreateRequest, current_user: dict = Depends(get_current_user)):
    wh = {"id": f"wh_{secrets.token_hex(8)}", "url": req.url, "events": req.events, "user_email": current_user["email"], "created_at": datetime.now(timezone.utc).isoformat(), "active": True}
    WEBHOOKS.setdefault(current_user["email"], []).append(wh)
    return {"status": "ok", "webhook": wh}


@router.get("")
async def list_webhooks(current_user: dict = Depends(get_current_user)):
    return {"webhooks": WEBHOOKS.get(current_user["email"], [])}


@router.delete("/{wh_id}")
async def delete_webhook(wh_id: str, current_user: dict = Depends(get_current_user)):
    hooks = WEBHOOKS.get(current_user["email"], [])
    WEBHOOKS[current_user["email"]] = [h for h in hooks if h["id"] != wh_id]
    return {"status": "ok"}


async def fire_webhooks(user_email: str, event: str, data: dict):
    for wh in WEBHOOKS.get(user_email, []):
        if event in wh.get("events", []) and wh.get("active"):
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    await client.post(wh["url"], json={"event": event, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()})
            except Exception as e:
                logger.warning(f"Webhook {wh['id']} failed: {e}")
