"""
Unit tests for Capability Schema models and serialization.
"""

import pytest
from cua.models.capability import (
    CapabilityArtifact, ActionStep, ActionType, RiskLevel,
    LocatorStrategy, InputParameter, OutputDeclaration,
    CheckpointAssertion, BusinessOutcomeRule, ParameterType,
    CapabilityMetadata
)


def test_capability_artifact_serialization():
    cap = CapabilityArtifact(
        schema_version="1.0.0",
        capability_id="test.lookup",
        name="Test Lookup",
        description="A test lookup capability",
        metadata=CapabilityMetadata(
            created_at="2026-08-13T00:00:00Z",
            source_goal="Test lookup goal"
        ),
        entry_point="http://127.0.0.1:8000/portal/member_search",
        inputs=[
            InputParameter(name="member_id", type=ParameterType.STRING, description="Member ID")
        ],
        outputs=[
            OutputDeclaration(name="balance", type=ParameterType.STRING, description="Balance")
        ],
        steps=[
            ActionStep(
                step_id="step_1",
                description="Input member ID",
                action_type=ActionType.FILL,
                target=LocatorStrategy(primary_role="textbox", css_selector="#txtMemberId"),
                param_binding="member_id"
            )
        ],
        checkpoints=[
            CheckpointAssertion(
                checkpoint_id="chk_1",
                description="Check table visible",
                target=LocatorStrategy(css_selector="#tblMemberAccounts")
            )
        ],
        business_outcomes=[
            BusinessOutcomeRule(
                outcome_code="MEMBER_NOT_FOUND",
                description="Not found outcome",
                trigger_locator=LocatorStrategy(css_selector="#error-code-badge")
            )
        ]
    )

    data = cap.model_dump()
    assert data["schema_version"] == "1.0.0"
    assert data["capability_id"] == "test.lookup"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["action_type"] == "FILL"

    # Reconstruct
    reconstructed = CapabilityArtifact(**data)
    assert reconstructed.capability_id == cap.capability_id
    assert reconstructed.steps[0].param_binding == "member_id"
