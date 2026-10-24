"""Why did the hole-edge setSize change nothing?

The convergence sweep returned five identical meshes for five different
HOLE_ARC_DIVISIONS values, which is the one outcome that is never a real
result.  This probe prints exactly what the builder sees, with no solver in
the loop.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPRO = Path(__file__).resolve().parents[1] / "feagpt_repro"
sys.path.insert(0, str(REPRO))

import gmsh                                # noqa: E402
from feagpt import geometry, open_hole     # noqa: E402
from feagpt.spec import FEASpec            # noqa: E402

open_hole.HOLE_ARC_DIVISIONS = 48
spec = open_hole.make_spec("t4_size_probe")
p = open_hole.parse_params(spec)
print("params      :", p.to_dict())
print("target arc  :", open_hole.hole_edge_size(p), "mm")

gmsh.initialize()
gmsh.option.setNumber("General.Terminal", 0)
gmsh.model.add("probe")
geo = geometry.build(gmsh, spec)
print("\ngeo.notes:")
for n in geo.notes:
    print("   ", n)

print("\nentities:")
box = gmsh.model.getBoundingBox(-1, -1)
print("  overall bbox", [round(v, 3) for v in box])
for dim, t in gmsh.model.getEntities(1):
    bb = gmsh.model.getBoundingBox(1, t)
    inside = (bb[0] > box[0] + 1e-6 and bb[1] > box[1] + 1e-6
              and bb[3] < box[3] - 1e-6 and bb[4] < box[4] - 1e-6)
    print(f"  curve {t}: bbox {[round(v,3) for v in bb]}  enclosed={inside}")

# read back the size gmsh actually holds for that curve
sizes = gmsh.model.mesh.getSizes([(1, t) for _d, t in gmsh.model.getEntities(1)])
print("\nper-curve sizes gmsh holds:")
for (_d, t), s in zip(gmsh.model.getEntities(1), sizes):
    print(f"  curve {t}: size {s}")

gmsh.finalize()
