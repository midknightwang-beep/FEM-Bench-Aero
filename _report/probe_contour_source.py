"""Probe: can we build a contour map from shipped artifacts alone?

A contour plot needs three things aligned on ONE node-id space:

  1. node coordinates        -> model.msh  (gmsh, archived in the dataset)
  2. element connectivity    -> model.msh
  3. per-node field values   -> <case>.odb.json  (Abaqus extract)
                             -> <case>.frd        (ccx)

This probe checks that the node ids in the *.msh archive match those in the
Abaqus odb.json (and, for ccx, in the .frd).  If they do not, a contour map
cannot key field values onto the mesh.

Run with the managed venv.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import gmsh

gmsh.initialize(interruptible=False)
gmsh.option.setNumber("General.Terminal", 0)

ROOT = Path(r"F:\AI FEA Modeling DataSets")
DS = ROOT / "FEM-Bench-Aero"
REPRO = ROOT / "feagpt_repro"


def msh_nodes(path: Path):
    gmsh.clear()
    gmsh.open(str(path))
    ntag, ncoord, _ = gmsh.model.mesh.getNodes()
    ntag = np.asarray(ntag, dtype=np.int64)
    coords = np.asarray(ncoord, dtype=float).reshape(-1, 3)
    # element type census
    types = {}
    for dim, tag in gmsh.model.getEntities(2):
        etypes, _, enodes = gmsh.model.mesh.getElements(2, tag)
        for et, en in zip(etypes, enodes):
            name = gmsh.model.mesh.getElementProperties(et)[0]
            npe = gmsh.model.mesh.getElementProperties(et)[3]
            types[name] = types.get(name, 0) + len(en) // npe
    return ntag, coords, types


def main():
    cases = [
        ("wingbox", DS / "modeling/naca4412_wingbox/model.msh",
         REPRO / "outputs_abaqus/naca4412_wingbox/naca4412_wingbox.odb.json"),
        ("wingbox-planar", DS / "modeling/naca4412_wingbox_sweep40/model.msh",
         REPRO / "outputs_b2_abaqus/naca4412_wingbox_sweep40/naca4412_wingbox_sweep40.odb.json"),
        ("panel", DS / "modeling/stiffened_panel_800x600_str3/model.msh",
         REPRO / "outputs_b2_abaqus/stiffened_panel_800x600_str3/stiffened_panel_800x600_str3.odb.json"),
        ("barrel", DS / "modeling/fuselage_barrel_d2000_l2000_str8_frm3/model.msh",
         REPRO / "outputs_b3_abaqus/fuselage_barrel_d2000_l2000_str8_frm3/fuselage_barrel_d2000_l2000_str8_frm3.odb.json"),
    ]
    for name, msh, odbj in cases:
        print(f"===== {name}")
        if not msh.exists():
            print("  msh MISSING", msh)
            continue
        ntag, coords, types = msh_nodes(msh)
        print(f"  msh: {len(ntag)} nodes, elems={types}")
        print(f"  msh node id range: {ntag.min()}..{ntag.max()}")
        if not odbj.exists():
            print("  odb.json MISSING", odbj)
            continue
        d = json.loads(odbj.read_text(encoding="utf-8"))
        kn = np.asarray([int(k) for k in d["nodes"].keys()], dtype=np.int64)
        print(f"  odb.json: {len(kn)} nodes, id range {kn.min()}..{kn.max()}")
        inter = np.intersect1d(ntag, kn)
        print(f"  intersection: {len(inter)}  "
              f"({len(inter)/len(ntag)*100:.2f}% of msh, {len(inter)/len(kn)*100:.2f}% of odb)")
        # coordinate agreement on a sample of shared ids
        dnodes = d["nodes"]
        sample = inter[:: max(len(inter) // 200, 1)][:200]
        lookup = {int(t): i for i, t in enumerate(ntag)}
        err = 0.0
        for sid in sample:
            a = coords[lookup[int(sid)]]
            b = np.asarray(dnodes[str(int(sid))], dtype=float)
            err = max(err, float(np.max(np.abs(a - b))))
        print(f"  max coord mismatch on {len(sample)} shared ids: {err:.3e} mm")
        # field census
        for fld, fv in d["results"].items():
            fk = np.asarray([int(k) for k in fv.keys()], dtype=np.int64)
            ii = np.intersect1d(ntag, fk)
            print(f"    field {fld:12s} n={len(fv):7d} share={len(ii):7d} "
                  f"({len(ii)/len(ntag)*100:.1f}% of msh)")
        print()


if __name__ == "__main__":
    main()
