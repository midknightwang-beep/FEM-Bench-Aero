#!/usr/bin/env python
"""Is the D1600 gate-3 breach a real disagreement, or a small-over-small ratio?

The sweep shows the D1600 case stays above 1 % even after a 150 mm end band is
removed, and its 1000-1800 mm stretch is worse than the baseline's at the same
stations.  ``_rel`` is a *relative* measure, so a node whose displacement is
0.05 mm can post a large percentage from a 0.0005 mm absolute gap and carry no
structural meaning.  This prints the worst offenders with both the absolute
difference and the deflection they are quoted against, for D1600 and for the
already-shipped baseline, and the same two cases on an absolute scale.

Reads what is on disk; runs no solver.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPRO = HERE.parent
sys.path.insert(0, str(REPRO))

from feagpt import post, fuselage                        # noqa: E402
from feagpt.spec import FEASpec                          # noqa: E402
from verify_barrel import _disp, _numag                  # noqa: E402

SPECS = REPRO / "_m5_probe" / "_batch6_specs"
SETS = (
    ("b6 D1600", "outputs_b6", "outputs_b6_abaqus",
     SPECS / "fuselage_barrel_d1600_l2000_str8_frm3.spec.json"),
    ("b3 str8_frm3 (shipped)", "outputs_b3", "outputs_b3_abaqus",
     REPRO / "outputs_b3/fuselage_barrel_d2000_l2000_str8_frm3/"
             "fuselage_barrel_d2000_l2000_str8_frm3.spec.json"),
)


def worst_nodes(dcx, dab, nodes, L, band, n=12):
    rows = []
    for t in dcx:
        if t not in dab:
            continue
        z = nodes[t][2]
        if z < band or z > L - band:
            continue
        mc, ma = _numag(dcx[t]), _numag(dab[t])
        if ma < 1e-12:
            continue
        rows.append((abs(mc - ma) / ma * 100.0, abs(mc - ma), mc, ma, z, t))
    rows.sort(reverse=True)
    return rows[:n]


def main() -> int:
    for label, cdir, adir, specp in SETS:
        spec = FEASpec.from_json(specp)
        name = specp.name.replace(".spec.json", "")
        p = fuselage.parse_params(spec)
        ccx = post.load_any(REPRO / cdir / name / f"{name}.frd")
        abq = post.load_results_json(REPRO / adir / name / f"{name}.odb.json")
        dcx, dab = _disp(ccx), _disp(abq)

        print("=" * 100)
        print(f"{label}   R = {p.radius:g}  L = {p.length:g}  "
              f"nodes = {len(ccx['nodes'])}")
        for band in (0.0, 25.0):
            rows = worst_nodes(dcx, dab, ccx["nodes"], p.length, band)
            print(f"\n  worst nodes with the end band {band:g} mm removed "
                  f"(relative error, absolute gap, and what it is relative to):")
            print(f"    {'rel %':>8s} {'abs mm':>10s} {'|u| ccx':>9s} "
                  f"{'|u| abq':>9s} {'z mm':>9s}  node")
            for e, d, mc, ma, z, t in rows:
                print(f"    {e:8.4f} {d:10.6f} {mc:9.5f} {ma:9.5f} "
                      f"{z:9.2f}  {t}")

        # absolute scale: the largest absolute gap, and where
        allrows = worst_nodes(dcx, dab, ccx["nodes"], p.length, 0.0, n=1_000_000)
        top_abs = max(allrows, key=lambda r: r[1])
        print(f"\n  largest absolute gap anywhere: {top_abs[1]:.6f} mm at "
              f"z = {top_abs[4]:.2f} (|u| ccx {top_abs[2]:.5f} vs abq "
              f"{top_abs[3]:.5f}, {top_abs[0]:.3f} %)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
