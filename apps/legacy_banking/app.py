"""
ApexCore Legacy Banking Operations Suite - Realistic Target Application
Simulates a multi-tenant legacy back-office core banking system with:
- Nested table-based layouts, legacy HTML structure, absence of data-testid
- Core banking member lookup with balances (Checking, Savings, Money Market)
- Open Sub-Account multi-step form with interstitial popups & confirmation codes
- Business exception states: Member not found (MEM-9999), Account Locked (MEM-LOCKED)
- Recoverable states: Security acknowledgment banner, interstitial modal
- Full audit logging & session state
"""

import os
from typing import Optional
from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="ApexCore Banking Suite v4.8.2-GA")

# In-memory mock core banking database
MEMBERS_DB = {
    "MEM-1082": {
        "id": "MEM-1082",
        "ssn_last4": "8841",
        "name": "Eleanor Vance",
        "email": "e.vance@example.org",
        "phone": "(555) 234-8901",
        "status": "Active",
        "branch": "Downtown Central (BR-014)",
        "joined_date": "2018-04-12",
        "accounts": [
            {"account_number": "ACT-1082-01", "type": "Primary Checking", "balance": "$4,250.80", "status": "Open"},
            {"account_number": "ACT-1082-02", "type": "High Yield Savings", "balance": "$18,940.25", "status": "Open"},
            {"account_number": "ACT-1082-03", "type": "36-Mo Certificate", "balance": "$10,000.00", "status": "Active"},
        ]
    },
    "MEM-4091": {
        "id": "MEM-4091",
        "ssn_last4": "3190",
        "name": "Marcus Holloway",
        "email": "m.holloway@example.org",
        "phone": "(555) 789-1122",
        "status": "Active",
        "branch": "Westside Branch (BR-022)",
        "joined_date": "2021-09-18",
        "accounts": [
            {"account_number": "ACT-4091-01", "type": "Primary Checking", "balance": "$1,120.00", "status": "Open"},
            {"account_number": "ACT-4091-02", "type": "High Yield Savings", "balance": "$5,630.50", "status": "Open"},
        ]
    },
    "MEM-LOCKED": {
        "id": "MEM-LOCKED",
        "ssn_last4": "0044",
        "name": "Arthur Pendelton",
        "email": "a.pendelton@example.org",
        "phone": "(555) 000-4411",
        "status": "FROZEN_COMPLIANCE_HOLD",
        "branch": "Compliance Escrow (BR-999)",
        "joined_date": "2015-02-01",
        "accounts": []
    }
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, tenant_id: str = "FCU-NATIONAL-01"):
    return templates.TemplateResponse(request=request, name="index.html", context={"tenant_id": tenant_id})


@app.get("/portal/member_search", response_class=HTMLResponse)
async def member_search_page(request: Request, show_interstitial: bool = False):
    return templates.TemplateResponse(request=request, name="member_lookup.html", context={
        "show_interstitial": show_interstitial,
        "error_message": None
    })


@app.post("/portal/member_search", response_class=HTMLResponse)
async def handle_member_search(request: Request, member_id: str = Form(...)):
    clean_id = member_id.strip().upper()
    if clean_id in MEMBERS_DB:
        member = MEMBERS_DB[clean_id]
        if member["status"] == "FROZEN_COMPLIANCE_HOLD":
            return templates.TemplateResponse(request=request, name="error.html", context={
                "error_code": "COMPLIANCE_HOLD_BLOCKED",
                "title": "Account Access Restricted (BSA/AML Compliance Hold)",
                "message": f"Member {clean_id} is currently under compliance review. Operator access is prohibited.",
                "member_id": clean_id
            }, status_code=200)
        return templates.TemplateResponse(request=request, name="member_detail.html", context={
            "member": member
        })
    else:
        # Expected business outcome: Record Not Found
        return templates.TemplateResponse(request=request, name="error.html", context={
            "error_code": "MEMBER_NOT_FOUND",
            "title": "Core Banking Record Not Found",
            "message": f"No active member matching identifier '{member_id}' was located in CIF master partition.",
            "member_id": member_id
        }, status_code=200)


@app.get("/portal/member/{member_id}", response_class=HTMLResponse)
async def member_detail(request: Request, member_id: str):
    clean_id = member_id.strip().upper()
    if clean_id in MEMBERS_DB:
        return templates.TemplateResponse(request=request, name="member_detail.html", context={
            "member": MEMBERS_DB[clean_id]
        })
    return templates.TemplateResponse(request=request, name="error.html", context={
        "error_code": "MEMBER_NOT_FOUND",
        "title": "Core Record Not Found",
        "message": f"Member '{member_id}' does not exist.",
        "member_id": member_id
    })


@app.get("/portal/subaccount/open", response_class=HTMLResponse)
async def open_subaccount_form(request: Request, member_id: str = Query("MEM-1082")):
    clean_id = member_id.strip().upper()
    member = MEMBERS_DB.get(clean_id)
    return templates.TemplateResponse(request=request, name="subaccount_open.html", context={
        "member": member,
        "member_id": clean_id,
        "step": 1
    })


@app.post("/portal/subaccount/submit", response_class=HTMLResponse)
async def submit_subaccount(
    request: Request,
    member_id: str = Form(...),
    account_type: str = Form(...),
    initial_deposit: str = Form(...),
    dividend_option: str = Form("compounded"),
    operator_override: Optional[str] = Form(None)
):
    clean_id = member_id.strip().upper()
    member = MEMBERS_DB.get(clean_id)
    if not member:
        return templates.TemplateResponse(request=request, name="error.html", context={
            "error_code": "MEMBER_NOT_FOUND",
            "title": "Invalid Member for Account Opening",
            "message": f"Cannot open sub-account for non-existent member {member_id}."
        })
    
    # Validation error checks
    try:
        deposit_val = float(initial_deposit.replace("$", "").replace(",", ""))
        if deposit_val < 25.00:
            return templates.TemplateResponse(request=request, name="error.html", context={
                "error_code": "VALIDATION_MIN_DEPOSIT",
                "title": "Policy Minimum Deposit Violation",
                "message": f"Initial deposit of ${deposit_val:.2f} is below the required regulatory minimum ($25.00)."
            })
    except ValueError:
        return templates.TemplateResponse(request=request, name="error.html", context={
            "error_code": "INVALID_AMOUNT",
            "title": "Malformed Financial Value",
            "message": f"Value '{initial_deposit}' cannot be parsed as currency."
        })

    new_act_num = f"ACT-{clean_id.split('-')[-1]}-0{len(member['accounts']) + 1}"
    new_account = {
        "account_number": new_act_num,
        "type": account_type,
        "balance": f"${deposit_val:,.2f}",
        "status": "Open"
    }
    member["accounts"].append(new_account)
    
    return templates.TemplateResponse(request=request, name="subaccount_open.html", context={
        "member": member,
        "member_id": clean_id,
        "step": 2,
        "created_account": new_account,
        "confirmation_code": f"CONF-SUB-{clean_id[-4:]}-98124"
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
