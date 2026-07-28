"""
Multi-provider inference for EcoQuery.
Uses OpenRouter with free models.
"""

import os
import logging

logger = logging.getLogger("EcoQuery.providers")


class ProviderRouter:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")

    def get_target(self, model_id: str) -> tuple:
        """Return (client_kwargs, model_name, provider_name)."""
        return (
            {"api_key": self.api_key, "base_url": "https://openrouter.ai/api/v1"},
            model_id,
            "openrouter",
        )

    async def chat_completion(
        self, model_id: str, messages: list, max_tokens: int = 1024
    ) -> dict:
        """Unified chat completion.

        Returns: {"content": str, "usage": {"prompt_tokens": int, "completion_tokens": int}}
        """
        client_kwargs, target_model, provider = self.get_target(model_id)
        import openai

        try:
            client = openai.OpenAI(**client_kwargs)
            response = client.chat.completions.create(
                model=target_model,
                messages=messages,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            prompt_tokens = 0
            completion_tokens = 0
            if response.usage:
                prompt_tokens = response.usage.prompt_tokens or 0
                completion_tokens = response.usage.completion_tokens or 0
            return {
                "content": content,
                "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
            }
        except Exception as e:
            logger.error(f"OpenRouter call failed: {e}")
            return {"content": f"Provider error: {e}", "usage": {"prompt_tokens": 0, "completion_tokens": 0}}

    async def stream_completion(
        self, model_id: str, messages: list, max_tokens: int = 1024
    ):
        """Streaming chat completion.

        Yields: str tokens
        """
        client_kwargs, target_model, provider = self.get_target(model_id)
        from openai import AsyncOpenAI

        client = AsyncOpenAI(**client_kwargs)
        try:
            stream = await client.chat.completions.create(
                model=target_model,
                messages=messages,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                token = (delta.content or "") if delta else ""
                if token:
                    yield token
        except Exception as e:
            logger.error(f"OpenRouter stream failed: {e}")
            yield f"Stream error: {e}"


provider_router = ProviderRouter()
