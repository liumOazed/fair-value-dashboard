# Fair Value Dashboard

A static dashboard comparing live-ish prices with estimated fair values (modern Graham framework: normalised earnings power, Bear/Base/Bull, never value on the bull case, margin of safety). Not investment advice.

## One-click setup (about 2 minutes)
1. Create a **public** GitHub repo and upload everything in this folder (keep the `.github` folder and `.nojekyll`).
2. **Settings → Pages → Build and deployment → Source: Deploy from a branch → `main` / `(root)` → Save.**
3. **Actions tab → "Update prices" → Run workflow** once (also enable workflows if GitHub asks).
4. Open `https://<your-username>.github.io/<repo-name>/`.

Prices refresh automatically every weekday after the US close. No keys or secrets are used.

## Growth Screen and Monthly Top 5 (once a month)

1. Upload the new month's CSV to `data/screens/` as `growth_screen_results_YYYY-MM.csv` (Add file → Upload files on GitHub).
2. That upload starts the **Monthly run** workflow automatically. It:
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

To produce the numbers, add or edit the inputs in `model/model.py` (`STOCKS`), run `python model/model.py` (prints fair values, writes `model/results.json`), then `python scripts/export_assets.py TICKER ...` to copy those results into `data/assets.json`. Every modelled stock needs an entry (rate + reason) in `data/required_returns.json`: that one file sets required returns for the Fair Value tab, the Growth Screen and the Monthly Top 5 (stock > theme > sector), so the tabs never disagree. The drawer shows each stock's fair value at 8-12% next to the rate used. Also add a starting price for a new ticker to `data/prices.json` (the daily job then keeps it fresh).

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
