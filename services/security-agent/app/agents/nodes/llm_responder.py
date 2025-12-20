"""
LLM Responder Node.

Routes queries to Gemini models via Vertex AI.
"""

import time
from typing import Dict, Any, Optional

# from langchain_google_vertexai import ChatVertexAI - Moved to get_llm
from langchain_core.messages import HumanMessage, SystemMessage
import httpx
import structlog

from app.core.config import get_settings
from app.core.metrics import get_security_metrics

logger = structlog.get_logger()

# Gemini Models Only (for now)
SUPPORTED_MODELS = {
    "gemini-2.5-flash": "gemini-2.5-flash",
    "default": "gemini-2.5-flash",
}

_llm_cache: Dict[str, Any] = {}


def get_model_name(requested: str) -> str:
    """Get the Vertex AI model name."""
    settings = get_settings()
    default_model = settings.LLM_MODEL_NAME

    if not requested:
        return default_model

    # Check if exact match in supported models
    if requested in SUPPORTED_MODELS:
        return SUPPORTED_MODELS[requested]

    # Check if exact match in supported models values
    if requested in SUPPORTED_MODELS.values():
        return requested

    return SUPPORTED_MODELS.get(requested.lower().strip(), default_model)


def get_llm(model_name: str) -> Any:
    """Get or create LLM instance."""
    global _llm_cache

    if model_name not in _llm_cache:
        from langchain_google_vertexai import ChatVertexAI

        settings = get_settings()
        _llm_cache[model_name] = ChatVertexAI(
            model_name=model_name,
            max_tokens=settings.LLM_MAX_TOKENS,
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_LOCATION,
        )
        logger.info("Created LLM", model=model_name)

    return _llm_cache[model_name]


async def call_guardian(
    llm_response: str,
    moderation_mode: str = "moderate",
    output_format: str = "json",
    guardrails: Optional[Dict[str, Any]] = None,
    original_query: Optional[str] = None,
) -> Dict[str, Any]:
    """Call Guardian for output validation."""
    settings = get_settings()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.GUARDIAN_SERVICE_URL}/validate",
                json={
                    "llm_response": llm_response,
                    "moderation_mode": moderation_mode,
                    "output_format": output_format,
                    "guardrails": guardrails,
                    "original_query": original_query,
                },
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error("Guardian call failed", error=str(e))
        return {"validation_passed": True, "validated_response": llm_response}


async def llm_responder_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph node for LLM response."""
    settings = get_settings()
    metrics = get_security_metrics()

    if state.get("is_blocked"):
        return state

    if not settings.LLM_FORWARD_ENABLED:
        return state

    # Get query
    query = (
        state.get("toon_query")
        or state.get("redacted_input")
        or state.get("sanitized_input")
        or (state.get("input") or {}).get("prompt", "")
    )

    if not query:
        logger.warning("No query for LLM")
        return state

    input_data = state.get("input") or {}
    requested_model = input_data.get("model", "")
    moderation = input_data.get("moderation", "moderate")
    output_format = input_data.get("output_format", "json")

    model_name = get_model_name(requested_model)

    logger.info("LLM request", model=model_name)

    start_time = time.perf_counter()

    try:
        llm = get_llm(model_name)

        messages = [
            SystemMessage(content="You are a helpful AI assistant."),
            HumanMessage(content=query),
        ]

        response = await llm.ainvoke(messages)
        llm_latency = (time.perf_counter() - start_time) * 1000

        response_text = (
            response.content if hasattr(response, "content") else str(response)
        )

        # Token usage
        input_tokens = output_tokens = 0
        if hasattr(response, "response_metadata"):
            usage = response.response_metadata.get("usage_metadata", {})
            input_tokens = usage.get("prompt_token_count", 0)
            output_tokens = usage.get("candidates_token_count", 0)

        if not input_tokens:
            input_tokens = len(query) // 4
        if not output_tokens:
            output_tokens = len(response_text) // 4

        metrics.record_llm_tokens(input_tokens, output_tokens)
        metrics.record_stage_latency("llm_response", llm_latency)

        logger.info("LLM response", model=model_name, latency_ms=round(llm_latency, 2))

        # Guardian validation
        guardrails = input_data.get("guardrails", {})
        original_query = input_data.get("prompt", "")

        guardian_result = await call_guardian(
            response_text,
            moderation,
            output_format,
            guardrails=guardrails,
            original_query=original_query,
        )

        # DEBUG: Log what Guardian returned
        logger.info(
            "Guardian result received",
            hallucination_detected=guardian_result.get("hallucination_detected"),
            citations_verified=guardian_result.get("citations_verified"),
            disclaimer_injected=guardian_result.get("disclaimer_injected"),
            has_validated_response=bool(guardian_result.get("validated_response")),
        )

        if guardian_result.get("content_blocked"):
            return {
                **state,
                "is_blocked": True,
                "block_reason": f"Output blocked: {guardian_result.get('content_block_reason')}",
                "llm_response": None,
                "model_used": model_name,
            }

        # Depseudonymization: Replace tokens with original PII values
        validated_response = guardian_result.get("validated_response", response_text)
        pii_mapping = state.get("pii_mapping", {})

        if pii_mapping and validated_response:
            # Replace each token with its original value
            for token, original_value in pii_mapping.items():
                validated_response = validated_response.replace(token, original_value)

            logger.info("Depseudonymization complete", tokens_restored=len(pii_mapping))

        return {
            **state,
            "llm_response": validated_response,
            "llm_tokens_used": {
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens,
            },
            "model_used": model_name,
            # NEW: Guardian validation results
            "guardian_validation": {
                "hallucination_detected": guardian_result.get("hallucination_detected"),
                "citations_verified": guardian_result.get("citations_verified"),
                "tone_compliant": guardian_result.get("tone_compliant"),
                "disclaimer_injected": guardian_result.get("disclaimer_injected"),
                "false_refusal_detected": guardian_result.get("false_refusal_detected"),
                "toxicity_score": guardian_result.get("toxicity_score"),
            },
        }

    except Exception as e:
        logger.error("LLM failed", model=model_name, error=str(e))
        return {
            **state,
            "llm_response": None,
            "llm_error": str(e),
            "model_used": model_name,
        }
