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

ROOT = pathlib.Path(__file__).resolve().parent.parent
CYCLICAL = {"Energy", "Basic Materials"}
GT = 0.025
# Required returns come from data/required_returns.json (shared with the full model): stock > theme > sector > default.
RRF = json.load(open(ROOT / "data/required_returns.json"))
REQ_RETURN, DEFAULT_R = RRF["sectors"], RRF["default"]
def required_return(t, sector, themes_of):
    if t in RRF["stocks"]: return RRF["stocks"][t]["r"], "stock", RRF["stocks"][t]["reason"]
    for th in themes_of:
        if th in RRF["themes"]: return RRF["themes"][th]["r"], "theme", f"{th}: " + RRF["themes"][th]["reason"]
    if sector in REQ_RETURN: return REQ_RETURN[sector], "sector", f"{sector} sector default"
    return DEFAULT_R, "default", "market default"
MIN_FCF_CONVERSION = 0.25      # FCF yield below 25% of earnings yield = FCF distorted by heavy capex (item 1)

def pct_in_sector(df, col, higher_better=True):
    s = df[col]
    sec = df.groupby("sector")[col].rank(pct=True)
    allr = s.rank(pct=True)
    n = df.groupby("sector")[col].transform("count")
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

SCORE_VERSION = 3
V3_COLS = ["roic_pct", "net_debt_ebitda", "interest_coverage", "rev_cagr_pct", "rev_cagr_years", "eps_cagr_pct",
           "rev_growth_std", "earnings_cv", "fcf_cv", "fcf_neg_years", "fcf_years", "share_change_pct_yr",
           "fcf_conversion", "capex_ocf_pct", "capex_fcf", "total_debt", "interest_expense", "tax_rate",
           "roic_basis", "share_jump"]

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
    fin = d.sector == "Financial Services"
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

def v3_source():
    """Newest full-universe screener run in data/screens/extra/ (used as a proxy for months whose CSV predates v3)."""
    best = None
    for f in sorted(glob.glob(str(ROOT / "data/screens/extra/*.csv"))):
        try:
            x = pd.read_csv(f)
        except Exception:
            continue
        if len(x) >= 300 and "roic_pct" in x.columns and x.roic_pct.notna().sum() > 200:
            best = f
    return best
V3_SRC = v3_source()
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

def month_of(p): return re.search(r"(\d{4}-\d{2})", p).group(1)
CACHE = ROOT / "data/cache"
def load_month(f):
    """Score one month, reusing data/cache/scores_YYYY-MM.json when the CSV has not changed (scores are relative
    within a month, so a month's result never changes unless its own CSV changes)."""
    import hashlib
    h = hashlib.sha1(open(f, "rb").read() + f"v{SCORE_VERSION}|{V3_SRC}".encode()).hexdigest()[:12]   # CSV + score version + proxy source
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
    d["v3_source"] = "own" if has_v3 else (pathlib.Path(V3_SRC).name if V3_SRC else "none")
    d = score_v3(d); d["rank"] = d.score.rank(ascending=False, method="min").astype(int)
    CACHE.mkdir(exist_ok=True)
    keep = d.drop(columns=[c for c in ("g", "roe_c", "fcf_c", "fpe_c", "evx_c", "cagr_c", "rstd_c", "ecv_c", "roic_c", "fcv_c", "nde_c", "shr_c") if c in d.columns])
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
rows = []
for t, r in cur.iterrows():
    rr, rr_src, rr_why = required_return(t, r.sector, t_of.get(t, []))
    # WACC = equity share x required return + debt share x after-tax cost of debt (interest / debt, clipped 2-10%)
    D = float(r.total_debt) if not pd.isna(r.total_debt) else 0.0
    E = float(r.market_cap) if not pd.isna(r.market_cap) else np.nan
    rd_raw = (r.interest_expense / D) if (D > 0 and not pd.isna(r.interest_expense)) else None
    rd = 0.05 if rd_raw is None else min(max(rd_raw, 0.02), 0.10)   # guardrail; raw rate is reported, never hidden
    tx = r.tax_rate if not pd.isna(r.tax_rate) else 0.21
    wacc = None if pd.isna(E) or E <= 0 else (E * rr + D * rd * (1 - tx)) / (E + D)
    spread = None if (wacc is None or pd.isna(r.roic_pct) or r.sector == "Financial Services") else round(r.roic_pct / 100 - wacc, 4)
    flags_out = list(r["flag_list"]) + (["Below WACC"] if spread is not None and spread < 0 else [])
    pe_for_yield = r.forward_pe if (not pd.isna(r.forward_pe) and r.forward_pe > 0) else (r.pe_ratio if (not pd.isna(r.pe_ratio) and r.pe_ratio > 0) else None)
    ey = 100 / pe_for_yield if pe_for_yield else None                 # earnings yield, %
    conv = None if (ey is None or pd.isna(r.fcf_yield_pct)) else r.fcf_yield_pct / ey   # share of earnings that becomes free cash
    capex_heavy = ey is not None and (r.sector == "Financial Services" or pd.isna(r.fcf_yield_pct) or r.fcf_yield_pct <= 0 or (conv is not None and conv < MIN_FCF_CONVERSION))   # banks/insurers: FCF is not meaningful
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
        fcf_yield_pct=num(r.fcf_yield_pct), market_cap=num(r.market_cap), implied_fcf_growth=ig, implied_tag=tag, implied_basis=basis, required_return=rr, required_return_source=rr_src, required_return_reason=rr_why, fcf_conversion=None if conv is None else round(conv, 2), earnings_yield=None if ey is None else round(ey, 2),
        **{c: num(r[c]) for c in V3_COLS if c not in ("total_debt", "interest_expense", "fcf_conversion", "roic_basis", "share_jump")}, fcf_ni_conversion=num(r["fcf_conversion"]),
        roic_basis=(r["roic_basis"] if isinstance(r["roic_basis"], str) else None), share_jump=bool(r["share_jump"]) if not pd.isna(r["share_jump"]) else False,
        wacc_detail=None if wacc is None else dict(equity_weight=round(E / (E + D), 3), debt_weight=round(D / (E + D), 3), cost_equity=rr,
            cost_debt_raw=None if rd_raw is None else round(float(rd_raw), 4), cost_debt_used=round(rd, 4), tax=round(float(tx), 3)), wacc=None if wacc is None else round(wacc, 4), roic_spread=spread,
        v3_source=r.v3_source, score_v2=float(r.score_v2), components={k: float(r[f"c_{k}"]) for k in ("growth", "profit", "cash", "value", "balance", "quality")}, pe_vs_market=vs_mkt(r.pe_ratio, MKT_PE), fpe_vs_market=vs_mkt(r.forward_pe, MKT_FPE), has_fair_value=t in fv))
rows.sort(key=lambda x: x["rank"])
out = dict(score_version=SCORE_VERSION, v3_source=(pathlib.Path(V3_SRC).name if V3_SRC else None), market=dict(pe=round(MKT_PE, 1), forward_pe=round(MKT_FPE, 1), n=int(len(_t)), method="total market value / total earnings of screened stocks with positive earnings"), month=cur_m, prev_month=prev_m, months=months, estimated_months=sorted(estimated), window=WINDOW, consistent_rule=f"in the top 50 in at least {NEED} of the last {len(WINDOW)} months, including the latest", built=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"), universe=len(rows),
           sectors=sorted(cur.sector.dropna().unique().tolist()), themes=list(themes), rows=rows)
json.dump(out, open(ROOT / "data/screen.json", "w"), indent=0)
print("built", cur_m, "vs", prev_m, "rows", len(rows), "consistent", sum(r["consistent"] for r in rows))
print("TOP 15:", [(r["ticker"], r["score"]) for r in rows[:15]])
import collections
print("top50 sectors:", dict(collections.Counter(r["sector"] for r in rows[:50])))
