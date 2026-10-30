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

## Business drivers (company KPIs)

Each Fair Value drawer has a **Business drivers** table: 4-6 KPIs chosen for that company (`data/kpi_defs.json`, e.g. Azure growth for MSFT, payments volume for V, room nights for BKNG), with the latest value, change vs a year earlier, the last 8 quarters and a trend judged against the company's own history (▲ improving / ● steady / ▼ worse; "worse" means worse for the business). A KPI that moves the wrong way 3 quarters running adds a flag. Values come from the companies' own releases and filings: each point in `data/kpis.json` keeps the source link and the exact quoted line (hover a value). `scripts/kpi_add.py` validates every addition. The **KPI backfill** task fills the history (queue in `data/kpi_backfill.json`); the daily earnings task adds each new quarter.

## Earnings updates (GitHub does the numbers, Claude does the reading)

Fair values update automatically after each company reports; Claude is only used for what needs reading.
1. **Earnings watch** (GitHub job, daily 07:30 Dhaka / 01:30 UTC, no Claude): `scripts/earnings_watch.py` refreshes the earnings calendar (`data/earnings_calendar.json`) and lists every company that has reported a quarter newer than its model (`data/pending_reports.json`, using `data/data_through.json`). Then `scripts/auto_update.py` rolls each pending model forward as soon as Yahoo shows the new quarter (usually 2-8 days after the report):
   - revenue, FCF and interest: old figure + (new quarter - same quarter a year earlier), so every hand adjustment already in the model (normalisations, exclusions, own definitions) stays in place; normalised-FCF models keep their normalised margin; pro forma / net-revenue models (NDAQ, SPGI, RMD) are scaled by Yahoo's TTM growth; stock pay = Yahoo's last 4 quarters; net cash, debt and shares move by Yahoo's balance-sheet change; price = latest close;
   - scenario growth / margins, required returns and safety margins are never changed by the script;
   - safety: not applied (queued for Claude) when Yahoo's quarters don't line up, for special cases (ADYEY, CTAS) or implausible changes (revenue +-30%, shares +-10%, FCF change > 15% of revenue, net cash change > 25% of market value); a fair value that moves more than 35% is reverted and queued;
   - then it re-runs the model, Monte Carlo and snapshot, records fair-value history, advances `data_through` and commits. Auto-updated notes carry a "[Numbers auto-updated ...]" tag until reviewed.
   Everything that still needs reading goes to `data/review_queue.json` (status `auto_updated` with flags such as a growth surprise vs the base case, or `manual` with the reason).
2. **Earnings review** (scheduled Claude task, Tuesday and Friday 08:41 Dhaka): works through the review queue: checks the auto numbers against the company's release, reads guidance (changes an assumption only when the results clearly contradict it), rewrites the notes, adds the quarter's business-driver KPIs; does the full update itself for `manual` items and for companies Yahoo still hasn't shown 4+ days after reporting; finishes any KPI backfill. Stops immediately when there is nothing to review.

Validation (Q3 2026): rolled forward from the June models, the script matched the hand-made September updates for MSFT, GOOGL, MA, GRMN, HWM, FIX, ALLE and SPGI within rounding, and correctly refused INCY (one-off licence payment).
The Growth Screen and Monthly Top 5 stay monthly (1st of each month).

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
- **Business quality**: five cards (Earnings, Cash flow, Business performance, Financial strength, Dividends & buybacks) — Layer-1 metrics include incremental ROIC (3 yrs), stock pay ÷ revenue, FCF margin trend, capex ÷ depreciation (asset-light firms labelled), R&D ÷ revenue and inventory vs sales growth, each graded Strong / OK / Weak with a headline number and a 4-5 year sparkline. Click a card for every metric, its grade and its sector percentile. Price is never part of these grades.
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

## Changelog (since the first push, 15 Oct 2026)

Functional changes only (layout and wording tweaks left out). Score and Top 5 rule changes apply from the month shown; earlier months stay as recorded.

| Date | Area | Change | Why / effect |
|---|---|---|---|
| 15 Oct | Fair Value | First version: 6 assets (AAPL, MSFT, GOOGL, AMZN, QQQ, GLD), DCF fair value, bear/base/bull, margin-of-safety bands, daily prices | — |
| 16 Oct | Growth Screen | New tab: score v2, themes, 6 more fair values | Rank the S&P 500 on growth quality |
| 16 Oct | Growth Screen | "Growth priced in": reverse DCF at sector required returns, earnings fallback when FCF is distorted, no verdict when sales shrink | Shows what today's price assumes |
| 16 Oct | Growth Screen | Earnings yield and FCF ÷ EY columns; synced scrollbar above the table | (FCF ÷ EY replaced on 26 Oct, see below) |
| 16 Oct | Monthly | Monthly pipeline: once-a-month lock, Aug/Sep estimated backfill, Calculate Top Growth / Evaluate Fair Value buttons, Monthly Top 5 table | One reproducible run per month |
| 17 Oct | Fair Value | Full models for APA, DECK, INCY, MKC; Top 5 page shows full-model value next to the quick estimate | October Top 5 checked with full models |
| 18 Oct | Growth Screen | Market P/E (trailing and forward, index-style) and a market comparison | Context for each stock's P/E |
| 19 Oct | All tabs | One required-return file (`data/required_returns.json`) for every tab; fair value at 8–12% table in the drawer | Tabs can't disagree on the hurdle rate |
| 20 Oct | Screener | v3 metrics: ROIC, net debt/EBITDA, interest cover, 3-yr CAGRs, volatility, FCF stability, share change, capex ratios; runs on GitHub | Quality and balance-sheet data |
| 20 Oct | Growth Screen | Score v3 (ROIC, balance sheet, consistency, FCF stability, dilution); WACC and flags; Top 5 balance-sheet filters | — |
| 21 Oct | Screener | ROIC on operating invested capital; EPS CAGR split guard; cost of debt = interest ÷ average debt; industry, beta, volatility, max drawdown | Fixes buyback and split distortions |
| 21 Oct | Growth Screen | **Score v4**: Quality 30 / Growth 30 / Valuation 20 / Resilience 20; Financial Safety score; sector-aware risk levels (utilities, REITs); distress cap; data confidence | Current scoring method |
| 22 Oct | Growth Screen | Fee-based financials peer group (V, MA, exchanges, data firms); **5 resilient compounders** added after the Top 50 | Durable businesses not missed for valuation |
| 22 Oct | Monthly Top 5 | Resilient picks join the candidates (from Nov) | — |
| 23 Oct | Growth Screen | Trend fields; **5 quick-answer questions** per stock and a Checks column | Plain-language health check |
| 23 Oct | Fair Value | **DCF method fixed**: FCF *before* interest at the required return, minus net debt (was double-counting debt cost); year-by-year forecast tables | Debt can never raise a value |
| 23 Oct | Fair Value | **Monte Carlo** (20k runs, 30/50/20 regimes, correlated inputs, Sobol check) and sensitivity chart | Range of outcomes, not one number |
| 23 Oct | Track record | **Forward test** vs SPY (monthly signals, daily refresh) | Honest live check of the method |
| 23 Oct | Track record | **Backtest 2013–2026** (SEC facts as first reported, membership history, block bootstrap) | Result: no reliable return edge from the score, but clearly lower risk |
| 24 Oct | Fair Value | Monte Carlo: below-price and downside tiles, Bear/Base/Bull split, what-if weights, **10-year-hold return** (can be negative) and hold-for-good return, chance of a loss, average vs median | Answers "what might I earn at this price?" |
| 24 Oct | Fair Value | **16 more full models** (EXPE, BKNG, INTU, ADSK, TPR, VEEV, MNST, ALLE, FTNT, RMD, V, FIX, MA, CTAS, DXCM, IDXX); "Fetch model inputs" workflow | 32 assets |
| 25 Oct | Fair Value | **Stock snapshot**: flags, five graded quality cards (Earnings, Cash flow, Business performance, Financial strength, Dividends & buybacks), valuation strip, what to watch, fair value history (`data/fv_history.json`) | Compact one-screen view per stock |
| 25 Oct | Data | Monthly "Refresh stock snapshot" job: dividends, annual statements, liquidity, splits, 6-yr prices | Keeps the snapshot current |
| 25 Oct | Fair Value / Growth Screen | New groups: Consumer brands, Travel, Medical devices & diagnostics, Industrials & services, Energy | Nothing left in "Other" |
| 25 Oct | Snapshot | Operating margin graded against the industry (sector if fewer than 8 peers); gross and net margin as context | Fair margin comparison (e.g. Apple vs software firms) |
| 25 Oct | Fair Value | Price filters: Below fair value, Interesting or better | — |
| 25 Oct | Automation | Quarterly fair-value refresh task updated for all stocks and the snapshot | — |
| 26 Oct | Monthly | Monthly run makes the month's screener CSV itself on GitHub (guarded: fewer than 450 stocks → warning) | Nothing to upload by hand |
| 26 Oct | Growth Screen | **Passes all 5 checks**: 5/5 badge, added to the list after the resilient picks, filter chip; groups for financial data & exchanges, aerospace & defense, media & streaming | Healthy businesses not missed |
| 26 Oct | Monthly Top 5 | 5/5-check stocks join the candidates (from Nov) | 79 candidates instead of 55 |
| 26 Oct | Fair Value | **12 more full models** (VRSN, NDAQ, MCO, SPGI pro forma ex-Mobility, NFLX, CBOE, GRMN, FDS, CRM incl. $25B buyback debt, HWM, ADP, AME) | 44 assets |
| 26 Oct | Fair Value | Health filter "Clean bill of health (5/5)" | — |
| 26 Oct | Cash-flow metrics | One **FCF ÷ net income** (statements, 3 years combined, Cash swing flag) replaces FCF ÷ EY; **FCF yield from statement cash flow** instead of Yahoo's levered estimate; trailing earnings yield (forward shown separately); score's earnings-yield part no longer repeats forward P/E (from Nov) | Same period, same definitions everywhere; removes wrong "FCF distorted" tags (NVDA, MSFT, GOOGL…) |
| 26 Oct | Growth Screen | **FCF / EV** column (FCF before interest ÷ enterprise value, %), display only | Cash yield of the whole business; debt can't flatter it |
| 25–26 Oct | Fixes | Dividend history robust to Yahoo gaps and payment-frequency changes; dividend-cut flag only for consecutive years; split-safe P/E history; duplicate operating-margin field that would have broken the monthly build | — |
| 30 Oct | Automation | **Daily earnings updates**: earnings calendar + pending list (GitHub job) and a daily task that updates each model from the company's own filing the morning after it reports; quarterly refresh task retired | Models current within a day of each report instead of up to 3 months |
| 30 Oct | Fair Value snapshot | **Layer-1 metrics**: incremental ROIC (3 years) and R&D ÷ revenue (Business performance); FCF margin trend, stock pay ÷ revenue (and ÷ FCF), capex ÷ depreciation, depreciation ÷ revenue for capital-heavy firms (Cash flow); inventory vs sales growth (Financial strength). Snapshot fetch adds depreciation and R&D | Answers 'are new investments paying off?', 'how much goes to stock pay?', 'more or less cash-generative?' |
| 30 Oct | Fair Value | **Business drivers** (Phase B): 187 company-specific KPIs for 42 stocks, latest vs 1 year, 8-quarter sparkline, trend vs own history, 3-quarter worsening flag, source + quote for every value; MSFT pilot loaded, backfill task fills the rest | Is the business story still on track? |
| 30 Oct | Fair Value | **7 payments companies**: AXP (valued on net income, like a lender), SHOP, PYPL, XYZ (Block, on gross profit), ADYEY (Adyen ADR, EUR converted), FISV (Fiserv), CRCL (Circle); KPI definitions added to the backfill queue. Stripe skipped (private, no share price) | 49 modelled stocks, 51 assets |
| 31 Oct | Automation | **Earnings updates split**: GitHub now rolls each model's numbers forward from Yahoo every day (`scripts/auto_update.py`: keeps hand adjustments, safety checks, review queue); the Claude task runs twice a week and only reads (guidance, assumptions, notes, KPIs) or handles what the script can't; the hourly KPI backfill task is folded into it | Same freshness with far less Claude usage |
