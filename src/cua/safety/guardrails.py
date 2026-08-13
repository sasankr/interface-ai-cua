"""
Safety Policy & Guardrail Enforcement Engine
Validates URL scopes, permitted operations, and risk thresholds prior to execution.
"""

from urllib.parse import urlparse
from typing import List, Optional
from cua.models.capability import ActionStep, ActionType, RiskLevel, SafetyPolicy
from cua.models.safety import SecurityProfile


class SecurityViolationError(Exception):
    """Raised when an automation action breaches active security guardrails."""
    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


class SafetyGuardrailEngine:
    def __init__(self, policy: Optional[SafetyPolicy] = None, profile: Optional[SecurityProfile] = None):
        self.policy = policy or SafetyPolicy()
        self.profile = profile or SecurityProfile()

    def validate_url(self, target_url: str) -> bool:
        """Ensure navigation is strictly within allowed domain bounds."""
        parsed = urlparse(target_url)
        hostname = parsed.hostname or ""
        port = str(parsed.port) if parsed.port else ""

        # Check allowed hosts / domains
        allowed = any(
            hostname == d or hostname.endswith("." + d) or d == "localhost" and hostname in ("127.0.0.1", "localhost")
            for d in self.policy.allowed_domains
        )
        
        if not allowed and self.policy.allowed_domains:
            raise SecurityViolationError(
                "DISALLOWED_DOMAIN",
                f"Attempted navigation to '{target_url}' is outside permitted domains: {self.policy.allowed_domains}"
            )

        # Check blocked URL patterns
        for blocked_pattern in self.profile.blocked_url_patterns:
            if blocked_pattern in parsed.path:
                raise SecurityViolationError(
                    "BLOCKED_URL_PATTERN",
                    f"URL path '{parsed.path}' matches restricted security blocklist pattern '{blocked_pattern}'."
                )

        return True

    def validate_step(self, step: ActionStep) -> bool:
        """Validate step action type and risk boundary."""
        if step.action_type not in self.policy.allowed_actions:
            raise SecurityViolationError(
                "FORBIDDEN_ACTION_TYPE",
                f"Action type '{step.action_type.value}' is prohibited under active safety policy."
            )

        if step.action_type == ActionType.NAVIGATE and step.value:
            self.validate_url(step.value)

        return True

    def evaluate_risk(self, step: ActionStep) -> RiskLevel:
        """Assign or check risk classification for an action."""
        if step.risk_level:
            return step.risk_level
        if step.action_type in (ActionType.CLICK, ActionType.FILL, ActionType.SELECT_OPTION):
            # Check if text implies mutation
            target_str = str(step.target.model_dump() if step.target else "")
            if any(term in target_str.lower() for term in ["delete", "submit", "transfer", "create", "override"]):
                return RiskLevel.IRREVERSIBLE_MUTATION
            return RiskLevel.SAFE_WRITE
        return RiskLevel.SAFE_READ
