import os
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from jose import JWTError, jwt
import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

logger = logging.getLogger("EcoQuery.auth")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    logger.warning("JWT_SECRET not set — using dev-only default. Set it in .env for production.")
    SECRET_KEY = "ecoquery-dev-jwt-secret-do-not-use-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

class UserInDB(BaseModel):
    email: str
    hashed_password: str
    display_name: str
    auth_provider: str = "email"
    google_id: Optional[str] = None
    created_at: str = ""
    is_active: bool = True
    role: str = "user"
    email_verified: bool = False

class AuthDB:
    def __init__(self):
        self.client = None
        self.db = None
        self.collection = None
        self.reset_collection = None
        self.available = False

    async def connect(self):
        url = os.getenv("MONGODB_URL", "mongodb://localhost:27017/ecoquery")
        try:
            self.client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=3000)
            self.db = self.client.get_default_database()
            self.collection = self.db["users"]
            self.reset_collection = self.db["reset_tokens"]
            await self.client.admin.command("ping")
            self.available = True
            logger.info("Connected to MongoDB for auth")
        except Exception as e:
            logger.warning(f"MongoDB unavailable for auth: {e}")
            self.available = False

    async def find_user_by_email(self, email: str) -> Optional[dict]:
        if self.available and self.collection is not None:
            return await self.collection.find_one({"email": email})
        return None

    async def find_user_by_google_id(self, google_id: str) -> Optional[dict]:
        if self.available and self.collection is not None:
            return await self.collection.find_one({"google_id": google_id})
        return None

    async def create_user(self, user: UserInDB) -> bool:
        if self.available and self.collection is not None:
            existing = await self.find_user_by_email(user.email)
            if existing:
                return False
            await self.collection.insert_one(user.model_dump())
            return True
        return False

    async def update_user(self, email: str, updates: dict) -> bool:
        if self.available and self.collection is not None:
            await self.collection.update_one({"email": email}, {"$set": updates})
            return True
        return False

    async def list_users(self, skip: int = 0, limit: int = 100) -> list:
        if self.available and self.collection is not None:
            cursor = self.collection.find().skip(skip).limit(limit)
            users = await cursor.to_list(length=limit)
            for u in users:
                u["_id"] = str(u["_id"])
            return users
        return []

    async def count_users(self) -> int:
        if self.available and self.collection is not None:
            return await self.collection.count_documents({})
        return 0

    async def create_reset_token(self, email: str) -> Optional[str]:
        if self.available and self.reset_collection is not None:
            token = secrets.token_urlsafe(32)
            await self.reset_collection.insert_one({
                "email": email,
                "token": token,
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
                "used": False
            })
            return token
        logger.warning("Cannot create reset token — MongoDB unavailable")
        return None

    async def verify_reset_token(self, token: str) -> Optional[str]:
        if self.available and self.reset_collection is not None:
            record = await self.reset_collection.find_one({"token": token, "used": False, "expires_at": {"$gt": datetime.now(timezone.utc)}})
            if record:
                await self.reset_collection.update_one({"_id": record["_id"]}, {"$set": {"used": True}})
                return record["email"]
        return None

auth_db = AuthDB()

def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # Try API key first (starts with eq_)
    if token.startswith("eq_"):
        user = await auth_db.collection.find_one({"api_key": token})
        if user is None:
            raise credentials_exception
        user["_id"] = str(user["_id"])
        return user
    # Then try JWT
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = await auth_db.find_user_by_email(email)
    if user is None:
        raise credentials_exception
    user["_id"] = str(user["_id"])
    return user

async def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
