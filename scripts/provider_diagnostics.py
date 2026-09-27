"""Run independent, redacted completion checks for configured providers.

Usage from the repository root:
    python scripts/provider_diagnostics.py
"""

import asyncio
import os
import time

from openai import AsyncOpenAI


TARGETS = {
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "meta-llama/llama-4-scout"),
    "grok": ("GROK_API_KEY", "https://api.x.ai/v1", "grok-beta"),
    "google": ("GOOGLE_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-1.5-pro"),
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
        result.update({"status": "failed", "failure_reason": type(exc).__name__})
    result["latency_seconds"] = round(time.perf_counter() - started, 3)
    return result


async def main() -> None:
    results = await asyncio.gather(*(check(provider, *target) for provider, target in TARGETS.items()))
    for result in results:
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
