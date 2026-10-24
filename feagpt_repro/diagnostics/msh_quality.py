"""Min scaled Jacobian, read back from an *archived* ``.msh``.

Why this exists
---------------
Gate 1 ("min Jacobian >= 0.30, zero tri3") is computed by :mod:`feagpt.meshing`
while the mesh is being built, and then thrown away -- the mesh report lives in
memory for the length of one pipeline run.  So the only way to quote the gate-1
number for an archived case was to *rebuild* the mesh and hope it is
deterministic, which is exactly the kind of "trust the rebuild" the project
otherwise refuses to do.

Reading the quality back off ``model.msh`` is strictly better evidence: it is
the artifact that actually ships, and it needs no OCC rebuild.  Same formula as
the gate (``minSICN`` over every 2-D element), so the two agree by construction.

Usage::

    # one file
    python diagnostics/msh_quality.py FEM-Bench-Aero/modeling/naca4412_wingbox/model.msh

    # every case under a tree, one line each, worst first
    python diagnostics/msh_quality.py --tree FEM-Bench-Aero/modeling
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import gmsh


def quality(path: Path) -> dict:
    """``minSICN`` over every 2-D element of ``path``.

    Returns a dict rather than a bare float so the caller can report the element
    mix too: "minJ 0.62" with 8 triangles hiding in it is a different model from
    "minJ 0.62" all-quad, and the gate cares about both.
    """
    gmsh.clear()
    gmsh.open(str(path))
    tags: list[int] = []
    counts: dict[int, int] = {}
    for dim, tag in gmsh.model.getEntities(2):
        et, etags, _ = gmsh.model.mesh.getElements(2, tag)
        for t, tg in zip(et, etags):
            counts[t] = counts.get(t, 0) + len(tg)
            tags.extend(tg)
    if not tags:
        return {"min": float("nan"), "n": 0, "types": {}}
    q = [float(v) for v in gmsh.model.mesh.getElementQualities(tags, "minSICN")]
    return {"min": min(q), "n": len(tags), "types": dict(sorted(counts.items()))}


# Gmsh element type ids we care about, named the way the project names them.
_GMSH_ELEM = {1: "line2", 2: "tri3", 3: "quad4", 4: "tet4", 5: "hex8", 9: "tri6", 10: "quad9"}


def _fmt(d: dict) -> str:
    types = ", ".join(f"{_GMSH_ELEM.get(t, 'type' + str(t))}x{n}"
                      for t, n in d["types"].items())
    return f"minJ {d['min']:.4f}  n={d['n']}  [{types}]"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("msh", nargs="?", help="a single .msh file")
    ap.add_argument("--tree", help="a dataset tree; every <case>/model.msh under it")
    ap.add_argument("--threshold", type=float, default=0.30,
                    help="gate-1 min Jacobian threshold (default 0.30)")
    args = ap.parse_args(argv)

    # One gmsh session for the whole run: ``quality()`` only clears and reopens,
    # so a --tree sweep initialises once instead of once per case.
    gmsh.initialize()
    rows: list[tuple[float, str]] = []
    if args.tree:
        root = Path(args.tree)
        for case in sorted(p for p in root.iterdir() if p.is_dir()):
            msh = case / "model.msh"
            if not msh.exists():
                print(f"  [skip] {case.name}: no model.msh")
                continue
            d = quality(msh)
            bad = " tri3!" if any(_GMSH_ELEM.get(t, "").startswith("tri") for t in d["types"]) else ""
            rows.append((d["min"], f"  {'PASS' if d['min'] >= args.threshold else 'FAIL'} "
                                   f"{case.name:46s} {_fmt(d)}{bad}"))
    elif args.msh:
        d = quality(Path(args.msh))
        rows.append((d["min"], f"  {_fmt(d)}"))
    else:
        ap.error("give a .msh path or --tree")

    for _, line in sorted(rows):
        print(line)
    if len(rows) > 1:
        worst = min(rows)[0]
        print(f"  worst minJ {worst:.4f} (threshold {args.threshold:g}) -> "
              f"{'PASS' if worst >= args.threshold else 'FAIL'}")
    gmsh.finalize()
    return 0


if __name__ == "__main__":
    sys.exit(main())
