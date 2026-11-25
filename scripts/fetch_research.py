#!/usr/bin/env python3
"""Fetch structured SEC EDGAR XBRL facts (10-yr financials, 5-yr debt maturities, working capital,
pure depreciation, Net PPE, RPO/backlog, advertising, insurance lines) and Yahoo Finance analyst
track record & revisions -> data/research_facts.json.

Information only: nothing here changes a fair value.
Usage: python3 scripts/fetch_research.py
       python3 scripts/fetch_research.py --sec-only
       python3 scripts/fetch_research.py --yahoo-only
"""
import datetime, http.cookiejar, json, pathlib, sys, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/research_facts.json"
ASSETS = [a["ticker"] for a in json.load(open(ROOT / "data/assets.json"))["assets"] if a.get("type") == "stock"]
SEC_UA = "FairValueDashboard research@liumoazed.dev"

# US-GAAP XBRL tag priority lists (first match with 10-K annual data wins per fiscal year)
FLOW_TAGS = {
    "rev": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "SalesRevenueServicesNet",
        "RegulatedAndUnregulatedOperatingRevenue",
        "RealEstateRevenueNet",
        "InterestAndDividendIncomeOperating",
    ],
    "gross": ["GrossProfit"],
    "op": ["OperatingIncomeLoss"],
    "pretax": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
               "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
    "ni": ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "CapitalExpendituresIncurredButNotYetPaid",
        "PaymentsForCapitalImprovements",
    ],
    "da": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
    ],
    "dep": ["Depreciation", "DepreciationNonproduction", "CostOfGoodsAndServicesSoldDepreciation"],
    "sbc": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "wc": ["IncreaseDecreaseInOperatingCapital"],
    "div": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock", "PaymentsOfOrdinaryDividends"],
    "buyback": ["PaymentsForRepurchaseOfCommonStock", "PaymentsForRepurchaseOfEquity"],
    "rd": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],
    "ad": ["AdvertisingExpense", "MarketingAndAdvertisingExpense", "SellingAndMarketingExpense"],
    # Insurance underwriting & investment income lines
    "premiums": ["PremiumsEarnedNet", "InsuranceServicesRevenue"],
    "claims": ["PolicyholderBenefitsAndClaimsIncurredNet", "LiabilityForUnpaidClaimsAndClaimsAdjustmentExpenseIncurredClaims1", "IncurredClaimsPropertyCasualtyAndLiability"],
    "inv_inc": ["NetInvestmentIncome", "InvestmentIncomeNet"],
    "acq_cost": ["DeferredPolicyAcquisitionCostAmortizationExpense", "PolicyAcquisitionCosts", "OtherUnderwritingExpense"],
    "prior_dev": ["LiabilityForUnpaidClaimsAndClaimsAdjustmentExpenseIncurredClaims2", "SupplementalInformationForPropertyCasualtyInsuranceUnderwritersPriorYearClaimsAndClaimsAdjustmentExpense"],
}

INSTANT_TAGS = {
    "ppe": ["PropertyPlantAndEquipmentNet", "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsAndShortTermInvestments"],
    "debt_cur": ["LongTermDebtCurrent", "ShortTermBorrowings", "DebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent"],
    "debt_noncur": ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations"],
    "rec": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
    "inv": ["InventoryNet"],
    "ap": ["AccountsPayableCurrent"],
    "def_rev": ["ContractWithCustomerLiabilityCurrent", "DeferredRevenueCurrent", "ContractWithCustomerLiability"],
    "shares": ["CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"],
    "rpo": ["RevenueRemainingPerformanceObligation"],
}

DEBT_MAT_TAGS = {
    "y1": [
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths",
        "LongTermDebtAndCapitalLeaseObligationsRepaymentsOfPrincipalInNextTwelveMonths",
        "LongTermDebtMaturitiesRepaymentsOfPrincipalRemainderOfFiscalYear",
    ],
    "y2": [
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo",
        "LongTermDebtAndCapitalLeaseObligationsRepaymentsOfPrincipalInYearTwo",
    ],
    "y3": [
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree",
        "LongTermDebtAndCapitalLeaseObligationsRepaymentsOfPrincipalInYearThree",
    ],
    "y4": [
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFour",
        "LongTermDebtAndCapitalLeaseObligationsRepaymentsOfPrincipalInYearFour",
    ],
    "y5": [
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFive",
        "LongTermDebtAndCapitalLeaseObligationsRepaymentsOfPrincipalInYearFive",
    ],
    "after5": [
        "LongTermDebtMaturitiesRepaymentsOfPrincipalAfterYearFive",
        "LongTermDebtAndCapitalLeaseObligationsRepaymentsOfPrincipalAfterYearFive",
    ],
}

SHARES_FLOW_TAGS = [
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "WeightedAverageNumberOfSharesOutstandingBasic",
]


def http_json(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": SEC_UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def extract_annual_flow(gaap, tag_list, unit="USD"):
    """Extract annual (10-K/20-F, ~330-400 day duration) values keyed by end date YYYY-MM-DD."""
    out = {}
    for tag in tag_list:
        obj = gaap.get(tag)
        if not obj:
            continue
        entries = obj.get("units", {}).get(unit) or []
        if not entries and unit == "USD/shares":
            entries = obj.get("units", {}).get("USD / shares") or []
        for e in entries:
            if e.get("form") not in ("10-K", "10-K/A", "20-F"):
                continue
            start, end, val = e.get("start"), e.get("end"), e.get("val")
            if not start or not end or val is None:
                continue
            try:
                days = (datetime.date.fromisoformat(end) - datetime.date.fromisoformat(start)).days
            except ValueError:
                continue
            if not (320 <= days <= 400):
                continue
            filed = e.get("filed", "")
            # Prefer earlier tag in priority list; within same tag prefer latest filing (restated/final)
            prev = out.get(end)
            if prev is None:
                out[end] = (tag, filed, float(val))
            elif prev[0] == tag and filed >= prev[1]:
                out[end] = (tag, filed, float(val))
    return {end: val for end, (_, _, val) in sorted(out.items())}


def extract_annual_instant(gaap, tag_list, unit="USD", dei=None):
    """Extract fiscal year-end balance sheet values from 10-K filings keyed by end date YYYY-MM-DD."""
    out = {}
    for tag in tag_list:
        obj = gaap.get(tag) or (dei.get(tag) if dei else None)
        if not obj:
            continue
        entries = obj.get("units", {}).get(unit) or []
        for e in entries:
            if e.get("form") not in ("10-K", "10-K/A", "20-F"):
                continue
            end, val = e.get("end"), e.get("val")
            if not end or val is None:
                continue
            filed = e.get("filed", "")
            # Filter out comparative/mid-year instants that aren't near FY end by preferring FY-end filings
            fp = e.get("fp")
            if fp and fp != "FY":
                continue
            prev = out.get(end)
            if prev is None:
                out[end] = (tag, filed, float(val))
            elif prev[0] == tag and filed >= prev[1]:
                out[end] = (tag, filed, float(val))
    return {end: val for end, (_, _, val) in sorted(out.items())}


def extract_debt_maturities(gaap):
    """Extract the latest 10-K 5-year debt maturity schedule (ASC 470-10-50-1)."""
    by_end = {}
    for bucket, tags in DEBT_MAT_TAGS.items():
        for tag in tags:
            obj = gaap.get(tag)
            if not obj:
                continue
            for e in obj.get("units", {}).get("USD", []):
                if e.get("form") not in ("10-K", "10-K/A", "20-F"):
                    continue
                end, val, filed = e.get("end"), e.get("val"), e.get("filed", "")
                if not end or val is None:
                    continue
                slot = by_end.setdefault(end, {})
                prev = slot.get(bucket)
                if prev is None or (prev[0] == tag and filed >= prev[1]):
                    slot[bucket] = (tag, filed, float(val))
    if not by_end:
        return None
    # Pick the most recent 10-K end date that has at least 2 maturity buckets (or latest overall)
    ranked = sorted(by_end.items(), key=lambda kv: (kv[0], len(kv[1])), reverse=True)
    best_end, best_slot = next(((e, s) for e, s in ranked if len(s) >= 2), ranked[0])
    # Only accept recent (within last 2.5 years, i.e., >= 2024-01-01)
    if best_end < "2024-01-01":
        return None
    res = {"as_of": best_end}
    for k in ("y1", "y2", "y3", "y4", "y5", "after5"):
        if k in best_slot:
            res[k] = round(best_slot[k][2] / 1e9, 4)
    y1_5 = sum(res.get(k, 0.0) for k in ("y1", "y2", "y3", "y4", "y5"))
    res["due_5y_b"] = round(y1_5, 4)
    res["total_sched_b"] = round(y1_5 + res.get("after5", 0.0), 4)
    return res


def merge_by_fy(series_map):
    """Align flow and instant series by fiscal year (YYYY, using end date; Jan-Mar FY ends mapped to prior year)."""
    def fy(d):
        return d[:4] if d[5:7] > "03" else str(int(d[:4]) - 1)

    years = {}
    for k, dmap in series_map.items():
        for end, val in dmap.items():
            y = fy(end)
            if y < "2006":
                continue
            rec = years.setdefault(y, {"end": end})
            if end > rec["end"]:
                rec["end"] = end
            if k not in rec:
                rec[k] = round(val, 4) if k == "eps" else round(val / 1e6, 2)  # $M for money/shares(M), $ for eps
    # Keep sorted by year, drop empty years
    return {y: years[y] for y in sorted(years) if len(years[y]) > 1}


def fetch_sec_all():
    print("Fetching SEC ticker->CIK map...")
    ct = http_json("https://www.sec.gov/files/company_tickers.json")
    t2cik = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in ct.values()}
    # Known overrides if ticker differs slightly
    out = {}
    ok, fail = 0, []
    for i, t in enumerate(sorted(ASSETS)):
        cik = t2cik.get(t)
        if not cik:
            fail.append((t, "no CIK"))
            continue
        try:
            cf = http_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", timeout=25)
            gaap = cf.get("facts", {}).get("us-gaap", {})
            dei = cf.get("facts", {}).get("dei", {})
            if not gaap:
                # Some foreign filers (20-F) use ifrs-full
                ifrs = cf.get("facts", {}).get("ifrs-full", {})
                if not ifrs:
                    fail.append((t, "no us-gaap/ifrs"))
                    continue
                gaap = ifrs
            smap = {}
            for k, tags in FLOW_TAGS.items():
                unit = "USD/shares" if k == "eps" else "USD"
                smap[k] = extract_annual_flow(gaap, tags, unit=unit)
            smap["dil_shares"] = extract_annual_flow(gaap, SHARES_FLOW_TAGS, unit="shares")
            for k, tags in INSTANT_TAGS.items():
                unit = "shares" if k == "shares" else "USD"
                smap[k] = extract_annual_instant(gaap, tags, unit=unit, dei=dei)
            annual = merge_by_fy(smap)
            mat = extract_debt_maturities(gaap)
            # Latest RPO
            rpo_s = smap.get("rpo") or {}
            rpo = None
            if rpo_s:
                last_d = max(rpo_s)
                if last_d >= "2024-01-01":
                    rpo = {"as_of": last_d, "val_b": round(rpo_s[last_d] / 1e9, 3)}
            out[t] = {
                "cik": cik,
                "entity": cf.get("entityName"),
                "annual": annual,
                "debt_maturities": mat,
                "rpo": rpo,
            }
            ok += 1
        except Exception as e:
            fail.append((t, str(e)[:80]))
        if (i + 1) % 25 == 0:
            print(f"  SEC progress: {i+1}/{len(ASSETS)} (ok={ok}, fail={len(fail)})")
        time.sleep(0.11)  # stay comfortably under SEC's 10 req/s guideline
    print(f"SEC done: {ok}/{len(ASSETS)} ok; failed: {fail}")
    return out


def fetch_yahoo_all():
    print("Fetching Yahoo Finance analyst history & revisions...")
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")]
    try:
        opener.open("https://fc.yahoo.com", timeout=10)
    except Exception:
        pass
    crumb = opener.open("https://query2.finance.yahoo.com/v1/test/getcrumb", timeout=10).read().decode().strip()
    out = {}
    ok, fail = 0, []
    for i, t in enumerate(sorted(ASSETS)):
        try:
            url = (f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{urllib.parse.quote(t)}"
                   f"?modules=earningsHistory,earningsTrend,financialData,assetProfile&crumb={urllib.parse.quote(crumb)}")
            raw = json.loads(opener.open(url, timeout=12).read())
            res = (raw.get("quoteSummary") or {}).get("result")
            if not res:
                fail.append((t, "empty result"))
                continue
            r0 = res[0]
            # Earnings history (actual vs estimate for last 4 quarters)
            hist = []
            for h in (r0.get("earningsHistory") or {}).get("history", []):
                act = (h.get("epsActual") or {}).get("raw")
                est = (h.get("epsEstimate") or {}).get("raw")
                surp = (h.get("surprisePercent") or {}).get("raw")
                q = (h.get("quarter") or {}).get("fmt")
                if act is not None and est is not None:
                    hist.append({
                        "q": q,
                        "actual": round(float(act), 4),
                        "est": round(float(est), 4),
                        "surprise": round(float(surp), 4) if surp is not None else (round((act - est) / abs(est), 4) if est else None),
                    })
            # Earnings trend & revisions
            trend = {}
            for tr in (r0.get("earningsTrend") or {}).get("trend", []):
                p = tr.get("period")
                if p not in ("0y", "+1y", "+5y"):
                    continue
                et = tr.get("epsTrend") or {}
                er = tr.get("epsRevisions") or {}
                rev = tr.get("revenueEstimate") or {}
                ee = tr.get("earningsEstimate") or {}
                raw_of = lambda o, k: (o.get(k) or {}).get("raw")
                trend[p] = {
                    "growth": raw_of(tr, "growth"),
                    "eps_avg": raw_of(ee, "avg"),
                    "eps_n": raw_of(ee, "numberOfAnalysts"),
                    "rev_growth": raw_of(rev, "growth"),
                    "cur": raw_of(et, "current"),
                    "d30": raw_of(et, "30daysAgo"),
                    "d60": raw_of(et, "60daysAgo"),
                    "d90": raw_of(et, "90daysAgo"),
                    "up7": raw_of(er, "upLast7days"),
                    "up30": raw_of(er, "upLast30days"),
                    "dn7": raw_of(er, "downLast7Days"),
                    "dn30": raw_of(er, "downLast30days"),
                }
            fd = r0.get("financialData") or {}
            ap = r0.get("assetProfile") or {}
            out[t] = {
                "history": hist,
                "trend": trend,
                "analysts": (fd.get("numberOfAnalystOpinions") or {}).get("raw"),
                "rec": fd.get("recommendationKey"),
                "sector": ap.get("sector"),
                "industry": ap.get("industry"),
            }
            ok += 1
        except Exception as e:
            fail.append((t, str(e)[:80]))
        if (i + 1) % 30 == 0:
            print(f"  Yahoo progress: {i+1}/{len(ASSETS)} (ok={ok}, fail={len(fail)})")
        time.sleep(0.12)
    print(f"Yahoo done: {ok}/{len(ASSETS)} ok; failed: {fail}")
    return out


def main():
    sec_only = "--sec-only" in sys.argv
    yahoo_only = "--yahoo-only" in sys.argv
    old = json.load(open(OUT)) if OUT.exists() else {}
    sec = old.get("sec", {}) if yahoo_only else fetch_sec_all()
    yahoo = old.get("yahoo", {}) if sec_only else fetch_yahoo_all()
    doc = {
        "_about": "Structured SEC EDGAR XBRL facts (annual financials, 5-year debt maturities, RPO) and Yahoo Finance analyst track record & revisions for scripts/framework.py. Information only.",
        "fetched": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "sec": sec,
        "yahoo": yahoo,
    }
    json.dump(doc, open(OUT, "w"), separators=(",", ":"))
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
