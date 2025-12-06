"""
Content Filter Node.

Filters LLM output for harmful, inappropriate, or sensitive content
based on moderation mode.
"""

import re
import time
from typing import Dict, Any, List, Tuple
from langchain_google_vertexai import ChatVertexAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import structlog

from app.core.config import get_settings
from app.core.metrics import get_guardian_metrics

logger = structlog.get_logger()
settings = get_settings()

# Moderation rules by mode
MODERATION_RULES = {
    "strict": {"harmful": "block", "inappropriate": "block", "sensitive": "block"},
    "moderate": {"harmful": "block", "inappropriate": "warn", "sensitive": "allow"},
    "relaxed": {"harmful": "block", "inappropriate": "allow", "sensitive": "allow"},
    "raw": {"harmful": "allow", "inappropriate": "allow", "sensitive": "allow"},
}

# Pattern-based detection for fast filtering
HARMFUL_PATTERNS = [
    re.compile(r"\b(kill|murder|harm|hurt)\s+(yourself|someone|people)\b", re.I),
    re.compile(r"\b(make|create|build)\s+(bomb|weapon|explosive)\b", re.I),
    re.compile(r"\b(how\s+to|instructions\s+for)\s+(hack|steal|break\s+into)\b", re.I),
]

INAPPROPRIATE_PATTERNS = [
    re.compile(r"\b(explicit|adult|nsfw)\b", re.I),
    re.compile(r"profanity|obscene|vulgar", re.I),
]

SENSITIVE_PATTERNS = [
    re.compile(r"\b(political|religious|controversial)\b", re.I),
    re.compile(r"\b(suicide|self-harm|depression)\b", re.I),
]

# LLM for advanced content analysis
_content_llm = None


def get_content_llm():
    global _content_llm
    if _content_llm is None:
        _content_llm = ChatVertexAI(model_name="gemini-2.0-flash-exp", temperature=0)
    return _content_llm


CONTENT_ANALYSIS_PROMPT = """
Analyze the following LLM response for content safety.

Response to analyze:
{response}

Classify the content into these categories with confidence scores (0.0-1.0):
- harmful: Content that could cause physical/psychological harm
- inappropriate: Adult, explicit, or offensive content
- sensitive: Political, religious, or controversial topics

Output JSON only:
{{
    "harmful": {{"detected": bool, "confidence": float, "reason": str}},
    "inappropriate": {{"detected": bool, "confidence": float, "reason": str}},
    "sensitive": {{"detected": bool, "confidence": float, "reason": str}}
}}
"""


def pattern_based_filter(text: str) -> Dict[str, Dict[str, Any]]:
    """Fast pattern-based content filtering."""
    results = {
        "harmful": {"detected": False, "confidence": 0.0, "matches": []},
        "inappropriate": {"detected": False, "confidence": 0.0, "matches": []},
        "sensitive": {"detected": False, "confidence": 0.0, "matches": []},
    }

    for pattern in HARMFUL_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            results["harmful"]["detected"] = True
            results["harmful"]["confidence"] = 0.8
            results["harmful"]["matches"].extend(matches)

    for pattern in INAPPROPRIATE_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            results["inappropriate"]["detected"] = True
            results["inappropriate"]["confidence"] = 0.7
            results["inappropriate"]["matches"].extend(matches)

    for pattern in SENSITIVE_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            results["sensitive"]["detected"] = True
            results["sensitive"]["confidence"] = 0.6
            results["sensitive"]["matches"].extend(matches)

    return results


async def llm_content_analysis(text: str) -> Dict[str, Dict[str, Any]]:
    """LLM-based content analysis for nuanced detection."""
    try:
        prompt = ChatPromptTemplate.from_template(CONTENT_ANALYSIS_PROMPT)
        chain = prompt | get_content_llm() | JsonOutputParser()
        result = await chain.ainvoke({"response": text})
        return result
    except Exception as e:
        logger.error("LLM content analysis failed", error=str(e))
        return {}


async def content_filter_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter LLM response content based on moderation mode.
    """
    metrics = get_guardian_metrics()
    start_time = time.perf_counter()

    llm_response = state.get("llm_response", "")
    moderation_mode = state.get("moderation_mode", settings.DEFAULT_MODERATION_MODE)
    rules = MODERATION_RULES.get(moderation_mode, MODERATION_RULES["moderate"])

    if not llm_response or moderation_mode == "raw":
        return {
            **state,
            "content_filtered": False,
            "content_warnings": [],
            "content_blocked": False,
        }

    # Pattern-based filtering first (fast)
    pattern_results = pattern_based_filter(llm_response)

    # LLM analysis for edge cases (if patterns didn't catch anything)
    content_issues = []
    blocked = False
    warnings = []

    for category, detection in pattern_results.items():
        if detection["detected"]:
            action = rules.get(category, "allow")
            metrics.record_content_filtered(category, action)

            if action == "block":
                blocked = True
                content_issues.append(f"{category}: blocked")
            elif action == "warn":
                warnings.append(f"{category}: flagged for review")

    latency_ms = (time.perf_counter() - start_time) * 1000
    metrics.record_latency("content_filter", latency_ms)

    logger.info(
        "Content filter complete",
        mode=moderation_mode,
        blocked=blocked,
        warnings=len(warnings),
        latency_ms=round(latency_ms, 2),
    )

    return {
        **state,
        "content_filtered": blocked or len(warnings) > 0,
        "content_warnings": warnings,
        "content_blocked": blocked,
        "content_block_reason": "; ".join(content_issues) if blocked else None,
    }
