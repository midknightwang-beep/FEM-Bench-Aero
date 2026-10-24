"""D36 side-probe: does the new station make a *cubic* sweep term identifiable?

Nothing is landed here.  This is the evidence the next decision needs, gathered
while the D36 dataset is fresh, and it exists because D34's rejection of the
cubic rested on an argument that D36 just invalidated:

  D34 said: "train holds only **3** positive-sweep rows and they share one
  geometry, so a 3-parameter cubic is exactly invertible on them -- it fits to
  machine zero and the 40 deg answer is pure guesswork."

After D36, train holds 4 taper-neutral positive stations (10 / 20 / 30 / 35)
plus 2 interaction rows.  A cubic is no longer exactly invertible, so the old
reason is spent -- but "the objection expired" is not "the cubic is right", and
it certainly is not licence to switch forms on the strength of one measurement.

What the measurement says (``d36_prediction_resolved.json``): the per-degree
slope on the taper-neutral line runs 0.00939 / 0.02459 / 0.05136 / 0.08835 /
0.13402 over 0-10 / 10-20 / 20-30 / 30-35 / 35-40 deg.  A quadratic in s makes
that slope grow *linearly* in s; going from the 30-35 bin (mid s = 1.625) to the
35-40 bin (mid s = 1.875), s rises 15.4 % while the slope rises **51.7 %**.  So
the curvature itself is growing, which is at least suggestive for a cubic and is
the reason this probe is worth running at all.

Protocol (D34-b): form decisions are judged on **leave-the-highest-station-out**
LOO, not on val.  Val is reported, test is reported, but neither picks the form.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "feagpt_repro"))

import numpy as np                                          # noqa: E402

import baseline as B                                        # noqa: E402

OUT = Path(__file__).resolve().parent
KEY = "max_disp"
FEATS = B.FEATS
BASE = [f for f in FEATS if f != "sweep"]


def design(rows, form: str):
    """Wing-box design matrix with the sweep term in the requested basis."""
    cols, names = [], []
    for f in BASE:
        v = np.array([float(r[f]) for r in rows])
        if f in B.MULT_FEATS:
            v = np.log(v)
        cols.append(v)
        names.append(f)
    s = np.array([float(r["sweep"]) for r in rows]) / B.SWEEP_DEG
    cols.append(s)
    names.append("sweep_s")
    if form in ("quad", "cubic"):
        cols.append(s ** 2)
        names.append("sweep_s2")
    if form == "cubic":
        cols.append(s ** 3)
        names.append("sweep_s3")
    return np.column_stack(cols), names


def independent_subset(Xs: np.ndarray, names: list[str], tol: float = 1e-10):
    """Greedy Gram-Schmidt: keep the columns that actually span the design.

    This is the D34 repair for the condition-number mistake.  ``np.linalg.cond``
    on the full standardised matrix returns ~1e19 for *every* form here, because
    the wing box carries structurally redundant columns (``is_T`` is constant in
    this family, ``n_web`` and ``web_pos`` are collinear).  Reporting that number
    as "the cubic is ill-conditioned" would be exactly the error D34 recorded:
    **compute rank first, drop, then report the condition number of what is
    left** -- and say which columns were dropped, so the reader can see whether
    the dropped one is the term under discussion.
    """
    keep: list[int] = []
    Q = np.zeros((Xs.shape[0], 0))
    for j in range(Xs.shape[1]):
        v = Xs[:, j].copy()
        if Q.shape[1]:
            v = v - Q @ (Q.T @ v)
        n = float(np.linalg.norm(v))
        if n > tol * max(1.0, float(np.linalg.norm(Xs[:, j]))):
            keep.append(j)
            Q = np.column_stack([Q, v / n])
    dropped = [n for i, n in enumerate(names) if i not in keep]
    reduced = Xs[:, keep]
    return keep, dropped, float(np.linalg.cond(reduced))


def fit(tr, form: str):
    X, names = design(tr, form)
    y = np.log([r[KEY] for r in tr])
    alpha, loo = B._loocv_alpha(X, y, B._alpha_grid())
    mu, sd, _ = B._zfit(X)
    Xs = (X - mu) / sd
    ym, w = B._ridge(Xs, y, alpha)
    keep, dropped, cond = independent_subset(Xs, names)

    def pred(rows):
        Xe = (design(rows, form)[0] - mu) / sd
        return list(np.exp(Xe @ w + ym))
    return pred, {"alpha": alpha, "train_loo": loo, "cond": cond,
                  "rank": len(keep), "n_cols": Xs.shape[1],
                  "dropped_cols": dropped}


def sape(p, o):
    return (p - o) / o * 100.0


def mape(pred, true):
    p, t = np.asarray(pred), np.asarray(true)
    return float(np.mean(np.abs(p - t) / t) * 100.0)


def main() -> int:
    rows = B.load_family("wingbox")
    tr = [r for r in rows if r["split"] == "train"]
    va = [r for r in rows if r["split"] == "val"]
    te = [r for r in rows if r["split"] == "test"]
    print(f"train {len(tr)} / val {len(va)} / test {len(te)}   (D36 dataset)")

    top = max(tr, key=lambda r: r["sweep"])          # sweep35
    second = sorted((r for r in tr if r["sweep"] > 0),
                    key=lambda r: -r["sweep"])[1]
    print(f"leave-out targets: top station {top['case_id']} "
          f"({top['sweep']:g} deg), runner-up {second['case_id']} ({second['sweep']:g} deg)")

    i40v = [i for i, r in enumerate(va) if r["case_id"] == "naca4412_wingbox_sweep40"][0]
    i40t = [i for i, r in enumerate(te)
            if r["case_id"] == "naca4412_wingbox_sweep40_taper040"][0]

    print(f"\n{'form':<8}{'k':>3}{'alpha':>9}{'cond':>10}{'rank':>6}"
          f"{'trainLOO':>10}{'LOO@top':>10}{'LOO@2nd':>10}"
          f"{'valMAPE':>9}{'v40':>8}{'testMAPE':>10}{'t40':>8}")
    out = {}
    for form in ("lin", "quad", "cubic"):
        pred, info = fit(tr, form)

        # -- leave-the-highest-station-out, refit without that row ---------- #
        tr_top = [r for r in tr if r["case_id"] != top["case_id"]]
        p_top = float(fit(tr_top, form)[0]([top])[0])
        e_top = sape(p_top, top[KEY])

        tr_2nd = [r for r in tr if r["case_id"] != second["case_id"]]
        p_2nd = float(fit(tr_2nd, form)[0]([second])[0])
        e_2nd = sape(p_2nd, second[KEY])

        pv = np.array(pred(va))
        pt = np.array(pred(te))
        rec = {"alpha": info["alpha"], "cond": info["cond"], "rank": info["rank"],
               "n_cols": info["n_cols"], "dropped_cols": info["dropped_cols"],
               "train_loo": info["train_loo"],
               "loo_top": {"case": top["case_id"], "pred": p_top,
                           "obs": top[KEY], "ape": e_top},
               "loo_second": {"case": second["case_id"], "pred": p_2nd,
                              "obs": second[KEY], "ape": e_2nd},
               "val_mape": mape(pv, [r[KEY] for r in va]),
               "val_sweep40_ape": sape(float(pv[i40v]), va[i40v][KEY]),
               "test_mape": mape(pt, [r[KEY] for r in te]),
               "test_sweep40_taper040_ape": sape(float(pt[i40t]), te[i40t][KEY])}
        out[form] = rec
        print(f"{form:<8}{info['n_cols']:>3}{info['alpha']:>9.0e}{info['cond']:>10.1f}"
              f"{info['rank']:>6}{info['train_loo']:>10.2f}{e_top:>9.2f}%{e_2nd:>9.2f}%"
              f"{rec['val_mape']:>8.2f}%{rec['val_sweep40_ape']:>7.2f}%"
              f"{rec['test_mape']:>9.2f}%{rec['test_sweep40_taper040_ape']:>7.2f}%")

    print("\n[read this way] LOO@top = leave sweep35 out and predict it (D34-b: this is")
    print("               what decides forms).  v40 = val sweep40 (taper neutral),")
    print("               t40 = test sweep40_taper040 (double extrapolation).")

    # explicit statement of what the D34 objection was and whether it still applies
    base = out["quad"]
    print(f"\n[cubic identifiability] n_cols {out['cubic']['n_cols']}, "
          f"numerical rank {out['cubic']['rank']}, cond {out['cubic']['cond']:.1f}")
    for form, rec in out.items():
        print(f"  {form:<6} dropped columns: {rec['dropped_cols'] or '(none)'}")
    print(f"  D34's objection was an exactly-invertible 3-point cubic; train now holds "
          f"{sum(1 for r in tr if r['sweep'] > 0)} positive-sweep rows.")

    payload = {"note": "form comparison on the D36 dataset; NOTHING landed",
               "target": KEY, "dataset": {"train": len(tr), "val": len(va), "test": len(te)},
               "forms": out,
               "measured_expectation": (
                   "slope per deg 0.05136 (20-30) -> 0.08835 (30-35) -> 0.13402 (35-40); "
                   "s goes 1.625 -> 1.875 (+15.4 %) while slope goes +51.7 %, so curvature "
                   "is still growing -- a quadratic in s cannot express that")}
    (OUT / "sweep_form_d36.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n-> sweep_form_d36.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
