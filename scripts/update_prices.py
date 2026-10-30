#!/usr/bin/env python3
"""Refresh data/prices.json for every ticker listed in data/assets.json.
Uses Yahoo Finance's public chart endpoint (no key needed). Keeps old values if a fetch fails.
Runs every 30 minutes on US trading days: while the market is open the price is the latest (delayed) trade,
after the close it is the official close. data/prices.json "market" records which one it is."""
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
    bars = [(ts, c) for ts, c in zip(r.get("timestamp") or [], r["indicators"]["quote"][0]["close"]) if c is not None]
    closes = [c for _, c in bars]
    m = r["meta"]
    price = m["regularMarketPrice"]
    # previous session's close: the last daily bar is today's (partial) session once trading has started
    days = [datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).date() for ts, _ in bars]
    tday = datetime.datetime.fromtimestamp(m.get("regularMarketTime", 0), datetime.timezone.utc).date()
    prev = closes[-2] if len(closes) > 1 and (not days or days[-1] == tday) else (closes[-1] if closes else price)
    global MARKET
    if MARKET is None and m.get("currentTradingPeriod"):
        reg, now = m["currentTradingPeriod"]["regular"], time.time()
        MARKET = dict(state="open" if reg["start"] <= now < reg["end"] else "closed",
                      session_start=datetime.datetime.fromtimestamp(reg["start"], datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      session_end=datetime.datetime.fromtimestamp(reg["end"], datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    return dict(price=round(price, 2), prev_close=round(prev, 2), history=[round(c, 2) for c in closes[-65:]],
                time=datetime.datetime.fromtimestamp(m.get("regularMarketTime", 0), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
MARKET = None
ok = changed = 0
for a in assets:
    t = a["ticker"]
    try:
        new = fetch(t); ok += 1
        if out["prices"].get(t, {}).get("price") != new["price"] or out["prices"].get(t, {}).get("prev_close") != new["prev_close"]:
            changed += 1
        out["prices"][t] = new; print("ok", t, new["price"])
    except Exception as e:
        print("FAILED", t, e, file=sys.stderr)
    time.sleep(0.5)
if ok and (changed or (MARKET or {}).get("state") != (out.get("market") or {}).get("state")):
    out["updated"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    if MARKET:
        MARKET["as_of"] = max(v.get("time", "") for v in out["prices"].values())
        out["market"] = MARKET
    out["source"] = "Yahoo Finance (delayed)"
    pfile.write_text(json.dumps(out, indent=1))
print("changed:", changed, "market:", MARKET)
sys.exit(0 if ok else 1)
