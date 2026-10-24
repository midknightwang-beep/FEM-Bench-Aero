"""M14 -- honest generalisation estimate: leave-one-out over *all* wing-box cases.

The published number (`max_disp` test MAPE 2.63 %) is measured on 6 points that
have been used to drive three rounds of dataset changes (D34/D35/D36).  Any
number produced that way is optimistically biased, and the project itself
records the tell: the same model scores 6.30 % on `val` and 2.63 % on `test`,
and 5.5-5.9 % on the two genuinely new *forms* in the test set.

What a downstream user actually needs is: "I bring a wing box that nobody has
solved -- how wrong will the surrogate be?"  That is not estimable from the
test set.  The least-biased estimate available without new solves is
**leave-one-out over every case in the family** (34), because each fold's
held-out point is predicted by a model that never saw it, and the fold set is
the whole (unevenly spread) design space rather than the curated 6.

Caveat stated up front: LOO is still *interpolation-flavoured* -- every
held-out point has neighbours in the fold set.  So this number is a **lower
bound on the error for a genuinely distant new design**, and an **upper bound
on what the 6-point test set can claim**.  Both directions matter.

Run:  python _probe_m14/all_loo.py
Out:  _probe_m14/all_loo.json
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
TARGETS = ("max_disp", "max_w", "max_von_mises", "max_von_mises_midsurface")


def main() -> dict:
    rows = B.load_family("wingbox")
    n = len(rows)
    res: dict = {"n_cases": n, "folds": {}}

    grid = B._alpha_grid()
    for tgt in TARGETS:
        preds = {}
        for i in range(n):
            tr = rows[:i] + rows[i + 1:]
            te = [rows[i]]
            # same estimator family the project publishes (M3q: ridge with the
            # quadratic sweep term); alpha re-selected by inner LOO in every
            # fold so no fold benefits from a hyper-parameter tuned on itself.
            f, info = B.fit_m3(tr, tgt, grid, quad=True)
            preds[rows[i]["case_id"]] = {
                "pred": float(f(te)[0]),
                "obs": float(rows[i][tgt]),
                "split": rows[i]["split"],
            }
        apes = {}
        for cid, r in preds.items():
            apes[cid] = (r["pred"] - r["obs"]) / r["obs"] * 100.0
        v = np.array([abs(x) for x in apes.values()])
        res["folds"][tgt] = {
            "mape": float(v.mean()),
            "median": float(np.median(v)),
            "max": float(v.max()),
            "p90": float(np.percentile(v, 90)),
            "apes": {k: round(x, 3) for k, x in apes.items()},
            "worst": sorted(apes.items(), key=lambda kv: -abs(kv[1]))[:5],
        }

    # the same folds, but reported per original split -- shows whether the
    # curated test set is really easier than the rest
    md = res["folds"]["max_disp"]
    by_split = {}
    for sp in ("train", "val", "test"):
        ids = [c for c, r in
               ((cid, md["apes"][cid]) for cid in md["apes"])
               if True]
        sel = [abs(md["apes"][c]) for c in md["apes"] if
               next(r["split"] for r in rows if r["case_id"] == c) == sp]
        by_split[sp] = {"n": len(sel), "mape": float(np.mean(sel)) if sel else None,
                        "max": float(max(sel)) if sel else None}
    res["max_disp_by_original_split"] = by_split

    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    r = main()
    print(f"n cases = {r['n_cases']}")
    print(f"\n{'target':<30}{'MAPE':>8}{'med':>8}{'p90':>8}{'max':>8}")
    for t, d in r["folds"].items():
        print(f"{t:<30}{d['mape']:>8.2f}{d['median']:>8.2f}{d['p90']:>8.2f}{d['max']:>8.2f}")
    print("\n=== max_disp: LOO error grouped by the case's ORIGINAL split ===")
    for sp, d in r["max_disp_by_original_split"].items():
        print(f"  {sp:<6} n={d['n']:<3} MAPE={d['mape']:.2f} %   max={d['max']:.2f} %")
    print("\n=== max_disp worst 5 folds ===")
    for cid, ape in r["folds"]["max_disp"]["worst"]:
        print(f"  {cid.replace('naca4412_wingbox_',''):<24}{ape:+8.2f} %")
    print(f"\nwritten -> {OUT}")
