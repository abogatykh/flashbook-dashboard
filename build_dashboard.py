#!/usr/bin/env python3
"""Interactive HTML dashboard for the funnel tests — Flashbook.
Run:  python build_dashboard.py [customers.csv] [payments.csv]
Self-contained output (Chart.js via CDN). Numbers computed live from the CSV.
"""
import sys, json, pandas as pd, numpy as np
from funnel_config import FUNNELS, BANDS, classify, num

CUST = sys.argv[1] if len(sys.argv) > 1 else "merged_customers.csv"
PAYS = sys.argv[2] if len(sys.argv) > 2 else "merged_payments.csv"

# ============================ EDIT: AD SPEND ============================
ROAS_HORIZON_DAYS = 8   # capture the trial-end (day-7) annual charge, which posts a few hours AFTER the 7.0-day mark.
ROAS_LABEL = "D7 (through the trial-end charge)"  # a strict 7.0-day cut drops it and understates free trial.
# Per test: the ad-spend window + spend per arm (from Meta). Revenue is computed
# live for the SAME window, so ROAS = windowed net revenue ÷ spend.
# Replace estimates with actual Meta "amount spent" for the exact window.
SPEND = {
 "Romania free vs picker": {
   "window": ["2026-06-20", "2026-07-01"],
   "note": "ROAS D7 = net revenue within ~7 days of signup ÷ ad spend (the decision metric), run through the trial-end charge. Renewals not included.",
   "arms": {
     "rofree": {"campaign": "CBO Trial started – RO", "spend": 4449.64,
                "flag": "Actual Meta spend for 20–30 Jun (windowed export). Was mistakenly treated as an estimate earlier."},
     "ropick": {"campaign": "CBO Purchase – RO (Test)", "spend": 4256.36,
                "flag": "Jun 19 → off total (≈ test window)"},
   }},
 "Japan €60 vs €80": {
   "window": ["2026-06-17", "2026-07-15"],
   "note": "Revenue D7 shown. Add Japan Meta spend (per arm, since 17 Jun) to compute ROAS.",
   "arms": {
     "jp60": {"campaign": "Japan €60 campaign", "spend": None, "flag": "SPEND NEEDED — paste Meta amount spent for the €60 arm, 17 Jun→now"},
     "jp80": {"campaign": "Japan €80 campaign", "spend": None, "flag": "SPEND NEEDED — paste Meta amount spent for the €80 arm, 17 Jun→now"},
   }},
 "Greece free vs picker": {
   "window": ["2026-06-26", "2026-07-04"],
   "note": "ROAS D7 through the trial-end charge. Two Greece campaigns: always-on free trial vs the plan-picker test (Jun 25→off).",
   "arms": {
     "grfree": {"campaign": "CBO Trial started – GR", "spend": 4767.91,
                "flag": "Actual Meta spend for 26 Jun–3 Jul (windowed export). Confirmed by user."},
     "grpick": {"campaign": "CBO monthly/yearly plan – GR (Test)", "spend": 4614.83,
                "flag": "Jun 25 → off total (≈ test window)"},
   }},
 "Czechia paid trial €0.99": {
   "window": ["2026-07-03", "2026-07-15"],
   "note": "Started 6 Jul — 24 users, cohort still maturing (annual charge lands ~7 days out), so ROAS not yet meaningful. Add spend when it matures.",
   "arms": {"czpt": {"campaign": "Czechia paid-trial campaign", "spend": None, "flag": "SPEND NEEDED — and cohort still maturing"}}},
 "RO+MD paid trial €0.99": {
   "window": ["2026-07-03", "2026-07-15"],
   "note": "Now receiving traffic (13 users, from 8 Jul) — cohort not yet matured. Add spend once it matures.",
   "arms": {"rompt": {"campaign": "RO+MD paid-trial campaign", "spend": None, "flag": "SPEND NEEDED — cohort just started (13 users, not matured)"}}},
}
# ======================================================================


c = pd.read_csv(CUST, dtype=str); pay = pd.read_csv(PAYS, dtype=str)
c['cr'] = pd.to_datetime(c['Created (UTC)'], errors='coerce', utc=True)
pay['cr'] = pd.to_datetime(pay['Created date (UTC)'], errors='coerce', utc=True)
NOW = pay['cr'].max()
c['age'] = (NOW - c['cr']).dt.total_seconds() / 86400
c['ff'] = c['ff_funnel (metadata)']
cmap = c.set_index('id')['ff']
pay['ff'] = pay['Customer ID'].map(cmap)
pay['amt'] = num(pay['Converted Amount']).fillna(0)
pay['ref'] = num(pay['Converted Amount Refunded']).fillna(0)
pay['P'] = pay['Status'].isin(['Paid', 'succeeded'])
pay['Fl'] = pay['Status'].isin(['Failed', 'requires_payment_method', 'requires_confirmation', 'canceled'])

def compute(ids, ff_for_bands, win, ann_min, yr_band=None):
    ids = set(ids); n = len(ids)
    sub = c[c['id'].isin(ids)]
    mat = set(sub[sub['age'] >= win]['id'])
    p = pay[pay['Customer ID'].isin(ids)]; pp = p[p['P']]
    net = pp.groupby('Customer ID')['amt'].sum().sub(p.groupby('Customer ID')['ref'].sum(), fill_value=0)
    payers = net[net > 0]; npay = len(payers)
    ann = set(pp[pp['amt'] >= ann_min]['Customer ID'])
    conv_mat = len(mat & ann)
    up_ids = set(cid for cid, a in zip(pp['Customer ID'], pp['amt']) if classify(ff_for_bands, a).startswith('upsell')) & set(payers.index)
    # upsell tiers
    tiers = {}
    for cid, a in zip(pp['Customer ID'], pp['amt']):
        cat = classify(ff_for_bands, a)
        if cat.startswith('upsell') and cid in payers.index:
            tiers.setdefault(cat, set()).add(cid)
    tiers = {k.replace('upsell ', ''): len(v) for k, v in tiers.items()}
    nfail = int(p['Fl'].sum()); natt = int(p['P'].sum()) + nfail
    d = dict(users=n, matured=len(mat), maturing=n - len(mat), payers=npay,
             conv=conv_mat, conv_rate=round(conv_mat / len(mat) * 100, 1) if mat else None,
             purchase_rate=round(npay / n * 100, 1) if n else 0,
             arpu=round(float(payers.sum()) / n, 2) if n else 0,
             arppu=round(float(payers.sum()) / npay, 2) if npay else 0,
             net=round(float(payers.sum()), 0),
             upsell_buyers=len(up_ids), upsell_rate=round(len(up_ids) / npay * 100, 1) if npay else 0,
             failed_rate=round(nfail / natt * 100, 1) if natt else 0, tiers=tiers,
             monthly=None, yearly=None, yearly_arpu=None, monthly_arpu=None, yearly_rev_share=None)
    if yr_band:
        lo, hi = yr_band
        yr = set(pp[(pp['amt'] >= lo) & (pp['amt'] < hi)]['Customer ID']) & set(payers.index)
        mo = set(payers.index) - yr
        yr_rev = float(payers[payers.index.isin(yr)].sum()); mo_rev = float(payers[payers.index.isin(mo)].sum())
        tot = yr_rev + mo_rev
        d.update(monthly=len(mo), yearly=len(yr),
                 yearly_arpu=round(yr_rev / len(yr), 2) if yr else 0,
                 monthly_arpu=round(mo_rev / len(mo), 2) if mo else 0,
                 yearly_rev_share=round(yr_rev / tot * 100, 1) if tot else 0)
    return d

def ids_of(ff): return c[c['ff'] == ff]['id']

# ---- variants (each row in charts/table) ----
V = []
ARM_IDS = {}
def add(test, arm, ff_key, ids, ff_bands, win, ann, yr=None, typ="", country=""):
    ids = list(ids); ARM_IDS[ff_key] = ids
    m = compute(ids, ff_bands, win, ann, yr)
    m.update(test=test, arm=arm, key=ff_key, type=typ, country=country)
    V.append(m)

add("Japan €60 vs €80", "€60 · ¥11,800", "jp60", ids_of("quiz_v1_jp_ft_11800yen-60-eur"), "quiz_v1_jp_ft_11800yen-60-eur", 7, 45, typ="Free trial", country="Japan")
add("Japan €60 vs €80", "€80 · ¥14,800", "jp80", ids_of("quiz_v1_jp_ft_14800yen-80-eur"), "quiz_v1_jp_ft_14800yen-80-eur", 7, 70, typ="Free trial", country="Japan")
add("Romania free vs picker", "Free trial", "rofree", c[(c['ff'] == 'quiz') & (c['Address Country'] == 'RO') & (c['cr'] >= '2026-06-19')]['id'], "quiz_v1_ro_nt_m10_y50eur", 7, 40, typ="Free trial", country="Romania")
add("Romania free vs picker", "Plan picker", "ropick", ids_of("quiz_v1_ro_nt_m10_y50eur"), "quiz_v1_ro_nt_m10_y50eur", 0, 30, (33, 42), typ="Plan picker", country="Romania")
add("Greece free vs picker", "Free trial", "grfree", c[(c['ff'] == 'quiz') & (c['Address Country'] == 'GR') & (c['cr'] >= '2026-06-26')]['id'], "quiz_v1_gr_nt_m10_y50eur", 7, 40, typ="Free trial", country="Greece")
add("Greece free vs picker", "Plan picker", "grpick", ids_of("quiz_v1_gr_nt_m10_y50eur"), "quiz_v1_gr_nt_m10_y50eur", 0, 40, (45, 55), typ="Plan picker", country="Greece")
add("Czechia paid trial €0.99", "Paid trial", "czpt", ids_of("quiz_v1_cz_pt_y60eur"), "quiz_v1_cz_pt_y60eur", 7, 45, typ="Paid trial", country="Czechia")
add("RO+MD paid trial €0.99", "Paid trial", "rompt", ids_of("quiz_v1_ro_pt_y60eur"), "quiz_v1_ro_pt_y60eur", 7, 45, typ="Paid trial", country="Romania+Moldova")

# ---- per-test meta (status + winner) ----
TESTS = [
 {"name": "Japan €60 vs €80", "start": "17 Jun", "status": "Running",
  "winner": "€80 back ahead this read — conversion 52% vs 44%, ARPPU €70.7 vs €62.4. But the verdict has flip-flopped across reads because the €80 arm is small (31 matured). Do NOT call it yet — needs more €80 volume to stabilize.",
  "wtone": "neutral"},
 {"name": "Romania free vs picker", "start": "20 Jun", "status": "Running",
  "winner": "Plan picker wins — with actual spend, D7 ROAS 0.64 vs 0.47 for free trial, and ~2.4× revenue per user. Free trial is the weakest on both.",
  "wtone": "good"},
 {"name": "Greece free vs picker", "start": "26 Jun", "status": "Running",
  "winner": "Plan picker wins on D7 ROAS with actual spend (0.57 vs 0.48) and monetizes far better per user. Picker mix stays monthly-heavy (yearly = 66% of revenue).",
  "wtone": "good"},
 {"name": "Czechia paid trial €0.99", "start": "6 Jul", "status": "Just started",
  "winner": "First conversions in: of 5 matured, 2 converted to annual (~40%). €0.99 trial paid at 91%, 20 upsell buyers. Sample tiny (5 matured) — directional only; the €3.99 Greece test hit 57%, so watch whether the lower barrier holds conversion as more mature.",
  "wtone": "warn"},
 {"name": "RO+MD paid trial €0.99", "start": "8 Jul", "status": "Just started",
  "winner": "55 users (mostly RO, 2 MD); €0.99 trial paid at ~78%, 18 upsell buyers. Still 0 matured (earliest ~6d) — first annual charges land ~15 Jul. No conversion read yet.",
  "wtone": "warn"},
]

def horizon_net(ids, w0, w1, days):
    """Net EUR realised within `days` of each customer's signup, for customers acquired in [w0,w1)."""
    ids = set(ids)
    sub = c[c['id'].isin(ids) & (c['cr'] >= w0) & (c['cr'] < w1)][['id', 'cr']]
    sig = dict(zip(sub['id'], sub['cr']))
    wids = set(sub['id'])
    if not wids:
        return 0, 0, 0.0
    p = pay[pay['Customer ID'].isin(wids)].copy()
    if p.empty:
        return len(wids), 0, 0.0
    p['sig'] = p['Customer ID'].map(sig)
    d = (p['cr'] - p['sig']).dt.total_seconds() / 86400
    within = p[(d >= -0.5) & (d <= days)]
    paid = within[within['P']]
    net = paid.groupby('Customer ID')['amt'].sum().sub(within.groupby('Customer ID')['ref'].sum(), fill_value=0)
    payers = net[net > 0]
    return len(wids), len(payers), float(payers.sum())

ROAS = []
H = ROAS_HORIZON_DAYS
for test, cfg in SPEND.items():
    w0 = pd.Timestamp(cfg['window'][0], tz='UTC'); w1 = pd.Timestamp(cfg['window'][1], tz='UTC')
    arms = []
    for key, a in cfg['arms'].items():
        n, npay, net = horizon_net(ARM_IDS.get(key, []), w0, w1, H)
        arms.append({"arm": next((v['arm'] for v in V if v['key'] == key), key), "campaign": a['campaign'],
                     "users": n, "payers": npay, "revenue": round(net, 2), "spend": a['spend'],
                     "flag": a['flag'], "roas": round(net / a['spend'], 2) if a['spend'] else None,
                     "cac": round(a['spend'] / npay, 2) if (npay and a['spend']) else None})
    ROAS.append({"test": test, "horizon": H, "hlabel": ROAS_LABEL,
                 "window": cfg['window'][0] + " → " + (w1 - pd.Timedelta(days=1)).strftime('%Y-%m-%d'),
                 "note": cfg['note'], "arms": arms})

data_date = f"{NOW:%d %b %Y}"
payload = json.dumps({"variants": V, "tests": TESTS, "roas": ROAS, "date": data_date})

TPL = r"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Flashbook — Funnel Tests Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1"></script>
<style>
:root{--bg:#0E1116;--card:#161B22;--card2:#1C2230;--line:#2A323D;--text:#E6EAF0;--muted:#8B95A5;--dim:#5E6776;--green:#3FB950;--blue:#4C8DD8;--amber:#D7A23B;--red:#E05D5D;--radius:12px;--gap:16px}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;padding:24px;line-height:1.5}
.wrap{max-width:1180px;margin:0 auto}
header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;border-bottom:1px solid var(--line);padding-bottom:20px;margin-bottom:var(--gap)}
h1{font-size:22px;font-weight:700;letter-spacing:-.02em}
.sub{color:var(--dim);font-size:13px;margin-top:4px}
select{padding:8px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card2);color:var(--text);font-size:14px}
.label{font-size:12px;color:var(--muted);margin-right:6px}
.filters{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--gap);margin-bottom:var(--gap)}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:18px 20px}
.kpi .l{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.kpi .v{font-size:28px;font-weight:700;margin-top:6px;font-variant-numeric:tabular-nums}
.tests{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:var(--gap);margin-bottom:var(--gap)}
.tcard{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--dim);border-radius:var(--radius);padding:16px 18px;cursor:pointer;transition:border-color .15s}
.tcard:hover{border-color:var(--blue)}
.tcard.good{border-left-color:var(--green)}.tcard.warn{border-left-color:var(--amber)}.tcard.bad{border-left-color:var(--red)}.tcard.neutral{border-left-color:var(--blue)}
.tcard.sel{background:var(--card2);border-color:var(--blue)}
.tcard .tn{font-size:14px;font-weight:700} .tcard .ts{font-size:11px;color:var(--dim);margin:2px 0 8px}
.badge{display:inline-block;font-size:10px;font-weight:600;padding:2px 8px;border-radius:999px;margin-bottom:8px}
.b-run{background:rgba(63,185,80,.15);color:var(--green)}.b-start{background:rgba(215,162,59,.15);color:var(--amber)}.b-no{background:rgba(224,93,93,.15);color:var(--red)}
.tcard .tw{font-size:12px;color:var(--muted)}
.charts{display:grid;grid-template-columns:1fr 1fr;gap:var(--gap);margin-bottom:var(--gap)}
.chart{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:18px 20px}
.chart h3{font-size:13px;font-weight:600;margin-bottom:14px}
.chart canvas{max-height:280px}
.tablewrap{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:18px 20px;overflow-x:auto}
.tablewrap h3{font-size:13px;font-weight:600;margin-bottom:14px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:9px 10px;text-align:right;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums;white-space:nowrap}
th{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.4px;cursor:pointer}
th:first-child,td:first-child{text-align:left} td:nth-child(2),td:nth-child(3),th:nth-child(2),th:nth-child(3){text-align:left;color:var(--muted)}
tr:hover td{background:var(--card2)}
.foot{color:var(--dim);font-size:12px;margin-top:18px;border-top:1px solid var(--line);padding-top:14px}
.roas{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:18px 20px;margin-bottom:var(--gap)}
.roas h3{font-size:13px;font-weight:600;margin-bottom:4px}
.roas .rn{font-size:12px;color:var(--amber);margin-bottom:14px}
.roasgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:var(--gap)}
.rarm{background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:16px}
.rarm .ra{font-size:14px;font-weight:700;margin-bottom:2px} .rarm .rc{font-size:11px;color:var(--dim);margin-bottom:12px}
.rrow{display:flex;justify-content:space-between;font-size:13px;padding:6px 0;color:var(--muted)} .rrow b{color:var(--text);font-variant-numeric:tabular-nums}
.roasbig{font-size:30px;font-weight:700;font-variant-numeric:tabular-nums}
.rflag{font-size:11px;color:var(--amber);margin-top:10px;line-height:1.4}
@media(max-width:820px){.kpis{grid-template-columns:repeat(2,1fr)}.charts{grid-template-columns:1fr}.roasgrid{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<header><div><h1>Funnel Tests — Live Dashboard</h1><div class="sub" id="sub"></div></div>
<div class="filters">
<span class="label">Test</span><select id="filter"><option value="all">All tests</option></select>
<span class="label">Type</span><select id="ftype"><option value="all">All types</option></select>
<span class="label">Country</span><select id="fctry"><option value="all">All countries</option></select>
</div></header>
<section class="kpis" id="kpis"></section>
<section id="roasWrap"></section>
<section class="tests" id="tests"></section>
<section class="charts">
<div class="chart"><h3>ARPU per entered user (€)</h3><canvas id="cArpu"></canvas></div>
<div class="chart"><h3>Conversion / purchase rate (%)</h3><canvas id="cConv"></canvas></div>
<div class="chart"><h3>Plan mix — monthly vs yearly (plan pickers)</h3><canvas id="cPlan"></canvas></div>
<div class="chart"><h3>Upsell take rate (% of payers)</h3><canvas id="cUp"></canvas></div>
</section>
<div class="tablewrap"><h3>All variants — detail</h3><table id="tbl"></table></div>
<div class="foot" id="foot"></div>
</div>
<script>
const D = /*DATA_JSON*/;
const GREEN="#3FB950",BLUE="#4C8DD8",AMBER="#D7A23B",RED="#E05D5D",MUTED="#8B95A5";
Chart.defaults.color=MUTED;Chart.defaults.borderColor="#2A323D";Chart.defaults.font.family="-apple-system,Segoe UI,Roboto,sans-serif";
let filter="all", ftype="all", fctry="all";
const sel=()=>D.variants.filter(v=>(filter==="all"||v.test===filter)&&(ftype==="all"||v.type===ftype)&&(fctry==="all"||v.country===fctry));
function fullLabel(v){return (v.test.length>16?v.test.slice(0,15)+"…":v.test)+" · "+v.arm;}

document.getElementById("sub").textContent="Data as of "+D.date+" · cumulative merged export · numbers computed live";
document.getElementById("foot").innerHTML="Matured = cohort ≥ trial window (7d trial, 0d no-trial). Conv→annual = matured with a paid charge ≥ annual price. ARPU/user = net € (paid−refunds, incl. upsells) ÷ entered users. Plan/upsell inferred from € amount (price_id empty in export). Greece €9.99 monthly = PDF upsell price, so GR monthly is an upper bound.";

const fsel=document.getElementById("filter"), tsel=document.getElementById("ftype"), csel=document.getElementById("fctry");
D.tests.forEach(t=>{const o=document.createElement("option");o.value=t.name;o.textContent=t.name;fsel.appendChild(o);});
[...new Set(D.variants.map(v=>v.type))].forEach(x=>{const o=document.createElement("option");o.value=x;o.textContent=x;tsel.appendChild(o);});
[...new Set(D.variants.map(v=>v.country))].forEach(x=>{const o=document.createElement("option");o.value=x;o.textContent=x;csel.appendChild(o);});
fsel.onchange=e=>{filter=e.target.value;render();document.querySelectorAll(".tcard").forEach(c=>c.classList.toggle("sel",c.dataset.t===filter));};
tsel.onchange=e=>{ftype=e.target.value;render();};
csel.onchange=e=>{fctry=e.target.value;render();};

// test cards
const tc=document.getElementById("tests");
D.tests.forEach(t=>{
  const badge=t.status==="Running"?'<span class="badge b-run">RUNNING</span>':t.status==="Just started"?'<span class="badge b-start">JUST STARTED</span>':t.status==="No data"?'<span class="badge b-no">NO DATA</span>':'<span class="badge b-run">'+t.status+'</span>';
  const el=document.createElement("div");el.className="tcard "+t.wtone;el.dataset.t=t.name;
  el.innerHTML=badge+'<div class="tn">'+t.name+'</div><div class="ts">Start '+t.start+'</div><div class="tw">'+t.winner+'</div>';
  el.onclick=()=>{filter=(filter===t.name?"all":t.name);fsel.value=filter;render();document.querySelectorAll(".tcard").forEach(c=>c.classList.toggle("sel",c.dataset.t===filter));};
  tc.appendChild(el);
});

function fmtE(x){return x==null?"—":"€"+Number(x).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});}
function kpis(){
  const v=sel();
  const users=v.reduce((a,x)=>a+x.users,0), payers=v.reduce((a,x)=>a+x.payers,0), net=v.reduce((a,x)=>a+x.net,0);
  const wins=D.tests.filter(t=>t.wtone==="good").length;
  const K=[["Variants in view",v.length],["Paying users",payers.toLocaleString()],["Net revenue","€"+Math.round(net).toLocaleString()],[filter==="all"?"Clear winners":"Users entered",filter==="all"?wins:users.toLocaleString()]];
  document.getElementById("kpis").innerHTML=K.map(k=>'<div class="kpi"><div class="l">'+k[0]+'</div><div class="v">'+k[1]+'</div></div>').join("");
}
let charts={};
function bar(id,labels,data,color,pct){
  if(charts[id])charts[id].destroy();
  charts[id]=new Chart(document.getElementById(id),{type:"bar",data:{labels,datasets:[{data,backgroundColor:color,borderRadius:5,maxBarThickness:46}]},
   options:{indexAxis:"y",responsive:true,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>(pct?c.parsed.x+"%":"€"+c.parsed.x)}}},
   scales:{x:{ticks:{callback:v=>(pct?v+"%":"€"+v)},grid:{color:"#20262f"}},y:{grid:{display:false}}},animation:false}});
}
function planChart(){
  const v=sel().filter(x=>x.yearly!=null);
  if(charts.cPlan)charts.cPlan.destroy();
  charts.cPlan=new Chart(document.getElementById("cPlan"),{type:"bar",
   data:{labels:v.map(fullLabel),datasets:[{label:"Monthly",data:v.map(x=>x.monthly),backgroundColor:BLUE,borderRadius:4},{label:"Yearly",data:v.map(x=>x.yearly),backgroundColor:GREEN,borderRadius:4}]},
   options:{responsive:true,plugins:{legend:{position:"bottom"},tooltip:{callbacks:{afterBody:i=>{const x=v[i[0].dataIndex];return "Yearly = "+x.yearly_rev_share+"% of revenue";}}}},scales:{x:{stacked:true,grid:{display:false}},y:{stacked:true,grid:{color:"#20262f"}}},animation:false}});
}
function upChart(){
  // grouped upsell tiers per variant
  const v=sel();const tierNames=[...new Set(v.flatMap(x=>Object.keys(x.tiers)))];
  const palette=[GREEN,BLUE,AMBER,RED];
  if(charts.cUp)charts.cUp.destroy();
  charts.cUp=new Chart(document.getElementById("cUp"),{type:"bar",
   data:{labels:v.map(fullLabel),datasets:[{label:"Upsell take %",data:v.map(x=>x.upsell_rate),backgroundColor:AMBER,borderRadius:5,maxBarThickness:46}]},
   options:{indexAxis:"y",responsive:true,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>c.parsed.x+"% of payers",afterBody:i=>{const x=v[i[0].dataIndex];return Object.entries(x.tiers).map(([k,n])=>k+": "+n+" buyers");}}}},scales:{x:{ticks:{callback:v=>v+"%"},grid:{color:"#20262f"}},y:{grid:{display:false}}},animation:false}});
}
const COLS=[["arm","Variant"],["type","Type"],["country","Country"],["users","Users"],["matured","Matured"],["payers","Payers"],["conv_rate","Conv %"],["purchase_rate","Purch %"],["arpu","ARPU/user"],["arppu","ARPPU"],["upsell_rate","Upsell %"],["failed_rate","Failed %"],["net","Net €"]];
let sortK="arpu",sortDir=-1;
function table(){
  const v=[...sel()].sort((a,b)=>{const x=a[sortK],y=b[sortK];return ((x==null?-1:x)>(y==null?-1:y)?1:-1)*sortDir;});
  const money=new Set(["arpu","arppu","net"]),pct=new Set(["conv_rate","purchase_rate","upsell_rate","failed_rate"]);
  let h="<thead><tr>"+COLS.map(c=>"<th data-k='"+c[0]+"'>"+c[1]+"</th>").join("")+"</tr></thead><tbody>";
  v.forEach(r=>{h+="<tr>"+COLS.map(c=>{let val=r[c[0]];if(val==null)val="—";else if(money.has(c[0]))val=(c[0]==="net"?"€"+Math.round(val).toLocaleString():fmtE(val));else if(pct.has(c[0]))val=val+"%";return "<td>"+val+"</td>";}).join("")+"</tr>";});
  const t=document.getElementById("tbl");t.innerHTML=h+"</tbody>";
  t.querySelectorAll("th").forEach(th=>th.onclick=()=>{const k=th.dataset.k;sortDir=(sortK===k?-sortDir:-1);sortK=k;table();});
}
function renderRoas(){
  const wrap=document.getElementById("roasWrap");
  const shownTests=new Set(sel().map(v=>v.test));
  const blocks=D.roas.filter(r=>shownTests.has(r.test));
  wrap.innerHTML=blocks.map(r=>{
    const roasVals=r.arms.map(a=>a.roas).filter(x=>x!=null);
    const best=roasVals.length?Math.max(...roasVals):null;
    const arms=r.arms.map(a=>{
      const has=a.roas!=null;
      const win=(has&&a.roas===best)?'style="color:var(--green)"':'';
      const roasStr=has?a.roas.toFixed(2):'<span style="color:var(--amber)">—</span>';
      const spendStr=a.spend!=null?'€'+Math.round(a.spend).toLocaleString():'<span style="color:var(--amber)">needed</span>';
      const cacStr=a.cac!=null?'€'+a.cac.toFixed(2):'—';
      return '<div class="rarm"><div class="ra">'+a.arm+'</div><div class="rc">'+a.campaign+'</div>'+
        '<div class="roasbig" '+win+'>ROAS '+roasStr+'</div>'+
        '<div class="rrow"><span>Revenue D7 (window)</span><b>€'+Math.round(a.revenue).toLocaleString()+'</b></div>'+
        '<div class="rrow"><span>Ad spend</span><b>'+spendStr+'</b></div>'+
        '<div class="rrow"><span>Payers · CAC</span><b>'+a.payers+' · '+cacStr+'</b></div>'+
        '<div class="rflag">⚠ '+a.flag+'</div></div>';
    }).join("");
    return '<div class="roas"><h3>💸 '+r.test+' — ROAS '+r.hlabel+' ('+r.window+')</h3><div class="rn">'+r.note+'</div><div class="roasgrid">'+arms+'</div></div>';
  }).join("");
}
function render(){kpis();renderRoas();
  const v=sel();
  bar("cArpu",v.map(fullLabel),v.map(x=>x.arpu),GREEN,false);
  bar("cConv",v.map(fullLabel),v.map(x=>x.conv_rate!=null?x.conv_rate:x.purchase_rate),BLUE,true);
  planChart();upChart();table();
}
render();
</script></body></html>"""

html = TPL.replace("/*DATA_JSON*/", payload)
out = "/home/claude/flashbook_dashboard.html"
open(out, "w").write(html)
print("saved", out, "| variants:", len(V), "| date", data_date)
