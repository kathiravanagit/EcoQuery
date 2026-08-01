"""
Carbon-Aware LLM Executor — actually calls Bedrock/Vertex AI/Ollama in the greenest region.
Routes requests in real-time to the lowest-carbon datacenter.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Optional
from carbon_collector import collector
from region_scorer import scorer

logger = logging.getLogger("EcoQuery.carbon_executor")


class CarbonAwareExecutor:
    """Routes and executes LLM requests to the greenest provider/region."""

    def __init__(self):
        self.aws_key = os.getenv("AWS_ACCESS_KEY_ID", "")
        self.aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        self.vertex_cred = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        self.openrouter_key = os.getenv("OPENAI_API_KEY", "")
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "")
        self.ollama_region = os.getenv("OLLAMA_REGION", "eu-north-1")

    async def execute(self, messages: list, model: str = "auto", max_tokens: int = 1024) -> dict:
        """Execute LLM request on greenest available provider.

        Returns:
            {
                "content": str,
                "provider": str,
                "region": str,
                "intensity": float,
                "energy_source": str,
                "is_green": bool,
            }
        """
        # Get carbon data for all available regions
        candidates = []

        # Ollama (self-hosted)
        if self.ollama_url:
            intensity_data = await collector.get_intensity(self.ollama_region)
            candidates.append({
                "provider": "ollama",
                "region": self.ollama_region,
                "intensity": intensity_data["intensity"],
                "energy": intensity_data.get("energy", {}),
                "execute_fn": self._call_ollama,
            })

        # AWS Bedrock regions
        if self.aws_key:
            bedrock_regions = {
                "eu-west-1": "Ireland",
                "eu-west-2": "London",
                "eu-central-1": "Frankfurt",
                "us-west-2": "Oregon",
            }
            for region, name in bedrock_regions.items():
                intensity_data = await collector.get_intensity(region)
                candidates.append({
                    "provider": "aws-bedrock",
                    "region": region,
                    "name": name,
                    "intensity": intensity_data["intensity"],
                    "energy": intensity_data.get("energy", {}),
                    "execute_fn": self._call_bedrock,
                })

        # Google Vertex AI regions
        if self.vertex_cred:
            vertex_regions = {
                "europe-west1": "Belgium",
                "europe-west4": "Netherlands",
                "us-central1": "Iowa",
            }
            for region, name in vertex_regions.items():
                intensity_data = await collector.get_intensity(region)
                candidates.append({
                    "provider": "google-vertex",
                    "region": region,
                    "name": name,
                    "intensity": intensity_data["intensity"],
                    "energy": intensity_data.get("energy", {}),
                    "execute_fn": self._call_vertex,
                })

        # OpenRouter (fallback)
        if self.openrouter_key:
            intensity_data = await collector.get_intensity("eu-west-1")
            candidates.append({
                "provider": "openrouter",
                "region": "global",
                "intensity": intensity_data["intensity"],
                "energy": intensity_data.get("energy", {}),
                "execute_fn": self._call_openrouter,
            })

        if not candidates:
            raise RuntimeError("No providers configured")

        # Score and rank
        ranked = []
        for c in candidates:
            score = scorer.score_region(
                region=c["region"],
                intensity=c["intensity"],
                energy_mix=c.get("energy"),
            )
            c["score"] = score
            ranked.append(c)

        ranked.sort(key=lambda x: x["score"].total_score)

        # Execute on greenest provider
        best = ranked[0]
        logger.info(
            f"Routing to {best['provider']} in {best['region']} "
            f"({best['intensity']}g CO₂/kWh, score: {best['score'].total_score})"
        )

        try:
            result = await best["execute_fn"](messages, model, max_tokens)
            return {
                "content": result["content"],
                "provider": best["provider"],
                "region": best["region"],
                "intensity": best["intensity"],
                "energy_source": best["score"].primary_energy,
                "is_green": best["score"].is_green,
                "score": best["score"].total_score,
                "usage": result.get("usage", {}),
                "alternatives": [
                    {
                        "provider": c["provider"],
                        "region": c["region"],
                        "intensity": c["intensity"],
                        "score": c["score"].total_score,
                    }
                    for c in ranked[1:3]
                ],
            }
        except Exception as e:
            logger.error(f"Provider {best['provider']} failed: {e}")
            # Try next provider
            for c in ranked[1:]:
                try:
                    result = await c["execute_fn"](messages, model, max_tokens)
                    return {
                        "content": result["content"],
                        "provider": c["provider"],
                        "region": c["region"],
                        "intensity": c["intensity"],
                        "energy_source": c["score"].primary_energy,
                        "is_green": c["score"].is_green,
                        "score": c["score"].total_score,
                        "usage": result.get("usage", {}),
                        "fallback": True,
                    }
                except Exception:
                    continue
            raise RuntimeError("All providers failed")

    async def _call_ollama(self, messages: list, model: str, max_tokens: int) -> dict:
        """Call self-hosted Ollama."""
        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.ollama_url}/v1/chat/completions",
                json={"model": model or "llama3.2", "messages": messages, "max_tokens": max_tokens},
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        return {
            "content": data["choices"][0]["message"]["content"],
            "usage": data.get("usage", {}),
        }

    async def _call_bedrock(self, messages: list, model: str, max_tokens: int) -> dict:
        """Call AWS Bedrock."""
        import boto3
        import json as json_mod

        bedrock = boto3.client(
            "bedrock-runtime",
            region_name="eu-west-1",
            aws_access_key_id=self.aws_key,
            aws_secret_access_key=self.aws_secret,
        )

        bedrock_model = model or "anthropic.claude-3-haiku-20240307-v1:0"
        response = bedrock.invoke_model(
            modelId=bedrock_model,
            body=json_mod.dumps({
                "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
                "max_tokens": max_tokens,
            }),
        )

        result = json_mod.loads(response["body"].read())
        return {
            "content": result.get("content", [{}])[0].get("text", ""),
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }

    async def _call_vertex(self, messages: list, model: str, max_tokens: int) -> dict:
        """Call Google Vertex AI."""
        import vertexai
        from vertexai.generative_models import GenerativeModel

        vertexai.init(project=os.getenv("GOOGLE_CLOUD_PROJECT"), location="europe-west1")
        gen_model = GenerativeModel(model or "gemini-2.0-flash")

        response = gen_model.generate_content(
            messages[-1]["content"] if messages else "",
            generation_config={"max_output_tokens": max_tokens},
        )

        return {
            "content": response.text,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }

    async def _call_openrouter(self, messages: list, model: str, max_tokens: int) -> dict:
        """Call OpenRouter."""
        import openai

        client = openai.OpenAI(
            api_key=self.openrouter_key,
            base_url="https://openrouter.ai/api/v1",
        )

        response = client.chat.completions.create(
            model=model or "deepseek-r1-0528:free",
            messages=messages,
            max_tokens=max_tokens,
        )

        return {
            "content": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens or 0 if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens or 0 if response.usage else 0,
            },
        }


executor = CarbonAwareExecutor()
