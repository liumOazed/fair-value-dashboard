#!/usr/bin/env python3
"""Merge model/results.json into data/assets.json (keeps existing entries' extra fields, never touches prices).
New tickers are added; run after `python model/model.py`. Per-ticker valued_on comes from VALUED (default: results as_of)."""
import json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
res = json.load(open(ROOT / "model/results.json"))
path = ROOT / "data/assets.json"
doc = json.load(open(path))
by = {a["ticker"]: a for a in doc["assets"]}
only = set(sys.argv[1:])           # optional: only refresh these tickers
for t, a in res["assets"].items():
    if only and t not in only: continue
    e = by.get(t, {"ticker": t})
    e.update(name=a["name"], type=a["type"], fair_value=round(a["fair_value"], 2), bear=round(a["bear"], 2), base=round(a["base"], 2),
             bull=round(a["bull"], 2), mos=a["mos"], buy_below=round(a["fair_value"] * (1 - a["mos"]), 2), required_return=a["r"],
             epv=round(a["epv"], 2) if a.get("epv") else None, implied_return=round(a["implied_irr"], 4) if a.get("implied_irr") else None,
             reverse_g1=round(a["reverse_g1"], 4) if a.get("reverse_g1") else None, tv_share=round(a["tv_share"], 3) if a.get("tv_share") else None,
             notes=a["notes"], valued_on=res["as_of"], scenarios=a["scen"])
    if "sens" in a:
        e["sensitivity"] = dict(r=[round(x, 4) for x in a["sens"]["r"]], g=a["sens"]["g"], grid=[[round(x, 1) for x in row] for row in a["sens"]["grid"]])
    by[t] = e
doc["assets"] = list(by.values())
json.dump(doc, open(path, "w"), indent=1)
print("updated", sorted(only) if only else "all", "->", len(doc["assets"]), "assets")
