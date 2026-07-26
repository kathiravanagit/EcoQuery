import os
import logging
import asyncio
import openai

logger = logging.getLogger("EcoQuery.classifier")

CLASSIFY_PROMPT = """Classify this user query into exactly one tier based on the REASONING DEPTH required to answer it well. Do not classify by length or topic familiarity.

- simple: A factual lookup, quick definition, or casual request. The answer can be given from a single fact or a short sentence. Examples: "What is the capital of France?", "Set a timer for 5 minutes", "Translate hello to Spanish"
- medium: Requires connecting a few facts, explaining a concept clearly, or solving a straightforward problem. One clear line of reasoning. Examples: "How does photosynthesis work?", "Write a Python function to sort a list", "Summarize this article"
- complex: Requires deep reasoning, multi-step analysis, multiple perspectives, or synthesizing information across domains. The answer benefits from a larger, more capable model. Examples: "Explain quantum entanglement and its implications for cryptography", "Compare REST vs GraphQL for a real-time collaborative app", "Derive the time complexity of quicksort and prove its average case"

Reply with ONLY one word: simple, medium, or complex.

Query: """

class QueryClassifier:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                return None
            kwargs = {"api_key": api_key}
            if api_key.startswith("sk-or-"):
                kwargs["base_url"] = "https://openrouter.ai/api/v1"
            self._client = openai.OpenAI(**kwargs)
        return self._client

    async def classify(self, message: str) -> dict:
        result = await asyncio.to_thread(self._classify_with_llm, message)
        if result:
            return result
        return self._classify_heuristic(message)

    def _classify_with_llm(self, message: str) -> dict | None:
        client = self._get_client()
        if client is None:
            return None
        try:
            model = "openai/gpt-4o-mini"
            if not os.getenv("OPENAI_API_KEY", "").startswith("sk-or-"):
                model = "gpt-4o-mini"
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": CLASSIFY_PROMPT + message}],
                max_tokens=10,
                temperature=0.0,
            )
            tier = response.choices[0].message.content.strip().lower()
            if tier in ("simple", "medium", "complex"):
                logger.info(f"LLM classifier: '{tier}' for query: {message[:60]}...")
                return {
                    "tier": tier,
                    "confidence": 0.95,
                    "method": "llm-classifier"
                }
            return None
        except Exception as e:
            logger.warning(f"LLM classifier failed: {e}. Using heuristic fallback.")
            return None

    def _classify_heuristic(self, message: str) -> dict:
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
            "method": "heuristic"
        }

classifier = QueryClassifier()
