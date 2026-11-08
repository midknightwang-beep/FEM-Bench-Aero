"""C6-P2 P0-1 / P0-2: ccx load-scaling + 6-mode buckling probe (2026-11-08).

Expert review FBA-C6P2-REV-001-EX01 found that ccx 2.23 logs
``sigma=1.000000,d[0]=1.008207`` while Abaqus fundamental lambda is
0.687155 (< 1).  ARPACK shift-invert with a fixed sigma=1.0 can miss the
lowest modes and converge to eigenvalues near sigma.  The decisive, cheap
test is: vary P_ref (0.1 / 0.05 / 0.02 MPa) on the SAME mesh and request
SIX modes.  If N_cr = lambda * P_ref is invariant and modes below 1.0
appear, the earlier "38% formulation difference" was (at least partly) a
mode-selection artifact.

Serial solves (R61).  .dat copies are archived under
reports/diagnostics/p2_scaling_ccx/ ; large decks stay in the job dir and
are represented by sha256 only.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from feagpt.spec import FEASpec          # noqa: E402
from feagpt import pipeline, solver      # noqa: E402
from extract_buckle_dat import extract    # noqa: E402

_V11 = _HERE.parent / "FEM-Bench-Aero" / "modeling"
_JOBS = _HERE / "_p2_scaling_ccx"
_ARCH = _HERE / "reports/diagnostics/p2_scaling_ccx"
_OUT = _HERE / "reports/diagnostics/p2_load_scaling_ccx_2026-11-08.json"
BASE = "fuselage_barrel_d1600_l1600_str8_frm3"
P_REFS = [0.1, 0.05, 0.02]
N_MODES = 6


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    _JOBS.mkdir(parents=True, exist_ok=True)
    _ARCH.mkdir(parents=True, exist_ok=True)
    rows = []
    for pref in P_REFS:
        tag = f"p{int(round(pref * 1000)):03d}"       # p100 / p050 / p020
        name = f"{BASE}_buckle_{tag}"
        d = json.loads((_V11 / BASE / "spec.json").read_text(encoding="utf-8"))
        d["name"] = name
        d["analysis"]["step_type"] = "buckle"
        d["analysis"]["buckling"] = {
            "n_modes": N_MODES,
            "reference_load": {"kind": "pressure", "magnitude": pref,
                               "pressure_sign": -1.0},
        }
        spec = FEASpec.from_dict(d)
        outdir = _JOBS / name
        outdir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        res = pipeline.run(spec, outdir=outdir, step_export=False,
                           deck_only=True, solver_name="ccx")
        deck = Path(res.artifacts["inp"])
        run = solver.run(deck, solver="ccx", timeout=2400)
        dat = outdir / f"{name}.dat"
        # archive the small .dat verbatim
        if dat.exists():
            shutil.copyfile(dat, _ARCH / f"{name}.dat")
        modes, lambdas, err = [], [], None
        if dat.exists():
            try:
                parsed = extract(str(dat), "ccx", expect=N_MODES)
                lambdas = parsed["lambdas"]
                modes = [m["mode"] for m in parsed["modes"]]
            except Exception as exc:                 # noqa: BLE001
                err = f"{type(exc).__name__}: {exc}"
        log = (run.log or "")
        sigma_hits = [x.strip() for x in log.splitlines() if "sigma=" in x.lower()]
        row = {
            "p_ref_mpa": pref, "tag": tag, "n_modes_requested": N_MODES,
            "solve_rc": run.returncode, "solve_ok": bool(run.ok),
            "wall_seconds": round(time.time() - t0, 1),
            "deck_sha256": sha(deck), "deck_bytes": deck.stat().st_size,
            "dat_archived": str(_ARCH / f"{name}.dat") if dat.exists() else None,
            "lambdas": lambdas, "modes": modes,
            "n_cr": [round(x * pref, 8) for x in lambdas],
            "has_lambda_below_1": any(0 < x < 1.0 for x in lambdas),
            "sigma_log_lines": sigma_hits[-3:],
            "parse_error": err,
        }
        rows.append(row)
        print(f"[{tag}] P_ref={pref} rc={run.returncode} lambdas={lambdas} "
              f"N_cr={row['n_cr']} sigma={sigma_hits[-1:] } wall={row['wall_seconds']}s",
              flush=True)

    # objective comparison; no final cause judgement here
    ncr1 = [r["n_cr"][0] for r in rows if r["n_cr"]]
    spread = (max(ncr1) - min(ncr1)) / (sum(ncr1) / len(ncr1)) if ncr1 else None
    out = {
        "what": "C6-P2 P0-1/P0-2 ccx load-scaling invariance + 6-mode probe",
        "date": "2026-11-08",
        "expert_trigger": "FBA-C6P2-REV-001-EX01: ccx sigma=1.0 shift-invert candidate",
        "status": "diagnostic evidence; NOT a final cause conclusion",
        "case": BASE, "p_refs_mpa": P_REFS, "n_modes_requested": N_MODES,
        "rows": rows,
        "n_cr_lambda1_spread_rel": round(spread, 6) if spread is not None else None,
        "interpretation_rules": [
            "If lambda scales ~1/P_ref (N_cr stable) and modes below 1.0 appear, "
            "the previous 2-mode result near sigma=1.0 was a mode-selection artifact.",
            "If lambda stays pinned near 1.0 regardless of P_ref, shift contamination "
            "is indicated and ccx 2.23 *BUCKLE is unusable for this case without mitigation.",
            "If N_cr is stable but still ~38% above Abaqus, the residual difference "
            "remains a formulation candidate (C1/C2), subject to mode-shape pairing.",
        ],
        "repro": ["python probe_p2_load_scaling.py"],
    }
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {_OUT}")
    print(f"N_cr(lambda1) spread rel = {out['n_cr_lambda1_spread_rel']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
