from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from byok_store import persistent_byok
from providers import BYOK_MAX_KEY_LENGTH, PROVIDER_BASE_URLS

router = APIRouter(prefix="/api/user/byok", tags=["byok"])


class ProviderKeyRequest(BaseModel):
    provider: str
    key: str


def _email(user: dict) -> str:
    return str(user.get("email", "")).strip().lower()


@router.get("")
async def list_keys(user: dict = Depends(get_current_user)):
    return {"providers": await persistent_byok.list_providers(_email(user))}


@router.put("")
async def save_key(payload: ProviderKeyRequest, user: dict = Depends(get_current_user)):
    provider = payload.provider.strip().lower()
    key = payload.key.strip()
    if provider not in PROVIDER_BASE_URLS:
        raise HTTPException(status_code=400, detail="Unsupported provider")
    if not key or len(key) > BYOK_MAX_KEY_LENGTH:
        raise HTTPException(status_code=400, detail="Invalid provider key")
    if not await persistent_byok.save(_email(user), provider, key):
        raise HTTPException(status_code=503, detail="Persistent key storage is unavailable")
    return {"provider": provider, "saved": True}


@router.post("/{provider}/revoke")
async def revoke_key(provider: str, user: dict = Depends(get_current_user)):
    if provider not in PROVIDER_BASE_URLS:
        raise HTTPException(status_code=404, detail="Unsupported provider")
    await persistent_byok.revoke(_email(user), provider)
    return {"provider": provider, "revoked": True}


@router.delete("/{provider}")
async def delete_key(provider: str, user: dict = Depends(get_current_user)):
    if provider not in PROVIDER_BASE_URLS:
        raise HTTPException(status_code=404, detail="Unsupported provider")
    await persistent_byok.delete(_email(user), provider)
    return {"provider": provider, "deleted": True}
