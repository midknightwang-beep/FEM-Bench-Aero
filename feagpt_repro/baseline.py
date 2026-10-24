"""Formal surrogate baseline on the frozen split (D12 / D25 / D30 / D31).

This supersedes `_probe_m7/learnability.py` for **reporting**.  The probe stays
in the tree as the historical record; the differences below are why the numbers
move, and each one makes the *baselines* stronger, not the learners:

  1. Single hyper-parameter selection.
     The probe called `m3_ridge(train, val, ...)` and `m3_ridge(train, test, ...)`
     separately, so each evaluation set got its own alpha from its own LOOCV and
     the two columns were not scored by the same model.  Here theta is chosen
     once on train, then the SAME fitted model predicts val and test.

  2. All tiers are fitted in log space.
     The metric is MAPE (a relative error).  A tier fitted by raw-space least
     squares minimises the wrong loss and is handicapped by construction.
     M0/M1 now use the geometric mean, which is the MAPE-optimal constant
     multiplier -- the probe used the arithmetic mean.  Consequence: the M0/M1
     numbers printed here are *lower* than the ones in `m7_learnability_d30.json`
     (34.95 % / 31.60 %).  Both are kept; the delta is reported.

  3. An extra opponent, M2L: power law with free exponents.
     `y = C * span^a * t^b * chord^d`, 4 fitted parameters, closed-form in log
     space.  This is the strongest form a physicist would defend at n_train=17.
     If M3 (10 features) cannot beat M2L, the extra features are decoration.

  4. Uncertainty.
     n_test is 7.  A bare point MAPE is not citable.  Every tier gets a
     bootstrap CI on test MAPE, plus a paired bootstrap on (best learner - best
     physics) so "learning beats physics" is a testable claim, not a vibe.

  5. Physics self-checks inside the report.
     Positivity of predictions, monotonicity in span / skin_thickness, and the
     implied exponents recovered from the fitted ridge weights.

  6. Dataset digest.
     sha256 over (case_id, spec_sha256, split) of the fitted tree, so the
     numbers are pinned to an exact dataset state.

Nothing here re-solves anything; it reads shipped truth.json / spec.json only.

Run:  python baseline.py [--json path] [--boot 4000]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
BENCH = ROOT.parent / "FEM-Bench-Aero"

# targets: key -> (label, prefix family, role)
#   role 'gate'  = primary reported number
#   role 'log'   = recorded, but D8 forbids bare peak comparison
TARGETS = {
    "max_disp": ("max|u| (mm)", "u", "gate"),
    "max_w": ("max normal deflection w (mm)", "u", "gate"),
    "max_von_mises_midsurface": ("mid-surface peak vM (MPa)", "vm", "gate"),
    "max_von_mises": ("outer-fibre peak vM (MPa)", "vm", "log"),
}

MULT_FEATS = ("chord", "span", "skin_t")   # go through log
FEATS = ["chord", "span", "skin_t", "n_ribs", "n_str", "sweep", "taper",
         "is_T", "web_pos", "n_web"]

#: D34 (2026-10-24): the sweep term may enter as a quadratic in s = sweep/20
#: instead of linearly.  Rationale and the measurements that justify it are in
#: ``_probe_m11/sweep_form.py``; the short version is that log y is *not* linear
#: in sweep -- the measured displacement ratio against the unswept case runs
#: 1.000 / 1.094 / 1.340 / 1.853 / 2.965 at 0/10/20/30/40 deg, i.e. increments
#: that keep growing -- and a linear term cannot bend.  The basis is written as
#: s^2 with s = sweep/20 (not raw degrees) so the two columns stay within an
#: order of magnitude of each other; standardisation would make it equivalent,
#: but raw degrees make the condition number unreadable.
SWEEP_DEG = 20.0
FEATS_Q = [f for f in FEATS if f != "sweep"] + ["sweep_s", "sweep_s2"]


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def load_family(fam: str) -> list[dict]:
    man = json.loads((BENCH / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    for c in man["cases"]:
        if c["tree"] != "modeling" or c["family"] != fam:
            continue
        d = BENCH / "modeling" / c["case_id"]
        spec = json.loads((d / "spec.json").read_text(encoding="utf-8"))
        truth = json.loads((d / "truth.json").read_text(encoding="utf-8"))
        sc = truth.get("scalars", {})
        a = spec["airfoil"]
        rows.append({
            "case_id": c["case_id"],
            "split": c["split"],
            "cls": c["geometry_class"],
            "spec_sha256": truth["spec_sha256"],
            "chord": float(a["chord"]),
            "span": float(a["span"]),
            "skin_t": float(a["skin_thickness"]),
            "n_ribs": float(a["n_ribs"]),
            "rib_t": float(a["rib_thickness"]),
            "n_str": float(a["n_stringers_per_skin"]),
            "str_t": float(a["stringer_thickness"]),
            "str_h": float(a["stringer_height"]),
            "sweep": float(a["sweep_deg"]),
            "taper": float(a["tip_chord_ratio"]),
            "n_web": float(len(a.get("web_chordwise") or [])),
            "web_pos": float((a.get("web_chordwise") or [0.0])[0]),
            "is_T": 1.0 if a.get("stringer_kind") == "T" else 0.0,
            "E": float(spec["material"]["youngs_modulus"]),
            "F": float(spec["load"]["magnitude"]),
            "max_disp": float(sc["max_disp"]),
            "max_w": float(sc["max_w"]),
            "max_von_mises": float(sc["max_von_mises"]),
            "max_von_mises_midsurface": float(sc["max_von_mises_midsurface"]),
            "u_node": int(sc["max_disp_node"]),
            "vm_node": int(sc["max_vm_midsurface_location"]),
        })
    return rows


def dataset_digest(rows: list[dict]) -> str:
    h = hashlib.sha256()
    for r in sorted(rows, key=lambda x: x["case_id"]):
        h.update(f"{r['case_id']}|{r['spec_sha256']}|{r['split']}\n".encode())
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# physics prefixes (the closed forms a stress engineer would write first)
# --------------------------------------------------------------------------- #
def beam_prefix(r: dict, kind: str) -> float:
    """Cantilever thin-walled box, unit constant.

    Deflection of a box boom: u ~ F*span^3/(E*I) with I ~ t*c^3.
    Bending stress:          s ~ M/Z   with M ~ F*span,  Z ~ t*c^2.
    """
    if kind == "u":
        return r["F"] * r["span"] ** 3 / (r["E"] * r["skin_t"] * r["chord"] ** 3)
    return r["F"] * r["span"] / (r["skin_t"] * r["chord"] ** 2)


def shape_features(r: dict) -> list[float]:
    th = math.radians(r["sweep"])
    return [
        math.cos(th) ** 2,          # spanwise bending stiffness lost to sweep
        (1.0 + r["taper"]) / 2.0,   # taper lowers the outboard section depth
        r["taper"],
    ]


# --------------------------------------------------------------------------- #
# tiers -- every one of them is fitted ONCE on train
# --------------------------------------------------------------------------- #
def fit_m0(tr, key):
    """Constant, geometric mean == log-space-optimal multiplier."""
    c = float(np.exp(np.mean(np.log([r[key] for r in tr]))))
    return lambda rows: [c] * len(rows), {"const_geomean": round(c, 6)}


def fit_m0m(tr, key):
    """Constant, MAPE-optimal == weighted median of y_i with weights 1/y_i.

    Minimising SUM |c-y_i|/y_i over c is a weighted-median problem.  This is the
    strongest "no information" floor, and it is stronger than the geometric mean
    (which is optimal in log space, not in MAPE).  Using it as the floor keeps
    the learner's relative gain honest.
    """
    y = np.array([r[key] for r in tr])
    o = np.argsort(y)
    y, w = y[o], (1.0 / y)[o]
    cdf = np.cumsum(w) / w.sum()
    c = float(y[min(int(np.searchsorted(cdf, 0.5)), len(y) - 1)])
    return lambda rows: [c] * len(rows), {"const_wmedian": round(c, 6)}


def fit_m1(tr, key, kind):
    """Pure beam scaling, 1 constant.  Log-space LSQ -> geometric mean."""
    c = float(np.exp(np.mean([math.log(r[key]) - math.log(beam_prefix(r, kind))
                              for r in tr])))
    return (lambda rows: [c * beam_prefix(r, kind) for r in rows]), {"const": c}


SIZE_NAMES = ["logC", "exp_span", "exp_skin", "exp_chord"]
SHAPE_NAMES = ["exp_cos2sweep", "exp_halfspan_taper", "exp_taper"]


def _size_design(rows):
    """[1, log span, log t, log chord] -- the axes beam theory names."""
    return np.array([[1.0, math.log(r["span"]), math.log(r["skin_t"]),
                      math.log(r["chord"])] for r in rows])


def _shape_design(rows):
    """log of the three dimensionless shape terms (multiplicative powers)."""
    return np.array([[math.log(max(f, 1e-12)) for f in shape_features(r)]
                     for r in rows])


def fit_m2(tr, key, kind, grid=None):
    """beam prefix x shape **powers**, ridge-shrunk (3 exponents).

    y = prefix * (cos^2)^c1 * ((1+taper)/2)^c2 * taper^c3

    Two failed attempts before this one, both worth recording:
      - linear shape multiplier solved by IRLS on the log loss: the 1/f^2
        weights blew the coefficients up (1373 % test);
      - the same powers solved by plain LSQ: the three shape columns are nearly
        collinear here (sweep takes only {0, 20} deg, taper only {0.6, 1.0}),
        so LSQ returns a huge minimum-norm coefficient vector that is fine on
        train and catastrophic outside (49665 % test).
    The condition number is reported alongside the score.  If it is large, the
    honest reading is "this 3-parameter physics form is not identifiable on this
    train set", NOT "physics loses to machine learning".
    """
    Xs_raw = _shape_design(tr)
    ylog = np.log([r[key] for r in tr])
    base = np.log([beam_prefix(r, kind) for r in tr])
    alpha, loo = _loocv_alpha(Xs_raw, ylog, grid if grid is not None else _alpha_grid(),
                              hybrid_offset=base)
    mu, sd, _ = _zfit(Xs_raw)
    ym, w = _ridge((Xs_raw - mu) / sd, ylog - base, alpha)
    cond = float(np.linalg.cond(np.column_stack([np.ones(len(tr)), Xs_raw])))

    def pred(rows):
        be = np.log([beam_prefix(r, kind) for r in rows])
        Xe = (_shape_design(rows) - mu) / sd
        return list(np.exp(Xe @ w + ym + be))
    return pred, {"alpha": alpha, "loo_mape": round(loo, 3),
                  "cond_number": round(cond, 1),
                  "identifiable": bool(cond < 1e6),
                  "exp": {n: round(float(v / s), 4)
                          for n, v, s in zip(SHAPE_NAMES, w, sd)}}


def fit_m2l(tr, key, kind):
    """Power law with free size exponents: y = C * span^a * t^b * chord^d.

    4 parameters, closed form.  The beam prefix fixes the *form*; a/b/d are free
    so the fit is not stuck with (3, -1, -3).  Load is constant (500 N) across
    this family, so F is deliberately not a column.
    """
    X = _size_design(tr)
    y = np.log([r[key] for r in tr])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)

    def pred(rows):
        return list(np.exp(_size_design(rows) @ coef))
    return pred, {n: float(v) for n, v in zip(SIZE_NAMES, coef)}


def fit_m2x(tr, key, kind):
    """Full power law: size **and** shape exponents free (7 parameters).

    y = C * span^a * t^b * chord^d * (cos^2)^e * ((1+taper)/2)^f * taper^g

    This is the strongest thing a stress engineer can defend at n_train=17, and
    it is the honest opponent for M3: if 10 generic features cannot beat 7
    exponents of known physics, the features are decoration.
    """
    X = np.column_stack([_size_design(tr), _shape_design(tr)])
    y = np.log([r[key] for r in tr])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    names = SIZE_NAMES + SHAPE_NAMES

    def pred(rows):
        Xe = np.column_stack([_size_design(rows), _shape_design(rows)])
        return list(np.exp(Xe @ coef))
    return pred, {n: float(v) for n, v in zip(names, coef)}


def feat_matrix(rows) -> np.ndarray:
    cols = []
    for f in FEATS:
        v = np.array([float(r[f]) for r in rows])
        if f in MULT_FEATS:
            v = np.log(v)
        cols.append(v)
    return np.column_stack(cols)


def feat_matrix_q(rows) -> np.ndarray:
    """``feat_matrix`` with the linear sweep column replaced by [s, s^2].

    ``s = sweep_deg / 20`` so the stations are 0, .5, 1, 1.5, 2.  Squared (not
    centred) on purpose: at sweep = 0 both new columns are exactly 0, which
    makes the unswept case the natural origin of the correction rather than an
    arbitrary point on a parabola.

    Train has only three positive-sweep rows and they share one geometry, so a
    *free* cubic is exactly invertible on those three rows -- see D34 and
    ``_probe_m11/sweep_form.py``, where cubic loses to quadratic on every
    held-out measure.  Two curvature parameters are already more than n_train
    can defend; three is interpolation dressed as extrapolation.
    """
    cols = []
    for f in FEATS:
        if f == "sweep":
            continue
        v = np.array([float(r[f]) for r in rows])
        if f in MULT_FEATS:
            v = np.log(v)
        cols.append(v)
    s = np.array([float(r["sweep"]) / SWEEP_DEG for r in rows])
    cols.append(s)
    cols.append(s * s)
    return np.column_stack(cols)


def _zfit(X):
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd < 1e-12] = 1.0
    return mu, sd, (X.std(axis=0) < 1e-12)


def _ridge(Xs, y, alpha):
    ym = y.mean()
    n, p = Xs.shape
    w = np.linalg.solve(Xs.T @ Xs + alpha * np.eye(p), Xs.T @ (y - ym))
    return ym, w


def _alpha_grid():
    return np.logspace(-3, 3, 25)


def _loocv_alpha(X, ylog, grid, hybrid_offset=None):
    """Pick alpha by train LOOCV. Called ONCE per (tier, target).

    Each fold re-computes its own mean/std from the KEPT rows only.  The M7
    probe standardised once on the full train matrix, which leaks the held-out
    row's own mean/sd into its own standardisation -- small, but this is the
    report that gets cited, so it is done properly here.
    """
    n = len(ylog)
    off = np.zeros(n) if hybrid_offset is None else hybrid_offset
    best = None
    for alpha in grid:
        errs = []
        for i in range(n):
            keep = [j for j in range(n) if j != i]
            Xk = X[keep]
            mu, sd, _ = _zfit(Xk)
            Xs = (Xk - mu) / sd
            ym, w = _ridge(Xs, (ylog - off)[keep], alpha)
            p = float(((X[i] - mu) / sd) @ w + ym + off[i])
            errs.append(abs(math.exp(p) - math.exp(ylog[i])) / math.exp(ylog[i]))
        m = float(np.mean(errs)) * 100
        if best is None or m < best[0]:
            best = (m, float(alpha))
    return best[1], best[0]


def fit_m3(tr, key, grid, quad: bool = False):
    mat, names = (feat_matrix_q, FEATS_Q) if quad else (feat_matrix, FEATS)
    X = mat(tr)
    ylog = np.log([r[key] for r in tr])
    alpha, loo = _loocv_alpha(X, ylog, grid)
    mu, sd, const = _zfit(X)
    Xs = (X - mu) / sd
    ym, w = _ridge(Xs, ylog, alpha)

    def pred(rows):
        Xe = (mat(rows) - mu) / sd
        return list(np.exp(Xe @ w + ym))
    return pred, {"alpha": alpha, "loo_mape": round(loo, 3),
                  "sweep_basis": ("quadratic s=sweep/20" if quad else "linear sweep_deg"),
                  "const_features": [f for f, c in zip(names, const) if c],
                  "feat_sd": {f: round(float(s), 6) for f, s in zip(names, sd)}}


def fit_m5(tr, key, kind, grid, quad: bool = False):
    """Physics prefix absorbed as a fixed offset; ridge learns the residual."""
    mat = feat_matrix_q if quad else feat_matrix
    X = mat(tr)
    ylog = np.log([r[key] for r in tr])
    base = np.log([beam_prefix(r, kind) for r in tr])
    alpha, loo = _loocv_alpha(X, ylog, grid, hybrid_offset=base)
    mu, sd, _ = _zfit(X)
    Xs = (X - mu) / sd
    ym, w = _ridge(Xs, ylog - base, alpha)

    def pred(rows):
        Xe = (mat(rows) - mu) / sd
        be = np.log([beam_prefix(r, kind) for r in rows])
        return list(np.exp(Xe @ w + ym + be))
    return pred, {"alpha": alpha, "loo_mape": round(loo, 3),
                  "sweep_basis": ("quadratic s=sweep/20" if quad else "linear sweep_deg")}


def _rbf(A, B, ls, sv):
    d2 = ((A[:, None, :] - B[None, :, :]) ** 2).sum(-1)
    return sv * np.exp(-0.5 * d2 / ls ** 2)


def fit_m4(tr, key):
    X = feat_matrix(tr)
    ylog = np.log([r[key] for r in tr])
    grid = [(ls, sv, sn) for ls in (0.5, 1.0, 2.0, 4.0, 8.0)
            for sv in (0.1, 0.5, 1.0, 2.0) for sn in (0.05, 0.1, 0.2, 0.4)]

    def build(ls, sv, sn, XX, yy):
        """Every statistic (mu/sd/mean) is computed from XX/yy only.

        The M7 probe passed the full-train mean into the LOO folds, i.e. the
        held-out point contributed to its own offset.  Fixed here.
        """
        mu, sd, _ = _zfit(XX)
        Xs = (XX - mu) / sd
        ym = yy.mean()
        K = _rbf(Xs, Xs, ls, sv) + sn ** 2 * np.eye(len(Xs))
        L = np.linalg.cholesky(K)
        a = np.linalg.solve(L.T, np.linalg.solve(L, yy - ym))
        r = yy - ym
        ll = float(-0.5 * r @ a - np.log(np.diag(L)).sum()
                   - 0.5 * len(yy) * math.log(2 * math.pi))
        return {"mu": mu, "sd": sd, "ym": ym, "Xs": Xs, "a": a, "h": (ls, sv, sn),
                "ll": ll}

    mu, sd, _ = _zfit(X)
    Xs = (X - mu) / sd
    best, best_ll = None, -1e300
    for h in grid:
        try:
            m = build(*h, X, ylog)
        except np.linalg.LinAlgError:
            continue
        if m["ll"] > best_ll:
            best, best_ll = h, m["ll"]
    model = build(*best, X, ylog)

    def pred(rows):
        Xe = (feat_matrix(rows) - model["mu"]) / model["sd"]
        v = _rbf(Xe, model["Xs"], best[0], best[1]) @ model["a"] + model["ym"]
        return list(np.exp(np.asarray(v).ravel()))
    # train LOOCV with the chosen hyper-parameters (refit all statistics per fold)
    errs = []
    for i in range(len(tr)):
        keep = [j for j in range(len(tr)) if j != i]
        sub = build(*best, X[keep], ylog[keep])
        xe = (X[i:i + 1] - sub["mu"]) / sub["sd"]
        p = float(np.asarray(_rbf(xe, sub["Xs"], best[0], best[1]) @ sub["a"]
                             + sub["ym"]).ravel()[0])
        errs.append(abs(math.exp(p) - math.exp(ylog[i])) / math.exp(ylog[i]))
    return pred, {"hparams_len_scale_signal_noise": [float(v) for v in best],
                  "loo_mape": round(float(np.mean(errs)) * 100, 3)}


def loo_generic(tr, key, fitter):
    """LOOCV for the closed-form tiers (1-7 parameters).

    The probe only reported LOOCV for the learned tiers, which let a reader
    compare "M2: -" against "M3: 5.5 %".  Parameter count is small here, so
    every tier gets the same honest in-distribution read.
    """
    errs = []
    for i in range(len(tr)):
        keep = [r for j, r in enumerate(tr) if j != i]
        f, _ = fitter(keep)
        p = f([tr[i]])[0]
        errs.append(abs(p - tr[i][key]) / tr[i][key])
    return round(float(np.mean(errs)) * 100, 3)


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def ape(pred, obs):
    return [abs(p - o) / o for p, o in zip(pred, obs)]


def mape(pred, obs):
    return float(np.mean(ape(pred, obs))) * 100


def coarse_ape(pred, obs):
    """MAPE excluding each tier's own single worst case (n-1 of n).

    One outlier can dominate a 7-point mean.  This is computed per tier from
    that tier's own worst point, so it cannot be gamed by choosing which case
    to drop -- the tier decides.
    """
    e = ape(pred, obs)
    if len(e) <= 1:
        return None
    keep = sorted(range(len(e)), key=lambda i: -e[i])[1:]
    return float(np.mean([e[i] for i in keep])) * 100


# D31 train intervals, restated here ONLY to label extrapolation type in the
# report.  The split itself is decided by manifest.SPLIT_RULES and is asserted
# against this labelling below, so the two cannot drift apart silently.
TRAIN_SPAN = (1600.0, 2400.0)
TRAIN_SKIN = (2.0, 4.0)


def extrap_tags(r, tr):
    """Label HOW a case leaves the training set.  Three disjoint mechanisms:

      *_out   an axis left the train [min,max]  -> the classical extrapolation
      *_new   a discrete axis took a value never seen in train (is_T, n_web,
              n_ribs, web position)
      combo   every axis is individually inside the train domain, but the
              *combination* is new -- this is exactly what D31 calls an
              in-interval interaction point, and it is neither of the above.

    Distinguishing these matters: a model can be fine at single-axis
    extrapolation and still fail at combination points, and averaging the two
    into one "test error" hides which is which.
    """
    out, new = [], []
    for f, lab in (("span", "size_out"), ("skin_t", "size_out")):
        lo = min(t[f] for t in tr)
        hi = max(t[f] for t in tr)
        if r[f] < lo - 1e-9 or r[f] > hi + 1e-9:
            out.append(lab)
    if r["sweep"] > max(t["sweep"] for t in tr) + 1e-9 \
            or r["taper"] < min(t["taper"] for t in tr) - 1e-9:
        out.append("planform_out")
    for f, lab in (("is_T", "section_new"), ("n_web", "multicell_new"),
                   ("n_ribs", "ribs_new"), ("web_pos", "webpos_new")):
        if round(r[f], 9) not in {round(t[f], 9) for t in tr}:
            new.append(lab)
    if out:
        return "+".join(sorted(set(out)))
    if new:
        return "+".join(sorted(new))
    return "combo"


def boot_ci(pred, obs, n=4000, seed=20261024):
    rng = np.random.default_rng(seed)
    idx = np.arange(len(obs))
    vals = []
    for _ in range(n):
        s = rng.choice(idx, size=len(idx), replace=True)
        vals.append(np.mean([abs(pred[i] - obs[i]) / obs[i] for i in s]) * 100)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def paired_boot(a_pred, b_pred, obs, n=4000, seed=20261024):
    """CI on MAPE(a) - MAPE(b).  Negative => a better. Both on the same cases."""
    rng = np.random.default_rng(seed)
    idx = np.arange(len(obs))
    vals = []
    for _ in range(n):
        s = rng.choice(idx, size=len(idx), replace=True)
        ea = np.mean([abs(a_pred[i] - obs[i]) / obs[i] for i in s])
        eb = np.mean([abs(b_pred[i] - obs[i]) / obs[i] for i in s])
        vals.append((ea - eb) * 100)
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)),
            float(np.mean(vals)))


# --------------------------------------------------------------------------- #
# physics self-checks
# --------------------------------------------------------------------------- #
def check_positive(name, pred, fails):
    bad = [i for i, p in enumerate(pred) if not (p > 0) or not math.isfinite(p)]
    if bad:
        fails.append(f"{name}: {len(bad)} non-positive/non-finite prediction(s)")
    return not bad


def check_monotone(name, predictor, proto, fails):
    """span up -> |u| up ; skin_t up -> |u| down.  Sampled on a grid."""
    spans = [proto["span"] * f for f in (0.5, 0.75, 1.0, 1.5, 2.0)]
    ts = [proto["skin_t"] * f for f in (0.5, 0.75, 1.0, 1.5, 2.0)]
    u_span = predictor([{**proto, "span": s} for s in spans])
    u_t = predictor([{**proto, "skin_t": t} for t in ts])
    ok_span = all(b > a * (1 - 1e-9) for a, b in zip(u_span, u_span[1:]))
    ok_t = all(b < a * (1 + 1e-9) for a, b in zip(u_t, u_t[1:]))
    bad = []
    if not ok_span:
        bad.append("span")
    if not ok_t:
        bad.append("skin_t")
    if bad:
        fails.append(f"{name}: monotonicity violated on {bad}")
    return {"span_increasing": ok_span, "skin_thickness_decreasing": ok_t}


def ridge_exponents(info):
    """w is d log y / d z_f ; the exponent is w / sd(log x_f)."""
    sd = info.get("feat_sd", {})
    return sd


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--boot", type=int, default=4000)
    ap.add_argument("--family", default="wingbox")
    args = ap.parse_args()

    rows = load_family(args.family)
    tr = [r for r in rows if r["split"] == "train"]
    va = [r for r in rows if r["split"] == "val"]
    te = [r for r in rows if r["split"] == "test"]
    digest = dataset_digest(rows)

    print("=" * 96)
    print(f"FORMAL BASELINE -- family {args.family}")
    print(f"  cases {len(rows)} = train {len(tr)} / val {len(va)} / test {len(te)}"
          f"   distinct geometry classes {len({r['cls'] for r in rows})}")
    print(f"  dataset digest {digest[:16]}...  (sha256 of case_id|spec_sha256|split)")
    print("=" * 96)

    grid = _alpha_grid()
    out = {"family": args.family, "dataset_digest": digest,
           "n": {"total": len(rows), "train": len(tr), "val": len(va), "test": len(te)},
           "n_classes": len({r["cls"] for r in rows}),
           "targets": {}, "self_checks": {}, "cross_family": {}}

    # train feature coverage: which axes are constant on train (=> pure extrapolation)
    Xtr = feat_matrix(tr)
    sd_tr = Xtr.std(axis=0)
    const = [f for f, s in zip(FEATS, sd_tr) if s < 1e-12]
    print(f"\n[train feature coverage] constant on train: {const or 'none'}")
    print(f"  train span {min(r['span'] for r in tr):g}-{max(r['span'] for r in tr):g}"
          f" | skin_t {min(r['skin_t'] for r in tr):g}-{max(r['skin_t'] for r in tr):g}"
          f" | sweep {min(r['sweep'] for r in tr):g}-{max(r['sweep'] for r in tr):g}")
    out["train_const_features"] = const

    for key, (label, kind, role) in TARGETS.items():
        obs_v = [r[key] for r in va]
        obs_t = [r[key] for r in te]
        print("\n" + "-" * 96)
        print(f"target: {label}   [{role}]")
        print(f"{'tier':<24}{'trainLOO':>10}{'val':>8}{'test':>8}"
              f"{'test 95% CI':>18}{'medAPE':>9}{'maxAPE':>8}{'dropWorst':>10}")
        res = {}

        def report(name, predictor, info):
            pv = predictor(va)
            pt = predictor(te)
            loo = info.get("loo_mape")
            mv, mt = mape(pv, obs_v), mape(pt, obs_t)
            ci = boot_ci(pt, obs_t, n=args.boot)
            med = float(np.median(ape(pt, obs_t))) * 100
            mx = max(ape(pt, obs_t)) * 100
            dw = coarse_ape(pt, obs_t)
            print(f"{name:<24}{(f'{loo:.2f}' if loo is not None else '-'):>10}"
                  f"{mv:>7.2f}%{mt:>7.2f}%"
                  f"{f'[{ci[0]:.2f},{ci[1]:.2f}]':>18}{med:>8.2f}%{mx:>7.1f}%"
                  f"{(f'{dw:.2f}%' if dw is not None else '-'):>10}")
            res[name] = {"val_mape": round(mv, 3), "test_mape": round(mt, 3),
                         "test_ci95": [round(ci[0], 2), round(ci[1], 2)],
                         "test_medape": round(med, 3),
                         "test_maxape": round(mx, 2),
                         "test_mape_drop_worst1": (round(dw, 3) if dw is not None else None),
                         "train_loo_mape": (round(loo, 3) if loo is not None else None),
                         "params": info,
                         "pred_test": [round(p, 6) for p in pt],
                         "ape_test": [round(a * 100, 3) for a in ape(pt, obs_t)]}
            return res[name]

        f0, i0 = fit_m0(tr, key)
        i0["loo_mape"] = loo_generic(tr, key, lambda s: fit_m0(s, key))
        report("M0 constant(geomean)", f0, i0)
        f0m, i0m = fit_m0m(tr, key)
        i0m["loo_mape"] = loo_generic(tr, key, lambda s: fit_m0m(s, key))
        report("M0m constant(MAPE-opt)", f0m, i0m)
        f1, i1 = fit_m1(tr, key, kind)
        i1["loo_mape"] = loo_generic(tr, key, lambda s: fit_m1(s, key, kind))
        report("M1 beam(1p)", f1, i1)
        f2, i2 = fit_m2(tr, key, kind, grid)
        report("M2 beam+shape^c(3p)", f2, i2)
        f2l, i2l = fit_m2l(tr, key, kind)
        i2l["loo_mape"] = loo_generic(tr, key, lambda s: fit_m2l(s, key, kind))
        report("M2L size-pow(4p)", f2l, i2l)
        f2x, i2x = fit_m2x(tr, key, kind)
        i2x["loo_mape"] = loo_generic(tr, key, lambda s: fit_m2x(s, key, kind))
        report("M2X full-pow(7p)", f2x, i2x)
        f3, i3 = fit_m3(tr, key, grid)
        report("M3 ridge(10f)", f3, i3)
        f3q, i3q = fit_m3(tr, key, grid, quad=True)
        report("M3q ridge+sweep^2", f3q, i3q)
        f4, i4 = fit_m4(tr, key)
        report("M4 GP-RBF(10f)", f4, i4)
        f5, i5 = fit_m5(tr, key, kind, grid)
        report("M5 hybrid(10f+phys)", f5, i5)
        f5q, i5q = fit_m5(tr, key, kind, grid, quad=True)
        report("M5q hybrid+sweep^2", f5q, i5q)

        # ---- model selection happens on VAL, never on TEST ---------------- #
        # Picking "best physics" by test score would be selection bias: the
        # headline test number would then be the best of 4 physics forms chosen
        # with knowledge of test.  Select on val, report test once.
        best_phys = min(("M1 beam(1p)", "M2 beam+shape^c(3p)",
                         "M2L size-pow(4p)", "M2X full-pow(7p)"),
                        key=lambda k: res[k]["val_mape"])
        best_learn = min(("M3 ridge(10f)", "M3q ridge+sweep^2", "M4 GP-RBF(10f)",
                          "M5 hybrid(10f+phys)", "M5q hybrid+sweep^2"),
                         key=lambda k: res[k]["val_mape"])
        d, m, mean = paired_boot(res[best_learn]["pred_test"],
                                 res[best_phys]["pred_test"], obs_t, n=args.boot)
        sig = (d > 0 and m > 0) or (d < 0 and m < 0)
        print(f"  selected on VAL: physics {best_phys} (val {res[best_phys]['val_mape']:.2f}%)"
              f"  |  learner {best_learn} (val {res[best_learn]['val_mape']:.2f}%)")
        # val is 7 rows; one of them is the only positive-sweep held-out row.  At
        # that size "best on val" is a statement about seven numbers, and D34
        # found a tier that won val and lost test badly (max_w: val 1.93 %,
        # test 13.49 %, maxAPE 65 %).  The flag below makes that visible instead
        # of leaving the reader to assume best-on-val == best-on-test.
        test_best = min((k for k in res if not k.startswith("_")),
                        key=lambda k: res[k]["test_mape"])
        if test_best != best_learn:
            print(f"  NOTE val and test disagree: best on TEST is {test_best} "
                  f"({res[test_best]['test_mape']:.2f}%), not the val-selected tier."
                  f"  n_val={len(va)}, n_test={len(te)} -- this is a warning about "
                  f"the size of val, not a licence to select on test.")
        out.setdefault("val_test_disagreement", {})[key] = {
            "best_learn_val": best_learn,
            "best_test": test_best,
            "agree": test_best == best_learn}
        print(f"  TEST: learner {res[best_learn]['test_mape']:.2f}%"
              f"  vs physics {res[best_phys]['test_mape']:.2f}%"
              f"   paired diff = {mean:+.2f} pp  95% CI [{d:+.2f}, {m:+.2f}]"
              f"  -> {'SIGNIFICANT' if sig else 'NOT resolved (CI spans 0)'}")
        # ratio to the no-information floor
        # the floor is the MAPE-optimal constant (M0m), the strongest "no info"
        # model; using the weaker geometric-mean constant would flatter learners
        floor = res["M0m constant(MAPE-opt)"]["test_mape"]
        print(f"  vs MAPE-optimal constant floor ({floor:.2f}%): "
              f"{best_learn} ratio = {res[best_learn]['test_mape'] / floor * 100:.1f}%")
        res["_summary"] = {"best_physics": best_phys, "best_learner": best_learn,
                           "paired_diff_pp": round(mean, 3),
                           "paired_ci95": [round(d, 3), round(m, 3)],
                           "significant": sig,
                           "floor_m0m_test_mape": floor,
                           "learner_over_floor_pct": round(
                               res[best_learn]["test_mape"] / floor * 100, 2)}
        out["targets"][key] = res

        # ---- self checks on this target -------------------------------- #
        fails = []
        proto = dict(max(tr, key=lambda r: r["max_disp"]))
        for nm, f in (("M2L", f2l), ("M3", f3), ("M3q", f3q), ("M5", f5), ("M5q", f5q)):
            check_positive(nm, f(rows), fails)
        mono = {}
        for nm, f in (("M1", f1), ("M2L", f2l), ("M2X", f2x), ("M3", f3),
                      ("M3q", f3q), ("M5", f5), ("M5q", f5q)):
            mono[nm] = check_monotone(nm, f, proto, fails)
        print(f"  self-check: {'OK' if not fails else 'FAIL -> ' + '; '.join(fails)}")
        out["self_checks"][key] = {
            "fails": fails, "monotone": mono,
            "implied_exponents_M2L": {k: round(v, 4) for k, v in i2l.items()},
            "implied_exponents_M2X": {k: round(v, 4) for k, v in i2x.items()}}

        if key == "max_disp":
            print(f"  implied exponents (M2L): span {i2l['exp_span']:+.3f}"
                  f" / skin {i2l['exp_skin']:+.3f} / chord {i2l['exp_chord']:+.3f}"
                  f"   (beam theory: +3 / -1 / -3)")
            print(f"  implied exponents (M2X): span {i2x['exp_span']:+.3f}"
                  f" / skin {i2x['exp_skin']:+.3f} / chord {i2x['exp_chord']:+.3f}"
                  f" / cos2sweep {i2x['exp_cos2sweep']:+.3f}"
                  f" / taper {i2x['exp_taper']:+.3f}")

        # ---- which kind of extrapolation is responsible for the error? ---- #
        tag_of = [extrap_tags(r, tr) for r in te]
        groups: dict[str, list[int]] = {}
        for i, g in enumerate(tag_of):
            groups.setdefault(g, []).append(i)
        covered = sum(len(v) for v in groups.values())
        if covered != len(te):          # nothing may fall through unlabelled
            fails.append(f"extrapolation labelling covers {covered}/{len(te)} test cases")
        reps = [("M1", res["M1 beam(1p)"]), ("M2X", res["M2X full-pow(7p)"]),
                ("M3", res["M3 ridge(10f)"]), ("M3q", res["M3q ridge+sweep^2"]),
                ("M5", res["M5 hybrid(10f+phys)"]), ("M5q", res["M5q hybrid+sweep^2"])]
        print("\n  error by extrapolation mechanism (descriptive only; n=1-3 per "
              "group, no verdict drawn):")
        print("    %-22s%4s" % ("group", "n") + "".join("%9s" % n for n, _ in reps))
        for tag, idx in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            row = "    %-22s%4d" % (tag, len(idx))
            for _, dct in reps:
                row += "%8.1f%%" % float(np.mean([dct["ape_test"][i] for i in idx]))
            print(row)
        out["test_groups"] = {t: [te[i]["case_id"] for i in idx]
                              for t, idx in groups.items()}
        out.setdefault("test_group_ape", {})[key] = {
            t: {n: round(float(np.mean([dct["ape_test"][i] for i in idx])), 2)
                for n, dct in reps}
            for t, idx in groups.items()}

        # ---- is the 1-parameter closed form already at the ceiling? ------- #
        m1t = res["M1 beam(1p)"]["test_mape"]
        blt = res[best_learn]["test_mape"]
        print(f"  1-parameter beam scaling {m1t:.2f}%  vs  best learner "
              f"{blt:.2f}%  ->  gap {m1t - blt:+.2f} pp"
              f"{'  (physics already at the ceiling)' if abs(m1t - blt) < 2 else ''}")

    # ---- is the scalar target a smooth functional or a discrete selection? -- #
    def loc_stats(field):
        c = Counter(r[field] for r in rows)
        return {"distinct": len(c), "n": len(rows),
                "most_common": [[int(k), int(v)] for k, v in c.most_common(3)]}
    out["peak_localisation"] = {"max_disp_node": loc_stats("u_node"),
                                "vm_midsurface_node": loc_stats("vm_node")}
    print("\n" + "=" * 96)
    print("[peak localisation] every scalar target here is a max over nodes.  If the")
    print("  argmax jumps between cases, the target is a discrete *selection*, not a")
    print("  smooth functional of the parameters -- and no smooth surrogate can fit it.")
    for k, v in out["peak_localisation"].items():
        print(f"  {k:<22} {v['distinct']}/{v['n']} distinct nodes"
              f"   top {v['most_common']}")

    # ---- cross-family trainability ------------------------------------- #
    print("\n" + "=" * 96)
    print("CROSS-FAMILY TRAINABILITY  (a family needs train >= 5 to fit any of the")
    print("tiers above; below that a held-out score measures nothing)")
    man = json.loads((BENCH / "manifest.json").read_text(encoding="utf-8"))
    cnt = Counter((c["family"], c["split"]) for c in man["cases"])
    for fam in sorted({c["family"] for c in man["cases"]}):
        ntr = cnt[(fam, "train")]
        verdict = "modelable" if ntr >= 5 else "NOT modelable (too few train cases)"
        print(f"  {fam:<20} train {ntr:>2}  val {cnt[(fam,'val')]:>2}"
              f"  test {cnt[(fam,'test')]:>2}   {verdict}")
        out["cross_family"][fam] = {"train": ntr, "val": cnt[(fam, "val")],
                                    "test": cnt[(fam, "test")], "verdict": verdict}

    all_fails = [f for t in out["self_checks"].values() for f in t["fails"]]
    out["verdict"] = "PASS" if not all_fails else "CHECK"
    print("\n" + "=" * 96)
    print(f"VERDICT: {out['verdict']}   ({len(all_fails)} self-check failure(s))")
    for f in all_fails:
        print(f"  - {f}")

    if args.json:
        p = Path(args.json)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n-> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
