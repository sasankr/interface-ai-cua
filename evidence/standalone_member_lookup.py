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

        # step_1_fill: I observe the Member Search inquiry page. To look up member 1082, I must enter the identifier 'MEM-1
        page.locator("#txtMemberId").fill("MEM-1082")
        page.wait_for_timeout(300)

        # step_2_click: The member ID field is populated. I now click 'Search Member Records' button to submit the query to 
        page.locator("#btnSearchMember").click()
        page.wait_for_timeout(300)

        # Checkpoint: Member demographic card and deposit accounts table rendered
        assert page.locator("#tblMemberAccounts").is_visible(), "Checkpoint chk_step_2 failed"

        print("Capability execution completed successfully!")
        browser.close()

if __name__ == "__main__":
    run_flow()