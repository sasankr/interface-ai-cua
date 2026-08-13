"""
CUA System Command-Line Interface (CLI)
Provides operators and agents with commands to discover, replay, inspect, and export capabilities.
"""

import sys
import os
import json

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add src to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from cua.agent.discovery_agent import DiscoveryAgent
from cua.replay.replay_engine import ReplayEngine
from cua.catalog.tool_catalog import CapabilityCatalog
from cua.catalog.codegen import CodeGenerator
from cua.models.capability import CapabilityArtifact
from cua.models.execution import ExecutionStatus

console = Console()


@click.group()
def cli():
    """Computer-Use Automation System (CUA) - Interface.ai"""
    pass


@cli.command("discover")
@click.option("--goal", "-g", required=True, help="Natural language goal to achieve.")
@click.option("--target", "-t", default="http://127.0.0.1:8000/portal/member_search", help="Target URL entry point.")
@click.option("--output", "-o", default=None, help="Output capability JSON artifact path.")
@click.option("--headless/--no-headless", default=True, help="Run browser in headless mode.")
def discover(goal: str, target: str, output: str, headless: bool):
    """Run goal-driven discovery loop against live UI to record a reusable capability."""
    console.print(Panel(f"[bold cyan]Starting CUA Discovery Loop[/bold cyan]\nGoal: [yellow]{goal}[/yellow]\nTarget: [green]{target}[/green]", title="Discovery Mode"))
    
    agent = DiscoveryAgent(headless=headless, evidence_dir="evidence")
    artifact, log_path = agent.discover(goal=goal, target_url=target, output_artifact_path=output)
    
    console.print(f"[bold green]✓ Discovery Completed Successfully![/bold green]")
    console.print(f"• Synthesized Capability: [bold]{artifact.name}[/bold] ({artifact.capability_id})")
    console.print(f"• Recorded Steps: {len(artifact.steps)}")
    console.print(f"• Defined Inputs: {[p.name for p in artifact.inputs]}")
    console.print(f"• Defined Outputs: {[o.name for o in artifact.outputs]}")
    console.print(f"• Execution Log: [blue]{log_path}[/blue]")


@cli.command("replay")
@click.option("--artifact", "-a", required=True, help="Path to Capability Artifact JSON file.")
@click.option("--inputs", "-i", default="{}", help="JSON string of input parameters.")
@click.option("--headless/--no-headless", default=True, help="Run browser in headless mode.")
def replay(artifact: str, inputs: str, headless: bool):
    """Replay a recorded capability deterministically with zero LLM in the loop."""
    if not os.path.exists(artifact):
        console.print(f"[bold red]Error:[/bold red] Artifact file '{artifact}' not found.")
        sys.exit(1)

    with open(artifact, "r", encoding="utf-8") as f:
        data = json.load(f)
        cap = CapabilityArtifact(**data)

    parsed_inputs = json.loads(inputs)
    console.print(Panel(f"[bold blue]Deterministic Production Replay[/bold blue]\nCapability: [bold]{cap.name}[/bold] ({cap.capability_id})\nInputs: {parsed_inputs}", title="Replay Engine"))

    engine = ReplayEngine(headless=headless, evidence_dir="evidence")
    result = engine.execute(cap, inputs=parsed_inputs)

    # Render result table
    table = Table(title="Replay Execution Result")
    table.add_column("Metric / Field", style="cyan")
    table.add_column("Value", style="bold")

    status_color = "green" if result.status == ExecutionStatus.SUCCESS else "yellow" if result.status == ExecutionStatus.BUSINESS_OUTCOME else "red"
    table.add_row("Execution Status", f"[{status_color}]{result.status.value}[/{status_color}]")
    table.add_row("Run ID", result.run_id)
    table.add_row("Total Duration", f"{result.total_duration_ms:.1f} ms")
    table.add_row("Extracted Outputs", json.dumps(result.outputs_extracted, indent=2))

    if result.business_outcome_code:
        table.add_row("Business Outcome", f"[{result.business_outcome_code}] {result.business_outcome_message}")
    if result.error_code:
        table.add_row("Error Diagnostics", f"[{result.error_code}] {result.error_message} (Step: {result.failed_step_id})")

    console.print(table)


@cli.group("catalog")
def catalog_group():
    """Agent-facing tool catalog management."""
    pass


@catalog_group.command("list")
@click.option("--dir", "-d", default="evidence", help="Artifacts directory.")
def list_catalog(dir: str):
    """List all registered capabilities in catalog."""
    catalog = CapabilityCatalog(artifacts_dir=dir)
    caps = catalog.list_capabilities()
    
    table = Table(title="Callable Capabilities Catalog")
    table.add_column("Capability ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Inputs", style="green")
    table.add_column("Outputs", style="magenta")

    for c in caps:
        inps = ", ".join([p["name"] for p in c["inputs"]])
        outs = ", ".join([o["name"] for o in c["outputs"]])
        table.add_row(c["capability_id"], c["name"], inps, outs)

    console.print(table)


@catalog_group.command("tools")
@click.option("--dir", "-d", default="evidence", help="Artifacts directory.")
def show_tools(dir: str):
    """Output standard OpenAI Tool / Function calling JSON schemas."""
    catalog = CapabilityCatalog(artifacts_dir=dir)
    tools = catalog.to_openai_tools()
    console.print_json(json.dumps(tools, indent=2))


@cli.command("export")
@click.option("--artifact", "-a", required=True, help="Capability artifact JSON file.")
@click.option("--output", "-o", default=None, help="Output python file path.")
def export_code(artifact: str, output: str):
    """Compile capability artifact into standalone Playwright Python test script."""
    with open(artifact, "r", encoding="utf-8") as f:
        data = json.load(f)
        cap = CapabilityArtifact(**data)

    py_code = CodeGenerator.generate_playwright_python(cap)
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(py_code)
        console.print(f"[bold green]✓ Exported standalone script to:[/bold green] {output}")
    else:
        console.print(py_code)


@cli.command("server")
@click.option("--port", "-p", default=8000, help="Server port.")
def run_server(port: int):
    """Start local mock legacy banking portal."""
    import uvicorn
    from apps.legacy_banking.app import app
    console.print(f"[bold green]Starting ApexCore Legacy Banking Host on http://127.0.0.1:{port}[/bold green]")
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    cli()
