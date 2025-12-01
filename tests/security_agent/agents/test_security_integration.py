"""
Integration tests for the enhanced security agent.
"""
import pytest
from unittest.mock import MagicMock, patch
from app.agents.state import AgentState
from app.agents.nodes.security import security_check


@pytest.mark.asyncio
class TestSecurityIntegration:
    """Integration tests for complete security flow."""
    
    @pytest.fixture
    def mock_llm(self):
        """Mock the LLM chain to avoid external calls."""
        with patch("app.agents.nodes.security.get_llm") as mock_get_llm:
            with patch("app.agents.nodes.security.ChatPromptTemplate") as mock_prompt:
                # Mock the chain execution
                mock_chain = MagicMock()
                # Setup async return value for ainvoke
                async def async_return(*args, **kwargs):
                    return {
                        "security_score": 0.1,
                        "is_blocked": False,
                        "reason": None
                    }
                mock_chain.ainvoke.side_effect = async_return
                
                # Mock get_llm to return something that works in the chain
                mock_llm_instance = MagicMock()
                mock_get_llm.return_value = mock_llm_instance
                
                yield mock_chain

    async def test_clean_input_passes(self):
        """Test that clean input passes all security checks."""
        state = AgentState(
            input={"prompt": "What is the weather today?"},
            security_score=0.0,
            is_blocked=False,
            block_reason=None,
            sanitized_input=None,
            sanitization_warnings=None,
            pii_detections=None,
            redacted_input=None,
            detected_threats=None,
            client_ip="192.168.1.1",
            user_agent="TestAgent"
        )
        
        # We need to mock the chain execution inside security_check
        with patch("langchain_core.prompts.ChatPromptTemplate.from_template") as mock_prompt:
            with patch("app.agents.nodes.security.get_llm") as mock_get_llm:
                with patch("langchain_core.output_parsers.JsonOutputParser") as mock_parser:
                    # Create a mock chain that returns what we want
                    mock_chain = MagicMock()
                    async def async_return(*args, **kwargs):
                        return {
                            "security_score": 0.1,
                            "is_blocked": False,
                            "reason": None
                        }
                    mock_chain.ainvoke.side_effect = async_return
                    
                    # Make the pipe operations return our mock chain
                    # prompt | get_llm() | parser -> chain
                    mock_prompt.return_value.__or__.return_value.__or__.return_value = mock_chain
                    
                    result = await security_check(state)
        
        assert result["is_blocked"] is False
        assert result["security_score"] < 0.85
        assert result["sanitized_input"] is not None
    
    async def test_sql_injection_blocked(self):
        """Test that SQL injection is detected and blocked."""
        state = AgentState(
            input={"prompt": "' UNION SELECT * FROM users --"},
            security_score=0.0,
            is_blocked=False,
            block_reason=None,
            sanitized_input=None,
            sanitization_warnings=None,
            pii_detections=None,
            redacted_input=None,
            detected_threats=None,
            client_ip="192.168.1.2",
            user_agent="TestAgent"
        )
        
        result = await security_check(state)
        
        assert result["is_blocked"] is True
        assert len(result["detected_threats"]) > 0
        assert any("sql" in t["threat_type"] for t in result["detected_threats"])
    
    async def test_xss_blocked(self):
        """Test that XSS is detected and blocked."""
        state = AgentState(
            input={"prompt": "<script>alert('xss')</script>"},
            security_score=0.0,
            is_blocked=False,
            block_reason=None,
            sanitized_input=None,
            sanitization_warnings=None,
            pii_detections=None,
            redacted_input=None,
            detected_threats=None,
            client_ip="192.168.1.3",
            user_agent="TestAgent"
        )
        
        result = await security_check(state)
        
        # Should be sanitized
        assert "<script>" not in result["sanitized_input"]
        # May or may not be blocked depending on LLM, but should detect threat
        assert len(result["detected_threats"]) > 0
    
    async def test_pii_redacted(self):
        """Test that PII is detected and redacted."""
        state = AgentState(
            input={"prompt": "My SSN is 123-45-6789 and email is test@example.com"},
            security_score=0.0,
            is_blocked=False,
            block_reason=None,
            sanitized_input=None,
            sanitization_warnings=None,
            pii_detections=None,
            redacted_input=None,
            detected_threats=None,
            client_ip="192.168.1.4",
            user_agent="TestAgent"
        )
        
        # Mock LLM to pass
        with patch("langchain_core.prompts.ChatPromptTemplate.from_template") as mock_prompt:
            with patch("app.agents.nodes.security.get_llm") as mock_get_llm:
                mock_chain = MagicMock()
                async def async_return(*args, **kwargs):
                    return {"security_score": 0.1, "is_blocked": False}
                mock_chain.ainvoke.side_effect = async_return
                
                # Mock get_llm to return something that works in the chain
                mock_llm_instance = MagicMock()
                mock_get_llm.return_value = mock_llm_instance
                
                # Mock the chain construction
                mock_prompt.return_value.__or__.return_value.__or__.return_value = mock_chain
                
                result = await security_check(state)
        
        assert len(result["pii_detections"]) > 0
        assert "123-45-6789" not in result["redacted_input"]
        assert "test@example.com" not in result["redacted_input"]
        assert "[SSN_REDACTED]" in result["redacted_input"]
        assert "[EMAIL_REDACTED]" in result["redacted_input"]
    
    async def test_sanitization_applied(self):
        """Test that input sanitization is applied."""
        state = AgentState(
            input={"prompt": "Hello\x00world"},
            security_score=0.0,
            is_blocked=False,
            block_reason=None,
            sanitized_input=None,
            sanitization_warnings=None,
            pii_detections=None,
            redacted_input=None,
            detected_threats=None,
            client_ip="192.168.1.5",
            user_agent="TestAgent"
        )
        
        # Mock LLM to pass
        with patch("langchain_core.prompts.ChatPromptTemplate.from_template") as mock_prompt:
            with patch("app.agents.nodes.security.get_llm") as mock_get_llm:
                mock_chain = MagicMock()
                async def async_return(*args, **kwargs):
                    return {"security_score": 0.1, "is_blocked": False}
                mock_chain.ainvoke.side_effect = async_return
                
                # Mock get_llm to return something that works in the chain
                mock_llm_instance = MagicMock()
                mock_get_llm.return_value = mock_llm_instance
                
                # Mock the chain construction
                mock_prompt.return_value.__or__.return_value.__or__.return_value = mock_chain
                
                result = await security_check(state)
        
        assert "\x00" not in result["sanitized_input"]
        assert len(result["sanitization_warnings"]) > 0
    
    async def test_multiple_threats(self):
        """Test detection of multiple threat types."""
        state = AgentState(
            input={"prompt": "<script>alert('xss')</script>' OR '1'='1"},
            security_score=0.0,
            is_blocked=False,
            block_reason=None,
            sanitized_input=None,
            sanitization_warnings=None,
            pii_detections=None,
            redacted_input=None,
            detected_threats=None,
            client_ip="192.168.1.6",
            user_agent="TestAgent"
        )
        
        result = await security_check(state)
        
        assert result["is_blocked"] is True
        threat_types = [t["threat_type"] for t in result["detected_threats"]]
        assert len(set(threat_types)) >= 2  # At least 2 different threat types
    
    async def test_error_handling_fails_safe(self):
        """Test that errors result in blocking (fail-safe)."""
        # Valid state
        state = AgentState(
            input={"prompt": "Something that causes error"},
            security_score=0.0,
            is_blocked=False,
            block_reason=None,
            sanitized_input=None,
            sanitization_warnings=None,
            pii_detections=None,
            redacted_input=None,
            detected_threats=None,
            client_ip="192.168.1.8",
            user_agent="TestAgent"
        )
        
        # Mock get_settings to raise an exception
        with patch("app.agents.nodes.security.get_settings") as mock_settings:
            mock_settings.side_effect = Exception("Simulated unexpected error")
            
            result = await security_check(state)
            
            # Should fail safe by blocking
            assert result["is_blocked"] is True
            assert "fail" in result["block_reason"].lower() or "error" in result["block_reason"].lower()
