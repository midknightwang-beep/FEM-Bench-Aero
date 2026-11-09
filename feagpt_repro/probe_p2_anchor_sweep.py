"""U3a helper: mesh-size sweep for the anchor shell (lambda1 + quality).

Answers one question before any boundary re-interpretation: is the 28 mm
N_cr mesh-converged?  Blossom minSICN on the plain shell is non-monotonic
in size (measured 20->0.0245, 22->0.0271, 24->0.0291, 26->0.0314, 28->0.441,
all vs the 0.30 gate), so only sizes that PASS the gate are usable anchors -
the sweep also reports quality so a failing size is distinguishable from a
converging lambda.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from feagpt.spec import FEASpec          # noqa: E402
from feagpt import pipeline, solver      # noqa: E402
from extract_buckle_dat import extract   # noqa: E402

_V11 = _HERE.parent / "FEM-Bench-Aero" / "modeling"
_JOBS = _HERE / "_p2_anchor_sweep"
BASE = "fuselage_barrel_d1600_l1600_str8_frm3"
SIZES = (28.0, 32.0, 35.0, 40.0)
P_REF = 0.01


def main() -> int:
    _JOBS.mkdir(parents=True, exist_ok=True)
    rows = []
    for size in SIZES:
        name = f"anchor_sweep_s{int(size)}"
        d = json.loads((_V11 / BASE / "spec.json").read_text(encoding="utf-8"))
        d["name"] = name
        d["structure"]["params"]["n_stringers"] = 0
        d["structure"]["params"]["n_frames"] = 0
        d["mesh"]["size_chord"] = size
        d["mesh"]["size_span"] = size
        d["analysis"]["step_type"] = "buckle"
        d["analysis"]["buckling"] = {
            "n_modes": 6,
            "reference_load": {"kind": "hydrostatic_external", "magnitude": P_REF,
                               "pressure_sign": -1.0, "load_group": "zL",
                               "axial_load_group": "z0"},
        }
        d["extra"] = {"bc_kind": "ss3_ring"}
        # R69-bounded relaxation, DIAGNOSTIC ONLY (never an external number):
        # the plain shell's blossom minSICN sits below the 0.30 dataset gate at
        # every size < 28 (measured 14..27), so the CONVERGENCE question needs
        # finer meshes than the gate allows.  Declared per-spec, gate still
        # runs, min_quality still recorded; nothing enters the dataset.
        d["mesh"]["min_jacobian"] = 0.015  # measured floor 0.019-0.031 at sizes 14-27
        spec = FEASpec.from_dict(d)
        outdir = _JOBS / name
        outdir.mkdir(parents=True, exist_ok=True)
        res = pipeline.run(spec, outdir=outdir, step_export=False,
                           deck_only=True, solver_name="ccx")
        deck = Path(res.artifacts["inp"])
        run = solver.run(deck, solver="ccx", timeout=1800)
        dat = outdir / f"{name}.dat"
        lambdas, mesh_fail = [], getattr(res, "messages", [])
        if dat.exists():
            try:
                lambdas = extract(str(dat), "ccx", expect=3)["lambdas"]
            except Exception as exc:                # noqa: BLE001
                mesh_fail.append(str(exc))
        mesh_note = [m for m in mesh_fail if "quality" in m.lower()]
        row = {
            "size": size,
            "solve_ok": bool(run.ok),
            "lambdas": lambdas,
            "n_cr1": round(lambdas[0] * P_REF, 6) if lambdas else None,
            "mesh_gate_note": mesh_note[:1],
        }
        rows.append(row)
        print(f"[s{int(size)}] ok={row['solve_ok']} lambdas={lambdas[:1]} "
              f"n_cr1={row['n_cr1']} gate={mesh_note[:1]}", flush=True)
    (_JOBS / "sweep_result.json").write_text(
        json.dumps(rows, indent=1), encoding="utf-8")
    print("wrote", _JOBS / "sweep_result.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
