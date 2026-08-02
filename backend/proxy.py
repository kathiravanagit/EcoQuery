"""
Carbon-aware proxy for EcoQuery.
Routes requests to the greenest available datacenter.
Supports: Ollama (self-hosted VPS), AWS Bedrock, Google Vertex AI, OpenRouter (fallback).
"""

import os
import json
import logging
import time
import httpx
from datetime import datetime, timezone
from carbon import get_carbon_optimal_region, REGIONS, STATIC_REGIONAL_INTENSITY, ENERGY_SOURCE_PROFILES
from router import compute_savings
from ledger import ledger
from verifier import verifier
from websocket_manager import ws_manager
from vps_utils import parse_vps_endpoints

logger = logging.getLogger("EcoQuery.proxy")


class CarbonAwareProxy:
    """Routes LLM requests to the greenest available provider/region."""

    def __init__(self):
        self.openrouter_key = os.getenv("OPENAI_API_KEY", "")
        self.aws_key = os.getenv("AWS_ACCESS_KEY_ID", "")
        self.aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        self.vertex_key = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

        self.vps_endpoints = parse_vps_endpoints()

    def get_available_providers(self) -> list:
        """Return list of available providers with their regions."""
        providers = []

        # Self-hosted VPS (Ollama) — highest priority
        for ep in self.vps_endpoints:
            providers.append({
                "name": "ollama",
                "url": ep["url"],
                "regions": [ep["region"]],
                "supports_region_pinning": True,
                "is_self_hosted": True,
            })

        if self.aws_key and self.aws_secret:
            providers.append({
                "name": "aws-bedrock",
                "regions": ["eu-west-1", "eu-west-2", "us-east-1", "us-west-2"],
                "supports_region_pinning": True,
            })

        if self.vertex_key:
            providers.append({
                "name": "google-vertex",
                "regions": ["europe-west1", "us-central1", "us-east1"],
                "supports_region_pinning": True,
            })

        if self.openrouter_key:
            providers.append({
                "name": "openrouter",
                "regions": ["global"],
                "supports_region_pinning": False,
            })

        return providers

    async def route_to_greenest(self, model_id: str, messages: list, max_tokens: int = 1024) -> dict:
        """Route request to the greenest available provider/region.

        Returns: {
            "content": str,
            "provider": str,
            "region": str,
            "carbon_intensity": float,
            "usage": dict,
        }
        """
        providers = self.get_available_providers()
        self_hosted = [p for p in providers if p.get("is_self_hosted")]

        if self_hosted:
            # Pick the greenest VPS from available endpoints
            best_endpoint = None
            best_intensity = float("inf")

            for ep in self.vps_endpoints:
                region = ep["region"]
                intensity = STATIC_REGIONAL_INTENSITY.get(region, 500)
                if intensity < best_intensity:
                    best_intensity = intensity
                    best_endpoint = ep

            if best_endpoint:
                # Get real-time intensity if available
                region_info = await get_carbon_optimal_region()
                carbon_intensity = region_info.get("carbon_intensity_g_kwh", best_intensity)

                return await self._call_ollama(
                    best_endpoint["url"], model_id, messages, max_tokens,
                    carbon_intensity, best_endpoint["region"]
                )

        # Fallback chain
        region_info = await get_carbon_optimal_region()
        region_code = region_info["region"]
        carbon_intensity = region_info["carbon_intensity_g_kwh"]

        region_providers = [p for p in providers if region_code in p.get("regions", [])]
        pinned_providers = [p for p in region_providers if p["supports_region_pinning"]]

        if pinned_providers:
            return await self._call_pinned_provider(
                pinned_providers[0], region_code, model_id, messages, max_tokens, carbon_intensity
            )
        elif region_providers:
            return await self._call_pinned_provider(
                region_providers[0], region_code, model_id, messages, max_tokens, carbon_intensity
            )
        else:
            return await self._call_openrouter(
                region_code, model_id, messages, max_tokens, carbon_intensity
            )

    async def _call_ollama(
        self, base_url: str, model_id: str, messages: list,
        max_tokens: int, carbon_intensity: float, region: str
    ) -> dict:
        """Call a self-hosted Ollama instance."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{base_url}/v1/chat/completions",
                    json={
                        "model": model_id,
                        "messages": messages,
                        "max_tokens": max_tokens,
                    },
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            return {
                "content": content,
                "provider": "ollama",
                "region": region,
                "carbon_intensity": carbon_intensity,
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                },
            }
        except Exception as e:
            logger.warning(f"Ollama call failed ({base_url}): {e}")
            # Try other VPS endpoints
            for ep in self.vps_endpoints:
                if ep["url"] != base_url:
                    try:
                        return await self._call_ollama(
                            ep["url"], model_id, messages, max_tokens,
                            STATIC_REGIONAL_INTENSITY.get(ep["region"], 500), ep["region"]
                        )
                    except Exception:
                        continue
            # Final fallback to OpenRouter
            return await self._call_openrouter(
                region, model_id, messages, max_tokens, carbon_intensity
            )

    async def _call_pinned_provider(
        self, provider: dict, region_code: str, model_id: str,
        messages: list, max_tokens: int, carbon_intensity: float
    ) -> dict:
        """Call a provider with region pinning."""
        if provider["name"] == "aws-bedrock":
            return await self._call_aws_bedrock(
                region_code, model_id, messages, max_tokens, carbon_intensity
            )
        elif provider["name"] == "google-vertex":
            return await self._call_vertex_ai(
                region_code, model_id, messages, max_tokens, carbon_intensity
            )
        else:
            return await self._call_openrouter(
                region_code, model_id, messages, max_tokens, carbon_intensity
            )

    async def _call_aws_bedrock(
        self, region_code: str, model_id: str, messages: list,
        max_tokens: int, carbon_intensity: float
    ) -> dict:
        """Call AWS Bedrock with region pinning."""
        try:
            import boto3

            bedrock = boto3.client(
                "bedrock-runtime",
                region_name=region_code,
                aws_access_key_id=self.aws_key,
                aws_secret_access_key=self.aws_secret,
            )

            bedrock_model = self._map_to_bedrock_model(model_id)

            response = bedrock.invoke_model(
                modelId=bedrock_model,
                body=json.dumps({
                    "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
                    "max_tokens": max_tokens,
                }),
            )

            result = json.loads(response["body"].read())
            content = result.get("content", [{}])[0].get("text", "")

            return {
                "content": content,
                "provider": "aws-bedrock",
                "region": region_code,
                "carbon_intensity": carbon_intensity,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            }
        except Exception as e:
            logger.warning(f"AWS Bedrock failed: {e}")
            return await self._call_openrouter(
                region_code, model_id, messages, max_tokens, carbon_intensity
            )

    async def _call_vertex_ai(
        self, region_code: str, model_id: str, messages: list,
        max_tokens: int, carbon_intensity: float
    ) -> dict:
        """Call Google Vertex AI with region pinning."""
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel

            vertexai.init(project=os.getenv("GOOGLE_CLOUD_PROJECT"), location=region_code)
            model = GenerativeModel(model_id)
            response = model.generate_content(
                messages[-1]["content"] if messages else "",
                generation_config={"max_output_tokens": max_tokens},
            )

            return {
                "content": response.text,
                "provider": "google-vertex",
                "region": region_code,
                "carbon_intensity": carbon_intensity,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            }
        except Exception as e:
            logger.warning(f"Vertex AI failed: {e}")
            return await self._call_openrouter(
                region_code, model_id, messages, max_tokens, carbon_intensity
            )

    async def _call_openrouter(
        self, region_code: str, model_id: str, messages: list,
        max_tokens: int, carbon_intensity: float
    ) -> dict:
        """Fallback to OpenRouter (no region pinning)."""
        import openai

        client = openai.OpenAI(
            api_key=self.openrouter_key,
            base_url="https://openrouter.ai/api/v1",
        )

        response = client.chat.completions.create(
            model=model_id,
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
            "provider": "openrouter",
            "region": region_code,
            "carbon_intensity": carbon_intensity,
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        }

    def _map_to_bedrock_model(self, model_id: str) -> str:
        """Map OpenRouter model ID to Bedrock model ID."""
        mapping = {
            "nemotron-3-ultra-550b-a55b:free": "nvidia.nemotron",
            "nemotron-3-super-120b-a12b:free": "nvidia.nemotron",
            "gemma-4-31b-it:free": "google.gemma4",
            "gpt-oss-20b:free": "openai.gpt-oss",
            "north-mini-code:free": "cohere.north",
            "ling-3.0-flash:free": "inclusionai.ling",
        }
        return mapping.get(model_id, model_id)


proxy = CarbonAwareProxy()
