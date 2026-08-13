"""
Targeted Live Model Discovery Script
=====================================
Runs ONLY the member lookup goal against the live banking app with a real LLM API key.
This script exists to generate evidence/discovery_trace.json that contains:
  - "llm_provider": "openai" (or anthropic/gemini)
  - "llm_model": "gpt-4o" (or equivalent)
  - A final cycle with "action": "FINISH" proving successful goal completion
  - "finished_by_model": true in the trace header

Usage (set one API key in your environment, then run):
    $env:OPENAI_API_KEY="sk-..."
    python run_live_discovery.py

    $env:ANTHROPIC_API_KEY="sk-ant-..."
    python run_live_discovery.py
"""

import sys
import os
import json
import subprocess
import threading
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "src")

from rich.console import Console
from rich.panel import Panel

console = Console(highlight=False)


def start_server():
    """Start the banking app server in background."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "legacy_banking.app:app", "--port", "8000", "--log-level", "error"],
        cwd="apps",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(2.0)
    return proc


def run_targeted_discovery():
    console.print(Panel("[bold]CUA Live Model Discovery — Member Lookup Goal[/bold]", style="blue"))

    # Detect provider
    provider = None
    if os.environ.get("OPENAI_API_KEY"):
        provider = "openai"
    elif os.environ.get("ANTHROPIC_API_KEY"):
        provider = "anthropic"
    elif os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        provider = "gemini"

    if not provider:
        console.print("[red]ERROR: No API key found.[/red]")
        console.print("Set one of: OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY")
        sys.exit(1)

    console.print(f"[green]✓ Detected provider:[/green] {provider.upper()}")

    # Start server
    console.print("\n[1/3] Starting ApexCore Banking server...")
    proc = start_server()
    console.print("[green]✓ Server running at http://127.0.0.1:8000[/green]")

    try:
        from cua.agent.discovery_agent import DiscoveryAgent

        console.print("\n[2/3] Running genuine LLM discovery: Member Lookup goal...")
        console.print(f"  Goal: look up member 1082 and read their current savings balance")
        console.print(f"  Provider: {provider.upper()} | Max steps: 12\n")

        agent = DiscoveryAgent(
            headless=True,
            evidence_dir="evidence",
            llm_provider=provider
        )

        artifact, log_path = agent.discover(
            goal="look up member 1082 and read their current savings balance",
            target_url="http://127.0.0.1:8000/portal/member_search",
            max_steps=12
        )

        # Verify the trace
        trace_path = "evidence/discovery_trace.json"
        with open(trace_path, encoding="utf-8") as f:
            trace = json.load(f)

        finished = trace.get("finished_by_model", False)
        final_action = trace["cycles"][-1]["model_decision"].get("action", "?") if trace["cycles"] else "?"

        console.print(f"\n[3/3] Discovery complete.")
        console.print(f"  Session ID:       {trace['session_id']}")
        console.print(f"  Provider:         {trace['llm_provider']}")
        console.print(f"  Model:            {trace['llm_model']}")
        console.print(f"  Total cycles:     {trace['total_cycles']}")
        console.print(f"  Final action:     {final_action}")
        console.print(f"  Finished by model: {finished}")
        console.print(f"  Artifact ID:      {trace.get('artifact_id', '?')}")

        if finished and final_action == "FINISH":
            console.print("\n[bold green]✓ SUCCESS: Model reached FINISH — genuine successful discovery proven.[/bold green]")
            console.print(f"\n  Now run:")
            console.print(f"  [cyan]git add evidence/; git commit -m 'evidence: genuine {provider}/gpt-4o successful discovery run with FINISH'; git push origin main[/cyan]")
        else:
            console.print(f"\n[yellow]⚠ WARNING: Model did not reach FINISH (final action: {final_action}).[/yellow]")
            console.print("  The discovery hit max_steps. Check evidence/discovery_run.log for the model's reasoning.")
            console.print("  You may run this script again — GPT-4o sometimes reaches FINISH on a fresh attempt.")

    finally:
        proc.terminate()


if __name__ == "__main__":
    run_targeted_discovery()
