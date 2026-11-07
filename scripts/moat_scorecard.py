#!/usr/bin/env python3
"""Moat scorecard (question 4: how durable is the competitive advantage?) -> data/moat_scorecard.json.

Two halves, 5 points each, 10 in all:
  Sources (judgement, data/moat_sources.json): network effects, switching costs, intangibles, cost advantage and
    efficient scale, each 0-2. Score = strongest source x 1.25 + 0.5 for each other source scored 2 and 0.25 for each
    scored 1 (max 5).
  Numbers (filings, data/returns.json and data/backtest/facts.json.gz):
    persistence  0-2  share of the last 10 years with ROIC at least 5 points above the required return, x 2
    fade         0-1  1 = not fading, 0.5 = fading slowly (excess half-life 8+ years), 0 = fading fast or at the hurdle
    new money    0-1  1 = returns on new investment holding up, 0.5 = diminishing, 0 = below hurdle
    margins      0-1  gross margin over 10 years: 1 = moved less than 3 points (std. dev.), 0.5 = less than 6, 0 = more
  Unanswered is never positive (Nov 2026): a part that can't be measured scores 0 and is listed in "unknown". When the
  whole filings half can't be measured (invested capital at or below zero), the score is out of 5 (sources only) and
  no class is suggested.
Suggested class: 7.5+ wide, 5+ narrow, else none; "short" (growth at or below 2.5%) is kept, since it is set by growth.
The suggestion is shown next to the class in data/moat.json and never changes it: edit moat.json to act on it.
"""
import gzip, json, pathlib, statistics as st

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = json.load(open(ROOT / "data/moat_sources.json"))
RET = json.load(open(ROOT / "data/returns.json"))["stocks"]
MOAT = json.load(open(ROOT / "data/moat.json"))["stocks"]
FACTS = ROOT / "data/backtest/facts.json.gz"
F = json.load(gzip.open(FACTS)) if FACTS.exists() else {}
KEYS = ["n", "s", "i", "c", "e"]

def gm_std(t):
    d = F.get(t) or {}; rev = d.get("revenue") or {}; gp = d.get("gross_profit") or {}; cor = d.get("cost_of_revenue") or {}
    g = []
    for y in sorted(rev)[-10:]:
        rv = rev[y][0] if isinstance(rev[y], list) else rev[y]
        if not rv: continue
        if y in gp: g.append((gp[y][0] if isinstance(gp[y], list) else gp[y]) / rv)
        elif y in cor: g.append(1 - (cor[y][0] if isinstance(cor[y], list) else cor[y]) / rv)
    return (st.pstdev(g), len(g)) if len(g) >= 5 else (None, len(g))

def score(t):
    s = SRC["stocks"][t]; v = sorted((s[k] for k in KEYS), reverse=True)
    src = min(5, v[0] * 1.25 + sum(0.5 if x == 2 else 0.25 if x == 1 else 0 for x in v[1:]))
    x = RET.get(t, {}); r = x.get("r")
    num, parts = None, {}
    if not x.get("note") and x.get("roic"):
        last10 = x["roic"][-10:]
        parts["persistence"] = round(2 * sum(1 for _, v_ in last10 if v_ >= r + 0.05) / len(last10), 2)
        hl = x.get("half_life")
        parts["fade"] = 1 if x.get("q2") == "not fading" else 0.5 if x.get("q2") == "fading" and hl and hl >= 8 else 0
        parts["new_money"] = {"holding up": 1, "diminishing": 0.5, "below hurdle": 0}.get(x.get("q1"))
        sd, n = gm_std(t)
        parts["margins"] = None if sd is None else 1 if sd < 0.03 else 0.5 if sd < 0.06 else 0
        parts["gm_std"] = None if sd is None else round(sd, 4)
        num = sum(parts[k] or 0 for k in ("persistence", "fade", "new_money", "margins"))
    unknown = ["filings"] if num is None else [k for k in ("new_money", "margins") if parts.get(k) is None]
    total = src + (num or 0)
    cur = (MOAT.get(t) or {}).get("moat")
    sug = None if num is None else "short" if cur == "short" else "wide" if total >= 7.5 else "narrow" if total >= 5 else "none"
    return dict(sources={k: s[k] for k in KEYS}, why=s["why"], risk=s["risk"], src=s.get("src"),
                source_score=round(src, 2), numbers_score=None if num is None else round(num, 2), parts=parts, unknown=unknown,
                total=round(total, 1), out_of=5 if num is None else 10, suggested=sug, current=cur, differs=sug is not None and sug != cur)

out = {"_about": __doc__.strip().split("\n")[0] + " See scripts/moat_scorecard.py for the scoring.", "checked": SRC.get("checked"),
       "stocks": {t: score(t) for t in SRC["stocks"]}}
json.dump(out, open(ROOT / "data/moat_scorecard.json", "w"), indent=1)
d = [t for t, x in out["stocks"].items() if x["differs"]]
print("scorecard:", len(out["stocks"]), "stocks;", len(d), "differ from moat.json:", ", ".join(f"{t} {out['stocks'][t]['current']}->{out['stocks'][t]['suggested']}" for t in d))
