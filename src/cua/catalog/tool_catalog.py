"""
Agent-Facing Capability Catalog
Exposes saved capability artifacts as standard OpenAI / Anthropic / Gemini Tool schemas.
Allows upstream conversational AI agents to discover, inspect, and invoke back-office capabilities.
"""

import os
import glob
import json
from typing import Dict, List, Any, Optional
from cua.models.capability import CapabilityArtifact
from cua.replay.replay_engine import ReplayEngine
from cua.models.execution import ReplayResult


class CapabilityCatalog:
    def __init__(self, artifacts_dir: str = "evidence", replay_engine: Optional[ReplayEngine] = None):
        self.artifacts_dir = artifacts_dir
        self.replay_engine = replay_engine or ReplayEngine()
        self._capabilities: Dict[str, CapabilityArtifact] = {}
        self.reload()

    def reload(self):
        """Scans artifacts directory and loads all JSON capability artifacts."""
        self._capabilities.clear()
        if not os.path.exists(self.artifacts_dir):
            return

        pattern = os.path.join(self.artifacts_dir, "capability_*.json")
        for file_path in glob.glob(pattern):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    artifact = CapabilityArtifact(**data)
                    self._capabilities[artifact.capability_id] = artifact
            except Exception as e:
                print(f"Warning: Failed to load artifact from {file_path}: {e}")

    def list_capabilities(self) -> List[Dict[str, Any]]:
        """Returns catalog metadata for all registered capabilities."""
        return [
            {
                "capability_id": cap.capability_id,
                "name": cap.name,
                "description": cap.description,
                "inputs": [p.model_dump() for p in cap.inputs],
                "outputs": [o.model_dump() for o in cap.outputs]
            }
            for cap in self._capabilities.values()
        ]

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """Formats catalog as standard OpenAI Function Calling / Tool definition."""
        tools = []
        for cap in self._capabilities.values():
            properties = {}
            required = []
            for inp in cap.inputs:
                properties[inp.name] = {
                    "type": inp.type.value,
                    "description": inp.description
                }
                if inp.default is not None:
                    properties[inp.name]["default"] = inp.default
                if inp.required:
                    required.append(inp.name)

            tool_def = {
                "type": "function",
                "function": {
                    "name": cap.capability_id.replace(".", "__"),
                    "description": f"{cap.name}: {cap.description}",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            }
            tools.append(tool_def)
        return tools

    def invoke(self, capability_id: str, arguments: Dict[str, Any]) -> ReplayResult:
        """Executes a capability by identifier using the deterministic replay engine."""
        normalized_id = capability_id.replace("__", ".")
        if normalized_id not in self._capabilities:
            raise KeyError(f"Capability '{normalized_id}' not found in catalog. Available: {list(self._capabilities.keys())}")

        artifact = self._capabilities[normalized_id]
        return self.replay_engine.execute(artifact, inputs=arguments)
