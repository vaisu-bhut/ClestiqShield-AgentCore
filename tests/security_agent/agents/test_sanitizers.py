"""
Unit tests for sanitization module.
"""
import pytest
from app.agents.nodes.sanitizers import InputSanitizer, PIIRedactor


class TestInputSanitizer:
    """Test cases for InputSanitizer."""
    
    def test_sanitize_clean_input(self):
        """Test sanitization of clean input."""
        text = "This is a normal query about weather"
        sanitized, warnings = InputSanitizer.sanitize_input(text)
        
        assert sanitized == text
        assert len(warnings) == 0
    
    def test_sanitize_null_bytes(self):
        """Test null byte removal."""
        text = "SELECT * FROM users\x00WHERE id=1"
        sanitized, warnings = InputSanitizer.sanitize_input(text)
        
        assert "\x00" not in sanitized
        assert "Null bytes detected and removed" in warnings
    
    def test_sanitize_path_traversal(self):
        """Test path traversal detection."""
        text = "../../etc/passwd"
        sanitized, warnings = InputSanitizer.sanitize_input(text)
        
        assert any("Path traversal" in w for w in warnings)
    
    def test_sanitize_html_escape(self):
        """Test HTML escaping."""
        text = "<script>alert('xss')</script>"
        sanitized, warnings = InputSanitizer.sanitize_input(text)
        
        assert "&lt;script&gt;" in sanitized
        assert "<script>" not in sanitized
    
    def test_sanitize_excessive_whitespace(self):
        """Test whitespace trimming."""
        text = "Hello    world    with    spaces"
        sanitized, warnings = InputSanitizer.sanitize_input(text)
        
        assert "  " not in sanitized
        assert sanitized == "Hello world with spaces"
    
    def test_sanitize_length_limit(self):
        """Test length limiting."""
        text = "A" * 20000
        sanitized, warnings = InputSanitizer.sanitize_input(text)
        
        assert len(sanitized) == 10000
        assert any("truncated" in w.lower() for w in warnings)
    
    def test_sanitize_unicode_normalization(self):
        """Test unicode normalization."""
        # Unicode character that looks like quote
        text = "Hello" + "\u2019" + "world"
        sanitized, warnings = InputSanitizer.sanitize_input(text)
        
        assert sanitized is not None
    
    def test_sanitize_output_clean(self):
        """Test output sanitization with clean content."""
        text = "This is a normal response"
        sanitized = InputSanitizer.sanitize_output(text)
        
        assert sanitized == text
    
    def test_sanitize_output_script_tags(self):
        """Test output sanitization removes script tags."""
        text = "Hello <script>alert('xss')</script> world"
        sanitized = InputSanitizer.sanitize_output(text)
        
        assert "<script>" not in sanitized
        assert "Hello" in sanitized
        assert "world" in sanitized
    
    def test_sanitize_output_allowed_tags(self):
        """Test output sanitization keeps allowed tags."""
        text = "<p>Hello <strong>world</strong></p>"
        sanitized = InputSanitizer.sanitize_output(text)
        
        assert "<p>" in sanitized
        assert "<strong>" in sanitized


class TestPIIRedactor:
    """Test cases for PIIRedactor."""
    
    def test_detect_ssn(self):
        """Test SSN detection."""
        text = "My SSN is 123-45-6789"
        redacted, detections = PIIRedactor.detect_and_redact_pii(text)
        
        assert "[SSN_REDACTED]" in redacted
        assert "123-45-6789" not in redacted
        assert any(d["type"] == "SSN" for d in detections)
    
    def test_detect_credit_card(self):
        """Test credit card detection."""
        text = "My card is 4532-1234-5678-9010"
        redacted, detections = PIIRedactor.detect_and_redact_pii(text)
        
        assert "[CC_REDACTED]" in redacted
        assert "4532-1234-5678-9010" not in redacted
        assert any(d["type"] == "CREDIT_CARD" for d in detections)
    
    def test_detect_email(self):
        """Test email detection."""
        text = "Contact me at john.doe@example.com"
        redacted, detections = PIIRedactor.detect_and_redact_pii(text)
        
        assert "[EMAIL_REDACTED]" in redacted
        assert "john.doe@example.com" not in redacted
        assert any(d["type"] == "EMAIL" for d in detections)
    
    def test_detect_phone(self):
        """Test phone number detection."""
        text = "Call me at (555) 123-4567"
        redacted, detections = PIIRedactor.detect_and_redact_pii(text)
        
        assert "[PHONE_REDACTED]" in redacted
        assert any(d["type"] == "PHONE" for d in detections)
    
    def test_detect_sensitive_keywords(self):
        """Test sensitive keyword detection."""
        text = "Here is my password: secret123"
        redacted, detections = PIIRedactor.detect_and_redact_pii(text)
        
        assert any(d["type"] == "SENSITIVE_KEYWORD" for d in detections)
    
    def test_detect_multiple_pii(self):
        """Test detection of multiple PII types."""
        text = "My SSN is 123-45-6789 and email is test@example.com"
        redacted, detections = PIIRedactor.detect_and_redact_pii(text)
        
        assert len(detections) >= 2
        assert "123-45-6789" not in redacted
        assert "test@example.com" not in redacted
    
    def test_no_pii(self):
        """Test text without PII."""
        text = "This is a normal query about weather"
        redacted, detections = PIIRedactor.detect_and_redact_pii(text)
        
        assert redacted == text
        assert len(detections) == 0
