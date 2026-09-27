"""Inference router for EcoQuery with dynamic multi-provider API Key fallback."""

import logging
from openai import AsyncOpenAI
import json
from key_manager import key_manager

logger = logging.getLogger("EcoQuery.providers")

# Known endpoints for providers compatible with OpenAI spec
PROVIDER_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "grok": "https://api.x.ai/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai/"
}

class ProviderRouter:
    def __init__(self):
        pass

    def get_target(self, model_id: str) -> tuple:
        """Return target configuration for a model."""
        return model_id, "openrouter" # default, logic will be handled in execution

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
        """Unified chat completion with strict fallback routing."""
        grouped_keys = key_manager.get_all_providers_keys()
        
        # Priority order of providers to try
        providers_to_try = ["openrouter", "grok", "google"]
        
        last_error = None
        for provider in providers_to_try:
            keys = grouped_keys.get(provider, [])
            if not keys:
                continue
                
            for key_data in keys:
                key_id = key_data["id"]
                api_key = key_data["key_value"]
                
                # Determine model based on provider
                target_model = model_id
                if provider == "grok":
                    target_model = "grok-beta" # Grok generic model
                elif provider == "google":
                    target_model = "gemini-1.5-pro" # Google generic model
                
                base_url = PROVIDER_BASE_URLS.get(provider)
                
                try:
                    result = await self._call_provider(api_key, base_url, target_model, messages, max_tokens)
                    if result.get("content"):
                        key_manager.log_usage(key_id, provider, target_model, result.get("usage", {}).get("completion_tokens", 0), "success")
                        logger.info(f"Successfully generated with {provider} using model {target_model}")
                        return result
                except Exception as e:
                    last_error = e
                    logger.warning(f"Key {key_id} for {provider} failed: {e}")
                    key_manager.log_usage(key_id, provider, target_model, 0, f"error: {str(e)[:50]}")
                    
                    if any(code in str(e).lower() for code in ("401", "403", "expired", "invalid")):
                        key_manager.mark_key_inactive(key_id)
        
        # Distinguish missing provider configuration from exhausted credentials.
        if not grouped_keys:
            logger.error("No active external model provider keys are configured")
            raise RuntimeError(json.dumps({
                "success": False,
                "error_code": "PROVIDER_UNAVAILABLE",
                "message": "No configured provider was able to process this request.",
                "attempted_providers": providers_to_try
            }))

        # If we exhausted all keys
        logger.error(f"All API keys across all providers failed. Last error: {last_error}")
        raise RuntimeError(json.dumps({
            "success": False,
            "error_code": "PROVIDER_UNAVAILABLE",
            "message": "All configured providers failed to process this request.",
            "attempted_providers": providers_to_try,
            "last_error": str(last_error) if last_error else "Unknown"
        }))

    async def _call_provider(self, api_key, base_url, target_model, messages, max_tokens):
        client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=60.0)
        response = await client.chat.completions.create(
            model=target_model,
            messages=messages,
            max_tokens=max_tokens,
        )
        choices = response.choices or []
        if not choices:
            return {"content": "", "usage": {"prompt_tokens": 0, "completion_tokens": 0}}
            
        content = choices[0].message.content if choices[0].message else ""
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0
        
        return {
            "content": content,
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
        }

    async def stream_completion(
        self, model_id: str, messages: list, max_tokens: int = 1024
    ):
        """Streaming chat completion with strict fallback routing."""
        grouped_keys = key_manager.get_all_providers_keys()
        providers_to_try = ["openrouter", "grok", "google"]
        
        for provider in providers_to_try:
            keys = grouped_keys.get(provider, [])
            for key_data in keys:
                key_id = key_data["id"]
                api_key = key_data["key_value"]
                
                target_model = model_id
                if provider == "grok":
                    target_model = "grok-beta"
                elif provider == "google":
                    target_model = "gemini-1.5-pro"
                
                base_url = PROVIDER_BASE_URLS.get(provider)
                
                try:
                    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=60.0)
                    stream = await client.chat.completions.create(
                        model=target_model,
                        messages=messages,
                        max_tokens=max_tokens,
                        stream=True,
                    )
                    
                    emitted = False
                    async for chunk in stream:
                        delta = chunk.choices[0].delta if chunk.choices else None
                        token = (delta.content or "") if delta else ""
                        if token:
                            emitted = True
                            yield {"token": token}
                            
                    if emitted:
                        key_manager.log_usage(key_id, provider, target_model, 10, "success") # Approx tokens for stream
                        return
                        
                except Exception as e:
                    logger.warning(f"Streaming failed for {provider} key {key_id}: {e}")
                    key_manager.log_usage(key_id, provider, target_model, 0, f"error: {str(e)[:50]}")
                    if any(code in str(e).lower() for code in ("401", "403", "expired", "invalid")):
                        key_manager.mark_key_inactive(key_id)

        raise RuntimeError(json.dumps({
            "success": False,
            "error_code": "PROVIDER_UNAVAILABLE",
            "message": "All configured providers failed to stream this request.",
            "attempted_providers": providers_to_try
        }))

    async def check_health(self) -> dict:
        """Check the health of all supported providers."""
        grouped_keys = key_manager.get_all_providers_keys()
        providers = ["openrouter", "grok", "google"]
        health = {}
        
        for provider in providers:
            keys = grouped_keys.get(provider, [])
            configured = len(keys) > 0
            
            target_model = "meta-llama/llama-4-scout" # default light model for testing
            if provider == "grok":
                target_model = "grok-beta"
            elif provider == "google":
                target_model = "gemini-1.5-pro"
                
            status = {
                "configured": configured,
                "authenticated": False,
                "completion_test": False,
                "model": target_model if configured else None
            }
            
            if configured:
                api_key = keys[0]["key_value"]
                base_url = PROVIDER_BASE_URLS.get(provider)
                try:
                    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=10.0)
                    response = await client.chat.completions.create(
                        model=target_model,
                        messages=[{"role": "user", "content": "Hello"}],
                        max_tokens=5,
                    )
                    status["authenticated"] = True
                    if response.choices and len(response.choices) > 0:
                        status["completion_test"] = True
                except Exception as e:
                    logger.warning(f"Health check failed for {provider}: {e}")
                    if not any(code in str(e).lower() for code in ("401", "403", "unauthorized", "invalid api key")):
                        status["authenticated"] = True # It reached the server but failed completion
            health[provider] = status
            
        return health

provider_router = ProviderRouter()
