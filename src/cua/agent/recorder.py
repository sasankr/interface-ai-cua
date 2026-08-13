"""
Capability Artifact Compiler / Recorder
Converts discovery observations into typed, versioned, validated CapabilityArtifact objects.
"""

import time
import json
from typing import List, Dict, Any, Optional
from cua.models.capability import (
    CapabilityArtifact, CapabilityMetadata, ActionStep, ActionType,
    RiskLevel, LocatorStrategy, InputParameter, OutputDeclaration,
    CheckpointAssertion, BusinessOutcomeRule, RecoverableCondition,
    SafetyPolicy, ParameterType
)
from cua.safety.redactor import RedactionEngine


class ArtifactCompiler:
    @classmethod
    def compile_artifact(
        cls,
        capability_id: str,
        name: str,
        description: str,
        goal: str,
        entry_point: str,
        inputs: List[InputParameter],
        outputs: List[OutputDeclaration],
        steps: List[ActionStep],
        checkpoints: List[CheckpointAssertion],
        business_outcomes: List[BusinessOutcomeRule],
        recoverable_conditions: Optional[List[RecoverableCondition]] = None,
        vendor_product: str = "ApexCore Banking"
    ) -> CapabilityArtifact:
        """Constructs and validates a full CapabilityArtifact."""
        metadata = CapabilityMetadata(
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            discovered_by="CUA Discovery Agent v1.0",
            source_goal=goal,
            tenant_scope="GLOBAL_APEXCORE",
            vendor_product=vendor_product,
            version="1.0.0",
            tags=["banking", "cif", "deterministic-replay", "auto-generated"]
        )

        artifact = CapabilityArtifact(
            schema_version="1.0.0",
            capability_id=capability_id,
            name=name,
            description=description,
            metadata=metadata,
            entry_point=entry_point,
            inputs=inputs,
            outputs=outputs,
            safety_policy=SafetyPolicy(
                allowed_domains=["127.0.0.1", "localhost"],
                allowed_actions=list(ActionType),
                prohibit_external_navigation=True,
                max_total_duration_sec=30
            ),
            steps=steps,
            checkpoints=checkpoints,
            business_outcomes=business_outcomes,
            recoverable_conditions=recoverable_conditions or []
        )
        return artifact

    @classmethod
    def save_to_file(cls, artifact: CapabilityArtifact, file_path: str) -> str:
        """Serializes capability artifact to JSON with redaction checks."""
        data = artifact.model_dump()
        clean_data = RedactionEngine.redact_data(data)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(clean_data, f, indent=2)
        return file_path
