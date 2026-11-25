#!/usr/bin/env python3
"""Research framework blocks for each stock's Fair Value drawer -> data/framework.json. Information only: nothing here
changes a fair value.

The drawer answers a fixed set of 64 questions (50 universal + 10 on what the market prices in + 4 on duration) plus 6–8 sector
questions per stock, chosen by business model (SECTOR_MODULES below), not by official sector. Every question is
"answered", "partly" or "unknown"; an unknown question is shown in grey as "not scored" and never counts as positive.

Per stock:
  business      latest fiscal year vs the year before: sales, EPS, free cash flow (data/snapshot_raw.json)
  market        share price change year to date, 1, 3 and 5 years (month-end closes + today's price), YTD with
                dividends, and the same for the S&P 500 (SPY) and the stock's equal-weight sector fund (data/sector_map.json)
  split         latest fiscal year (or 2-yr positive-EPS window): price change = EPS change x P/E change
  bonds         inputs for the three spreads: earnings yield vs Moody's Aaa, the 10-year Treasury and the 10-year real
                (TIPS) yield. The drawer adds the expected 10-year return (Monte Carlo median) for spreads 2 and 3.
  growth        split-adjusted 3/5/10-yr EPS & revenue CAGRs, exact EPS decomposition (revenue + margins + buybacks),
                growth trajectory (accelerating/steady/slowing), 3-5 yr expected growth (consensus + model), demand durability
  analysts      4-quarter actual vs estimate EPS beat/miss track record and 30d/90d EPS revision momentum (Yahoo Finance)
  cash_alloc    working capital vs core operating cash flow, maintenance vs growth capex (depreciation + Greenwald PPE/sales),
                capital-intensity trend, self-funding test, buyback price discipline vs fair value, value-per-share vs size
  industry_moat industry 3-yr growth & stock's relative market-share spread across screener peers, pricing power & inflation
                gross-margin test, barriers to copying, tech/AI disruption, 5-year debt maturity schedule (ASC 470),
                customer/supplier/market concentration, regulatory/geopolitical/technology risks
  recession     supplemental 2008-09 / 2020 10-K recession check for stocks not in durability.json (e.g. Russell 2000)
  assumes       at today's price and the required return, with the model's own cash-flow engine (model/model.py):
                year-1 sales growth needed, implied EPS/FCF growth, cash margin needed at base growth, value if growth is half
                the implied rate, advantage period needed, sector & own median P/E, Bear/Base/Bull 10-yr returns vs 10-yr bond,
                and 10-yr return decomposition (business growth + cash yield vs multiple re-rating)
  sector        the stock's module and each question's answer from statements, live KPIs (data/kpis.json), XBRL or 10-K research
  coverage      counts of answered / partly / unknown questions (underwriters: free-cash-flow and capex questions are "na")

Usage: python scripts/framework.py            (after model/model.py, the snapshot refresh and scripts/durability.py)
       python scripts/framework.py --offline  (skip the benchmark download and keep the previous benchmark prices)
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
RF = J("data/research_facts.json", {"sec": {}, "yahoo": {}})
SEC_F = RF.get("sec") or {}
YH_F = RF.get("yahoo") or {}
CR = (J("data/company_research.json", {"stocks": {}}) or {}).get("stocks") or {}
KPIS = (J("data/kpis.json", {"stocks": {}}) or {}).get("stocks") or {}
KPI_DEFS = (J("data/kpi_defs.json", {"stocks": {}}) or {}).get("stocks") or {}
DS = (J("data/debt_stress.json", {"stocks": {}}) or {}).get("stocks") or {}

# ------------------------------------------------------------------ the 64 fixed questions
# Each question's status is determined dynamically per stock from real data availability.
Q = [
 ("A1", "Earnings yield vs high-quality company bonds"),
 ("A2", "Earnings yield vs the 10-year Treasury"),
 ("A3", "Is the earnings spread positive or negative?"),
 ("A4", "Today's spread vs its own historical median"),
 ("A5", "Expensive vs bonds by its own history?"),
 ("A6", "Same currency and a comparable horizon?"),
 ("A7", "Extra return for taking equity risk"),
 ("B8", "EPS growth over 3, 5 and 10 years"),
 ("B9", "EPS growth from revenue vs margins"),
 ("B10", "EPS growth from buybacks"),
 ("B11", "Expected EPS growth over 3-5 years"),
 ("B12", "How reliable analyst forecasts have been"),
 ("B13", "Is growth speeding up or slowing?"),
 ("B14", "Earnings growing faster than revenue, and why"),
 ("B15", "Recurring demand or temporary circumstances?"),
 ("C16", "Pricing power"),
 ("C17", "Can it raise prices without losing customers?"),
 ("C18", "Sources of competitive advantage"),
 ("C19", "How easily can competitors copy it?"),
 ("C20", "Market share rising or falling?"),
 ("C21", "Industry growing, flat or shrinking?"),
 ("C22", "Could technology disrupt the business?"),
 ("C23", "How long the advantage can last"),
 ("D24", "Free cash flow growing with earnings?"),
 ("D25", "Share of net income that becomes free cash flow"),
 ("D26", "Cash flow from operations or working capital?"),
 ("D27", "Capex needed to maintain the business"),
 ("D28", "Capex needed for growth"),
 ("D29", "Becoming more or less capital-intensive?"),
 ("D30", "Can it fund growth without borrowing or issuing shares?"),
 ("E31", "Share of earnings paid as dividends"),
 ("E32", "Buybacks reducing the share count?"),
 ("E33", "Buybacks below or above intrinsic value?"),
 ("E34", "Retained capital earning above its cost?"),
 ("E35", "How capital is allocated"),
 ("E36", "Creating value per share or just size?"),
 ("F37", "Volatility of revenue, earnings and cash flow"),
 ("F38", "Sensitivity to recessions"),
 ("F39", "Debt to refinance in the next 1-5 years"),
 ("F40", "Cash flow covers interest and debt?"),
 ("F41", "Dependence on few customers, suppliers or markets"),
 ("F42", "Regulatory, geopolitical or technology risks"),
 ("F43", "Earnings fall in a realistic bad scenario"),
 ("G44", "Price change YTD, 1, 3 and 5 years"),
 ("G45", "Price rise from earnings vs a higher P/E"),
 ("G46", "Better or worse than its sector and the market?"),
 ("G47", "Valuation rising faster than earnings?"),
 ("G48", "Analysts becoming more optimistic?"),
 ("G49", "Growth implied by today's price"),
 ("G50", "Expected return if the multiple goes back to its average"),
 ("M1", "EPS growth implied by today's price"),
 ("M2", "Revenue growth needed"),
 ("M3", "Margin needed"),
 ("M4", "Enough room to reinvest for that growth?"),
 ("M5", "What if growth is half the implied rate?"),
 ("M6", "What if the P/E falls to the sector median?"),
 ("M7", "Bear, base and bull outcomes"),
 ("M8", "Each scenario vs the bond yield"),
 ("M9", "Return from business growth vs a re-rating"),
 ("M10", "Is the valuation premium covered by the advantage?"),
 # Duration (from November 2026, scripts/duration.py): how far into the future the value depends on receiving cash
 ("T1", "Share of value from cash 5, 10, 20 and 30+ years away"),
 ("T2", "How much the value moves if interest rates change"),
 ("T3", "Does your holding period cover where the value comes from?"),
 ("T4", "How reliable are the assumptions behind distant cash flows?"),
]

# Questions that don't apply to an underwriter (valued on book value and ROE): its cash flow mixes in premiums held for
# future claims, and its capex and working capital say little. Marked "na": not answered, not unknown, not counted.
NA_INSURER = {"D24", "D25", "D26", "D27", "D28", "D29", "D30", "F40"}

# ------------------------------------------------------------------ sector modules (by business model, all 132 stocks)
M_ = lambda name, tickers, qs: dict(name=name, tickers=tickers.split(), questions=qs)
SECTOR_MODULES = [
 M_("Software and internet", "MSFT GOOGL AMZN META NFLX ADBE CRM INTU ADSK WDAY VEEV FTNT VRSN GDDY APP FICO RDDT SHOP BKNG EXPE CARG ACIW BOX QLYS IDCC",
    [("How much revenue is recurring (subscriptions)?", None), ("Net revenue retention and churn", None),
     ("Gross margin holding up?", "gross_margin"), ("R&D share of revenue", "rd_rev"), ("Stock pay share of revenue", "sbc_rev"),
     ("Free cash flow margin", "fcf_margin"), ("Growth needs heavy infrastructure spending?", "capex_rev"),
     ("Is AI a new market or a threat?", None)]),
 M_("Hardware and devices", "AAPL GRMN MSI ANET",
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
 M_("Medical technology and animal health", "SYK RMD IDXX STE DXCM ZTS ALGN LMAT",
    [("Share of revenue from recurring consumables", None), ("Gross margin holding up?", "gross_margin"),
     ("R&D share of revenue", "rd_rev"), ("Recession resilience", "recession"), ("Product concentration", None),
     ("Reimbursement and approval risk", None)]),
 M_("Pharmaceuticals and biotech", "LLY REGN BMY AMGN JNJ INCY INVA",
    [("Revenue from patented products", None), ("When major patents expire", None), ("Pipeline success and trial risk", None),
     ("Product concentration", None), ("R&D share of revenue", "rd_rev"), ("Gross margin holding up?", "gross_margin"),
     ("Drug pricing and reimbursement risk", None)]),
 M_("Consumer brands and retail", "DECK TPR RL LULU ROST DLTR CMG HAS MNST MKC KO PG MO PM CL WSM MCRI",
    [("Growth from higher prices or more volume?", None), ("Market share rising or falling?", "mkt_share"),
     ("Gross margin holding up (pricing power)?", "gross_margin"), ("Inventory growing faster than sales?", "inventory"),
     ("Recession resilience", "recession"), ("Operating margin trend", "op_margin"), ("Customer acquisition cost", None)]),
 M_("Industrials and building", "ALLE AME CTAS FAST FIX EME HWM LII RSG TT WAB VLTO SHW PPG CPRT AOS EPAC LIN USLM",
    [("Order backlog and book-to-bill", None), ("Operating leverage (profit vs sales growth)", "op_leverage"),
     ("Maintenance capex (capex vs depreciation)", "capex_dep"), ("Returns on new investment", "incr_roic"),
     ("How cyclical is demand?", "recession"), ("Pricing power over input costs (gross margin)", "gross_margin"),
     ("Dependence on a few large customers", None)]),
 M_("Energy and commodities", "APA EOG BKR CF NEM TPL",
    [("Commodity prices behind today's earnings", None), ("Breakeven production cost", None), ("Production and reserves", None),
     ("How cyclical are profits?", "recession"), ("Debt vs earnings", "debt_ebitda"), ("Maintenance capex (capex vs depreciation)", "capex_dep"),
     ("Payouts covered by free cash flow", "div_cover")]),
 M_("Real estate (REITs)", "SPG HST VICI CTRE",
    [("Occupancy", None), ("Same-property income growth", None), ("Net asset value per share", None), ("Debt maturities", "debt_mat"),
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
 M_("Education services", "CVSA LAUR LRN",
    [("Enrollment growth", None), ("Revenue per student / pricing", None), ("Operating margin trend", "op_margin"),
     ("Free cash flow margin", "fcf_margin"), ("Recession resilience", "recession"), ("Regulatory and funding risk", None)]),
]
MODULE_OF = {t: m for m in SECTOR_MODULES for t in m["tickers"]}

# ------------------------------------------------------------------ helpers
def pct(a, b):
    return None if a is None or b in (None, 0) or (a < 0) != (b < 0) and b < 0 else a / b - 1

def r1(x, n=4):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(x, n)

def cagr(v1, v0, n):
    if v1 is None or v0 is None or v0 <= 0 or v1 <= 0 or n <= 0:
        return None
    return (v1 / v0) ** (1.0 / n) - 1.0

def years(raw, part):
    d = (raw.get("annual") or {}).get(part) or {}
    return sorted(d.items())                                   # [(date, {...}), ...] oldest first

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

# ------------------------------------------------------------------ split-adjusted multi-year history (SEC + snapshot_raw)
def build_annual_history(t, raw):
    """Merge 10+ years of SEC XBRL annuals ($M) with snapshot_raw annuals (converted to $M) and normalize
    dil_shares & eps for historical stock splits so 3/5/10-yr EPS and share-count CAGRs are split-exact."""
    sec_ann = (SEC_F.get(t) or {}).get("annual") or {}
    merged = {}
    for y, d in sec_ann.items():
        merged[int(y)] = dict(d)
    # Top up with snapshot_raw annuals (in $) converted to $M
    inc, cfs, bal = dict(years(raw, "inc")), dict(years(raw, "cfs")), dict(years(raw, "bal"))
    all_dates = sorted(set(inc) | set(cfs) | set(bal))
    raw_ys = [int(d[:4]) if d[5:7] > "03" else int(d[:4]) - 1 for d in all_dates]
    raw_cutoff = (max(raw_ys) - 3) if raw_ys else 0
    for d in all_dates:
        y = int(d[:4]) if d[5:7] > "03" else int(d[:4]) - 1
        rec = merged.setdefault(y, {"end": d[:10]})
        vi, vc, vb = inc.get(d) or {}, cfs.get(d) or {}, bal.get(d) or {}
        m = lambda v: round(v / 1e6, 2) if v is not None else None
        # Prefer snapshot_raw for the latest ~4 years when SEC lacks a line or is slightly behind
        for sk, rk in (("rev", "rev"), ("gross", "gross"), ("op", "op"), ("ni", "ni"), ("pretax", "pretax"), ("rd", "rd")):
            if vi.get(rk) is not None and (sk not in rec or y >= raw_cutoff):
                rec[sk] = m(vi[rk])
        if vi.get("eps") is not None and ("eps" not in rec or y >= raw_cutoff):
            rec["eps"] = round(float(vi["eps"]), 4)
        for sk, rk in (("ocf", "ocf"), ("capex", "capex"), ("da", "dep"), ("sbc", "sbc"), ("div", "div_paid"), ("buyback", "buyback"), ("acq", "acq"), ("issued", "issued")):
            if vc.get(rk) is not None and (sk not in rec or y >= raw_cutoff):
                rec[sk] = m(abs(vc[rk]) if sk in ("capex", "div", "buyback") else vc[rk])
        if vc.get("fcf") is not None:
            rec["fcf"] = m(vc["fcf"])
        for sk, rk in (("cash", "cash"), ("equity", "equity"), ("shares", "shares")):
            if vb.get(rk) is not None and (sk not in rec or y >= raw_cutoff):
                rec[sk] = m(vb[rk])
        if vb.get("debt") is not None and y >= raw_cutoff:
            rec["debt_tot"] = m(vb["debt"])
    # Fill dil_shares from ni/eps where missing or >5x off (fixes XBRL unit quirks like GRMN 2020-21), and fill fcf
    for y, rec in merged.items():
        if rec.get("fcf") is None and rec.get("ocf") is not None and rec.get("capex") is not None:
            rec["fcf"] = round(rec["ocf"] - abs(rec["capex"]), 2)
        if rec.get("premiums") and (rec.get("rev") is None or rec["rev"] < rec["premiums"] * 0.5):
            rec["rev"] = round(rec["premiums"] + (rec.get("inv_inc") or 0.0), 2)
        if rec.get("ni") and rec.get("eps") and rec["ni"] * rec["eps"] > 0:
            implied_sh = rec["ni"] / rec["eps"]
            if rec.get("dil_shares") is None or (implied_sh > 0 and (rec["dil_shares"] / implied_sh > 5.0 or rec["dil_shares"] / implied_sh < 0.2)):
                rec["dil_shares"] = round(implied_sh, 2)
        elif rec.get("dil_shares") is None and rec.get("shares"):
            rec["dil_shares"] = rec["shares"]
        if rec.get("eps") is None and rec.get("ni") is not None and rec.get("dil_shares") and rec["dil_shares"] > 0:
            rec["eps"] = round(rec["ni"] / rec["dil_shares"], 4)

    # Split-adjust dil_shares and eps walking backwards from the most recent year!
    # Match sudden jumps in dil_shares (or eps) against known split factors from raw["splits"] (or clean integer splits >= 1.5x).
    splits = [float(v) for k, v in (raw.get("splits") or {}).items() if k >= "2008-01-01" and float(v) >= 1.4]
    cand_factors = sorted(set(splits + [k * k2 for k in splits for k2 in splits if k != k2]), reverse=True)
    ys = sorted(merged)
    sh_series = {y: merged[y].get("dil_shares") for y in ys if merged[y].get("dil_shares") and merged[y]["dil_shares"] > 0}
    sh_ys = sorted(sh_series)
    cum = 1.0
    adj_factor = {}
    if sh_ys:
        adj_factor[sh_ys[-1]] = 1.0
        for i in range(len(sh_ys) - 2, -1, -1):
            y_cur, y_nxt = sh_ys[i], sh_ys[i + 1]
            ratio = sh_series[y_nxt] / sh_series[y_cur]
            matched = None
            for f in cand_factors:
                if abs(ratio / f - 1.0) < 0.28:
                    matched = f
                    break
            if matched:
                cum *= matched
            adj_factor[y_cur] = cum
    for y in ys:
        # Interpolate factor from nearest >= year
        f = adj_factor.get(y)
        if f is None:
            later = [yy for yy in sh_ys if yy >= y]
            f = adj_factor[later[0]] if later else 1.0
        if f != 1.0:
            if merged[y].get("dil_shares"):
                merged[y]["dil_shares"] = round(merged[y]["dil_shares"] * f, 2)
            if merged[y].get("eps") is not None:
                merged[y]["eps"] = round(merged[y]["eps"] / f, 4)
        # Re-verify split-consistent EPS from ni / dil_shares when EPS was still on a pre-split basis
        rec = merged[y]
        if rec.get("ni") is not None and rec.get("dil_shares") and rec["dil_shares"] > 0:
            calc_eps = rec["ni"] / rec["dil_shares"]
            if rec.get("eps") is None or (rec["eps"] * calc_eps > 0 and abs(rec["eps"] / calc_eps - 1.0) > 0.35):
                rec["eps"] = round(calc_eps, 4)
    return merged

# ------------------------------------------------------------------ industry benchmarks (C20, C21) from screener CSVs
def load_industry_benchmarks():
    """Aggregate 3-yr revenue CAGR and YoY revenue growth by exact industry & sector across all S&P 500 + Russell 2000 CSVs."""
    by_ind, by_sec, stock_meta = {}, {}, {}
    sources = []
    gfiles = sorted(f for f in glob.glob(str(ROOT / "data/screens/growth_screen_results_*.csv")) if "estimated" not in f)
    rfiles = sorted(glob.glob(str(ROOT / "data/screens/russell/r2000_screen_*.csv")))
    if gfiles: sources.append(gfiles[-1])
    if rfiles: sources.append(rfiles[-1])
    seen = set()
    for fp in sources:
        for row in csv.DictReader(open(fp)):
            tk = (row.get("ticker") or "").strip().upper()
            if not tk or tk in seen: continue
            seen.add(tk)
            ind = (row.get("industry") or "").strip()
            sec = (row.get("sector") or "").strip()
            def flt(k):
                try:
                    v = float(row.get(k, ""))
                    return v if math.isfinite(v) and -80 < v < 300 else None
                except (ValueError, TypeError):
                    return None
            c3 = flt("rev_cagr_pct")
            y1 = flt("rev_growth_pct")
            stock_meta[tk] = dict(industry=ind, sector=sec, rev_cagr_pct=c3, rev_growth_pct=y1)
            if ind:
                slot = by_ind.setdefault(ind, {"c3": [], "y1": []})
                if c3 is not None: slot["c3"].append(c3)
                if y1 is not None: slot["y1"].append(y1)
            if sec:
                slot = by_sec.setdefault(sec, {"c3": [], "y1": []})
                if c3 is not None: slot["c3"].append(c3)
                if y1 is not None: slot["y1"].append(y1)
    return by_ind, by_sec, stock_meta

# ------------------------------------------------------------------ block builders
def build_growth(t, a, raw, hist, ins):
    ys = sorted(y for y, d in hist.items() if d.get("rev") and d["rev"] > 0)
    out = {}
    if ys:
        y_end = ys[-1]
        def pick_cagr(key, span):
            # Look for exact span, else span +/- 1 year; skip near-zero breakeven EPS bases (<$0.05 & NM <0.5%)
            for dy in (span, span + 1, span - 1):
                y0 = y_end - dy
                if y0 in hist and hist[y0].get(key) is not None and hist[y_end].get(key) is not None:
                    v0 = hist[y0][key]
                    if key == "eps" and v0 > 0 and v0 < 0.05 and hist[y0].get("ni") and hist[y0].get("rev") and hist[y0]["ni"] / hist[y0]["rev"] < 0.005:
                        continue
                    v = cagr(hist[y_end][key], v0, dy)
                    if v is not None:
                        return r1(v), dy
            return None, None
        for span, lab in ((3, "3y"), (5, "5y"), (10, "10y")):
            ev, en = pick_cagr("eps", span)
            rv, rn = pick_cagr("rev", span)
            if ev is not None: out[f"eps_{lab}"] = ev
            if rv is not None: out[f"rev_{lab}"] = rv
        # EPS growth decomposition (B9, B10, B14): prefer 5-yr positive window, else 3-yr
        decomp = None
        for span in (5, 4, 3, 2):
            y0 = y_end - span
            if y0 not in hist: continue
            d0, d1 = hist[y0], hist[y_end]
            if all(d.get(k) and d[k] > 0 for d in (d0, d1) for k in ("rev", "ni", "dil_shares")):
                g_rev = cagr(d1["rev"], d0["rev"], span)
                nm0, nm1 = d0["ni"] / d0["rev"], d1["ni"] / d1["rev"]
                g_nm = cagr(nm1, nm0, span)
                g_bb = cagr(d0["dil_shares"], d1["dil_shares"], span)  # positive = buybacks boosted EPS
                g_sh = cagr(d1["dil_shares"], d0["dil_shares"], span)
                g_eps = (1 + g_rev) * (1 + g_nm) * (1 + g_bb) - 1
                g_om = None
                if d0.get("op") and d1.get("op") and d0["op"] > 0 and d1["op"] > 0:
                    g_om = cagr(d1["op"] / d1["rev"], d0["op"] / d0["rev"], span)
                gap = g_eps - g_rev
                parts = [f"sales {g_rev*100:+.1f}%/yr", f"net margin {g_nm*100:+.1f}%/yr",
                         f"{'buybacks' if g_bb >= 0 else 'dilution'} {g_bb*100:+.1f}%/yr"]
                decomp = dict(
                    years=f"{y0}–{y_end}", n=span,
                    eps_cagr=r1(g_eps), rev_cagr=r1(g_rev), margin_cagr=r1(g_nm),
                    op_margin_cagr=r1(g_om), buyback_cagr=r1(g_bb), shares_cagr=r1(g_sh),
                    gap=r1(gap), nm0=r1(nm0), nm1=r1(nm1),
                    faster=gap > 0.005, summary=", ".join(parts),
                )
                break
        if decomp:
            out["decomp"] = decomp
        # Growth trajectory (B13): compare 1y / recent Q YoY vs 3y vs 5y
        rev_1y = cagr(hist[y_end]["rev"], hist[y_end - 1]["rev"], 1) if (y_end - 1) in hist and hist[y_end - 1].get("rev") else None
        eps_1y = cagr(hist[y_end].get("eps"), hist[y_end - 1].get("eps"), 1) if (y_end - 1) in hist else None
        q_yoy_m = snap_metric(t, "Revenue growth, latest quarter")
        q_yoy = None
        if q_yoy_m and q_yoy_m.get("value"):
            try: q_yoy = float(str(q_yoy_m["value"]).replace("%", "").replace("+", "").replace("−", "-")) / 100.0
            except ValueError: pass
        recent_r = q_yoy if q_yoy is not None else rev_1y
        base_r = out.get("rev_3y") if out.get("rev_3y") is not None else out.get("rev_5y")
        if recent_r is not None and base_r is not None:
            diff_r = recent_r - base_r
            lbl = "speeding up" if diff_r > 0.025 else "slowing" if diff_r < -0.025 else "steady"
            tone = "good" if lbl == "speeding up" else "caution" if lbl == "steady" else "bad"
            out["trajectory"] = dict(
                label=lbl, tone=tone,
                rev_q=r1(q_yoy), rev_1y=r1(rev_1y), rev_3y=out.get("rev_3y"), rev_5y=out.get("rev_5y"),
                eps_1y=r1(eps_1y), eps_3y=out.get("eps_3y"), eps_5y=out.get("eps_5y"),
            )
    # Expected 3-5 yr growth (B11): Yahoo consensus 0y/+1y EPS growth + model base 3-yr & 5-yr cash-flow/earnings CAGR
    yt = (YH_F.get(t) or {}).get("trend") or {}
    a0y = (yt.get("0y") or {}).get("growth")
    a1y = (yt.get("+1y") or {}).get("growth")
    fc_base = ((a.get("forecast") or {}).get("base") or {})
    rows_fc = fc_base.get("rows") or []
    m3, m5 = None, None
    if len(rows_fc) >= 5:
        if ins and fc_base.get("ni") and len(fc_base["ni"]) >= 5 and fc_base["ni"][0] > 0:
            m3 = cagr(fc_base["ni"][3], fc_base["ni"][0], 3) if fc_base["ni"][3] > 0 else None
            m5 = cagr(fc_base["ni"][4], fc_base["ni"][0], 4) if fc_base["ni"][4] > 0 else None
        elif rows_fc[0].get("fcf") and rows_fc[0]["fcf"] > 0:
            m3 = cagr(rows_fc[2]["fcf"], rows_fc[0]["fcf"], 2) if rows_fc[2]["fcf"] > 0 else None
            m5 = cagr(rows_fc[4]["fcf"], rows_fc[0]["fcf"], 4) if rows_fc[4]["fcf"] > 0 else None
        # Also include revenue base CAGR y1-y5
        r5 = cagr(rows_fc[4]["rev"], rows_fc[0]["rev"], 4) if rows_fc[0].get("rev") and rows_fc[4].get("rev") else None
    else:
        r5 = None
    if any(v is not None for v in (a0y, a1y, m5, r5)):
        out["expected"] = dict(
            analyst_0y=r1(a0y), analyst_1y=r1(a1y),
            model_cf_5y=r1(m5), model_rev_5y=r1(r5),
            base_g1=r1(((a.get("scenarios") or {}).get("base") or {}).get("g1")),
        )
    # Demand durability (B15 — dated research note)
    cr = CR.get(t) or {}
    if cr.get("demand"):
        out["demand"] = dict(cr["demand"], note=True)
    return out or None

def build_analysts(t):
    y = YH_F.get(t) or {}
    out = {}
    hist = y.get("history") or []
    if len(hist) >= 3:
        beats = sum(1 for h in hist if h.get("surprise") is not None and h["surprise"] > 0.002)
        misses = sum(1 for h in hist if h.get("surprise") is not None and h["surprise"] < -0.002)
        surps = [h["surprise"] for h in hist if h.get("surprise") is not None]
        avg_s = st.mean(surps) if surps else None
        verdict = ("consistently beats" if beats == len(hist) else "mostly beats" if beats > misses
                   else "mostly misses" if misses > beats else "mixed")
        tone = "good" if beats >= len(hist) - 1 and (avg_s or 0) >= 0 else "bad" if misses > beats else "caution"
        out["history"] = dict(
            n=len(hist), beats=beats, misses=misses, avg_surprise=r1(avg_s),
            min_surp=r1(min(surps)) if surps else None, max_surp=r1(max(surps)) if surps else None,
            verdict=verdict, tone=tone, quarters=hist[-4:],
        )
    tr = y.get("trend") or {}
    # Prefer +1y for forward optimism, fall back to 0y
    p1, p0 = tr.get("+1y") or {}, tr.get("0y") or {}
    ref = p1 if p1.get("cur") is not None and (p1.get("d30") is not None or p1.get("d90") is not None) else p0
    if ref and ref.get("cur") is not None and (ref.get("d30") is not None or ref.get("d90") is not None):
        chg30 = (ref["cur"] / ref["d30"] - 1) if ref.get("d30") and ref["d30"] > 0 else None
        chg90 = (ref["cur"] / ref["d90"] - 1) if ref.get("d90") and ref["d90"] > 0 else None
        up30, dn30 = int(ref.get("up30") or 0), int(ref.get("dn30") or 0)
        chg_ref = chg90 if chg90 is not None else chg30
        if (chg_ref is not None and chg_ref > 0.015) or (up30 > dn30 and (chg30 or 0) >= 0):
            verdict, tone = "more optimistic", "good"
        elif (chg_ref is not None and chg_ref < -0.015) or (dn30 > up30 and (chg30 or 0) <= 0):
            verdict, tone = "more cautious", "bad"
        else:
            verdict, tone = "steady", "key"
        out["revisions"] = dict(
            period="+1y" if ref is p1 else "0y",
            cur=r1(ref["cur"], 2), d30=r1(ref.get("d30"), 2), d90=r1(ref.get("d90"), 2),
            chg_30d=r1(chg30), chg_90d=r1(chg90),
            up30=up30, dn30=dn30, n_analysts=int(ref.get("eps_n") or y.get("analysts") or 0),
            verdict=verdict, tone=tone,
        )
    if out:
        as_of = (y.get("fetched") or RF.get("yahoo_fetched") or RF.get("fetched") or "")[:10]
        if as_of:
            out["as_of"] = as_of
    return out or None

def build_cash_alloc(t, a, raw, hist, ins, growth):
    out = {}
    ys = sorted(hist)
    # --- Non-insurer cash flow & capex questions (D26, D27, D28, D29, D30) ---
    if not ins:
        # D26: Cash flow from operations vs working capital (3-yr cumulative OCF vs NI + D&A + SBC)
        wc_ys = [y for y in ys[-4:] if hist[y].get("ocf") is not None and hist[y].get("ni") is not None]
        if len(wc_ys) >= 2:
            use = wc_ys[-3:]
            ocf_s = sum(hist[y]["ocf"] for y in use)
            ni_s = sum(hist[y]["ni"] for y in use)
            da_s = sum(abs(hist[y].get("da") or hist[y].get("dep") or 0) for y in use)
            sbc_s = sum(abs(hist[y].get("sbc") or 0) for y in use)
            core_s = ni_s + da_s + sbc_s
            wc_other = ocf_s - core_s
            wc_share = wc_other / ocf_s if ocf_s > 0 else None
            if wc_share is not None:
                if abs(wc_share) <= 0.15:
                    v, tone = "from core operations", "good"
                elif wc_share > 0.15:
                    v, tone = "boosted by working capital / deferred rev", "caution" if wc_share > 0.30 else "good"
                else:
                    v, tone = "working capital absorbed cash", "caution" if wc_share > -0.30 else "bad"
                out["wc"] = dict(
                    years=f"{use[0]}–{use[-1]}", ocf_b=r1(ocf_s / 1e3, 2), core_b=r1(core_s / 1e3, 2),
                    wc_b=r1(wc_other / 1e3, 2), wc_share=r1(wc_share), verdict=v, tone=tone,
                )
        # D27 & D28: Maintenance vs Growth Capex (Depreciation proxy + Greenwald PPE/Sales check)
        cx_ys = [y for y in ys[-4:] if hist[y].get("capex") is not None and hist[y].get("rev") and hist[y]["rev"] > 0]
        if len(cx_ys) >= 2:
            use = cx_ys[-3:]
            cx_avg = st.mean(abs(hist[y]["capex"]) for y in use)
            rev_avg = st.mean(hist[y]["rev"] for y in use)
            ocf_vals = [hist[y]["ocf"] for y in use if hist[y].get("ocf") is not None]
            ocf_avg = st.mean(ocf_vals) if ocf_vals else None
            # Prefer pure PPE depreciation ("dep") over D&A ("da") when available so acquired-intangible amort doesn't overstate maint
            dep_pure = [abs(hist[y]["dep"]) for y in use if hist[y].get("dep") is not None]
            da_vals = [abs(hist[y]["da"]) for y in use if hist[y].get("da") is not None]
            maint_dep = st.mean(dep_pure) if dep_pure else (st.mean(da_vals) if da_vals else None)
            # Greenwald Net-PPE / Sales growth-capex estimate over available window
            ppe_ys = [y for y in ys[-5:] if hist[y].get("ppe") and hist[y].get("rev") and hist[y]["rev"] > 0]
            gw_growth = None
            if len(ppe_ys) >= 3:
                ppe_sales = st.median(hist[y]["ppe"] / hist[y]["rev"] for y in ppe_ys)
                d_rev_yr = (hist[ppe_ys[-1]]["rev"] - hist[ppe_ys[0]]["rev"]) / max(1, ppe_ys[-1] - ppe_ys[0])
                gw_growth = max(0.0, d_rev_yr * ppe_sales)
            if maint_dep is not None:
                maint = min(cx_avg, maint_dep)
                if gw_growth is not None:
                    # Blend Greenwald growth capex with excess-over-depreciation when capex > dep
                    growth_cx = max(0.0, min(cx_avg, (max(0.0, cx_avg - maint) + min(cx_avg, gw_growth)) / 2.0))
                    maint = max(0.0, cx_avg - growth_cx)
                    method = "depreciation + PPE/sales (Greenwald)"
                else:
                    growth_cx = max(0.0, cx_avg - maint)
                    method = "pure depreciation" if dep_pure else "D&A proxy"
            elif gw_growth is not None:
                growth_cx = min(cx_avg, gw_growth)
                maint = max(0.0, cx_avg - growth_cx)
                method = "PPE/sales (Greenwald)"
            else:
                maint, growth_cx, method = cx_avg * 0.7, cx_avg * 0.3, "estimated split"
            out["capex_split"] = dict(
                years=f"{use[0]}–{use[-1]}",
                total_b=r1(cx_avg / 1e3, 2), maint_b=r1(maint / 1e3, 2), growth_b=r1(growth_cx / 1e3, 2),
                maint_pct_rev=r1(maint / rev_avg), growth_pct_rev=r1(growth_cx / rev_avg),
                maint_pct_ocf=r1(maint / ocf_avg) if ocf_avg and ocf_avg > 0 else None,
                method=method,
            )
        # D29: Becoming more or less capital-intensive? (Compare early vs recent Capex/Rev and Net PPE/Rev)
        ci_ys = [y for y in ys if hist[y].get("capex") is not None and hist[y].get("rev") and hist[y]["rev"] > 0]
        if len(ci_ys) >= 4:
            early = ci_ys[:min(3, len(ci_ys) // 2)]
            recent = ci_ys[-min(3, len(ci_ys) // 2):]
            c_early = st.mean(abs(hist[y]["capex"]) / hist[y]["rev"] for y in early)
            c_rec = st.mean(abs(hist[y]["capex"]) / hist[y]["rev"] for y in recent)
            ch = c_rec - c_early
            ppe_e = [hist[y]["ppe"] / hist[y]["rev"] for y in early if hist[y].get("ppe")]
            ppe_r = [hist[y]["ppe"] / hist[y]["rev"] for y in recent if hist[y].get("ppe")]
            lbl = "more capital-intensive" if ch > 0.015 else "less capital-intensive" if ch < -0.015 else "steady"
            tone = "bad" if ch > 0.04 else "caution" if ch > 0.015 else "good"
            out["cap_intensity"] = dict(
                early_years=f"{early[0]}–{early[-1]}" if len(early) > 1 else str(early[0]),
                recent_years=f"{recent[0]}–{recent[-1]}" if len(recent) > 1 else str(recent[0]),
                capex_early=r1(c_early), capex_recent=r1(c_rec), change_pts=r1(ch),
                ppe_early=r1(st.mean(ppe_e)) if ppe_e else None,
                ppe_recent=r1(st.mean(ppe_r)) if ppe_r else None,
                verdict=lbl, tone=tone,
            )
        # D30: Can it fund growth without borrowing or issuing shares? (3-yr FCF vs Dividends + Acq, net debt & share change)
        sf_ys = [y for y in ys[-4:] if hist[y].get("fcf") is not None]
        if len(sf_ys) >= 2:
            use = sf_ys[-3:]
            fcf_s = sum(hist[y]["fcf"] for y in use)
            div_s = sum(abs(hist[y].get("div") or 0) for y in use)
            acq_s = sum(abs(hist[y].get("acq") or 0) for y in use)
            iss_s = sum(max(0.0, hist[y].get("issued") or 0) for y in use)
            bb_s = sum(abs(hist[y].get("buyback") or 0) for y in use)
            needs = div_s + acq_s
            surplus = fcf_s - needs
            if fcf_s > 0 and surplus >= -0.05 * fcf_s and iss_s <= max(bb_s, 0.10 * fcf_s):
                v, tone = "yes — self-funded from cash flow", "good"
            elif fcf_s > 0 and fcf_s >= div_s:
                v, tone = "operations self-funded; used debt for M&A or buybacks", "caution"
            else:
                v, tone = "needed outside debt or equity", "bad"
            out["self_fund"] = dict(
                years=f"{use[0]}–{use[-1]}",
                fcf_b=r1(fcf_s / 1e3, 2), div_b=r1(div_s / 1e3, 2), acq_b=r1(acq_s / 1e3, 2),
                verdict=v, tone=tone,
            )

    # --- E33: Buyback price timing vs own P/E history (marked partly: historical fair values aren't recorded) ---
    cfs_raw = dict(years(raw, "cfs"))
    inc_raw = dict(years(raw, "inc"))
    mp = raw.get("monthly_prices") or {}
    mcap = (raw.get("price") or a.get("price") or 0) * (raw.get("shares") or (a.get("shares", 0) * 1e9))
    bb_rows = []
    for d, vc in sorted(cfs_raw.items()):
        bb = abs(vc.get("buyback") or 0)
        end_ym = d[:7]
        start_ym = ym_minus(end_ym, 11)
        fy_pxs = [v for k, v in mp.items() if start_ym <= k <= end_ym and v and v > 0]
        avg_px = st.mean(fy_pxs) if fy_pxs else month_close(raw, end_ym)
        fy_lbl = d[:4]
        eps = (inc_raw.get(d) or {}).get("eps")
        pe = avg_px / eps if avg_px and eps and eps > 0 else None
        if avg_px:
            bb_rows.append((fy_lbl, bb, avg_px, pe))
    active = [x for x in bb_rows if x[1] > 0]
    tot_bb = sum(x[1] for x in active)
    ann_bb_pct = (tot_bb / max(1, len(cfs_raw))) / mcap if mcap > 0 else 0
    if not cfs_raw:
        pass
    elif tot_bb <= 0 or ann_bb_pct < 0.0025:
        out["buyback_val"] = dict(
            status="partly", verdict="minimal or no buybacks", tone="key",
            total_b=r1(tot_bb / 1e9, 2), reading="retains cash or pays dividends instead",
        )
    else:
        w_px = sum(x[1] * x[2] for x in active) / tot_bb
        s_px = st.mean(x[2] for x in active)
        pe_rows = [x for x in active if x[3] is not None and x[3] < 150]
        w_pe = (sum(x[1] * x[3] for x in pe_rows) / sum(x[1] for x in pe_rows)) if pe_rows else None
        s_pe = st.mean(x[3] for x in pe_rows) if pe_rows else None
        if w_pe is not None and s_pe is not None and len(pe_rows) >= 2:
            rel = w_pe / s_pe - 1.0
            if rel <= -0.05:
                v, tone = f"bought more at lower P/E ({w_pe:.1f}× vs {s_pe:.1f}× avg)", "good"
            elif rel >= 0.05:
                v, tone = f"bought more at higher P/E ({w_pe:.1f}× vs {s_pe:.1f}× avg)", "caution"
            else:
                v, tone = f"steady pace around {w_pe:.1f}× P/E", "key"
        elif w_pe is not None:
            v, tone = f"weighted buyback P/E {w_pe:.1f}×", "key"
        else:
            v, tone = f"avg buyback price ${w_px:.2f}", "key"
        out["buyback_val"] = dict(
            status="partly", years=f"FY{active[0][0]}–FY{active[-1][0]}", total_b=r1(tot_bb / 1e9, 2),
            avg_px=r1(w_px, 2), period_avg_px=r1(s_px, 2), w_pe=r1(w_pe, 1), period_avg_pe=r1(s_pe, 1),
            verdict=v, tone=tone,
        )

    # --- E36: Creating value per share or just size? (All 132 stocks) ---
    dc = (growth or {}).get("decomp")
    rx = RET.get(t) or {}
    roic_now, r_req = rx.get("roic_now"), rx.get("r") or a.get("required_return") or 0.09
    fcf_ps_cagr = None
    if not ins and dc:
        y0, y1 = int(dc["years"].split("–")[0]), int(dc["years"].split("–")[1])
        d0, d1 = hist.get(y0) or {}, hist.get(y1) or {}
        if d0.get("fcf") and d1.get("fcf") and d0["fcf"] > 0 and d1["fcf"] > 0 and d0.get("dil_shares") and d1.get("dil_shares"):
            fcf_ps_cagr = cagr(d1["fcf"] / d1["dil_shares"], d0["fcf"] / d0["dil_shares"], dc["n"])
    if dc or roic_now is not None:
        eps_g = dc["eps_cagr"] if dc else None
        rev_g = dc["rev_cagr"] if dc else None
        sh_g = dc["shares_cagr"] if dc else None
        beats_r = roic_now is not None and roic_now > r_req
        ps_ok = (eps_g is not None and rev_g is not None and eps_g >= rev_g - 0.01 and eps_g > 0.03)
        diluting = sh_g is not None and sh_g > 0.025
        if beats_r and ps_ok and not diluting:
            v, tone = "creating value per share", "good"
        elif (roic_now is not None and roic_now < r_req) or (diluting and eps_g is not None and rev_g is not None and eps_g < rev_g - 0.02):
            v, tone = "growing size faster than per-share value", "bad"
        else:
            v, tone = "mixed per-share compounding", "caution"
        out["per_share"] = dict(
            years=dc["years"] if dc else None,
            eps_cagr=r1(eps_g), rev_cagr=r1(rev_g), fcf_ps_cagr=r1(fcf_ps_cagr),
            shares_cagr=r1(sh_g), roic=r1(roic_now), hurdle=r1(r_req),
            measure=rx.get("measure") or ("ROE" if ins else "ROIC"),
            verdict=v, tone=tone,
        )
    return out or None

def build_industry_moat(t, a, raw, hist, by_ind, by_sec, smeta):
    out = {}
    cr = CR.get(t) or {}
    yh = YH_F.get(t) or {}
    meta = smeta.get(t) or {}
    ind = meta.get("industry") or yh.get("industry")
    sec_raw = meta.get("sector") or yh.get("sector") or (SMAP.get("stocks") or {}).get(t)
    SEC_ALIAS = {"Financials": "Financial Services", "Information Technology": "Technology", "Health Care": "Healthcare",
                 "Consumer Discretionary": "Consumer Cyclical", "Consumer Staples": "Consumer Defensive", "Materials": "Basic Materials"}
    sec = SEC_ALIAS.get(sec_raw, sec_raw)
    if not ind and t == "FISV":
        ind = "Information Technology Services"
    # C21: Industry growth
    slot = by_ind.get(ind) if ind and len((by_ind.get(ind) or {}).get("c3", [])) >= 4 else None
    basis = ind if slot else sec
    if not slot and sec:
        slot = by_sec.get(sec)
    ind_c3 = st.median(slot["c3"]) / 100.0 if slot and slot.get("c3") else None
    ind_y1 = st.median(slot["y1"]) / 100.0 if slot and slot.get("y1") else None
    n_peers = len(slot["c3"]) if slot and slot.get("c3") else 0
    if ind_c3 is not None:
        lbl = "growing" if ind_c3 >= 0.06 else "moderate growth" if ind_c3 >= 0.02 else "flat" if ind_c3 >= -0.02 else "shrinking"
        tone = "good" if ind_c3 >= 0.06 else "key" if ind_c3 >= 0.02 else "caution" if ind_c3 >= -0.02 else "bad"
        out["industry"] = dict(name=basis, peers=n_peers, cagr_3y=r1(ind_c3), yoy=r1(ind_y1), verdict=lbl, tone=tone)
        # C20: Market share rising or falling? (Company 3-yr revenue CAGR vs industry median)
        ys = sorted(y for y, d in hist.items() if d.get("rev") and d["rev"] > 0)
        co_c3 = None
        if meta.get("rev_cagr_pct") is not None:
            co_c3 = meta["rev_cagr_pct"] / 100.0
        elif len(ys) >= 4:
            co_c3 = cagr(hist[ys[-1]]["rev"], hist[ys[-4]]["rev"], ys[-1] - ys[-4])
        elif len(ys) >= 3:
            co_c3 = cagr(hist[ys[-1]]["rev"], hist[ys[-3]]["rev"], ys[-1] - ys[-3])
        if co_c3 is not None:
            sp = co_c3 - ind_c3
            slbl = "gaining share" if sp >= 0.02 else "losing share" if sp <= -0.02 else "holding share"
            stone = "good" if sp >= 0.02 else "bad" if sp <= -0.02 else "key"
            out["share"] = dict(co_cagr_3y=r1(co_c3), ind_cagr_3y=r1(ind_c3), spread=r1(sp),
                                peers=n_peers, industry=basis, verdict=slbl, tone=stone)
    # C16 & C17: Pricing power + 2021-2026 inflation gross-margin test
    gm_pts = [(y, hist[y]["gross"] / hist[y]["rev"]) for y in sorted(hist)
              if y >= 2020 and hist[y].get("gross") is not None and hist[y].get("rev") and hist[y]["rev"] > 0]
    gm_info = None
    if len(gm_pts) >= 2:
        gm_ch = gm_pts[-1][1] - gm_pts[0][1]
        gm_info = dict(y0=gm_pts[0][0], y1=gm_pts[-1][0], gm0=r1(gm_pts[0][1]), gm1=r1(gm_pts[-1][1]), chg=r1(gm_ch))
    if cr.get("pricing"):
        out["pricing"] = dict(cr["pricing"], note=True, **({"gm": gm_info} if gm_info else {}))
    if cr.get("barriers"): out["barriers"] = dict(cr["barriers"], note=True)
    if cr.get("tech_risk"): out["tech_risk"] = dict(cr["tech_risk"], note=True)
    if cr.get("concentration"): out["concentration"] = dict(cr["concentration"], note=True)
    if cr.get("risks"): out["risks"] = dict(cr["risks"], note=True)

    # F39: 5-year Debt Maturities (ASC 470 from SEC XBRL / 10-K)
    sf = SEC_F.get(t) or {}
    mat = sf.get("debt_maturities")
    cash_b = ((raw.get("info") or {}).get("totalCash") or 0) / 1e9
    fcf_vals = [hist[y]["fcf"] for y in sorted(hist)[-3:] if hist[y].get("fcf") is not None]
    fcf_b = (st.mean(fcf_vals) / 1e3) if fcf_vals else None
    if mat:
        if mat.get("zero_debt"):
            out["debt_mat"] = dict(status="answered", zero_debt=True, due_5y_b=0.0, total_b=0.0,
                                   as_of=mat.get("as_of"), tone="good",
                                   answer="No financial debt due (leases only)",
                                   reading=mat.get("note") or f"Cash ${cash_b:.2f}B; no scheduled bond/loan maturities")
        else:
            n_yrs = sum(1 for i in range(1, 6) if mat.get(f"y{i}") is not None)
            has_full_5y = (n_yrs == 5) or bool(mat.get("note"))
            st_mat = "answered" if has_full_5y else "partly"
            d5 = mat.get("due_5y_b") or 0.0
            tot = mat.get("total_sched_b") or d5
            cov_5y = (cash_b + max(0.0, (fcf_b or 0.0) * 5)) / d5 if d5 > 0.01 else 99.0
            tone = "good" if d5 <= cash_b or cov_5y >= 2.5 else "caution" if cov_5y >= 1.2 else "bad"
            yrs_str = " · ".join(f"Y{i} ${mat[f'y{i}']:.2f}B" for i in range(1, 6) if mat.get(f"y{i}") is not None)
            after5 = mat.get("after5")
            if after5 is not None:
                yrs_str = (yrs_str + " · " if yrs_str else "") + f">5y ${after5:.2f}B"
            miss_note = f" ({n_yrs} of 5 years tagged in XBRL)" if not has_full_5y else ""
            out["debt_mat"] = dict(
                status=st_mat, zero_debt=False, as_of=mat.get("as_of"), n_years_tagged=n_yrs,
                due_5y_b=r1(d5, 2), total_b=r1(tot, 2),
                y1=mat.get("y1"), y2=mat.get("y2"), y3=mat.get("y3"), y4=mat.get("y4"), y5=mat.get("y5"), after5=after5,
                cash_b=r1(cash_b, 2), tone=tone,
                answer=(f"${d5:.2f}B due in 5 yrs" if has_full_5y else f"${d5:.2f}B tagged ({n_yrs}/5 yrs)") if d5 >= 0.01 else "$0 due in next 5 yrs",
                reading=(mat.get("note") or yrs_str) + miss_note + (f" (cash ${cash_b:.2f}B)" if cash_b else ""),
            )
    elif sf.get("debt_maturities_partial"):
        tot_d = ((raw.get("info") or {}).get("totalDebt") or 0) / 1e9
        out["debt_mat"] = dict(
            status="partly", zero_debt=False, total_b=r1(tot_d, 2), cash_b=r1(cash_b, 2), tone="caution",
            answer=f"${tot_d:.2f}B total debt (tranches known)",
            reading=f"{sf['debt_maturities_partial']} (cash ${cash_b:.2f}B; exact annual breakdown not tagged in XBRL)",
        )
    return out or None

def build_recession_fallback(t, hist, ins):
    """Run the 2008-09 / 2020 recession check on SEC 10-K history for stocks missing durability.stress.label."""
    if ((DUR.get(t) or {}).get("stress") or {}).get("label"):
        return None
    # Check 2008-09 (2009/2010 vs 2007/2008) and 2020 (2020 vs 2019) from hist
    pk = "ni" if ins else "op"
    episodes = []
    for name, base_ys, hit_ys in (("2008-09 recession", (2007, 2008), (2009, 2010)), ("2020 pandemic", (2019,), (2020,))):
        b_y = next((y for y in reversed(base_ys) if y in hist and hist[y].get("rev") and hist[y].get(pk) and hist[y][pk] > 0), None)
        if b_y is None: continue
        hits = []
        for hy in hit_ys:
            if hy in hist and hist[hy].get("rev") and hist[hy].get(pk) is not None:
                p_chg = hist[hy][pk] / hist[b_y][pk] - 1.0
                r_chg = hist[hy]["rev"] / hist[b_y]["rev"] - 1.0
                hits.append((hy, p_chg, r_chg))
        if hits:
            hy, p_chg, r_chg = min(hits, key=lambda x: x[1])
            one_off = r_chg > 0 and p_chg < -0.30
            episodes.append(dict(name=name, base_year=b_y, worst_year=hy, profit_chg=r1(p_chg), rev_chg=r1(r_chg), one_off=one_off))
    if episodes:
        usable = [e for e in episodes if not e["one_off"]] or episodes
        worst = min(usable, key=lambda e: e["profit_chg"])
        pc = worst["profit_chg"]
        lbl = "durable" if pc > -0.25 else "cyclical" if pc <= -0.50 else "somewhat cyclical"
        tone = {"durable": "good", "somewhat cyclical": "caution", "cyclical": "bad"}[lbl]
        return dict(status="answered", label=lbl, tone=tone, worst=worst, episodes=episodes, source="10-K SEC XBRL")
    # Fallback for young IPOs with no 2020 10-K: use debt_stress sector estimate if present (marked partly/estimate)
    ds = DS.get(t) or {}
    if ds.get("episode"):
        op_chg = (ds["op_stressed_b"] / ds["op_now_b"] - 1.0) if ds.get("op_now_b") and ds["op_now_b"] > 0 and ds.get("op_stressed_b") is not None else None
        return dict(status="partly", estimate=True, label="sector estimate", tone="caution",
                    episode=ds["episode"], rev_chg=ds.get("rev"), op_chg=r1(op_chg), source="sector 2008-09 median estimate")
    return None

# ------------------------------------------------------------------ sector-module metrics (statements + KPIs + 10-K research)
def metric(key, t, raw, hist, ind_moat, rec_fb):
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
        # Fall back to SEC hist if snapshot_raw lacked that line (e.g. R&D or op income)
        if not vals:
            hk = {"gross": "gross", "op": "op", "fcf": "fcf", "rd": "rd", "sbc": "sbc", "capex": "capex"}.get(num_key)
            if hk:
                for y in sorted(hist)[-5:]:
                    n, r = hist[y].get(hk), hist[y].get("rev")
                    if n is not None and r and r > 0:
                        vals.append((str(y), abs(n) / r if num_key in ("capex", "sbc", "rd") else n / r))
        return vals
    def trend(vals, good_up=True):
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
        if len(ops) < 3:
            ops = [(f"{y}-12-31", hist[y]["op"]) for y in sorted(hist)[-5:] if hist[y].get("op") and hist[y].get("rev")]
        if len(ops) < 3: return None
        (d0, o0), (d1, o1) = ops[0], ops[-1]
        n = int(d1[:4]) - int(d0[:4])
        r0 = (inc.get(d0) or {}).get("rev") or (hist.get(int(d0[:4])) or {}).get("rev")
        r1v = (inc.get(d1) or {}).get("rev") or (hist.get(int(d1[:4])) or {}).get("rev")
        if o0 <= 0 or o1 <= 0 or n <= 0 or not r0 or not r1v: return None
        go, gs = (o1 / o0) ** (1 / n) - 1, (r1v / r0) ** (1 / n) - 1
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
        if s.get("label"):
            tone = {"durable": "good", "somewhat cyclical": "caution", "cyclical": "bad"}[s["label"]]
            rd = f"a repeat of the {b['episode']}: profit {b['op_change'] * 100:+.0f}%" if b else ""
            return dict(answer=s["label"], reading=rd, tone=tone)
        if rec_fb and rec_fb.get("status") == "answered":
            w = rec_fb["worst"]
            return dict(answer=rec_fb["label"], reading=f"{w['name']} ({w['worst_year']}): profit {w['profit_chg']*100:+.0f}% (10-K)", tone=rec_fb["tone"])
        return None
    if key == "incr_roic":
        x = RET.get(t) or {}
        v = x.get("inc_recent")
        if v is None:
            m = snap_metric(t, "Incremental ROIC")
            if m and m.get("value") not in (None, "", "not in free data", "–"):
                return dict(answer=str(m["value"]), reading="3-year incremental ROIC (snapshot)", tone="key")
            return None
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
        if sv:
            tot1 = sum(v[0] for v in sg.values())
            g = sv[0] / sv[1] - 1
            return dict(answer=f"Services {sv[0] / tot1 * 100:.0f}% of sales", reading=f"growing {g * 100:+.0f}% ({SEG[t]['period'].split(' vs')[0]})",
                        tone="good" if g > 0.05 else "key")
        return None
    if key == "mkt_share":
        sh = (ind_moat or {}).get("share")
        if not sh: return None
        return dict(answer=sh["verdict"], reading=f"3-yr sales {sh['co_cagr_3y']*100:+.1f}%/yr vs {sh['ind_cagr_3y']*100:+.1f}% industry median ({sh['peers']} peers)", tone=sh["tone"])
    if key == "debt_mat":
        dm = (ind_moat or {}).get("debt_mat")
        if not dm: return None
        return dict(answer=dm["answer"], reading=dm["reading"], tone=dm["tone"], status=dm["status"])
    return None

# Direct live KPI -> sector question mappings (auto-updated from quarterly filings in data/kpis.json).
# Only KPIs that directly answer the question are mapped; partial proxies are marked status="partly".
KPI_SECTOR_MAP = {
    "Payment volume growth": [
        "payments_volume_growth_constant", "gross_dollar_volume_growth", "billed_business_growth_fx_adjusted",
        "total_payment_volume_growth", "square_gross_payment_volume_growth", "processed_volume_growth",
    ],
    "Take rate holding up?": [
        "take_rate_net_revenue_processed_volume", "reserve_return_rate",
    ],
    "Credit losses and fee regulation": ["net_write_off_rate_principal"],
    "Occupancy": ["occupancy_rate_us_malls_and_outlets"],
    "Same-property income growth": ["domestic_property_noi_growth", "comparable_hotel_revpar_growth"],
    "Underwriting profit: combined ratio below 100%?": ["combined_ratio"],
    "Capital strength (risk-based capital, solvency ratios)": ["pmiers_sufficiency_ratio", "pmiers_excess_capital"],
    "Catastrophe exposure and reinsurance cover": ["reportable_catastrophes", "catastrophe_losses"],
    "Commodity prices behind today's earnings": ["realised_oil_price", "average_selling_price_per_ton", "average_realized_gold_price"],
    "Breakeven production cost": ["all_in_sustaining_cost_per_ounce"],
    "Production and reserves": [
        "production_boe_d_growth", "gross_ammonia_production_thousand_tons", "total_production_growth",
        "attributable_gold_production_thousand_oz",
    ],
    "Order backlog and book-to-bill": [
        "orders_and_book_to_bill", "remaining_performance_obligations", "backlog_growth", "backlog", "total_backlog",
    ],
    "Net revenue retention and churn": [
        "net_revenue_retention_company_range", "software_dollar_based_net_retention",
        "net_retention_rate", "net_dollar_expansion", "renewal_rate", "client_retention_asv_and_count",
    ],
    "How much revenue is recurring (subscriptions)?": [
        "annual_recurring_revenue", "ratings_transaction_vs_non_transaction_revenue",
    ],
    "Dependence on a few large customers": ["top_customer_concentration_10_k"],
    "Product concentration": ["top_2_drugs_share_of_revenue", "non_jakafi_share_of_revenue"],
    "When major patents expire": ["jakafi_patent_expiry_timing"],
    "Pipeline success and trial risk": ["pipeline_milestones_e_g_orforglipron"],
    "Growth from higher prices or more volume?": [
        "volume_mix_vs_price", "price_vs_volume_cases", "price_mix", "pricing_contribution",
        "average_unit_retail_growth", "transactions_growth_comparable", "smokeable_products_shipment_volume_growth",
    ],
    "Enrollment growth": ["total_enrollment_growth", "new_enrollment_growth"],
}

# Live KPIs that inform the question but only answer half of it (counted as "partly", never "answered")
KPI_PARTLY_IDS = {
    "renewal_rate",                               # gross domain renewal rate, not net revenue retention (VRSN)
    "smokeable_products_shipment_volume_growth",  # volume only, no price split (MO)
    "average_unit_retail_growth",                 # AUR price/mix only, no volume split (RL)
}

def _fmt_kpi_val(val, unit):
    if unit == "text":
        s = str(val)
        return s[:64] + ("…" if len(s) > 64 else "")
    v = float(val)
    if unit == "pct": return f"{v:.1f}%".replace(".0%", "%")
    if unit == "usd_b": return f"${v:.2f}B" if abs(v) < 10 else f"${v:.1f}B"
    if unit == "usd": return f"${v:,.0f}" if abs(v) >= 100 else f"${v:.2f}"
    if unit == "x": return f"{v:.2f}×"
    if abs(v) >= 1e9: return f"{v/1e9:.2f}B"
    if abs(v) >= 1e6: return f"{v/1e6:.1f}M"
    return f"{v:,.0f}"

def kpi_sector_answer(q, t, hist=None):
    """Answer a sector question directly from live quarterly filings in data/kpis.json (or live XBRL RPO)."""
    kd_map = {d["id"]: d for d in (KPI_DEFS.get(t) or {}).get("kpis", [])}
    kdata = KPIS.get(t) or {}
    cands = KPI_SECTOR_MAP.get(q) or []
    for kid in cands:
        pts = kdata.get(kid) or []
        if not pts: continue
        last = sorted(pts, key=lambda p: p["period"])[-1]
        d = kd_map.get(kid) or {"label": kid.replace("_", " "), "unit": "num", "better": "none"}
        unit, val = d.get("unit", "num"), last["value"]
        # Special formatting when a pair of KPIs answers the question together (e.g. KO/PG volume+price, AME book-to-bill+backlog)
        ans = _fmt_kpi_val(val, unit)
        lbl = d.get("label", kid)
        rd_extra = ""
        st_kpi = "partly" if kid in KPI_PARTLY_IDS else "answered"
        if kid == "combined_ratio":
            tone = "good" if float(val) < 95 else "caution" if float(val) < 100 else "bad"
            ans = f"{ans} combined ratio"
        elif kid == "non_jakafi_share_of_revenue":
            tone = "bad" if float(val) < 50 else "caution"
            ans = f"Jakafi {100 - float(val):.1f}% of rev"
        elif kid == "top_2_drugs_share_of_revenue":
            tone = "bad" if float(val) > 50 else "caution"
            ans = f"{ans} from top 2 drugs"
        elif kid == "top_customer_concentration_10_k":
            tone = "bad" if float(val) >= 15 else "caution"
            ans = f"Top customer {ans} of sales"
        elif kid == "occupancy_rate_us_malls_and_outlets":
            tone = "good" if float(val) >= 92 else "caution"
            ans = f"{ans} occupied"
        elif kid == "pmiers_sufficiency_ratio":
            tone = "good" if float(val) >= 130 else "caution"
            ans = f"{ans} PMIERs sufficiency"
        elif kid == "pmiers_excess_capital":
            tone = "good"
            ans = f"{ans} PMIERs excess capital"
        elif kid == "take_rate_net_revenue_processed_volume":
            tone = "key"
            ans = f"{float(val)*100:.1f} bps ({float(val):.2f}%)"
        elif kid == "renewal_rate":
            tone = "key"
            ans = f"{ans} domain renewal rate"
        elif kid == "gross_ammonia_production_thousand_tons":
            tone = "key"
            ans = f"{float(val):,.0f}k tons ammonia"
        elif kid == "attributable_gold_production_thousand_oz":
            tone = "key"
            ans = f"{float(val):,.0f}k oz gold"
        elif kid == "average_realized_gold_price":
            tone = "key"
            ans = f"${float(val):,.0f}/oz"
        elif kid == "all_in_sustaining_cost_per_ounce":
            tone = "key"
            ans = f"${float(val):,.0f}/oz AISC"
        elif kid == "realised_oil_price":
            tone = "key"
            ans = f"${float(val):.2f}/bbl"
        elif kid == "average_selling_price_per_ton":
            tone = "key"
            ans = f"${float(val):,.0f}/ton"
        elif kid == "smokeable_products_shipment_volume_growth":
            v = float(val)
            tone = "bad" if v < 0 else "good"
            ans = f"volume {v:+.1f}%"
        elif kid == "average_unit_retail_growth":
            v = float(val)
            tone = "good" if v > 0 else "bad"
            ans = f"AUR {v:+.1f}%".replace(".0%", "%")
        elif kid == "orders_and_book_to_bill":
            tone = "good" if float(val) >= 1.0 else "caution"
            ans = f"{ans} book-to-bill"
            if kdata.get("backlog"):
                bl = sorted(kdata["backlog"], key=lambda p: p["period"])[-1]
                rd_extra = f"; backlog ${float(bl['value']):.2f}B"
        elif kid == "price_mix" and kdata.get("unit_case_volume_growth"):
            vol = sorted(kdata["unit_case_volume_growth"], key=lambda p: p["period"])[-1]
            ans = f"vol {float(vol['value']):+.0f}%, price/mix {float(val):+.0f}%"
            tone = "good" if float(vol["value"]) > 0 else "caution"
        elif kid == "pricing_contribution" and kdata.get("volume_growth"):
            vol = sorted(kdata["volume_growth"], key=lambda p: p["period"])[-1]
            ans = f"vol {float(vol['value']):+.1f}%, price {float(val):+.1f}%"
            tone = "good" if float(vol["value"]) > 0 else "caution"
        elif kid == "transactions_growth_comparable" and kdata.get("comparable_restaurant_sales_growth"):
            cs = sorted(kdata["comparable_restaurant_sales_growth"], key=lambda p: p["period"])[-1]
            ans = f"comps {float(cs['value']):+.1f}% (traffic {float(val):+.1f}%)"
            tone = "good" if float(val) > 0 else "caution"
        elif unit == "pct" and ("growth" in kid or "noi" in kid or "revpar" in kid):
            v = float(val)
            ans = f"{v:+.1f}%".replace(".0%", "%")
            tone = "good" if v > 3 else "bad" if v < 0 else "key"
        elif unit == "usd_b":
            ans = f"{ans} ({lbl.split('(')[0].strip()})"
            tone = "key"
        elif unit == "text":
            tone = "key"
        else:
            better = d.get("better", "none")
            tone = "good" if better == "up" and isinstance(val, (int, float)) and val > 0 else "key"
        rd = f"{lbl}: {last['label']} ({last['period']}){rd_extra}"
        return dict(answer=ans, reading=rd, tone=tone, status=st_kpi, url=last.get("source"), as_of=last["period"])
    # Live XBRL RPO fallback for Industrials backlog (skip tiny ASC 606 >1y practical-expedient footnotes <15% of sales)
    if q == "Order backlog and book-to-bill":
        rpo = (SEC_F.get(t) or {}).get("rpo")
        if rpo and rpo.get("val_b"):
            rev_b = None
            if hist:
                ry = [y for y in sorted(hist) if hist[y].get("rev") and hist[y]["rev"] > 0]
                if ry:
                    rev_b = hist[ry[-1]]["rev"] / 1e3
            if rev_b is None or rpo["val_b"] >= 0.15 * rev_b:
                return dict(answer=f"${rpo['val_b']:.2f}B RPO", reading=f"SEC 10-K remaining performance obligations as of {rpo['as_of']}", tone="key", status="answered", as_of=rpo["as_of"])
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

def mc_regime_hold10(a, px):
    """Interpolate each regime's median 10-yr annual return at today's price from assets.json mc.irr.hold10."""
    I = ((a.get("mc") or {}).get("irr") or {})
    if not I or not I.get("hold10") or not px or not I.get("fair_value"):
        return None
    g = I["price_multiples"]
    m = px / I["fair_value"]
    L = math.log(max(m, 1e-6))
    j = 0
    while j < len(g) - 2 and math.log(g[j + 1]) < L:
        j += 1
    t_ = min(1.0, max(0.0, (L - math.log(g[j])) / (math.log(g[j + 1]) - math.log(g[j]))))
    out = {}
    for k in ("bear", "base", "bull"):
        qa, qb = I["hold10"][k][j], I["hold10"][k][j + 1]
        # index 50 is the 50th percentile (median) out of 101 quantiles (0..100)
        mid = len(qa) // 2
        out[k] = r1(qa[mid] + (qb[mid] - qa[mid]) * t_)
    return out

def assumes_ins(ns, t, a, price, bd):
    """Underwriter (book value and ROE model): long-run ROE & year-1 book growth needed, implied EPS growth,
    scenario 10-yr returns vs bonds, and return split (book/payout vs P/B re-rating)."""
    s = dict(ns["INSURERS"][t]); r = ns["req_return"](t)
    mo = dict(ns["moat_of"](t), r_req=r)
    B = dict(s["scen"]["base"])
    V = lambda g1, m: ns["ri_value"](s["bv"], s["roe0"], g1, B["g10"], m, r, s["extra"], s["shares"], mo=mo)
    solve = ns["solve"]
    bv_ps = s["bv"] / s["shares"]
    pb = price / bv_ps
    out = dict(method="excess_roe", price=price, r=r, base_g1=B["g1"], base_m=B["m"], bv_ps=r1(bv_ps, 2), pb=r1(pb, 3))
    lo, hi = -0.5, 1.5
    out["g1_needed"] = r1(solve(lambda g: V(g, B["m"]) - price, lo, hi)) if (V(lo, B["m"]) - price) * (V(hi, B["m"]) - price) < 0 else None
    out["m_needed"] = r1(solve(lambda m: V(B["g1"], m) - price, -0.2, 0.9)) if (V(B["g1"], -0.2) - price) * (V(B["g1"], 0.9) - price) < 0 else None
    g = out["g1_needed"]
    if g is not None and g > B["g10"]:
        out["half_g1"] = r1(g / 2)
        out["half_value"] = r1(V(g / 2, B["m"]), 2)
    out["cap_needed"] = ns["ri_cap"](price, s, B, r, mo)
    # M1: Implied earnings growth from the model's own forecast at the price-implied growth (or ROE)
    fc_ins = (a.get("forecast") or {}).get("base") or {}
    if out["g1_needed"] is not None:
        det = ns["ri_value"](s["bv"], s["roe0"], out["g1_needed"], B["g10"], B["m"], r, s["extra"], s["shares"], mo=mo, detail=True)
        rws_i = det["rows"]
        if len(rws_i) >= 10 and rws_i[0]["ni"] > 0 and rws_i[9]["ni"] > 0:
            out["eps_g_implied"] = r1(cagr(rws_i[9]["ni"], rws_i[0]["ni"], 9))
            out["eps_g_span"] = "y1–y10 NI"
            nis_b = fc_ins.get("ni") or []
            if len(nis_b) >= 10 and nis_b[0] > 0 and nis_b[9] > 0:
                out["eps_g_base"] = r1(cagr(nis_b[9], nis_b[0], 9))
    elif out["m_needed"] is not None:
        det = ns["ri_value"](s["bv"], s["roe0"], B["g1"], B["g10"], out["m_needed"], r, s["extra"], s["shares"], mo=mo, detail=True)
        rws_i = det["rows"]
        if len(rws_i) >= 10 and rws_i[0]["ni"] > 0 and rws_i[9]["ni"] > 0:
            out["eps_g_implied"] = r1(cagr(rws_i[9]["ni"], rws_i[0]["ni"], 9))
            out["eps_g_span"] = "y1–y10 NI"
            nis_b = fc_ins.get("ni") or []
            if len(nis_b) >= 10 and nis_b[0] > 0 and nis_b[9] > 0:
                out["eps_g_base"] = r1(cagr(nis_b[9], nis_b[0], 9))
    # M7 & M8: Bear/Base/Bull 10-yr returns vs 10-yr Treasury
    h10 = mc_regime_hold10(a, price)
    t10 = (bd.get("t10_now") / 100.0) if bd and bd.get("t10_now") is not None else None
    if h10:
        out["scenarios_ret"] = {
            k: dict(val=a.get(k), ret10=h10[k], vs_t10=r1(h10[k] - t10) if t10 is not None else None)
            for k in ("bear", "base", "bull")
        }
        out["t10"] = r1(t10)
    # M9: Return decomposition (business growth + payouts vs P/B re-rating) over 10 yrs (base case)
    # Exact Year-10 equity value = PV of post-year-10 payouts + PV of terminal value, brought forward 10 yrs at r
    fc = fc_ins
    rws = fc.get("rows") or []
    if len(rws) >= 10 and pb > 0 and s["shares"] > 0:
        bv10 = rws[9]["rev"]
        rem_pv0 = sum(rw["pv"] for rw in rws[10:]) + (fc.get("pv_tv") or 0)
        eq10 = rem_pv0 * ((1.0 + r) ** 10)
        exit_pb = (eq10 / bv10) if bv10 > 0 and eq10 > 0 else None
        if exit_pb and exit_pb > 0:
            bv_g = cagr(bv10, s["bv"], 10)
            rerate = (exit_pb / pb) ** (1 / 10.0) - 1.0
            pay_y = st.mean(rw["fcf"] for rw in rws[:10]) / (price * s["shares"])
            tot = h10["base"] if h10 else ((bv_g or 0) + pay_y + rerate)
            out["ret_decomp"] = dict(
                total=r1(tot), business=r1(tot - rerate), rerate=r1(rerate),
                mult_label="P/B", mult_now=r1(pb, 2), mult_exit=r1(exit_pb, 2),
            )
    return out

def assumes(ns, t, a, price, bd):
    if t in ns.get("INSURERS", {}):
        return assumes_ins(ns, t, a, price, bd) if price else None
    s = ns["STOCKS"].get(t)
    if not s or not price: return None
    s = dict(s); s["r"] = ns["req_return"](t)
    mo = dict(ns["moat_of"](t), r_req=s["r"]); sg = ns["segments_of"](t)
    su = ns["stock_setup"](t, s)                    # same cash-flow separation as the model
    D = lambda *x, **kw: ns["dcf"](*x, mo=mo, sg=sg, **su["kw"], **kw)
    add, m0 = su["add"], su["m0"]
    W = (lambda re: ns["wacc_of"](t, s, re)) if ns["DCF_METHOD"] == "fcff_wacc" else (lambda re: re)
    w = W(s["r"]); nc = su["nc"]
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
    out["cap_needed"] = ns["implied_cap"](price, s["rev"], m0, B["g1"], B["m"], w, nc, s["shares"], **su["kw"])
    # M1: Implied cash-flow growth from the model's own forecast at g1_needed (Year 1 -> Year 10, or first positive year -> Year 10)
    rws_b = ((a.get("forecast") or {}).get("base") or {}).get("rows") or []
    if g is not None:
        det = D(s["rev"], m0, g, B["g10"], B["m"], w, nc, s["shares"], detail=True)
        rws_i = det["rows"]
        if len(rws_i) >= 10 and rws_i[9]["fcf"] > 0:
            i0 = next((i for i in range(6) if rws_i[i]["fcf"] > 0), None)
            if i0 is not None and 9 - i0 >= 4:
                out["eps_g_implied"] = r1(cagr(rws_i[9]["fcf"], rws_i[i0]["fcf"], 9 - i0))
                out["eps_g_span"] = f"y{i0+1}–y10 FCF"
                if len(rws_b) >= 10 and rws_b[i0]["fcf"] > 0 and rws_b[9]["fcf"] > 0:
                    out["eps_g_base"] = r1(cagr(rws_b[9]["fcf"], rws_b[i0]["fcf"], 9 - i0))
            elif rws_i[0]["rev"] > 0 and rws_i[9]["rev"] > 0:
                out["eps_g_implied"] = r1(cagr(rws_i[9]["rev"], rws_i[0]["rev"], 9))
                out["eps_g_span"] = "y1–y10 sales"
                if len(rws_b) >= 10 and rws_b[0]["rev"] > 0 and rws_b[9]["rev"] > 0:
                    out["eps_g_base"] = r1(cagr(rws_b[9]["rev"], rws_b[0]["rev"], 9))
    # M7 & M8: Bear / Base / Bull 10-yr expected returns vs 10-yr Treasury
    h10 = mc_regime_hold10(a, price)
    t10 = (bd.get("t10_now") / 100.0) if bd and bd.get("t10_now") is not None else None
    if h10:
        out["scenarios_ret"] = {
            k: dict(val=a.get(k), ret10=h10[k], vs_t10=r1(h10[k] - t10) if t10 is not None else None)
            for k in ("bear", "base", "bull")
        }
        out["t10"] = r1(t10)
    # M9: Return from business growth (+ cash yield) vs multiple re-rating over 10-year base hold
    fc = (a.get("forecast") or {}).get("base") or {}
    rws = fc.get("rows") or []
    if len(rws) >= 10 and s["shares"] > 0:
        ev_now = price * s["shares"] - nc
        fcf0 = max(s["rev"] * m0, rws[0]["fcf"])
        fcf10 = rws[9]["fcf"]
        # Implied operating value at year 10 (PV of cash flows after yr 10 discounted to yr 10)
        # In base forecast, sum(pv_t for t>10) + pv_tv, brought forward 10 yrs at w
        rem_pv0 = sum(rw["pv"] for rw in rws[10:]) + (fc.get("pv_tv") or 0)
        ev10 = rem_pv0 * ((1.0 + w) ** 10)
        if ev_now > 0 and fcf0 > 0 and fcf10 > 0 and ev10 > 0:
            m_now = ev_now / fcf0
            m_exit = ev10 / fcf10
            rerate = (m_exit / m_now) ** (1 / 10.0) - 1.0
            tot = h10["base"] if h10 else ((cagr(fcf10, fcf0, 10) or 0) + fcf0 / ev_now + rerate)
            out["ret_decomp"] = dict(
                total=r1(tot), business=r1(tot - rerate), rerate=r1(rerate),
                mult_label="EV/FCF", mult_now=r1(m_now, 1), mult_exit=r1(m_exit, 1),
            )
        elif ev_now > 0 and fcf10 > 0 and ev10 > 0:
            eps_live = (((SNAP.get(t) or {}).get("valuation") or {}).get("live") or {}).get("trailing_eps") or ((RAW.get(t) or {}).get("info") or {}).get("trailingEps")
            if eps_live and eps_live > 0:
                m_now = price / eps_live
                m_exit = ev10 / fcf10
                rerate = (m_exit / m_now) ** (1 / 10.0) - 1.0
                tot = h10["base"] if h10 else rerate
                out["ret_decomp"] = dict(
                    total=r1(tot), business=r1(tot - rerate), rerate=r1(rerate),
                    mult_label="P/E→EV/FCF", mult_now=r1(m_now, 1), mult_exit=r1(m_exit, 1),
                )
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
    med = {k: round(st.median(v), 1) for k, v in by.items() if len(v) >= 5}
    # Map custom peer group name "Fee-based financials" to Financial Services (fixes 12 stocks for M6!)
    if "Financial Services" in med:
        med["Fee-based financials"] = med["Financial Services"]
    return med, pathlib.Path(files[-1]).name

def main():
    offline = "--offline" in sys.argv
    BM = benchmarks(offline)
    SPE, spe_src = sector_median_pe()
    BY_IND, BY_SEC, SMETA = load_industry_benchmarks()
    ns = load_model()
    tips_m = (BOND.get("monthly") or {}).get("DFII10") or {}
    tips = (max(tips_m), tips_m[max(tips_m)]) if tips_m else None
    today = datetime.date.today()
    stocks = {}
    for t, a in sorted(ASSETS.items()):
        raw = RAW.get(t) or {}
        px = (PRICES.get(t) or {}).get("price") or a.get("price")
        now_ym = (PRICES.get(t) or {}).get("time", today.isoformat())[:7]
        ins = t in ns.get("INSURERS", {})
        hist = build_annual_history(t, raw)
        x = dict(currency=raw.get("currency") or "USD")

        # business: latest fiscal year vs the one before
        inc, cfs = years(raw, "inc"), dict(years(raw, "cfs"))
        fy = [(d, v) for d, v in inc if v.get("rev")]
        if len(fy) >= 2:
            (d0, v0), (d1, v1) = fy[-2], fy[-1]
            f0, f1 = (cfs.get(d0) or {}).get("fcf"), (cfs.get(d1) or {}).get("fcf")
            # Fill missing EPS from split-adjusted hist if raw missed it (e.g. EPAC, RMD)
            y0i = int(d0[:4]) if d0[5:7] > "03" else int(d0[:4]) - 1
            y1i = int(d1[:4]) if d1[5:7] > "03" else int(d1[:4]) - 1
            e0 = v0.get("eps") if v0.get("eps") is not None else (hist.get(y0i) or {}).get("eps")
            e1 = v1.get("eps") if v1.get("eps") is not None else (hist.get(y1i) or {}).get("eps")
            x["business"] = dict(fy=d1[:10], prev=d0[:10], sales=r1(pct(v1["rev"], v0["rev"])),
                                 eps=r1(pct(e1, e0)) if e0 and e0 > 0 and e1 is not None else None,
                                 fcf=r1(pct(f1, f0)) if f0 and f0 > 0 and f1 is not None else None)
            # split of the price move over that fiscal year (fallback to 2-yr positive-EPS window if prior yr had GAAP loss)
            p0, p1 = month_close(raw, d0[:7]), month_close(raw, d1[:7])
            if p0 and p1 and e0 and e1 and e0 > 0 and e1 > 0:
                x["split"] = dict(fy=d1[:10], price=r1(p1 / p0 - 1), eps=r1(e1 / e0 - 1), pe0=round(p0 / e0, 1), pe1=round(p1 / e1, 1),
                                  pe=r1((p1 / e1) / (p0 / e0) - 1))
            elif len(fy) >= 3 and p1 and e1 and e1 > 0:
                d_prev, v_prev = fy[-3]
                ypi = int(d_prev[:4]) if d_prev[5:7] > "03" else int(d_prev[:4]) - 1
                ep = v_prev.get("eps") if v_prev.get("eps") is not None else (hist.get(ypi) or {}).get("eps")
                pp = month_close(raw, d_prev[:7])
                if pp and ep and ep > 0:
                    x["split"] = dict(fy=d1[:10], prev=d_prev[:10], years=2, price=r1(p1 / pp - 1), eps=r1(e1 / ep - 1),
                                      pe0=round(pp / ep, 1), pe1=round(p1 / e1, 1), pe=r1((p1 / e1) / (pp / ep) - 1))

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

        # bonds (spread 1 inputs + TIPS)
        bd = (DUR.get(t) or {}).get("bond")
        if bd:
            x["bonds"] = dict(ey=bd.get("ey_now"), aaa=bd.get("aaa_now"), t10=bd.get("t10_now"), month=bd.get("yields_month"),
                              median_gap=bd.get("gap_median"), tips=tips[1] if tips else None, tips_month=tips[0] if tips else None)

        # NEW research framework blocks
        gr = build_growth(t, a, raw, hist, ins)
        if gr: x["growth"] = gr
        an = build_analysts(t)
        if an: x["analysts"] = an
        ca = build_cash_alloc(t, a, raw, hist, ins, gr)
        if ca: x["cash_alloc"] = ca
        im = build_industry_moat(t, a, raw, hist, BY_IND, BY_SEC, SMETA)
        if im: x["industry_moat"] = im
        rfb = build_recession_fallback(t, hist, ins)
        if rfb: x["recession"] = rfb

        # what the price assumes
        try:
            asm = assumes(ns, t, a, px, bd)
        except Exception as e:
            print(f"{t}: assumes failed ({e})"); asm = None
        V = (SNAP.get(t) or {}).get("valuation") or {}
        eps_ttm = ((V.get("live") or {}).get("trailing_eps")) or ((raw.get("info") or {}).get("trailingEps"))
        if not eps_ttm or eps_ttm <= 0:
            # Fallback to latest positive annual EPS from hist (fixes FISV!)
            last_ys = sorted(hist)
            if last_ys and (hist[last_ys[-1]].get("eps") or 0) > 0:
                eps_ttm = hist[last_ys[-1]]["eps"]
        sname = (V.get("sector_pct") or {}).get("name") or (YH_F.get(t) or {}).get("sector") or (SMAP.get("stocks") or {}).get(t)
        own = [p for _, p in (V.get("history") or {}).get("pe", []) if p and p > 0]
        if asm is not None:
            asm["eps_ttm"] = r1(eps_ttm, 2) if eps_ttm is not None else None
            if eps_ttm and eps_ttm > 0 and sname in SPE:
                asm["pe_sector"] = SPE[sname]; asm["sector"] = sname
            if eps_ttm and eps_ttm > 0 and own:
                asm["pe_own"] = round(st.median(own), 1); asm["pe_own_years"] = f"{(V['history']['pe'][0][0])}–{V['history']['pe'][-1][0]}"
            x["assumes"] = asm

        # sector module (3-tier: live statements -> live data/kpis.json & XBRL -> dated company_research note [partly] -> unknown)
        mod = MODULE_OF.get(t)
        sq = []
        cr_sec = (CR.get(t) or {}).get("sector") or {}
        if mod:
            for q, key in mod["questions"]:
                ans = metric(key, t, raw, hist, im, rfb) if key else None
                if ans is not None:
                    ans.setdefault("status", "answered")
                else:
                    ans = kpi_sector_answer(q, t, hist)
                if ans is None and q in cr_sec:
                    ans = dict(cr_sec[q], status="partly", note=True)
                sq.append(dict(q=q, **(ans or {"answer": None, "status": "unknown"})))
            x["sector"] = dict(module=mod["name"], questions=sq)

        # Dynamic, honest per-stock coverage evaluation for all 64 fixed questions!
        has_snap = t in SNAP
        has_moat = t in MS
        has_ret = t in RET
        has_mc = bool(a.get("mc"))
        has_bonds = "bonds" in x
        has_dur = t in DURN
        has_mkt = "market" in x
        has_split = "split" in x
        has_bench = bool((x.get("market") or {}).get("spy") and (x.get("market") or {}).get("sector"))
        has_asm = bool(asm and (asm.get("g1_needed") is not None or (asm.get("method") == "excess_roe" and asm.get("m_needed") is not None)))
        has_stress = bool(((DUR.get(t) or {}).get("stress") or {}).get("label")) or (rfb is not None and rfb.get("status") == "answered")
        part_stress = (not has_stress) and (rfb is not None and rfb.get("status") == "partly")

        def status_of(qid):
            if ins and qid in NA_INSURER: return "na"
            if qid in ("A1", "A2", "A3", "A4", "A5", "A6"): return "answered" if has_bonds else "unknown"
            if qid == "A7": return "answered" if has_mc else "unknown"
            if qid == "B8":
                if gr and all(gr.get(k) is not None for k in ("eps_3y", "eps_5y", "eps_10y")): return "answered"
                if gr and any(gr.get(k) is not None for k in ("eps_3y", "eps_5y")): return "partly"
                return "unknown"
            if qid == "B9": return "answered" if (gr and gr.get("decomp")) else "unknown"
            if qid == "B10":
                if gr and gr.get("decomp"): return "answered"
                return "partly" if has_snap else "unknown"
            if qid == "B11":
                ex = (gr or {}).get("expected") or {}
                if (ex.get("analyst_1y") is not None or ex.get("analyst_0y") is not None) and (ex.get("model_cf_5y") is not None or ex.get("model_rev_5y") is not None):
                    return "answered"
                return "partly" if ex else "unknown"
            if qid == "B12": return "answered" if (an and an.get("history")) else "unknown"
            if qid == "B13": return "answered" if (gr and gr.get("trajectory")) else ("partly" if has_snap else "unknown")
            if qid == "B14": return "answered" if (gr and gr.get("decomp")) else ("partly" if has_snap else "unknown")
            # Qualitative questions backed by dated research notes in company_research.json count strictly as "partly"
            if qid == "B15": return "partly" if (gr and gr.get("demand")) else "unknown"
            if qid == "C16": return "partly" if ((im and im.get("pricing")) or has_snap) else "unknown"
            if qid == "C17": return "partly" if (im and im.get("pricing")) else "unknown"
            if qid == "C18": return "answered" if has_moat else "unknown"
            if qid == "C19": return "partly" if (has_moat or (im and im.get("barriers"))) else "unknown"
            if qid == "C20": return "answered" if (im and im.get("share")) else "unknown"
            if qid == "C21": return "answered" if (im and im.get("industry")) else "unknown"
            if qid == "C22": return "partly" if (has_moat or (im and im.get("tech_risk"))) else "unknown"
            if qid == "C23": return "answered"
            if qid in ("D24", "D25"): return "answered" if has_snap else "unknown"
            if qid == "D26": return "answered" if (ca and ca.get("wc")) else "unknown"
            if qid in ("D27", "D28"): return "answered" if (ca and ca.get("capex_split")) else ("partly" if has_snap else "unknown")
            if qid == "D29": return "answered" if (ca and ca.get("cap_intensity")) else ("partly" if has_snap else "unknown")
            if qid == "D30": return "answered" if (ca and ca.get("self_fund")) else ("partly" if has_snap else "unknown")
            if qid in ("E31", "E32", "E35"): return "answered" if has_snap else "unknown"
            if qid == "E33": return "partly" if (ca and ca.get("buyback_val")) else "unknown"
            if qid == "E34": return "answered" if has_ret else "unknown"
            if qid == "E36": return "answered" if (ca and ca.get("per_share")) else "unknown"
            if qid == "F37": return "answered" if has_snap else "unknown"
            if qid in ("F38", "F43"): return "answered" if has_stress else ("partly" if part_stress else "unknown")
            if qid == "F39":
                dm = (im or {}).get("debt_mat")
                return dm["status"] if dm else "unknown"
            if qid == "F40": return "answered" if has_snap else "unknown"
            if qid == "F41": return "partly" if (im and im.get("concentration")) else "unknown"
            if qid == "F42": return "partly" if (has_moat or (im and im.get("risks"))) else "unknown"
            if qid == "G44": return "answered" if has_mkt else "unknown"
            if qid in ("G45", "G47"): return "answered" if has_split else "unknown"
            if qid == "G46": return "answered" if has_bench else ("partly" if has_mkt else "unknown")
            if qid == "G48": return "answered" if (an and an.get("revisions")) else "unknown"
            if qid == "G49": return "answered"
            if qid == "G50": return "answered" if (asm and asm.get("pe_own")) else "unknown"
            if qid == "M1": return "answered" if (asm and asm.get("eps_g_implied") is not None) else ("partly" if has_asm else "unknown")
            if qid in ("M2", "M3", "M5"): return "answered" if has_asm else "unknown"
            if qid in ("M4", "M10"): return "answered"
            if qid == "M6": return "answered" if (asm and asm.get("pe_sector")) else "unknown"
            if qid == "M7": return "answered" if (asm and asm.get("scenarios_ret")) else "partly"
            if qid == "M8": return "answered" if (asm and asm.get("scenarios_ret") and asm.get("t10") is not None) else ("partly" if has_mc else "unknown")
            if qid == "M9": return "answered" if (asm and asm.get("ret_decomp")) else "unknown"
            if qid in ("T1", "T2", "T3", "T4"): return "answered" if has_dur else "unknown"
            return "unknown"

        fixed = [[qid, status_of(qid)] for qid, _ in Q]
        n_ans = sum(1 for _, s in fixed if s == "answered") + sum(1 for q in sq if q.get("status") == "answered")
        n_part = sum(1 for _, s in fixed if s == "partly") + sum(1 for q in sq if q.get("status") == "partly")
        n_unk = sum(1 for _, s in fixed if s == "unknown") + sum(1 for q in sq if q.get("status") == "unknown")
        n_na = sum(1 for _, s in fixed if s == "na")
        x["coverage"] = dict(total=len(fixed) + len(sq) - n_na, answered=n_ans, partly=n_part, unknown=n_unk, fixed=fixed, **({"na": n_na} if n_na else {}))
        stocks[t] = x

    doc = {"_about": __doc__.strip().split("\n\n")[0], "built": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "analysts_as_of": (RF.get("yahoo_fetched") or RF.get("fetched") or "")[:10] or None,
           "questions": {q[0]: q[1] for q in Q}, "sector_pe_source": spe_src, "benchmarks": BM, "stocks": stocks}
    if {k: v for k, v in OLD.items() if k != "built"} == json.loads(json.dumps({k: v for k, v in doc.items() if k != "built"}, default=float)):
        print("framework.json: no change"); return                   # keeps the daily price job a no-op outside market hours
    json.dump(doc, open(OUT, "w"), indent=None, separators=(",", ":"), default=float)
    c = [s["coverage"] for s in stocks.values()]
    tot = sum(x["total"] for x in c)
    ans = sum(x["answered"] for x in c)
    part = sum(x["partly"] for x in c)
    unk = sum(x["unknown"] for x in c)
    print(f"framework.json: {len(stocks)} stocks; answered {ans}/{tot} ({ans/max(1,tot)*100:.1f}%), "
          f"partly {part} ({part/max(1,tot)*100:.1f}%), unknown {unk} ({unk/max(1,tot)*100:.1f}%)")
    miss = [t for t in ASSETS if t not in MODULE_OF]
    if miss: print("no sector module:", " ".join(miss))

if __name__ == "__main__":
    main()
