"""D36 A/B: does the station at 35 pay for itself?

Same 6 test cases both sides (D35 set), same alpha grid, same code -- only the
training set differs by one row:

* ``A_d35``  train 20 = D35 as shipped
* ``B_d36``  train 21 = + ``sweep35``

Two extra things get reported because they are what D36 was *for*, and neither
is in the test set:

* ``val_sweep40``  -- the taper-neutral 40 deg case whose error D35 blew up from
  -3.17 % to -12.79 %.  If B does not move it, the station bought nothing on the
  axis it was placed on.
* ``val_all``      -- the 7-case val set, same reason, less cherry-picked.

Sign convention: the per-case column is *signed* ``pred/true - 1`` in percent, so
an under-prediction shows as a negative number.  MAPE columns are unsigned.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "feagpt_repro"))

import numpy as np                          # noqa: E402

import baseline as B                        # noqa: E402

OUT = Path(__file__).resolve().parent
NEW = "naca4412_wingbox_sweep35"
VAL_SWEEP40 = "naca4412_wingbox_sweep40"
TARGETS = ("max_disp", "max_w", "max_von_mises", "max_von_mises_midsurface")
BOOT = 4000


def mape(pred, true):
    p, t = np.asarray(pred), np.asarray(true)
    return float(np.mean(np.abs(p - t) / t) * 100.0)


def boot_ci(pred, true, rng, n=BOOT):
    rel = np.asarray(pred) / np.asarray(true) - 1.0
    idx = rng.integers(0, len(rel), size=(n, len(rel)))
    return (float(np.percentile(np.abs(rel[idx]).mean(axis=1) * 100, 2.5)),
            float(np.percentile(np.abs(rel[idx]).mean(axis=1) * 100, 97.5)))


def paired(pa, pb, true, rng, n=BOOT):
    """Bootstrap CI of MAPE(B) - MAPE(A) on the same cases (paired)."""
    ea = np.abs(np.asarray(pa) / np.asarray(true) - 1.0)
    eb = np.abs(np.asarray(pb) / np.asarray(true) - 1.0)
    d = eb - ea
    idx = rng.integers(0, len(d), size=(n, len(d)))
    vals = d[idx].mean(axis=1) * 100.0
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)),
            float(d.mean() * 100.0))


def main() -> int:
    rows = B.load_family("wingbox")
    train_now = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    val = [r for r in rows if r["split"] == "val"]
    assert any(r["case_id"] == NEW for r in train_now), f"{NEW} is not in train"
    print(f"train {len(train_now)} / val {len(val)} / test {len(test)}")

    cfg = {"A_d35": [r for r in train_now if r["case_id"] != NEW],
           "B_d36": train_now}

    rng = np.random.default_rng(20261024)
    result: dict = {"test_cases": [r["case_id"] for r in test],
                    "val_cases": [r["case_id"] for r in val],
                    "boot": BOOT, "seed": 20261024, "by_target": {}}

    for key in TARGETS:
        print(f"\n=== target {key} ===")
        print(f"{'config':<10}{'n_tr':>5}{'alpha':>10}{'LOO':>8}{'testMAPE':>10}"
              f"{'95% CI':>18}{'maxAPE':>9}{'valMAPE':>9}{'v40':>8}")
        keep = {}
        for name, tr in cfg.items():
            pred, info = B.fit_m3(tr, key, B._alpha_grid(), quad=True)
            p = np.array(pred(test))
            t = np.array([r[key] for r in test])
            pv = np.array(pred(val))
            tv = np.array([r[key] for r in val])
            i40 = [i for i, r in enumerate(val) if r["case_id"] == VAL_SWEEP40][0]
            lo, hi = boot_ci(p, t, rng)
            rec = {"n_train": len(tr), "alpha": info["alpha"],
                   "loo_mape": info["loo_mape"], "test_mape": mape(p, t),
                   "ci95": [lo, hi],
                   "max_ape": float(np.max(np.abs(p / t - 1.0)) * 100.0),
                   "val_mape": mape(pv, tv),
                   "val_sweep40_ape": float((pv[i40] / tv[i40] - 1.0) * 100.0),
                   "per_case": {r["case_id"]: round(float(pp / tt - 1) * 100, 2)
                                for r, pp, tt in zip(test, p, t)}}
            result["by_target"].setdefault(key, {})[name] = rec
            keep[name] = p
            print(f"{name:<10}{len(tr):>5}{info['alpha']:>10.0e}{info['loo_mape']:>8.2f}"
                  f"{rec['test_mape']:>9.2f}%  [{lo:>5.2f},{hi:>5.2f}]"
                  f"{rec['max_ape']:>8.1f}%{rec['val_mape']:>8.2f}%"
                  f"{rec['val_sweep40_ape']:>7.2f}%")
        lo, hi, mu = paired(keep["A_d35"], keep["B_d36"], np.array([r[key] for r in test]), rng)
        result["by_target"][key]["paired_B_minus_A"] = {"mean": mu, "ci95": [lo, hi]}
        print(f"    paired B-A on test MAPE: {mu:+.2f} pp  [{lo:+.2f},{hi:+.2f}]"
              f"{'  (CI crosses 0 -> not significant)' if lo * hi < 0 else ''}")

    print("\n=== per-case signed error (max_disp) ===")
    print(f"{'case':<44}{'A_d35':>11}{'B_d36':>11}")
    for i, r in enumerate(test):
        cid = r["case_id"]
        a = result["by_target"]["max_disp"]["A_d35"]["per_case"][cid]
        b = result["by_target"]["max_disp"]["B_d36"]["per_case"][cid]
        print(f"{cid:<44}{a:>10.2f}%{b:>10.2f}%")

    (OUT / "d36_ab.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(f"\n-> d36_ab.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
