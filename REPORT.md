# Design Report: Computer-Use Automation System (CUA)
**Author:** Sasank  
**Submission Target:** interface.ai Engineering Team  

---

## 1. Architecture

### System Purpose & Core Paradigm
In US banking and credit union operations, core banking systems (e.g., FIS, Fiserv, Jack Henry) and internal servicing consoles lack public or unified APIs. These applications are characterized by stable, slowly changing UIs, but frequent and legitimate runtime business errors (*record not found*, *AML/compliance holds*, *interstitial security banners*, *timeout modals*).

Our architecture is anchored on a two-phase decoupled model:
1. **Phase 1: Discovery (LLM in the Loop)**: An agent navigates a live surface using an Observe $\rightarrow$ Decide $\rightarrow$ Act loop to achieve a natural language goal. It inspects the Accessibility Object Model (AOM), form controls, visual anchors, and layout geometry. It parameterizes concrete inputs and outputs, identifies checkpoints and error signatures, and compiles a typed **Capability Artifact**.
2. **Phase 2: Replay Engine (Zero LLM Tokens)**: Production execution relies exclusively on deterministic replay. When an upstream AI agent or service triggers a capability, the replay engine executes the recorded flow without re-invoking the model.

```
+---------------------------------------------------------------------------------------------------+
|                                    Upstream AI Agent / Caller                                     |
|                       (Goal: "Look up Member 1082 and extract savings balance")                   |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                    +-----------------------------+-----------------------------+
                    |                                                           |
                    v (Discovery Mode)                                          v (Production Mode)
     +------------------------------+                            +------------------------------+
     |   Goal-Driven Agent Loop     |                            |   Deterministic Replay       |
     | (Observe -> Decide -> Act)   |                            |   Execution Engine           |
     | - Live Browser Interaction   |                            | - 0 LLM Tokens in Loop       |
     | - Multi-Strategy Locators    |                            | - Parameter Substitution     |
     | - Parameter Inference        |                            | - Fallback Locator Hierarchy |
     | - Checkpoints & Outcomes     |                            | - Strict Outcome Taxonomy    |
     +--------------+---------------+                            +--------------+---------------+
                    |                                                           |
                    v                                                           v
     +------------------------------+                            +------------------------------+
     | Capability Artifact Compiler |                            |   Outcome & Safety Parser    |
     | - Type & Schema Validation   |                            | - Success vs Business Outcome|
     | - PII Scrubbing / Redaction  +--------> [ CAPABILITY ] <--+ - Checkpoint Verification    |
     +------------------------------+          [  ARTIFACT  ]    +--------------+---------------+
                                               [ (JSON/YAML)]                   |
                                                                                | (On Hard Failure / Stuck)
                                                                                v
                                                                 +------------------------------+
                                                                 |    HITL Escalation Manager   |
                                                                 | - Live Browser Context Pause |
                                                                 | - Operator Handoff & Log     |
                                                                 | - Resumption on Same Session |
                                                                 +------------------------------+
```

### Key Decisions & Trade-Offs

| Architectural Decision | Choice Made | Rationale & Trade-Offs |
| :--- | :--- | :--- |
| **Execution Decoupling** | Pure separation between Discovery and Replay | Calling an LLM on every production step introduces latency variance, non-determinism, and unnecessary token costs. Recording a typed artifact once enables sub-second deterministic replays with full auditability. |
| **Locator Strategy** | Multi-strategy prioritized tuples (*AOM $\rightarrow$ Label $\rightarrow$ Placeholder $\rightarrow$ Text $\rightarrow$ CSS $\rightarrow$ XPath $\rightarrow$ Visual Anchor*) | Legacy banking UIs rarely have `data-testid`. Relying solely on raw CSS/XPath is brittle to DOM nesting changes; relying solely on vision is computationally heavy. Multi-tier accessibility + visual anchoring provides resilience against table nesting while running at native speeds. |
| **Target Application** | Embedded realistic legacy core banking web portal (*ApexCore v4.8.2*) | Built-in non-semantic table layouts, frames, security interstitials, and explicit business outcome states (`MEM-9999`, `MEM-LOCKED`). Provides 100% reproducible, zero-external-dependency evaluation. |
| **Process Model** | In-process Playwright browser context with async event-driven orchestration | Avoids heavyweight distributed queues for local predictability while cleanly exposing seams for remote worker pools. |

---

## 2. Artifact Schema

The Capability Artifact schema (`src/cua/models/capability.py`) represents a typed, versioned, agent-invocable capability contract.

### Schema Blueprint
```json
{
  "schema_version": "1.0.0",
  "capability_id": "core_banking.member_lookup",
  "name": "Core Banking Member Lookup & Balance Inquiry",
  "description": "Searches a CIF member record and extracts demographic summary and deposit balances.",
  "metadata": {
    "created_at": "2026-08-13T20:34:00Z",
    "discovered_by": "CUA Discovery Agent v1.0",
    "source_goal": "look up member 1082 and read their current savings balance",
    "tenant_scope": "GLOBAL_APEXCORE",
    "vendor_product": "ApexCore Banking",
    "version": "1.0.0"
  },
  "entry_point": "http://127.0.0.1:8000/portal/member_search",
  "inputs": [
    {
      "name": "member_id",
      "type": "string",
      "description": "Unique core banking CIF member identifier",
      "required": true,
      "default": "MEM-1082",
      "redaction_class": "MEMBER_ID"
    }
  ],
  "outputs": [
    {
      "name": "savings_balance",
      "type": "string",
      "description": "Current ledger balance of High Yield Savings sub-account",
      "target_locator": {
        "css_selector": "tr[data-account-type='High Yield Savings'] .account-balance",
        "visual_anchor": "High Yield Savings"
      }
    }
  ],
  "steps": [
    {
      "step_id": "step_1_input_member_id",
      "description": "Enter target CIF Member Identifier into search textbox",
      "action_type": "FILL",
      "target": {
        "primary_role": "textbox",
        "placeholder": "e.g. MEM-1082",
        "label_text": "Member Identifier (CIF#):",
        "css_selector": "#txtMemberId"
      },
      "param_binding": "member_id",
      "risk_level": "SAFE_READ"
    }
  ],
  "checkpoints": [ ... ],
  "business_outcomes": [
    {
      "outcome_code": "MEMBER_NOT_FOUND",
      "description": "Record Not Found in core CIF partition",
      "trigger_locator": { "css_selector": "#error-code-badge", "text_content": "MEMBER_NOT_FOUND" }
    }
  ],
  "recoverable_conditions": [
    {
      "condition_id": "rec_security_notice",
      "detection_locator": { "css_selector": "#security-notice-interstitial" },
      "recovery_action": "CLICK",
      "recovery_target": { "css_selector": "#btn-ack-interstitial" }
    }
  ]
}
```

### Why It Is Shaped This Way
1. **Contract Over Script**: It is not a flat list of clicks. It defines input types, extraction shapes, and preconditions so an upstream AI agent or tool caller knows how to invoke it and what to expect in return.
2. **Decoupled from Raw Model Traces**: Raw model scratchpads contain conversational drift. The compiled artifact isolates pure operational mechanics.
3. **Explicit Business & Recoverable States**: Incorporates first-class models for `business_outcomes` and `recoverable_conditions` so runtime variations do not trigger unhandled exceptions.
4. **Fine-Grained Risk Annotations**: Every step carries a `RiskLevel` (`SAFE_READ`, `SAFE_WRITE`, `IRREVERSIBLE_MUTATION`) to govern safety policy enforcement and confirmation gates.

---

## 3. Determinism & Error Handling

### 1. Robust Element Targeting Hierarchy
When replaying against legacy software, standard selectors fail due to table layout changes, auto-generated IDs, and framesets. The `LocatorResolver` resolves elements using ranked fallbacks:
1. **Accessibility Role + Accessible Name (AOM)**: `page.get_by_role(role, name=name)` — mirrors how assistive technologies and human eyes locate controls.
2. **Label Association**: `page.get_by_label(text)` — identifies inputs bound to text labels.
3. **Placeholder & Visible Text**: `page.get_by_placeholder()` / `page.get_by_text()` — resilient to markup alterations.
4. **Visual Anchor Proximity**: Finds relative controls within the same row/container as neighboring anchor text (e.g. locating the input adjacent to `"Member Identifier (CIF#):"`).
5. **CSS Selector & XPath**: Low-level DOM fallbacks with automated timeout bounding.

### 2. Explicit Error & Outcome Taxonomy
The system explicitly separates 4 runtime conditions:

```
                                  [ Replay Engine Step ]
                                             |
                     +-----------------------+-----------------------+
                     |                                               |
              (Normal Step)                                   (State Change)
                     |                                               |
             +-------v-------+                       +---------------v---------------+
             | Element Found |                       | Transient Popup / Banner?     |
             +-------+-------+                       +---------------+---------------+
                     |                                               | YES
             +-------v-------+                                       v
             | Execute Action|                       [ Recoverable Interstitial ]
             +-------+-------+                       (Dismiss & Continue Replay)
                     |
     +---------------+---------------+
     |                               |
     v                               v
(Success State)              (Exception State)
     |                               |
     v                               +-------------------------------+
[ SUCCESS ]                          |                               |
(Outputs Extracted)                  v                               v
                          [ BUSINESS OUTCOME ]               [ HARD FAILURE ]
                          - MEMBER_NOT_FOUND                 - Missing element
                          - COMPLIANCE_HOLD                  - Network dropped
                          - INSUFFICIENT_FUNDS               (Trigger HITL Escalation)
                          (Report typed domain result)
```

1. **Success (`SUCCESS`)**: All steps executed, checkpoints verified, declared outputs extracted and type-validated.
2. **Expected Business Outcomes (`BUSINESS_OUTCOME`)**: The application legitimately produced an expected business exception (e.g., `MEMBER_NOT_FOUND`, `COMPLIANCE_HOLD_BLOCKED`). The engine captures the outcome code, message, and screenshot, reporting it as a typed result rather than an unhandled system crash.
3. **Recoverable Conditions (`RECOVERED_AUTOMATICALLY`)**: Transient roadblocks (e.g. daily security notice modals, session banners) are automatically detected and dismissed by `OutcomeEvaluator.handle_recoverable_conditions` before resuming the step.
4. **Hard Failures (`HARD_FAILURE`)**: Unhandled DOM drift, missing controls, or broken network states. Pauses execution, captures full diagnostics (DOM dump, screenshot, trace), and triggers HITL escalation.

---

## 4. Heterogeneity & Multi-Tenant

### Surface Abstraction Seam
To scale beyond modern web browsers to legacy framesets, terminal emulators (TN3270 / AS400), and desktop applications (WPF/WinForms/Java Swing):

```
+-----------------------------------------------------------------------------------+
|                        Unified Capability Artifact Contract                       |
|          (Goal, Inputs, Outputs, Checkpoints, Steps, Business Outcomes)           |
+-----------------------------------------+-----------------------------------------+
                                          |
                   +----------------------+----------------------+
                    |                                             |
                   v                                             v
    [ Web Surface Driver ]                         [ Desktop / OS Surface Driver ]
    (Playwright / CDP / AOM)                       (Windows UI Automation / pywinauto)
    - Role / Accessible Name                       - ControlType (Edit, Button, DataItem)
    - ARIA Labels / Text                           - AutomationId / Name property
    - Frame Locators (iframes)                     - Coordinate Bounding Box Fallback
```

The seam lies between the **Capability Contract** and the **Surface Driver Interface**:
- A step action `FILL(target, value)` is abstract.
- On Web: mapped to `page.locator().fill(val)`.
- On Desktop: mapped to Windows UI Automation `ValuePattern.SetValue(val)` or `SendKeys`.
- On Mainframe/Terminal: mapped to `screen.write_field(row, col, val)`.

### Multi-Tenant Reuse & Drift Management
Hundreds of financial institutions use identical underlying vendor packages (e.g., ApexCore, Symitar, CorePRO) configured with custom styling, custom branding, or minor layout differences.
1. **Base Capability Artifact**: Captures the canonical workflow and semantic control definitions.
2. **Tenant Specialization Layer (`CrossTenantAdapter`)**: Applies declarative overrides per institution:
   - `entry_point_override`: Base URL for tenant instance (e.g., `https://core.fcu-national.org/`).
   - `step_locator_overrides`: Custom selectors if a specific tenant customized a button or form.
   - `default_param_overrides`: Tenant-specific default values (e.g., branch code).
3. **Drift Detection**: When replay confidence scores drop below a threshold or fallback locator frequency increases, the system flags the artifact for automated discovery refresh.

---

## 5. Escalation & Handoff

### Stuck Detection
The engine identifies that automation is blocked when:
- All prioritized locator fallbacks fail for a non-optional step after timeout.
- A critical checkpoint assertion fails.
- An unknown modal or unhandled error state is present on the surface.
- A high-risk action (`IRREVERSIBLE_MUTATION`) triggers a policy confirmation gate.

### Control-Transfer Model & Live Session Seam
The system implements a true **Live Session Handoff** rather than restarting from a fresh session:

```
[ Automation Active ]
  (Holding live Playwright Browser Context & authenticated session cookies)
       |
       v (Failure detected at Step N)
[ 1. Freeze Automation Execution ]
       |
       v
[ 2. Generate HumanInterventionRequest ]
  - Intervention ID (INT-1F8653D8)
  - Failing Step ID & Reason
  - Live Screenshot & Redacted DOM Snippet
  - Suggested Remediation Action
       |
       v
[ 3. Transfer Control Token: AUTOMATION -> HUMAN_OPERATOR ]
       |
       v
[ 4. Operator Interacts Directly on the Live Session ]
  - Solves challenge, dismisses unexpected popup, or enters credentials
  - Records operator ID and resolution notes
       |
       v
[ 5. Operator Signals Completion ]
       |
       v
[ 6. Reclaim Control Token: HUMAN_OPERATOR -> AUTOMATION ]
       |
       v
[ 7. Resume Execution on Same Browser Session ]
```

All human interventions are recorded directly in the execution evidence audit trail (`ReplayResult.human_interventions`), guaranteeing regulatory compliance.

---

## 6. Safety

### Guardrail Model
Financial automation requires defense-in-depth:

```
+-----------------------------------------------------------------------------------+
|                            Incoming Action / Navigation                           |
+-----------------------------------------+-----------------------------------------+
                                          |
                   +----------------------+----------------------+
                   |                                             |
                   v                                             v
        [ Domain & Route Allowlist ]                  [ Action & Risk Filter ]
        - Allowed: 127.0.0.1, localhost               - Permitted: NAVIGATE, CLICK, FILL, etc.
        - Blocked: /admin/wipe, /debug/exec           - Prohibited: Raw eval, arbitrary OS exec
                   |                                             |
                   +----------------------+----------------------+
                                          |
                                          v
                              [ Risk Classification ]
                              - SAFE_READ: Auto-approved
                              - SAFE_WRITE: Verified bounds
                              - IRREVERSIBLE: Gated & Logged
                                          |
                                          v
                           [ PII & Secret Redaction Engine ]
                           - SSN: \d{3}-\d{2}-\d{4} -> [REDACTED_SSN]
                           - Card #: (?:\d{4}[ -]?){3}\d{4} -> [REDACTED_CARD_NUMBER]
                           - Passwords & Auth Tokens Masked
```

1. **Domain & Route Allowlist**: Enforces strict URL bounds (`127.0.0.1`, `localhost`, institution domain). Navigation attempts to unauthorized domains raise `SecurityViolationError`.
2. **Action Permissions**: Disallows unsafe scripting, unauthorized downloads, or arbitrary code execution.
3. **Risk Categorization**:
   - `SAFE_READ`: Idempotent data queries (auto-approved).
   - `SAFE_WRITE`: Standard form entry and filtering.
   - `IRREVERSIBLE_MUTATION`: Fund transfers, account openings, profile updates.
4. **Zero Secret Persistence & PII Redaction**: The `RedactionEngine` scrubs SSNs, card numbers, passwords, bearer tokens, emails, and phone numbers before writing to logs, traces, or artifacts.

### Boundaries & Limits
- *Client-side limits*: While client-side allowlists block unauthorized URLs, network-level firewall proxies and role-based access tokens are recommended in production environments.

---

## 7. Cuts

### Deliberately Left Out (and Justification)
1. **Full Real-Time WebSocket Co-Browsing UI**: Building a full WebRTC/VNC remote desktop console was cut in favor of a clean, real live session handoff seam with structured CLI/callback hooks.
2. **Distributed Queue Infrastructure (Kafka/Celery/Redis)**: Omitted premature distributed orchestration infrastructure in favor of clean in-process execution modules with well-defined serialization interfaces.
3. **Multi-Model LLM Benchmark Suite**: Standardized the discovery layer on modern vision/DOM agent loops rather than writing bespoke adapters for 10 different model providers.

### What We Would Build Next
1. **Automated Capability Drift Self-Healing**: If a replay fails because a vendor updated their UI, automatically spin up a bounded single-step LLM healing run, re-verify the checkpoint, and propose a versioned patch (`1.0.0` $\rightarrow$ `1.0.1`).
2. **Computer Vision Coordinate Fallback for Canvas/Citrix**: Integrate OmniParser / YOLO bounding box model for non-DOM remote desktop streams where zero accessibility tree exists.
3. **Shadow Mode & Canary Replay Pipeline**: Replay new capability artifacts in shadow mode against staging cores to compute flakiness and reliability scores prior to promotion to `APPROVED` production catalog status.

---

## 8. Verification & Demonstration Evidence Summary

All end-to-end capabilities have been verified and documented in `/evidence/`:

| Artifact / Log File | Evidence Description | Validation Outcome |
| :--- | :--- | :--- |
| [`capability_member_lookup.json`](evidence/capability_member_lookup.json) | Discovered Member Lookup Capability Artifact | Typed JSON schema with inputs, outputs, locators |
| [`capability_open_subaccount.json`](evidence/capability_open_subaccount.json) | Discovered Sub-Account Origination Artifact | Multi-step mutation flow with checkpoints |
| [`discovery_run.log`](evidence/discovery_run.log) | Discovery Agent Observe-Decide-Act Trace | Complete live UI interaction trace |
| [`run_core_banking.member_lookup_RUN-31FCB450.log`](evidence/run_core_banking.member_lookup_RUN-31FCB450.log) | Deterministic Replay: Happy Path (`MEM-1082`) | Succeeded cleanly; extracted balances |
| [`run_core_banking.member_lookup_RUN-2882C84A.log`](evidence/run_core_banking.member_lookup_RUN-2882C84A.log) | Deterministic Replay: Not Found (`MEM-9999`) | Detected `MEMBER_NOT_FOUND` business outcome |
| [`run_core_banking.member_lookup.hitl_test_RUN-D2982CD3.log`](evidence/run_core_banking.member_lookup.hitl_test_RUN-D2982CD3.log) | HITL Live Session Escalation & Resume Trace | Paused live session, logged human handoff, resumed |
| [`standalone_member_lookup.py`](evidence/standalone_member_lookup.py) | Code Generation Stretch Goal | Compiled standalone runnable Playwright script |
| [`evidence/screenshots/`](evidence/screenshots/) | Step & Outcome Screenshots | Visual evidence across discovery and replay runs |
