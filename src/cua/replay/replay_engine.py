"""
Deterministic Replay Engine
Executes recorded Capability Artifacts with 100% determinism (ZERO LLM calls).
Provides:
- Resilient locator resolution with automatic multi-strategy fallback
- Explicit differentiation between Business Outcomes, Recoverable Interstitials, and Hard Failures
- Parameter injection and type casting
- Checkpoint assertion verification
- Automated screenshot & step latency logging
- Seamless HITL escalation routing on failure
"""

import time
import uuid
import re
import os
from typing import Dict, Any, Optional, Callable
from playwright.sync_api import sync_playwright, Browser, Page

from cua.models.capability import (
    CapabilityArtifact, ActionStep, ActionType, RiskLevel,
    InputParameter, OutputDeclaration, CheckpointAssertion
)
from cua.models.execution import (
    ReplayResult, ExecutionStatus, StepExecutionRecord,
    HumanInterventionRequest, HumanInterventionResult
)
from cua.safety.guardrails import SafetyGuardrailEngine, SecurityViolationError
from cua.safety.redactor import RedactionEngine
from cua.replay.locator import LocatorResolver, LocatorResolutionError
from cua.replay.outcome_evaluator import OutcomeEvaluator
from cua.hitl.escalation import HITLEscalationManager
from cua.observability.evidence import EvidenceCollector


class ReplayEngine:
    def __init__(
        self,
        headless: bool = True,
        evidence_dir: str = "evidence",
        hitl_manager: Optional[HITLEscalationManager] = None
    ):
        self.headless = headless
        self.evidence_dir = evidence_dir
        self.hitl_manager = hitl_manager or HITLEscalationManager(evidence_dir=evidence_dir)
        self.evidence_collector = EvidenceCollector(output_dir=evidence_dir)

    def execute(
        self,
        artifact: CapabilityArtifact,
        inputs: Optional[Dict[str, Any]] = None,
        operator_callback: Optional[Callable[[HumanInterventionRequest, Page], HumanInterventionResult]] = None
    ) -> ReplayResult:
        """
        Executes a capability artifact against a live browser session deterministically.
        """
        run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
        start_time = time.time()
        applied_inputs = self._prepare_inputs(artifact, inputs or {})
        guardrails = SafetyGuardrailEngine(policy=artifact.safety_policy)

        step_records = []
        screenshot_paths = []
        interventions = []
        extracted_outputs = {}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()

            try:
                # 1. Execute Entry Point Navigation
                guardrails.validate_url(artifact.entry_point)
                page.goto(artifact.entry_point, timeout=10000)
                page.wait_for_load_state("networkidle", timeout=5000)

                # Pre-flight check for recoverable interstitials
                OutcomeEvaluator.handle_recoverable_conditions(page, artifact.recoverable_conditions)

                # 2. Sequential Step Execution Loop
                for step in artifact.steps:
                    step_start = time.time()
                    step_status = "SUCCESS"
                    error_msg = None
                    loc_details = None
                    resolved_val = None

                    try:
                        # Safety check on step
                        guardrails.validate_step(step)

                        # Handle any transient interstitials before step
                        OutcomeEvaluator.handle_recoverable_conditions(page, artifact.recoverable_conditions)

                        # Check if current page already matched a known business outcome
                        outcome_match = OutcomeEvaluator.check_business_outcomes(page, artifact.business_outcomes)
                        if outcome_match:
                            rule, msg = outcome_match
                            return self._build_result(
                                artifact, run_id, ExecutionStatus.BUSINESS_OUTCOME,
                                applied_inputs, extracted_outputs, start_time, step_records,
                                screenshot_paths, interventions,
                                business_outcome_code=rule.outcome_code,
                                business_outcome_message=msg
                            )

                        # Resolve parameter substitution for value
                        resolved_val = self._resolve_step_value(step, applied_inputs)

                        # Execute action
                        loc_details = self._execute_step_action(page, step, resolved_val)
                        
                        # Post-action settling delay
                        if step.wait_after_ms > 0:
                            page.wait_for_timeout(step.wait_after_ms)

                        # Check for business outcome immediately post-action
                        outcome_match = OutcomeEvaluator.check_business_outcomes(page, artifact.business_outcomes)
                        if outcome_match:
                            rule, msg = outcome_match
                            # Capture screenshot of business outcome
                            ss_path = self._capture_screenshot(page, run_id, f"outcome_{rule.outcome_code}")
                            screenshot_paths.append(ss_path)
                            
                            step_records.append(StepExecutionRecord(
                                step_id=step.step_id,
                                description=step.description,
                                action_type=step.action_type.value,
                                status="BUSINESS_OUTCOME_TRIGGERED",
                                resolved_value=resolved_val,
                                locator_details=loc_details,
                                duration_ms=(time.time() - step_start) * 1000,
                                screenshot_path=ss_path
                            ))
                            return self._build_result(
                                artifact, run_id, ExecutionStatus.BUSINESS_OUTCOME,
                                applied_inputs, extracted_outputs, start_time, step_records,
                                screenshot_paths, interventions,
                                business_outcome_code=rule.outcome_code,
                                business_outcome_message=msg
                            )

                    except (LocatorResolutionError, SecurityViolationError, Exception) as ex:
                        step_status = "FAILED"
                        error_msg = str(ex)

                        # Capture failure screenshot
                        fail_ss = self._capture_screenshot(page, run_id, f"fail_{step.step_id}")
                        screenshot_paths.append(fail_ss)

                        # Attempt Human Escalation / Live Handoff
                        if not step.optional:
                            hitl_result = self.hitl_manager.trigger_escalation(
                                page=page,
                                capability=artifact,
                                failing_step=step,
                                reason=f"Step {step.step_id} failed: {error_msg}",
                                goal=artifact.description,
                                operator_callback=operator_callback
                            )
                            interventions.append(hitl_result)

                            if hitl_result.resolution_status == "RESUMED":
                                step_status = "RECOVERED_BY_OPERATOR"
                            else:
                                step_records.append(StepExecutionRecord(
                                    step_id=step.step_id,
                                    description=step.description,
                                    action_type=step.action_type.value,
                                    status="ESCALATED_FAILED",
                                    resolved_value=resolved_val,
                                    duration_ms=(time.time() - step_start) * 1000,
                                    screenshot_path=fail_ss,
                                    error_message=error_msg
                                ))
                                return self._build_result(
                                    artifact, run_id, ExecutionStatus.HARD_FAILURE,
                                    applied_inputs, extracted_outputs, start_time, step_records,
                                    screenshot_paths, interventions,
                                    error_code="STEP_EXECUTION_FAILURE",
                                    error_message=error_msg,
                                    failed_step_id=step.step_id,
                                    observed_dom_snippet=RedactionEngine.redact_text(page.content()[:1500])
                                )

                    # Record successful step
                    step_ss = self._capture_screenshot(page, run_id, step.step_id)
                    screenshot_paths.append(step_ss)

                    step_records.append(StepExecutionRecord(
                        step_id=step.step_id,
                        description=step.description,
                        action_type=step.action_type.value,
                        status=step_status,
                        resolved_value=resolved_val,
                        locator_details=loc_details,
                        duration_ms=(time.time() - step_start) * 1000,
                        screenshot_path=step_ss,
                        error_message=error_msg
                    ))

                # 3. Verify Checkpoints
                for cp in artifact.checkpoints:
                    passed = OutcomeEvaluator.verify_checkpoint(page, cp)
                    if not passed and cp.critical:
                        fail_ss = self._capture_screenshot(page, run_id, f"checkpoint_{cp.checkpoint_id}_fail")
                        screenshot_paths.append(fail_ss)
                        return self._build_result(
                            artifact, run_id, ExecutionStatus.HARD_FAILURE,
                            applied_inputs, extracted_outputs, start_time, step_records,
                            screenshot_paths, interventions,
                            error_code="CHECKPOINT_ASSERTION_FAILED",
                            error_message=f"Critical checkpoint '{cp.checkpoint_id}' ({cp.description}) was not satisfied.",
                            failed_step_id=cp.checkpoint_id,
                            observed_dom_snippet=RedactionEngine.redact_text(page.content()[:1500])
                        )

                # 4. Extract Declared Outputs
                for output in artifact.outputs:
                    extracted_val = self._extract_output(page, output)
                    extracted_outputs[output.name] = extracted_val

                # 5. Build Final Success Result
                res = self._build_result(
                    artifact, run_id, ExecutionStatus.SUCCESS,
                    applied_inputs, extracted_outputs, start_time, step_records,
                    screenshot_paths, interventions
                )
                self.evidence_collector.record_run(res)
                return res

            except Exception as unhandled:
                fail_ss = self._capture_screenshot(page, run_id, "unhandled_crash")
                screenshot_paths.append(fail_ss)
                res = self._build_result(
                    artifact, run_id, ExecutionStatus.HARD_FAILURE,
                    applied_inputs, extracted_outputs, start_time, step_records,
                    screenshot_paths, interventions,
                    error_code="UNHANDLED_ENGINE_EXCEPTION",
                    error_message=str(unhandled)
                )
                self.evidence_collector.record_run(res)
                return res
            finally:
                browser.close()

    def _prepare_inputs(self, artifact: CapabilityArtifact, provided_inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Validates and merges provided inputs with artifact defaults."""
        merged = {}
        for param in artifact.inputs:
            if param.name in provided_inputs:
                merged[param.name] = provided_inputs[param.name]
            elif param.default is not None:
                merged[param.name] = param.default
            elif param.required:
                raise ValueError(f"Missing required parameter '{param.name}' for capability '{artifact.capability_id}'.")
        return merged

    def _resolve_step_value(self, step: ActionStep, inputs: Dict[str, Any]) -> Optional[str]:
        if step.param_binding and step.param_binding in inputs:
            return str(inputs[step.param_binding])
        if step.value:
            val = step.value
            for k, v in inputs.items():
                val = val.replace(f"{{{{{k}}}}}", str(v))
            return val
        return None

    def _execute_step_action(self, page: Page, step: ActionStep, resolved_value: Optional[str]):
        """Dispatches action to Playwright."""
        action = step.action_type

        if action == ActionType.NAVIGATE:
            page.goto(resolved_value, timeout=step.timeout_ms)
            return None

        if not step.target:
            raise ValueError(f"Step {step.step_id} requires a target locator.")

        elem, loc_details = LocatorResolver.resolve(page, step.target, timeout_ms=step.timeout_ms)

        if action == ActionType.CLICK:
            elem.click(timeout=step.timeout_ms)
        elif action == ActionType.FILL:
            elem.fill(resolved_value or "", timeout=step.timeout_ms)
        elif action == ActionType.SELECT_OPTION:
            elem.select_option(label=resolved_value, timeout=step.timeout_ms)
        elif action == ActionType.CHECK:
            elem.check(timeout=step.timeout_ms)
        elif action == ActionType.PRESS_KEY:
            elem.press(resolved_value or "Enter", timeout=step.timeout_ms)
        elif action == ActionType.WAIT_FOR_ELEMENT:
            elem.wait_for(state="visible", timeout=step.timeout_ms)
        
        return loc_details

    def _extract_output(self, page: Page, output: OutputDeclaration) -> Any:
        """Extracts data from the page using declared output rules."""
        if not output.target_locator:
            return None
        try:
            elem, _ = LocatorResolver.resolve(page, output.target_locator, timeout_ms=3000)
            text = elem.text_content() or ""
            text = text.strip()

            if output.regex_capture:
                m = re.search(output.regex_capture, text)
                if m:
                    text = m.group(1) if m.groups() else m.group(0)

            return text
        except Exception:
            return None

    def _capture_screenshot(self, page: Page, run_id: str, tag: str) -> str:
        ss_dir = os.path.join(self.evidence_dir, "screenshots")
        os.makedirs(ss_dir, exist_ok=True)
        path = os.path.join(ss_dir, f"{run_id}_{tag}.png")
        try:
            page.screenshot(path=path)
            return path
        except Exception:
            return ""

    def _build_result(
        self,
        artifact: CapabilityArtifact,
        run_id: str,
        status: ExecutionStatus,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        start_time: float,
        step_records: list,
        screenshot_paths: list,
        interventions: list,
        business_outcome_code: Optional[str] = None,
        business_outcome_message: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        failed_step_id: Optional[str] = None,
        observed_dom_snippet: Optional[str] = None
    ) -> ReplayResult:
        total_ms = (time.time() - start_time) * 1000
        res = ReplayResult(
            capability_id=artifact.capability_id,
            run_id=run_id,
            status=status,
            inputs_applied=inputs,
            outputs_extracted=outputs,
            business_outcome_code=business_outcome_code,
            business_outcome_message=business_outcome_message,
            error_code=error_code,
            error_message=error_message,
            failed_step_id=failed_step_id,
            observed_dom_snippet=observed_dom_snippet,
            total_duration_ms=total_ms,
            step_records=step_records,
            screenshot_paths=screenshot_paths,
            human_interventions=interventions
        )
        self.evidence_collector.record_run(res)
        return res
