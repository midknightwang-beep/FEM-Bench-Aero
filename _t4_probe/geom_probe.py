"""T4 probe 0 -- can gmsh/OCC cut a clean central hole and mesh it?

No feagpt imports: this answers one question only, and answers it before any
family code is written.  If the hole cut leaves a dirty boundary or the hole
edge cannot be resolved, that changes the whole T4 design, so it is worth the
30 lines.

What it reports
  * the face count after the cut (a plate with a hole must still be ONE face);
  * the curve count (the rectangle's 4 edges + the hole's 1 circle);
  * mesh size actually achieved on the hole edge vs the far field;
  * element types (tri/quad split) and the scaled Jacobian floor.
"""

from __future__ import annotations

import numpy as np
import gmsh

L, W, T = 400.0, 200.0, 2.0        # plate, mm
D = 20.0                           # hole diameter
FAR = 5.0                          # far-field target size
HOLE = D / 8.0                     # hole-edge target size (8 elements per radius)


def quality(nodes, elems):
    """Scaled Jacobian of quad4 shells, the same measure the gates use."""
    q = []
    for e in elems:
        p = np.array([nodes[n - 1] for n in e])
        if len(p) == 3:
            continue
        a = p[1] - p[0]
        b = p[3] - p[0]
        c = p[2] - p[1]
        d = p[0] - p[3]
        # cross products at the four corners
        js = [np.cross(a, -d), np.cross(b, a), np.cross(c, b), np.cross(d, c)]
        js = [abs(j[2]) for j in js]
        maj = [np.linalg.norm(v) for v in (a, b, c, d)]
        q.append(min(js) / max(1e-12, max(maj) ** 2))
    return q


gmsh.initialize()
gmsh.option.setNumber("General.Terminal", 0)
gmsh.model.add("t4_probe")
occ = gmsh.model.occ

rect = occ.addRectangle(0.0, 0.0, 0.0, L, W)
disc = occ.addDisk(0.5 * L, 0.5 * W, 0.0, 0.5 * D, 0.5 * D)
out, outmap = occ.cut([(2, rect)], [(2, disc)])
occ.synchronize()

faces = gmsh.model.getEntities(2)
curves = gmsh.model.getEntities(1)
print(f"after cut: {len(faces)} face(s) {[t for _, t in faces]}, "
      f"{len(curves)} curve(s) {[t for _, t in curves]}")
print("outmap entries:", len(outmap))

# hole curve = the closed curve whose bounding box is *inside* the plate
hole_curves = []
for _d, t in curves:
    bb = gmsh.model.getBoundingBox(1, t)
    if bb[0] > 1e-6 and bb[1] > 1e-6 and bb[3] < L - 1e-6 and bb[4] < W - 1e-6:
        hole_curves.append(t)
print("hole curve(s):", hole_curves)

# ---- mesh: far field FAR, hole edge HOLE ------------------------------- #
# Options mirror feagpt.meshing.build_mesh so the probe answers the question
# the real chain will ask, not a different one.
gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 24.0)
gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 1.0)
gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 1.0)
gmsh.option.setNumber("Mesh.MeshSizeMin", max(HOLE / 6.0, 0.5))
gmsh.option.setNumber("Mesh.MeshSizeMax", FAR)
gmsh.option.setNumber("Mesh.Algorithm", 6)          # Frontal-Delaunay
gmsh.option.setNumber("Mesh.RecombineAll", 1)
gmsh.option.setNumber("Mesh.RecombinationAlgorithm", 3)   # blossom full-quad
if hole_curves:
    gmsh.model.mesh.setSize([(1, t) for t in hole_curves], HOLE)
gmsh.model.mesh.generate(2)

ntypes, ntags, nnodes = gmsh.model.mesh.getElements(2)
counts = {}
allq = []
for t, tags, conn in zip(ntypes, ntags, nnodes):
    name = gmsh.model.mesh.getElementProperties(t)[0]
    counts[name] = counts.get(name, 0) + len(tags)
# node table
ntags_all, ncoords, _ = gmsh.model.mesh.getNodes()
ntags_all = np.asarray(ntags_all, dtype=int)
ncoords = np.asarray(ncoords, dtype=float).reshape(-1, 3)
idx = {t: i for i, t in enumerate(ntags_all)}

# rebuild quad connectivity for the quality measure
qs = []
for t, tags, conn in zip(*(gmsh.model.mesh.getElements(2))):
    name = gmsh.model.mesh.getElementProperties(t)[0]
    npe = gmsh.model.mesh.getElementProperties(t)[3]
    if name != "Quadrangle":
        continue
    conn = np.asarray(conn, dtype=int)
    for i in range(len(tags)):
        qs.append([idx[n] for n in conn[i * npe:(i + 1) * npe]])

# mesh size on the hole edge: sample element edge lengths near the hole
from collections import Counter
print(f"elements: {counts}")
print(f"nodes: {len(ntags_all)}")

# distance of each node to hole centre
r = np.hypot(ncoords[:, 0] - 0.5 * L, ncoords[:, 1] - 0.5 * W)
near = (r > 0.5 * D - 1e-6) & (r < 0.5 * D + 3.0)
print(f"nodes within 3 mm of the hole edge: {int(near.sum())}, "
      f"min r = {r.min():.4f} (hole radius {0.5*D:.1f})")

q = quality([tuple(v) for v in ncoords], qs)
q = np.asarray(q)
if q.size:
    print(f"quad count {len(qs)}, scaled-J min {q.min():.4f} "
          f"(p1 {np.percentile(q,1):.4f}, median {np.median(q):.4f})")
else:
    print(f"quad count 0 -- recombination produced no quad4")

# radial spacing of hole-boundary nodes -> angular resolution
th = np.arctan2(ncoords[:, 1] - 0.5 * W, ncoords[:, 0] - 0.5 * L)
edge = np.abs(r - 0.5 * D) < 1e-3
th_edge = np.sort(np.mod(th[edge], 2 * np.pi))
print(f"nodes exactly on the hole edge: {int(edge.sum())}")
if edge.sum() > 3:
    dth = np.diff(np.r_[th_edge, th_edge[0] + 2 * np.pi])
    print(f"hole-edge angular step: min {np.degrees(dth.min()):.2f} deg, "
          f"max {np.degrees(dth.max()):.2f} deg, mean {np.degrees(dth.mean()):.2f} deg")

gmsh.finalize()
