"""M7 stage 2: is the ceiling sample size or coverage?

The stage-1 probe showed a physics-plus-3-constants model (M2) beating free
Gaussian-process regression on val and test.  That answers "what works at
n=13".  It does not answer the question that actually drives the roadmap:

    is the error dominated by *how many* cases we have, or by *how far* the
    query sits outside the envelope the training set covers?

Those two have opposite remedies (collect more vs. collect wider), so they
have to be measured separately.

Method
------
1. Rank the 13 frozen-train wingbox cases by distance from the family centre,
   then grow the training set one case at a time in that order.  The error
   curve therefore tracks *envelope growth*, not random resampling noise, and
   it is deterministic (no seed, reproducible).
2. For every val/test case, take the nearest-neighbour distance to the
   training set in standardised feature space and plot the error against it.

No re-solving, no re-splitting: the D12 split is used exactly as shipped.

Run:  python _probe_m7/extrapolation.py [--json out.json]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_probe_m7"))
from learnability import (  # noqa: E402
    FEATS, beam_prefix, feat_matrix, load_family, m2_physics_shape, m3_ridge,
    mape, ridge_fit, ridge_pred, shape_features,
)

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT.parent / "FEM-Bench-Aero"
DIST_FEATS = ["chord", "span", "skin_t", "n_ribs", "n_str", "sweep", "taper",
              "n_web", "is_T", "web_pos"]


def dist_matrix(rows, ref) -> np.ndarray:
    """Standardised Euclidean distance from every row to every ref row."""
    all_rows = list(rows) + list(ref)
    X = feat_matrix(all_rows, [f for f in DIST_FEATS if f not in FEATS])
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd[sd < 1e-12] = 1.0
    Xs = (X - mu) / sd
    A, B = Xs[:len(rows)], Xs[len(rows):]
    return np.sqrt(((A[:, None, :] - B[None, :, :]) ** 2).sum(-1))


def main() -> int:
    rows = load_family("wingbox")
    tr_all = [r for r in rows if r["split"] == "train"]
    ev = [r for r in rows if r["split"] in ("val", "test")]

    # --- 1. deterministic envelope growth ---------------------------------- #
    # order the train cases by distance from the centre of the whole family,
    # so each step adds the case that extends coverage the most
    Xall = feat_matrix(rows, [f for f in DIST_FEATS if f not in FEATS])
    mu, sd = Xall.mean(axis=0), Xall.std(axis=0)
    sd[sd < 1e-12] = 1.0
    Xs = (Xall - mu) / sd
    is_tr = np.array([r["split"] == "train" for r in rows])
    centre = Xs[is_tr].mean(axis=0)
    order = sorted([i for i in range(len(rows)) if is_tr[i]],
                   key=lambda i: float(np.linalg.norm(Xs[i] - centre)))
    ordered = [rows[i] for i in order]

    print("envelope growth order (nearest to family centre first):")
    for k, r in enumerate(ordered, 1):
        print(f"  {k:>2}. {r['case_id']}")

    print("\nlearning curve, target max_disp")
    print(f"{'n_train':>8}{'max radius':>12}{'val MAPE':>10}{'test MAPE':>11}"
          f"{'M2 val':>9}{'M2 test':>9}")
    curve = []
    for n in range(4, len(ordered) + 1):
        sub = ordered[:n]
        Xtr = feat_matrix(sub, [f for f in DIST_FEATS if f not in FEATS])
        Xs_tr = (Xtr - mu) / sd
        radius = float(np.max(np.sqrt(((Xs_tr - centre) ** 2).sum(-1))))
        pv = m2_physics_shape(sub, [r for r in ev if r["split"] == "val"], "u")
        pt = m2_physics_shape(sub, [r for r in ev if r["split"] == "test"], "u")
        rv = m3_ridge(sub, [r for r in ev if r["split"] == "val"], "u")[0]
        rt = m3_ridge(sub, [r for r in ev if r["split"] == "test"], "u")[0]
        mv = mape(pv, [r["u"] for r in ev if r["split"] == "val"]) if n >= 4 else float("nan")
        mt = mape(pt, [r["u"] for r in ev if r["split"] == "test"]) if n >= 4 else float("nan")
        rmv = mape(rv, [r["u"] for r in ev if r["split"] == "val"])
        rmt = mape(rt, [r["u"] for r in ev if r["split"] == "test"])
        curve.append({"n_train": n, "radius": round(radius, 3),
                      "m2_val": round(mv, 2), "m2_test": round(mt, 2),
                      "ridge_val": round(rmv, 2), "ridge_test": round(rmt, 2)})
        print(f"{n:>8}{radius:>12.2f}{rmv:>9.1f}%{rmt:>10.1f}%"
              f"{mv:>8.1f}%{mt:>8.1f}%")

    # --- 2. error vs distance from the shipped training envelope ----------- #
    print("\nerror vs nearest-training-neighbour distance (shipped split, ridge 10f)")
    D = dist_matrix(ev, tr_all)
    dmin = D.min(axis=1)
    # the predictor MUST live in the same feature space as the distance,
    # otherwise the correlation measures nothing (a mistake worth recording).
    p_all = m3_ridge(tr_all, ev, "u")[0]
    p_m2 = m2_physics_shape(tr_all, ev, "u")
    print(f"{'case':<40}{'split':<6}{'d_min':>7}{'obs':>9}{'ridge':>9}{'err':>8}"
          f"{'M2 err':>8}")
    pts = []
    for r, d, p, p2 in zip(ev, dmin, p_all, p_m2):
        e = (p - r["u"]) / r["u"] * 100
        e2 = (p2 - r["u"]) / r["u"] * 100
        pts.append({"case_id": r["case_id"], "split": r["split"],
                    "d_min": round(float(d), 3), "obs": round(r["u"], 4),
                    "pred_ridge": round(p, 4), "err_pct": round(float(e), 2),
                    "pred_m2": round(p2, 4), "err_m2_pct": round(float(e2), 2)})
        print(f"{r['case_id']:<40}{r['split']:<6}{d:>7.2f}{r['u']:>9.4f}"
              f"{p:>9.4f}{e:>7.1f}%{e2:>7.1f}%")

    # correlation between distance and |error| - the claim that has to hold up
    dd = np.array([p["d_min"] for p in pts])
    ee = np.abs(np.array([p["err_pct"] for p in pts]))
    corr = float(np.corrcoef(dd, ee)[0, 1]) if len(dd) >= 3 else float("nan")
    print(f"\ncorr(distance, |error|) = {corr:.3f}   (n={len(dd)})")
    inside = [p for p in pts if p["d_min"] <= 1.0]
    outside = [p for p in pts if p["d_min"] > 1.0]
    for tag, grp in (("d <= 1.0", inside), ("d > 1.0", outside)):
        if grp:
            m = float(np.mean([abs(p["err_pct"]) for p in grp]))
            print(f"  {tag:<10} n={len(grp):<3} mean|err| = {m:6.1f}%  "
                  f"max = {max(abs(p['err_pct']) for p in grp):6.1f}%")

    out = {"family": "wingbox", "order": [r["case_id"] for r in ordered],
           "curve": curve, "points": pts, "corr_dist_err": round(corr, 4)}
    for arg in sys.argv[1:]:
        if arg.startswith("--json="):
            path = Path(arg.split("=", 1)[1])
            path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"\n-> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
