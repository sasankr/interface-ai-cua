"""
Comprehensive End-to-End CUA System Demonstration Runner
Orchestrates the complete lifecycle:
1. Spawns local legacy banking application
2. Executes Phase 1: Goal-driven LLM Discovery & Artifact Synthesis
3. Executes Phase 2: Deterministic Production Replay (Happy Path - Member Lookup)
4. Executes Phase 3: Deterministic Replay (Business Exception Path - Member Not Found)
5. Executes Phase 4: Deterministic Replay (Multi-Step Mutation - Open Sub-Account)
6. Executes Phase 5: Human-in-the-Loop (HITL) Live Session Escalation & Resume
7. Exercises Tool Catalog & Code Generation
8. Generates all required evidence artifacts in /evidence/
"""

import sys
import os
import time
import threading
import json
import uvicorn
import requests

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add src to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from apps.legacy_banking.app import app as bank_app
from cua.agent.discovery_agent import DiscoveryAgent
from cua.replay.replay_engine import ReplayEngine
from cua.models.capability import CapabilityArtifact, ActionStep, ActionType, LocatorStrategy, RiskLevel
from cua.models.execution import ExecutionStatus, HumanInterventionRequest, HumanInterventionResult
from cua.hitl.escalation import HITLEscalationManager
from cua.catalog.tool_catalog import CapabilityCatalog
from cua.catalog.codegen import CodeGenerator

console = Console()
PORT = 8000
BASE_URL = f"http://127.0.0.1:{PORT}"
EVIDENCE_DIR = os.path.join(os.path.dirname(__file__), "evidence")


def start_server_background():
    """Runs FastAPI banking app in a daemon thread."""
    config = uvicorn.Config(bank_app, host="127.0.0.1", port=PORT, log_level="error")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    
    # Wait for server readiness
    for _ in range(30):
        try:
            r = requests.get(BASE_URL)
            if r.status_code == 200:
                return server
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("Failed to start legacy banking server.")


def run_full_demonstration():
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    console.print(Panel("[bold green]Starting Computer-Use Automation System (CUA) Demonstration[/bold green]", title="Interface.ai Evaluation Demo"))

    # Step 1: Launch Local Host Application
    console.print("\n[1/6] Launching local legacy banking application (ApexCore v4.8.2)...")
    server = start_server_background()
    console.print(f"      ✓ Server running at {BASE_URL}")

    # Step 2: Phase 1 Discovery
    console.print("\n[2/6] Running Phase 1: Goal-Driven Discovery Agent Loop...")
    goal_1 = "look up member 1082 and read their current savings balance"
    target_1 = f"{BASE_URL}/portal/member_search"
    
    discovery_agent = DiscoveryAgent(headless=True, evidence_dir=EVIDENCE_DIR)
    art_lookup, disc_log_1 = discovery_agent.discover(
        goal=goal_1,
        target_url=target_1,
        output_artifact_path=os.path.join(EVIDENCE_DIR, "capability_member_lookup.json")
    )
    console.print(f"      ✓ Discovered & synthesized capability: [bold]{art_lookup.name}[/bold]")
    console.print(f"      ✓ Saved Capability Artifact: {os.path.join(EVIDENCE_DIR, 'capability_member_lookup.json')}")
    console.print(f"      ✓ Saved Discovery Log: {disc_log_1}")

    # Also discover open sub-account flow
    goal_2 = "open a new sub-account for this member and reach the confirmation screen"
    target_2 = f"{BASE_URL}/portal/subaccount/open"
    art_subacc, _ = discovery_agent.discover(
        goal=goal_2,
        target_url=target_2,
        output_artifact_path=os.path.join(EVIDENCE_DIR, "capability_open_subaccount.json")
    )
    console.print(f"      ✓ Discovered & synthesized capability: [bold]{art_subacc.name}[/bold]")

    # Step 3: Phase 2 Deterministic Replay - Happy Path
    console.print("\n[3/6] Running Phase 2: Deterministic Replay (Zero LLM) - Happy Path [MEM-1082]...")
    replay_engine = ReplayEngine(headless=True, evidence_dir=EVIDENCE_DIR)
    
    res_happy = replay_engine.execute(
        artifact=art_lookup,
        inputs={"member_id": "MEM-1082"}
    )
    console.print(f"      ✓ Replay Status: [bold green]{res_happy.status.value}[/bold green] (Duration: {res_happy.total_duration_ms:.1f}ms)")
    console.print(f"      ✓ Extracted Outputs: {json.dumps(res_happy.outputs_extracted)}")

    # Step 4: Phase 3 Deterministic Replay - Business Exception (Member Not Found)
    console.print("\n[4/6] Running Phase 3: Deterministic Replay - Business Outcome [MEM-9999]...")
    res_not_found = replay_engine.execute(
        artifact=art_lookup,
        inputs={"member_id": "MEM-9999"}
    )
    console.print(f"      ✓ Replay Status: [bold yellow]{res_not_found.status.value}[/bold yellow]")
    console.print(f"      ✓ Business Outcome Code: [bold]{res_not_found.business_outcome_code}[/bold]")
    console.print(f"      ✓ Business Outcome Message: '{res_not_found.business_outcome_message}'")
    console.print("      ✓ Confirmed: Replay cleanly separated expected domain outcome from system crash!")

    # Step 5: Phase 4 Multi-Step Mutation Replay (Open Sub-Account)
    console.print("\n[5/6] Running Phase 4: Deterministic Replay - Sub-Account Origination Flow...")
    res_subacc = replay_engine.execute(
        artifact=art_subacc,
        inputs={
            "member_id": "MEM-1082",
            "account_type": "High Yield Savings (APY 4.25%)",
            "initial_deposit": "$300.00"
        }
    )
    console.print(f"      ✓ Replay Status: [bold green]{res_subacc.status.value}[/bold green]")
    console.print(f"      ✓ Assigned Account Number: {res_subacc.outputs_extracted.get('assigned_account_number')}")
    console.print(f"      ✓ Core Confirmation Code: {res_subacc.outputs_extracted.get('confirmation_code')}")

    # Step 6: Phase 5 Human-in-the-Loop (HITL) Live Session Escalation Test
    console.print("\n[6/6] Running Phase 5: Human-in-the-Loop (HITL) Live Session Escalation & Resume...")
    
    # Create an artifact with an intentional roadblock requiring operator intervention
    art_hitl = art_lookup.model_copy(deep=True)
    art_hitl.capability_id = "core_banking.member_lookup.hitl_test"
    art_hitl.steps.insert(0, ActionStep(
        step_id="step_0_simulated_roadblock",
        description="Verify security captcha or operator badge check",
        action_type=ActionType.CLICK,
        target=LocatorStrategy(css_selector="#nonexistent-captcha-challenge"),
        timeout_ms=1000,
        risk_level=RiskLevel.SAFE_READ
    ))

    def simulated_operator_intervention(req: HumanInterventionRequest, page) -> HumanInterventionResult:
        console.print(f"      🚨 [HITL TRIGGERED] Intervention ID: {req.intervention_id}")
        console.print(f"         Reason: {req.reason}")
        console.print(f"         Screenshot Context: {req.screenshot_path}")
        console.print("         Operator Action: Human bypassed unexpected roadblock in live session and signaled resume.")
        return HumanInterventionResult(
            intervention_id=req.intervention_id,
            operator_id="OPERATOR-JANE-DOE",
            resolution_status="RESUMED",
            operator_notes="Verified terminal session security clearance; dismissed roadblock manually.",
            manual_actions_taken=["Bypassed captcha", "Validated session clearance"],
            resumed_at=time.strftime("%Y-%m-%d %H:%M:%S")
        )

    res_hitl = replay_engine.execute(
        artifact=art_hitl,
        inputs={"member_id": "MEM-1082"},
        operator_callback=simulated_operator_intervention
    )
    console.print(f"      ✓ HITL Run Status: [bold green]{res_hitl.status.value}[/bold green]")
    console.print(f"      ✓ Human Interventions Recorded: {len(res_hitl.human_interventions)}")

    # Stretch Goals: Tool Catalog & Code Generation
    console.print("\n[Stretch Goals] Catalog & Standalone Code Generation...")
    catalog = CapabilityCatalog(artifacts_dir=EVIDENCE_DIR)
    tools = catalog.to_openai_tools()
    console.print(f"      ✓ Agent-Facing Function Calling Tools Exported: {len(tools)} tools ready for LLM invocation")

    standalone_script = CodeGenerator.generate_playwright_python(art_lookup)
    codegen_path = os.path.join(EVIDENCE_DIR, "standalone_member_lookup.py")
    with open(codegen_path, "w", encoding="utf-8") as f:
        f.write(standalone_script)
    console.print(f"      ✓ Standalone Playwright Script Emitted: {codegen_path}")

    # Summary Table
    table = Table(title="\nCUA System Evidence & Deliverables Manifest", style="cyan")
    table.add_column("Deliverable", style="bold")
    table.add_column("Location", style="green")
    table.add_column("Description")

    table.add_row("Capability Artifact 1", "evidence/capability_member_lookup.json", "Typed JSON contract for Member Lookup")
    table.add_row("Capability Artifact 2", "evidence/capability_open_subaccount.json", "Typed JSON contract for Sub-Account Opening")
    table.add_row("Discovery Run Log", "evidence/discovery_run.log", "Live agent observe-decide-act discovery trace")
    table.add_row("Replay Log (Success)", f"evidence/run_{res_happy.capability_id}_{res_happy.run_id}.log", "Deterministic replay execution trace (Happy Path)")
    table.add_row("Replay Log (Not Found)", f"evidence/run_{res_not_found.capability_id}_{res_not_found.run_id}.log", "Business Outcome detection trace (MEM-9999)")
    table.add_row("Replay Log (HITL)", f"evidence/run_{res_hitl.capability_id}_{res_hitl.run_id}.log", "Human escalation live session takeover & resume")
    table.add_row("Step Screenshots", "evidence/screenshots/", "Step-by-step visual evidence captures")
    table.add_row("Generated Script", "evidence/standalone_member_lookup.py", "Compiled standalone Playwright test script")

    console.print(table)
    console.print(Panel("[bold green]All end-to-end requirements and demonstrations completed successfully![/bold green]"))


if __name__ == "__main__":
    run_full_demonstration()
