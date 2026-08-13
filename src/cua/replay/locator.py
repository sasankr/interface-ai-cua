"""
Resilient Multi-Strategy Locator Resolver
Resolves UI elements on heterogeneous / legacy surfaces using prioritized fallbacks:
1. ARIA Role + Accessible Name (AOM - Accessibility Object Model)
2. Form Label / Label Association
3. Placeholder Text
4. Visible Text Content
5. CSS Selector Fallback
6. XPath Hierarchy Fallback
7. Visual Anchor Proximity
"""

import time
from typing import Optional, Tuple
from playwright.sync_api import Page, Locator, FrameLocator
from cua.models.capability import LocatorStrategy
from cua.models.execution import LocatorResolutionDetails


class LocatorResolutionError(Exception):
    """Raised when an element cannot be resolved via any locator fallback."""
    pass


class LocatorResolver:
    @classmethod
    def resolve(
        cls,
        page: Page,
        strategy: LocatorStrategy,
        timeout_ms: int = 4000
    ) -> Tuple[Locator, LocatorResolutionDetails]:
        """
        Attempts to resolve an element using the strategy's prioritized hierarchy.
        Returns the resolved Playwright Locator and resolution metadata.
        """
        start_time = time.time()
        context = page
        
        # If frame selector is present, switch context to iframe
        if strategy.frame_selector:
            try:
                context = page.frame_locator(strategy.frame_selector)
            except Exception:
                context = page

        attempts = 0

        # Strategy 1: ARIA Role + Accessible Name (Gold standard for accessibility & resilience)
        if strategy.primary_role and strategy.accessible_name:
            attempts += 1
            try:
                loc = context.get_by_role(strategy.primary_role, name=strategy.accessible_name, exact=False)
                if loc.count() > 0:
                    loc.first.wait_for(state="attached", timeout=1200)
                    elapsed = (time.time() - start_time) * 1000
                    return loc.first, LocatorResolutionDetails(
                        strategy_used="ARIA_ROLE_NAME",
                        selector_string=f"role={strategy.primary_role}[name='{strategy.accessible_name}']",
                        resolved_in_ms=elapsed,
                        fallback_attempts=attempts
                    )
            except Exception:
                pass

        # Strategy 2: Form Label association
        if strategy.label_text:
            attempts += 1
            try:
                loc = context.get_by_label(strategy.label_text, exact=False)
                if loc.count() > 0:
                    loc.first.wait_for(state="attached", timeout=1200)
                    elapsed = (time.time() - start_time) * 1000
                    return loc.first, LocatorResolutionDetails(
                        strategy_used="LABEL_ASSOCIATION",
                        selector_string=f"label='{strategy.label_text}'",
                        resolved_in_ms=elapsed,
                        fallback_attempts=attempts
                    )
            except Exception:
                pass

        # Strategy 3: Input Placeholder
        if strategy.placeholder:
            attempts += 1
            try:
                loc = context.get_by_placeholder(strategy.placeholder, exact=False)
                if loc.count() > 0:
                    loc.first.wait_for(state="attached", timeout=1200)
                    elapsed = (time.time() - start_time) * 1000
                    return loc.first, LocatorResolutionDetails(
                        strategy_used="PLACEHOLDER",
                        selector_string=f"placeholder='{strategy.placeholder}'",
                        resolved_in_ms=elapsed,
                        fallback_attempts=attempts
                    )
            except Exception:
                pass

        # Strategy 4: Visible Text Content
        if strategy.text_content:
            attempts += 1
            try:
                loc = context.get_by_text(strategy.text_content, exact=False)
                if loc.count() > 0:
                    loc.first.wait_for(state="attached", timeout=1200)
                    elapsed = (time.time() - start_time) * 1000
                    return loc.first, LocatorResolutionDetails(
                        strategy_used="TEXT_CONTENT",
                        selector_string=f"text='{strategy.text_content}'",
                        resolved_in_ms=elapsed,
                        fallback_attempts=attempts
                    )
            except Exception:
                pass

        # Strategy 5: CSS Selector
        if strategy.css_selector:
            attempts += 1
            try:
                loc = context.locator(strategy.css_selector)
                if loc.count() > 0:
                    loc.first.wait_for(state="attached", timeout=1200)
                    elapsed = (time.time() - start_time) * 1000
                    return loc.first, LocatorResolutionDetails(
                        strategy_used="CSS_SELECTOR",
                        selector_string=strategy.css_selector,
                        resolved_in_ms=elapsed,
                        fallback_attempts=attempts
                    )
            except Exception:
                pass

        # Strategy 6: XPath Fallback
        if strategy.xpath:
            attempts += 1
            try:
                loc = context.locator(f"xpath={strategy.xpath}")
                if loc.count() > 0:
                    loc.first.wait_for(state="attached", timeout=1200)
                    elapsed = (time.time() - start_time) * 1000
                    return loc.first, LocatorResolutionDetails(
                        strategy_used="XPATH",
                        selector_string=strategy.xpath,
                        resolved_in_ms=elapsed,
                        fallback_attempts=attempts
                    )
            except Exception:
                pass

        # Strategy 7: Visual Anchor Proximity (e.g. Find input element next to anchor text)
        if strategy.visual_anchor:
            attempts += 1
            try:
                anchor = context.get_by_text(strategy.visual_anchor, exact=False).first
                if anchor.count() > 0:
                    # Look for input or button in same table row or parent container
                    candidate = anchor.locator("xpath=./following::input | ./ancestor::tr//input | ./following::button").first
                    if candidate.count() > 0:
                        candidate.wait_for(state="attached", timeout=1200)
                        elapsed = (time.time() - start_time) * 1000
                        return candidate, LocatorResolutionDetails(
                            strategy_used="VISUAL_ANCHOR_PROXIMITY",
                            selector_string=f"anchor='{strategy.visual_anchor}'",
                            resolved_in_ms=elapsed,
                            fallback_attempts=attempts
                        )
            except Exception:
                pass

        raise LocatorResolutionError(
            f"Failed to resolve target element after {attempts} strategy attempts. Strategy: {strategy.model_dump()}"
        )
