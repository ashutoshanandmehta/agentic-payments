"""
The user's control app.

    python3 src/console.py        then open http://localhost:8000

What a person actually opens this for is not the permissions screen. It is the
question "what did it buy, and was that right?" -- so purchases come first, with the
agent's signed intent shown beside each one, and the limits sit underneath.

That ordering is also the point of the app existing. The UPI block is already visible
in the user's bank app and the card token in the issuer's app. **The purchase history
with the intent attached exists nowhere else.**

Revoking fans out to all three places an agent's authority lives and reports each
separately, because a revoke that half worked is worse than one that failed loudly.
"""

from __future__ import annotations

import json
import threading
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import revocation
import sim as world
import vcard
from consent import Keypair, Order, OrderSigner
from core import Money, new_id
from models import AccountType, MandateStatus, utcnow

STATE = {"sim": None, "cards": {}, "operator": Keypair("operator"), "n": 0}
LOCK = threading.Lock()

AGENTS = [
    ("fridge-restock", "Kitchen fridge", "Groceries when stock runs low",
     "2000", "15000"),
    ("alexa-household", "Living room speaker", "Household items on request",
     "1000", "6000"),
]


# --------------------------------------------------------------------------
# World
# --------------------------------------------------------------------------

def seed() -> None:
    sim = world.build(db_path="console.db", fresh=True)
    world.seed(sim)
    now = utcnow()
    cards = {}

    for agent_id, _label, purpose, per_txn, monthly in AGENTS:
        card = vcard.issue(sim, agent_id, world.USER_VPA, umn="")
        mandate = sim.orchestrator.create_mandate(
            payer_vpa=world.USER_VPA,
            allowed_payees=[card.vpa],       # the card is the only payee on the UPI leg
            max_amount_per_txn=Money.rupees(per_txn),
            total_cap=Money.rupees(monthly),
            valid_from=now - timedelta(minutes=1),
            valid_until=now + timedelta(days=90),
            purpose=purpose,
        )
        card.umn = mandate.umn
        cards[agent_id] = card

    STATE["sim"], STATE["cards"], STATE["n"] = sim, cards, 0


def snapshot() -> dict:
    sim = STATE["sim"]
    agents = []
    for agent_id, label, purpose, _p, _m in AGENTS:
        card = STATE["cards"][agent_id]
        m = sim.store.get_mandate(card.umn)
        agents.append({
            "agent_id": agent_id, "label": label, "purpose": purpose,
            "revoked": card.revoked or m.status is not MandateStatus.ACTIVE,
            "status": m.status.value,
            "per_txn": m.max_amount_per_txn.to_rupees_str(),
            "cap": m.total_cap.to_rupees_str(),
            "spent": m.consumed.to_rupees_str(),
            "left": m.remaining.to_rupees_str(),
            "pct": round(100 * m.consumed.paise / max(1, m.total_cap.paise)),
            "expires": m.valid_until.strftime("%d %b %Y"),
            "float": vcard.balance(sim, card).to_rupees_str(),
            "float_paise": vcard.balance(sim, card).paise,
            "card_vpa": card.vpa,
        })

    # sort on the purchase counter rather than trusting event insertion order --
    # getting this wrong showed the oldest purchase as the newest.
    buys = sorted(
        (ev["payload"] for ev in sim.store.list_events(limit=500)
         if ev.get("kind") == "console.purchase"),
        key=lambda b: b.get("n", 0), reverse=True,
    )

    revokes = list(reversed([
        ev["payload"] for ev in sim.store.list_events(limit=500)
        if ev.get("kind") == "agent.revoked"
    ]))

    user = sim.store.get_account_by_vpa(world.USER_VPA)
    return {
        "user": {"vpa": user.vpa, "name": user.holder_name,
                 "balance": user.balance.to_rupees_str()},
        "agents": agents, "purchases": buys[:20], "revocations": revokes,
    }


# --------------------------------------------------------------------------
# Buying
# --------------------------------------------------------------------------

BASKETS = {
    "groceries": ([("Atta 5kg", "275"), ("Milk 1L x2", "128"), ("Eggs 12", "89")], "bigbasket"),
    "snacks": ([("Biscuits", "60"), ("Chips", "40")], "blinkit"),
    "big": ([("Rice 25kg", "2400")], "bigbasket"),
}


def purchase(agent_id: str, basket: str, fail: bool) -> dict:
    sim, card = STATE["sim"], STATE["cards"][agent_id]
    lines, merchant_name = BASKETS[basket]
    merchant = world.MERCHANT_VPA if merchant_name == "bigbasket" else world.SECOND_MERCHANT_VPA

    STATE["n"] += 1
    n = STATE["n"]
    total = Money(sum(Money.rupees(a).paise for _t, a in lines))

    order = Order.build(f"ORD-{n}", merchant, lines)
    order.sign(OrderSigner.AGENT, sim.agent_key, sim.merchant_keys[merchant])

    out = {
        "n": n, "agent_id": agent_id, "basket": basket, "merchant": merchant,
        "items": [{"title": t, "amount": Money.rupees(a).to_rupees_str()} for t, a in lines],
        "total": total.to_rupees_str(), "at": utcnow().strftime("%H:%M:%S"),
        "order_id": order.order_id,
    }

    # -- leg 1: fund the card off the user's mandate ----------------------
    ld = vcard.load(sim, card, total, f"load-{n}", order=None)
    out["load"] = {"ok": ld.ok, "detail": ld.verdict.reasons[0] if not ld.ok else "funded"}
    if not ld.ok:
        out["outcome"] = "refused"
        sim.store.record_event("console.purchase", out)
        return out

    # -- leg 2: the card pays the merchant --------------------------------
    if fail:
        sim.faults.force = "credit_fail"
    try:
        sp = vcard.spend(sim, card, merchant, total, f"spend-{n}",
                         order=order, load_txn_id=ld.txn.txn_id)
        if sp.ok:
            detail = "paid"
        elif sp.verdict.reasons:
            detail = sp.verdict.reasons[0]
        else:
            detail = f"the rails returned {sp.txn.state.value}"
        out["spend"] = {"ok": sp.ok, "detail": detail}
    except vcard.CardRevoked as exc:
        out["spend"] = {"ok": False, "detail": str(exc)}

    if not out["spend"]["ok"]:
        # the money is on the card. return it rather than leave it sitting.
        back = vcard.sweep(sim, card, f"refund-{n}")
        out["refund"] = {"ok": bool(back and back.ok),
                         "detail": f"returned {total}" if back and back.ok
                                   else "refund failed -- float still on the card"}
        out["outcome"] = "failed_and_refunded" if out["refund"]["ok"] else "float_stranded"
    else:
        out["outcome"] = "paid"

    sim.store.record_event("console.purchase", out)
    return out


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
        elif self.path == "/api/state":
            with LOCK:
                self._json(snapshot())
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        try:
            with LOCK:
                if self.path == "/api/seed":
                    seed()
                    self._json(snapshot())
                elif self.path == "/api/buy":
                    purchase(body["agent_id"], body.get("basket", "groceries"),
                             bool(body.get("fail")))
                    self._json(snapshot())
                elif self.path == "/api/revoke":
                    card = STATE["cards"][body["agent_id"]]
                    rec = revocation.revoke(STATE["sim"], card,
                                            body.get("reason", "user_revoked"),
                                            STATE["operator"])
                    self._json({"record": rec.to_dict(), "state": snapshot()})
                else:
                    self._send(404, b"not found", "text/plain")
        except Exception as exc:                            # noqa: BLE001
            self._json({"error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, *a):
        pass


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent controls</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=Roboto+Mono:wght@400;500&display=swap">
<style>
:root{--bg:#f2f3f5;--card:#fff;--ink:#15171c;--soft:#61656f;--faint:#9296a1;
 --line:#e3e5e9;--go:#1d7a4d;--stop:#c0392b;--hold:#b07a15;--tint:#eef4ff;--brand:#2f5fd0}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){
 --bg:#111318;--card:#1a1d23;--ink:#e8eaee;--soft:#9aa0ab;--faint:#6b717c;
 --line:#282c34;--go:#4ec27f;--stop:#e8705e;--hold:#d9a44a;--tint:#1a2333;--brand:#7aa2f7}}
:root[data-theme=dark]{--bg:#111318;--card:#1a1d23;--ink:#e8eaee;--soft:#9aa0ab;
 --faint:#6b717c;--line:#282c34;--go:#4ec27f;--stop:#e8705e;--hold:#d9a44a;
 --tint:#1a2333;--brand:#7aa2f7}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:Figtree,system-ui,sans-serif;font-size:15px;line-height:1.5}
.wrap{max-width:30rem;margin:0 auto;padding:1.2rem 1rem 4rem}
.mono{font-family:"Roboto Mono",monospace}
header{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:1rem}
h1{font-size:1.25rem;font-weight:700;margin:0;letter-spacing:-.02em}
.bal{font-family:"Roboto Mono",monospace;font-size:.9rem;color:var(--soft)}
h2{font-size:.72rem;text-transform:uppercase;letter-spacing:.11em;color:var(--faint);margin:1.6rem 0 .6rem;font-weight:600}
.c{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:1rem;margin-bottom:.7rem}
.ag{display:flex;justify-content:space-between;align-items:flex-start;gap:.6rem}
.ag h3{margin:0;font-size:1rem;font-weight:600}
.ag .p{margin:.1rem 0 0;font-size:.83rem;color:var(--soft)}
.badge{font-size:.65rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:.2rem .5rem;border-radius:20px;white-space:nowrap}
.badge.on{background:color-mix(in srgb,var(--go) 16%,transparent);color:var(--go)}
.badge.off{background:color-mix(in srgb,var(--stop) 16%,transparent);color:var(--stop)}
.bar{height:6px;background:var(--line);border-radius:4px;margin:.8rem 0 .35rem;overflow:hidden}
.bar i{display:block;height:100%;background:var(--brand);border-radius:4px}
.nums{display:flex;justify-content:space-between;font-size:.78rem;color:var(--soft);font-family:"Roboto Mono",monospace}
.meta{display:grid;grid-template-columns:auto 1fr;gap:.1rem .8rem;font-size:.78rem;margin-top:.7rem;color:var(--soft)}
.meta span:nth-child(odd){color:var(--faint)}
.meta span:nth-child(even){font-family:"Roboto Mono",monospace}
.float{background:var(--tint);border-radius:7px;padding:.5rem .7rem;margin-top:.7rem;font-size:.8rem;color:var(--hold);font-weight:600}
.acts{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.8rem}
button{font:inherit;font-size:.8rem;font-weight:600;padding:.45rem .8rem;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer}
button:hover{border-color:var(--brand)}
button.danger{background:var(--stop);border-color:var(--stop);color:#fff}
button:disabled{opacity:.45;cursor:not-allowed}
.buy{border-left:3px solid var(--line);padding-left:.8rem;margin-bottom:.9rem}
.buy.paid{border-left-color:var(--go)}
.buy.refused,.buy.failed_and_refunded{border-left-color:var(--hold)}
.buy.float_stranded{border-left-color:var(--stop)}
.buy .top{display:flex;justify-content:space-between;font-size:.85rem;font-weight:600}
.buy .who{font-size:.75rem;color:var(--faint);margin:.1rem 0}
.buy ul{margin:.35rem 0 0;padding-left:1rem;font-size:.78rem;color:var(--soft)}
.buy .out{font-size:.75rem;font-weight:600;margin-top:.3rem}
.buy .out.paid{color:var(--go)} .buy .out.refused,.buy .out.failed_and_refunded{color:var(--hold)}
.buy .out.float_stranded{color:var(--stop)}
.steps{margin-top:.6rem;font-size:.78rem}
.steps div{display:flex;gap:.45rem;padding:.2rem 0}
.steps .ok{color:var(--go);font-weight:700}
.steps .no{color:var(--stop);font-weight:700}
.empty{color:var(--faint);font-size:.85rem;padding:.4rem 0}
.sig{font-family:"Roboto Mono",monospace;font-size:.7rem;color:var(--faint);margin-top:.5rem;word-break:break-all}
</style></head><body>
<div class="wrap">
  <header><h1>Agent controls</h1><span class="bal" id="bal"></span></header>
  <div id="agents"></div>
  <h2>Recent purchases</h2>
  <div class="c" id="buys"></div>
  <h2 id="revh" style="display:none">Revocations</h2>
  <div id="revs"></div>
  <div style="margin-top:1.4rem"><button onclick="seed()">Reset everything</button></div>
</div>
<script>
let S={};
const post=(u,b)=>fetch(u,{method:'POST',body:JSON.stringify(b||{})}).then(r=>r.json());

async function load(){ S=await (await fetch('/api/state')).json(); draw(); }
async function seed(){ S=await post('/api/seed'); draw(); }
async function buy(a,b,f){ S=await post('/api/buy',{agent_id:a,basket:b,fail:f}); draw(); }
async function revoke(a){
  if(!confirm('Switch this agent off? This kills its card token, stops future funding, and returns anything unspent.'))return;
  const r=await post('/api/revoke',{agent_id:a,reason:'user_revoked'});
  S=r.state; draw(r.record);
}

function draw(rec){
  document.getElementById('bal').textContent=S.user.balance+' available';
  document.getElementById('agents').innerHTML=S.agents.map(a=>`
    <div class="c">
      <div class="ag">
        <div><h3>${a.label}</h3><p class="p">${a.purpose}</p></div>
        <span class="badge ${a.revoked?'off':'on'}">${a.revoked?'off':'active'}</span>
      </div>
      <div class="bar"><i style="width:${Math.min(100,a.pct)}%"></i></div>
      <div class="nums"><span>${a.spent} spent</span><span>${a.left} left</span></div>
      <div class="meta">
        <span>per purchase</span><span>${a.per_txn}</span>
        <span>monthly cap</span><span>${a.cap}</span>
        <span>expires</span><span>${a.expires}</span>
      </div>
      ${a.float_paise>0?`<div class="float">${a.float} is sitting on this agent's card right now</div>`:''}
      <div class="acts">
        <button onclick="buy('${a.agent_id}','groceries',false)" ${a.revoked?'disabled':''}>Buy groceries</button>
        <button onclick="buy('${a.agent_id}','big',false)" ${a.revoked?'disabled':''}>Buy ₹2,400 rice</button>
        <button onclick="buy('${a.agent_id}','snacks',true)" ${a.revoked?'disabled':''}>Buy, force failure</button>
        <button class="danger" onclick="revoke('${a.agent_id}')" ${a.revoked?'disabled':''}>Switch off</button>
      </div>
    </div>`).join('');

  document.getElementById('buys').innerHTML = S.purchases.length? S.purchases.map(b=>`
    <div class="buy ${b.outcome}">
      <div class="top"><span>${b.merchant}</span><span>${b.total}</span></div>
      <div class="who">${b.agent_id} · ${b.at} · order ${b.order_id}</div>
      <ul>${b.items.map(i=>`<li>${i.title} — ${i.amount}</li>`).join('')}</ul>
      <div class="out ${b.outcome}">${
        b.outcome==='paid'?'paid':
        b.outcome==='refused'?('not allowed — '+b.load.detail):
        b.outcome==='failed_and_refunded'?('payment failed — '+b.refund.detail):
        'payment failed and the money is still on the card'}</div>
    </div>`).join('') : '<div class="empty">Nothing yet.</div>';

  const rv=S.revocations||[];
  document.getElementById('revh').style.display=rv.length?'block':'none';
  document.getElementById('revs').innerHTML=rv.map(r=>`
    <div class="c">
      <div class="ag"><div><h3>${r.agent_id}</h3>
        <p class="p">${r.reason.replace(/_/g,' ')} · ${new Date(r.at).toLocaleTimeString()}</p></div>
        <span class="badge ${r.complete?'on':'off'}">${r.complete?'complete':'partial'}</span></div>
      <div class="steps">${r.steps.map(s=>
        `<div><span class="${s.ok?'ok':'no'}">${s.ok?'✓':'✗'}</span>
         <span>${s.step.replace(/_/g,' ')} — ${s.detail}</span></div>`).join('')}</div>
      <div class="sig">signed by ${r.signer||'—'} · ${r.id}</div>
    </div>`).join('');
}
load();
</script></body></html>
"""


def main(port: int = 8000) -> None:
    seed()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"  Agent controls running at http://localhost:{port}")
    print("  Ctrl-C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped")


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
