#!/usr/bin/env python3
"""Build data/screen.json from the monthly screen CSVs in data/screens/.

Score v2 ("Growth Quality Score") fixes the problems in the original growth_score:
  * every metric is ranked inside the stock's own sector (energy is compared with energy)
  * growth is counted once (no Rule of 40 double count) and capped at 60 so one-offs cannot dominate
  * cyclical sectors (Energy, Basic Materials) lean less on growth and more on cash generation
  * negative margins and missing valuation data are penalised
  * a 'consistent' badge marks stocks in the top 50 in BOTH of the latest two months
Quick indicator: the 10-year free-cash-flow growth the current price already assumes
(10% required return, 2.5% terminal growth). Indicative only, not a fair value.
Usage: python scripts/build_screen.py
"""
import glob, json, re, pathlib, datetime
import numpy as np, pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
CYCLICAL = {"Energy", "Basic Materials"}
R, GT = 0.10, 0.025

def pct_in_sector(df, col, higher_better=True):
    s = df[col]
    sec = df.groupby("sector")[col].rank(pct=True)
    allr = s.rank(pct=True)
    n = df.groupby("sector")[col].transform("count")
    out = np.where(n >= 8, sec, allr)            # small sectors fall back to the whole market
    out = pd.Series(out, index=df.index)
    if not higher_better: out = 1 - out
    return out.where(s.notna())

def score_v2(d):
    d = d.copy()
    d["g"] = d.rev_growth_pct.clip(-10, 60)
    d["roe_c"] = d.roe_pct.clip(-20, 60)
    d["fcf_c"] = d.fcf_yield_pct.clip(-10, 15)
    d["fpe_c"] = d.forward_pe.where((d.forward_pe > 0) & (d.forward_pe < 100))
    d["evx_c"] = d.ev_ebitda.where((d.ev_ebitda > 0) & (d.ev_ebitda < 100))
    comp = pd.DataFrame(index=d.index)
    comp["growth"] = pct_in_sector(d, "g")
    comp["profit"] = pd.concat([pct_in_sector(d, "profit_margin_pct"), pct_in_sector(d, "roe_c")], axis=1).mean(axis=1)
    comp["cash"] = pct_in_sector(d, "fcf_c")
    comp["value"] = pd.concat([pct_in_sector(d, "fpe_c", False), pct_in_sector(d, "evx_c", False)], axis=1).mean(axis=1)
    comp["quality"] = pct_in_sector(d, "gross_margin_pct")
    comp = comp.fillna(0.3)                       # missing data is not rewarded
    base_w = dict(growth=.30, profit=.25, cash=.20, value=.15, quality=.10)
    cyc_w = dict(growth=.15, profit=.25, cash=.35, value=.15, quality=.10)
    w = d.sector.map(lambda s: cyc_w if s in CYCLICAL else base_w)
    sc = sum(comp[k] * w.map(lambda x: x[k]) for k in base_w) * 100
    sc = sc - np.where(d.profit_margin_pct < 0, 10, 0) - np.where(d.pe_ratio.isna() & d.forward_pe.isna(), 5, 0)
    d["score"] = sc.clip(0, 100).round(1)
    d["flag_list"] = [[f for f, on in (("One-off growth?", g > 100), ("Loss-making", m < 0), ("Cyclical", s in CYCLICAL), ("Missing P/E", pd.isna(a) and pd.isna(b)))
                   if on] for g, m, s, a, b in zip(d.rev_growth_pct, d.profit_margin_pct, d.sector, d.pe_ratio, d.forward_pe)]
    return d

def implied_growth(y_pct):
    if y_pct is None or pd.isna(y_pct) or y_pct <= 0: return None
    y = y_pct / 100
    def f(g):
        s = sum(((1 + g) / (1 + R)) ** t for t in range(1, 11))
        tv = (1 + g) ** 10 * (1 + GT) / ((R - GT) * (1 + R) ** 10)
        return y * (s + tv) - 1
    lo, hi = -0.3, 0.8
    if f(hi) < 0: return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if f(mid) < 0: lo = mid
        else: hi = mid
    return round((lo + hi) / 2, 4)

def month_of(p): return re.search(r"(\d{4}-\d{2})", p).group(1)
files = sorted(glob.glob(str(ROOT / "data/screens/*.csv")), key=month_of)
if len(files) < 1: raise SystemExit("No CSVs in data/screens/")
months = [month_of(f) for f in files]
frames = {}
for f, m in zip(files, months):
    d = pd.read_csv(f).drop_duplicates("ticker").set_index("ticker", drop=False)
    d = score_v2(d); d["rank"] = d.score.rank(ascending=False, method="min").astype(int)
    d["old_rank"] = d.growth_score.rank(ascending=False, method="min").astype(int)
    frames[m] = d
cur_m, prev_m = months[-1], (months[-2] if len(months) > 1 else None)
cur = frames[cur_m]; prev = frames[prev_m] if prev_m else None
themes = {k: v for k, v in json.load(open(ROOT / "data/themes.json")).items() if not k.startswith("_")}
t_of = {}
for th, tk in themes.items():
    for t in tk: t_of.setdefault(t, []).append(th)
fv = {a["ticker"] for a in json.load(open(ROOT / "data/assets.json"))["assets"]}
top_cur = set(cur.nsmallest(50, "rank").index)
top_prev = set(prev.nsmallest(50, "rank").index) if prev is not None else set()
def num(x): return None if pd.isna(x) else round(float(x), 2)
rows = []
for t, r in cur.iterrows():
    ig = implied_growth(r.fcf_yield_pct)
    ref = min(max(r.rev_growth_pct, 3), 30) / 100 if not pd.isna(r.rev_growth_pct) else None
    tag = None
    if ig is not None and ref:
        tag = "Demanding" if ig > ref * 1.25 else ("Undemanding" if ig < ref * 0.75 else "In line")
    p = prev.loc[t] if (prev is not None and t in prev.index) else None
    rows.append(dict(ticker=t, name=r["name"], sector=r.sector, themes=t_of.get(t, []), score=float(r.score), rank=int(r["rank"]),
        prev_score=None if p is None else float(p.score), prev_rank=None if p is None else int(p["rank"]),
        rank_change=None if p is None else int(p["rank"]) - int(r["rank"]),
        old_score=float(r.growth_score), consistent=(t in top_cur and t in top_prev), top50=t in top_cur, flags=r["flag_list"],
        rev_growth_pct=num(r.rev_growth_pct), gross_margin_pct=num(r.gross_margin_pct), profit_margin_pct=num(r.profit_margin_pct),
        roe_pct=num(r.roe_pct), pe=num(r.pe_ratio), forward_pe=num(r.forward_pe), ev_ebitda=num(r.ev_ebitda), ps=num(r.ps_ratio),
        fcf_yield_pct=num(r.fcf_yield_pct), market_cap=num(r.market_cap), implied_fcf_growth=ig, implied_tag=tag, has_fair_value=t in fv))
rows.sort(key=lambda x: x["rank"])
out = dict(month=cur_m, prev_month=prev_m, built=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"), universe=len(rows),
           sectors=sorted(cur.sector.dropna().unique().tolist()), themes=list(themes), rows=rows)
json.dump(out, open(ROOT / "data/screen.json", "w"), indent=0)
print("built", cur_m, "vs", prev_m, "rows", len(rows), "consistent", sum(r["consistent"] for r in rows))
print("TOP 15:", [(r["ticker"], r["score"]) for r in rows[:15]])
import collections
print("top50 sectors:", dict(collections.Counter(r["sector"] for r in rows[:50])))
