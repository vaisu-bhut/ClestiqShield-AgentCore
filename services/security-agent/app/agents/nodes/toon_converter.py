"""
TOON (Text-Only Object Notation) Converter Module.

Converts verbose JSON queries to a more compact TOON format to save tokens
when sending to LLM platforms. TOON reduces token usage by:
- Removing unnecessary whitespace
- Using compact key notation
- Stripping redundant structure where possible

The conversion is reversible for responses.
"""
import json
import re
from typing import Dict, Any, Tuple, Optional
import structlog

logger = structlog.get_logger()

# Approximate tokens per character (rough estimate: 1 token ≈ 4 characters)
CHARS_PER_TOKEN = 4


class ToonConverter:
    """Converts between JSON and TOON (compact text) format."""
    
    # Common key abbreviations for further compression
    KEY_ABBREVIATIONS = {
        "prompt": "p",
        "message": "m",
        "content": "c",
        "role": "r",
        "system": "s",
        "user": "u",
        "assistant": "a",
        "temperature": "t",
        "max_tokens": "mt",
        "messages": "ms",
        "context": "ctx",
        "history": "h",
        "response": "res",
        "request": "req",
    }
    
    # Reverse mapping for decompression
    KEY_EXPANSIONS = {v: k for k, v in KEY_ABBREVIATIONS.items()}
    
    @classmethod
    def to_toon(cls, data: Any, use_abbreviations: bool = True) -> str:
        """
        Convert data to TOON format.
        
        Args:
            data: Any JSON-serializable data
            use_abbreviations: Whether to use key abbreviations
            
        Returns:
            Compact TOON string
        """
        if isinstance(data, str):
            # If already a string, compact it
            try:
                parsed = json.loads(data)
                data = parsed
            except json.JSONDecodeError:
                # Not JSON, return as-is but trimmed
                return data.strip()
        
        def compact_value(v: Any) -> str:
            """Recursively compact a value."""
            if v is None:
                return "~"  # Compact null
            elif isinstance(v, bool):
                return "T" if v else "F"  # Compact booleans
            elif isinstance(v, str):
                # Escape special chars and wrap in minimal quotes
                escaped = v.replace("\\", "\\\\").replace('"', '\\"')
                return f'"{escaped}"'
            elif isinstance(v, (int, float)):
                return str(v)
            elif isinstance(v, list):
                items = ",".join(compact_value(item) for item in v)
                return f"[{items}]"
            elif isinstance(v, dict):
                pairs = []
                for key, val in v.items():
                    # Abbreviate key if enabled
                    if use_abbreviations and key in cls.KEY_ABBREVIATIONS:
                        key = cls.KEY_ABBREVIATIONS[key]
                    pairs.append(f"{key}:{compact_value(val)}")
                return "{" + ",".join(pairs) + "}"
            else:
                return str(v)
        
        return compact_value(data)
    
    @classmethod
    def from_toon(cls, toon_str: str, expand_abbreviations: bool = True) -> Any:
        """
        Convert TOON format back to Python data.
        
        Args:
            toon_str: TOON string
            expand_abbreviations: Whether to expand abbreviated keys
            
        Returns:
            Python data structure
        """
        # Replace TOON-specific tokens back to JSON
        json_str = toon_str
        json_str = re.sub(r'(?<![\\])~', 'null', json_str)  # ~ -> null
        json_str = re.sub(r'(?<![a-zA-Z])T(?![a-zA-Z])', 'true', json_str)  # T -> true
        json_str = re.sub(r'(?<![a-zA-Z])F(?![a-zA-Z])', 'false', json_str)  # F -> false
        
        # Add quotes around unquoted keys
        json_str = re.sub(r'([{,])(\w+):', r'\1"\2":', json_str)
        
        try:
            data = json.loads(json_str)
            
            if expand_abbreviations and isinstance(data, dict):
                data = cls._expand_keys(data)
            
            return data
        except json.JSONDecodeError as e:
            logger.warning("TOON parsing failed, returning raw string", error=str(e))
            return toon_str
    
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
    def convert_with_metrics(cls, data: Any) -> Tuple[str, int, Dict[str, Any]]:
        """
        Convert to TOON and calculate token savings.
        
        Args:
            data: Input data to convert
            
        Returns:
            Tuple of (toon_string, tokens_saved, conversion_metrics)
        """
        # Calculate original size
        if isinstance(data, str):
            original_str = data
        else:
            original_str = json.dumps(data, separators=(',', ':'))
        
        original_chars = len(original_str)
        original_tokens = original_chars // CHARS_PER_TOKEN
        
        # Convert to TOON
        toon_str = cls.to_toon(data)
        toon_chars = len(toon_str)
        toon_tokens = toon_chars // CHARS_PER_TOKEN
        
        # Calculate savings
        chars_saved = original_chars - toon_chars
        tokens_saved = max(0, original_tokens - toon_tokens)
        
        compression_ratio = (1 - (toon_chars / original_chars)) * 100 if original_chars > 0 else 0
        
        metrics = {
            "original_chars": original_chars,
            "toon_chars": toon_chars,
            "chars_saved": chars_saved,
            "original_tokens_est": original_tokens,
            "toon_tokens_est": toon_tokens,
            "tokens_saved": tokens_saved,
            "compression_ratio_pct": round(compression_ratio, 2),
        }
        
        logger.debug(
            "TOON conversion complete",
            original_chars=original_chars,
            toon_chars=toon_chars,
            tokens_saved=tokens_saved,
            compression_pct=round(compression_ratio, 2)
        )
        
        return toon_str, tokens_saved, metrics


async def toon_conversion_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node that converts the sanitized/redacted input to TOON format.
    
    Args:
        state: Agent state containing redacted_input or sanitized_input
        
    Returns:
        Updated state with toon_query and token_savings
    """
    from app.core.metrics import get_security_metrics, track_latency
    import time
    
    # Get the cleanest available input
    clean_input = (
        state.get("redacted_input") or 
        state.get("sanitized_input") or 
        (state.get("input") or {}).get("prompt", "")
    )
    
    if not clean_input:
        return {
            **state,
            "toon_query": None,
            "token_savings": 0,
        }
    
    start_time = time.perf_counter()
    
    # Convert to TOON
    toon_str, tokens_saved, conversion_metrics = ToonConverter.convert_with_metrics(clean_input)
    
    latency_ms = (time.perf_counter() - start_time) * 1000
    
    # Record metrics
    metrics = get_security_metrics()
    metrics.record_tokens_saved(tokens_saved)
    metrics.record_stage_latency("toon_conversion", latency_ms)
    
    # Update metrics data if present
    metrics_data = state.get("metrics_data") or {}
    metrics_data["toon_conversion"] = conversion_metrics
    metrics_data["latencies_ms"] = metrics_data.get("latencies_ms", {})
    metrics_data["latencies_ms"]["toon_conversion"] = round(latency_ms, 2)
    
    logger.info(
        "TOON conversion complete",
        tokens_saved=tokens_saved,
        compression_pct=conversion_metrics["compression_ratio_pct"]
    )
    
    return {
        **state,
        "toon_query": toon_str,
        "token_savings": tokens_saved,
        "metrics_data": metrics_data,
    }
