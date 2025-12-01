"""
On-premise input/output sanitization module.

This module handles sanitization without external API calls for performance and reliability.
"""
import re
import html
import unicodedata
from typing import Dict, Any, List, Tuple
import bleach
import structlog

logger = structlog.get_logger()


class InputSanitizer:
    """Sanitizes user input to prevent various injection attacks."""
    
    # Allowed HTML tags for output sanitization (very restrictive)
    ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u']
    ALLOWED_ATTRIBUTES = {}
    
    # Dangerous patterns
    NULL_BYTE_PATTERN = re.compile(r'\x00')
    PATH_TRAVERSAL_PATTERN = re.compile(r'\.\.[/\\]')
    
    @staticmethod
    def sanitize_input(text: str) -> Tuple[str, List[str]]:
        """
        Sanitize input text.
        
        Args:
            text: Raw input text
            
        Returns:
            Tuple of (sanitized_text, list_of_warnings)
        """
        if not isinstance(text, str):
            text = str(text)
        
        warnings = []
        original_text = text
        
        # 1. Unicode normalization to prevent bypass attempts
        text = unicodedata.normalize('NFKC', text)
        
        # 2. Remove null bytes
        if InputSanitizer.NULL_BYTE_PATTERN.search(text):
            warnings.append("Null bytes detected and removed")
            text = InputSanitizer.NULL_BYTE_PATTERN.sub('', text)
        
        # 3. Check for path traversal attempts
        if InputSanitizer.PATH_TRAVERSAL_PATTERN.search(text):
            warnings.append("Path traversal pattern detected")
        
        # 4. HTML escape for basic XSS prevention
        text = html.escape(text)
        
        # 5. Trim excessive whitespace
        text = ' '.join(text.split())
        
        # 6. Limit length (prevent DoS)
        max_length = 10000
        if len(text) > max_length:
            warnings.append(f"Input truncated from {len(text)} to {max_length} characters")
            text = text[:max_length]
        
        if text != original_text:
            logger.info("Input sanitized", warnings=warnings)
        
        return text, warnings
    
    @staticmethod
    def sanitize_output(text: str) -> str:
        """
        Sanitize output text to prevent XSS in responses.
        
        Args:
            text: Raw output text
            
        Returns:
            Sanitized output text
        """
        if not isinstance(text, str):
            text = str(text)
        
        # Use bleach to sanitize HTML
        sanitized = bleach.clean(
            text,
            tags=InputSanitizer.ALLOWED_TAGS,
            attributes=InputSanitizer.ALLOWED_ATTRIBUTES,
            strip=True
        )
        
        return sanitized


class PIIRedactor:
    """Detects and redacts Personally Identifiable Information (PII)."""
    
    # Regex patterns for common PII
    SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
    SSN_PATTERN_ALT = re.compile(r'\b\d{9}\b')
    
    # Credit card patterns (basic Luhn algorithm not implemented for simplicity)
    CC_PATTERN = re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b')
    
    # Email pattern
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    
    # Phone number patterns (US format)
    PHONE_PATTERN = re.compile(r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b')
    
    # API keys and tokens (common patterns)
    API_KEY_PATTERN = re.compile(r'\b[A-Za-z0-9_-]{32,}\b')
    SECRET_KEYWORDS = ['password', 'secret', 'api_key', 'token', 'private_key', 'credential']
    
    @staticmethod
    def detect_and_redact_pii(text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Detect and redact PII from text.
        
        Args:
            text: Input text
            
        Returns:
            Tuple of (redacted_text, list_of_detections)
        """
        if not isinstance(text, str):
            text = str(text)
        
        detections = []
        redacted_text = text
        
        # 1. Redact SSN
        matches = PIIRedactor.SSN_PATTERN.findall(text)
        if matches:
            detections.append({"type": "SSN", "count": len(matches)})
            redacted_text = PIIRedactor.SSN_PATTERN.sub('[SSN_REDACTED]', redacted_text)
        
        # 2. Redact credit cards
        matches = PIIRedactor.CC_PATTERN.findall(text)
        if matches:
            detections.append({"type": "CREDIT_CARD", "count": len(matches)})
            redacted_text = PIIRedactor.CC_PATTERN.sub('[CC_REDACTED]', redacted_text)
        
        # 3. Redact emails
        matches = PIIRedactor.EMAIL_PATTERN.findall(text)
        if matches:
            detections.append({"type": "EMAIL", "count": len(matches)})
            redacted_text = PIIRedactor.EMAIL_PATTERN.sub('[EMAIL_REDACTED]', redacted_text)
        
        # 4. Redact phone numbers
        matches = PIIRedactor.PHONE_PATTERN.findall(text)
        if matches:
            detections.append({"type": "PHONE", "count": len(matches)})
            redacted_text = PIIRedactor.PHONE_PATTERN.sub('[PHONE_REDACTED]', redacted_text)
        
        # 5. Check for sensitive keywords
        lower_text = text.lower()
        for keyword in PIIRedactor.SECRET_KEYWORDS:
            if keyword in lower_text:
                detections.append({"type": "SENSITIVE_KEYWORD", "keyword": keyword})
        
        if detections:
            logger.warning("PII detected and redacted", detections=detections)
        
        return redacted_text, detections
