from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone
import os
import time
import logging
import openai
from jose import JWTError, jwt

from schemas import ChatRequest, ChatResponse
from auth import SECRET_KEY, ALGORITHM
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
    routing = await route_query(classification["tier"], prompt_length=prompt_len)
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
        try:
            payload = jwt.decode(auth_header[7:], SECRET_KEY, algorithms=[ALGORITHM])
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
            "verification_status": v_result["status"],
            "verification_reason": v_result["reason"],
            "observed_tps": v_result["observed_tps"],
            "is_local_inference": (model_sel["provider"] == "Ollama (Local)")
        }
    )
