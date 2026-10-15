# Fair Value Dashboard

A static dashboard comparing live-ish prices with estimated fair values (modern Graham framework: normalised earnings power, Bear/Base/Bull, never value on the bull case, margin of safety). Not investment advice.

## One-click setup (about 2 minutes)
1. Create a **public** GitHub repo and upload everything in this folder (keep the `.github` folder and `.nojekyll`).
2. **Settings → Pages → Build and deployment → Source: Deploy from a branch → `main` / `(root)` → Save.**
3. **Actions tab → "Update prices" → Run workflow** once (also enable workflows if GitHub asks).
4. Open `https://<your-username>.github.io/<repo-name>/`.

Prices refresh automatically every weekday after the US close. No keys or secrets are used.

## Add a new stock
Open `data/assets.json` and copy one block in `assets`. Required fields: `ticker`, `name`, `type` (`stock`, `etf` or `commodity`), `fair_value`, `bear`, `base`, `bull`, `mos` (margin of safety, e.g. 0.25), `buy_below` (fair value × (1 − mos)), `valued_on`. The rest (`scenarios`, `sensitivity`, `epv`, `implied_return`, `notes`) is optional and only fills the detail panel. Commit. The price script picks the ticker up on its next run (or run the workflow by hand).

To produce the numbers, edit the inputs in `model/model.py` (`STOCKS`) and run `python model/model.py`; it prints fair values and writes `model/results.json`.

## Refresh fair values
Fair values are slow-moving. Re-run the model after each earnings report (roughly quarterly), paste the new numbers into `data/assets.json`, commit.

## Files
- `index.html`, `assets/` the dashboard (plain HTML/CSS/JS, no build step)
- `data/assets.json` fair-value inputs, `data/prices.json` latest prices (auto-updated)
- `scripts/update_prices.py` + `.github/workflows/update-prices.yml` daily price job
- `docs/fair_value_model.xlsx` step-by-step calculations (import to Google Sheets via File → Import)

Preview locally: `python -m http.server` then open http://localhost:8000.
