"""
Execution & Observability Result Models
Typed contracts for replay results, step execution records, and human intervention requests.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    BUSINESS_OUTCOME = "BUSINESS_OUTCOME"
    HARD_FAILURE = "HARD_FAILURE"
    SAFETY_VIOLATION = "SAFETY_VIOLATION"
    ESCALATED_TO_HUMAN = "ESCALATED_TO_HUMAN"
    RECOVERED_AUTOMATICALLY = "RECOVERED_AUTOMATICALLY"


class LocatorResolutionDetails(BaseModel):
    strategy_used: str
    selector_string: str
    resolved_in_ms: float
    fallback_attempts: int = 0


class StepExecutionRecord(BaseModel):
    step_id: str
    description: str
    action_type: str
    status: str
    resolved_value: Optional[str] = None
    locator_details: Optional[LocatorResolutionDetails] = None
    duration_ms: float
    screenshot_path: Optional[str] = None
    error_message: Optional[str] = None
    human_assisted: bool = False


class HumanInterventionRequest(BaseModel):
    intervention_id: str
    capability_id: str
    goal: str
    failing_step_id: Optional[str] = None
    reason: str
    current_url: str
    screenshot_path: str
    dom_snippet_path: Optional[str] = None
    suggested_action: str
    created_at: str


class HumanInterventionResult(BaseModel):
    intervention_id: str
    operator_id: str
    resolution_status: str  # RESUMED | CANCELLED | MANUAL_OVERRIDE_COMPLETED
    operator_notes: str
    manual_actions_taken: List[str] = Field(default_factory=list)
    resumed_at: str


class ReplayResult(BaseModel):
    """Structured production result returned to calling AI agent."""
    capability_id: str
    run_id: str
    status: ExecutionStatus
    inputs_applied: Dict[str, Any]
    outputs_extracted: Dict[str, Any] = Field(default_factory=dict)
    
    # Business outcome details if status == BUSINESS_OUTCOME
    business_outcome_code: Optional[str] = None
    business_outcome_message: Optional[str] = None
    
    # Failure diagnostics if status == HARD_FAILURE or SAFETY_VIOLATION
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    failed_step_id: Optional[str] = None
    observed_dom_snippet: Optional[str] = None
    
    # Execution metrics & observability
    total_duration_ms: float = 0.0
    step_records: List[StepExecutionRecord] = Field(default_factory=list)
    screenshot_paths: List[str] = Field(default_factory=list)
    evidence_bundle_path: Optional[str] = None
    
    # Human Escalation audit
    human_interventions: List[HumanInterventionResult] = Field(default_factory=list)
