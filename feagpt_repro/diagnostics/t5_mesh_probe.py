"""Probe: why does the T-section model fail with ``1D mesh cannot be divided by 2``?

The blade model meshes fine; the T model does not.  The difference is that a T
adds a **flange strip**: after the web cuts it, each half is 15 x 500 mm, and
those halves sit at 90 degrees to the web they hang off.

This probe builds the real T geometry and then tries a ladder of meshing
settings, so the failing control is identified rather than guessed at.  It also
dumps the curve-length distribution, because "cannot be divided by 2" is a
statement about a *1D* entity.

Run::

    python diagnostics/t5_mesh_probe.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gmsh  # noqa: E402

from feagpt import geometry as G  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
SPEC = HERE / "_t5_probe" / "naca4412_wingbox_str3_T.spec.json"

BASE = {
    "Mesh.MeshSizeFromCurvature": 24.0,
    "Mesh.MeshSizeExtendFromBoundary": 1.0,
    "Mesh.MeshSizeFromPoints": 1.0,
    "Mesh.MeshSizeMin": 2.0,
    "Mesh.MeshSizeMax": 25.0,
    "Mesh.Algorithm": 6,
    "Mesh.RecombineAll": 1,
    "Mesh.RecombinationAlgorithm": 3,
    "Mesh.ElementOrder": 1,
}

LADDER = [
    ("as-is", {}),
    ("no recombine", {"Mesh.RecombineAll": 0}),
    ("recomb alg 1", {"Mesh.RecombinationAlgorithm": 1}),
    ("no curvature field", {"Mesh.MeshSizeFromCurvature": 0.0}),
    ("no extend-from-boundary", {"Mesh.MeshSizeExtendFromBoundary": 0.0}),
    ("max size 10", {"Mesh.MeshSizeMax": 10.0}),
    ("max size 6", {"Mesh.MeshSizeMax": 6.0}),
    ("min size 0.5", {"Mesh.MeshSizeMin": 0.5}),
    ("algorithm 5 (delaunay)", {"Mesh.Algorithm": 5}),
    ("algorithm 1 (meshadapt)", {"Mesh.Algorithm": 1}),
]


def curve_lengths() -> list[float]:
    out = []
    for _dim, tag in gmsh.model.getEntities(1):
        try:
            out.append(float(gmsh.model.occ.getMass(1, tag)))
        except Exception:
            try:
                out.append(float(gmsh.model.getMass(1, tag)))
            except Exception:
                out.append(-1.0)
    return sorted(out)


def main() -> int:
    spec = FEASpec.from_json(SPEC)

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("t5_probe")
    try:
        geo = G.build(gmsh, spec)
        occ = gmsh.model.occ
        occ.synchronize()

        n_faces = len(gmsh.model.getEntities(2))
        n_curves = len(gmsh.model.getEntities(1))
        print(f"geometry built: {n_faces} faces, {n_curves} curves")
        print("group sizes   :", {k: len(v) for k, v in geo.surfaces.items() if v})
        for note in geo.notes:
            print("  note:", note)

        lens = [v for v in curve_lengths() if v >= 0]
        lens.sort()
        print(f"\ncurve lengths : min {lens[0]:.4f}  p10 {lens[len(lens)//10]:.3f}  "
              f"median {lens[len(lens)//2]:.3f}  max {lens[-1]:.1f}  (n={len(lens)})")
        print("shortest 12   :", [round(v, 4) for v in lens[:12]])
        print("by length band:")
        import collections
        bounds = [(0, 0.5), (0.5, 1), (1, 2), (2, 5), (5, 10), (10, 20), (20, 50),
                  (50, 200), (200, 1e9)]
        for lo, hi in bounds:
            n = sum(1 for v in lens if lo <= v < hi)
            if n:
                print(f"    [{lo:>5}, {hi:>9}) : {n}")

        # 1D alone: isolates whether the failure is on a curve
        print("\n--- 1D only ---")
        for label, opts in LADDER:
            for k, v in {**BASE, **opts}.items():
                gmsh.option.setNumber(k, v)
            gmsh.model.mesh.clear()
            try:
                gmsh.model.mesh.generate(1)
                print(f"  {label:<26} 1D OK  ({len(gmsh.model.mesh.getNodes()[0])} nodes)")
            except Exception as exc:
                print(f"  {label:<26} 1D FAIL {exc}")

        print("\n--- 2D ladder ---")
        results = []
        for label, opts in LADDER:
            for k, v in {**BASE, **opts}.items():
                gmsh.option.setNumber(k, v)
            gmsh.model.mesh.clear()
            rec = {"label": label, "opts": opts}
            try:
                gmsh.model.mesh.generate(2)
                tags, _, _ = gmsh.model.mesh.getNodes()
                etypes = {}
                for _d, t in gmsh.model.getEntities(2):
                    et, etags, _ = gmsh.model.mesh.getElements(2, t)
                    for typ, tg in zip(et, etags):
                        etypes[typ] = etypes.get(typ, 0) + len(tg)
                rec.update({"ok": True, "n_nodes": len(tags), "etypes": etypes})
                print(f"  {label:<26} OK   nodes={len(tags):>6}  etypes={etypes}")
            except Exception as exc:
                rec.update({"ok": False, "error": str(exc)})
                print(f"  {label:<26} FAIL {exc}")
            results.append(rec)
    finally:
        gmsh.finalize()

    out = Path(__file__).resolve().parent / "t5_mesh_probe.json"
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"\nraw -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
