#!/usr/bin/env python3
"""Russell 2000 small-cap screen: data/screens/russell/r2000_screen_YYYY-MM.csv -> data/russell.json.

Steps (each month, after the Russell run of scripts/growth_screener.py --universe r2000):
1. Quality gate. About 40% of the index loses money, so a stock is ranked only if it passes ALL of:
     market value at least $1B | average daily trading at least $5M | at least 4 fiscal years of statements
     | operating margin above zero | free cash flow positive in 3 of the last 4 years (banks and insurers: net margin
     above zero and ROE of at least 8% instead, as their free cash flow is not meaningful)
   Every failed stock keeps its first failed test, so the page can show why the gate is as narrow as it is.
2. Score: the same Growth Quality Score v4 as the S&P 500 screen (scripts/screen_score.py), but every percentile is
   taken WITHIN the gated small caps, never against the S&P 500 (or small caps would be judged against Apple).
3. Top 50 by score. Each gets the Monthly Top 5 quick estimate (scripts/fair_value_table.py: lower of FCF and trailing
   earnings yield, Bear/Base/Bull 30/50/20, 2.5% terminal growth) at the sector required return PLUS the small-cap
   premium in data/required_returns.json. Margin of safety 35% (40% cyclical): small caps are less certain.
   The same sanity filters as the Top 5 apply (loss-making, FCF distorted, one-off growth, high debt ...), and a
   value-to-price above 2.5x goes to "check first" instead of getting a fair value.
4. History: each month's top 50 is kept, so 'months in top 50' shows which names are steady.
No full models: a stock moves to the Fair Value tab only when it is modelled by hand.
Usage: python scripts/build_russell.py
"""
import datetime, glob, json, pathlib, re, sys
import numpy as np, pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from screen_score import ROOT, RRF, CYCLICAL, V3_COLS, score_v4, risk_assessment   # same score as the S&P 500 screen
from fair_value_table import evaluate, price, TOO_CHEAP                              # same quick estimate as the Top 5

GATE = dict(min_cap=1e9, min_dollar_volume=5e6, min_years=4, max_neg_fcf_years=1, bank_min_roe=8.0)
PREMIUM = RRF.get("small_cap_premium", {}).get("r", 0.02)
TOP_N = 50
OUT = ROOT / "data/russell.json"


def latest_csv():
    files = sorted(glob.glob(str(ROOT / "data/screens/russell/r2000_screen_*.csv")))
    if not files: raise SystemExit("No Russell 2000 screen yet: run the Russell 2000 workflow")
    return files[-1], re.search(r"(\d{4}-\d{2})", files[-1]).group(1)


def gate_reason(r):
    """First failed test, or None when the stock passes the quality gate."""
    fin = r.sector == "Financial Services"
    if not (r.market_cap >= GATE["min_cap"]): return "Market value under $1B"
    if not (r.avg_dollar_volume >= GATE["min_dollar_volume"]): return "Trades under $5M a day"
    if not (r.rev_cagr_years >= GATE["min_years"] - 1): return "Under 4 years of statements"
    if fin:
        if not (r.profit_margin_pct > 0): return "Loss-making"
        if not (r.roe_pct >= GATE["bank_min_roe"]): return "ROE under 8% (bank / insurer)"
        return None
    if not (r.operating_margin_pct > 0): return "Operating loss"
    if not (r.fcf_years >= GATE["min_years"]) or not (r.fcf_neg_years <= GATE["max_neg_fcf_years"]):
        return "Free cash flow negative in 2+ of the last 4 years (or under 4 years)"
    return None


def required_return(sector):
    base = RRF["sectors"].get(sector, RRF["default"])
    return round(base + PREMIUM, 4)


def skip_reason(r):
    """The Monthly Top 5 sanity filters that need no previous month (small caps have no history in this screen yet)."""
    ey, fy, conv, g, m = r["earnings_yield"], r["fcf_yield_pct"], r["fcf_ni"], r["rev_growth_pct"], r["profit_margin_pct"]
    if r["sector"] == "Financial Services": return "Financial company: free cash flow is not meaningful"
    if ey is None: return "No P/E (no earnings to cross-check)"
    if m is not None and m < 0: return "Loss-making"
    if fy is None or fy <= 0 or (conv is not None and conv < 0.25): return "FCF distorted (cash flow far below earnings)"
    if conv is not None and conv > 1.5: return "FCF unusually high (more than 1.5x net income, may not last)"
    if g is not None and g > 100: return "One-off growth (sales more than doubled)"
    if g is not None and g > 40 and m is not None and m < 5: return "Acquisition-like growth (sales up >40% on a thin margin)"
    nde, cov = r["net_debt_ebitda"], r["interest_coverage"]
    if nde is not None and nde > 4: return f"High debt (net debt {nde:.1f}x EBITDA)"
    if cov is not None and cov < 3 and nde is not None and nde > 0: return f"Weak interest cover (EBIT only {cov:.1f}x interest)"
    return None


def num(x, n=2):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) or pd.isna(x) else round(float(x), n)


def main():
    f, month = latest_csv()
    d = pd.read_csv(f).drop_duplicates("ticker").set_index("ticker", drop=False)
    for c in V3_COLS + ["avg_dollar_volume"]:
        if c not in d.columns: d[c] = np.nan
    d["gate"] = [gate_reason(r) for _, r in d.iterrows()]
    failed = d[d.gate.notna()]
    g = d[d.gate.isna()].copy()
    if len(g) < 100: raise SystemExit(f"Only {len(g)} stocks passed the gate: the run looks incomplete")
    g["peer"] = g.sector                                       # percentiles within each sector of the gated group
    g["v3_source"] = "own"
    g = score_v4(g)
    g["rank"] = g.score.rank(ascending=False, method="min").astype(int)
    g = g.rename_axis(None).sort_values(["rank", "ticker"])

    prev = json.load(open(OUT)) if OUT.exists() else {"months": {}}
    hist = {m: set(v["top50"]) for m, v in prev.get("months", {}).items() if m != month}
    window = sorted(hist)[-2:] + [month]                       # this month and the two before it

    rows = []
    for _, r in g.iterrows():
        fin = r.sector == "Financial Services"
        tey = num(r.earnings_yield_pct) if not pd.isna(r.earnings_yield_pct) else (num(100 / r.pe_ratio) if r.pe_ratio and r.pe_ratio > 0 else None)
        top = int(r["rank"]) <= TOP_N
        row = dict(ticker=r.ticker, name=r["name"], sector=r.sector, industry=r.industry if isinstance(r.industry, str) else "",
                   score=float(r.score), rank=int(r["rank"]), top50=top,
                   parts={k: num(r[f"c_{k}"], 0) for k in ("quality", "growth", "value", "resilience")},
                   market_cap_b=num(r.market_cap / 1e9, 2), dollar_volume_m=num(r.avg_dollar_volume / 1e6, 1),
                   rev_growth_pct=num(r.rev_growth_pct, 1), rev_cagr_pct=num(r.rev_cagr_pct, 1), profit_margin_pct=num(r.profit_margin_pct, 1),
                   roic_pct=num(r.roic_pct, 1), fcf_yield_pct=num(r.fcf_yield_pct), earnings_yield=tey, pe=num(r.pe_ratio, 1), forward_pe=num(r.forward_pe, 1),
                   net_debt_ebitda=num(r.net_debt_ebitda, 1), interest_coverage=num(r.interest_coverage, 1),
                   fcf_ni=num(r.fcf_ni_3y if not pd.isna(r.fcf_ni_3y) else r.fcf_conversion),
                   risk_level=r.risk_level, risks=list(r.risk_serious) + list(r.risk_warn), data_confidence=r.data_confidence,
                   flags=list(r.flag_list), required_return=required_return(r.sector),
                   months_in_top50=sum(r.ticker in hist.get(m, set()) for m in window[:-1]) + int(top))
        if top:
            why = skip_reason(row)
            if why:
                row["fv_skip"] = why
            else:
                ev = evaluate(dict(row, pe=row["pe"]))
                ev["mos"] = 0.40 if ev["cyclical"] else 0.35         # small caps: 5 points more safety than the Top 5
                if ev["value_to_price"] > TOO_CHEAP:
                    row["fv_skip"] = f"Looks {ev['value_to_price']:.1f}x undervalued: too cheap to trust without checking for one-off gains or data errors"
                    row["check_first"] = True
                else:
                    p = price(r.ticker)
                    fv = None if p is None else round(p * ev["value_to_price"], 2)
                    row.update(price_at_eval=p, fair_value=fv, buy_below=None if fv is None else round(fv * (1 - ev["mos"]), 2),
                               scenario_values=None if p is None else {k: round(p * v["ratio"], 2) for k, v in ev["scenarios"].items()}, quick=ev)
        rows.append(row)

    counts = failed.gate.value_counts().to_dict()
    src = (ROOT / "data/universe/IWM_holdings.csv")
    as_of = next((l.split(",", 1)[1].strip().strip('"') for l in src.read_text(encoding="utf-8-sig").splitlines()[:5]
                  if l.startswith("Fund Holdings as of")), None) if src.exists() else None
    out = dict(prev, month=month, csv=pathlib.Path(f).name, built=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
               members_as_of=as_of, screened=int(len(d)), passed=int(len(g)), gate=GATE, gate_failed=counts,
               small_cap_premium=PREMIUM, window=window, rows=rows)
    out.setdefault("months", {})[month] = dict(top50=[x["ticker"] for x in rows if x["top50"]], passed=int(len(g)), screened=int(len(d)))
    json.dump(out, open(OUT, "w"), indent=0)
    valued = [x for x in rows if x.get("fair_value")]
    print(f"Russell 2000 {month}: {len(d)} screened, {len(g)} passed the gate, top {TOP_N} scored, {len(valued)} quick fair values")
    print("gate failures:", counts)
    print("TOP 10:", [(x["ticker"], x["score"]) for x in rows[:10]])


if __name__ == "__main__":
    main()
