"""
Disclaimer Injector Node.

Automatically detects medical/financial/legal advice and injects
appropriate disclaimers to reduce liability.
"""

import re
import time
from typing import Dict, Any, Optional
import structlog

from app.core.metrics import get_guardian_metrics

logger = structlog.get_logger()


class DisclaimerInjector:
    """Detects advice types and injects disclaimers."""

    # Keywords for detecting advice types
    MEDICAL_KEYWORDS = [
        "diagnos",
        "treatment",
        "medication",
        "symptom",
        "disease",
        "prescription",
        "medical",
        "health",
        "doctor",
        "therapy",
        "cure",
        "condition",
        "illness",
    ]

    FINANCIAL_KEYWORDS = [
        "invest",
        "stock",
        "trading",
        "financial advice",
        "portfolio",
        "tax",
        "return on investment",
        "roi",
        "dividend",
        "crypto",
        "bitcoin",
        "retirement",
        "savings",
    ]

    LEGAL_KEYWORDS = [
        "legal",
        "lawsuit",
        "contract",
        "attorney",
        "law",
        "court",
        "regulation",
        "compliance",
        "liability",
        "rights",
    ]

    # Disclaimers
    MEDICAL_DISCLAIMER = "\n\n⚠️ **Medical Disclaimer**: This information is for educational purposes only and is not medical advice. Please consult a licensed healthcare professional for medical concerns."

    FINANCIAL_DISCLAIMER = "\n\n⚠️ **Financial Disclaimer**: This is not financial advice. Consult a certified financial advisor before making investment decisions."

    LEGAL_DISCLAIMER = "\n\n⚠️ **Legal Disclaimer**: This is not legal advice. Consult a qualified attorney for legal matters."

    @classmethod
    def detect_advice_type(cls, text: str) -> Optional[str]:
        """Detect if text contains medical, financial, or legal advice."""
        lower_text = text.lower()

        # Count keyword matches
        medical_count = sum(1 for kw in cls.MEDICAL_KEYWORDS if kw in lower_text)
        financial_count = sum(1 for kw in cls.FINANCIAL_KEYWORDS if kw in lower_text)
        legal_count = sum(1 for kw in cls.LEGAL_KEYWORDS if kw in lower_text)

        # Threshold: at least 2 keywords to trigger disclaimer
        if medical_count >= 2:
            return "medical"
        elif financial_count >= 2:
            return "financial"
        elif legal_count >= 2:
            return "legal"

        return None

    @classmethod
    def inject_disclaimer(cls, text: str, advice_type: str) -> str:
        """Inject appropriate disclaimer into text."""
        disclaimers = {
            "medical": cls.MEDICAL_DISCLAIMER,
            "financial": cls.FINANCIAL_DISCLAIMER,
            "legal": cls.LEGAL_DISCLAIMER,
        }

        disclaimer = disclaimers.get(advice_type, "")
        return text + disclaimer


async def disclaimer_injector_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect advice type and inject appropriate disclaimers.
    """
    metrics = get_guardian_metrics()
    start_time = time.perf_counter()

    llm_response = state.get("llm_response", "")
    guardrails = state.get("guardrails") or {}

    # Check if auto_disclaimers is enabled
    if not guardrails.get("auto_disclaimers", False):
        return state

    if not llm_response:
        return state

    try:
        advice_type = DisclaimerInjector.detect_advice_type(llm_response)

        if advice_type:
            modified_response = DisclaimerInjector.inject_disclaimer(
                llm_response, advice_type
            )

            latency_ms = (time.perf_counter() - start_time) * 1000
            metrics.record_latency("disclaimer_injection", latency_ms)

            logger.info(
                "Disclaimer injected",
                advice_type=advice_type,
                latency_ms=round(latency_ms, 2),
            )

            return {
                **state,
                "llm_response": modified_response,
                "disclaimer_injected": True,
                "disclaimer_text": advice_type,
            }
        else:
            return {
                **state,
                "disclaimer_injected": False,
            }

    except Exception as e:
        logger.error("Disclaimer injection failed", error=str(e))
        return state
