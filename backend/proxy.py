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
from carbon import get_carbon_optimal_region
from router import compute_savings
from ledger import ledger
from verifier import verifier
from websocket_manager import ws_manager

logger = logging.getLogger("EcoQuery.proxy")


class CarbonAwareProxy:
    """Routes LLM requests to the greenest available provider/region."""

    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "")
        self.aws_key = os.getenv("AWS_ACCESS_KEY_ID", "")
        self.aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        self.vertex_key = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        self.openrouter_key = os.getenv("OPENAI_API_KEY", "")
        self.ollama_region = os.getenv("OLLAMA_REGION", "eu-north-1")

    def get_available_providers(self) -> list:
        """Return list of available providers with their regions."""
        providers = []

        # Ollama (self-hosted VPS) — highest priority (real region pinning)
        if self.ollama_url:
            providers.append({
                "name": "ollama",
                "regions": [self.ollama_region],
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

        # OpenRouter always available as fallback
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
        # Get optimal region based on carbon intensity
        region_info = await get_carbon_optimal_region()
        region_code = region_info["region"]
        carbon_intensity = region_info["carbon_intensity_g_kwh"]

        # Check which providers support this region
        providers = self.get_available_providers()

        # Prefer self-hosted (Ollama) — real region pinning
        self_hosted = [p for p in providers if p.get("is_self_hosted")]
        if self_hosted:
            return await self._call_ollama(
                model_id, messages, max_tokens, carbon_intensity
            )

        # Then prefer providers with region pinning
        region_providers = [p for p in providers if region_code in p.get("regions", [])]
        pinned_providers = [p for p in region_providers if p["supports_region_pinning"]]

        if pinned_providers:
            provider = pinned_providers[0]
            return await self._call_pinned_provider(
                provider, region_code, model_id, messages, max_tokens, carbon_intensity
            )
        elif region_providers:
            provider = region_providers[0]
            return await self._call_pinned_provider(
                provider, region_code, model_id, messages, max_tokens, carbon_intensity
            )
        else:
            # Fallback to OpenRouter (no region pinning)
            return await self._call_openrouter(
                region_code, model_id, messages, max_tokens, carbon_intensity
            )

    async def _call_ollama(
        self, model_id: str, messages: list, max_tokens: int, carbon_intensity: float
    ) -> dict:
        """Call self-hosted Ollama instance (real region pinning)."""
        try:
            # Ollama uses OpenAI-compatible API
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.ollama_url}/v1/chat/completions",
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
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            return {
                "content": content,
                "provider": "ollama",
                "region": self.ollama_region,
                "carbon_intensity": carbon_intensity,
                "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
            }
        except Exception as e:
            logger.warning(f"Ollama call failed: {e}")
            # Fallback to OpenRouter
            return await self._call_openrouter(
                self.ollama_region, model_id, messages, max_tokens, carbon_intensity
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
            "deepseek-v4-flash": "deepseek.v4-flash",
            "ling-3.0-flash": "inclusionai.ling-3.0-flash",
            "laguna-s-2.1": "poolside.laguna-s-2.1",
            "mimo-v2.5": "xiaomi.mimo-v2.5",
            "north-mini-code": "cohere.north-mini-code",
            "nemotron-3-ultra": "nvidia.nemotron-3-ultra",
        }
        return mapping.get(model_id, model_id)


proxy = CarbonAwareProxy()
