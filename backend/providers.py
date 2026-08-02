"""
Multi-provider inference for EcoQuery.
Supports OpenRouter (free models), direct Anthropic, Gemini, and OpenAI.
"""

import os
import logging

logger = logging.getLogger("EcoQuery.providers")


class ProviderRouter:
    def __init__(self):
        self.openrouter_key = os.getenv("OPENAI_API_KEY", "")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_key = os.getenv("OPENAI_DIRECT_KEY", "")

    def get_target(self, model_id: str) -> tuple:
        """Return (client_kwargs, model_name, provider_name)."""
        if model_id.startswith("claude-") and self.anthropic_key:
            return (
                {"api_key": self.anthropic_key},
                model_id,
                "anthropic",
            )
        if model_id.startswith("gemini-") and self.gemini_key:
            return (
                {"api_key": self.gemini_key},
                model_id,
                "gemini",
            )
        return (
            {"api_key": self.openrouter_key, "base_url": "https://openrouter.ai/api/v1"},
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

        if provider == "anthropic":
            return await self._anthropic_call(target_model, messages, max_tokens)
        elif provider == "gemini":
            return await self._gemini_call(target_model, messages, max_tokens)
        else:
            return await self._openrouter_call(client_kwargs, target_model, messages, max_tokens)

    async def _openrouter_call(self, client_kwargs, target_model, messages, max_tokens):
        from openai import AsyncOpenAI
        try:
            client = AsyncOpenAI(**client_kwargs, timeout=60.0)
            response = await client.chat.completions.create(
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

    async def _anthropic_call(self, model_id, messages, max_tokens):
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self.anthropic_key)
            system_msg = ""
            user_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    user_messages.append(msg)
            response = await client.messages.create(
                model=model_id,
                max_tokens=max_tokens,
                system=system_msg if system_msg else None,
                messages=user_messages,
            )
            content = response.content[0].text if response.content else ""
            return {
                "content": content,
                "usage": {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                },
            }
        except Exception as e:
            logger.error(f"Anthropic call failed: {e}")
            return {"content": f"Provider error: {e}", "usage": {"prompt_tokens": 0, "completion_tokens": 0}}

    async def _gemini_call(self, model_id, messages, max_tokens):
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_key)
            model = genai.GenerativeModel(model_id)
            contents = []
            for msg in messages:
                role = "user" if msg["role"] in ("user", "assistant") else "user"
                contents.append({"role": role, "parts": [msg["content"]]})
            response = await model.generate_content_async(
                contents,
                generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens),
            )
            content = response.text or ""
            return {
                "content": content,
                "usage": {
                    "prompt_tokens": response.usage_metadata.prompt_token_count if response.usage_metadata else 0,
                    "completion_tokens": response.usage_metadata.candidates_token_count if response.usage_metadata else 0,
                },
            }
        except Exception as e:
            logger.error(f"Gemini call failed: {e}")
            return {"content": f"Provider error: {e}", "usage": {"prompt_tokens": 0, "completion_tokens": 0}}

    async def stream_completion(
        self, model_id: str, messages: list, max_tokens: int = 1024
    ):
        """Streaming chat completion.

        Yields: str tokens
        """
        client_kwargs, target_model, provider = self.get_target(model_id)

        if provider == "anthropic":
            async for token in self._anthropic_stream(target_model, messages, max_tokens):
                yield token
        elif provider == "gemini":
            async for token in self._gemini_stream(target_model, messages, max_tokens):
                yield token
        else:
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
            logger.error(f"OpenRouter stream failed: {e}")
            yield f"Stream error: {e}"

    async def _anthropic_stream(self, model_id, messages, max_tokens):
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self.anthropic_key)
            system_msg = ""
            user_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    user_messages.append(msg)
            async with client.messages.stream(
                model=model_id,
                max_tokens=max_tokens,
                system=system_msg if system_msg else None,
                messages=user_messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Anthropic stream failed: {e}")
            yield f"Stream error: {e}"

    async def _gemini_stream(self, model_id, messages, max_tokens):
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_key)
            model = genai.GenerativeModel(model_id)
            contents = []
            for msg in messages:
                role = "user" if msg["role"] in ("user", "assistant") else "user"
                contents.append({"role": role, "parts": [msg["content"]]})
            response = await model.generate_content_async(
                contents,
                generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens),
                stream=True,
            )
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Gemini stream failed: {e}")
            yield f"Stream error: {e}"


provider_router = ProviderRouter()
