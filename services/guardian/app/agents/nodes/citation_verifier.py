"""
Citation Verifier Node.

Detects and verifies citations (URLs, paper titles, sources) in LLM responses
to catch fabricated or generic references.
"""

import re
import time
from typing import Dict, Any, List
import structlog

from app.core.metrics import get_guardian_metrics

logger = structlog.get_logger()


class CitationVerifier:
    """Verifies citations in LLM responses."""

    # Citation patterns
    URL_PATTERN = re.compile(r"https?://[^\s]+")
    ARXIV_PATTERN = re.compile(r"arXiv:\d{4}\.\d{4,5}", re.IGNORECASE)
    DOI_PATTERN = re.compile(r"10\.\d{4,}/[^\s]+")
    PAPER_TITLE_PATTERN = re.compile(r'"([^"]{20,})"')  # Quoted titles

    # Suspicious patterns (generic/fake citations)
    SUSPICIOUS_DOMAINS = ["example.com", "test.com", "localhost", "dummy.com"]
    SUSPICIOUS_PHRASES = [
        "according to research",
        "studies show",
        "experts say",
        "it has been proven",
    ]

    @classmethod
    def extract_citations(cls, text: str) -> Dict[str, List[str]]:
        """Extract all citations from text."""
        citations = {
            "urls": cls.URL_PATTERN.findall(text),
            "arxiv": cls.ARXIV_PATTERN.findall(text),
            "dois": cls.DOI_PATTERN.findall(text),
            "paper_titles": [
                m.group(1) for m in cls.PAPER_TITLE_PATTERN.finditer(text)
            ],
        }
        return citations

    @classmethod
    def verify_citations(cls, text: str) -> tuple[bool, List[str]]:
        """
        Verify citations and detect potential fakes.

        Returns:
            (citations_verified, list_of_fake_citations)
        """
        fake_citations = []

        # Extract citations
        citations = cls.extract_citations(text)

        # Check URLs for suspicious domains
        for url in citations["urls"]:
            for suspicious_domain in cls.SUSPICIOUS_DOMAINS:
                if suspicious_domain in url.lower():
                    fake_citations.append(f"Suspicious URL: {url}")

        # Check for vague references without actual citations
        lower_text = text.lower()
        has_vague_claims = any(
            phrase in lower_text for phrase in cls.SUSPICIOUS_PHRASES
        )
        has_actual_citations = any(citations.values())

        if has_vague_claims and not has_actual_citations:
            fake_citations.append("Vague claims without citations")

        citations_verified = len(fake_citations) == 0
        return citations_verified, fake_citations


async def citation_verifier_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify citations in LLM response.
    """
    metrics = get_guardian_metrics()
    start_time = time.perf_counter()

    llm_response = state.get("llm_response", "")
    guardrails = state.get("guardrails") or {}

    # Check if citation verification is enabled
    if not guardrails.get("citation_verification", False):
        return state

    if not llm_response:
        return state

    try:
        citations_verified, fake_citations = CitationVerifier.verify_citations(
            llm_response
        )

        latency_ms = (time.perf_counter() - start_time) * 1000
        metrics.record_latency("citation_verification", latency_ms)

        logger.info(
            "Citation verification complete",
            verified=citations_verified,
            fake_count=len(fake_citations),
            latency_ms=round(latency_ms, 2),
        )

        return {
            **state,
            "citations_verified": citations_verified,
            "fake_citations": fake_citations if not citations_verified else None,
        }

    except Exception as e:
        logger.error("Citation verification failed", error=str(e))
        return state
