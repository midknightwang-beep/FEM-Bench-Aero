"""Probe: can a *local* size field make the T stringer mesh robustly?

``t5_flange_sweep.py`` showed that widening the flange "works" only by luck:
minJ jumped 0.339 -> 0.225 -> 0.523 -> 0.314 as the width went 40/50/60/80, which
is not a trend, it is a coin toss decided by one bad element.  Betting the
zero-triangle gate on that is not acceptable.

Hypothesis to test: full-quad fails because the 15 mm flange half is meshed with
a single element across its width (target size ~25 mm), and the recombiner needs
an even count.  If so, forcing a small element size *near the stringers* should
fix it - without touching the global size field, which would perturb the
archived blade models (str3 is one of the nine regression seeds).

Each variant is timed and reports nodes / minJ / element mix, so the cost of the
refinement is visible and not just its effect.

Run::

    python diagnostics/t5_local_refine.py
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

# label, kind, width, field params (None = no field), extra options
VARIANTS = [
    ("T30 baseline (no field)", "T", 30.0, None, {}),
    ("T30 field size 7.5 dist 12", "T", 30.0, (7.5, 12.0), {}),
    ("T30 field size 5.0 dist 12", "T", 30.0, (5.0, 12.0), {}),
    ("T30 field size 5.0 dist 25", "T", 30.0, (5.0, 25.0), {}),
    ("T30 field size 3.0 dist 12", "T", 30.0, (3.0, 12.0), {}),
    ("T30 global max 15", "T", 30.0, None, {"Mesh.MeshSizeMax": 15.0}),
    ("T30 global max 12", "T", 30.0, None, {"Mesh.MeshSizeMax": 12.0}),
    ("blade + field (must stay OK)", "blade", 30.0, (5.0, 12.0), {}),
]


def run_variant(kind: str, width: float, field, extra: dict) -> dict:
    spec = FEASpec.from_json(SPEC)
    spec.airfoil.stringer_kind = kind
    spec.airfoil.stringer_flange_width = width

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("refine")
    try:
        geo = G.build(gmsh, spec)
        opts = {**BASE, **extra}
        for k, v in opts.items():
            gmsh.option.setNumber(k, v)

        if field is not None:
            size_min, dist_max = field
            strip_tags = [t for k, v in geo.surfaces.items()
                          if k.startswith("stringers_") for t in v]
            fd = gmsh.model.mesh.field.add("Distance")
            gmsh.model.mesh.field.setNumbers(fd, "SurfacesList", strip_tags)
            gmsh.model.mesh.field.setNumber(fd, "Sampling", 200)
            ft = gmsh.model.mesh.field.add("Threshold")
            gmsh.model.mesh.field.setNumber(ft, "InField", fd)
            gmsh.model.mesh.field.setNumber(ft, "SizeMin", float(size_min))
            gmsh.model.mesh.field.setNumber(ft, "SizeMax", float(opts["Mesh.MeshSizeMax"]))
            gmsh.model.mesh.field.setNumber(ft, "DistMin", 0.0)
            gmsh.model.mesh.field.setNumber(ft, "DistMax", float(dist_max))
            gmsh.model.mesh.field.setAsBackgroundMesh(ft)

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
            "n_elements": int(len(all_tags)),
            "etypes": {ETYPE.get(k, str(k)): v for k, v in sorted(etypes.items())},
            "minJ": round(min(q), 4),
            "meanJ": round(sum(q) / len(q), 4),
        }
    finally:
        gmsh.finalize()


def main() -> int:
    rows = []
    for label, kind, width, field, extra in VARIANTS:
        rec = run_variant(kind, width, field, extra)
        rec.update({"label": label, "kind": kind, "width": width,
                    "field": field, "extra": extra})
        rows.append(rec)
        if rec["ok"]:
            print(f"  {label:<30} OK    nodes={rec['n_nodes']:>7} el={rec['n_elements']:>7} "
                  f"minJ={rec['minJ']:.3f} meanJ={rec['meanJ']:.3f}  {rec['etypes']}")
        else:
            print(f"  {label:<30} FAIL  {rec['error']}")
    out = Path(__file__).resolve().parent / "t5_local_refine.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"\nraw -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
