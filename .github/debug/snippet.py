import json, urllib.request
for t in "SPY RSPT RSPF RSPH RSPD RSPS RSPN RSPG RSPC RSPM RSPR RSPU XLK XLF XLV XLY XLP XLI XLE XLC XLB XLRE XLU".split():
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request(f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=5d&interval=1d", headers={"User-Agent": "Mozilla/5.0"}), timeout=20))["chart"]["result"][0]["meta"]
        print(t, r.get("regularMarketPrice"), r.get("longName") or r.get("shortName"))
    except Exception as e:
        print(t, "ERR", e)
