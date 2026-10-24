#!/usr/bin/env python
"""T4 pilot - build the default open-hole coupon, solve it, measure Kt.

Answers one question before any of the family machinery is trusted: can a shell
mesh carrying 15 deg of hole-arc resolution reproduce a stress-concentration
factor that is **known independently**?  If it cannot, the family's whole
premise (a hole edge puts the mesher on trial) is untestable and the design
changes.

Reads the field back the way the shipped chain does - ``post.load_any`` on the
FRD, which folds the OUTPUT=3D expanded shell back to the mid-surface - and
reduces it over the **hole-edge nodes only**, selected geometrically from the
result's own node table.  A global maximum would be free to pick up the end
constraint, which is not the number this family exists to measure.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

REPRO = Path(__file__).resolve().parents[1] / "feagpt_repro"
sys.path.insert(0, str(REPRO))

from feagpt import open_hole, pipeline, post   # noqa: E402

OUT = Path(__file__).resolve().parent / "out"


def main() -> int:
    spec = open_hole.make_spec("t4_pilot_d200_l400")
    p = open_hole.parse_params(spec)
    print(f"spec      : {spec.name}")
    print(f"params    : {p.to_dict()}")
    print(f"load      : {spec.load.kind} {spec.load.magnitude:g} N "
          f"along {spec.load.direction}")

    r = pipeline.run(spec, outdir=OUT / spec.name, solver_name="ccx")
    print(f"\nsolved ok : {r.ok}")
    for m in r.messages:
        print("   ", m)
    if not r.ok:
        print("FAILED - stopping")
        return 1

    mesh = r.mesh
    print(f"\nmesh      : {mesh.get('n_nodes')} nodes, "
          f"{mesh.get('n_elements')} shells, {mesh.get('element_types')}, "
          f"minJ {mesh.get('min_quality')}, tri {mesh.get('tri_count')}")

    frd = OUT / spec.name / f"{spec.name}.frd"
    data = post.load_any(frd)
    nodes = data["nodes"]
    stress = data["results"].get("STRESS") or {}
    peak = data["results"].get("STRESS_PEAK") or {}
    print(f"result    : {len(nodes)} nodes, fields {sorted(data['results'])}")

    cx, cy = p.center()
    r_hole = 0.5 * p.hole_d
    edge = [t for t, (x, y, _z) in nodes.items()
            if abs(math.hypot(x - cx, y - cy) - r_hole) < 1e-3]
    print(f"hole edge : {len(edge)} nodes selected geometrically")

    vm = post.von_mises
    if stress:
        s_edge = {t: vm(stress[t]) for t in edge}
        t_hot = max(s_edge, key=s_edge.get)
        s_max = s_edge[t_hot]
        s_glob = max(vm(v) for v in stress.values())
        print(f"\n  mid-surface von Mises")
        print(f"    hole-edge max : {s_max:.4f} MPa at node {t_hot} "
              f"(th={math.degrees(math.atan2(nodes[t_hot][1]-cy, nodes[t_hot][0]-cx)):.1f} deg)")
        print(f"    global  max   : {s_glob:.4f} MPa  "
              f"({'hole edge governs' if abs(s_glob - s_max) < 1e-9 else 'ELSEWHERE -> check'})")
    if peak:
        p_edge = {t: vm(peak[t]) for t in edge}
        t_hot_p = max(p_edge, key=p_edge.get)
        print(f"    outer-fibre hole-edge max : {p_edge[t_hot_p]:.4f} MPa")

    sig_gross = open_hole.gross_stress(spec.load.magnitude, p)
    sig_net = open_hole.net_stress(spec.load.magnitude, p)
    lam = p.lambda_ratio
    print(f"\n  nominal stress")
    print(f"    gross {sig_gross:.4f} MPa   net {sig_net:.4f} MPa   lambda {lam:.4f}")
    print(f"\n  stress-concentration factor")
    if stress:
        print(f"    Kt_gross measured     : {s_max / sig_gross:.4f}")
        print(f"    Kt_net   measured     : {s_max / sig_net:.4f}")
        print(f"    Howland Kt_net (fit)  : {open_hole.howland_kt_net(lam):.4f}")
        print(f"    Howland Kt_gross      : {open_hole.howland_kt_gross(lam):.4f}")
        print(f"    Kirsch infinite-plate : {open_hole.kirsch_kt():.4f}")
        kt_g = s_max / sig_gross
        err = (kt_g / open_hole.howland_kt_gross(lam) - 1.0) * 100.0
        print(f"    error vs Howland gross: {err:+.2f} %")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
