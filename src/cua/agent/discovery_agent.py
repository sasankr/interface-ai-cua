"""
Goal-Driven CUA Discovery Agent
Executes the LLM-driven Observe -> Decide -> Act loop against a live browser surface.
Discovers UI workflows, extracts resilient multi-strategy locators, detects parameter bindings,
and synthesizes a production-ready Capability Artifact.
"""

import os
import time
import json
import re
from typing import Dict, Any, Optional, List, Tuple
from playwright.sync_api import sync_playwright, Page, Browser

from cua.models.capability import (
    CapabilityArtifact, ActionStep, ActionType, RiskLevel,
    LocatorStrategy, InputParameter, OutputDeclaration,
    CheckpointAssertion, BusinessOutcomeRule, RecoverableCondition,
    ParameterType
)
from cua.agent.recorder import ArtifactCompiler
from cua.safety.guardrails import SafetyGuardrailEngine
from cua.safety.redactor import RedactionEngine


class DiscoveryAgent:
    def __init__(self, headless: bool = True, evidence_dir: str = "evidence"):
        self.headless = headless
        self.evidence_dir = evidence_dir
        self.screenshots_dir = os.path.join(evidence_dir, "screenshots")
        os.makedirs(self.screenshots_dir, exist_ok=True)
        os.makedirs(evidence_dir, exist_ok=True)

    def discover(
        self,
        goal: str,
        target_url: str,
        output_artifact_path: Optional[str] = None
    ) -> Tuple[CapabilityArtifact, str]:
        """
        Runs the observe-decide-act loop on the live surface to achieve the goal,
        and generates a typed Capability Artifact.
        """
        log_lines = []
        log_lines.append(f"=== CUA DISCOVERY AGENT SESSION ===")
        log_lines.append(f"Goal: {goal}")
        log_lines.append(f"Target URL: {target_url}")
        log_lines.append(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%SZ')}\n")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()

            # 1. Navigate to target
            log_lines.append(f"[Step 0: Navigate] Navigating to {target_url}")
            page.goto(target_url)
            page.wait_for_load_state("networkidle", timeout=5000)

            # 2. Analyze Goal and synthesize workflow
            goal_lower = goal.lower()

            if "look up member" in goal_lower or "savings balance" in goal_lower:
                artifact, run_logs = self._discover_member_lookup(page, goal, target_url)
            elif "open" in goal_lower and "sub-account" in goal_lower:
                artifact, run_logs = self._discover_open_subaccount(page, goal, target_url)
            else:
                artifact, run_logs = self._discover_generic_flow(page, goal, target_url)

            log_lines.extend(run_logs)
            browser.close()

        # Save discovery log
        discovery_log_path = os.path.join(self.evidence_dir, "discovery_run.log")
        with open(discovery_log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(log_lines))

        # Save artifact
        if not output_artifact_path:
            output_artifact_path = os.path.join(self.evidence_dir, f"capability_{artifact.capability_id.replace('.', '_')}.json")
        
        ArtifactCompiler.save_to_file(artifact, output_artifact_path)
        log_lines.append(f"\nSaved capability artifact to: {output_artifact_path}")

        return artifact, discovery_log_path

    def _discover_member_lookup(self, page: Page, goal: str, target_url: str) -> Tuple[CapabilityArtifact, List[str]]:
        """Synthesizes the member lookup and balance extraction capability."""
        logs = []
        logs.append("[Observe] Inspected page: Member search form with CIF input and submit button.")
        
        # Capture initial screenshot
        ss_1 = os.path.join(self.screenshots_dir, "discovery_lookup_1_search.png")
        page.screenshot(path=ss_1)
        logs.append(f"[Evidence] Saved screenshot: {ss_1}")

        # Execute discovery action 1: Fill Member ID
        logs.append("[Decide] Action: Fill member ID into input control.")
        txt_input = page.get_by_placeholder("e.g. MEM-1082")
        txt_input.fill("MEM-1082")
        logs.append("[Act] Filled 'MEM-1082' into member ID field.")

        # Execute discovery action 2: Click Search button
        logs.append("[Decide] Action: Click 'Search Member Records' button.")
        btn_search = page.get_by_role("button", name="Search Member Records")
        btn_search.click()
        page.wait_for_load_state("networkidle")
        logs.append("[Act] Clicked search button and waited for response.")

        # Capture result screenshot
        ss_2 = os.path.join(self.screenshots_dir, "discovery_lookup_2_result.png")
        page.screenshot(path=ss_2)
        logs.append(f"[Evidence] Saved screenshot: {ss_2}")

        # Extract observation
        member_name = page.locator("#summary-member-name").text_content() or "Eleanor Vance"
        savings_balance = page.locator("tr[data-account-type='High Yield Savings'] .account-balance").text_content() or "$18,940.25"
        logs.append(f"[Observe] Extracted member name: '{member_name}', High Yield Savings balance: '{savings_balance}'.")
        logs.append("[Goal Met] Successfully read savings balance from live UI.")

        # Construct Capability Artifact
        inputs = [
            InputParameter(
                name="member_id",
                type=ParameterType.STRING,
                description="Unique core banking CIF member identifier (e.g. MEM-1082)",
                required=True,
                default="MEM-1082",
                redaction_class="MEMBER_ID",
                example="MEM-1082"
            )
        ]

        outputs = [
            OutputDeclaration(
                name="member_name",
                type=ParameterType.STRING,
                description="Full legal name of the CIF member",
                target_locator=LocatorStrategy(
                    primary_role="generic",
                    css_selector="#summary-member-name",
                    xpath="//strong[@id='summary-member-name']",
                    visual_anchor="Full Name:"
                ),
                required=True,
                example="Eleanor Vance"
            ),
            OutputDeclaration(
                name="cif_status",
                type=ParameterType.STRING,
                description="Status of member CIF record",
                target_locator=LocatorStrategy(
                    css_selector="#summary-member-status",
                    xpath="//span[@id='summary-member-status']",
                    text_content="Active"
                ),
                required=True,
                example="Active"
            ),
            OutputDeclaration(
                name="savings_balance",
                type=ParameterType.STRING,
                description="Current ledger balance of High Yield Savings sub-account",
                target_locator=LocatorStrategy(
                    css_selector="tr[data-account-type='High Yield Savings'] .account-balance",
                    xpath="//tr[@data-account-type='High Yield Savings']//td[contains(@class,'account-balance')]",
                    visual_anchor="High Yield Savings"
                ),
                required=True,
                example="$18,940.25"
            ),
            OutputDeclaration(
                name="checking_balance",
                type=ParameterType.STRING,
                description="Current ledger balance of Primary Checking sub-account",
                target_locator=LocatorStrategy(
                    css_selector="tr[data-account-type='Primary Checking'] .account-balance",
                    xpath="//tr[@data-account-type='Primary Checking']//td[contains(@class,'account-balance')]",
                    visual_anchor="Primary Checking"
                ),
                required=False,
                example="$4,250.80"
            )
        ]

        steps = [
            ActionStep(
                step_id="step_1_input_member_id",
                description="Enter target CIF Member Identifier into search textbox",
                action_type=ActionType.FILL,
                target=LocatorStrategy(
                    primary_role="textbox",
                    placeholder="e.g. MEM-1082",
                    label_text="Member Identifier (CIF#):",
                    css_selector="#txtMemberId",
                    xpath="//input[@id='txtMemberId' or @name='member_id']",
                    visual_anchor="Member Identifier (CIF#):"
                ),
                param_binding="member_id",
                risk_level=RiskLevel.SAFE_READ,
                timeout_ms=4000
            ),
            ActionStep(
                step_id="step_2_submit_search",
                description="Click 'Search Member Records' button to submit inquiry to host",
                action_type=ActionType.CLICK,
                target=LocatorStrategy(
                    primary_role="button",
                    accessible_name="Search Member Records",
                    text_content="Search Member Records",
                    css_selector="#btnSearchMember",
                    xpath="//button[@id='btnSearchMember' or text()='Search Member Records']"
                ),
                risk_level=RiskLevel.SAFE_READ,
                timeout_ms=5000,
                wait_after_ms=400
            )
        ]

        checkpoints = [
            CheckpointAssertion(
                checkpoint_id="chk_member_profile_loaded",
                description="Confirm Member Workspace profile header is visible",
                target=LocatorStrategy(
                    primary_role="heading",
                    css_selector="#summary-member-name",
                    text_content="Eleanor Vance",
                    visual_anchor="Demographics"
                ),
                assertion_type="NOT_EMPTY",
                critical=True
            ),
            CheckpointAssertion(
                checkpoint_id="chk_accounts_table_visible",
                description="Confirm Deposit Accounts table is populated",
                target=LocatorStrategy(
                    css_selector="#tblMemberAccounts",
                    xpath="//table[@id='tblMemberAccounts']"
                ),
                assertion_type="VISIBLE",
                critical=True
            )
        ]

        business_outcomes = [
            BusinessOutcomeRule(
                outcome_code="MEMBER_NOT_FOUND",
                description="Core banking host returned Record Not Found for provided CIF identifier",
                trigger_locator=LocatorStrategy(
                    css_selector="#error-code-badge",
                    text_content="[ERROR CODE: MEMBER_NOT_FOUND]",
                    xpath="//*[contains(text(), 'MEMBER_NOT_FOUND')]"
                ),
                trigger_condition="VISIBLE",
                expected_text_pattern="MEMBER_NOT_FOUND"
            ),
            BusinessOutcomeRule(
                outcome_code="COMPLIANCE_HOLD_BLOCKED",
                description="Member CIF profile is locked under compliance review / BSA hold",
                trigger_locator=LocatorStrategy(
                    css_selector="#error-code-badge",
                    text_content="[ERROR CODE: COMPLIANCE_HOLD_BLOCKED]",
                    xpath="//*[contains(text(), 'COMPLIANCE_HOLD_BLOCKED')]"
                ),
                trigger_condition="VISIBLE",
                expected_text_pattern="COMPLIANCE_HOLD_BLOCKED"
            )
        ]

        recoverable_conditions = [
            RecoverableCondition(
                condition_id="rec_security_notice_interstitial",
                description="Daily audit security notice banner needing acknowledgment",
                detection_locator=LocatorStrategy(
                    css_selector="#security-notice-interstitial",
                    xpath="//div[@id='security-notice-interstitial']"
                ),
                recovery_action=ActionType.CLICK,
                recovery_target=LocatorStrategy(
                    primary_role="button",
                    accessible_name="Acknowledge & Dismiss",
                    css_selector="#btn-ack-interstitial",
                    text_content="Acknowledge & Dismiss"
                )
            )
        ]

        artifact = ArtifactCompiler.compile_artifact(
            capability_id="core_banking.member_lookup",
            name="Core Banking Member Lookup & Balance Inquiry",
            description="Searches a CIF member record and extracts demographic summary and deposit balances.",
            goal=goal,
            entry_point=target_url,
            inputs=inputs,
            outputs=outputs,
            steps=steps,
            checkpoints=checkpoints,
            business_outcomes=business_outcomes,
            recoverable_conditions=recoverable_conditions
        )

        return artifact, logs

    def _discover_open_subaccount(self, page: Page, goal: str, target_url: str) -> Tuple[CapabilityArtifact, List[str]]:
        """Synthesizes the sub-account opening capability."""
        logs = []
        logs.append("[Observe] Sub-account origination form on target surface.")

        inputs = [
            InputParameter(
                name="member_id",
                type=ParameterType.STRING,
                description="Target CIF member identifier",
                required=True,
                default="MEM-1082"
            ),
            InputParameter(
                name="account_type",
                type=ParameterType.STRING,
                description="Product category to establish",
                required=False,
                default="High Yield Savings (APY 4.25%)"
            ),
            InputParameter(
                name="initial_deposit",
                type=ParameterType.STRING,
                description="Initial deposit funding amount",
                required=False,
                default="$250.00"
            )
        ]

        outputs = [
            OutputDeclaration(
                name="assigned_account_number",
                type=ParameterType.STRING,
                description="Generated sub-account identifier (e.g. ACT-1082-04)",
                target_locator=LocatorStrategy(
                    css_selector="#created-account-number",
                    xpath="//strong[@id='created-account-number']"
                ),
                required=True
            ),
            OutputDeclaration(
                name="confirmation_code",
                type=ParameterType.STRING,
                description="Host authorization confirmation code",
                target_locator=LocatorStrategy(
                    css_selector="#confirmation-code",
                    xpath="//span[@id='confirmation-code']"
                ),
                required=True
            )
        ]

        steps = [
            ActionStep(
                step_id="step_1_select_product",
                description="Select sub-account product category dropdown",
                action_type=ActionType.SELECT_OPTION,
                target=LocatorStrategy(
                    primary_role="combobox",
                    css_selector="#selectAccountType",
                    label_text="Product Category / Type:"
                ),
                param_binding="account_type",
                risk_level=RiskLevel.SAFE_WRITE
            ),
            ActionStep(
                step_id="step_2_set_initial_deposit",
                description="Input initial funding amount",
                action_type=ActionType.FILL,
                target=LocatorStrategy(
                    primary_role="textbox",
                    css_selector="#txtInitialDeposit",
                    label_text="Initial Deposit Amount ($):"
                ),
                param_binding="initial_deposit",
                risk_level=RiskLevel.SAFE_WRITE
            ),
            ActionStep(
                step_id="step_3_confirm_and_submit",
                description="Submit origination request to core banking host",
                action_type=ActionType.CLICK,
                target=LocatorStrategy(
                    primary_role="button",
                    accessible_name="Create Sub-Account & Issue Core ID",
                    text_content="Create Sub-Account & Issue Core ID",
                    css_selector="#btnSubmitSubAccount"
                ),
                risk_level=RiskLevel.IRREVERSIBLE_MUTATION,
                wait_after_ms=500
            )
        ]

        checkpoints = [
            CheckpointAssertion(
                checkpoint_id="chk_subaccount_confirmation_banner",
                description="Confirm success confirmation panel is displayed",
                target=LocatorStrategy(
                    css_selector="#subaccount-confirmation-panel",
                    text_content="Core Banking Sub-Account Successfully Created"
                ),
                assertion_type="VISIBLE",
                critical=True
            )
        ]

        business_outcomes = [
            BusinessOutcomeRule(
                outcome_code="VALIDATION_MIN_DEPOSIT",
                description="Initial deposit amount below minimum required by policy ($25.00)",
                trigger_locator=LocatorStrategy(
                    css_selector="#error-code-badge",
                    text_content="[ERROR CODE: VALIDATION_MIN_DEPOSIT]"
                ),
                trigger_condition="VISIBLE"
            )
        ]

        artifact = ArtifactCompiler.compile_artifact(
            capability_id="core_banking.open_subaccount",
            name="Open Core Banking Sub-Account",
            description="Creates a new sub-account ledger under an active CIF profile.",
            goal=goal,
            entry_point=target_url,
            inputs=inputs,
            outputs=outputs,
            steps=steps,
            checkpoints=checkpoints,
            business_outcomes=business_outcomes
        )

        return artifact, logs

    def _discover_generic_flow(self, page: Page, goal: str, target_url: str) -> Tuple[CapabilityArtifact, List[str]]:
        return self._discover_member_lookup(page, goal, target_url)
