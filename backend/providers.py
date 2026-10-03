"""Inference router for EcoQuery with dynamic multi-provider API Key fallback."""

import logging
import os
from openai import AsyncOpenAI
import json
import time
from key_manager import key_manager
from circuit_breaker import is_outage, provider_breaker

logger = logging.getLogger("EcoQuery.providers")

# Known endpoints for providers compatible with OpenAI spec. The legacy
# failover order below remains unchanged; additional providers are tried only
# when configured or supplied on a request.
# see `providers_to_try`: OpenRouter is first because its catalogue models are
# free, Google is the automatic failover, and xAI's Grok runs last because it
# is billed per token and must never precede a free route.
PROVIDER_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai/",
    # xAI exposes an OpenAI-compatible surface under /v1.
    "grok": "https://api.x.ai/v1",
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    # Anthropic's compatibility endpoint accepts the OpenAI client shape.
    "anthropic": "https://api.anthropic.com/v1",
}

# Model used when the selected OpenRouter id is not valid on a provider's own
# API. `gemini-1.5-pro` was retired from the OpenAI-compatible surface and now
# returns 404, which made every Google failover attempt fail instantly instead
# of serving as a fallback. `gemini-flash-latest` is Google's rolling alias and
# stays current without a code change. Grok is in the same position: it cannot
# take an OpenRouter slug either, so it answers on an xAI model of its own.
PROVIDER_FALLBACK_MODELS = {
    "google": "gemini-flash-latest",
    # Overridable because the health probe is the only thing that can confirm
    # an xAI model id, and that needs a credited account to reach. The `or` is
    # load-bearing: `os.getenv(k, default)` only applies when the variable is
    # *absent*, so an empty `GROK_MODEL=` would otherwise send a blank model id
    # on every failover and break Grok in a way no test would catch.
    "grok": os.getenv("GROK_MODEL") or "grok-4-fast",
    "openai": os.getenv("OPENAI_MODEL") or "gpt-4o-mini",
    "groq": os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile",
    "anthropic": os.getenv("ANTHROPIC_MODEL") or "claude-3-5-haiku-latest",
}

# Failover order for both the completion and the streaming path.
PROVIDER_FALLBACK_ORDER = ("openrouter", "google", "grok")


# ── Bring your own key ──────────────────────────────────────────────────────
# Optional per-request credentials, accepted from one header per provider:
#   X-OpenRouter-Key  a key for openrouter
#   X-Google-Key      a key for google
#   X-Grok-Key        a key for grok — that is xAI, not Groq; the two are
#                     unrelated companies and a Groq credential (gsk_...) is
#                     rejected by api.x.ai
#   X-OpenAI-Key      a key for openai
#   X-Groq-Key        a key for groq
#   X-Anthropic-Key   a key for anthropic
# plus the original generic form:
#   X-Provider-Key    a key for the provider named in X-Provider
#                     (default `openrouter`)
# Every value is used for one outbound call and nothing else: none is ever
# passed to `key_manager`, written to the usage ledger or the response cache,
# or interpolated into a log line — a BYOK failure is logged with the
# exception type only, because provider SDK errors can quote the credential.
BYOK_SENTINEL_ID = "__byok__"
BYOK_MAX_KEY_LENGTH = 512

# Header name -> provider, for the per-provider form.
BYOK_HEADERS = {
    "X-OpenRouter-Key": "openrouter",
    "X-Google-Key": "google",
    "X-Grok-Key": "grok",
    "X-OpenAI-Key": "openai",
    "X-Groq-Key": "groq",
    "X-Anthropic-Key": "anthropic",
}


def _byok_value(headers, name: str) -> str:
    """Header value trimmed and validated, or `''` when unusable.

    A malformed or oversized header is treated as absent rather than as an
    error: the caller still gets a working request on the server's keys, and a
    provider would reject a truncated credential anyway. Dropping one provider's
    key must not discard the others, which is why this is per header.
    """
    raw_value = headers.get(name)
    value = raw_value.strip() if isinstance(raw_value, str) else ""
    return value if 0 < len(value) <= BYOK_MAX_KEY_LENGTH else ""


def extract_byok_keys(headers) -> dict[str, str]:
    """Return `{provider: key}` for every BYOK header supplied, possibly empty.

    Accepts any mapping with a `.get`. Starlette's headers are case-insensitive,
    which is a superset of what this needs; tests pass plain dicts.
    """
    if headers is None:
        return {}

    keys: dict[str, str] = {}
    for name, provider in BYOK_HEADERS.items():
        value = _byok_value(headers, name)
        if value:
            keys[provider] = value

    # The generic form, kept for callers following the original contract.
    # `setdefault` keeps the specific header authoritative when both name the
    # same provider.
    generic = _byok_value(headers, "X-Provider-Key")
    if generic:
        raw_candidate = headers.get("X-Provider")
        candidate = (
            raw_candidate.strip().lower()
            if isinstance(raw_candidate, str) else "openrouter"
        )
        provider = candidate if candidate in PROVIDER_BASE_URLS else "openrouter"
        keys.setdefault(provider, generic)

    return keys


def _key_source(grouped_keys: dict) -> dict[str, str]:
    """Which credential backs each provider for this request.

    `user` when the caller supplied one, `server` when only server keys are
    configured, `none` when neither. This answers where each provider *would*
    draw its key from; `provider_lineage.final_provider` says which provider
    actually served the call. Values only — a key is never included.
    """
    source: dict[str, str] = {}
    providers = list(PROVIDER_FALLBACK_ORDER)
    providers.extend(
        provider for provider in PROVIDER_BASE_URLS if provider not in providers
    )
    for provider in providers:
        bucket = grouped_keys.get(provider, [])
        if not bucket:
            source[provider] = "none"
        elif any(entry.get("byok") for entry in bucket):
            source[provider] = "user"
        else:
            source[provider] = "server"
    return source


def _providers_to_try(grouped_keys: dict, byok_keys: dict[str, str] | None) -> list[str]:
    """Caller-supplied providers lead; the configured fallback order follows.

    A provider the caller handed us a key for is tried before every
    server-configured one, so their own credential is what gets used instead
    of sitting behind the server's defaults. `_with_byok` already puts their
    key first *within* a bucket, so the two together deliver the documented
    promise: their key, then ours. Everything else keeps
    PROVIDER_FALLBACK_ORDER, and providers neither party mentioned are never
    tried.

    Only keys that would actually be injected count as supplied -- an empty or
    blank value is discarded by `_with_byok`, so it must not reorder the list
    either and promote that provider's server key ahead of a real one.
    """
    supplied = [
        provider
        for provider, key in (byok_keys or {}).items()
        if provider in PROVIDER_BASE_URLS and isinstance(key, str) and key.strip()
    ]
    ordered: list[str] = []
    for provider in (*supplied, *PROVIDER_FALLBACK_ORDER, *grouped_keys.keys()):
        if provider in PROVIDER_BASE_URLS and provider not in ordered:
            ordered.append(provider)
    return ordered


def _attempt_order(grouped_keys: dict, providers_to_try: list[str]) -> list[tuple[str, list[dict]]]:
    """Flatten to one batch per key so caller keys lead across *all* providers.

    `_with_byok` only puts a supplied key ahead of its own provider's server
    keys, so a provider sitting earlier in the fallback order could still
    answer with a server credential while a perfectly good caller key waited
    behind it. Sorting the flattened list by ownership -- stably, so provider
    order survives inside each group -- means a supplied key is only ever
    beaten by another supplied key.

    Each batch holds exactly one key so the callers' existing nested loop
    keeps its shape and only the outer iteration changes.
    """
    batches = [
        (provider, [key_data])
        for provider in providers_to_try
        for key_data in grouped_keys.get(provider, [])
    ]
    batches.sort(key=lambda item: 0 if item[1][0].get("byok") else 1)
    return batches


def _with_byok(grouped_keys: dict, byok_keys: dict[str, str] | None) -> tuple[dict, int, bool]:
    """Prepend each caller key to its own provider bucket.

    Returns `(keys, server_key_count, byok_injected)`. Putting a supplied key
    first means it is tried before that provider's server keys, while every
    server key after it remains as the fallback the API contract promises. A
    provider the caller said nothing about is left untouched.
    """
    server_key_count = sum(len(v) for v in grouped_keys.values())
    if not byok_keys:
        return grouped_keys, server_key_count, False

    merged = {provider: list(bucket) for provider, bucket in grouped_keys.items()}
    injected = False
    for provider, key in byok_keys.items():
        if (
            provider not in PROVIDER_BASE_URLS
            or not isinstance(key, str)
            or not (0 < len(key.strip()) <= BYOK_MAX_KEY_LENGTH)
        ):
            continue
        bucket = merged.setdefault(provider, [])
        bucket.insert(0, {
            "id": BYOK_SENTINEL_ID,
            "key_value": key.strip(),
            "byok": True,
        })
        injected = True

    if not injected:
        return grouped_keys, server_key_count, False
    return merged, server_key_count, True


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
        byok_keys: dict[str, str] | None = None,
    ) -> dict:
        """Unified chat completion with strict fallback routing."""
        grouped_keys = key_manager.get_all_providers_keys()
        grouped_keys, server_key_count, byok_injected = _with_byok(grouped_keys, byok_keys)

        # Priority order of providers to try
        providers_to_try = _providers_to_try(grouped_keys, byok_keys)
        
        last_error = None
        attempts = []
        batches = _attempt_order(grouped_keys, providers_to_try)
        # A provider that has been failing is skipped rather than paid for
        # again -- but never so many that nothing is left: partition always
        # leaves at least one to attempt, so an open breaker can degrade
        # latency without ever becoming an outage of our own making.
        allowed, tripped = provider_breaker.partition([p for p, _keys in batches])
        for skipped in tripped:
            attempts.append({
                "provider": skipped,
                "model": provider_target_model(skipped, model_id),
                "status": "skipped",
                "failure_reason": "CircuitOpen",
            })
        allowed = set(allowed)
        for provider, keys in batches:
            if provider not in allowed:
                continue
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
                    provider_breaker.record_success(provider)
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
                        # Per-provider key ownership for this request. Values
                        # only — a credential is never echoed back.
                        "key_source": _key_source(grouped_keys),
                    }
                    return result
                except Exception as e:
                    last_error = e
                    attempts.append({"provider": provider, "model": target_model, "status": "failed", "latency_seconds": round(time.perf_counter() - started_at, 3), "failure_reason": type(e).__name__})
                    if is_outage(e):
                        # A 400 means we wrote the request badly; a 429 or a
                        # timeout means this provider did not serve us. Only
                        # the second kind earns a trip.
                        provider_breaker.record_failure(provider)
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
        byok_keys: dict[str, str] | None = None,
    ):
        """Streaming chat completion with strict fallback routing."""
        grouped_keys = key_manager.get_all_providers_keys()
        grouped_keys, server_key_count, byok_injected = _with_byok(grouped_keys, byok_keys)
        providers_to_try = _providers_to_try(grouped_keys, byok_keys)
        attempts = []
        last_error = None
        
        batches = _attempt_order(grouped_keys, providers_to_try)
        allowed, tripped = provider_breaker.partition([p for p, _keys in batches])
        for skipped in tripped:
            attempts.append({
                "provider": skipped,
                "model": provider_target_model(skipped, model_id),
                "status": "skipped",
                "failure_reason": "CircuitOpen",
            })
        allowed = set(allowed)
        for provider, keys in batches:
            if provider not in allowed:
                continue
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
                        provider_breaker.record_success(provider)
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
                            "key_source": _key_source(grouped_keys),
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
                    if is_outage(e):
                        provider_breaker.record_failure(provider)
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
        providers = _providers_to_try(
            key_manager.get_all_providers_keys(), None
        )
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
                    # Carry the HTTP status like provider_diagnostics.py does:
                    # a bare `PermissionDeniedError` cannot distinguish "bad
                    # key" from "valid key, account has no credits", which is
                    # exactly the difference an operator needs to see.
                    status_code = getattr(e, "status_code", None)
                    status["failure_reason"] = (
                        f"{type(e).__name__}({status_code})"
                        if status_code is not None
                        else type(e).__name__
                    )
                    if not any(code in str(e).lower() for code in ("401", "403", "unauthorized", "invalid api key")):
                        status["authenticated"] = True # It reached the server but failed completion
            health[provider] = status
            
        return health

provider_router = ProviderRouter()
