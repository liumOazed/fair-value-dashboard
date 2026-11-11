#!/usr/bin/env python3
"""Rule-based bear / base / bull scenarios -> data/scenarios_rule.json. From November 2026 these are the model's default
scenarios (model/model.py reads this file); a stock listed in data/scenario_overrides.json keeps its hand-written ones.

The hand-written scenarios in model/model.py (year-1 growth g1, year-10 growth g10, target cash margin m) move fair
value more than anything else. This script sets the same three inputs from data with fixed rules, values every stock
with the model's own engine (model.dcf via stock_setup: same required return, advantage period, segments, cash-flow
separation and 30/50/20 weights) and records the rule-based and hand-written values side by side.

Rules
  base rates      S&P 500 companies 2007-2025 (data/backtest/facts.json.gz) grouped by 3-year revenue growth and
                  revenue size (under $5B, $5-25B, over $25B; a group with under 30 cases uses all sizes)
  year-1 growth   base = analysts' revenue growth for next fiscal year (Yahoo 'revenue_estimate' +1y; the current
                  year if next is missing; with fewer than 2 analysts, the 3-year revenue growth rate), kept inside
                  the 20th-80th percentile of the group's next-3-year growth
                  bear / bull = base + the group's 20th / 80th percentile spread (vs its median)
  year-10 growth  the group's 20th / 50th / 80th percentile growth in years 6-10, capped by size because the base
                  rates only hold companies still in the S&P 500 (survivors): base 6.5% / 5.5% / 4.5% for revenue
                  under $5B / $5-25B / over $25B, bull 1.5 points above, bear 1.5 points below; also capped at the
                  scenario's own year-1 growth (2.5% minimum)
  cash margin     (free cash flow - stock pay) / revenue over the last 4 fiscal years and the last 12 months:
                  bear = 20th percentile, bull = 80th percentile, base = halfway between the median and the recent
                  level (average of the latest fiscal year and the last 12 months). If the after-tax operating margin
                  is higher (heavy investment now), base = halfway to it and bull = at least it.
                  Lenders (AXP, AMP): net income
Base rates come from companies that are in the S&P 500 today, so they flatter growth (survivorship).
Usage: python scripts/scenario_rules.py   (BEFORE model/model.py, which reads the result)
"""
import json, gzip, glob, pathlib, datetime as dt
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
_src = (ROOT / "model/model.py").read_text()
M = {"__file__": str(ROOT / "model/model.py"), "__name__": "scenario_rules"}
exec(compile(_src.split('\nout = {"as_of"')[0], "model.py", "exec"), M)
STOCKS, PROBS, GT = M["STOCKS"], M["PROBS"], M["GT"]
SNAP = json.load(open(ROOT / "data/snapshot_raw.json"))["stocks"]
G10_CAP = [0.065, 0.055, 0.045]               # base-case year-10 growth cap by size (SIZES); bear -1.5 pt, bull +1.5 pt
G10_STEP = 0.015
BUCKETS = [(-9, 0), (0, .05), (.05, .10), (.10, .15), (.15, .25), (.25, .40), (.40, 99)]   # 3-year revenue growth
SIZES = [(0, 5), (5, 25), (25, 1e6)]                                                        # revenue, $B
MIN_N = 30                                    # fewer observations than this: pool all sizes for that growth bucket

def bucket(x): return next(j for j, (lo, hi) in enumerate(BUCKETS) if lo <= x < hi)
def size(rev_b): return next(j for j, (lo, hi) in enumerate(SIZES) if lo <= rev_b < hi)

def base_rates():
    """Per (3-year growth bucket, revenue size): 20/50/80th percentiles of growth over the next 3 years and in years
    6-10. Cells with too few observations use the growth bucket's figures across all sizes."""
    f = json.load(gzip.open(ROOT / "data/backtest/facts.json.gz"))
    obs = {(g, z): dict(next3=[], late=[]) for g in range(len(BUCKETS)) for z in range(len(SIZES))}
    for v in f.values():
        ys = sorted((dt.date.fromisoformat(k), x[0]) for k, x in (v.get("revenue") or {}).items() if x and x[0] and x[0] > 0)
        s, last = [], None
        for d, x in ys:                                   # one point per fiscal year
            if last is None or (d - last).days > 300: s.append(x); last = d
        for i in range(3, len(s)):
            c = obs[(bucket((s[i] / s[i - 3]) ** (1 / 3) - 1), size(s[i] / 1e9))]
            if i + 3 < len(s): c["next3"].append((s[i + 3] / s[i]) ** (1 / 3) - 1)
            if i + 10 < len(s): c["late"].append((s[i + 10] / s[i + 5]) ** (1 / 5) - 1)
    q = lambda a: [float(x) for x in np.percentile(a, [20, 50, 80])]
    out = {}
    for (g, z), c in obs.items():
        e = dict(growth=list(BUCKETS[g]), size_b=list(SIZES[z]))
        for k in ("next3", "late"):
            a, pooled = c[k], False
            if len(a) < MIN_N: a, pooled = [x for zz in range(len(SIZES)) for x in obs[(g, zz)][k]], True
            e[k] = q(a); e["n_" + k] = len(a); e["pooled_" + k] = pooled
        out[f"{g},{z}"] = e
    return out

def latest_inputs():
    """Newest Yahoo inputs record per ticker across data/inputs/*.json (file names sort by date)."""
    out = {}
    for p in sorted(glob.glob(str(ROOT / "data/inputs/inputs_*.json"))):
        d = json.load(open(p)); d = d.get("stocks", d)
        for t, v in d.items():
            if isinstance(v, dict) and v.get("revenue_estimate"): out[t] = dict(v, _file=pathlib.Path(p).name)
    return out

def history(t, s):
    """Annual (year, revenue, cash margin) for the last 4 fiscal years + the model's TTM point; 3-year revenue growth."""
    a = SNAP.get(t, {}).get("annual", {}); inc, cfs = a.get("inc", {}), a.get("cfs", {})
    pts = []
    for y in sorted(inc):
        rev = (inc[y] or {}).get("rev"); c = cfs.get(y) or {}
        if not rev: continue
        if t in M["LENDERS"]:
            ni = inc[y].get("ni")
            if ni is not None: pts.append((y, rev, ni / rev))
        elif c.get("fcf") is not None:
            pts.append((y, rev, (c["fcf"] - (c.get("sbc") or 0)) / rev))
    revs = [p[1] for p in pts]
    g3 = (revs[-1] / revs[-4]) ** (1 / 3) - 1 if len(revs) >= 4 and revs[-4] > 0 else (revs[-1] / revs[0]) ** (1 / max(len(revs) - 1, 1)) - 1 if len(revs) >= 2 else None
    ttm = (s["fcf"] - s["sbc"]) / s["rev"]
    return pts, g3, ttm

def analyst_g1(inp, g3):
    re_ = (inp or {}).get("revenue_estimate") or {}
    g, n = re_.get("growth") or {}, re_.get("numberOfAnalysts") or {}
    for k in ("+1y", "0y"):
        if g.get(k) is not None and (n.get(k) or 0) >= 2: return float(g[k]), f"analysts {k} ({int(n[k])})"
    return (g3, "3-year history") if g3 is not None else (None, "none")

def rule_scen(t, s, br, inp):
    pts, g3, ttm = history(t, s)
    g1a, src = analyst_g1(inp, g3)
    if g1a is None: return None
    cell = br[f"{bucket(g3 if g3 is not None else g1a)},{size(s['rev'])}"]
    n3 = cell["next3"]
    g1b = min(max(g1a, n3[0]), n3[2])               # analysts, kept inside what similar companies actually did
    d_lo, d_hi = n3[0] - n3[1], n3[2] - n3[1]
    bl = cell["late"]
    ms = [p[2] for p in pts] + [ttm]
    mq = [float(x) for x in np.percentile(ms, [20, 50, 80])]
    recent = sum(ms[-2:]) / len(ms[-2:])            # latest fiscal year and TTM: where the margin is now
    mq[1] = (mq[1] + recent) / 2; mq[0] = min(mq[0], mq[1]); mq[2] = max(mq[2], mq[1])
    nm = None if t in M["LENDERS"] else M["nopat_margin"](t, M["FIN"][t]["tax"])
    if nm is not None and nm > mq[1]:              # investing heavily: cash margin below after-tax operating profit
        mq[1] = (mq[1] + nm) / 2; mq[2] = max(mq[2], nm)
    sc = {}
    for i, k in enumerate(("bear", "base", "bull")):
        g1 = g1b + (d_lo, 0.0, d_hi)[i]
        g10 = min(bl[i], G10_CAP[size(s["rev"])] + (-G10_STEP, 0.0, G10_STEP)[i], max(g1, GT))
        sc[k] = dict(g1=round(g1, 4), g10=round(g10, 4), m=round(mq[i], 4))
    why = dict(g1_source=src, g1_analysts=round(g1a, 4), g1_base=round(g1b, 4), nopat_margin=None if nm is None else round(nm, 4),
               cell=dict(growth=cell["growth"], size_b=cell["size_b"], n=cell["n_next3"], pooled=cell["pooled_next3"]), g3=None if g3 is None else round(g3, 4), margins=[round(x, 4) for x in ms],
               margin_years=[p[0] for p in pts] + ["TTM"], inputs_file=(inp or {}).get("_file"))
    return sc, why

def value(t, scen):
    s = dict(STOCKS[t], scen=scen); r = M["req_return"](t)    # stock_setup reads the scenarios from s["scen"]
    mo = dict(M["moat_of"](t), r_req=r); sg = M["segments_of"](t); su = M["stock_setup"](t, s)
    v = {k: M["dcf"](s["rev"], su["m0"], p["g1"], p["g10"], p["m"], r, su["nc"], s["shares"], mo=mo, sg=sg, **su["kw"])
         for k, p in su["S2"].items()}
    return sum(PROBS[k] * v[k] for k in PROBS), v

def main():
    br = base_rates(); inp = latest_inputs()
    out = dict(as_of=dt.date.today().isoformat(), rules=__doc__.split("Rules\n")[1].split("Usage:")[0].strip(),
               base_rates=br, stocks={})
    for t, s in STOCKS.items():
        r = rule_scen(t, s, br, inp.get(t))
        if not r: continue
        sc, why = r
        fv, v = value(t, sc)
        hs = s.get("scen_hand", s["scen"])            # the hand-written scenarios (model.py keeps them as scen_hand)
        hf, hv = value(t, hs)
        out["stocks"][t] = dict(scen=sc, why=why, fair_value=round(fv, 2), **{k: round(v[k], 2) for k in v},
                                hand=dict(scen=hs, fair_value=round(hf, 2), **{k: round(hv[k], 2) for k in hv}),
                                diff=round(fv / hf - 1, 4) if hf > 0 else None)
    json.dump(out, open(ROOT / "data/scenarios_rule.json", "w"), indent=1)
    d = [x["diff"] for x in out["stocks"].values() if x["diff"] is not None]
    print(f"scenarios_rule.json: {len(out['stocks'])} stocks; rule vs hand fair value median {np.median(d):+.1%}, "
          f"within 15%: {sum(abs(x) <= .15 for x in d)}, rule higher by >15%: {sum(x > .15 for x in d)}, lower: {sum(x < -.15 for x in d)}")

if __name__ == "__main__":
    main()
