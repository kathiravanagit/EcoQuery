"""Run independent, redacted completion checks for configured providers.

Usage from the repository root:
    python scripts/provider_diagnostics.py
"""

import asyncio
import argparse
import os
import sys
import time

from openai import AsyncOpenAI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from providers import HEALTH_PROBE_MODEL, PROVIDER_BASE_URLS, PROVIDER_FALLBACK_MODELS  # noqa: E402


TARGETS = {
    "openrouter": ("OPENROUTER_API_KEY", PROVIDER_BASE_URLS["openrouter"], HEALTH_PROBE_MODEL),
    "google": ("GOOGLE_API_KEY", PROVIDER_BASE_URLS["google"], PROVIDER_FALLBACK_MODELS["google"]),
    "grok": ("GROK_API_KEY", PROVIDER_BASE_URLS["grok"], PROVIDER_FALLBACK_MODELS["grok"]),
    # Optional probes: these are not server-key defaults. Set one temporarily
    # when validating a user's provider credential.
    "openai": ("OPENAI_API_KEY", PROVIDER_BASE_URLS["openai"], PROVIDER_FALLBACK_MODELS["openai"]),
    "groq": ("GROQ_API_KEY", PROVIDER_BASE_URLS["groq"], PROVIDER_FALLBACK_MODELS["groq"]),
    "anthropic": ("ANTHROPIC_API_KEY", PROVIDER_BASE_URLS["anthropic"], PROVIDER_FALLBACK_MODELS["anthropic"]),
}

MODEL_CANDIDATES = {
    "google": ("gemini-2.5-flash-lite", "gemini-2.5-flash"),
    "openai": ("gpt-4o-mini", "gpt-4.1-mini"),
    "groq": ("llama-3.3-70b-versatile", "llama-3.1-8b-instant"),
    "anthropic": ("claude-3-5-haiku-latest", "claude-3-5-haiku-20241022"),
}


async def resolve_model(client: AsyncOpenAI, provider: str, preferred: str) -> tuple[str, str | None]:
    """Use the provider's live model catalog when available.

    Optional BYOK providers change model availability independently of
    EcoQuery, so a stale hardcoded model must not be treated as verified.
    """
    try:
        models = await client.models.list()
        available = {item.id for item in models.data}
    except Exception as exc:
        # Some compatible endpoints do not expose /models. Still run the
        # completion probe, but retain the limitation in the result.
        return preferred, f"model_list_unavailable:{type(exc).__name__}"

    if preferred in available:
        return preferred, None
    for candidate in MODEL_CANDIDATES.get(provider, ()):
        if candidate in available:
            return candidate, f"preferred_unavailable:{preferred}"
    return preferred, f"preferred_unavailable:{preferred}"


async def check(provider: str, env_name: str, base_url: str, model: str) -> dict:
    api_key = os.getenv(env_name, "")
    result = {"provider": provider, "model": model, "configured": bool(api_key), "status": "not_configured"}
    if not api_key:
        return result

    started = time.perf_counter()
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=15.0)
        model, model_note = await resolve_model(client, provider, model)
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with OK."}],
            # Not 5: a reasoning model can spend a tiny budget on its own
            # thinking and return choices with no text, which would otherwise
            # be reported as a healthy provider.
            max_tokens=64,
        )
        if not response.choices:
            result.update({"status": "no_completion", "failure_reason": None})
        elif not (response.choices[0].message.content or "").strip():
            result.update({"status": "empty_response", "failure_reason": None})
        else:
            result.update({"status": "ok", "failure_reason": model_note})
    except Exception as exc:  # diagnostic output must never include the credential
        # Include the HTTP status where available: a 404 means the model id is
        # wrong (a code bug), while 429/503 mean the key or quota is the problem.
        status_code = getattr(exc, "status_code", None)
        reason = type(exc).__name__
        if status_code is not None:
            reason = f"{reason}({status_code})"
        result.update({"status": "failed", "failure_reason": reason})
    result["latency_seconds"] = round(time.perf_counter() - started, 3)
    return result


async def main(required: set[str]) -> int:
    results = await asyncio.gather(*(check(provider, *target) for provider, target in TARGETS.items()))
    for result in results:
        print(result)
    failed_required = [
        result["provider"]
        for result in results
        if result["provider"] in required and result["status"] != "ok"
    ]
    if failed_required:
        print(f"Required provider probes failed: {', '.join(failed_required)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--require", nargs="*", choices=sorted(TARGETS), default=[])
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(set(args.require))))
