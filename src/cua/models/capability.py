"""
Capability Artifact Schema Models
Defines the typed, versioned, serializable contract for automated capabilities.
Decoupled from raw model traces to allow 100% deterministic production replay.
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field


class ParameterType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ENUM = "enum"


class RiskLevel(str, Enum):
    SAFE_READ = "SAFE_READ"                  # Idempotent, safe read-only action
    SAFE_WRITE = "SAFE_WRITE"                # Non-destructive input / navigation
    IRREVERSIBLE_MUTATION = "IRREVERSIBLE"   # Financial transfer, account creation, deletion


class ActionType(str, Enum):
    NAVIGATE = "NAVIGATE"
    CLICK = "CLICK"
    FILL = "FILL"
    SELECT_OPTION = "SELECT_OPTION"
    CHECK = "CHECK"
    UNCHECK = "UNCHECK"
    PRESS_KEY = "PRESS_KEY"
    WAIT_FOR_ELEMENT = "WAIT_FOR_ELEMENT"
    EXTRACT_TEXT = "EXTRACT_TEXT"
    EXTRACT_ATTRIBUTE = "EXTRACT_ATTRIBUTE"
    ASSERT_TEXT = "ASSERT_TEXT"
    ASSERT_VISIBLE = "ASSERT_VISIBLE"
    DISMISS_DIALOG = "DISMISS_DIALOG"


class LocatorStrategy(BaseModel):
    """
    Multi-strategy resilient element locator.
    Provides hierarchical fallbacks across Accessibility, Visual/Text, ARIA, and DOM levels.
    """
    primary_role: Optional[str] = Field(None, description="ARIA role (button, textbox, combobox, link)")
    accessible_name: Optional[str] = Field(None, description="Accessible name or ARIA label")
    text_content: Optional[str] = Field(None, description="Visible text or regex snippet")
    placeholder: Optional[str] = Field(None, description="Input placeholder text")
    label_text: Optional[str] = Field(None, description="Associated field label text")
    css_selector: Optional[str] = Field(None, description="Specific CSS selector fallback")
    xpath: Optional[str] = Field(None, description="XPath hierarchy fallback")
    visual_anchor: Optional[str] = Field(None, description="Neighboring visual anchor text")
    frame_selector: Optional[str] = Field(None, description="IFrame / frameset selector if nested")
    confidence_score: float = Field(1.0, description="Estimated stability score (0.0 - 1.0)")


class InputParameter(BaseModel):
    """Typed input parameter for capability invocation."""
    name: str
    type: ParameterType = ParameterType.STRING
    description: str
    required: bool = True
    default: Optional[Any] = None
    allowed_values: Optional[List[str]] = None
    redaction_class: Optional[str] = Field(None, description="PII class (e.g. SSN, CARD_NUMBER, PASSWORD, MEMBER_ID)")
    example: Optional[Any] = None


class OutputDeclaration(BaseModel):
    """Typed output extracted by the capability."""
    name: str
    type: ParameterType = ParameterType.STRING
    description: str
    target_locator: Optional[LocatorStrategy] = None
    extraction_attribute: Optional[str] = Field(None, description="Attribute name or 'text_content'")
    regex_capture: Optional[str] = Field(None, description="Regex pattern with capture group")
    required: bool = True
    example: Optional[Any] = None


class ActionStep(BaseModel):
    """A single deterministic execution step."""
    step_id: str = Field(..., description="Unique step identifier e.g. step_1")
    description: str
    action_type: ActionType
    target: Optional[LocatorStrategy] = None
    value: Optional[str] = Field(None, description="Literal value or parameter binding e.g. '{{member_id}}'")
    param_binding: Optional[str] = Field(None, description="Input parameter name bound to this action")
    timeout_ms: int = Field(5000, description="Step execution timeout in milliseconds")
    risk_level: RiskLevel = RiskLevel.SAFE_READ
    optional: bool = Field(False, description="Whether failure of this step can be safely skipped")
    wait_after_ms: int = Field(200, description="Settling delay after action in ms")


class CheckpointAssertion(BaseModel):
    """Verification assertion to confirm expected UI state."""
    checkpoint_id: str
    description: str
    target: LocatorStrategy
    assertion_type: str = Field("VISIBLE", description="VISIBLE | TEXT_CONTAINS | VALUE_EQUALS | NOT_EMPTY")
    expected_value: Optional[str] = None
    critical: bool = True


class BusinessOutcomeRule(BaseModel):
    """
    Expected non-crash business outcomes (e.g. Member Not Found, Account Frozen).
    Distinguishes legitimate business states from system errors.
    """
    outcome_code: str = Field(..., description="e.g. MEMBER_NOT_FOUND, ACCOUNT_LOCKED")
    description: str
    trigger_locator: LocatorStrategy
    trigger_condition: str = Field("VISIBLE", description="VISIBLE | TEXT_CONTAINS")
    expected_text_pattern: Optional[str] = None
    extract_message: bool = True


class RecoverableCondition(BaseModel):
    """
    Auto-recoverable runtime conditions (e.g. security modal, cookie banner, transient spinner).
    """
    condition_id: str
    description: str
    detection_locator: LocatorStrategy
    recovery_action: ActionType = ActionType.CLICK
    recovery_target: Optional[LocatorStrategy] = None
    max_retries: int = 2


class SafetyPolicy(BaseModel):
    """Policy guardrails bound to the capability."""
    allowed_domains: List[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    allowed_actions: List[ActionType] = Field(default_factory=lambda: list(ActionType))
    prohibit_external_navigation: bool = True
    max_total_duration_sec: int = 60
    requires_human_confirmation_for_mutation: bool = False


class CapabilityMetadata(BaseModel):
    """Metadata regarding creation and origin of the capability."""
    created_at: str
    discovered_by: str = "CUA Discovery Agent"
    source_goal: str
    tenant_scope: str = "GLOBAL"
    vendor_product: str = "ApexCore"
    version: str = "1.0.0"
    tags: List[str] = Field(default_factory=list)


class CapabilityArtifact(BaseModel):
    """
    The complete Typed Capability Artifact.
    Represents an agent-invocable, deterministic automation contract.
    """
    schema_version: str = "1.0.0"
    capability_id: str
    name: str
    description: str
    metadata: CapabilityMetadata
    entry_point: str
    inputs: List[InputParameter] = Field(default_factory=list)
    outputs: List[OutputDeclaration] = Field(default_factory=list)
    safety_policy: SafetyPolicy = Field(default_factory=SafetyPolicy)
    steps: List[ActionStep] = Field(default_factory=list)
    checkpoints: List[CheckpointAssertion] = Field(default_factory=list)
    business_outcomes: List[BusinessOutcomeRule] = Field(default_factory=list)
    recoverable_conditions: List[RecoverableCondition] = Field(default_factory=list)
