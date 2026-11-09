#!/usr/bin/env python3
"""Research framework blocks for each stock's Fair Value drawer -> data/framework.json. Information only: nothing here
changes a fair value.

The drawer answers a fixed set of 64 questions (50 universal + 10 on what the market prices in + 4 on duration) plus up to 8 sector
questions per stock, chosen by business model (SECTOR_MODULES below), not by official sector. Every question is
"answered", "partly" or "unknown"; an unknown question is shown in grey as "not scored" and never counts as positive.

Per stock:
  business    latest fiscal year vs the year before: sales, EPS, free cash flow (data/snapshot_raw.json)
  market      share price change year to date, 1, 3 and 5 years (month-end closes + today's price), YTD with
              dividends, and the same for the S&P 500 (SPY) and the stock's equal-weight sector fund (data/sector_map.json)
  split       latest fiscal year: price change = EPS change x P/E change, so a rise from earnings is told apart from a
              rise from a higher multiple (month-end close at each fiscal year end, EPS as reported)
  bonds       inputs for the three spreads: earnings yield vs Moody's Aaa, the 10-year Treasury and the 10-year real
              (TIPS) yield. The drawer adds the expected 10-year return (Monte Carlo median) for spreads 2 and 3.
  assumes     at today's price and the required return, with the model's own cash-flow engine (model/model.py):
              year-1 sales growth needed, cash margin needed at base growth, value if growth is half the implied rate,
              the advantage period the price needs, and the median P/E of the sector (latest growth screen) and of the
              stock's own last 4 years, for "what if the multiple goes back"
  sector      the stock's module and each question's answer from the statements, or unknown
  coverage    counts of answered / partly / unknown questions (underwriters: the free-cash-flow and capex questions are
              "na", not applicable, and left out of the total)

Usage: python scripts/framework.py            (after model/model.py, the snapshot refresh and scripts/durability.py)
       python scripts/framework.py --offline  (skip the benchmark download and keep the previous benchmark prices)
Benchmarks (SPY and sector funds) come from Yahoo through yfinance when it is installed; otherwise the previous ones are
kept and, if there are none, the comparison shows as unknown.
"""
import csv, datetime, glob, json, math, pathlib, statistics as st, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/framework.json"
J = lambda p, d=None: json.load(open(ROOT / p)) if (ROOT / p).exists() else d

ASSETS = {a["ticker"]: a for a in J("data/assets.json")["assets"] if a.get("type") == "stock"}
PRICES = J("data/prices.json")["prices"]
RAW = J("data/snapshot_raw.json", {"stocks": {}})["stocks"]
SNAP = J("data/snapshot.json", {"stocks": {}})["stocks"]
DUR = J("data/durability.json", {"stocks": {}})["stocks"]
DURN = J("data/duration.json", {"stocks": {}})["stocks"]       # scripts/duration.py: value by horizon, duration, edge ending early
RET = J("data/returns.json", {"stocks": {}})["stocks"]
MS = J("data/moat_scorecard.json", {"stocks": {}})["stocks"]
SEG = J("data/segments.json", {"stocks": {}})["stocks"]
BOND = J("data/bond_yields.json", {})
SMAP = J("data/sector_map.json")
OLD = J("data/framework.json", {})

# ------------------------------------------------------------------ the 64 fixed questions
# status after this build; "needs" = a block that must exist for this stock, otherwise the question is unknown.
Q = [
 ("A1", "Earnings yield vs high-quality company bonds", "answered", "bonds"),
 ("A2", "Earnings yield vs the 10-year Treasury", "answered", "bonds"),
 ("A3", "Is the earnings spread positive or negative?", "answered", "bonds"),
 ("A4", "Today's spread vs its own historical median", "answered", "bonds"),
 ("A5", "Expensive vs bonds by its own history?", "answered", "bonds"),
 ("A6", "Same currency and a comparable horizon?", "answered", "bonds"),
 ("A7", "Extra return for taking equity risk", "answered", "mc"),
 ("B8", "EPS growth over 3, 5 and 10 years", "partly", None),
 ("B9", "EPS growth from revenue vs margins", "unknown", None),
 ("B10", "EPS growth from buybacks", "partly", None),
 ("B11", "Expected EPS growth over 3-5 years", "partly", None),
 ("B12", "How reliable analyst forecasts have been", "unknown", None),
 ("B13", "Is growth speeding up or slowing?", "partly", None),
 ("B14", "Earnings growing faster than revenue, and why", "partly", None),
 ("B15", "Recurring demand or temporary circumstances?", "unknown", None),
 ("C16", "Pricing power", "partly", None),
 ("C17", "Can it raise prices without losing customers?", "unknown", None),
 ("C18", "Sources of competitive advantage", "answered", "moat"),
 ("C19", "How easily can competitors copy it?", "partly", "moat"),
 ("C20", "Market share rising or falling?", "unknown", None),
 ("C21", "Industry growing, flat or shrinking?", "unknown", None),
 ("C22", "Could technology disrupt the business?", "partly", "moat"),
 ("C23", "How long the advantage can last", "answered", None),
 ("D24", "Free cash flow growing with earnings?", "answered", "snapshot"),
 ("D25", "Share of net income that becomes free cash flow", "answered", "snapshot"),
 ("D26", "Cash flow from operations or working capital?", "unknown", None),
 ("D27", "Capex needed to maintain the business", "partly", "snapshot"),
 ("D28", "Capex needed for growth", "partly", "returns"),
 ("D29", "Becoming more or less capital-intensive?", "partly", "snapshot"),
 ("D30", "Can it fund growth without borrowing or issuing shares?", "partly", "snapshot"),
 ("E31", "Share of earnings paid as dividends", "answered", "snapshot"),
 ("E32", "Buybacks reducing the share count?", "answered", "snapshot"),
 ("E33", "Buybacks below or above intrinsic value?", "unknown", None),
 ("E34", "Retained capital earning above its cost?", "answered", "returns"),
 ("E35", "How capital is allocated", "answered", "snapshot"),
 ("E36", "Creating value per share or just size?", "unknown", None),
 ("F37", "Volatility of revenue, earnings and cash flow", "answered", "snapshot"),
 ("F38", "Sensitivity to recessions", "answered", "stress"),
 ("F39", "Debt to refinance in the next 1-5 years", "unknown", None),
 ("F40", "Cash flow covers interest and debt?", "answered", "snapshot"),
 ("F41", "Dependence on few customers, suppliers or markets", "unknown", None),
 ("F42", "Regulatory, geopolitical or technology risks", "partly", "moat"),
 ("F43", "Earnings fall in a realistic bad scenario", "answered", "stress"),
 ("G44", "Price change YTD, 1, 3 and 5 years", "answered", "market"),
 ("G45", "Price rise from earnings vs a higher P/E", "answered", "split"),
 ("G46", "Better or worse than its sector and the market?", "answered", "bench"),
 ("G47", "Valuation rising faster than earnings?", "answered", "split"),
 ("G48", "Analysts becoming more optimistic?", "unknown", None),
 ("G49", "Growth implied by today's price", "answered", None),
 ("G50", "Expected return if the multiple goes back to its average", "answered", "pe_own"),
 ("M1", "EPS growth implied by today's price", "partly", None),
 ("M2", "Revenue growth needed", "answered", "assumes"),
 ("M3", "Margin needed", "answered", "assumes"),
 ("M4", "Enough room to reinvest for that growth?", "answered", None),
 ("M5", "What if growth is half the implied rate?", "answered", "assumes"),
 ("M6", "What if the P/E falls to the sector median?", "answered", "pe_sector"),
 ("M7", "Bear, base and bull outcomes", "partly", None),
 ("M8", "Each scenario vs the bond yield", "partly", "mc"),
 ("M9", "Return from business growth vs a re-rating", "unknown", None),
 ("M10", "Is the valuation premium covered by the advantage?", "answered", None),
 # Duration (from November 2026, scripts/duration.py): how far into the future the value depends on receiving cash
 ("T1", "Share of value from cash 5, 10, 20 and 30+ years away", "answered", "duration"),
 ("T2", "How much the value moves if interest rates change", "answered", "duration"),
 ("T3", "Does your holding period cover where the value comes from?", "answered", "duration"),
 ("T4", "How reliable are the assumptions behind distant cash flows?", "answered", "duration"),
]

# Questions that don't apply to an underwriter (valued on book value and ROE): its cash flow mixes in premiums held for
# future claims, and its capex and working capital say little. Marked "na": not answered, not unknown, not counted.
NA_INSURER = {"D24", "D25", "D26", "D27", "D28", "D29", "D30", "F40"}

# ------------------------------------------------------------------ sector modules (by business model)
M_ = lambda name, tickers, qs: dict(name=name, tickers=tickers.split(), questions=qs)
SECTOR_MODULES = [
 M_("Software and internet", "MSFT GOOGL AMZN META NFLX ADBE CRM INTU ADSK WDAY VEEV FTNT VRSN GDDY APP FICO RDDT SHOP BKNG EXPE",
    [("How much revenue is recurring (subscriptions)?", None), ("Net revenue retention and churn", None),
     ("Gross margin holding up?", "gross_margin"), ("R&D share of revenue", "rd_rev"), ("Stock pay share of revenue", "sbc_rev"),
     ("Free cash flow margin", "fcf_margin"), ("Growth needs heavy infrastructure spending?", "capex_rev"),
     ("Is AI a new market or a threat?", None)]),
 M_("Hardware and devices", "AAPL GRMN MSI",
    [("How much revenue is recurring (services)?", "services_share"), ("Gross margin holding up?", "gross_margin"),
     ("R&D share of revenue", "rd_rev"), ("Inventory growing faster than sales?", "inventory"),
     ("Growth needs heavy capex?", "capex_rev"), ("Customer retention", None), ("Is AI a new market or a threat?", None)]),
 M_("Semiconductors", "NVDA AVGO KLAC MRVL",
    [("How cyclical are profits?", "recession"), ("Inventory growing faster than sales?", "inventory"),
     ("Gross margin holding up?", "gross_margin"), ("R&D share of revenue", "rd_rev"), ("Capex share of revenue", "capex_rev"),
     ("Dependence on a few large customers", None), ("Export controls and trade risk", None)]),
 M_("Payments and networks", "V MA AXP PYPL FIS FISV XYZ ADYEY CRCL",
    [("Payment volume growth", None), ("Take rate holding up?", None), ("Operating margin trend", "op_margin"),
     ("Operating leverage (profit vs sales growth)", "op_leverage"), ("Free cash flow margin", "fcf_margin"),
     ("Stock pay share of revenue", "sbc_rev"), ("Credit losses and fee regulation", None)]),
 M_("Exchanges, ratings and financial data", "SPGI MCO CME CBOE NDAQ FDS BR ADP AMP",
    [("How much revenue is recurring (subscriptions)?", None), ("Operating margin trend", "op_margin"),
     ("Sensitivity to market activity (revenue swings)", "rev_stability"), ("Operating leverage (profit vs sales growth)", "op_leverage"),
     ("Debt vs earnings", "debt_ebitda"), ("Free cash flow margin", "fcf_margin"), ("Pricing and regulatory risk", None)]),
 M_("Medical technology and animal health", "SYK RMD IDXX STE DXCM ZTS",
    [("Share of revenue from recurring consumables", None), ("Gross margin holding up?", "gross_margin"),
     ("R&D share of revenue", "rd_rev"), ("Recession resilience", "recession"), ("Product concentration", None),
     ("Reimbursement and approval risk", None)]),
 M_("Pharmaceuticals and biotech", "LLY REGN BMY AMGN JNJ INCY",
    [("Revenue from patented products", None), ("When major patents expire", None), ("Pipeline success and trial risk", None),
     ("Product concentration", None), ("R&D share of revenue", "rd_rev"), ("Gross margin holding up?", "gross_margin"),
     ("Drug pricing and reimbursement risk", None)]),
 M_("Consumer brands and retail", "DECK TPR RL LULU ROST DLTR CMG HAS MNST MKC KO PG MO PM",
    [("Growth from higher prices or more volume?", None), ("Market share rising or falling?", None),
     ("Gross margin holding up (pricing power)?", "gross_margin"), ("Inventory growing faster than sales?", "inventory"),
     ("Recession resilience", "recession"), ("Operating margin trend", "op_margin"), ("Customer acquisition cost", None)]),
 M_("Industrials and building", "ALLE AME CTAS FAST FIX EME HWM LII RSG TT WAB VLTO SHW PPG",
    [("Order backlog and book-to-bill", None), ("Operating leverage (profit vs sales growth)", "op_leverage"),
     ("Maintenance capex (capex vs depreciation)", "capex_dep"), ("Returns on new investment", "incr_roic"),
     ("How cyclical is demand?", "recession"), ("Pricing power over input costs (gross margin)", "gross_margin"),
     ("Dependence on a few large customers", None)]),
 M_("Energy and commodities", "APA EOG BKR CF NEM",
    [("Commodity prices behind today's earnings", None), ("Breakeven production cost", None), ("Production and reserves", None),
     ("How cyclical are profits?", "recession"), ("Debt vs earnings", "debt_ebitda"), ("Maintenance capex (capex vs depreciation)", "capex_dep"),
     ("Payouts covered by free cash flow", "div_cover")]),
 M_("Real estate (REITs)", "SPG HST",
    [("Occupancy", None), ("Same-property income growth", None), ("Net asset value per share", None), ("Debt maturities", None),
     ("Dividends covered by free cash flow", "div_cover"), ("Debt vs earnings", "debt_ebitda"), ("Interest cover", "int_cover")]),
 M_("Insurance underwriters", "ALL HIG AIZ NMIH ESNT UVE HCI SLDE PLMR PLGO HG UFCS SKWD",
    [("Underwriting profit: combined ratio below 100%?", None), ("Return on equity vs the required return", "roe"),
     ("Book value growth", "bv_growth"), ("Catastrophe exposure and reinsurance cover", None),
     ("Reserve development (past claims re-estimated)", None), ("Premium growth from price or from more policies?", None),
     ("Capital strength (risk-based capital, solvency ratios)", None), ("Investment portfolio: yield and credit risk", None)]),
 M_("Insurance brokers and claims services", "MRSH WTW CRVL",
    [("Organic revenue growth", None), ("Operating margin trend", "op_margin"), ("Operating leverage (profit vs sales growth)", "op_leverage"),
     ("Free cash flow margin", "fcf_margin"), ("Debt vs earnings", "debt_ebitda"), ("Sensitivity to insurance prices (revenue swings)", "rev_stability"),
     ("Interest earned on client money (fiduciary income)", None)]),
 M_("Power and utilities", "NRG",
    [("Revenue regulated or contracted?", None), ("Can it pass inflation through?", None), ("Debt vs earnings", "debt_ebitda"),
     ("Interest cover", "int_cover"), ("Demand stability (revenue swings)", "rev_stability"), ("Dividends covered by free cash flow", "div_cover")]),
]
MODULE_OF = {t: m for m in SECTOR_MODULES for t in m["tickers"]}

# ------------------------------------------------------------------ helpers
def pct(a, b):
    return None if a is None or b in (None, 0) or (a < 0) != (b < 0) and b < 0 else a / b - 1

def r1(x, n=4):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(x, n)

def years(raw, part):
    d = (raw.get("annual") or {}).get(part) or {}
    return sorted(d.items())                                   # [(date, {...}), ...] oldest first

def series(raw, part, key):
    return [(d[:10], v.get(key)) for d, v in years(raw, part) if v.get(key) is not None]

def month_close(raw, ym):
    mp = raw.get("monthly_prices") or {}
    if ym in mp: return mp[ym]
    prev = [k for k in mp if k <= ym]
    return mp[max(prev)] if prev else None

def ym_minus(ym, months):
    y, m = int(ym[:4]), int(ym[5:7]) - months
    while m <= 0: y, m = y - 1, m + 12
    return f"{y:04d}-{m:02d}"

def snap_metric(t, label):
    for c in (SNAP.get(t) or {}).get("cards", []):
        for m in c.get("metrics", []):
            if m["label"].startswith(label): return m
    return None

# ------------------------------------------------------------------ benchmarks (SPY + equal-weight sector funds)
def benchmarks(offline):
    old = (OLD.get("benchmarks") or {})
    tickers = sorted({SMAP["market"]} | {v["equal_weight"] for v in SMAP["sectors"].values()})
    if offline: return old
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance not installed: keeping the previous benchmark prices"); return old
    out = dict(old)
    for b in tickers:
        try:
            h = yf.Ticker(b).history(period="6y", interval="1d", auto_adjust=False)["Close"].dropna()
            if len(h) < 200: raise ValueError("short history")
            me = h.groupby(h.index.strftime("%Y-%m")).last()
            out[b] = dict(monthly={k: round(float(v), 2) for k, v in me.items()}, price=round(float(h.iloc[-1]), 2),
                          date=h.index[-1].strftime("%Y-%m-%d"))
        except Exception as e:
            print(f"benchmark {b}: download failed ({e}); keeping the previous values")
    return out

def returns_from(monthly, price, now_ym):
    """YTD, 1, 3, 5-year price change from month-end closes to today's price."""
    def at(ym):
        if ym in monthly: return monthly[ym]
        prev = [k for k in monthly if k <= ym]
        return monthly[max(prev)] if prev else None
    out = {}
    base = {"ytd": f"{int(now_ym[:4]) - 1}-12", "y1": ym_minus(now_ym, 12), "y3": ym_minus(now_ym, 36), "y5": ym_minus(now_ym, 60)}
    first = min(monthly) if monthly else None
    for k, ym in base.items():
        p0 = at(ym) if first and first <= ym else None
        out[k] = r1(price / p0 - 1) if p0 and price else None
    return out

# ------------------------------------------------------------------ sector-module metrics (from the statements)
def metric(key, t, raw):
    inc, cfs, bal = dict(years(raw, "inc")), dict(years(raw, "cfs")), dict(years(raw, "bal"))
    ds = sorted(d for d in inc if (inc[d] or {}).get("rev"))
    pc = lambda x: f"{x * 100:.1f}%"
    pts = lambda x: f"{'+' if x >= 0 else '−'}{abs(x) * 100:.1f} pts"
    def ratio(num_part, num_key, den_key="rev"):
        vals = []
        for d in ds:
            src = {"inc": inc, "cfs": cfs, "bal": bal}[num_part].get(d) or {}
            n, r = src.get(num_key), (inc.get(d) or {}).get(den_key)
            if n is not None and r: vals.append((d[:4], abs(n) / r if num_key in ("capex", "sbc", "rd") else n / r))
        return vals
    def trend(vals, good_up=True, lab=""):
        if len(vals) < 2: return None
        (y0, a), (y1, b) = vals[0], vals[-1]
        ch = b - a
        tone = ("good" if (ch >= -0.01 if good_up else ch <= 0.01) else "bad" if (ch < -0.03 if good_up else ch > 0.03) else "caution")
        return dict(answer=pc(b), reading=f"{pts(ch)} since {y0}", tone=tone)
    if key == "gross_margin": return trend(ratio("inc", "gross"))
    if key == "op_margin": return trend(ratio("inc", "op"))
    if key == "fcf_margin": return trend(ratio("cfs", "fcf"))
    if key in ("rd_rev", "sbc_rev", "capex_rev"):
        vals = ratio("inc" if key == "rd_rev" else "cfs", {"rd_rev": "rd", "sbc_rev": "sbc", "capex_rev": "capex"}[key])
        if not vals: return None
        y0, a = vals[0]; y1, b = vals[-1]
        if key == "sbc_rev": tone = "bad" if b > 0.10 else "caution" if b > 0.05 else "key"
        elif key == "capex_rev": tone = "good" if b < 0.05 else "key"
        else: tone = "key"
        rd = f"{pc(a)} in {y0}" if len(vals) > 1 else ""
        if key == "capex_rev" and b < 0.05: rd = (rd + " · " if rd else "") + "asset-light"
        return dict(answer=pc(b), reading=rd, tone=tone)
    if key == "inventory":
        bd = sorted(d for d in bal if (bal[d] or {}).get("inventory"))
        if len(bd) < 2 or len(ds) < 2: return None
        i0, i1 = bal[bd[-2]]["inventory"], bal[bd[-1]]["inventory"]
        s0, s1 = inc[ds[-2]]["rev"], inc[ds[-1]]["rev"]
        gi, gs = i1 / i0 - 1, s1 / s0 - 1
        tone = "bad" if gi > gs + 0.10 else "caution" if gi > gs + 0.03 else "good"
        return dict(answer=f"inventory {gi * 100:+.0f}% vs sales {gs * 100:+.0f}%", reading=f"fiscal {ds[-1][:4]}", tone=tone)
    if key == "op_leverage":
        ops = [(d, inc[d].get("op")) for d in ds if inc[d].get("op")]
        if len(ops) < 3: return None
        (d0, o0), (d1, o1) = ops[0], ops[-1]
        n = int(d1[:4]) - int(d0[:4])
        if o0 <= 0 or o1 <= 0 or n <= 0: return None
        go, gs = (o1 / o0) ** (1 / n) - 1, (inc[d1]["rev"] / inc[d0]["rev"]) ** (1 / n) - 1
        tone = "good" if go >= gs else "caution" if go >= gs - 0.03 else "bad"
        return dict(answer=f"profit {go * 100:+.1f}%/yr vs sales {gs * 100:+.1f}%/yr", reading=f"{d0[:4]}–{d1[:4]}", tone=tone)
    if key == "capex_dep":
        m = snap_metric(t, "Capex ÷ depreciation")
        return dict(answer=m["value"], reading="", tone="key") if m and m.get("value") not in (None, "", "not in free data") else None
    if key in ("debt_ebitda", "int_cover", "rev_stability"):
        lab = {"debt_ebitda": "Net debt / EBITDA", "int_cover": "Interest coverage", "rev_stability": "Revenue consistency"}[key]
        m = snap_metric(t, lab)
        if not m or m.get("value") in (None, "", "not in free data"): return None
        tone = {2: "good", 1: "caution", 0: "bad"}.get(m.get("score"), "key") if m.get("graded") else "key"
        return dict(answer=str(m["value"]), reading=m.get("note") or "", tone=tone)
    if key == "div_cover":
        m = snap_metric(t, "Dividend coverage")
        if not m or m.get("value") in (None, "", "not in free data"): return None
        tone = {2: "good", 1: "caution", 0: "bad"}.get(m.get("score"), "key") if m.get("graded") else "key"
        return dict(answer=str(m["value"]), reading="free cash flow ÷ dividends", tone=tone)
    if key == "recession":
        s = (DUR.get(t) or {}).get("stress") or {}
        b = s.get("bad")
        if not s.get("label"): return None
        tone = {"durable": "good", "somewhat cyclical": "caution", "cyclical": "bad"}[s["label"]]
        rd = f"a repeat of the {b['episode']}: profit {b['op_change'] * 100:+.0f}%" if b else ""
        return dict(answer=s["label"], reading=rd, tone=tone)
    if key == "incr_roic":
        x = RET.get(t) or {}
        v = x.get("inc_recent")
        if v is None: return None
        r = x.get("r") or 0.09
        tone = "good" if v >= r + 0.05 else "caution" if v >= r else "bad"
        return dict(answer=("over 100%" if v > 1 else pc(v)), reading=f"vs {pc(r)} required return", tone=tone)
    if key == "roe":
        x = RET.get(t) or {}
        if x.get("measure") != "ROE" or not x.get("roic"): return None
        r, pts_ = x.get("r") or 0.09, x["roic"][-5:]
        now = pts_[-1][1]
        above = sum(1 for _, v in pts_ if v > r)
        tone = "good" if now >= r + 0.05 and above == len(pts_) else "bad" if now < r else "caution"
        return dict(answer=pc(now), reading=f"{pts_[-1][0]}; above the {pc(r)} required return in {above} of the last {len(pts_)} years", tone=tone)
    if key == "bv_growth":
        eq = [(d[:4], (bal[d] or {}).get("equity")) for d in sorted(bal) if (bal[d] or {}).get("equity")]
        if len(eq) < 3 or eq[0][1] <= 0: return None
        n = int(eq[-1][0]) - int(eq[0][0])
        if n <= 0: return None
        g = (eq[-1][1] / eq[0][1]) ** (1 / n) - 1
        return dict(answer=f"{g * 100:+.1f}% a year", reading=f"book value {eq[0][0]}–{eq[-1][0]} (incl. buybacks and dividends paid out)", tone="good" if g > 0.05 else "caution" if g >= 0 else "bad")
    if key == "services_share":
        sg = (SEG.get(t) or {}).get("segments") or {}
        sv = sg.get("Services")
        if not sv: return None
        tot0, tot1 = sum(v[1] for v in sg.values()), sum(v[0] for v in sg.values())
        g = sv[0] / sv[1] - 1
        return dict(answer=f"Services {sv[0] / tot1 * 100:.0f}% of sales", reading=f"growing {g * 100:+.0f}% ({SEG[t]['period'].split(' vs')[0]})",
                    tone="good" if g > 0.05 else "key")
    return None

# ------------------------------------------------------------------ the model (for "what the price assumes")
def load_model():
    """Runs model/model.py up to the point where it starts valuing stocks, so the same DCF engine, inputs, moat periods
    and segments are used. Nothing is written."""
    src = (ROOT / "model/model.py").read_text()
    cut = src.index("\nout = {")
    ns = {"__file__": str(ROOT / "model/model.py"), "__name__": "model_for_framework"}
    exec(compile(src[:cut], "model/model.py", "exec"), ns)
    return ns

def assumes_ins(ns, t, price):
    """Underwriter (book value and ROE model): the long-run ROE and the year-1 book growth today's price needs, the value
    if that growth is halved, and how long the base-case excess ROE must last."""
    s = dict(ns["INSURERS"][t]); r = ns["req_return"](t)
    mo = dict(ns["moat_of"](t), r_req=r)
    B = dict(s["scen"]["base"])
    V = lambda g1, m: ns["ri_value"](s["bv"], s["roe0"], g1, B["g10"], m, r, s["extra"], s["shares"], mo=mo)
    solve = ns["solve"]
    out = dict(method="excess_roe", price=price, r=r, base_g1=B["g1"], base_m=B["m"], bv_ps=r1(s["bv"] / s["shares"], 2), pb=r1(price / (s["bv"] / s["shares"]), 3))
    lo, hi = -0.5, 1.5
    out["g1_needed"] = r1(solve(lambda g: V(g, B["m"]) - price, lo, hi)) if (V(lo, B["m"]) - price) * (V(hi, B["m"]) - price) < 0 else None
    out["m_needed"] = r1(solve(lambda m: V(B["g1"], m) - price, -0.2, 0.9)) if (V(B["g1"], -0.2) - price) * (V(B["g1"], 0.9) - price) < 0 else None
    g = out["g1_needed"]
    if g is not None and g > B["g10"]:
        out["half_g1"] = r1(g / 2)
        out["half_value"] = r1(V(g / 2, B["m"]), 2)
    out["cap_needed"] = ns["ri_cap"](price, s, B, r, mo)
    return out

def assumes(ns, t, price):
    if t in ns.get("INSURERS", {}):
        return assumes_ins(ns, t, price) if price else None
    s = ns["STOCKS"].get(t)
    if not s or not price: return None
    s = dict(s); s["r"] = ns["req_return"](t)
    mo = dict(ns["moat_of"](t), r_req=s["r"]); sg = ns["segments_of"](t)
    D = lambda *x, **kw: ns["dcf"](*x, mo=mo, sg=sg, **kw)
    f = ns["FIN"][t]
    aint = 0.0 if ns["DCF_METHOD"] == "equity" else f["interest"] * (1 - f["tax"])
    add = aint / s["rev"]; m0 = (s["fcf"] - s["sbc"] + aint) / s["rev"]
    W = (lambda re: ns["wacc_of"](t, s, re)) if ns["DCF_METHOD"] == "fcff_wacc" else (lambda re: re)
    w = W(s["r"]); nc = s["net_cash"] + s["extra"]
    B = dict(s["scen"]["base"]); B["m"] += add
    V = lambda g1, m: D(s["rev"], m0, g1, B["g10"], m, w, nc, s["shares"])
    solve = ns["solve"]
    out = dict(price=price, r=s["r"], base_g1=B["g1"], base_m=B["m"])
    lo, hi = -0.5, 1.5
    out["g1_needed"] = r1(solve(lambda g: V(g, B["m"]) - price, lo, hi)) if (V(lo, B["m"]) - price) * (V(hi, B["m"]) - price) < 0 else None
    out["m_needed"] = r1(solve(lambda m: V(B["g1"], m) - price, -0.5, 0.95)) if (V(B["g1"], -0.5) - price) * (V(B["g1"], 0.95) - price) < 0 else None
    g = out["g1_needed"]
    if g is not None and g > B["g10"]:
        out["half_g1"] = r1(g / 2)
        out["half_value"] = r1(V(g / 2, B["m"]), 2)
    out["cap_needed"] = ns["implied_cap"](price, s["rev"], m0, B["g1"], B["m"], w, nc, s["shares"])
    return out

# ------------------------------------------------------------------ build
def sector_median_pe():
    files = sorted(f for f in glob.glob(str(ROOT / "data/screens/growth_screen_results_*.csv")) if "estimated" not in f)
    if not files: return {}, None
    by = {}
    for r in csv.DictReader(open(files[-1])):
        try:
            pe = float(r["pe_ratio"])
        except (ValueError, KeyError):
            continue
        if 0 < pe < 300: by.setdefault(r["sector"], []).append(pe)
    return {k: round(st.median(v), 1) for k, v in by.items() if len(v) >= 5}, pathlib.Path(files[-1]).name

def main():
    offline = "--offline" in sys.argv
    BM = benchmarks(offline)
    SPE, spe_src = sector_median_pe()
    ns = load_model()
    tips_m = (BOND.get("monthly") or {}).get("DFII10") or {}
    tips = (max(tips_m), tips_m[max(tips_m)]) if tips_m else None
    today = datetime.date.today()
    stocks = {}
    for t, a in sorted(ASSETS.items()):
        raw = RAW.get(t) or {}
        px = (PRICES.get(t) or {}).get("price") or a.get("price")
        now_ym = (PRICES.get(t) or {}).get("time", today.isoformat())[:7]
        have = {"snapshot": t in SNAP, "moat": t in MS, "returns": t in RET, "mc": bool(a.get("mc")),
                "bonds": bool((DUR.get(t) or {}).get("bond")), "stress": bool(((DUR.get(t) or {}).get("stress") or {}).get("label")),
                "duration": t in DURN}
        x = dict(currency=raw.get("currency") or "USD")
        # business: latest fiscal year vs the one before
        inc, cfs = years(raw, "inc"), dict(years(raw, "cfs"))
        fy = [(d, v) for d, v in inc if v.get("rev")]
        if len(fy) >= 2:
            (d0, v0), (d1, v1) = fy[-2], fy[-1]
            f0, f1 = (cfs.get(d0) or {}).get("fcf"), (cfs.get(d1) or {}).get("fcf")
            x["business"] = dict(fy=d1[:10], prev=d0[:10], sales=r1(pct(v1["rev"], v0["rev"])),
                                 eps=r1(pct(v1.get("eps"), v0.get("eps"))) if v0.get("eps") and v0["eps"] > 0 and v1.get("eps") is not None else None,
                                 fcf=r1(pct(f1, f0)) if f0 and f0 > 0 and f1 is not None else None)
            # split of the price move over that fiscal year
            p0, p1 = month_close(raw, d0[:7]), month_close(raw, d1[:7])
            e0, e1 = v0.get("eps"), v1.get("eps")
            if p0 and p1 and e0 and e1 and e0 > 0 and e1 > 0:
                x["split"] = dict(fy=d1[:10], price=r1(p1 / p0 - 1), eps=r1(e1 / e0 - 1), pe0=round(p0 / e0, 1), pe1=round(p1 / e1, 1),
                                  pe=r1((p1 / e1) / (p0 / e0) - 1))
        # market: price change to today, YTD with dividends, benchmarks
        mp = dict(raw.get("monthly_prices") or {})
        if mp and px:
            mk = returns_from({k: v for k, v in mp.items() if k < now_ym}, px, now_ym)
            dv = ((raw.get("dividends") or {}).get("by_year") or {}).get(now_ym[:4])
            p_ytd = month_close(raw, f"{int(now_ym[:4]) - 1}-12")
            mk["ytd_total"] = r1((px + (dv or 0)) / p_ytd - 1) if p_ytd and mk.get("ytd") is not None else None
            sec = (SMAP.get("stocks") or {}).get(t)
            etf = (SMAP["sectors"].get(sec) or {}).get("equal_weight") if sec else None
            for lab, b in (("spy", SMAP["market"]), ("sector", etf)):
                B = BM.get(b) if b else None
                mk[lab] = dict(ticker=b, **returns_from({k: v for k, v in B["monthly"].items() if k < B["date"][:7]}, B["price"], B["date"][:7]), date=B["date"]) if B else None
            mk["sector_name"] = sec
            x["market"] = mk
        have["market"] = "market" in x
        have["split"] = "split" in x
        have["bench"] = bool((x.get("market") or {}).get("spy") and (x.get("market") or {}).get("sector"))
        # bonds (spread 1 inputs + TIPS)
        bd = (DUR.get(t) or {}).get("bond")
        if bd:
            x["bonds"] = dict(ey=bd.get("ey_now"), aaa=bd.get("aaa_now"), t10=bd.get("t10_now"), month=bd.get("yields_month"),
                              median_gap=bd.get("gap_median"), tips=tips[1] if tips else None, tips_month=tips[0] if tips else None)
        # what the price assumes
        try:
            asm = assumes(ns, t, px)
        except Exception as e:
            print(f"{t}: assumes failed ({e})"); asm = None
        V = (SNAP.get(t) or {}).get("valuation") or {}
        eps_ttm = ((V.get("live") or {}).get("trailing_eps")) or ((raw.get("info") or {}).get("trailingEps"))
        sname = (V.get("sector_pct") or {}).get("name")
        own = [p for _, p in (V.get("history") or {}).get("pe", []) if p and p > 0]
        if asm is not None:
            asm["eps_ttm"] = eps_ttm
            if eps_ttm and eps_ttm > 0 and sname in SPE:
                asm["pe_sector"] = SPE[sname]; asm["sector"] = sname
            if eps_ttm and eps_ttm > 0 and own:
                asm["pe_own"] = round(st.median(own), 1); asm["pe_own_years"] = f"{(V['history']['pe'][0][0])}–{V['history']['pe'][-1][0]}"
            x["assumes"] = asm
        have["assumes"] = bool(asm and (asm.get("g1_needed") is not None or (asm.get("method") == "excess_roe" and asm.get("m_needed") is not None)))
        have["pe_sector"] = bool(asm and asm.get("pe_sector"))
        have["pe_own"] = bool(asm and asm.get("pe_own"))
        # sector module
        mod = MODULE_OF.get(t)
        sq = []
        if mod:
            for q, key in mod["questions"]:
                ans = metric(key, t, raw) if key else None
                sq.append(dict(q=q, **(ans or {"answer": None})))
            x["sector"] = dict(module=mod["name"], questions=sq)
        # coverage
        fixed = []
        ins = t in ns.get("INSURERS", {})
        for qid, text, status, need in Q:
            if ins and qid in NA_INSURER:
                fixed.append([qid, "na"]); continue
            if need and not have.get(need): status = "unknown" if status == "answered" or need in ("bonds", "market", "split", "assumes") else status
            if qid == "G46" and not have["bench"] and have["market"]: status = "partly"
            fixed.append([qid, status])
        n_ans = sum(1 for _, s in fixed if s == "answered") + sum(1 for q in sq if q.get("answer") is not None)
        n_part = sum(1 for _, s in fixed if s == "partly")
        n_unk = sum(1 for _, s in fixed if s == "unknown") + sum(1 for q in sq if q.get("answer") is None)
        n_na = sum(1 for _, s in fixed if s == "na")
        x["coverage"] = dict(total=len(fixed) + len(sq) - n_na, answered=n_ans, partly=n_part, unknown=n_unk, fixed=fixed, **({"na": n_na} if n_na else {}))
        stocks[t] = x
    doc = {"_about": __doc__.strip().split("\n\n")[0], "built": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "questions": {q[0]: q[1] for q in Q}, "sector_pe_source": spe_src, "benchmarks": BM, "stocks": stocks}
    if {k: v for k, v in OLD.items() if k != "built"} == json.loads(json.dumps({k: v for k, v in doc.items() if k != "built"}, default=float)):
        print("framework.json: no change"); return                   # keeps the daily price job a no-op outside market hours
    json.dump(doc, open(OUT, "w"), indent=None, separators=(",", ":"), default=float)
    c = [s["coverage"] for s in stocks.values()]
    print(f"framework.json: {len(stocks)} stocks; answered {sum(x['answered'] for x in c) / max(1, sum(x['total'] for x in c)) * 100:.0f}% "
          f"of {sum(x['total'] for x in c)} questions, unknown {sum(x['unknown'] for x in c)}")
    miss = [t for t in ASSETS if t not in MODULE_OF]
    if miss: print("no sector module:", " ".join(miss))

if __name__ == "__main__":
    main()
