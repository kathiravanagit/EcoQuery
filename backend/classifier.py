import os
import logging

logger = logging.getLogger("EcoQuery.classifier")

class QueryClassifier:
    def __init__(self):
        self._pipeline = None
        self.labels = ["simple query", "medium query", "complex query"]
        self._ml_enabled = os.getenv("ECO_QUERY_USE_ML_CLASSIFIER", "").lower() in ("1", "true", "yes")
        if self._ml_enabled:
            logger.info("ML classifier enabled (model loads on first use)")
        else:
            logger.info("ML classifier disabled (using heuristic).")

    def classify(self, message: str) -> dict:
        if self._ml_enabled and self._pipeline is None:
            self._load_model()
        if self._pipeline is not None:
            return self._classify_with_model(message)
        return self._classify_heuristic(message)

    def _load_model(self):
        try:
            from transformers import pipeline
            self._pipeline = pipeline(
                "zero-shot-classification",
                model="distilbert-base-uncased",
                device=-1
            )
            logger.info("distil-bert zero-shot classifier loaded")
        except Exception as e:
            logger.warning(f"Failed to load distil-bert model: {e}. Using heuristic fallback.")
            self._pipeline = None

    def _classify_with_model(self, message: str) -> dict:
        result = self._pipeline(message, self.labels)
        scores = dict(zip(result["labels"], result["scores"]))
        tier = max(scores, key=scores.get)
        return {
            "tier": tier.split()[0],
            "confidence": max(scores.values()),
            "method": "distil-bert"
        }

    def _classify_heuristic(self, message: str) -> dict:
        length = len(message)
        words = message.split()
        has_code = any(c in message for c in ("def ", "class ", "import ", "```", "function"))
        has_math = any(c in message for c in ("∑", "∫", "∂", "√", "±"))
        word_count = len(words)

        if word_count > 100 or has_code or has_math:
            tier = "complex"
            confidence = 0.75 if word_count > 100 else 0.85
        elif word_count > 30 or length > 150:
            tier = "medium"
            confidence = 0.7
        else:
            tier = "simple"
            confidence = 0.8

        return {
            "tier": tier,
            "confidence": confidence,
            "method": "heuristic"
        }

classifier = QueryClassifier()
