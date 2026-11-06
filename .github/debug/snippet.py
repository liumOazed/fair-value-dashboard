# Probe 2: Wikipedia list pages for Nasdaq-100 / DJIA members, IWM holdings URL variants
import io, urllib.request, pandas as pd
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "text/csv,application/json,*/*"}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60) as r:
        return r.read()
for name, url in [("NDX", "https://en.wikipedia.org/wiki/List_of_Nasdaq-100_companies"),
                  ("DJIA", "https://en.wikipedia.org/wiki/List_of_Dow_Jones_Industrial_Average_companies"),
                  ("DJIA2", "https://en.wikipedia.org/wiki/Historical_components_of_the_Dow_Jones_Industrial_Average")]:
    try:
        tbls = pd.read_html(io.BytesIO(get(url)))
        print(name, "tables:", len(tbls))
        for i, t in enumerate(tbls[:6]):
            print(" ", i, t.shape, list(t.columns)[:8])
        for t in tbls:
            cols = [str(c) for c in t.columns]
            if any("Symbol" in c or "Ticker" in c for c in cols) and len(t) >= 25:
                print(name, "MEMBERS:\n", t.to_csv(index=False)[:5000]); break
    except Exception as e:
        print(name, "FAILED", repr(e))
base = "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/1467271812596.ajax"
for q in ["?fileType=csv&fileName=IWM_holdings&dataType=fund", "?tab=all&fileType=json", "?fileType=csv&fileName=IWM_holdings&dataType=fund&asOfDate="]:
    try:
        b = get(base + q).decode("utf-8-sig", "replace")
        print("IWM", q, "bytes", len(b), "| starts:", b[:300].replace("\n", " | "))
    except Exception as e:
        print("IWM", q, "FAILED", repr(e))
for u in ["https://www.ishares.com/us/products/239710/fund/1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund",
          "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/1521942788811.ajax?fileType=xls&fileName=iShares-Russell-2000-ETF_fund&dataType=fund"]:
    try:
        b = get(u).decode("utf-8-sig", "replace"); print("ALT", u[-60:], len(b), b[:300].replace("\n", " | "))
    except Exception as e:
        print("ALT FAILED", repr(e))
