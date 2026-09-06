"""
Persistent Complex-Question Response Cache for EcoQuery.
Provides database-backed semantic response caching for questions requiring LLM inference.
"""

import os
import re
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import numpy as np
import difflib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger("EcoQuery.response_cache")


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


class ResponseCache:
    """Persistent, semantic response cache backed by MongoDB and an in-memory vector index."""

    def __init__(self):
        self._entries: List[Dict[str, Any]] = []
        self._questions: List[str] = []
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._tfidf_matrix = None
        self._collection = None
        self._db_initialized = False

    def _ensure_db(self):
        if self._db_initialized:
            return
        from ledger import ledger
        if ledger.available and ledger.db is not None:
            try:
                self._collection = ledger.db.response_cache
                self._db_initialized = True
            except Exception as e:
                logger.warning(f"Could not connect to MongoDB response_cache: {e}")

    async def init_from_db(self):
        """Load stored responses from database into memory index on startup."""
        self._ensure_db()
        if self._collection is not None:
            try:
                cursor = self._collection.find({}).sort("timestamp", -1).limit(2000)
                docs = await cursor.to_list(2000)
                for doc in docs:
                    self._entries.append(doc)
                    self._questions.append(doc.get("question", ""))
                self._rebuild_index()
                logger.info(f"Loaded {len(self._entries)} cached responses from database.")
            except Exception as e:
                logger.warning(f"Failed to load response_cache from DB: {e}")

    def _rebuild_index(self):
        if not self._questions:
            self._vectorizer = None
            self._tfidf_matrix = None
            return
        try:
            # Build TF-IDF on normalized questions for better semantic matching
            normalized_questions = [_normalize(q) for q in self._questions]
            self._vectorizer = TfidfVectorizer(
                ngram_range=(1, 3),
                sublinear_tf=True,
                strip_accents="unicode",
                lowercase=False,  # already normalized
                stop_words="english",
                token_pattern=r'(?u)\b\w+\b'
            )
            self._tfidf_matrix = self._vectorizer.fit_transform(normalized_questions)
        except Exception as e:
            logger.warning(f"Failed to rebuild response_cache TF-IDF index: {e}")

    async def match(self, query: str, tier: Optional[str] = None) -> Dict[str, Any]:
        """
        Check if a semantically similar complex question has already been answered and cached.
        Returns match status, confidence score, and stored response.
        """
        self._ensure_db()
        if not self._entries or not self._vectorizer or self._tfidf_matrix is None or not query.strip():
            return {
                "matched": False,
                "confidence": 0.0,
                "answer": None,
                "stored_question": None,
                "tier": None,
                "model_used": None,
                "provider": None,
                "region": None,
                "energy_source": None,
                "co2_saved_g": 0.0,
            }

        norm_query = _normalize(query)

        # 1. Exact normalized match
        for entry in self._entries:
            if _normalize(entry.get("question", "")) == norm_query:
                return {
                    "matched": True,
                    "confidence": 1.0,
                    "answer": entry.get("answer"),
                    "stored_question": entry.get("question"),
                    "tier": entry.get("complexity", tier or "complex"),
                    "model_used": entry.get("model_used", "EcoQuery Stored Response"),
                    "provider": entry.get("provider", "EcoQuery Cache"),
                    "region": entry.get("region", "local-cache"),
                    "energy_source": entry.get("energy_source", "zero-emission"),
                    "co2_saved_g": entry.get("co2_saved_g", 0.05),
                }

        # 2. Semantic TF-IDF Cosine Similarity
        try:
            query_vec = self._vectorizer.transform([_normalize(query)])
            sims = cosine_similarity(query_vec, self._tfidf_matrix)[0]
            best_idx = int(np.argmax(sims))
            best_score = float(sims[best_idx])
            best_entry = self._entries[best_idx]

            q_words = set(norm_query.split())
            stored_words = set(_normalize(best_entry.get("question", "")).split())
            common_words = [w for w in (q_words & stored_words) if len(w) > 3]

            # Compute edit similarity (SequenceMatcher) as an alternative to TF‑IDF
            max_edit_score = 0.0
            best_edit_entry = None
            for entry in self._entries:
                entry_norm = _normalize(entry.get("question", ""))
                ratio = difflib.SequenceMatcher(None, norm_query, entry_norm).ratio()
                if ratio > max_edit_score:
                    max_edit_score = ratio
                    best_edit_entry = entry

            # Choose the higher scoring method (TF‑IDF vs edit similarity)
            if max_edit_score > best_score:
                best_score = max_edit_score
                best_entry = best_edit_entry

            # Use a higher confidence threshold for semantic matches (>= 0.80)
            if best_score >= 0.80 and len(common_words) >= 1:
                return {
                    "matched": True,
                    "confidence": round(min(0.99, best_score), 2),
                    "answer": best_entry.get("answer"),
                    "stored_question": best_entry.get("question"),
                    "tier": best_entry.get("complexity", tier or "complex"),
                    "model_used": best_entry.get("model_used", "EcoQuery Stored Response"),
                    "provider": best_entry.get("provider", "EcoQuery Cache"),
                    "region": best_entry.get("region", "local-cache"),
                    "energy_source": best_entry.get("energy_source", "zero-emission"),
                    "co2_saved_g": best_entry.get("co2_saved_g", 0.05),
                }

            return {
                "matched": False,
                "confidence": round(best_score, 2),
                "answer": None,
                "stored_question": best_entry.get("question"),
                "tier": best_entry.get("complexity", tier),
                "model_used": None,
                "provider": None,
                "region": None,
                "energy_source": None,
                "co2_saved_g": 0.0,
            }
        except Exception as e:
            logger.warning(f"Response cache matching error: {e}")
            return {
                "matched": False,
                "confidence": 0.0,
                "answer": None,
                "stored_question": None,
                "tier": None,
                "model_used": None,
                "provider": None,
                "region": None,
                "energy_source": None,
                "co2_saved_g": 0.0,
            }

    async def store(
        self,
        question: str,
        answer: str,
        tier: str,
        model: str,
        provider: str,
        region_info: dict,
        savings: dict,
    ) -> bool:
        """Store a high-quality LLM response in database and update vector index."""
        if not question or not answer or not answer.strip():
            return False

        # Do not store error / fallback responses
        error_indicators = (
            "i'm sorry", "encountered an error", "no response generated",
            "contact support", "error processing your request"
        )
        if any(err in answer.lower() for err in error_indicators):
            return False

        # Privacy safety filter: do not store queries containing credentials or private keys
        private_indicators = ("password", "api_key", "secret", "bearer ", "token", "eq_", "sk-")
        if any(priv in question.lower() for priv in private_indicators):
            return False

        doc = {
            "question": question.strip(),
            "normalized_question": _normalize(question),
            "answer": answer.strip(),
            "complexity": tier,
            "model_used": model,
            "provider": provider,
            "region": region_info.get("region", "unknown"),
            "energy_source": region_info.get("energy_source", "grid"),
            "co2_saved_g": savings.get("saved_vs_baseline_g", 0.05),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Update in-memory index
        self._entries.append(doc)
        self._questions.append(question.strip())
        self._rebuild_index()

        # Persist to database
        self._ensure_db()
        if self._collection is not None:
            try:
                await self._collection.insert_one(doc)
                return True
            except Exception as e:
                logger.debug(f"Could not persist to response_cache collection: {e}")

        return True


response_cache = ResponseCache()
