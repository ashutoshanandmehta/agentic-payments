"""The payment lifecycle state machine.

Drives one transaction from an agent's intent to a terminal state:

    CREATED -> AUTHORIZED -> DEBIT_PENDING -> DEBITED
            -> CREDIT_PENDING -> CREDITED -> SETTLED

with the failure branches that matter:

    * declined before any money moved            -> DECLINED
    * debited, credit rejected                   -> REVERSED
    * debited, outcome unknown (lost response)   -> TIMED_OUT, left for recon

The ordering rule this file exists to enforce: **the mandate is consumed only
after a successful debit, and released on reversal.** Consuming on
authorisation would let a failed payment permanently eat the user's headroom;
consuming after settlement would let concurrent payments both pass the cap.
"""

from __future__ import annotations

from dataclasses import dataclass

from core import Money, new_id, new_rrn, new_umn, new_upi_txn_id, validate_vpa
from models import (
    Mandate,
    MandateStatus,
    PaymentIntent,
    Transaction,
    TxnState,
    utcnow,
)
from authority import Rail, check_expressible
from policy import PolicyEngine, Verdict
from rails import Switch
from store import Store


class RailCannotExpress(ValueError):
    """The chosen rail cannot record what the user actually authorised.

    Raised at creation rather than swallowed, because the alternative is an
    authority that looks narrower than it is.
    """

    def __init__(self, rail: str, losses: list[str]):
        self.rail = rail
        self.losses = losses
        super().__init__(
            f"{rail} cannot express this authority: " + "; ".join(losses)
        )


@dataclass
class PaymentResult:
    txn: Transaction | None
    verdict: Verdict
    intent: PaymentIntent | None
    replayed: bool = False
    trace: list[dict] = None

    def to_dict(self) -> dict:
        return {
            "transaction": self.txn.to_dict() if self.txn else None,
            "verdict": self.verdict.to_dict(),
            "intent": self.intent.to_dict() if self.intent else None,
            "replayed": self.replayed,
            "trace": self.trace or [],
        }

    @property
    def ok(self) -> bool:
        return self.txn is not None and self.txn.state is TxnState.SETTLED


class Orchestrator:
    def __init__(self, store: Store, switch: Switch, policy: PolicyEngine):
        self.store = store
        self.switch = switch
        self.policy = policy

    # ----------------------------------------------------------------------
    # Mandates
    # ----------------------------------------------------------------------

    def create_mandate(
        self,
        payer_vpa: str,
        allowed_payees: list[str],
        max_amount_per_txn: Money,
        total_cap: Money,
        valid_from,
        valid_until,
        purpose: str,
        agent_id: str | None = None,
        categories: list[str] | None = None,
        rail: str | None = None,
        period_cap: Money | None = None,
        period_days: int | None = None,
    ) -> Mandate:
        payer_vpa = validate_vpa(payer_vpa)
        if self.store.get_account_by_vpa(payer_vpa) is None:
            raise ValueError(f"no account for payer {payer_vpa}")

        categories = categories or []

        # If a rail is named, it must be able to say what the user said. Recording
        # an authority the rail cannot express means quietly dropping part of the
        # instruction and telling the user it was set up -- which is worse than
        # refusing, because they believe they are protected.
        if rail is not None:
            verdict = check_expressible(
                Rail(rail), allowed_payees, categories, total_cap
            )
            if not verdict.expressible:
                raise RailCannotExpress(rail, verdict.losses)

        mandate = Mandate(
            umn=new_umn(),
            payer_vpa=payer_vpa,
            allowed_payees=[p if p == "*" else validate_vpa(p) for p in allowed_payees],
            max_amount_per_txn=max_amount_per_txn,
            total_cap=total_cap,
            consumed=Money.zero(),
            valid_from=valid_from,
            valid_until=valid_until,
            status=MandateStatus.ACTIVE,
            purpose=purpose,
            agent_id=agent_id,
            categories=categories,
            rail=rail,
            period_cap=period_cap,
            period_days=period_days,
            period_started_at=utcnow() if period_cap is not None else None,
        )
        self.store.save_mandate(mandate)
        self.store.record_event("mandate.created", mandate.to_dict())
        return mandate

    def revoke_mandate(self, umn: str) -> Mandate:
        m = self.store.set_mandate_status(umn, MandateStatus.REVOKED)
        self.store.record_event("mandate.revoked", {"umn": umn})
        return m

    # ----------------------------------------------------------------------
    # Payment
    # ----------------------------------------------------------------------

    def execute(
        self,
        intent: PaymentIntent,
        payer_vpa: str,
        idempotency_key: str,
        umn: str | None = None,
        note: str = "",
        order=None,
        agent_id: str | None = None,
        quantity: str | None = None,
    ) -> PaymentResult:
        """Gate an intent, then run it through the rails.

        `agent_id` rides on the transaction. It is the field Section II-C of the
        brief says UPI does not carry -- without it, a debit is just a debit, and
        nothing afterwards can say which agent caused it.
        """
        trace: list[dict] = []
        payer_vpa = validate_vpa(payer_vpa)

        # -- idempotency: a replay returns the original, never a second charge
        existing = self.store.get_txn_by_idempotency_key(idempotency_key)
        if existing is not None:
            trace.append({
                "step": "idempotency",
                "detail": f"key already used by {existing.txn_id}; replaying",
            })
            return PaymentResult(
                txn=existing,
                verdict=Verdict(True, existing.response_code or "00", ["replayed"], []),
                intent=intent, replayed=True, trace=trace,
            )

        # -- gate ----------------------------------------------------------
        mandate = self.store.get_mandate(umn) if umn else None
        verdict = self.policy.evaluate(intent, payer_vpa, mandate, order, quantity)
        trace.append({
            "step": "policy",
            "detail": "allowed" if verdict.allowed else "; ".join(verdict.reasons),
        })

        if not verdict.allowed:
            self.store.record_event("payment.blocked", {
                "intent": intent.to_dict(), "verdict": verdict.to_dict(),
                "idempotency_key": idempotency_key,
            })
            return PaymentResult(None, verdict, intent, trace=trace)

        # -- create --------------------------------------------------------
        txn = Transaction(
            txn_id=new_id("txn"),
            upi_txn_id=new_upi_txn_id(),
            rrn=new_rrn(),
            idempotency_key=idempotency_key,
            payer_vpa=payer_vpa,
            payee_vpa=validate_vpa(intent.payee_vpa),
            amount=intent.amount,
            state=TxnState.CREATED,
            response_code=None,
            umn=umn,
            note=note or intent.reason,
            agent_id=agent_id,
        )
        self.store.create_txn(txn)
        self.store.record_event("payment.created", txn.to_dict(), txn.txn_id)
        trace.append({"step": "created", "detail": f"{txn.txn_id} rrn={txn.rrn}"})

        txn = self.store.update_txn_state(txn.txn_id, TxnState.AUTHORIZED)
        trace.append({"step": "authorized", "detail": f"mandate={umn or 'none'}"})

        return self._run_legs(txn, trace, verdict, intent)

    # ----------------------------------------------------------------------

    def _run_legs(self, txn, trace, verdict, intent) -> PaymentResult:
        # -- debit ---------------------------------------------------------
        txn = self.store.update_txn_state(txn.txn_id, TxnState.DEBIT_PENDING,
                                          bump_attempts=True)
        debit = self.switch.debit_leg(txn)
        self.store.record_event("leg.debit", debit.to_dict(), txn.txn_id)
        trace.append({"step": "debit", "detail": f"[{debit.code}] {debit.message}"})

        if debit.code == "BT":
            # The debit committed but the response was lost. We cannot claim
            # success and must not retry -- reconciliation resolves it.
            txn = self.store.update_txn_state(txn.txn_id, TxnState.TIMED_OUT, "BT")
            self.store.record_event("payment.timed_out",
                                    {"leg": "debit", "code": "BT"}, txn.txn_id)
            trace.append({"step": "timeout", "detail": "debit outcome unknown; left for recon"})
            return PaymentResult(txn, verdict, intent, trace=trace)

        if not debit.ok:
            txn = self.store.update_txn_state(txn.txn_id, TxnState.DECLINED, debit.code)
            self.store.record_event("payment.declined", debit.to_dict(), txn.txn_id)
            return PaymentResult(txn, verdict, intent, trace=trace)

        txn = self.store.update_txn_state(txn.txn_id, TxnState.DEBITED, "00")

        # Money has left the payer, so the mandate is consumed now. Doing this
        # on authorisation would let a declined payment eat headroom forever.
        if txn.umn:
            self.store.consume_mandate(txn.umn, txn.amount)
            trace.append({"step": "mandate", "detail": f"consumed {txn.amount} of {txn.umn}"})

        # -- credit --------------------------------------------------------
        txn = self.store.update_txn_state(txn.txn_id, TxnState.CREDIT_PENDING)
        credit = self.switch.credit_leg(txn)
        self.store.record_event("leg.credit", credit.to_dict(), txn.txn_id)
        trace.append({"step": "credit", "detail": f"[{credit.code}] {credit.message}"})

        if credit.code == "BT":
            txn = self.store.update_txn_state(txn.txn_id, TxnState.TIMED_OUT, "BT")
            self.store.record_event("payment.timed_out",
                                    {"leg": "credit", "code": "BT"}, txn.txn_id)
            trace.append({"step": "timeout", "detail": "credit outcome unknown; left for recon"})
            return PaymentResult(txn, verdict, intent, trace=trace)

        if not credit.ok:
            return PaymentResult(
                self._reverse(txn, credit.code, trace), verdict, intent, trace=trace
            )

        txn = self.store.update_txn_state(txn.txn_id, TxnState.CREDITED, "00")
        txn = self.store.update_txn_state(txn.txn_id, TxnState.SETTLED, "00")
        self.store.record_event("payment.settled", txn.to_dict(), txn.txn_id)
        trace.append({"step": "settled", "detail": f"{txn.amount} to {txn.payee_vpa}"})
        return PaymentResult(txn, verdict, intent, trace=trace)

    def _reverse(self, txn: Transaction, cause_code: str, trace: list[dict]) -> Transaction:
        """Return in-flight funds and give the mandate headroom back."""
        rev = self.switch.reverse_leg(txn)
        self.store.record_event("leg.reversal",
                                {**rev.to_dict(), "cause": cause_code}, txn.txn_id)
        trace.append({"step": "reversal", "detail": f"[{rev.code}] {rev.message}"})

        if not rev.ok:
            txn = self.store.update_txn_state(txn.txn_id, TxnState.FAILED, rev.code)
            self.store.record_event("payment.failed",
                                    {"reason": "reversal failed", **rev.to_dict()}, txn.txn_id)
            return txn

        txn = self.store.update_txn_state(txn.txn_id, TxnState.REVERSED, cause_code)
        if txn.umn:
            self.store.release_mandate(txn.umn, txn.amount)
            trace.append({"step": "mandate", "detail": f"released {txn.amount} back to {txn.umn}"})
        self.store.record_event("payment.reversed", {"cause": cause_code}, txn.txn_id)
        return txn

    # ----------------------------------------------------------------------
    # Agent entry point
    # ----------------------------------------------------------------------

    def run_agent_payment(
        self,
        planner,
        standing_instruction: str,
        event: dict,
        payer_vpa: str,
        umn: str | None,
        idempotency_key: str | None = None,
        order=None,
        agent_id: str | None = None,
        quantity: str | None = None,
    ) -> PaymentResult:
        """Standing instruction + event -> intent -> gate -> rails."""
        from agent import AgentContext

        ctx = AgentContext(
            standing_instruction=standing_instruction,
            event=event,
            payer_vpa=validate_vpa(payer_vpa),
        )
        intent = planner.plan(ctx)
        self.store.record_event("agent.intent", {
            "planner": planner.name, "event": event, "intent": intent.to_dict(),
        })

        # Derive a stable key from the event so a redelivered webhook can't
        # pay twice. Callers with their own key may pass one.
        key = idempotency_key or f"evt:{event.get('invoice_id') or event.get('event_id') or new_id('ev')}"

        return self.execute(
            intent=intent, payer_vpa=payer_vpa, idempotency_key=key,
            umn=umn, note=f"agent({planner.name}): {intent.reason}", order=order,
            agent_id=agent_id,
        )
