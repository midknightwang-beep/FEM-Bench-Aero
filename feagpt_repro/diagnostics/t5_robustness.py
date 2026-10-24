"""Probe: is the size cap robust across flange widths?

``t5_local_refine.py`` found three settings that make the T model mesh, but all
of them were tuned on a single width (30 mm).  ``t5_flange_sweep.py`` already
showed what happens when a setting is width-tuned: minJ jumped 0.339 -> 0.225 ->
0.523 -> 0.314 as the width went 40/50/60/80.  A pipeline that only meshes at
the width it was tuned for is not a pipeline.

So this probe holds the setting fixed and sweeps the width, testing

* a **fixed** global cap (12, 15 mm), and
* a cap **derived from the geometry**: ``0.8 x flange_half_width``, so the strip
  is always resolved the same way regardless of how wide the flange is.

The acceptance rule is minJ >= 0.35 at *every* width (not >= 0.30, which is the
gate: a build that only just clears the gate has no margin for the next change).

Run::

    python diagnostics/t5_robustness.py
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
    "Mesh.Algorithm": 6,
    "Mesh.RecombineAll": 1,
    "Mesh.RecombinationAlgorithm": 3,
    "Mesh.ElementOrder": 1,
}

ETYPE = {2: "tri3", 3: "quad4"}
WIDTHS = [20.0, 30.0, 40.0, 50.0, 60.0]
SETTINGS = [("adaptive 0.8*half", "adaptive"), ("fixed max 12", 12.0), ("fixed max 15", 15.0)]
ACCEPT_MINJ = 0.35


def mesh_case(width: float, setting) -> dict:
    spec = FEASpec.from_json(SPEC)
    spec.airfoil.stringer_kind = "T"
    spec.airfoil.stringer_flange_width = width

    cap = 0.8 * (width / 2.0) if setting == "adaptive" else float(setting)

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("robust")
    try:
        G.build(gmsh, spec)
        for k, v in BASE.items():
            gmsh.option.setNumber(k, v)
        gmsh.option.setNumber("Mesh.MeshSizeMax", cap)
        try:
            gmsh.model.mesh.generate(2)
        except Exception as exc:
            return {"cap": round(cap, 2), "ok": False, "error": str(exc)}
        tags, _, _ = gmsh.model.mesh.getNodes()
        etypes: dict[int, int] = {}
        all_tags: list[int] = []
        for _d, t in gmsh.model.getEntities(2):
            et, etags, _ = gmsh.model.mesh.getElements(2, t)
            for typ, tg in zip(et, etags):
                etypes[int(typ)] = etypes.get(int(typ), 0) + len(tg)
                all_tags.extend(int(v) for v in tg)
        q = [float(v) for v in gmsh.model.mesh.getElementQualities(all_tags, "minSICN")]
        return {"cap": round(cap, 2), "ok": True, "n_nodes": int(len(tags)),
                "etypes": {ETYPE.get(k, str(k)): v for k, v in sorted(etypes.items())},
                "minJ": round(min(q), 4)}
    finally:
        gmsh.finalize()


def main() -> int:
    rows = []
    for label, setting in SETTINGS:
        print(f"\n== {label} ==")
        for w in WIDTHS:
            rec = mesh_case(w, setting)
            rec.update({"setting": label, "width": w, "flange_half": w / 2.0})
            rows.append(rec)
            if rec["ok"]:
                verdict = "ok" if rec["minJ"] >= ACCEPT_MINJ else "MARGIN-LOW"
                print(f"  w={w:>5}  half={w/2:>4}  cap={rec['cap']:>5}  OK   "
                      f"nodes={rec['n_nodes']:>7} minJ={rec['minJ']:.3f}  {rec['etypes']}  [{verdict}]")
            else:
                print(f"  w={w:>5}  half={w/2:>4}  cap={rec['cap']:>5}  FAIL {rec['error']}")
    out = Path(__file__).resolve().parent / "t5_robustness.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"\nraw -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
