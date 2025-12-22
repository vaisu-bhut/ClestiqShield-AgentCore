"""
Hallucination Detector Node.

Uses a "Judge LLM" pattern to verify factual consistency between
the original query and the LLM's response.
"""

import time
from typing import Dict, Any

# from langchain_google_genai import ChatGoogleGenerativeAI - Moved to get_judge_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import structlog

from app.core.metrics import get_guardian_metrics

logger = structlog.get_logger()

# Judge LLM for hallucination detection
_judge_llm = None


def get_judge_llm():
    global _judge_llm
    if _judge_llm is None:
        from langchain_google_genai import ChatGoogleGenerativeAI

        from app.core.config import get_settings

        settings = get_settings()
        _judge_llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0,
        )
    return _judge_llm


HALLUCINATION_JUDGE_PROMPT = """
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


async def hallucination_detector_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect hallucinations in LLM response using a Judge LLM.
    """
    logger.info(
        "HALLUCINATION DETECTOR NODE CALLED", guardrails=state.get("guardrails")
    )  # DEBUG

    metrics = get_guardian_metrics()
    start_time = time.perf_counter()

    llm_response = state.get("llm_response", "")
    original_query = state.get("original_query", "")
    guardrails = state.get("guardrails") or {}

    # Check if hallucination check is enabled
    if not guardrails.get("hallucination_check", False):
        logger.info("Hallucination check SKIPPED - not enabled in guardrails")  # DEBUG
        return state

    if not original_query or not llm_response:
        logger.debug("Skipping hallucination check: missing query or response")
        return state

    try:
        prompt = ChatPromptTemplate.from_template(HALLUCINATION_JUDGE_PROMPT)
        chain = prompt | get_judge_llm() | JsonOutputParser()

        result = await chain.ainvoke(
            {"query": original_query, "response": llm_response}
        )

        hallucination_detected = result.get("hallucination_detected", False)
        confidence = result.get("confidence", 0.0)
        details = result.get("details")

        latency_ms = (time.perf_counter() - start_time) * 1000
        metrics.record_latency("hallucination_check", latency_ms)

        logger.info(
            "Hallucination check complete",
            detected=hallucination_detected,
            confidence=confidence,
            latency_ms=round(latency_ms, 2),
        )

        return {
            **state,
            "hallucination_detected": hallucination_detected,
            "hallucination_details": details if hallucination_detected else None,
        }

    except Exception as e:
        logger.error("Hallucination check failed", error=str(e))
        return state
