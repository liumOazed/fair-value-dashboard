#!/usr/bin/env python3
"""Build data/screen.json from the monthly screen CSVs in data/screens/.

Score v3 (2026-10) adds ROIC, balance sheet, growth consistency, FCF stability and dilution (see score_v3 below).
Score v2 ("Growth Quality Score") fixed the problems in the original growth_score:
  * every metric is ranked inside the stock's own sector (energy is compared with energy)
  * growth is counted once (no Rule of 40 double count) and capped at 60 so one-offs cannot dominate
  * cyclical sectors (Energy, Basic Materials) lean less on growth and more on cash generation
  * negative margins and missing valuation data are penalised
  * a 'consistent' badge marks stocks in the top 50 in BOTH of the latest two months
Quick indicator ("growth priced in"): the 10-year cash-flow growth the current price already assumes, using a sector
required return (see REQ_RETURN) and 2.5% terminal growth. If free cash flow is distorted by heavy capex (FCF yield under
25% of earnings yield) the earnings yield is used instead and the row is labelled FCF distorted (financial companies always use earnings). No verdict when sales are
shrinking. Indicative only, not a fair value.
Usage: python scripts/build_screen.py
"""
import glob, json, re, pathlib, datetime
import numpy as np, pandas as pd
import sys; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from screen_score import *            # scoring functions and config (moved out unchanged so build_russell.py can share them)
from screen_score import _V3

def month_of(p): return re.search(r"(\d{4}-\d{2})", p).group(1)
CACHE = ROOT / "data/cache"
def load_month(f):
    """Score one month, reusing data/cache/scores_YYYY-MM.json when the CSV has not changed (scores are relative
    within a month, so a month's result never changes unless its own CSV changes)."""
    import hashlib
    h = hashlib.sha1(open(f, "rb").read() + f"v{SCORE_VERSION}|{V3_SRC}|{json.dumps(PEER, sort_keys=True)}".encode()).hexdigest()[:12]   # CSV + score version + proxy source
    cf = CACHE / f"scores_{month_of(f)}.json"
    if cf.exists():
        c = json.load(open(cf))
        if c.get("csv_hash") == h:
            d = pd.DataFrame(c["rows"]).set_index("ticker", drop=False)
            for col in V3_COLS:                                   # older cache files may predate a column
                if col not in d.columns: d[col] = np.nan
            d.attrs["cached"] = True; return d
    d = pd.read_csv(f).drop_duplicates("ticker").set_index("ticker", drop=False)
    has_v3 = "roic_pct" in d.columns and d.roic_pct.notna().sum() > 0.4 * len(d)
    if not has_v3 and _V3 is not None:                       # older CSV: borrow multi-year metrics from the newest full run
        d = d.drop(columns=[c for c in V3_COLS if c in d.columns]).join(_V3, how="left")
    for c in V3_COLS:
        if c not in d.columns: d[c] = np.nan
    d["peer"] = [PEER_OF.get(t, sec) for t, sec in zip(d.index, d.sector)]
    d["v3_source"] = "own" if has_v3 else (pathlib.Path(V3_SRC).name if V3_SRC else "none")
    d = score_v4(d); d["rank"] = d.score.rank(ascending=False, method="min").astype(int)
    CACHE.mkdir(exist_ok=True)
    keep = d.drop(columns=[c for c in d.columns if c.endswith("_c") or c == "g"])
    json.dump(dict(csv=pathlib.Path(f).name, csv_hash=h, rows=json.loads(keep.to_json(orient="records"))), open(cf, "w"))
    d.attrs["cached"] = False; return d

allf = glob.glob(str(ROOT / "data/screens/*.csv"))
by_month = {}
for f in sorted(allf, key=lambda p: ("_estimated" not in p)):     # real files sort last, so they overwrite estimates
    by_month[month_of(f)] = f
months = sorted(by_month)
if not months: raise SystemExit("No CSVs in data/screens/")
estimated = {m for m in months if "_estimated" in by_month[m]}
frames = {m: load_month(by_month[m]) for m in months}
print("months:", [m + ("*" if m in estimated else "") for m in months], "cache hits:", [m for m in months if frames[m].attrs.get("cached")])
cur_m = months[-1]
if cur_m in estimated: raise SystemExit("Latest month is an estimate; add the real CSV")
real_before = [m for m in months[:-1] if m not in estimated]
prev_m = real_before[-1] if real_before else None                 # rank change is measured against the last REAL month
cur = frames[cur_m]; prev = frames[prev_m] if prev_m else None
WINDOW = months[-4:]                                               # consistency window: latest 4 months (estimates included)
top_sets = {m: set(frames[m].nsmallest(50, "rank").index) for m in WINDOW}
NEED = 3 if len(WINDOW) >= 4 else len(WINDOW)
themes = {k: v for k, v in json.load(open(ROOT / "data/themes.json")).items() if not k.startswith("_")}
_dj = ROOT / "data/universe/djia.json"
DJIA = json.load(open(_dj))["members"] if _dj.exists() else []      # Dow members: ranked among themselves for the "Dow top 10" filter
t_of = {}
for th, tk in themes.items():
    for t in tk: t_of.setdefault(t, []).append(th)
fv = {a["ticker"] for a in json.load(open(ROOT / "data/assets.json"))["assets"]}
top_cur = top_sets[cur_m]
def num(x): return None if pd.isna(x) else round(float(x), 2)
# Market P/E = index-style aggregate: total market value / total earnings of the stocks with positive earnings.
_t = cur[cur.pe_ratio > 0]; _f = cur[cur.forward_pe > 0]
MKT_PE = float(_t.market_cap.sum() / (_t.market_cap / _t.pe_ratio).sum())
MKT_FPE = float(_f.market_cap.sum() / (_f.market_cap / _f.forward_pe).sum())
def vs_mkt(x, m): return None if (x is None or pd.isna(x) or x <= 0) else round(float(x) / m - 1, 4)
_ind = cur[cur.industry.fillna("").astype(str) != ""]
ind_rank = _ind.groupby("industry").score.rank(ascending=False, method="min").astype(int).to_dict()
ind_n = _ind.groupby("industry").size().to_dict()
rows = []
for t, r in cur.iterrows():
    rr, rr_src, rr_why = required_return(t, r.sector, t_of.get(t, []))
    # WACC = equity share x required return + debt share x after-tax cost of debt (interest / debt, clipped 2-10%)
    D = float(r.total_debt) if not pd.isna(r.total_debt) else 0.0
    E = float(r.market_cap) if not pd.isna(r.market_cap) else np.nan
    rd_raw = (float(r.cost_of_debt) if not pd.isna(r.cost_of_debt) else                 # interest / average annual debt
              (r.interest_expense / D) if (D > 0 and not pd.isna(r.interest_expense)) else None)
    rd = 0.05 if rd_raw is None else min(max(rd_raw, 0.02), 0.10)   # guardrail; raw rate is reported, never hidden
    tx = r.tax_rate if not pd.isna(r.tax_rate) else 0.21
    wacc = None if pd.isna(E) or E <= 0 else (E * rr + D * rd * (1 - tx)) / (E + D)
    spread = None if (wacc is None or pd.isna(r.roic_pct) or r.peer == "Financial Services") else round(r.roic_pct / 100 - wacc, 4)
    flags_out = list(r["flag_list"]) + (["Below WACC"] if spread is not None and spread < 0 else [])
    # earnings yield = TRAILING earnings / price (same period as the trailing FCF yield); forward shown separately
    ey_t = r.get("earnings_yield_pct")
    ey = (float(ey_t) if not pd.isna(ey_t) else None) if ey_t is not None else None
    if ey is None and not pd.isna(r.pe_ratio) and r.pe_ratio > 0: ey = 100 / r.pe_ratio
    ey_f = r.get("earnings_yield_fwd_pct")
    ey_fwd = float(ey_f) if ey_f is not None and not pd.isna(ey_f) else (100 / r.forward_pe if not pd.isna(r.forward_pe) and r.forward_pe > 0 else None)
    # one cash-conversion figure: statement FCF / statement net income, 3-year cumulative (latest year if not available)
    c3, c1 = r.get("fcf_ni_3y"), r.fcf_conversion
    c3 = None if c3 is None or pd.isna(c3) else float(c3); c1 = None if pd.isna(c1) else float(c1)
    conv = c3 if c3 is not None else c1
    swing = c3 is not None and c1 is not None and c3 > 0 and abs(c1 / c3 - 1) > 0.30      # latest year far from the 3-year norm
    if swing: flags_out.append("Cash swing")
    capex_heavy = ey is not None and (r.peer == "Financial Services" or pd.isna(r.fcf_yield_pct) or r.fcf_yield_pct <= 0 or (conv is not None and conv < MIN_FCF_CONVERSION))   # banks/insurers: FCF is not meaningful
    basis = "earnings" if capex_heavy else "fcf"
    ig = implied_growth(ey if capex_heavy else r.fcf_yield_pct, rr)
    g = r.rev_growth_pct
    ref = (min(max(g, 3), 30) / 100) if (not pd.isna(g) and g > 0) else None   # item 4: no verdict when sales shrink
    tag = None
    if ig is not None:
        if capex_heavy: tag = "FCF distorted"
        elif ref is None: tag = "Sales shrinking"
        else: tag = "Demanding" if ig > ref * 1.25 else ("Undemanding" if ig < ref * 0.75 else "In line")
    p = prev.loc[t] if (prev is not None and t in prev.index) else None
    rows.append(dict(ticker=t, name=r["name"], sector=r.sector, themes=t_of.get(t, []), score=float(r.score), rank=int(r["rank"]),
        prev_score=None if p is None else float(p.score), prev_rank=None if p is None else int(p["rank"]),
        rank_change=None if p is None else int(p["rank"]) - int(r["rank"]),
        old_score=float(r.growth_score), consistent=(t in top_cur and sum(t in top_sets[m] for m in WINDOW) >= NEED), months_in_top50=sum(t in top_sets[m] for m in WINDOW), top50=t in top_cur,
        history=[dict(m=m, rank=int(frames[m].loc[t, 'rank']), score=float(frames[m].loc[t, 'score']), est=m in estimated) if t in frames[m].index else dict(m=m, rank=None, score=None, est=m in estimated) for m in months], flags=flags_out,
        rev_growth_pct=num(r.rev_growth_pct), gross_margin_pct=num(r.gross_margin_pct), profit_margin_pct=num(r.profit_margin_pct),
        roe_pct=num(r.roe_pct), pe=num(r.pe_ratio), forward_pe=num(r.forward_pe), ev_ebitda=num(r.ev_ebitda), ps=num(r.ps_ratio),
        fcf_yield_pct=num(r.fcf_yield_pct), market_cap=num(r.market_cap), implied_fcf_growth=ig, implied_tag=tag, implied_basis=basis, required_return=rr, required_return_source=rr_src, required_return_reason=rr_why, fcf_ni=None if conv is None else round(conv, 2), fcf_ni_basis=("3y" if c3 is not None else ("latest FY" if c1 is not None else None)), cash_swing=bool(swing),
        earnings_yield=None if ey is None else round(ey, 2), earnings_yield_fwd=None if ey_fwd is None else round(ey_fwd, 2),
        fcf_basis=(r.get("fcf_basis") if isinstance(r.get("fcf_basis"), str) else "Yahoo"),
        **{c: num(r[c]) for c in V3_COLS if c not in ("total_debt", "interest_expense", "fcf_conversion", "roic_basis", "share_jump", "cost_of_debt", "industry", "fcf_basis", "earnings_yield_pct", "earnings_yield_fwd_pct")}, fcf_ni_conversion=num(r["fcf_conversion"]),
        roic_basis=(r["roic_basis"] if isinstance(r["roic_basis"], str) else None), share_jump=bool(r["share_jump"]) if not pd.isna(r["share_jump"]) else False,
        wacc_detail=None if wacc is None else dict(equity_weight=round(E / (E + D), 3), debt_weight=round(D / (E + D), 3), cost_equity=rr,
            cost_debt_raw=None if rd_raw is None else round(float(rd_raw), 4), cost_debt_used=round(rd, 4), tax=round(float(tx), 3)), wacc=None if wacc is None else round(wacc, 4), roic_spread=spread,
        v3_source=r.v3_source, score_prev=float(r.score_v3), components={k: float(r[f"c_{k}"]) for k in ("quality", "growth", "value", "resilience")},
        safety=float(r.safety), risk_level=r.risk_level, risk_serious=list(r.risk_serious), risk_warn=list(r.risk_warn), data_confidence=r.data_confidence,
        distress_cap=bool(r.distress_cap), industry=(r.industry if isinstance(r.industry, str) and r.industry else None),
        industry_rank=ind_rank.get(t), industry_n=ind_n.get(r.industry) if isinstance(r.industry, str) else None, pe_vs_market=vs_mkt(r.pe_ratio, MKT_PE), fpe_vs_market=vs_mkt(r.forward_pe, MKT_FPE), peer_group=PEER_OF.get(t), has_fair_value=t in fv))
rows.sort(key=lambda x: x["rank"])
# ---- Quick answers: five plain questions per stock, answered from the metrics above ----
def _p(x, d=1): return f"{x:+.{d}f}" if x is not None else "n/a"
def quick_answers(r):
    bank = r["sector"] == "Financial Services" and not r.get("peer_group")
    util = r["sector"] == "Utilities"
    A = []
    # 1. Is revenue growing?
    g, c, n, sd = r["rev_growth_pct"], r["rev_cagr_pct"], r.get("rev_cagr_years"), r["rev_growth_std"]
    if g is None and c is None: v, t = "na", "No revenue data."
    else:
        v = ("yes" if (g or 0) > 5 and (c is None or c > 5) else "no" if (g is None or g <= 0) and (c is None or c <= 0) else "partly")
        t = f"Latest quarter {_p(g)}% year on year" + (f"; {_p(c)}% a year over {int(n or 3)} years" if c is not None else "")
        if sd is not None: t += ", steady" if sd < 5 else (f", uneven (±{sd:.0f} pts a year)" if sd > 15 else "")
        if g is not None and c is not None and g > 100: t += ". The jump looks one-off (acquisition or cycle)"
        elif g is not None and c is not None and g > c + 30:
            v = "partly"; t += ". Far above its own 3-year trend, so likely an acquisition or one-off"
        elif g is not None and c is not None and g > 5 and c <= 0: t += ". Recent pick-up after a flat or shrinking period"
        elif g is not None and c is not None and g <= 0 < c: t += ". Growth has stalled recently"
    A.append(dict(q="Is revenue growing?", v=v, t=t + "."))
    # 2. Are profits healthy?
    nm, roic, sp, eps, roe = r["profit_margin_pct"], r["roic_pct"], r["roic_spread"], r["eps_cagr_pct"], r["roe_pct"]
    if nm is None: v, t = "na", "No profit data."
    elif bank:
        v = "no" if nm < 0 else ("yes" if (roe or 0) >= 12 and nm >= 10 else "partly")
        t = f"Net margin {nm:.1f}%, return on equity {roe:.1f}%" if roe is not None else f"Net margin {nm:.1f}%"
    else:
        v = "no" if nm < 0 or (sp is not None and sp < -0.03 and nm < 5) else ("yes" if nm >= 10 and (sp is None or sp >= 0) and (eps is None or eps >= 0) else "partly")
        t = f"Net margin {nm:.1f}%" + (f", ROIC {roic:.0f}% vs {r['wacc']*100:.1f}% cost of capital ({_p(sp*100)} pts)" if sp is not None else "")
        if eps is not None: t += f", EPS {_p(eps)}% a year"
        if nm < 0: t += ". Loss-making"
        elif sp is not None and sp < 0: t += ". Earns less than its cost of capital"
    A.append(dict(q="Are profits healthy?", v=v, t=t + "."))
    # 3. Is cash flow strong?
    neg, yrs, conv, fy, cv = r["fcf_neg_years"], r["fcf_years"], r["fcf_ni"], r["fcf_yield_pct"], r["fcf_cv"]
    if bank: v, t = "na", "Free cash flow isn't a meaningful test for banks and insurers"
    elif yrs is None and fy is None: v, t = "na", "No cash-flow data"
    else:
        if util and (neg or 0) >= 1: v = "partly"
        elif (neg or 0) >= 2 or (fy is not None and fy <= 0): v = "no"
        elif (neg or 0) == 0 and (conv is None or conv >= 0.8) and (cv is None or cv <= 0.5) and (fy or 0) > 0: v = "yes"
        else: v = "partly"
        t = (f"FCF positive in {int(yrs - neg)} of {int(yrs)} years" if yrs else "FCF history n/a") + (f", {conv:.2f}x net income" + (" over 3 years" if r.get("fcf_ni_basis") == "3y" else "") if conv is not None else "") + (f", FCF yield {fy:.1f}%" if fy is not None else "")
        if cv is not None and cv > 0.5: t += ", uneven from year to year"
        if util and (neg or 0) >= 1: t += ". Negative FCF is normal for utilities (capex funded by borrowing)"
    A.append(dict(q="Is cash flow strong?", v=v, t=t + "."))
    # 4. Is debt manageable?
    nde, cov = r["net_debt_ebitda"], r["interest_coverage"]
    ser = [x for x in r["risk_serious"] if x.startswith(("Net debt", "Interest"))]; war = [x for x in r["risk_warn"] if x.startswith(("Net debt", "Interest"))]
    if bank: v, t = "na", "Leverage ratios don't apply to banks and insurers"
    elif nde is None: v, t = "partly", "EBITDA is negative or missing, so leverage can't be judged"
    else:
        v = "no" if ser else ("partly" if war else "yes")
        t = ("Net cash" if nde < 0 else f"Net debt {nde:.1f}x EBITDA") + (", no meaningful interest" if cov is not None and cov >= 999 else f", interest covered {cov:.1f}x" if cov is not None else "")
        lim = lambda x: x.split(" (")[0].split(" ")[0].lower() + (" debt" if x.startswith("Net") else " cover") + " " + x.split("(")[1].rstrip(")")
        if ser: t += ". Over the serious limit: " + ", ".join(lim(x) for x in ser)
        if war: t += (", " if ser else ". ") + "over the warning limit: " + ", ".join(lim(x) for x in war)
        if util or r["sector"] == "Real Estate": t += f" ({r['sector']} limits are higher by design)"
    A.append(dict(q="Is debt manageable?", v=v, t=t + "."))
    # 5. Is the financial position improving?
    up, down = [], []
    then = r.get("nd_ebitda_then")
    if not bank and then is not None and nde is not None:
        if nde < then - 0.3: up.append(f"leverage down ({then:.1f}x → {nde:.1f}x)")
        elif nde > then + 0.3: down.append(f"leverage up ({then:.1f}x → {nde:.1f}x)")
    mc = r.get("margin_change_pts")
    if mc is not None:
        if mc > 1: up.append(f"net margin {_p(mc)} pts")
        elif mc < -1: down.append(f"net margin {_p(mc)} pts")
    fc = r.get("fcf_cagr_pct")
    if not bank and fc is not None:
        if fc > 5: up.append(f"FCF growing {fc:.0f}% a year")
        elif fc < -5: down.append(f"FCF shrinking {abs(fc):.0f}% a year")
    sc = r["share_change_pct_yr"]
    if sc is not None:
        if sc < -0.5: up.append(f"share count falling {abs(sc):.1f}% a year")
        elif sc > 2: down.append(f"share count rising {sc:.1f}% a year")
    if g is not None and c is not None and g < 100:
        if g > c + 5: up.append("growth accelerating")
        elif g < c - 5: down.append("growth slowing")
    if len(up) + len(down) < 2: v, t = "na", "Not enough history to judge the trend"
    else:
        net = len(up) - len(down)
        v = "yes" if net >= 2 else ("no" if net <= -2 else "partly")
        t = ("Better: " + ", ".join(up) if up else "") + (". " if up and down else "") + ("Worse: " + ", ".join(down) if down else "")
    A.append(dict(q="Is the financial position improving?", v=v, t=t + "."))
    return A

for r in rows:
    r["answers"] = quick_answers(r)
    r["checks_score"] = sum(a["v"] == "yes" for a in r["answers"]) - sum(a["v"] == "no" for a in r["answers"])

# ---- Resilient compounders: 5 extra stocks outside the top 50, picked on absolute safety + business quality ----
RES_RULES = dict(min_cap=10e9, max_nde=1.0, min_cov=10, max_neg_fcf=0, max_fcf_cv=0.5, max_share_chg=0.5, min_quality=60, min_cagr=3.0, n=5)
def res_ok(r):
    R = RES_RULES
    if r["top50"] or (r["market_cap"] or 0) < R["min_cap"] or r["risk_level"] != "Normal": return False
    if r.get("peer_group") is None and r["sector"] == "Financial Services": return False      # banks/insurers: tests don't apply
    nde, cov = r["net_debt_ebitda"], r["interest_coverage"]
    return (nde is not None and nde <= R["max_nde"] and (cov is None or cov >= R["min_cov"]) and r["fcf_neg_years"] == 0
            and r["fcf_cv"] is not None and r["fcf_cv"] <= R["max_fcf_cv"] and r["share_change_pct_yr"] is not None
            and r["share_change_pct_yr"] <= R["max_share_chg"] and r["components"]["quality"] >= R["min_quality"]
            and r["rev_cagr_pct"] is not None and r["rev_cagr_pct"] >= R["min_cagr"])
passed = sorted([r for r in rows if res_ok(r)], key=lambda r: (-r["components"]["quality"], -r["score"]))
picks, seen = [], set()
for r in passed:                                             # one pick per company (GOOG / GOOGL)
    if r["name"] in seen: continue
    seen.add(r["name"]); picks.append(r)
    if len(picks) == RES_RULES["n"]: break
for i, r in enumerate(rows):
    r["resilient_pick"] = r in picks
    r["resilient_rank"] = picks.index(r) + 1 if r in picks else None
RESILIENT = dict(rules=RES_RULES, passed=len(passed), picks=[r["ticker"] for r in picks])
print("resilient compounders:", RESILIENT["picks"], f"({len(passed)} passed)")

# ---- Passes all 5 checks: every stock answering "yes" to all five quick questions (revenue growing, profits healthy,
# cash flow strong, debt manageable, position improving). Those not already in the top 50 or the resilient picks are
# added to the default list as well, so good businesses held back by valuation or a tough peer group are not missed.
for r in rows:
    r["all_checks"] = bool(r["answers"]) and all(a["v"] == "yes" for a in r["answers"])
    r["checks_pick"] = r["all_checks"] and not r["top50"] and not r["resilient_pick"]
ALLCHECKS = dict(rule="yes to all 5 quick questions", passed=sum(r["all_checks"] for r in rows),
                 picks=[r["ticker"] for r in sorted((r for r in rows if r["checks_pick"]), key=lambda r: -r["score"])])
print("all 5 checks:", ALLCHECKS["passed"], "passed;", len(ALLCHECKS["picks"]), "added:", ALLCHECKS["picks"])

# ---- FCF / EV (display only, not scored): from the month's CSV, else the newest supplementary scan
_sup = sorted(glob.glob(str(ROOT / "data/screens/extra/fcfev_*.csv")))
SUP = pd.read_csv(_sup[-1]).drop_duplicates("ticker").set_index("ticker")["fcff_ev_pct"].to_dict() if _sup else {}
for r in rows:
    if r.get("fcff_ev_pct") is None and SUP.get(r["ticker"]) == SUP.get(r["ticker"]):
        r["fcff_ev_pct"] = num(SUP.get(r["ticker"]))
        r["fcff_ev_src"] = pathlib.Path(_sup[-1]).name if r["fcff_ev_pct"] is not None else None
    if r["sector"] == "Financial Services" and not r.get("peer_group"):
        r["fcff_ev_pct"] = None                                    # banks / insurers: enterprise value is not meaningful
_djr = sorted((r for r in rows if r["ticker"] in DJIA), key=lambda r: -r["score"])
for i, r in enumerate(_djr, 1):
    r["djia_rank"] = i                                            # rank among the 30 Dow stocks by Growth Quality Score
out = dict(resilient=RESILIENT, all_checks=ALLCHECKS, peer_groups={k: dict(reason=v["reason"], tickers=v["tickers"]) for k, v in PEER.items()}, score_version=SCORE_VERSION, v3_source=(pathlib.Path(V3_SRC).name if V3_SRC else None), market=dict(pe=round(MKT_PE, 1), forward_pe=round(MKT_FPE, 1), n=int(len(_t)), method="total market value / total earnings of screened stocks with positive earnings"), month=cur_m, prev_month=prev_m, months=months, estimated_months=sorted(estimated), window=WINDOW, consistent_rule=f"in the top 50 in at least {NEED} of the last {len(WINDOW)} months, including the latest", built=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"), universe=len(rows), djia=dict(as_of=json.load(open(_dj))["as_of"] if _dj.exists() else None, n=len(_djr), missing=[t for t in DJIA if t not in {r["ticker"] for r in _djr}]),
           sectors=sorted(cur.sector.dropna().unique().tolist()), themes=list(themes), rows=rows)
json.dump(out, open(ROOT / "data/screen.json", "w"), indent=0)
print("built", cur_m, "vs", prev_m, "rows", len(rows), "consistent", sum(r["consistent"] for r in rows))
print("TOP 15:", [(r["ticker"], r["score"]) for r in rows[:15]])
import collections
print("top50 sectors:", dict(collections.Counter(r["sector"] for r in rows[:50])))
