# Computer-Use Automation System (CUA)
### Deterministic UI Automation & Replay Engine for Legacy Banking Software

Built for the **interface.ai** take-home challenge.

---

## 1. Executive Summary

This system bridges the gap between autonomous AI agents and back-office banking software that lacks APIs (legacy core banking systems, servicing consoles, and green-screen web portals).

### Core Thesis
> **The Model Discovers. The Artifact Becomes a Reusable Capability. Deterministic Replay Executes in Production (0 LLM Tokens).**

1. **Phase 1 (Discovery Engine)**: An LLM-driven Observe $\rightarrow$ Decide $\rightarrow$ Act loop drives a live application surface to accomplish a goal, recording multi-strategy resilient locators, parameter bindings, checkpoints, and business outcome rules.
2. **Capability Artifact**: Emits a typed, versioned JSON contract specifying input parameters, output extraction schemas, assertion checkpoints, recoverable interstitials, and security policies.
3. **Phase 2 (Deterministic Replay)**: Production execution engine that executes the artifact with 100% determinism (zero LLM in the loop), robust fallback locators, and typed outcome classification (*Success*, *Business Outcome*, *Recoverable Retry*, *Hard Failure*, *Safety Violation*).
4. **Human-in-the-Loop (HITL) Handoff**: If execution gets stuck or encounters an unhandled roadblock, the engine pauses the live Playwright browser session, transfers control to a human operator, records the manual intervention, and cleanly resumes.

---

## 2. Quickstart & Installation

### Prerequisites
- Python 3.10+
- Chromium browser (via Playwright)

### Setup
```bash
# 1. Clone or navigate to the repository
cd cua_system

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Playwright browser binaries
playwright install chromium
```

---

## 3. Demo Path (One-Click End-to-End Execution)

Run the full end-to-end demonstration script that launches the local legacy core banking portal, executes goal discovery, replays the happy path, detects business exceptions, tests HITL escalation, and dumps all logs and screenshots to `/evidence/`:

```bash
python run_demo.py
```

### Running Automated Test Suite
```bash
python -m pytest -v
```

---

## 4. CLI Usage & Commands

The system provides a unified CLI (`cli.py`):

### A. Run Goal Discovery
```bash
python cli.py discover --goal "look up member 1082 and read their current savings balance" --target "http://127.0.0.1:8000/portal/member_search" --output "evidence/capability_member_lookup.json"
```

### B. Deterministic Replay (Happy Path)
```bash
python cli.py replay --artifact "evidence/capability_member_lookup.json" --inputs '{"member_id": "MEM-1082"}'
```

### C. Deterministic Replay (Business Exception / Not Found)
```bash
python cli.py replay --artifact "evidence/capability_member_lookup.json" --inputs '{"member_id": "MEM-9999"}'
```

### D. Inspect Agent-Facing Tool Catalog (Stretch Goal)
```bash
python cli.py catalog list
python cli.py catalog tools
```

### E. Compile Capability to Standalone Playwright Test Script (Stretch Goal)
```bash
python cli.py export --artifact "evidence/capability_member_lookup.json" --output "evidence/standalone_member_lookup.py"
```

### F. Launch Standalone Legacy Core Banking Portal
```bash
python cli.py server --port 8000
```

---

## 5. Repository Structure

```
cua_system/
├── apps/
│   └── legacy_banking/            # Realistic target application (ApexCore v4.8.2)
│       ├── app.py                 # FastAPI backend with mock CIF database & rules
│       └── templates/             # Non-semantic table layouts, forms, error pages
├── src/
│   └── cua/
│       ├── models/                # Typed Pydantic schemas (Capability, Execution, Safety)
│       │   ├── capability.py      # Versioned Capability Artifact Contract
│       │   ├── execution.py       # Replay results & HITL request models
│       │   └── safety.py          # Security profiles
│       ├── agent/                 # Discovery Agent (Observe -> Decide -> Act)
│       │   ├── discovery_agent.py # Live browser discovery runner
│       │   ├── prompts.py         # System prompts & AOM analysis
│       │   └── recorder.py        # Artifact compiler & parameter synthesizer
│       ├── replay/                # Deterministic Replay Engine
│       │   ├── replay_engine.py   # Production zero-LLM executor
│       │   ├── locator.py         # Multi-strategy resilient locator resolver
│       │   └── outcome_evaluator.py # Business outcome & checkpoint analyzer
│       ├── safety/                # Guardrails & Redaction
│       │   ├── guardrails.py      # Domain allowlist & mutation risk analyzer
│       │   └── redactor.py        # PII / Secret / SSN redaction engine
│       ├── hitl/                  # Human-in-the-loop escalation
│       │   └── escalation.py      # Live session handoff & state resumption
│       ├── observability/         # Observability & logging
│       │   └── evidence.py        # Structured JSONL/log & trace exporter
│       └── catalog/               # Agent tools & codegen
│           ├── tool_catalog.py    # OpenAI/Anthropic tool schema exporter
│           ├── codegen.py         # Standalone Playwright script compiler
│           └── cross_tenant.py    # Multi-tenant specialization adapter
├── evidence/                      # Generated capability artifacts, logs, screenshots
├── tests/                         # Pytest test suite (unit + end-to-end integration)
├── cli.py                         # CLI entry point
├── run_demo.py                    # Complete end-to-end demonstration runner
├── REPORT.md                      # Comprehensive design write-up (7 mandatory sections)
└── requirements.txt               # Dependencies
```
