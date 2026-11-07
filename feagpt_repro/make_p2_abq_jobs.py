"""Prepare the C6-P2 Abaqus external smoke job (2026-11-07).

Two decks (one stiffened panel, one barrel) are written with the abaqus
dialect but NOT solved here: Abaqus inside the agent always fails (tsbx.dll).
The generated .bat is to be run by the user OUTSIDE WorkBuddy.

Family-specific values (pressure group / dload sign) are deliberately NOT
written into analysis.buckling.reference_load -- the pipeline supplies the
builder's declaration (D21), keeping dataset meta and execution config apart
(N-35).
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
_JOBS = _HERE / "_p2_abq_jobs"
CASES = ["stiffened_panel_600x600", "fuselage_barrel_d1600_l1600_str8_frm3"]

BAT_HEAD = """@echo off
REM ============================================================
REM  C6-P2 Abaqus *BUCKLE smoke -- run OUTSIDE WorkBuddy.
REM  2 decks, ccx side already proven (rc=0, .dat BUCKLING FACTOR OUTPUT).
REM  Purpose: verify the Abaqus data line (n, 1.0e6 / SUBSPACE) and
REM  capture the eigenvalue table layout for extract_buckle_dat.py.
REM  When you see "ALL DONE", tell WOONZI and he takes over.
REM ============================================================
setlocal enabledelayedexpansion
set BASE=F:\\AI FEA Modeling DataSets\\feagpt_repro
set ABAQUS="D:\\Program Files\\SIMULIA\\Commands\\abaqus.bat"
"""

BAT_CASE = """
echo ============ %CASE% ============
cd /d "%BASE%\\_p2_abq_jobs\\%CASE%"
if not exist "%CASE%.inp" (
  echo [ERR] input deck missing
  pause
  exit /b 1
)
if exist "%CASE%.odb" del /q "%CASE%.odb"
if exist "%CASE%.odb_f" del /q "%CASE%.odb_f"
if exist "%CASE%.lck" del /q "%CASE%.lck"
echo === solving %CASE% ===
call %ABAQUS% job=%CASE% cpus=1 interactive ask_delete=OFF
if errorlevel 1 (
  echo [ERR] solver error. Check %CASE%.dat / %CASE%.msg / %CASE%.sta
  pause
  exit /b 1
)
if not exist "%CASE%.sta" (
  echo [ERR] no .sta -- job may have died before writing a status file
  pause
  exit /b 1
)
echo --- %CASE%.sta ---
type "%CASE%.sta"
echo --- eigenvalue hits in %CASE%.dat ---
findstr /i /c:"EIGENVALUE" /c:"BUCKLING" /c:"MODE NO" "%CASE%.dat"
"""

BAT_TAIL = """
echo.
echo === ALL DONE - 2/2 submitted ===
echo Paste the .sta tails and the eigenvalue-table lines back to WOONZI.
pause
exit /b 0
"""


def main() -> int:
    _JOBS.mkdir(parents=True, exist_ok=True)
    good = 0
    for base in CASES:
        d = json.loads((_V11 / base / "spec.json").read_text(encoding="utf-8"))
        d["name"] = base + "_buckle"
        d["analysis"]["step_type"] = "buckle"
        d["analysis"]["buckling"] = {
            "n_modes": 2,
            # kind + magnitude only; group/sign come from the builder (D21)
            "reference_load": {"kind": "pressure", "magnitude": 0.1},
        }
        spec = FEASpec.from_dict(d)
        outdir = _JOBS / spec.name
        outdir.mkdir(parents=True, exist_ok=True)
        res = pipeline.run(spec, outdir=outdir, step_export=False,
                           deck_only=True, solver_name="abaqus")
        deck = Path(res.artifacts["inp"])
        txt = deck.read_text(encoding="utf-8")
        checks = {
            "*BUCKLE present": "*BUCKLE" in txt,
            "SUBSPACE eigensolver": "EIGENSOLVER=SUBSPACE" in txt,
            "*STATIC absent": "*STATIC" not in txt,
            "no OUTPUT=2D": "OUTPUT=2D" not in txt,
            "no NUMBER INTERVAL": "NUMBER INTERVAL" not in txt,
            "reference load in step": "*DLOAD" in txt.split("*BUCKLE", 1)[-1],
        }
        bad = [k for k, v in checks.items() if not v]
        for k, v in checks.items():
            print(f"  [{'ok' if v else 'FAIL':4}] {spec.name}: {k}")
        if bad:
            print(f"  !! {spec.name} has {len(bad)} failed checks, bat not written for it")
            continue
        good += 1
        print(f"  deck: {deck}")
    if good != len(CASES):
        return 1
    bat = BAT_HEAD + "".join(
        BAT_CASE.replace("%CASE%", c + "_buckle") for c in CASES) + BAT_TAIL
    bat_path = _JOBS / "run_p2_abq_MANUAL.bat"
    bat_path.write_text(bat, encoding="utf-8", newline="\r\n")
    print(f"\n{_JOBS / 'run_p2_abq_MANUAL.bat'} written ({good} decks ready)")
    print("REMINDER: run it OUTSIDE WorkBuddy (agent-side Abaqus always fails).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
