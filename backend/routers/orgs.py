from datetime import datetime, timezone, timedelta
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import auth_db, get_current_user
from email_service import email_service
from schemas import OrgCreateRequest, OrgInviteRequest

router = APIRouter(prefix="/api/orgs", tags=["organizations"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _key_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _public_org(org: dict) -> dict:
    result = {key: value for key, value in org.items() if key != "_id"}
    result["api_keys"] = [
        {
            "id": item["id"],
            "prefix": item["prefix"],
            "created_at": item["created_at"],
            "created_by": item["created_by"],
            "revoked_at": item.get("revoked_at"),
        }
        for item in result.get("api_keys", [])
    ]
    return result


async def get_orgs_collection():
    if auth_db.available and auth_db.db is not None:
        return auth_db.db["organizations"]
    return None


async def get_invites_collection():
    if auth_db.available and auth_db.db is not None:
        return auth_db.db["organization_invites"]
    return None


async def require_org(org_id: str, email: str, owner_only: bool = False) -> tuple[dict, object]:
    collection = await get_orgs_collection()
    if collection is None:
        raise HTTPException(status_code=503, detail="Organization service is unavailable")

    org = await collection.find_one({"id": org_id})
    if not org or email not in org.get("members", []):
        raise HTTPException(status_code=404, detail="Organization not found")
    if owner_only and org.get("owner") != email:
        raise HTTPException(status_code=403, detail="Only the owner can perform this action")
    return org, collection


@router.post("/create")
async def create_org(req: OrgCreateRequest, current_user: dict = Depends(get_current_user)):
    collection = await get_orgs_collection()
    if collection is None:
        raise HTTPException(status_code=503, detail="Organization service is unavailable")

    org = {
        "id": f"org_{secrets.token_hex(12)}",
        "name": req.name.strip(),
        "owner": current_user["email"],
        "members": [current_user["email"]],
        "roles": {current_user["email"]: "admin"},
        "api_keys": [],
        "created_at": _now().isoformat(),
        "total_queries": 0,
        "daily_quota": 100000,
    }
    await collection.insert_one(org)
    return {"status": "ok", "org": _public_org(org)}


@router.get("")
async def list_orgs(current_user: dict = Depends(get_current_user)):
    collection = await get_orgs_collection()
    if collection is None:
        raise HTTPException(status_code=503, detail="Organization service is unavailable")
    cursor = collection.find({"members": current_user["email"]}).sort("created_at", -1)
    orgs = await cursor.to_list(length=100)
    return {"orgs": [_public_org(org) for org in orgs]}


@router.get("/{org_id}")
async def get_org(org_id: str, current_user: dict = Depends(get_current_user)):
    org, _ = await require_org(org_id, current_user["email"])
    return {"org": _public_org(org)}


@router.post("/{org_id}/invite")
async def invite_member(org_id: str, req: OrgInviteRequest, current_user: dict = Depends(get_current_user)):
    org, _ = await require_org(org_id, current_user["email"], owner_only=True)
    email = req.email.strip().lower()
    if email in org.get("members", []):
        raise HTTPException(status_code=400, detail="Already a member")

    invites = await get_invites_collection()
    if invites is None:
        raise HTTPException(status_code=503, detail="Organization service is unavailable")
    token = secrets.token_urlsafe(32)
    await invites.insert_one({
        "token_hash": _key_hash(token),
        "org_id": org_id,
        "email": email,
        "org_name": org["name"],
        "invited_by": current_user["email"],
        "created_at": _now(),
        "expires_at": _now() + timedelta(days=7),
        "used": False,
    })
    await email_service.send_org_invite(email, org["name"], current_user["email"], token)
    return {"status": "ok", "message": f"Invitation sent to {email}"}


@router.post("/join")
async def join_org(token: str = Query(min_length=20, max_length=200), current_user: dict = Depends(get_current_user)):
    invites = await get_invites_collection()
    collection = await get_orgs_collection()
    if invites is None or collection is None:
        raise HTTPException(status_code=503, detail="Organization service is unavailable")

    invite = await invites.find_one_and_update(
        {"token_hash": _key_hash(token), "used": False, "expires_at": {"$gt": _now()}, "email": current_user["email"]},
        {"$set": {"used": True, "used_at": _now()}},
    )
    if not invite:
        raise HTTPException(status_code=400, detail="Invalid, expired, or already-used invitation")

    await collection.update_one(
        {"id": invite["org_id"]},
        {"$addToSet": {"members": current_user["email"]}, "$set": {f"roles.{current_user['email']}": "member"}},
    )
    org = await collection.find_one({"id": invite["org_id"]})
    if not org:
        raise HTTPException(status_code=404, detail="Organization no longer exists")
    return {"status": "ok", "org": _public_org(org)}


@router.delete("/{org_id}/members/{email}")
async def remove_member(org_id: str, email: str, current_user: dict = Depends(get_current_user)):
    org, collection = await require_org(org_id, current_user["email"], owner_only=True)
    email = email.strip().lower()
    if email == org["owner"]:
        raise HTTPException(status_code=400, detail="Cannot remove the owner")
    await collection.update_one({"id": org_id}, {"$pull": {"members": email}, "$unset": {f"roles.{email}": ""}})
    return {"status": "ok"}


@router.post("/{org_id}/api-key")
async def generate_org_api_key(org_id: str, current_user: dict = Depends(get_current_user)):
    org, collection = await require_org(org_id, current_user["email"], owner_only=True)
    raw_key = f"eq_org_{secrets.token_urlsafe(32)}"
    metadata = {
        "id": f"key_{secrets.token_hex(10)}",
        "prefix": raw_key[:14],
        "hash": _key_hash(raw_key),
        "created_at": _now().isoformat(),
        "created_by": current_user["email"],
        "revoked_at": None,
    }
    await collection.update_one({"id": org_id}, {"$push": {"api_keys": metadata}})
    return {"api_key": raw_key, "key_id": metadata["id"], "warning": "Store this key securely; it will not be shown again."}


@router.get("/{org_id}/sustainability")
async def get_org_sustainability(org_id: str, current_user: dict = Depends(get_current_user)):
    org, _ = await require_org(org_id, current_user["email"])
    from ledger import ledger
    records, _ = await ledger.get_audit_log(limit=10000, skip=0, user_email=current_user["email"])
    total = len(records)
    total_co2 = sum(r.get("co2_saved_vs_baseline", 0) for r in records)
    total_cost = sum(r.get("api_cost", 0) for r in records)
    green = sum(1 for r in records if r.get("model_tier") == "green")
    regions = {}
    for record in records:
        region = record.get("region", "unknown")
        regions[region] = regions.get(region, 0) + 1
    return {
        "org_id": org_id,
        "org_name": org["name"],
        "report_period": f"Last {total} queries",
        "summary": {"total_queries": total, "total_co2_saved_g": round(total_co2, 4), "total_api_cost_usd": round(total_cost, 6), "green_query_percent": round(green / total * 100, 1) if total else 0},
        "region_usage": regions,
        "environmental_impact": {"trees_equivalent": round(total_co2 / 21.0, 4), "car_km_equivalent": round(total_co2 / 0.21, 2), "led_bulb_hours": round(total_co2 / 0.01, 0)},
        "generated_at": _now().isoformat(),
    }


@router.get("/{org_id}/members/roles")
async def get_org_member_roles(org_id: str, current_user: dict = Depends(get_current_user)):
    org, _ = await require_org(org_id, current_user["email"])
    return {"org_id": org_id, "members": [{"email": email, "role": org.get("roles", {}).get(email, "admin" if email == org["owner"] else "member")} for email in org.get("members", [])]}


@router.post("/{org_id}/members/{email}/role")
async def update_member_role(org_id: str, email: str, role: str = Query(pattern="^(admin|member|viewer)$"), current_user: dict = Depends(get_current_user)):
    org, collection = await require_org(org_id, current_user["email"], owner_only=True)
    email = email.strip().lower()
    if email not in org.get("members", []):
        raise HTTPException(status_code=404, detail="Member not found")
    await collection.update_one({"id": org_id}, {"$set": {f"roles.{email}": role}})
    return {"status": "ok", "email": email, "role": role, "org_id": org_id}


@router.get("/{org_id}/dashboard")
async def get_org_dashboard(org_id: str, current_user: dict = Depends(get_current_user)):
    org, _ = await require_org(org_id, current_user["email"])
    from ledger import ledger
    records, _ = await ledger.get_audit_log(limit=10000, skip=0, user_email=current_user["email"])
    total = len(records)
    total_co2 = sum(r.get("co2_saved_vs_baseline", 0) for r in records)
    total_cost = sum(r.get("api_cost", 0) for r in records)
    avg_latency = sum(r.get("latency_seconds", 0) for r in records) / total if total else 0
    tiers = {tier: sum(1 for r in records if r.get("model_tier") == tier) for tier in ("green", "balanced", "performance")}
    models = {}
    for record in records:
        model = record.get("model_used", "unknown")
        models[model] = models.get(model, 0) + 1
    return {"org_id": org_id, "org_name": org["name"], "owner": org["owner"], "member_count": len(org.get("members", [])), "summary": {"total_queries": total, "total_co2_saved_g": round(total_co2, 4), "total_api_cost_usd": round(total_cost, 6), "avg_latency_s": round(avg_latency, 3), "green_query_percent": round(tiers["green"] / total * 100, 1) if total else 0}, "tier_distribution": tiers, "top_models": dict(sorted(models.items(), key=lambda item: item[1], reverse=True)[:10]), "updated_at": _now().isoformat()}
