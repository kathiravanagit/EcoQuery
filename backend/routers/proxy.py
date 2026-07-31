"""
Carbon-aware proxy endpoint.
Routes requests to the greenest available datacenter.
Supports multiple self-hosted VPS instances across green regions.
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from schemas import ChatRequest, ChatResponse
from auth import get_current_user
from models import CARBON_MODELS
from classifier import classifier
from carbon import get_carbon_optimal_region
from router import compute_savings
from ledger import ledger
from verifier import verifier
from websocket_manager import ws_manager
from proxy import proxy

logger = logging.getLogger("EcoQuery.proxy_router")
router = APIRouter(prefix="/api/proxy", tags=["proxy"])


@router.post("/chat", response_model=ChatResponse)
async def proxy_chat(req: ChatRequest, request: Request):
    """Carbon-aware chat endpoint.

    Routes to the greenest available provider/region.
    Supports multiple self-hosted VPS instances across green regions.
    Fallback chain: Ollama VPS → AWS Bedrock → Vertex AI → OpenRouter.
    """
    start_time = time.time()

    # Classify the query
    classification = await classifier.classify(req.message)
    prompt_len = len(req.message)

    # Get optimal region
    region_info = await get_carbon_optimal_region()
    carbon_intensity = region_info["carbon_intensity_g_kwh"]

    # Select model based on tier
    from router import route_query
    routing = await route_query(classification["tier"], prompt_length=prompt_len)
    model_sel = routing["model"]
    savings = routing["savings"]

    # Allow model override
    if req.model_id:
        for m in CARBON_MODELS:
            if m["id"] == req.model_id:
                model_sel = {
                    "model": m["id"],
                    "provider": m["provider"],
                    "display_name": f"{m['provider']} {m['id']}",
                    "openrouter_id": m["openrouter_id"],
                    "tier": m["tier"],
                    "carbon_score": m["carbon_score"],
                    "estimated_latency_s": model_sel.get("estimated_latency_s", 2.0),
                    "reason": m["description"]
                }
                intensity = region_info.get("carbon_intensity_g_kwh", 200.0)
                savings = compute_savings(model_sel["carbon_score"], intensity, prompt_length=prompt_len)
                break

    # Route to greenest provider (handles multiple VPS endpoints)
    target_model = model_sel["openrouter_id"] or model_sel["model"]
    result = await proxy.route_to_greenest(
        model_id=target_model,
        messages=[{"role": "user", "content": req.message}],
        max_tokens=1024,
    )

    reply_content = result["content"]
    actual_region = result["region"]
    actual_provider = result["provider"]
    actual_intensity = result["carbon_intensity"]
    usage = result.get("usage", {})

    # Calculate savings
    actual_co2 = compute_savings(model_sel["carbon_score"], actual_intensity, prompt_length=prompt_len)
    worst_co2 = compute_savings(9, 710.0, prompt_length=prompt_len)

    latency_seconds = round(time.time() - start_time, 3)

    # Verify
    v_result = verifier.verify_completion(
        model_id=model_sel["model"],
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        latency_seconds=latency_seconds,
        reported_co2_g=actual_co2["estimated_co2_g"],
    )

    # Record
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
        "query": req.message,
        "tier": classification["tier"],
        "model_used": model_sel["model"],
        "model_provider": actual_provider,
        "model_tier": model_sel["tier"],
        "carbon_score": model_sel["carbon_score"],
        "region": actual_region,
        "energy_source": region_info.get("energy_source", "unknown"),
        "co2_estimated": actual_co2["estimated_co2_g"],
        "co2_saved_vs_baseline": actual_co2["saved_vs_baseline_g"],
        "is_mocked": False,
        "classifier_method": classification["method"],
        "classifier_confidence": classification["confidence"],
        "carbon_method": region_info.get("method", "static"),
        "api_cost": 0.0,
        "latency_seconds": latency_seconds,
        "verification_status": v_result["status"],
        "verification_confidence": v_result["confidence"],
        "observed_tps": v_result["observed_tps"],
        "integrity_hash": v_result.get("integrity_hash", ""),
        "routing_mode": "eco",
        "is_local_inference": False,
    }, user_email=user_email)

    # Get available providers for metadata
    available = proxy.get_available_providers()
    provider_names = [p["name"] for p in available]

    return ChatResponse(
        reply=reply_content,
        metadata={
            "model_used": model_sel["display_name"],
            "model_id": model_sel["model"],
            "model_tier": model_sel["tier"],
            "carbon_score": model_sel["carbon_score"],
            "region": actual_region,
            "energy_source": region_info.get("energy_source", "unknown"),
            "co2_estimated_g": actual_co2["estimated_co2_g"],
            "co2_saved_g": actual_co2["saved_vs_baseline_g"],
            "tier": classification["tier"],
            "confidence": round(classification["confidence"], 3),
            "is_mocked": False,
            "api_cost": 0.0,
            "latency_seconds": latency_seconds,
            "verification_status": v_result["status"],
            "verification_reason": v_result["reason"],
            "observed_tps": v_result["observed_tps"],
            "integrity_hash": v_result.get("integrity_hash", ""),
            "routing_mode": "eco",
            "is_local_inference": False,
            "proxy_provider": actual_provider,
            "proxy_region_pinned": actual_provider != "openrouter",
            "available_providers": provider_names,
            "what_if": {
                "baseline_model": "nemotron-3-ultra",
                "baseline_region": "ap-south-1 (Mumbai)",
                "baseline_co2_g": worst_co2["estimated_co2_g"],
                "actual_model": model_sel["model"],
                "actual_region": actual_region,
                "actual_co2_g": actual_co2["estimated_co2_g"],
                "co2_saved_g": round(worst_co2["estimated_co2_g"] - actual_co2["estimated_co2_g"], 4),
                "baseline_cost": 0.0,
                "actual_cost": 0.0,
            },
        }
    )
