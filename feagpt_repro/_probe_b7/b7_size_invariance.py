#!/usr/bin/env python
"""Size-invariance probe for batch 7 - the open-hole size dimension's physics.

Howland's finite-width ``Kt`` sees only ``lambda = d/width``.  The 600x300_d30
val point and the shipped d20 baseline share ``lambda = 0.1``, so the theory
says their stress concentration factors must agree - the analytic yardstick
does not move when the specimen does.  This is the open-hole analogue of the
barrel's per-size closed forms (``verify_barrel_size.py``): a size sweep whose
yardstick cannot move is the one comparison a size extrapolation can actually
fail.  A systematic size error (width read from the wrong place, the deck
scaling the load with the wrong area) shows up here even though every other
gate is blind to it.

Reads four artifacts from disk; runs neither solver.

Usage::

    python _probe_b7/b7_size_invariance.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPRO = HERE.parent
sys.path.insert(0, str(REPRO))

from feagpt import open_hole, post                          # noqa: E402
from feagpt.spec import FEASpec                             # noqa: E402

#: (label, spec_path, ccx_result, abaqus_result) - the two lambda = 0.1 coupons.
#: The d20 baseline keeps its per-node fields only in the batch-4 *source*
#: trees (``outputs_hole`` / ``outputs_hole_abaqus``); the published dataset
#: tree stores the six-piece set without FRD/ODB.
PAIRS = (
    ("baseline_400x200_d20",
     REPRO / "outputs_hole" / "open_hole_panel_400x200_d20"
     / "open_hole_panel_400x200_d20.spec.json",
     REPRO / "outputs_hole" / "open_hole_panel_400x200_d20"
     / "open_hole_panel_400x200_d20.frd",
     REPRO / "outputs_hole_abaqus" / "open_hole_panel_400x200_d20"
     / "open_hole_panel_400x200_d20.odb.json"),
    ("b7_600x300_d30",
     REPRO / "_probe_b7" / "_batch7_specs" / "open_hole_panel_600x300_d30.spec.json",
     REPRO / "outputs_b7" / "open_hole_panel_600x300_d30"
     / "open_hole_panel_600x300_d30.frd",
     REPRO / "outputs_b7_abaqus" / "open_hole_panel_600x300_d30"
     / "open_hole_panel_600x300_d30.odb.json"),
)

TOL_PCT = 2.0  # verify_hole's Howland tolerance: both must sit there anyway

#: Which side the Howland gate sits on.  ``verify_hole.py`` gates the analytic
#: line on the **ccx** recovery and prints the Abaqus peak for reference only:
#: a peak is a recovery statistic, not an invariant (D8).  The shipped baseline
#: already sits 1.48 % below Howland on the Abaqus side (``_t4_probe/
#: verify_hole_full.json``, 6 PASS / 0 FAIL) - the averaging recovery reads the
#: steepest gradient low, and the d30 coupon's edge element is coarser in
#: absolute terms (pi*30/72 = 1.309 mm vs 0.873 mm), so its offset grows to
#: ~3 % without anything being wrong.  A real size error (wrong width, load
#: spread over the wrong area) would move the displacement field first - and
#: the d30 cross-solver displacement gap is 0.094 % (``_b7_gate3.json``).
HOWLAND_SIDE = "ccx"


def _kt(data: dict, spec: FEASpec) -> dict:
    p = open_hole.parse_params(spec)
    nodes = data["nodes"]
    stress = data["results"].get("STRESS") or {}
    cx, cy = p.center()
    rh = 0.5 * float(p.hole_d)
    vm = post.von_mises
    prof = [vm(stress[t]) for t, (x, y, _z) in nodes.items()
            if abs(math.hypot(x - cx, y - cy) - rh) < 1e-3 and t in stress]
    s_max = max(prof)
    F = float(spec.load.magnitude)
    return {"lambda": p.lambda_ratio,
            "sigma_max": s_max,
            "Kt_gross": s_max / open_hole.gross_stress(F, p),
            "Kt_net": s_max / open_hole.net_stress(F, p),
            "howland_net": open_hole.howland_kt_net(p.lambda_ratio),
            "howland_gross": open_hole.howland_kt_gross(p.lambda_ratio),
            "n_edge": len(prof)}


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b) * 100.0 if b else float("inf")


def main() -> int:
    print("size invariance: same lambda -> same Kt, whatever the footprint")
    print("=" * 96)
    out: dict = {}
    kts: dict = {}
    for label, spec_path, ccx_path, abq_path in PAIRS:
        spec = FEASpec.from_json(spec_path)
        kc = _kt(post.load_any(ccx_path), spec)
        ka = _kt(post.load_results_json(abq_path), spec)
        kts[label] = {"ccx": kc, "abaqus": ka}
        print(f"{label:22s} lambda={kc['lambda']:.3f}  "
              f"Kt_gross ccx {kc['Kt_gross']:.4f} / abq {ka['Kt_gross']:.4f}  "
              f"(Howland {kc['howland_gross']:.4f}; edge n={kc['n_edge']})")
    base, b7 = kts["baseline_400x200_d20"], kts["b7_600x300_d30"]
    # The size-invariance gate: WITHIN one code, same recovery path on both
    # coupons, same lambda - any gap is either real size dependence or the
    # documented +-1 % peak scatter (_t4_probe/t4_convergence.py: 2.97-3.04).
    gap_c = _rel(base["ccx"]["Kt_gross"], b7["ccx"]["Kt_gross"])
    gap_a = _rel(base["abaqus"]["Kt_gross"], b7["abaqus"]["Kt_gross"])
    # The analytic gate: ccx size point vs Howland, exactly what verify_hole
    # gates.  The Abaqus offset is printed beside the baseline's own offset for
    # context and never asserted on (D8).
    err_c = _rel(b7["ccx"]["Kt_gross"], b7["ccx"]["howland_gross"])
    err_a = _rel(b7["abaqus"]["Kt_gross"], b7["abaqus"]["howland_gross"])
    err_base_c = _rel(base["ccx"]["Kt_gross"], base["ccx"]["howland_gross"])
    err_base_a = _rel(base["abaqus"]["Kt_gross"], base["abaqus"]["howland_gross"])
    ok = (max(gap_c, gap_a) <= TOL_PCT
          and (err_c <= TOL_PCT if HOWLAND_SIDE == "ccx"
               else max(err_c, err_a) <= TOL_PCT))
    print("-" * 96)
    print(f"Kt_gross baseline vs size point: ccx {gap_c:.3f} % / abaqus "
          f"{gap_a:.3f} % (tol {TOL_PCT:g} %)  [GATED]")
    print(f"size point vs Howland:           ccx {err_c:+.3f} % (tol "
          f"{TOL_PCT:g} %)  [GATED - verify_hole gates the analytic line on ccx]")
    print(f"abaqus peak vs Howland:          size {err_a:+.3f} % / baseline "
          f"{err_base_a:+.3f} %  [reference only, D8 - recovery statistic, "
          f"not an invariant]")
    print(f"ccx baseline vs Howland:         {err_base_c:+.3f} %  [reference]")
    print("VERDICT:", "PASS" if ok else "FAIL",
          "- the analytic yardstick did not move with the specimen")
    out = {"pairs": kts, "baseline_vs_size_point_pct": {"ccx": round(gap_c, 5),
                                                        "abaqus": round(gap_a, 5)},
           "size_point_vs_howland_pct": {"ccx": round(err_c, 5),
                                         "abaqus": round(err_a, 5)},
           "baseline_vs_howland_pct": {"ccx": round(err_base_c, 5),
                                       "abaqus": round(err_base_a, 5)},
           "howland_gate_side": HOWLAND_SIDE,
           "tol_pct": TOL_PCT, "pass": ok}
    (HERE / "_b7_size_invariance.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"report -> {HERE / '_b7_size_invariance.json'}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
