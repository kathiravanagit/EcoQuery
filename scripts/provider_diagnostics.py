"""Run independent, redacted completion checks for configured providers.

Usage from the repository root:
    python scripts/provider_diagnostics.py
"""

import asyncio
import os
import sys
import time

from openai import AsyncOpenAI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from providers import PROVIDER_BASE_URLS, PROVIDER_FALLBACK_MODELS  # noqa: E402


TARGETS = {
    "openrouter": ("OPENROUTER_API_KEY", PROVIDER_BASE_URLS["openrouter"], "meta-llama/llama-4-scout"),
    "google": ("GOOGLE_API_KEY", PROVIDER_BASE_URLS["google"], PROVIDER_FALLBACK_MODELS["google"]),
}


async def check(provider: str, env_name: str, base_url: str, model: str) -> dict:
    api_key = os.getenv(env_name, "")
    result = {"provider": provider, "model": model, "configured": bool(api_key), "status": "not_configured"}
    if not api_key:
        return result

    started = time.perf_counter()
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=15.0)
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with OK."}],
            max_tokens=5,
        )
        result.update({"status": "ok" if response.choices else "no_completion", "failure_reason": None})
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


async def main() -> None:
    results = await asyncio.gather(*(check(provider, *target) for provider, target in TARGETS.items()))
    for result in results:
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
