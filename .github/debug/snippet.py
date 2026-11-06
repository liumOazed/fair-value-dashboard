# Probe: Nasdaq-100 / DJIA tables on Wikipedia and the IWM holdings CSV
import io, urllib.request, pandas as pd
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60) as r:
        return r.read()
for name, url in [("NDX", "https://en.wikipedia.org/wiki/Nasdaq-100"), ("DJIA", "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average")]:
    try:
        tbls = pd.read_html(io.BytesIO(get(url)))
        print(name, "tables:", len(tbls))
        for i, t in enumerate(tbls):
            print(" ", i, t.shape, list(t.columns)[:8])
        for t in tbls:
            cols = [str(c) for c in t.columns]
            if any("Symbol" in c or "Ticker" in c for c in cols) and len(t) >= 25:
                print(name, "MEMBERS:", t.to_csv(index=False)[:6000])
                break
    except Exception as e:
        print(name, "FAILED", repr(e))
for u in ["https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund"]:
    try:
        b = get(u).decode("utf-8", "replace")
        print("IWM bytes", len(b)); print(b[:1500]); print("...lines", b.count("\n"))
    except Exception as e:
        print("IWM FAILED", repr(e))
