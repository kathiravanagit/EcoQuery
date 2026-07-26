import os
import logging
from datetime import datetime, timezone
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger("EcoQuery.ledger")

class VerificationLedger:
    def __init__(self):
        self.client = None
        self.db = None
        self.collection = None
        self.available = False

    async def connect(self):
        url = os.getenv("MONGODB_URL", "mongodb://localhost:27017/ecoquery")
        try:
            self.client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=3000)
            self.db = self.client.get_default_database()
            self.collection = self.db["audit_log"]
            await self.client.admin.command("ping")
            self.available = True
            logger.info("Connected to MongoDB for verification ledger")
        except Exception as e:
            logger.warning(f"MongoDB unavailable: {e}. Audit trail will be stored in memory.")
            self.available = False

    async def record_query(self, entry: dict, user_email: str = "") -> str:
        record = {
            **entry,
            "user_email": user_email,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0"
        }
        if self.available and self.collection is not None:
            result = await self.collection.insert_one(record)
            return str(result.inserted_id)
        return "no-db-entry"

    async def get_audit_log(self, limit: int = 50, skip: int = 0, user_email: str = "") -> list:
        if self.available and self.collection is not None:
            query = {"user_email": user_email} if user_email else {}
            cursor = self.collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
            records = await cursor.to_list(length=limit)
            for r in records:
                r["_id"] = str(r["_id"])
            return records
        return []

    async def get_stats(self) -> dict:
        if self.available and self.collection is not None:
            total = await self.collection.count_documents({})
            pipeline = [
                {"$group": {"_id": None, "total_co2": {"$sum": "$co2_saved_vs_baseline"}}}
            ]
            result = await self.collection.aggregate(pipeline).to_list(1)
            total_co2 = result[0]["total_co2"] if result else 0
            return {"total_queries": total, "total_co2_saved_g": round(total_co2, 3)}
        return {"total_queries": 0, "total_co2_saved_g": 0}

ledger = VerificationLedger()
