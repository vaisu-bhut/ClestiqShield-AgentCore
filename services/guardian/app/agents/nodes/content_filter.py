"""
Content Filter Node.

Filters LLM output for harmful, inappropriate, or sensitive content
based on moderation mode.
"""

import re
import time
from typing import Dict, Any

# from langchain_google_genai import ChatGoogleGenerativeAI - Moved to get_content_llm
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
        from langchain_google_genai import ChatGoogleGenerativeAI

        settings = get_settings()
        _content_llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0,
        )
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

    # Guardrails for toxicity threshold
    guardrails = state.get("guardrails") or {}
    toxicity_threshold = guardrails.get("toxicity_threshold", 0.7)

    # LLM-based toxicity scoring (NEW)
    toxicity_score = 0.0
    toxicity_details = {}

    if any(detection["detected"] for detection in pattern_results.values()):
        # Use LLM for precise toxicity scoring
        try:
            toxicity_result = await llm_toxicity_scoring(llm_response)
            toxicity_score = toxicity_result.get("toxicity_score", 0.0)
            toxicity_details = toxicity_result
        except Exception as e:
            logger.error("LLM toxicity scoring failed", error=str(e))
            # Fallback to pattern-based confidence
            max_confidence = max(
                (d.get("confidence", 0.0) for d in pattern_results.values())
            )
            toxicity_score = max_confidence

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

    # Block if toxicity score exceeds threshold
    if toxicity_score >= toxicity_threshold:
        blocked = True
        content_issues.append(
            f"toxicity score {toxicity_score:.2f} exceeds threshold {toxicity_threshold}"
        )

    latency_ms = (time.perf_counter() - start_time) * 1000
    metrics.record_latency("content_filter", latency_ms)

    logger.info(
        "Content filter complete",
        mode=moderation_mode,
        blocked=blocked,
        warnings=len(warnings),
        toxicity_score=toxicity_score,
        latency_ms=round(latency_ms, 2),
    )

    return {
        **state,
        "content_filtered": blocked or len(warnings) > 0,
        "content_warnings": warnings,
        "content_blocked": blocked,
        "content_block_reason": "; ".join(content_issues) if blocked else None,
        "toxicity_score": toxicity_score if toxicity_score > 0 else None,
        "toxicity_details": toxicity_details if toxicity_details else None,
    }


async def llm_toxicity_scoring(text: str) -> Dict[str, Any]:
    """Use LLM to score toxicity on a 0.0-1.0 scale."""
    try:
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

        prompt = ChatPromptTemplate.from_template(TOXICITY_PROMPT)
        chain = prompt | get_content_llm() | JsonOutputParser()
        result = await chain.ainvoke({"text": text})
        return result
    except Exception as e:
        logger.error("LLM toxicity scoring error", error=str(e))
        return {"toxicity_score": 0.0, "categories": []}
