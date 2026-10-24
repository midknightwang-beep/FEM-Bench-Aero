"""M14 -- why is the same model 2.63 % on its own test set but 5.88 % under
leave-one-out?  Attribute the gap to a cause instead of guessing.

Three training sets, one fixed evaluation set (the published 6 test cases),
one estimator (M3q, alpha re-selected by inner LOO inside each training set):

  A  train=21          -> the published protocol (baseline.py)
  B  train=21+val=28   -> does merely *adding* the val extremes move the answer?
  C  train=33 minus the held-out case, averaged over the 6 folds
                       -> this is what all_loo.py reports

A vs B isolates "more data, same design-space span" (should help or be neutral).
B vs C isolates "the fold set now contains the other test points", i.e. whether
the single held-out point is being predicted from a fold set that already
contains its neighbours.

If A < B ~ C, the published number is optimistic because the protocol trains
only on the near-baseline OFAT cloud while evaluating on points that were
*targeted* by three rounds of dataset additions (D34/D35/D36).

Run:  python _probe_m14/gap_attribution.py
Out:  _probe_m14/gap_attribution.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPRO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPRO))
import baseline as B  # noqa: E402

OUT = Path(__file__).with_suffix(".json")
TGT = "max_disp"


def evaluate(tr, te):
    f, info = B.fit_m3(tr, TGT, B._alpha_grid(), quad=True)
    pred = f(te)
    apes = [(p - r[TGT]) / r[TGT] * 100.0 for p, r in zip(pred, te)]
    v = np.abs(apes)
    return {
        "n_train": len(tr), "n_test": len(te),
        "alpha": info["alpha"], "train_loo": info["loo_mape"],
        "mape": float(v.mean()), "median": float(np.median(v)),
        "max": float(v.max()),
        "per_case": {r["case_id"].replace("naca4412_wingbox_", ""): round(a, 3)
                     for r, a in zip(te, apes)},
    }


def main() -> dict:
    rows = B.load_family("wingbox")
    tr = [r for r in rows if r["split"] == "train"]
    val = [r for r in rows if r["split"] == "val"]
    te = [r for r in rows if r["split"] == "test"]

    A = evaluate(tr, te)
    Bb = evaluate(tr + val, te)

    # C: for each test case, train on everything except it (33 cases)
    apes_c, per_c = [], {}
    for held in te:
        fold = [r for r in rows if r["case_id"] != held["case_id"]]
        f, info = B.fit_m3(fold, TGT, B._alpha_grid(), quad=True)
        p = f([held])[0]
        a = (p - held[TGT]) / held[TGT] * 100.0
        apes_c.append(abs(a))
        per_c[held["case_id"].replace("naca4412_wingbox_", "")] = round(a, 3)
    C = {"n_train": len(rows) - 1, "n_test": len(te),
         "mape": float(np.mean(apes_c)),
         "median": float(np.median(apes_c)),
         "max": float(max(apes_c)), "per_case": per_c}

    # D: same as C but restricting the fold set to train+val only (28-1 = 27)
    apes_d, per_d = [], {}
    for held in te:
        fold = [r for r in rows if r["split"] != "test" and r["case_id"] != held["case_id"]]
        f, info = B.fit_m3(fold, TGT, B._alpha_grid(), quad=True)
        p = f([held])[0]
        a = (p - held[TGT]) / held[TGT] * 100.0
        apes_d.append(abs(a))
        per_d[held["case_id"].replace("naca4412_wingbox_", "")] = round(a, 3)
    D = {"n_train": 27, "n_test": len(te),
         "mape": float(np.mean(apes_d)), "median": float(np.median(apes_d)),
         "max": float(max(apes_d)), "per_case": per_d}

    res = {
        "target": TGT,
        "A_published_train21": A,
        "B_train28_incl_val": Bb,
        "D_loo_trainvalonly": D,
        "C_loo_all33": C,
        "reading": ("A is the published protocol; B adds val without touching"
                    " the test cases; D/C hold the test case out entirely."),
    }
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    r = main()
    print(f"target = {r['target']}\n")
    print(f"{'protocol':<34}{'n_tr':>6}{'MAPE':>8}{'med':>7}{'max':>8}{'alpha':>9}")
    for k, lbl in (("A_published_train21", "A published (train=21)"),
                   ("B_train28_incl_val", "B train+val (28)"),
                   ("D_loo_trainvalonly", "D LOO on train+val (27)"),
                   ("C_loo_all33", "C LOO on all 33")):
        d = r[k]
        print(f"{lbl:<34}{d['n_train']:>6}{d['mape']:>8.2f}{d['median']:>7.2f}"
              f"{d['max']:>8.2f}{d.get('alpha', float('nan')):>9.2g}")
    print("\n=== per-case, A vs B vs D vs C ===")
    cases = list(r["A_published_train21"]["per_case"])
    print(f"{'case':<24}" + "".join(f"{n:>9}" for n in ("A", "B", "D", "C")))
    for c in cases:
        print(f"{c:<24}" + "".join(
            f"{r[k]['per_case'][c]:>9.2f}" for k in
            ("A_published_train21", "B_train28_incl_val",
             "D_loo_trainvalonly", "C_loo_all33")))
    print(f"\nwritten -> {OUT}")
