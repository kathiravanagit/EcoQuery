"""
Ollama endpoint — direct self-hosted inference.
Bypasses OpenRouter entirely, calls your VPS Ollama instance directly.
Auto-routes to greenest VPS if multiple are configured.
"""

import os
import time
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
import httpx

from schemas import ChatRequest, ChatResponse
from auth import get_current_user
from classifier import classifier
from carbon import get_carbon_optimal_region
from carbon_collector import collector
from region_scorer import scorer
from router import compute_savings
from ledger import ledger
from verifier import verifier
from websocket_manager import ws_manager

logger = logging.getLogger("EcoQuery.ollama")
router = APIRouter(prefix="/api/ollama", tags=["ollama"])


def _parse_vps_endpoints() -> list:
    """Parse OLLAMA_ENDPOINTS env var into list of {url, region} dicts."""
    raw = os.getenv("OLLAMA_ENDPOINTS", "")
    if not raw:
        url = os.getenv("OLLAMA_BASE_URL", "")
        region = os.getenv("OLLAMA_REGION", "eu-north-1")
        if url:
            return [{"url": url, "region": region}]
        return []

    endpoints = []
    for part in raw.split(","):
        part = part.strip()
        if ":" in part:
            parts = part.rsplit(":", 1)
            if len(parts) == 2:
                url, region = parts
                endpoints.append({"url": url.rstrip("/"), "region": region})
    return endpoints


async def _pick_greenest_vps(endpoints: list) -> dict:
    """Pick the greenest VPS endpoint based on real-time carbon intensity."""
    best = None
    best_score = float("inf")

    for ep in endpoints:
        region = ep["region"]
        try:
            zone = _map_region_to_zone(region)
            if zone:
                intensity_data = await collector.get_intensity(zone)
                intensity = intensity_data["intensity"]
            else:
                intensity = _static_intensity(region)
        except Exception:
            intensity = _static_intensity(region)

        score = scorer.score_region(region=region, intensity=intensity)

        if score.total_score < best_score:
            best_score = score.total_score
            best = {
                "url": ep["url"],
                "region": region,
                "intensity": intensity,
                "score": score.total_score,
                "is_green": score.is_green,
            }

    return best


def _static_intensity(region: str) -> float:
    """Fallback static intensity per region."""
    STATIC = {
        "eu-north-1": 13, "eu-west-3": 55, "eu-central-1": 180,
        "eu-west-1": 300, "us-west-1": 80, "us-east-1": 350,
        "ap-south-1": 700, "ap-northeast-1": 500,
    }
    return STATIC.get(region, 300)


def _map_region_to_zone(region: str) -> str | None:
    """Map VPS region to Electricity Maps zone."""
    ZONE_MAP = {
        "eu-north-1": "SE", "eu-west-3": "FR", "eu-central-1": "DE",
        "eu-west-1": "IE", "us-west-1": "US-NW", "us-east-1": "US-VIRGINIA-CAROLINAS",
        "ap-south-1": "IN-SOUTH", "ap-northeast-1": "JP",
    }
    return ZONE_MAP.get(region)


async def _call_ollama(base_url: str, model: str, messages: list, max_tokens: int = 1024) -> dict:
    """Call Ollama instance."""
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{base_url}/v1/chat/completions",
            json={"model": model, "messages": messages, "max_tokens": max_tokens},
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return {
        "content": content,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
    }


@router.post("/chat", response_model=ChatResponse)
async def ollama_chat(req: ChatRequest, request: Request):
    """Direct Ollama chat — routes to greenest self-hosted VPS.

    No OpenRouter involved. Pure self-hosted inference.
    """
    start_time = time.time()
    endpoints = _parse_vps_endpoints()

    if not endpoints:
        raise HTTPException(
            status_code=503,
            detail="No Ollama endpoints configured. Set OLLAMA_ENDPOINTS or OLLAMA_BASE_URL env var."
        )

    classification = await classifier.classify(req.message)
    prompt_len = len(req.message)

    greenest = await _pick_greenest_vps(endpoints)
    if not greenest:
        greenest = {"url": endpoints[0]["url"], "region": endpoints[0]["region"],
                     "intensity": _static_intensity(endpoints[0]["region"]), "score": 5, "is_green": False}

    # Default to a good Ollama model
    model = req.model_id or "llama3.2:latest"

    result = None
    last_error = None

    # Try greenest first, then fallback through all endpoints
    ordered = [greenest] + [ep for ep in endpoints if ep["url"] != greenest["url"]]
    for ep in ordered:
        try:
            result = await _call_ollama(ep["url"], model, [{"role": "user", "content": req.message}])
            greenest = ep
            break
        except Exception as e:
            last_error = e
            logger.warning(f"Ollama failed at {ep['url']}: {e}")
            continue

    if result is None:
        raise HTTPException(status_code=502, detail=f"All Ollama endpoints failed. Last error: {last_error}")

    # Get real-time carbon data for the region we actually used
    try:
        zone = _map_region_to_zone(greenest["region"])
        if zone:
            intensity_data = await collector.get_intensity(zone)
            carbon_intensity = intensity_data["intensity"]
        else:
            carbon_intensity = greenest["intensity"]
    except Exception:
        carbon_intensity = greenest["intensity"]

    savings = compute_savings(10, carbon_intensity, prompt_length=prompt_len)  # Ollama = carbon score 10
    worst_savings = compute_savings(6, 710.0, prompt_length=prompt_len)
    latency_seconds = round(time.time() - start_time, 3)

    v_result = verifier.verify_completion(
        model_id=model, prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
        latency_seconds=latency_seconds, reported_co2_g=savings["estimated_co2_g"],
    )

    user_email = ""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if token.startswith("eq_"):
            try:
                from auth import auth_db
                user = await auth_db.collection.find_one({"api_key": token})
                if user:
                    user_email = user.get("email", "")
            except Exception:
                pass
        else:
            from jose import JWTError, jwt
            from auth import SECRET_KEY, ALGORITHM
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                user_email = payload.get("sub", "")
            except JWTError:
                pass

    await ledger.record_query({
        "query": req.message, "tier": classification["tier"],
        "model_used": model, "model_provider": "ollama",
        "model_tier": "self-hosted", "carbon_score": 10,
        "region": greenest["region"], "energy_source": "self-hosted",
        "co2_estimated": savings["estimated_co2_g"],
        "co2_saved_vs_baseline": savings["saved_vs_baseline_g"],
        "is_mocked": False, "classifier_method": classification["method"],
        "classifier_confidence": classification["confidence"],
        "carbon_method": "greenest-vps", "api_cost": 0.0,
        "latency_seconds": latency_seconds,
        "verification_status": v_result["status"],
        "verification_confidence": v_result["confidence"],
        "observed_tps": v_result["observed_tps"],
        "integrity_hash": v_result.get("integrity_hash", ""),
        "routing_mode": "ollama", "is_local_inference": True,
    }, user_email=user_email)

    if user_email:
        await ws_manager.broadcast_to_user(user_email, "query.routed", {
            "query": req.message[:100], "tier": classification["tier"],
            "model": model, "region": greenest["region"],
            "co2_g": savings["estimated_co2_g"],
            "co2_saved_g": savings["saved_vs_baseline_g"],
            "api_cost": 0.0, "mode": "ollama",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return ChatResponse(
        reply=result["content"],
        metadata={
            "model_used": f"ollama/{model} (self-hosted)",
            "model_id": model, "model_tier": "self-hosted",
            "carbon_score": 10, "region": greenest["region"],
            "energy_source": "self-hosted",
            "co2_estimated_g": savings["estimated_co2_g"],
            "co2_saved_g": savings["saved_vs_baseline_g"],
            "tier": classification["tier"],
            "confidence": round(classification["confidence"], 3),
            "is_mocked": False, "api_cost": 0.0,
            "latency_seconds": latency_seconds,
            "verification_status": v_result["status"],
            "verification_reason": v_result["reason"],
            "observed_tps": v_result["observed_tps"],
            "integrity_hash": v_result.get("integrity_hash", ""),
            "routing_mode": "ollama",
            "is_local_inference": True,
            "proxy_provider": "ollama",
            "proxy_region_pinned": True,
            "what_if": {
                "baseline_model": "nemotron-3-ultra",
                "baseline_region": "ap-south-1 (Mumbai)",
                "baseline_co2_g": worst_savings["estimated_co2_g"],
                "actual_model": model,
                "actual_region": greenest["region"],
                "actual_co2_g": savings["estimated_co2_g"],
                "co2_saved_g": round(worst_savings["estimated_co2_g"] - savings["estimated_co2_g"], 4),
                "baseline_cost": 0.0, "actual_cost": 0.0,
            },
        }
    )


@router.post("/chat/stream")
async def ollama_chat_stream(req: ChatRequest, request: Request):
    """Streaming Ollama chat — direct to self-hosted VPS."""
    start_time = time.time()
    endpoints = _parse_vps_endpoints()

    if not endpoints:
        raise HTTPException(status_code=503, detail="No Ollama endpoints configured.")

    classification = await classifier.classify(req.message)
    prompt_len = len(req.message)
    model = req.model_id or "llama3.2:latest"
    greenest = await _pick_greenest_vps(endpoints)
    if not greenest:
        greenest = {"url": endpoints[0]["url"], "region": endpoints[0]["region"],
                     "intensity": _static_intensity(endpoints[0]["region"]), "score": 5, "is_green": False}

    full_reply = ""

    async def generate():
        nonlocal full_reply
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream(
                    "POST", f"{greenest['url']}/v1/chat/completions",
                    json={"model": model, "messages": [{"role": "user", "content": req.message}], "max_tokens": 1024, "stream": True},
                    headers={"Content-Type": "application/json"},
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            chunk = json.loads(line[6:])
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                full_reply += token
                                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            logger.warning(f"Ollama stream failed: {e}")
            full_reply = f"Error: {e}"
            yield f"data: {json.dumps({'token': full_reply})}\n\n"

        latency_seconds = round(time.time() - start_time, 3)
        try:
            zone = _map_region_to_zone(greenest["region"])
            if zone:
                intensity_data = await collector.get_intensity(zone)
                carbon_intensity = intensity_data["intensity"]
            else:
                carbon_intensity = greenest["intensity"]
        except Exception:
            carbon_intensity = greenest["intensity"]

        savings = compute_savings(10, carbon_intensity, prompt_length=prompt_len)
        worst_savings = compute_savings(6, 710.0, prompt_length=prompt_len)

        metadata = {
            "model_used": f"ollama/{model} (self-hosted)",
            "model_id": model, "model_tier": "self-hosted",
            "carbon_score": 10, "region": greenest["region"],
            "energy_source": "self-hosted",
            "co2_estimated_g": savings["estimated_co2_g"],
            "co2_saved_g": savings["saved_vs_baseline_g"],
            "tier": classification["tier"],
            "is_mocked": False, "api_cost": 0.0,
            "latency_seconds": latency_seconds,
            "routing_mode": "ollama",
            "is_local_inference": True,
            "proxy_provider": "ollama",
            "what_if": {
                "baseline_model": "nemotron-3-ultra",
                "baseline_co2_g": worst_savings["estimated_co2_g"],
                "actual_model": model,
                "actual_co2_g": savings["estimated_co2_g"],
                "co2_saved_g": round(worst_savings["estimated_co2_g"] - savings["estimated_co2_g"], 4),
            },
        }
        yield f"data: {json.dumps({'done': True, 'metadata': metadata})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/endpoints")
async def list_ollama_endpoints():
    """List configured Ollama endpoints with their regions."""
    endpoints = _parse_vps_endpoints()
    results = []
    for ep in endpoints:
        results.append({
            "url": ep["url"],
            "region": ep["region"],
            "intensity": _static_intensity(ep["region"]),
        })
    return {"endpoints": results, "count": len(results)}
