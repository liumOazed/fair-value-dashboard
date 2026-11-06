#!/usr/bin/env python3
"""Growth Quality Score: the scoring library shared by build_screen.py (S&P 500 + Nasdaq 100) and build_russell.py
(Russell 2000). Moved here unchanged from build_screen.py so both screens score stocks the same way; see build_screen.py
for the method. Importing this module only defines functions and reads config files; it writes nothing."""
import glob, json, re, pathlib, datetime
import numpy as np, pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
CYCLICAL = {"Energy", "Basic Materials"}
GT = 0.025
# Required returns come from data/required_returns.json (shared with the full model): stock > theme > sector > default.
RRF = json.load(open(ROOT / "data/required_returns.json"))
REQ_RETURN, DEFAULT_R = RRF["sectors"], RRF["default"]
def required_return(t, sector, themes_of):
    if t in RRF["stocks"]: return RRF["stocks"][t]["r"], "stock", RRF["stocks"][t]["reason"]
    if t in PEER_OF: return PEER[PEER_OF[t]]["required_return"], "peer group", f"{PEER_OF[t]}: " + PEER[PEER_OF[t]]["reason"]
    for th in themes_of:
        if th in RRF["themes"]: return RRF["themes"][th]["r"], "theme", f"{th}: " + RRF["themes"][th]["reason"]
    if sector in REQ_RETURN: return REQ_RETURN[sector], "sector", f"{sector} sector default"
    return DEFAULT_R, "default", "market default"
MIN_FCF_CONVERSION = 0.25      # FCF below 25% of net income (statement figures, same period) = FCF distorted by heavy capex (item 1)

def pct_in_sector(df, col, higher_better=True):
    s = df[col]
    key = "peer" if "peer" in df.columns else "sector"
    sec = df.groupby(key)[col].rank(pct=True)
    allr = s.rank(pct=True)
    n = df.groupby(key)[col].transform("count")
    out = np.where(n >= 8, sec, allr)            # small sectors fall back to the whole market
    out = pd.Series(out, index=df.index)
    if not higher_better: out = 1 - out
    return out.where(s.notna())

def score_v2(d):
    d = d.copy()
    d["g"] = d.rev_growth_pct.clip(-10, 60)
    d["roe_c"] = d.roe_pct.clip(-20, 60)
    d["fcf_c"] = d.fcf_yield_pct.clip(-10, 15)
    d["fpe_c"] = d.forward_pe.where((d.forward_pe > 0) & (d.forward_pe < 100))
    d["evx_c"] = d.ev_ebitda.where((d.ev_ebitda > 0) & (d.ev_ebitda < 100))
    comp = pd.DataFrame(index=d.index)
    comp["growth"] = pct_in_sector(d, "g")
    comp["profit"] = pd.concat([pct_in_sector(d, "profit_margin_pct"), pct_in_sector(d, "roe_c")], axis=1).mean(axis=1)
    comp["cash"] = pct_in_sector(d, "fcf_c")
    comp["value"] = pd.concat([pct_in_sector(d, "fpe_c", False), pct_in_sector(d, "evx_c", False)], axis=1).mean(axis=1)
    comp["quality"] = pct_in_sector(d, "gross_margin_pct")
    comp = comp.fillna(0.3)                       # missing data is not rewarded
    base_w = dict(growth=.30, profit=.25, cash=.20, value=.15, quality=.10)
    cyc_w = dict(growth=.15, profit=.25, cash=.35, value=.15, quality=.10)
    w = d.sector.map(lambda s: cyc_w if s in CYCLICAL else base_w)
    sc = sum(comp[k] * w.map(lambda x: x[k]) for k in base_w) * 100
    sc = sc - np.where(d.profit_margin_pct < 0, 10, 0) - np.where(d.pe_ratio.isna() & d.forward_pe.isna(), 5, 0)
    d["score"] = sc.clip(0, 100).round(1)
    d["flag_list"] = [[f for f, on in (("One-off growth?", g > 100), ("Loss-making", m < 0), ("Cyclical", s in CYCLICAL), ("Missing P/E", pd.isna(a) and pd.isna(b)))
                   if on] for g, m, s, a, b in zip(d.rev_growth_pct, d.profit_margin_pct, d.sector, d.pe_ratio, d.forward_pe)]
    return d

SCORE_VERSION = 4
V3_COLS = ["roic_pct", "net_debt_ebitda", "interest_coverage", "rev_cagr_pct", "rev_cagr_years", "eps_cagr_pct",
           "rev_growth_std", "earnings_cv", "fcf_cv", "fcf_neg_years", "fcf_years", "share_change_pct_yr",
           "fcf_conversion", "capex_ocf_pct", "capex_fcf", "total_debt", "interest_expense", "tax_rate",
           "roic_basis", "share_jump", "cost_of_debt", "industry", "beta", "volatility_1y_pct", "max_drawdown_1y_pct",
           "nd_ebitda_then", "margin_change_pts", "fcf_cagr_pct", "operating_margin_pct",
           "fcf_ni_3y", "fcf_ttm", "ni_ttm", "fcf_yield_yahoo_pct", "earnings_yield_pct", "earnings_yield_fwd_pct", "fcf_basis",
           "enterprise_value", "fcff_ev_pct"]

def score_v3(d):
    """Growth Quality Score v3, 0-100. Every metric is ranked inside the stock's own sector (as v2).
      Growth 25%        = current sales growth (capped 60%) 50% + 3-yr revenue CAGR (capped 40%) 30%
                          + consistency 20% (steady yearly revenue growth and steady earnings)
      Profitability 25% = ROIC 60% + ROE 20% (capped) + net margin 20%   (banks/insurers: ROE + margin only)
      Cash 20%          = FCF yield 60% + FCF stability 40% (low variability, fewer negative years)
      Valuation 15%     = forward P/E and EV/EBITDA (lower is better)
      Balance sheet 10% = net debt / EBITDA 60% (net cash best) + share count change 40% (buybacks best)
      Quality 5%        = gross margin
    Cyclical sectors (Energy, Basic Materials): growth 12%, cash 33%. Loss-making -10, no P/E -5.
    Missing metrics are not rewarded (component filled at the 30th percentile, as v2)."""
    d = d.copy()
    fin = (d.peer if "peer" in d.columns else d.sector) == "Financial Services"     # banks/insurers only (fee-based peers excluded)
    comp = pd.DataFrame(index=d.index)
    d["g"] = d.rev_growth_pct.clip(-10, 60)
    d["cagr_c"] = d.rev_cagr_pct.clip(-20, 40)
    d["rstd_c"] = d.rev_growth_std.clip(0, 60)
    d["ecv_c"] = d.earnings_cv.clip(0, 3)
    cons = pd.concat([pct_in_sector(d, "rstd_c", False), pct_in_sector(d, "ecv_c", False)], axis=1).mean(axis=1)
    g_parts = pd.concat([pct_in_sector(d, "g") * .5, pct_in_sector(d, "cagr_c") * .3, cons * .2], axis=1)
    comp["growth"] = g_parts.sum(axis=1, min_count=1) / pd.concat([pct_in_sector(d, "g").notna() * .5, pct_in_sector(d, "cagr_c").notna() * .3, cons.notna() * .2], axis=1).sum(axis=1).replace(0, np.nan)
    d["roic_c"] = d.roic_pct.clip(-20, 80).where(~fin)
    d["roe_c"] = d.roe_pct.clip(-20, 60)
    pr, pe_, pm = pct_in_sector(d, "roic_c"), pct_in_sector(d, "roe_c"), pct_in_sector(d, "profit_margin_pct")
    w_roic = pr.notna() * .6
    comp["profit"] = (pr.fillna(0) * .6 + pe_.fillna(0) * .2 + pm.fillna(0) * .2) / (w_roic + pe_.notna() * .2 + pm.notna() * .2).replace(0, np.nan)
    d["fcf_c"] = d.fcf_yield_pct.clip(-10, 15)
    d["fcv_c"] = d.fcf_cv.clip(0, 3)
    stab = pct_in_sector(d, "fcv_c", False) * (1 - (d.fcf_neg_years / d.fcf_years).fillna(0))
    stab = stab.where(d.fcf_neg_years.isna() | d.fcf_cv.notna(), (1 - d.fcf_neg_years / d.fcf_years) * .5)   # mean FCF <= 0: weak
    pf = pct_in_sector(d, "fcf_c")
    comp["cash"] = (pf.fillna(0) * .6 + stab.fillna(0) * .4) / (pf.notna() * .6 + stab.notna() * .4).replace(0, np.nan)
    d["fpe_c"] = d.forward_pe.where((d.forward_pe > 0) & (d.forward_pe < 100))
    d["evx_c"] = d.ev_ebitda.where((d.ev_ebitda > 0) & (d.ev_ebitda < 100))
    comp["value"] = pd.concat([pct_in_sector(d, "fpe_c", False), pct_in_sector(d, "evx_c", False)], axis=1).mean(axis=1)
    d["nde_c"] = d.net_debt_ebitda.clip(-5, 10).where(~fin)
    d["shr_c"] = d.share_change_pct_yr.clip(-10, 20)
    pn, ps_ = pct_in_sector(d, "nde_c", False), pct_in_sector(d, "shr_c", False)
    pn = pn.where(~fin, 0.5)                                         # leverage ratios don't apply to banks: neutral
    comp["balance"] = (pn.fillna(0) * .6 + ps_.fillna(0) * .4) / (pn.notna() * .6 + ps_.notna() * .4).replace(0, np.nan)
    comp["quality"] = pct_in_sector(d, "gross_margin_pct")
    comp = comp.fillna(0.3)
    base_w = dict(growth=.25, profit=.25, cash=.20, value=.15, balance=.10, quality=.05)
    cyc_w = dict(growth=.12, profit=.25, cash=.33, value=.15, balance=.10, quality=.05)
    w = d.sector.map(lambda s: cyc_w if s in CYCLICAL else base_w)
    sc = sum(comp[k] * w.map(lambda x: x[k]) for k in base_w) * 100
    sc = sc - np.where(d.profit_margin_pct < 0, 10, 0) - np.where(d.pe_ratio.isna() & d.forward_pe.isna(), 5, 0)
    d["score"] = sc.clip(0, 100).round(1)
    d["score_v2"] = score_v2(d)["score"]
    for k in base_w: d[f"c_{k}"] = (comp[k] * 100).round(0)
    flags = []
    for i, r in d.iterrows():
        f = [x for x, on in (("One-off growth?", r.rev_growth_pct > 100), ("Loss-making", r.profit_margin_pct < 0),
                             ("Cyclical", r.sector in CYCLICAL), ("Missing P/E", pd.isna(r.pe_ratio) and pd.isna(r.forward_pe)),
                             ("High debt", (not fin[i]) and r.net_debt_ebitda > 4),
                             ("Weak interest cover", (not fin[i]) and r.interest_coverage < 3 and (r.total_debt or 0) > 0),
                             ("Diluting", r.share_change_pct_yr > 3)) if on is True or on == True]
        flags.append(f)
    d["flag_list"] = flags
    return d

def wavg(parts):
    """Weighted average of (percentile Series, weight) pairs, re-normalised over the parts that exist per stock."""
    num = sum(p.fillna(0) * w for p, w in parts)
    den = sum(p.notna() * w for p, w in parts)
    return num / den.replace(0, np.nan)

# Risk thresholds: (net debt/EBITDA warning, serious), (interest cover warning, serious), negative-FCF test applies?
# Utilities and REITs are financed with more debt by design (regulated / property assets), so they get their own limits;
# utilities' negative FCF is normal (capex funded by borrowing against the rate base) and is not treated as a risk.
RISK_LIMITS = {"default": ((3, 4), (5, 3), True), "Utilities": ((6, 7), (2.5, 1.8), False), "Real Estate": ((6.5, 8), (2.5, 1.8), True)}

def risk_assessment(r, fin):
    """Warning / serious thresholds (sector-specific for Utilities and Real Estate; banks use dilution only)."""
    ser, warn = [], []
    nde, cov, neg, shr, debt = r.net_debt_ebitda, r.interest_coverage, r.fcf_neg_years, r.share_change_pct_yr, r.total_debt
    (nw, ns), (cw, cs), fcf_test = RISK_LIMITS.get(r.sector, RISK_LIMITS["default"])
    if not fin:
        if nde > ns: ser.append(f"Net debt {nde:.1f}x EBITDA (> {ns}x)")
        elif nde > nw: warn.append(f"Net debt {nde:.1f}x EBITDA (> {nw}x)")
        if (debt or 0) > 0 and cov < cs: ser.append(f"Interest cover {cov:.1f}x (< {cs}x)")
        elif (debt or 0) > 0 and cov < cw: warn.append(f"Interest cover {cov:.1f}x (< {cw}x)")
        if fcf_test and neg >= 2: ser.append(f"Negative FCF in {int(neg)} of {int(r.fcf_years)} years")
        elif fcf_test and neg == 1: warn.append(f"Negative FCF in 1 of {int(r.fcf_years)} years")
    if shr > 5: ser.append(f"Shares up {shr:.1f}% a year (> 5%)")
    elif shr > 3: warn.append(f"Shares up {shr:.1f}% a year (> 3%)")
    level = "High" if ser else ("Elevated" if warn else "Normal")
    return level, ser, warn

def score_v4(d):
    """Growth Quality Score v4 (0-100) = four parts, each a weighted average of within-sector percentiles:
      Business quality 30%    ROIC 35, net margin 20, gross margin 20, FCF / net income 15, ROE 10 (when meaningful)
      Growth & consistency 30% latest-quarter growth 25, 3-yr revenue CAGR 25, EPS CAGR 20,
                               revenue-growth volatility 15 (lower better), earnings variability 15 (lower better)
      Valuation 20%           forward P/E 30 (lower better), FCF yield 30, EV/EBITDA 25 (lower better), earnings yield 15
      Financial resilience 20% net debt/EBITDA 35, interest cover 25, FCF variability 15, negative-FCF years 15,
                               share-count change 10 (lower better)
    Cyclical sectors: growth 15, quality 35, valuation 25, resilience 25. A part with no data is filled at the
    30th percentile (missing data is not rewarded). No blanket penalties; a distress cap of 50 applies when free
    cash flow was negative in 2+ years AND interest cover is under 3x.
    Financial Safety = the resilience part on its own. Risk level = High / Elevated / Normal from thresholds."""
    d = d.copy()
    fin = (d.peer if "peer" in d.columns else d.sector) == "Financial Services"     # banks/insurers only (fee-based peers excluded)
    P = lambda col, hb=True: pct_in_sector(d, col, hb)
    d["roic_c"] = d.roic_pct.clip(-20, 80).where(~fin)
    d["roe_c"] = d.roe_pct.where((d.roe_pct > -50) & (d.roe_pct < 100))           # negative/huge equity: not meaningful
    # cash conversion: 3-year cumulative FCF / net income when the CSV has it (Nov-2026 on), else the latest fiscal year
    d["fni_c"] = (d.fcf_ni_3y.fillna(d.fcf_conversion) if "fcf_ni_3y" in d.columns else d.fcf_conversion).clip(0, 1.5)
    d["g"] = d.rev_growth_pct.clip(-10, 60)
    d["cagr_c"] = d.rev_cagr_pct.clip(-20, 40)
    d["eps_c"] = d.eps_cagr_pct.clip(-30, 60)
    d["rstd_c"] = d.rev_growth_std.clip(0, 60)
    d["ecv_c"] = d.earnings_cv.clip(0, 3)
    d["fpe_c"] = d.forward_pe.where((d.forward_pe > 0) & (d.forward_pe < 100))
    d["evx_c"] = d.ev_ebitda.where((d.ev_ebitda > 0) & (d.ev_ebitda < 100))
    d["fcf_c"] = d.fcf_yield_pct.clip(-10, 15)
    pe_y = d.forward_pe.where(d.forward_pe > 0).fillna(d.pe_ratio.where(d.pe_ratio > 0))
    d["ey_c"] = (100 / pe_y).clip(0, 20)
    if "earnings_yield_pct" in d.columns and d.earnings_yield_pct.notna().sum() > 100:
        # from Nov-2026: TRAILING earnings yield, so it adds information instead of repeating the forward P/E (30%)
        d["ey_c"] = d.earnings_yield_pct.clip(-20, 20)
    d["nde_c"] = d.net_debt_ebitda.clip(-5, 10).where(~fin)
    d["cov_c"] = d.interest_coverage.clip(0, 50).where(~fin)
    d["fcv_c"] = d.fcf_cv.clip(0, 3).where(~fin)
    d["neg_c"] = (d.fcf_neg_years / d.fcf_years).where(~fin)
    d["shr_c"] = d.share_change_pct_yr.clip(-10, 20)
    comp = pd.DataFrame(index=d.index)
    comp["quality"] = wavg([(P("roic_c"), .35), (P("profit_margin_pct"), .20), (P("gross_margin_pct"), .20), (P("fni_c"), .15), (P("roe_c"), .10)])
    comp["growth"] = wavg([(P("g"), .25), (P("cagr_c"), .25), (P("eps_c"), .20), (P("rstd_c", False), .15), (P("ecv_c", False), .15)])
    comp["value"] = wavg([(P("fpe_c", False), .30), (P("fcf_c"), .30), (P("evx_c", False), .25), (P("ey_c"), .15)])
    neutral = pd.Series(np.where(fin, 0.5, np.nan), index=d.index)                 # leverage/FCF tests don't fit banks
    comp["resilience"] = wavg([(P("nde_c", False).fillna(neutral), .35), (P("cov_c").fillna(neutral), .25), (P("fcv_c", False).fillna(neutral), .15),
                               (P("neg_c", False).fillna(neutral), .15), (P("shr_c", False), .10)])
    comp = comp.fillna(0.3)
    base_w = dict(quality=.30, growth=.30, value=.20, resilience=.20)
    cyc_w = dict(quality=.35, growth=.15, value=.25, resilience=.25)
    w = d.sector.map(lambda s: cyc_w if s in CYCLICAL else base_w)
    sc = sum(comp[k] * w.map(lambda x: x[k]) for k in base_w) * 100
    cov_serious = d.sector.map(lambda x: RISK_LIMITS.get(x, RISK_LIMITS["default"])[1][1])
    distress = (d.fcf_neg_years >= 2) & (d.interest_coverage < cov_serious) & ~fin & (d.sector != "Utilities")
    d["distress_cap"] = distress
    d["score"] = np.where(distress, np.minimum(sc, 50), sc).clip(0, 100).round(1)
    for k in base_w: d[f"c_{k}"] = (comp[k] * 100).round(0)
    d["safety"] = (comp["resilience"] * 100).round(0)
    prev = score_v3(d.drop(columns=["score"]))
    d["score_v3"] = prev["score"]
    risk = [risk_assessment(r, fin[i]) for i, r in d.iterrows()]
    d["risk_level"] = [x[0] for x in risk]; d["risk_serious"] = [x[1] for x in risk]; d["risk_warn"] = [x[2] for x in risk]
    key = ["roic_pct", "net_debt_ebitda", "interest_coverage", "rev_cagr_pct", "fcf_cv", "share_change_pct_yr", "forward_pe", "fcf_yield_pct"]
    conf = []
    for i, r in d.iterrows():
        need = [k for k in key if not (fin[i] and k in ("roic_pct", "net_debt_ebitda", "interest_coverage", "fcf_cv"))]
        miss = sum(pd.isna(r[k]) for k in need)
        borrowed = r.get("v3_source", "own") != "own"
        conf.append("Low" if miss >= 3 else ("Medium" if miss >= 1 or borrowed or r.get("roic_basis") == "debt+equity" else "High"))
    d["data_confidence"] = conf
    d["flag_list"] = prev["flag_list"]
    return d

def v3_source():
    """Newest full-universe screener run in data/screens/extra/ (used as a proxy for months whose CSV predates v3)."""
    best = None
    for f in sorted(glob.glob(str(ROOT / "data/screens/extra/*_full.csv"))):   # full runs only (supplements never change scores)
        try:
            x = pd.read_csv(f)
        except Exception:
            continue
        if len(x) >= 300 and "roic_pct" in x.columns and x.roic_pct.notna().sum() > 200:
            best = f
    return best
V3_SRC = v3_source()
PG_FILE = ROOT / "data/peer_groups.json"
PEER = json.load(open(PG_FILE)) if PG_FILE.exists() else {}
PEER = {k: v for k, v in PEER.items() if not k.startswith("_")}
PEER_OF = {t: g for g, v in PEER.items() for t in v["tickers"]}
_V3 = pd.read_csv(V3_SRC).drop_duplicates("ticker").set_index("ticker").reindex(columns=V3_COLS) if V3_SRC else None

def implied_growth(y_pct, R):
    if y_pct is None or pd.isna(y_pct) or y_pct <= 0: return None
    y = y_pct / 100
    def f(g):
        s = sum(((1 + g) / (1 + R)) ** t for t in range(1, 11))
        tv = (1 + g) ** 10 * (1 + GT) / ((R - GT) * (1 + R) ** 10)
        return y * (s + tv) - 1
    lo, hi = -0.3, 0.8
    if f(hi) < 0: return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if f(mid) < 0: lo = mid
        else: hi = mid
    return round((lo + hi) / 2, 4)


def wacc_of(r, rr):
    """WACC = equity share x required return + debt share x after-tax cost of debt (interest / debt, clipped 2-10%).
    r is one CSV row; returns (wacc, debt, equity, raw cost of debt, cost of debt used, tax rate)."""
    D = float(r.total_debt) if not pd.isna(r.total_debt) else 0.0
    E = float(r.market_cap) if not pd.isna(r.market_cap) else np.nan
    rd_raw = (float(r.cost_of_debt) if not pd.isna(r.cost_of_debt) else                 # interest / average annual debt
              (r.interest_expense / D) if (D > 0 and not pd.isna(r.interest_expense)) else None)
    rd = 0.05 if rd_raw is None else min(max(rd_raw, 0.02), 0.10)   # guardrail; raw rate is reported, never hidden
    tx = r.tax_rate if not pd.isna(r.tax_rate) else 0.21
    wacc = None if pd.isna(E) or E <= 0 else (E * rr + D * rd * (1 - tx)) / (E + D)
    return wacc, D, E, rd_raw, rd, tx

# ---- Quick answers: five plain questions per stock (moved unchanged from build_screen.py so the Russell 2000 screen
# can answer them too). r is a row dict with the screen's display fields.
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
