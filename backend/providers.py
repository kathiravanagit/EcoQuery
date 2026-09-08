"""OpenRouter inference for EcoQuery."""

import os
import logging

logger = logging.getLogger("EcoQuery.providers")


class ProviderRouter:
    def __init__(self):
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        self.openrouter_key_2 = os.getenv("OPENROUTER_API_KEY_2", "")

    def get_target(self, model_id: str) -> tuple:
        """Return OpenRouter client settings for a model."""
        return (
            {"api_key": self.openrouter_key, "base_url": "https://openrouter.ai/api/v1"},
            model_id,
            "openrouter",
        )

    FALLBACK_MODELS = [
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "meta-llama/llama-4-scout",
        "openai/gpt-oss-120b:free",
        "deepseek/deepseek-chat-v3-0324:free",
        "openai/gpt-oss-20b:free",
        "google/gemma-4-31b:free",
    ]

    async def chat_completion(
        self, model_id: str, messages: list, max_tokens: int = 1024
    ) -> dict:
        """Unified chat completion.

        Returns: {"content": str, "usage": {"prompt_tokens": int, "completion_tokens": int}}
        """
        client_kwargs, target_model, provider = self.get_target(model_id)
        result = await self._openrouter_call(client_kwargs, target_model, messages, max_tokens)

        if not result.get("content") and provider == "openrouter":
            for fb in self.FALLBACK_MODELS:
                if fb == target_model:
                    continue
                try:
                    result = await self._openrouter_call(client_kwargs, fb, messages, max_tokens)
                    if result.get("content"):
                        logger.info(f"Fallback to {fb} succeeded")
                        break
                except Exception:
                    continue

        return result

    async def _openrouter_call(self, client_kwargs, target_model, messages, max_tokens):
        from openai import AsyncOpenAI
        try:
            client = AsyncOpenAI(**client_kwargs, timeout=60.0)
            response = await client.chat.completions.create(
                model=target_model,
                messages=messages,
                max_tokens=max_tokens,
            )
            choices = response.choices or []
            if not choices:
                logger.warning(f"OpenRouter returned no choices for model={target_model}")
                return {
                    "content": "",
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                }
            choice = choices[0]
            content = choice.message.content if choice.message else ""
            finish = choice.finish_reason
            logger.info(f"OpenRouter response: model={target_model}, finish={finish}, content_len={len(content) if content else 0}, content_preview={repr(content[:100]) if content else 'None'}")
            if not content:
                content = "The model did not generate a response. Please try again."
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
            error_str = str(e)
            if self.openrouter_key_2 and any(code in error_str for code in ("402", "401", "credit", "balance", "quota", "rate")):
                logger.warning(f"Primary key failed ({error_str[:80]}), retrying with secondary key")
                try:
                    fallback_kwargs = {**client_kwargs, "api_key": self.openrouter_key_2}
                    client = AsyncOpenAI(**fallback_kwargs, timeout=60.0)
                    response = await client.chat.completions.create(
                        model=target_model,
                        messages=messages,
                        max_tokens=max_tokens,
                    )
                    choices = response.choices or []
                    content = choices[0].message.content if choices and choices[0].message else ""
                    prompt_tokens = response.usage.prompt_tokens if response.usage else 0
                    completion_tokens = response.usage.completion_tokens if response.usage else 0
                    return {
                        "content": content,
                        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
                    }
                except Exception as e2:
                    logger.error(f"Secondary key also failed: {e2}")
                    return {"content": "I'm sorry, I encountered an error connecting to the model provider.", "usage": {"prompt_tokens": 0, "completion_tokens": 0}}
            logger.error(f"OpenRouter call failed: {e}")
            return {"content": "I'm sorry, I encountered an error connecting to the model provider.", "usage": {"prompt_tokens": 0, "completion_tokens": 0}}

    async def stream_completion(
        self, model_id: str, messages: list, max_tokens: int = 1024
    ):
        """Streaming chat completion.

        Yields: str tokens
        """
        client_kwargs, target_model, provider = self.get_target(model_id)
        async for token in self._openrouter_stream(client_kwargs, target_model, messages, max_tokens):
            yield token

    async def _openrouter_stream(self, client_kwargs, target_model, messages, max_tokens):
        from openai import AsyncOpenAI
        client = AsyncOpenAI(**client_kwargs, timeout=60.0)
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
            error_str = str(e)
            if self.openrouter_key_2 and any(code in error_str for code in ("402", "401", "credit", "balance", "quota", "rate")):
                logger.warning(f"Primary key stream failed, retrying with secondary key")
                try:
                    fallback_kwargs = {**client_kwargs, "api_key": self.openrouter_key_2}
                    client = AsyncOpenAI(**fallback_kwargs, timeout=60.0)
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
                    return
                except Exception as e2:
                    logger.error(f"Secondary key stream also failed: {e2}")
                    yield "Stream error: Connection to provider failed."
                    return
            logger.error(f"OpenRouter stream failed: {e}")
            yield "Stream error: Connection to provider failed."


provider_router = ProviderRouter()
