#!/usr/bin/env python3
"""Build data/snapshot.json: the compact six-part snapshot shown at the top of each stock's Fair Value drawer.

Inputs: data/snapshot_raw.json (scripts/fetch_snapshot.py), data/screen.json (Growth Screen metrics + sector peers),
data/assets.json (fair values).
Five business-quality cards (Earnings, Cash flow, Business performance, Financial strength, Dividends & buybacks), each
graded Strong / OK / Weak from its own metrics; Valuation is NOT graded here (it needs the live price and is computed in
the page), so quality and price never mix. Each metric is graded in exactly one card; repeats elsewhere are shown in grey
("info") and not counted. Thresholds are absolute and simple; the sector percentile is shown next to each metric for context.
"""
import json, math, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
CYCLICAL_SECTORS = {"Energy", "Basic Materials"}
CYCLICAL_INDUSTRIES = ("Engineering & Construction", "Travel", "Luxury", "Semiconductor", "Oil & Gas", "Footwear", "Apparel", "Building")


def ok(x):
    return x is not None and not (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))


def g3(v, good, okv, higher=True):
    """2 = strong, 1 = ok, 0 = weak."""
    if not ok(v):
        return None
    if higher:
        return 2 if v >= good else 1 if v >= okv else 0
    return 2 if v <= good else 1 if v <= okv else 0


def cagr(a, b, n):
    if not (ok(a) and ok(b)) or a <= 0 or b <= 0 or n <= 0:
        return None
    return (b / a) ** (1 / n) - 1


def series(tab, key):
    """Ascending [(year, value)] from {date: {key: v}}."""
    out = [(d[:4], r.get(key)) for d, r in sorted(tab.items())]
    return [(y, v) for y, v in out if ok(v)]


def pct_rank(vals, v, higher=True):
    vals = [x for x in vals if ok(x)]
    if not ok(v) or len(vals) < 5:
        return None
    below = sum(1 for x in vals if (x < v if higher else x > v))
    eq = sum(1 for x in vals if x == v)
    return round(100 * (below + 0.5 * eq) / len(vals))


def fmt_pct(x, d=1, sign=False):
    return None if not ok(x) else (("+" if sign and x > 0 else "") + f"{x * 100:.{d}f}%")


def fmt_x(x, d=1):
    return None if not ok(x) else f"{x:.{d}f}x"


def card_grade(ms):
    sc = [m["score"] for m in ms if m.get("graded") and m.get("score") is not None]
    if len(sc) < 2:
        return "n/a"
    a = sum(sc) / len(sc)
    return "Strong" if a >= 1.45 else "OK" if a >= 0.75 else "Weak"


def M(label, value, score=None, graded=True, pct=None, note=None, raw=None, grp=None):
    return dict(label=label, value=value if value is not None else "–", score=score if graded else None,
                graded=graded and score is not None, pct=pct, note=note, raw=raw, grp=grp)


def build():
    raw = json.load(open(ROOT / "data/snapshot_raw.json"))
    scr = json.load(open(ROOT / "data/screen.json"))
    assets = {a["ticker"]: a for a in json.load(open(ROOT / "data/assets.json"))["assets"]}
    rows = {r["ticker"]: r for r in scr["rows"]}
    by_sector = {}
    for r in scr["rows"]:
        by_sector.setdefault(r.get("peer_group") or r.get("sector"), []).append(r)
    uop = raw.get("universe_op_margin") or {}
    opm = lambda r: r.get("operating_margin_pct") if ok(r.get("operating_margin_pct")) else (uop[r["ticker"]] * 100 if ok(uop.get(r["ticker"])) else None)
    for r in scr["rows"]:
        r["_opm"] = opm(r)
    by_ind = {}
    for r in scr["rows"]:
        if r.get("industry"):
            by_ind.setdefault(r["industry"], []).append(r)
    out = {"_about": __doc__.strip().split("\n")[0], "built_from": raw.get("fetched"), "stocks": {}}

    for t, R in raw["stocks"].items():
        if "error" in R or t not in assets:
            continue
        s = rows.get(t, {})
        grp = by_sector.get(s.get("peer_group") or s.get("sector"), [])
        P = lambda key, higher=True: pct_rank([x.get(key) for x in grp], s.get(key), higher)
        # margins differ by industry (software ~80% gross, hardware ~40%): rank them within the industry when it has
        # at least 8 companies with data, otherwise within the sector
        ind = by_ind.get(s.get("industry"), [])
        mgrp, mname = (ind, s.get("industry")) if sum(ok(x.get("_opm")) for x in ind) >= 8 else (grp, s.get("peer_group") or s.get("sector"))
        PM = lambda key: pct_rank([x.get(key) for x in mgrp], s.get(key), True)
        s_opm = s.get("_opm")
        inc, bal, cfs = R["annual"]["inc"], R["annual"]["bal"], R["annual"]["cfs"]
        mcap = s.get("market_cap") or ((R.get("price") or 0) * (R.get("shares") or 0)) or None
        price = R.get("price")

        # ---------- Earnings: is the company becoming more profitable?
        rv, ep, ni = series(inc, "rev"), series(inc, "eps"), series(inc, "ni")
        earn = [
            M("Revenue growth, latest quarter (YoY)", fmt_pct((s.get("rev_growth_pct") or 0) / 100 if ok(s.get("rev_growth_pct")) else None, sign=True),
              g3(s.get("rev_growth_pct"), 8, 0), pct=P("rev_growth_pct")),
            M(f"Revenue growth, {int(s.get('rev_cagr_years') or 3)}-year CAGR", fmt_pct(s["rev_cagr_pct"] / 100 if ok(s.get("rev_cagr_pct")) else None, sign=True),
              g3(s.get("rev_cagr_pct"), 8, 3), pct=P("rev_cagr_pct")),
            M("EPS growth, CAGR", fmt_pct(s["eps_cagr_pct"] / 100 if ok(s.get("eps_cagr_pct")) else None, sign=True), g3(s.get("eps_cagr_pct"), 10, 3), pct=P("eps_cagr_pct")),
            M("Earnings stability (variation)", None if not ok(s.get("earnings_cv")) else f"{s['earnings_cv']:.2f}", g3(s.get("earnings_cv"), 0.15, 0.35, higher=False),
              pct=P("earnings_cv", False), note="Year-to-year variation of earnings; lower is steadier."),
            M("P/E · forward P/E", None if not ok(s.get("pe")) else f"{s['pe']:.1f} · {s['forward_pe']:.1f}" if ok(s.get("forward_pe")) else f"{s['pe']:.1f}",
              graded=False, note="Graded under Valuation."),
        ]
        ecard = dict(key="earnings", title="Earnings", question="Is the company becoming more profitable?", metrics=earn,
                     trend=dict(label="EPS by year", points=[[y, round(v, 2)] for y, v in ep]) if len(ep) >= 2 else
                     dict(label="Revenue by year ($B)", points=[[y, round(v / 1e9, 2)] for y, v in rv]),
                     headline=[x for x in [f"EPS {fmt_pct(s['eps_cagr_pct'] / 100, 0, True)}/yr" if ok(s.get("eps_cagr_pct")) else None,
                                           f"sales {fmt_pct(s['rev_cagr_pct'] / 100, 0, True)}/yr" if ok(s.get("rev_cagr_pct")) else None] if x])

        # ---------- Cash flow: are profits turning into actual cash?
        fc, oc = series(cfs, "fcf"), series(cfs, "ocf")
        pairs = [(cfs[d]["fcf"], inc[d]["ni"]) for d in sorted(cfs) if d in inc and ok(cfs[d].get("fcf")) and ok(inc[d].get("ni"))]
        last3 = pairs[-3:]
        cv3 = sum(f for f, _ in last3) / sum(n for _, n in last3) if len(last3) >= 2 and sum(n for _, n in last3) > 0 else None
        cv1 = pairs[-1][0] / pairs[-1][1] if pairs and pairs[-1][1] > 0 else None
        swing = ok(cv3) and ok(cv1) and cv3 > 0 and abs(cv1 / cv3 - 1) > 0.30
        fi = assets[t].get("fcf_inputs") or {}
        fcf_ttm = float(fi["fcf"]) * 1e9 if ok(fi.get("fcf")) else (fc[-1][1] if fc else None)   # the model's (TTM / normalised) FCF
        rev_last = rv[-1][1] if rv else None
        fmargin = fcf_ttm / rev_last if ok(fcf_ttm) and ok(rev_last) and rev_last else None
        if ok(fmargin) and len(fc) and len(rv):           # prefer the same-year ratio
            fmargin = fc[-1][1] / rv[-1][1]
        yrs = sorted(d for d in cfs if d in inc and ok(inc[d].get("rev")) and inc[d]["rev"])
        fm = [(d[:4], cfs[d]["fcf"] / inc[d]["rev"]) for d in yrs if ok(cfs[d].get("fcf"))]
        fm_tr = fm[-1][1] - fm[0][1] if len(fm) >= 2 else None
        ly = yrs[-1] if yrs else None
        sbc_r = (cfs[ly]["sbc"] / inc[ly]["rev"]) if ly and ok(cfs[ly].get("sbc")) else None
        sbc_f = (cfs[ly]["sbc"] / cfs[ly]["fcf"]) if ly and ok(cfs[ly].get("sbc")) and ok(cfs[ly].get("fcf")) and cfs[ly]["fcf"] > 0 else None
        dep = lambda d: cfs[d].get("dep") if ok(cfs[d].get("dep")) else inc.get(d, {}).get("dep_inc")
        cd = [(d[:4], abs(cfs[d]["capex"]) / dep(d)) for d in yrs if ok(cfs[d].get("capex")) and ok(dep(d)) and dep(d) > 0]
        cd3 = sum(x for _, x in cd[-3:]) / len(cd[-3:]) if cd else None
        capex_rev = (abs(cfs[ly]["capex"]) / inc[ly]["rev"]) if ly and ok(cfs[ly].get("capex")) else None
        if ok(capex_rev) and capex_rev < 0.05:
            cd_word = "asset-light"     # capex tiny vs revenue: depreciation is mostly amortised acquisitions, so the ratio means little
        else:
            cd_word = None if not ok(cd3) else ("investing for growth" if cd3 > 1.5 else "about upkeep" if cd3 >= 0.8 else "below upkeep: check")
        dr = [(d[:4], dep(d) / inc[d]["rev"]) for d in yrs if ok(dep(d))]
        heavy = ok(s.get("capex_ocf_pct")) and s["capex_ocf_pct"] > 30
        cash = [
            M("Operating cash flow · free cash flow (latest year)", None if not (oc and fc) else f"${oc[-1][1] / 1e9:.2f}B · ${fc[-1][1] / 1e9:.2f}B", graded=False),
            M("FCF margin", fmt_pct(fmargin), g3(fmargin, 0.15, 0.05)),
            M("FCF margin trend", None if not ok(fm_tr) else f"{fm[0][1] * 100:.0f}% → {fm[-1][1] * 100:.0f}% ({fm[0][0]}–{fm[-1][0]}, {fm_tr * 100:+.1f} pts)",
              g3(fm_tr, 0.0, -0.03), note="Free cash flow as a share of revenue, first vs latest fiscal year: is the business becoming more or less cash-generative?"),
            M("Stock pay ÷ revenue", fmt_pct(sbc_r, 1), g3(sbc_r, 0.03, 0.08, False),
              note="Stock-based compensation ÷ revenue (latest fiscal year): a real cost paid in shares." + (f" It equals {sbc_f * 100:.0f}% of free cash flow." if ok(sbc_f) else "")),
            M("FCF / net income (3 years combined)", fmt_x(cv3, 2) if ok(cv3) else fmt_x(cv1, 2), g3(cv3 if ok(cv3) else cv1, 0.9, 0.6), pct=P("fcf_ni"),
              note="Free cash flow ÷ net income from the statements, same years. Above ~0.9x means profits arrive as cash."
                   + (f" Latest year {cv1:.2f}x: far from the 3-year norm (working-capital swing), so the 3-year figure is the one graded." if swing else "")),
            M("FCF growth, CAGR", fmt_pct(s["fcf_cagr_pct"] / 100 if ok(s.get("fcf_cagr_pct")) else None, sign=True), g3(s.get("fcf_cagr_pct"), 8, 0), pct=P("fcf_cagr_pct")),
            M("FCF stability (variation)", None if not ok(s.get("fcf_cv")) else f"{s['fcf_cv']:.2f}", g3(s.get("fcf_cv"), 0.25, 0.5, False), pct=P("fcf_cv", False)),
            M("Negative-FCF years", None if not ok(s.get("fcf_neg_years")) else f"{int(s['fcf_neg_years'])} of {int(s.get('fcf_years') or 0)}",
              g3(s.get("fcf_neg_years"), 0, 1, False)),
            M("Capex / operating cash flow", fmt_pct(s["capex_ocf_pct"] / 100 if ok(s.get("capex_ocf_pct")) else None, 0), g3(s.get("capex_ocf_pct"), 25, 50, False),
              pct=P("capex_ocf_pct", False), note="How much of the cash must be reinvested just to run and grow the business."),
            M("Capex ÷ depreciation (3-yr average)", None if not ok(cd3) else f"{cd3:.1f}x · {cd_word}", graded=False,
              note="Above ~1.5x the company is building new capacity; about 1x it is replacing what wears out; well below 1x it may be under-investing. Not good or bad on its own."
                   + (f" Capex is only {capex_rev * 100:.1f}% of revenue here, so depreciation is mostly amortisation of past acquisitions and the ratio says little." if cd_word == "asset-light" else "")),
            M("FCF yield", fmt_pct(fcf_ttm / mcap if ok(fcf_ttm) and mcap else None), graded=False, note="Graded under Valuation."),
        ] + ([M("Depreciation ÷ revenue", f"{dr[0][1] * 100:.1f}% → {dr[-1][1] * 100:.1f}% ({dr[0][0]}–{dr[-1][0]})", graded=False,
                note="Capital-heavy business: a rising share means past investment is weighing on future margins.")] if heavy and len(dr) >= 2 else [])
        ccard = dict(key="cash", title="Cash flow", question="Are its profits turning into actual cash?", metrics=cash,
                     trend=dict(label="FCF margin by year", points=[[y, round(v * 100, 1)] for y, v in fm], unit="%") if len(fm) >= 2 else
                     dict(label="Free cash flow by year ($B)", points=[[y, round(v / 1e9, 2)] for y, v in fc]),
                     headline=[x for x in [f"FCF margin {fmt_pct(fmargin, 0)}" if ok(fmargin) else None,
                                           f"{(cv3 if ok(cv3) else cv1):.2f}x net income" if ok(cv3) or ok(cv1) else None] if x])

        # ---------- Business performance: efficient and consistent?
        roic, nic = [], []          # nic: (year, NOPAT, invested capital) for incremental ROIC
        for d in sorted(inc):
            i, b = inc[d], bal.get(d, {})
            tr = (i.get("tax") / i["pretax"]) if ok(i.get("tax")) and ok(i.get("pretax")) and i["pretax"] > 0 else 0.21
            tr = min(max(tr, 0.0), 0.35)
            ic = (b.get("equity") or 0) + (b.get("debt") or 0) - (b.get("cash") or 0)
            if ok(i.get("op")) and ic > 0:
                roic.append((d[:4], i["op"] * (1 - tr) / ic)); nic.append((d[:4], i["op"] * (1 - tr), ic))
        gm = [(d[:4], r["gross"] / r["rev"]) for d, r in sorted(inc.items()) if ok(r.get("gross")) and ok(r.get("rev")) and r["rev"]]
        om = [(d[:4], r["op"] / r["rev"]) for d, r in sorted(inc.items()) if ok(r.get("op")) and ok(r.get("rev")) and r["rev"]]
        wacc = s.get("wacc")
        inc_roic, inc_note = None, None
        if len(nic) >= 3:
            (y0, n0, c0), (y1, n1, c1) = nic[max(0, len(nic) - 4)], nic[-1]
            if c1 - c0 > 0.05 * c0:
                inc_roic = (n1 - n0) / (c1 - c0); inc_note = f"{y0}–{y1}: extra after-tax operating profit ÷ extra invested capital"
            else:
                inc_note = f"Invested capital barely grew or shrank {y0}–{y1} (buybacks, asset-light), so the ratio isn't meaningful."
        rd = [(d[:4], inc[d]["rd"] / inc[d]["rev"]) for d in sorted(inc) if ok(inc[d].get("rd")) and ok(inc[d].get("rev")) and inc[d]["rev"]]
        above = sum(1 for _, x in roic if ok(wacc) and x > wacc)
        roic_tr = roic[-1][1] - roic[0][1] if len(roic) >= 2 else None
        om_tr = om[-1][1] - om[0][1] if len(om) >= 2 else None
        gm_tr = gm[-1][1] - gm[0][1] if len(gm) >= 2 else None
        perf = [
            M("ROIC vs cost of capital (WACC)", None if not ok(s.get("roic_pct")) else f"{s['roic_pct']:.0f}% vs {wacc * 100:.1f}%" if ok(wacc) else f"{s['roic_pct']:.0f}%",
              g3(s.get("roic_spread"), 0.10, 0.0), pct=P("roic_spread"), note="Return on the money invested in the business vs what that money costs."),
            M("ROIC trend", None if not ok(roic_tr) else f"{roic[0][1] * 100:.0f}% → {roic[-1][1] * 100:.0f}% ({roic[0][0]}–{roic[-1][0]})",
              g3(roic_tr, 0.0, -0.05)),
            M("ROIC above cost of capital", None if not roic or not ok(wacc) else f"{above} of {len(roic)} years", g3(above / len(roic) if roic and ok(wacc) else None, 0.99, 0.5),
              note="A lasting gap is the clearest measurable sign of a competitive advantage."),
            M("Incremental ROIC (3 years)", fmt_pct(inc_roic, 0) if ok(inc_roic) else ("n/a" if inc_note else None),
              g3(inc_roic, 0.15, wacc if ok(wacc) else 0.08) if ok(inc_roic) else None,
              note=(inc_note or "") + " Shows whether NEW investment earns good returns, not just the existing business."),
            M("Operating margin", fmt_pct(s_opm / 100 if ok(s_opm) else None, 1), g3(PM("_opm"), 60, 35), pct=PM("_opm"), grp=mname,
              note=f"Profit from the business itself, after all running costs. Graded against {mname} ({len(mgrp)} companies)."),
            M("Gross margin", fmt_pct(s["gross_margin_pct"] / 100 if ok(s.get("gross_margin_pct")) else None, 1), graded=False, pct=PM("gross_margin_pct"), grp=mname,
              note=f"After the cost of making the product: the purest pricing-power signal, but very industry-dependent (ranked against {mname}). Its trend is graded below."),
            M("Net margin", fmt_pct(s["profit_margin_pct"] / 100 if ok(s.get("profit_margin_pct")) else None, 1), graded=False, pct=PM("profit_margin_pct"), grp=mname,
              note=f"The bottom line, after interest, tax and one-offs; can be distorted by one-time items (ranked against {mname})."),
            M("Gross margin trend", None if not ok(gm_tr) else f"{gm_tr * 100:+.1f} pts", g3(gm_tr, 0.0, -0.02)),
            M("Operating margin trend", None if not ok(om_tr) else f"{om[0][1] * 100:.0f}% → {om[-1][1] * 100:.0f}% ({om_tr * 100:+.1f} pts)", g3(om_tr, 0.0, -0.02)),
            *([M("R&D ÷ revenue", f"{rd[-1][1] * 100:.1f}%" + (f" ({rd[0][1] * 100:.1f}% in {rd[0][0]})" if len(rd) >= 2 else ""), graded=False,
                 note="Research & development spending as a share of revenue: how much is reinvested to stay competitive.")] if rd else []),
            M("Revenue consistency (growth variation)", None if not ok(s.get("rev_growth_std")) else f"{s['rev_growth_std']:.1f} pts", g3(s.get("rev_growth_std"), 5, 12, False),
              pct=P("rev_growth_std", False)),
            M("Share count change a year", fmt_pct(s["share_change_pct_yr"] / 100 if ok(s.get("share_change_pct_yr")) else None, 1, True),
              g3(s.get("share_change_pct_yr"), -1, 1, False), note="Negative = buybacks shrink the share count; positive = dilution."),
        ]
        pcard = dict(key="performance", title="Business performance", question="Does it use capital efficiently and keep its edge?", metrics=perf,
                     trend=dict(label="ROIC by year", points=[[y, round(v * 100, 1)] for y, v in roic], unit="%", ref=round(wacc * 100, 1) if ok(wacc) else None)
                     if len(roic) >= 2 else dict(label="Operating margin by year", points=[[y, round(v * 100, 1)] for y, v in om], unit="%"),
                     headline=[x for x in ([f"ROIC {s['roic_pct']:.0f}%", f"vs WACC {wacc * 100:.1f}%" if ok(wacc) else None] if ok(s.get("roic_pct")) else
                                           [f"Gross margin {s['gross_margin_pct']:.0f}%" if ok(s.get("gross_margin_pct")) else None,
                                            f"op. margin {om[-1][1] * 100:.0f}%" if om else None]) if x],
                     note=None if ok(s.get("roic_pct")) or len(roic) >= 2 else "ROIC not meaningful (negative equity from buybacks); judged on margins and consistency.")

        # ---------- Financial strength: can it survive a downturn?
        qb = next(iter(R.get("quarterly_bal", {}).values()), {}) or {}
        cur = qb.get("cur_assets") / qb["cur_liab"] if ok(qb.get("cur_assets")) and ok(qb.get("cur_liab")) and qb["cur_liab"] else R["info"].get("currentRatio")
        qcash, qdebt = qb.get("cash", R["info"].get("totalCash")), qb.get("debt", R["info"].get("totalDebt"))
        nde = s.get("net_debt_ebitda")
        light = s.get("sector") in ("Technology", "Financial Services") or (s.get("industry") or "").startswith("Software")
        rl = s.get("risk_level")
        by = sorted(d for d in bal if ok(bal[d].get("inventory")) and d in inc and ok(inc[d].get("rev")))
        inv_g = sal_g = None; ly2 = by[-1] if by else ""
        if len(by) >= 2 and inc[by[-1]]["rev"] and bal[by[-1]]["inventory"] / inc[by[-1]]["rev"] >= 0.05 and bal[by[-2]]["inventory"] > 0:
            inv_g = bal[by[-1]]["inventory"] / bal[by[-2]]["inventory"] - 1; sal_g = inc[by[-1]]["rev"] / inc[by[-2]]["rev"] - 1
        fin = [
            M("Net debt / EBITDA", "net cash" if ok(nde) and nde < 0 else fmt_x(nde), g3(nde, 1.0, 3.0, False), pct=P("net_debt_ebitda", False)),
            M("Interest coverage", "no meaningful debt" if not ok(s.get("interest_coverage")) and (not ok(qdebt) or (qdebt or 0) < 1e8) else fmt_x(s.get("interest_coverage")),
              2 if not ok(s.get("interest_coverage")) and (not ok(qdebt) or (qdebt or 0) < 1e8) else g3(s.get("interest_coverage"), 10, 4), pct=P("interest_coverage")),
            M("Current ratio", fmt_x(cur, 2), g3(cur, 1.5, 0.8 if light else 1.0),
              note="Current assets ÷ current liabilities. Below 1 is normal for subscription and payment businesses (customers pay in advance)." if light else
              "Current assets ÷ current liabilities; above 1.5 is comfortable."),
            M("Cash vs debt", None if not (ok(qcash) and ok(qdebt)) else f"${qcash / 1e9:.1f}B cash vs ${qdebt / 1e9:.1f}B debt",
              g3((qcash / qdebt) if ok(qcash) and ok(qdebt) and qdebt else (9 if ok(qcash) else None), 1.0, 0.3)),
            M("Risk check (sector limits)", rl or None, {"Normal": 2, "Elevated": 1, "High": 0}.get(rl),
              note="; ".join((s.get("risk_serious") or []) + (s.get("risk_warn") or [])) or "No warnings on debt, interest cover or cash flow."),
            *([M("Inventory growth vs sales growth", f"inventory {inv_g * 100:+.0f}% vs sales {sal_g * 100:+.0f}% ({ly2[:4]})", g3(inv_g - sal_g, 0.05, 0.15, False),
                 note="Inventory growing much faster than sales can mean unsold stock and future discounts or write-downs.")] if ok(inv_g) and ok(sal_g) else []),
            M("Debt maturities", "not in free data", graded=False, note="Yahoo's free data has no maturity schedule; check the 10-K debt note before buying a leveraged name."),
        ]
        fcard = dict(key="strength", title="Financial strength", question="Can it withstand difficult years?", metrics=fin,
                     headline=[x for x in ["Net cash" if ok(nde) and nde < 0 else (f"Net debt {nde:.1f}x EBITDA" if ok(nde) else None),
                                           f"cover {s['interest_coverage']:.0f}x" if ok(s.get("interest_coverage")) else None] if x])

        # ---------- Dividends & buybacks: how much cash do I receive?
        dv = R["dividends"]
        dps = sorted(((int(y), v) for y, v in dv["by_year"].items()), key=lambda x: x[0])
        this_year = int((raw.get("fetched") or "2026")[:4])
        full = [(y, v) for y, v in dps if y < this_year]
        rate = R["info"].get("dividendRate")
        gaps = []
        # Yahoo sometimes misses a payment: a one-year dip that is fully back the next year (or in today's declared
        # rate) is treated as a data gap, not a cut.
        for i in range(1, len(full)):
            nxt = full[i + 1][1] if i + 1 < len(full) else (rate or 0)
            if full[i][1] < 0.7 * full[i - 1][1] and nxt >= 0.9 * full[i - 1][1]:
                gaps.append(full[i][0])
                full[i] = (full[i][0], (full[i - 1][1] + nxt) / 2)
        # a year counts as growth if the yearly total OR the annualised rate rose (robust to payment timing and frequency changes)
        pmax, pcnt = {}, {}
        for d_, v_ in dv.get("payments", []):
            y_ = int(d_[:4]); pmax[y_] = max(pmax.get(y_, 0), v_); pcnt[y_] = pcnt.get(y_, 0) + 1
        pmax = {y_: v_ * pcnt[y_] for y_, v_ in pmax.items()}     # annualised rate: largest payment x payments that year
        streak = 0
        for i in range(len(full) - 1, 0, -1):
            y0, y1 = full[i - 1][0], full[i][0]
            up = full[i][1] > full[i - 1][1] * 1.001 or (pmax.get(y1, 0) > pmax.get(y0, 0) * 1.001 and pmax.get(y0, 0) > 0)
            if up and y1 == y0 + 1:
                streak += 1
            else:
                break
        ttm = dv.get("ttm") or 0.0
        recent = dv.get("last_date") and dv["last_date"] >= f"{this_year - 1}-{(raw.get('fetched') or '2026-10')[5:7]}"
        payer = (ttm > 0 or (rate or 0) > 0) and bool(recent)
        dyield = (rate or ttm) / price if payer and price else 0.0
        g5 = None
        if len(full) >= 6 and full[-6][1] > 0:
            g5 = cagr(full[-6][1], full[-1][1], 5)
        ycf = sorted(cfs)
        last = cfs[ycf[-1]] if ycf else {}
        divp = -(last.get("div_paid") or 0.0)
        nbb = -(last.get("buyback") or 0.0) - (last.get("issued") or 0.0)
        bby = nbb / mcap if mcap else None
        po_ni = divp / last_ni if (last_ni := (ni[-1][1] if ni else None)) and divp > 0 else None
        po_fcf = divp / fc[-1][1] if fc and fc[-1][1] > 0 and divp > 0 else None
        cover = fc[-1][1] / divp if fc and divp > 0 else None
        cut = (payer and len(full) >= 2 and full[-1][0] == full[-2][0] + 1 and full[-1][1] < full[-2][1] * 0.95
               and pmax.get(full[-1][0], 0) < pmax.get(full[-2][0], 0) * 0.95)     # consecutive years, total AND annualised rate down
        div = [
            M("Dividend yield", fmt_pct(dyield, 2) if payer else "no dividend", graded=False, note="Not graded: a low yield isn't a weakness for a company that reinvests or buys back stock."),
            M("Dividend per share growth, 5-year CAGR", fmt_pct(g5, 1, True), g3(g5, 0.07, 0.02) if payer else None, graded=payer),
            M("Payout ratio (earnings · FCF)", None if not payer else f"{fmt_pct(po_ni, 0) or '–'} · {fmt_pct(po_fcf, 0) or '–'}", g3(po_fcf, 0.6, 0.9, False) if payer else None,
              graded=payer, note="Share of profits / free cash flow paid out; graded on FCF."),
            M("Dividend coverage (FCF ÷ dividends)", fmt_x(cover), g3(cover, 2.0, 1.2) if payer else None, graded=payer),
            M("Years of consecutive dividend growth", f"{streak}" if payer else "–", g3(streak, 10, 3) if payer else None, graded=payer,
              note="Calendar years with a higher dividend per share than the year before (Yahoo history)." + (f" Missing Yahoo data filled for {', '.join(map(str, gaps))}." if gaps else "")),
            M("Net buybacks (yield)", fmt_pct(bby, 1) if ok(bby) else None, g3(bby, 0.02, 0.0), note="Buybacks minus new shares issued, as a share of market value."),
            M("Shareholder yield (dividends + net buybacks)", fmt_pct((dyield or 0) + (bby or 0), 1) if ok(bby) else fmt_pct(dyield, 1), graded=False),
        ]
        if cut:
            div.insert(1, M("Latest full-year dividend", f"cut vs {full[-2][0]}", 0))
        reinvests = not payer and (not ok(bby) or bby < 0.003)
        dcard = dict(key="dividends", title="Dividends & buybacks", question="How much cash do I receive directly?", metrics=div,
                     trend=dict(label="Dividend per share by year", points=[[str(y), round(v, 3)] for y, v in full[-8:]]) if payer and len(full) >= 2 else None,
                     headline=[x for x in [f"Yield {fmt_pct(dyield, 1)}" if payer else "No dividend",
                                           f"+ {fmt_pct(bby, 1)} buybacks" if ok(bby) and bby > 0.002 else None,
                                           f"{streak} yrs growth" if payer and streak >= 3 else None] if x])
        if not payer and not reinvests:
            dcard["grade"] = "Strong" if bby >= 0.02 else "OK" if bby >= 0.005 else "Weak"
            dcard["note"] = "No dividend: graded on net buybacks only."
        if reinvests:
            dcard["grade"] = "Reinvests"
            dcard["headline"] = ["No dividend or net buybacks", "cash goes back into the business"]

        cards = [ecard, ccard, pcard, fcard, dcard]
        for c in cards:
            c.setdefault("grade", card_grade(c["metrics"]))
            for m in c["metrics"]:
                m.pop("raw", None)

        # ---------- valuation history (own range) for P/E, EV/EBITDA, FCF yield
        mp = R.get("monthly_prices", {})
        mkeys = sorted(mp)
        splits = sorted(R.get("splits", {}).items())
        sh_now = R.get("shares")

        def price_at(d):
            k = d[:7]
            cands = [m for m in mkeys if m <= k]
            return mp[cands[-1]] if cands else None

        hist = dict(pe=[], ev_ebitda=[], fcf_yield=[])
        for d in sorted(inc):
            i, b, c = inc[d], bal.get(d, {}), cfs.get(d, {})
            p = price_at(d)
            sh = b.get("shares")
            if not (ok(p) and ok(sh) and sh_now):
                continue
            f = 1.0
            for sd, r in splits:
                if sd > d:
                    f *= r
            # statements may or may not be restated for later splits: use whichever share count is closer to today's
            sh_adj = min((sh, sh * f), key=lambda x: abs(math.log(x / sh_now)))
            mc = p * sh_adj
            if ok(i.get("ni")) and i["ni"] > 0:
                hist["pe"].append([d[:4], round(mc / i["ni"], 1)])
            if ok(i.get("ebitda")) and i["ebitda"] > 0:
                hist["ev_ebitda"].append([d[:4], round((mc + (b.get("debt") or 0) - (b.get("cash") or 0)) / i["ebitda"], 1)])
            if ok(c.get("fcf")):
                hist["fcf_yield"].append([d[:4], round(c["fcf"] / mc * 100, 2)])
        net_debt = (qdebt or 0) - (qcash or 0)
        live = dict(ttm_ni=None, trailing_eps=R["info"].get("trailingEps"), ebitda=R["info"].get("ebitda"), net_debt=net_debt, shares=R.get("shares"),
                    fcf_ttm=fcf_ttm, ttm_dps=ttm if payer else 0.0)
        sect = dict(pe=P("pe", False), ev_ebitda=P("ev_ebitda", False), fcf_yield=P("fcf_yield_pct"), name=s.get("peer_group") or s.get("sector"), n=len(grp))
        now = dict(pe=s.get("pe"), ev_ebitda=s.get("ev_ebitda"), fcf_yield=(fcf_ttm / mcap * 100) if ok(fcf_ttm) and mcap else s.get("fcf_yield_pct"))

        # ---------- static flags (the page adds price-based ones)
        notes = (assets[t].get("notes") or "")
        flags = []
        if "FCF NORMALISED" in notes:
            flags.append(dict(t="FCF normalised", d="The model uses a lower free cash flow than reported (one-off working-capital swing); see Notes."))
        if "ESTIMATE" in notes:
            flags.append(dict(t="Estimated input", d="Stock pay (SBC) is estimated, not from filings."))
        if "STANDALONE" in notes or re.search(r"\bpending\b", notes, re.I):
            flags.append(dict(t="Pending deal", d="A pending transaction would change the per-share value; this is a standalone valuation."))
        if s.get("sector") in CYCLICAL_SECTORS or any(k in (s.get("industry") or "") for k in CYCLICAL_INDUSTRIES) or t in ("FIX", "APA"):
            flags.append(dict(t="Cyclical", d="Results swing with the economic or industry cycle: judge it on several years, not the latest one."))
        if ok(s.get("share_change_pct_yr")) and s["share_change_pct_yr"] > 1.5:
            flags.append(dict(t=f"Dilution {s['share_change_pct_yr']:.1f}%/yr", d="The share count is rising: each share owns a shrinking slice."))
        for w in (s.get("risk_serious") or []):
            flags.append(dict(t="Risk", d=w))
        if cut:
            flags.append(dict(t="Dividend cut", d=f"Dividend per share fell in {full[-1][0]}."))
        if swing:
            flags.append(dict(t="Cash swing", d=f"Free cash flow was {cv1:.2f}x net income last year vs {cv3:.2f}x over 3 years: a working-capital or capex swing, so one year can mislead."))
        if s.get("data_confidence") == "Low":
            flags.append(dict(t="Low data confidence", d="Several inputs are missing or estimated."))
        tv = assets[t].get("tv_share")
        if ok(tv) and tv > 0.62:
            flags.append(dict(t=f"{tv * 100:.0f}% of value after year 10", d="Most of the value depends on the long run, so small changes in long-term assumptions move it a lot."))

        prices = [[k, mp[k]] for k in mkeys[-25:]]
        out["stocks"][t] = dict(all_checks=bool(s.get("all_checks")), checks=[dict(q=x["q"], v=x["v"]) for x in (s.get("answers") or [])], cards=cards, valuation=dict(history=hist, now=now, sector_pct=sect, live=live), prices=prices, flags=flags,
                                cyclical=any(f["t"] == "Cyclical" for f in flags))
    json.dump(out, open(ROOT / "data/snapshot.json", "w"), separators=(",", ":"))
    print("snapshot:", len(out["stocks"]), "stocks")
    return out


if __name__ == "__main__":
    build()
