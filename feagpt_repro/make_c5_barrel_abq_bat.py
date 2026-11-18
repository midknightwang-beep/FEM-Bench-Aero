"""Write the OUTSIDE-WorkBuddy bat that solves the barrel with Abaqus.

Abaqus aborts inside the agent sandbox (tsbx.dll injection), so the owner runs
this bat from a normal cmd window.  Two steps per job:

  1. ``abaqus job=<name>``          -- static solve, writes <name>.odb
  2. ``abaqus python abaqus_odb.py`` -- ODB -> <name>.odb.json in the exact
     intermediate form ``feagpt.post.load_any`` consumes (so C5 post/report
     stay solver-agnostic).

Step 2 is the same script the pipeline uses for every Abaqus run; it emits
STRESS_PEAK (outer fibre) alongside the mid-surface STRESS, which is what the
barrel's registered max-vM definition (D8) needs.

All paths are read from the manifest written by make_c5_barrel_abq_job.py, and
from the launcher path already proven by the P2 runs on this machine.
"""
from __future__ import annotations

import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_MANIFEST = (_HERE / "_c5_runs" / "fuselage_barrel_d1800_l2000_str8_frm3"
             / "abq" / "c5_barrel_abq_manifest.json")

# 实测路径（2026-11-08 P2 已成功跑过；本机存在性再次核验过）
ABAQUS_BAT = r"D:\Program Files\SIMULIA\Commands\abaqus.bat"
ODB_SCRIPT = _HERE / "feagpt" / "abaqus_odb.py"
CHECK_SCRIPT = _HERE / "check_c5_barrel_abq.py"

HEAD = [
    "@echo off",
    "REM ============================================================",
    "REM  C5 barrel -- Abaqus STATIC solve + ODB extraction.",
    "REM  Run OUTSIDE WorkBuddy (agent-side Abaqus aborts: tsbx.dll).",
    "REM  Combined load: internal pressure 0.05 MPa + end shear 50 kN",
    "REM  + end moment 50 kN.m, on the SAME deck the ccx case used.",
    "REM  When you see ALL DONE, tell WOONZI and he takes over the",
    "REM  report / cross-solver check.",
    "REM ============================================================",
    "setlocal enabledelayedexpansion",
    f'set "ABAQUS={ABAQUS_BAT}"',
    'set "ODB_SCRIPT={odb_script}"',
    'set "PY={py}"',
    'set "CHECK={check}"',
    'set "ROOT={root}"',
    'set "NAME={name}"',
    "echo.",
    "echo === Preflight ===",
    'if not exist "%ABAQUS%" ( echo [ERR] abaqus.bat not found & goto :fail )',
    'if not exist "%ODB_SCRIPT%" ( echo [ERR] abaqus_odb.py not found & goto :fail )',
    'if not exist "%CHECK%" ( echo [ERR] check script not found & goto :fail )',
    'if not exist "%PY%" ( echo [ERR] venv python not found & goto :fail )',
    'if not exist "%ROOT%\\%NAME%.inp" ( echo [ERR] input deck missing & goto :fail )',
    "echo OK",
    "echo.",
]

# Each line is data -- no shell interpolation surprises.
BODY = [
    'cd /d "%ROOT%"',
    'echo === Solving %NAME% with Abaqus/Standard (static) ===',
    'echo    143402 S4 shell nodes / ~860k DOF -- expect several minutes.',
    'if exist "%NAME%.odb" del /q "%NAME%.odb"',
    'if exist "%NAME%.odb_f" del /q "%NAME%.odb_f"',
    'if exist "%NAME%.lck" del /q "%NAME%.lck"',
    'if exist "%NAME%.msg" del /q "%NAME%.msg"',
    'if exist "%NAME%.sta" del /q "%NAME%.sta"',
    'if exist "%NAME%.dat" del /q "%NAME%.dat"',
    'if exist "%NAME%.odb.json" del /q "%NAME%.odb.json"',
    'call "%ABAQUS%" job=%NAME% cpus=4 interactive ask_delete=OFF',
    "if errorlevel 1 (",
    '  echo [ERR] solver returned non-zero. Check %NAME%.msg / .dat / .sta',
    "  goto :fail",
    ")",
    'if not exist "%NAME%.odb" (',
    "  echo [ERR] no .odb produced -- job died before writing results",
    "  goto :fail",
    ")",
    "echo --- %NAME%.sta ---",
    'if exist "%NAME%.sta" type "%NAME%.sta"',
    "echo.",
    "echo === Extracting ODB -> %NAME%.odb.json ===",
    'call "%ABAQUS%" python "%ODB_SCRIPT%" "%ROOT%\\%NAME%.odb" "%ROOT%\\%NAME%.odb.json"',
    "if errorlevel 1 (",
    "  echo [ERR] ODB extraction failed",
    "  goto :fail",
    ")",
    'if not exist "%NAME%.odb.json" (',
    "  echo [ERR] no .odb.json -- extraction did not produce output",
    "  goto :fail",
    ")",
    "echo --- extracted blocks (raw ODB JSON keys) ---",
    'type "%NAME%.odb.json" | findstr /c:"STRESS_PEAK" /c:"section_points" /c:"stress_candidates_max_vm" /c:"stress_type"',
    "echo.",
    "echo === Structural gate (node count / blocks / finite) ===",
    'call "%PY%" "%CHECK%" "%ROOT%\\%NAME%.odb.json"',
    "if errorlevel 1 (",
    "  echo [ERR] structural gate FAILED -- see lines above",
    "  goto :fail",
    ")",
    "echo.",
    "echo === ALL DONE - barrel solved + ODB extracted + gate GREEN ===",
    "echo Tell WOONZI; he runs the cross-solver check and C5 report.",
    "pause",
    "exit /b 0",
    "",
    ":fail",
    "echo.",
    "echo [FAILED] see the [ERR] line above. Do NOT tell WOONZI it finished.",
    "pause",
    "exit /b 1",
    "",
]


def main() -> int:
    m = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    name = m["name"]
    root = Path(m["abq_dir"])
    py = (Path.home() / ".workbuddy/binaries/python/envs/default/Scripts/python.exe")
    lines = [ln.format(odb_script=str(ODB_SCRIPT), py=str(py),
                       check=str(CHECK_SCRIPT),
                       root=str(root), name=name) for ln in HEAD]
    lines += BODY
    bat = root / "run_c5_barrel_abq_MANUAL.bat"
    # CRLF + ASCII-safe (all substituted paths are ASCII on this machine)
    payload = ("\r\n".join(lines) + "\r\n")
    try:
        bat.write_bytes(payload.encode("ascii"))
    except UnicodeEncodeError as exc:
        raise SystemExit(f"[FAIL] bat has non-ASCII bytes: {exc}")
    # self-checks: 2 abaqus calls (solve + extract) + 1 venv gate call
    raw = bat.read_bytes()
    assert raw.count(b"call \"%ABAQUS%\"") == 2, "expected solve + extract calls"
    assert raw.count(b"call \"%PY%\"") == 1, "expected 1 structural-gate call"
    assert b"job=%NAME%" in raw and f'set "NAME={name}"'.encode() in raw
    assert b":fail" in raw and raw.count(b"\r\n") == len(lines), "CRLF mismatch"
    print(f"wrote {bat}  ({len(raw)} bytes, {len(lines)} lines)")
    print(f"  job = {name}")
    print(f"  root = {root}")
    print("Run it OUTSIDE WorkBuddy. NO solve is performed here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
