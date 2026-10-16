#!/usr/bin/env python3
"""Estimate missing months between two real screen CSVs by straight-line interpolation.

Example: July and October exist -> writes ..._2026-08_estimated.csv and ..._2026-09_estimated.csv.
* Only stocks present in BOTH real months are estimated (others cannot be bridged).
* Every numeric column is interpolated. Slow metrics (sales growth, margins, ROE) interpolate reasonably;
  price-driven ones (P/E, P/S, FCF yield, EV/EBITDA, market cap) are only rough guesses because prices jump.
* A real CSV for a month always wins: if growth_screen_results_YYYY-MM.csv exists, no estimate is written
  and any old estimate for that month is deleted.
Usage: python scripts/backfill.py            (fills every gap between consecutive real months)
"""
import glob, re, pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIR = ROOT / "data/screens"
def ym(p): return re.search(r"(\d{4})-(\d{2})", p).groups()
def mnum(y, m): return int(y) * 12 + int(m) - 1
def mstr(n): return f"{n // 12}-{n % 12 + 1:02d}"

real = sorted([p for p in glob.glob(str(DIR / "*.csv")) if "_estimated" not in p], key=lambda p: mnum(*ym(p)))
real_months = {mnum(*ym(p)) for p in real}
for p in glob.glob(str(DIR / "*_estimated.csv")):          # a real file replaces its estimate
    if mnum(*ym(p)) in real_months: pathlib.Path(p).unlink(); print("removed estimate (real data exists):", p)
written = 0
for a, b in zip(real, real[1:]):
    ma, mb = mnum(*ym(a)), mnum(*ym(b))
    if mb - ma < 2: continue
    A = pd.read_csv(a).drop_duplicates("ticker").set_index("ticker")
    B = pd.read_csv(b).drop_duplicates("ticker").set_index("ticker")
    common = A.index.intersection(B.index)
    numcols = [c for c in A.columns if c in B.columns and pd.api.types.is_numeric_dtype(A[c]) and pd.api.types.is_numeric_dtype(B[c])]
    for k in range(1, mb - ma):
        w = k / (mb - ma)
        E = B.loc[common].copy()                              # names/sectors from the newer month
        for c in numcols:
            va, vb = A.loc[common, c], B.loc[common, c]
            E[c] = (va * (1 - w) + vb * w).where(va.notna() & vb.notna(), (vb if w >= 0.5 else va)).round(4)
        out = DIR / f"growth_screen_results_{mstr(ma + k)}_estimated.csv"
        E.reset_index().to_csv(out, index=False); written += 1
        print(f"wrote {out.name}: {len(E)} stocks (dropped {len(A.index.union(B.index)) - len(common)} not in both months)")
print("estimates written:", written)
