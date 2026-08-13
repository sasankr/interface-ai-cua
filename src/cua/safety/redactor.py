"""
PII & Secret Redaction Engine
Strictly scrubs sensitive financial records, social security numbers, credentials,
and personal identifiers before persistence in artifacts, logs, or evidence dumps.
"""

import re
from typing import Any, Dict, List, Union


class RedactionEngine:
    # Regex patterns for regulated data
    PATTERNS = [
        # SSN patterns (e.g. 123-45-6789 or 123456789)
        (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
        # Credit / Debit Card numbers (13-16 digits with optional dashes/spaces)
        (re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"), "[REDACTED_CARD_NUMBER]"),
        # Bearer tokens and API keys
        (re.compile(r"(?i)\b(bearer|token|apikey|secret|pwd|password)\s*[:=]\s*([A-Za-z0-9_\-\.]{8,})"), r"\1=[REDACTED_SECRET]"),
        # Email addresses
        (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[REDACTED_EMAIL]"),
        # US Phone numbers
        (re.compile(r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b"), "[REDACTED_PHONE]")
    ]

    SENSITIVE_KEYS = {
        "password", "secret", "token", "ssn", "social_security_number",
        "pin", "cvv", "card_number", "auth_token", "api_key"
    }

    @classmethod
    def redact_text(cls, text: str) -> str:
        """Scrub known sensitive patterns from free-form string."""
        if not text or not isinstance(text, str):
            return text
        result = text
        for pattern, replacement in cls.PATTERNS:
            result = pattern.sub(replacement, result)
        return result

    @classmethod
    def redact_data(cls, data: Any) -> Any:
        """Recursively redact dictionaries, lists, and primitives."""
        if isinstance(data, dict):
            clean_dict = {}
            for k, v in data.items():
                if any(sens in k.lower() for sens in cls.SENSITIVE_KEYS):
                    clean_dict[k] = "[REDACTED_CONFIDENTIAL]"
                else:
                    clean_dict[k] = cls.redact_data(v)
            return clean_dict
        elif isinstance(data, list):
            return [cls.redact_data(item) for item in data]
        elif isinstance(data, str):
            return cls.redact_text(data)
        else:
            return data
