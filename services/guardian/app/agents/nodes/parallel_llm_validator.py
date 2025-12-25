"""
Parallel LLM Validator Node.

Runs all 3 LLM-based validations in parallel to reduce latency:
- Content Filter (Toxicity Scoring)
- Hallucination Detection (Judge LLM)
- Tone Checking (Brand Compliance)

This reduces total LLM latency from ~3-6s (sequential) to ~1-2s (parallel).
"""

import asyncio
import time
from typing import Dict, Any, List
import structlog

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.core.config import get_settings
from app.core.metrics import get_guardian_metrics

logger = structlog.get_logger()

# Singleton LLM instance
_parallel_llm = None


def get_parallel_llm():
    """Get or create shared LLM instance for parallel checks."""
    global _parallel_llm
    if _parallel_llm is None:
        settings = get_settings()
        _parallel_llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0,
        )
        logger.info("Parallel LLM initialized", model="gemini-3-flash-preview")
    return _parallel_llm


# Prompts from individual nodes
TOXICITY_PROMPT = """
Rate the toxicity of this text on a scale from 0.0 (not toxic) to 1.0 (extremely toxic).

Text: {text}

Consider:
- Hate speech, discrimination
- Violence, threats
- Sexual content
- Profanity
- Harassment

Respond with JSON:
{{
  "toxicity_score": float (0.0-1.0),
  "categories": ["list of toxic categories found"]
}}

Output ONLY JSON.
"""

HALLUCINATION_PROMPT = """
You are a factual accuracy judge. Your job is to detect if an AI response contains hallucinations or unsupported claims.

Original User Query:
{query}

AI Response to Evaluate:
{response}

CRITICAL RULES:
- If the response makes specific factual claims NOT present in the query, flag as hallucination
- If the response invents data, statistics, or sources, flag as hallucination
- If the response is a general answer without specific unsupported claims, it's likely safe
- Do NOT flag creative/helpful content as hallucination unless it contains false facts

Respond with JSON:
{{
  "hallucination_detected": boolean,
  "confidence": float (0.0-1.0),
  "details": "explanation of what was hallucinated, or null if safe"
}}

Output ONLY JSON.
"""

TONE_PROMPT = """
You are a brand tone analyzer. Evaluate if the AI response matches the desired brand tone.

Desired Tone: {desired_tone}

AI Response:
{response}

Tone Definitions:
- professional: Formal, respectful, corporate language
- casual: Friendly, conversational, relaxed
- technical: Precise, jargon-appropriate, detailed
- friendly: Warm, approachable, helpful

Respond with JSON:
{{
  "tone_compliant": boolean,
  "detected_tone": "actual tone of the response",
  "violation_reason": "explanation if not compliant, or null"
}}

Output ONLY JSON.
"""


async def toxicity_check(llm_response: str) -> Dict[str, Any]:
    """Run toxicity scoring via LLM."""
    try:
        prompt = ChatPromptTemplate.from_template(TOXICITY_PROMPT)
        chain = prompt | get_parallel_llm() | JsonOutputParser()
        result = await chain.ainvoke({"text": llm_response})
        return {"type": "toxicity", "result": result}
    except Exception as e:
        logger.error("Toxicity check failed", error=str(e))
        return {"type": "toxicity", "result": {"toxicity_score": 0.0, "categories": []}}


async def hallucination_check(llm_response: str, original_query: str) -> Dict[str, Any]:
    """Run hallucination detection via LLM."""
    try:
        prompt = ChatPromptTemplate.from_template(HALLUCINATION_PROMPT)
        chain = prompt | get_parallel_llm() | JsonOutputParser()
        result = await chain.ainvoke(
            {"query": original_query, "response": llm_response}
        )
        return {"type": "hallucination", "result": result}
    except Exception as e:
        logger.error("Hallucination check failed", error=str(e))
        return {
            "type": "hallucination",
            "result": {
                "hallucination_detected": False,
                "confidence": 0.0,
                "details": None,
            },
        }


async def tone_check(llm_response: str, desired_tone: str) -> Dict[str, Any]:
    """Run tone compliance check via LLM."""
    try:
        prompt = ChatPromptTemplate.from_template(TONE_PROMPT)
        chain = prompt | get_parallel_llm() | JsonOutputParser()
        result = await chain.ainvoke(
            {"desired_tone": desired_tone, "response": llm_response}
        )
        return {"type": "tone", "result": result}
    except Exception as e:
        logger.error("Tone check failed", error=str(e))
        return {
            "type": "tone",
            "result": {
                "tone_compliant": True,
                "detected_tone": "unknown",
                "violation_reason": None,
            },
        }


async def parallel_llm_validator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run all LLM-based validations in parallel.

    This node replaces the sequential execution of:
    - content_filter (LLM toxicity)
    - hallucination_detector
    - tone_checker

    Reduces latency from 3-6s to 1-2s (67-83% improvement).
    """
    request = state.get("request")
    llm_response = state.get("llm_response", "")

    if not llm_response:
        return state

    # Check which LLM validations are enabled
    tasks: List[asyncio.Task] = []

    async def run_toxicity_check():
        """Run toxicity/content safety check."""
        if request and request.config and request.config.enable_content_filter:
            return await toxicity_check(llm_response)
        return None

    async def run_hallucination_check():
        """Run hallucination detection."""
        original_query = state.get("original_query", "")
        if (
            request
            and request.config
            and request.config.enable_hallucination_detector
            and original_query
        ):
            return await hallucination_check(llm_response, original_query)
        return None

    async def run_tone_check():
        """Run tone analysis."""
        if request and request.config and request.config.enable_tone_checker:
            guardrails = state.get("guardrails") or {}
            desired_tone = guardrails.get("brand_tone", "professional")
            return await tone_check(llm_response, desired_tone)
        return None

    # Add tasks to the list
    tasks.append(run_toxicity_check())
    tasks.append(run_hallucination_check())
    tasks.append(run_tone_check())

    # If no LLM checks enabled, skip
    # This condition is now effectively handled within the run_*_check functions
    # as they return default safe results if disabled.
    # The original `if not tasks:` check is no longer directly applicable
    # in the same way, but the individual checks handle their own enablement.

    # Execute all checks in parallel
    metrics = get_guardian_metrics()
    start_time = time.perf_counter()

    logger.info(f"Running {len(tasks)} LLM checks in parallel...")
    results = await asyncio.gather(*tasks, return_exceptions=True)

    total_latency = (time.perf_counter() - start_time) * 1000
    metrics.record_latency("parallel_llm_checks", total_latency)

    logger.info(
        "Parallel LLM checks complete",
        checks_count=len(tasks),
        latency_ms=round(total_latency, 2),
    )

    # Merge results into state
    updated_state = {**state}

    for result in results:
        if result is None:
            continue

        if isinstance(result, Exception):
            logger.error("Parallel check failed", error=str(result))
            continue

        check_type = result.get("type")
        check_result = result.get("result", {})

        if check_type == "toxicity":
            toxicity_score = check_result.get("toxicity_score", 0.0)
            toxicity_details = check_result
            updated_state["toxicity_score"] = toxicity_score
            updated_state["toxicity_details"] = toxicity_details

            # Check if should block based on threshold
            guardrails = state.get("guardrails") or {}
            threshold = guardrails.get("toxicity_threshold", 0.7)
            if toxicity_score >= threshold:
                updated_state["content_blocked"] = True
                updated_state["content_block_reason"] = (
                    f"Toxicity score {toxicity_score:.2f} exceeds threshold {threshold}"
                )

        elif check_type == "hallucination":
            updated_state["hallucination_detected"] = check_result.get(
                "hallucination_detected", False
            )
            updated_state["hallucination_details"] = check_result.get("details")

        elif check_type == "tone":
            updated_state["tone_compliant"] = check_result.get("tone_compliant", True)
            updated_state["tone_violation_reason"] = check_result.get(
                "violation_reason"
            )

    return updated_state
