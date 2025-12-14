"""
Brand Tone Checker Node.

Verifies that LLM responses match the user-defined brand tone
(professional, casual, technical, friendly).
"""

import time
from typing import Dict, Any
from langchain_google_vertexai import ChatVertexAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import structlog

from app.core.metrics import get_guardian_metrics

logger = structlog.get_logger()

_tone_llm = None


def get_tone_llm():
    global _tone_llm
    if _tone_llm is None:
        _tone_llm = ChatVertexAI(model_name="gemini-2.0-flash-exp", temperature=0)
    return _tone_llm


TONE_CHECK_PROMPT = """
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


async def tone_checker_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check if LLM response matches the desired brand tone.
    """
    metrics = get_guardian_metrics()
    start_time = time.perf_counter()

    llm_response = state.get("llm_response", "")
    guardrails = state.get("guardrails") or {}

    # Get desired tone from guardrails
    desired_tone = guardrails.get("brand_tone")

    # Skip if brand_tone not specified
    if not desired_tone:
        return state

    if not llm_response:
        return state

    try:
        prompt = ChatPromptTemplate.from_template(TONE_CHECK_PROMPT)
        chain = prompt | get_tone_llm() | JsonOutputParser()

        result = await chain.ainvoke(
            {"desired_tone": desired_tone, "response": llm_response}
        )

        tone_compliant = result.get("tone_compliant", True)
        violation_reason = result.get("violation_reason")

        latency_ms = (time.perf_counter() - start_time) * 1000
        metrics.record_latency("tone_check", latency_ms)

        logger.info(
            "Tone check complete",
            compliant=tone_compliant,
            desired=desired_tone,
            latency_ms=round(latency_ms, 2),
        )

        return {
            **state,
            "tone_compliant": tone_compliant,
            "tone_violation_reason": violation_reason if not tone_compliant else None,
        }

    except Exception as e:
        logger.error("Tone check failed", error=str(e))
        return state
