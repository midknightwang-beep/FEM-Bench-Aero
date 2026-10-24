#!/usr/bin/env python
"""Where exactly does the D1600 case's 1.13 % gate-3 gap live?

Same mesh, same node, same loads - yet the D20 structure peak disagrees by
1.13 % while its deflection profile agrees to 0.14 %.  That asymmetry says the
gap is local.  This prints the peak node's coordinates, how its error compares
with the whole field, and how the error distributes along the axis - so the
question "is the 1 % gate tripping on the load-application boundary rather than
on the structure?" is answered by a number, not a guess.
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPRO = HERE.parent
sys.path.insert(0, str(REPRO))

from feagpt import post, fuselage                       # noqa: E402
from feagpt.spec import FEASpec                         # noqa: E402
from verify_barrel import _disp, _numag, structure_peak  # noqa: E402

NAME = "fuselage_barrel_d1600_l2000_str8_frm3"
SPECS = REPRO / "_m5_probe" / "_batch6_specs"


def main() -> int:
    spec = FEASpec.from_json(SPECS / f"{NAME}.spec.json")
    p = fuselage.parse_params(spec)
    ccx = post.load_any(REPRO / "outputs_b6" / NAME / f"{NAME}.frd")
    abq = post.load_results_json(REPRO / "outputs_b6_abaqus" / NAME / f"{NAME}.odb.json")

    z_end = p.frame_z()[-1]
    held = set(fuselage.barrel_nodes(ccx["nodes"], p, z_end))
    dcx, dab = _disp(ccx), _disp(abq)
    print(f"{NAME}")
    print(f"  L = {p.length:g}  R = {p.radius:g}  t = {p.thickness:g}  "
          f"last frame plane z = {z_end:g}")
    print(f"  nodes ccx {len(ccx['nodes'])} / abq {len(abq['nodes'])};  "
          f"end-load ring excludes {len(held)} node(s)")

    s_c, n_c = structure_peak(ccx, spec)
    s_a, n_a = structure_peak(abq, spec)
    xyz = ccx["nodes"][n_c]
    print(f"  peak node {n_c} at z = {xyz[2]:.3f} mm  "
          f"(distance to load ring plane = {z_end - xyz[2]:.3f} mm)")
    print(f"  ccx {s_c:.5f}  abq {s_a:.5f} mm  -> {abs(s_c-s_a)/s_a*100:.4f} %")
    print()

    # ---- error along the axis, over nodes with a non-trivial displacement ---
    common = [t for t in dcx if t in dab and t not in held]
    buckets = collections.defaultdict(lambda: [0, 0, 0.0])   # n, n>1%, worst
    worst = (0.0, None)
    for t in common:
        mc, ma = _numag(dcx[t]), _numag(dab[t])
        if ma < 1e-6:
            continue
        e = abs(mc - ma) / ma * 100.0
        z = ccx["nodes"][t][2]
        k = int(z // 200) * 200                     # 200 mm axial bins
        b = buckets[k]
        b[0] += 1
        if e > 1.0:
            b[1] += 1
        b[2] = max(b[2], e)
        if e > worst[0]:
            worst = (e, t)

    print(f"  {'z bin (mm)':>14s} {'nodes':>7s} {'>1 %':>6s} {'worst %':>9s}")
    for k in sorted(buckets):
        n, over, w = buckets[k]
        print(f"  {k:>6d}-{k+200:<6d} {n:7d} {over:6d} {w:9.4f}")
    e, t = worst
    print(f"  worst single node overall: {t} at z = {ccx['nodes'][t][2]:.2f} mm "
          f"-> {e:.4f} %")

    # ---- how much of the 1 % breach is inside the last 200 mm? -------------- #
    near = [t for t in common if ccx["nodes"][t][2] > z_end - 200]
    print(f"\n  nodes within 200 mm of the load ring: {len(near)} of {len(common)}")
    print(f"  the peak node {n_c} is {'INSIDE' if n_c in near else 'outside'} "
          f"that band")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
