#!/usr/bin/env python3
"""Monthly run with a once-per-month lock (data/runs.json).

  python scripts/monthly.py --step growth        "Calculate Top Growth": backfill gaps, score, rank, Top 50
  python scripts/monthly.py --step fair_value    "Evaluate Fair Value": pick the month's 5 most undervalued stocks
  python scripts/monthly.py --step both          growth, then fair value (what the 1st-of-month schedule runs)
  add --force to re-run a month that is already done (e.g. after fixing that month's CSV)

The lock is per DATA month (the newest real CSV in data/screens/). A second run for the same month does nothing and
says so. If the calendar has moved on but the new month's CSV has not been uploaded yet, nothing runs and it tells you
to upload it. Scored months are cached in data/cache/, so earlier months are never recalculated.
"""
import argparse, datetime, glob, json, os, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "data/runs.json"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
def nice(m): y, mm = m.split("-"); return f"{MONTHS[int(mm) - 1]} {y}"
def note(msg, kind="notice"):
    print(msg)
    if os.environ.get("GITHUB_ACTIONS"): print(f"::{kind}::{msg}")
    s = os.environ.get("GITHUB_STEP_SUMMARY")
    if s: open(s, "a").write(f"- {msg}\n")
def run(*cmd): subprocess.run([sys.executable, *cmd], cwd=ROOT, check=True)

ap = argparse.ArgumentParser(); ap.add_argument("--step", choices=["growth", "fair_value", "both"], default="both"); ap.add_argument("--force", action="store_true")
a = ap.parse_args()
real = [re.search(r"(\d{4}-\d{2})", p).group(1) for p in glob.glob(str(ROOT / "data/screens/*.csv")) if "_estimated" not in p]
if not real: sys.exit("No CSVs in data/screens/")
month = max(real)
today = datetime.datetime.now(datetime.timezone.utc)
cal = today.strftime("%Y-%m")
try: runs = json.load(open(RUNS))
except Exception: runs = {}
runs.setdefault("growth", {}); runs.setdefault("fair_value", {})
if cal > month and month in runs["growth"] and not a.force:
    note(f"No CSV for {nice(cal)} yet. Upload data/screens/growth_screen_results_{cal}.csv, then run again.", "warning")
changed = False
def stamp(): return dict(ran=today.strftime("%Y-%m-%d %H:%M UTC"), calendar_month=cal, forced=a.force, by=os.environ.get("GITHUB_ACTOR", "local"))

if a.step in ("growth", "both"):
    if month in runs["growth"] and not a.force:
        note(f"Top Growth already calculated for {nice(month)} (on {runs['growth'][month]['ran']}). Nothing to do.")
    else:
        run("scripts/backfill.py"); run("scripts/build_screen.py")
        runs["growth"][month] = stamp(); changed = True
        note(f"Calculated Top Growth for {nice(month)}.")
if a.step in ("fair_value", "both"):
    if month not in runs["growth"]:
        note(f"Run Calculate Top Growth for {nice(month)} first.", "warning")
    elif month in runs["fair_value"] and not a.force:
        note(f"Fair Value already evaluated for {nice(month)} (on {runs['fair_value'][month]['ran']}). Nothing to do.")
    else:
        run("scripts/fair_value_table.py")
        picks = json.load(open(ROOT / "data/fair_value_table.json"))["months"][month]["picks"]
        runs["fair_value"][month] = dict(stamp(), picks=[p["ticker"] for p in picks]); changed = True
        note(f"Evaluated Fair Value for {nice(month)}: {', '.join(p['ticker'] for p in picks)}.")
if changed:
    runs["latest_data_month"] = month
    json.dump(runs, open(RUNS, "w"), indent=1)
