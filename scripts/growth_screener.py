"""
ARIA-Growth — Growth Screener  (REBUILT 2026-07)
=================================================
Rebuild of the original growth_screener.py (source lost). Produces the exact
same schema so the whole downstream pipeline (archiver, allocator, executor,
reports) works unchanged:

  ticker, name, sector, rev_growth_pct, rule_of_40, gross_margin_pct,
  ps_ratio, pe_ratio, growth_score, forward_pe, profit_margin_pct, market_cap

Universe: S&P 500 + Nasdaq 100 (deduped), fetched from Wikipedia with a
hardcoded fallback if scraping fails.

Fundamentals: yfinance .info (CURRENT snapshot — same known limitation as the
original: no historical fundamentals, so screens must be archived monthly to
build the point-in-time dataset).

SCORING — honest note:
  rule_of_40 = rev_growth_pct + profit_margin_pct   (verified EXACT vs original)
  growth_score: growth + quality + valuation composite, fixed absolute ranges
  (comparable across monthly snapshots). See compute_growth_score() docstring
  for the exact weights.
  IMPORTANT: the archive stores RAW metrics, so any future backtest can
  rescore all snapshots uniformly — formula drift does not poison the dataset.

v3 METRICS (added 2026-10, appended AFTER growth_score so the original column
order and the downstream pipeline are unchanged). From yfinance annual
statements (usually 4 fiscal years, so "multi-year" = up to 3 yearly steps):
  roic_pct            NOPAT / invested capital (total debt + equity), avg of last 2 years
  net_debt_ebitda     (total debt - cash) / EBITDA (TTM); negative = net cash
  interest_coverage   EBIT / interest expense (latest year); 999 = no interest
  rev_cagr_pct        revenue CAGR over rev_cagr_years (up to 3)
  eps_cagr_pct        diluted EPS CAGR (only when first and last EPS are positive)
  rev_growth_std      std-dev of yearly revenue growth, in % points (lower = steadier)
  earnings_cv         std / mean of net income (lower = steadier; blank if mean <= 0)
  fcf_cv              std / mean of free cash flow (lower = steadier; blank if mean <= 0)
  fcf_neg_years       years with negative free cash flow, out of fcf_years
  share_change_pct_yr yearly change in share count (+ = dilution, - = buybacks)
  fcf_conversion      FCF / net income (latest fiscal year, both from the statements)
  capex_ocf_pct       capex as % of operating cash flow (capital intensity, stable)
  capex_fcf           capex / FCF (blank when FCF <= 0)
  total_debt, interest_expense, tax_rate   inputs so the dashboard can compute WACC
Statements are cached per ticker in .screener_cache/YYYY-MM/ so an interrupted
run resumes where it stopped (delete the folder to force a refetch).

Usage:
  python growth_screener.py                 # → 9_aria_growth/growth_screen_results_YYYY-MM.csv
  python growth_screener.py --out my.csv
  python growth_screener.py --tickers AAPL,MSFT,NVDA --out test.csv   # quick test
  python growth_screener.py --no-history    # original fast mode (no v3 metrics)

Install: pip install yfinance pandas numpy lxml
"""

import argparse
import io
import json
import sys
import time
import urllib.request
import warnings
from datetime import date
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Windows console defaults to cp1252, which can't encode the ✓/⚠ glyphs below.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _read_html(url: str):
    """pd.read_html via urllib with a browser User-Agent — Wikipedia 403s on the default one."""
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req) as resp:
        return pd.read_html(io.BytesIO(resp.read()))


# ══════════════════════════════════════════════════════════════════════════════
# UNIVERSE
# ══════════════════════════════════════════════════════════════════════════════
def get_universe() -> list[str]:
    """S&P 500 + Nasdaq 100 tickers, deduped. Wikipedia with graceful failure."""
    tickers = set()
    try:
        sp = _read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
        tickers |= set(sp["Symbol"].str.replace(".", "-", regex=False))
        print(f"  ✓ S&P 500: {len(sp)} tickers")
    except Exception as e:
        print(f"  ⚠ S&P 500 fetch failed: {e}")
    try:
        for tbl in _read_html("https://en.wikipedia.org/wiki/Nasdaq-100"):
            for col in ("Ticker", "Symbol"):
                if col in tbl.columns:
                    tickers |= set(tbl[col].astype(str).str.replace(".", "-", regex=False))
                    print(f"  ✓ Nasdaq 100 merged")
                    break
            else:
                continue
            break
    except Exception as e:
        print(f"  ⚠ Nasdaq 100 fetch failed: {e}")
    if not tickers:
        raise SystemExit("Could not build universe — check internet / install lxml.")
    return sorted(t for t in tickers if t and t == t)  # drop NaN


# ══════════════════════════════════════════════════════════════════════════════
# v3 METRICS (annual statements: income, balance sheet, cash flow)
# ══════════════════════════════════════════════════════════════════════════════
def _series(df, *names):
    """First matching row of a yfinance statement as an oldest→newest float Series (NaNs dropped)."""
    if df is None or getattr(df, "empty", True):
        return pd.Series(dtype=float)
    for n in names:
        if n in df.index:
            s = pd.to_numeric(df.loc[n], errors="coerce").dropna()
            if len(s):
                return s.sort_index()          # columns are dates; sort oldest → newest
    return pd.Series(dtype=float)


def _cagr(s: pd.Series):
    if len(s) < 2 or s.iloc[0] <= 0 or s.iloc[-1] <= 0:
        return np.nan, np.nan
    n = len(s) - 1
    return (s.iloc[-1] / s.iloc[0]) ** (1 / n) - 1, n


def _cv(s: pd.Series):
    if len(s) < 3 or s.mean() <= 0:
        return np.nan
    return float(s.std(ddof=0) / s.mean())


def history_metrics(inc, bal, cfs, info) -> dict:
    """All v3 metrics from yfinance annual statements + .info. Every value may be NaN."""
    out = {}
    rev = _series(inc, "Total Revenue", "Operating Revenue")
    ebit = _series(inc, "EBIT", "Operating Income")
    ni = _series(inc, "Net Income", "Net Income Common Stockholders")
    eps = _series(inc, "Diluted EPS", "Basic EPS")
    intr = _series(inc, "Interest Expense", "Interest Expense Non Operating")
    taxr = _series(inc, "Tax Rate For Calcs")
    pretax, taxp = _series(inc, "Pretax Income"), _series(inc, "Tax Provision")
    debt = _series(bal, "Total Debt")
    eq = _series(bal, "Stockholders Equity", "Common Stock Equity")
    cash = _series(bal, "Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents")
    shares = _series(bal, "Ordinary Shares Number", "Share Issued")
    fcf = _series(cfs, "Free Cash Flow")
    ocf = _series(cfs, "Operating Cash Flow")
    capex = _series(cfs, "Capital Expenditure")

    # tax rate: reported rate, else provision / pretax, clipped to 0-35%
    if len(taxr):
        t = float(taxr.iloc[-1])
    elif len(pretax) and len(taxp) and pretax.iloc[-1] > 0:
        t = float(taxp.iloc[-1] / pretax.iloc[-1])
    else:
        t = 0.21
    t = min(max(t, 0.0), 0.35)
    out["tax_rate"] = round(t, 4)

    # ROIC = EBIT x (1 - t) / invested capital (total debt + equity), average of last two years.
    # Cash is NOT subtracted: for cash-rich firms that leaves almost no capital and an absurd ROIC.
    if len(ebit) and len(eq):
        ic = (debt.reindex(eq.index).fillna(0) + eq).dropna()
        ic_avg = ic.iloc[-2:].mean() if len(ic) else np.nan
        out["roic_pct"] = round(float(ebit.iloc[-1]) * (1 - t) / ic_avg * 100, 2) if ic_avg and ic_avg > 0 else np.nan
    else:
        out["roic_pct"] = np.nan

    # leverage (TTM from .info)
    td, tc, ebitda = info.get("totalDebt"), info.get("totalCash"), info.get("ebitda")
    out["total_debt"] = td if td is not None else (float(debt.iloc[-1]) if len(debt) else np.nan)
    out["net_debt_ebitda"] = round(((td or 0) - (tc or 0)) / ebitda, 2) if ebitda and ebitda > 0 else np.nan
    ie = abs(float(intr.iloc[-1])) if len(intr) else 0.0
    out["interest_expense"] = ie if len(intr) else np.nan
    out["interest_coverage"] = (999.0 if ie < 1 else round(float(ebit.iloc[-1]) / ie, 2)) if len(ebit) else np.nan

    # growth consistency
    g, n = _cagr(rev)
    out["rev_cagr_pct"], out["rev_cagr_years"] = (round(g * 100, 2) if g == g else np.nan), n
    ge, _ = _cagr(eps)
    out["eps_cagr_pct"] = round(ge * 100, 2) if ge == ge else np.nan
    yoy = rev.pct_change().dropna() * 100
    out["rev_growth_std"] = round(float(yoy.std(ddof=0)), 2) if len(yoy) >= 2 else np.nan
    out["earnings_cv"] = round(_cv(ni), 3) if _cv(ni) == _cv(ni) else np.nan

    # cash-flow durability
    out["fcf_cv"] = round(_cv(fcf), 3) if _cv(fcf) == _cv(fcf) else np.nan
    out["fcf_neg_years"] = int((fcf <= 0).sum()) if len(fcf) else np.nan
    out["fcf_years"] = int(len(fcf)) if len(fcf) else np.nan

    # dilution / buybacks (per year)
    sc, _ = _cagr(shares)
    out["share_change_pct_yr"] = round(sc * 100, 2) if sc == sc else np.nan

    # conversion + capital intensity
    out["fcf_conversion"] = round(float(fcf.iloc[-1] / ni.iloc[-1]), 2) if len(fcf) and len(ni) and ni.iloc[-1] > 0 else np.nan
    if len(capex) and len(ocf) and ocf.iloc[-1] > 0:
        out["capex_ocf_pct"] = round(abs(float(capex.iloc[-1])) / float(ocf.iloc[-1]) * 100, 2)
    else:
        out["capex_ocf_pct"] = np.nan
    out["capex_fcf"] = round(abs(float(capex.iloc[-1])) / float(fcf.iloc[-1]), 2) if len(capex) and len(fcf) and fcf.iloc[-1] > 0 else np.nan
    return out


V3_COLS = ["roic_pct", "net_debt_ebitda", "interest_coverage", "rev_cagr_pct", "rev_cagr_years", "eps_cagr_pct",
           "rev_growth_std", "earnings_cv", "fcf_cv", "fcf_neg_years", "fcf_years", "share_change_pct_yr",
           "fcf_conversion", "capex_ocf_pct", "capex_fcf", "total_debt", "interest_expense", "tax_rate"]


def _df_to_json(df):
    return None if df is None or df.empty else {str(c.date() if hasattr(c, "date") else c): {k: (None if pd.isna(v) else float(v)) for k, v in df[c].items()} for c in df.columns}


def _json_to_df(d):
    return pd.DataFrame(d) if d else pd.DataFrame()


def fetch_statements(tk, t: str, cache_dir: Path | None):
    """Annual income statement, balance sheet and cash flow, cached as JSON per ticker."""
    f = cache_dir / f"{t}.json" if cache_dir else None
    if f and f.exists():
        d = json.loads(f.read_text())
        return _json_to_df(d["inc"]), _json_to_df(d["bal"]), _json_to_df(d["cfs"])
    for attempt in range(3):
        try:
            inc, bal, cfs = tk.income_stmt, tk.balance_sheet, tk.cashflow
            break
        except Exception:
            time.sleep(2 * (attempt + 1))
    else:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    if f:
        f.write_text(json.dumps({"inc": _df_to_json(inc), "bal": _df_to_json(bal), "cfs": _df_to_json(cfs)}))
    return inc, bal, cfs


# ══════════════════════════════════════════════════════════════════════════════
# FUNDAMENTALS (yfinance .info — current snapshot only)
# ══════════════════════════════════════════════════════════════════════════════
def fetch_fundamentals(tickers: list[str], history: bool = True, cache_dir: Path | None = None) -> pd.DataFrame:
    import yfinance as yf
    rows, failed = [], []
    print(f"\n📥 Fetching fundamentals for {len(tickers)} tickers (slow, ~1/s)...")
    for i, t in enumerate(tickers, 1):
        try:
            tk = yf.Ticker(t)
            info = tk.info
            if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
                failed.append(t); continue
            rev_g = info.get("revenueGrowth")
            pm    = info.get("profitMargins")
            gm    = info.get("grossMargins")
            roe   = info.get("returnOnEquity")
            fcf   = info.get("freeCashflow")
            mcap  = info.get("marketCap")
            row = {
                "ticker": t,
                "name": info.get("shortName") or info.get("longName") or t,
                "sector": info.get("sector") or "Unknown",
                "rev_growth_pct": round(rev_g * 100, 2) if rev_g is not None else np.nan,
                "gross_margin_pct": round(gm * 100, 2) if gm is not None else np.nan,
                "profit_margin_pct": round(pm * 100, 2) if pm is not None else np.nan,
                "ps_ratio": info.get("priceToSalesTrailing12Months"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "market_cap": mcap,
                # v2 metrics (quality + cleaner valuation)
                "fcf_yield_pct": round(fcf / mcap * 100, 2) if fcf and mcap else np.nan,
                "roe_pct": round(roe * 100, 2) if roe is not None else np.nan,
                "ev_ebitda": info.get("enterpriseToEbitda"),
            }
            if history:
                try:
                    row.update(history_metrics(*fetch_statements(tk, t, cache_dir), info))
                except Exception as e:
                    print(f"  ⚠ {t}: statements failed ({e}); v3 metrics left blank")
            rows.append(row)
        except Exception:
            failed.append(t)
        if i % 50 == 0:
            print(f"  ... {i}/{len(tickers)} ({len(rows)} ok, {len(failed)} failed)")
        time.sleep(0.3 if history else 0.1)   # be polite to the API
    print(f"  ✓ {len(rows)} tickers with data ({len(failed)} failed/skipped)")
    df = pd.DataFrame(rows)
    for c in V3_COLS:
        if c not in df.columns:
            df[c] = np.nan
    # rule_of_40 = revenue growth + profit margin  (verified exact vs original)
    df["rule_of_40"] = (df["rev_growth_pct"] + df["profit_margin_pct"]).round(2)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# SCORING (best-fit reconstruction of the lost original — see header note)
# ══════════════════════════════════════════════════════════════════════════════
def _clipscale(s: pd.Series, lo: float, hi: float, invert: bool = False) -> pd.Series:
    x = (s.clip(lo, hi) - lo) / (hi - lo) * 100
    x = (100 - x) if invert else x
    return x.fillna(50.0)      # missing metric → neutral, not penalized


def compute_growth_score(df: pd.DataFrame) -> pd.Series:
    """
    v2 composite: growth + quality + valuation, all fixed absolute ranges
    (comparable across monthly snapshots, no percentile ranking):
      25% rev growth (0-50)     | 20% Rule-of-40 (0-60)   | 15% gross margin (0-80)
      10% FCF yield (0-8%)      | 10% ROE (0-40%)
       8% EV/EBITDA (5-40 inv)  |  6% P/S (0-10 inv)      |  6% trailing P/E (0-50 inv)
    Missing metrics score neutral 50 (e.g. banks without EBITDA aren't penalized).
    """
    return (0.25 * _clipscale(df["rev_growth_pct"], 0, 50)
            + 0.20 * _clipscale(df["rule_of_40"], 0, 60)
            + 0.15 * _clipscale(df["gross_margin_pct"], 0, 80)
            + 0.10 * _clipscale(df["fcf_yield_pct"], 0, 8)
            + 0.10 * _clipscale(df["roe_pct"], 0, 40)
            + 0.08 * _clipscale(df["ev_ebitda"], 5, 40, invert=True)
            + 0.06 * _clipscale(df["ps_ratio"], 0, 10, invert=True)
            + 0.06 * _clipscale(df["pe_ratio"], 0, 50, invert=True)).round(1)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    default_out = Path(__file__).resolve().parent / f"growth_screen_results_{date.today():%Y-%m}.csv"
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(default_out))
    ap.add_argument("--tickers", help="comma-separated tickers instead of the S&P 500 + Nasdaq 100 universe (for testing)")
    ap.add_argument("--no-history", action="store_true", help="skip the v3 multi-year metrics (original fast mode)")
    ap.add_argument("--cache-dir", default=str(Path(__file__).resolve().parent / ".screener_cache" / f"{date.today():%Y-%m}"))
    args = ap.parse_args()

    print("=" * 66)
    print("  ARIA-Growth — Screener (rebuilt)")
    print("=" * 66)

    tickers = [x.strip().upper() for x in args.tickers.split(",")] if args.tickers else get_universe()
    cache_dir = None
    if not args.no_history:
        cache_dir = Path(args.cache_dir); cache_dir.mkdir(parents=True, exist_ok=True)
    df = fetch_fundamentals(tickers, history=not args.no_history, cache_dir=cache_dir)

    # Need at least the score inputs; drop rows missing all of them
    df = df.dropna(subset=["rev_growth_pct", "profit_margin_pct"], how="all")
    df["growth_score"] = compute_growth_score(df)
    df = df.sort_values("growth_score", ascending=False).reset_index(drop=True)

    cols = ["ticker", "name", "sector", "rev_growth_pct", "rule_of_40",
            "gross_margin_pct", "ps_ratio", "pe_ratio",
            "forward_pe", "profit_margin_pct", "market_cap",
            "fcf_yield_pct", "roe_pct", "ev_ebitda", "growth_score"]
    if not args.no_history:
        cols += V3_COLS          # appended after growth_score: original column order unchanged
    df = df[cols]
    df.to_csv(args.out, index=False)

    print(f"\n  ✓ {len(df)} stocks screened → {args.out}")
    print(f"  Score range: {df.growth_score.min():.1f} - {df.growth_score.max():.1f}")
    print("\n  Top 10:")
    for _, r in df.head(10).iterrows():
        print(f"    {r.ticker:<6} {r.growth_score:>5.1f}  rev {r.rev_growth_pct:>6.1f}%  "
              f"R40 {r.rule_of_40:>6.1f}  [{str(r.sector)[:20]}]")
    if not args.no_history:
        cov = {c: int(df[c].notna().sum()) for c in ("roic_pct", "net_debt_ebitda", "rev_cagr_pct", "fcf_cv", "share_change_pct_yr")}
        print(f"\n  v3 metric coverage (non-blank of {len(df)}): {cov}")
    print("\n  Next: python aria_growth_archive_screen.py --screen", args.out)


if __name__ == "__main__":
    main()