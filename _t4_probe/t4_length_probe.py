"""Does the clamped end contaminate the nominal stress at the hole?

The coupon is clamped at x = 0 and pulled at x = length; Saint-Venant says the
disturbance decays over a length of order the plate width, so on a 400 mm
coupon the hole sits only 200 mm from a fully clamped end.  The far field was
measured at 10.1 MPa instead of the nominal 10.0 - about +1 %, exactly the size
of the tolerance this family wants to judge against - so it matters whether
that is the hole's own bypass or the clamp.

Runs the same coupon at three lengths and looks at both the far-field level and
the resulting Kt.  If it is the clamp, the far field relaxes to 10.0 and Kt
settles as the coupon lengthens.
"""

from __future__ import annotations

import math
import statistics
import sys
from pathlib import Path

REPRO = Path(__file__).resolve().parents[1] / "feagpt_repro"
sys.path.insert(0, str(REPRO))

from feagpt import open_hole, pipeline, post   # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
open_hole.HOLE_ARC_DIVISIONS = 72


def run(length: float) -> dict | None:
    name = f"t4_len{int(length)}"
    spec = open_hole.make_spec(name, size=5.0, length=length)
    p = open_hole.parse_params(spec)
    r = pipeline.run(spec, outdir=OUT / name, solver_name="ccx")
    if not r.ok:
        print(f"  L={length}: FAILED")
        return None
    data = post.load_any(OUT / name / f"{name}.frd")
    nodes = data["nodes"]
    stress = data["results"]["STRESS"]
    vm = post.von_mises
    cx, cy = p.center()
    rh = 0.5 * p.hole_d

    far = [vm(stress[t]) for t, (x, y, _z) in nodes.items()
           if math.hypot(x - cx, y - cy) > 4 * rh
           and abs(x - cx) < 0.25 * p.length]
    edge = [vm(stress[t]) for t, (x, y, _z) in nodes.items()
            if abs(math.hypot(x - cx, y - cy) - rh) < 1e-3]
    s_max = max(edge)
    sig = open_hole.gross_stress(spec.load.magnitude, p)
    med = statistics.median(far)
    return {
        "L": length, "n_elem": r.mesh["n_elements"], "n_edge": len(edge),
        "far_median": med, "far_over_nominal": med / sig,
        "sigma_max": s_max, "Kt_gross": s_max / sig,
        "Kt_gross_corrected": s_max / med,   # peak over the *measured* far field
        "Howland": open_hole.howland_kt_gross(p.lambda_ratio),
    }


rows = []
for L in (400.0, 600.0, 800.0):
    row = run(L)
    if row:
        rows.append(row)
        print(f"  L={L:5.0f}: {row['n_elem']:6d} elems, {row['n_edge']:3d} edge nodes, "
              f"far {row['far_median']:.4f} MPa (x{row['far_over_nominal']:.4f}), "
              f"sigma_max {row['sigma_max']:.4f}, "
              f"Kt_gross {row['Kt_gross']:.4f} "
              f"(vs measured far field {row['Kt_gross_corrected']:.4f})")

print("\n  Howland Kt_gross (analytic, gross convention): "
      f"{open_hole.howland_kt_gross(0.1):.4f}")
print("  nominal sigma_gross = 10 MPa by construction")
