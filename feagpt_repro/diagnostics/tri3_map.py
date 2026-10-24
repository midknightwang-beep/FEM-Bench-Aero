"""Locate the tri3 elements in an archived ``.msh`` and say *where* they sit.

Why this exists
---------------
Gate 1 has always been described as "min Jacobian >= 0.30, zero tri3", but
:mod:`feagpt.meshing` only ever checked the Jacobian.  ``diagnostics/msh_quality.py``
established that two archived wing-box cases (``n_ribs3_chord800``,
``n_ribs5_chord800``) carry 8 and 16 ``S3`` elements.  "There are 8 triangles"
is not enough to act on: a fix has to know whether they sit on one face that
can be re-meshed, or scattered over the whole model.

This tool answers the next question: per 2-D surface, how many tri3, and what
is that surface's bounding box compared with the target element size.  A face
whose short edge is only ~1 element wide is the classic blossom-recombination
failure, and the number that matters is ``short_edge / size``.

Usage::

    python diagnostics/tri3_map.py ../FEM-Bench-Aero/modeling
    python diagnostics/tri3_map.py ../FEM-Bench-Aero/modeling --case naca4412_wingbox_n_ribs5_chord800
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import gmsh


def scan(path: Path) -> list[dict]:
    """Per-surface tri3 census of one ``.msh``.

    ``short`` is the smallest bounding-box edge that is *not* the thickness /
    normal direction, i.e. the in-plane narrow dimension of the face.  On a
    shell model every surface is a plane-ish patch, so the two largest bbox
    extents are the patch's own dimensions and the remaining one is noise.
    """
    gmsh.clear()
    gmsh.open(str(path))
    out: list[dict] = []
    for dim, tag in gmsh.model.getEntities(2):
        et, etags, enodes = gmsh.model.mesh.getElements(2, tag)
        tri = quad = 0
        centroids: list[tuple[float, float, float]] = []
        for t, tg, nd in zip(et, etags, enodes):
            if t == 2:
                tri += len(tg)
                n = len(nd) // 3
                for i in range(n):
                    pts = [gmsh.model.mesh.getNode(int(x))[0] for x in nd[3 * i:3 * i + 3]]
                    centroids.append(tuple(sum(q[k] for q in pts) / 3.0 for k in range(3)))
            elif t == 3:
                quad += len(tg)
        bb = list(gmsh.model.getBoundingBox(2, tag))
        ext = sorted([bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]])
        out.append({
            "tag": tag, "tri": tri, "quad": quad,
            "bbox": bb, "ext": ext, "short": ext[0],
            "centroids": centroids,
        })
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tree", help="dataset tree (or a .msh file with --case omitted)")
    ap.add_argument("--case", help="one <case>/model.msh under the tree")
    ap.add_argument("--size", type=float, default=None,
                    help="target element size, to report short_edge/size")
    args = ap.parse_args(argv)

    root = Path(args.tree)
    if args.case:
        files = [root / args.case / "model.msh"]
    elif root.is_file():
        files = [root]
    else:
        files = [p / "model.msh" for p in sorted(root.iterdir()) if p.is_dir()]

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    total_tri = 0
    for f in files:
        if not f.exists():
            continue
        rows = scan(f)
        ntri = sum(r["tri"] for r in rows)
        total_tri += ntri
        flag = "  <-- tri3" if ntri else ""
        print(f"\n=== {f.parent.name}   tri3={ntri}{flag}")
        if not ntri:
            continue
        for r in rows:
            if not r["tri"]:
                continue
            ratio = ""
            if args.size:
                ratio = f"  short/size={r['short'] / args.size:.3f}  short={r['short']:.2f}"
            print(f"  face {r['tag']:>5d}: tri3={r['tri']:>4d} quad4={r['quad']:>4d} "
                  f"ext={r['ext'][0]:.1f}/{r['ext'][1]:.1f}/{r['ext'][2]:.1f}{ratio}")
            bb = r["bbox"]
            print(f"        bbox x[{bb[0]:.1f},{bb[3]:.1f}] y[{bb[1]:.1f},{bb[4]:.1f}] z[{bb[2]:.1f},{bb[5]:.1f}]")
            for c in r["centroids"][:20]:
                print(f"        centroid ({c[0]:8.2f},{c[1]:8.2f},{c[2]:8.2f})")
    gmsh.finalize()
    print(f"\nTOTAL tri3 over {len(files)} case(s) = {total_tri}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
