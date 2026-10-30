#!/usr/bin/env python3
"""Earnings watch: which modelled companies have published a quarter newer than their fair-value model?

1. Earnings calendar (Yahoo via yfinance, runs on GitHub): last and next report date for every stock in
   data/assets.json -> data/earnings_calendar.json.
2. Pending list -> data/pending_reports.json: a company is pending when it has reported AFTER the quarter its
   model already covers (data/data_through.json). A report on date d covers a quarter that ended roughly 2-10
   weeks earlier, so it is "newer" when d - 70 days is after data_through.
The daily Claude task reads the pending list, updates those models from the companies' own filings (SEC 8-K /
10-Q, investor-relations releases), advances data_through and re-runs this script.

Usage: python scripts/earnings_watch.py            (calendar + pending)
       python scripts/earnings_watch.py --pending  (pending list only, from the saved calendar)
"""
import argparse, datetime as dt, json, pathlib, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
LAG = 70           # days: a report filed d covers a quarter ending after d - LAG
TODAY = dt.datetime.now(dt.timezone.utc).date()


def stocks():
    return [a["ticker"] for a in json.load(open(ROOT / "data/assets.json"))["assets"] if a.get("type") == "stock"]


def dates_for(t):
    """Past and future earnings dates from Yahoo (several fallbacks, Yahoo's endpoints change often)."""
    import yfinance as yf
    tk = yf.Ticker(t)
    past, fut = set(), set()
    try:
        df = tk.get_earnings_dates(limit=12)
        if df is not None and len(df):
            for ts in df.index:
                d = ts.date()
                (past if d <= TODAY else fut).add(d)
    except Exception:
        pass
    try:
        cal = tk.calendar or {}
        for d in (cal.get("Earnings Date") or []):
            d = d if isinstance(d, dt.date) else dt.date.fromisoformat(str(d)[:10])
            (past if d <= TODAY else fut).add(d)
    except Exception:
        pass
    mrq = None
    try:
        info = tk.info or {}
        for k in ("earningsTimestamp", "earningsTimestampStart", "earningsTimestampEnd"):
            v = info.get(k)
            if v:
                d = dt.datetime.fromtimestamp(v, dt.timezone.utc).date()
                (past if d <= TODAY else fut).add(d)
        v = info.get("mostRecentQuarter")
        mrq = dt.datetime.fromtimestamp(v, dt.timezone.utc).date().isoformat() if v else None
    except Exception:
        pass
    return dict(last_report=max(past).isoformat() if past else None, next_report=min(fut).isoformat() if fut else None,
                yahoo_latest_quarter=mrq, past=sorted(d.isoformat() for d in past)[-6:])


def calendar_update():
    cal = {}
    for t in stocks():
        try:
            cal[t] = dates_for(t)
        except Exception as e:
            cal[t] = {"error": str(e)}
        print(t, cal[t].get("last_report"), "->", cal[t].get("next_report"))
        time.sleep(0.5)
    json.dump({"updated": TODAY.isoformat(), "source": "Yahoo Finance via yfinance", "stocks": cal},
              open(ROOT / "data/earnings_calendar.json", "w"), indent=1)


def pending_update():
    cal = json.load(open(ROOT / "data/earnings_calendar.json"))["stocks"]
    thr = {k: v for k, v in json.load(open(ROOT / "data/data_through.json")).items() if not k.startswith("_")}
    pend, upcoming = [], []
    for t in stocks():
        c, through = cal.get(t, {}), thr.get(t)
        if not through:
            continue
        newer = [d for d in c.get("past", []) if dt.date.fromisoformat(d) - dt.timedelta(days=LAG) > dt.date.fromisoformat(through)]
        # Yahoo's own statements already show a newer quarter: also pending (covers a missing calendar)
        yq = c.get("yahoo_latest_quarter")
        if newer or (yq and yq > through):
            pend.append(dict(ticker=t, data_through=through, reported_on=max(newer) if newer else None, yahoo_latest_quarter=yq,
                             waiting_days=(TODAY - dt.date.fromisoformat(max(newer))).days if newer else None))
        elif c.get("next_report"):
            upcoming.append(dict(ticker=t, next_report=c["next_report"], data_through=through))
    pend.sort(key=lambda x: x["reported_on"] or "")
    upcoming.sort(key=lambda x: x["next_report"])
    json.dump({"updated": TODAY.isoformat(), "rule": f"reported on d with d - {LAG} days after data_through (or Yahoo already shows a newer quarter)",
               "pending": pend, "upcoming": upcoming}, open(ROOT / "data/pending_reports.json", "w"), indent=1)
    print("pending:", [p["ticker"] for p in pend])
    print("next up:", [(u["ticker"], u["next_report"]) for u in upcoming[:10]])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--pending", action="store_true")
    a = ap.parse_args()
    if not a.pending:
        calendar_update()
    pending_update()
