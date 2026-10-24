#!/usr/bin/env python3
"""Fetch the raw inputs needed to build a full fair-value model for new stocks (runs on GitHub; Yahoo via yfinance).
Writes one JSON with, per ticker: price, shares, last-4-quarter (TTM) revenue / free cash flow / stock pay / interest /
tax, latest cash and debt, 4 annual years of the same, and analyst revenue/EPS growth estimates. Inputs only: the
scenarios are written by hand in model/model.py.
Usage: python scripts/fetch_inputs.py --tickers V,MA --out data/inputs/2026-10-24.json
"""
import argparse, json, math, time
import pandas as pd

ROWS = {
    "rev": ["Total Revenue", "Operating Revenue"],
    "ocf": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "capex": ["Capital Expenditure"],
    "fcf": ["Free Cash Flow"],
    "sbc": ["Stock Based Compensation"],
    "interest": ["Interest Expense", "Interest Expense Non Operating"],
    "tax": ["Tax Provision"],
    "pretax": ["Pretax Income"],
    "ni": ["Net Income", "Net Income Common Stockholders"],
    "op_inc": ["Operating Income"],
    "ebitda": ["EBITDA", "Normalized EBITDA"],
    "buyback": ["Repurchase Of Capital Stock"],
    "dividends": ["Cash Dividends Paid", "Common Stock Dividend Paid"],
}
BAL = {
    "cash": ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"],
    "debt": ["Total Debt"],
    "lease": ["Capital Lease Obligations"],
    "shares_bs": ["Ordinary Shares Number", "Share Issued"],
}

def num(x):
    try:
        x = float(x)
        return None if math.isnan(x) else x
    except Exception:
        return None

def pick(df, names, col):
    for n in names:
        if df is not None and not df.empty and n in df.index:
            v = num(df.loc[n, col])
            if v is not None:
                return v
    return None

def series(df, names, k):
    if df is None or df.empty:
        return []
    cols = list(df.columns)[:k]
    return [{"period": str(c)[:10], "value": pick(df, names, c)} for c in cols]

def ttm(df, names):
    if df is None or df.empty:
        return None
    cols = list(df.columns)[:4]
    vals = [pick(df, names, c) for c in cols]
    return sum(vals) if len(cols) == 4 and all(v is not None for v in vals) else None

def get(tk, attr):
    for i in range(3):
        try:
            return getattr(tk, attr)
        except Exception:
            time.sleep(2 * (i + 1))
    return None

def fetch(t):
    import yfinance as yf
    tk = yf.Ticker(t)
    info = get(tk, "info") or {}
    qi, qc, qb = get(tk, "quarterly_income_stmt"), get(tk, "quarterly_cashflow"), get(tk, "quarterly_balance_sheet")
    ai, ac = get(tk, "income_stmt"), get(tk, "cashflow")
    out = dict(
        ticker=t, name=info.get("longName") or info.get("shortName"), sector=info.get("sector"), industry=info.get("industry"),
        currency=info.get("financialCurrency"), price=num(info.get("currentPrice") or info.get("regularMarketPrice")),
        shares=num(info.get("sharesOutstanding")), implied_shares=num(info.get("impliedSharesOutstanding")),
        market_cap=num(info.get("marketCap")), beta=num(info.get("beta")),
        info=dict(totalRevenue=num(info.get("totalRevenue")), freeCashflow=num(info.get("freeCashflow")),
                  operatingCashflow=num(info.get("operatingCashflow")), totalCash=num(info.get("totalCash")),
                  totalDebt=num(info.get("totalDebt")), revenueGrowth=num(info.get("revenueGrowth")),
                  earningsGrowth=num(info.get("earningsGrowth")), grossMargins=num(info.get("grossMargins")),
                  operatingMargins=num(info.get("operatingMargins")), profitMargins=num(info.get("profitMargins")),
                  trailingPE=num(info.get("trailingPE")), forwardPE=num(info.get("forwardPE")),
                  trailingEps=num(info.get("trailingEps")), forwardEps=num(info.get("forwardEps")),
                  dividendYield=num(info.get("dividendYield")), targetMeanPrice=num(info.get("targetMeanPrice")),
                  numberOfAnalystOpinions=num(info.get("numberOfAnalystOpinions")), mostRecentQuarter=info.get("mostRecentQuarter")),
        ttm={k: ttm(qi if k in ("rev", "interest", "tax", "pretax", "ni", "op_inc", "ebitda") else qc, v) for k, v in ROWS.items()},
        quarters={k: series(qi if k in ("rev", "interest", "tax", "pretax", "ni", "op_inc", "ebitda") else qc, v, 5) for k, v in ROWS.items()},
        balance={k: series(qb, v, 2) for k, v in BAL.items()},
        annual={k: series(ai if k in ("rev", "interest", "tax", "pretax", "ni", "op_inc", "ebitda") else ac, v, 5) for k, v in ROWS.items()},
    )
    for attr in ("revenue_estimate", "earnings_estimate", "growth_estimates"):
        df = get(tk, attr)
        try:
            out[attr] = json.loads(df.to_json()) if df is not None and not df.empty else None
        except Exception:
            out[attr] = None
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    res = {}
    for t in [x.strip().upper() for x in a.tickers.split(",") if x.strip()]:
        try:
            res[t] = fetch(t); print("ok", t, res[t]["price"], res[t]["ttm"]["rev"], res[t]["ttm"]["fcf"])
        except Exception as e:
            res[t] = {"error": str(e)}; print("FAIL", t, e)
        time.sleep(1)
    import pathlib
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(a.out, "w"), indent=1, default=str)

if __name__ == "__main__":
    main()
