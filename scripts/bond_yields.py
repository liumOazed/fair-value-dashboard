#!/usr/bin/env python3
"""Bond yields for the "advantage over bonds" card -> data/bond_yields.json.

From FRED (St. Louis Fed), no API key needed:
  GS10  10-year US Treasury constant-maturity yield, monthly average
  AAA   Moody's seasoned Aaa corporate bond yield, monthly average (the safest company bonds)
Keeps monthly values from 2000 and the average of each calendar year. If a download fails the old values are kept.
Usage: python scripts/bond_yields.py
"""
import csv, datetime, io, json, pathlib, statistics as st, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/bond_yields.json"
SERIES = {"GS10": "10-year Treasury", "AAA": "Moody's Aaa corporate"}
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"

def fetch(sid):
    req = urllib.request.Request(URL.format(sid), headers={"User-Agent": "fair-value-dashboard (github.com/liumOazed/fair-value-dashboard)"})
    txt = urllib.request.urlopen(req, timeout=60).read().decode()
    out = {}
    for row in csv.DictReader(io.StringIO(txt)):
        d = row.get("observation_date") or row.get("DATE")
        v = row.get(sid)
        if d and d >= "2000" and v not in (None, "", "."):
            out[d[:7]] = round(float(v), 3)
    if len(out) < 100: raise ValueError(f"{sid}: only {len(out)} months")
    return out

old = json.load(open(OUT)) if OUT.exists() else {}
doc = {"_about": "Monthly averages in percent from FRED (GS10 = 10-year Treasury, AAA = Moody's seasoned Aaa corporate). "
                 "annual = calendar-year average (partial for the current year). Built by scripts/bond_yields.py.",
       "source": "https://fred.stlouisfed.org", "names": SERIES, "fetched": old.get("fetched", {}), "monthly": {}, "annual": {}}
for sid in SERIES:
    try:
        doc["monthly"][sid] = fetch(sid)
        doc["fetched"][sid] = datetime.date.today().isoformat()
        print(f"{sid}: {len(doc['monthly'][sid])} months, latest {max(doc['monthly'][sid])} = {doc['monthly'][sid][max(doc['monthly'][sid])]}%")
    except Exception as e:
        print(f"{sid}: download failed ({e}); keeping the previous values")
        doc["monthly"][sid] = (old.get("monthly") or {}).get(sid, {})
    by = {}
    for m, v in doc["monthly"][sid].items(): by.setdefault(m[:4], []).append(v)
    doc["annual"][sid] = {y: round(st.mean(v), 3) for y, v in sorted(by.items())}
if any(doc["monthly"].values()):
    json.dump(doc, open(OUT, "w"), indent=1)
