#!/usr/bin/env python
"""Where do the bad elements live once stringers are added?

Run with the venv python::

    python diagnostics/stringer_quality.py [n_stringers]

Prints, per logical group, the face count, element count, element mix and the
worst scaled Jacobian - so "the mesh got worse" can be attributed to a specific
piece of geometry instead of guessed at.
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gmsh  # noqa: E402

from feagpt import geometry, meshing  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402


def main() -> int:
    n_str = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    spec = FEASpec()
    spec.airfoil.n_stringers_per_skin = n_str

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("probe")
    try:
        geo = geometry.build(gmsh, spec)
        rep = meshing.build_mesh(gmsh, spec, geo)
        print(f"n_stringers_per_skin = {n_str}")
        print(f"overall: {rep.n_nodes} nodes, {rep.n_elements} elements, "
              f"minJ {rep.min_quality:.4f}, meanJ {rep.mean_quality:.4f}")
        print(f"{'group':18s} {'faces':>5s} {'elems':>6s} {'worstJ':>8s}  mix")
        for g, tags in geo.surfaces.items():
            worst, n, mix = 1e9, 0, collections.Counter()
            for t in tags:
                et, etags, _ = gmsh.model.mesh.getElements(2, t)
                for ty, tg in zip(et, etags):
                    info = meshing._GMSH_ELEM.get(ty)
                    if not info or info[2] != "surface":
                        continue
                    tg = list(tg)
                    mix[info[0]] += len(tg)
                    n += len(tg)
                    worst = min(worst, min(gmsh.model.mesh.getElementQualities(tg, "minSICN")))
            if tags or n:
                print(f"{g:18s} {len(tags):5d} {n:6d} "
                      f"{'   -   ' if worst > 1e8 else f'{worst:8.4f}'}  {dict(mix)}")
    finally:
        gmsh.finalize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
