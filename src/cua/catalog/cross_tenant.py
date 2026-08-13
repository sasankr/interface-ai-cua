"""
Cross-Tenant Specialization & Override Engine
Allows an enterprise Capability Artifact recorded on a base core banking product
to be safely specialized and applied across different institution tenants.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from cua.models.capability import CapabilityArtifact, LocatorStrategy, ActionStep


class TenantOverride(BaseModel):
    tenant_id: str
    tenant_name: str
    entry_point_override: Optional[str] = None
    step_locator_overrides: Dict[str, LocatorStrategy] = Field(default_factory=dict)
    default_param_overrides: Dict[str, Any] = Field(default_factory=dict)


class CrossTenantAdapter:
    @classmethod
    def apply_tenant_override(
        cls,
        base_artifact: CapabilityArtifact,
        override: TenantOverride
    ) -> CapabilityArtifact:
        """Clones base artifact and applies tenant-specific locators and entry points."""
        artifact_copy = base_artifact.model_copy(deep=True)
        artifact_copy.metadata.tenant_scope = override.tenant_id
        
        if override.entry_point_override:
            artifact_copy.entry_point = override.entry_point_override

        # Apply locator overrides
        for step in artifact_copy.steps:
            if step.step_id in override.step_locator_overrides:
                step.target = override.step_locator_overrides[step.step_id]

        # Apply param defaults
        for inp in artifact_copy.inputs:
            if inp.name in override.default_param_overrides:
                inp.default = override.default_param_overrides[inp.name]

        return artifact_copy
