"""
Fair-value model (modern Graham framework) – shared by the Google Sheet and the dashboard.
All $ figures in billions unless noted. Inputs sourced from Q2-2026 filings / price history as of 2026-10-14 close.
"""
import json, math

AS_OF = "2026-10-14"
GT = 0.025            # terminal growth
PROBS = {"bear": 0.30, "base": 0.50, "bull": 0.20}

# ---------------------------------------------------------------- inputs
STOCKS = {
 "AAPL": dict(name="Apple Inc.", price=342.96, shares=14.594, rev=466.8, fcf=136.683, sbc=13.706,
              net_cash=64.2, extra=0.0, r=0.09, mos=0.25,
              scen=dict(bear=dict(g1=.06,g10=.03,m=.225), base=dict(g1=.09,g10=.04,m=.245), bull=dict(g1=.12,g10=.05,m=.265)),
              notes="TTM to Jun-2026. FCF margin is flattered by low cash taxes; normalised SBC-adjusted margin 24.5% base."),
 "MSFT": dict(name="Microsoft Corp.", price=533.69, shares=7.43, rev=331.3, fcf=66.987, sbc=12.405,
              net_cash=20.0, extra=0.0, r=0.09, mos=0.25,
              scen=dict(bear=dict(g1=.12,g10=.035,m=.18), base=dict(g1=.17,g10=.05,m=.25), bull=dict(g1=.20,g10=.06,m=.29)),
              notes="FY26 (Jun-2026). Capex $116B cash (+finance leases) crushes current FCF; margin recovers as build-out matures."),
 "GOOGL": dict(name="Alphabet Inc. (Class A)", price=347.64, shares=12.23, rev=445.8, fcf=53.273, sbc=24.5,
              net_cash=129.7, extra=65.7, r=0.10, mos=0.30,
              scen=dict(bear=dict(g1=.14,g10=.035,m=.13), base=dict(g1=.20,g10=.05,m=.19), bull=dict(g1=.24,g10=.06,m=.24)),
              notes="TTM to Jun-2026. SBC and TTM revenue are estimates. 'extra' = $131.5B private equity stakes at a 50% haircut."),
 "AMZN": dict(name="Amazon.com Inc.", price=254.08, shares=10.786, rev=775.7, fcf=-7.604, sbc=22.0,
              net_cash=-100.2, extra=0.0, r=0.105, mos=0.30,
              scen=dict(bear=dict(g1=.09,g10=.035,m=.05), base=dict(g1=.13,g10=.05,m=.085), bull=dict(g1=.16,g10=.06,m=.12)),
              notes="TTM to Jun-2026. FCF negative on $169B capex. SBC estimated. Anthropic stake NOT valued (upside not counted)."),
}

def dcf(rev0, m0, g1, g10, m_target, r, net_cash_plus, shares, gt=GT, ramp=5, detail=False):
    rev, pv, rows = rev0, 0.0, []
    for t in range(1, 11):
        g = g1 + (g10 - g1) * (t - 1) / 9
        rev *= 1 + g
        m = m0 + (m_target - m0) * min(t, ramp) / ramp
        fcf = rev * m
        df = 1 / (1 + r) ** t
        pv += fcf * df
        rows.append(dict(t=t, g=g, rev=rev, m=m, fcf=fcf, df=df, pv=fcf * df))
    tv = rows[-1]["fcf"] * (1 + gt) / (r - gt)
    pv_tv = tv * rows[-1]["df"]
    ev = pv + pv_tv
    eq = ev + net_cash_plus
    ps = eq / shares
    if detail:
        return dict(rows=rows, pv_fcf=pv, tv=tv, pv_tv=pv_tv, ev=ev, equity=eq, per_share=ps, tv_share=pv_tv / ev)
    return ps

def solve(f, lo, hi, tol=1e-6):
    flo = f(lo)
    for _ in range(200):
        mid = (lo + hi) / 2
        fm = f(mid)
        if (fm > 0) == (flo > 0): lo, flo = mid, fm
        else: hi = mid
        if hi - lo < tol: break
    return (lo + hi) / 2

out = {"as_of": AS_OF, "terminal_growth": GT, "probabilities": PROBS, "assets": {}}

for tk, s in STOCKS.items():
    m0 = (s["fcf"] - s["sbc"]) / s["rev"]
    nc = s["net_cash"] + s["extra"]
    res = {}
    for sc, p in s["scen"].items():
        d = dcf(s["rev"], m0, p["g1"], p["g10"], p["m"], s["r"], nc, s["shares"], detail=True)
        res[sc] = dict(params=p, per_share=d["per_share"], detail=d)
    fv = sum(PROBS[k] * res[k]["per_share"] for k in res)
    base = res["base"]["per_share"]
    # EPV (no-growth floor): normalised SBC-adj FCF / r
    epv = (s["rev"] * s["scen"]["base"]["m"] / s["r"] + nc) / s["shares"]
    # implied IRR at current price on base case
    irr = solve(lambda r: dcf(s["rev"], m0, **{k: s["scen"]["base"][k] for k in ("g1","g10")}, m_target=s["scen"]["base"]["m"], r=r, net_cash_plus=nc, shares=s["shares"]) - s["price"], 0.035, 0.30)
    # reverse DCF: first-year growth (fading to base g10) needed to justify price at required return
    rg = solve(lambda g1: dcf(s["rev"], m0, g1, s["scen"]["base"]["g10"], s["scen"]["base"]["m"], s["r"], nc, s["shares"]) - s["price"], 0.0, 1.5)
    # sensitivity base case: r vs gT
    rs = [s["r"] - .02, s["r"] - .01, s["r"], s["r"] + .01, s["r"] + .02]
    gs = [.015, .02, .025, .03, .035]
    sens = [[dcf(s["rev"], m0, s["scen"]["base"]["g1"], s["scen"]["base"]["g10"], s["scen"]["base"]["m"], r, nc, s["shares"], gt=g) for g in gs] for r in rs]
    out["assets"][tk] = dict(
        name=s["name"], type="stock", price=s["price"], shares=s["shares"], r=s["r"], mos=s["mos"],
        start_margin=m0, net_cash=nc, rev=s["rev"], notes=s["notes"],
        bear=res["bear"]["per_share"], base=base, bull=res["bull"]["per_share"],
        fair_value=fv, anchor=fv, buy_below=fv * (1 - s["mos"]), epv=epv,
        implied_irr=irr, reverse_g1=rg, tv_share=res["base"]["detail"]["tv_share"],
        sens=dict(r=rs, g=gs, grid=sens), detail={k: res[k]["detail"] for k in res}, scen=s["scen"], fcf=s["fcf"], sbc=s["sbc"],
    )

# ----------------------------------------------------------------- QQQ (look-through earnings model)
q = dict(price=728.95, r=0.095, mos=0.30)
TRAIL_PE, FWD_PE = 27.91, 21.5
e_lo, e_hi = q["price"] / TRAIL_PE, q["price"] / FWD_PE
qs = dict(bear=dict(eps=e_lo, g1=.08, g10=.035, conv=.70),
          base=dict(eps=(e_lo + e_hi) / 2, g1=.12, g10=.05, conv=.80),
          bull=dict(eps=e_hi, g1=.14, g10=.06, conv=.85))
def qqq(eps, g1, g10, conv, r=q["r"], gt=GT, detail=False):
    e, pv, rows = eps, 0.0, []
    for t in range(1, 11):
        g = g1 + (g10 - g1) * (t - 1) / 9
        e *= 1 + g
        f = e * conv
        df = 1 / (1 + r) ** t
        pv += f * df
        rows.append(dict(t=t, g=g, eps=e, fcf=f, df=df, pv=f * df))
    tv = rows[-1]["fcf"] * (1 + gt) / (r - gt)
    pv_tv = tv * rows[-1]["df"]
    v = pv + pv_tv
    return dict(rows=rows, pv_fcf=pv, tv=tv, pv_tv=pv_tv, per_share=v, tv_share=pv_tv / v) if detail else v
qres = {k: qqq(**v, detail=True) for k, v in qs.items()}
qfv = sum(PROBS[k] * qres[k]["per_share"] for k in qres)
qirr = solve(lambda r: qqq(**qs["base"], r=r) - q["price"], 0.035, 0.30)
qrs = [q["r"] - .02, q["r"] - .01, q["r"], q["r"] + .01, q["r"] + .02]
qgs = [.015, .02, .025, .03, .035]
out["assets"]["QQQ"] = dict(
    name="Invesco QQQ Trust (Nasdaq-100)", type="etf", price=q["price"], r=q["r"], mos=q["mos"],
    bear=qres["bear"]["per_share"], base=qres["base"]["per_share"], bull=qres["bull"]["per_share"],
    fair_value=qfv, anchor=qfv, buy_below=qfv * (1 - q["mos"]), epv=(qs["base"]["eps"] * qs["base"]["conv"] / q["r"]),
    implied_irr=qirr, tv_share=qres["base"]["tv_share"], scen=qs,
    sens=dict(r=qrs, g=qgs, grid=[[qqq(**qs["base"], r=r, gt=g) for g in qgs] for r in qrs]),
    detail={k: qres[k] for k in qres}, trailing_eps=e_lo, fwd_pe_ref=FWD_PE, trailing_pe=TRAIL_PE,
    notes="Look-through earnings model. Low-medium confidence: EPS inputs blend trailing GAAP (inflated by unrealised investment gains) and forward consensus.")

# ----------------------------------------------------------------- GLD (scenario reference range, NOT intrinsic value)
OZ = 0.0925   # approx. ounces of gold per GLD share (estimate)
g = dict(price=375.99)
gscen = dict(bear=dict(gold=3300, why="Real yields stay >2.5%, USD firm; gold reverts toward the inflation-adjusted 1980 peak (~$3,300-3,500)."),
             base=dict(gold=4100, why="Range-bound near the 2026 trading range as real yields and central-bank buying offset."),
             bull=dict(gold=5000, why="Fed pivots / inflation de-anchors; sell-side targets of $4,900-5,000 are reached."))
gprobs = {"bear": 0.35, "base": 0.45, "bull": 0.20}
gv = {k: v["gold"] * OZ for k, v in gscen.items()}
gfv = sum(gprobs[k] * gv[k] for k in gv)
out["assets"]["GLD"] = dict(
    name="SPDR Gold Shares", type="commodity", price=g["price"], r=None, mos=0.30,
    bear=gv["bear"], base=gv["base"], bull=gv["bull"], fair_value=gfv, anchor=gfv, buy_below=gfv * 0.70,
    epv=None, implied_irr=None, scen=gscen, probs=gprobs, oz_per_share=OZ, implied_gold=g["price"] / OZ,
    notes="No cash flows => no intrinsic value. Scenario REFERENCE range only (low confidence); oz/share is an estimate.")

json.dump(out, open("/tmp/claude-0/-home-claude/fc9c1ae0-822b-5ee4-919e-5198119cc063/scratchpad/work/results.json", "w"), indent=1, default=float)

print(f"{'Tkr':6}{'Price':>9}{'Bear':>9}{'Base':>9}{'Bull':>9}{'FV(30/50/20)':>14}{'BuyBelow':>10}{'Diff%':>8}{'EPV':>8}{'IRR':>7}{'revG1':>7}{'TV%':>6}")
for tk, a in out["assets"].items():
    diff = (a["price"] / a["fair_value"] - 1) * 100
    print(f"{tk:6}{a['price']:9.2f}{a['bear']:9.1f}{a['base']:9.1f}{a['bull']:9.1f}{a['fair_value']:14.1f}{a['buy_below']:10.1f}{diff:8.1f}"
          f"{(a['epv'] or 0):8.1f}{(a['implied_irr'] or 0)*100:7.2f}{(a.get('reverse_g1') or 0)*100:7.1f}{(a.get('tv_share') or 0)*100:6.0f}")
print("start margins:", {k: round(v['start_margin'], 4) for k, v in out['assets'].items() if 'start_margin' in v})
