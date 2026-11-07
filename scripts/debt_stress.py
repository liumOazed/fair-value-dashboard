#!/usr/bin/env python3
"""Can it pay its debts in a bad year? -> data/debt_stress.json. Information only: nothing here changes a fair value.

A company can look strong after one or two boom years. These checks replay its worst recession year on today's
business and today's debt, in cash, not just profit. For each modelled stock (latest fiscal year from
data/snapshot_raw.json, history from the 10-K facts in data/backtest/facts.json.gz):

  bad year      the weakest year of the 2008-09 recession (fiscal years ending 2008-10 to 2010-06, against the last
                fiscal year ending before 2008-10, i.e. before the Lehman collapse) or of 2020 (2020-03 to 2021-06
                against the last year before 2020-03): revenue change, operating-margin change and operating-cash-flow
                change. The worse of the two (by operating profit) is used. A year in which revenue still grew but profit
                fell over 30% is treated as a one-off charge and only used when it is the only one.
                No usable recession: the sector's median 2008-09 hit across every company in the facts file is used
                instead, marked as an estimate.
  Q1 cash cover    stressed free cash flow (today's operating cash flow x (1 + bad-year cash-flow change) minus today's
                   capex, which is not cut) / (interest + debt due within 12 months + dividends)
  Q2 bottom leverage  net debt / stressed EBITDA (stressed operating profit + today's depreciation). Lenders usually
                   start to worry above 3.5x.
  Q3 refinance     interest cover in the bad year if all debt cost today's Moody's Baa yield (Aaa when Baa is missing)
  Q4 cash runway   months the cash on hand covers the bad-year gap (interest + debt due + dividends - stressed FCF)
  Q5 last time     what it did in its bad year: dividend per share cut? diluted shares up more than 2%?
  Q7 normal margin interest cover at its 10-year median operating margin, so one boom year doesn't flatter it
Verdict: "pays its debts" when Q1 >= 1 (or cash covers 24+ months of the gap), Q2 <= 3.5x and Q3 >= 3x;
"at risk" when Q2 > 5x, or Q3 < 1.5x, or Q1 < 1 with under 12 months of cash; otherwise "tight". A check that can't
be measured is unknown and never helps the verdict; without Q1 and Q2 there is no verdict.
Lenders and insurers (AXP, AMP, valued on net income, and the underwriters in INSURERS) need capital-ratio tests instead
and are not scored. Insurance brokers (MRSH, WTW, CRVL) are fee businesses and get the normal tests.
Usage: python scripts/debt_stress.py   (after the snapshot refresh and scripts/bond_yields.py)
"""
import csv, glob, gzip, json, pathlib, re, statistics as st

ROOT = pathlib.Path(__file__).resolve().parent.parent
F = json.load(gzip.open(ROOT / "data/backtest/facts.json.gz"))
SNAP = json.load(open(ROOT / "data/snapshot_raw.json"))["stocks"]
BOND = json.load(open(ROOT / "data/bond_yields.json"))
ASSETS = {a["ticker"]: a for a in json.load(open(ROOT / "data/assets.json"))["assets"] if a.get("type") == "stock"}
_src = (ROOT / "model/model.py").read_text()
M = {"__file__": str(ROOT / "model/model.py"), "__name__": "model_defs"}
exec(compile(_src.split('\nout = {"as_of"')[0], "model.py", "exec"), M)
STOCKS, FIN, INSURERS = M["STOCKS"], M["FIN"], M.get("INSURERS", {})
EPISODES = [("2008-09 recession", "2008-10", "2008-10", "2010-06"), ("2020 pandemic", "2020-03", "2020-03", "2021-06")]
ONE_OFF = -0.30

def v(d, k, end):
    x = (d.get(k) or {}).get(end)
    return x[0] if isinstance(x, list) else x

def fy_of(end):
    return end[:4] if end[5:7] > "03" else str(int(end[:4]) - 1)

def history(t):
    """Fiscal year -> rev, op, ocf, shares (10-K facts as first reported, topped up by the snapshot)."""
    out, d = {}, F.get(t) or {}
    for end in d.get("revenue", {}):
        rev = v(d, "revenue", end)
        if not rev: continue
        op = v(d, "operating_income", end)
        if op is None:
            pt, it = v(d, "pretax", end), v(d, "interest", end)
            op = None if pt is None else pt + abs(it or 0)
        out[fy_of(end)] = dict(end=end, rev=rev, op=op, ocf=v(d, "ocf", end), shares=v(d, "dil_shares", end))
    a = (SNAP.get(t) or {}).get("annual") or {}
    for end, x in (a.get("inc") or {}).items():
        if not x.get("rev"): continue
        c = (a.get("cfs") or {}).get(end) or {}
        old = out.get(fy_of(end), {})
        out[fy_of(end)] = dict(end=end, rev=x["rev"], op=x["op"] if x.get("op") is not None else x.get("pretax"),
                               ocf=c.get("ocf"), shares=old.get("shares"))
    return dict(sorted(out.items()))

def episodes(H):
    yrs, res = list(H), []
    for name, before, lo, hi in EPISODES:
        base = [y for y in yrs if H[y]["end"][:7] < before and H[y].get("op") is not None]
        hit = [y for y in yrs if lo <= H[y]["end"][:7] <= hi and H[y].get("op") is not None and H[y]["rev"]]
        if not base or not hit: continue
        b = H[base[-1]]
        if not b["rev"] or not b["op"] or b["op"] <= 0: continue
        tr = min(hit, key=lambda y: H[y]["op"] / b["op"])
        x = H[tr]
        res.append(dict(name=name, base_year=base[-1], year=tr, rev=x["rev"] / b["rev"] - 1,
                        margin=x["op"] / x["rev"] - b["op"] / b["rev"], profit=x["op"] / b["op"] - 1,
                        ocf=(x["ocf"] / b["ocf"] - 1) if x.get("ocf") is not None and b.get("ocf") and b["ocf"] > 0 else None,
                        shares=(x["shares"] / b["shares"] - 1) if x.get("shares") and b.get("shares") else None,
                        one_off=x["rev"] >= b["rev"] and x["op"] / b["op"] - 1 < ONE_OFF))
    return res

# sector medians of the 2008-09 hit, for stocks with no usable recession of their own
screens = sorted(f for f in glob.glob(str(ROOT / "data/screens/growth_screen_results_*.csv")) if "estimated" not in f)
SECTOR = {r["ticker"]: r["sector"] for r in csv.DictReader(open(screens[-1]))} if screens else {}
by = {}
for t in F:
    e = [x for x in episodes(history(t)) if x["name"].startswith("2008") and not x["one_off"]]
    if e and SECTOR.get(t): by.setdefault(SECTOR[t], []).append(e[0])
SECTOR_HIT = {s: dict(rev=st.median(x["rev"] for x in L), margin=st.median(x["margin"] for x in L),
                      ocf=st.median(x["ocf"] for x in L if x["ocf"] is not None) if any(x["ocf"] is not None for x in L) else None, n=len(L))
              for s, L in by.items() if len(L) >= 8}

def latest_yield(sid):
    m = (BOND.get("monthly") or {}).get(sid) or {}
    return (max(m), m[max(m)]) if m else None

BAA = latest_yield("BAA"); AAA = latest_yield("AAA")
REF = ("Baa", *BAA) if BAA else ("Aaa", *AAA) if AAA else None

def tone(x, good, bad, higher_better=True):
    if x is None: return None
    if higher_better: return "good" if x >= good else "bad" if x < bad else "caution"
    return "good" if x <= good else "bad" if x > bad else "caution"

def stock(t):
    if t in INSURERS:                # underwriters: claims, reserves and regulatory capital, not a debt test
        return dict(lender=True, insurer=True)
    s0 = STOCKS[t]
    if re.search(r"cash flow = net income", s0["notes"], re.I):
        return dict(lender=True)
    a = (SNAP.get(t) or {}).get("annual") or {}
    end = max((a.get("inc") or {}) or [None]) if a.get("inc") else None
    if not end: return None
    inc, cfs = a["inc"][end], (a.get("cfs") or {}).get(end) or {}
    bal = (a.get("bal") or {}).get(max(a.get("bal") or {end: 0})) or {}
    rev, op, ocf = inc.get("rev"), inc.get("op") if inc.get("op") is not None else inc.get("pretax"), cfs.get("ocf")
    capex, div, dep = abs(cfs.get("capex") or 0), abs(cfs.get("div_paid") or 0), cfs.get("dep") or inc.get("dep_inc") or 0
    if ocf is None and cfs.get("fcf") is not None: ocf = cfs["fcf"] + capex          # some filings give only FCF and capex
    debt, cash = bal.get("debt") or FIN[t]["debt"] * 1e9, bal.get("cash") or 0
    intr = FIN[t]["interest"] * 1e9
    d = F.get(t) or {}
    ld = [e for e in (d.get("ltd_cur") or {}) if e[:4] >= str(int(end[:4]) - 1)]
    sd = [e for e in (d.get("st_debt") or {}) if e[:4] >= str(int(end[:4]) - 1)]
    due, due_year = None, None
    if debt <= 0.005 * (rev or 1):                                   # practically no debt: nothing falls due
        due, due_year = 0.0, end[:10]
    elif ld or sd:
        due = (v(d, "ltd_cur", max(ld)) or 0 if ld else 0) + (v(d, "st_debt", max(sd)) or 0 if sd else 0)
        due_year = max(ld + sd)[:10]
    H = history(t)
    eps = episodes(H)
    real = [e for e in eps if not e["one_off"]]
    w = min(real or eps, key=lambda e: e["profit"]) if eps else None
    estimate = False
    sh = SECTOR_HIT.get(SECTOR.get(t))
    if sh and rev and op is not None and not any(e["name"].startswith("2008") for e in eps):
        hit = lambda x: rev * (1 + min(x["rev"], 0)) * (op / rev + min(x["margin"], 0))
        alt = dict(name=f"{SECTOR[t]} median 2008-09 hit ({sh['n']} companies)", year=None, rev=sh["rev"], margin=sh["margin"],
                   ocf=sh["ocf"], shares=None, profit=None, one_off=False)
        if not w or hit(alt) < hit(w): w, estimate = alt, True       # no 2008 history: the sector's 2008-09 hit, if worse
    out = dict(lender=False, year=end[:10], estimate=estimate, ref=REF and dict(name=REF[0], month=REF[1], y=REF[2]))
    if not (w and rev and op is not None):
        return out
    rev_s = rev * (1 + min(w["rev"], 0)); opm_s = op / rev + min(w["margin"], 0); op_s = rev_s * opm_s
    ocf_chg = w.get("ocf") if w.get("ocf") is not None else (op_s / op - 1 if op > 0 else None)
    ocf_s = ocf * (1 + min(ocf_chg, 0)) if ocf is not None and ocf_chg is not None else None
    fcf_s = ocf_s - capex if ocf_s is not None else None
    due_known = due is not None
    if not due_known and cash >= debt:                               # due unknown, but cash on hand covers all of the debt
        due, due_year, due_known = 0.0, None, "cash covers all debt"
    need = intr + (due or 0) + div
    q1 = (fcf_s / need) if fcf_s is not None and need > 0 else (99.0 if fcf_s is not None and fcf_s > 0 and need == 0 else None)
    gap = max(0.0, need - (fcf_s or 0)) if fcf_s is not None else None
    months = None if gap is None else (999 if gap == 0 else cash / gap * 12)
    ebitda_s = op_s + dep
    q2 = ((debt - cash) / ebitda_s) if ebitda_s > 0 else None
    q3 = (op_s / (debt * REF[2] / 100)) if REF and debt > 0 else None
    yrs = list(H)[-10:]
    mm = [H[y]["op"] / H[y]["rev"] for y in yrs if H[y].get("op") is not None and H[y]["rev"]]
    q7 = (st.median(mm) * rev / intr) if len(mm) >= 5 and intr > 0 else None
    # what it did last time (dividend per share in the bad calendar year vs the year before; shares from the 10-K)
    q5 = None
    if w.get("year"):
        dv = ((SNAP.get(t) or {}).get("dividends") or {}).get("by_year") or {}
        y = H[w["year"]]["end"][:4]
        cut = None
        if dv.get(str(int(y) - 1)):
            cut = (dv.get(y) or 0) < dv[str(int(y) - 1)] * 0.95
        q5 = dict(year=w["year"], dividend_cut=cut, paid_dividend=bool(dv.get(str(int(y) - 1))), shares=w.get("shares"))
    rows = dict(
        q1=None if q1 is None else dict(v=round(q1, 2), fcf_b=round(fcf_s / 1e9, 2), need_b=round(need / 1e9, 2), interest_b=round(intr / 1e9, 2),
                                        due_b=None if not due_known else round((due or 0) / 1e9, 2), due_year=due_year,
                                        due_note=due_known if isinstance(due_known, str) else None if due_known else "debt due unknown", div_b=round(div / 1e9, 2),
                                        tone=("caution" if q1 >= 0.5 else "bad") if not due_known else "good" if q1 >= 1 else "caution" if q1 >= 0.5 else "bad"),
        q2=None if q2 is None else dict(v=round(q2, 2), net_debt_b=round((debt - cash) / 1e9, 2), ebitda_b=round(ebitda_s / 1e9, 2),
                                        tone=tone(q2, 2.0, 3.5, False)) if ebitda_s > 0 else dict(v=None, ebitda_b=round(ebitda_s / 1e9, 2), tone="bad"),
        q3=None if q3 is None else dict(v=round(q3, 1), tone=tone(q3, 5, 2)),
        q4=None if months is None else dict(v=round(min(months, 999)), cash_b=round(cash / 1e9, 2), gap_b=round(gap / 1e9, 2),
                                            tone="good" if months >= 24 else "caution" if months >= 12 else "bad"),
        q5=q5,
        q7=None if q7 is None else dict(v=round(q7, 1), margin=round(st.median(mm), 4), years=len(mm), tone=tone(q7, 8, 3)))
    if ebitda_s <= 0: rows["q2"] = dict(v=None, ebitda_b=round(ebitda_s / 1e9, 2), tone="bad")
    if debt - cash <= 0 and rows.get("q2"): rows["q2"]["tone"] = "good"
    out.update(episode=w["name"], episode_year=w.get("year"), rev=round(w["rev"], 4), margin=round(w["margin"], 4),
               ocf_change=None if ocf_chg is None else round(ocf_chg, 4), op_now_b=round(op / 1e9, 2), op_stressed_b=round(op_s / 1e9, 2),
               debt_b=round(debt / 1e9, 2), cash_b=round(cash / 1e9, 2), **rows)
    # verdict: unknown never helps
    a1, a2, a3, a4 = rows["q1"], rows["q2"], rows["q3"], rows["q4"]
    if not a1 or not a2 or a1.get("due_note") == "debt due unknown":
        out["verdict"] = None                                        # not enough data: an unknown never helps
    else:
        pays_cash = a1["v"] >= 1 or (a4 and a4["v"] >= 24)
        lev = a2["v"] if a2["v"] is not None else 99
        if (lev > 5) or (a3 and a3["v"] < 1.5) or (a1["v"] < 1 and (not a4 or a4["v"] < 12)): out["verdict"] = "at risk"
        elif pays_cash and lev <= 3.5 and (a3 and a3["v"] >= 3): out["verdict"] = "pays its debts"
        else: out["verdict"] = "tight"
    return out

doc = {"_about": __doc__.strip().split("\n\n")[0], "ref_yield": REF and dict(name=REF[0], month=REF[1], y=REF[2]),
       "sector_hits": {k: {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in x.items()} for k, x in SECTOR_HIT.items()},
       "stocks": {t: stock(t) for t in ASSETS if t in STOCKS or t in INSURERS}}
json.dump(doc, open(ROOT / "data/debt_stress.json", "w"), separators=(",", ":"))
from collections import Counter
print("debt_stress.json:", Counter((x or {}).get("verdict") if not (x or {}).get("lender") else "lender" for x in doc["stocks"].values()))
for t, x in doc["stocks"].items():
    if x and not x.get("lender"):
        print(f"{t:6} {x.get('verdict')!s:15} {x.get('episode','')[:28]:28} Q1 {(x.get('q1') or {}).get('v')} Q2 {(x.get('q2') or {}).get('v')} "
              f"Q3 {(x.get('q3') or {}).get('v')} Q4 {(x.get('q4') or {}).get('v')} Q7 {(x.get('q7') or {}).get('v')}{' est' if x.get('estimate') else ''}")
