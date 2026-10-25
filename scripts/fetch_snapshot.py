#!/usr/bin/env python3
"""Fetch the extra history the Fair Value snapshot needs (runs on GitHub; Yahoo via yfinance).
Per stock: dividend history, 4-5 annual years of income / balance sheet / cash flow (margins, ROIC, payout, buybacks),
the latest quarterly balance sheet (current ratio, cash vs debt) and 6 years of month-end prices (split-adjusted) plus the split history (for P/E, EV/EBITDA and
FCF-yield ranges). Debt maturities are not in Yahoo's free data, so they are not fetched.
Usage: python scripts/fetch_snapshot.py [--tickers AAPL,MSFT] --out data/snapshot_raw.json
(default tickers: every stock in data/assets.json)
"""
import argparse, json, math, pathlib, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
INC = {"rev": ["Total Revenue", "Operating Revenue"], "gross": ["Gross Profit"], "op": ["Operating Income", "Total Operating Income As Reported"],
       "ni": ["Net Income Common Stockholders", "Net Income"], "eps": ["Diluted EPS", "Basic EPS"], "ebitda": ["EBITDA", "Normalized EBITDA"],
       "pretax": ["Pretax Income"], "tax": ["Tax Provision"], "interest": ["Interest Expense", "Interest Expense Non Operating"]}
BAL = {"equity": ["Stockholders Equity", "Total Equity Gross Minority Interest"], "debt": ["Total Debt"],
       "cash": ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"],
       "cur_assets": ["Current Assets"], "cur_liab": ["Current Liabilities"], "shares": ["Ordinary Shares Number", "Share Issued"],
       "inventory": ["Inventory"], "receivables": ["Accounts Receivable", "Receivables"]}
CFS = {"ocf": ["Operating Cash Flow"], "capex": ["Capital Expenditure"], "fcf": ["Free Cash Flow"], "sbc": ["Stock Based Compensation"],
       "div_paid": ["Cash Dividends Paid", "Common Stock Dividend Paid"], "buyback": ["Repurchase Of Capital Stock", "Common Stock Payments"],
       "issued": ["Issuance Of Capital Stock", "Common Stock Issuance"]}


def num(x):
    try:
        x = float(x)
        return None if math.isnan(x) else x
    except Exception:
        return None


def table(df, rows, k=5):
    """{'2025-09-30': {'rev': .., ...}, ...} for the latest k columns."""
    out = {}
    if df is None or getattr(df, "empty", True):
        return out
    for c in list(df.columns)[:k]:
        rec = {}
        for key, names in rows.items():
            for n in names:
                if n in df.index:
                    v = num(df.loc[n, c])
                    if v is not None:
                        rec[key] = v
                        break
        out[str(c)[:10]] = rec
    return out


def get(tk, attr, *a, **kw):
    for i in range(3):
        try:
            v = getattr(tk, attr)
            return v(*a, **kw) if callable(v) else v
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def fetch(t):
    import yfinance as yf
    tk = yf.Ticker(t)
    info = get(tk, "info") or {}
    divs = get(tk, "dividends")
    dps = {}
    if divs is not None and len(divs):
        for d, v in divs.items():
            dps[str(d.year)] = dps.get(str(d.year), 0.0) + float(v)
    last12 = None
    if divs is not None and len(divs):
        cut = divs.index[-1] - __import__("pandas").Timedelta(days=365)
        last12 = float(divs[divs.index > cut].sum())
    sp = get(tk, "splits")
    splits = {str(d)[:10]: float(v) for d, v in sp.items()} if sp is not None and len(sp) else {}
    px = get(tk, "history", period="6y", interval="1mo", auto_adjust=False)
    prices = {}
    if px is not None and not px.empty:
        for d, v in px["Close"].dropna().items():
            prices[str(d)[:7]] = round(float(v), 4)
    return dict(
        ticker=t, price=num(info.get("currentPrice") or info.get("regularMarketPrice")), shares=num(info.get("sharesOutstanding")),
        currency=info.get("financialCurrency"),
        info={k: num(info.get(k)) for k in ("dividendRate", "dividendYield", "payoutRatio", "fiveYearAvgDividendYield", "trailingEps",
                                             "forwardEps", "enterpriseValue", "ebitda", "currentRatio", "quickRatio", "totalCash", "totalDebt",
                                             "returnOnEquity", "returnOnAssets", "operatingMargins", "grossMargins", "profitMargins")},
        dividends=dict(by_year=dps, ttm=last12, last_date=str(divs.index[-1])[:10] if divs is not None and len(divs) else None,
                       payments=[[str(d)[:10], round(float(v), 6)] for d, v in divs.items()][-120:] if divs is not None and len(divs) else []),
        annual=dict(inc=table(get(tk, "income_stmt"), INC), bal=table(get(tk, "balance_sheet"), BAL), cfs=table(get(tk, "cashflow"), CFS)),
        quarterly_bal=table(get(tk, "quarterly_balance_sheet"), BAL, 1),
        monthly_prices=prices, splits=splits,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="")
    ap.add_argument("--out", default=str(ROOT / "data/snapshot_raw.json"))
    a = ap.parse_args()
    tickers = [x.strip().upper() for x in a.tickers.split(",") if x.strip()] or \
        [x["ticker"] for x in json.load(open(ROOT / "data/assets.json"))["assets"] if x.get("type") == "stock"]
    res = {}
    for t in tickers:
        try:
            res[t] = fetch(t)
            print("ok", t, len(res[t]["dividends"]["by_year"]), "div years,", len(res[t]["monthly_prices"]), "months")
        except Exception as e:
            res[t] = {"ticker": t, "error": str(e)}
            print("FAIL", t, e)
        time.sleep(1)
    doc = {"fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": "Yahoo Finance via yfinance", "stocks": res}
    pathlib.Path(a.out).write_text(json.dumps(doc, separators=(",", ":")))


if __name__ == "__main__":
    main()
