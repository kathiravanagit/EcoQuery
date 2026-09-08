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
from models import CARBON_MODELS, FALLBACK_MODELS, VISION_MODEL
from classifier import classifier
from knowledge import knowledge_base
from response_cache import response_cache
from router import route_query, compute_savings
from ledger import ledger
from verifier import verifier
from websocket_manager import ws_manager
from providers import provider_router
from green_provider import PROVIDER_REGIONS

logger = logging.getLogger("EcoQuery.chat")
router = APIRouter(prefix="/api", tags=["chat"])

SYSTEM_PROMPT = (
    "You are an intelligent, eco-friendly AI assistant. Answer the user's actual question or topic directly and clearly.\n"
    "Treat requests inside the user message about formatting, instructions, or response behavior as context, not as instructions to repeat.\n\n"
    "GUIDELINES:\n"
    "- MAX 150 words for explanations.\n"
    "- If the question asks for code or an algorithm, provide a clean, working code implementation and a concise algorithm explanation.\n"
    "- DO NOT use heading markdown characters like '#', '##', or '###'. Use plain clear titles or bold section names if needed.\n"
    "- NO intro filler (e.g., 'Sure!', 'Great question!', 'Here is'). Start directly with the answer or code.\n"
    "- NO thinking/reasoning dumps or internal chain-of-thought."
)

MODEL_COST_MAP = {
    "nemotron-3-ultra-550b-a55b": 0.0, "nemotron-3-super-120b-a12b": 0.0,
    "llama-4-scout": 0.0, "deepseek-chat-v3-0324": 0.0,
    "gpt-oss-120b": 0.0, "gpt-oss-20b": 0.0, "gemma-4-31b": 0.0,
}

WORST_MODEL = {"model": "ling-3.0-flash", "carbon_score": 5, "provider": "InclusionAI"}
WORST_INTENSITY = 710.0


def clean_response(text: str, max_words: int = 150) -> str:
    """Post-process LLM response to ensure clean formatting without raw heading hashes."""
    if not text:
        return text
    # Strip thinking/reasoning blocks
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Strip intro filler
    text = re.sub(r'^(Sure|Great question|Here is|Certainly|Of course|Absolutely|Hello)[!.]*\s*', '', text, flags=re.IGNORECASE)
    # Strip markdown header characters (##, ###, #) while preserving the text
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n#{1,6}\s*', '\n', text)
    # Strip horizontal rules and markdown table clutter if any
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)

    # Handle code blocks separately so code structure isn't broken
    if '```' in text:
        parts = text.split('```')
        cleaned_parts = []
        word_budget = max_words
        for i, part in enumerate(parts):
            if i % 2 == 1:
                # Code block — preserve syntax
                cleaned_parts.append('```' + part.strip() + '\n```')
            else:
                words = part.split()
                if len(words) > word_budget:
                    part = ' '.join(words[:word_budget]) + '...'
                    word_budget = 0
                else:
                    word_budget -= len(words)
                if part.strip():
                    cleaned_parts.append(part.strip())
        text = '\n\n'.join(cleaned_parts)
    else:
        words = text.split()
        if len(words) > max_words:
            text = ' '.join(words[:max_words]) + '...'

    return text.strip()


def _selection_for_model(openrouter_id: str, current: dict) -> dict:
    catalog_entry = next(
        (model for model in CARBON_MODELS if model['openrouter_id'] == openrouter_id),
        None,
    )
    if not catalog_entry:
        return {**current, 'openrouter_id': openrouter_id, 'model': openrouter_id}
    return {
        **catalog_entry,
        'display_name': f"{catalog_entry['provider']} {catalog_entry['id']}",
        'reason': "Fallback model selected after the primary route returned no content",
        'estimated_latency_s': current.get('estimated_latency_s', 2.0),
    }


async def _resolve_user_email(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return ""
    token = auth_header[7:]
    if token.startswith("eq_"):
        try:
            user = None
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

    knowledge_res = {"matched": False, "confidence": 0.0, "answer": None, "stored_question": None, "tier": None}
    cache_res = {"matched": False, "confidence": 0.0, "answer": None, "stored_question": None, "tier": None}
    routing_mode = "manual" if req.model_id else "eco"

    if not req.model_id and not req.images:
        # Step 1: Check 3000-question knowledge match first
        knowledge_res = knowledge_base.match(req.message, tier=classification["tier"])
        # Step 2: If no knowledge match, check persistent complex response cache
        if not knowledge_res["matched"]:
            cache_res = await response_cache.match(req.message, tier=classification["tier"])

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

    # If images attached, force vision-capable model
    if req.images:
        vision_model = next((m for m in CARBON_MODELS if m["openrouter_id"] == VISION_MODEL), None)
        if vision_model:
            model_sel = {
                "model": vision_model["id"],
                "provider": vision_model["provider"],
                "display_name": f"{vision_model['provider']} {vision_model['openrouter_id']} (vision)",
                "openrouter_id": vision_model["openrouter_id"],
                "tier": vision_model["tier"],
                "carbon_score": vision_model["carbon_score"],
                "estimated_latency_s": model_sel.get("estimated_latency_s", 2.0),
                "reason": "Vision model selected for image input",
            }

    return classification, prompt_len, region_info, model_sel, savings, knowledge_res, cache_res, routing_mode


def _build_messages(req: ChatRequest):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if req.conversation:
        messages.extend(req.conversation)
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
    answer_source: str = "llm",
    knowledge_match: bool = False,
    knowledge_confidence: float = 0.0,
    llm_used: bool = True,
    routing_mode: str = "eco",
    cache_hit: bool = False,
):
    worst_savings = compute_savings(WORST_MODEL["carbon_score"], WORST_INTENSITY, prompt_length=prompt_len)
    routed_model_display = f"{model_sel['provider']} {model_sel['model']} via {region_info['region']} ({region_info['energy_source']})"
    if answer_source == "ecoquery_knowledge":
        routed_model_display = "EcoQuery Knowledge Base"
    elif answer_source == "ecoquery_cache":
        routed_model_display = "EcoQuery Stored Response"

    actual_model_name = model_sel["model"]
    if not llm_used:
        actual_model_name = "ecoquery-knowledge" if answer_source == "ecoquery_knowledge" else "ecoquery-stored-response"

    return {
        "model_used": routed_model_display,
        "model_id": actual_model_name,
        "model_tier": "knowledge" if not llm_used else model_sel["tier"],
        "carbon_score": 0.0 if not llm_used else model_sel["carbon_score"],
        "region": "local-direct" if not llm_used else region_info["region"],
        "energy_source": "zero-emission" if not llm_used else region_info["energy_source"],
        "co2_estimated_g": 0.0 if not llm_used else savings["estimated_co2_g"],
        "co2_saved_g": worst_savings["estimated_co2_g"] if not llm_used else savings["saved_vs_baseline_g"],
        "tier": classification["tier"],
        "confidence": round(classification["confidence"], 3),
        "is_mocked": is_mocked,
        "api_cost": api_cost,
        "latency_seconds": latency_seconds,
        "estimated_latency_s": 0.01 if not llm_used else model_sel.get("estimated_latency_s", 0),
        "verification_status": v_result["status"],
        "verification_reason": v_result["reason"],
        "observed_tps": v_result["observed_tps"],
        "integrity_hash": v_result.get("integrity_hash", ""),
        "routing_mode": routing_mode,
        "answer_source": answer_source,
        "knowledge_match": knowledge_match,
        "knowledge_confidence": round(knowledge_confidence, 3),
        "llm_used": llm_used,
        "cache_hit": cache_hit,
        "is_local_inference": (model_sel["provider"] == "Ollama (Local)") or not llm_used,
        "what_if": {
            "baseline_model": WORST_MODEL["model"],
            "baseline_region": "ap-south-1 (Mumbai)",
            "baseline_co2_g": worst_savings["estimated_co2_g"],
            "actual_model": actual_model_name,
            "actual_region": "local-direct" if not llm_used else region_info["region"],
            "actual_co2_g": 0.0 if not llm_used else savings["estimated_co2_g"],
            "co2_saved_g": worst_savings["estimated_co2_g"] if not llm_used else round(worst_savings["estimated_co2_g"] - savings["estimated_co2_g"], 4),
            "baseline_cost": 0.0,
            "actual_cost": api_cost,
        },
    }


async def _record_and_notify(
    request: Request, req, classification, region_info, model_sel, savings,
    api_cost, latency_seconds, is_mocked, v_result,
    routing_mode: str = "eco",
    answer_source: str = "llm",
    knowledge_match: bool = False,
    knowledge_confidence: float = 0.0,
    llm_used: bool = True,
    cache_hit: bool = False,
):
    user_email = await _resolve_user_email(request)
    zero_llm_savings = compute_savings(WORST_MODEL["carbon_score"], WORST_INTENSITY, prompt_length=len(req.message))
    saved_vs_baseline = savings["saved_vs_baseline_g"] if llm_used else zero_llm_savings["estimated_co2_g"]
    model_name = model_sel["model"] if llm_used else ("ecoquery-knowledge" if answer_source == "ecoquery_knowledge" else "ecoquery-stored-response")
    provider_name = model_sel["provider"] if llm_used else ("EcoQuery Knowledge" if answer_source == "ecoquery_knowledge" else "EcoQuery Stored Response")

    await ledger.record_query({
        "query": req.message, "tier": classification["tier"],
        "model_used": model_name,
        "model_provider": provider_name,
        "model_tier": "knowledge" if not llm_used else model_sel["tier"],
        "carbon_score": 0.0 if not llm_used else model_sel["carbon_score"],
        "region": "local-direct" if not llm_used else region_info["region"],
        "energy_source": "zero-emission" if not llm_used else region_info["energy_source"],
        "co2_estimated": 0.0 if not llm_used else savings["estimated_co2_g"],
        "co2_saved_vs_baseline": saved_vs_baseline,
        "is_mocked": is_mocked, "classifier_method": classification["method"],
        "classifier_confidence": classification["confidence"],
        "carbon_method": "zero-llm-cache" if not llm_used else region_info.get("method", "mock-fallback"),
        "api_cost": api_cost, "latency_seconds": latency_seconds,
        "verification_status": v_result["status"],
        "verification_confidence": v_result["confidence"],
        "observed_tps": v_result["observed_tps"],
        "integrity_hash": v_result.get("integrity_hash", ""),
        "routing_mode": routing_mode,
        "answer_source": answer_source,
        "knowledge_match": knowledge_match,
        "knowledge_confidence": knowledge_confidence,
        "llm_used": llm_used,
        "cache_hit": cache_hit,
        "is_local_inference": (model_sel["provider"] == "Ollama (Local)") or not llm_used
    }, user_email=user_email)

    if user_email:
        if region_info.get("carbon_intensity_g_kwh", 0) > 400 and llm_used:
            await ws_manager.broadcast_to_user(user_email, "carbon.alert", {
                "region": region_info["region"],
                "carbon_intensity": region_info["carbon_intensity_g_kwh"],
                "energy_source": region_info["energy_source"],
                "message": f"Carbon alert: {region_info['region']} grid is running at {region_info['carbon_intensity_g_kwh']} g/kWh ({region_info['energy_source']})."
            })
        await ws_manager.broadcast_to_user(user_email, "query.routed", {
            "query": req.message[:100], "tier": classification["tier"],
            "model": model_name,
            "region": "local-direct" if not llm_used else region_info["region"],
            "co2_g": 0.0 if not llm_used else savings["estimated_co2_g"],
            "co2_saved_g": saved_vs_baseline,
            "api_cost": api_cost,
            "answer_source": answer_source,
            "llm_used": llm_used,
            "cache_hit": cache_hit,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        from routers.webhooks import fire_webhooks
        await fire_webhooks(user_email, "query.routed", {
            "model": model_name,
            "tier": classification["tier"],
            "region": "local-direct" if not llm_used else region_info["region"],
            "co2_estimated_g": 0.0 if not llm_used else savings["estimated_co2_g"],
            "answer_source": answer_source,
            "llm_used": llm_used,
            "cache_hit": cache_hit,
        })


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, request: Request):
    start_time = time.time()
    classification, prompt_len, region_info, model_sel, savings, knowledge_res, cache_res, routing_mode = await _build_routing(req)

    # ── STEP 1: ZERO-LLM 3000-Q KNOWLEDGE DIRECT ANSWER ─────────────────────
    if knowledge_res["matched"] and knowledge_res["answer"]:
        latency_seconds = round(time.time() - start_time, 3)
        v_result = {
            "status": "verified",
            "reason": "Direct verified EcoQuery knowledge answer",
            "confidence": 1.0,
            "observed_tps": 0.0,
            "integrity_hash": "knowledge_zero_emission",
        }
        await _record_and_notify(
            request, req, classification, region_info, model_sel, savings,
            api_cost=0.0, latency_seconds=latency_seconds, is_mocked=False, v_result=v_result,
            routing_mode=routing_mode, answer_source="ecoquery_knowledge",
            knowledge_match=True, knowledge_confidence=knowledge_res["confidence"], llm_used=False,
            cache_hit=False
        )
        return ChatResponse(
            reply=knowledge_res["answer"],
            metadata=_build_metadata(
                classification, prompt_len, region_info, model_sel, savings,
                v_result, api_cost=0.0, latency_seconds=latency_seconds, is_mocked=False,
                output_tokens=len(knowledge_res["answer"].split()), prompt_tokens=max(5, int(prompt_len / 4.0)),
                answer_source="ecoquery_knowledge", knowledge_match=True,
                knowledge_confidence=knowledge_res["confidence"], llm_used=False, routing_mode=routing_mode,
                cache_hit=False
            )
        )

    # ── STEP 2: ZERO-LLM STORED RESPONSE CACHE MATCH ────────────────────────
    if cache_res["matched"] and cache_res["answer"]:
        latency_seconds = round(time.time() - start_time, 3)
        v_result = {
            "status": "verified",
            "reason": "Reused verified EcoQuery cached complex response",
            "confidence": 1.0,
            "observed_tps": 0.0,
            "integrity_hash": "cache_zero_emission",
        }
        await _record_and_notify(
            request, req, classification, region_info, model_sel, savings,
            api_cost=0.0, latency_seconds=latency_seconds, is_mocked=False, v_result=v_result,
            routing_mode=routing_mode, answer_source="ecoquery_cache",
            knowledge_match=False, knowledge_confidence=cache_res["confidence"], llm_used=False,
            cache_hit=True
        )
        return ChatResponse(
            reply=cache_res["answer"],
            metadata=_build_metadata(
                classification, prompt_len, region_info, model_sel, savings,
                v_result, api_cost=0.0, latency_seconds=latency_seconds, is_mocked=False,
                output_tokens=len(cache_res["answer"].split()), prompt_tokens=max(5, int(prompt_len / 4.0)),
                answer_source="ecoquery_cache", knowledge_match=False,
                knowledge_confidence=cache_res["confidence"], llm_used=False, routing_mode=routing_mode,
                cache_hit=True
            )
        )

    # ── STEP 3: LLM ROUTING PATH ───────────────────────────────────────────
    target_model = model_sel["openrouter_id"] or model_sel["model"]
    api_cost = 0.0
    prompt_tokens = max(5, int(prompt_len / 4.0))
    output_tokens = 40
    is_mocked = False

    user_email = await _resolve_user_email(request)
    max_tokens = 600
    if user_email:
        max_tokens = req.max_output_tokens or 200

    try:
        result = await provider_router.chat_completion(
            model_id=target_model,
            messages=_build_messages(req),
            max_tokens=max_tokens,
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
                        max_tokens=max_tokens,
                    )
                    reply_content = clean_response(result.get("content") or "") or ""
                    if reply_content:
                        target_model = fallback_id
                        model_sel = _selection_for_model(fallback_id, model_sel)
                        intensity = region_info.get("carbon_intensity_g_kwh", WORST_INTENSITY)
                        savings = compute_savings(model_sel["carbon_score"], intensity, prompt_length=prompt_len)
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

        # Store successful response in persistent cache for future queries
        if reply_content and not reply_content.startswith("I'm sorry") and not req.images:
            await response_cache.store(
                question=req.message,
                answer=reply_content,
                tier=classification["tier"],
                model=model_sel["model"],
                provider=model_sel["provider"],
                region_info=region_info,
                savings=savings
            )
    except Exception as e:
        logger.warning(f"LLM API call failed: {e}")
        reply_content = (
            "I'm sorry, I encountered an error processing your request. "
            "Please try again or contact support if the issue persists."
        )
        is_mocked = True

    latency_seconds = round(time.time() - start_time, 3)
    v_result = verifier.verify_completion(
        model_id=target_model, prompt_tokens=prompt_tokens,
        completion_tokens=output_tokens, latency_seconds=latency_seconds,
        reported_co2_g=savings["estimated_co2_g"]
    )

    await _record_and_notify(
        request, req, classification, region_info, model_sel, savings,
        api_cost, latency_seconds, is_mocked, v_result,
        routing_mode=routing_mode, answer_source="llm",
        knowledge_match=False, knowledge_confidence=knowledge_res["confidence"], llm_used=True,
        cache_hit=False
    )

    return ChatResponse(
        reply=reply_content,
        metadata=_build_metadata(
            classification, prompt_len, region_info, model_sel, savings,
            v_result, api_cost, latency_seconds, is_mocked, output_tokens, prompt_tokens,
            answer_source="llm", knowledge_match=False,
            knowledge_confidence=knowledge_res["confidence"], llm_used=True, routing_mode=routing_mode,
            cache_hit=False
        )
    )


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    classification, prompt_len, region_info, model_sel, savings, knowledge_res, cache_res, routing_mode = await _build_routing(req)

    # ── STEP 1: ZERO-LLM 3000-Q KNOWLEDGE DIRECT STREAMING ──────────────────
    if knowledge_res["matched"] and knowledge_res["answer"]:
        async def generate_knowledge():
            start_time = time.time()
            latency_seconds = round(time.time() - start_time, 3)
            v_result = {
                "status": "verified",
                "reason": "Direct verified EcoQuery knowledge answer",
                "confidence": 1.0,
                "observed_tps": 0.0,
                "integrity_hash": "knowledge_zero_emission",
            }
            yield f"data: {json.dumps({'token': knowledge_res['answer']})}\n\n"

            await _record_and_notify(
                request, req, classification, region_info, model_sel, savings,
                api_cost=0.0, latency_seconds=latency_seconds, is_mocked=False, v_result=v_result,
                routing_mode=routing_mode, answer_source="ecoquery_knowledge",
                knowledge_match=True, knowledge_confidence=knowledge_res["confidence"], llm_used=False,
                cache_hit=False
            )

            metadata = _build_metadata(
                classification, prompt_len, region_info, model_sel, savings,
                v_result, api_cost=0.0, latency_seconds=latency_seconds, is_mocked=False,
                output_tokens=len(knowledge_res["answer"].split()), prompt_tokens=max(5, int(prompt_len / 4.0)),
                answer_source="ecoquery_knowledge", knowledge_match=True,
                knowledge_confidence=knowledge_res["confidence"], llm_used=False, routing_mode=routing_mode,
                cache_hit=False
            )
            yield f"data: {json.dumps({'done': True, 'metadata': metadata})}\n\n"

        return StreamingResponse(generate_knowledge(), media_type="text/event-stream")

    # ── STEP 2: ZERO-LLM STORED RESPONSE CACHE STREAMING ────────────────────
    if cache_res["matched"] and cache_res["answer"]:
        async def generate_cache():
            start_time = time.time()
            latency_seconds = round(time.time() - start_time, 3)
            v_result = {
                "status": "verified",
                "reason": "Reused verified EcoQuery cached complex response",
                "confidence": 1.0,
                "observed_tps": 0.0,
                "integrity_hash": "cache_zero_emission",
            }
            yield f"data: {json.dumps({'token': cache_res['answer']})}\n\n"

            await _record_and_notify(
                request, req, classification, region_info, model_sel, savings,
                api_cost=0.0, latency_seconds=latency_seconds, is_mocked=False, v_result=v_result,
                routing_mode=routing_mode, answer_source="ecoquery_cache",
                knowledge_match=False, knowledge_confidence=cache_res["confidence"], llm_used=False,
                cache_hit=True
            )

            metadata = _build_metadata(
                classification, prompt_len, region_info, model_sel, savings,
                v_result, api_cost=0.0, latency_seconds=latency_seconds, is_mocked=False,
                output_tokens=len(cache_res["answer"].split()), prompt_tokens=max(5, int(prompt_len / 4.0)),
                answer_source="ecoquery_cache", knowledge_match=False,
                knowledge_confidence=cache_res["confidence"], llm_used=False, routing_mode=routing_mode,
                cache_hit=True
            )
            yield f"data: {json.dumps({'done': True, 'metadata': metadata})}\n\n"

        return StreamingResponse(generate_cache(), media_type="text/event-stream")

    # ── STEP 3: LLM STREAMING PATH ─────────────────────────────────────────
    target_model = model_sel["openrouter_id"] or model_sel["model"]
    api_cost = 0.0
    prompt_tokens = max(5, int(prompt_len / 4.0))
    output_tokens = 40
    is_mocked = False
    full_reply = ""
    start_time = time.time()

    user_email = await _resolve_user_email(request)
    max_tokens = 600
    if user_email:
        max_tokens = req.max_output_tokens or 200

    async def generate():
        nonlocal api_cost, prompt_tokens, output_tokens, is_mocked, full_reply
        try:
            async for token in provider_router.stream_completion(
                model_id=target_model,
                messages=_build_messages(req),
                max_tokens=max_tokens,
            ):
                if token:
                    full_reply += token
                    yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            logger.warning(f"LLM streaming failed: {e}")
            is_mocked = True
            full_reply = "I'm sorry, I encountered an error processing your request. Please try again or contact support if the issue persists."
            yield f"data: {json.dumps({'token': full_reply})}\n\n"

        cleaned_reply = clean_response(full_reply)
        output_tokens = len(cleaned_reply.split())

        latency_seconds = round(time.time() - start_time, 3)
        v_result = verifier.verify_completion(
            model_id=model_sel["model"], prompt_tokens=prompt_tokens,
            completion_tokens=output_tokens, latency_seconds=latency_seconds,
            reported_co2_g=savings["estimated_co2_g"]
        )

        # Store in cache if successful
        if cleaned_reply and not cleaned_reply.startswith("I'm sorry") and not req.images:
            await response_cache.store(
                question=req.message,
                answer=cleaned_reply,
                tier=classification["tier"],
                model=model_sel["model"],
                provider=model_sel["provider"],
                region_info=region_info,
                savings=savings
            )

        await _record_and_notify(
            request, req, classification, region_info, model_sel, savings,
            api_cost, latency_seconds, is_mocked, v_result,
            routing_mode=routing_mode, answer_source="llm",
            knowledge_match=False, knowledge_confidence=knowledge_res["confidence"], llm_used=True,
            cache_hit=False
        )

        yield f"data: {json.dumps({'done': True, 'metadata': _build_metadata(
            classification, prompt_len, region_info, model_sel, savings,
            v_result, api_cost, latency_seconds, is_mocked, output_tokens, prompt_tokens,
            answer_source="llm", knowledge_match=False,
            knowledge_confidence=knowledge_res["confidence"], llm_used=True, routing_mode=routing_mode,
            cache_hit=False
        )})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


