#!/usr/bin/env python3
"""Relative backtest (P3) of the Growth Screen rules, using only information available at each date.

Every quarter-end from 2013: take that day's S&P 500 members, rebuild each one's metrics from annual SEC figures
FILED BEFORE that day (as first reported), price them with that day's close, score them with the live score v4 code,
form groups and hold them for one quarter (equal weight, dividend-adjusted returns). Groups:
  score quintiles Q1 (best) .. Q5 (worst), the top 50, value quintiles by the quick fair value (V1 = cheapest),
  risk level Normal vs High, and top 50 that also look cheap (value / price >= 1). Baselines: all scored members
  equal-weighted, SPY and RSP (equal-weight S&P 500 ETF).
Differences that matter: annual figures (not latest-quarter), trailing P/E instead of forward P/E, today's sector
labels and required-return file. Survivorship: companies with no price history today are missing, so absolute
returns are flattered; compare groups with each other (spreads), not with SPY.
Block bootstrap (circular, 4-quarter blocks, 10,000 draws) gives the range of each spread.
Usage: python scripts/bt_run.py
"""
import gzip, json, pathlib, datetime, math
import numpy as np, pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
B = ROOT / "data/backtest"
SEED = 20261023

# reuse the live scoring and quick fair value code
ns = {"__file__": str(ROOT / "scripts/build_screen.py")}
exec(open(ROOT / "scripts/build_screen.py").read().split("allf = glob.glob")[0], ns)
fv_ns = {"__file__": str(ROOT / "scripts/fair_value_table.py"), "__name__": "fair_value_table"}
exec(open(ROOT / "scripts/fair_value_table.py").read(), fv_ns)              # main() is not run (__name__ guard)
score_v4, required_return, V3_COLS = ns["score_v4"], ns["required_return"], ns["V3_COLS"]
evaluate = fv_ns["evaluate"]

def load():
    mem = json.load(open(B / "membership.json"))
    facts = json.load(gzip.open(B / "facts.json.gz", "rt"))
    px = json.load(gzip.open(B / "prices.json.gz", "rt"))
    cur = pd.read_csv(sorted((ROOT / "data/screens").glob("growth_screen_results_*.csv"))[-1]).drop_duplicates("ticker").set_index("ticker")
    themes = {k: v for k, v in json.load(open(ROOT / "data/themes.json")).items() if not k.startswith("_")}
    t_of = {}
    for th, tk in themes.items():
        for t in tk: t_of.setdefault(t, []).append(th)
    return mem, facts, px, cur, t_of

def price_series(p):
    d = pd.to_datetime(p["d"])
    s_close = pd.Series(p["close"], index=d, dtype=float).dropna()
    s_adj = pd.Series(p["adj"], index=d, dtype=float).dropna()
    return s_close, s_adj

def at(s, d):
    """Last value on or before d (monthly bars are stamped at the month start)."""
    s = s[s.index <= d]
    return float(s.iloc[-1]) if len(s) else None

def split_factor_after(splits, date):
    f = 1.0
    for d, r in splits:
        if d > date: f *= r
    return f

def pit(series, d, n=4):
    """Annual values known on date d (filed <= d), oldest -> newest, at most n."""
    v = sorted((e, x[0]) for e, x in series.items() if x[1] <= d)
    return v[-n:]

def metrics(t, F, P, d):
    ds = d.strftime("%Y-%m-%d")
    g = {k: pit(F.get(k, {}), ds) for k in F if k != "cik"}
    rev = g["revenue"]
    if len(rev) < 2: return None
    if (d - pd.Timestamp(rev[-1][0])).days > 460: return None                     # stale: no 10-K in ~15 months
    vals = lambda k: [x for _, x in g[k]]
    last = lambda k: g[k][-1][1] if g[k] else None
    R = np.array(vals("revenue"), float)
    ni = last("net_income"); r0 = R[-1]
    if r0 is None or r0 <= 0: return None
    yoy = R[1:] / R[:-1] - 1
    out = dict(rev_growth_pct=yoy[-1] * 100, rev_cagr_pct=((R[-1] / R[0]) ** (1 / (len(R) - 1)) - 1) * 100 if R[0] > 0 else np.nan,
               rev_cagr_years=len(R) - 1, rev_growth_std=float(np.std(yoy * 100)) if len(yoy) >= 2 else np.nan)
    out["profit_margin_pct"] = ni / r0 * 100 if ni is not None else np.nan
    gp = last("gross_profit"); cogs = last("cost_of_revenue")
    out["gross_margin_pct"] = gp / r0 * 100 if gp is not None else ((r0 - cogs) / r0 * 100 if cogs is not None else np.nan)
    NI = np.array(vals("net_income"), float)
    out["earnings_cv"] = float(np.std(NI) / NI.mean()) if len(NI) >= 3 and NI.mean() > 0 else np.nan
    # free cash flow by year (match OCF and capex on the same period end)
    oc = dict(g["ocf"]); cx = dict(g["capex"])
    F_ = np.array([oc[e] - cx.get(e, 0) for e in sorted(oc)], float)
    out["fcf_years"] = len(F_) or np.nan; out["fcf_neg_years"] = int((F_ <= 0).sum()) if len(F_) else np.nan
    out["fcf_cv"] = float(np.std(F_) / F_.mean()) if len(F_) >= 3 and F_.mean() > 0 else np.nan
    fcf = F_[-1] if len(F_) else np.nan
    out["fcf_conversion"] = fcf / ni if ni and ni > 0 and fcf == fcf else np.nan
    capex, ocf = last("capex"), last("ocf")
    out["capex_ocf_pct"] = capex / ocf * 100 if capex is not None and ocf and ocf > 0 else np.nan
    out["capex_fcf"] = capex / fcf if capex is not None and fcf == fcf and fcf > 0 else np.nan
    # tax, ROIC (operating invested capital), leverage
    tax, pre = last("tax"), last("pretax")
    t_ = min(max(tax / pre, 0), 0.35) if tax is not None and pre and pre > 0 else 0.21
    out["tax_rate"] = t_
    oi = last("operating_income")
    A = dict(g["assets"]); CL = dict(g["cur_liab"]); C = dict(g["cash"]); SI = dict(g["st_inv"])
    LC = dict(g["ltd_cur"]); SD = dict(g["st_debt"]); LN = dict(g["ltd_noncur"]); LT = dict(g["ltd_total"]); EQ = dict(g["equity"])
    def debt_at(e): return (LN.get(e, 0) + LC.get(e, 0) + SD.get(e, 0)) if (e in LN or e in LC) else (LT.get(e, 0) + SD.get(e, 0) if (e in LT or e in SD) else 0.0)
    ends = [e for e in sorted(A) if e in CL][-2:]
    ic = [A[e] - C.get(e, 0) - SI.get(e, 0) - (CL[e] - LC.get(e, 0) - SD.get(e, 0)) for e in ends]
    out["roic_pct"] = oi * (1 - t_) / np.mean(ic) * 100 if oi is not None and ic and np.mean(ic) > 0 else np.nan
    out["roic_basis"] = "operating"
    eq = last("equity")
    out["roe_pct"] = ni / eq * 100 if ni is not None and eq and eq > 0 else np.nan
    e_last = sorted(A)[-1] if A else None
    debt = debt_at(e_last) if e_last else 0.0
    cash = (C.get(e_last, 0) + SI.get(e_last, 0)) if e_last else 0.0
    dna = last("dna"); ebitda = (oi + dna) if (oi is not None and dna is not None) else None
    out["total_debt"] = debt
    out["net_debt_ebitda"] = (debt - cash) / ebitda if ebitda and ebitda > 0 else np.nan
    it = last("interest")
    out["interest_expense"] = abs(it) if it is not None else np.nan
    out["interest_coverage"] = (999.0 if (it is None or abs(it) < 1) else oi / abs(it)) if oi is not None else np.nan
    out["cost_of_debt"] = abs(it) / debt if it is not None and debt > 0 else np.nan
    # per-share figures on today's split basis
    sp = P.get("splits", [])
    sh = [(e, x * split_factor_after(sp, e)) for e, x in g["dil_shares"]]
    S = np.array([x for _, x in sh if x and x > 0], float)
    out["share_change_pct_yr"] = ((S[-1] / S[0]) ** (1 / (len(S) - 1)) - 1) * 100 if len(S) >= 2 and S[0] > 0 else np.nan
    out["share_jump"] = bool(len(S) >= 2 and np.any(np.abs(S[1:] / S[:-1] - 1) > 0.5))
    E = np.array([x / split_factor_after(sp, e) for e, x in g["eps"]], float)
    out["eps_cagr_pct"] = ((E[-1] / E[0]) ** (1 / (len(E) - 1)) - 1) * 100 if len(E) >= 2 and E[0] > 0 and E[-1] > 0 and not out["share_jump"] else np.nan
    # market data on date d (split-adjusted close x split-adjusted shares)
    close, adj = price_series(P)
    p = at(close, d)
    if p is None or not len(S): return None
    mcap = p * S[-1]
    out["market_cap"] = mcap
    out["pe_ratio"] = mcap / ni if ni and ni > 0 else np.nan
    out["forward_pe"] = out["pe_ratio"]                                           # no historical forecasts
    out["ev_ebitda"] = (mcap + debt - cash) / ebitda if ebitda and ebitda > 0 else np.nan
    out["fcf_yield_pct"] = fcf / mcap * 100 if fcf == fcf else np.nan
    out["ps_ratio"] = mcap / r0
    out["margin_change_pts"] = np.nan; out["nd_ebitda_then"] = np.nan; out["fcf_cagr_pct"] = np.nan
    return out

def quarter_return(P, d0, d1):
    _, adj = price_series(P)
    a, b = at(adj, d0), at(adj, d1)
    return None if (a is None or b is None or a <= 0) else b / a - 1

def stats(r):
    r = np.array(r, float)
    if not len(r): return {}
    cum = np.cumprod(1 + r)
    dd = float((cum / np.maximum.accumulate(cum) - 1).min())
    return dict(ann=float(cum[-1] ** (4 / len(r)) - 1), vol=float(r.std() * 2), maxdd=dd, n=len(r))

def bootstrap(x, n=10000, block=4, seed=SEED):
    x = np.array(x, float); L = len(x)
    if L < block * 2: return None
    rng = np.random.default_rng(seed)
    nb = math.ceil(L / block)
    starts = rng.integers(0, L, size=(n, nb))
    idx = (starts[:, :, None] + np.arange(block)) % L
    s = x[idx.reshape(n, -1)[:, :L]]
    ann = np.prod(1 + s, axis=1) ** (4 / L) - 1
    return dict(p5=float(np.percentile(ann, 5)), p50=float(np.percentile(ann, 50)), p95=float(np.percentile(ann, 95)), p_pos=float((ann > 0).mean()))

def main():
    mem, facts, px, cur, t_of = load()
    dates = [pd.Timestamp(d) for d in sorted(mem) if pd.Timestamp(d) >= pd.Timestamp("2013-03-31")]
    last_px = max(pd.to_datetime(px["SPY"]["d"]))
    dates = [d for d in dates if d + pd.DateOffset(months=3) <= last_px]
    groups = {k: [] for k in ["Q1", "Q2", "Q3", "Q4", "Q5", "TOP50", "V1", "V2", "V3", "V4", "V5", "NORMAL", "HIGH", "TOP50_CHEAP", "ALL", "SPY", "RSP"]}
    cover, sizes = [], []
    for d in dates:
        d1 = d + pd.DateOffset(months=3)
        rows = []
        for t in mem[d.strftime("%Y-%m-%d")]:
            if t not in facts or t not in px: continue
            try: m = metrics(t, facts[t], px[t], d)
            except Exception: m = None
            if not m: continue
            sec = cur.sector.get(t) if t in cur.index else "Unknown"
            rr, _, _ = required_return(t, sec, t_of.get(t, []))
            m.update(ticker=t, name=t, sector=sec if isinstance(sec, str) else "Unknown", growth_score=np.nan, required_return=rr,
                     peer=ns["PEER_OF"].get(t, sec), v3_source="own", industry="", beta=np.nan, volatility_1y_pct=np.nan, max_drawdown_1y_pct=np.nan)
            m["fwd_ret"] = quarter_return(px[t], d, d1)
            rows.append(m)
        if len(rows) < 100: continue
        df = pd.DataFrame(rows).set_index("ticker", drop=False)
        df = score_v4(df)
        df = df[df.fwd_ret.notna()]
        df["q"] = pd.qcut(df.score.rank(method="first", ascending=False), 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"])
        top50 = df.nsmallest(50, "score").index if False else df.nlargest(50, "score").index
        # quick fair value (same evaluate() as the live Monthly Top 5), on stocks passing the basic sanity filters
        ok = df[(df.sector != "Financial Services") & (df.pe_ratio > 0) & (df.profit_margin_pct >= 0) & (df.fcf_yield_pct > 0)]
        conv = ok.fcf_yield_pct / (100 / ok.pe_ratio)
        ok = ok[(conv >= 0.25) & (conv <= 1.5)]
        vtp = {}
        for t, r in ok.iterrows():
            rd = dict(sector=r.sector, fcf_yield_pct=r.fcf_yield_pct, pe=r.pe_ratio, earnings_yield=100 / r.pe_ratio,
                      rev_growth_pct=r.rev_growth_pct, required_return=r.required_return)
            vtp[t] = evaluate(rd)["value_to_price"]
        vs = pd.Series(vtp)
        vq = pd.qcut(vs.rank(method="first", ascending=False), 5, labels=["V1", "V2", "V3", "V4", "V5"]) if len(vs) >= 50 else None
        ew = lambda idx: float(df.loc[list(idx), "fwd_ret"].mean()) if len(idx) else np.nan
        for q in ["Q1", "Q2", "Q3", "Q4", "Q5"]: groups[q].append(ew(df.index[df.q == q]))
        groups["TOP50"].append(ew(top50))
        for q in ["V1", "V2", "V3", "V4", "V5"]: groups[q].append(ew(vq.index[vq == q]) if vq is not None else np.nan)
        groups["NORMAL"].append(ew(df.index[df.risk_level == "Normal"])); groups["HIGH"].append(ew(df.index[df.risk_level == "High"]))
        cheap = [t for t in top50 if vtp.get(t, 0) >= 1]
        groups["TOP50_CHEAP"].append(ew(cheap) if len(cheap) >= 5 else ew(top50))
        groups["ALL"].append(ew(df.index))
        for b in ("SPY", "RSP"): groups[b].append(quarter_return(px[b], d, d1))
        cover.append(dict(date=d.strftime("%Y-%m-%d"), members=len(mem[d.strftime("%Y-%m-%d")]), scored=len(df), valued=len(vs), top50_cheap=len(cheap)))
        print(f"{d.date()} members {len(mem[d.strftime('%Y-%m-%d')])} scored {len(df)} | Q1 {groups['Q1'][-1]:+.3f} Q5 {groups['Q5'][-1]:+.3f} ALL {groups['ALL'][-1]:+.3f}", flush=True)
    G = {k: [0.0 if (x is None or x != x) else x for x in v] for k, v in groups.items()}
    spreads = {"Q1 − Q5 (score)": np.subtract(G["Q1"], G["Q5"]), "Top 50 − all": np.subtract(G["TOP50"], G["ALL"]),
               "V1 − V5 (quick fair value)": np.subtract(G["V1"], G["V5"]), "Normal − High risk": np.subtract(G["NORMAL"], G["HIGH"]),
               "Top 50 cheap − all": np.subtract(G["TOP50_CHEAP"], G["ALL"])}
    out = dict(built=datetime.date.today().isoformat(), dates=[c["date"] for c in cover], coverage=cover,
               groups={k: dict(returns=[round(x, 5) for x in v], cum=[round(float(c), 4) for c in np.cumprod(1 + np.array(v))], **stats(v)) for k, v in G.items()},
               spreads={k: dict(ann_mean=float(np.mean(v) * 4), hit=float((np.array(v) > 0).mean()), bootstrap=bootstrap(v)) for k, v in spreads.items()},
               notes=["Survivorship: companies without a price history today are missing, so compare groups with each other, not with SPY.",
                      "Annual SEC figures as first reported, filed before each date; trailing P/E (no historical forecasts); today's sectors and required returns.",
                      "Equal weight, dividend-adjusted, quarterly rebalance, no trading costs."])
    json.dump(out, open(B / "results.json", "w"), indent=1)
    for k, v in out["spreads"].items(): print(f"{k:28} ann {v['ann_mean']:+.2%}  hit {v['hit']:.0%}  bootstrap {v['bootstrap']}")

if __name__ == "__main__":
    main()
