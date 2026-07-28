from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
import os
import time
import logging
import json
from jose import JWTError, jwt

from schemas import ChatRequest, ChatResponse
from auth import SECRET_KEY, ALGORITHM, auth_db
from models import CARBON_MODELS
from classifier import classifier
from carbon import get_carbon_optimal_region
from router import route_query, compute_savings
from ledger import ledger
from verifier import verifier
from websocket_manager import ws_manager
from providers import provider_router

logger = logging.getLogger("EcoQuery.chat")
router = APIRouter(prefix="/api", tags=["chat"])

MODEL_COST_MAP = {
    "deepseek-v4-flash": 0.0, "ling-3.0-flash": 0.0,
    "laguna-s-2.1": 0.0, "mimo-v2.5": 0.0,
    "north-mini-code": 0.0, "nemotron-3-ultra": 0.0,
}


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, request: Request):
    start_time = time.time()
    classification = await classifier.classify(req.message)
    prompt_len = len(req.message)
    mode = req.mode or "eco"
    routing = await route_query(classification["tier"], prompt_length=prompt_len, mode=mode)
    region_info = routing["region"]
    model_sel = routing["model"]
    savings = routing["savings"]

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

    target_model = model_sel["openrouter_id"] or model_sel["model"]

    routed_model_display = f"{model_sel['provider']} {model_sel['model']} via {region_info['region']} ({region_info['energy_source']})"

    api_cost = 0.0
    prompt_tokens = max(5, int(prompt_len / 4.0))
    output_tokens = 40
    is_mocked = False

    try:
        result = await provider_router.chat_completion(
            model_id=target_model,
            messages=[{"role": "user", "content": req.message}],
            max_tokens=1024,
        )
        reply_content = result["content"]
        usage = result.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
        output_tokens = usage.get("completion_tokens", output_tokens)
        if prompt_tokens and output_tokens:
            rate = MODEL_COST_MAP.get(model_sel["model"], 0.001)
            api_cost = round((prompt_tokens * rate / 1000) + (output_tokens * rate / 1000), 6)
    except Exception as e:
        err_msg = str(e)
        logger.warning(f"LLM API call failed: {err_msg}")
        reply_content = (
            f"Error: {err_msg}\n\n"
            f"Routing info:\n"
            f"Classification: {classification['tier']} "
            f"(confidence: {classification['confidence']:.1%}, method: {classification['method']})\n"
            f"Routed to: {routed_model_display}\n"
            f"Model tier: {model_sel['tier']} (carbon score: {model_sel['carbon_score']}/10)\n"
            f"Region carbon intensity: {region_info.get('carbon_intensity_g_kwh', 'N/A')} g/kWh\n"
            f"CO\u2082 estimate: {savings['estimated_co2_g']}g (saved {savings['saved_vs_baseline_g']}g vs baseline)"
        )
        is_mocked = True

    latency_seconds = round(time.time() - start_time, 3)

    v_result = verifier.verify_completion(
        model_id=model_sel["model"],
        prompt_tokens=prompt_tokens,
        completion_tokens=output_tokens,
        latency_seconds=latency_seconds,
        reported_co2_g=savings["estimated_co2_g"]
    )

    user_email = ""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if token.startswith("eq_"):
            try:
                user = await auth_db.collection.find_one({"api_key": token})
                if user:
                    user_email = user.get("email", "")
            except Exception:
                pass
        else:
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                user_email = payload.get("sub", "")
            except JWTError:
                pass

    await ledger.record_query({
        "query": req.message,
        "tier": classification["tier"],
        "model_used": model_sel["model"],
        "model_provider": model_sel["provider"],
        "model_tier": model_sel["tier"],
        "carbon_score": model_sel["carbon_score"],
        "region": region_info["region"],
        "energy_source": region_info["energy_source"],
        "co2_estimated": savings["estimated_co2_g"],
        "co2_saved_vs_baseline": savings["saved_vs_baseline_g"],
        "is_mocked": is_mocked,
        "classifier_method": classification["method"],
        "classifier_confidence": classification["confidence"],
        "carbon_method": region_info.get("method", "mock-fallback"),
        "api_cost": api_cost,
        "latency_seconds": latency_seconds,
        "verification_status": v_result["status"],
        "verification_confidence": v_result["confidence"],
        "observed_tps": v_result["observed_tps"],
        "integrity_hash": v_result.get("integrity_hash", ""),
        "routing_mode": mode,
        "is_local_inference": (model_sel["provider"] == "Ollama (Local)")
    }, user_email=user_email)

    if user_email:
        if region_info.get("carbon_intensity_g_kwh", 0) > 400:
            await ws_manager.broadcast_to_user(user_email, "carbon.alert", {
                "region": region_info["region"],
                "carbon_intensity": region_info["carbon_intensity_g_kwh"],
                "energy_source": region_info["energy_source"],
                "message": f"⚠️ {region_info['region']} grid is running at {region_info['carbon_intensity_g_kwh']} g/kWh ({region_info['energy_source']}). Switch to eco mode!"
            })
        event_data = {
            "query": req.message[:100],
            "tier": classification["tier"],
            "model": model_sel["model"],
            "region": region_info["region"],
            "co2_g": savings["estimated_co2_g"],
            "co2_saved_g": savings["saved_vs_baseline_g"],
            "api_cost": api_cost,
            "mode": mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await ws_manager.broadcast_to_user(user_email, "query.routed", event_data)
        from routers.webhooks import fire_webhooks
        await fire_webhooks(user_email, "query.routed", {
            "model": model_sel["model"],
            "tier": classification["tier"],
            "region": region_info["region"],
            "co2_estimated_g": savings["estimated_co2_g"],
        })

        worst_model = {"model": "nemotron-3-ultra", "carbon_score": 6, "provider": "NVIDIA"}
    worst_region_intensity = 710.0
    worst_savings = compute_savings(worst_model["carbon_score"], worst_region_intensity, prompt_length=prompt_len)

    return ChatResponse(
        reply=reply_content,
        metadata={
            "model_used": routed_model_display,
            "model_id": model_sel["model"],
            "model_tier": model_sel["tier"],
            "carbon_score": model_sel["carbon_score"],
            "region": region_info["region"],
            "energy_source": region_info["energy_source"],
            "co2_estimated_g": savings["estimated_co2_g"],
            "co2_saved_g": savings["saved_vs_baseline_g"],
            "tier": classification["tier"],
            "confidence": round(classification["confidence"], 3),
            "is_mocked": is_mocked,
            "api_cost": api_cost,
            "latency_seconds": latency_seconds,
            "estimated_latency_s": model_sel.get("estimated_latency_s", 0),
            "verification_status": v_result["status"],
            "verification_reason": v_result["reason"],
            "observed_tps": v_result["observed_tps"],
            "integrity_hash": v_result.get("integrity_hash", ""),
            "routing_mode": mode,
            "is_local_inference": (model_sel["provider"] == "Ollama (Local)"),
            "what_if": {
                "baseline_model": worst_model["model"],
                "baseline_region": "ap-south-1 (Mumbai)",
                "baseline_co2_g": worst_savings["estimated_co2_g"],
                "actual_model": model_sel["model"],
                "actual_region": region_info["region"],
                "actual_co2_g": savings["estimated_co2_g"],
                "co2_saved_g": round(worst_savings["estimated_co2_g"] - savings["estimated_co2_g"], 4),
                "baseline_cost": 0.0,
                "actual_cost": api_cost,
            },
        }
    )


async def _resolve_user_email(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return ""
    token = auth_header[7:]
    if token.startswith("eq_"):
        try:
            user = await auth_db.collection.find_one({"api_key": token})
            if user:
                return user.get("email", "")
        except Exception:
            pass
    else:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload.get("sub", "")
        except JWTError:
            pass
    return ""


async def _build_routing(req: ChatRequest):
    classification = await classifier.classify(req.message)
    prompt_len = len(req.message)
    mode = req.mode or "eco"
    routing = await route_query(classification["tier"], prompt_length=prompt_len, mode=mode)
    region_info = routing["region"]
    model_sel = routing["model"]
    savings = routing["savings"]

    if req.model_id:
        for m in CARBON_MODELS:
            if m["id"] == req.model_id:
                model_sel = {
                    "model": m["id"], "provider": m["provider"],
                    "display_name": f"{m['provider']} {m['id']}",
                    "openrouter_id": m["openrouter_id"], "tier": m["tier"],
                    "carbon_score": m["carbon_score"],
                    "estimated_latency_s": model_sel.get("estimated_latency_s", 2.0),
                    "reason": m["description"]
                }
                intensity = region_info.get("carbon_intensity_g_kwh", 200.0)
                savings = compute_savings(model_sel["carbon_score"], intensity, prompt_length=prompt_len)
                break

    return classification, prompt_len, mode, region_info, model_sel, savings


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    classification, prompt_len, mode, region_info, model_sel, savings = await _build_routing(req)
    target_model = model_sel["openrouter_id"] or model_sel["model"]
    api_cost = 0.0
    prompt_tokens = max(5, int(prompt_len / 4.0))
    output_tokens = 40
    is_mocked = False
    full_reply = ""
    start_time = time.time()

    async def generate():
        nonlocal api_cost, prompt_tokens, output_tokens, is_mocked, full_reply
        try:
            async for token in provider_router.stream_completion(
                model_id=target_model,
                messages=[{"role": "user", "content": req.message}],
                max_tokens=1024,
            ):
                if token:
                    full_reply += token
                    yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            err_msg = str(e)
            logger.warning(f"LLM streaming failed: {err_msg}")
            is_mocked = True
            full_reply = (
                f"Error: {err_msg}\n\nRouting info:\n"
                f"Classification: {classification['tier']} (confidence: {classification['confidence']:.1%}, method: {classification['method']})\n"
                f"Routed to: {model_sel['provider']} {model_sel['model']} via {region_info['region']} ({region_info['energy_source']})\n"
                f"Model tier: {model_sel['tier']} (carbon score: {model_sel['carbon_score']}/10)\n"
                f"Region carbon intensity: {region_info.get('carbon_intensity_g_kwh', 'N/A')} g/kWh\n"
                f"CO\u2082 estimate: {savings['estimated_co2_g']}g (saved {savings['saved_vs_baseline_g']}g vs baseline)"
            )
            yield f"data: {json.dumps({'token': full_reply})}\n\n"

        latency_seconds = round(time.time() - start_time, 3)
        v_result = verifier.verify_completion(
            model_id=model_sel["model"], prompt_tokens=prompt_tokens,
            completion_tokens=output_tokens, latency_seconds=latency_seconds,
            reported_co2_g=savings["estimated_co2_g"]
        )

        user_email = await _resolve_user_email(request)
        await ledger.record_query({
            "query": req.message, "tier": classification["tier"],
            "model_used": model_sel["model"], "model_provider": model_sel["provider"],
            "model_tier": model_sel["tier"], "carbon_score": model_sel["carbon_score"],
            "region": region_info["region"], "energy_source": region_info["energy_source"],
            "co2_estimated": savings["estimated_co2_g"],
            "co2_saved_vs_baseline": savings["saved_vs_baseline_g"],
            "is_mocked": is_mocked, "classifier_method": classification["method"],
            "classifier_confidence": classification["confidence"],
            "carbon_method": region_info.get("method", "mock-fallback"),
            "api_cost": api_cost, "latency_seconds": latency_seconds,
            "verification_status": v_result["status"],
            "verification_confidence": v_result["confidence"],
            "observed_tps": v_result["observed_tps"],
            "integrity_hash": v_result.get("integrity_hash", ""),
            "routing_mode": mode,
            "is_local_inference": (model_sel["provider"] == "Ollama (Local)")
        }, user_email=user_email)

        if user_email:
            if region_info.get("carbon_intensity_g_kwh", 0) > 400:
                await ws_manager.broadcast_to_user(user_email, "carbon.alert", {
                    "region": region_info["region"],
                    "carbon_intensity": region_info["carbon_intensity_g_kwh"],
                    "energy_source": region_info["energy_source"],
                    "message": f"\u26a0\ufe0f {region_info['region']} grid is running at {region_info['carbon_intensity_g_kwh']} g/kWh ({region_info['energy_source']}). Switch to eco mode!"
                })
            await ws_manager.broadcast_to_user(user_email, "query.routed", {
                "query": req.message[:100], "tier": classification["tier"],
                "model": model_sel["model"], "region": region_info["region"],
                "co2_g": savings["estimated_co2_g"],
                "co2_saved_g": savings["saved_vs_baseline_g"],
                "api_cost": api_cost, "mode": mode,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        worst_model = {"model": "nemotron-3-ultra", "carbon_score": 6, "provider": "NVIDIA"}
        worst_region_intensity = 710.0
        worst_savings = compute_savings(worst_model["carbon_score"], worst_region_intensity, prompt_length=prompt_len)

        metadata = {
            "model_used": model_sel["model"], "model_id": model_sel["model"],
            "model_tier": model_sel["tier"], "carbon_score": model_sel["carbon_score"],
            "region": region_info["region"], "energy_source": region_info["energy_source"],
            "co2_estimated_g": savings["estimated_co2_g"],
            "co2_saved_g": savings["saved_vs_baseline_g"],
            "tier": classification["tier"],
            "confidence": round(classification["confidence"], 3),
            "is_mocked": is_mocked, "api_cost": api_cost,
            "latency_seconds": latency_seconds,
            "verification_status": v_result["status"],
            "verification_reason": v_result["reason"],
            "observed_tps": v_result["observed_tps"],
            "integrity_hash": v_result.get("integrity_hash", ""),
            "routing_mode": mode,
            "is_local_inference": (model_sel["provider"] == "Ollama (Local)"),
            "what_if": {
                "baseline_model": worst_model["model"],
                "baseline_region": "ap-south-1 (Mumbai)",
                "baseline_co2_g": worst_savings["estimated_co2_g"],
                "actual_model": model_sel["model"],
                "actual_region": region_info["region"],
                "actual_co2_g": savings["estimated_co2_g"],
                "co2_saved_g": round(worst_savings["estimated_co2_g"] - savings["estimated_co2_g"], 4),
                "baseline_cost": 0.0,
                "actual_cost": api_cost,
            },
        }
        yield f"data: {json.dumps({'done': True, 'metadata': metadata})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
