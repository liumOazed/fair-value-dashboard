# Fair Value Dashboard

A static dashboard comparing live-ish prices with estimated fair values (modern Graham framework: normalised earnings power, Bear/Base/Bull, never value on the bull case, margin of safety). Not investment advice.

## One-click setup (about 2 minutes)
1. Create a **public** GitHub repo and upload everything in this folder (keep the `.github` folder and `.nojekyll`).
2. **Settings → Pages → Build and deployment → Source: Deploy from a branch → `main` / `(root)` → Save.**
3. **Actions tab → "Update prices" → Run workflow** once (also enable workflows if GitHub asks).
4. Open `https://<your-username>.github.io/<repo-name>/`.

Prices refresh automatically every weekday after the US close. No keys or secrets are used.

## Growth Screen and Monthly Top 5 (once a month)

1. Nothing to do: on the 1st of each month (03:00 UTC) the **Monthly run** workflow runs the screener itself on GitHub (`scripts/growth_screener.py`, ~20 min) and saves `data/screens/growth_screen_results_YYYY-MM.csv`. If the run looks incomplete (fewer than 450 stocks, e.g. Yahoo limits) it saves it to `data/screens/extra/` instead and warns; then run the workflow again or upload a CSV.
   You can still upload your own CSV for a month (Add file → Upload files on GitHub); an uploaded file is never overwritten and starts the run immediately.
2. The **Monthly run** then:
   - fills any missing months in between with estimates (`scripts/backfill.py`, files ending `_estimated.csv`; a real file for that month always replaces its estimate),
   - scores and ranks every stock and saves the Top 50 (`scripts/build_screen.py`, results cached per month in `data/cache/`),
   - picks the month's 5 most undervalued stocks for the Fair Value Table (`scripts/fair_value_table.py`).
3. The dashboard buttons **Calculate Top Growth** and **Evaluate Fair Value** open the same workflow (Actions → Monthly run → Run workflow).

Each step runs **once per month**: `data/runs.json` records what's done, and a second run in the same month stops with
"Already calculated for <month>". The workflow also runs on the 1st of each month; if the new CSV isn't there yet it says so and does nothing.
To redo a month after fixing its CSV, run the workflow with **force** ticked.

Edit `data/themes.json` to change the theme filters (that rebuilds the screen without touching the monthly lock).

- **Score v2** is explained at the bottom of the Growth Screen page and in the docstring of `scripts/build_screen.py`. Weights and caps are at the top of that file.
- **Growth priced in** is an indicative reverse DCF, not a fair value. It uses a sector required return (`REQ_RETURN` in `scripts/build_screen.py`, based on Damodaran's Jan-2026 cost of equity + about 1 point). Where free cash flow is distorted (FCF yield under 25% of earnings yield, or a bank/insurer) it uses the earnings yield and shows `FCF distorted` with no verdict; shrinking sales also get no verdict.
- **Monthly Top 5** fair values are quick estimates from the CSV (method on the page and in `scripts/fair_value_table.py`). Only stocks in `data/assets.json` have a full, hand-checked fair value.

## Add a new stock
Open `data/assets.json` and copy one block in `assets`. Required fields: `ticker`, `name`, `type` (`stock`, `etf` or `commodity`), `fair_value`, `bear`, `base`, `bull`, `mos` (margin of safety, e.g. 0.25), `buy_below` (fair value × (1 − mos)), `valued_on`. The rest (`scenarios`, `sensitivity`, `epv`, `implied_return`, `notes`) is optional and only fills the detail panel. Commit. The price script picks the ticker up on its next run (or run the workflow by hand).

To produce the numbers, add or edit the inputs in `model/model.py` (`STOCKS`), run `python model/model.py` (prints fair values, writes `model/results.json`), then `python scripts/export_assets.py TICKER ...` to copy those results into `data/assets.json`. After exporting, run `python model/montecarlo.py`: it adds the Monte Carlo range (20,000 runs, fixed seed), the sensitivity chart data and a Sobol convergence check to each modelled stock in `data/assets.json`; the page computes the model-implied probabilities against the live price. Runs are split exactly 30/50/20 between Bear/Base/Bull and stored per case, so the drawer can show where outcomes come from and re-weight them with the what-if sliders (view only; the official fair value keeps 30/50/20). It also stores each run's yearly return at 17 prices (0.3x-3x fair value) in two versions: a 10-year hold (sold at the end of year 10 at the price that gives the next buyer the required return; can be negative) and hold-for-good (cash flows forever); the page reads them off at the live price. In both, 'return beats the required return' is exactly 'value above price', because value falls as the discount rate rises. Every modelled stock needs an entry (rate + reason) in `data/required_returns.json`: that one file sets required returns for the Fair Value tab, the Growth Screen and the Monthly Top 5 (stock > theme > sector), so the tabs never disagree. The drawer shows each stock's fair value at 8-12% next to the rate used. Also add a starting price for a new ticker to `data/prices.json` (the daily job then keeps it fresh). To gather a new stock's raw inputs (price, shares, TTM revenue / FCF / stock pay, cash, debt, interest, tax, analyst growth estimates), commit `.github/inputs-request.json` with the tickers: the **Fetch model inputs** workflow writes them to `data/inputs/`.

## Refresh fair values
Fair values are slow-moving. Re-run the model after each earnings report (roughly quarterly), paste the new numbers into `data/assets.json`, commit.

## Files
- `index.html`, `assets/` the dashboard (plain HTML/CSS/JS, no build step)
- `data/assets.json` fair-value inputs, `data/prices.json` latest prices (auto-updated)
- `scripts/update_prices.py` + `.github/workflows/update-prices.yml` daily price job
- `screener.html`, `assets/screen.js`, `scripts/build_screen.py`, `data/screens/`, `data/screen.json`, `data/themes.json` growth screen
- `scripts/export_assets.py` copies model results into `data/assets.json`
- `docs/fair_value_model.xlsx` step-by-step calculations (import to Google Sheets via File → Import)

Preview locally: `python -m http.server` then open http://localhost:8000.

## Cash-flow definitions (one per question)

| Question | Metric | Definition |
|---|---|---|
| Are profits real cash? | **FCF ÷ net income** | Statement free cash flow (operating cash flow − capex) ÷ reported net income, **3 fiscal years combined** (latest year when history is short). A "Cash swing" flag appears when the latest year is more than 30% away from the 3-year figure. |
| Cash return for the price | **FCF yield** | Statement free cash flow, last 4 quarters (latest fiscal year if quarters are missing) ÷ market value. Yahoo's computed "levered FCF" is kept only as `fcf_yield_yahoo_pct` for reference. |
| Cash return for the whole business | **FCF / EV** | (Statement FCF + after-tax interest) ÷ enterprise value (market value + debt − cash). Neutral to how the company is financed, so debt can't flatter it. Display only (not in the score); not shown for banks and insurers. |
| Profit return for the price | **Earnings yield** | Trailing net income (last 4 quarters) ÷ market value, the same period as the FCF yield. The forward (analyst) earnings yield is shown separately. |

The old "FCF ÷ EY" column was dropped: done consistently it equals FCF ÷ net income, and it mixed Yahoo's FCF with forward earnings. These definitions apply to Growth Screen scores and the Monthly Top 5 from November 2026; October stays as recorded.

## Stock snapshot (top of each Fair Value drawer)

Click a stock to see, before the detail:
- **Flags**: anything you must know (FCF normalised, cyclical, dilution, pending deal, dividend cut, price far above fair value, ...). Click a flag for the reason.
- **Business quality**: five cards (Earnings, Cash flow, Business performance, Financial strength, Dividends & buybacks), each graded Strong / OK / Weak with a headline number and a 4-5 year sparkline. Click a card for every metric, its grade and its sector percentile. Price is never part of these grades.
  Each metric is graded in one card only (margins under Business performance, P/E under Valuation); repeats are shown in grey as "info". Companies with no dividend are graded on buybacks, or shown as "Reinvests". Debt maturities are not in free data.
- **Valuation**: bear / fair / bull range with the live price and buy-below level, chance the value is above the price, 10-year return, growth priced in, and P/E, EV/EBITDA and FCF yield against the stock's own last 4-5 years and its sector.
- **What to watch**: the two inputs that move the value most, with the base / bear / bull values and what to check each quarter.
- **Fair value over time**: monthly price vs every recorded valuation (`data/fv_history.json`, appended by `export_assets.py`; recording started 2026-10-25).

Data: `scripts/fetch_snapshot.py` (GitHub job **Refresh stock snapshot**, 2nd of each month) fetches dividends, annual statements, liquidity, splits and 6 years of prices into `data/snapshot_raw.json`; `scripts/build_snapshot.py` grades them into `data/snapshot.json` using the Growth Screen metrics for sector percentiles.

## Backtest (relative, 2013 onwards)
`python scripts/bt_fetch.py` (on a home computer, with `SEC_CONTACT=you@example.com`; it caches and can be re-run) downloads S&P 500
membership history (fja05680/sp500), annual SEC figures as first reported and monthly prices into `data/backtest/`.
`python scripts/bt_run.py` rebuilds the screen every quarter from filings available at the time, scores it with the live
score v4, compares groups (score and fair-value quintiles, top 50, risk level) and block-bootstraps the gaps. Results appear on
the Track record page. Survivorship-biased: compare groups with each other, not with SPY.
