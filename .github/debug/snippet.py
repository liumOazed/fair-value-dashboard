# One-off: acquisition spend, interest income and book equity per stock (for the cash-flow separation fixes).
import json, math, yfinance as yf
T = "AAPL,MSFT,GOOGL,AMZN,NVDA,AVGO,LLY,ADBE,APP,FICO,APA,DECK,INCY,MKC,EXPE,BKNG,INTU,ADSK,TPR,VEEV,MNST,ALLE,FTNT,RMD,V,FIX,MA,CTAS,DXCM,IDXX,VRSN,NDAQ,MCO,SPGI,NFLX,CBOE,GRMN,FDS,CRM,HWM,ADP,AME,AXP,SHOP,PYPL,XYZ,ADYEY,FISV,CRCL,SPG,META,TT,RL,ROST,GDDY,FAST,SYK,CMG,KLAC,CME,STE,WDAY,BR,MSI,BKR,RSG,WAB,MRVL,LULU,RDDT,CF,EME,HST,LII,NEM,REGN,ZTS,MO,HAS,BMY,NRG,FIS,PG,KO,SHW,JNJ,AMGN,VLTO,AMP,PPG,EOG,PM,DLTR,INVA,CTRE,CVSA,QLYS,LAUR,IDCC,LMAT,BOX,ACIW,MRSH,WTW,CRVL".split(",")
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
