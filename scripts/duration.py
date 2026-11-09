#!/usr/bin/env python3
"""How far away is the value? Duration and distant cash-flow checks for each modelled stock -> data/duration.json.
Information only: nothing here changes a fair value, a rating or a margin of safety.

Four questions from Durand's "Growth stocks and the Petersburg paradox" (1957), asked of the model's own cash flows
(model/model.py: same engine, inputs, advantage period, segments and 30/50/20 weights):
  horizon     share of each case's operating value (before net debt) received in years 1-5, 6-10, 11-20, 21-30 and
              after year 30, and the year by which half of it has arrived. The value after the last forecast year is a
              growing perpetuity, so its first m years are worth pv_tv x (1 - ((1 + g) / (1 + r))^m): every stock is cut
              at the same years whatever its advantage period. Underwriters: cash to shareholders (net income - growth in
              book value) and the value after the last year, the same way.
  duration    % change in the 30/50/20 fair value for a 1-point fall and a 1-point rise in the required return, and the
              equity duration (average of the two, per point). Next to it the modified duration of a 10-year and a
              30-year Treasury bought at par at today's 10-year yield (GS10, data/bond_yields.json; no 30-year series, so
              the 10-year yield is used for both). Assumes a rate move passes fully into the required return.
  stress      the 30/50/20 fair value if the edge ends early, at the same required return:
                one class lower   wide -> narrow -> none -> edge ends at year 10 (data/moat.json rules)
                ends at year 10   growth fades from year 1 to year 10 only, then new investment earns only the required
                                  return (terminal cash flow x (1 - 2.5% / r) / (1 - 2.5% / RONIC), RONIC = the class's
                                  return on new investment, 20% for wide)
              'short' stocks are already valued over 10 years with growth at or below 2.5%: not tested.
  reliability concerns about the distant cash flows (see CONCERNS); 0 = well supported, 1 = some reliance on distant
              cash, 2+ = leans on distant cash.
  mos         suggested margin of safety = the stock's own + 2.5 points per concern other than 'price', at most +10
              points. Shown in the drawer, not applied: the official buy-below keeps data/assets.json's margin.

Usage: python scripts/duration.py   (after model/model.py; reads data/moat_scorecard.json, data/returns.json,
       data/bond_yields.json and data/assets.json for the advantage period the price needs)
"""
import datetime, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/duration.json"
src = (ROOT / "model/model.py").read_text().split("out = {")[0]
M = {"__file__": str(ROOT / "model/model.py")}
exec(src, M)                                       # STOCKS, INSURERS, FIN, PROBS, GT, dcf, ri_value, moat_of, ...
J = lambda p, d=None: json.load(open(ROOT / p)) if (ROOT / p).exists() else d
PROBS, GT = M["PROBS"], M["GT"]
CLASSES = M["MOAT"]["classes"]
LOWER = {"wide": "narrow", "narrow": "none", "none": "end10"}
BUCKETS = [(1, 5), (6, 10), (11, 20), (21, 30), (31, None)]
MS = J("data/moat_scorecard.json", {"stocks": {}})["stocks"]
RET = J("data/returns.json", {"stocks": {}})["stocks"]
ASSETS = {a["ticker"]: a for a in J("data/assets.json")["assets"]}

# Reliability: each true line is one concern about the distant cash flows.
LIMITS = dict(beyond10=0.60, end10_loss=0.15, half_life=5)
# Suggested margin of safety (shown, NOT applied; review after the Q4 2026 earnings round): the stock's own margin plus
# MOS_STEP for each distant-cash concern, at most MOS_CAP. The 'price' concern is left out: the margin of safety
# already deals with price, so it would be counted twice.
MOS_STEP, MOS_CAP = 0.025, 0.10
CONCERNS = [
    ("beyond10", "More than 60% of the base value arrives after year 10"),
    ("end10", "Fair value falls more than 15% if the edge ends at year 10"),
    ("score", "The moat scorecard suggests a lower class than the model uses"),
    ("fade", "Returns above the hurdle are halving in under 5 years"),
    ("price", "Today's price needs a longer advantage period than ours"),
]
RANK = {"none": 0, "short": 0, "narrow": 1, "wide": 2}


def horizon(d, r, g=GT):
    """Shares of operating value by year bucket, and the year by which half has arrived. d = dcf()/ri_value() detail."""
    rows, n, ev = d["rows"], len(d["rows"]), d["ev"]
    if not ev or ev <= 0: return None
    q = (1 + g) / (1 + r)
    cum = lambda y: (sum(x["pv"] for x in rows if x["t"] <= y) if y <= n else d["pv_fcf"] + d["pv_tv"] * (1 - q ** (y - n)))
    sh = []
    for lo, hi in BUCKETS:
        top = cum(hi) if hi else ev
        sh.append((top - cum(lo - 1)) / ev)
    half = next((y for y in range(1, 400) if cum(y) >= ev / 2), None)
    return dict(shares=[round(x, 4) for x in sh], half_year=half, beyond10=round(sum(sh[2:]), 4), beyond20=round(sum(sh[3:]), 4))


def treasury_duration(y, years):
    """Modified duration of a par bond with semi-annual coupons at yield y."""
    return (1 - (1 + y / 2) ** (-2 * years)) / y


def stock_values(tk):
    """Returns (value(mo, r) -> 30/50/20 fair value, base detail, case details, required return, moat class)."""
    s, f = M["STOCKS"][tk], M["FIN"][tk]
    r = M["req_return"](tk)
    sg = M["segments_of"](tk)
    aint = f["interest"] * (1 - f["tax"])                       # fcff_re: free cash flow before interest
    add = aint / s["rev"]
    m0 = (s["fcf"] - s["sbc"] + aint) / s["rev"]
    nc = s["net_cash"] + s["extra"]
    S2 = {k: dict(v, m=v["m"] + add) for k, v in s["scen"].items()}
    cls = M["moat_of"](tk)["cls"]

    def mo_for(c):
        if c == "end10": return dict(cap_years=10, ronic_forecast=None, cls="end10")
        return dict(CLASSES[c], cls=c, r_req=r)

    def case(k, mo, rate, detail=False):
        p = S2[k]
        if mo["cls"] != "end10":
            return M["dcf"](s["rev"], m0, p["g1"], p["g10"], p["m"], rate, nc, s["shares"], detail=detail, mo=mo, sg=sg)
        # Edge ends at year 10: years 1-10 as in the model, then new investment earns only the required return. The
        # terminal cash flow is scaled by the value-driver factor (1 - 2.5% / r) / (1 - 2.5% / RONIC), the same
        # reinvestment the full-length model has in its last year (growth 2.5%), so cutting the period never frees cash.
        d = M["dcf"](s["rev"], m0, p["g1"], p["g10"], p["m"], rate, nc, s["shares"], detail=True, mo=mo, sg=sg)
        rf = CLASSES[cls].get("ronic_forecast") or 0.20
        k_ = (1 - GT / r) / (1 - GT / rf)
        return d["per_share"] + (k_ - 1) * d["pv_tv"] / s["shares"]

    value = lambda c, rate=r: sum(PROBS[k] * case(k, mo_for(c), rate) for k in PROBS)
    det = {k: case(k, mo_for(cls), r, True) for k in PROBS}
    return value, det, r, cls


def insurer_values(tk):
    s = M["INSURERS"][tk]
    r = M["req_return"](tk)
    cls = M["moat_of"](tk)["cls"]

    def mo_for(c):
        if c == "end10": return dict(CLASSES["none"], cap_years=11, cls="none", r_req=r)     # shortest an insurer path allows
        return dict(CLASSES[c], cls=c, r_req=r)

    def case(k, mo, rate, detail=False):
        p = s["scen"][k]
        return M["ri_value"](s["bv"], s["roe0"], p["g1"], p["g10"], p["m"], rate, s["extra"], s["shares"], detail=detail, mo=mo)

    value = lambda c, rate=r: sum(PROBS[k] * case(k, mo_for(c), rate) for k in PROBS)
    det = {k: case(k, mo_for(cls), r, True) for k in PROBS}
    return value, det, r, cls


def main():
    bond = J("data/bond_yields.json", {})
    g10 = bond.get("monthly", {}).get("GS10", {})
    ym, y10 = (sorted(g10.items())[-1] if g10 else (None, 4.5))
    y = y10 / 100
    tsy = dict(yield_pct=y10, month=ym, d10=round(treasury_duration(y, 10), 1), d30=round(treasury_duration(y, 30), 1))
    stocks = {}
    for tk in list(M["STOCKS"]) + list(M["INSURERS"]):
        ins = tk in M["INSURERS"]
        value, det, r, cls = (insurer_values if ins else stock_values)(tk)
        fv = value(cls)
        if fv <= 0: continue
        up, dn = value(cls, r - 0.01) / fv - 1, value(cls, r + 0.01) / fv - 1
        dur = (up - dn) / 2 / 0.01
        hz = {k: horizon(det[k], r) for k in det}
        stress = None
        if cls != "short":
            low = LOWER[cls]
            v_low, v_10 = value(low), value("end10")
            stress = dict(lower=low, lower_fv=round(v_low, 2), lower_chg=round(v_low / fv - 1, 4),
                          end10_fv=round(v_10, 2), end10_chg=round(v_10 / fv - 1, 4))
        ms, rt, a = MS.get(tk) or {}, RET.get(tk) or {}, ASSETS.get(tk) or {}
        cap, years = a.get("implied_cap"), a.get("cap_years") or (M["ri_years"](M["moat_of"](tk)) if ins else M["moat_of"](tk).get("cap_years", 10))
        hb = hz["base"] or {}
        flags = dict(
            beyond10=hb.get("beyond10", 0) > LIMITS["beyond10"],
            end10=bool(stress and stress["end10_chg"] < -LIMITS["end10_loss"]),
            score=bool(ms.get("suggested") and RANK.get(ms["suggested"], 0) < RANK.get(cls, 0)),
            fade=rt.get("half_life") is not None and 0 < rt["half_life"] < LIMITS["half_life"],
            price=cap is not None and cap > years,
        )
        n = sum(flags.values())
        counted = [k for k, v in flags.items() if v and k != "price"]
        mos0 = a.get("mos")
        mos = None if mos0 is None else dict(current=mos0, extra=min(MOS_CAP, MOS_STEP * len(counted)), counted=counted)
        if mos: mos["suggested"] = round(mos0 + mos["extra"], 4)
        stocks[tk] = dict(
            kind="insurer" if ins else "stock", moat=cls, cap_years=years, r=r, fv=round(fv, 2),
            horizon={k: v for k, v in hz.items() if v},
            duration=dict(years=round(dur, 1), up=round(up, 4), down=round(dn, 4),
                          vs=("shorter than a 10-year Treasury" if dur < tsy["d10"] else "longer than a 30-year Treasury" if dur > tsy["d30"]
                              else "between a 10- and a 30-year Treasury")),
            stress=stress, mos=mos,
            reliability=dict(concerns=[k for k, v in flags.items() if v], n=n,
                             label="well supported" if n == 0 else "some reliance on distant cash" if n == 1 else "leans on distant cash",
                             half_life=rt.get("half_life"), score=ms.get("total"), suggested=ms.get("suggested"), implied_cap=cap),
        )
    doc = {"_about": __doc__.strip().split("\n\n")[0], "built": datetime.date.today().isoformat(),
           "buckets": ["1-5", "6-10", "11-20", "21-30", "30+"], "treasury": tsy, "limits": LIMITS, "mos_rule": dict(step=MOS_STEP, cap=MOS_CAP, applied=False, review="after the Q4 2026 earnings round (about February 2027)"),
           "concerns": {k: t for k, t in CONCERNS}, "stocks": stocks}
    json.dump(doc, open(OUT, "w"), indent=None, separators=(",", ":"))
    ds = sorted(v["duration"]["years"] for v in stocks.values())
    lab = {}
    for v in stocks.values(): lab[v["reliability"]["label"]] = lab.get(v["reliability"]["label"], 0) + 1
    print(f"duration.json: {len(stocks)} stocks; equity duration median {ds[len(ds) // 2]} (10-yr Treasury {tsy['d10']}, 30-yr {tsy['d30']}); {lab}")


if __name__ == "__main__":
    main()
