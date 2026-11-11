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
Underwriters (INSURERS in model.py, valued on book value and ROE) use the same regimes and noise on book growth and ROE.
Usage: python model/montecarlo.py [TICKER ...]   (after model.py / export_assets.py; tickers = only write those)
"""
import json, pathlib, sys
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

def moat(tk, r):
    """This stock's advantage period and terminal-return settings (data/moat.json), as model.dcf uses them."""
    sep = M["stock_setup"](tk, M["STOCKS"][tk])["kw"] if tk in M["STOCKS"] else {}
    return dict(M["moat_of"](tk), r_req=r, sg=M["segments_of"](tk), sep=sep)

def tv_k(mo, gt, g_last):
    """Vectorised model.tv_factor (terminal cash flow vs the last explicit year)."""
    if mo.get("ronic_forecast") is None: return np.ones_like(np.asarray(gt, float))
    rf, rq = mo["ronic_forecast"], mo["r_req"]
    rt = rq if mo["ronic_terminal"] == "r" else (rf + rq) / 2 if mo["ronic_terminal"] == "mid" else mo["ronic_terminal"]
    return (1 - gt / rt) / (1 - np.minimum(g_last, 0.9 * rf) / rf)

def inputs(tk):
    s = M["STOCKS"][tk]; r = M["req_return"](tk)
    su = M["stock_setup"](tk, s)                   # same cash-flow separation as model.py
    return s, r, su["m0"], su["S2"], su["nc"]

def separate(fcf, k, rev, rev0, gt, mo):
    """model.dcf's cash-flow separation on simulated paths: lenders keep 1 - g/ROE of profit, acquisition spend is
    charged as reinvestment scaled by growth. Returns the new paths and terminal factor."""
    sep = (mo or {}).get("sep") or {}
    roe, acq = sep.get("roe"), sep.get("acq")
    if not roe and not acq: return fcf, k
    gt = np.broadcast_to(np.asarray(gt, float), (len(fcf),))
    prev = np.concatenate([np.full((len(fcf), 1), rev0), rev[:, :-1]], axis=1)
    g = rev / prev - 1
    gcol = gt[:, None]
    ch = lambda x, gg: (acq[0] * np.minimum(1.0, np.maximum(x - gg, 0.0) / np.maximum(acq[1] - gg, 1e-12)) * (acq[1] > gg)) if acq else 0.0
    base_last = fcf[:, -1]
    if roe:
        rt, rq = mo.get("ronic_terminal"), mo.get("r_req")
        rn = rq if rt == "r" else (roe + rq) / 2 if rt == "mid" else roe
        new = fcf * (1 - g / roe) - rev * ch(g, gcol)
        term = base_last * (1 - gt / rn) - rev[:, -1] * ch(gt, gt)
    else:
        new = fcf - rev * ch(g, gcol)
        term = base_last * k - rev[:, -1] * ch(gt, gt)
    return new, term / new[:, -1]

def _growth(g1, g10, gt, n):
    t = np.arange(1, n + 1)
    g = g1[:, None] + (g10 - g1)[:, None] * (np.minimum(t, 10) - 1) / 9
    if n > 10:
        gt_ = np.broadcast_to(np.asarray(gt, float), g10.shape)
        g = np.where(t > 10, g10[:, None] + (gt_ - g10)[:, None] * (t - 10) / (n - 10), g)
    return g

def paths(rev0, m0, g1, g10, m, gt=None, n=T, sg=None):
    """Cash-flow paths (runs, n years): growth fades linearly from g1 to g10 over years 1-10, then from g10 to the
    terminal rate by year n (the advantage period); margin ramps to target over 5 years. With segments (model.seg_g1s),
    each segment has its own year-1 growth on the same fade. Also returns the last year's growth."""
    t = np.arange(1, n + 1)
    if sg:
        x = np.stack([np.minimum(g1 * q, sg["cap"] * g1) for q in sg["ratio"]], axis=1)       # (runs, segments)
        w = np.array(sg["share"])
        x = x + (g1 - x @ w)[:, None]
        x = np.where((g1 > 0)[:, None], x, g1[:, None])
        rev = sum(rev0 * w[i] * np.cumprod(1 + _growth(x[:, i], g10, gt, n), axis=1) for i in range(len(w)))
        g_last = _growth(g1, g10, gt, n)[:, -1]
    else:
        g = _growth(g1, g10, gt, n)
        rev = rev0 * np.cumprod(1 + g, axis=1)
        g_last = g[:, -1]
    mt = m0 + (m - m0)[:, None] * np.minimum(t, 5) / 5
    return rev * mt, g_last

def paths_k(rev0, m0, g1, g10, m, gt, mo):
    """Cash-flow paths and the terminal factor k per run, as model.dcf. Per-engine stocks (segments with "engines"): each
    engine fades to 2.5% over its own advantage period with its own margin multiple, and carries its class's value-driver
    factor once its period ends (model.dcf_eng); k is then the engines' combined terminal factor."""
    sg = (mo or {}).get("sg")
    if not (sg and sg.get("engines")):
        n = (mo or {}).get("cap_years", T)
        fcf, gl = paths(rev0, m0, g1, g10, m, gt, n, sg)
        k = tv_k(mo, gt, gl) if mo else 1.0
        if not (mo or {}).get("sep"): return fcf, k
        one = np.ones_like(np.asarray(g1, float))
        rev, _ = paths(rev0, 1.0, g1, g10, one, gt, n, sg)          # revenue paths (margin 1)
        return separate(fcf, np.broadcast_to(np.asarray(k, float), (len(fcf),)), rev, rev0, gt, mo)
    E = sg["engines"]; MO = [M["eng_mo"](c, mo) for c in E["moat"]]; caps = [x.get("cap_years", T) for x in MO]
    n = max(caps + [mo.get("cap_years", T)]); t = np.arange(1, n + 1)
    gt_ = np.broadcast_to(np.asarray(gt, float), g10.shape)
    x = np.stack([np.minimum(g1 * q, sg["cap"] * g1) for q in sg["ratio"]], axis=1)
    w = np.array(sg["share"]); x = x + (g1 - x @ w)[:, None]; x = np.where((g1 > 0)[:, None], x, g1[:, None])
    mt = m0 + (m - m0)[:, None] * np.minimum(t, 5) / 5
    fcf = np.zeros((len(g1), n)); term = np.zeros(len(g1)); rev = np.zeros((len(g1), n))
    for i in range(len(w)):
        c = caps[i]
        g = x[:, i][:, None] + (g10 - x[:, i])[:, None] * (np.minimum(t, 10) - 1) / 9
        if c > 10: g = np.where(t > 10, g10[:, None] + (gt_ - g10)[:, None] * (np.minimum(t, c) - 10) / (c - 10), g)
        g = np.where(t > c, gt_[:, None], g)
        ri = rev0 * w[i] * np.cumprod(1 + g, axis=1); rev += ri
        f = ri * mt * E["x"][i]
        ki = tv_k(dict(MO[i], r_req=mo["r_req"]), gt_, g[:, c - 1])
        f = np.where(t > c, f * np.asarray(ki)[..., None] if np.ndim(ki) else f * ki, f)
        fcf += f
        term += f[:, -1] * (ki if c == n else 1.0)
    return separate(fcf, term / fcf[:, -1], rev, rev0, gt, mo)

def pv_paths(fcf, gt, r, nc, shares, k=1.0):
    """Value per share of cash-flow paths; r may be a scalar or one rate per run; k = terminal cash-flow factor."""
    t = np.arange(1, fcf.shape[1] + 1)
    r = np.broadcast_to(np.asarray(r, float), (len(fcf),))
    df = (1 + r[:, None]) ** -t
    tv = fcf[:, -1] * (1 + gt) * k / (r - gt) * df[:, -1]
    return ((fcf * df).sum(axis=1) + tv + nc) / shares

def value(rev0, m0, g1, g10, m, gt, r, nc, shares, mo=None):
    """Vectorised DCF identical to model.dcf."""
    fcf, k = paths_k(rev0, m0, g1, g10, m, gt, mo)
    return pv_paths(fcf, gt, r, nc, shares, k)

def implied_returns(fcf, gt, nc, shares, price, k=1.0, hi=0.60, it=60):
    """Per run: the yearly return that makes that run's cash flows (10 years + value after year 10) cost exactly
    `price` today. Bisection; the value after year 10 needs a return above terminal growth, so the floor is gt + 0.25 pt."""
    lo = gt + 0.0025; a = lo.copy(); b = np.full_like(lo, hi)
    for _ in range(it):
        mid = (a + b) / 2
        up = pv_paths(fcf, gt, mid, nc, shares, k) > price   # still worth more than the price -> return is higher
        a = np.where(up, mid, a); b = np.where(up, b, mid)
    return (a + b) / 2

# ---- underwriters (model.py INSURERS): cash to shareholders = net income - growth in book value; same regimes and noise,
# with g1 / g10 = book-value growth and m = long-run ROE. The value after the last year is book value x (terminal ROE - gt)
# / (r - gt), written as last year's cash x (1 + gt) x k so that pv_paths, implied_returns and hold_returns work unchanged.
def ins_inputs(tk):
    s = M["INSURERS"][tk]; r = M["req_return"](tk)
    return s, r, s["scen"], s["extra"]

def ins_paths(s, r, g1, g10, m, gt, mo):
    n = M["ri_years"](mo)
    t = np.arange(1, n + 1)
    g = _growth(g1, g10, gt, n)
    bv = s["bv"] * np.cumprod(1 + g, axis=1)
    prev = np.concatenate([np.full((len(g1), 1), s["bv"]), bv[:, :-1]], axis=1)
    roe = s["roe0"] + (m - s["roe0"])[:, None] * np.minimum(t, 5) / 5
    cash = roe * prev - (bv - prev)
    rq = mo.get("r_req", r)
    rt = np.where(m <= rq, m, rq if mo["cls"] == "none" else (m + rq) / 2 if mo["cls"] == "narrow" else m)
    return cash, (rt - gt) / (m - gt)

def ins_value(tk, g1, g10, m, gt, r):
    s, rq, _, nc = ins_inputs(tk)
    mo = moat(tk, rq)
    gt = np.broadcast_to(np.asarray(gt, float), np.shape(g1))
    cash, k = ins_paths(s, rq, g1, g10, m, gt, mo)
    return pv_paths(cash, gt, r, nc, s["shares"], k)

def simulate(tk, u, stratify=False, full=False):
    if tk in M.get("INSURERS", {}): return simulate_ins(tk, u, stratify, full)
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
    mo = moat(tk, r)
    fcf, k = paths_k(s["rev"], m0, g1, g10, m, gt, mo)
    v = pv_paths(fcf, gt, r, nc, s["shares"], k)
    if full:
        return v, reg, dict(fcf=fcf, gt=gt, nc=nc, shares=s["shares"], r=r, k=k)
    return v, reg

def simulate_ins(tk, u, stratify=False, full=False):
    s, r, sc, nc = ins_inputs(tk)
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
    g10 = np.minimum(g10, r - 0.01); gt = np.minimum(gt, r - 0.015); m = np.maximum(m, gt + 0.01)
    mo = moat(tk, r)
    cash, k = ins_paths(s, r, g1, g10, m, gt, mo)
    v = pv_paths(cash, gt, r, nc, s["shares"], k)
    if full:
        return v, reg, dict(fcf=cash, gt=gt, nc=nc, shares=s["shares"], r=r, k=k)
    return v, reg

def tornado_ins(tk):
    s, r, sc, nc = ins_inputs(tk)
    b = sc["base"]
    one = lambda **k: float(ins_value(tk, np.array([k.get("g1", b["g1"])]), np.array([k.get("g10", b["g10"])]),
                                      np.array([k.get("m", b["m"])]), k.get("gt", M["GT"]), k.get("r", r))[0])
    base = one()
    rows = [("Year-1 book-value growth", "g1"), ("Long-run book growth (year 10)", "g10"), ("Long-run return on equity", "m")]
    out = [dict(label=l, low=one(**{p: sc["bear"][p]}), high=one(**{p: sc["bull"][p]}),
                low_in=sc["bear"][p], high_in=sc["bull"][p]) for l, p in rows]
    out.append(dict(label="Terminal growth (2% / 3%)", low=one(gt=0.02), high=one(gt=0.03), low_in=0.02, high_in=0.03))
    out.append(dict(label="Required return (+1 / -1 pt)", low=one(r=r + 0.01), high=one(r=r - 0.01), low_in=r + 0.01, high_in=r - 0.01, choice=True))
    for o in out: o["swing"] = abs(o["high"] - o["low"])
    return dict(base=base, rows=sorted(out, key=lambda o: -o["swing"]))

def tornado(tk):
    if tk in M.get("INSURERS", {}): return tornado_ins(tk)
    """Base case; move one input to its bear and bull value (others at base). Sorted by total swing."""
    s, r, m0, sc, nc = inputs(tk)
    b = sc["base"]
    one = lambda **k: float(value(s["rev"], m0, np.array([k.get("g1", b["g1"])]), np.array([k.get("g10", b["g10"])]),
                                  np.array([k.get("m", b["m"])]), k.get("gt", M["GT"]), k.get("r", r), nc, s["shares"], moat(tk, r))[0])
    base = one()
    rows = [("Year-1 growth", "g1"), ("Long-run growth (year 10)", "g10"), ("Target cash margin", "m")]
    out = [dict(label=l, low=one(**{p: sc["bear"][p]}), high=one(**{p: sc["bull"][p]}),
                low_in=sc["bear"][p], high_in=sc["bull"][p]) for l, p in rows]
    out.append(dict(label="Terminal growth (2% / 3%)", low=one(gt=0.02), high=one(gt=0.03), low_in=0.02, high_in=0.03))
    out.append(dict(label="Required return (+1 / -1 pt)", low=one(r=r + 0.01), high=one(r=r - 0.01), low_in=r + 0.01, high_in=r - 0.01, choice=True))
    for o in out: o["swing"] = abs(o["high"] - o["low"])
    return dict(base=base, rows=sorted(out, key=lambda o: -o["swing"]))

def hold_returns(fcf, gt, nc, shares, price, r, k=1.0, H=T, lo=-0.6, hi=0.8, it=60):
    """Per run: yearly return if you buy at `price`, collect H years of cash flow and sell at the end of year H at the
    price that gives the next buyer the required return r (the gap closes in year H). At return = r this is exactly the
    model value, so 'return beats r' <=> 'value at r beats price'. Can be negative. When H is beyond the advantage period,
    the years in between are the terminal cash flows (last year x k, growing at gt)."""
    n = fcf.shape[1]
    gt_ = np.broadcast_to(np.asarray(gt, float), (len(fcf),))
    k_ = np.broadcast_to(np.asarray(k, float), (len(fcf),))
    if H > n:                                          # extend with the terminal cash flows up to year H
        F = np.concatenate([fcf, fcf[:, -1:] * k_[:, None] * (1 + gt_[:, None]) ** np.arange(1, H - n + 1)], axis=1)
        k_after = 1.0
    else:
        F, k_after = fcf, k_
    L_ = F.shape[1]                                    # sale value at the end of year H: years H+1..L + terminal, at r
    exit_ = F[:, -1] * (1 + gt_) * k_after / (r - gt_) / (1 + r) ** (L_ - H)
    if L_ > H: exit_ = exit_ + (F[:, H:] * (1 + r) ** -np.arange(1, L_ - H + 1)).sum(axis=1)
    t = np.arange(1, H + 1)
    fH = F[:, :H]
    def val(x):
        df = (1 + x[:, None]) ** -t
        return ((fH * df).sum(axis=1) + exit_ * df[:, -1] + nc) / shares
    a = np.full(len(fcf), lo); b = np.full(len(fcf), hi)
    for _ in range(it):
        mid = (a + b) / 2
        up = val(mid) > price
        a = np.where(up, mid, a); b = np.where(up, b, mid)
    return (a + b) / 2

HORIZONS = (5, 20)                                     # extra holding periods for "My horizon" -> data/mc_horizon.json
HZ_PATH = ROOT / "data/mc_horizon.json"

def main():
    path = ROOT / "data/assets.json"
    doc = json.load(open(path))
    rng = np.random.default_rng(SEED)
    hz = json.load(open(HZ_PATH)) if HZ_PATH.exists() else {}
    hz.update(_about="Yearly return at 17 prices (multiples of fair value) for a 5- and a 20-year hold, per case: 21 quantiles "
                     "(step 5%) of the runs, the same runs as hold10 in data/assets.json. Read by the page for My horizon. "
                     "Built by model/montecarlo.py.", quantiles_step=0.05)
    hz.setdefault("stocks", {})
    only = set(sys.argv[1:])          # optional: only write these tickers (every modelled stock still draws its runs, so results match a full run)
    for a in doc["assets"]:
        tk = a["ticker"]
        if tk not in M["STOCKS"] and tk not in M.get("INSURERS", {}):
            continue
        u = rng.random((N, 5))
        if only and tk not in only:
            continue
        v, reg, X = simulate(tk, u, stratify=True, full=True)
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
        irr = {k: [] for k in KEYS}; hold = {k: [] for k in KEYS}; hx = {h: {k: [] for k in KEYS} for h in HORIZONS}
        for gmul in grid:
            ir = implied_returns(X["fcf"], X["gt"], X["nc"], X["shares"], gmul * a["fair_value"], X["k"])
            hr = hold_returns(X["fcf"], X["gt"], X["nc"], X["shares"], gmul * a["fair_value"], X["r"], X["k"])
            hh = {h: hold_returns(X["fcf"], X["gt"], X["nc"], X["shares"], gmul * a["fair_value"], X["r"], X["k"], H=h) for h in HORIZONS}
            for i, k in enumerate(KEYS):
                irr[k].append([round(float(x), 4) for x in np.quantile(ir[reg == i], q21)])
                hold[k].append([round(float(x), 4) for x in np.quantile(hr[reg == i], q21)])
                for h in HORIZONS:
                    hx[h][k].append([round(float(x), 4) for x in np.quantile(hh[h][reg == i], q21)])
        hz["stocks"][tk] = dict(price_multiples=grid, fair_value=a["fair_value"], **{f"hold{h}": hx[h] for h in HORIZONS})
        a["mc"]["irr"] = dict(price_multiples=grid, fair_value=a["fair_value"], quantiles_step=0.05, regimes=irr, hold10=hold,
                              note="Per run: the yearly return that makes that run's cash flows plus the value after year 10 equal the price. "
                                   "Floor = terminal growth + 0.25 pt, cap 60%.")
        a["mc"]["tornado"]["rows"] = [{k: (round(x, 4) if isinstance(x, float) else x) for k, x in o.items()} for o in a["mc"]["tornado"]["rows"]]
        print(f"{tk:5} FV {a['fair_value']:9.2f}  MC mean {a['mc']['mean']:9.2f}  p10 {a['mc']['p10']:9.2f}  p50 {a['mc']['p50']:9.2f}  p90 {a['mc']['p90']:9.2f}"
              f"  | Sobol p50 {a['mc']['sobol']['p50']:9.2f} ({a['mc']['sobol']['p50'] / a['mc']['p50'] - 1:+.2%})")
    json.dump(doc, open(path, "w"), indent=1)
    json.dump(hz, open(HZ_PATH, "w"), separators=(",", ":"))

if __name__ == "__main__":
    main()
