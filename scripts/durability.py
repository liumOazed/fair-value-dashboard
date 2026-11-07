#!/usr/bin/env python3
"""Two durability questions for every stock on the Fair Value tab -> data/durability.json. Information only:
nothing here changes a fair value.

1. Advantage over bonds (bond): each fiscal year's earnings yield (EPS / share price at the fiscal year end) next to
   that calendar year's average 10-year Treasury and Moody's Aaa corporate yield (data/bond_yields.json, from FRED).
   EPS as first reported in the 10-K (data/backtest/facts.json.gz), divided by any later stock splits, topped up with
   the latest years from data/snapshot_raw.json. Today = trailing EPS / price vs the latest monthly yields.
   Gap vs Aaa: over 3 points = "large", 0 to 3 = "thin", below 0 = "negative".

2. Are the profits durable (stress)?
   a. Normal margins: the same fcff_re model (required return, 30/50/20 weights, 2.5% terminal growth, moat
      advantage period) re-run with the starting margin and all three scenario margins set to the stock's median
      FCF margin of the last 10 fiscal years (after today's stock-pay share, plus the interest add-back, as in the
      model). For AXP and AMP, valued on net income, the net margin is used. For underwriters (INSURERS, valued on book
      value and ROE) the starting and all scenario ROEs are set to the median ROE of the last 10 fiscal years.
   b. Bad year: for each recession in the data (fiscal years ending 2008-01 to 2010-06, and 2020-03 to 2021-06) the
      weakest year's revenue change and operating-margin change against the last fiscal year before it. The worse of
      the two is applied to the latest year: is it still profitable, and how well is interest covered? Also the
      years after the weakest year until operating profit was back at the pre-recession level. Net income for AXP, AMP and underwriters. Recessions only,
      so one-off charges in other years don't count; a stock listed after 2008 is tested on 2020 alone. A recession
      year in which revenue still grew but profit fell over 30% is marked as a likely one-off charge (an impairment,
      a legal settlement, an acquisition) and only used when it is the only one. Operating profit = pre-tax profit
      plus interest where the filing doesn't report it.
   Label: "cyclical" when the bad year leaves an operating loss or halves operating profit; "durable" when the bad
   year costs under 25% of operating profit and normal margins cost under 20% of the fair value; otherwise
   "somewhat cyclical".
Usage: python scripts/durability.py   (after model/model.py, scripts/bond_yields.py and the snapshot refresh)
"""
import gzip, json, pathlib, re, statistics as st

ROOT = pathlib.Path(__file__).resolve().parent.parent
FACTS = ROOT / "data/backtest/facts.json.gz"
PRICES = ROOT / "data/backtest/prices.json.gz"
F = json.load(gzip.open(FACTS)) if FACTS.exists() else {}
P = json.load(gzip.open(PRICES)) if PRICES.exists() else {}
SNAP = json.load(open(ROOT / "data/snapshot_raw.json"))["stocks"]
BY = ROOT / "data/bond_yields.json"
BOND = json.load(open(BY)) if BY.exists() else None
ASSETS = {a["ticker"]: a for a in json.load(open(ROOT / "data/assets.json"))["assets"]}

# The model's own functions and inputs, without running its valuation loop (which rewrites model/results.json)
_src = (ROOT / "model/model.py").read_text()
M = {"__file__": str(ROOT / "model/model.py"), "__name__": "model_defs"}
exec(compile(_src.split('\nout = {"as_of"')[0], "model.py", "exec"), M)
STOCKS, FIN, PROBS = M["STOCKS"], M["FIN"], M["PROBS"]
INSURERS = M.get("INSURERS", {})      # underwriters, valued on book value and ROE

YEARS_NORMAL = 10
EPISODES = [("2008-09 recession", "2008-01", "2008-01", "2010-06"), ("2020 pandemic", "2020-03", "2020-03", "2021-06")]
LARGE, CYC_DROP, DUR_DROP, DUR_FV, ONE_OFF = 3.0, -0.50, -0.25, -0.20, -0.30

def first(d, k, y):
    x = (d.get(k) or {}).get(y)
    return (x[0], x[1]) if isinstance(x, list) else (x, None)

def history(t):
    """Fiscal years -> dict(rev, op, ni, fcf, eps, eps_basis_date, end). Snapshot (latest ~5 years, current share basis)
    wins over the 10-K facts for the same fiscal year."""
    out = {}
    d = F.get(t)
    if d:
        for end in d.get("revenue", {}):
            rev, _ = first(d, "revenue", end)
            if not rev: continue
            op, _ = first(d, "operating_income", end); ni, _ = first(d, "net_income", end)
            if op is None:                                 # not reported (many drug makers): pre-tax profit + interest
                pt, _ = first(d, "pretax", end); it, _ = first(d, "interest", end)
                op = None if pt is None else pt + abs(it or 0)
            ocf, _ = first(d, "ocf", end); cx, _ = first(d, "capex", end); eps, filed = first(d, "eps", end)
            out[end[:4] if end[5:7] > "03" else str(int(end[:4]) - 1)] = dict(end=end, rev=rev, op=op, ni=ni,
                fcf=None if ocf is None else ocf - abs(cx or 0), eps=eps, filed=filed)
    a = (SNAP.get(t) or {}).get("annual") or {}
    for end, v in (a.get("inc") or {}).items():
        if not v.get("rev"): continue
        c = (a.get("cfs") or {}).get(end) or {}
        fy = end[:4] if end[5:7] > "03" else str(int(end[:4]) - 1)
        out[fy] = dict(end=end, rev=v["rev"], op=v["op"] if v.get("op") is not None else v.get("pretax"), ni=v.get("ni"), fcf=c.get("fcf"), eps=v.get("eps"), filed=None)
    return dict(sorted(out.items()))

def split_after(t, date):
    """Product of the stock splits after a date (to put an old EPS on today's share basis)."""
    sp = (P.get(t) or {}).get("splits") or [[k, v] for k, v in ((SNAP.get(t) or {}).get("splits") or {}).items()]
    f = 1.0
    for d, r in sp:
        if d[:7] > date[:7] and r > 0: f *= r
    return f

def price_at(t, end):
    """Split-adjusted close in the fiscal year-end month (or the latest before it, within 3 months)."""
    m = (SNAP.get(t) or {}).get("monthly_prices") or {}
    if end[:7] in m: return m[end[:7]]
    p = P.get(t)
    if not p: return None
    best = None
    for d, c in zip(p["d"], p["close"]):
        if d[:7] <= end[:7] and c: best = (d, c)
    if best and (int(end[:4]) * 12 + int(end[5:7])) - (int(best[0][:4]) * 12 + int(best[0][5:7])) <= 3: return best[1]
    return None

def bond_block(t, H, price):
    if not BOND: return None
    A10, AAA = BOND["annual"].get("GS10", {}), BOND["annual"].get("AAA", {})
    rows = []
    for fy, h in H.items():
        if h["eps"] is None or h["end"][:4] not in A10: continue
        eps = h["eps"] / (split_after(t, h["filed"]) if h["filed"] else 1.0)
        p = price_at(t, h["end"])
        if not p: continue
        y = h["end"][:4]
        rows.append([int(y), round(eps / p * 100, 2), A10.get(y), AAA.get(y)])
    dedup = {}
    for r in rows: dedup[r[0]] = r                       # one point per calendar year (the latest fiscal year in it)
    rows = [dedup[k] for k in sorted(dedup)]
    info = (SNAP.get(t) or {}).get("info") or {}
    eps_now = info.get("trailingEps")
    M10, MAAA = BOND["monthly"].get("GS10", {}), BOND["monthly"].get("AAA", {})
    l10 = max(M10) if M10 else None; laaa = max(MAAA) if MAAA else None
    ey_now = round(eps_now / price * 100, 2) if eps_now is not None and price else None
    gaps = [r[1] - r[3] for r in rows if r[3] is not None]
    gap_now = round(ey_now - MAAA[laaa], 2) if ey_now is not None and laaa else None
    label = None if gap_now is None else "large" if gap_now > LARGE else "thin" if gap_now >= 0 else "negative"
    return dict(years=rows, ey_now=ey_now, t10_now=M10.get(l10) if l10 else None, aaa_now=MAAA.get(laaa) if laaa else None,
                yields_month=laaa or l10, gap_now=gap_now, gap_t10_now=round(ey_now - M10[l10], 2) if ey_now is not None and l10 else None,
                gap_median=round(st.median(gaps), 2) if gaps else None, label=label)

def model_value(t, m_normal):
    """Fair value per share with the starting and all scenario margins set to m_normal (before the interest add-back)."""
    s = dict(STOCKS[t]); s["r"] = M["req_return"](t)
    mo = dict(M["moat_of"](t), r_req=s["r"]); sg = M["segments_of"](t)
    f = FIN[t]
    aint = 0.0 if M["DCF_METHOD"] == "equity" else f["interest"] * (1 - f["tax"])
    add = aint / s["rev"]
    nc = s["net_cash"] + s["extra"]
    D = lambda m0, p: M["dcf"](s["rev"], m0, p["g1"], p["g10"], p["m"], s["r"], nc, s["shares"], mo=mo, sg=sg)
    now = sum(PROBS[k] * D((s["fcf"] - s["sbc"] + aint) / s["rev"], dict(v, m=v["m"] + add)) for k, v in s["scen"].items())
    norm = sum(PROBS[k] * D(m_normal + add, dict(v, m=m_normal + add)) for k, v in s["scen"].items())
    return now, norm, (s["fcf"] - s["sbc"]) / s["rev"], {k: v["m"] for k, v in s["scen"].items()}, s

def roe_years(t):
    """Fiscal year -> return on equity (net income / average book value), 10-K facts topped up by the snapshot."""
    ni, eq = {}, {}
    d = F.get(t) or {}
    for k, dst in (("net_income", ni), ("equity", eq)):
        for end in d.get(k, {}):
            x, _ = first(d, k, end)
            if x is not None: dst[end[:4] if end[5:7] > "03" else str(int(end[:4]) - 1)] = x
    a = (SNAP.get(t) or {}).get("annual") or {}
    for end, v in (a.get("inc") or {}).items():
        fy = end[:4] if end[5:7] > "03" else str(int(end[:4]) - 1)
        if v.get("ni") is not None: ni[fy] = v["ni"]
    for end, v in (a.get("bal") or {}).items():
        fy = end[:4] if end[5:7] > "03" else str(int(end[:4]) - 1)
        if v.get("equity"): eq[fy] = v["equity"]
    out = {}
    for y in sorted(ni):
        if y in eq and eq[y] > 0:
            base = (eq[y] + eq[str(int(y) - 1)]) / 2 if eq.get(str(int(y) - 1), 0) > 0 else eq[y]
            out[y] = ni[y] / base
    return out

def normal_ins(t):
    """Underwriter: fair value with the starting ROE and every scenario's long-run ROE set to the median ROE of the last
    10 fiscal years (so one great or terrible year doesn't set the value)."""
    s = INSURERS[t]; r = M["req_return"](t); mo = dict(M["moat_of"](t), r_req=r)
    R = roe_years(t); last = sorted(R)[-YEARS_NORMAL:]
    if len(last) < 5: return None
    med = st.median(R[y] for y in last)
    V = lambda roe0, p: M["ri_value"](s["bv"], roe0, p["g1"], p["g10"], p["m"], r, s["extra"], s["shares"], mo=mo)
    now = sum(PROBS[k] * V(s["roe0"], p) for k, p in s["scen"].items())
    norm = sum(PROBS[k] * V(med, dict(p, m=med)) for k, p in s["scen"].items())
    return dict(median_margin=round(med, 4), years=len(last), low=round(min(R[y] for y in last), 4), high=round(max(R[y] for y in last), 4),
                margin_now=round(s["ni"] / s["bv"], 4), base_margin=round(s["scen"]["base"]["m"], 4), sbc_share=0.0,
                fv_model=round(now, 2), fv_normal=round(norm, 2), change=round(norm / now - 1, 4) if now > 0 else None,
                series=[[int(y), round(R[y] * 100, 1)] for y in last])

def stress_block(t, H):
    ins = t in INSURERS
    s0 = INSURERS[t] if ins else STOCKS[t]
    lender = ins or bool(re.search(r"cash flow = net income", s0["notes"], re.I))
    yrs = list(H)
    last = yrs[-YEARS_NORMAL:]
    key = "ni" if lender else "fcf"
    ms = [H[y][key] / H[y]["rev"] for y in last if H[y].get(key) is not None and H[y]["rev"] > 0]
    out = dict(years_from=yrs[0] if yrs else None, years_to=yrs[-1] if yrs else None, basis="ROE" if ins else "net margin" if lender else "FCF margin")
    if ins:
        n = normal_ins(t)
        if n: out["normal"] = n
    elif len(ms) >= 5:
        med = st.median(ms)
        sbc_share = 0.0 if lender else s0["sbc"] / s0["rev"]
        now_fv, norm_fv, m_now, scen_m, _ = model_value(t, med - sbc_share)
        out["normal"] = dict(median_margin=round(med, 4), years=len(ms), low=round(min(ms), 4), high=round(max(ms), 4),
                             margin_now=round(m_now + sbc_share, 4), base_margin=round(scen_m["base"] + sbc_share, 4), sbc_share=round(sbc_share, 4),
                             fv_model=round(now_fv, 2), fv_normal=round(norm_fv, 2), change=round(norm_fv / now_fv - 1, 4) if now_fv > 0 else None,
                             series=[[int(y), round(H[y][key] / H[y]["rev"] * 100, 1)] for y in last if H[y].get(key) is not None and H[y]["rev"] > 0])
    # bad year: the two recessions in the data, each against the last fiscal year before it
    pk = "ni" if lender else "op"
    eps_ = []
    for name, base_before, lo, hi in EPISODES:
        base = [y for y in yrs if H[y]["end"][:7] < base_before and H[y].get(pk) is not None]
        hit = [y for y in yrs if lo <= H[y]["end"][:7] <= hi and H[y].get(pk) is not None and H[y]["rev"]]
        if not base or not hit: continue
        b0 = H[base[-1]]
        if not b0["rev"] or b0[pk] is None or b0[pk] <= 0: continue
        tr = min(hit, key=lambda y: H[y][pk] / b0[pk])                 # weakest year of the episode
        x = H[tr]
        eps_.append(dict(name=name, base_year=base[-1], year=tr, rev=x["rev"] / b0["rev"] - 1,
                         margin=x[pk] / x["rev"] - b0[pk] / b0["rev"], profit=x[pk] / b0[pk] - 1,
                         one_off=x["rev"] >= b0["rev"] and x[pk] / b0[pk] - 1 < ONE_OFF,
                         recovery=None if x[pk] >= b0[pk] else next((int(y) - int(tr) for y in yrs if y > tr and H[y].get(pk) is not None and H[y][pk] >= b0[pk]), "not yet")))
    lt = H[yrs[-1]] if yrs else None
    if lt and lt.get(pk) is not None and lt["rev"]:
        out["episodes"] = [dict(name=e["name"], base_year=e["base_year"], year=e["year"], rev=round(e["rev"], 4), margin=round(e["margin"], 4),
                                profit=round(e["profit"], 4), recovery_years=e["recovery"], one_off=e["one_off"]) for e in eps_]
    if eps_ and lt and lt.get(pk) is not None and lt["rev"]:
        real = [e for e in eps_ if not e["one_off"]]
        w = min(real or eps_, key=lambda e: e["profit"])
        opm = lt[pk] / lt["rev"]
        rev_s = lt["rev"] * (1 + min(w["rev"], 0)); opm_s = opm + min(w["margin"], 0); op_s = rev_s * opm_s
        intr = 0.0 if lender else FIN[t]["interest"] * 1e9
        drop = op_s / lt[pk] - 1 if lt[pk] > 0 else None
        out["bad"] = dict(episode=w["name"], one_off=w["one_off"], measure="net income" if lender else "operating profit", latest_year=yrs[-1],
                          worst_rev=round(w["rev"], 4), worst_margin_drop=round(w["margin"], 4), worst_profit=round(w["profit"], 4),
                          margin_now=round(opm, 4), margin_stressed=round(opm_s, 4), profit_now_b=round(lt[pk] / 1e9, 2),
                          profit_stressed_b=round(op_s / 1e9, 2), op_change=round(drop, 4) if drop is not None else None,
                          interest_b=round(intr / 1e9, 3), cover_now=round(lt[pk] / intr, 1) if intr > 0 else None,
                          cover_stressed=round(op_s / intr, 1) if intr > 0 else None, profitable=op_s > 0)
    b, n = out.get("bad"), out.get("normal")
    if b:
        if not b["profitable"] or (b["op_change"] is not None and b["op_change"] <= CYC_DROP): out["label"] = "cyclical"
        elif b["op_change"] is not None and b["op_change"] > DUR_DROP and (not n or n["change"] is None or n["change"] > DUR_FV): out["label"] = "durable"
        else: out["label"] = "somewhat cyclical"
    return out

doc = {"_about": __doc__.strip().split("\n\n")[0], "built_from": dict(bond_yields=(BOND or {}).get("fetched"), model_as_of=M["AS_OF"]),
       "thresholds": dict(large_gap=LARGE, cyclical_drop=CYC_DROP, durable_drop=DUR_DROP, durable_fv=DUR_FV, normal_years=YEARS_NORMAL),
       "yields": None if not BOND else dict(annual=BOND["annual"], names=BOND["names"]), "stocks": {}}
for t in list(STOCKS) + list(INSURERS):
    H = history(t)
    price = (ASSETS.get(t) or {}).get("price") or (SNAP.get(t) or {}).get("price") or (STOCKS.get(t) or INSURERS[t])["price"]
    doc["stocks"][t] = dict(bond=bond_block(t, H, (SNAP.get(t) or {}).get("price") or price), stress=stress_block(t, H))
json.dump(doc, open(ROOT / "data/durability.json", "w"), indent=0, separators=(",", ":"))
for t, v in doc["stocks"].items():
    b, s = v["bond"] or {}, v["stress"]; n, d = s.get("normal") or {}, s.get("bad") or {}
    print(f"{t:6} EY {b.get('ey_now')}% gap {b.get('gap_now')} ({b.get('label')})  normal FV {n.get('fv_model')} -> {n.get('fv_normal')} "
          f"({n.get('change')})  bad year op {d.get('op_change')} cover {d.get('cover_stressed')}  {s.get('label')}")
