"""
On-premise threat detection module.

This module detects common attack patterns without LLM calls for fast, local security checks.
"""
import re
from typing import Dict, Any, List
from enum import Enum
import structlog

logger = structlog.get_logger()


class ThreatType(Enum):
    """Types of security threats."""
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    COMMAND_INJECTION = "command_injection"
    PATH_TRAVERSAL = "path_traversal"
    LDAP_INJECTION = "ldap_injection"
    XML_INJECTION = "xml_injection"


class ThreatDetector:
    """Detects various injection and attack patterns."""
    
    # SQL Injection patterns
    SQL_PATTERNS = [
        re.compile(r"(\bunion\b.*\bselect\b)", re.IGNORECASE),
        re.compile(r"(\bselect\b.*\bfrom\b)", re.IGNORECASE),
        re.compile(r"(\binsert\b.*\binto\b)", re.IGNORECASE),
        re.compile(r"(\bupdate\b.*\bset\b)", re.IGNORECASE),
        re.compile(r"(\bdelete\b.*\bfrom\b)", re.IGNORECASE),
        re.compile(r"(\bdrop\b.*\btable\b)", re.IGNORECASE),
        re.compile(r"(\bexec\b.*\()", re.IGNORECASE),
        re.compile(r"(\bexecute\b.*\()", re.IGNORECASE),
        re.compile(r"(--|\#|\/\*)", re.IGNORECASE),  # SQL comments
        re.compile(r"(\bor\b.*=.*)", re.IGNORECASE),
        re.compile(r"(\band\b.*=.*)", re.IGNORECASE),
        re.compile(r"('.*\bor\b.*'.*=.*')", re.IGNORECASE),
        re.compile(r"(1\s*=\s*1)", re.IGNORECASE),
        re.compile(r"(sleep\(|benchmark\(|waitfor\s+delay)", re.IGNORECASE),
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        re.compile(r"<script[^>]*>", re.IGNORECASE),
        re.compile(r"</script>", re.IGNORECASE),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),  # Event handlers like onclick, onerror
        re.compile(r"<iframe[^>]*>", re.IGNORECASE),
        re.compile(r"<object[^>]*>", re.IGNORECASE),
        re.compile(r"<embed[^>]*>", re.IGNORECASE),
        re.compile(r"<img[^>]*src", re.IGNORECASE),
        re.compile(r"eval\s*\(", re.IGNORECASE),
        re.compile(r"expression\s*\(", re.IGNORECASE),
        re.compile(r"vbscript:", re.IGNORECASE),
        re.compile(r"data:text/html", re.IGNORECASE),
    ]
    
    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        re.compile(r"[;&|`$]"),  # Shell metacharacters
        re.compile(r"\$\(.*\)"),  # Command substitution
        re.compile(r"`.*`"),  # Backtick command execution
        re.compile(r"&&|\|\|"),  # Command chaining
        re.compile(r">\s*\/|<\s*\/"),  # File redirection
        re.compile(r"\bcat\b|\bls\b|\bwhoami\b|\bpwd\b", re.IGNORECASE),
        re.compile(r"\bcurl\b|\bwget\b|\bnc\b|\bnetcat\b", re.IGNORECASE),
        re.compile(r"\bchmod\b|\bchown\b|\brm\b", re.IGNORECASE),
    ]
    
    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        re.compile(r"\.\.\/"),
        re.compile(r"\.\.\\"),
        re.compile(r"%2e%2e%2f", re.IGNORECASE),
        re.compile(r"%2e%2e\/", re.IGNORECASE),
        re.compile(r"\.\.%2f", re.IGNORECASE),
    ]
    
    # LDAP injection patterns
    LDAP_INJECTION_PATTERNS = [
        re.compile(r"[*()|\&]"),
        re.compile(r"\*\)|\(\&"),
    ]
    
    # XML injection patterns
    XML_INJECTION_PATTERNS = [
        re.compile(r"<!ENTITY", re.IGNORECASE),
        re.compile(r"<!DOCTYPE", re.IGNORECASE),
        re.compile(r"SYSTEM|PUBLIC", re.IGNORECASE),
    ]
    
    @staticmethod
    def detect_sql_injection(text: str) -> Dict[str, Any]:
        """
        Detect SQL injection attempts.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Detection result with threat details
        """
        matches = []
        for pattern in ThreatDetector.SQL_PATTERNS:
            found = pattern.findall(text)
            if found:
                matches.extend(found)
        
        is_detected = len(matches) > 0
        
        if is_detected:
            logger.warning("SQL injection pattern detected", matches=matches[:3])
        
        return {
            "detected": is_detected,
            "threat_type": ThreatType.SQL_INJECTION.value,
            "confidence": min(len(matches) * 0.3, 1.0),  # More matches = higher confidence
            "matches": matches[:5],  # Limit to first 5 matches
        }
    
    @staticmethod
    def detect_xss(text: str) -> Dict[str, Any]:
        """
        Detect XSS (Cross-Site Scripting) attempts.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Detection result with threat details
        """
        matches = []
        for pattern in ThreatDetector.XSS_PATTERNS:
            found = pattern.findall(text)
            if found:
                matches.extend(found)
        
        is_detected = len(matches) > 0
        
        if is_detected:
            logger.warning("XSS pattern detected", matches=matches[:3])
        
        return {
            "detected": is_detected,
            "threat_type": ThreatType.XSS.value,
            "confidence": min(len(matches) * 0.3, 1.0),
            "matches": matches[:5],
        }
    
    @staticmethod
    def detect_command_injection(text: str) -> Dict[str, Any]:
        """
        Detect command injection attempts.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Detection result with threat details
        """
        matches = []
        for pattern in ThreatDetector.COMMAND_INJECTION_PATTERNS:
            found = pattern.findall(text)
            if found:
                matches.extend(found)
        
        is_detected = len(matches) > 0
        
        if is_detected:
            logger.warning("Command injection pattern detected", matches=matches[:3])
        
        return {
            "detected": is_detected,
            "threat_type": ThreatType.COMMAND_INJECTION.value,
            "confidence": min(len(matches) * 0.3, 1.0),
            "matches": matches[:5],
        }
    
    @staticmethod
    def detect_path_traversal(text: str) -> Dict[str, Any]:
        """
        Detect path traversal attempts.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Detection result with threat details
        """
        matches = []
        for pattern in ThreatDetector.PATH_TRAVERSAL_PATTERNS:
            found = pattern.findall(text)
            if found:
                matches.extend(found)
        
        is_detected = len(matches) > 0
        
        if is_detected:
            logger.warning("Path traversal pattern detected", matches=matches[:3])
        
        return {
            "detected": is_detected,
            "threat_type": ThreatType.PATH_TRAVERSAL.value,
            "confidence": min(len(matches) * 0.4, 1.0),
            "matches": matches[:5],
        }
    
    @staticmethod
    def detect_all_threats(text: str) -> List[Dict[str, Any]]:
        """
        Run all threat detection checks.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of detected threats
        """
        threats = []
        
        # Run all detectors
        sql_result = ThreatDetector.detect_sql_injection(text)
        if sql_result["detected"]:
            threats.append(sql_result)
        
        xss_result = ThreatDetector.detect_xss(text)
        if xss_result["detected"]:
            threats.append(xss_result)
        
        command_result = ThreatDetector.detect_command_injection(text)
        if command_result["detected"]:
            threats.append(command_result)
        
        path_result = ThreatDetector.detect_path_traversal(text)
        if path_result["detected"]:
            threats.append(path_result)
        
        return threats
