"""
Safety models and policies for CUA operations.
"""

from typing import List, Pattern, Set
from pydantic import BaseModel, Field


class SecurityProfile(BaseModel):
    profile_name: str = "BANKING_STRICT"
    allowed_hosts: Set[str] = {"127.0.0.1", "localhost"}
    blocked_url_patterns: List[str] = [
        r"/admin/wipe_database",
        r"/debug/exec",
        r"/system/shutdown"
    ]
    prohibited_actions: Set[str] = {"EXECUTE_SCRIPT_UNSAFE"}
    max_retries_per_step: int = 3
    enforce_pii_redaction: bool = True
    mask_financial_inputs: bool = True
