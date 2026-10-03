from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from datetime import datetime, timezone
import asyncio
import time
import logging
import hashlib
import json
import re
import os
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
from providers import provider_router, extract_byok_keys
from idempotency import idempotency_store, normalise_key
from byok_store import persistent_byok
from energy import begin as begin_energy_sample, end as end_energy_sample, measurement_type as get_measurement_type
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

# Approximate $ per 1K tokens, keyed by models.CARBON_MODELS `id`. Every
# catalog model is on a free tier, so their true rate is zero — the 0.001
# default below only applies to an id we don't recognise.
MODEL_COST_MAP = {
    "nemotron-3-ultra-550b-a55b:free": 0.0,
    "nemotron-3-super-120b-a12b:free": 0.0,
    "dots-3-note-preview:free": 0.0,
    "qwen3.8-27b:free": 0.0,
    "nemotron-3-nano-omni-30b-a3b-reasoning:free": 0.0,
    "north-mini-code:free": 0.0,
    "lfm-2.5-2.6b:free": 0.0,
}

# Conservative blended per-1K-token estimates for providers outside the free
# catalog. These are deliberately surfaced as estimates, not billing records.
PROVIDER_COST_MAP = {
    "openai": 0.005,
    "groq": 0.0006,
    "anthropic": 0.001,
}

WORST_MODEL = {"model": "ling-3.0-flash", "carbon_score": 5, "provider": "InclusionAI"}
WORST_INTENSITY = 710.0

# Rough g CO2/kWh by grid mix, used where a provider's region data records a
# fuel type rather than a measured intensity. Module-level because both the
# manual-model path in `_build_routing` and the post-call reconciliation in
# `_reconcile_final_route` must agree on it.
GRID_ESTIMATES = {
    "Hydro/Nuclear": 15, "Hydro": 30, "Nuclear": 50, "Wind": 100,
    "Wind/Nuclear": 80, "Wind/Gas": 180, "Gas/Wind": 200, "Gas": 350,
    "Mixed": 300, "Wind/Coal": 350, "Coal/Gas": 500, "Coal": 650,
}

# What the grid half of a CO2 estimate was derived from. Surfaced so a figure
# is never read as locating the call in a place we cannot substantiate.
CARBON_BASIS_FINAL_PROVIDER = "final-provider-region"
CARBON_BASIS_SELECTED_REGION = "selected-region"

# Floor for a caller-chosen `max_output_tokens`. The schema accepts 1, but a
# reasoning model can spend a small budget on its own thinking and reply with
# nothing: `gemini-flash-latest` returned content=None at max_tokens 8, 16 and
# 32, and only produced text from 64 upwards (OpenRouter's llama-4-scout
# answers at every budget tested). Handing back 128 tokens when someone asks
# for fewer beats handing back an empty response that reads like a dead
# provider.
MIN_OUTPUT_TOKENS = 128


def _api_cost_rate(model_sel: dict, provider_lineage: dict | None) -> tuple[float, bool]:
    """Return the rate and whether it is a provider/model approximation."""
    final_provider = (provider_lineage or {}).get("final_provider")
    final_model = (provider_lineage or {}).get("final_model")
    if final_provider in PROVIDER_COST_MAP:
        return PROVIDER_COST_MAP[final_provider], True
    model_id = final_model or model_sel["model"]
    return MODEL_COST_MAP.get(model_id, MODEL_COST_MAP.get(model_sel["model"], 0.001)), False


def _effective_max_tokens(max_output_tokens: int | None) -> int:
    """Resolve an authenticated caller's output budget against the floor.

    Anonymous requests bypass this entirely and use the fixed default above.
    """
    return max(MIN_OUTPUT_TOKENS, max_output_tokens or 200)


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
    token = auth_header[7:] if auth_header.startswith("Bearer ") else request.cookies.get("ecoquery_access_token", "")
    if not token:
        return ""
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


# Two independent switches, because the two endpoints serve different callers:
#
#   /api/chat        The documented programmatic API (README shows an
#                    `Authorization: Bearer eq_...` header). No frontend
#                    caller uses it anonymously, so anonymous access defaults
#                    to OFF and locks down in every environment.
#   /api/chat/stream Powers the public homepage demo (LiveDemo.tsx posts with
#                    no auth header), so anonymous access defaults to ON.
#
# Before these existed the policy was implicit and drifted: /api/chat
# 401'd anonymous callers on Render while /api/chat/stream accepted them, and
# neither had a switch. Both now flow through _require_chat_access() below so
# the shared quota check cannot diverge; only `allow_anonymous` differs.
#
# Anonymous calls on either endpoint are independently bounded by the stricter
# unauthenticated /api/chat* rate-limit bucket in main.py.
def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() == "true"


# Defaults are named constants so tests can assert them directly — a silent
# flip of either one would change the public API's auth posture.
DEFAULT_ALLOW_ANONYMOUS_CHAT = False       # /api/chat — locked down
DEFAULT_ALLOW_ANONYMOUS_CHAT_STREAM = True  # /api/chat/stream — public demo

_ALLOW_ANONYMOUS_CHAT = _env_flag("ALLOW_ANONYMOUS_CHAT", DEFAULT_ALLOW_ANONYMOUS_CHAT)
_ALLOW_ANONYMOUS_CHAT_STREAM = _env_flag("ALLOW_ANONYMOUS_CHAT_STREAM", DEFAULT_ALLOW_ANONYMOUS_CHAT_STREAM)


def _env_seconds(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    # A zero or negative interval would spin, and an absurd one would make the
    # keepalive meaningless, so fall back rather than honour it.
    return value if 0.1 <= value <= 300 else default


# Seconds the stream may stay silent before a keepalive comment is emitted.
# Two things depend on it: most reverse proxies reap an idle connection well
# before a slow provider's first token arrives, and the client cannot tell
# "still thinking" from "socket is dead" without something arriving in between.
#
# The frame is an SSE comment (a line beginning ':'), which the SSE spec
# discards and our own parser skips, so it is invisible to every consumer while
# still proving the connection is alive.
DEFAULT_SSE_HEARTBEAT_S = 10.0
SSE_HEARTBEAT_S = _env_seconds("SSE_HEARTBEAT_S", DEFAULT_SSE_HEARTBEAT_S)


async def _require_chat_access(request: Request, *, allow_anonymous: bool) -> str:
    """Shared authentication + quota policy for both chat endpoints.

    Returns the authenticated user's email, or "" for an anonymous caller.
    Raises 401 when anonymous access is disallowed for this endpoint, 402 when
    the user is over quota.
    """
    email = await _resolve_user_email(request)
    if not email:
        if not allow_anonymous:
            raise HTTPException(status_code=401, detail="Authentication is required for the chat API")
        return ""

    user = await auth_db.find_user_by_email(email)
    if user and user.get("tokens_used", 0) >= 100000:
        raise HTTPException(status_code=402, detail="Token limit of 100K reached.")
    return email


def _final_provider_region(final_provider: str | None) -> dict | None:
    """Grid facts for the provider that actually served the call, or None.

    `PROVIDER_REGIONS` only covers the vendors it was written for; openrouter,
    grok, openai and groq have no entry, so most requests come back None and
    keep the region chosen at routing time.
    """
    if not final_provider:
        return None
    info = PROVIDER_REGIONS.get(str(final_provider).lower())
    if not info:
        return None
    greenest = info.get("greenest_region")
    region_data = (info.get("regions") or {}).get(greenest) or {}
    grid_type = region_data.get("grid", "Mixed")
    return {
        "region": greenest,
        "energy_source": grid_type,
        "carbon_intensity_g_kwh": GRID_ESTIMATES.get(grid_type, 350),
        "method": "final-provider-region",
    }


def _reconcile_final_route(
    region_info: dict, model_sel: dict, savings: dict,
    provider_lineage: dict | None, prompt_len: int,
) -> tuple[dict, dict]:
    """Re-price the route that ran, and record which grid it was priced against.

    CO2 here is model-carbon-score x grid intensity. The grid half was picked
    at routing time from the carbon-optimal region, but a fallback decides who
    actually serves the call -- so that region can describe somewhere other
    than the place that did the work.

    Where we hold region data for the serving provider we re-derive both
    intensity and savings from it. Where we do not, the planned intensity is
    kept and `carbon_basis` says so, rather than implying a location we cannot
    name. `region_info` is copied first: the dict may be the cached carbon
    payload, and mutating it would rewrite the cache for every later request.
    """
    final_region = _final_provider_region((provider_lineage or {}).get("final_provider"))
    base = dict(region_info)
    if final_region is None:
        base["carbon_basis"] = CARBON_BASIS_SELECTED_REGION
        return base, savings

    base.update(final_region)
    base["carbon_basis"] = CARBON_BASIS_FINAL_PROVIDER
    recomputed = compute_savings(
        model_sel["carbon_score"],
        final_region["carbon_intensity_g_kwh"],
        prompt_length=prompt_len,
    )
    return base, recomputed


async def _build_routing(req: ChatRequest):
    classification = await classifier.classify(req.message)
    prompt_len = len(req.message)
    routing_mode = req.routing_mode if req.routing_mode else "balanced"
    if req.model_id:
        routing_mode = "manual"
        
    routing = await route_query(classification["tier"], prompt_length=prompt_len, mode=routing_mode, confidence=classification["confidence"])
    region_info = routing["region"]
    model_sel = routing["model"]
    savings = routing["savings"]

    knowledge_res = {"matched": False, "confidence": 0.0, "answer": None, "stored_question": None, "tier": None}
    cache_res = {"matched": False, "confidence": 0.0, "answer": None, "stored_question": None, "tier": None}

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
    routing_mode: str = "balanced",
    cache_hit: bool = False,
    provider_lineage: dict | None = None,
    energy_reading=None,
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
    cost_rate, cost_is_estimate = _api_cost_rate(model_sel, provider_lineage)
    final_provider = (provider_lineage or {}).get("final_provider", model_sel["provider"])
    final_model = (provider_lineage or {}).get("final_model", actual_model_name)
    external_provider_estimate = final_provider in PROVIDER_COST_MAP
    if external_provider_estimate and llm_used:
        routed_model_display = (
            f"{final_provider} {final_model} (approximate carbon proxy) "
            f"via {region_info['region']} ({region_info['energy_source']})"
        )

    measurement_status = get_measurement_type(reading=energy_reading, provider_reported=False)
    co2e_value = round(energy_reading.energy_kwh * region_info.get("carbon_intensity_g_kwh", 0), 4) if energy_reading else (0.0 if not llm_used else savings["estimated_co2_g"])
    measured_zero = bool(energy_reading is not None and energy_reading.energy_kwh == 0)
    uncertainty_range = (
        {"min": 0, "max": 0}
        if measured_zero
        else ({"min": 0, "max": 0} if not llm_used else savings.get("uncertainty_range_g", {"min": 0, "max": 0}))
    )
    uncertainty_components = {} if measured_zero or not llm_used else savings.get("uncertainty_components", {})
    uncertainty_relative = 0.0 if measured_zero or not llm_used else savings.get("uncertainty_relative", 0.0)
    metadata = {
        "model_used": routed_model_display,
        "model_id": actual_model_name,
        "model_tier": "knowledge" if not llm_used else model_sel["tier"],
        "carbon_score": 0.0 if not llm_used else model_sel["carbon_score"],
        "region": "local-direct" if not llm_used else region_info["region"],
        "measurement_type": measurement_status,
        "energy_kwh": energy_reading.energy_kwh if energy_reading else (0.0 if not llm_used else savings.get("energy_kwh")),
        "energy_measurement_source": energy_reading.source if energy_reading else ("none" if not llm_used else "model-calibration-estimate"),
        "grid_source": region_info.get("data_source", "Mock"),
        "grid_timestamp": region_info.get("grid_timestamp"),
        "grid_intensity_g_per_kwh": 0.0 if not llm_used else region_info.get("carbon_intensity_g_kwh", 0),
        # Which grid that intensity came from: the provider that actually
        # served the call where we hold region data for it, otherwise the
        # region routing selected (which may not be where it ran).
        "carbon_basis": region_info.get("carbon_basis", CARBON_BASIS_SELECTED_REGION),
        "energy_assumption_kwh_per_1000_tokens": 0.0 if not llm_used else savings.get("energy_assumption_kwh_per_1000_tokens", 0),
        "calibration_version": None if not llm_used else savings.get("calibration_version"),
        "calibration_source": None if not llm_used else savings.get("calibration_source"),
        "uncertainty_range_g": uncertainty_range,
        "uncertainty_components": uncertainty_components,
        "uncertainty_relative": uncertainty_relative,
        "energy_source": "zero-emission" if not llm_used else region_info.get("energy_source", "Unknown"),
        "carbon_formula": "energy_kwh × grid_intensity_g_per_kwh",
        "carbon_assumptions": [
            "Cloud-provider energy is estimated unless the provider reports energy directly.",
            "Grid intensity comes from the provider that served the call where EcoQuery holds region data for it, otherwise from the selected routing region; `carbon_basis` says which applied.",
        ] if llm_used else ["No external LLM inference was used; total application electricity is not measured by this result."],
        "carbon_baseline": {"model": WORST_MODEL["model"], "region": "ap-south-1 (Mumbai)", "grid_intensity_g_per_kwh": WORST_INTENSITY},
        "co2e_g": co2e_value,
        "co2_estimated_g": co2e_value,
        "co2_saved_g": worst_savings["estimated_co2_g"] if not llm_used else round(max(0.0, worst_savings["estimated_co2_g"] - co2e_value), 4),
        "tier": classification["tier"],
        "confidence": round(classification["confidence"], 3),
        "is_mocked": is_mocked,
        "api_cost": api_cost,
        "api_cost_is_estimate": cost_is_estimate,
        "api_cost_basis": (
            f"{final_provider}/{final_model} blended estimate at ${cost_rate}/1K tokens"
            if cost_is_estimate else "catalog model cost map"
        ),
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
        "requested_model": model_sel["model"],
        "requested_provider": (provider_lineage or {}).get("requested_provider", "openrouter"),
        "attempted_providers": (provider_lineage or {}).get("attempted_providers", []),
        "final_provider": (provider_lineage or {}).get("final_provider", model_sel["provider"]),
        "final_model": (provider_lineage or {}).get("final_model", actual_model_name),
        "carbon_estimate_is_approximate": external_provider_estimate,
        "carbon_estimate_basis": (
            f"Catalog carbon proxy applied to {final_provider}/{final_model}; "
            "provider energy and region are not directly reported."
            if external_provider_estimate else "Catalog model calibration and routed region"
        ),
        "fallback_reason": (provider_lineage or {}).get("fallback_reason") or model_sel.get("reason", "Direct selection"),
        "quality_safeguard": model_sel.get("quality_safeguard"),
        "success": not is_mocked,
        "what_if": {
            "baseline_model": WORST_MODEL["model"],
            "baseline_region": "ap-south-1 (Mumbai)",
            "baseline_co2_g": worst_savings["estimated_co2_g"],
            "actual_model": actual_model_name,
            "actual_region": "local-direct" if not llm_used else region_info["region"],
            "actual_co2_g": co2e_value,
            "co2_saved_g": round(max(0.0, worst_savings["estimated_co2_g"] - co2e_value), 4),
            "baseline_cost": 0.0,
            "actual_cost": api_cost,
        },
    }

    # BYOK provenance. Only present when a provider call actually happened, so
    # knowledge-base and cached answers do not claim a key source. Ownership
    # values only — a credential is never echoed back to the caller.
    if provider_lineage:
        metadata["byok_used"] = bool(provider_lineage.get("byok_used"))
        if provider_lineage.get("key_source"):
            metadata["key_source"] = provider_lineage["key_source"]

    return metadata


async def _record_and_notify(
    request: Request, req, classification, region_info, model_sel, savings,
    api_cost, latency_seconds, is_mocked, v_result,
    routing_mode: str = "balanced",
    answer_source: str = "llm",
    knowledge_match: bool = False,
    knowledge_confidence: float = 0.0,
    llm_used: bool = True,
    cache_hit: bool = False,
    provider_lineage: dict | None = None,
    energy_reading=None,
):
    user_email = await _resolve_user_email(request)
    zero_llm_savings = compute_savings(WORST_MODEL["carbon_score"], WORST_INTENSITY, prompt_length=len(req.message))
    saved_vs_baseline = savings["saved_vs_baseline_g"] if llm_used else zero_llm_savings["estimated_co2_g"]
    model_name = model_sel["model"] if llm_used else ("ecoquery-knowledge" if answer_source == "ecoquery_knowledge" else "ecoquery-stored-response")
    provider_name = model_sel["provider"] if llm_used else ("EcoQuery Knowledge" if answer_source == "ecoquery_knowledge" else "EcoQuery Stored Response")
    co2e_value = round(energy_reading.energy_kwh * region_info.get("carbon_intensity_g_kwh", 0), 4) if energy_reading else (0.0 if not llm_used else savings["estimated_co2_g"])

    await ledger.record_query({
        "query": req.message if os.getenv("STORE_QUERY_TEXT", "false").lower() == "true" else "[redacted]",
        "tier": classification["tier"],
        "model_used": model_name,
        "model_provider": provider_name,
        "model_tier": "knowledge" if not llm_used else model_sel["tier"],
        "carbon_score": 0.0 if not llm_used else model_sel["carbon_score"],
        "region": "local-direct" if not llm_used else region_info["region"],
        "energy_source": "zero-emission" if not llm_used else region_info["energy_source"],
        "co2_estimated": co2e_value,
        "co2_saved_vs_baseline": saved_vs_baseline,
        "is_mocked": is_mocked, "classifier_method": classification["method"],
        "classifier_confidence": classification["confidence"],
        "carbon_method": "zero-llm-cache" if not llm_used else region_info.get("method", "mock-fallback"),
        "carbon_basis": region_info.get("carbon_basis", CARBON_BASIS_SELECTED_REGION),
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
        "is_local_inference": (model_sel["provider"] == "Ollama (Local)") or not llm_used,
        "measurement_type": get_measurement_type(reading=energy_reading, provider_reported=False),
        "energy_kwh": energy_reading.energy_kwh if energy_reading else (0.0 if not llm_used else savings.get("energy_kwh")),
        "energy_measurement_source": energy_reading.source if energy_reading else ("none" if not llm_used else "model-calibration-estimate"),
        "calibration_version": savings.get("calibration_version"),
        "requested_provider": (provider_lineage or {}).get("requested_provider", "openrouter"),
        "requested_model": (provider_lineage or {}).get("requested_model", model_name),
        "attempted_providers": (provider_lineage or {}).get("attempted_providers", []),
        "final_provider": (provider_lineage or {}).get("final_provider", provider_name),
        "final_model": (provider_lineage or {}).get("final_model", model_name),
        "fallback_reason": (provider_lineage or {}).get("fallback_reason"),
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
            "co2_g": co2e_value,
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
            "co2_estimated_g": co2e_value,
            "answer_source": answer_source,
            "llm_used": llm_used,
            "cache_hit": cache_hit,
        })


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, request: Request):
    user_email = await _require_chat_access(request, allow_anonymous=_ALLOW_ANONYMOUS_CHAT)
    # Optional bring-your-own-key. Extracted once here, passed only to the
    # outbound provider calls, and never stored, logged or cached. Knowledge,
    # cache and zero-LLM answers simply leave it unused.
    byok_keys = extract_byok_keys(request.headers)
    if user_email:
        byok_keys = {**await persistent_byok.load_keys(user_email), **byok_keys}

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
    provider_lineage = None
    energy_started_at, energy_start_value, energy_nvml = begin_energy_sample()

    user_email = await _resolve_user_email(request)
    max_tokens = 600
    if user_email:
        max_tokens = _effective_max_tokens(req.max_output_tokens)

    try:
        result = await provider_router.chat_completion(
            model_id=target_model,
            messages=_build_messages(req),
            max_tokens=max_tokens,
            byok_keys=byok_keys,
        )
            
        reply_content = clean_response(result.get("content") or "") or ""
        provider_lineage = result.get("provider_lineage")

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
                        byok_keys=byok_keys,
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
            return JSONResponse(status_code=502, content={
                "success": False,
                "error_code": "PROVIDER_EMPTY_RESPONSE",
                "message": "The configured provider returned no usable response.",
            })

        # The fallback chain above may have swapped the model; the provider
        # router may have swapped the provider. Price the route that ran.
        region_info, savings = _reconcile_final_route(
            region_info, model_sel, savings, provider_lineage, prompt_len,
        )

        usage = result.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
        output_tokens = usage.get("completion_tokens", output_tokens)
        if prompt_tokens and output_tokens:
            rate, _cost_is_estimate = _api_cost_rate(model_sel, provider_lineage)
            api_cost = round((prompt_tokens * rate / 1000) + (output_tokens * rate / 1000), 6)

        # Store successful response in persistent cache for future queries
        if reply_content and not reply_content.startswith("I'm sorry") and not req.images and os.getenv("STORE_QUERY_TEXT", "false").lower() == "true":
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
        try:
            error_data = json.loads(str(e))
            if error_data.get("error_code"):
                return JSONResponse(status_code=503, content=error_data)
        except (ValueError, json.JSONDecodeError):
            pass
        return JSONResponse(status_code=502, content={
            "success": False,
            "error_code": "PROVIDER_REQUEST_FAILED",
            "message": "The configured provider failed to process this request.",
        })

    latency_seconds = round(time.time() - start_time, 3)
    energy_reading = end_energy_sample(energy_started_at, energy_start_value, energy_nvml) if model_sel.get("provider") == "Ollama (Local)" else None
    v_result = verifier.verify_completion(
        model_id=target_model, prompt_tokens=prompt_tokens,
        completion_tokens=output_tokens, latency_seconds=latency_seconds,
        reported_co2_g=round(energy_reading.energy_kwh * region_info.get("carbon_intensity_g_kwh", 0), 4) if energy_reading else savings["estimated_co2_g"]
    )

    await _record_and_notify(
        request, req, classification, region_info, model_sel, savings,
        api_cost, latency_seconds, is_mocked, v_result,
        routing_mode=routing_mode, answer_source="llm",
        knowledge_match=False, knowledge_confidence=knowledge_res["confidence"], llm_used=True,
        cache_hit=False, provider_lineage=provider_lineage, energy_reading=energy_reading
    )

    if user_email:
        await auth_db.increment_user_tokens(user_email, prompt_tokens + output_tokens)

    return ChatResponse(
        reply=reply_content,
        metadata=_build_metadata(
            classification, prompt_len, region_info, model_sel, savings,
            v_result, api_cost, latency_seconds, is_mocked, output_tokens, prompt_tokens,
            answer_source="llm", knowledge_match=False,
            knowledge_confidence=knowledge_res["confidence"], llm_used=True, routing_mode=routing_mode,
            cache_hit=False, provider_lineage=provider_lineage, energy_reading=energy_reading
        )
    )


def _request_fingerprint(req: ChatRequest, principal: str) -> str:
    """Digest of the exact request a replay would be answering, for one caller.

    Two independent conditions. The key says "this id was seen"; the body says
    "seen for *this* question" — without it a reused key hands one prompt's
    answer to a different prompt. The principal says "seen by *this* caller":
    the store is process-wide, so without it a tenant who obtained another's
    key could be served that tenant's answer. Anonymous callers all share an
    empty principal and are separated by the key alone, which is unguessable.

    Canonicalised so that key order in the conversation cannot make an
    identical request look different.
    """
    payload = json.dumps(req.model_dump(), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{principal}\n{payload}".encode("utf-8")).hexdigest()


def _replay_stored(stored: dict):
    """Emit a finished answer in the frames a live stream would have sent.

    The original was written token by token; the client only accumulates text,
    so one frame carrying the whole reply produces the identical bubble and
    keeps the replay free of the work it exists to avoid.

    `idempotent_replay` is set so a caller — and the tests — can tell a
    replayed answer from a freshly generated one rather than having to infer it
    from timing.
    """
    yield f"data: {json.dumps({'token': stored['reply']})}\n\n"
    metadata = {**stored.get('metadata', {}), 'idempotent_replay': True}
    yield f"data: {json.dumps({'done': True, 'metadata': metadata})}\n\n"


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    user_email = await _require_chat_access(request, allow_anonymous=_ALLOW_ANONYMOUS_CHAT_STREAM)

    # After auth, before anything costs money: a send that has already been
    # answered is answered again from memory. Deliberately upstream of routing
    # and classification, which a replay has no need to perform.
    idem_key = normalise_key(request.headers.get("Idempotency-Key"))
    fingerprint = _request_fingerprint(req, user_email)
    stored = idempotency_store.get(idem_key)
    # Three things must line up: the key was seen, seen for this question, and
    # seen by this caller. Any two of them is not enough — a reused key must not
    # be handed another prompt's answer, nor another tenant's.
    if stored is not None and stored.get("fingerprint") == fingerprint:
        return StreamingResponse(_replay_stored(stored), media_type="text/event-stream")
    # Optional bring-your-own-key; passed only to the outbound provider call.
    # Never stored, logged or cached, and unused on knowledge/cache answers.
    byok_keys = extract_byok_keys(request.headers)
    if user_email:
        byok_keys = {**await persistent_byok.load_keys(user_email), **byok_keys}

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
    provider_lineage = None
    start_time = time.time()

    user_email = await _resolve_user_email(request)
    max_tokens = 600
    if user_email:
        max_tokens = _effective_max_tokens(req.max_output_tokens)

    async def generate():
        # `region_info`/`savings` are assigned below by the reconciliation, so
        # they must be declared nonlocal too -- otherwise Python treats them as
        # locals of `generate()` for the whole body and every earlier read hits
        # UnboundLocalError.
        nonlocal api_cost, prompt_tokens, output_tokens, is_mocked, full_reply, provider_lineage
        nonlocal region_info, savings

        # The provider stream is drained into a queue by a separate task rather
        # than read directly. Waiting on the generator with a timeout would
        # cancel it instead: `asyncio.wait_for` throws CancelledError into
        # `__anext__` at its suspension point, which closes the provider call
        # and ends the reply. The reader has to be something a timeout can be
        # applied to without harming it, which is what the queue is for.
        stream_task = None
        try:
            queue: asyncio.Queue = asyncio.Queue()
            _END = object()

            async def _pump(source):
                """Drain `source` into `queue`, ending it or handing over an error.

                `except Exception` deliberately does not catch CancelledError:
                cancelling this task must propagate rather than arrive at the
                consumer as an ordinary end-of-stream.
                """
                try:
                    async for token in source:
                        await queue.put(token)
                except Exception as exc:  # the consumer raises it, as before
                    await queue.put(exc)
                else:
                    await queue.put(_END)

            stream_task = asyncio.create_task(_pump(provider_router.stream_completion(
                model_id=target_model,
                messages=_build_messages(req),
                max_tokens=max_tokens,
                byok_keys=byok_keys,
            )))

            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=SSE_HEARTBEAT_S)
                except asyncio.TimeoutError:
                    # Nothing has arrived, but the connection is still ours to
                    # hold open: an SSE comment keeps a proxy from reaping an
                    # idle socket while a slow provider produces its first
                    # token, and lets the client tell slow from dead.
                    yield ": hb\n\n"
                    continue

                if item is _END:
                    break
                if isinstance(item, BaseException):
                    raise item
                if isinstance(item, dict) and "token" in item:
                    tok = item["token"]
                    full_reply += tok
                    yield f"data: {json.dumps({'token': tok})}\n\n"
                elif isinstance(item, str):
                    full_reply += item
                    yield f"data: {json.dumps({'token': item})}\n\n"
                elif isinstance(item, dict) and "provider_lineage" in item:
                    provider_lineage = item["provider_lineage"]
        except Exception as e:
            logger.warning(f"LLM streaming failed: {e}")
            try:
                error_data = json.loads(str(e))
                if error_data.get("error_code") == "PROVIDER_UNAVAILABLE":
                    yield f"data: {json.dumps(error_data)}\n\n"
                    return
            except (ValueError, json.JSONDecodeError):
                pass
                
            yield f"data: {json.dumps({'success': False, 'error_code': 'PROVIDER_UNAVAILABLE', 'message': 'No configured provider was able to process this request.'})}\n\n"
            return
        finally:
            # Reached on a client disconnect too, and load-bearing there: the
            # pump outlives this generator otherwise, so it would keep paying
            # a provider for tokens nobody is left to receive.
            if stream_task is not None:
                stream_task.cancel()

        cleaned_reply = clean_response(full_reply)
        output_tokens = len(cleaned_reply.split())
        rate, _cost_is_estimate = _api_cost_rate(model_sel, provider_lineage)
        api_cost = round((prompt_tokens * rate / 1000) + (output_tokens * rate / 1000), 6)

        # The provider router may have swapped the provider mid-call; price
        # the route that ran rather than the one routing-time chose. Ahead of
        # the verifier so the figure it checks is the figure we report.
        region_info, savings = _reconcile_final_route(
            region_info, model_sel, savings, provider_lineage, prompt_len,
        )

        latency_seconds = round(time.time() - start_time, 3)
        v_result = verifier.verify_completion(
            model_id=model_sel["model"], prompt_tokens=prompt_tokens,
            completion_tokens=output_tokens, latency_seconds=latency_seconds,
            reported_co2_g=savings["estimated_co2_g"]
        )

        # Store in cache if successful
        if cleaned_reply and not cleaned_reply.startswith("I'm sorry") and not req.images and os.getenv("STORE_QUERY_TEXT", "false").lower() == "true":
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
            cache_hit=False, provider_lineage=provider_lineage
        )

        if user_email:
            await auth_db.increment_user_tokens(user_email, prompt_tokens + output_tokens)

        metadata = _build_metadata(
            classification, prompt_len, region_info, model_sel, savings,
            v_result, api_cost, latency_seconds, is_mocked, output_tokens, prompt_tokens,
            answer_source="llm", knowledge_match=False,
            knowledge_confidence=knowledge_res["confidence"], llm_used=True, routing_mode=routing_mode,
            cache_hit=False, provider_lineage=provider_lineage,
        )
        # Stored exactly where the terminal frame is emitted, so the invariant
        # holds that anything replayable was answered in full: an errored,
        # cancelled or aborted stream never reaches this line and therefore
        # leaves nothing behind for a retry to find.
        idempotency_store.put(idem_key, {
            "reply": cleaned_reply,
            "metadata": metadata,
            "fingerprint": fingerprint,
        })

        yield f"data: {json.dumps({'done': True, 'metadata': metadata})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
