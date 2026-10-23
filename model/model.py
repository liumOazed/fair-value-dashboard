"""
Fair-value model (modern Graham framework) – shared by the Google Sheet and the dashboard.
All $ figures in billions unless noted. Inputs sourced from Q2-2026 filings / price history as of 2026-10-14 close.
"""
import json, math

AS_OF = "2026-10-23"   # method change: FCF before interest at the required return, minus net debt
GT = 0.025            # terminal growth
PROBS = {"bear": 0.30, "base": 0.50, "bull": 0.20}
import pathlib
_ROOT = pathlib.Path(__file__).resolve().parent.parent
RR = json.load(open(_ROOT / "data/required_returns.json"))     # single source of truth for required returns
def req_return(t):
    if t not in RR["stocks"]: raise SystemExit(f"Add {t} to data/required_returns.json (with a reason)")
    return RR["stocks"][t]["r"]
RATE_GRID = [0.08, 0.09, 0.10, 0.11, 0.12]                     # rate table shown in the drawer (+ the chosen rate)

# ---------------------------------------------------------------- inputs
STOCKS = {
 "AAPL": dict(name="Apple Inc.", price=342.96, shares=14.594, rev=466.8, fcf=136.683, sbc=13.706,
              net_cash=64.2, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=.06,g10=.03,m=.225), base=dict(g1=.09,g10=.04,m=.245), bull=dict(g1=.12,g10=.05,m=.265)),
              notes="TTM to Jun-2026. FCF margin is flattered by low cash taxes; normalised SBC-adjusted margin 24.5% base."),
 "MSFT": dict(name="Microsoft Corp.", price=533.69, shares=7.43, rev=331.3, fcf=66.987, sbc=12.405,
              net_cash=20.0, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=.12,g10=.035,m=.18), base=dict(g1=.17,g10=.05,m=.25), bull=dict(g1=.20,g10=.06,m=.29)),
              notes="FY26 (Jun-2026). Capex $116B cash (+finance leases) crushes current FCF; margin recovers as build-out matures."),
 "GOOGL": dict(name="Alphabet Inc. (Class A)", price=347.64, shares=12.23, rev=445.8, fcf=53.273, sbc=24.5,
              net_cash=129.7, extra=65.7, mos=0.30,
              scen=dict(bear=dict(g1=.14,g10=.035,m=.13), base=dict(g1=.20,g10=.05,m=.19), bull=dict(g1=.24,g10=.06,m=.24)),
              notes="TTM to Jun-2026. SBC and TTM revenue are estimates. 'extra' = $131.5B private equity stakes at a 50% haircut."),
 "AMZN": dict(name="Amazon.com Inc.", price=254.08, shares=10.786, rev=775.7, fcf=-7.604, sbc=22.0,
              net_cash=-100.2, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.09,g10=.035,m=.05), base=dict(g1=.13,g10=.05,m=.085), bull=dict(g1=.16,g10=.06,m=.12)),
              notes="TTM to Jun-2026. FCF negative on $169B capex. SBC estimated. Anthropic stake NOT valued (upside not counted)."),
 "NVDA": dict(name="NVIDIA Corp.", price=217.23, shares=24.147, rev=302.97, fcf=127.01, sbc=7.0,
              net_cash=23.61, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.08,g10=.03,m=.32), base=dict(g1=.22,g10=.04,m=.42), bull=dict(g1=.35,g10=.06,m=.50)),
              notes="TTM to Jul-2026 (FY27 Q2). SBC is an ESTIMATE (about 2.3% of revenue). Data-centre demand is highly cyclical and concentrated: lower confidence. Base case is deliberately below consensus growth. Base case is deliberately below consensus growth."),
 "AVGO": dict(name="Broadcom Inc.", price=344.33, shares=4.774, rev=89.10, fcf=39.40, sbc=8.9,
              net_cash=-35.44, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.12,g10=.03,m=.30), base=dict(g1=.25,g10=.05,m=.38), bull=dict(g1=.35,g10=.06,m=.43)),
              notes="TTM to Aug-2026 (FY26 Q3). SBC is an ESTIMATE (about 10% of revenue). Net debt from acquisitions. AI custom-chip demand drives growth."),
 "LLY": dict(name="Eli Lilly and Co.", price=1251.61, shares=0.8915, rev=79.67, fcf=18.19, sbc=2.2,
              net_cash=-45.16, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=.08,g10=.03,m=.26), base=dict(g1=.20,g10=.04,m=.32), bull=dict(g1=.28,g10=.05,m=.38)),
              notes="TTM to Jun-2026. SBC is an ESTIMATE. FCF is depressed by $9.9B capex on new plants; margin rises as the build-out matures. Growth rests on obesity drugs; pricing and patent risk."),
 "ADBE": dict(name="Adobe Inc.", price=251.67, shares=0.3892, rev=25.97, fcf=10.59, sbc=2.1,
              net_cash=-1.15, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=-.03,g10=.02,m=.26), base=dict(g1=.07,g10=.03,m=.32), bull=dict(g1=.11,g10=.045,m=.36)),
              notes="TTM to Aug-2026 (FY26 Q3). SBC is an ESTIMATE (about 8% of revenue). The bear case assumes generative-AI tools erode its creative-software moat (sales shrink first, then recover slowly); the market price looks close to that view."),
 "APP": dict(name="AppLovin Corp.", price=279.29, shares=0.3347, rev=6.83, fcf=4.53, sbc=0.4,
              net_cash=-0.46, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=.10,g10=.03,m=.45), base=dict(g1=.25,g10=.05,m=.55), bull=dict(g1=.40,g10=.06,m=.62)),
              notes="TTM to Jun-2026. SBC is an ESTIMATE. Very high margins and heavy reliance on terminal value: lower confidence. Higher required return (11%) and 35% safety margin."),
 "FICO": dict(name="Fair Isaac Corp.", price=769.93, shares=0.0216, rev=2.39, fcf=1.00, sbc=0.2,
              net_cash=-5.35, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.05,g10=.03,m=.33), base=dict(g1=.10,g10=.04,m=.38), bull=dict(g1=.14,g10=.05,m=.43)),
              notes="TTM to Jun-2026. SBC is an ESTIMATE (about 8% of revenue). Net debt of $5.4B from buybacks. Pricing power in credit scores faces regulatory scrutiny."),
 "APA": dict(name="APA Corporation", price=49.15, shares=0.34015, rev=8.57, fcf=2.10, sbc=0.15,
              net_cash=-3.44, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-.08,g10=.00,m=.10), base=dict(g1=-.04,g10=.02,m=.15), bull=dict(g1=.02,g10=.025,m=.20)),
              notes="TTM to Jun-2026, earned at about $98/bbl realised oil: a cycle high, so every case assumes revenue falls and the cash margin shrinks from today's ~23% (after SBC) toward 10-20%. SBC from filings (~$0.15B/yr). Net debt $3.4B. Oil-price dependent: lower confidence, 10% required return and 35% safety margin."),
 "DECK": dict(name="Deckers Outdoor Corp.", price=85.71, shares=0.13618, rev=5.53, fcf=1.12, sbc=0.07,
              net_cash=1.13, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.00,g10=.02,m=.15), base=dict(g1=.06,g10=.03,m=.18), bull=dict(g1=.10,g10=.04,m=.20)),
              notes="TTM to Jun-2026. FY27 guidance: revenue $5.86-5.91B (high single digit growth), HOKA low-double-digit, UGG mid-single-digit, operating margin ~21.5% after ~150bp tariff drag. SBC is an ESTIMATE (~1% of revenue). $1.1B net cash, heavy buybacks. Fashion/brand risk: the bear case assumes HOKA growth stalls."),
 "INCY": dict(name="Incyte Corp.", price=113.07, shares=0.2027, rev=5.57, fcf=1.92, sbc=0.26,
              net_cash=3.23, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-.02,g10=.02,m=.18), base=dict(g1=.03,g10=.03,m=.24), bull=dict(g1=.08,g10=.04,m=.30)),
              notes="TTM to Jun-2026, revenue cut by the one-off $246M Opzelura settlement benefit. Net cash $4.5B less ~$1.27B Vega (latarcibart) upfront due in Q3-2026. SBC from filings (~$0.26B/yr). Jakafi is ~60% of sales and faces loss of exclusivity later this decade, so the bear case has shrinking sales and lower margins; 35% safety margin."),
 "MKC": dict(name="McCormick & Co.", price=46.35, shares=0.26906, rev=7.69, fcf=0.926, sbc=0.05,
              net_cash=-4.69, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.01,g10=.02,m=.10), base=dict(g1=.04,g10=.03,m=.125), bull=dict(g1=.06,g10=.035,m=.14)),
              notes="TTM to Aug-2026. Trailing P/E is distorted by a one-off $867M gain on taking control of McCormick de Mexico (Jan-2026), so this model uses free cash flow. Organic growth ~3-6%. STANDALONE value only: the pending Unilever Foods combination (McCormick holders to own 35%, $15.7B cash to Unilever, close expected mid-2027) would change the per-share value substantially. Lower confidence."),
}

# ---------------------------------------------------------------- capital structure (for WACC)
# Gross debt and after-tax cost of debt make the DCF consistent: free cash flow BEFORE interest (FCFF) is discounted at
# WACC, then net debt is subtracted. Source: yfinance annual statements via the screener run of 2026-10-23.
# debt = total debt incl. leases ($B); rd = interest expense / average debt (clipped to 2-10% when used); tax = effective rate.
FIN = {
 "AAPL": dict(debt=84.34, interest=3.933, rd=0.0383, tax=0.156), "MSFT": dict(debt=128.81, interest=3.051, rd=0.0520, tax=0.194),
 "GOOGL": dict(debt=120.79, interest=0.736, rd=0.0180, tax=0.168), "AMZN": dict(debt=251.64, interest=2.274, rd=0.0160, tax=0.196),
 "NVDA": dict(debt=38.86, interest=0.259, rd=0.0246, tax=0.151), "AVGO": dict(debt=59.42, interest=3.210, rd=0.0484, tax=0.256),
 "LLY": dict(debt=54.91, interest=0.781, rd=0.0205, tax=0.198), "ADBE": dict(debt=6.79, interest=0.263, rd=0.0414, tax=0.180),
 "APP": dict(debt=3.52, interest=0.207, rd=0.0583, tax=0.132), "FICO": dict(debt=5.60, interest=0.134, rd=0.0504, tax=0.188),
 "APA": dict(debt=3.88, interest=0.278, rd=0.0517, tax=0.350), "DECK": dict(debt=0.47, interest=0.003, rd=0.0078, tax=0.228),
 "INCY": dict(debt=0.04, interest=0.002, rd=0.0578, tax=0.227), "MKC": dict(debt=5.02, interest=0.196, rd=0.0452, tax=0.214),
}

# DCF_METHOD: "equity" = original (FCF after interest at the required return, minus net debt; double-counts debt cost)
#             "fcff_re" = FCF before interest at the required return (hurdle for the whole business), minus net debt
#             "fcff_wacc" = textbook: FCF before interest at WACC, minus net debt (rewards leverage unless the equity rate is re-levered)
DCF_METHOD = "fcff_re"

def wacc_of(t, s, re):
    """Blended cost of capital: market-value equity at the required return + debt at the after-tax cost of debt."""
    f = FIN[t]
    E, D = s["price"] * s["shares"], f["debt"]
    rd = min(max(f["rd"], 0.02), 0.10)
    return (E * re + D * rd * (1 - f["tax"])) / (E + D)

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
    s["r"] = req_return(tk)                                   # cost of equity (required return)
    f = FIN[tk]
    aint = 0.0 if DCF_METHOD == "equity" else f["interest"] * (1 - f["tax"])   # after-tax interest added back: FCF -> FCFF
    add = aint / s["rev"]                                     # kept as a constant share of revenue in every year
    m0 = (s["fcf"] - s["sbc"] + aint) / s["rev"]              # starting FCFF margin (after SBC)
    W = (lambda re: wacc_of(tk, s, re)) if DCF_METHOD == "fcff_wacc" else (lambda re: re)
    w = W(s["r"])
    nc = s["net_cash"] + s["extra"]
    S2 = {k: dict(v, m=v["m"] + add) for k, v in s["scen"].items()}   # scenario margins stated to equity, + interest share
    res = {}
    for sc, p in S2.items():
        d = dcf(s["rev"], m0, p["g1"], p["g10"], p["m"], w, nc, s["shares"], detail=True)
        res[sc] = dict(params=p, per_share=d["per_share"], detail=d)
    fv = sum(PROBS[k] * res[k]["per_share"] for k in res)
    base = res["base"]["per_share"]
    # EPV (no-growth floor): normalised SBC-adj FCF / r
    B = S2["base"]
    epv = (s["rev"] * B["m"] / w + nc) / s["shares"]          # no-growth value: base FCFF / WACC - net debt
    # implied return to shareholders at the current price (solve the cost of equity, WACC follows)
    irr = solve(lambda re: dcf(s["rev"], m0, B["g1"], B["g10"], B["m"], W(re), nc, s["shares"]) - s["price"], 0.035, 0.30)
    # reverse DCF: first-year growth (fading to base g10) needed to justify price at the required return
    rg = solve(lambda g1: dcf(s["rev"], m0, g1, B["g10"], B["m"], w, nc, s["shares"]) - s["price"], -0.5, 1.5)
    # sensitivity base case: required return (-> WACC) vs terminal growth
    rs = [s["r"] - .02, s["r"] - .01, s["r"], s["r"] + .01, s["r"] + .02]
    gs = [.015, .02, .025, .03, .035]
    sens = [[dcf(s["rev"], m0, B["g1"], B["g10"], B["m"], W(r), nc, s["shares"], gt=g) for g in gs] for r in rs]
    rates = sorted(set(RATE_GRID + [s["r"]]))
    rate_table = [dict(r=r, wacc=W(r), fv=sum(PROBS[k] * dcf(s["rev"], m0, S2[k]["g1"], S2[k]["g10"], S2[k]["m"], W(r), nc, s["shares"]) for k in PROBS),
                       base=dcf(s["rev"], m0, B["g1"], B["g10"], B["m"], W(r), nc, s["shares"])) for r in rates]
    E_ = s["price"] * s["shares"]
    out["assets"][tk] = dict(
        rate_table=rate_table, r_reason=RR["stocks"][tk]["reason"],
        dcf_method=DCF_METHOD, wacc=dict(wacc=wacc_of(tk, s, s["r"]), discount_rate=w, cost_equity=s["r"], equity_weight=E_ / (E_ + f["debt"]), debt_weight=f["debt"] / (E_ + f["debt"]),
                  cost_debt=min(max(f["rd"], 0.02), 0.10), cost_debt_raw=f["rd"], tax=f["tax"], debt=f["debt"], after_tax_interest=aint),
        name=s["name"], type="stock", price=s["price"], shares=s["shares"], r=s["r"], mos=s["mos"],
        start_margin=m0, net_cash=nc, rev=s["rev"], notes=s["notes"],
        bear=res["bear"]["per_share"], base=base, bull=res["bull"]["per_share"],
        fair_value=fv, anchor=fv, buy_below=fv * (1 - s["mos"]), epv=epv,
        implied_irr=irr, reverse_g1=rg, tv_share=res["base"]["detail"]["tv_share"],
        sens=dict(r=rs, g=gs, grid=sens), detail={k: res[k]["detail"] for k in res}, scen=s["scen"], fcf=s["fcf"], sbc=s["sbc"],
    )

# ----------------------------------------------------------------- QQQ (look-through earnings model)
q = dict(price=728.95, r=req_return("QQQ"), mos=0.30)
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
qrates = sorted(set(RATE_GRID + [q["r"]]))
out["assets"]["QQQ"] = dict(
    rate_table=[dict(r=r, fv=sum(PROBS[k] * qqq(**qs[k], r=r) for k in PROBS), base=qqq(**qs["base"], r=r)) for r in qrates], r_reason=RR["stocks"]["QQQ"]["reason"],
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

json.dump(out, open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "results.json"), "w"), indent=1, default=float)

print(f"{'Tkr':6}{'Price':>9}{'Bear':>9}{'Base':>9}{'Bull':>9}{'FV(30/50/20)':>14}{'BuyBelow':>10}{'Diff%':>8}{'EPV':>8}{'IRR':>7}{'revG1':>7}{'TV%':>6}")
for tk, a in out["assets"].items():
    diff = (a["price"] / a["fair_value"] - 1) * 100
    print(f"{tk:6}{a['price']:9.2f}{a['bear']:9.1f}{a['base']:9.1f}{a['bull']:9.1f}{a['fair_value']:14.1f}{a['buy_below']:10.1f}{diff:8.1f}"
          f"{(a['epv'] or 0):8.1f}{(a['implied_irr'] or 0)*100:7.2f}{(a.get('reverse_g1') or 0)*100:7.1f}{(a.get('tv_share') or 0)*100:6.0f}")
print("start margins:", {k: round(v['start_margin'], 4) for k, v in out['assets'].items() if 'start_margin' in v})
