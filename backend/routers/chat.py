from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
import os
import time
import logging
import json
import openai
from openai import AsyncOpenAI
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

logger = logging.getLogger("EcoQuery.chat")
router = APIRouter(prefix="/api", tags=["chat"])

MODEL_COST_MAP = {
    "gpt-4o-mini": 0.00015, "gemini-2.5-flash-lite": 0.000075, "claude-3-haiku": 0.00025,
    "llama-3.1-8b": 0.00005, "gpt-4o": 0.0025, "gemini-2.5-flash": 0.0001,
    "claude-3.5-sonnet": 0.003, "llama-3.1-70b": 0.00035,
    "gpt-4.5": 0.075, "gemini-2.5-pro": 0.002, "claude-3.5-opus": 0.015, "llama-3.1-405b": 0.002,
    "ollama-llama3-8b": 0.0, "groq-llama-3.1-70b": 0.00035, "groq-mixtral-8x7b": 0.0002
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

    target_model = model_sel["model"]
    api_key = os.getenv("OPENAI_API_KEY", "")
    is_openrouter = api_key.startswith("sk-or-")
    openrouter_id = model_sel["openrouter_id"]

    client_kwargs = {"api_key": api_key}
    if is_openrouter:
        client_kwargs["base_url"] = "https://openrouter.ai/api/v1"
        target_model = openrouter_id

    routed_model_display = f"{model_sel['provider']} {model_sel['model']} via {region_info['region']} ({region_info['energy_source']})"

    api_cost = 0.0
    prompt_tokens = max(5, int(prompt_len / 4.0))
    output_tokens = 40
    is_mocked = False

    try:
        client = openai.OpenAI(**client_kwargs)
        response = client.chat.completions.create(
            model=target_model,
            messages=[{"role": "user", "content": req.message}],
            max_tokens=1024
        )
        reply_content = response.choices[0].message.content
        if response.usage:
            prompt_tokens = response.usage.prompt_tokens or prompt_tokens
            output_tokens = response.usage.completion_tokens or output_tokens
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
            "is_local_inference": (model_sel["provider"] == "Ollama (Local)")
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


def _get_client_kwargs(model_sel: dict):
    api_key = os.getenv("OPENAI_API_KEY", "")
    is_openrouter = api_key.startswith("sk-or-")
    target_model = model_sel["openrouter_id"] if is_openrouter else model_sel["model"]
    client_kwargs = {"api_key": api_key}
    if is_openrouter:
        client_kwargs["base_url"] = "https://openrouter.ai/api/v1"
    return client_kwargs, target_model, api_key, is_openrouter


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    classification, prompt_len, mode, region_info, model_sel, savings = await _build_routing(req)
    client_kwargs, target_model, api_key, is_openrouter = _get_client_kwargs(model_sel)
    api_cost = 0.0
    prompt_tokens = max(5, int(prompt_len / 4.0))
    output_tokens = 40
    is_mocked = False
    full_reply = ""
    start_time = time.time()

    async def generate():
        nonlocal api_cost, prompt_tokens, output_tokens, is_mocked, full_reply
        client = AsyncOpenAI(**client_kwargs)
        try:
            stream = await client.chat.completions.create(
                model=target_model,
                messages=[{"role": "user", "content": req.message}],
                max_tokens=1024,
                stream=True
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                token = (delta.content or "") if delta else ""
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
                f"CO₂ estimate: {savings['estimated_co2_g']}g (saved {savings['saved_vs_baseline_g']}g vs baseline)"
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
            await ws_manager.broadcast_to_user(user_email, "query.routed", {
                "query": req.message[:100], "tier": classification["tier"],
                "model": model_sel["model"], "region": region_info["region"],
                "co2_g": savings["estimated_co2_g"],
                "co2_saved_g": savings["saved_vs_baseline_g"],
                "api_cost": api_cost, "mode": mode,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

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
        }
        yield f"data: {json.dumps({'done': True, 'metadata': metadata})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
