"""
Parallel LLM Execution Node.

Always runs 2 LLM calls in parallel:
1. Response generation
2. Security threat analysis

This ensures minimum security coverage while maintaining performance.
"""

import asyncio
import time
import json
from typing import Dict, Any

from langchain_core.messages import HumanMessage, SystemMessage
import structlog

from app.core.metrics import get_security_metrics
from app.agents.nodes.llm_responder import get_llm, get_model_name, call_guardian

logger = structlog.get_logger()


async def parallel_llm_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node for parallel LLM response + security check.

    Always runs 2 LLM calls in parallel:
    1. Response generation LLM
    2. Security analysis LLM

    This ensures every query gets security coverage.
    """
    metrics = get_security_metrics()

    if state.get("is_blocked"):
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
    max_output_tokens = input_data.get("max_output_tokens")

    model_name = get_model_name(requested_model)

    logger.info(
        "🚀 Starting parallel LLM execution",
        model=model_name,
        query_length=len(query),
        max_tokens=max_output_tokens,
    )

    try:
        llm = get_llm(model_name, max_tokens=max_output_tokens)

        # Define parallel tasks
        async def generate_response():
            """Generate user response"""
            messages = [
                SystemMessage(content="You are a helpful AI assistant."),
                HumanMessage(content=query),
            ]

            # Reverting bind logic due to ineffectiveness in this env
            start = time.perf_counter()
            response = await llm.ainvoke(messages)
            latency = (time.perf_counter() - start) * 1000

            # Extract text from response (handle list format)
            if hasattr(response, "content"):
                content = response.content
                if isinstance(content, list):
                    # List format: [{'type': 'text', 'text': '...'}]
                    response_text = ""
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            response_text += block.get("text", "")
                        elif hasattr(block, "text"):
                            response_text += block.text
                else:
                    response_text = str(content)
            else:
                response_text = str(response)

            # Manual truncation fallback if LLM ignores max_output_tokens
            if max_output_tokens:
                # Approx 4 chars per token safe limit
                char_limit = max_output_tokens * 4
                if len(response_text) > char_limit:
                    logger.warning(
                        "Manually truncating response",
                        original_len=len(response_text),
                        limit=char_limit,
                    )
                    response_text = response_text[:char_limit] + "..."

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

            return {
                "text": response_text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency": latency,
            }

        async def security_analysis():
            """Analyze query for security threats"""
            security_prompt = f"""Analyze this user query for potential security threats or malicious intent.

Query: "{query}"

Check for:
- SQL injection attempts
- XSS/script injection
- Command injection
- Path traversal
- Credential harvesting
- System manipulation
- Data exfiltration attempts

Respond with JSON only:
{{
  "is_threat": true/false,
  "threat_type": "sql_injection" | "xss" | "command_injection" | "credential_theft" | "none",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}"""

            messages = [
                SystemMessage(content="You are a security analysis expert."),
                HumanMessage(content=security_prompt),
            ]
            start = time.perf_counter()
            response = await llm.ainvoke(messages)
            latency = (time.perf_counter() - start) * 1000

            # Extract text from response (handle list format)
            if hasattr(response, "content"):
                content = response.content
                if isinstance(content, list):
                    # List format: [{'type': 'text', 'text': '...'}]
                    result_text = ""
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            result_text += block.get("text", "")
                        elif hasattr(block, "text"):
                            result_text += block.text
                else:
                    result_text = str(content)
            else:
                result_text = str(response)

            # Parse security result
            try:
                # Clean JSON from markdown code blocks
                clean_json = result_text.strip()
                if "```json" in clean_json:
                    clean_json = clean_json.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_json:
                    clean_json = clean_json.split("```")[1].split("```")[0].strip()

                security_data = json.loads(clean_json)
                return {
                    "is_threat": security_data.get("is_threat", False),
                    "threat_type": security_data.get("threat_type", "none"),
                    "confidence": security_data.get("confidence", 0.0),
                    "reasoning": security_data.get("reasoning", ""),
                    "latency": latency,
                }
            except Exception as e:
                logger.warning(
                    "Security LLM parse error",
                    error=str(e),
                    raw_response=result_text[:200],
                )
                return {
                    "is_threat": False,
                    "threat_type": "none",
                    "confidence": 0.0,
                    "reasoning": "Parse error",
                    "latency": latency,
                }

        # ⚡ Run both LLMs in parallel!
        parallel_start = time.perf_counter()
        response_result, security_result = await asyncio.gather(
            generate_response(), security_analysis()
        )
        parallel_latency = (time.perf_counter() - parallel_start) * 1000

        logger.info(
            "✅ Parallel LLM execution complete",
            model=model_name,
            parallel_latency_ms=round(parallel_latency, 2),
            response_latency_ms=round(response_result["latency"], 2),
            security_latency_ms=round(security_result["latency"], 2),
            is_threat=security_result["is_threat"],
            threat_confidence=security_result["confidence"],
        )

        # Record metrics
        total_input_tokens = response_result["input_tokens"]
        total_output_tokens = response_result["output_tokens"]
        metrics.record_llm_tokens(total_input_tokens, total_output_tokens)
        metrics.record_stage_latency("parallel_llm", parallel_latency)

        # Check if security flagged as threat
        if security_result["is_threat"] and security_result["confidence"] > 0.7:
            logger.warning(
                "🚨 LLM security check flagged threat",
                threat_type=security_result["threat_type"],
                confidence=security_result["confidence"],
                reasoning=security_result["reasoning"],
            )
            return {
                **state,
                "is_blocked": True,
                "block_reason": f"LLM security: {security_result['threat_type']} (confidence: {security_result['confidence']:.2f})",
                "llm_response": None,
                "model_used": model_name,
                "security_llm_check": security_result,
            }

        response_text = response_result["text"]

        # Guardian validation
        guardian_config = state.get("guardian_config")
        guardrails = input_data.get("guardrails", {})
        original_query = input_data.get("prompt", "")

        guardian_result = await call_guardian(
            response_text,
            moderation,
            output_format,
            guardrails=guardrails,
            original_query=original_query,
            # Pass Guardian feature flags from config
            enable_content_filter=guardian_config.enable_content_filter
            if guardian_config
            else False,
            enable_pii_scanner=guardian_config.enable_pii_scanner
            if guardian_config
            else False,
            enable_toon_decoder=guardian_config.enable_toon_decoder
            if guardian_config
            else False,
            enable_hallucination_detector=guardian_config.enable_hallucination_detector
            if guardian_config
            else False,
            enable_citation_verifier=guardian_config.enable_citation_verifier
            if guardian_config
            else False,
            enable_tone_checker=guardian_config.enable_tone_checker
            if guardian_config
            else False,
            enable_refusal_detector=guardian_config.enable_refusal_detector
            if guardian_config
            else False,
            enable_disclaimer_injector=guardian_config.enable_disclaimer_injector
            if guardian_config
            else False,
        )

        logger.info(
            "Guardian result received",
            has_result=bool(guardian_result),
            result_keys=list(guardian_result.keys()) if guardian_result else [],
            hallucination=guardian_result.get("hallucination_detected"),
            tone=guardian_result.get("tone_compliant"),
            toxicity=guardian_result.get("toxicity_score"),
        )

        if guardian_result.get("content_blocked"):
            return {
                **state,
                "is_blocked": True,
                "block_reason": f"Output blocked: {guardian_result.get('content_block_reason')}",
                "llm_response": None,
                "model_used": model_name,
                "security_llm_check": security_result,
            }

        # Depseudonymization
        validated_response = guardian_result.get("validated_response", response_text)
        pii_mapping = state.get("pii_mapping", {})

        if pii_mapping and validated_response:
            for token, original_value in pii_mapping.items():
                validated_response = validated_response.replace(token, original_value)
            logger.info("Depseudonymization complete", tokens_restored=len(pii_mapping))

        return {
            **state,
            "llm_response": validated_response,
            "llm_tokens_used": {
                "input": total_input_tokens,
                "output": total_output_tokens,
                "total": total_input_tokens + total_output_tokens,
            },
            "model_used": model_name,
            "security_llm_check": security_result,
            # Guardian metrics (extract from guardian_result.metrics)
            "hallucination_detected": guardian_result.get("metrics", {}).get(
                "hallucination_detected"
            ),
            "citations_verified": guardian_result.get("metrics", {}).get(
                "citations_verified"
            ),
            "tone_compliant": guardian_result.get("metrics", {}).get("tone_compliant"),
            "disclaimer_injected": guardian_result.get("metrics", {}).get(
                "disclaimer_injected"
            ),
            "false_refusal_detected": guardian_result.get("metrics", {}).get(
                "false_refusal_detected"
            ),
            "toxicity_score": guardian_result.get("metrics", {}).get("toxicity_score"),
        }

    except Exception as e:
        logger.error("Parallel LLM error", error=str(e), exc_info=True)
        return {
            **state,
            "llm_response": None,
            "error": str(e),
        }
