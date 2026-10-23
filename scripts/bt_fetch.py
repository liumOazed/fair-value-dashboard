#!/usr/bin/env python3
"""Backtest data (P3), run on GitHub Actions (SEC, Wikipedia and Yahoo are reachable there).

Writes three compact files to data/backtest/ so the backtest itself can run anywhere:
  membership.json   S&P 500 members on each quarter-end since 2010 (fja05680/sp500 historical components dataset)
  facts.json.gz     per company: ANNUAL (10-K, fiscal-year) figures AS FIRST REPORTED, each with its filing date
                    (point in time: later restatements are ignored, a figure only exists after it was filed)
  prices.json.gz    per ticker: monthly close, dividend-adjusted close and split history (Yahoo), plus SPY and RSP
Known limit (survivorship): companies that were acquired, went bankrupt or changed ticker have no prices or CIK here,
so they drop out. The backtest therefore compares rules WITHIN the same universe; it cannot judge absolute returns.
Run it on a HOME computer: the SEC blocks cloud servers such as GitHub Actions (HTTP 403).
Needs Python 3.9+ and pandas. It can be stopped and re-run: finished companies are cached in .bt_cache/.
Usage: SEC_CONTACT=you@example.com python scripts/bt_fetch.py [--limit N]
"""
import argparse, datetime, gzip, io, json, os, pathlib, sys, time, urllib.request
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/backtest"
# SEC fair-access policy: identify with a real contact. Set SEC_CONTACT=you@example.com (the default identity is blocked).
UA_SEC = {"User-Agent": f"fair-value-dashboard {os.environ.get('SEC_CONTACT', 'liumOazed@users.noreply.github.com')}", "Accept-Encoding": "gzip"}
UA_WEB = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
CACHE = ROOT / ".bt_cache"

def get(url, headers, tries=3):
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=40)
            b = r.read()
            if r.headers.get("Content-Encoding") == "gzip": b = gzip.decompress(b)
            return b
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(2 * (i + 1))

# ---------------------------------------------------------------- membership
MEMBERS_URL = "https://raw.githubusercontent.com/fja05680/sp500/master/S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv"

def membership():
    """S&P 500 members on each quarter-end since 2010, from the public fja05680/sp500 dataset (dated snapshots of
    the index since 1996, maintained from Wikipedia's change log)."""
    h = pd.read_csv(io.BytesIO(get(MEMBERS_URL, UA_WEB)))
    h["date"] = pd.to_datetime(h["date"]); h = h.sort_values("date")
    dates = pd.date_range("2010-03-31", datetime.date.today(), freq="QE")
    members = {}
    for d in dates:
        row = h[h.date <= d].iloc[-1]
        members[d.strftime("%Y-%m-%d")] = sorted(t.strip().replace(".", "-") for t in row.tickers.split(",") if t.strip())
    cur = members[max(members)]
    print(f"membership source: {len(h)} snapshots, latest {h.date.max().date()}")
    return members, cur

# ---------------------------------------------------------------- SEC facts
DUR = {  # annual duration concepts, in order of preference
 "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueGoodsNet"],
 "net_income": ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
 "gross_profit": ["GrossProfit"],
 "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"],
 "operating_income": ["OperatingIncomeLoss"],
 "dna": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "DepreciationAmortizationAndAccretionNet", "Depreciation"],
 "ocf": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
 "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
 "interest": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt", "InterestPaidNet"],
 "tax": ["IncomeTaxExpenseBenefit"],
 "pretax": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
 "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted", "EarningsPerShareBasic"],
 "dil_shares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
}
INST = {  # balance-sheet (instant) concepts
 "assets": ["Assets"], "cur_liab": ["LiabilitiesCurrent"],
 "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "Cash"],
 "st_inv": ["ShortTermInvestments", "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"],
 "ltd_noncur": ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"],
 "ltd_cur": ["LongTermDebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent", "DebtCurrent"],
 "ltd_total": ["LongTermDebt"],
 "st_debt": ["ShortTermBorrowings", "CommercialPaper"],
 "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
}

def annual_series(facts, names, instant):
    """First-reported fiscal-year values: {period_end: [value, filed]} from 10-K filings only."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for n in names:
        if n not in gaap: continue
        units = gaap[n]["units"]
        u = units.get("USD") or units.get("USD/shares") or units.get("shares") or next(iter(units.values()))
        best = {}
        for x in u:
            if not str(x.get("form", "")).startswith("10-K"): continue
            if not instant:
                if "start" not in x: continue
                days = (datetime.date.fromisoformat(x["end"]) - datetime.date.fromisoformat(x["start"])).days
                if not 340 <= days <= 380: continue
            end, filed = x["end"], x["filed"]
            if end not in best or filed < best[end][1]:        # keep the value AS FIRST REPORTED
                best[end] = [x["val"], filed]
        if instant:                                           # keep fiscal-year-end balances only (from 10-K)
            best = {e: v for e, v in best.items()}
        if len(best) >= 2:
            return {e: best[e] for e in sorted(best)}
    return {}

def company_facts(cik):
    f = CACHE / f"cf_{cik}.json"
    if f.exists(): return json.loads(f.read_text())
    b = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", UA_SEC)
    d = json.loads(b)
    keep = {k: annual_series(d, v, False) for k, v in DUR.items()}
    keep.update({k: annual_series(d, v, True) for k, v in INST.items()})
    f.write_text(json.dumps(keep))
    return keep

# ---------------------------------------------------------------- prices
def prices(t):
    f = CACHE / f"px_{t}.json"
    if f.exists(): return json.loads(f.read_text())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=max&interval=1mo&events=div,split"
    r = json.loads(get(url, UA_WEB))["chart"]["result"][0]
    ts = r.get("timestamp") or []
    q = r["indicators"]["quote"][0]["close"]; adj = r["indicators"].get("adjclose", [{}])[0].get("adjclose", q)
    out = dict(d=[datetime.datetime.fromtimestamp(x, datetime.timezone.utc).strftime("%Y-%m-%d") for x in ts], close=q, adj=adj,
               splits=[[datetime.datetime.fromtimestamp(int(k), datetime.timezone.utc).strftime("%Y-%m-%d"), v["numerator"] / v["denominator"]]
                       for k, v in (r.get("events", {}).get("splits") or {}).items()])
    f.write_text(json.dumps(out))
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=0); a = ap.parse_args()
    CACHE.mkdir(exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    mem, cur = membership()
    universe = sorted({t for v in mem.values() for t in v})
    print(f"membership: {len(mem)} quarter-ends, {len(universe)} tickers ever in the index since 2010 ({len(cur)} now)")
    json.dump(mem, open(OUT / "membership.json", "w"))
    tick = json.loads(get("https://www.sec.gov/files/company_tickers.json", UA_SEC))
    cik_of = {v["ticker"].replace(".", "-"): int(v["cik_str"]) for v in tick.values()}
    if a.limit: universe = universe[: a.limit]
    facts, px, miss_cik, miss_px = {}, {}, [], []
    for i, t in enumerate(universe, 1):
        cik = cik_of.get(t)
        if cik is None: miss_cik.append(t)
        else:
            try: facts[t] = dict(cik=cik, **company_facts(cik))
            except Exception as e: print("facts failed", t, e); miss_cik.append(t)
            time.sleep(0.12)
        try:
            p = prices(t)
            if p["d"]: px[t] = p
            else: miss_px.append(t)
        except Exception as e:
            miss_px.append(t)
        time.sleep(0.25)
        if i % 50 == 0: print(f"  {i}/{len(universe)}  facts {len(facts)}  prices {len(px)}", flush=True)
    for b in ("SPY", "RSP"):
        px[b] = prices(b)
    json.dump(facts, gzip.open(OUT / "facts.json.gz", "wt"))
    json.dump(px, gzip.open(OUT / "prices.json.gz", "wt"))
    json.dump(dict(built=datetime.date.today().isoformat(), tickers=len(universe), with_facts=len(facts), with_prices=len(px) - 2,
                   no_cik=miss_cik, no_prices=miss_px), open(OUT / "coverage.json", "w"), indent=1)
    print(f"done: facts {len(facts)}, prices {len(px) - 2}; no CIK {len(miss_cik)}, no prices {len(miss_px)}")

if __name__ == "__main__":
    main()
