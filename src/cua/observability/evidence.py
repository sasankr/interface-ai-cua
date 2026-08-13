"""
Evidence Collector & Observability Manager
Captures step-by-step screenshots, redacted execution traces, timing profiles,
and compiles consolidated run summaries for auditable compliance.
"""

import json
import os
import time
from typing import Dict, Any, List
from cua.models.execution import ReplayResult, StepExecutionRecord
from cua.safety.redactor import RedactionEngine


class EvidenceCollector:
    def __init__(self, output_dir: str = "evidence"):
        self.output_dir = output_dir
        self.screenshots_dir = os.path.join(output_dir, "screenshots")
        os.makedirs(self.screenshots_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

    def record_run(self, result: ReplayResult) -> str:
        """Saves structured result JSON and summary log."""
        # 1. Redact result payload
        raw_dict = result.model_dump()
        clean_dict = RedactionEngine.redact_data(raw_dict)

        # 2. Write JSON trace
        trace_path = os.path.join(self.output_dir, f"run_{result.capability_id}_{result.run_id}.json")
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(clean_dict, f, indent=2)

        # 3. Write structured human-readable run log
        log_path = os.path.join(self.output_dir, f"run_{result.capability_id}_{result.run_id}.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"=== CUA RUN EXECUTION EVIDENCE ===\n")
            f.write(f"Capability: {result.capability_id}\n")
            f.write(f"Run ID:     {result.run_id}\n")
            f.write(f"Status:     {result.status.value}\n")
            f.write(f"Duration:   {result.total_duration_ms:.2f} ms\n")
            f.write(f"Inputs:     {json.dumps(clean_dict['inputs_applied'])}\n")
            f.write(f"Outputs:    {json.dumps(clean_dict['outputs_extracted'])}\n")
            if result.business_outcome_code:
                f.write(f"Outcome:    [{result.business_outcome_code}] {result.business_outcome_message}\n")
            if result.error_code:
                f.write(f"Error:      [{result.error_code}] {result.error_message} (Step: {result.failed_step_id})\n")
            f.write(f"\n--- STEP TIMELINE ---\n")
            for idx, step in enumerate(result.step_records, 1):
                loc_info = f" ({step.locator_details.strategy_used})" if step.locator_details else ""
                f.write(f"[{idx}] {step.step_id} - {step.action_type}{loc_info}: {step.status} ({step.duration_ms:.1f}ms)\n")
                if step.error_message:
                    f.write(f"    ERROR: {step.error_message}\n")
            if result.human_interventions:
                f.write(f"\n--- HUMAN INTERVENTIONS ---\n")
                for hitl in result.human_interventions:
                    f.write(f"- ID: {hitl.intervention_id} | Status: {hitl.resolution_status} | Operator: {hitl.operator_id}\n")
                    f.write(f"  Notes: {hitl.operator_notes}\n")

        return log_path
