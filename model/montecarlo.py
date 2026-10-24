#!/usr/bin/env python3
"""Monte Carlo layer on top of the DCF in model/model.py (P1).

Design (agreed 2026-10-23):
  * Regimes: each simulation first draws Bear / Base / Bull with the model's 30 / 50 / 20 weights (the scenario
    probabilities are used ONCE, here), then adds correlated noise around that regime's assumptions.
  * Noise: year-1 growth, year-10 growth and the target cash margin move together (correlation 0.5 / 0.5 / 0.3);
    each standard deviation is 1/8 of the bear-to-bull spread, so regimes overlap a little but stay distinct.
    Terminal growth is drawn around 2.5% (sd 0.4%, kept between 1% and 3.5%).
  * Fixed on purpose: the required return (a choice, not an uncertainty), starting revenue and margin, net debt, shares.
  * Same engine as model.py: free cash flow before interest at the required return, minus net debt.
  * 20,000 runs, seed 20261023 (reproducible). A Sobol (quasi-Monte Carlo) run is done as a convergence check only.
Outputs per stock (written into data/assets.json under "mc"): 101 quantiles of value per share (the page turns them
into model-implied probabilities against the live price), percentiles, regime shares, a one-at-a-time sensitivity
(tornado) on the base case, and the Sobol check.
The probabilities are MODEL-IMPLIED: only as good as the assumption ranges above.
Usage: python model/montecarlo.py   (after model.py / export_assets.py)
"""
import json, pathlib
import numpy as np
from scipy.stats import qmc, norm

ROOT = pathlib.Path(__file__).resolve().parent.parent
src = (ROOT / "model/model.py").read_text().split("out = {")[0]
M = {"__file__": str(ROOT / "model/model.py")}
exec(src, M)                                      # STOCKS, FIN, PROBS, GT, req_return, dcf, DCF_METHOD
N, SEED, T = 20000, 20261023, 10
CORR = np.array([[1.0, 0.5, 0.5], [0.5, 1.0, 0.3], [0.5, 0.3, 1.0]])
L = np.linalg.cholesky(CORR)
KEYS = ["bear", "base", "bull"]

def inputs(tk):
    s = M["STOCKS"][tk]; f = M["FIN"][tk]; r = M["req_return"](tk)
    aint = 0.0 if M["DCF_METHOD"] == "equity" else f["interest"] * (1 - f["tax"])
    add = aint / s["rev"]
    m0 = (s["fcf"] - s["sbc"] + aint) / s["rev"]
    sc = {k: dict(v, m=v["m"] + add) for k, v in s["scen"].items()}
    return s, r, m0, sc, s["net_cash"] + s["extra"]

def paths(rev0, m0, g1, g10, m):
    """Cash-flow paths (n, 10): growth fades linearly from year 1 to year 10, margin ramps to target over 5 years."""
    t = np.arange(1, T + 1)
    g = g1[:, None] + (g10 - g1)[:, None] * (t - 1) / 9
    rev = rev0 * np.cumprod(1 + g, axis=1)
    mt = m0 + (m - m0)[:, None] * np.minimum(t, 5) / 5
    return rev * mt

def pv_paths(fcf, gt, r, nc, shares):
    """Value per share of cash-flow paths; r may be a scalar or one rate per run."""
    t = np.arange(1, T + 1)
    r = np.broadcast_to(np.asarray(r, float), (len(fcf),))
    df = (1 + r[:, None]) ** -t
    tv = fcf[:, -1] * (1 + gt) / (r - gt) * df[:, -1]
    return ((fcf * df).sum(axis=1) + tv + nc) / shares

def value(rev0, m0, g1, g10, m, gt, r, nc, shares):
    """Vectorised DCF identical to model.dcf."""
    return pv_paths(paths(rev0, m0, g1, g10, m), gt, r, nc, shares)

def implied_returns(fcf, gt, nc, shares, price, hi=0.60, it=60):
    """Per run: the yearly return that makes that run's cash flows (10 years + value after year 10) cost exactly
    `price` today. Bisection; the value after year 10 needs a return above terminal growth, so the floor is gt + 0.25 pt."""
    lo = gt + 0.0025; a = lo.copy(); b = np.full_like(lo, hi)
    for _ in range(it):
        mid = (a + b) / 2
        up = pv_paths(fcf, gt, mid, nc, shares) > price      # still worth more than the price -> return is higher
        a = np.where(up, mid, a); b = np.where(up, b, mid)
    return (a + b) / 2

def simulate(tk, u, stratify=False, full=False):
    """u: (n, 5) uniforms -> regime, 3 correlated shocks, terminal growth.
    stratify=True gives each regime exactly its weight in runs (30/50/20), so the page can re-weight regimes exactly."""
    s, r, m0, sc, nc = inputs(tk)
    n = len(u)
    if stratify:
        cnt = [round(M["PROBS"][k] * n) for k in KEYS]; cnt[1] = n - cnt[0] - cnt[2]
        reg = np.repeat(np.arange(3), cnt)
    else:
        cum = np.cumsum([M["PROBS"][k] for k in KEYS])
        reg = np.minimum(np.searchsorted(cum, u[:, 0] * cum[-1]), 2)
    z = norm.ppf(np.clip(u[:, 1:4], 1e-9, 1 - 1e-9)) @ L.T
    P = {p: np.array([sc[k][p] for k in KEYS]) for p in ("g1", "g10", "m")}
    sd = {p: max((P[p][2] - P[p][0]) / 8, 0.002) for p in P}
    g1 = P["g1"][reg] + z[:, 0] * sd["g1"]
    g10 = P["g10"][reg] + z[:, 1] * sd["g10"]
    m = P["m"][reg] + z[:, 2] * sd["m"]
    gt = np.clip(M["GT"] + norm.ppf(np.clip(u[:, 4], 1e-9, 1 - 1e-9)) * 0.004, 0.01, 0.035)
    g10 = np.minimum(g10, r - 0.01); gt = np.minimum(gt, r - 0.015); m = np.maximum(m, 0.005)
    fcf = paths(s["rev"], m0, g1, g10, m)
    v = pv_paths(fcf, gt, r, nc, s["shares"])
    if full:
        return v, reg, dict(fcf=fcf, gt=gt, nc=nc, shares=s["shares"], r=r)
    return v, reg

def tornado(tk):
    """Base case; move one input to its bear and bull value (others at base). Sorted by total swing."""
    s, r, m0, sc, nc = inputs(tk)
    b = sc["base"]
    one = lambda **k: float(value(s["rev"], m0, np.array([k.get("g1", b["g1"])]), np.array([k.get("g10", b["g10"])]),
                                  np.array([k.get("m", b["m"])]), k.get("gt", M["GT"]), k.get("r", r), nc, s["shares"])[0])
    base = one()
    rows = [("Year-1 growth", "g1"), ("Long-run growth (year 10)", "g10"), ("Target cash margin", "m")]
    out = [dict(label=l, low=one(**{p: sc["bear"][p]}), high=one(**{p: sc["bull"][p]}),
                low_in=sc["bear"][p], high_in=sc["bull"][p]) for l, p in rows]
    out.append(dict(label="Terminal growth (2% / 3%)", low=one(gt=0.02), high=one(gt=0.03), low_in=0.02, high_in=0.03))
    out.append(dict(label="Required return (+1 / -1 pt)", low=one(r=r + 0.01), high=one(r=r - 0.01), low_in=r + 0.01, high_in=r - 0.01, choice=True))
    for o in out: o["swing"] = abs(o["high"] - o["low"])
    return dict(base=base, rows=sorted(out, key=lambda o: -o["swing"]))

def hold_returns(fcf, gt, nc, shares, price, r, lo=-0.6, hi=0.8, it=60):
    """Per run: yearly return if you buy at `price`, collect 10 years of cash flow and sell at the end of year 10 at the
    price that gives the next buyer the required return r (the gap closes in year 10). At return = r this is exactly the
    model value, so 'return beats r' <=> 'value at r beats price'. Can be negative."""
    t = np.arange(1, T + 1)
    exit_ = fcf[:, -1] * (1 + gt) / (r - gt)
    def val(x):
        df = (1 + x[:, None]) ** -t
        return ((fcf * df).sum(axis=1) + exit_ * df[:, -1] + nc) / shares
    a = np.full(len(fcf), lo); b = np.full(len(fcf), hi)
    for _ in range(it):
        mid = (a + b) / 2
        up = val(mid) > price
        a = np.where(up, mid, a); b = np.where(up, b, mid)
    return (a + b) / 2

def main():
    path = ROOT / "data/assets.json"
    doc = json.load(open(path))
    rng = np.random.default_rng(SEED)
    for a in doc["assets"]:
        tk = a["ticker"]
        if tk not in M["STOCKS"]:
            continue
        v, reg, X = simulate(tk, rng.random((N, 5)), stratify=True, full=True)
        sob = qmc.Sobol(d=5, scramble=True, seed=SEED).random_base2(m=14)        # 16,384 points
        vs, _ = simulate(tk, sob)
        q = np.quantile(v, np.linspace(0, 1, 101))
        pc = lambda x, p: float(np.percentile(x, p))
        a["mc"] = dict(
            n=N, seed=SEED, method=M["DCF_METHOD"], quantiles=[round(float(x), 2) for x in q],
            p10=round(pc(v, 10), 2), p25=round(pc(v, 25), 2), p50=round(pc(v, 50), 2), p75=round(pc(v, 75), 2), p90=round(pc(v, 90), 2),
            mean=round(float(v.mean()), 2), regime_share={k: round(float((reg == i).mean()), 3) for i, k in enumerate(KEYS)},
            sobol=dict(n=len(sob), p10=round(pc(vs, 10), 2), p50=round(pc(vs, 50), 2), p90=round(pc(vs, 90), 2)),
            tornado={k: (round(x, 2) if isinstance(x, float) else x) for k, x in tornado(tk).items()},
            note="Model-implied: Bear/Base/Bull drawn 30/50/20 with correlated noise on growth and margin; required return fixed.")
        # per-regime distributions (the page re-weights them for the what-if weights)
        q101 = np.linspace(0, 1, 101); q21 = np.linspace(0, 1, 21)
        a["mc"]["regimes"] = {k: dict(weight=M["PROBS"][k], mean=round(float(v[reg == i].mean()), 2), quantiles=[round(float(x), 2) for x in np.quantile(v[reg == i], q101)])
                              for i, k in enumerate(KEYS)}
        # implied yearly return at a grid of prices (multiples of fair value); the page interpolates at the live price
        grid = [round(float(x), 4) for x in np.exp(np.linspace(np.log(0.3), np.log(3.0), 17))]
        irr = {k: [] for k in KEYS}; hold = {k: [] for k in KEYS}
        for gmul in grid:
            ir = implied_returns(X["fcf"], X["gt"], X["nc"], X["shares"], gmul * a["fair_value"])
            hr = hold_returns(X["fcf"], X["gt"], X["nc"], X["shares"], gmul * a["fair_value"], X["r"])
            for i, k in enumerate(KEYS):
                irr[k].append([round(float(x), 4) for x in np.quantile(ir[reg == i], q21)])
                hold[k].append([round(float(x), 4) for x in np.quantile(hr[reg == i], q21)])
        a["mc"]["irr"] = dict(price_multiples=grid, fair_value=a["fair_value"], quantiles_step=0.05, regimes=irr, hold10=hold,
                              note="Per run: the yearly return that makes that run's cash flows plus the value after year 10 equal the price. "
                                   "Floor = terminal growth + 0.25 pt, cap 60%.")
        a["mc"]["tornado"]["rows"] = [{k: (round(x, 4) if isinstance(x, float) else x) for k, x in o.items()} for o in a["mc"]["tornado"]["rows"]]
        print(f"{tk:5} FV {a['fair_value']:9.2f}  MC mean {a['mc']['mean']:9.2f}  p10 {a['mc']['p10']:9.2f}  p50 {a['mc']['p50']:9.2f}  p90 {a['mc']['p90']:9.2f}"
              f"  | Sobol p50 {a['mc']['sobol']['p50']:9.2f} ({a['mc']['sobol']['p50'] / a['mc']['p50'] - 1:+.2%})")
    json.dump(doc, open(path, "w"), indent=1)

if __name__ == "__main__":
    main()
