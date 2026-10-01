"""Inference router for EcoQuery with dynamic multi-provider API Key fallback."""

import logging
from openai import AsyncOpenAI
import json
import time
from key_manager import key_manager

logger = logging.getLogger("EcoQuery.providers")

# Known endpoints for providers compatible with OpenAI spec.
# Two credentials only: OpenRouter is tried first, Google is the automatic
# failover. Order matters — see `providers_to_try`.
PROVIDER_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai/"
}

# Model used when the selected OpenRouter id is not valid on a provider's own
# API. `gemini-1.5-pro` was retired from the OpenAI-compatible surface and now
# returns 404, which made every Google failover attempt fail instantly instead
# of serving as a fallback. `gemini-flash-latest` is Google's rolling alias and
# stays current without a code change.
PROVIDER_FALLBACK_MODELS = {
    "google": "gemini-flash-latest",
}

# Failover order for both the completion and the streaming path.
PROVIDER_FALLBACK_ORDER = ("openrouter", "google")


# ── Bring your own key ──────────────────────────────────────────────────────
# Optional per-request credentials, accepted from two headers:
#   X-OpenRouter-Key  shorthand for the default provider
#   X-Provider-Key    a key for the provider named in `X-Provider`
#                     (default `openrouter`)
# The value is used for one outbound call and nothing else: it is never passed
# to `key_manager`, never written to the usage ledger or the response cache,
# and never interpolated into a log line — a BYOK failure is logged with the
# exception type only, because provider SDK errors can quote the credential.
BYOK_SENTINEL_ID = "__byok__"
BYOK_MAX_KEY_LENGTH = 512


def extract_byok_key(headers) -> tuple[str, str] | None:
    """Return `(provider, key)` from the BYOK headers, or `None` when absent.

    Accepts any mapping with a `.get`. Starlette's headers are case-insensitive,
    which is a superset of what this needs; tests pass plain dicts.
    """
    if headers is None:
        return None

    openrouter_key = (headers.get("X-OpenRouter-Key") or "").strip()
    generic_key = (headers.get("X-Provider-Key") or "").strip()

    provider = "openrouter"
    key = ""
    if openrouter_key:
        key = openrouter_key
    elif generic_key:
        key = generic_key
        candidate = (headers.get("X-Provider") or "openrouter").strip().lower()
        provider = candidate if candidate in PROVIDER_BASE_URLS else "openrouter"

    # A malformed or oversized header is treated as absent rather than as an
    # error: the caller still gets a working request on the server's keys.
    if not key or len(key) > BYOK_MAX_KEY_LENGTH:
        return None
    return provider, key


def _with_byok(grouped_keys: dict, byok: tuple[str, str] | None) -> tuple[dict, int, bool]:
    """Prepend the caller's key to its provider bucket.

    Returns `(keys, server_key_count, byok_injected)`. Putting it first means it
    is tried before any server key, while every server key after it remains as
    the fallback the API contract promises.
    """
    server_key_count = sum(len(v) for v in grouped_keys.values())
    if not byok:
        return grouped_keys, server_key_count, False
    provider, key = byok
    bucket = list(grouped_keys.get(provider, []))
    bucket.insert(0, {"id": BYOK_SENTINEL_ID, "key_value": key, "byok": True})
    return {**grouped_keys, provider: bucket}, server_key_count, True


def provider_target_model(provider: str, model_id: str) -> str:
    """Model id to send to `provider`, falling back to its own family model."""
    return PROVIDER_FALLBACK_MODELS.get(provider, model_id)


# Model used by `check_health` to prove a provider can actually generate text.
# Must be a genuinely free OpenRouter slug — a paid one spends credit on every
# health poll, and a dead one fails the probe for the wrong reason. It also has
# to produce text at the probe's 64-token budget: `nemotron-3-super-120b` and
# `qwen3.8-27b` both intermittently return an empty reply at that size, which
# would read as an unhealthy provider. Ultra-550B answered every trial at
# budgets 16, 64 and 256.
HEALTH_PROBE_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"


class ProviderRouter:
    def __init__(self):
        pass

    def get_target(self, model_id: str) -> tuple:
        """Return target configuration for a model."""
        return model_id, "openrouter" # default, logic will be handled in execution

    async def chat_completion(
        self, model_id: str, messages: list, max_tokens: int = 1024,
        byok: tuple[str, str] | None = None,
    ) -> dict:
        """Unified chat completion with strict fallback routing."""
        grouped_keys = key_manager.get_all_providers_keys()
        grouped_keys, server_key_count, byok_injected = _with_byok(grouped_keys, byok)

        # Priority order of providers to try
        providers_to_try = list(PROVIDER_FALLBACK_ORDER)
        
        last_error = None
        attempts = []
        for provider in providers_to_try:
            keys = grouped_keys.get(provider, [])
            if not keys:
                continue
                
            for key_data in keys:
                key_id = key_data["id"]
                api_key = key_data["key_value"]
                is_byok = bool(key_data.get("byok"))
                
                target_model = provider_target_model(provider, model_id)
                base_url = PROVIDER_BASE_URLS.get(provider)
                
                try:
                    started_at = time.perf_counter()
                    result = await self._call_provider(api_key, base_url, target_model, messages, max_tokens)
                    latency = round(time.perf_counter() - started_at, 3)
                    if not (result.get("content") or "").strip():
                        # The provider answered, but with no text: a safety block,
                        # or a `max_tokens` budget a reasoning model spends before
                        # it emits a token (gemini-flash-latest returns content=None
                        # at max_tokens=16). Falling through unrecorded left the
                        # request dying with "all providers failed" while
                        # `provider_attempts` showed this provider as never tried.
                        attempts.append({"provider": provider, "model": target_model, "status": "empty_response", "latency_seconds": latency, "failure_reason": "EmptyContent"})
                        if not is_byok:
                            key_manager.log_usage(key_id, provider, target_model, 0, "empty response")
                        logger.warning(f"{provider} returned no text for {target_model}; trying the next provider")
                        continue
                    attempts.append({"provider": provider, "model": target_model, "status": "success", "latency_seconds": latency})
                    if not is_byok:
                        key_manager.log_usage(key_id, provider, target_model, result.get("usage", {}).get("completion_tokens", 0), "success")
                    logger.info(f"Successfully generated with {provider} using model {target_model}")
                    result["provider_lineage"] = {
                        "requested_provider": "openrouter",
                        "requested_model": model_id,
                        "attempted_providers": attempts,
                        "final_provider": provider,
                        "final_model": target_model,
                        "fallback_reason": "provider fallback" if len(attempts) > 1 else None,
                        "success": True,
                        # Which credential served the call — never the key.
                        "byok_used": is_byok,
                    }
                    return result
                except Exception as e:
                    last_error = e
                    attempts.append({"provider": provider, "model": target_model, "status": "failed", "latency_seconds": round(time.perf_counter() - started_at, 3), "failure_reason": type(e).__name__})
                    if is_byok:
                        # The credential belongs to the caller: log the exception
                        # type only (provider SDK errors can quote the key), record
                        # no usage against a server key, and never mark one
                        # inactive because of it.
                        logger.warning(
                            "Supplied API key rejected by %s (%s); falling back to server keys",
                            provider, type(e).__name__,
                        )
                    else:
                        logger.warning(f"Key {key_id} for {provider} failed: {e}")
                        key_manager.log_usage(key_id, provider, target_model, 0, f"error: {str(e)[:50]}")

                        if any(code in str(e).lower() for code in ("401", "403", "expired", "invalid")):
                            key_manager.mark_key_inactive(key_id)
        
        # A supplied key with no server key behind it: the caller's credential
        # is the problem, so say so rather than blaming the service config.
        if byok_injected and server_key_count == 0:
            logger.warning(
                "Supplied API key was rejected (%s)",
                type(last_error).__name__ if last_error else "unknown",
            )
            raise RuntimeError(json.dumps({
                "success": False,
                "error_code": "PROVIDER_KEY_REJECTED",
                "message": "The supplied API key was rejected by the provider, and no server fallback key is configured.",
                "attempted_providers": providers_to_try,
                "provider_attempts": attempts,
                "last_failure_reason": type(last_error).__name__ if last_error else "Unknown"
            }))

        # Distinguish missing provider configuration from exhausted credentials.
        if not grouped_keys:
            logger.error("No active external model provider keys are configured")
            raise RuntimeError(json.dumps({
                "success": False,
                "error_code": "PROVIDER_UNAVAILABLE",
                "message": "No configured provider was able to process this request.",
                "attempted_providers": providers_to_try,
                "provider_attempts": []
            }))

        # If we exhausted all keys. Never interpolate the raw exception when a
        # caller-supplied key may be what failed.
        if byok_injected:
            logger.error(
                "All provider attempts failed with a supplied key present; last error type: %s",
                type(last_error).__name__ if last_error else "unknown",
            )
        else:
            logger.error(f"All API keys across all providers failed. Last error: {last_error}")
        raise RuntimeError(json.dumps({
            "success": False,
            "error_code": "PROVIDER_UNAVAILABLE",
            "message": "All configured providers failed to process this request.",
            "attempted_providers": providers_to_try,
            "provider_attempts": attempts,
            "last_failure_reason": type(last_error).__name__ if last_error else "Unknown"
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
        self, model_id: str, messages: list, max_tokens: int = 1024,
        byok: tuple[str, str] | None = None,
    ):
        """Streaming chat completion with strict fallback routing."""
        grouped_keys = key_manager.get_all_providers_keys()
        grouped_keys, server_key_count, byok_injected = _with_byok(grouped_keys, byok)
        providers_to_try = list(PROVIDER_FALLBACK_ORDER)
        attempts = []
        last_error = None
        
        for provider in providers_to_try:
            keys = grouped_keys.get(provider, [])
            for key_data in keys:
                key_id = key_data["id"]
                api_key = key_data["key_value"]
                is_byok = bool(key_data.get("byok"))
                
                target_model = provider_target_model(provider, model_id)
                
                base_url = PROVIDER_BASE_URLS.get(provider)
                
                try:
                    started_at = time.perf_counter()
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
                        attempts.append({"provider": provider, "model": target_model, "status": "success", "latency_seconds": round(time.perf_counter() - started_at, 3)})
                        if not is_byok:
                            key_manager.log_usage(key_id, provider, target_model, 10, "success") # Approx tokens for stream
                        yield {"provider_lineage": {
                            "requested_provider": "openrouter",
                            "requested_model": model_id,
                            "attempted_providers": attempts,
                            "final_provider": provider,
                            "final_model": target_model,
                            "fallback_reason": "provider fallback" if len(attempts) > 1 else None,
                            "success": True,
                            # Which credential served the call — never the key.
                            "byok_used": is_byok,
                        }}
                        return

                    # A stream that opened cleanly but produced no tokens has to
                    # be recorded like any other failure, otherwise the caller is
                    # told every provider failed while this one shows as skipped.
                    attempts.append({"provider": provider, "model": target_model, "status": "empty_response", "latency_seconds": round(time.perf_counter() - started_at, 3), "failure_reason": "EmptyContent"})
                    if not is_byok:
                        key_manager.log_usage(key_id, provider, target_model, 0, "empty response")
                    logger.warning(f"Streaming from {provider} produced no text for {target_model}; trying the next provider")
                        
                except Exception as e:
                    last_error = e
                    attempts.append({"provider": provider, "model": target_model, "status": "failed", "latency_seconds": round(time.perf_counter() - started_at, 3), "failure_reason": type(e).__name__})
                    if is_byok:
                        # Caller-owned credential: exception type only, and no
                        # server key is logged or deactivated because of it.
                        logger.warning(
                            "Streaming: supplied API key rejected by %s (%s); falling back to server keys",
                            provider, type(e).__name__,
                        )
                    else:
                        logger.warning(f"Streaming failed for {provider} key {key_id}: {e}")
                        key_manager.log_usage(key_id, provider, target_model, 0, f"error: {str(e)[:50]}")
                        if any(code in str(e).lower() for code in ("401", "403", "expired", "invalid")):
                            key_manager.mark_key_inactive(key_id)

        if byok_injected and server_key_count == 0:
            logger.warning(
                "Supplied API key was rejected while streaming (%s)",
                type(last_error).__name__ if last_error else "unknown",
            )
            raise RuntimeError(json.dumps({
                "success": False,
                "error_code": "PROVIDER_KEY_REJECTED",
                "message": "The supplied API key was rejected by the provider, and no server fallback key is configured.",
                "attempted_providers": providers_to_try,
                "provider_attempts": attempts
            }))

        raise RuntimeError(json.dumps({
            "success": False,
            "error_code": "PROVIDER_UNAVAILABLE",
            "message": "All configured providers failed to stream this request.",
            "attempted_providers": providers_to_try,
            "provider_attempts": attempts
        }))

    async def check_health(self) -> dict:
        """Check the health of all supported providers."""
        providers = list(PROVIDER_FALLBACK_ORDER)
        health = {}
        
        for provider in providers:
            keys = key_manager.get_active_keys(provider)
            configured = len(keys) > 0
            
            target_model = provider_target_model(provider, HEALTH_PROBE_MODEL)
                
            status = {
                "configured": configured,
                "authenticated": False,
                "completion_test": False,
                "model": target_model if configured else None
            }
            
            if configured:
                api_key = keys[0]["key_value"]
                base_url = PROVIDER_BASE_URLS.get(provider)
                started_at = time.perf_counter()
                try:
                    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=10.0)
                    response = await client.chat.completions.create(
                        model=target_model,
                        messages=[{"role": "user", "content": "Hello"}],
                        # Not 5: at a tiny budget a reasoning model returns
                        # choices with no text, which used to count as a pass.
                        max_tokens=64,
                    )
                    status["authenticated"] = True
                    message = response.choices[0].message if response.choices else None
                    text = (getattr(message, "content", "") or "") if message else ""
                    status["latency_seconds"] = round(time.perf_counter() - started_at, 3)
                    if text.strip():
                        status["completion_test"] = True
                        status["failure_reason"] = None
                    else:
                        # Reached and authenticated, but nothing usable came
                        # back — report that rather than a clean pass.
                        status["failure_reason"] = "EmptyContent"
                except Exception as e:
                    logger.warning(f"Health check failed for {provider}: {e}")
                    status["latency_seconds"] = round(time.perf_counter() - started_at, 3)
                    status["failure_reason"] = type(e).__name__
                    if not any(code in str(e).lower() for code in ("401", "403", "unauthorized", "invalid api key")):
                        status["authenticated"] = True # It reached the server but failed completion
            health[provider] = status
            
        return health

provider_router = ProviderRouter()
