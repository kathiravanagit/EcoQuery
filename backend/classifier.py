import os
import logging
import asyncio

logger = logging.getLogger("EcoQuery.classifier")


class QueryClassifier:
    def __init__(self):
        pass

    async def classify(self, message: str) -> dict:
        return self._classify_simple(message)

    def _classify_simple(self, message: str) -> dict:
        words = message.split()
        word_count = len(words)
        lower = message.lower()

        reasoning_words = (
            "why", "how does", "how do", "explain", "compare", "analyze",
            "evaluate", "prove", "derive", "what are the implications",
            "what are the tradeoffs", "contrast", "critique", "design",
            "architect", "implement", "optimize", "debug", "reason about",
        )
        has_reasoning = any(rw in lower for rw in reasoning_words)

        has_code = any(c in message for c in ("def ", "class ", "import ", "```", "function ", "const ", "let "))
        has_math = any(c in message for c in ("∑", "∫", "∂", "√", "±", "=", "²", "^"))

        if word_count > 80 or has_code or has_math or (has_reasoning and word_count > 20):
            tier = "complex"
            confidence = 0.75 if word_count > 80 else 0.8
        elif has_reasoning or word_count > 25:
            tier = "medium"
            confidence = 0.7
        else:
            tier = "simple"
            confidence = 0.75

        return {
            "tier": tier,
            "confidence": confidence,
            "method": "simple-rules",
        }


classifier = QueryClassifier()