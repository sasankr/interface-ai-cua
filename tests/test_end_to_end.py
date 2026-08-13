"""
End-to-end integration tests for Discovery and Deterministic Replay.
"""

import os
import sys
import time
import threading
import pytest
import requests
import uvicorn

from apps.legacy_banking.app import app as bank_app
from cua.agent.discovery_agent import DiscoveryAgent
from cua.replay.replay_engine import ReplayEngine
from cua.models.execution import ExecutionStatus

PORT = 8899
BASE_URL = f"http://127.0.0.1:{PORT}"


@pytest.fixture(scope="session", autouse=True)
def run_test_server():
    t = threading.Thread(
        target=uvicorn.run,
        args=(bank_app,),
        kwargs={"host": "127.0.0.1", "port": PORT, "log_level": "error"},
        daemon=True
    )
    t.start()
    for _ in range(30):
        try:
            r = requests.get(BASE_URL)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.1)
    yield


def test_discovery_and_replay_happy_path(tmp_path):
    evidence_dir = str(tmp_path / "evidence")
    discovery = DiscoveryAgent(headless=True, evidence_dir=evidence_dir)
    artifact, log_path = discovery.discover(
        goal="look up member 1082 and read savings balance",
        target_url=f"{BASE_URL}/portal/member_search"
    )

    assert artifact.capability_id == "core_banking.member_lookup"
    assert len(artifact.steps) >= 2

    # Deterministic replay with inputs
    replay = ReplayEngine(headless=True, evidence_dir=evidence_dir)
    res = replay.execute(artifact, inputs={"member_id": "MEM-1082"})

    assert res.status == ExecutionStatus.SUCCESS, f"Replay failed with error: {res.error_code} - {res.error_message} (Failed step: {res.failed_step_id})"
    assert res.outputs_extracted.get("savings_balance") == "$18,940.25"
    assert res.outputs_extracted.get("member_name") == "Eleanor Vance"


def test_replay_business_outcome_not_found(tmp_path):
    evidence_dir = str(tmp_path / "evidence")
    discovery = DiscoveryAgent(headless=True, evidence_dir=evidence_dir)
    artifact, _ = discovery.discover(
        goal="look up member 1082 and read savings balance",
        target_url=f"{BASE_URL}/portal/member_search"
    )

    replay = ReplayEngine(headless=True, evidence_dir=evidence_dir)
    res = replay.execute(artifact, inputs={"member_id": "MEM-9999"})

    assert res.status == ExecutionStatus.BUSINESS_OUTCOME
    assert res.business_outcome_code == "MEMBER_NOT_FOUND"
    assert "No active member" in res.business_outcome_message
