"""
Multi-provider inference for EcoQuery.
Priority: direct API -> OpenRouter fallback.
Supported: OpenAI, Anthropic, Google Gemini, OpenRouter.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger("EcoQuery.providers")


class ProviderRouter:
    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.is_openrouter = self.openai_key.startswith("sk-or-")

    def get_target(self, model_id: str) -> tuple:
        """Return (client_kwargs, model_name, provider_name, client_class).

        Priority:
        1. Anthropic direct for Claude models
        2. Gemini direct for Gemini models
        3. OpenAI direct for GPT models (non-OpenRouter key)
        4. OpenRouter fallback
        """
        if "claude" in model_id and self.anthropic_key:
            return (
                {"api_key": self.anthropic_key},
                model_id,
                "anthropic-direct",
                "anthropic.Anthropic",
            )

        if "gemini" in model_id and self.gemini_key:
            return (
                {"api_key": self.gemini_key},
                model_id,
                "gemini-direct",
                "google.generativeai",
            )

        if not self.is_openrouter and self.openai_key:
            return (
                {"api_key": self.openai_key},
                model_id,
                "openai-direct",
                "openai.OpenAI",
            )

        # OpenRouter fallback
        return (
            {"api_key": self.openai_key, "base_url": "https://openrouter.ai/api/v1"},
            model_id,
            "openrouter",
            "openai.OpenAI",
        )

    async def chat_completion(
        self, model_id: str, messages: list, max_tokens: int = 1024
    ) -> dict:
        """Unified chat completion across all providers.

        Returns: {"content": str, "usage": {"prompt_tokens": int, "completion_tokens": int}}
        """
        client_kwargs, target_model, provider, client_name = self.get_target(model_id)
        import openai

        if provider == "anthropic-direct":
            try:
                import anthropic

                client = anthropic.Anthropic(**client_kwargs)
                response = client.messages.create(
                    model=target_model,
                    max_tokens=max_tokens,
                    messages=[{"role": m["role"], "content": m["content"]} for m in messages],
                )
                content = response.content[0].text if response.content else ""
                usage = {"prompt_tokens": 0, "completion_tokens": 0}
                if hasattr(response, "usage"):
                    usage["prompt_tokens"] = getattr(response.usage, "input_tokens", 0)
                    usage["completion_tokens"] = getattr(response.usage, "output_tokens", 0)
                return {"content": content, "usage": usage}
            except Exception as e:
                logger.warning(f"Anthropic direct failed, falling back: {e}")

        if provider == "gemini-direct":
            try:
                import google.generativeai as genai

                genai.configure(**client_kwargs)
                model = genai.GenerativeModel(target_model)
                response = model.generate_content(messages[-1]["content"] if messages else "")
                return {
                    "content": response.text,
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                }
            except Exception as e:
                logger.warning(f"Gemini direct failed, falling back: {e}")

        # OpenAI / OpenRouter path (default)
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
            logger.error(f"OpenAI/OpenRouter call failed: {e}")
            return {"content": f"Provider error: {e}", "usage": {"prompt_tokens": 0, "completion_tokens": 0}}

    async def stream_completion(
        self, model_id: str, messages: list, max_tokens: int = 1024
    ):
        """Streaming unified chat completion.

        Yields: str tokens
        After completion, the caller should handle ledger/writing.
        """
        client_kwargs, target_model, provider, client_name = self.get_target(model_id)

        if provider == "anthropic-direct":
            try:
                import anthropic

                client = anthropic.Anthropic(**client_kwargs)
                with client.messages.stream(
                    model=target_model,
                    max_tokens=max_tokens,
                    messages=[{"role": m["role"], "content": m["content"]} for m in messages],
                ) as stream:
                    for text in stream.text_stream:
                        yield text
                return
            except Exception as e:
                logger.warning(f"Anthropic direct stream failed, falling back: {e}")

        if provider == "gemini-direct":
            try:
                import google.generativeai as genai

                genai.configure(**client_kwargs)
                model = genai.GenerativeModel(target_model)
                response = model.generate_content(
                    messages[-1]["content"] if messages else "",
                    stream=True,
                )
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
                return
            except Exception as e:
                logger.warning(f"Gemini direct stream failed, falling back: {e}")

        # OpenAI / OpenRouter streaming
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
            logger.error(f"OpenAI/OpenRouter stream failed: {e}")
            yield f"Stream error: {e}"


provider_router = ProviderRouter()
