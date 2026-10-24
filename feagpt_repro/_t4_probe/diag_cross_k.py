#!/usr/bin/env python
"""Measure the cross-solver gap that made ``verify_hole.hole.cross-solver`` FAIL.

This is a **measurement**, not a gate.  The gate (``verify_hole.TOL_CROSS_PCT``)
compared the two codes' *hole-edge peak* von Mises and demanded 1 % agreement;
measured, the peak sits 1.92 % apart while the same fields' *median* node
agrees to ~1 %, and the displacement field to ~0.2 %.  That is the exact shape
D8 warned about: two codes reporting the *same* physical quantity reach it
through different stress-recovery reductions, so a peak -- the most
discretisation-sensitive statistic there is -- cannot be compared bare.

So this script prints, for the one mesh and the one load both codes shared:

  * displacement: max |u| per code and the per-node median gap;
  * hole-edge stress: peak, median and mean per-node gap, for both the
    membrane block (``STRESS``) and the outer-fibre block (``STRESS_PEAK``);
  * the collapse bookkeeping on the ccx side, to rule out an orphaned hole
    node being blamed for a recovery difference.

Inputs are the artifacts ``verify_hole.py`` just wrote, so it re-runs nothing.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

REPRO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPRO))

from feagpt import open_hole, post  # noqa: E402

CCX = REPRO / "outputs/_verify_hole/verify_hole_kt"
ABQ = REPRO / "outputs/_verify_hole_abaqus/verify_hole_kt"


def _pct(a: float, b: float) -> float:
    return (a - b) / b * 100.0 if b else float("inf")


def _edge_vm(data: dict, p: "open_hole.OpenHoleParams", block: str) -> dict[int, float]:
    cx, cy = p.center()
    rh = 0.5 * p.hole_d
    st = data["results"].get(block) or {}
    out: dict[int, float] = {}
    for t, (x, y, _z) in data["nodes"].items():
        if abs(math.hypot(x - cx, y - cy) - rh) < 1e-3 and t in st:
            out[t] = post.von_mises(st[t])
    return out


def _max_u(data: dict) -> tuple[float, int]:
    disp = data["results"].get("DISP") or {}
    mag = {t: (v[3] if len(v) >= 4 else math.sqrt(sum(c * c for c in v[:3])))
           for t, v in disp.items()}
    t = max(mag, key=mag.get)
    return mag[t], t


def main() -> int:
    ccx = post.load_any(CCX / "verify_hole_kt.frd")
    abq = post.load_results_json(ABQ / "verify_hole_kt.odb.json")
    p = open_hole.OpenHoleParams()
    F = float(open_hole.make_spec("x").load.magnitude)

    print("=== blocks present")
    print("  ccx:", sorted(ccx["results"]))
    print("  abq:", sorted(abq["results"]))
    print("  ccx meta.collapse:", json.dumps(ccx.get("meta", {}).get("collapse")))
    print("  abq meta.stress_components:", abq.get("meta", {}).get("stress_components"))
    print("  abq meta.section_points:", abq.get("meta", {}).get("section_points"))
    print("  abq meta.stress_candidates_max_vm:",
          json.dumps(abq.get("meta", {}).get("stress_candidates_max_vm")))

    # ---- displacement -------------------------------------------------- #
    uc, tc = _max_u(ccx)
    ub, tb = _max_u(abq)
    dc = ccx["results"]["DISP"]
    db = abq["results"]["DISP"]
    common = sorted(set(dc) & set(db))
    gaps = [abs(math.sqrt(sum(x * x for x in db[t][:3]))
                - math.sqrt(sum(x * x for x in dc[t][:3])))
            / math.sqrt(sum(x * x for x in dc[t][:3])) * 100.0
            for t in common if sum(x * x for x in dc[t][:3]) > 0]
    print("\n=== displacement (common nodes: %d)" % len(common))
    print(f"  max |u|  ccx {uc:.6f} mm (node {tc}) | abq {ub:.6f} mm (node {tb})"
          f"  -> {_pct(ub, uc):+.3f} %")
    print(f"  per-node |u| gap: median {statistics.median(gaps):.4f} %  "
          f"mean {statistics.mean(gaps):.4f} %  max {max(gaps):.4f} %")

    # ---- hole-edge stress, both reductions ----------------------------- #
    sig_gross = open_hole.gross_stress(F, p)
    for block in ("STRESS", "STRESS_PEAK"):
        ec = _edge_vm(ccx, p, block)
        eb = _edge_vm(abq, p, block)
        if not ec or not eb:
            print(f"\n=== {block}: missing (ccx {len(ec)}, abq {len(eb)})")
            continue
        thr = sorted(set(ec) & set(eb))
        rel = [_pct(eb[t], ec[t]) for t in thr if ec[t] > 0]
        sc = max(ec.values())
        sb = max(eb.values())
        print(f"\n=== hole-edge {block}  (ccx {len(ec)} nodes, abq {len(eb)}, "
              f"common {len(thr)})")
        print(f"  peak      ccx {sc:.4f} MPa (Kt_gross {sc/sig_gross:.4f}) | "
              f"abq {sb:.4f} MPa (Kt_gross {sb/sig_gross:.4f}) -> {_pct(sb, sc):+.3f} %")
        print(f"  per-node  median {statistics.median(rel):+.3f} %  "
              f"mean {statistics.mean(rel):+.3f} %  "
              f"min {min(rel):+.3f} %  max {max(rel):+.3f} %")

    # ---- the two conventions, for the record --------------------------- #
    print("\n=== nominal stresses at lambda = %.3f" % p.lambda_ratio)
    print(f"  gross {sig_gross:.4f} MPa  net {open_hole.net_stress(F, p):.4f} MPa  "
          f"(ratio {sig_gross/open_hole.net_stress(F,p):.4f})")

    # ---- does the rewritten gate actually bite? ------------------------ #
    # A gate that cannot fail is not a gate.  The measured pair must pass and
    # a pair just past either bound must fail; if the boundary does not flip,
    # the assertion is decorative.
    from verify_hole import TOL_CROSS_DISP_PCT, TOL_CROSS_VM_MEDIAN_PCT
    print(f"\n=== hole.cross-solver boundary check "
          f"(disp tol {TOL_CROSS_DISP_PCT:g} %, median tol "
          f"{TOL_CROSS_VM_MEDIAN_PCT:g} %)")
    measured = None
    for block in ("STRESS",):
        ec = _edge_vm(ccx, p, block)
        eb = _edge_vm(abq, p, block)
        thr = sorted(set(ec) & set(eb))
        rel = sorted((_pct(eb[t], ec[t]) for t in thr if ec[t] > 0), key=abs)
        measured = statistics.median(abs(x) for x in rel)
    du = abs(_pct(ub, uc))
    trials = [
        ("as measured", du, measured, True),
        ("median exactly at tol", du, TOL_CROSS_VM_MEDIAN_PCT, True),
        ("median just past tol", du, TOL_CROSS_VM_MEDIAN_PCT + 0.01, False),
        ("displacement just past tol", TOL_CROSS_DISP_PCT + 0.01, measured, False),
    ]
    bad = 0
    for label, gu, med, want in trials:
        ok = gu <= TOL_CROSS_DISP_PCT and med <= TOL_CROSS_VM_MEDIAN_PCT
        flag = "ok " if ok == want else "!! "
        bad += ok != want
        print(f"  {flag}{label}: disp {gu:.4f} %, median {med:.4f} % "
              f"-> gate {ok} (expected {want})")
    print(f"  boundary behaves as intended: {bad == 0}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
