#!/usr/bin/env python
"""M10 / D33 - cross-solver verification of the single ``sweep30`` case.

Deliberately *not* a copy of the M8 checker: it imports ``_probe_m8/xval_m8``
and only redirects its data root, so the four checks (same mesh / equilibrium /
max displacement / per-node von Mises median) are byte-for-byte the same code
that produced ``_xval_m8.json``.  Two implementations of a gate is how gates
drift apart.

What the D33 point has to prove before it may join train:

* the two codes solved the *same* mesh (otherwise nothing below means anything),
* the root reactions balance the applied 500 N (the one check that depends on
  neither code's conventions; ccx sums total external force, abaqus sums
  reactions, so only the magnitude is comparable),
* the displacement fields agree -- reported, not gated (D20: model-wide max|u|
  sits on a single node),
* the per-node von Mises median agrees -- this is the gated field check (D8:
  peaks are recorded, never compared bare).

Usage::

    python _probe_m10/xval_m10.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPRO = HERE.parent
sys.path.insert(0, str(REPRO / "_probe_m8"))
sys.path.insert(0, str(REPRO))

import xval_m8 as X  # noqa: E402

#: Point the shared checker at this milestone's output directories.  ``HERE`` is
#: the only thing that differs, so the checks themselves are the M8 ones.
X.HERE = HERE

CASE = "naca4412_wingbox_sweep30"
OUT = REPRO.parent / "FEM-Bench-Aero" / "_xval_d33.json"


def main() -> int:
    r = X.check_one(CASE)
    d = r["max_disp"]
    s = r["stress_field"]
    m = r["mesh"]
    eq = r["equilibrium"]

    print("=" * 78)
    print("  M10 / D33 CROSS-SOLVER - sweep30 station (ccx vs abaqus)")
    print("=" * 78)
    print(f"  case                 {r['case']}")
    print(f"  sources              ccx={r['sources']['ccx']}  abaqus={r['sources']['abaqus']}")
    print(f"  mesh                 n_ccx={m['n_ccx']}  n_abaqus={m['n_abaqus']}  "
          f"identical_labels={m['identical_labels']}  "
          f"max_coord_diff={m['max_coord_diff_mm']:.3e} mm")
    print(f"  equilibrium          roots={eq['roots']}  load={eq['load_n']} N  "
          f"dominant={eq['ccx']['dominant']}/{eq['abaqus']['dominant']}  "
          f"worst residual={eq['worst_residual_pct']:.3e} %  (tol {X.EQ_TOL_PCT})")
    print(f"  max|u| (not gated)   ccx={d['ccx']['mm']:.5f} mm  "
          f"abaqus={d['abaqus']['mm']:.5f} mm  gap={d['gap_pct']:.2f} %  "
          f"abs={d['abs_diff_mm']:.3e} mm")
    print(f"  vM median (gated)    n_common={s['n_common']}  median={s['median_pct']:.2f} %  "
          f"p90={s['p90_pct']:.2f} %  (tol {s['tol_pct']})")
    pv = r["peak_von_mises"]
    if "ccx" in pv and "abaqus" in pv:
        print(f"  vM peak (not gated)  ccx={pv['ccx']['vm_mpa']:.3f} @ {pv['ccx']['node']}  "
              f"abaqus={pv['abaqus']['vm_mpa']:.3f} @ {pv['abaqus']['node']}")
    print("-" * 78)
    print(f"  VERDICT: {'PASS' if r['pass'] else 'CHECK'}")
    for f in r["failures"]:
        print(f"    ! {f}")

    OUT.write_text(json.dumps({
        "generated": "2026-10-24",
        "milestone": "D33 sweep 30 deg intermediate station",
        "gates": {"equilibrium_pct": X.EQ_TOL_PCT,
                  "stress_median_pct": X.STRESS_MED_TOL_PCT,
                  "coord_tol_mm": X.COORD_TOL},
        "n_cases": 1,
        "n_fail": 0 if r["pass"] else 1,
        "verdict": "PASS" if r["pass"] else "CHECK",
        "shared_implementation": "_probe_m8/xval_m8.py:check_one (HERE redirected)",
        "cases": [r],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {OUT}")
    return 0 if r["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
