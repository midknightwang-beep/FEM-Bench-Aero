#!/usr/bin/env python
"""T4 convergence - how fine must the hole arc be before Kt stops moving?

The whole family rests on one claim: that the mesh resolves the hole-edge
gradient.  A tip deflection would survive a 30 % mesh change; a stress
concentration factor does not, so the claim is not assumed - the arc is refined
and the factor is watched until it settles.

Refines only the **hole edge** (``open_hole.HOLE_ARC_DIVISIONS``); the far field
is held at the family default.  Reuses the shipped chain - the same builder,
mesher, deck writer and post-processor the dataset is generated with - so the
numbers mean what the dataset's numbers mean.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPRO = Path(__file__).resolve().parents[1] / "feagpt_repro"
sys.path.insert(0, str(REPRO))

from feagpt import open_hole, pipeline, post   # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
DIVISIONS = (12, 24, 36, 48, 72, 96)
# The hole edge is set by ``Mesh.MeshSizeFromCurvature``, which is clamped
# between ``MeshSizeMin = size_chord / 6`` and ``MeshSizeMax = size_span``.
# Both are widened here so the sweep measures the arc, not the clamp: at the
# family default (5 / 5) everything coarser than 24 is cut off by the ceiling
# and everything finer than ~75 by the floor.
CHORD = 3.0     # -> MeshSizeMin 0.5 mm
SPAN = 6.0      # -> MeshSizeMax 6.0 mm


def measure(div: int, size: float) -> dict | None:
    open_hole.HOLE_ARC_DIVISIONS = div
    name = f"t4_conv_div{div}"
    spec = open_hole.make_spec(name, size=size)
    spec.mesh.size_span = SPAN
    p = open_hole.parse_params(spec)
    r = pipeline.run(spec, outdir=OUT / name, solver_name="ccx")
    if not r.ok:
        print(f"  div={div}: FAILED")
        return None

    data = post.load_any(OUT / name / f"{name}.frd")
    nodes = data["nodes"]
    stress = data["results"]["STRESS"]
    cx, cy = p.center()
    rh = 0.5 * p.hole_d
    edge = [t for t, (x, y, _z) in nodes.items()
            if abs(math.hypot(x - cx, y - cy) - rh) < 1e-3]
    vm = post.von_mises
    s_max = max(vm(stress[t]) for t in edge)
    sig_gross = open_hole.gross_stress(spec.load.magnitude, p)
    sig_net = open_hole.net_stress(spec.load.magnitude, p)
    return {
        "divisions": div,
        "arc_deg": 360.0 / div,
        "hole_edge_mm": open_hole.hole_edge_size(p, div),
        "far_mm": size,
        "n_nodes": r.mesh["n_nodes"],
        "n_elements": r.mesh["n_elements"],
        "n_tri": r.mesh["tri_count"],
        "min_jacobian": r.mesh["min_quality"],
        "n_edge_nodes": len(edge),
        "sigma_max_MPa": s_max,
        "Kt_gross": s_max / sig_gross,
        "Kt_net": s_max / sig_net,
    }


def main() -> int:
    rows = []
    for div in DIVISIONS:
        row = measure(div, CHORD)
        if row is None:
            continue
        rows.append(row)
        print(f"  div={div:3d} ({row['arc_deg']:.2f} deg, "
              f"{row['hole_edge_mm']:.3f} mm): "
              f"{row['n_elements']:6d} elems, tri {row['n_tri']}, "
              f"minJ {row['min_jacobian']:.4f}, "
              f"edge nodes {row['n_edge_nodes']:3d}, "
              f"sigma_max {row['sigma_max_MPa']:.4f} MPa, "
              f"Kt_gross {row['Kt_gross']:.4f}, Kt_net {row['Kt_net']:.4f}")

    open_hole.HOLE_ARC_DIVISIONS = 24

    if len(rows) < 2:
        print("not enough successful runs to judge convergence")
        return 1

    p = open_hole.OpenHoleParams()
    lam = p.lambda_ratio
    fine = rows[-1]
    print("\n  analytic yardsticks")
    print(f"    Howland Kt_net   {open_hole.howland_kt_net(lam):.4f}")
    print(f"    Howland Kt_gross {open_hole.howland_kt_gross(lam):.4f}")
    print(f"    Kirsch (infinite) {open_hole.kirsch_kt():.4f}")

    print("\n  convergence of Kt_gross (relative to the finest run)")
    for row in rows:
        d = (row["Kt_gross"] / fine["Kt_gross"] - 1.0) * 100.0
        print(f"    div {row['divisions']:3d}: {row['Kt_gross']:.4f}  ({d:+.3f} %)")

    # successive-change criterion: the step from the last two refinements
    step = abs(rows[-1]["Kt_gross"] - rows[-2]["Kt_gross"])
    rel = step / rows[-1]["Kt_gross"] * 100.0
    print(f"\n  last step {step:.5f} ({rel:.3f} %)")
    base = next((r for r in rows if r["divisions"] == 24), rows[0])
    print(f"  default 24 vs finest: "
          f"{(base['Kt_gross'] / fine['Kt_gross'] - 1) * 100:+.3f} %")

    (Path(__file__).resolve().parent / "t4_convergence.json").write_text(
        json.dumps({"rows": rows,
                    "howland_kt_net": open_hole.howland_kt_net(lam),
                    "howland_kt_gross": open_hole.howland_kt_gross(lam),
                    "kirsch": open_hole.kirsch_kt(),
                    "lambda": lam}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
