from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
import time
import logging
import json
import re
from jose import JWTError, jwt

from schemas import ChatRequest, ChatResponse
from auth import SECRET_KEY, ALGORITHM, auth_db
from models import CARBON_MODELS, FALLBACK_MODELS
from classifier import classifier
from router import route_query, compute_savings
from ledger import ledger
from verifier import verifier
from websocket_manager import ws_manager
from providers import provider_router
from green_provider import green_router, PROVIDER_REGIONS

logger = logging.getLogger("EcoQuery.chat")
router = APIRouter(prefix="/api", tags=["chat"])

SYSTEM_PROMPT = (
    "You are an encyclopedia. For ANY question, write a single clear paragraph.\n\n"
    "FORMAT: Start with a direct definition (1-2 sentences). Then explain what it is, how it works, or why it matters (2-3 sentences).\n\n"
    "RULES:\n"
    "- MAX 60 words, MAX 4 sentences\n"
    "- ONE clean paragraph, no line breaks inside\n"
    "- NO headers, NO bullets, NO tables, NO lists, NO bold, NO markdown\n"
    "- NO intro filler (Sure, Great question, Here is)\n"
    "- NO thinking, NO reasoning, NO chain of thought\n"
    "- Start DIRECTLY with the topic name or definition\n"
    "- Example: Solar energy is the radiant light and heat from the Sun harnessed using solar panels and thermal systems to generate electricity. It is a renewable, clean source that produces no greenhouse gas emissions during operation, making it key for reducing fossil fuel reliance and combating climate change."
)

MODEL_COST_MAP = {
    "nemotron-3-ultra-550b-a55b": 0.0, "nemotron-3-super-120b-a12b": 0.0,
    "llama-4-scout": 0.0, "deepseek-chat-v3-0324": 0.0,
    "gpt-oss-120b": 0.0, "gpt-oss-20b": 0.0, "gemma-4-31b": 0.0,
}

WORST_MODEL = {"model": "ling-3.0-flash", "carbon_score": 5, "provider": "InclusionAI"}
WORST_INTENSITY = 710.0


def clean_response(text: str, max_words: int = 60) -> str:
    """Post-process LLM response to ensure short, clean output."""
    if not text:
        return text
    # Strip thinking/reasoning blocks
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Strip leaked chain-of-thought
    text = re.sub(r'^(Hmm|Let me think|Okay,?|So,?|The user wants|I need to|I should|Let me).*?(?=\n[A-Z]|\n\n)', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Strip intro filler
    text = re.sub(r'^(Sure|Great question|Here is|Certainly|Of course|Absolutely)[!.]*\s*', '', text, flags=re.IGNORECASE)
    # Strip markdown headers, tables, horizontal rules
    text = re.sub(r'^#{1,6}\s+.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\|.*\|.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    # Collapse to single paragraph
    text = re.sub(r'\n{2,}', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    # Trim to max words
    words = text.split()
    if len(words) > max_words:
        text = ' '.join(words[:max_words]) + '...'
    return text.strip()


async def _resolve_user_email(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return ""
    token = auth_header[7:]
    if token.startswith("eq_"):
        try:
            if auth_db.available and auth_db.collection is not None:
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
    routing = await route_query(classification["tier"], prompt_length=prompt_len)
    region_info = routing["region"]
    model_sel = routing["model"]
    savings = routing["savings"]

    try:
        green_route = await green_router.route_to_greenest(query=req.message)
        green_model_id = await green_router.get_green_model(req.message)
        green_provider = green_route["provider"]
        green_intensity = green_route["intensity"]
        green_score = green_route["score"]
        green_region = green_route["region"]

        model_sel = {
            "model": green_model_id.split("/")[-1],
            "provider": green_provider,
            "display_name": f"{green_provider} {green_model_id} (greenest)",
            "openrouter_id": green_model_id,
            "tier": "free",
            "carbon_score": round(green_score, 1),
            "estimated_latency_s": model_sel.get("estimated_latency_s", 2.0),
            "reason": f"Routed to greenest provider: {green_provider} ({green_route['location']}, {green_intensity} g/kWh, grid: {green_route['grid']})"
        }
        region_info = {
            "region": green_region,
            "energy_source": green_route["grid"],
            "carbon_intensity_g_kwh": green_intensity,
            "method": "green-provider-realtime",
        }
        intensity = green_intensity
        savings = compute_savings(model_sel["carbon_score"], intensity, prompt_length=prompt_len)
        logger.info(f"Green provider override: {green_provider} ({green_region}) @ {green_intensity} g/kWh")
    except Exception as e:
        logger.warning(f"Green provider routing failed, falling back: {e}")

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
                # Look up overridden model's actual provider region intensity
                provider_key = m["provider"].lower()
                provider_info = PROVIDER_REGIONS.get(provider_key)
                if provider_info:
                    greenest = provider_info["greenest_region"]
                    region_data = provider_info["regions"].get(greenest, {})
                    grid_type = region_data.get("grid", "Mixed")
                    GRID_ESTIMATES = {
                        "Hydro/Nuclear": 15, "Hydro": 30, "Nuclear": 50, "Wind": 100,
                        "Wind/Nuclear": 80, "Wind/Gas": 180, "Gas/Wind": 200, "Gas": 350,
                        "Mixed": 300, "Wind/Coal": 350, "Coal/Gas": 500, "Coal": 650,
                    }
                    intensity = GRID_ESTIMATES.get(grid_type, 350)
                    region_info = {
                        "region": greenest,
                        "energy_source": grid_type,
                        "carbon_intensity_g_kwh": intensity,
                        "method": "model-override-provider-region",
                    }
                else:
                    intensity = region_info.get("carbon_intensity_g_kwh", 200.0)
                savings = compute_savings(model_sel["carbon_score"], intensity, prompt_length=prompt_len)
                break

    return classification, prompt_len, region_info, model_sel, savings


def _build_messages(req: ChatRequest):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if req.images:
        content = [{"type": "text", "text": req.message}]
        for img in req.images:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img}"}
            })
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": req.message})
    return messages


def _build_metadata(
    classification, prompt_len, region_info, model_sel, savings,
    v_result, api_cost, latency_seconds, is_mocked, output_tokens, prompt_tokens,
):
    worst_savings = compute_savings(WORST_MODEL["carbon_score"], WORST_INTENSITY, prompt_length=prompt_len)
    routed_model_display = f"{model_sel['provider']} {model_sel['model']} via {region_info['region']} ({region_info['energy_source']})"
    return {
        "model_used": routed_model_display, "model_id": model_sel["model"],
        "model_tier": model_sel["tier"], "carbon_score": model_sel["carbon_score"],
        "region": region_info["region"], "energy_source": region_info["energy_source"],
        "co2_estimated_g": savings["estimated_co2_g"],
        "co2_saved_g": savings["saved_vs_baseline_g"],
        "tier": classification["tier"],
        "confidence": round(classification["confidence"], 3),
        "is_mocked": is_mocked, "api_cost": api_cost,
        "latency_seconds": latency_seconds,
        "estimated_latency_s": model_sel.get("estimated_latency_s", 0),
        "verification_status": v_result["status"],
        "verification_reason": v_result["reason"],
        "observed_tps": v_result["observed_tps"],
        "integrity_hash": v_result.get("integrity_hash", ""),
        "routing_mode": "eco",
        "is_local_inference": (model_sel["provider"] == "Ollama (Local)"),
        "what_if": {
            "baseline_model": WORST_MODEL["model"],
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


async def _record_and_notify(
    request: Request, req, classification, region_info, model_sel, savings,
    api_cost, latency_seconds, is_mocked, v_result,
):
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
        "routing_mode": "eco",
        "is_local_inference": (model_sel["provider"] == "Ollama (Local)")
    }, user_email=user_email)

    if user_email:
        if region_info.get("carbon_intensity_g_kwh", 0) > 400:
            await ws_manager.broadcast_to_user(user_email, "carbon.alert", {
                "region": region_info["region"],
                "carbon_intensity": region_info["carbon_intensity_g_kwh"],
                "energy_source": region_info["energy_source"],
                "message": f"⚠️ {region_info['region']} grid is running at {region_info['carbon_intensity_g_kwh']} g/kWh ({region_info['energy_source']})."
            })
        await ws_manager.broadcast_to_user(user_email, "query.routed", {
            "query": req.message[:100], "tier": classification["tier"],
            "model": model_sel["model"], "region": region_info["region"],
            "co2_g": savings["estimated_co2_g"],
            "co2_saved_g": savings["saved_vs_baseline_g"],
            "api_cost": api_cost,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        from routers.webhooks import fire_webhooks
        await fire_webhooks(user_email, "query.routed", {
            "model": model_sel["model"],
            "tier": classification["tier"],
            "region": region_info["region"],
            "co2_estimated_g": savings["estimated_co2_g"],
        })


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, request: Request):
    start_time = time.time()
    classification, prompt_len, region_info, model_sel, savings = await _build_routing(req)
    target_model = model_sel["openrouter_id"] or model_sel["model"]

    api_cost = 0.0
    prompt_tokens = max(5, int(prompt_len / 4.0))
    output_tokens = 40
    is_mocked = False

    try:
        result = await provider_router.chat_completion(
            model_id=target_model,
            messages=_build_messages(req),
            max_tokens=150,
        )
        reply_content = clean_response(result.get("content") or "") or ""

        # Fallback chain: if primary returns empty, try next models
        if not reply_content:
            for fallback_id in FALLBACK_MODELS:
                if fallback_id == target_model:
                    continue
                try:
                    logger.info(f"Primary empty, trying fallback: {fallback_id}")
                    result = await provider_router.chat_completion(
                        model_id=fallback_id,
                        messages=_build_messages(req),
                        max_tokens=150,
                    )
                    reply_content = clean_response(result.get("content") or "") or ""
                    if reply_content:
                        target_model = fallback_id
                        break
                except Exception:
                    continue

        if not reply_content:
            reply_content = "No response generated."

        usage = result.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
        output_tokens = usage.get("completion_tokens", output_tokens)
        if prompt_tokens and output_tokens:
            rate = MODEL_COST_MAP.get(model_sel["model"], 0.001)
            api_cost = round((prompt_tokens * rate / 1000) + (output_tokens * rate / 1000), 6)
    except Exception as e:
        logger.warning(f"LLM API call failed: {e}")
        reply_content = (
            "I'm sorry, I encountered an error processing your request. "
            "Please try again or contact support if the issue persists."
        )
        is_mocked = True

    latency_seconds = round(time.time() - start_time, 3)
    v_result = verifier.verify_completion(
        model_id=model_sel["model"], prompt_tokens=prompt_tokens,
        completion_tokens=output_tokens, latency_seconds=latency_seconds,
        reported_co2_g=savings["estimated_co2_g"]
    )

    await _record_and_notify(
        request, req, classification, region_info, model_sel, savings,
        api_cost, latency_seconds, is_mocked, v_result,
    )

    return ChatResponse(
        reply=reply_content,
        metadata=_build_metadata(
            classification, prompt_len, region_info, model_sel, savings,
            v_result, api_cost, latency_seconds, is_mocked, output_tokens, prompt_tokens,
        )
    )


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    classification, prompt_len, region_info, model_sel, savings = await _build_routing(req)
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
                messages=_build_messages(req),
                max_tokens=150,
            ):
                if token:
                    full_reply += token
                    yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            logger.warning(f"LLM streaming failed: {e}")
            is_mocked = True
            full_reply = "I'm sorry, I encountered an error processing your request. Please try again or contact support if the issue persists."
            yield f"data: {json.dumps({'token': full_reply})}\n\n"

        latency_seconds = round(time.time() - start_time, 3)
        v_result = verifier.verify_completion(
            model_id=model_sel["model"], prompt_tokens=prompt_tokens,
            completion_tokens=output_tokens, latency_seconds=latency_seconds,
            reported_co2_g=savings["estimated_co2_g"]
        )

        await _record_and_notify(
            request, req, classification, region_info, model_sel, savings,
            api_cost, latency_seconds, is_mocked, v_result,
        )

        yield f"data: {json.dumps({'done': True, 'metadata': _build_metadata(
            classification, prompt_len, region_info, model_sel, savings,
            v_result, api_cost, latency_seconds, is_mocked, output_tokens, prompt_tokens,
        )})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
