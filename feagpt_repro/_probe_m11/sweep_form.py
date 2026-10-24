#!/usr/bin/env python
"""M11 / D34 - does changing the *form* of the sweep term help, and if so which?

Why this script exists
----------------------
D33 added the 30 deg station.  It helped (planform_out 32.9 -> 25.7 %) but the
residual at 40 deg is still the largest error in the table.  The physics check
(``_probe_m10/physics_sweep_axis.py``) says the curve is cubic-ish: a cubic
through {0,10,20,30} lands within -7.2 % at 40 deg while the linear secant is
-43.4 %.  So the next lever is not more samples, it is the *form*: ``log y`` is
currently linear in ``sweep``, and a linear function cannot bend.

The trap this script is built to avoid
--------------------------------------
Train has only **three** rows with ``sweep > 0`` -- and those three rows share
one geometry (taper 1.0, 5 ribs, chord 1000, skin 3.0, span 2000, no webs).  So
adding s^2 and s^3 gives three columns that are non-zero on exactly three rows:
a 3x3 design that is *exactly invertible*.  A cubic would fit those three rows
to machine zero and its 40 deg branch would be pure guesswork -- this is the M2
failure mode again (perfect interpolation, catastrophic extrapolation).

Therefore every form here reports, next to its score:

* the **condition number** of the design (M2 taught us < 1e6 = identifiable),
* the **leave-one-out APE at the 20 and 30 deg stations specifically** -- the
  only leak-free measurement of "can it extrapolate one station further",
* the **cost** at the interpolating rows (train LOO overall), because a form
  that buys the tail by wrecking the bulk is not a win.

Which rows decide, and which rows only report
---------------------------------------------
* **train LOO at the top station** selects the form (no leakage: the station is
  removed before fitting).
* **val** is ``naca4412_wingbox_sweep40``: same geometry as the train sweep
  series (taper 1.0, 5 ribs), sweep outside the train hull.  A clean single-axis
  extrapolation -- by far the most informative held-out row for this question.
* **test** (``sweep40_taper040`` and everything else) is reported once, never
  used to choose.  Picking the form on test would be the selection bias that
  D32/§8 already forbids.

Usage::

    python _probe_m11/sweep_form.py

Writes ``sweep_form.json`` next to this file.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPRO = HERE.parent
sys.path.insert(0, str(REPRO))

import baseline as B  # noqa: E402

OUT = HERE / "sweep_form.json"
DEG = 20.0  # sweep normaliser: s = sweep_deg / 20  ->  stations 0, .5, 1, 1.5, 2

#: every candidate replaces the single linear ``sweep`` column with these
#: columns.  ``lin`` must reproduce M3 bit for bit -- that is the self-check.
BASES = {
    "lin": lambda s: [s],
    "powsec": lambda s: [np.log(1.0 / np.cos(np.radians(s * DEG)))],
    "quad": lambda s: [s, s ** 2],
    "cubic": lambda s: [s, s ** 2, s ** 3],
}

DESC = {
    "lin": "现状：log y 对 sweep 线性（= 现有 M3）",
    "powsec": "物理：乘 sec^p（后掠使有效展长 span/cos 增大，弯曲 ∝ sec^p），p 自由",
    "quad": "log 空间加二次（1 个曲率参数，过原点）",
    "cubic": "log 空间加二+三次（2 个曲率参数，3 个非零点 ⇒ 恰好可逆，风险）",
}


# --------------------------------------------------------------------------- #
# design / fit -- same machinery as M3, only the sweep columns change
# --------------------------------------------------------------------------- #
def design(rows: list[dict], form: str) -> np.ndarray:
    cols = []
    for f in B.FEATS:
        if f == "sweep":
            continue
        v = np.array([float(r[f]) for r in rows])
        if f in B.MULT_FEATS:
            v = np.log(v)
        cols.append(v)
    s = np.array([r["sweep"] / DEG for r in rows], dtype=float)
    cols.extend(np.asarray(c, dtype=float) for c in BASES[form](s))
    return np.column_stack(cols)


def _cond(X: np.ndarray) -> tuple[float, list[str], list[str]]:
    """Condition number of the *reduced* standardised design.

    Two reductions, both necessary and both reported -- not silent cleanup:

    1. **raw-scale** is meaningless here: ``log(chord)`` ~ 6.9 against ``is_T``
       in {0,1} makes cond() ~1e19 for every form, the current one included.
       Standardise first; that is what the ridge actually sees.
    2. **structural rank deficiency in the data itself**: on train, ``n_web``
       and ``web_pos`` are *exactly* collinear (singular value 1.3e-15) because
       train holds a single webbed case, so both columns are non-zero on the
       same one row; and ``is_T`` is constant 0 (no T-stringer case in train).
       Those are properties of the dataset, not of the sweep basis, so the
       sweep forms must not be charged for them.  Columns are admitted in
       FEATS order and dropped only when the added column leaves the matrix
       rank-deficient.

    Returns ``(cond, kept_names, dropped_names)`` with the *reason* left in the
    names list order, so the JSON records exactly what left the design.
    """
    sd = X.std(axis=0)
    names = [f"c{j}" for j in range(X.shape[1])]
    keep, dropped = [], []
    for j in range(X.shape[1]):
        if sd[j] <= 1e-12:
            dropped.append(j)          # constant on train
            continue
        trial = keep + [j]
        Xk = X[:, trial]
        Xs = (Xk - Xk.mean(axis=0)) / Xk.std(axis=0)
        A = np.column_stack([np.ones(len(Xk)), Xs])
        sv = np.linalg.svd(A, compute_uv=False)
        if sv[-1] > 1e-8 * sv[0]:
            keep = trial
        else:
            dropped.append(j)          # linearly dependent on what is in
    Xk = X[:, keep]
    Xs = (Xk - Xk.mean(axis=0)) / Xk.std(axis=0)
    A = np.column_stack([np.ones(len(Xk)), Xs])
    return float(np.linalg.cond(A)), names, dropped


def fit(rows: list[dict], key: str, form: str, hybrid: bool = False, kind: str = "u"):
    """Ridge on log y, alpha by train LOOCV -- the M3 recipe, unchanged.

    ``hybrid=True`` absorbs the beam prefix as a fixed offset (the M5 recipe).
    That matters for the comparison: the number this project *reports* for the
    primary target is the M5 row (7.74 % at D33), not M3 (8.62 %).  Changing the
    sweep term while leaving the physics prefix out would be improving a tier
    nobody quotes -- and would let a 6.16 % result be compared against 7.74 % as
    if it were the same baseline.
    """
    X = design(rows, form)
    ylog = np.log([r[key] for r in rows])
    base = (np.log([B.beam_prefix(r, kind) for r in rows]) if hybrid
            else np.zeros(len(rows)))
    alpha, loo = B._loocv_alpha(X, ylog, B._alpha_grid(), hybrid_offset=base)
    mu, sd, const = B._zfit(X)
    Xs = (X - mu) / sd
    ym, w = B._ridge(Xs, ylog - base, alpha)
    cond, _, dropped = _cond(X)
    nm = _names(form)

    def pred(rs):
        Xe = (design(rs, form) - mu) / sd
        be = (np.log([B.beam_prefix(r, kind) for r in rs]) if hybrid
              else np.zeros(len(rs)))
        return list(np.exp(Xe @ w + ym + be))

    coef = {n: round(float(c / d), 6)
            for n, c, d in zip(nm, w, sd) if d > 1e-12}
    return pred, {"form": form, "hybrid": hybrid, "alpha": float(alpha),
                  "loo_mape": round(loo, 3),
                  "cond_number": round(cond, 1), "identifiable": bool(cond < 1e6),
                  "dropped_cols": [nm[j] for j in dropped],
                  "n_free_directions": X.shape[1] - len(dropped),
                  "sweep_coef": {k: v for k, v in coef.items() if k.startswith("sw:")},
                  "const_features": [f for f, c in zip(nm, const) if c]}


def _names(form: str) -> list[str]:
    base = [f for f in B.FEATS if f != "sweep"]
    extra = {"lin": ["sw:s"], "powsec": ["sw:logsec"],
             "quad": ["sw:s", "sw:s2"], "cubic": ["sw:s", "sw:s2", "sw:s3"]}[form]
    return base + extra


def loo_pointwise(rows: list[dict], key: str, form: str, alpha: float,
                  hybrid: bool = False, kind: str = "u") -> dict:
    """Per-row LOO prediction with alpha held at the value chosen on full train.

    Deliberately *not* re-selecting alpha per fold: re-selection per fold is a
    second, hidden degrees-of-freedom that would make a higher-order form look
    better than it is.  The number this returns for the 30 deg row is the honest
    answer to "would it have predicted the next station?".
    """
    n = len(rows)
    ylog = np.log([r[key] for r in rows])
    base = (np.log([B.beam_prefix(r, kind) for r in rows]) if hybrid
            else np.zeros(n))
    out = []
    for i in range(n):
        keep = [j for j in range(n) if j != i]
        Xk = design([rows[j] for j in keep], form)
        mu, sd, _ = B._zfit(Xk)
        ym, w = B._ridge((Xk - mu) / sd, (ylog - base)[keep], alpha)
        Xi = design([rows[i]], form)
        p = float((((Xi - mu) / sd) @ w + ym + base[i]).ravel()[0])
        out.append(float(np.exp(p)))
    return {"pred": out, "obs": [float(r[key]) for r in rows]}


def ape(pred: float, obs: float) -> float:
    return (pred - obs) / obs * 100.0


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    fails: list[str] = []
    rows = B.load_family("wingbox")
    tr = [r for r in rows if r["split"] == "train"]
    va = [r for r in rows if r["split"] == "val"]
    te = [r for r in rows if r["split"] == "test"]

    stations = sorted({r["sweep"] for r in tr if r["sweep"] > 0})
    if stations != [10.0, 20.0, 30.0]:
        fails.append(f"unexpected positive-sweep stations in train: {stations}")
    n_zero = sum(1 for r in tr if r["sweep"] == 0.0)
    print("=" * 104)
    print("  M11 / D34  sweep-term FORM comparison  (wing-box, target max_disp)")
    print("=" * 104)
    print(f"  train {len(tr)} rows = {n_zero} at sweep=0 + {len(stations)} at "
          f"sweep={stations} deg")
    print("  NOTE those positive-sweep rows are ONE geometry (taper 1.0, 5 ribs, "
          "chord 1000, skin 3.0)")
    print("       -> s^2 and s^3 are non-zero on exactly 3 rows; identifiability "
          "is the whole story here.")
    print()

    # which train rows are the sweep stations, for the pointwise LOO report
    idx_st = {}
    for st in stations:
        hits = [i for i, r in enumerate(tr) if r["sweep"] == st]
        if len(hits) != 1:
            fails.append(f"station {st} has {len(hits)} train rows (expected 1)")
        else:
            idx_st[st] = hits[0]

    #: ``form@tier``: tier "ridge" = M3 recipe, "phys" = M5 recipe.
    #: Both are kept because the project quotes M5 for the primary target but M3
    #: is the tier the previous form decisions were made on -- a form change has
    #: to be judged on the tier it will actually be shipped in.
    results = {}
    for tier, hybrid in (("ridge", False), ("phys", True)):
        for form in BASES:
            tag = f"{form}@{tier}"
            pred, info = fit(tr, "max_disp", form, hybrid=hybrid)
            lw = loo_pointwise(tr, "max_disp", form, info["alpha"], hybrid=hybrid)
            st_ape = {f"{int(st)}deg": round(ape(lw["pred"][i], lw["obs"][i]), 2)
                      for st, i in idx_st.items()}
            pv = pred(va)
            pt = pred(te)
            results[tag] = {
                **info,
                "loo_station_ape_pct": st_ape,
                "val": {r["case_id"]: round(ape(p, r["max_disp"]), 2)
                        for p, r in zip(pv, va)},
                "val_mape": round(float(np.mean([abs(ape(p, r["max_disp"]))
                                                 for p, r in zip(pv, va)])), 2),
                "test": {r["case_id"]: round(ape(p, r["max_disp"]), 2)
                         for p, r in zip(pt, te)},
                "test_mape": round(float(np.mean([abs(ape(p, r["max_disp"]))
                                                  for p, r in zip(pt, te)])), 2),
            }

    # ---- self-check: 'lin@ridge' must reproduce M3, 'lin@phys' must reproduce M5
    m3_pred, _ = B.fit_m3(tr, "max_disp", B._alpha_grid())
    m5_pred, _ = B.fit_m5(tr, "max_disp", "u", B._alpha_grid())
    checks = []
    for tag, ref in (("lin@ridge", m3_pred), ("lin@phys", m5_pred)):
        ref_ape = [ape(p, r["max_disp"]) for p, r in zip(ref(va), va)]
        got = [results[tag]["val"][r["case_id"]] for r in va]
        d = max(abs(a - b) for a, b in zip(got, ref_ape))
        checks.append((tag, d))
        print(f"  self-check  {tag:11s} vs baseline : max |dAPE| on val = {d:.2e} pp")
    drift = max(d for _, d in checks)
    # ``lin`` uses s = sweep/20 where the baseline uses raw degrees.  Standardisation
    # makes the two designs identical up to round-off, so the only admissible source
    # of drift is the alpha grid landing on a neighbouring knot at the 1e-2 pp level.
    # Anything larger means the new design is not equivalent to the baseline and the
    # whole comparison would be against the wrong opponent.
    if drift > 5e-2:
        fails.append(f"'lin' does not reproduce the baseline (drift {drift:.3e} pp > 0.05)")

    # ---- table ------------------------------------------------------------ #
    print()
    print(f"{'form@tier':14s}{'p':>3s}{'cond':>8s}{'LOO%':>8s}{'LOO@20':>9s}"
          f"{'LOO@30':>9s}{'val40':>9s}{'test%':>8s}  ident")
    print("-" * 104)
    for tag, r in results.items():
        v40 = r["val"].get("naca4412_wingbox_sweep40")
        print(f"{tag:14s}{len(BASES[r['form']](np.array([1.0]))):3d}"
              f"{r['cond_number']:8.1f}{r['loo_mape']:8.2f}"
              f"{r['loo_station_ape_pct']['20deg']:9.2f}"
              f"{r['loo_station_ape_pct']['30deg']:9.2f}"
              f"{(v40 if v40 is not None else float('nan')):9.2f}"
              f"{r['test_mape']:8.2f}  {'yes' if r['identifiable'] else 'NO'}")
    print("  ridge = M3 recipe (no physics prefix) | phys = M5 recipe (beam prefix "
          "as fixed offset)")
    print("  LOO@20 / LOO@30 = leave that station out, predict it (leak-free). "
          "val40 = held-out single-axis extrapolation.")

    # ---- test rows, reported once ----------------------------------------- #
    print()
    print("  test rows, max_disp APE % (reported once, never used to choose):")
    cols = ["lin@ridge", "quad@ridge", "lin@phys", "quad@phys"]
    print(f"    {'case':44s}" + "".join(f"{c:>11s}" for c in cols))
    for cid in results["lin@ridge"]["test"]:
        print(f"    {cid:44s}" + "".join(f"{results[c]['test'][cid]:11.1f}"
                                         for c in cols))

    # ---- verdict ---------------------------------------------------------- #
    # Selection rule, fixed before looking at the numbers:
    #   tier      = phys (M5), because that is the row the project quotes
    #   primary   = LOO APE at the 30 deg station (leak-free "next station")
    #   guard 1   = train LOO may not get worse by >15 % relative to lin@phys
    #   guard 2   = condition number < 1e6 (M2 rule)
    cand = {t: r for t, r in results.items() if r["form"] not in () and t.endswith("@phys")}
    base_loo = results["lin@phys"]["loo_mape"]
    ok = {t: r for t, r in cand.items()
          if r["identifiable"] and r["loo_mape"] <= base_loo * 1.15}
    best = min(ok, key=lambda t: abs(results[t]["loo_station_ape_pct"]["30deg"]))
    chosen = results[best]
    print()
    print(f"  eligible @phys (identifiable & LOO not worse than 1.15x lin@phys): {sorted(ok)}")
    print(f"  CHOSEN FORM: {best}  (min |LOO@30| among eligible)")
    print(f"    |LOO@30| = {abs(chosen['loo_station_ape_pct']['30deg']):.2f} %  "
          f"vs lin@phys {abs(results['lin@phys']['loo_station_ape_pct']['30deg']):.2f} %")
    print(f"    val40    = {chosen['val'].get('naca4412_wingbox_sweep40')} %  "
          f"vs lin@phys {results['lin@phys']['val'].get('naca4412_wingbox_sweep40')} %"
          f"  <-- confirmation, not a selection input")
    print(f"    test MAPE= {chosen['test_mape']} %  vs lin@phys "
          f"{results['lin@phys']['test_mape']} % (the number D33 quotes)")

    doc = {
        "generated": "2026-10-24",
        "milestone": "M11 / D34 sweep-term form",
        "target": "max_disp",
        "design_note": (
            "train has 3 positive-sweep rows sharing one geometry; s^2/s^3 are "
            "non-zero on exactly those 3 rows, so a free cubic is exactly "
            "invertible there (M2 failure mode). Condition number is reported "
            "for every form and is a hard eligibility gate."),
        "selection_rule": {
            "primary": "min |LOO APE at 30 deg station| (leak-free)",
            "guard_1": "train LOO <= 1.15 x lin",
            "guard_2": "condition number < 1e6",
            "val_sweep40": "confirmation only",
            "test": "reported once, never used to choose",
        },
        "train_stations_deg": stations,
        "n_train_zero_sweep": n_zero,
        "lin_reproduces_m3_max_dape_pp": drift,
        "forms": results,
        "chosen": best,
        "fails": fails,
        "verdict": "PASS" if not fails else "CHECK",
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print()
    print(f"  VERDICT: {doc['verdict']}")
    for f in fails:
        print(f"    ! {f}")
    print(f"  wrote {OUT}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
