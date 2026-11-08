#!/usr/bin/env python3
"""Returns on capital over time (questions 1, 2 and 5 of the Durand/CAP review) -> data/returns.json.

For every modelled stock, from annual 10-K figures (data/backtest/facts.json.gz, as first reported)
topped up with the latest years in data/snapshot_raw.json:
  ROIC         = operating profit x (1 - tax rate) / invested capital (equity + debt - cash and short-term investments,
                 average of the start and end of the year), shown up to 200%. Includes goodwill, so serial acquirers
                 look lower than the businesses they bought.
  Q1 Incremental = extra after-tax operating profit / extra invested capital over the latest 5 years and the 5 before
                 (each end averaged over 2 years; only when invested capital grew by more than 10%). "diminishing" when
                 the latest is under 80% of today's ROIC or 5+ points below the earlier window; "below hurdle" when
                 under the stock's required return.
  Q2 Fade      = robust (Theil-Sen) trend of ROIC minus the required return on a log scale over the last 8 years:
                 the half-life of the excess return, and the years until it is within 2 points of the hurdle at that
                 pace (capped at 50). "not fading" when the excess shrinks by less than 2% a year.
  Q5 Reinvest  = growth in invested capital over the latest 5 years / after-tax operating profit in those years, the
                 dollars a year that represents, and the growth it funds (reinvestment rate x latest incremental return, left out above 100%, where growth
                 comes mostly from existing assets and pricing rather than new capital).
  Latest      = nopat_last_b and ic_last_b ($B): economic profit at any rate = NOPAT - rate x capital (Capital and returns card).
  Invest      = capex, depreciation, R&D, acquisitions, operating cash flow and revenue for the latest 5 fiscal years ($B).
Underwriters (INSURERS in model/model.py) hold investments against claims, so invested capital means nothing for them:
they get the same tests on return on equity (net income / book value, average of the start and end of the year),
marked measure = "ROE".
Diagnostics only: nothing here changes a fair value. Run after the snapshot is refreshed.
"""
import gzip, json, math, pathlib, re, statistics as st

ROOT = pathlib.Path(__file__).resolve().parent.parent
FACTS = ROOT / "data/backtest/facts.json.gz"
F = json.load(gzip.open(FACTS)) if FACTS.exists() else {}
SNAP = json.load(open(ROOT / "data/snapshot_raw.json"))["stocks"]
RR = json.load(open(ROOT / "data/required_returns.json"))["stocks"]
TICKERS = list(dict.fromkeys(re.findall(r'^ "([A-Z.]+)": dict\(name', (ROOT / "model/model.py").read_text(), re.M)))
_MT = (ROOT / "model/model.py").read_text()
_IB = _MT[_MT.index("\nINSURERS = {"):] if "\nINSURERS = {" in _MT else ""
INSURERS = set(re.findall(r'^ "([A-Z.]+)": dict\(name', _IB[:_IB.index("\n}\n")] if _IB else "", re.M))   # underwriters: ROE, not ROIC
SPAN, TREND_YEARS, CAP = 5, 8, 2.0     # 5-year windows, 8-year trends, ROIC shown up to 200%

def v(d, k, y):
    x = (d.get(k) or {}).get(y)
    return x[0] if isinstance(x, list) else x

def years_from_facts(t):
    d = F.get(t)
    if not d: return {}
    out = {}
    for y in sorted(set(d.get("revenue", {})) | set(d.get("pretax", {}))):
        op = v(d, "operating_income", y)
        if op is None and v(d, "pretax", y) is not None:
            op = v(d, "pretax", y) + (v(d, "interest", y) or 0)          # EBIT proxy when operating income isn't tagged
        debt = v(d, "ltd_total", y)
        if debt is None:
            debt = (v(d, "ltd_noncur", y) or 0) + (v(d, "ltd_cur", y) or 0)
            if v(d, "ltd_cur", y) is None: debt += v(d, "st_debt", y) or 0
        out[y[:4]] = dict(op=op, tax=v(d, "tax", y), pretax=v(d, "pretax", y), equity=v(d, "equity", y), debt=debt, ni=v(d, "net_income", y),
                          cash=(v(d, "cash", y) or 0) + (v(d, "st_inv", y) or 0), rev=v(d, "revenue", y))
    return out

def years_from_snapshot(t):
    s = SNAP.get(t) or {}; inc = s.get("annual", {}).get("inc", {}); bal = s.get("annual", {}).get("bal", {})
    return {y[:4]: dict(op=inc[y].get("op"), tax=inc[y].get("tax"), pretax=inc[y].get("pretax"), equity=(bal.get(y) or {}).get("equity"), ni=inc[y].get("ni"),
                        debt=(bal.get(y) or {}).get("debt"), cash=(bal.get(y) or {}).get("cash"), rev=inc[y].get("rev")) for y in inc}

def theil_sen(pts):
    """Median of pairwise slopes: a straight-line trend that a single odd year can't swing."""
    sl = [(y2 - y1) / (x2 - x1) for i, (x1, y1) in enumerate(pts) for x2, y2 in pts[i + 1:] if x2 != x1]
    return st.median(sl) if len(pts) >= 4 and sl else None

def incremental(nopat, ic, y_end, span):
    """Extra after-tax profit / extra invested capital from year y_end-span to y_end, each end averaged over 2 years."""
    a, b = [str(y_end - span - 1), str(y_end - span)], [str(y_end - 1), str(y_end)]
    if not all(y in nopat and y in ic for y in a + b): return None, "missing years"
    n0, n1 = st.mean(nopat[y] for y in a), st.mean(nopat[y] for y in b)
    c0, c1 = st.mean(ic[y] for y in a), st.mean(ic[y] for y in b)
    if c0 <= 0: return None, "invested capital at or below zero"
    if c1 - c0 <= 0.10 * c0: return None, "invested capital barely grew or shrank"
    return (n1 - n0) / (c1 - c0), None

def investment(t, n=5):
    """What the company spends to grow, per fiscal year ($B, latest n years): capex, depreciation (roughly the capex
    that keeps today's business running; the rest is growth capex), R&D (an expense in the accounts, but money spent
    on future products), acquisitions (cash paid for businesses, net of cash acquired) and operating cash flow.
    Yahoo annual statements (data/snapshot_raw.json), older years filled from the 10-K facts."""
    s = SNAP.get(t) or {}; A = s.get("annual", {}); inc, cfs = A.get("inc", {}), A.get("cfs", {})
    d = F.get(t) or {}
    rows = {}
    for y in sorted(set(inc) | set(cfs)):
        i, c = inc.get(y) or {}, cfs.get(y) or {}
        rows[y[:4]] = dict(capex=-c["capex"] if c.get("capex") is not None else None, dep=c.get("dep") if c.get("dep") is not None else i.get("dep_inc"),
                           rd=i.get("rd"), acq=-c["acq"] if c.get("acq") is not None else None, ocf=c.get("ocf"), rev=i.get("rev"))
    for y in sorted(set(d.get("capex", {})) | set(d.get("ocf", {}))):
        r = rows.setdefault(y[:4], {})
        for k, fk, sgn in (("capex", "capex", 1), ("dep", "dna", 1), ("ocf", "ocf", 1), ("rev", "revenue", 1)):
            if r.get(k) is None and v(d, fk, y) is not None: r[k] = abs(v(d, fk, y)) if k == "capex" else v(d, fk, y)
    ys = [y for y in sorted(rows) if rows[y].get("capex") is not None or rows[y].get("rd") is not None][-n:]
    b = lambda x: None if x is None else round(x / 1e9, 3)
    return [dict(y=int(y), **{k: b(rows[y].get(k)) for k in ("capex", "dep", "rd", "acq", "ocf", "rev")}) for y in ys] or None

def analyse(t):
    Y = years_from_facts(t)
    ins = t in INSURERS
    key = "ni" if ins else "op"
    for y, row in years_from_snapshot(t).items():                       # newer years, or fill gaps
        if y not in Y or Y[y].get(key) is None: Y[y] = row
    nopat, ic = {}, {}
    for y in sorted(Y)[-12:]:
        r = Y[y]
        if ins:                      # underwriter: return on equity = net income / book value (capital is the equity)
            if r.get("ni") is None or not r.get("equity"): continue
            nopat[y], ic[y] = r["ni"], r["equity"]
            continue
        if r.get("op") is None or r.get("equity") is None: continue
        tr = r["tax"] / r["pretax"] if r.get("tax") is not None and r.get("pretax") and r["pretax"] > 0 else 0.21
        nopat[y] = r["op"] * (1 - min(max(tr, 0.0), 0.35))
        ic[y] = r["equity"] + (r.get("debt") or 0) - (r.get("cash") or 0)
    r = RR.get(t, {}).get("r")
    roic = []
    for y in sorted(nopat):
        prev = str(int(y) - 1)
        base = (ic[y] + ic[prev]) / 2 if prev in ic else ic[y]
        if base > 0: roic.append([int(y), min(nopat[y] / base, CAP)])
    last = max(map(int, nopat)) if nopat else None
    out = dict(r=r, roic=roic, last_year=last)
    if ins: out["measure"] = "ROE"     # the drawer labels the chart "return on equity"; same tests on net income and book value
    if ins and (len(roic) < 4 or roic[-1][0] != last):
        out["note"] = ("No statements for this company in the data yet." if not roic else
                       f"Only {len(roic)} year{'s' if len(roic) != 1 else ''} of net income and book value in the data, so the return-on-equity tests can't be run.")
        return out
    if roic and roic[-1][0] == last:          # value created at any rate = after-tax profit - rate x capital (Capital and returns card)
        ly, py = str(last), str(last - 1)
        out["nopat_last_b"] = nopat[ly] / 1e9
        out["ic_last_b"] = ((ic[ly] + ic[py]) / 2 if py in ic else ic[ly]) / 1e9
    if not ins: out["invest"] = investment(t)
    if len(roic) < 4 or roic[-1][0] != last:
        out["note"] = "Invested capital is at or below zero in recent years (cash exceeds equity plus debt, or big buybacks), so returns on capital can't be measured. The business needs very little capital."
        return out
    # Q1: is each new dollar earning less than the last?
    recent, why = incremental(nopat, ic, last, SPAN)
    earlier, _ = incremental(nopat, ic, last - SPAN, SPAN)
    now = st.mean(x for _, x in roic[-2:])
    out.update(roic_now=now, inc_recent=recent, inc_earlier=earlier, inc_why=why,
               windows=[f"{last - 2 * SPAN}-{last - SPAN}", f"{last - SPAN}-{last}"])
    if recent is None: q1 = "unmeasured"
    elif recent < r: q1 = "below hurdle"
    elif recent < 0.8 * now or (earlier is not None and recent < earlier - 0.05): q1 = "diminishing"
    else: q1 = "holding up"
    out["q1"] = q1
    # Q2: how fast is the excess return over the hurdle fading?
    pts = roic[-TREND_YEARS:]
    out["roic_trend"] = theil_sen(pts)
    ex = [[y, x - r] for y, x in pts]
    if ex[-1][1] <= 0.01 or now - r <= 0.01:
        out.update(q2="at hurdle", years_left=0)
    else:
        lg = [[y, math.log(e)] for y, e in ex if e > 0.005]
        k = theil_sen(lg) if len(lg) >= 4 else None
        out["half_life"] = None if k is None or k >= -0.02 else math.log(2) / -k
        if k is None or k >= -0.02:
            out.update(q2="not fading", years_left=None)
        else:
            out.update(q2="fading", years_left=min(math.log((now - r) / 0.02) / -k, 50) if now - r > 0.02 else 0)
    # Q5: how much is being reinvested, and what growth does it buy?
    ys = [str(y) for y in range(last - SPAN, last + 1)]
    if all(y in ic for y in ys) and all(nopat[y] > 0 for y in ys[1:]):
        tot = sum(nopat[y] for y in ys[1:]); dic = ic[ys[-1]] - ic[ys[0]]
        rate = dic / tot
        out["reinvest"] = dict(rate=rate, per_year_b=dic / SPAN / 1e9, nopat_b=nopat[ys[-1]] / 1e9, years=f"{ys[0]}-{ys[-1]}",
                               growth_funded=rate * recent if recent is not None and 0 < rate and recent <= 1 else None)
    return out

def rnd(o):
    if isinstance(o, float): return round(o, 4)
    if isinstance(o, dict): return {k: rnd(x) for k, x in o.items()}
    if isinstance(o, list): return [rnd(x) for x in o]
    return o

out = {"_about": __doc__.strip().split("\n")[0] + " See scripts/returns_history.py for definitions.",
       "stocks": {t: rnd(analyse(t)) for t in TICKERS}}
json.dump(out, open(ROOT / "data/returns.json", "w"), indent=1)
print("returns:", len(out["stocks"]), "stocks")
