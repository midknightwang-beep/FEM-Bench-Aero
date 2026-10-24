"""Probe: how to build a T-section stringer so web and flange share an edge.

Why this needs probing
----------------------
A **blade** stringer is a single plane (``x = const`` extruded along the span),
so M1/M2 never had to ask this question.  A **T** section is a web (plane
``x = const``) plus a flange (plane ``y = const``) meeting at 90 degrees along a
single line.  If those two faces do not share that edge, then after meshing the
flange has no shared nodes with the web - it is a *structurally detached*
cantilever strip.  The linear static solve still returns "displacements", so no
numerical gate would notice; the model is simply wrong.

Candidates
----------
``nofrag``   two separate extrudes, no boolean.
``frag``     two separate extrudes, then ``occ.fragment`` so the flange is cut
             by the web and the pieces inherit a shared edge.

Verdict
-------
Two independent readings, because they can disagree:

* OCC topology - the boundary curves of each resulting face
  (``occ.getBoundary``).  A shared curve tag means a shared edge.
* mesh - the node tags each face owns after ``mesh.generate(2)``.  A non-empty
  intersection means the faces are actually connected once discretised.

Run::

    python diagnostics/t_stringer_probe.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gmsh  # noqa: E402

SPAN = 400.0
H = 20.0        # web depth
W = 30.0        # flange width
X0 = 0.0        # web plane
Y_TOP = 0.0     # bonded edge (would sit on the skin)


def _face_nodes(tag: int) -> set[int]:
    ntags, _, _ = gmsh.model.mesh.getNodes(2, tag, True, False)
    return {int(t) for t in ntags}


def _face_bbox(tag: int) -> tuple:
    return tuple(round(float(v), 4) for v in gmsh.model.getBoundingBox(2, tag))


def _face_boundary_curves(tag: int) -> set[int]:
    try:
        bnd = gmsh.model.getBoundary([(2, tag)], combined=False, oriented=False, recursive=False)
    except Exception:
        return set()
    return {int(t) for d, t in bnd if d == 1}


def build(method: str) -> dict:
    occ = gmsh.model.occ
    y_bot = Y_TOP - H

    # web: plane x = X0, from the bonded edge down to the free edge
    pw0 = occ.addPoint(X0, Y_TOP, 0.0)
    pw1 = occ.addPoint(X0, y_bot, 0.0)
    lw = occ.addLine(pw0, pw1)
    # flange: plane y = y_bot, straddling the web
    pf0 = occ.addPoint(X0 - W / 2.0, y_bot, 0.0)
    pf1 = occ.addPoint(X0 + W / 2.0, y_bot, 0.0)
    lf = occ.addLine(pf0, pf1)

    out = occ.extrude([(1, lw), (1, lf)], 0.0, 0.0, SPAN, recombine=False)
    faces = [t for d, t in out if d == 2]
    occ.synchronize()

    info: dict = {
        "method": method,
        "faces_before": [{"tag": t, "bbox": _face_bbox(t), "n_curves": len(_face_boundary_curves(t))}
                         for t in faces],
    }

    if method == "frag":
        out2, out_map = occ.fragment([(2, faces[0])], [(2, faces[1])])
        occ.synchronize()
        faces = [t for d, t in out2 if d == 2]
        info["out_map_len"] = len(out_map)
        info["out_map"] = [[list(x) for x in ent] for ent in out_map]

    info["faces_after"] = [{"tag": t, "bbox": _face_bbox(t), "n_curves": len(_face_boundary_curves(t))}
                           for t in faces]
    info["n_faces"] = len(faces)

    # shared edge at the OCC level
    bnds = [_face_boundary_curves(t) for t in faces]
    info["occ_boundary_curve_counts"] = [len(b) for b in bnds]
    info["occ_shared_boundary_pairs"] = [[len(bnds[i] & bnds[j]) for j in range(len(faces))]
                                         for i in range(len(faces))]

    # mesh and compare node sets
    gmsh.option.setNumber("Mesh.MeshSizeMax", 40.0)
    gmsh.option.setNumber("Mesh.MeshSizeMin", 8.0)
    gmsh.model.mesh.generate(2)
    nsets = [_face_nodes(t) for t in faces]
    info["nodes_per_face"] = [len(s) for s in nsets]
    info["shared_nodes"] = [[len(nsets[i] & nsets[j]) for j in range(len(nsets))]
                            for i in range(len(nsets))]
    return info


def main() -> int:
    results = []
    for method in ("nofrag", "frag"):
        gmsh.initialize()
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add(f"probe_{method}")
        try:
            results.append(build(method))
        finally:
            gmsh.finalize()

    for r in results:
        print("=" * 74)
        print(f"METHOD: {r['method']}   ->  {r['n_faces']} face(s)")
        print("-" * 74)
        for f in r["faces_before"]:
            print(f"  before  tag {f['tag']:>3}  bbox={f['bbox']}  boundary curves={f['n_curves']}")
        for f in r["faces_after"]:
            print(f"  after   tag {f['tag']:>3}  bbox={f['bbox']}  boundary curves={f['n_curves']}")
        print(f"  OCC boundary curves per face: {r['occ_boundary_curve_counts']}")
        print(f"  OCC shared-boundary pairs   : {r['occ_shared_boundary_pairs']}")
        print(f"  nodes per face             : {r['nodes_per_face']}")
        print(f"  shared node matrix         : {r['shared_nodes']}")
        n = len(r["shared_nodes"])
        connected = any(r["shared_nodes"][i][j] > 0 for i in range(n) for j in range(n) if i != j)
        occ_conn = any(r["occ_shared_boundary_pairs"][i][j] > 0 for i in range(n) for j in range(n) if i != j)
        print(f"  VERDICT: {'CONNECTED - web and flange share nodes' if connected else 'DETACHED - no shared nodes'}"
              f"   (occ shared boundary: {occ_conn})")
    print("=" * 74)

    out = Path(__file__).resolve().parent / "t_stringer_probe.json"
    out.write_text(json.dumps(results, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o)),
                   encoding="utf-8")
    print(f"raw -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
