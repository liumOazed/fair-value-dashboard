#!/usr/bin/env python3
"""Price-drop watch: the four-step check when a Fair Value stock falls (runs on GitHub after every price update).

Step 1 (trigger), compared with QQQ over the same window:
  * day:  down 7%+ since the previous close and at least 5 points worse than QQQ
  * week: down 12%+ over 5 sessions and at least 5 points worse than QQQ
  * high: 25%+ below its 52-week high and at least 5 points further below its high than QQQ
    (a "slide": shown in a quieter list; day/week triggers are "alerts")
  * EMERGENCY: down 12%+ in a day or 20%+ in a week AND at least 10 points worse than QQQ
    (a quick Claude check the next morning instead of waiting for the twice-weekly review)
Step 2 evidence (Yahoo via yfinance, refreshed at most once a day per event): QQQ move, industry peers' median move,
  an earnings report in the days before, analysts' EPS-estimate revisions, latest headlines, plus a provisional cause.
  The verdict (temporary vs lasting, and why) is written by Claude:  --verdict (see below).
Steps 3-4 are computed on the page from the snapshot, business drivers and the model, so they are always current.
Events stay open until 30 days after the last trigger, then move to the log; returns vs QQQ 30 and 90 days after the
drop are recorded so the framework can be judged later.

Usage: python scripts/drop_watch.py
       python scripts/drop_watch.py --verdict PYPL --label temporary|lasting|unclear --confidence low|medium|high \
              --cause "Earnings reaction: Q3 margins down on one-off; guidance kept" --summary "two or three sentences" [--model-changed]
"""
import argparse, datetime as dt, json, pathlib, statistics, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATH = ROOT / "data/drops.json"
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date()
T_DAY, T_WEEK, T_HIGH, REL = -0.07, -0.12, -0.25, -0.05
E_DAY, E_WEEK, E_REL = -0.12, -0.20, -0.10
KEEP_OPEN = 30          # days after the last trigger
EVIDENCE_V = 4          # bump when the evidence logic changes (forces a refresh)


def load(p, default):
    try:
        return json.load(open(p))
    except Exception:
        return default


def moves(p):
    if not p or not p.get("price"):
        return None
    px = p["price"]
    return dict(day=px / p["prev_close"] - 1 if p.get("prev_close") else None,
                week=px / p["ref_5d"] - 1 if p.get("ref_5d") else None,
                high=px / p["high_52w"] - 1 if p.get("high_52w") else None)


def triggers(m, q):
    out, emergency = [], False
    for k, lim in (("day", T_DAY), ("week", T_WEEK), ("high", T_HIGH)):
        if m[k] is not None and m[k] <= lim and (q is None or q[k] is None or m[k] - q[k] <= REL):
            out.append(k)
    rel = lambda k: m[k] - (q[k] if q and q[k] is not None else 0)
    if (m["day"] is not None and m["day"] <= E_DAY and rel("day") <= E_REL) or \
       (m["week"] is not None and m["week"] <= E_WEEK and rel("week") <= E_REL):
        emergency = True
    return out, emergency


# ---------- step-2 evidence ----------
def closes_1y(t):
    import yfinance as yf
    h = yf.Ticker(t).history(period="1y", interval="1d", auto_adjust=False)
    return [float(x) for x in h["Close"].dropna()] if h is not None and len(h) else []


def peer_moves(t, screen, themes):
    rows = {r["ticker"]: r for r in screen}
    me = rows.get(t)
    stem = lambda n: (n or "").lower().replace(",", " ").split()[0] if n else ""
    same_co = lambda r: me and stem(r.get("name")) == stem(me.get("name"))      # other share classes (GOOG/GOOGL, FOX/FOXA)
    ind = [r for r in screen if me and me.get("industry") and r.get("industry") == me["industry"] and r["ticker"] != t and not same_co(r)]
    if len(ind) >= 3:
        peers = sorted(ind, key=lambda r: -(r.get("market_cap") or 0))[:8]
        basis, names = f"industry: {me['industry']}", [r["ticker"] for r in peers]
    else:
        grp = next((g for g, L in themes.items() if isinstance(L, list) and t in L and g != "Index & commodities"), None)
        names, basis = ([x for x in themes.get(grp, []) if x != t and not (x in rows and same_co(rows[x]))][:8], f"group: {grp}") if grp else ([], "none")
    res = {}
    for p in names:
        try:
            c = closes_1y(p)
            if len(c) >= 6:
                res[p] = dict(day=c[-1] / c[-2] - 1, week=c[-1] / c[-6] - 1, high=c[-1] / max(c) - 1)
        except Exception:
            pass
        time.sleep(0.3)
    med = {k: statistics.median([v[k] for v in res.values()]) for k in ("day", "week", "high")} if len(res) >= 3 else None
    return dict(basis=basis, n=len(res), median=med, tickers=list(res))


def estimates(tk):
    out = {}
    try:
        df = tk.eps_trend
        if df is not None and len(df):
            for per in ("0y", "+1y"):
                if per in df.index:
                    row = df.loc[per]
                    cur, ago = row.get("current"), row.get("30daysAgo")
                    if cur and ago:
                        out[per] = dict(current=float(cur), d30=float(ago), chg=float(cur) / float(ago) - 1)
    except Exception:
        pass
    try:
        df = tk.eps_revisions
        if df is not None and len(df) and "+1y" in df.index:
            r = df.loc["+1y"]
            out["revisions_30d"] = dict(up=int(r.get("upLast30days") or 0), down=int(r.get("downLast30Days") or r.get("downLast30days") or 0))
    except Exception:
        pass
    return out


def news(t, name, k=6):
    """Latest headlines (past 7 days): Google News RSS, then Yahoo Finance RSS (yfinance's news list is empty from GitHub)."""
    import email.utils, re as _re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
    short = _re.sub(r"[,.]?\s+(Inc|Corp|Corporation|Co|Company|Holdings|Group|plc|N\.V|Ltd|Limited|Incorporated)\b.*$", "", name or t).strip()
    urls = ["https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": f'"{short}" stock when:7d', "hl": "en-US", "gl": "US", "ceid": "US:en"}),
            f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={t}&region=US&lang=en-US"]
    for url in urls:
        try:
            x = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read()
            items = []
            for it in ET.fromstring(x).findall(".//item"):
                title, src = it.findtext("title") or "", it.findtext("source") or ""
                if src and title.endswith(" - " + src):
                    title = title[: -len(src) - 3]
                try:
                    d = email.utils.parsedate_to_datetime(it.findtext("pubDate")).astimezone(dt.timezone.utc)
                except Exception:
                    d = None
                items.append(dict(title=title, publisher=src or None, link=it.findtext("link"), date=d.date().isoformat() if d else "", _d=d))
            items = [x for x in items if x["_d"] and (NOW - x["_d"]).days <= 10]
            items.sort(key=lambda x: x["_d"], reverse=True)
            if items:
                return [{k: v for k, v in x.items() if k != "_d"} for x in items[:k]]
        except Exception:
            pass
    return []


def provisional(ev):
    """A first read of the cause from the data alone (Claude's verdict replaces it)."""
    E, m, q = ev["evidence"], ev["moves"], ev["qqq"]
    k = "day" if "day" in ev["triggers"] else "week" if "week" in ev["triggers"] else "high"
    peers = (E.get("peers") or {}).get("median") or {}
    est = (E.get("estimates") or {}).get("+1y", {}).get("chg")
    cut = est is not None and est <= -0.05
    if peers.get(k) is not None and m[k] and peers[k] <= 0.6 * m[k]:
        return dict(cause=f"Industry-wide: peers fell {peers[k] * 100:.0f}% too (rates, sector rotation or an industry worry)", lean="temporary" if not cut else "unclear")
    if E.get("earnings_on"):
        if cut:
            return dict(cause=f"Earnings reaction and next-year EPS forecasts cut {est * 100:.0f}%: check whether the setback lasts", lean="unclear")
        return dict(cause="Earnings reaction, but analysts have not cut next year's forecasts (yet)", lean="temporary")
    if cut:
        return dict(cause=f"Company-specific: next-year EPS forecasts cut {est * 100:.0f}% in 30 days", lean="unclear")
    if q and q.get(k) is not None and m[k] and q[k] <= 0.5 * m[k]:
        return dict(cause=f"Largely market-wide: QQQ {q[k] * 100:.0f}% vs this stock {m[k] * 100:.0f}%", lean="temporary")
    if k == "high":
        return dict(cause=f"Long slide: {m[k] * 100:.0f}% below its 52-week high (QQQ {q[k] * 100:.0f}%), more than its peers: read why", lean="unclear")
    return dict(cause="Company-specific, no clear cause in the data: read the headlines", lean="unclear")


def evidence(ev, screen, themes, cal):
    import yfinance as yf
    t = ev["ticker"]
    tk = yf.Ticker(t)
    past = [dt.date.fromisoformat(x) for x in (cal.get(t, {}).get("past") or [])]
    opened = dt.date.fromisoformat(ev["opened"])
    rep = [d for d in past if -1 <= (opened - d).days <= 7]
    return dict(v=EVIDENCE_V, updated=TODAY.isoformat(), earnings_on=max(rep).isoformat() if rep else None,
                last_report=max(past).isoformat() if past else None,
                peers=peer_moves(t, screen, themes), estimates=estimates(tk), news=news(t, ev.get("name")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verdict"); ap.add_argument("--label", choices=["temporary", "lasting", "unclear"])
    ap.add_argument("--confidence", choices=["low", "medium", "high"], default="medium")
    ap.add_argument("--cause", default=""); ap.add_argument("--summary", default="")
    ap.add_argument("--model-changed", action="store_true")
    ap.add_argument("--no-evidence", action="store_true")
    a = ap.parse_args()
    D = load(PATH, {"open": [], "log": []})

    if a.verdict:
        ev = next((e for e in D["open"] if e["ticker"] == a.verdict.upper()), None)
        if not ev or not a.label or len(a.summary) < 20:
            raise SystemExit("need an open event, --label and a --summary of at least 20 characters")
        ev["verdict"] = dict(label=a.label, confidence=a.confidence, cause=a.cause, summary=a.summary,
                             model_changed=a.model_changed, date=TODAY.isoformat(), by="Claude")
        ev["needs_verdict"] = False
        save(D); print("verdict saved", ev["ticker"], a.label); return

    P = load(ROOT / "data/prices.json", {"prices": {}})["prices"]
    assets = [x for x in load(ROOT / "data/assets.json", {"assets": []})["assets"] if x.get("type") == "stock"]
    screen = load(ROOT / "data/screen.json", {"rows": []})["rows"]
    themes = load(ROOT / "data/themes.json", {})
    cal = load(ROOT / "data/earnings_calendar.json", {"stocks": {}})["stocks"]
    q = moves(P.get("QQQ"))
    still = set()
    for x in assets:
        t, p = x["ticker"], P.get(x["ticker"])
        m = moves(p)
        if not m:
            continue
        trig, emer = triggers(m, q)
        ev = next((e for e in D["open"] if e["ticker"] == t), None)
        if not trig:
            continue
        still.add(t)
        rnd = lambda d: {k: (round(v, 4) if v is not None else None) for k, v in d.items()} if d else None
        if ev is None:
            day = (p.get("time") or TODAY.isoformat())[:10]          # the US trading session of the drop
            ev = dict(id=f"{t}-{day}", ticker=t, name=x["name"], opened=day, price_at_open=p["price"],
                      qqq_at_open=(P.get("QQQ") or {}).get("price"), fair_value_at_open=x["fair_value"],
                      buy_below_at_open=x["buy_below"], valued_on=x.get("valued_on"), triggers=[], emergency=False,
                      needs_verdict=True, verdict=None, evidence={}, outcome={})
            D["open"].append(ev); print("NEW drop event", t, trig, "EMERGENCY" if emer else "")
        ev["triggers"] = sorted(set(ev["triggers"]) | set(trig), key=["day", "week", "high"].index)
        if {"day", "week"} & set(trig) and ev.get("kind") == "slide" and ev.get("verdict"):
            ev["needs_verdict"] = True          # a sharp new drop on top of a slide: look again
        ev["kind"] = "alert" if {"day", "week"} & set(ev["triggers"]) else "slide"
        ev["last_triggered"] = TODAY.isoformat()
        ev["moves"], ev["qqq"] = rnd(m), rnd(q)
        ev["worst"] = {k: min(v, (ev.get("worst") or {}).get(k, 0) or 0) for k, v in rnd(m).items() if v is not None}
        if emer and not ev["emergency"]:
            ev["emergency"] = True
            if ev.get("verdict") and ev["verdict"].get("date", "") < TODAY.isoformat():
                ev["needs_verdict"] = True      # escalated after the last verdict: look again
    # refresh evidence (once a day per event), provisional cause, close old events, outcomes
    for ev in list(D["open"]):
        E0 = ev.get("evidence") or {}
        if not a.no_evidence and (E0.get("updated") != TODAY.isoformat() or E0.get("v") != EVIDENCE_V):
            try:
                ev["evidence"] = evidence(ev, screen, themes, cal)
            except Exception as e:
                print("evidence failed", ev["ticker"], e)
        if ev.get("moves"):
            ev["provisional"] = provisional(ev)
        if ev["ticker"] not in still and (TODAY - dt.date.fromisoformat(ev["last_triggered"])).days > KEEP_OPEN:
            ev["closed"] = TODAY.isoformat(); D["open"].remove(ev); D["log"].insert(0, ev)
    for ev in D["open"] + D["log"]:
        age = (TODAY - dt.date.fromisoformat(ev["opened"])).days
        p, qq = (P.get(ev["ticker"]) or {}).get("price"), (P.get("QQQ") or {}).get("price")
        for k, days in (("d30", 30), ("d90", 90)):
            if age >= days and k not in ev["outcome"] and p and qq and ev.get("qqq_at_open"):
                r, rq = p / ev["price_at_open"] - 1, qq / ev["qqq_at_open"] - 1
                ev["outcome"][k] = dict(stock=round(r, 4), qqq=round(rq, 4), vs_qqq=round(r - rq, 4), on=TODAY.isoformat())
    D["open"].sort(key=lambda e: (not e["emergency"], e.get("kind") != "alert", (e.get("moves") or {}).get("day") or 0))
    D["emergency_pending"] = [e["ticker"] for e in D["open"] if e["emergency"] and e.get("needs_verdict")]
    D["review_pending"] = [e["ticker"] for e in D["open"] if e.get("needs_verdict")]
    save(D)
    print("open:", [e["ticker"] for e in D["open"]], "| emergency pending:", D["emergency_pending"])


def save(D):
    strip = lambda x: {k: v for k, v in x.items() if k != "updated"}
    if json.dumps(strip(load(PATH, {})), default=str, sort_keys=True) == json.dumps(strip(D), default=str, sort_keys=True):
        return                      # nothing changed: keep the file (no commit)
    D["updated"] = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    D["rules"] = ("Trigger: down 7%+ in a day, 12%+ in 5 sessions or 25%+ below the 52-week high, each at least 5 points worse "
                  "than QQQ. Emergency: 12%+ in a day or 20%+ in a week and 10+ points worse than QQQ.")
    json.dump(D, open(PATH, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
