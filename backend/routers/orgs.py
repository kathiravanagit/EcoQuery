from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Optional
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


@router.get("/{org_id}/sustainability")
async def get_org_sustainability(org_id: str, current_user: dict = Depends(get_current_user)):
    org = ORGANIZATIONS.get(org_id)
    if not org or current_user["email"] not in org.get("members", []):
        raise HTTPException(status_code=404, detail="Organization not found")
    
    from ledger import ledger
    records = await ledger.get_audit_log(limit=10000, skip=0, user_email=current_user["email"])
    
    total = len(records)
    total_co2 = sum(r.get("co2_saved_vs_baseline", 0) for r in records)
    total_cost = sum(r.get("api_cost", 0) for r in records)
    green = sum(1 for r in records if r.get("model_tier") == "green")
    
    regions = {}
    for r in records:
        reg = r.get("region", "unknown")
        regions[reg] = regions.get(reg, 0) + 1
    
    return {
        "org_id": org_id,
        "org_name": org["name"],
        "report_period": f"Last {total} queries",
        "summary": {
            "total_queries": total,
            "total_co2_saved_g": round(total_co2, 4),
            "total_api_cost_usd": round(total_cost, 6),
            "green_query_percent": round((green / total * 100), 1) if total else 0,
        },
        "region_usage": regions,
        "environmental_impact": {
            "trees_equivalent": round(total_co2 / 21.0, 4),
            "car_km_equivalent": round(total_co2 / 0.21, 2),
            "led_bulb_hours": round(total_co2 / 0.01, 0),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/{org_id}/members/roles")
async def get_org_member_roles(org_id: str, current_user: dict = Depends(get_current_user)):
    org = ORGANIZATIONS.get(org_id)
    if not org or current_user["email"] not in org.get("members", []):
        raise HTTPException(status_code=404, detail="Organization not found")
    
    members = []
    for email in org.get("members", []):
        role = "admin" if email == org.get("owner") else "member"
        members.append({"email": email, "role": role})
    
    return {"org_id": org_id, "members": members}


@router.post("/{org_id}/members/{email}/role")
async def update_member_role(org_id: str, email: str, role: str, current_user: dict = Depends(get_current_user)):
    org = ORGANIZATIONS.get(org_id)
    if not org or org.get("owner") != current_user["email"]:
        raise HTTPException(status_code=403, detail="Only the owner can update roles")
    if email not in org.get("members", []):
        raise HTTPException(status_code=404, detail="Member not found")
    
    if role not in ["admin", "member", "viewer"]:
        raise HTTPException(status_code=400, detail="Invalid role. Use: admin, member, viewer")
    
    return {"status": "ok", "email": email, "role": role, "org_id": org_id}


@router.get("/{org_id}/dashboard")
async def get_org_dashboard(org_id: str, current_user: dict = Depends(get_current_user)):
    org = ORGANIZATIONS.get(org_id)
    if not org or current_user["email"] not in org.get("members", []):
        raise HTTPException(status_code=404, detail="Organization not found")
    
    from ledger import ledger
    all_records = await ledger.get_audit_log(limit=10000, skip=0, user_email=current_user["email"])
    
    total = len(all_records)
    total_co2 = sum(r.get("co2_saved_vs_baseline", 0) for r in all_records)
    total_cost = sum(r.get("api_cost", 0) for r in all_records)
    avg_latency = sum(r.get("latency_seconds", 0) for r in all_records) / total if total else 0
    green = sum(1 for r in all_records if r.get("model_tier") == "green")
    balanced = sum(1 for r in all_records if r.get("model_tier") == "balanced")
    performance = sum(1 for r in all_records if r.get("model_tier") == "performance")
    
    models_used = {}
    for r in all_records:
        model = r.get("model_used", "unknown")
        models_used[model] = models_used.get(model, 0) + 1
    
    return {
        "org_id": org_id,
        "org_name": org["name"],
        "owner": org["owner"],
        "member_count": len(org.get("members", [])),
        "summary": {
            "total_queries": total,
            "total_co2_saved_g": round(total_co2, 4),
            "total_api_cost_usd": round(total_cost, 6),
            "avg_latency_s": round(avg_latency, 3),
            "green_query_percent": round((green / total * 100), 1) if total else 0,
        },
        "tier_distribution": {
            "green": green,
            "balanced": balanced,
            "performance": performance,
        },
        "top_models": dict(sorted(models_used.items(), key=lambda x: x[1], reverse=True)[:10]),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
