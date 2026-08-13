"""
Auto-Generated Playwright Test Script for: Core Banking Member Lookup & Balance Inquiry
Capability ID: core_banking.member_lookup
Schema Version: 1.0.0
"""

from playwright.sync_api import sync_playwright

def run_flow():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        # Navigate to entry point
        page.goto("http://127.0.0.1:8000/portal/member_search")
        page.wait_for_load_state("networkidle")

        # step_1_input_member_id: Enter target CIF Member Identifier into search textbox
        page.locator("#txtMemberId").fill("{inputs["member_id"]}")
        page.wait_for_timeout(200)

        # step_2_submit_search: Click 'Search Member Records' button to submit inquiry to host
        page.locator("#btnSearchMember").click()
        page.wait_for_timeout(400)

        # Checkpoint: Confirm Member Workspace profile header is visible
        assert page.locator("#summary-member-name").is_visible(), "Checkpoint chk_member_profile_loaded failed"
        # Checkpoint: Confirm Deposit Accounts table is populated
        assert page.locator("#tblMemberAccounts").is_visible(), "Checkpoint chk_accounts_table_visible failed"

        print("Capability execution completed successfully!")
        browser.close()

if __name__ == "__main__":
    run_flow()