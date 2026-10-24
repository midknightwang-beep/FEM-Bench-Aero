"""M7 stage 1: learnability probe on the wingbox family.

    ⚠️ HISTORICAL RECORD ONLY -- do NOT cite these numbers (2026-10-24, M8).
    This script is kept as the audit trail of how the question was first asked.
    It has five defects that make its output non-comparable and, in places,
    too flattering or too harsh: per-set alpha selection (val and test were not
    scored by the same model), M1/M2 fitted in raw space while M3/M4/M5 fitted
    in log space, arithmetic-mean constant baselines (MAPE's optimum is the
    weighted median), no free-exponent power-law opponent, and no interval.
    The reportable baseline is `../baseline.py` -> `FEM-Bench-Aero/BASELINE.md`.

Question being answered: *does the shipped data carry signal a model can
learn, beyond what closed-form physics already gives?*

The design has to be adversarial to itself, otherwise a small-sample run
produces a fake positive.  Four tiers, all fitted on the **frozen D12 train
split** (13 wingbox cases) and scored on val / test as shipped:

  M0  constant            - the "no information" floor
  M1  beam scaling law    - 1 fitted constant on u = C*F*span^3/(E*t*c^3)
  M2  physics + shape     - adds cos(sweep) and taper with 3 fitted constants
  M3  ridge (log-linear)  - 7 features, alpha picked by train LOOCV
  M4  Gaussian process    - RBF, hyper-parameters picked by train LOOCV

M1/M2 are the opponents that matter: if a closed form already explains the
data, M3/M4 "learning" is decoration.  M2 is where physics prior meets a few
empirical constants, which is the honest middle ground for n=13.

Nothing here re-solves anything.  It reads the shipped truth.json only.

Run:  python _probe_m7/learnability.py [--json out.json]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT.parent / "FEM-Bench-Aero"


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def load_family(fam: str) -> dict:
    man = json.loads((BENCH / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    for c in man["cases"]:
        if c["tree"] != "modeling" or c["family"] != fam:
            continue
        d = BENCH / "modeling" / c["case_id"]
        spec = json.loads((d / "spec.json").read_text(encoding="utf-8"))
        truth = json.loads((d / "truth.json").read_text(encoding="utf-8"))
        sc = truth.get("scalars", truth)
        a = spec["airfoil"]
        rows.append({
            "case_id": c["case_id"],
            "split": c["split"],
            "cls": c["geometry_class"],
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
            "u": float(sc["max_disp"]),
            "vm": float(sc["max_von_mises"]),
        })
    return rows


# --------------------------------------------------------------------------- #
# tiers
# --------------------------------------------------------------------------- #
def m0_constant(tr, te, key):
    c = float(np.mean([r[key] for r in tr]))
    return [c] * len(te)


def beam_prefix(r, key):
    """u for a cantilever box scaled to unit constant: F*span^3/(E*t*c^3).

    For stress the equivalent prefix is F*span/(t*c^2) (bending moment over
    section modulus, with I ~ t*c^3 and half-depth ~ c).
    """
    if key == "u":
        return r["F"] * r["span"] ** 3 / (r["E"] * r["skin_t"] * r["chord"] ** 3)
    return r["F"] * r["span"] / (r["skin_t"] * r["chord"] ** 2)


def m1_beam(tr, te, key):
    c = float(np.mean([r[key] / beam_prefix(r, key) for r in tr]))
    return [c * beam_prefix(r, key) for r in te]


def shape_features(r) -> list[float]:
    """Physics-motivated shape corrections, all dimensionless."""
    th = math.radians(r["sweep"])
    return [
        math.cos(th) ** 2,          # spanwise bending stiffness lost to sweep
        (1.0 + r["taper"]) / 2.0,   # taper reduces the outboard section depth
        r["taper"],
    ]


def m2_physics_shape(tr, te, key):
    """prefix * (a*cos^2 + b*(1+taper)/2 + c*taper), 3 constants by LSQ."""
    A = np.array([[r[key] / beam_prefix(r, key)] for r in tr])
    B = np.array([shape_features(r) for r in tr])
    coef, *_ = np.linalg.lstsq(B, A.ravel(), rcond=None)
    return [beam_prefix(r, key) * float(np.dot(shape_features(r), coef)) for r in te]


FEATS = ["chord", "span", "skin_t", "n_ribs", "n_str", "sweep", "taper",
         "is_T", "web_pos", "n_web"]


def feat_matrix(rows, extra: list[str]) -> np.ndarray:
    cols = []
    for f in FEATS + extra:
        v = np.array([float(r[f]) for r in rows])
        # multiplicative axes go through log, discrete knobs stay linear
        if f in ("chord", "span", "skin_t"):
            v = np.log(v)
        cols.append(v)
    return np.column_stack(cols)


def _zscore_fit(X):
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd < 1e-12] = 1.0
    return mu, sd


def ridge_fit(X, y, alpha):
    mu, sd = _zscore_fit(X)
    Xs = (X - mu) / sd
    ym = y.mean()
    n, p = Xs.shape
    w = np.linalg.solve(Xs.T @ Xs + alpha * np.eye(p), Xs.T @ (y - ym))
    return mu, sd, ym, w


def ridge_pred(model, X):
    mu, sd, ym, w = model
    return ((X - mu) / sd) @ w + ym


def m3_ridge(tr, te, key, extra=()):
    Xtr = feat_matrix(tr, list(extra))
    Xte = feat_matrix(te, list(extra))
    ytr = np.log(np.array([r[key] for r in tr]))
    best = None
    for alpha in np.logspace(-3, 3, 25):
        errs = []
        for i in range(len(tr)):
            keep = [j for j in range(len(tr)) if j != i]
            mdl = ridge_fit(Xtr[keep], ytr[keep], alpha)
            errs.append(abs(math.exp(ridge_pred(mdl, Xtr[i:i + 1])[0]) - math.exp(ytr[i]))
                        / math.exp(ytr[i]))
        mape = float(np.mean(errs)) * 100
        if best is None or mape < best[0]:
            best = (mape, alpha)
    mdl = ridge_fit(Xtr, ytr, best[1])
    return list(np.exp(ridge_pred(mdl, Xte))), {"alpha": float(best[1]),
                                                "loo_mape": round(best[0], 3)}


def m5_hybrid(tr, te, key, extra=()):
    """Physics prefix (carries the axes the data never varies) + ridge on the
    residual (learns the axes it does vary).

    span and skin_t are constant across the whole wingbox family, so a pure
    learner assigns them zero weight and cannot react if a query moves them.
    The beam prefix supplies exactly that missing prior; ridge then only has
    to explain what is left.
    """
    Xtr = feat_matrix(tr, list(extra))
    Xte = feat_matrix(te, list(extra))
    base_tr = np.log(np.array([beam_prefix(r, key) for r in tr]))
    base_te = np.log(np.array([beam_prefix(r, key) for r in te]))
    y = np.log(np.array([r[key] for r in tr])) - base_tr
    best = None
    for alpha in np.logspace(-3, 3, 25):
        errs = []
        for i in range(len(tr)):
            keep = [j for j in range(len(tr)) if j != i]
            mdl = ridge_fit(Xtr[keep], y[keep], alpha)
            p = math.exp(ridge_pred(mdl, Xtr[i:i + 1])[0] + base_tr[i])
            errs.append(abs(p - math.exp(y[i] + base_tr[i])) / math.exp(y[i] + base_tr[i]))
        m = float(np.mean(errs)) * 100
        if best is None or m < best[0]:
            best = (m, alpha)
    mdl = ridge_fit(Xtr, y, best[1])
    pred = np.exp(ridge_pred(mdl, Xte) + base_te)
    return list(pred), {"alpha": float(best[1]), "loo_mape": round(best[0], 3)}


def _rbf(A, B, ls, sv):
    d2 = ((A[:, None, :] - B[None, :, :]) ** 2).sum(-1)
    return sv * np.exp(-0.5 * d2 / ls ** 2)


def gp_fit(X, y, ls, sv, sn):
    mu, sd = _zscore_fit(X)
    Xs = (X - mu) / sd
    ym = y.mean()
    K = _rbf(Xs, Xs, ls, sv) + sn ** 2 * np.eye(len(Xs))
    L = np.linalg.cholesky(K)
    a = np.linalg.solve(L.T, np.linalg.solve(L, y - ym))
    return mu, sd, ym, Xs, L, a, (ls, sv, sn)


def gp_pred(model, X):
    mu, sd, ym, Xs, L, a, (ls, sv, sn) = model
    Ks = _rbf((X - mu) / sd, Xs, ls, sv)
    return Ks @ a + ym


def gp_loglik(model, y):
    mu, sd, ym, Xs, L, a, _ = model
    r = y - ym
    return float(-0.5 * r @ a - np.log(np.diag(L)).sum()
                 - 0.5 * len(y) * math.log(2 * math.pi))


def m4_gp(tr, te, key, extra=()):
    Xtr = feat_matrix(tr, list(extra))
    Xte = feat_matrix(te, list(extra))
    ytr = np.log(np.array([r[key] for r in tr]))
    grid = [(ls, sv, sn)
            for ls in (0.5, 1.0, 2.0, 4.0, 8.0)
            for sv in (0.1, 0.5, 1.0, 2.0)
            for sn in (0.05, 0.1, 0.2, 0.4)]
    # honest model selection: maximise the marginal likelihood on train only
    best = max(grid, key=lambda h: gp_loglik(gp_fit(Xtr, ytr, *h), ytr))
    mdl = gp_fit(Xtr, ytr, *best)
    pred = list(np.exp(gp_pred(mdl, Xte)))
    # train LOOCV with the chosen hyper-parameters, for an in-distribution read
    errs = []
    for i in range(len(tr)):
        keep = [j for j in range(len(tr)) if j != i]
        sub = gp_fit(Xtr[keep], ytr[keep], *best)
        p = math.exp(gp_pred(sub, Xtr[i:i + 1])[0])
        errs.append(abs(p - math.exp(ytr[i])) / math.exp(ytr[i]))
    return pred, {"hparams": [float(v) for v in best],
                  "loo_mape": round(float(np.mean(errs)) * 100, 3)}


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #
def mape(pred, obs):
    return float(np.mean([abs(p - o) / o for p, o in zip(pred, obs)])) * 100


def main() -> int:
    rows = load_family("wingbox")
    tr = [r for r in rows if r["split"] == "train"]
    va = [r for r in rows if r["split"] == "val"]
    te = [r for r in rows if r["split"] == "test"]
    print(f"wingbox: {len(rows)} cases -> train {len(tr)} / val {len(va)} / test {len(te)}")
    print(f"distinct geometry classes: {len({r['cls'] for r in rows})}")

    out = {"family": "wingbox", "n": {"train": len(tr), "val": len(va), "test": len(te)},
           "targets": {}}

    for key, label in (("u", "max_disp (mm)"), ("vm", "max_von_Mises (MPa)")):
        print("\n" + "=" * 78)
        print(f"target: {label}")
        print(f"{'tier':<26}{'train LOOCV':>13}{'val MAPE':>11}{'test MAPE':>11}"
              f"{'test max':>10}")
        obs_v = [r[key] for r in va]
        obs_t = [r[key] for r in te]
        res = {}

        def report(name, pred_v, pred_t, loo=None):
            mv, mt = mape(pred_v, obs_v), mape(pred_t, obs_t)
            mx = max(abs(p - o) / o for p, o in zip(pred_t, obs_t)) * 100
            print(f"{name:<26}{(f'{loo:.2f}%' if loo is not None else '-'):>13}"
                  f"{mv:>10.2f}%{mt:>10.2f}%{mx:>9.1f}%")
            res[name] = {"val_mape": round(mv, 3), "test_mape": round(mt, 3),
                         "test_max_pct": round(mx, 2),
                         "train_loo_mape": (round(loo, 3) if loo is not None else None)}

        report("M0 constant", m0_constant(tr, va, key), m0_constant(tr, te, key))
        report("M1 beam scaling", m1_beam(tr, va, key), m1_beam(tr, te, key))
        report("M2 beam+shape(3p)", m2_physics_shape(tr, va, key),
               m2_physics_shape(tr, te, key))
        p, info = m3_ridge(tr, va, key)
        q, _ = m3_ridge(tr, te, key)
        report("M3 ridge(10f)", p, q, info["loo_mape"])
        p, info = m4_gp(tr, va, key)
        q, _ = m4_gp(tr, te, key)
        report("M4 GP-RBF(10f)", p, q, info["loo_mape"])
        p, info = m5_hybrid(tr, va, key)
        q, _ = m5_hybrid(tr, te, key)
        report("M5 hybrid beam+ridge", p, q, info["loo_mape"])

        # per-case detail for the best learned tier, so nothing hides in an average
        print(f"\n  per-case (M4 GP) {label}:")
        pred_all = m4_gp(tr, rows, key)[0]
        for r, p in zip(rows, pred_all):
            print(f"    {r['case_id']:<44}{r['split']:<6}"
                  f"obs={r[key]:>9.4f} pred={p:>9.4f} err={(p - r[key]) / r[key] * 100:>7.1f}%")
        out["targets"][key] = res

    for arg in sys.argv[1:]:
        if arg.startswith("--json="):
            path = Path(arg.split("=", 1)[1])
            path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"\n-> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
