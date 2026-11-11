# One-off: acquisition spend, interest income and book equity per stock (for the cash-flow separation fixes).
import json, math, yfinance as yf
T = "CPRT,AOS,TPL,VICI,LIN,CL,ALGN,ANET,WSM,LRN,MCRI,CARG,USLM,EPAC".split(",")
ACQ = ["Net Business Purchase And Sale", "Purchase Of Business", "Acquisitions Net"]
II = ["Interest Income", "Interest Income Non Operating", "Interest And Dividend Income"]
def num(x):
    try:
        x = float(x); return None if math.isnan(x) else x
    except Exception: return None
def rows(df, names, k=4):
    for n in names:
        if df is not None and not df.empty and n in df.index:
            return n, {str(c)[:10]: num(df.loc[n, c]) for c in list(df.columns)[:k]}
    return None, {}
out = {}
for t in T:
    try:
        tk = yf.Ticker(t)
        cf, inc, qinc, bal = tk.cashflow, tk.income_stmt, tk.quarterly_income_stmt, tk.quarterly_balance_sheet
        an, a = rows(cf, ACQ); iname, i = rows(inc, II); _, qi = rows(qinc, II, 4)
        _, eq = rows(bal, ["Common Stock Equity", "Stockholders Equity"], 5)
        _, ta = rows(bal, ["Total Assets"], 1)
        out[t] = dict(acq_row=an, acq=a, ii_row=iname, ii=i, ii_q=qi, equity_q=eq, assets_q=ta)
    except Exception as e:
        out[t] = dict(error=str(e))
print(json.dumps(out))
