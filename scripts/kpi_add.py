#!/usr/bin/env python3
"""Add or replace business-driver (KPI) values in data/kpis.json, with validation.

Input: a JSON file with a list of points, e.g.
  [{"ticker": "MSFT", "kpi": "azure_other_cloud_services_growth", "period": "2026-09-30", "label": "Q1 FY27",
    "value": 48, "source": "https://www.sec.gov/...", "quote": "Azure and other cloud services revenue increased 48%"}]
Rules (checked):
  * ticker and kpi id must exist in data/kpi_defs.json
  * period = fiscal quarter end, YYYY-MM-DD; label = how the company names the quarter
  * value: a number for every unit except "text" (pct values are percentages: 48 means 48%; usd_b in billions)
  * source must be a URL to the company's release/filing; quote = the exact sentence or table line the value comes from
  * the same ticker + kpi + period replaces the old point (corrections are allowed and logged)
Usage: python scripts/kpi_add.py points.json        (prints what was added / replaced / rejected)
       python scripts/kpi_add.py --check             (validate the whole file)
"""
import datetime as dt, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFS = json.load(open(ROOT / "data/kpi_defs.json"))["stocks"]
PATH = ROOT / "data/kpis.json"


def problem(p):
    t, k = p.get("ticker"), p.get("kpi")
    if t not in DEFS: return f"unknown ticker {t}"
    d = next((x for x in DEFS[t]["kpis"] if x["id"] == k), None)
    if not d: return f"unknown kpi {k} for {t}"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(p.get("period", ""))): return "period must be YYYY-MM-DD"
    v = p.get("value")
    if d["unit"] == "text":
        if not isinstance(v, str) or not v.strip(): return "text KPI needs a text value"
    elif not isinstance(v, (int, float)) or isinstance(v, bool): return f"value must be a number for unit {d['unit']}"
    if not str(p.get("source", "")).startswith("http"): return "source URL missing"
    if len(str(p.get("quote", ""))) < 8: return "quote missing"
    return None


def main():
    doc = json.load(open(PATH))
    S = doc.setdefault("stocks", {})
    if sys.argv[1:] == ["--check"]:
        bad = [(t, k, pt.get("period"), problem(dict(pt, ticker=t, kpi=k))) for t, ks in S.items() for k, pts in ks.items() for pt in pts]
        bad = [b for b in bad if b[3]]
        print("ok" if not bad else bad); sys.exit(1 if bad else 0)
    pts = json.load(open(sys.argv[1]))
    added = replaced = 0
    for p in pts:
        why = problem(p)
        if why:
            print("REJECTED", p.get("ticker"), p.get("kpi"), p.get("period"), "-", why); continue
        L = S.setdefault(p["ticker"], {}).setdefault(p["kpi"], [])
        rec = {k: p[k] for k in ("period", "label", "value", "source", "quote") if k in p}
        rec["added"] = dt.date.today().isoformat()
        old = next((i for i, x in enumerate(L) if x["period"] == p["period"]), None)
        if old is None:
            L.append(rec); added += 1
        else:
            if L[old].get("value") != rec["value"]:
                print("REPLACED", p["ticker"], p["kpi"], p["period"], L[old].get("value"), "->", rec["value"])
            L[old] = rec; replaced += 1
        L.sort(key=lambda x: x["period"])
    json.dump(doc, open(PATH, "w"), indent=1, ensure_ascii=False)
    print(f"added {added}, replaced {replaced}, total points {sum(len(v) for ks in S.values() for v in ks.values())}")


if __name__ == "__main__":
    main()
