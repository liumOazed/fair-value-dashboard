#!/usr/bin/env python3
"""Monthly Fair Value Table: pick the 5 most undervalued stocks from the current Top 50 (quick estimates).

Steps
1. Candidates = this month's Top 50 by Growth Quality Score, the 5 resilient compounders and every stock passing all
   5 quick checks (data/screen.json; the 5/5 group joined from November 2026).
2. Sanity filters (a stock is skipped, with the reason recorded, if any apply):
   financial company (FCF not meaningful) | FCF distorted (FCF < 25% of earnings) | FCF unusually high (> 1.5x earnings)
   | acquisition-like growth (sales > +40% with net margin < 5%) | one-off growth (> +100%) | loss-making | no P/E
   | sales growth changed by more than 30 points since the last real month (acquisition, one-off or commodity swing)
   | free cash flow flipped sign since the last real month (unstable cash flow)
   | high debt (net debt > 4x EBITDA) | weak interest cover (EBIT < 3x interest)
3. Quick fair value (same idea as the full model, simplified to what the CSV has):
   cash yield  = the LOWER of FCF yield and TRAILING earnings yield (actual results, not forecasts; forward P/E only if
                 trailing is missing); cyclical sectors x 0.8 (mid-cycle haircut)
   growth base = recent sales growth, clipped 0-40% (cyclical sectors capped at 10%)
   Bear / Base / Bull: year-1 growth = 25% / 50% / 75% of that (caps 8% / 15% / 25%), fading to 2% / 3% / 4% by year 10
   10-year DCF at the sector required return + 2.5% terminal growth; weights 30 / 50 / 20
   value-to-price = cash yield x DCF multiple  ->  fair value per share = value-to-price x price at evaluation
   margin of safety 30% (35% for cyclical sectors)
4. Top 5 = highest value-to-price, at most 2 per sector. A value-to-price above 2.5x is treated as "too cheap to trust
   without checking" and goes to a Check-first list instead of the picks.
Writes data/fair_value_table.json (keeps every past month so picks can be tracked).
Usage: python scripts/fair_value_table.py
"""
import json, pathlib, datetime, urllib.request, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
S = json.load(open(ROOT / "data/screen.json"))
CYCLICAL = {"Energy", "Basic Materials"}
GT, W = 0.025, (0.3, 0.5, 0.2)
SCEN = {"bear": (0.25, 0.08, 0.02), "base": (0.50, 0.15, 0.03), "bull": (0.75, 0.25, 0.04)}   # share of hist growth, cap, year-10 growth

def multiple(g1, g10, R):
    """PV of a cash stream starting at 1 (year-0 cash), growth fading g1 -> g10, plus terminal value."""
    cf, pv = 1.0, 0.0
    for t in range(1, 11):
        g = g1 + (g10 - g1) * (t - 1) / 9
        cf *= 1 + g; pv += cf / (1 + R) ** t
    return pv + cf * (1 + GT) / ((R - GT) * (1 + R) ** 10)

PREV = {}
if S.get("prev_month"):
    try: PREV = {x["ticker"]: x for x in json.load(open(ROOT / f"data/cache/scores_{S['prev_month']}.json"))["rows"]}
    except Exception as e: print("previous month not cached, stability checks skipped:", e, file=sys.stderr)
TOO_CHEAP = 2.5

def skip_reason(r):
    q = PREV.get(r["ticker"])
    ey, fy, conv, g, m = r["earnings_yield"], r["fcf_yield_pct"], r["fcf_conversion"], r["rev_growth_pct"], r["profit_margin_pct"]
    if r["sector"] == "Financial Services" and not r.get("peer_group"): return "Financial company: free cash flow is not meaningful"
    if ey is None: return "No P/E (no earnings to cross-check)"
    if m is not None and m < 0: return "Loss-making"
    if fy is None or fy <= 0 or (conv is not None and conv < 0.25): return "FCF distorted (cash flow far below earnings)"
    if conv is not None and conv > 1.5: return "FCF unusually high (more than 1.5x earnings, may not last)"
    if g is not None and g > 100: return "One-off growth (sales more than doubled)"
    if g is not None and g > 40 and m is not None and m < 5: return "Acquisition-like growth (sales up >40% on a thin margin)"
    nde, cov = r.get("net_debt_ebitda"), r.get("interest_coverage")
    if nde is not None and nde > 4: return f"High debt (net debt {nde:.1f}x EBITDA)"
    if cov is not None and cov < 3 and nde is not None and nde > 0: return f"Weak interest cover (EBIT only {cov:.1f}x interest)"
    if q is not None and g is not None and q.get("rev_growth_pct") is not None and abs(g - q["rev_growth_pct"]) > 30:
        return f"Sales growth swung from {q['rev_growth_pct']:.0f}% to {g:.0f}% since {S['prev_month']} (acquisition, one-off or commodity cycle)"
    if q is not None and q.get("fcf_yield_pct") is not None and (q["fcf_yield_pct"] <= 0) != (fy <= 0):
        return f"Free cash flow flipped sign since {S['prev_month']} (unstable)"
    return None

def evaluate(r):
    cyc = r["sector"] in CYCLICAL
    tey = 100 / r["pe"] if (r["pe"] or 0) > 0 else r["earnings_yield"]       # trailing earnings yield
    y = min(r["fcf_yield_pct"], tey) / 100 * (0.8 if cyc else 1)
    gh = min(max(r["rev_growth_pct"] or 0, 0), 10 if cyc else 40) / 100
    R = r["required_return"]
    sc = {}
    for k, (share, cap, g10) in SCEN.items():
        g1 = min(gh * share, cap)
        sc[k] = dict(g1=round(g1, 4), g10=g10, ratio=round(y * multiple(g1, g10, R), 4))
    ratio = sum(w * sc[k]["ratio"] for w, k in zip(W, SCEN))
    mos = 0.35 if cyc else 0.30
    return dict(cash_yield=round(y, 4), cash_basis="FCF" if r["fcf_yield_pct"] <= tey else "trailing earnings", trailing_ey=round(tey, 2),
                cyclical=cyc, growth_input=round(gh, 4), required_return=R, scenarios=sc, value_to_price=round(ratio, 4), mos=mos)

def price(t):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=5d&interval=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        return round(json.load(urllib.request.urlopen(req, timeout=20))["chart"]["result"][0]["meta"]["regularMarketPrice"], 2)
    except Exception as e:
        try: return json.load(open(ROOT / "data/prices.json"))["prices"][t]["price"]
        except Exception: print("no price for", t, e, file=sys.stderr); return None

def main():
    top = [r for r in S["rows"] if r["top50"] or r.get("resilient_pick") or r.get("checks_pick")]   # top 50 + resilient + all 5 checks
    picks, skipped, ranked = [], [], []
    for r in top:
        why = skip_reason(r)
        if why: skipped.append(dict(ticker=r["ticker"], name=r["name"], reason=why)); continue
        ranked.append((r, evaluate(r)))
    ranked.sort(key=lambda x: -x[1]["value_to_price"])
    check = [dict(ticker=r["ticker"], name=r["name"], sector=r["sector"], value_to_price=ev["value_to_price"],
                  reason=f"Looks {ev['value_to_price']:.1f}x undervalued: too cheap to trust without checking for one-off gains or data errors")
             for r, ev in ranked if ev["value_to_price"] > TOO_CHEAP]
    ranked = [x for x in ranked if x[1]["value_to_price"] <= TOO_CHEAP]
    per_sector = {}
    for r, ev in ranked:
        if len(picks) == 5: break
        if per_sector.get(r["sector"], 0) >= 2: continue
        per_sector[r["sector"]] = per_sector.get(r["sector"], 0) + 1
        p = price(r["ticker"])
        fair = None if p is None else round(p * ev["value_to_price"], 2)
        picks.append(dict(ticker=r["ticker"], name=r["name"], sector=r["sector"], score=r["score"], rank=r["rank"], consistent=r["consistent"],
                          has_full_model=r["has_fair_value"], price_at_eval=p, fair_value=fair,
                          buy_below=None if fair is None else round(fair * (1 - ev["mos"]), 2),
                          scenario_values=None if p is None else {k: round(p * v["ratio"], 2) for k, v in ev["scenarios"].items()},
                          metrics=dict(rev_growth_pct=r["rev_growth_pct"], fcf_yield_pct=r["fcf_yield_pct"], earnings_yield=r["earnings_yield"],
                                       fcf_conversion=r["fcf_conversion"], profit_margin_pct=r["profit_margin_pct"], forward_pe=r["forward_pe"]), **ev))
    runners = [dict(ticker=r["ticker"], name=r["name"], sector=r["sector"], value_to_price=ev["value_to_price"])
               for r, ev in ranked if r["ticker"] not in {p["ticker"] for p in picks}][:10]
    f = ROOT / "data/fair_value_table.json"
    try: out = json.load(open(f))
    except Exception: out = {"months": {}}
    out["months"][S["month"]] = dict(month=S["month"], evaluated=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
                                     candidates=len(top), passed=len(ranked), picks=picks, runners_up=runners, check_first=check, skipped=skipped,
                                     method=f"Score v{S.get('score_version', 2)}, shared required returns, balance-sheet filter",
                                     prev_month=S.get("prev_month"))
    out["latest"] = max(out["months"])
    json.dump(out, open(f, "w"), indent=1)
    print(f"{S['month']}: {len(top)} candidates, {len(skipped)} skipped, {len(check)} check-first, {len(ranked)} valued")
    for p in picks: print(f"  {p['ticker']:6} {p['sector']:24} value/price {p['value_to_price']:.2f}  price {p['price_at_eval']}  fair {p['fair_value']}")

if __name__ == "__main__": main()
