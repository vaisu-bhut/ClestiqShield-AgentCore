"""
TOON Decoder Node.

Converts TOON (compact format) responses back to JSON.
"""

import json
import re
import time
from typing import Dict, Any, Tuple
import structlog

from app.core.metrics import get_guardian_metrics

logger = structlog.get_logger()


class ToonDecoder:
    """Decodes TOON format back to JSON."""

    # Abbreviated key expansions
    KEY_EXPANSIONS = {
        "p": "prompt",
        "m": "message",
        "c": "content",
        "r": "role",
        "s": "system",
        "u": "user",
        "a": "assistant",
        "t": "temperature",
        "mt": "max_tokens",
        "ms": "messages",
        "ctx": "context",
        "h": "history",
        "res": "response",
        "req": "request",
    }

    @classmethod
    def is_toon(cls, text: str) -> bool:
        """Check if text appears to be in TOON format."""
        if not text or not isinstance(text, str):
            return False

        text = text.strip()

        # TOON indicators:
        # - Starts with { but has unquoted keys
        # - Contains ~ for null
        # - Contains single letter keys followed by :
        if text.startswith("{") and text.endswith("}"):
            # Check for unquoted keys pattern: key:value
            if re.search(r"[{,](\w+):", text):
                return True
            # Check for TOON null (~)
            if "~" in text:
                return True

        return False

    @classmethod
    def decode(cls, toon_str: str) -> Tuple[Any, bool]:
        """
        Decode TOON string to Python object.

        Returns:
            Tuple of (decoded_data, success)
        """
        if not toon_str:
            return toon_str, False

        try:
            # Replace TOON-specific tokens
            json_str = toon_str
            json_str = re.sub(r"(?<![\\])~", "null", json_str)  # ~ -> null
            json_str = re.sub(
                r"(?<![a-zA-Z])T(?![a-zA-Z])", "true", json_str
            )  # T -> true
            json_str = re.sub(
                r"(?<![a-zA-Z])F(?![a-zA-Z])", "false", json_str
            )  # F -> false

            # Add quotes around unquoted keys
            json_str = re.sub(r"([{,])(\w+):", r'\1"\2":', json_str)

            # Parse JSON
            data = json.loads(json_str)

            # Expand abbreviated keys
            data = cls._expand_keys(data)

            return data, True

        except json.JSONDecodeError as e:
            logger.warning("TOON decoding failed", error=str(e))
            return toon_str, False

    @classmethod
    def _expand_keys(cls, data: Any) -> Any:
        """Recursively expand abbreviated keys."""
        if isinstance(data, dict):
            return {
                cls.KEY_EXPANSIONS.get(k, k): cls._expand_keys(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [cls._expand_keys(item) for item in data]
        return data

    @classmethod
    def to_json_string(cls, data: Any) -> str:
        """Convert data to formatted JSON string."""
        if isinstance(data, str):
            return data
        return json.dumps(data, indent=2, ensure_ascii=False)


async def toon_decoder_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decode TOON response to JSON if applicable.
    """
    metrics = get_guardian_metrics()
    start_time = time.perf_counter()

    llm_response = state.get("llm_response", "")
    output_format = state.get("output_format", "json")

    if not llm_response:
        return state

    # Check if response is TOON and needs decoding
    is_toon = ToonDecoder.is_toon(llm_response)

    if is_toon and output_format == "json":
        decoded, success = ToonDecoder.decode(llm_response)
        metrics.record_toon_conversion(success)

        if success:
            # Convert to JSON string for response
            llm_response = ToonDecoder.to_json_string(decoded)
            logger.info("TOON decoded to JSON successfully")
        else:
            logger.warning("TOON decoding failed, returning original")

    latency_ms = (time.perf_counter() - start_time) * 1000
    logger.debug(
        "TOON decoder complete", is_toon=is_toon, latency_ms=round(latency_ms, 2)
    )

    return {
        **state,
        "llm_response": llm_response,
        "was_toon": is_toon,
    }
