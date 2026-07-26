from fastapi import APIRouter, Depends

from schemas import AdminUserUpdateRequest
from auth import auth_db, get_admin_user
from ledger import ledger
from shared import ORGANIZATIONS

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users")
async def admin_list_users(admin: dict = Depends(get_admin_user), skip: int = 0, limit: int = 100):
    users = await auth_db.list_users(skip=skip, limit=limit)
    safe = [{"email": u["email"], "display_name": u.get("display_name",""), "role": u.get("role","user"), "auth_provider": u.get("auth_provider","email"), "email_verified": u.get("email_verified",False), "created_at": u.get("created_at",""), "is_active": u.get("is_active",True)} for u in users]
    return {"users": safe, "count": len(safe)}


@router.get("/stats")
async def admin_stats(admin: dict = Depends(get_admin_user)):
    user_count = await auth_db.count_users()
    ledger_stats = await ledger.get_stats()
    return {"total_users": user_count, "total_queries": ledger_stats.get("total_queries", 0), "total_co2_saved_g": ledger_stats.get("total_co2_saved_g", 0), "org_count": len(ORGANIZATIONS)}


@router.patch("/users/{email}")
async def admin_update_user(email: str, req: AdminUserUpdateRequest, admin: dict = Depends(get_admin_user)):
    updates = {}
    if req.role is not None:
        updates["role"] = req.role
    if req.is_active is not None:
        updates["is_active"] = req.is_active
    if updates:
        await auth_db.update_user(email, updates)
        return {"status": "ok", "updated": updates}
    return {"status": "ok", "updated": {}}
