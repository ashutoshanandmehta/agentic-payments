"""
The test bench.

    python3 src/bench.py        then open http://localhost:8010

`console.py` is the owner's app: what did my agent buy, and can I switch it off.
This is the other audience -- you, checking whether the simulation actually says
what the thesis claims it says.

Five panels, in the order the argument runs:

    1  can the authority even be written down?   authority.py
    2  can anyone check it?                      enforcement.py
    3  what does the gate catch?                 consent.py + policy.py
    4  can one agent be switched off?            registration.py
    5  does the money actually move?             orchestrator.py + recon.py

Every number on the page comes from the same code the tests run against. Nothing
here is illustrative -- if a panel says a payment was refused, `policy.evaluate`
refused it.

Stdlib only, and no network: the page loads no fonts, scripts or styles from
anywhere. It works on a laptop with the wifi off, which is the point.
"""

from __future__ import annotations

import json
import threading
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import sim as world
from authority import RAIL_LIMITS, compare_rails
from consent import Order, OrderSigner
from core import Money
from enforcement import (
    CHECK_NEEDS,
    CHECK_QUESTION,
    UPI_TODAY,
    Check,
    Evidence,
    report,
    with_cart_reference,
)
from identity import Signer
from models import PaymentIntent, utcnow
from policy import PolicyConfig
from rails import FAULTS

STATE: dict = {"sim": None, "n": 0}
LOCK = threading.Lock()

DB = "bench.db"


# --------------------------------------------------------------------------
# World
# --------------------------------------------------------------------------

def build() -> None:
    sim = world.build(db_path=DB, fresh=True,
                      policy_config=PolicyConfig(require_order=False))
    world.seed(sim)
    STATE["sim"], STATE["n"] = sim, 0


def sim():
    if STATE["sim"] is None:
        build()
    return STATE["sim"]


def _next() -> int:
    STATE["n"] += 1
    return STATE["n"]


# --------------------------------------------------------------------------
# 1. Which rail can carry the authority
# --------------------------------------------------------------------------

def panel_rails(payees: list[str], categories: list[str], cap: str) -> dict:
    cap_money = Money.rupees(str(cap or "5000"))
    results = compare_rails(payees, categories, cap_money)
    return {
        "authority": {
            "payees": payees,
            "categories": categories,
            "cap": cap_money.to_rupees_str(),
        },
        "rails": [
            {
                "rail": rail.value,
                "description": RAIL_LIMITS[rail].description,
                "source": RAIL_LIMITS[rail].source_note,
                "expressible": verdict.expressible,
                "losses": verdict.losses,
            }
            for rail, verdict in results.items()
        ],
        "any": any(v.expressible for v in results.values()),
    }


# --------------------------------------------------------------------------
# 2. Who could run the check
# --------------------------------------------------------------------------

def panel_enforce(cart_reference: bool) -> dict:
    topology = with_cart_reference() if cart_reference else UPI_TODAY
    result = report(topology)

    reasons = {(f["check"], f["party"]): f for f in result["findings"]}
    parties = []
    for view in topology.values():
        parties.append({
            "party": view.party.value,
            "role": view.role,
            "exists": view.exists_on_upi,
            "conflict": None if view.trusted else view.conflict.value,
            "holds": sorted(e.value for e in view.sees),
            "checks": {
                check.value: {
                    "can": reasons[(check.value, view.party.value)]["can_enforce"],
                    "reason": reasons[(check.value, view.party.value)]["reason"],
                    "missing": view.missing_for(check),
                }
                for check in Check
            },
        })

    return {
        "cart_reference": cart_reference,
        "documents": [e.value for e in Evidence],
        "needs": {c.value: sorted(e.value for e in CHECK_NEEDS[c]) for c in Check},
        "questions": {c.value: CHECK_QUESTION[c] for c in Check},
        "parties": parties,
        "enforcers": result["enforcers"],
        "unenforceable": result["unenforceable"],
    }


# --------------------------------------------------------------------------
# 3. The order gate
# --------------------------------------------------------------------------

def panel_gate(lines, charged, per_txn, signer, gate_on,
               order_category, authority_categories, agreed=None) -> dict:
    s = sim()
    now = utcnow()

    # An explicit agreed total replaces the itemised basket with a single line.
    # The lines only exist to make the default look like a real invoice; the
    # experiment is the relationship between the total and what is charged.
    if str(agreed or "").strip():
        parsed = [("Basket", str(agreed).strip())]
    else:
        parsed = [(str(t), str(a)) for t, a in lines if str(a).strip()]
    if not parsed:
        # the canonical basket used everywhere else in the project: 99 + 19 = 118
        parsed = [("Monthly plan", "99"), ("GST", "19")]

    mandate = s.orchestrator.create_mandate(
        payer_vpa=world.USER_VPA,
        allowed_payees=[world.MERCHANT_VPA],
        max_amount_per_txn=Money.rupees(str(per_txn or "1000")),
        total_cap=Money.rupees("50000"),
        valid_from=now - timedelta(minutes=1),
        valid_until=now + timedelta(days=90),
        purpose="bench",
        agent_id=s.agent_name,
        categories=[c for c in (authority_categories or []) if c],
    )

    order = Order.build(f"ORD-{_next()}", world.MERCHANT_VPA, parsed,
                        category=order_category or "general")
    chosen = OrderSigner(signer or "agent")
    order.sign(chosen, s.agent_key, s.merchant_keys[world.MERCHANT_VPA])

    amount = Money.rupees(str(charged or order.total.to_rupees_str()))
    intent = PaymentIntent(True, world.MERCHANT_VPA, amount,
                           "bench payment", 0.95, "rule")

    s.policy.config.require_order = bool(gate_on)
    s.policy.order_signer = chosen
    verdict = s.policy.evaluate(intent, world.USER_VPA, mandate,
                                order if gate_on else None)

    return {
        "agreed": order.total.to_rupees_str(),
        "charged": amount.to_rupees_str(),
        "gap": (amount - order.total).to_rupees_str(),
        "lines": [{"title": l.title, "amount": l.amount.to_rupees_str()}
                  for l in order.lines],
        "order_category": order.category,
        "signed_by": sorted(order.signatures),
        "gate_on": bool(gate_on),
        "allowed": verdict.allowed,
        "code": verdict.code,
        "checks": verdict.checks,
        "reasons": verdict.reasons,
        "passed": sum(1 for c in verdict.checks if c["passed"]),
        "total_checks": len(verdict.checks),
    }


# --------------------------------------------------------------------------
# 4. Agents on one device
# --------------------------------------------------------------------------

def panel_agents() -> dict:
    s = sim()
    registry = s.registry
    out = []
    for reg in registry._by_id.values():
        ok, reasons, claims = registry.verify(reg.token)
        out.append({
            "agent_id": reg.agent_id,
            "did": reg.agent_did,
            "device_id": reg.device_id,
            "status_index": reg.status_index,
            "revoked": registry.is_revoked(reg.agent_id),
            "valid": ok,
            "reasons": reasons,
            "attestation": claims.get("attestation", {}),
            "token": reg.token,
        })
    return {
        "owner": registry.owner_key.did,
        "owner_vpa": registry.owner_vpa,
        "device": world.DEVICE_ID,
        "agents": out,
        "status_list": registry.status_credential(),
    }


def register_agent(agent_id: str, device_id: str) -> dict:
    s = sim()
    s.registry.register_agent(
        Signer(agent_id), device_id=device_id or world.DEVICE_ID,
        agent_id=agent_id,
    )
    return panel_agents()


# --------------------------------------------------------------------------
# 5. Does the money move
# --------------------------------------------------------------------------

def panel_pay(amount: str, fault: str | None, with_order: bool,
              suppress_duplicates: bool = False) -> dict:
    """Send one payment through the rails, optionally breaking it on the way.

    Duplicate suppression is off by default here and on in the real policy. On a
    bench you send the same ₹118 over and over, and the operator guardrail would
    refuse every one after the first -- correctly, but it would look like the
    fault injection was broken. It stays available as a toggle rather than being
    quietly disabled, because suppressing a retried charge is a feature worth
    seeing work.
    """
    s = sim()
    n = _next()
    now = utcnow()

    mandate = s.orchestrator.create_mandate(
        payer_vpa=world.USER_VPA,
        allowed_payees=[world.MERCHANT_VPA],
        max_amount_per_txn=Money.rupees("5000"),
        total_cap=Money.rupees("50000"),
        valid_from=now - timedelta(minutes=1),
        valid_until=now + timedelta(days=90),
        purpose="bench payment",
        agent_id=s.agent_name,
    )

    money = Money.rupees(str(amount or "118"))
    order = None
    if with_order:
        order = Order.build(f"PAY-{n}", world.MERCHANT_VPA,
                            [("Bench item", money.to_rupees_str())])
        order.sign(s.policy.order_signer, s.agent_key,
                   s.merchant_keys[world.MERCHANT_VPA])

    s.policy.config.require_order = bool(with_order)
    s.policy.config.duplicate_window_seconds = 120 if suppress_duplicates else 0
    if fault and fault in FAULTS:
        s.faults.force = fault

    result = s.orchestrator.execute(
        intent=PaymentIntent(True, world.MERCHANT_VPA, money,
                             "bench payment", 0.95, "rule"),
        payer_vpa=world.USER_VPA, idempotency_key=f"bench-{n}",
        umn=mandate.umn, order=order, agent_id=s.agent_name,
    )
    s.faults.force = None

    recon = None
    if result.txn is not None and not result.txn.state.is_terminal:
        recon = s.reconciler.sweep().to_dict()

    txn = s.store.get_txn(result.txn.txn_id) if result.txn else None
    entries = s.store.ledger_for_txn(txn.txn_id) if txn else []

    return {
        "ok": result.ok,
        "state": txn.state.value if txn else "never created",
        "code": txn.response_code if txn else result.verdict.code,
        "amount": money.to_rupees_str(),
        "agent_id": txn.agent_id if txn else None,
        "rrn": txn.rrn if txn else None,
        "trace": result.trace or [],
        "reasons": result.verdict.reasons,
        "ledger": [
            {"account": e.account_id, "direction": e.direction.value,
             "amount": e.amount.to_rupees_str(), "narrative": e.narrative}
            for e in entries
        ],
        "recon": recon,
        "audit": s.reconciler.audit(),
        "balances": [
            {"vpa": a.vpa, "type": a.account_type.value,
             "balance": a.balance.to_rupees_str()}
            for a in s.store.list_accounts()
        ],
        "faults": list(FAULTS),
    }


# --------------------------------------------------------------------------
# Server
# --------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj):
        self._send(200, json.dumps(obj, default=str).encode(), "application/json")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif self.path == "/api/agents":
            with LOCK:
                self._json(panel_agents())
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        try:
            with LOCK:
                self._json(self._route(self.path, body))
        except Exception as exc:                              # noqa: BLE001
            self._json({"error": f"{type(exc).__name__}: {exc}"})

    def _route(self, path, body):
        if path == "/api/rails":
            return panel_rails(
                [p for p in body.get("payees", []) if p],
                [c for c in body.get("categories", []) if c],
                body.get("cap", "5000"),
            )
        if path == "/api/enforce":
            return panel_enforce(bool(body.get("cart_reference")))
        if path == "/api/gate":
            return panel_gate(
                body.get("lines", []), body.get("charged"), body.get("per_txn"),
                body.get("signer", "agent"), body.get("gate_on", True),
                body.get("order_category", "general"),
                body.get("authority_categories", []),
                body.get("agreed"),
            )
        if path == "/api/agents/register":
            return register_agent(body.get("agent_id", ""), body.get("device_id", ""))
        if path == "/api/agents/revoke":
            sim().registry.revoke_agent(body.get("agent_id", ""))
            return panel_agents()
        if path == "/api/pay":
            return panel_pay(body.get("amount"), body.get("fault"),
                             bool(body.get("with_order")),
                             bool(body.get("suppress_duplicates")))
        if path == "/api/reset":
            build()
            return {"ok": True}
        raise ValueError(f"no such endpoint: {path}")

    def log_message(self, *a):
        pass


# --------------------------------------------------------------------------
# The page
#
# Warm light, rounded, soft-edged. Light only.
#
# A delegated payment produces four documents, each party holds some of them,
# and a check needs two specific ones in the same pair of hands. The panel that
# matters is literally that: rows of parties, pills for the copies they hold.
#
# Blind is amber and conflicted is red, everywhere, because only one of those
# two is fixable by changing the rail. The colour is carrying the argument.
# --------------------------------------------------------------------------

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Delegated payments &mdash; test bench</title>
<style>
/* ------------------------------------------------------------------
   Warm light, rounded, soft-edged. Light only -- every colour stated,
   no dark blocks.

   Type: `ui-rounded` resolves to SF Pro Rounded on Apple platforms,
   with rounded fallbacks after it. Monospace is kept only where digits
   have to line up -- amounts, ledger columns, identifiers -- because a
   rounded face with proportional figures makes a column of rupees
   unreadable.

   Brackets still enclose. A cart has to fit INSIDE an authority, so
   containment is the one structural idea, and a payment that does not
   fit is drawn breaking out of its brackets.
   ------------------------------------------------------------------ */
:root{
  --paper:#f7f1e7; --sheet:#ffffff; --sunk:#f2ebe0; --edge:#fbf7f0;
  --rule:#e8ddcc; --rule2:#f0e8db;
  --ink:#2b241c; --dim:#6f6455; --faint:#9c9081;
  --blue:#12439b; --blue-soft:#e6ecfa; --sky:#1ba3e0;
  --madder:#c2392c; --madder-soft:#fbe7e4;
  --marigold:#bf7a08; --marigold-soft:#fcf0d9;
  --bottle:#1d7a55; --bottle-soft:#e2f2ea;
  --r:16px; --r-sm:11px; --pill:999px;
  --shadow:0 1px 2px rgba(43,36,28,.05), 0 6px 20px rgba(43,36,28,.05);
  --round:ui-rounded,"SF Pro Rounded","Hiragino Maru Gothic ProN",Quicksand,Nunito,
          "Varela Round",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--paper)}
body{color:var(--ink);font:15px/1.62 var(--round);-webkit-font-smoothing:antialiased}
.mono{font-family:var(--mono)}
::selection{background:var(--blue);color:#fff}

/* ---------- top bar ---------- */
.topbar{
  display:flex;align-items:center;gap:.95rem;
  padding:.85rem 1.5rem;background:var(--sheet);
  border-bottom:1px solid var(--rule);position:sticky;top:0;z-index:20;
}
.mark{
  font-family:var(--mono);font-size:1.5rem;font-weight:700;line-height:1;
  color:var(--blue);letter-spacing:-.07em;user-select:none;
  background:var(--blue-soft);border-radius:var(--r-sm);padding:.3rem .55rem;
}
.mark span{color:var(--madder);font-size:1rem;vertical-align:.12em;margin:0 .04em}
.topbar h1{margin:0;font-size:1rem;font-weight:700;letter-spacing:-.01em;color:var(--ink)}
.topbar p{margin:.06rem 0 0;font-size:.78rem;color:var(--faint)}
.env{
  margin-left:auto;font-size:.72rem;color:var(--dim);font-weight:600;
  background:var(--sunk);border-radius:var(--pill);padding:.32rem .8rem;
}
.env b{color:var(--bottle);font-weight:700}

/* ---------- shell ---------- */
.shell{display:grid;grid-template-columns:16.5rem 1fr;min-height:calc(100vh - 3.6rem)}
@media(max-width:900px){.shell{grid-template-columns:1fr}}

/* ---------- index ---------- */
.index{padding:1.3rem .75rem;background:var(--paper)}
@media(max-width:900px){.index{border-bottom:1px solid var(--rule)}}
.idxlabel{
  font-size:.7rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
  color:var(--faint);padding:0 .7rem .7rem;
}
.index ol{list-style:none;margin:0;padding:0;display:grid;gap:.25rem}
.index button{
  width:100%;text-align:left;background:none;border:0;cursor:pointer;color:var(--dim);
  font:inherit;padding:.65rem .8rem;display:grid;grid-template-columns:1.9rem 1fr;
  gap:.45rem;align-items:center;border-radius:var(--r-sm);
}
.index button .n{
  font-family:var(--mono);font-size:.7rem;font-weight:700;color:var(--faint);
  background:var(--sunk);border-radius:var(--pill);padding:.16rem 0;text-align:center;
}
.index button .t{font-size:.85rem;line-height:1.35;font-weight:500}
.index button:hover{background:var(--sheet);color:var(--ink)}
.index button:focus-visible{outline:2px solid var(--blue);outline-offset:1px}
.index li[aria-current=true] button{
  background:var(--sheet);color:var(--ink);font-weight:700;box-shadow:var(--shadow);
}
.index li[aria-current=true] .n{background:var(--blue);color:#fff}
.idxfoot{padding:1rem .8rem 0;margin-top:.8rem;border-top:1px solid var(--rule)}

/* ---------- panel ---------- */
main{padding:2rem 2.2rem 5rem;max-width:66rem}
@media(max-width:900px){main{padding:1.4rem 1.05rem 4rem}}
.eyebrow{
  font-size:.74rem;font-weight:700;letter-spacing:.05em;color:var(--blue);
  margin:0 0 .5rem;background:var(--blue-soft);display:inline-block;
  padding:.22rem .7rem;border-radius:var(--pill);
}
h2{margin:0;font-size:1.62rem;font-weight:700;letter-spacing:-.025em;line-height:1.22}
.lede{margin:.6rem 0 0;color:var(--dim);font-size:.95rem;max-width:48rem}
.rule{border:0;border-top:1px solid var(--rule);margin:1.4rem 0}

/* ---------- controls: soft, filled, rounded ---------- */
.form{display:flex;flex-wrap:wrap;gap:1rem 1.3rem;align-items:flex-end}
.field{display:flex;flex-direction:column;gap:.38rem}
label{font-size:.76rem;font-weight:600;color:var(--dim)}
input,select{
  font:inherit;font-size:.92rem;font-weight:500;color:var(--ink);
  background:var(--sheet);border:1.5px solid var(--rule);border-radius:var(--r-sm);
  padding:.62rem .8rem;min-width:8.5rem;transition:border-color .12s,box-shadow .12s;
}
input::placeholder{color:var(--faint);font-weight:400}
input.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
input:hover,select:hover{border-color:#d9cbb4}
input:focus,select:focus{outline:0;border-color:var(--blue);box-shadow:0 0 0 4px var(--blue-soft)}
button.act{
  font:inherit;font-size:.88rem;font-weight:700;cursor:pointer;
  background:var(--blue);color:#fff;border:1.5px solid var(--blue);
  border-radius:var(--pill);padding:.6rem 1.25rem;transition:filter .12s,transform .06s;
}
button.act:hover{filter:brightness(1.12)}
button.act:active{transform:translateY(1px)}
button.act.ghost{background:var(--sheet);color:var(--blue);border-color:var(--rule)}
button.act.ghost:hover{border-color:var(--blue);filter:none}
button.act:focus-visible{outline:2px solid var(--sky);outline-offset:2px}
.toggle{display:inline-flex;background:var(--sunk);border-radius:var(--pill);padding:.2rem;gap:.15rem}
.toggle button{
  font:inherit;font-size:.82rem;font-weight:600;padding:.42rem .9rem;border:0;
  cursor:pointer;background:transparent;color:var(--dim);border-radius:var(--pill);
}
.toggle button:hover{color:var(--ink)}
.toggle button[aria-pressed=true]{background:var(--sheet);color:var(--blue);font-weight:700;box-shadow:var(--shadow)}
.chips{display:flex;flex-wrap:wrap;gap:.35rem;align-items:center}
.chip{
  display:inline-flex;align-items:center;gap:.4rem;font-size:.82rem;font-weight:600;
  background:var(--blue-soft);color:var(--blue);border-radius:var(--pill);
  padding:.34rem .5rem .34rem .8rem;
}
.chip button{border:0;background:none;cursor:pointer;color:var(--blue);opacity:.55;
  line-height:1;padding:0 .15rem;font-size:1rem}
.chip button:hover{opacity:1;color:var(--madder)}

/* ---------- verdict ---------- */
.verdict{
  display:flex;flex-wrap:wrap;align-items:center;gap:.9rem 1.4rem;
  border-radius:var(--r);background:var(--sheet);padding:1rem 1.25rem;margin:1.3rem 0;
  box-shadow:var(--shadow);border:1px solid var(--rule2);
}
.verdict.no{background:var(--madder-soft);border-color:#f3d5d0}
.verdict.yes{background:var(--bottle-soft);border-color:#cfe6da}
.verdict.warn{background:var(--marigold-soft);border-color:#f0dfbc}
.vword{font-size:1.1rem;font-weight:700;letter-spacing:.01em}
.verdict.no .vword{color:var(--madder)}
.verdict.yes .vword{color:var(--bottle)}
.verdict.warn .vword{color:var(--marigold)}
.vsub{font-size:.79rem;color:var(--dim);margin-top:.12rem;font-weight:500}
.vtally{font-size:.85rem;color:var(--dim);margin-left:auto;text-align:right}
.vtally b{color:var(--ink);font-weight:700}
@media(prefers-reduced-motion:no-preference){
  .verdict{animation:in .2s ease-out}
  @keyframes in{from{opacity:0;transform:translateY(-3px)}to{opacity:1;transform:none}}
}

/* ---------- containment: the signature ---------- */
.contain{display:flex;align-items:stretch;gap:.55rem;margin:.2rem 0 .5rem}
.brk{
  font-family:var(--mono);font-size:2.9rem;line-height:1;color:var(--blue);
  font-weight:300;user-select:none;display:flex;align-items:center;
}
.brk.broken{color:var(--madder)}
.track{
  flex:1;position:relative;background:var(--sunk);border-radius:var(--r-sm);
  height:2.9rem;overflow:hidden;
}
.seg{position:absolute;top:0;bottom:0}
.seg.agreed{background:var(--blue);opacity:.85;border-radius:var(--r-sm) 0 0 var(--r-sm)}
.seg.over{background:repeating-linear-gradient(45deg,var(--madder) 0 6px,transparent 6px 13px);opacity:.75}
.spill{
  width:4.6rem;background-color:var(--madder-soft);border-radius:var(--r-sm);
  background-image:repeating-linear-gradient(45deg,rgba(194,57,44,.45) 0 6px,transparent 6px 13px);
  border:1.5px solid var(--madder);height:2.9rem;
  display:grid;place-items:center;font-size:.72rem;color:var(--madder);font-weight:700;
}
.containkey{display:flex;flex-wrap:wrap;gap:1.2rem;font-size:.78rem;color:var(--dim);margin-top:.5rem}
.containkey i{font-style:normal;display:inline-block;width:.7rem;height:.7rem;
  border-radius:3px;margin-right:.4rem;vertical-align:-.05rem}
.k-agreed i{background:var(--blue)} .k-over i{background:var(--madder)} .k-cap i{background:var(--ink)}

/* ---------- cards ---------- */
.card{background:var(--sheet);border:1px solid var(--rule2);border-radius:var(--r);
  padding:1.1rem 1.25rem;box-shadow:var(--shadow)}
.card.no{border-left:4px solid var(--madder)}
.card.yes{border-left:4px solid var(--bottle)}
.card h3{margin:0;font-size:.98rem;font-weight:700;letter-spacing:-.01em}
.card h3.mono{font-family:var(--mono);font-size:.88rem}
.card .why{margin:.35rem 0 0;font-size:.85rem;color:var(--dim)}
.stack{display:grid;gap:.65rem}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(17rem,1fr));gap:.65rem}

/* ---------- matrix ---------- */
.matrix{width:100%;border-collapse:collapse;font-size:.85rem}
.matrix th{
  text-align:left;font-size:.74rem;font-weight:700;color:var(--faint);
  padding:0 .55rem .6rem;vertical-align:bottom;
}
.matrix td{border-top:1px solid var(--rule2);padding:.6rem .55rem;vertical-align:middle}
.matrix tr.gone{opacity:.45}
.matrix .who{font-size:.86rem;white-space:nowrap;font-weight:700}
.matrix .who small{display:block;font-weight:400;color:var(--faint);font-size:.76rem;
  white-space:normal;max-width:18rem;margin-top:.14rem}
.docs{display:flex;align-items:center;gap:.25rem}
.docs .b{font-family:var(--mono);color:var(--blue);font-size:1.15rem;opacity:.45}
.doc{
  min-width:2.4rem;text-align:center;font-family:var(--mono);font-size:.62rem;
  font-weight:700;letter-spacing:.05em;border-radius:var(--pill);
  padding:.3rem .3rem;color:var(--faint);background:var(--sunk);
}
.doc.held{background:var(--blue);color:#fff}
.doc.need{box-shadow:0 0 0 2.5px var(--marigold)}
.doc.gained{background:var(--bottle);color:#fff}
.res{font-size:.8rem;font-weight:600;white-space:nowrap}
.res.blind{color:var(--marigold)} .res.conflicted{color:var(--madder)}
.res.can{color:var(--bottle);font-weight:700} .res.absent{color:var(--faint)}

/* ---------- checks ---------- */
.checks{list-style:none;margin:.6rem 0 0;padding:0}
.checks li{
  display:grid;grid-template-columns:1.2rem 1fr auto;gap:.55rem;align-items:baseline;
  padding:.34rem 0;border-top:1px solid var(--rule2);font-size:.85rem;
}
.checks li:first-child{border-top:0}
.checks .m{font-weight:700;font-size:.85rem}
.checks .m.ok{color:var(--bottle)} .checks .m.no{color:var(--madder)}
.checks .nm{font-family:var(--mono);font-size:.78rem;color:var(--dim)}
.checks li.failed .nm{color:var(--madder);font-weight:600}
.checks .dt{font-family:var(--mono);color:var(--faint);font-size:.74rem;text-align:right}
.reasons{list-style:none;margin:.9rem 0 0;padding:0;display:grid;gap:.4rem}
.reasons li{
  font-size:.85rem;color:var(--madder);background:var(--madder-soft);
  border-radius:var(--r-sm);padding:.5rem .75rem;font-weight:500;
}

/* ---------- misc ---------- */
.kv{display:grid;grid-template-columns:auto 1fr;gap:.22rem .9rem;font-size:.8rem}
.kv dt{font-size:.75rem;font-weight:600;color:var(--faint)}
.kv dd{margin:0;font-family:var(--mono);word-break:break-all;color:var(--dim);font-size:.76rem}
.note{font-size:.82rem;color:var(--dim);margin:.9rem 0 0;max-width:52rem;
  background:var(--edge);border-radius:var(--r-sm);padding:.7rem .9rem}
.note b{color:var(--marigold);font-weight:700}
.src{font-size:.76rem;color:var(--faint);margin-top:.6rem}
.hint{font-size:.82rem;color:var(--faint);margin-top:.65rem}
.trace{list-style:none;margin:.55rem 0 0;padding:0;font-size:.84rem}
.trace li{display:grid;grid-template-columns:6.2rem 1fr;gap:.6rem;padding:.32rem 0;
  border-top:1px solid var(--rule2)}
.trace li:first-child{border-top:0}
.trace .st{font-size:.72rem;font-weight:700;color:var(--blue)}
table.led{width:100%;border-collapse:collapse;font-size:.8rem}
table.led th{text-align:left;font-size:.73rem;font-weight:700;color:var(--faint);padding:0 .55rem .45rem}
table.led td{border-top:1px solid var(--rule2);padding:.4rem .55rem;color:var(--dim);
  font-family:var(--mono);font-size:.78rem}
table.led td.dr{color:var(--madder);font-weight:600}
table.led td.cr{color:var(--bottle);font-weight:600}
.empty{color:var(--faint);font-size:.88rem}
.err{color:var(--madder);font-size:.86rem;background:var(--madder-soft);
  border-radius:var(--r-sm);padding:.7rem .9rem}
</style></head><body>

<header class="topbar">
  <div class="mark" aria-hidden="true">[<span>&#8377;</span>]</div>
  <div>
    <h1>Delegated payments</h1>
    <p>test bench &middot; every figure comes from the code the tests run</p>
  </div>
  <div class="env"><b>&bull;</b> runs offline</div>
</header>

<div class="shell">
  <nav class="index" aria-label="Experiments">
    <p class="idxlabel">Experiments</p>
    <ol id="nav"></ol>
    <div class="idxfoot"><button class="act ghost" onclick="reset()">Reset the world</button></div>
  </nav>
  <main id="panel"><p class="empty">Loading&hellip;</p></main>
</div>

<script>
const PANELS = [
  {id:'rails',   t:'Can the authority be written down?'},
  {id:'enforce', t:'Can anyone check it?'},
  {id:'gate',    t:'What does the gate catch?'},
  {id:'agents',  t:'Can one agent be switched off?'},
  {id:'pay',     t:'Does the money actually move?'},
];

let current = 'rails';
const S = {
  rails:  {payees:['brewhouse@ybl','cloudhost@okaxis'], categories:['groceries'], cap:'5000'},
  enforce:{cart_reference:false},
  gate:   {lines:[['Monthly plan','99'],['GST','19']], agreed:'', charged:'600',
           per_txn:'1000', signer:'agent', gate_on:true,
           order_category:'general', authority_categories:[]},
  pay:    {amount:'118', fault:'', with_order:true, suppress_duplicates:false},
};
const DATA = {};

const post = (u,b) => fetch(u,{method:'POST',body:JSON.stringify(b||{})}).then(r=>r.json());
const esc = s => String(s??'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const el = id => document.getElementById(id);
const num = v => Number(String(v).replace(/[^\d.-]/g,'')) || 0;

function drawNav(){
  el('nav').innerHTML = PANELS.map((p,i)=>`
    <li aria-current="${p.id===current}">
      <button onclick="go('${p.id}')">
        <span class="n">${String(i+1).padStart(2,'0')}</span>
        <span class="t">${esc(p.t)}</span>
      </button>
    </li>`).join('');
}

async function go(id){ current=id; drawNav(); await refresh(); }

async function refresh(){
  const p = current;
  if(p==='rails')   DATA.rails   = await post('/api/rails', S.rails);
  if(p==='enforce') DATA.enforce = await post('/api/enforce', S.enforce);
  if(p==='gate')    DATA.gate    = await post('/api/gate', S.gate);
  if(p==='agents')  DATA.agents  = await (await fetch('/api/agents')).json();
  draw();
}

async function reset(){ await post('/api/reset'); DATA.pay=null; await refresh(); }

function verdict(kind, word, sub, tally){
  return `<div class="verdict ${kind}">
    <div><div class="vword">${esc(word)}</div><div class="vsub">${esc(sub||'')}</div></div>
    ${tally?`<div class="vtally">${tally}</div>`:''}
  </div>`;
}

function head(n, title, lede){
  return `<p class="eyebrow">Experiment ${String(n).padStart(2,'0')}</p>
          <h2>${esc(title)}</h2><p class="lede">${lede}</p><hr class="rule">`;
}

/* ---------------- 01 rails ---------------- */
function drawRails(){
  const d = DATA.rails; if(!d) return '';
  const chip = (v,k,i) => `<span class="chip">${esc(v)}<button onclick="dropChip('${k}',${i})" aria-label="Remove ${esc(v)}">&times;</button></span>`;
  const carried = d.rails.filter(r=>r.expressible).length;
  return head(1,'Can the authority be written down?',
    'One authority, put to each rail. A rail that cannot carry it reports exactly which of the user&rsquo;s instructions it would have to discard.')
  + `<div class="form">
      <div class="field"><label>Shops the agent may pay</label>
        <div class="chips">${S.rails.payees.map((p,i)=>chip(p,'payees',i)).join('')}
        <input id="np" placeholder="add a VPA" style="min-width:9rem" onkeydown="if(event.key==='Enter')addChip('payees','np')"></div></div>
      <div class="field"><label>What it may buy</label>
        <div class="chips">${S.rails.categories.map((c,i)=>chip(c,'categories',i)).join('')}
        <input id="nc" placeholder="add a category" style="min-width:9rem" onkeydown="if(event.key==='Enter')addChip('categories','nc')"></div></div>
      <div class="field"><label>Total cap &#8377;</label>
        <input class="mono" style="min-width:6.5rem" value="${esc(S.rails.cap)}" onchange="S.rails.cap=this.value;refresh()"></div>
     </div>`
  + verdict(d.any?'yes':'no',
      d.any?'EXPRESSIBLE':'NO VOCABULARY',
      d.any?'a rail can record this':'no rail can record this',
      `<b>${carried}</b> of <b>${d.rails.length}</b> rails can say what the user said`)
  + `<div class="stack">
       ${d.rails.map(r=>`
        <div class="card ${r.expressible?'yes':'no'}">
          <h3 class="mono">${esc(r.rail)}</h3>
          <p class="why">${esc(r.description)}</p>
          ${r.losses.length ? `<ul class="reasons">${r.losses.map(l=>`<li>${esc(l)}</li>`).join('')}</ul>`
                            : `<p class="why" style="color:var(--pass)">Carries every part of this authority.</p>`}
          <p class="src">source &middot; ${esc(r.source)}</p>
        </div>`).join('')}
     </div>
     <p class="note"><b>Unverified.</b> The money ceilings come from the brief&rsquo;s secondary sources. NPCI OC 228 and 201-B have not been read. The scope limits &mdash; what each rail can and cannot name &mdash; are the well-attested part.</p>`;
}
function addChip(key, inputId){
  const v = el(inputId).value.trim(); if(!v) return;
  S.rails[key].push(v); refresh();
}
function dropChip(key, i){ S.rails[key].splice(i,1); refresh(); }

/* ---------------- 02 enforcement ---------------- */
const DOCLABEL = {authority:'AUT', cart:'CRT', payment_request:'REQ', settlement:'STL'};

function drawEnforce(){
  const d = DATA.enforce; if(!d) return '';
  const rows = check => d.parties.map(p=>{
    const c = p.checks[check], need = d.needs[check];
    let cls='absent', word='not on this rail';
    if(p.exists){
      if(c.can){ cls='can'; word='CAN RUN IT'; }
      else if(c.missing.length){ cls='blind'; word='blind &middot; no '+c.missing.join(' + '); }
      else { cls='conflicted'; word='conflicted'; }
    }
    const gained = d.cart_reference && p.party==='remitter_bank';
    return `<tr class="${p.exists?'':'gone'}">
      <td class="who">${esc(p.party)}<small>${esc(p.role)}</small></td>
      <td><div class="docs"><span class="b">[</span>${d.documents.map(doc=>{
        const held = p.holds.includes(doc);
        const isNew = gained && doc==='cart';
        return `<span class="doc ${held?(isNew?'gained':'held'):''} ${need.includes(doc)?'need':''}" title="${esc(doc)}${held?' — holds a copy':' — no copy'}">${DOCLABEL[doc]}</span>`;
      }).join('')}<span class="b">]</span></div></td>
      <td class="res ${cls}">${word}</td>
    </tr>`;
  }).join('');

  const blocked = d.unenforceable.length;
  return head(2,'Can anyone check it?',
    'A delegated payment produces four documents, and each party holds only some of them. A check needs two specific copies <em>in the same pair of hands</em> &mdash; and a party holding both still has to be one you would trust.')
  + `<div class="form">
      <div class="field"><label>Rail</label>
        <div class="toggle">
          <button aria-pressed="${!d.cart_reference}" onclick="S.enforce.cart_reference=false;refresh()">UPI as it is</button>
          <button aria-pressed="${d.cart_reference}" onclick="S.enforce.cart_reference=true;refresh()">Carrying a cart reference</button>
        </div></div>
     </div>`
  + verdict(blocked?'no':'yes',
      blocked?'UNENFORCEABLE':'ENFORCEABLE',
      blocked?('checks '+d.unenforceable.join(' and ')):'by the remitter bank',
      blocked ? 'Every party is either <b>blind</b> or <b>conflicted</b>.'
              : 'One added copy. Both checks land with the party that already decides whether to debit.')
  + Object.keys(d.questions).map(ck=>`
      <div class="card" style="margin-bottom:.6rem">
        <h3>Check ${esc(ck)} <span style="font-weight:400;color:var(--dim)">&mdash; ${esc(d.questions[ck])}</span></h3>
        <p class="why">Needs the <b class="mono" style="color:var(--cyan)">${d.needs[ck].map(x=>DOCLABEL[x]).join('</b> and <b class="mono" style="color:var(--cyan)">')}</b> copy, outlined below.</p>
        <table class="matrix" style="margin-top:.7rem">
          <thead><tr><th>Party</th><th>Copies held</th><th>Verdict</th></tr></thead>
          <tbody>${rows(ck)}</tbody>
        </table>
      </div>`).join('')
  + `<p class="note">Blind is amber and conflicted is red on purpose: <b>only blindness can be fixed by changing the rail.</b> Handing the merchant the authority copy would not make it trustworthy &mdash; it earns more when the amount is higher.</p>`;
}

/* ---------------- 03 order gate ---------------- */
const gapOf = d => num(d.gap);

function gateStamp(d){
  const gap = gapOf(d);
  if(d.allowed) return gap > 0 ? ['no','ALLOWED','overcharge permitted']
                               : ['yes','ALLOWED', d.code];
  return gap > 0 ? ['yes','REFUSED','overcharge caught']
                 : ['warn','REFUSED','an honest payment stopped'];
}

/* The signature: the authority is a pair of brackets and the payment is a bar
   inside them. An overcharge overruns the agreed segment; a payment over the
   ceiling breaks out past the closing bracket entirely. */
function containment(d){
  const agreed = num(d.agreed), charged = num(d.charged), cap = num(S.gate.per_txn);
  if(cap <= 0) return '';
  const pct = v => +Math.max(0, Math.min(100, (v/cap)*100)).toFixed(2);
  const over = charged > agreed;
  const breaks = charged > cap;
  return `<div class="contain">
      <span class="brk">[</span>
      <div class="track">
        <div class="seg agreed" style="left:0;width:${pct(agreed)}%"></div>
        ${over?`<div class="seg over" style="left:${pct(agreed)}%;width:${pct(Math.min(charged,cap))-pct(agreed)}%"></div>`:''}
      </div>
      <span class="brk ${breaks?'broken':''}">]</span>
      ${breaks?`<div class="spill" title="${esc(d.charged)} is past the ceiling">OVER</div>`:''}
    </div>
    <div class="containkey">
      <span class="k-agreed"><i></i>agreed ${esc(d.agreed)}</span>
      ${over?`<span class="k-over"><i></i>charged ${esc(d.charged)}</span>`:''}
      <span class="k-cap"><i></i>ceiling &#8377;${esc(S.gate.per_txn)} &mdash; the brackets</span>
    </div>`;
}

function drawGate(){
  const d = DATA.gate; if(!d) return '';
  const g = S.gate, v = gateStamp(d);
  return head(3,'What does the gate catch?',
    'The mandate says how much may be spent and with whom. It does not know what the user agreed to buy. Change the charge and watch which limit refuses it &mdash; and which one does not.')
  + `<div class="form">
      <div class="field"><label>User agreed to &#8377;</label>
        <input class="mono" style="min-width:6.5rem" value="${esc(d.agreed)}" onchange="S.gate.agreed=this.value;refresh()"></div>
      <div class="field"><label>Agent charges &#8377;</label>
        <input class="mono" style="min-width:6.5rem" value="${esc(g.charged)}" onchange="S.gate.charged=this.value;refresh()"></div>
      <div class="field"><label>Per-payment ceiling &#8377;</label>
        <input class="mono" style="min-width:6.5rem" value="${esc(g.per_txn)}" onchange="S.gate.per_txn=this.value;refresh()"></div>
      <div class="field"><label>Order signed by</label>
        <select onchange="S.gate.signer=this.value;refresh()">
          ${['agent','merchant','both'].map(s=>`<option ${g.signer===s?'selected':''}>${s}</option>`).join('')}
        </select></div>
      <div class="field"><label>Order gate</label>
        <div class="toggle">
          <button aria-pressed="${!g.gate_on}" onclick="S.gate.gate_on=false;refresh()">Off (UPI today)</button>
          <button aria-pressed="${g.gate_on}" onclick="S.gate.gate_on=true;refresh()">On</button>
        </div></div>
     </div>
     <div style="margin-top:1.3rem">${containment(d)}</div>`
  + verdict(v[0], v[1], v[2],
      `agreed <b>${esc(d.agreed)}</b> &middot; charged <b>${esc(d.charged)}</b><br>${d.passed} of ${d.total_checks} checks passed`)
  + `${d.allowed && gapOf(d)>0 ? `<p class="note" style="color:#ffa3b4">Every limit was respected and the user is still out ${esc(d.gap)}.</p>`:''}
     <div class="card" style="margin-bottom:.6rem">
       <h3>Checks the gate ran</h3>
       <ul class="checks">
         ${d.checks.map(c=>`<li class="${c.passed?'':'failed'}">
            <span class="m ${c.passed?'ok':'no'}">${c.passed?'&#10003;':'&#10007;'}</span>
            <span class="nm">${esc(c.check)}</span>
            <span class="dt">${esc(c.detail)}</span></li>`).join('')}
       </ul>
       ${d.reasons.length?`<ul class="reasons">${d.reasons.map(r=>`<li>${esc(r)}</li>`).join('')}</ul>`:''}
     </div>
     <div class="card">
       <h3>The order</h3>
       <ul class="checks">
        ${d.lines.map(l=>`<li><span></span><span class="nm">${esc(l.title)}</span><span class="dt">${esc(l.amount)}</span></li>`).join('')}
       </ul>
       <p class="src">signed by ${esc(d.signed_by.join(', ')||'nobody')} &middot; category ${esc(d.order_category)}</p>
     </div>
     <p class="note">Try it: set the ceiling to <b>150</b> with the gate <b>off</b>. The same inflated order is refused &mdash; not by the signature, by the limit.</p>`;
}

/* ---------------- 04 agents ---------------- */
function drawAgents(){
  const d = DATA.agents; if(!d) return '';
  const live = d.agents.filter(a=>!a.revoked).length;
  return head(4,'Can one agent be switched off?',
    'Several agents can share one appliance. Revoking one must not silently kill the others &mdash; and since a <span class="mono">did:key</span> cannot be revoked at all, status has to live in a separate list.')
  + `<div class="form">
      <div class="field"><label>Register another agent</label>
        <input id="na" placeholder="agent:fuel" onkeydown="if(event.key==='Enter')addAgent()"></div>
      <button class="act" onclick="addAgent()">Register on this device</button>
     </div>`
  + verdict(live?'yes':'no', live?'ISOLATED':'ALL OFF',
      live+' of '+d.agents.length+' still active',
      `device <b>${esc(d.device)}</b><br>issued by <b>${esc(d.owner_vpa)}</b>`)
  + `<div class="grid2">
      ${d.agents.map(a=>`
        <div class="card ${a.revoked?'no':'yes'}">
          <h3 class="mono">${esc(a.agent_id)}</h3>
          <p class="why">${a.revoked?'Revoked &mdash; status bit '+a.status_index+' is set.':'Active. Its credential verifies.'}</p>
          <dl class="kv" style="margin-top:.6rem">
            <dt>did</dt><dd style="font-size:.7rem">${esc(a.did)}</dd>
            <dt>bit</dt><dd>${a.status_index}</dd>
            <dt>attested</dt><dd>${a.attestation && a.attestation.simulated ? 'simulated' : '&mdash;'}</dd>
          </dl>
          ${a.reasons.length?`<ul class="reasons">${a.reasons.map(r=>`<li>${esc(r)}</li>`).join('')}</ul>`:''}
          ${a.revoked?'':`<p style="margin:.85rem 0 0"><button class="act ghost" onclick="revokeAgent('${esc(a.agent_id)}')">Switch this one off</button></p>`}
        </div>`).join('')}
     </div>
     <div class="card" style="margin-top:.6rem">
       <h3>The published status list</h3>
       <p class="why">What a verifier fetches. 131,072 bits of mostly zeros, gzipped &mdash; its length tells an observer nothing about how many agents exist.</p>
       <dl class="kv" style="margin-top:.6rem">
         <dt>purpose</dt><dd>${esc(d.status_list.statusPurpose)}</dd>
         <dt>encoded</dt><dd style="font-size:.7rem">${esc(d.status_list.encodedList)}</dd>
       </dl>
     </div>
     <p class="note"><b>Simulated attestation.</b> The token shape is a real EAT. The evidence behind it is not &mdash; there is no TDX or Secure Enclave here, so every one says <span class="mono">simulated: true</span>.</p>`;
}
async function addAgent(){
  const v = el('na').value.trim(); if(!v) return;
  DATA.agents = await post('/api/agents/register',{agent_id:v}); draw();
}
async function revokeAgent(id){
  DATA.agents = await post('/api/agents/revoke',{agent_id:id}); draw();
}

/* ---------------- 05 payment ---------------- */
function drawPay(){
  const d = DATA.pay, p = S.pay;
  const faults = ['','insufficient_funds','debit_fail','invalid_mpin','debit_timeout',
                  'credit_fail','beneficiary_down','credit_timeout'];
  let out = head(5,'Does the money actually move?',
    'The gate is only half of it. Run a payment through the rails, break it on purpose, and check the books still balance afterwards.')
  + `<div class="form">
      <div class="field"><label>Amount &#8377;</label>
        <input class="mono" style="min-width:6.5rem" value="${esc(p.amount)}" onchange="S.pay.amount=this.value"></div>
      <div class="field"><label>Inject a fault</label>
        <select onchange="S.pay.fault=this.value">
          ${faults.map(f=>`<option value="${f}" ${p.fault===f?'selected':''}>${f||'none'}</option>`).join('')}
        </select></div>
      <div class="field"><label>Order gate</label>
        <div class="toggle">
          <button aria-pressed="${!p.with_order}" onclick="S.pay.with_order=false;draw()">Off</button>
          <button aria-pressed="${p.with_order}" onclick="S.pay.with_order=true;draw()">On</button>
        </div></div>
      <div class="field"><label>Suppress repeat charges</label>
        <div class="toggle">
          <button aria-pressed="${!p.suppress_duplicates}" onclick="S.pay.suppress_duplicates=false;draw()">Off</button>
          <button aria-pressed="${p.suppress_duplicates}" onclick="S.pay.suppress_duplicates=true;draw()">On</button>
        </div></div>
      <button class="act" onclick="runPay()">Send the payment</button>
     </div>
     <p class="hint">Repeat suppression is off so the same amount can be sent again while you work through the faults. Turn it on and send twice to watch the operator guardrail refuse the second.</p>`;

  if(!d) return out + `<p class="empty" style="margin-top:1.6rem">No payment sent yet.</p>`;

  const a = d.audit;
  out += verdict(d.ok?'yes':(d.state==='TIMED_OUT'?'warn':'no'),
      d.ok?'SETTLED':String(d.state).replace(/_/g,' '),
      d.code||'',
      `${esc(d.amount)} &middot; rrn <b>${esc(d.rrn||'—')}</b><br>started by <b>${esc(d.agent_id||'nobody claimed it')}</b>`);

  out += verdict(a.healthy?'yes':'no',
      a.healthy?'BOOKS BALANCE':'BOOKS BROKEN',
      a.healthy?'ledger nets to zero':'ledger does not net',
      `${a.entry_count} entries &middot; ${a.transaction_count} transactions<br>in flight <b>${esc(a.in_flight)}</b>`);

  if(d.reasons.length) out += `<ul class="reasons" style="margin-bottom:.9rem">${d.reasons.map(r=>`<li>${esc(r)}</li>`).join('')}</ul>`;

  out += `<div class="grid2">
      <div class="card"><h3>What happened</h3>
        <ul class="trace">
          ${d.trace.map(t=>`<li><span class="st">${esc(t.step)}</span><span>${esc(t.detail)}</span></li>`).join('')}
        </ul>
        ${d.recon?`<p class="src">reconciliation swept ${d.recon.scanned}: ${esc(JSON.stringify(d.recon.counts))}</p>`:''}
      </div>
      <div class="card"><h3>Ledger entries</h3>
        ${d.ledger.length?`<table class="led" style="margin-top:.5rem">
          <thead><tr><th>Account</th><th>Dr/Cr</th><th>Amount</th></tr></thead>
          <tbody>${d.ledger.map(e=>`<tr>
            <td>${esc(e.account.replace('acct_',''))}</td>
            <td class="${e.direction==='DR'?'dr':'cr'}">${esc(e.direction)}</td>
            <td>${esc(e.amount)}</td></tr>`).join('')}</tbody></table>`
          :`<p class="empty" style="margin-top:.5rem">No entries &mdash; the money never moved.</p>`}
      </div>
     </div>
     <div class="card" style="margin-top:.6rem"><h3>Balances</h3>
       <table class="led" style="margin-top:.5rem">
         <thead><tr><th>Account</th><th>Type</th><th>Balance</th></tr></thead>
         <tbody>${d.balances.map(b=>`<tr><td>${esc(b.vpa)}</td><td>${esc(b.type)}</td><td>${esc(b.balance)}</td></tr>`).join('')}</tbody>
       </table>
     </div>
     <p class="note">Every balance above is re-derived from the ledger, not read from a cached field. If a debit ever went missing, <span class="mono">BOOKS BROKEN</span> is what you would see.</p>`;
  return out;
}
async function runPay(){ DATA.pay = await post('/api/pay', S.pay); draw(); }

/* ---------------- draw ---------------- */
function draw(){
  const fn = {rails:drawRails, enforce:drawEnforce, gate:drawGate,
              agents:drawAgents, pay:drawPay}[current];
  const d = DATA[current];
  if(d && d.error){ el('panel').innerHTML = `<p class="err">${esc(d.error)}</p>`; return; }
  el('panel').innerHTML = fn();
}

drawNav(); refresh();
</script></body></html>
"""


def main(port: int = 8010) -> None:
    build()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"  Test bench running at http://localhost:{port}")
    print("  Ctrl-C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped")


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8010)
