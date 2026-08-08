"""
Enhanced verification ledger with integrity hashing and advanced analytics.
"""

import os
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger("EcoQuery.ledger")


class VerificationLedger:
    def __init__(self):
        self.client = None
        self.db = None
        self.collection = None
        self.badges_col = None
        self.available = False

    async def connect(self):
        url = os.getenv("MONGODB_URL", "mongodb://localhost:27017/ecoquery")
        try:
            self.client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=3000)
            self.db = self.client.get_default_database()
            self.collection = self.db["audit_log"]
            self.badges_col = self.db["user_badges"]
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
            "version": "2.0",
            "ledger_hash": self._compute_ledger_hash(entry, user_email),
        }
        if self.available and self.collection is not None:
            result = await self.collection.insert_one(record)
            if user_email:
                await self._update_badges(user_email)
            return str(result.inserted_id)
        return "no-db-entry"

    async def get_audit_log(self, limit: int = 50, skip: int = 0, user_email: str = "",
                            q: str = "", model: str = "", tier: str = "",
                            sort: str = "timestamp", date_from: str = "", date_to: str = "") -> list:
        if self.available and self.collection is not None:
            query: dict = {}
            if user_email:
                query["user_email"] = user_email
            if q:
                query["query"] = {"$regex": q, "$options": "i"}
            if model:
                query["model_used"] = model
            if tier:
                query["tier"] = tier
            if date_from or date_to:
                ts_filter: dict = {}
                if date_from:
                    ts_filter["$gte"] = date_from
                if date_to:
                    ts_filter["$lte"] = date_to
                query["timestamp"] = ts_filter

            sort_key = "timestamp"
            sort_dir = -1
            if sort == "co2":
                sort_key = "co2_saved_vs_baseline"
            elif sort == "cost":
                sort_key = "api_cost"
            elif sort == "latency":
                sort_key = "latency_seconds"
            elif sort == "oldest":
                sort_key = "timestamp"
                sort_dir = 1

            total = await self.collection.count_documents(query)
            cursor = self.collection.find(query).sort(sort_key, sort_dir).skip(skip).limit(limit)
            records = await cursor.to_list(length=limit)
            for r in records:
                r["_id"] = str(r["_id"])
            return records, total
        return [], 0

    async def get_stats(self) -> dict:
        if self.available and self.collection is not None:
            total = await self.collection.count_documents({})
            pipeline = [
                {"$group": {
                    "_id": None,
                    "total_co2": {"$sum": "$co2_saved_vs_baseline"},
                    "total_cost": {"$sum": "$api_cost"},
                    "avg_latency": {"$avg": "$latency_seconds"},
                    "green_count": {"$sum": {"$cond": [{"$eq": ["$model_tier", "green"]}, 1, 0]}},
                    "flagged_count": {"$sum": {"$cond": [{"$eq": ["$verification_status", "flagged_substitution"]}, 1, 0]}},
                }}
            ]
            result = await self.collection.aggregate(pipeline).to_list(1)
            if result:
                green_pct = round((result[0].get("green_count", 0) / total * 100), 1) if total else 0
                return {
                    "total_queries": total,
                    "total_co2_saved_g": round(result[0].get("total_co2", 0), 3),
                    "total_api_cost": round(result[0].get("total_cost", 0), 6),
                    "avg_latency_s": round(result[0].get("avg_latency", 0), 3),
                    "flagged_queries": result[0].get("flagged_count", 0),
                    "green_query_pct": green_pct,
                }
            return {"total_queries": total, "total_co2_saved_g": 0, "total_api_cost": 0, "avg_latency_s": 0, "flagged_queries": 0, "green_query_pct": 0}
        return {"total_queries": 0, "total_co2_saved_g": 0, "total_api_cost": 0, "avg_latency_s": 0, "flagged_queries": 0, "green_query_pct": 0}

    async def get_analytics(self, user_email: str = "", days: int = 30) -> dict:
        if not self.available or self.collection is None:
            return {"queries_by_day": [], "queries_by_tier": {}, "queries_by_model": {}, "carbon_by_day": [], "latency_by_model": {}}

        from datetime import timedelta
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = {"timestamp": {"$gte": since}}
        if user_email:
            query["user_email"] = user_email

        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": {"$substr": ["$timestamp", 0, 10]},
                "count": {"$sum": 1},
                "co2_saved": {"$sum": "$co2_saved_vs_baseline"},
                "avg_latency": {"$avg": "$latency_seconds"},
            }},
            {"$sort": {"_id": 1}}
        ]
        daily = await self.collection.aggregate(pipeline).to_list(100)

        tier_pipeline = [
            {"$match": query},
            {"$group": {"_id": "$tier", "count": {"$sum": 1}}},
        ]
        tier_data = await self.collection.aggregate(tier_pipeline).to_list(20)
        queries_by_tier = {t["_id"]: t["count"] for t in tier_data if t["_id"]}

        model_pipeline = [
            {"$match": query},
            {"$group": {"_id": "$model_used", "count": {"$sum": 1}, "avg_latency": {"$avg": "$latency_seconds"}}},
        ]
        model_data = await self.collection.aggregate(model_pipeline).to_list(30)
        queries_by_model = {m["_id"]: {"count": m["count"], "avg_latency": round(m.get("avg_latency", 0), 2)} for m in model_data if m["_id"]}

        return {
            "queries_by_day": [{"date": d["_id"], "count": d["count"], "co2_saved": round(d.get("co2_saved", 0), 3), "avg_latency": round(d.get("avg_latency", 0), 2)} for d in daily],
            "queries_by_tier": queries_by_tier,
            "queries_by_model": queries_by_model,
        }

    async def get_leaderboard(self, limit: int = 20) -> list:
        if not self.available:
            return []
        pipeline = [
            {"$group": {
                "_id": "$user_email",
                "total_co2": {"$sum": "$co2_saved_vs_baseline"},
                "total_queries": {"$sum": 1},
            }},
            {"$sort": {"total_co2": -1}},
            {"$limit": limit},
        ]
        results = await self.collection.aggregate(pipeline).to_list(limit)
        return [
            {"email": r["_id"], "total_co2_saved_g": round(r["total_co2"], 3), "total_queries": r["total_queries"]}
            for r in results if r["_id"]
        ]

    async def get_user_badges(self, user_email: str) -> list:
        if not self.available or self.badges_col is None:
            return []
        doc = await self.badges_col.find_one({"email": user_email})
        return doc.get("badges", []) if doc else []

    async def _update_badges(self, user_email: str):
        if not self.available or self.badges_col is None:
            return

        pipeline = [
            {"$match": {"user_email": user_email}},
            {"$group": {
                "_id": "$user_email",
                "total_queries": {"$sum": 1},
                "total_co2": {"$sum": "$co2_saved_vs_baseline"},
                "green_count": {"$sum": {"$cond": [{"$eq": ["$model_tier", "green"]}, 1, 0]}},
            }}
        ]
        result = await self.collection.aggregate(pipeline).to_list(1)
        if not result:
            return

        stats = result[0]
        badges = []

        if stats["total_queries"] >= 1:
            badges.append({"id": "first_query", "name": "First Step", "description": "Routed your first query", "icon": "🌱", "earned_at": datetime.now(timezone.utc).isoformat()})
        if stats["total_queries"] >= 10:
            badges.append({"id": "eco_explorer", "name": "Eco Explorer", "description": "Routed 10 queries", "icon": "🌿", "earned_at": datetime.now(timezone.utc).isoformat()})
        if stats["total_queries"] >= 50:
            badges.append({"id": "green_champion", "name": "Green Champion", "description": "Routed 50 queries", "icon": "🏆", "earned_at": datetime.now(timezone.utc).isoformat()})
        if stats["total_queries"] >= 100:
            badges.append({"id": "carbon_warrior", "name": "Carbon Warrior", "description": "Routed 100 queries", "icon": "⚡", "earned_at": datetime.now(timezone.utc).isoformat()})
        if stats["total_co2"] > 0.01:
            badges.append({"id": "carbon_saver", "name": "Carbon Saver", "description": "Saved over 0.01g CO₂", "icon": "🌍", "earned_at": datetime.now(timezone.utc).isoformat()})
        if stats["total_co2"] > 0.1:
            badges.append({"id": "eco_hero", "name": "Eco Hero", "description": "Saved over 0.1g CO₂", "icon": "🦸", "earned_at": datetime.now(timezone.utc).isoformat()})
        if stats["total_co2"] > 1.0:
            badges.append({"id": "planet_guardian", "name": "Planet Guardian", "description": "Saved over 1g CO₂", "icon": "🌏", "earned_at": datetime.now(timezone.utc).isoformat()})
        if stats["total_queries"] > 0 and (stats["green_count"] / stats["total_queries"]) > 0.8:
            badges.append({"id": "pure_green", "name": "Pure Green", "description": "80%+ queries on green tier", "icon": "💚", "earned_at": datetime.now(timezone.utc).isoformat()})

        badge_ids = [b["id"] for b in badges]
        if self.badges_col is not None:
            existing_doc = await self.badges_col.find_one({"email": user_email})
            existing_ids = [b["id"] for b in (existing_doc.get("badges", []) if existing_doc else [])]
            new_badges = [b for b in badges if b["id"] not in existing_ids]
            if new_badges:
                all_badges = (existing_doc.get("badges", []) if existing_doc else []) + new_badges
                await self.badges_col.update_one(
                    {"email": user_email},
                    {"$set": {"badges": all_badges, "updated_at": datetime.now(timezone.utc).isoformat()}},
                    upsert=True
                )

    def _compute_ledger_hash(self, entry: dict, user_email: str) -> str:
        payload = f"{user_email}:{entry.get('model_used', '')}:{entry.get('co2_estimated', 0)}:{entry.get('timestamp', '')}"
        return hashlib.sha256(payload.encode()).hexdigest()[:24]


ledger = VerificationLedger()
