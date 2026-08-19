"""REST API over the simulator.

    uvicorn api:app --reload --app-dir src
    open http://127.0.0.1:8000/docs

The API is the source of truth for the system's behaviour; the CLI drives the
same objects. Write endpoints accept an `Idempotency-Key` header, matching the
convention every real payments API uses -- replaying a key returns the original
transaction rather than charging twice.
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from typing import Any, Literal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import Body, FastAPI, Header, HTTPException, Query  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from agent import RulePlanner, build_planner, credentials_available  # noqa: E402
from core import Money, UpiError, new_id, validate_vpa  # noqa: E402
from models import AccountType, MandateStatus, PaymentIntent, TxnState, utcnow  # noqa: E402
from rails import FAULTS  # noqa: E402
import sim as simulator  # noqa: E402

DB_PATH = os.environ.get("UPI_SIM_DB", simulator.DEFAULT_DB)

app = FastAPI(
    title="Agentic UPI Payment Simulator",
    version="1.0.0",
    description=(
        "A simulated UPI stack with an LLM agent that proposes payments and a "
        "deterministic mandate + policy engine that authorises them. Money moves "
        "through a double-entry ledger in two legs with a suspense account "
        "between, so reversal and reconciliation are real operations."
    ),
)

SIM = simulator.build(db_path=DB_PATH)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class SeedResponse(BaseModel):
    user: dict
    merchant: dict
    other_merchant: dict
    mandate: dict
    standing_instruction: str


class AccountCreate(BaseModel):
    vpa: str = Field(..., examples=["ashutosh@okhdfc"])
    holder_name: str
    account_type: Literal["USER", "MERCHANT"] = "USER"
    opening_balance_rupees: str = Field("0", examples=["10000.00"])


class MandateCreate(BaseModel):
    payer_vpa: str = Field(..., examples=["ashutosh@okhdfc"])
    allowed_payees: list[str] = Field(..., examples=[["brewhouse@ybl"]])
    max_amount_per_txn_rupees: str = Field(..., examples=["1000.00"])
    total_cap_rupees: str = Field(..., examples=["5000.00"])
    valid_days: int = Field(365, ge=1, le=3650)
    purpose: str = "Recurring subscription"


class AgentRunRequest(BaseModel):
    standing_instruction: str = Field(..., examples=[simulator.STANDING_INSTRUCTION])
    event: dict[str, Any] = Field(..., examples=[{
        "invoice_id": "INV-1001",
        "merchant_name": "Brewhouse Coffee",
        "payee_vpa": "brewhouse@ybl",
        "amount_rupees": "499.00",
        "plan": "monthly",
        "status": "issued",
    }])
    payer_vpa: str = Field(..., examples=["ashutosh@okhdfc"])
    umn: str | None = None
    use_llm: bool = Field(True, description="Fall back to the rule planner if unset or unavailable")


class DirectPaymentRequest(BaseModel):
    """Skip the agent, but not the gate. Still mandate- and policy-checked."""

    payer_vpa: str
    payee_vpa: str
    amount_rupees: str
    umn: str | None = None
    note: str = "direct API payment"


class FaultRequest(BaseModel):
    force: str | None = Field(None, examples=["credit_fail"])
    probabilities: dict[str, float] = Field(default_factory=dict)


# --------------------------------------------------------------------------
# Meta
# --------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
def health():
    planner = build_planner()
    return {
        "status": "ok",
        "database": DB_PATH,
        "accounts": len(SIM.store.list_accounts()),
        "planner": planner.name,
        "anthropic_credentials": credentials_available(),
        "available_faults": list(FAULTS),
    }


@app.get("/policy", tags=["meta"])
def get_policy():
    return SIM.policy.config.to_dict()


@app.post("/seed", response_model=SeedResponse, tags=["meta"])
def seed():
    """Create the demo world: a user, two merchants, and a scoped mandate."""
    return simulator.seed(SIM)


@app.post("/faults", tags=["meta"])
def set_faults(req: FaultRequest):
    """Arm a fault. `force` fires once on the next matching leg."""
    if req.force and req.force not in FAULTS:
        raise HTTPException(400, f"unknown fault {req.force!r}; expected one of {list(FAULTS)}")
    for name in req.probabilities:
        if name not in FAULTS:
            raise HTTPException(400, f"unknown fault {name!r}")
    SIM.faults.force = req.force
    SIM.faults.probabilities = req.probabilities
    return {"force": SIM.faults.force, "probabilities": SIM.faults.probabilities}


@app.delete("/faults", tags=["meta"])
def clear_faults():
    SIM.faults.clear()
    return {"force": None, "probabilities": {}}


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------


@app.get("/accounts", tags=["accounts"])
def list_accounts():
    return [a.to_dict() for a in SIM.store.list_accounts()]


@app.post("/accounts", status_code=201, tags=["accounts"])
def create_account(req: AccountCreate):
    if SIM.store.get_account_by_vpa_safe(req.vpa) is not None:
        raise HTTPException(409, f"{req.vpa} already exists")
    try:
        acct = SIM.store.create_account(
            vpa=req.vpa,
            holder_name=req.holder_name,
            account_type=AccountType(req.account_type),
            opening_balance=Money.rupees(req.opening_balance_rupees),
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return acct.to_dict()


@app.get("/accounts/{vpa}", tags=["accounts"])
def get_account(vpa: str):
    acct = SIM.store.get_account_by_vpa_safe(vpa)
    if acct is None:
        raise HTTPException(404, f"no account for {vpa}")
    return acct.to_dict()


@app.get("/resolve/{vpa}", tags=["accounts"])
def resolve_vpa(vpa: str):
    """VPA directory lookup, as a payer app does before showing 'Pay to'."""
    try:
        return SIM.switch.resolve(vpa)
    except (UpiError, ValueError) as exc:
        raise HTTPException(404, str(exc)) from exc


# --------------------------------------------------------------------------
# Mandates
# --------------------------------------------------------------------------


@app.get("/mandates", tags=["mandates"])
def list_mandates(payer_vpa: str | None = Query(None)):
    return [m.to_dict() for m in SIM.store.list_mandates(payer_vpa)]


@app.post("/mandates", status_code=201, tags=["mandates"])
def create_mandate(req: MandateCreate):
    now = utcnow()
    try:
        mandate = SIM.orchestrator.create_mandate(
            payer_vpa=req.payer_vpa,
            allowed_payees=req.allowed_payees,
            max_amount_per_txn=Money.rupees(req.max_amount_per_txn_rupees),
            total_cap=Money.rupees(req.total_cap_rupees),
            valid_from=now,
            valid_until=now + timedelta(days=req.valid_days),
            purpose=req.purpose,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return mandate.to_dict()


@app.get("/mandates/{umn}", tags=["mandates"])
def get_mandate(umn: str):
    m = SIM.store.get_mandate(umn)
    if m is None:
        raise HTTPException(404, f"no mandate {umn}")
    return m.to_dict()


@app.post("/mandates/{umn}/revoke", tags=["mandates"])
def revoke_mandate(umn: str):
    if SIM.store.get_mandate(umn) is None:
        raise HTTPException(404, f"no mandate {umn}")
    return SIM.orchestrator.revoke_mandate(umn).to_dict()


@app.post("/mandates/{umn}/pause", tags=["mandates"])
def pause_mandate(umn: str):
    if SIM.store.get_mandate(umn) is None:
        raise HTTPException(404, f"no mandate {umn}")
    return SIM.store.set_mandate_status(umn, MandateStatus.PAUSED).to_dict()


@app.post("/mandates/{umn}/resume", tags=["mandates"])
def resume_mandate(umn: str):
    m = SIM.store.get_mandate(umn)
    if m is None:
        raise HTTPException(404, f"no mandate {umn}")
    if m.status is MandateStatus.REVOKED:
        raise HTTPException(409, "a revoked mandate cannot be resumed")
    return SIM.store.set_mandate_status(umn, MandateStatus.ACTIVE).to_dict()


# --------------------------------------------------------------------------
# Payments
# --------------------------------------------------------------------------


@app.post("/agent/run", tags=["payments"])
def agent_run(
    req: AgentRunRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Standing instruction + event -> agent intent -> gate -> rails.

    The full pipeline. The response carries the agent's intent, every gate
    check with its verdict, and the rail-by-rail trace, so a blocked payment
    shows exactly which check stopped it.
    """
    planner = build_planner(prefer_llm=req.use_llm)
    try:
        result = SIM.orchestrator.run_agent_payment(
            planner=planner,
            standing_instruction=req.standing_instruction,
            event=req.event,
            payer_vpa=req.payer_vpa,
            umn=req.umn,
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    payload = result.to_dict()
    payload["planner"] = planner.name
    return payload


@app.post("/payments", tags=["payments"])
def direct_payment(
    req: DirectPaymentRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Raise a payment without the agent. The mandate and policy gate still run."""
    try:
        intent = PaymentIntent(
            should_pay=True,
            payee_vpa=validate_vpa(req.payee_vpa),
            amount=Money.rupees(req.amount_rupees),
            reason=req.note,
            confidence=1.0,
            source="api",
        )
        result = SIM.orchestrator.execute(
            intent=intent,
            payer_vpa=req.payer_vpa,
            idempotency_key=idempotency_key or new_id("idem"),
            umn=req.umn,
            note=req.note,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return result.to_dict()


@app.get("/payments", tags=["payments"])
def list_payments(
    state: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    try:
        parsed = TxnState(state) if state else None
    except ValueError as exc:
        raise HTTPException(400, f"unknown state {state!r}") from exc
    return [t.to_dict() for t in SIM.store.list_txns(state=parsed, limit=limit)]


@app.get("/payments/{txn_id}", tags=["payments"])
def get_payment(txn_id: str):
    txn = SIM.store.get_txn(txn_id)
    if txn is None:
        raise HTTPException(404, f"no transaction {txn_id}")
    return {
        "transaction": txn.to_dict(),
        "ledger": [e.to_dict() for e in SIM.store.ledger_for_txn(txn_id)],
        "events": SIM.store.list_events(txn_id=txn_id),
    }


# --------------------------------------------------------------------------
# Reconciliation and audit
# --------------------------------------------------------------------------


@app.post("/recon/sweep", tags=["recon"])
def recon_sweep():
    """Resolve stuck transactions by asking the banks what actually posted."""
    return SIM.reconciler.sweep().to_dict()


@app.get("/recon/audit", tags=["recon"])
def recon_audit():
    """Re-derive every balance from the ledger and check the books balance."""
    return SIM.reconciler.audit()


@app.get("/ledger", tags=["recon"])
def ledger(txn_id: str | None = Query(None)):
    entries = (
        SIM.store.ledger_for_txn(txn_id) if txn_id else SIM.store.all_ledger_entries()
    )
    return [e.to_dict() for e in entries]


@app.get("/events", tags=["recon"])
def events(txn_id: str | None = Query(None), limit: int = Query(100, ge=1, le=1000)):
    return SIM.store.list_events(txn_id=txn_id, limit=limit)
