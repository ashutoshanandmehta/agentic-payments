"""
A local web interface for the simulation.

    ./.venv/bin/python -m sim.web
    open http://localhost:8000

Nothing is installed and nothing leaves the machine. It uses Python's built-in HTTP
server, so there is no framework to learn and no build step.

The point of this page is to let you change one number at a time and watch the answer
change. The Rs 600 finding is easiest to see here: load the "consistent lie" preset,
watch it get approved, then drop the per-payment limit and watch it get refused.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .rail import Rail
from .uap.authority import Money, PaymentAuthority
from .uap.cart import Cart, PaymentRequest
from .uap.delegation import Agent, Device, Household, Principal
from .uap.mandate import (
    CartSigner,
    Keypair,
    authority_record,
    cart_record,
    request_record,
)

SHOPS = ("blinkit", "instamart", "bigbasket")
CATEGORIES = ("grocery", "dairy", "alcohol", "transport")


# --------------------------------------------------------------------------
# Presets -- each one is a starting point you can then edit
# --------------------------------------------------------------------------

def _base() -> dict:
    return {
        "maxPerPayment": 800, "maxTotal": 2000,
        "merchants": list(SHOPS), "categories": ["grocery"],
        "maxPayments": 2, "validFrom": 0, "validUntil": 100,
        "cartId": "cart-1", "cartMerchant": "instamart", "cartCategory": "grocery",
        "lines": [["Fortune Atta 1kg", 54], ["Amul Milk 1L", 64]],
        "cartTotal": "", "agreedAt": 10,
        "reqAmount": "", "reqMerchant": "instamart", "reqAt": 20, "nonce": "n1",
        "cartSigner": "agent", "actualSigner": "same",
        "alreadySpent": 0, "alreadyPaid": 0, "usedNonces": "",
        "revoked": [], "deviceReset": False,
    }


PRESETS = {
    "clean": ("Nothing wrong", {}),
    "price-drift": ("Price changed after agreement", {"reqAmount": 162}),
    "payee-swap": ("Money sent to a different shop", {"reqMerchant": "blinkit"}),
    "double-debit": ("Same payment twice", {"usedNonces": "n1"}),
    "cart-arithmetic": ("Cart total does not match its lines", {"cartTotal": 300}),
    "wrong-shop": ("Shop not on the approved list",
                   {"merchants": ["blinkit", "instamart"], "cartMerchant": "bigbasket",
                    "reqMerchant": "bigbasket"}),
    "wrong-category": ("Category not allowed",
                       {"cartCategory": "alcohol", "lines": [["Lager 650ml", 160]]}),
    "over-per-payment": ("Single payment too large",
                         {"lines": [["Bulk order", 1400]]}),
    "over-budget": ("Total budget already used",
                    {"alreadySpent": 1900, "maxPayments": 5}),
    "too-many": ("Used more times than allowed", {"alreadyPaid": 2}),
    "expired": ("Authority expired", {"agreedAt": 150, "reqAt": 160}),
    "consistent-lie": ("Rs 600 cart, internally consistent  <- the finding",
                       {"lines": [["Fortune Atta 1kg", 300], ["Amul Milk 1L", 300]]}),
    "tight-authority": ("Same Rs 600 cart, tight limit",
                        {"lines": [["Fortune Atta 1kg", 300], ["Amul Milk 1L", 300]],
                         "maxPerPayment": 150}),
    "shop-absent": ("Both must sign, shop does not",
                    {"cartSigner": "both", "actualSigner": "agent"}),
    "milk-teen": ("Dairy: whose money pays?",
                  {"cartCategory": "dairy", "categories": ["grocery", "dairy"],
                   "lines": [["Amul Milk 1L", 64]]}),
    "nobody-covers": ("Nobody's grant covers alcohol",
                      {"cartCategory": "alcohol", "categories": ["grocery", "alcohol"],
                       "lines": [["Lager 650ml", 160]], "revoked": ["Mum"]}),
    "revocation-race": ("Revoked while the payment was in flight",
                        {"revoked": ["Dad", "Mum", "Teen"]}),
    "device-reset": ("Appliance sold and wiped", {"deviceReset": True}),
}


def preset_payload(name: str) -> dict:
    d = _base()
    d.update(PRESETS[name][1])
    return d


# --------------------------------------------------------------------------
# Running one payment
# --------------------------------------------------------------------------

def evaluate(p: dict) -> dict:
    dad = Principal("Dad", Keypair("Dad"))
    mum = Principal("Mum", Keypair("Mum"))
    teen = Principal("Teen", Keypair("Teen"))

    fridge = Device("fridge-01", Keypair("fridge-01"), shared=True)
    agent = Agent("fridge-restock", Keypair("agent:fridge-restock"), fridge)
    agent.grant(dad, Money.rupees(4_000),
                categories=frozenset({"grocery", "transport"}))
    agent.grant(mum, Money.rupees(4_000))
    agent.grant(teen, Money.rupees(500), categories=frozenset({"dairy"}))

    household = Household("Anand", [dad, mum, teen], [fridge], [agent])
    by_name = {"Dad": dad, "Mum": mum, "Teen": teen}
    for who in p.get("revoked", []):
        household.revoke_all_from(by_name[who])
    if p.get("deviceReset"):
        fridge.factory_reset()

    shops = {n: Keypair(n) for n in SHOPS}
    signer = CartSigner(p.get("cartSigner", "agent"))
    rail = Rail(Keypair("npci-uap"), cart_signer=signer)

    authority = PaymentAuthority.build(
        max_per_payment=p["maxPerPayment"], max_total=p["maxTotal"],
        allowed_merchants=p["merchants"],
        allowed_categories=p["categories"] or None,
        max_payments=int(p["maxPayments"]),
        valid_from=int(p["validFrom"]), valid_until=int(p["validUntil"]),
    )

    cart = Cart.build(
        cart_id=p["cartId"], merchant=p["cartMerchant"], category=p["cartCategory"],
        lines=[(t, a) for t, a in p["lines"]],
        total=p["cartTotal"] if p["cartTotal"] not in ("", None) else None,
        agreed_at=int(p["agreedAt"]),
    )

    req = PaymentRequest(
        cart_ref=p["cartId"], merchant=p["reqMerchant"],
        amount=(Money.rupees(p["reqAmount"])
                if p["reqAmount"] not in ("", None) else cart.total),
        requested_at=int(p["reqAt"]), nonce=p["nonce"],
    )

    arec = authority_record(authority, dad.key, agent.agent_id)

    # "actualSigner" lets you require one thing and supply another, which is how the
    # shop-does-not-participate case is tested
    actual = p.get("actualSigner", "same")
    sign_as = signer if actual == "same" else CartSigner(actual)
    crec = cart_record(cart, sign_as, agent.key, shops[cart.merchant])
    rrec = request_record(req, arec.id, agent.key)

    aid = arec.id
    if p.get("alreadySpent"):
        rail.spent[aid] = Money.rupees(p["alreadySpent"])
    if p.get("alreadyPaid"):
        rail.counts[aid] = int(p["alreadyPaid"])
    used = [n.strip() for n in str(p.get("usedNonces", "")).split(",") if n.strip()]
    if used:
        rail.nonces[aid] = set(used)

    out = rail.authorise(
        authority=authority, authority_rec=arec, cart_rec=crec, request_rec=rrec,
        principal_key=dad.key, agent=agent,
        merchant_key=shops[req.merchant], now=req.requested_at,
    )

    return {
        "approved": out.approved,
        "reason": out.reason,
        "checksRun": out.result.checks_run if out.result else 0,
        "score": round(out.result.score, 2) if out.result else 0,
        "violations": [
            {"kind": v.kind, "detail": v.detail, "expected": v.expected,
             "actual": v.actual, "severity": v.severity.value}
            for v in (out.result.violations if out.result else [])
        ],
        "funding": (out.funding.principal.name if out.funding else None),
        "fundingLeft": (str(out.funding.remaining) if out.funding else None),
        "trace": out.trace,
        "authority": authority.describe(),
        "cart": cart.describe(),
        "cartLineSum": str(cart.line_sum),
        "cartTotal": str(cart.total),
        "requestAmount": str(req.amount),
        "signedBy": crec.signed_by(),
        "evidenceComplete": bool(out.evidence and out.evidence.complete()),
    }


# --------------------------------------------------------------------------
# Server
# --------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif self.path == "/api/presets":
            data = {k: {"label": v[0], "payload": preset_payload(k)}
                    for k, v in PRESETS.items()}
            self._send(200, json.dumps(data).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        if self.path != "/api/check":
            self._send(404, b"not found", "text/plain")
            return
        n = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(n) or b"{}")
            result = evaluate(payload)
        except Exception as exc:                      # noqa: BLE001
            result = {"error": f"{type(exc).__name__}: {exc}"}
        self._send(200, json.dumps(result).encode(), "application/json")

    def log_message(self, *args) -> None:
        pass                                          # keep the console quiet


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Delegated payment checker</title>
<style>
:root{--bg:#fbfbfa;--fg:#1a1a18;--dim:#6b6b66;--line:#e2e2dd;--card:#fff;
      --ok:#0d7a4a;--bad:#b3261e;--warn:#8a6d00;--accent:#2f5fd0}
@media (prefers-color-scheme:dark){:root:not([data-t=light]){
  --bg:#16161a;--fg:#e8e8e4;--dim:#9a9a94;--line:#2e2e34;--card:#1e1e23;
  --ok:#4ade80;--bad:#f87171;--warn:#fbbf24;--accent:#7aa2f7}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
     font:14px/1.5 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif}
header{padding:18px 22px;border-bottom:1px solid var(--line)}
h1{margin:0;font-size:17px}
header p{margin:5px 0 0;color:var(--dim);font-size:13px}
.wrap{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;
      padding:18px 22px;align-items:start}
@media (max-width:900px){.wrap{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;
      padding:14px 16px;margin-bottom:14px}
.card h2{margin:0 0 10px;font-size:13px;text-transform:uppercase;
         letter-spacing:.06em;color:var(--dim)}
label{display:block;margin:8px 0 3px;font-size:12px;color:var(--dim)}
input,select{width:100%;padding:6px 8px;border:1px solid var(--line);border-radius:5px;
             background:var(--bg);color:var(--fg);font:inherit;font-size:13px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.row3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}
.chip{display:flex;align-items:center;gap:5px;border:1px solid var(--line);
      border-radius:20px;padding:3px 10px;font-size:12px;cursor:pointer;user-select:none}
.chip input{width:auto;margin:0}
.lines div{display:grid;grid-template-columns:1fr 90px 30px;gap:6px;margin-bottom:6px}
button{font:inherit;padding:7px 14px;border-radius:6px;border:1px solid var(--line);
       background:var(--bg);color:var(--fg);cursor:pointer}
button.go{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
button.mini{padding:3px 8px;font-size:12px}
#verdict{font-size:19px;font-weight:700;margin:0 0 4px}
.ok{color:var(--ok)} .bad{color:var(--bad)}
.v{border-left:3px solid var(--bad);padding:7px 10px;margin:7px 0;
   background:color-mix(in srgb,var(--bad) 7%,transparent);border-radius:0 5px 5px 0}
.v.warn{border-color:var(--warn);background:color-mix(in srgb,var(--warn) 7%,transparent)}
.v b{font-family:ui-monospace,Menlo,monospace;font-size:12px}
.v p{margin:3px 0 0;font-size:13px}
.v small{color:var(--dim);font-size:12px}
.kv{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;font-size:13px;margin-top:10px}
.kv span:nth-child(odd){color:var(--dim)}
pre{background:var(--bg);border:1px solid var(--line);border-radius:5px;padding:9px;
    font-size:12px;overflow-x:auto;margin:8px 0 0}
.hint{color:var(--dim);font-size:12px;margin-top:8px}
</style></head><body>

<header>
  <h1>Delegated payment checker</h1>
  <p>The cart is already full. This is what happens when the agent tries to pay.</p>
</header>

<div class="wrap">
  <div>
    <div class="card">
      <h2>Start from</h2>
      <select id="preset"></select>
      <p class="hint">Pick <b>Rs 600 cart, internally consistent</b> and press Check.
        It is approved. Then set the per-payment limit to 150 and press Check again.</p>
    </div>

    <div class="card">
      <h2>What the human allowed</h2>
      <div class="row">
        <div><label>Most per payment (Rs)</label><input id="maxPerPayment" type="number"></div>
        <div><label>Most in total (Rs)</label><input id="maxTotal" type="number"></div>
      </div>
      <label>Shops allowed</label><div class="chips" id="merchants"></div>
      <label>Categories allowed</label><div class="chips" id="categories"></div>
      <div class="row3">
        <div><label>Max payments</label><input id="maxPayments" type="number"></div>
        <div><label>Valid from (tick)</label><input id="validFrom" type="number"></div>
        <div><label>Valid until (tick)</label><input id="validUntil" type="number"></div>
      </div>
    </div>

    <div class="card">
      <h2>The cart</h2>
      <div class="row3">
        <div><label>Cart id</label><input id="cartId"></div>
        <div><label>Shop</label><select id="cartMerchant"></select></div>
        <div><label>Category</label><select id="cartCategory"></select></div>
      </div>
      <label>Items</label><div class="lines" id="lines"></div>
      <button class="mini" onclick="addLine()">+ add item</button>
      <div class="row">
        <div><label>Override total (Rs) &mdash; blank means sum of items</label>
             <input id="cartTotal" placeholder="(sum of items)"></div>
        <div><label>Agreed at (tick)</label><input id="agreedAt" type="number"></div>
      </div>
    </div>

    <div class="card">
      <h2>The payment request</h2>
      <div class="row3">
        <div><label>Amount (Rs) &mdash; blank means cart total</label>
             <input id="reqAmount" placeholder="(cart total)"></div>
        <div><label>Paying which shop</label><select id="reqMerchant"></select></div>
        <div><label>Requested at (tick)</label><input id="reqAt" type="number"></div>
      </div>
      <div class="row"><div><label>Reference (nonce)</label><input id="nonce"></div>
        <div><label>References already settled</label>
             <input id="usedNonces" placeholder="comma separated"></div></div>
    </div>

    <div class="card">
      <h2>Signing and state</h2>
      <div class="row">
        <div><label>Cart must be signed by</label>
          <select id="cartSigner">
            <option value="agent">the agent</option>
            <option value="merchant">the shop</option>
            <option value="both">both</option>
          </select></div>
        <div><label>Actually signed by</label>
          <select id="actualSigner">
            <option value="same">whoever is required</option>
            <option value="agent">the agent only</option>
            <option value="merchant">the shop only</option>
            <option value="both">both</option>
          </select></div>
      </div>
      <div class="row">
        <div><label>Already spent on this authority (Rs)</label>
             <input id="alreadySpent" type="number"></div>
        <div><label>Payments already made</label>
             <input id="alreadyPaid" type="number"></div>
      </div>
      <label>Who has revoked their grant</label><div class="chips" id="revoked"></div>
      <label class="chip" style="margin-top:8px;display:inline-flex">
        <input type="checkbox" id="deviceReset"> fridge was sold and wiped</label>
    </div>

    <button class="go" onclick="check()">Check this payment</button>
  </div>

  <div>
    <div class="card" id="out">
      <h2>Result</h2>
      <p class="hint">Press Check.</p>
    </div>
  </div>
</div>

<script>
const SHOPS=["blinkit","instamart","bigbasket"];
const CATS=["grocery","dairy","alcohol","transport"];
const PEOPLE=["Dad","Mum","Teen"];
let PRESETS={};

function chips(host,items,name){
  document.getElementById(host).innerHTML=items.map(v=>
    `<label class="chip"><input type="checkbox" data-g="${name}" value="${v}">${v}</label>`).join("");
}
function opts(id,items){
  document.getElementById(id).innerHTML=items.map(v=>`<option>${v}</option>`).join("");
}
function getChips(n){return [...document.querySelectorAll(`[data-g="${n}"]:checked`)].map(e=>e.value);}
function setChips(n,vals){document.querySelectorAll(`[data-g="${n}"]`).forEach(e=>e.checked=vals.includes(e.value));}

function addLine(title="",amt=""){
  const d=document.createElement("div");
  d.innerHTML=`<input placeholder="item" value="${title}">
               <input type="number" placeholder="Rs" value="${amt}">
               <button class="mini" onclick="this.parentNode.remove()">&times;</button>`;
  document.getElementById("lines").appendChild(d);
}
function getLines(){
  return [...document.querySelectorAll("#lines div")].map(d=>{
    const i=d.querySelectorAll("input");
    return [i[0].value, Number(i[1].value||0)];
  }).filter(l=>l[0]);
}

function load(p){
  for(const k of ["maxPerPayment","maxTotal","maxPayments","validFrom","validUntil",
                  "cartId","cartMerchant","cartCategory","cartTotal","agreedAt",
                  "reqAmount","reqMerchant","reqAt","nonce","cartSigner","actualSigner",
                  "alreadySpent","alreadyPaid","usedNonces"])
    document.getElementById(k).value = p[k] ?? "";
  setChips("merchants",p.merchants); setChips("categories",p.categories);
  setChips("revoked",p.revoked||[]);
  document.getElementById("deviceReset").checked = !!p.deviceReset;
  document.getElementById("lines").innerHTML="";
  (p.lines||[]).forEach(l=>addLine(l[0],l[1]));
}

function collect(){
  const g=id=>document.getElementById(id).value;
  return {
    maxPerPayment:Number(g("maxPerPayment")), maxTotal:Number(g("maxTotal")),
    merchants:getChips("merchants"), categories:getChips("categories"),
    maxPayments:Number(g("maxPayments")), validFrom:Number(g("validFrom")),
    validUntil:Number(g("validUntil")),
    cartId:g("cartId"), cartMerchant:g("cartMerchant"), cartCategory:g("cartCategory"),
    lines:getLines(), cartTotal:g("cartTotal"), agreedAt:Number(g("agreedAt")),
    reqAmount:g("reqAmount"), reqMerchant:g("reqMerchant"), reqAt:Number(g("reqAt")),
    nonce:g("nonce"), cartSigner:g("cartSigner"), actualSigner:g("actualSigner"),
    alreadySpent:Number(g("alreadySpent")||0), alreadyPaid:Number(g("alreadyPaid")||0),
    usedNonces:g("usedNonces"),
    revoked:getChips("revoked"), deviceReset:document.getElementById("deviceReset").checked,
  };
}

async function check(){
  const r=await fetch("/api/check",{method:"POST",body:JSON.stringify(collect())});
  const d=await r.json(); const o=document.getElementById("out");
  if(d.error){o.innerHTML=`<h2>Result</h2><pre>${d.error}</pre>`;return;}
  const vs=d.violations.map(v=>
    `<div class="v ${v.severity==='warn'?'warn':''}"><b>${v.kind}</b>
       <p>${v.detail}</p>
       <small>expected ${v.expected} &mdash; got ${v.actual}</small></div>`).join("");
  o.innerHTML=`<h2>Result</h2>
    <p id="verdict" class="${d.approved?'ok':'bad'}">${d.approved?'APPROVED':'REFUSED'}</p>
    <small style="color:var(--dim)">${d.checksRun} checks run &middot; score ${d.score}</small>
    ${vs||'<p class="hint">Every check passed.</p>'}
    <div class="kv">
      <span>authority</span><span>${d.authority}</span>
      <span>cart</span><span>${d.cart}</span>
      <span>items add to</span><span>${d.cartLineSum}</span>
      <span>cart total says</span><span>${d.cartTotal}</span>
      <span>being paid</span><span>${d.requestAmount}</span>
      <span>cart signed by</span><span>${d.signedBy.join(", ")||"nobody"}</span>
      <span>funded by</span><span>${d.funding||"&mdash;"} ${d.fundingLeft?("("+d.fundingLeft+" left)"):""}</span>
      <span>dispute evidence</span><span>${d.evidenceComplete?"complete":"incomplete"}</span>
    </div>
    <pre>${d.trace.join("\n")}</pre>`;
}

(async()=>{
  chips("merchants",SHOPS,"merchants"); chips("categories",CATS,"categories");
  chips("revoked",PEOPLE,"revoked");
  opts("cartMerchant",SHOPS); opts("reqMerchant",SHOPS); opts("cartCategory",CATS);
  PRESETS=await (await fetch("/api/presets")).json();
  document.getElementById("preset").innerHTML=
    Object.entries(PRESETS).map(([k,v])=>`<option value="${k}">${v.label}</option>`).join("");
  document.getElementById("preset").onchange=e=>load(PRESETS[e.target.value].payload);
  load(PRESETS["clean"].payload);
})();
</script></body></html>
"""


def main(port: int = 8000) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"  Delegated payment checker running at http://localhost:{port}")
    print("  Ctrl-C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped")


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
