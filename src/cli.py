"""Command-line driver for the simulator.

    python src/cli.py seed
    python src/cli.py demo                       # full happy path, narrated
    python src/cli.py pay --amount 499 --invoice INV-001
    python src/cli.py pay --amount 499 --invoice INV-002 --fail credit_fail
    python src/cli.py recon
    python src/cli.py audit
    python src/cli.py accounts | mandates | txns | events

Everything is stdlib except the optional `anthropic` SDK, which is only
imported when an LLM planner is actually built.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import RulePlanner, build_planner, credentials_available  # noqa: E402
from core import Money  # noqa: E402
from models import TxnState  # noqa: E402
from rails import FAULTS, FaultConfig  # noqa: E402
import sim as simulator  # noqa: E402

BOLD, DIM, RED, GREEN, YELLOW, CYAN, RESET = (
    "\033[1m", "\033[2m", "\033[31m", "\033[32m", "\033[33m", "\033[36m", "\033[0m"
)


def _colour(enabled: bool):
    if enabled:
        return BOLD, DIM, RED, GREEN, YELLOW, CYAN, RESET
    return ("",) * 7


def dump(obj):
    print(json.dumps(obj, indent=2, default=str))


# --------------------------------------------------------------------------


def cmd_seed(args, sim):
    info = simulator.seed(sim)
    print(f"Seeded. Mandate {info['mandate']['umn']}")
    dump(info)


def cmd_accounts(args, sim):
    dump([a.to_dict() for a in sim.store.list_accounts()])


def cmd_mandates(args, sim):
    dump([m.to_dict() for m in sim.store.list_mandates()])


def cmd_txns(args, sim):
    state = TxnState(args.state) if args.state else None
    dump([t.to_dict() for t in sim.store.list_txns(state=state, limit=args.limit)])


def cmd_events(args, sim):
    dump(sim.store.list_events(txn_id=args.txn, limit=args.limit))


def cmd_ledger(args, sim):
    if args.txn:
        dump([e.to_dict() for e in sim.store.ledger_for_txn(args.txn)])
    else:
        dump([e.to_dict() for e in sim.store.all_ledger_entries()])


def cmd_recon(args, sim):
    report = sim.reconciler.sweep()
    dump(report.to_dict())


def cmd_audit(args, sim):
    report = sim.reconciler.audit()
    dump(report)
    if not report["healthy"]:
        sys.exit(1)


def cmd_revoke(args, sim):
    dump(sim.orchestrator.revoke_mandate(args.umn).to_dict())


# --------------------------------------------------------------------------


def _resolve_mandate(sim, umn: str | None) -> str | None:
    if umn:
        return umn
    mandates = sim.store.list_mandates(payer_vpa=simulator.USER_VPA)
    return mandates[0].umn if mandates else None


def _build_event(args) -> dict:
    return {
        "invoice_id": args.invoice,
        "merchant_name": args.merchant_name,
        "payee_vpa": args.payee,
        "amount_rupees": args.amount,
        "plan": args.plan,
        "status": args.status,
        "description": args.description,
    }


def cmd_pay(args, sim):
    b, d, r, g, y, c, x = _colour(not args.no_colour)

    if args.fail:
        sim.faults.force = args.fail
        print(f"{y}fault armed:{x} {args.fail} will fire on the next matching leg\n")

    planner = RulePlanner() if args.no_llm else build_planner()
    event = _build_event(args)
    umn = _resolve_mandate(sim, args.umn)

    print(f"{b}Standing instruction{x}")
    print(f"  {simulator.STANDING_INSTRUCTION}\n")
    print(f"{b}Event{x}")
    for k, v in event.items():
        if v is not None:
            print(f"  {k:<15} {v}")
    print(f"\n{b}Planner{x}  {planner.name}"
          f"{'' if planner.name == 'llm' else f'{d} (no Anthropic credentials found){x}'}\n")

    result = sim.orchestrator.run_agent_payment(
        planner=planner,
        standing_instruction=simulator.STANDING_INSTRUCTION,
        event=event,
        payer_vpa=args.payer,
        umn=umn,
    )

    intent = result.intent
    print(f"{b}Agent intent{x}")
    print(f"  should_pay      {intent.should_pay}")
    print(f"  payee           {intent.payee_vpa}")
    print(f"  amount          {intent.amount if intent.amount else '-'}")
    print(f"  confidence      {intent.confidence:.2f}")
    print(f"  reason          {intent.reason}\n")

    print(f"{b}Gate{x}")
    for chk in result.verdict.checks:
        mark = f"{g}pass{x}" if chk["passed"] else f"{r}FAIL{x}"
        print(f"  [{mark}] {chk['check']:<26} {d}{chk['detail']}{x}")
    if not result.verdict.allowed:
        print(f"\n{r}BLOCKED{x} [{result.verdict.code}]")
        for reason in result.verdict.reasons:
            print(f"  - {reason}")
        return

    print(f"\n{b}Rails{x}")
    for step in result.trace:
        print(f"  {step['step']:<12} {step['detail']}")

    txn = result.txn
    state_colour = g if txn.state is TxnState.SETTLED else (
        y if txn.state is TxnState.TIMED_OUT else r
    )
    print(f"\n{b}Result{x}  {state_colour}{txn.state.value}{x} "
          f"[{txn.response_code}] rrn={txn.rrn}")

    payer = sim.store.get_account_by_vpa(txn.payer_vpa)
    payee = sim.store.get_account_by_vpa(txn.payee_vpa)
    print(f"  {payer.vpa:<22} {payer.balance}")
    print(f"  {payee.vpa:<22} {payee.balance}")

    if txn.state is TxnState.TIMED_OUT:
        print(f"\n{y}Funds are in suspense.{x} Run `python src/cli.py recon` to resolve.")


def cmd_consent(args, sim):
    """
    The order gate, shown twice: off, then on.

    Same mandate, same policy, same payment. The only difference is whether the
    system holds a record of what the user agreed to buy.
    """
    from consent import Order, OrderSigner
    from models import PaymentIntent
    from core import Money
    import sim as simwiring

    seeded = simwiring.seed(sim)
    umn = seeded["mandate"]["umn"]
    mandate = sim.store.get_mandate(umn)

    # what the user actually agreed to
    order = Order.build("ORD-1", simwiring.MERCHANT_VPA,
                        [("Monthly plan", "99"), ("GST", "19")])
    order.sign(sim.policy.order_signer, sim.agent_key,
               sim.merchant_keys[simwiring.MERCHANT_VPA])

    # what the agent asks for
    charged = args.amount or "600"
    intent = PaymentIntent(True, simwiring.MERCHANT_VPA, Money.rupees(str(charged)),
                           "monthly invoice", 0.95, "rule")

    print(f"\n{CYAN}{'-' * 68}{RESET}")
    print(f"  {BOLD}User agreed to {order.total}.  "
          f"Agent is asking for {Money.rupees(str(charged))}.{RESET}")
    print(f"{CYAN}{'-' * 68}{RESET}")

    for on in (False, True):
        sim.policy.config.require_order = on
        v = sim.policy.evaluate(intent, simwiring.USER_VPA, mandate,
                                order if on else None)
        head = "WITH the order gate" if on else "WITHOUT the order gate (UPI today)"
        print(f"\n  {BOLD}{head}{RESET}")
        print(f"    {GREEN + 'ALLOWED' + RESET if v.allowed else RED + 'REFUSED' + RESET}"
              f"   {len(v.checks)} checks")
        for c in v.checks:
            if not c["passed"]:
                print(f"      {RED}x {c['check']}{RESET}  {DIM}{c['detail']}{RESET}")
        for r in v.reasons:
            print(f"      {YELLOW}{r}{RESET}")
    print()


def cmd_rails(args, sim):
    """Put one authority to every rail and print what each would have to drop."""
    from authority import compare_rails
    import sim as simwiring

    payees = args.payees or [simwiring.MERCHANT_VPA, simwiring.SECOND_MERCHANT_VPA]
    cats = args.categories or ["groceries"]
    cap = Money.rupees(str(args.cap or "5000"))

    print(f"\n{CYAN}{'-' * 68}{RESET}")
    print(f"  {BOLD}The authority the user set{RESET}")
    print(f"{CYAN}{'-' * 68}{RESET}")
    print(f"    pay        {', '.join(payees)}")
    print(f"    for        {', '.join(cats) if cats else 'anything'}")
    print(f"    up to      {cap}\n")

    carried = 0
    for rail, verdict in compare_rails(payees, cats, cap).items():
        if verdict.expressible:
            carried += 1
            print(f"  {GREEN}CAN CARRY{RESET}  {BOLD}{rail.value}{RESET}")
        else:
            print(f"  {RED}CANNOT   {RESET}  {BOLD}{rail.value}{RESET}")
        for loss in verdict.losses:
            print(f"      {YELLOW}drops{RESET} {DIM}{loss}{RESET}")
        print()

    if not carried:
        print(f"  {RED}{BOLD}No rail can record what the user said.{RESET}")
        print(f"  {DIM}That is the gap: not a missing check, a missing "
              f"vocabulary.{RESET}\n")


def cmd_enforce(args, sim):
    """Who on a UPI payment could actually run the two checks?"""
    from enforcement import (
        CHECK_QUESTION, UPI_TODAY, Check, report, with_cart_reference,
    )

    for title, topology in (
        ("UPI as it is today", UPI_TODAY),
        ("UPI carrying a cart reference", with_cart_reference()),
    ):
        result = report(topology)
        print(f"\n{CYAN}{'-' * 68}{RESET}")
        print(f"  {BOLD}{title}{RESET}")
        print(f"{CYAN}{'-' * 68}{RESET}")

        for check in Check:
            print(f"\n  {BOLD}Check {check.value}{RESET} "
                  f"{DIM}{CHECK_QUESTION[check]}{RESET}")
            for f in result["findings"]:
                if f["check"] != check.value:
                    continue
                mark = f"{GREEN}CAN {RESET}" if f["can_enforce"] else f"{DIM}  - {RESET}"
                print(f"    {mark} {f['party']:<20} {DIM}{f['reason']}{RESET}")

        blocked = result["unenforceable"]
        print()
        if blocked:
            print(f"  {RED}{BOLD}Checks {', '.join(blocked)} cannot be enforced by "
                  f"anyone.{RESET}")
            print(f"  {DIM}Every party is either blind or conflicted. Only blindness "
                  f"is fixable by the rail.{RESET}")
        else:
            for check, who in result["enforcers"].items():
                print(f"  {GREEN}Check {check}{RESET} enforceable by "
                      f"{BOLD}{', '.join(who)}{RESET}")
    print()


def cmd_demo(args, sim):
    """Seed, pay, break it, reconcile, audit -- the whole story in one run."""
    b, d, r, g, y, c, x = _colour(not args.no_colour)

    def banner(title):
        print(f"\n{c}{'─' * 68}{x}\n{b}{title}{x}\n{c}{'─' * 68}{x}")

    banner("1. Seed accounts and mandate")
    info = simulator.seed(sim)
    print(f"  user      {info['user']['vpa']:<22} {info['user']['balance']}")
    print(f"  merchant  {info['merchant']['vpa']:<22} {info['merchant']['balance']}")
    m = info["mandate"]
    print(f"  mandate   {m['umn']}")
    print(f"            payees={m['allowed_payees']} per-txn≤₹{m['max_amount_per_txn']} "
          f"cap=₹{m['total_cap']}")

    planner = RulePlanner() if args.no_llm else build_planner()
    umn = m["umn"]

    def run(label, event, fault=None):
        banner(label)
        if fault:
            sim.faults.force = fault
            print(f"  {y}fault armed: {fault}{x}")
        res = sim.orchestrator.run_agent_payment(
            planner=planner, standing_instruction=simulator.STANDING_INSTRUCTION,
            event=event, payer_vpa=simulator.USER_VPA, umn=umn,
        )
        print(f"  intent    should_pay={res.intent.should_pay} "
              f"{res.intent.amount or ''} -> {res.intent.payee_vpa or '-'}")
        if not res.verdict.allowed:
            print(f"  {r}BLOCKED{x} [{res.verdict.code}]")
            for reason in res.verdict.reasons:
                print(f"    - {reason}")
            return res
        for step in res.trace:
            print(f"  {step['step']:<12} {step['detail']}")
        col = g if res.txn.state is TxnState.SETTLED else (
            y if res.txn.state is TxnState.TIMED_OUT else r)
        print(f"  {b}state{x}     {col}{res.txn.state.value}{x} [{res.txn.response_code}]")
        return res

    base = dict(merchant_name="Brewhouse Coffee", payee_vpa=simulator.MERCHANT_VPA,
                plan="monthly", status="issued",
                description="Monthly subscription")

    run("2. Happy path — invoice arrives, agent pays",
        {**base, "invoice_id": "INV-1001", "amount_rupees": "499.00"})

    run("3. Same invoice redelivered — idempotency suppresses the double charge",
        {**base, "invoice_id": "INV-1001", "amount_rupees": "499.00"})

    run("4. Out-of-scope payee — mandate blocks it",
        {**base, "invoice_id": "INV-1002", "amount_rupees": "499.00",
         "merchant_name": "CloudHost Systems", "payee_vpa": simulator.SECOND_MERCHANT_VPA})

    run("5. Over the per-transaction ceiling — mandate blocks it",
        {**base, "invoice_id": "INV-1003", "amount_rupees": "4999.00"})

    run("6. Credit leg fails — funds automatically reversed",
        {**base, "invoice_id": "INV-1004", "amount_rupees": "250.00"},
        fault="credit_fail")

    run("7. Response lost after debit — left in suspense for reconciliation",
        {**base, "invoice_id": "INV-1005", "amount_rupees": "150.00"},
        fault="credit_timeout")

    banner("8. Reconciliation sweep")
    report = sim.reconciler.sweep()
    print(f"  scanned {report.scanned}, outcomes {report.counts}")
    for o in report.outcomes:
        print(f"    {o.action:<10} {o.txn_id}  {d}{o.detail}{x}")

    banner("9. Ledger audit")
    audit = sim.reconciler.audit()
    for key in ("entry_count", "transaction_count", "global_net_paise",
                "suspense_balance_paise"):
        print(f"  {key:<24} {audit[key]}")
    verdict = f"{g}BOOKS BALANCE{x}" if audit["healthy"] else f"{r}DISCREPANCY{x}"
    print(f"  {b}{verdict}{x}")
    if not audit["healthy"]:
        dump(audit)

    banner("10. Final balances")
    for a in sim.store.list_accounts():
        print(f"  {a.vpa:<22} {a.account_type.value:<9} {a.balance}")
    mandate = sim.store.get_mandate(umn)
    print(f"\n  mandate consumed {mandate.consumed} of {mandate.total_cap} "
          f"({mandate.remaining} left)")

    if not audit["healthy"]:
        sys.exit(1)


# --------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(
        prog="upi-agent-sim",
        description="Simulated agentic UPI payments: mandate-gated, fully reconciled.",
    )
    ap.add_argument("--db", default=simulator.DEFAULT_DB)
    ap.add_argument("--fresh", action="store_true", help="wipe the database first")
    ap.add_argument("--no-colour", action="store_true")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("seed").set_defaults(func=cmd_seed)
    sub.add_parser("accounts").set_defaults(func=cmd_accounts)
    sub.add_parser("mandates").set_defaults(func=cmd_mandates)
    sub.add_parser("recon").set_defaults(func=cmd_recon)
    sub.add_parser("audit").set_defaults(func=cmd_audit)

    p = sub.add_parser("txns"); p.set_defaults(func=cmd_txns)
    p.add_argument("--state", choices=[s.value for s in TxnState])
    p.add_argument("--limit", type=int, default=50)

    p = sub.add_parser("events"); p.set_defaults(func=cmd_events)
    p.add_argument("--txn"); p.add_argument("--limit", type=int, default=100)

    p = sub.add_parser("ledger"); p.set_defaults(func=cmd_ledger)
    p.add_argument("--txn")

    p = sub.add_parser("revoke"); p.set_defaults(func=cmd_revoke)
    p.add_argument("umn")

    p = sub.add_parser("consent",
                       help="show the same payment with and without the order gate")
    p.set_defaults(func=cmd_consent)
    p.add_argument("--amount", help="what the agent asks for (default 600)")

    p = sub.add_parser("rails",
                       help="which rail can carry the authority the user set")
    p.set_defaults(func=cmd_rails)
    p.add_argument("--payees", nargs="*", help="VPAs the agent may pay")
    p.add_argument("--categories", nargs="*", help="what it may buy")
    p.add_argument("--cap", help="total cap in rupees (default 5000)")

    p = sub.add_parser("enforce",
                       help="who on a UPI payment could run the two checks")
    p.set_defaults(func=cmd_enforce)

    p = sub.add_parser("demo", help="seed, pay, fail, reconcile, audit")
    p.set_defaults(func=cmd_demo)
    p.add_argument("--no-llm", action="store_true", help="force the deterministic planner")

    p = sub.add_parser("pay", help="drive one agent payment")
    p.set_defaults(func=cmd_pay)
    p.add_argument("--amount", required=True, help="rupees, e.g. 499 or 499.50")
    p.add_argument("--invoice", required=True, help="invoice id (also the idempotency key)")
    p.add_argument("--payee", default=simulator.MERCHANT_VPA)
    p.add_argument("--payer", default=simulator.USER_VPA)
    p.add_argument("--merchant-name", default="Brewhouse Coffee")
    p.add_argument("--plan", default="monthly")
    p.add_argument("--status", default="issued")
    p.add_argument("--description", default="Monthly subscription")
    p.add_argument("--umn", help="mandate to charge against (defaults to the user's first)")
    p.add_argument("--fail", choices=FAULTS, help="inject a fault on the next leg")
    p.add_argument("--no-llm", action="store_true", help="force the deterministic planner")

    args = ap.parse_args()
    # `demo` is a scripted narrative -- it always starts from a clean world so
    # the balances and mandate headroom it prints mean what the script says.
    fresh = args.fresh or args.command in ("demo", "consent")
    sim = simulator.build(db_path=args.db, fresh=fresh)
    try:
        args.func(args, sim)
    finally:
        sim.close()


if __name__ == "__main__":
    main()
