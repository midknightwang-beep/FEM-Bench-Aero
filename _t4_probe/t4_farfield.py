"""Is the far field really at the nominal stress?

The Kt reduction divides the hole-edge peak by ``sigma_gross = F / (W t)``,
which assumes the stress midway between the hole and the clamped end has
relaxed to the uniform value.  That is a Saint-Venant assumption with a decay
length of order the plate width, and on a 400 mm coupon the hole sits only
200 mm from a fully clamped end - so it is worth measuring rather than
assuming.

Reports, on an existing run:
  * the far-field von Mises (mean / median) away from the hole and the ends;
  * the hole-edge profile as a function of angle, so the peak location and the
    shape of the concentration are visible.
"""

from __future__ import annotations

import math
import statistics
import sys
from pathlib import Path

REPRO = Path(__file__).resolve().parents[1] / "feagpt_repro"
sys.path.insert(0, str(REPRO))

from feagpt import open_hole, post   # noqa: E402

OUT = Path(__file__).resolve().parent / "out"


def analyse(name: str) -> None:
    case = OUT / name
    data = post.load_any(case / f"{name}.frd")
    nodes = data["nodes"]
    stress = data["results"]["STRESS"]
    vm = post.von_mises

    p = open_hole.OpenHoleParams()
    cx, cy = p.center()
    rh = 0.5 * p.hole_d
    L, W = p.length, p.width

    # far field: mid-plate band, away from the hole and from both ends
    far = []
    for t, (x, y, _z) in nodes.items():
        r = math.hypot(x - cx, y - cy)
        if r > 4 * rh and abs(x - cx) < 0.25 * L:
            far.append(vm(stress[t]))
    print(f"\n{name}")
    print(f"  far-field nodes (r > 4*{rh:g} mm, |x-cx| < {0.25*L:g} mm): "
          f"{len(far)}")
    print(f"    mean   {statistics.fmean(far):.4f} MPa")
    print(f"    median {statistics.median(far):.4f} MPa")
    print(f"    stdev  {statistics.pstdev(far):.4f} MPa "
          f"({statistics.pstdev(far)/statistics.fmean(far)*100:.2f} %)")
    print(f"  nominal gross 10.0000 MPa -> far/median ratio "
          f"{statistics.median(far)/10.0:.4f}")

    # hole edge profile
    edge = []
    for t, (x, y, _z) in nodes.items():
        r = math.hypot(x - cx, y - cy)
        if abs(r - rh) < 1e-3:
            th = math.degrees(math.atan2(y - cy, x - cx)) % 360.0
            edge.append((th, vm(stress[t])))
    edge.sort()
    print(f"  hole edge: {len(edge)} nodes, "
          f"min {min(v for _t, v in edge):.3f}, "
          f"max {max(v for _t, v in edge):.3f} MPa")
    hot = [e for e in edge if 60 <= e[0] <= 120]
    print("    profile near the load-normal diameter (theta, vM):")
    for th, v in hot:
        print(f"      {th:6.1f} deg  {v:8.4f} MPa")


for nm in ("t4_conv_div72", "t4_conv_div96", "t4_conv_div24"):
    try:
        analyse(nm)
    except FileNotFoundError:
        print(f"\n{nm}: no output on disk")
