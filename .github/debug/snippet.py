# 10-K facts (as first reported) and monthly prices for the 9 Russell 2000 stocks that pass all 5 checks,
# printed as one JSON line so they can be merged into data/backtest/facts.json.gz and prices.json.gz.
import json, os, sys, time, gzip, base64
sys.path.insert(0, "scripts")
import bt_fetch as B
B.UA_SEC = {"User-Agent": "fair-value-dashboard/1.0 (github.com/liumOazed/fair-value-dashboard)", "Accept-Encoding": "gzip"}
B.CACHE.mkdir(exist_ok=True)
T = ["INVA", "CTRE", "CVSA", "QLYS", "LAUR", "IDCC", "LMAT", "BOX", "ACIW"]
tick = json.loads(B.get("https://www.sec.gov/files/company_tickers.json", B.UA_SEC))
cik_of = {v["ticker"].replace(".", "-"): int(v["cik_str"]) for v in tick.values()}
facts, px = {}, {}
for t in T:
    cik = cik_of.get(t)
    print("ticker", t, "cik", cik, file=sys.stderr)
    if cik:
        try:
            f = B.company_facts(cik); facts[t] = dict(cik=cik, **f)
            print(t, {k: len(v) for k, v in f.items()}, file=sys.stderr)
        except Exception as e: print("facts failed", t, e, file=sys.stderr)
    time.sleep(0.3)
    try: px[t] = B.prices(t)
    except Exception as e: print("prices failed", t, e, file=sys.stderr)
    time.sleep(0.3)
sys.stderr.flush()
print("PAYLOAD " + base64.b64encode(gzip.compress(json.dumps(dict(facts=facts, prices=px)).encode())).decode())
