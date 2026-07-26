from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from datetime import datetime, timezone
import os
import httpx

from schemas import (
    SignupRequest, LoginRequest, AuthResponse,
    UpdateNameRequest, UpdatePasswordRequest, DeleteAccountRequest,
    ForgotPasswordRequest, ResetPasswordRequest
)
from auth import (
    auth_db, hash_password, verify_password, create_access_token,
    get_current_user, UserInDB
)
from email_service import email_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse)
async def signup(req: SignupRequest):
    existing = await auth_db.find_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = UserInDB(
        email=req.email,
        hashed_password=hash_password(req.password),
        display_name=req.display_name,
        created_at=datetime.now(timezone.utc).isoformat()
    )
    success = await auth_db.create_user(user)
    if not success:
        raise HTTPException(status_code=500, detail="Could not create user")
    token = create_access_token({"sub": req.email})
    await auth_db.update_user(req.email, {"email_verified": True})
    return AuthResponse(access_token=token, user={"email": req.email, "display_name": req.display_name})


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    user = await auth_db.find_user_by_email(req.email)
    if not user or not verify_password(req.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({"sub": req.email})
    return AuthResponse(access_token=token, user={"email": user["email"], "display_name": user["display_name"]})


@router.get("/google")
async def google_login():
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
    params = f"client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope=openid%20email%20profile"
    return RedirectResponse(url=f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/google/callback")
async def google_callback(code: str):
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code, "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": redirect_uri, "grant_type": "authorization_code"
    }
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(token_url, data=data)
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Google OAuth failed")
        tokens = token_resp.json()
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")
        google_user = userinfo_resp.json()
    google_id = google_user["id"]
    email = google_user["email"]
    name = google_user.get("name", email)
    existing = await auth_db.find_user_by_google_id(google_id)
    if not existing:
        existing_email = await auth_db.find_user_by_email(email)
        if existing_email:
            await auth_db.collection.update_one({"email": email}, {"$set": {"google_id": google_id, "auth_provider": "google", "email_verified": True}})
        else:
            user = UserInDB(
                email=email, hashed_password="", display_name=name,
                auth_provider="google", google_id=google_id,
                created_at=datetime.now(timezone.utc).isoformat(),
                email_verified=True
            )
            await auth_db.create_user(user)
    token = create_access_token({"sub": email})
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    return RedirectResponse(url=f"{frontend_url}/auth/callback?token={token}&email={email}&name={name}")


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "email": current_user["email"],
        "display_name": current_user.get("display_name", ""),
        "auth_provider": current_user.get("auth_provider", "email"),
        "email_verified": current_user.get("email_verified", False),
        "role": current_user.get("role", "user"),
    }


@router.patch("/profile")
async def update_name(req: UpdateNameRequest, current_user: dict = Depends(get_current_user)):
    if not auth_db.available or auth_db.collection is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    await auth_db.collection.update_one({"email": current_user["email"]}, {"$set": {"display_name": req.display_name}})
    return {"status": "ok", "display_name": req.display_name}


@router.patch("/password")
async def update_password(req: UpdatePasswordRequest, current_user: dict = Depends(get_current_user)):
    if not auth_db.available or auth_db.collection is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    if not verify_password(req.current_password, current_user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    new_hashed = hash_password(req.new_password)
    await auth_db.collection.update_one({"email": current_user["email"]}, {"$set": {"hashed_password": new_hashed}})
    return {"status": "ok"}


@router.delete("/account")
async def delete_account(req: DeleteAccountRequest, current_user: dict = Depends(get_current_user)):
    if not auth_db.available or auth_db.collection is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    if current_user.get("auth_provider") == "email" and not verify_password(req.password, current_user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Password is incorrect")
    await auth_db.collection.delete_one({"email": current_user["email"]})
    from ledger import ledger
    await ledger.collection.delete_many({"user_email": current_user["email"]})
    return {"status": "ok"}


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    user = await auth_db.find_user_by_email(req.email)
    if not user:
        return {"status": "ok", "message": "If the email exists, a reset link has been sent."}
    if user.get("auth_provider") == "google":
        return {"status": "ok", "message": "Google accounts use Google login. No password reset needed."}
    token = await auth_db.create_reset_token(req.email)
    await email_service.send_password_reset(req.email, token)
    return {"status": "ok", "message": "If the email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    email = await auth_db.verify_reset_token(req.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    await auth_db.update_user(email, {"hashed_password": hash_password(req.new_password)})
    return {"status": "ok", "message": "Password has been reset. You can now log in."}
