"""Minimal lab: does gmsh honour a curve setSize on this geometry, and does
``Mesh.MeshSizeFromCurvature`` overrule it?

Three variants on the same 400x200 plate with a d=20 hole:
  A  setSize(hole, 1.0), curvature OFF
  B  setSize(hole, 1.0), curvature 24 (what the shipped size field sets)
  C  no setSize, curvature 48

Counts the nodes that land exactly on the hole edge, which is the discretisation
the convergence study was trying to change.
"""

from __future__ import annotations

import math

import gmsh


def build(size, curvature):
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("lab")
    occ = gmsh.model.occ
    rect = occ.addRectangle(0.0, 0.0, 0.0, 400.0, 200.0)
    disc = occ.addDisk(200.0, 100.0, 0.0, 10.0, 10.0)
    occ.cut([(2, rect)], [(2, disc)])
    occ.synchronize()

    hole = None
    for _d, t in gmsh.model.getEntities(1):
        bb = gmsh.model.getBoundingBox(1, t)
        if bb[0] > 1e-6 and bb[1] > 1e-6 and bb[3] < 400 - 1e-6 and bb[4] < 200 - 1e-6:
            hole = t
    if size is not None and hole is not None:
        gmsh.model.mesh.setSize([(1, hole)], size)
        print(f"    setSize -> getSizes reads back {gmsh.model.mesh.getSizes([(1, hole)])}")

    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", curvature)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 1.0)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 1.0)
    gmsh.option.setNumber("Mesh.MeshSizeMin", 0.5)
    gmsh.option.setNumber("Mesh.MeshSizeMax", 5.0)
    gmsh.option.setNumber("Mesh.Algorithm", 6)
    gmsh.option.setNumber("Mesh.RecombineAll", 1)
    gmsh.option.setNumber("Mesh.RecombinationAlgorithm", 1)
    gmsh.model.mesh.generate(2)

    ntags, ncoords, _ = gmsh.model.mesh.getNodes()
    nc = 0
    for i, t in enumerate(ntags):
        x, y = ncoords[3 * i], ncoords[3 * i + 1]
        r = math.hypot(x - 200.0, y - 100.0)
        if abs(r - 10.0) < 1e-6:
            nc += 1
    nel = 0
    for _d, t in gmsh.model.getEntities(2):
        for _et, etags, _en in zip(*gmsh.model.mesh.getElements(2, t)):
            nel += len(etags)
    gmsh.finalize()
    return nc, nel


for label, size, curv in (("A setSize=1.0, curvature OFF", 1.0, 0.0),
                          ("B setSize=1.0, curvature 24", 1.0, 24.0),
                          ("C no setSize,   curvature 48", None, 48.0),
                          ("D setSize=2.0, curvature 24", 2.0, 24.0)):
    n_edge, n_elem = build(size, curv)
    print(f"  {label:32s}: hole-edge nodes {n_edge:3d} "
          f"({360.0/max(n_edge,1):5.2f} deg), elements {n_elem}")
