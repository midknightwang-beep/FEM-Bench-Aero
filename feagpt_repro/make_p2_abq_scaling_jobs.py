"""C6-P2 P0-1/P0-2: Abaqus external jobs for load scaling (2026-11-08).

Companion to probe_p2_load_scaling.py (ccx side).  SAME spec family, SAME
six modes, SAME three reference pressures (0.1 / 0.05 / 0.02 MPa), abaqus
dialect only.  Abaqus cannot run inside the agent (tsbx.dll), so this script
writes decks + a manual .bat to be run OUTSIDE WorkBuddy.

Expert review EX01: if N_cr = lambda * P_ref is invariant across the three
loads while ccx stays pinned near sigma=1.0, the shift/mode-selection cause
(C3) is confirmed and the earlier 37.87% cannot be called a formula gap.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from feagpt.spec import FEASpec          # noqa: E402
from feagpt import pipeline              # noqa: E402

_V11 = _HERE.parent / "FEM-Bench-Aero" / "modeling"
_JOBS = _HERE / "_p2_abq_scaling"
BASE = "fuselage_barrel_d1600_l1600_str8_frm3"
P_REFS = [0.1, 0.05, 0.02]
N_MODES = 6

HEAD = """@echo off
REM ============================================================
REM  C6-P2 P0-1/P0-2 Abaqus load-scaling -- run OUTSIDE WorkBuddy.
REM  3 decks: P_ref = 0.1 / 0.05 / 0.02 MPa, 6 modes each.
REM  Compare lambda * P_ref against the ccx scaling artifact.
REM  When you see ALL DONE, tell WOONZI and he takes over.
REM ============================================================
setlocal enabledelayedexpansion
set BASE=F:\\AI FEA Modeling DataSets\\feagpt_repro
set ABAQUS="D:\\Program Files\\SIMULIA\\Commands\\abaqus.bat"
"""

CASE = """
echo ============ %CASE% ============
cd /d "%BASE%\\_p2_abq_scaling\\%CASE%"
if not exist "%CASE%.inp" (
  echo [ERR] input deck missing
  pause
  exit /b 1
)
if exist "%CASE%.odb" del /q "%CASE%.odb"
if exist "%CASE%.odb_f" del /q "%CASE%.odb_f"
if exist "%CASE%.lck" del /q "%CASE%.lck"
call %ABAQUS% job=%CASE% cpus=1 interactive ask_delete=OFF
if errorlevel 1 (
  echo [ERR] solver error. Check %CASE%.dat / %CASE%.msg / %CASE%.sta
  pause
  exit /b 1
)
if not exist "%CASE%.sta" (
  echo [ERR] no .sta -- job died before writing a status file
  pause
  exit /b 1
)
echo --- %CASE%.sta ---
type "%CASE%.sta"
echo --- eigenvalue table in %CASE%.dat ---
findstr /i /c:"MODE NO" /c:"EIGENVALUE" /c:"ACCEPTED" "%CASE%.dat"
"""

TAIL = """
echo.
echo === ALL DONE - 3/3 submitted ===
echo Paste each .sta tail and the .dat eigenvalue tables back to WOONZI.
pause
exit /b 0
"""


def main() -> int:
    _JOBS.mkdir(parents=True, exist_ok=True)
    names = []
    for pref in P_REFS:
        tag = f"p{int(round(pref * 1000)):03d}"
        name = f"{BASE}_buckle_{tag}_abq"
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
        res = pipeline.run(spec, outdir=outdir, step_export=False,
                           deck_only=True, solver_name="abaqus")
        deck = Path(res.artifacts["inp"])
        txt = deck.read_text(encoding="utf-8")
        checks = {
            "*BUCKLE present": "*BUCKLE" in txt,
            "LANCZOS": "EIGENSOLVER=LANCZOS" in txt,
            "6 modes line": f"{N_MODES}, 0.0, 1.0e6" in txt,
            "*STATIC absent": "*STATIC" not in txt,
            "no OUTPUT=2D": "OUTPUT=2D" not in txt,
            "no NUMBER INTERVAL": "NUMBER INTERVAL" not in txt,
            "reference load in step": "*DLOAD" in txt.split("*BUCKLE", 1)[-1],
            "dload value": f"E_SKIN, P, -{pref:g}" in txt,
        }
        bad = [k for k, v in checks.items() if not v]
        print(f"  [{name}] p_ref={pref} checks={sum(checks.values())}/{len(checks)}"
              + (f" FAILED={bad}" if bad else ""))
        if bad:
            return 1
        names.append(name)

    bat = HEAD + "".join(CASE.replace("%CASE%", n) for n in names) + TAIL
    bat_path = _JOBS / "run_p2_abq_scaling_MANUAL.bat"
    bat_path.write_text(bat, encoding="utf-8", newline="\r\n")
    print(f"\n{bat_path} written ({len(names)} decks)")
    print("REMINDER: run OUTSIDE WorkBuddy; agent-side Abaqus always fails.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
