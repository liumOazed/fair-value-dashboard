#!/usr/bin/env python3
"""Refresh data/prices.json for every ticker listed in data/assets.json.
Uses Yahoo Finance's public chart endpoint (no key needed). Keeps old values if a fetch fails."""
import json, sys, time, urllib.request, datetime, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
assets = json.loads((ROOT / "data/assets.json").read_text())["assets"]
try:   # also price every stock ever picked in the monthly Fair Value Table, so picks can be tracked
    _fv = json.loads((ROOT / "data/fair_value_table.json").read_text())["months"]
    _have = {a["ticker"] for a in assets}
    for _m in _fv.values():
        for _p in _m["picks"]:
            if _p["ticker"] not in _have: assets.append({"ticker": _p["ticker"]}); _have.add(_p["ticker"])
except Exception: pass
pfile = ROOT / "data/prices.json"
try: out = json.loads(pfile.read_text())
except Exception: out = {"prices": {}}
def fetch(t):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=3mo&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    r = json.load(urllib.request.urlopen(req, timeout=20))["chart"]["result"][0]
    closes = [c for c in r["indicators"]["quote"][0]["close"] if c is not None]
    price = r["meta"]["regularMarketPrice"]
    prev = closes[-2] if len(closes) > 1 else price
    return dict(price=round(price, 2), prev_close=round(prev, 2), history=[round(c, 2) for c in closes[-65:]])
ok = 0
for a in assets:
    t = a["ticker"]
    try:
        out["prices"][t] = fetch(t); ok += 1; print("ok", t, out["prices"][t]["price"])
    except Exception as e:
        print("FAILED", t, e, file=sys.stderr)
    time.sleep(0.5)
if ok:
    out["updated"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    out["source"] = "Yahoo Finance (delayed)"
    pfile.write_text(json.dumps(out, indent=1))
sys.exit(0 if ok else 1)
