"""
Capability Code Generator
Compiles a CapabilityArtifact into a standalone, runnable Playwright Python test script.
"""

from typing import Optional
from cua.models.capability import CapabilityArtifact, ActionType


class CodeGenerator:
    @classmethod
    def generate_playwright_python(cls, artifact: CapabilityArtifact) -> str:
        """Emits executable standalone Python code using Playwright sync API."""
        code_lines = []
        code_lines.append(f'"""')
        code_lines.append(f'Auto-Generated Playwright Test Script for: {artifact.name}')
        code_lines.append(f'Capability ID: {artifact.capability_id}')
        code_lines.append(f'Schema Version: {artifact.schema_version}')
        code_lines.append(f'"""\n')
        code_lines.append('from playwright.sync_api import sync_playwright\n')
        code_lines.append('def run_flow():')
        code_lines.append('    with sync_playwright() as p:')
        code_lines.append('        browser = p.chromium.launch(headless=False)')
        code_lines.append('        context = browser.new_context(viewport={"width": 1280, "height": 800})')
        code_lines.append('        page = context.new_page()')
        code_lines.append(f'        # Navigate to entry point')
        code_lines.append(f'        page.goto("{artifact.entry_point}")')
        code_lines.append('        page.wait_for_load_state("networkidle")\n')

        # Generate step code
        for step in artifact.steps:
            code_lines.append(f'        # {step.step_id}: {step.description}')
            if step.action_type == ActionType.FILL:
                val = step.value or f'{{inputs["{step.param_binding}"]}}'
                if step.target.css_selector:
                    code_lines.append(f'        page.locator("{step.target.css_selector}").fill("{val}")')
                elif step.target.placeholder:
                    code_lines.append(f'        page.get_by_placeholder("{step.target.placeholder}").fill("{val}")')
            elif step.action_type == ActionType.CLICK:
                if step.target.css_selector:
                    code_lines.append(f'        page.locator("{step.target.css_selector}").click()')
                elif step.target.accessible_name:
                    code_lines.append(f'        page.get_by_role("button", name="{step.target.accessible_name}").click()')
            elif step.action_type == ActionType.SELECT_OPTION:
                val = step.value or f'{{inputs["{step.param_binding}"]}}'
                if step.target.css_selector:
                    code_lines.append(f'        page.locator("{step.target.css_selector}").select_option(label="{val}")')
            
            if step.wait_after_ms > 0:
                code_lines.append(f'        page.wait_for_timeout({step.wait_after_ms})\n')

        # Checkpoints
        for cp in artifact.checkpoints:
            code_lines.append(f'        # Checkpoint: {cp.description}')
            if cp.target.css_selector:
                code_lines.append(f'        assert page.locator("{cp.target.css_selector}").is_visible(), "Checkpoint {cp.checkpoint_id} failed"')

        code_lines.append('\n        print("Capability execution completed successfully!")')
        code_lines.append('        browser.close()\n')
        code_lines.append('if __name__ == "__main__":')
        code_lines.append('    run_flow()')

        return "\n".join(code_lines)
