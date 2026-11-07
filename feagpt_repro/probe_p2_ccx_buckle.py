"""C6-P2 ccx *BUCKLE smoke probe (2026-11-07).

One stiffened-panel case, reference pressure load inside the *BUCKLE step.
Prints the .dat lines that carry the buckling factor / eigenvalue table.
Read-only against the frozen volumes; everything lives in a temp dir.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from feagpt.spec import FEASpec          # noqa: E402
from feagpt import pipeline, solver      # noqa: E402

_V11 = _HERE.parent / "FEM-Bench-Aero" / "modeling"
BASE = "stiffened_panel_600x600"


def main() -> int:
    d = json.loads((_V11 / BASE / "spec.json").read_text(encoding="utf-8"))
    d["analysis"]["step_type"] = "buckle"
    d["analysis"]["buckling"] = {
        "n_modes": 2,
        "reference_load": {"kind": "pressure", "magnitude": 0.1,
                           "pressure_group": "panel", "pressure_dload_sign": -1.0},
    }
    spec = FEASpec.from_dict(d)
    with tempfile.TemporaryDirectory(prefix="p2_ccx_") as td:
        out = Path(td)
        res = pipeline.run(spec, outdir=out, step_export=False,
                           deck_only=True, solver_name="ccx")
        deck = Path(res.artifacts["inp"])
        print(f"deck: {deck.stat().st_size} B")
        run = solver.run(deck, solver="ccx", timeout=1800)
        print(f"solve: rc={run.returncode} ok={run.ok} dat={bool(run.dat)} "
              f"frd={bool(run.frd)}")
        if run.log:
            print("--- log tail ---")
            print((run.log or "")[-600:])
        dat = out / f"{spec.name}.dat"
        if not dat.exists():
            print("NO .dat -- solver did not produce eigenvalue output")
            return 1
        text = dat.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        hits = [(i, x) for i, x in enumerate(lines)
                if any(k in x.lower() for k in
                       ("buckl", "eigenvalue", "eigen value", "factor", "mode no"))]
        print(f"--- .dat keyword hits: {len(hits)} ---")
        for i, x in hits[:25]:
            print(f"  {i:5}: {x.rstrip()}")
        print("--- .dat tail ---")
        for x in lines[-25:]:
            print("   ", x.rstrip())
        return 0 if run.ok and hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
