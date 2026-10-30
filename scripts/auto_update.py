#!/usr/bin/env python3
"""Automatic earnings update (runs on GitHub every day after the Earnings watch; Yahoo via yfinance).

For every company in data/pending_reports.json it rolls the model's trailing-12-month numbers forward once Yahoo
shows the new quarter, so the fair value moves the same day the data appears. Judgment stays with the twice-weekly
Claude review (data/review_queue.json): guidance, scenario assumptions, notes and business-driver KPIs.

How the numbers move (keeps every hand adjustment in the model):
  * TTM items (revenue, FCF, interest): new = old + (new quarter - same quarter a year earlier), summed over each new
    quarter. A normalisation or exclusion already in the model therefore stays in place.
  * Normalised FCF ("FCF NORMALISED" in the notes): keeps the normalised FCF margin on the new revenue.
  * Pro forma / net-revenue models: revenue and FCF scaled by Yahoo's TTM growth instead of the dollar change.
  * Stock pay: Yahoo's sum of the last 4 quarters when all 4 are reported, otherwise rolled forward like the rest.
  * Net cash and debt: old + change in Yahoo's (cash - total debt) since the model's quarter; shares scaled by the
    change in Yahoo's share count. Price = latest close in data/prices.json.
  * Scenario growth / margins, required returns and safety margins are never changed here.
Safety: a company is NOT auto-updated (queued for Claude instead) when Yahoo's quarters don't line up with the
model, a special case is listed in MANUAL, or the change looks implausible (revenue +-30%, shares +-10%, FCF change
over 15% of revenue, net-cash change over 25% of market value). After the model runs, --finalize reverts any company
whose fair value moved more than 35% and queues it for review.

Usage: python scripts/auto_update.py                 (pending companies; writes model.py, data_through, review queue)
       python scripts/auto_update.py --finalize      (after model/model.py: fill new fair values, revert big moves)
       python scripts/auto_update.py --dry-run --model OLD.py --through OLD.json --tickers AMZN,MA   (validation)
"""
import argparse, calendar, datetime as dt, json, math, pathlib, re, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
TODAY = dt.date.today()
QUEUE = ROOT / "data/review_queue.json"
UPDATED = ROOT / "data/.auto_updated.txt"     # tickers updated in this run (read by the workflow)

# Special cases: field mapping and what to keep (see the model notes)
CFG = {
    "AXP": dict(fcf="ni", keep=["sbc", "net_cash", "fin"]),          # valued like a lender on net income
    "XYZ": dict(rev="gross"),                                          # valued on gross profit
    "EXPE": dict(keep=["net_cash"]),                                   # cash is customers' money (net cash zero)
    "CRCL": dict(keep=["net_cash"]),                                   # USDC reserves excluded
    "NDAQ": dict(scale=True), "SPGI": dict(scale=True), "RMD": dict(scale=True),   # net revenue / pro forma
}
MANUAL = {
    "ADYEY": "Reports in EUR, half-yearly, FCF estimated: needs a manual update from the release.",
    "CTAS": "Revenue and cash flow use different periods in the model: needs a manual update.",
}
YROWS = {  # yahoo row names per field
    "rev": ["Total Revenue", "Operating Revenue"], "gross": ["Gross Profit"], "ni": ["Net Income Common Stockholders", "Net Income"],
    "interest": ["Interest Expense", "Interest Expense Non Operating"],
    "fcf": ["Free Cash Flow"], "ocf": ["Operating Cash Flow"], "capex": ["Capital Expenditure"], "sbc": ["Stock Based Compensation"],
    "cash": ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"], "debt": ["Total Debt"],
    "shares": ["Ordinary Shares Number", "Share Issued"],
}


def num(x):
    try:
        x = float(x)
        return None if math.isnan(x) else x
    except Exception:
        return None


def d(s):
    return dt.date.fromisoformat(str(s)[:10])


def frame(df, keys):
    out = {}
    if df is None or getattr(df, "empty", True):
        return out
    for c in df.columns:
        rec = {}
        for k in keys:
            for n in YROWS[k]:
                if n in df.index and num(df.loc[n, c]) is not None:
                    rec[k] = num(df.loc[n, c]); break
        out[d(c)] = rec
    return out


def yahoo(t):
    import yfinance as yf
    tk = yf.Ticker(t)
    def get(attr):
        for i in range(3):
            try:
                return getattr(tk, attr)
            except Exception:
                time.sleep(2 * (i + 1))
    q = frame(get("quarterly_income_stmt"), ["rev", "gross", "ni", "interest"])
    for p, rec in frame(get("quarterly_cashflow"), ["fcf", "ocf", "capex", "sbc"]).items():
        if "fcf" not in rec and "ocf" in rec and "capex" in rec:
            rec["fcf"] = rec["ocf"] + rec["capex"]
        q.setdefault(p, {}).update(rec)
    trail = {}
    for fn, keys in (("get_income_stmt", ["rev", "gross", "ni", "interest"]), ("get_cash_flow", ["fcf", "ocf", "capex", "sbc"])):
        try:
            for p, rec in frame(getattr(tk, fn)(freq="trailing"), keys).items():
                if "fcf" in keys and "fcf" not in rec and "ocf" in rec and "capex" in rec:
                    rec["fcf"] = rec["ocf"] + rec["capex"]
                trail.setdefault(p, {}).update(rec)
        except Exception:
            pass
    return q, frame(get("quarterly_balance_sheet"), ["cash", "debt", "shares"]), trail


def near(dates, target, tol=20):
    c = [x for x in dates if abs((x - target).days) <= tol]
    return min(c, key=lambda x: abs((x - target).days)) if c else None


def month_end(p):
    if p.day <= 7:                      # 52/53-week fiscal calendars (e.g. quarter ends 3 Oct = September quarter)
        p = p.replace(day=1) - dt.timedelta(days=1)
    return p.replace(day=calendar.monthrange(p.year, p.month)[1])


# ---------- model.py text helpers ----------
def block(src, t):
    m = re.search(r'^ "%s": dict\(name=.*?notes=".*?"\),\s*$' % t, src, re.M | re.S)
    return m


def fin_block(src, t):
    i = src.index("FIN = {")
    m = re.compile(r'"%s": dict\(debt=[^)]*\)' % t).search(src, i)
    return m


def val(text, k):
    m = re.search(r'\b%s=(-?[\d.eE+-]+)' % k, text)
    return float(m.group(1)) if m else None


def setv(text, k, v):
    return re.sub(r'\b%s=(-?[\d.eE+-]+)' % k, f"{k}={v}", text, count=1)


def rnd(x, n=3):
    return float(f"{x:.{n}f}")


def plan(t, src, through, prices):
    """Return (status, info). status: updated | waiting | manual."""
    if t in MANUAL:
        return "manual", dict(reason=MANUAL[t])
    b = block(src, t)
    if not b:
        return "manual", dict(reason="ticker not found in model.py")
    text = b.group(0)
    notes = re.search(r'notes="(.*?)"\)', text, re.S).group(1)
    cfg = CFG.get(t, {})
    q, bal, trail = yahoo(t)
    if not q:
        return "waiting", dict(reason="Yahoo returned no quarterly statements")
    rk, fk = cfg.get("rev", "rev"), cfg.get("fcf", "fcf")
    # Yahoo often adds an empty column for a new quarter before filling it: only count quarters with numbers
    periods = sorted([p for p in q if q[p].get(rk) is not None], reverse=True)
    if not periods:
        return "waiting", dict(reason="Yahoo has no quarterly revenue yet")
    new = [p for p in periods if p > through + dt.timedelta(days=20)]
    if not new:
        return "waiting", dict(reason=f"Yahoo's latest quarter is {periods[0]} (model already through {through})")
    if (min(new) - through).days > 110:
        return "manual", dict(reason=f"gap between the model ({through}) and Yahoo's next quarter ({min(new)})")
    old = {k: val(text, k) for k in ("price", "shares", "rev", "fcf", "sbc", "net_cash", "extra")}
    fb = fin_block(src, t)
    fin_old = {k: val(fb.group(0), k) for k in ("debt", "interest", "rd", "tax")} if fb else None
    flags, ch = [], {}
    if any(q[p].get(fk) is None for p in new) and not cfg.get("scale") and not ("NORMALISED" in notes and fk == "fcf"):
        return "waiting", dict(reason=f"Yahoo has the new quarter's income statement but not its cash flow ({fk}) yet")

    def delta(k):
        s = 0.0
        for p in new:
            ya = near(q.keys(), p - dt.timedelta(days=365))
            if ya is None or q[p].get(k) is None or q[ya].get(k) is None:
                return None
            s += q[p][k] - q[ya][k]
        return s / 1e9

    def ttm(k, end):
        ps = [p for p in periods if p <= end][:4]
        if len(ps) < 4 or (ps[0] - ps[3]).days > 300 or any(q[p].get(k) is None for p in ps):
            return None
        return sum(q[p][k] for p in ps) / 1e9

    latest = max(new)
    prev_end = near(q.keys(), through)
    tl = near(trail.keys(), latest)

    def trailing(k):
        """Yahoo's own TTM figure for the new quarter (fallback when the year-ago quarter is blank)."""
        v = trail.get(tl, {}).get(k) if tl else None
        return None if v is None else v / 1e9
    adjusted = any(w in notes for w in ("NORMALISED", "PRO FORMA", "one-off", "excluding", "own definition"))
    new_vals = dict(old)
    # revenue
    if cfg.get("scale"):
        a, b0 = ttm(rk, latest), ttm(rk, prev_end) if prev_end else None
        if not a or not b0:
            return "manual", dict(reason="cannot compute Yahoo TTM revenue growth for a scaled (pro forma / net revenue) model")
        g = a / b0
        new_vals["rev"] = old["rev"] * g
        new_vals["fcf"] = old["fcf"] * g
        flags.append(f"Pro forma / net-revenue model: revenue and FCF scaled by Yahoo TTM growth ({(g - 1) * 100:+.1f}%) - check against the release")
    else:
        dr = delta(rk)
        if dr is not None:
            new_vals["rev"] = old["rev"] + dr
        elif trailing(rk) and not adjusted and len(new) == 1:
            new_vals["rev"] = trailing(rk)
            flags.append(f"Year-ago quarter blank in Yahoo: revenue set to Yahoo's TTM ({trailing(rk):.3f}) - check the definition matches")
        else:
            return "manual", dict(reason=f"Yahoo is missing {rk} for the new or year-ago quarter")
        if "NORMALISED" in notes and fk == "fcf":
            new_vals["fcf"] = old["fcf"] / old["rev"] * new_vals["rev"]
            flags.append("FCF NORMALISED: kept the normalised margin on the new revenue - check one-offs / working capital in the release")
        else:
            df_ = delta(fk)
            if df_ is not None:
                new_vals["fcf"] = old["fcf"] + df_
            elif trailing(fk) is not None and not adjusted and len(new) == 1:
                new_vals["fcf"] = trailing(fk)
                flags.append(f"Year-ago quarter blank in Yahoo: {fk} set to Yahoo's TTM ({trailing(fk):.3f}) - check the definition matches")
            else:
                return "manual", dict(reason=f"Yahoo is missing {fk} for the new or year-ago quarter")
    # stock pay
    if "sbc" not in cfg.get("keep", []):
        s4 = ttm("sbc", latest)
        if s4 is None and trailing("sbc"):
            s4 = trailing("sbc")
        if s4 is not None and s4 > 0:
            if re.search(r"SBC (is )?an? ESTIMATE", notes) or "SBC estimated" in notes:
                flags.append(f"SBC was an estimate ({old['sbc']}); now Yahoo's reported TTM {s4:.3f} - remove 'ESTIMATE' from the notes")
            new_vals["sbc"] = s4
        else:
            ds = delta("sbc")
            if ds is not None:
                new_vals["sbc"] = max(0.0, old["sbc"] + ds)
            else:
                flags.append("SBC not in Yahoo's quarterly data: kept unchanged")
    # balance sheet
    bl, bp = near(bal.keys(), latest), near(bal.keys(), through)
    if bl and bp and all(bal[x].get(k) is not None for x in (bl, bp) for k in ("cash", "debt")):
        dnet = ((bal[bl]["cash"] - bal[bl]["debt"]) - (bal[bp]["cash"] - bal[bp]["debt"])) / 1e9
        ddebt = (bal[bl]["debt"] - bal[bp]["debt"]) / 1e9
        if "net_cash" not in cfg.get("keep", []):
            new_vals["net_cash"] = old["net_cash"] + dnet
        if bal[bl].get("shares") and bal[bp].get("shares"):
            new_vals["shares"] = old["shares"] * bal[bl]["shares"] / bal[bp]["shares"]
        else:
            flags.append("share count change not in Yahoo's data: shares kept")
    else:
        ddebt = None
        flags.append("Yahoo balance sheet not available for both quarters: net cash and shares kept")
    p = prices.get(t, {}).get("price")
    if p:
        new_vals["price"] = p
    # FIN (debt, interest)
    fin_new = dict(fin_old) if fin_old else None
    if fin_old and "fin" not in cfg.get("keep", []):
        if ddebt is not None:
            fin_new["debt"] = max(0.0, fin_old["debt"] + ddebt)
        di = delta("interest")
        if di is not None and fin_old["interest"]:
            fin_new["interest"] = max(0.0, fin_old["interest"] + di)
        fin_new["rd"] = fin_new["interest"] / fin_new["debt"] if fin_new["debt"] and fin_new["interest"] else fin_old["rd"]
    # plausibility guards
    mcap = old["price"] * old["shares"]
    why = []
    if new_vals["rev"] <= 0 or abs(new_vals["rev"] / old["rev"] - 1) > 0.30:
        why.append(f"revenue {old['rev']} -> {new_vals['rev']:.3f}")
    if abs(new_vals["shares"] / old["shares"] - 1) > 0.10:
        why.append(f"shares {old['shares']} -> {new_vals['shares']:.4f}")
    if abs(new_vals["fcf"] - old["fcf"]) > 0.15 * max(old["rev"], new_vals["rev"]):
        why.append(f"FCF {old['fcf']} -> {new_vals['fcf']:.3f}")
    if abs(new_vals["net_cash"] - old["net_cash"]) > 0.25 * mcap:
        why.append(f"net cash {old['net_cash']} -> {new_vals['net_cash']:.3f}")
    if why:
        return "manual", dict(reason="change looks implausible, check the release: " + "; ".join(why))
    # surprise flags (applied, but worth a read)
    for p_ in new:
        ya = near(q.keys(), p_ - dt.timedelta(days=365))
        if ya and q[p_].get(rk) and q[ya].get(rk):
            gq = q[p_][rk] / q[ya][rk] - 1
            base_g1 = float(re.search(r"base=dict\(g1=(-?[\d.]+)", text).group(1))
            if abs(gq - base_g1) > 0.08:
                flags.append(f"Quarter to {p_} grew {gq * 100:+.1f}% YoY vs base-case year-1 growth {base_g1 * 100:.1f}%: check guidance")
    for k in ("NORMALISED", "PRO FORMA", "one-off", "excluding"):
        if k in notes and not any(k.lower() in f.lower() for f in flags):
            flags.append(f"Notes mention '{k}': confirm the adjustment still applies")
    new_vals = {k: (rnd(v, 5) if k == "shares" else rnd(v, 3) if k != "price" else round(v, 2)) for k, v in new_vals.items()}
    if fin_new:
        fin_new = dict(debt=rnd(fin_new["debt"]), interest=rnd(fin_new["interest"], 4), rd=rnd(fin_new["rd"], 4), tax=fin_old["tax"])
    ch = {k: [old[k], new_vals[k]] for k in old if old[k] != new_vals[k] and k != "extra"}
    if fin_new:
        ch.update({f"fin.{k}": [fin_old[k], fin_new[k]] for k in fin_old if fin_old[k] != fin_new[k]})
    return "updated", dict(quarter_end=month_end(latest).isoformat(), yahoo_quarters=[str(x) for x in sorted(new)],
                           new=new_vals, fin=fin_new, changes=ch, flags=flags, old_block=text,
                           old_fin=fb.group(0) if fb else None)


def apply(src, t, info):
    text = info["old_block"]
    nt = text
    for k, v in info["new"].items():
        if k != "extra":
            nt = setv(nt, k, v)
    mon = dt.date.fromisoformat(info["quarter_end"]).strftime("%b-%Y")
    nt = re.sub(r'notes="(Revenue )?(TTM|FY) to [A-Z][a-z]{2}-\d{4}', lambda m: f'notes="{m.group(1) or ""}TTM to {mon}', nt, count=1)
    nt = re.sub(r' \[Numbers auto-updated[^\]]*\]', "", nt)
    nt = nt.replace('"),', f' [Numbers auto-updated {TODAY:%d %b %Y} from Yahoo quarterly data (TTM roll-forward); text review pending.]"),', 1) \
        if nt.rstrip().endswith('"),') else nt
    src = src.replace(text, nt, 1)
    if info.get("fin") and info.get("old_fin"):
        nf = info["old_fin"]
        for k, v in info["fin"].items():
            nf = setv(nf, k, v)
        i = src.index("FIN = {")
        src = src[:i] + src[i:].replace(info["old_fin"], nf, 1)
    return src


def load_queue():
    try:
        return json.load(open(QUEUE))
    except Exception:
        return {"items": []}


def save_queue(Q):
    Q["updated"] = TODAY.isoformat()
    Q["how"] = ("Written by scripts/auto_update.py. status auto_updated = numbers rolled forward from Yahoo, the text review "
                "(guidance, assumptions, notes, KPIs) is still to do; manual = not auto-updated, needs a full update from the release. "
                "The twice-weekly Claude review removes items when done.")
    json.dump(Q, open(QUEUE, "w"), indent=1)


def results_fv():
    R = json.load(open(ROOT / "model/results.json"))["assets"]
    return {t: a.get("fair_value") for t, a in R.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="")
    ap.add_argument("--model", default=str(ROOT / "model/model.py"))
    ap.add_argument("--through", default=str(ROOT / "data/data_through.json"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--finalize", action="store_true")
    a = ap.parse_args()
    mp = pathlib.Path(a.model)

    if a.finalize:
        Q, fv, src, reverted = load_queue(), results_fv(), mp.read_text(), []
        thr = json.load(open(a.through))
        for it in Q["items"]:
            if it.get("status") == "auto_updated" and it.get("auto_date") == TODAY.isoformat() and it.get("fv_new") is None:
                it["fv_new"] = round(fv.get(it["ticker"]) or 0, 2)
                old = it.get("fv_old")
                if old and abs(it["fv_new"] / old - 1) > 0.35:
                    b = block(src, it["ticker"]).group(0)
                    src = src.replace(b, it.pop("old_block_text"), 1)
                    if it.get("old_fin_text"):
                        f = fin_block(src, it["ticker"]).group(0)
                        i = src.index("FIN = {"); src = src[:i] + src[i:].replace(f, it["old_fin_text"], 1)
                    thr[it["ticker"]] = it["data_through_before"]
                    it.update(status="manual", reason=f"auto update moved the fair value {old} -> {it['fv_new']} (over 35%): reverted, check the release")
                    reverted.append(it["ticker"])
                elif old and abs(it["fv_new"] / old - 1) > 0.15:
                    it["flags"].append(f"Fair value moved {(it['fv_new'] / old - 1) * 100:+.1f}%: worth a look")
            it.pop("old_block_text", None); it.pop("old_fin_text", None)
        mp.write_text(src); json.dump(thr, open(a.through, "w"), indent=1); save_queue(Q)
        if reverted:
            ups = [x for x in UPDATED.read_text().split() if x not in reverted] if UPDATED.exists() else []
            UPDATED.write_text(" ".join(ups))
        print("finalized; reverted:", reverted or "none")
        return

    src, thr = mp.read_text(), json.load(open(a.through))
    prices = json.load(open(ROOT / "data/prices.json"))["prices"]
    if a.tickers:
        tickers = [x.strip().upper() for x in a.tickers.split(",") if x.strip()]
    else:
        tickers = [p["ticker"] for p in json.load(open(ROOT / "data/pending_reports.json"))["pending"]]
    fv = results_fv() if not a.dry_run else {}
    Q, done, report = load_queue(), [], {}
    for t in tickers:
        try:
            status, info = plan(t, src, d(thr[t]), prices)
        except Exception as e:
            status, info = "manual", dict(reason=f"error: {e}")
        report[t] = (status, info)
        print(f"{t}: {status}", info.get("reason", ""), json.dumps(info.get("changes", {})), *info.get("flags", []), sep="\n   ")
        if a.dry_run:
            continue
        Q["items"] = [x for x in Q["items"] if x["ticker"] != t or x.get("status") == "auto_updated" and status == "waiting"]
        if status == "updated":
            before = thr[t]
            src = apply(src, t, info)
            thr[t] = info["quarter_end"]
            done.append(t)
            Q["items"] = [x for x in Q["items"] if x["ticker"] != t]
            Q["items"].append(dict(ticker=t, status="auto_updated", quarter_end=info["quarter_end"], auto_date=TODAY.isoformat(),
                                   fv_old=round(fv.get(t) or 0, 2), fv_new=None, changes=info["changes"], flags=info["flags"],
                                   data_through_before=before, old_block_text=info["old_block"], old_fin_text=info.get("old_fin")))
        elif status == "manual":
            Q["items"].append(dict(ticker=t, status="manual", reason=info["reason"], since=TODAY.isoformat()))
        time.sleep(1)
    if a.dry_run:
        json.dump({t: dict(status=s, **{k: v for k, v in i.items() if k not in ("old_block", "old_fin")}) for t, (s, i) in report.items()},
                  open(ROOT / "data/.auto_update_dryrun.json", "w"), indent=1, default=str)
        return
    mp.write_text(src)
    json.dump(thr, open(a.through, "w"), indent=1)
    save_queue(Q)
    UPDATED.write_text(" ".join(done))
    print("auto-updated:", done or "none")


if __name__ == "__main__":
    main()
