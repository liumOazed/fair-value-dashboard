# Probe 3: Nasdaq-100 list page title, IWM with siteEntryPassthrough, Vanguard VTWO, SEC N-PORT
import io, json, urllib.request, pandas as pd
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "*/*"}
def get(u, h=H):
    with urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=60) as r:
        return r.read()
for url in ["https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies", "https://en.wikipedia.org/wiki/Nasdaq-100_Index"]:
    try:
        tbls = pd.read_html(io.BytesIO(get(url)))
        print(url, "tables:", len(tbls))
        for i, t in enumerate(tbls[:6]): print(" ", i, t.shape, list(t.columns)[:8])
        for t in tbls:
            cols = [str(c) for c in t.columns]
            if any("Symbol" in c or "Ticker" in c for c in cols) and len(t) >= 90:
                print("MEMBERS:", len(t)); print(t.head(3).to_csv(index=False)); break
    except Exception as e:
        print(url, "FAILED", repr(e))
for u in ["https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund&siteEntryPassthrough=true",
          "https://investor.vanguard.com/investment-products/etfs/profile/api/VTWO/portfolio-holding/stock",
          "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/holdings-daily-us-en-twok.xlsx"]:
    try:
        b = get(u); s = b[:400].decode("utf-8-sig", "replace").replace("\n", " | ")
        print("SRC", u[:90], "bytes", len(b), "| starts:", s)
    except Exception as e:
        print("SRC FAILED", u[:90], repr(e))
try:
    sh = {"User-Agent": "fair-value-dashboard research contact@example.com"}
    j = json.loads(get("https://efts.sec.gov/LATEST/search-index?q=%22iShares%20Russell%202000%20ETF%22&forms=NPORT-P", sh))
    print("SEC hits", j.get("hits", {}).get("total"))
except Exception as e:
    print("SEC FAILED", repr(e))
