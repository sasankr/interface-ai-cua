"""
Unit tests for safety guardrails and PII redaction.
"""

import pytest
from cua.safety.redactor import RedactionEngine
from cua.safety.guardrails import SafetyGuardrailEngine, SecurityViolationError
from cua.models.capability import SafetyPolicy, ActionStep, ActionType


def test_pii_redaction_text():
    # SSN Redaction
    text_ssn = "Customer SSN is 123-45-6789 on record."
    assert RedactionEngine.redact_text(text_ssn) == "Customer SSN is [REDACTED_SSN] on record."

    # Email Redaction
    text_email = "Contact user at john.doe@bankcorp.org for confirmation."
    assert "[REDACTED_EMAIL]" in RedactionEngine.redact_text(text_email)

    # Phone Redaction
    text_phone = "Calling (555) 234-8901 now."
    assert "[REDACTED_PHONE]" in RedactionEngine.redact_text(text_phone)


def test_pii_redaction_dict():
    payload = {
        "user": "Alice",
        "ssn": "987-65-4321",
        "password": "SuperSecretPassword123",
        "nested": {
            "account_token": "bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        }
    }
    redacted = RedactionEngine.redact_data(payload)
    assert redacted["ssn"] == "[REDACTED_CONFIDENTIAL]"
    assert redacted["password"] == "[REDACTED_CONFIDENTIAL]"


def test_guardrails_domain_allowlist():
    engine = SafetyGuardrailEngine(policy=SafetyPolicy(allowed_domains=["127.0.0.1", "localhost"]))
    
    # Valid domain
    assert engine.validate_url("http://127.0.0.1:8000/portal/member_search") is True
    
    # Prohibited domain
    with pytest.raises(SecurityViolationError) as exc_info:
        engine.validate_url("https://malicious-external-site.com/steal")
    assert "DISALLOWED_DOMAIN" in str(exc_info.value)
