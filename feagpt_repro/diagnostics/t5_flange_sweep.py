"""Probe: what makes blossom full-quad fail on the T stringer, and where is the
width threshold?

Established by ``t5_mesh_probe.py``:

* the 1D mesh is fine, the failure is in 2D recombination;
* ``Mesh.RecombineAll=0`` meshes (all triangles) and ``RecombinationAlgorithm=1``
  meshes (blossom, leaving 5 % triangles), so the geometry is sound;
* only ``RecombinationAlgorithm=3`` (blossom **full-quad**, which is what the
  zero-triangle gate needs) fails.

The T's flange is cut in two by the web, so each half is a 15 x 500 mm strip -
narrower than the blade's 20 x 500 mm strip, which full-quad handles.  This
probe sweeps the flange width (and a couple of alternative controls) to find
where the strip becomes meshable again.

Run::

    python diagnostics/t5_flange_sweep.py
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

ETYPE = {2: "tri3", 3: "quad4"}

CASES = [
    ("blade (reference)",       "blade", 30.0, {}),
    ("T flange 30 (as spec'd)", "T",     30.0, {}),
    ("T flange 40",             "T",     40.0, {}),
    ("T flange 50",             "T",     50.0, {}),
    ("T flange 60",             "T",     60.0, {}),
    ("T flange 80",             "T",     80.0, {}),
    ("T 30 + optimize topo",    "T",     30.0, {"Mesh.RecombineOptimizeTopology": 5}),
    ("T 30 + recomb alg 1",     "T",     30.0, {"Mesh.RecombinationAlgorithm": 1}),
    ("T 30 + no recombine",     "T",     30.0, {"Mesh.RecombineAll": 0}),
]


def mesh_case(kind: str, width: float, extra: dict) -> dict:
    spec = FEASpec.from_json(SPEC)
    spec.name = f"probe_{kind}_{width}"
    spec.airfoil.stringer_kind = kind
    spec.airfoil.stringer_flange_width = width

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add(spec.name)
    try:
        G.build(gmsh, spec)
        for k, v in {**BASE, **extra}.items():
            gmsh.option.setNumber(k, v)
        n_faces = len(gmsh.model.getEntities(2))
        try:
            gmsh.model.mesh.generate(2)
        except Exception as exc:
            return {"n_faces": n_faces, "ok": False, "error": str(exc)}

        tags, _, _ = gmsh.model.mesh.getNodes()
        etypes: dict[int, int] = {}
        all_tags: list[int] = []
        for _d, t in gmsh.model.getEntities(2):
            et, etags, _ = gmsh.model.mesh.getElements(2, t)
            for typ, tg in zip(et, etags):
                etypes[int(typ)] = etypes.get(int(typ), 0) + len(tg)
                all_tags.extend(int(v) for v in tg)
        q = [float(v) for v in gmsh.model.mesh.getElementQualities(all_tags, "minSICN")]
        return {
            "n_faces": n_faces, "ok": True, "n_nodes": int(len(tags)),
            "etypes": {ETYPE.get(k, str(k)): v for k, v in sorted(etypes.items())},
            "minJ": round(min(q), 4),
        }
    finally:
        gmsh.finalize()


def main() -> int:
    rows = []
    for label, kind, width, extra in CASES:
        rec = mesh_case(kind, width, extra)
        rec.update({"label": label, "kind": kind, "width": width,
                    "extra": extra, "flange_half": width / 2.0})
        rows.append(rec)
        if rec["ok"]:
            print(f"  {label:<24} OK    faces={rec['n_faces']:>4} nodes={rec['n_nodes']:>7} "
                  f"minJ={rec['minJ']:.3f}  {rec['etypes']}")
        else:
            print(f"  {label:<24} FAIL  faces={rec['n_faces']:>4} {rec['error']}")

    out = Path(__file__).resolve().parent / "t5_flange_sweep.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"\nraw -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
