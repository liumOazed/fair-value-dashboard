#!/usr/bin/env python3
"""Forward test (P2): record every signal the dashboard makes, with its entry price, then measure it against SPY.

Nothing is back-filled with hindsight: a group is recorded the day it is made, using that day's price, and never
changed afterwards. Groups recorded each month:
  top5        Monthly Top 5 fair-value picks (entry = price on the evaluation day, already stored by the picker)
  top50       Growth Screen top 50 (equal weight)
  resilient   the 5 resilient compounders
  fv_below    full-model stocks trading below fair value
  fv_buy      full-model stocks trading below their buy-below price (inside the margin of safety)
Benchmark: SPY, bought on the same day as each group. Returns are price-only (dividends excluded on both sides).

  python scripts/track.py --snapshot     record this month's groups (once per month; existing groups are kept)
  python scripts/track.py --update       refresh current prices and data/tracking/performance.json
"""
import argparse, datetime, json, pathlib, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
TD = ROOT / "data/tracking"
UA = {"User-Agent": "Mozilla/5.0"}

def _chart(t, q):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?{q}"
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20))["chart"]["result"][0]

def price_now(t):
    try:
        return round(_chart(t, "range=5d&interval=1d")["meta"]["regularMarketPrice"], 2)
    except Exception:
        try: return json.load(open(ROOT / "data/prices.json"))["prices"][t]["price"]
        except Exception: return None

def close_on(t, day):
    """Close on `day` (or the next trading day) - used for SPY on a past evaluation day."""
    try:
        d0 = int(datetime.datetime.fromisoformat(day).replace(tzinfo=datetime.timezone.utc).timestamp())
        r = _chart(t, f"period1={d0}&period2={d0 + 6 * 86400}&interval=1d")
        closes = [c for c in r["indicators"]["quote"][0]["close"] if c is not None]
        return round(closes[0], 2) if closes else None
    except Exception:
        return None

def snapshot():
    today = datetime.date.today().isoformat()
    S = json.load(open(ROOT / "data/screen.json"))
    A = json.load(open(ROOT / "data/assets.json"))["assets"]
    month = S["month"]
    f = TD / f"{month}.json"
    snap = json.load(open(f)) if f.exists() else {"month": month, "groups": {}}
    G = snap["groups"]
    def add(name, label, tickers, entry_date, entry=None):
        if name in G:
            print(f"{name}: already recorded for {month}, kept"); return
        px = {t: (entry or {}).get(t) or price_now(t) for t in tickers}
        spy = price_now("SPY") if entry_date == today else close_on("SPY", entry_date)
        G[name] = dict(label=label, date=entry_date, spy=spy, stocks=[dict(ticker=t, entry=px[t]) for t in tickers])
        print(f"{name}: recorded {len(tickers)} stocks on {entry_date}, SPY {spy}")
        time.sleep(0.2)
    try:
        T = json.load(open(ROOT / "data/fair_value_table.json"))["months"].get(month)
    except Exception:
        T = None
    if T and T.get("picks"):
        add("top5", "Monthly Top 5 picks", [p["ticker"] for p in T["picks"]], T["evaluated"], {p["ticker"]: p["price_at_eval"] for p in T["picks"]})
    rows = S["rows"]
    add("top50", "Growth Screen top 50", [r["ticker"] for r in rows if r["top50"]], today)
    add("resilient", "Resilient compounders", [r["ticker"] for r in rows if r.get("resilient_pick")], today)
    P = {a["ticker"]: price_now(a["ticker"]) for a in A if a["type"] == "stock"}
    add("fv_below", "Full models: price below fair value", [a["ticker"] for a in A if a["type"] == "stock" and P[a["ticker"]] and P[a["ticker"]] <= a["fair_value"]], today, P)
    add("fv_buy", "Full models: price below buy-below", [a["ticker"] for a in A if a["type"] == "stock" and P[a["ticker"]] and P[a["ticker"]] <= a["buy_below"]], today, P)
    TD.mkdir(exist_ok=True)
    json.dump(snap, open(f, "w"), indent=1)

def update():
    snaps = sorted(TD.glob("20??-??.json"))
    tick = sorted({s["ticker"] for f in snaps for g in json.load(open(f))["groups"].values() for s in g["stocks"]} | {"SPY"})
    now = {}
    for t in tick:
        now[t] = price_now(t); time.sleep(0.2)
    out = dict(updated=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), spy=now["SPY"], groups=[])
    for f in snaps:
        snap = json.load(open(f))
        for key, g in snap["groups"].items():
            st = []
            for s in g["stocks"]:
                p = now.get(s["ticker"])
                ret = None if (p is None or not s["entry"]) else p / s["entry"] - 1
                st.append(dict(ticker=s["ticker"], entry=s["entry"], now=p, ret=None if ret is None else round(ret, 4)))
            rets = [x["ret"] for x in st if x["ret"] is not None]
            spy_ret = None if not (g["spy"] and now["SPY"]) else now["SPY"] / g["spy"] - 1
            ew = sum(rets) / len(rets) if rets else None
            days = (datetime.date.today() - datetime.date.fromisoformat(g["date"])).days
            out["groups"].append(dict(month=snap["month"], key=key, label=g["label"], date=g["date"], days=days, n=len(st),
                ret=None if ew is None else round(ew, 4), spy_ret=None if spy_ret is None else round(spy_ret, 4),
                excess=None if (ew is None or spy_ret is None) else round(ew - spy_ret, 4),
                beat=None if spy_ret is None or not rets else round(sum(r > spy_ret for r in rets) / len(rets), 3), stocks=st))
    json.dump(out, open(TD / "performance.json", "w"), indent=1)
    for g in out["groups"]:
        print(f"{g['month']} {g['key']:9} n={g['n']:2} ret={g['ret']} spy={g['spy_ret']} excess={g['excess']} beat={g['beat']}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--snapshot", action="store_true"); ap.add_argument("--update", action="store_true")
    a = ap.parse_args()
    if a.snapshot: snapshot()
    if a.update or a.snapshot: update()
    if not (a.snapshot or a.update): sys.exit("use --snapshot and/or --update")
