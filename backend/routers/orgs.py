from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
import secrets

from schemas import OrgCreateRequest, OrgInviteRequest
from auth import get_current_user
from email_service import email_service
from shared import ORGANIZATIONS, ORG_INVITES, ORG_API_KEYS

router = APIRouter(prefix="/api/orgs", tags=["organizations"])


async def get_orgs_collection():
    from auth import auth_db
    if auth_db.available:
        return auth_db.db["organizations"]
    return None


@router.post("/create")
async def create_org(req: OrgCreateRequest, current_user: dict = Depends(get_current_user)):
    org_id = f"org_{secrets.token_hex(12)}"
    org = {
        "id": org_id, "name": req.name,
        "owner": current_user["email"],
        "members": [current_user["email"]],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_queries": 0,
        "daily_quota": 100000
    }
    ORGANIZATIONS[org_id] = org
    coll = await get_orgs_collection()
    if coll:
        await coll.insert_one(org)
    return {"status": "ok", "org": org}


@router.get("")
async def list_orgs(current_user: dict = Depends(get_current_user)):
    user_orgs = [o for o in ORGANIZATIONS.values() if current_user["email"] in o.get("members", [])]
    for o in user_orgs:
        o.setdefault("api_keys", [])
    return {"orgs": user_orgs}


@router.get("/{org_id}")
async def get_org(org_id: str, current_user: dict = Depends(get_current_user)):
    org = ORGANIZATIONS.get(org_id)
    if not org or current_user["email"] not in org.get("members", []):
        raise HTTPException(status_code=404, detail="Organization not found")
    org.setdefault("api_keys", [])
    ak = ORG_API_KEYS.get(org_id, [])
    org["api_keys"] = ak
    return {"org": org}


@router.post("/{org_id}/invite")
async def invite_member(org_id: str, req: OrgInviteRequest, current_user: dict = Depends(get_current_user)):
    org = ORGANIZATIONS.get(org_id)
    if not org or org.get("owner") != current_user["email"]:
        raise HTTPException(status_code=403, detail="Only the owner can invite members")
    if req.email in org["members"]:
        raise HTTPException(status_code=400, detail="Already a member")
    token = secrets.token_urlsafe(32)
    ORG_INVITES[token] = {"org_id": org_id, "email": req.email, "org_name": org["name"], "invited_by": current_user["email"]}
    await email_service.send_org_invite(req.email, org["name"], current_user["email"], token)
    return {"status": "ok", "message": f"Invitation sent to {req.email}"}


@router.post("/join")
async def join_org(token: str, current_user: dict = Depends(get_current_user)):
    invite = ORG_INVITES.pop(token, None)
    if not invite:
        raise HTTPException(status_code=400, detail="Invalid or expired invitation")
    if invite["email"] != current_user["email"]:
        raise HTTPException(status_code=403, detail="This invitation is for another user")
    org = ORGANIZATIONS.get(invite["org_id"])
    if not org:
        raise HTTPException(status_code=404, detail="Organization no longer exists")
    if current_user["email"] not in org["members"]:
        org["members"].append(current_user["email"])
    return {"status": "ok", "org": org}


@router.delete("/{org_id}/members/{email}")
async def remove_member(org_id: str, email: str, current_user: dict = Depends(get_current_user)):
    org = ORGANIZATIONS.get(org_id)
    if not org or org.get("owner") != current_user["email"]:
        raise HTTPException(status_code=403, detail="Only the owner can remove members")
    if email == org["owner"]:
        raise HTTPException(status_code=400, detail="Cannot remove the owner")
    org["members"] = [m for m in org["members"] if m != email]
    return {"status": "ok"}


@router.post("/{org_id}/api-key")
async def generate_org_api_key(org_id: str, current_user: dict = Depends(get_current_user)):
    org = ORGANIZATIONS.get(org_id)
    if not org or org.get("owner") != current_user["email"]:
        raise HTTPException(status_code=403, detail="Only the owner can generate API keys")
    key = f"eq_org_{secrets.token_hex(24)}"
    ORG_API_KEYS.setdefault(org_id, []).append({"key": key, "created_at": datetime.now(timezone.utc).isoformat(), "created_by": current_user["email"]})
    return {"api_key": key}
