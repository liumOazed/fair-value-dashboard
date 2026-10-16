# Fair Value Dashboard

A static dashboard comparing live-ish prices with estimated fair values (modern Graham framework: normalised earnings power, Bear/Base/Bull, never value on the bull case, margin of safety). Not investment advice.

## One-click setup (about 2 minutes)
1. Create a **public** GitHub repo and upload everything in this folder (keep the `.github` folder and `.nojekyll`).
2. **Settings → Pages → Build and deployment → Source: Deploy from a branch → `main` / `(root)` → Save.**
3. **Actions tab → "Update prices" → Run workflow** once (also enable workflows if GitHub asks).
4. Open `https://<your-username>.github.io/<repo-name>/`.

Prices refresh automatically every weekday after the US close. No keys or secrets are used.

## Growth Screen tab (monthly)
Each month, add the new screen CSV to `data/screens/` (name it like `growth_screen_results_2026-11.csv`; the month in the name is what counts). A GitHub job (`build-screen.yml`) rebuilds `data/screen.json` automatically, or run `python scripts/build_screen.py` yourself (needs `pandas`). The page shows the latest month versus the previous one.
- **Score v2** is explained at the bottom of the Growth Screen page and in the docstring of `scripts/build_screen.py`. Weights and caps are at the top of that file.
- **Themes** (Hyperscalers, AI chips, ...) live in `data/themes.json`. Edit the lists freely; sectors come from the CSV.
- **Growth priced in** is an indicative reverse DCF, not a fair value. It uses a sector required return (`REQ_RETURN` in `scripts/build_screen.py`, based on Damodaran's Jan-2026 cost of equity + about 1 point). Where free cash flow is distorted (FCF yield under 25% of earnings yield, or a bank/insurer) it uses the earnings yield and shows `FCF distorted` with no verdict; shrinking sales also get no verdict. Only stocks in `data/assets.json` have a full fair value.

## Add a new stock
Open `data/assets.json` and copy one block in `assets`. Required fields: `ticker`, `name`, `type` (`stock`, `etf` or `commodity`), `fair_value`, `bear`, `base`, `bull`, `mos` (margin of safety, e.g. 0.25), `buy_below` (fair value × (1 − mos)), `valued_on`. The rest (`scenarios`, `sensitivity`, `epv`, `implied_return`, `notes`) is optional and only fills the detail panel. Commit. The price script picks the ticker up on its next run (or run the workflow by hand).

To produce the numbers, add or edit the inputs in `model/model.py` (`STOCKS`), run `python model/model.py` (prints fair values, writes `model/results.json`), then `python scripts/export_assets.py TICKER ...` to copy those results into `data/assets.json`. Also add a starting price for a new ticker to `data/prices.json` (the daily job then keeps it fresh).

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
