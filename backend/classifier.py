import os
import json
import logging
import asyncio
import openai

logger = logging.getLogger("EcoQuery.classifier")

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
PIPELINE_PATH = os.path.join(MODEL_DIR, "pipeline.pkl")


class QueryClassifier:
    def __init__(self):
        self._pipeline = None
        self._available = False
        self._load_model()

    def _load_model(self):
        import joblib
        try:
            if os.path.exists(PIPELINE_PATH):
                self._pipeline = joblib.load(PIPELINE_PATH)
                self._available = True
                logger.info("Loaded trained classifier pipeline from %s", PIPELINE_PATH)
            else:
                logger.info("No trained model found at %s — will use ML API or simple rules", PIPELINE_PATH)
        except Exception as e:
            logger.warning("Failed to load classifier model: %s", e)

    async def classify(self, message: str) -> dict:
        # Testing mode — skip everything and use deterministic rules
        if os.getenv("ECO_QUERY_TESTING") == "1":
            return self._classify_simple(message)

        # 1) Trained sklearn model (fastest, no API call)
        if self._available:
            try:
                return self._classify_sklearn(message)
            except Exception as e:
                logger.debug("Sklearn classification failed: %s", e)

        # 2) ML model via OpenRouter API
        result = await self._classify_ml(message)
        if result is not None:
            return result

        # 3) Fallback to simple heuristics
        return self._classify_simple(message)

    def _classify_sklearn(self, message: str) -> dict:
        proba = self._pipeline.predict_proba([message])[0]
        pred = self._pipeline.predict([message])[0]
        confidence = round(float(max(proba)), 3)
        return {
            "tier": str(pred),
            "confidence": confidence,
            "method": "sklearn-logistic-regression",
        }

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
            logger.debug("ML classification failed, falling back", exc_info=True)
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
