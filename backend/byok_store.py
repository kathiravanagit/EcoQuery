import base64
import hashlib
import os
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken

from auth import SECRET_KEY, auth_db


class PersistentByokStore:
    """Encrypted provider credentials scoped to an authenticated user."""

    collection_name = "user_provider_keys"

    def __init__(self) -> None:
        secret = os.getenv("KEY_ENCRYPTION_KEY") or os.getenv("JWT_SECRET") or SECRET_KEY
        derived = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        self._fernet = Fernet(derived)

    @property
    def collection(self):
        if not auth_db.available or auth_db.db is None:
            return None
        return auth_db.db[self.collection_name]

    def _encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def _decrypt(self, value: str) -> str | None:
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except (InvalidToken, UnicodeDecodeError):
            return None

    async def save(self, email: str, provider: str, key: str) -> bool:
        collection = self.collection
        if collection is None:
            return False
        await collection.update_one(
            {"email": email, "provider": provider},
            {"$set": {
                "encrypted_key": self._encrypt(key),
                "updated_at": datetime.now(timezone.utc),
                "revoked": False,
            }},
            upsert=True,
        )
        return True

    async def list_providers(self, email: str) -> list[str]:
        collection = self.collection
        if collection is None:
            return []
        return [
            row["provider"]
            async for row in collection.find(
                {"email": email, "revoked": {"$ne": True}},
                {"provider": 1, "_id": 0},
            )
        ]

    async def load_keys(self, email: str) -> dict[str, str]:
        collection = self.collection
        if collection is None:
            return {}
        result: dict[str, str] = {}
        async for row in collection.find({"email": email, "revoked": {"$ne": True}}):
            key = self._decrypt(row.get("encrypted_key", ""))
            if key:
                result[row["provider"]] = key
        return result

    async def revoke(self, email: str, provider: str) -> bool:
        collection = self.collection
        if collection is None:
            return False
        result = await collection.update_one(
            {"email": email, "provider": provider},
            {"$set": {"revoked": True, "updated_at": datetime.now(timezone.utc)}},
        )
        return result.matched_count > 0

    async def delete(self, email: str, provider: str) -> bool:
        collection = self.collection
        if collection is None:
            return False
        result = await collection.delete_one({"email": email, "provider": provider})
        return result.deleted_count > 0


persistent_byok = PersistentByokStore()
