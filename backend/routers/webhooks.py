from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from urllib.parse import urlparse
import hashlib
import hmac
import ipaddress
import secrets
import socket
import logging
import httpx

from schemas import WebhookCreateRequest
from auth import get_current_user
from shared import WEBHOOKS

logger = logging.getLogger("EcoQuery.webhooks")
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host in ("localhost", "0.0.0.0", "::1"):
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port)
    except socket.gaierror:
        return False
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


def _sign_body(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@router.post("")
async def create_webhook(req: WebhookCreateRequest, current_user: dict = Depends(get_current_user)):
    if not _is_safe_url(req.url):
        raise HTTPException(status_code=422, detail="Webhook URL resolves to a private or internal address")
    secret = secrets.token_hex(32)
    wh = {
        "id": f"wh_{secrets.token_hex(8)}",
        "url": req.url,
        "events": req.events,
        "user_email": current_user["email"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "active": True,
        "secret": secret,
    }
    WEBHOOKS.setdefault(current_user["email"], []).append(wh)
    return {"status": "ok", "webhook": wh, "secret": secret}


@router.get("")
async def list_webhooks(current_user: dict = Depends(get_current_user)):
    return {"webhooks": WEBHOOKS.get(current_user["email"], [])}


@router.delete("/{wh_id}")
async def delete_webhook(wh_id: str, current_user: dict = Depends(get_current_user)):
    hooks = WEBHOOKS.get(current_user["email"], [])
    WEBHOOKS[current_user["email"]] = [h for h in hooks if h["id"] != wh_id]
    return {"status": "ok"}


async def fire_webhooks(user_email: str, event: str, data: dict):
    import json
    for wh in WEBHOOKS.get(user_email, []):
        if event in wh.get("events", []) and wh.get("active"):
            if not _is_safe_url(wh["url"]):
                logger.warning(f"Webhook {wh['id']} blocked: unsafe URL {wh['url']}")
                continue
            payload = {
                "event": event,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            body = json.dumps(payload, separators=(",", ":"), default=str).encode()
            signature = _sign_body(wh.get("secret", ""), body)
            headers = {
                "Content-Type": "application/json",
                "X-EcoQuery-Signature": f"sha256={signature}",
                "X-EcoQuery-Event": event,
            }
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    await client.post(wh["url"], content=body, headers=headers)
            except Exception as e:
                logger.warning(f"Webhook {wh['id']} failed: {e}")
