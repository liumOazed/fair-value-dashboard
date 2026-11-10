#!/usr/bin/env python3
"""Merge model/results.json into data/assets.json (keeps existing entries' extra fields, never touches prices).
New tickers are added; run after `python model/model.py`. Per-ticker valued_on comes from VALUED (default: results as_of)."""
import json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
res = json.load(open(ROOT / "model/results.json"))
_M = json.load(open(ROOT / "data/moat.json"))["classes"]
MOAT_NOTE = {k: v.get("about") for k, v in _M.items()}
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
    if "detail" in a and a.get("type") == "stock":
        rnd = lambda x, n=3: round(float(x), n)
        e["forecast"] = {k: dict(rows=[dict(t=r["t"], g=rnd(r["g"], 4), rev=rnd(r["rev"]), m=rnd(r["m"], 4), fcf=rnd(r["fcf"]), df=rnd(r["df"], 4), pv=rnd(r["pv"]))
                                       for r in v["rows"]], pv_fcf=rnd(v["pv_fcf"]), tv=rnd(v["tv"]), pv_tv=rnd(v["pv_tv"]), ev=rnd(v["ev"]),
                                  equity=rnd(v["equity"]), per_share=rnd(v["per_share"], 2), tv_factor=rnd(v.get("tv_factor", 1.0), 4)) for k, v in a["detail"].items()}
        e["start_margin"] = rnd(a["start_margin"], 4); e["net_cash"] = rnd(a["net_cash"]); e["shares"] = a["shares"]; e["rev"] = a["rev"]
        e["dcf_method"] = a.get("dcf_method"); e["wacc"] = {k: rnd(v, 4) for k, v in a.get("wacc", {}).items()}
        e["fcf_inputs"] = dict(fcf=a["fcf"], sbc=a["sbc"])
        e["moat"] = a.get("moat"); e["cap_years"] = a.get("cap_years"); e["moat_reason"] = a.get("moat_reason")
        e["moat_note"] = MOAT_NOTE.get(a.get("moat"))
        sgm = a.get("segments")
        e["segments"] = None if not sgm else dict(names=sgm["names"], share=[rnd(x, 4) for x in sgm["share"]], reported=rnd(sgm["reported"], 4),
                                                  g1={k: [rnd(x, 4) for x in v] for k, v in sgm["g1"].items()}, period=sgm["period"], source=sgm["source"],
                                                  engines=None if not sgm.get("engines") else dict(sgm["engines"], x=[rnd(x, 4) for x in sgm["engines"]["x"]]))
        if a.get("method") == "excess_roe":      # underwriters (model.py INSURERS): book value and return on equity
            e["method"] = "excess_roe"; e["kind"] = a.get("kind")
            e["insurer"] = {k: (rnd(v, 4) if isinstance(v, float) else {kk: rnd(vv, 4) for kk, vv in v.items()} if isinstance(v, dict) else v)
                            for k, v in a["insurer"].items()}
            for k, v in a["detail"].items():
                e["forecast"][k].update(ni=[rnd(r["ni"]) for r in v["rows"]], bv0=rnd(v["bv0"]), roe_terminal=rnd(v["roe_terminal"], 4),
                                        excess=rnd(v["excess"]))
        e["implied_cap"] = a.get("implied_cap"); e["nopat_margin"] = rnd(a["nopat_margin"], 4) if a.get("nopat_margin") is not None else None
        e["growth_check"] = {k: (None if v is None else dict(forecast=None if v["forecast"] is None else rnd(v["forecast"], 4),
                                                          terminal=None if v["terminal"] is None else rnd(v["terminal"], 4),
                                                          reinvest_share=rnd(v["reinvest_share"], 4), flag=v["flag"]))
                             for k, v in (a.get("growth_check") or {}).items()} if a.get("growth_check") else None
    if "rate_table" in a:
        e["rate_table"] = [dict(r=x["r"], fv=round(x["fv"], 2), **{k: round(x[k], 2) for k in ("bear", "base", "bull") if k in x}) for x in a["rate_table"]]
        if a.get("wacc_row"):   # value at the blended WACC (Capital and returns card)
            w = a["wacc_row"]; e["wacc_row"] = dict(r=round(w["r"], 4), fv=round(w["fv"], 2), **{k: round(w[k], 2) for k in ("bear", "base", "bull")})
        e["required_return_reason"] = a.get("r_reason")
    if "sens" in a:
        e["sensitivity"] = dict(r=[round(x, 4) for x in a["sens"]["r"]], g=a["sens"]["g"], grid=[[round(x, 1) for x in row] for row in a["sens"]["grid"]])
    by[t] = e
doc["assets"] = list(by.values())
json.dump(doc, open(path, "w"), indent=1)
# fair value history: one point per ticker per valuation (date, fair value, bear/base/bull, price on the day), appended
hp = ROOT / "data/fv_history.json"
hist = json.load(open(hp)) if hp.exists() else {"_about": "Fair value recorded at each model refresh (export_assets.py). Price = live price when exported."}
prices = json.load(open(ROOT / "data/prices.json")).get("prices", {})
for t, e in by.items():
    if only and t not in only: continue
    pt = dict(date=e["valued_on"], fv=e["fair_value"], bear=e["bear"], base=e["base"], bull=e["bull"],
              price=(prices.get(t) or {}).get("price"), method=e.get("dcf_method"))
    L = hist.setdefault(t, [])
    if L and L[-1]["date"] == pt["date"]:
        L[-1] = pt                      # same valuation date: keep the latest numbers
    elif not L or abs(L[-1]["fv"] - pt["fv"]) > 1e-9 or L[-1]["date"] != pt["date"]:
        L.append(pt)
json.dump(hist, open(hp, "w"), indent=1)
print("updated", sorted(only) if only else "all", "->", len(doc["assets"]), "assets")
