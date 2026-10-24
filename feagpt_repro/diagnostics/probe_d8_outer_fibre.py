#!/usr/bin/env python
"""D8 probe: is the expanded-shell outer fibre really ``6 M / t^2``?

Why this exists
---------------
D8 declares the archive's stress to be the **outer fibre**, and CalculiX can
only reach it through ``OUTPUT=3D`` (the expanded shell, every mid-surface node
written twice at +/-t/2).  That mechanism is only worth shipping if the number
it produces *is* the bending stress.  So it is checked here against a plate with
a closed-form answer, two independent ways:

* **against the closed form** - ``6 Mx/t^2`` from the Navier double-sine series;
* **against the FE's own displacement field** - fit ``w(x,y)`` over a disk at the
  centre with a quadratic by least squares and form ``-D(w,xx + nu w,yy)``.

The second one is not redundant, and it earned its place: it is how the *first*
version of the closed form was caught being wrong.  That version carried
``sin(m pi/2) = s_m`` from the shape function and then multiplied by ``s_m``
again, doubling the sign and turning the sum all-positive - inflating the
reference by 37 % (0.0705 -> 0.0967 on this plate) while still looking entirely
like a plate formula.  Two witnesses disagreeing by 37 % is what made the bug
findable; one witness alone would have "verified" a wrong number.

Why a 120 mm plate
------------------
So the probe runs in seconds.  The physics is the one ``verify_panel.py`` checks
on the 600 mm production panel, minus the mesh cost.

Usage::

    python diagnostics/probe_d8_outer_fibre.py           # solve if needed
    python diagnostics/probe_d8_outer_fibre.py --reuse   # read what is on disk
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feagpt import panel, pipeline, post  # noqa: E402

A = B = 120.0
T = 2.0
Q = 1e-4
E = 73100.0
NU = 0.33
OUT = Path("outputs/_probe_d8")


def navier(a: float, q: float, t: float, nu: float, nmax: int = 1201):
    """``w_max`` and the central ``sigma = 6 Mx/t^2``, from one series pair.

    Both sums are taken at the centre, so both carry ``s_m s_n`` - the shape
    function's own sign at ``x = y = a/2``.  Applying it once is the whole
    content of this function.
    """
    s_w = s_m = 0.0
    for m in range(1, nmax + 1, 2):
        sm = 1.0 if ((m - 1) // 2) % 2 == 0 else -1.0
        for n in range(1, nmax + 1, 2):
            sn = 1.0 if ((n - 1) // 2) % 2 == 0 else -1.0
            den = m * n * ((m / a) ** 2 + (n / a) ** 2) ** 2
            s_w += sm * sn / den
            s_m += sm * sn * (m * m + nu * n * n) / (m * n * (m * m + n * n) ** 2)
    D = E * t**3 / (12.0 * (1.0 - nu**2))
    w = 16.0 * q / (math.pi**6 * D) * s_w
    Mx = 16.0 * q * a * a / math.pi**4 * s_m
    return {"D": D, "w_max": w, "coeff_w": w / (q * a**4 / D),
            "Mx": Mx, "sigma": 6.0 * Mx / t**2}


def fe_moment_from_displacement(mid: dict, radius: float = 12.0) -> dict:
    """Second witness: fit ``w`` quadratically at the centre, not the stress."""
    nodes, disp = mid["nodes"], mid["results"]["DISP"]
    pts = [(c[0], c[1], disp[n][2]) for n, c in nodes.items()
           if (c[0] - A / 2) ** 2 + (c[1] - B / 2) ** 2 < radius * radius]
    design = np.array([[1, x, y, 0.5 * x * x, x * y, 0.5 * y * y]
                       for x, y, _ in pts])
    coef, *_ = np.linalg.lstsq(design, np.array([w for _, _, w in pts]),
                               rcond=None)
    D = E * T**3 / (12.0 * (1.0 - NU**2))
    # Magnitudes: a downward load gives w < 0 and w,xx > 0, so the signed
    # product flips twice.  The quantity under test is how big the stress is,
    # not which way it points, and every comparison below is against a
    # magnitude.
    Mx = abs(-D * (coef[3] + NU * coef[5]))
    return {"n_pts": len(pts), "w_xx": coef[3], "w_yy": coef[5],
            "Mx": Mx, "sigma": 6.0 * Mx / T**2}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reuse", action="store_true",
                    help="read the cases already under outputs/_probe_d8")
    args = ap.parse_args(argv)

    ref = navier(A, Q, T, NU)
    print("=" * 78)
    print("  D8 PROBE - the outer fibre against the Navier closed form")
    print("=" * 78)
    print(f"  plate {A:g} x {B:g} x {T:g} mm, q = {Q:g} MPa, "
          f"E = {E:g} MPa, nu = {NU}")
    print(f"  closed form: w_max {ref['w_max']:.8f} mm | "
          f"Mx {ref['Mx']:.6f} N.mm/mm | sigma = 6Mx/t^2 = {ref['sigma']:.5f} MPa")
    print("-" * 78)

    verdict_y = True
    for size in (6.0, 3.0):
        name = f"probe_d8_stress_{size:g}"
        case_dir = OUT / name
        if not args.reuse:
            spec = panel.make_spec(name, n_stringers=0, size=size,
                                   length=A, width=B, thickness=T, pressure=Q)
            res = pipeline.run(spec, outdir=case_dir, solver_name="ccx")
            if not res.ok:
                print(f"  [{size:g} mm] SOLVER FAILED {res.messages[-3:]}")
                return 2

        frd = case_dir / f"{name}.frd"
        raw = post.parse_frd(frd)
        mid = post.load_any(frd)
        meta = (mid.get("meta") or {}).get("collapse") or {}

        # exactly the node nearest the plate centre, on the outer layer
        top = [(n, c) for n, c in raw["nodes"].items() if c[2] > T / 2 - 1e-6]
        nid, coord = min(top, key=lambda q_: (q_[1][0] - A / 2) ** 2
                                           + (q_[1][1] - B / 2) ** 2)
        vm_node = post.von_mises(raw["results"]["STRESS"][nid])

        # The same node as load_any exposes it: mid-surface label, outer fibre
        # carried in STRESS_PEAK.  This is the path the pipeline actually reads,
        # so a value that only exists in the raw read would be a bug.
        peak = mid["results"].get("STRESS_PEAK") or {}
        mid_nid = min(mid["nodes"], key=lambda n: (mid["nodes"][n][0] - A / 2) ** 2
                                                + (mid["nodes"][n][1] - B / 2) ** 2)
        vm_via_peak = post.von_mises(peak[mid_nid]) if mid_nid in peak else float("nan")
        fit = fe_moment_from_displacement(mid)

        e_node = (vm_node - ref["sigma"]) / ref["sigma"] * 100.0
        e_fit = (fit["sigma"] - ref["sigma"]) / ref["sigma"] * 100.0
        err_node = (vm_via_peak - ref["sigma"]) / ref["sigma"] * 100.0
        print(f"  [{size:g} mm] {meta.get('expanded_nodes', '?')} expanded nodes "
              f"-> {meta.get('mid_nodes_out', '?')} mid-surface "
              f"(orphans {meta.get('orphan_expanded_nodes', '?')})")
        print(f"        witness 1 (closed form)     : {ref['sigma']:.5f} MPa")
        print(f"        witness 2 (FE displacement) : {fit['sigma']:.5f} MPa "
              f"from {fit['n_pts']} nodes, w,xx {fit['w_xx']:+.4e} "
              f"-> {e_fit:+.2f} %")
        print(f"        raw FRD node {nid} {tuple(round(c, 2) for c in coord)}: "
              f"vM {vm_node:.5f} -> {e_node:+.2f} %")
        print(f"        STRESS_PEAK at mid node {mid_nid}: {vm_via_peak:.5f} "
              f"-> {err_node:+.2f} %  (the path the pipeline reads)")
        if abs(e_node) > 2.0 or abs(err_node) > 2.0:
            verdict_y = False
        print("-" * 78)

    print(f"  VERDICT: {'PASS - the outer fibre is the bending stress' if verdict_y else 'FAIL'}")
    print("=" * 78)
    return 0 if verdict_y else 1


if __name__ == "__main__":
    raise SystemExit(main())
