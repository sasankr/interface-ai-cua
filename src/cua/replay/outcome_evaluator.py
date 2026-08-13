"""
Outcome & Exception Evaluator
Distinguishes between:
1. Expected Business Outcomes (e.g., MEMBER_NOT_FOUND - legitimate domain outcome)
2. Recoverable Runtime States (e.g., Security popups / transient interstitials)
3. Checkpoints & State Assertions
"""

import re
from typing import List, Optional, Tuple
from playwright.sync_api import Page
from cua.models.capability import BusinessOutcomeRule, RecoverableCondition, CheckpointAssertion
from cua.replay.locator import LocatorResolver


class OutcomeEvaluator:
    @classmethod
    def check_business_outcomes(
        cls,
        page: Page,
        rules: List[BusinessOutcomeRule]
    ) -> Optional[Tuple[BusinessOutcomeRule, str]]:
        """
        Scans the current page for indicators of expected business exceptions.
        Returns the matched rule and extracted message, or None if on normal flow.
        """
        for rule in rules:
            try:
                element, _ = LocatorResolver.resolve(page, rule.trigger_locator, timeout_ms=1000)
                if element and element.is_visible():
                    extracted_text = element.text_content() or ""
                    # Check if there is a detailed message element on page
                    detail_elem = page.locator("#error-message")
                    if detail_elem.count() > 0 and detail_elem.first.is_visible():
                        extracted_text = detail_elem.first.text_content() or extracted_text

                    if rule.expected_text_pattern:
                        if re.search(rule.expected_text_pattern, element.text_content() or "", re.IGNORECASE):
                            return rule, extracted_text.strip()
                    else:
                        return rule, extracted_text.strip()
            except Exception:
                continue
        return None

    @classmethod
    def handle_recoverable_conditions(
        cls,
        page: Page,
        conditions: List[RecoverableCondition]
    ) -> List[str]:
        """
        Detects and clears transient obstacles (e.g. dismissing an interstitial banner).
        Returns list of condition IDs recovered.
        """
        handled = []
        for cond in conditions:
            for _ in range(cond.max_retries):
                try:
                    elem, _ = LocatorResolver.resolve(page, cond.detection_locator, timeout_ms=800)
                    if elem and elem.is_visible():
                        if cond.recovery_target:
                            rec_target, _ = LocatorResolver.resolve(page, cond.recovery_target, timeout_ms=1000)
                            rec_target.click()
                        else:
                            elem.click()
                        page.wait_for_timeout(300)
                        handled.append(cond.condition_id)
                        break
                except Exception:
                    break
        return handled

    @classmethod
    def verify_checkpoint(cls, page: Page, checkpoint: CheckpointAssertion) -> bool:
        """Verifies checkpoint assertion."""
        try:
            elem, _ = LocatorResolver.resolve(page, checkpoint.target, timeout_ms=2500)
            if not elem.is_visible():
                return False
            
            if checkpoint.assertion_type == "TEXT_CONTAINS" and checkpoint.expected_value:
                content = elem.text_content() or ""
                return checkpoint.expected_value.lower() in content.lower()
            elif checkpoint.assertion_type == "NOT_EMPTY":
                content = elem.text_content() or ""
                return len(content.strip()) > 0
            
            return True
        except Exception:
            return False
