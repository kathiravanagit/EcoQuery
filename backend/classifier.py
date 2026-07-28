import os
import json
import logging
import asyncio
import openai

logger = logging.getLogger("EcoQuery.classifier")


class QueryClassifier:
    def __init__(self):
        pass

    async def classify(self, message: str) -> dict:
        if os.getenv("ECO_QUERY_TESTING") == "1":
            return self._classify_simple(message)
        result = await self._classify_ml(message)
        if result is not None:
            return result
        return self._classify_simple(message)

    async def _classify_ml(self, message: str) -> dict | None:
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return None

        client_kwargs = {"api_key": api_key}
        if api_key.startswith("sk-or-"):
            client_kwargs["base_url"] = "https://openrouter.ai/api/v1"

        try:
            client = openai.OpenAI(**client_kwargs)
            response = client.chat.completions.create(
                model="google/gemini-2.5-flash-lite",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a query classifier. Classify the user's message into one of "
                            "three tiers: 'simple', 'medium', or 'complex'.\n"
                            "- simple: short factual questions, greetings, yes/no, basic lookups\n"
                            "- medium: multi-step reasoning, comparisons, explanations\n"
                            "- complex: deep analysis, code, math, architecture, design\n\n"
                            "Respond with ONLY a JSON object, e.g. "
                            '{"tier": "simple", "confidence": 0.95}'
                        ),
                    },
                    {"role": "user", "content": message},
                ],
                max_tokens=50,
                temperature=0,
            )
            raw = response.choices[0].message.content.strip()
            data = json.loads(raw)
            tier = data.get("tier", "simple")
            confidence = data.get("confidence", 0.5)
            return {
                "tier": tier,
                "confidence": confidence,
                "method": "ml-gemini-flash-lite",
            }
        except Exception:
            logger.debug("ML classification failed, falling back to rules", exc_info=True)
            return None

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
