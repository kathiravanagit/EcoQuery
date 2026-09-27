from fastapi import APIRouter, Depends
from datetime import datetime, timezone
import secrets
import logging
import httpx
import socket
import ipaddress
from urllib.parse import urlparse
from fastapi import HTTPException

from schemas import WebhookCreateRequest
from auth import get_current_user
from shared import WEBHOOKS

logger = logging.getLogger("EcoQuery.webhooks")
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        if parsed.port and parsed.port not in (80, 443):
            return False
        
        hostname = parsed.hostname
        if not hostname:
            return False
        
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast:
            return False
        if str(ip) == "169.254.169.254":
            return False
            
        return True
    except Exception:
        return False


@router.post("")
async def create_webhook(req: WebhookCreateRequest, current_user: dict = Depends(get_current_user)):
    if not is_safe_url(req.url):
        raise HTTPException(status_code=400, detail="Invalid or insecure webhook URL.")

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
                if not is_safe_url(wh["url"]):
                    continue
                async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
                    await client.post(wh["url"], json={"event": event, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()})
            except Exception as e:
                logger.warning(f"Webhook {wh['id']} failed: {e}")
