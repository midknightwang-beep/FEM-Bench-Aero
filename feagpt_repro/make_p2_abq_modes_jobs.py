"""Prepare the ONE external Abaqus job for P0-3 mode-shape extraction.

The three .odb files from the 2026-11-08 scaling batch already exist and their
decks contain ``*OUTPUT, FIELD / *NODE OUTPUT U`` -> NO re-solve is needed.
This only reads the ODBs with ``abaqus python`` (which cannot run inside the
WorkBuddy agent: tsbx.dll), so the user runs the generated .bat outside.

Generates: _p2_abq_scaling/run_p2_abq_modes_MANUAL.bat
"""

from __future__ import annotations

import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_JOBS = _HERE / "_p2_abq_scaling"
_SCRIPT = _HERE / "odb_tools" / "extract_buckle_odb.py"
_BASE = "fuselage_barrel_d1600_l1600_str8_frm3_buckle"
TAGS = ("p100", "p050", "p020")
ABAQUS_BAT = r"D:\Program Files\SIMULIA\Commands\abaqus.bat"

# Each line is built as data (no shell interpolation surprises).
HEAD = [
    "@echo off",
    "REM ============================================================",
    "REM  C6-P2 P0-3 / U14: extract Abaqus BUCKLE mode shapes from the",
    "REM  EXISTING .odb files (no solve). Run OUTSIDE WorkBuddy.",
    "REM  When you see ALL DONE, tell WOONZI and he takes over.",
    "REM ============================================================",
    "setlocal",
    f'set "ABAQUS={ABAQUS_BAT}"',
    'set "EXTRACT=F:\\AI FEA Modeling DataSets\\feagpt_repro\\odb_tools\\extract_buckle_odb.py"',
    'set "CHECK=F:\\AI FEA Modeling DataSets\\feagpt_repro\\check_p2_abq_modes_meta.py"',
    'set "PY=C:\\Users\\22207\\.workbuddy\\binaries\\python\\envs\\default\\Scripts\\python.exe"',
    'set "ROOT=F:\\AI FEA Modeling DataSets\\feagpt_repro\\_p2_abq_scaling"',
    "echo.",
    "echo === Checking Abaqus launcher ===",
    'if not exist "%ABAQUS%" ( echo [ERR] abaqus.bat not found & goto :fail )',
    'if not exist "%EXTRACT%" ( echo [ERR] extractor script not found & goto :fail )',
    'if not exist "%CHECK%" ( echo [ERR] checksum validator not found & goto :fail )',
    'if not exist "%PY%" ( echo [ERR] project venv python not found & goto :fail )',
    "echo OK",
    "echo.",
]

TAIL = [
    "echo.",
    "echo === ALL DONE - 3/3 mode-shape sets extracted ===",
    "echo Paste this window back to WOONZI (or just tell him it finished).",
    "pause",
    "exit /b 0",
    "",
    ":fail",
    "echo.",
    "echo [FAILED] see the [ERR] line above. Do NOT tell WOONZI it finished.",
    "pause",
    "exit /b 1",
]


def block(tag: str) -> list[str]:
    job = f"{_BASE}_{tag}_abq"
    d = f"%ROOT%\\{job}"
    odb = f"{d}\\{job}.odb"
    prefix = f"{d}\\{tag}_modes"
    meta = f"{prefix}.meta.json"
    return [
        f"echo === {tag} (P_ref from the 2026-11-08 scaling batch) ===",
        f'if not exist "{odb}" ( echo [ERR] missing {tag} .odb & goto :fail )',
        f'call "%ABAQUS%" python "%EXTRACT%" "{odb}" "{prefix}" 6',
        'if errorlevel 1 ( echo [ERR] abaqus python failed for ' + tag + ' & goto :fail )',
        f'if not exist "{meta}" (',
        f'  echo [ERR] no meta.json for {tag} -- extraction did not produce output',
        "  goto :fail",
        ")",
        f'call "%PY%" "%CHECK%" {tag}',
        "if errorlevel 1 (",
        f'  echo [ERR] {tag}: meta/binary checksum validation failed',
        "  goto :fail",
        ")",
        f'echo --- {tag} meta summary ---',
        f'type "{meta}" | findstr /c:"n_u_frames" /c:"n_nodes" /c:"u_bin_sha256"',
        "echo.",
    ]


def main() -> int:
    assert _SCRIPT.is_file(), f"missing {_SCRIPT}"
    assert (_HERE / "check_p2_abq_modes_meta.py").is_file(), "missing validator"
    checks = {}
    for tag in TAGS:
        job = f"{_BASE}_{tag}_abq"
        d = _JOBS / job
        odb = d / f"{job}.odb"
        inp = d / f"{job}.inp"
        assert odb.is_file(), f"missing {odb}"
        assert inp.is_file(), f"missing {inp}"
        txt = inp.read_text(encoding="utf-8", errors="replace")
        checks[tag] = {
            "odb_exists": True,
            "odb_bytes": odb.stat().st_size,
            "has_NODE_OUTPUT_U": "*NODE OUTPUT" in txt and "\nU\n" in txt,
            "has_OUTPUT_2D": "OUTPUT=2D" in txt,
            "has_NUMBER_INTERVAL": "NUMBER INTERVAL" in txt,
            "has_BUCKLE_LANCZOS": "*BUCKLE, EIGENSOLVER=LANCZOS" in txt,
            "has_6_modes": "6, 0.0, 1.0e6" in txt,
        }
        c = checks[tag]
        assert c["has_NODE_OUTPUT_U"], f"{tag}: deck has no *NODE OUTPUT U"
        assert not c["has_OUTPUT_2D"], f"{tag}: ccx-only OUTPUT=2D leaked"
        assert not c["has_NUMBER_INTERVAL"], f"{tag}: NUMBER INTERVAL in BUCKLE step"
        assert c["has_BUCKLE_LANCZOS"] and c["has_6_modes"]

    lines = HEAD[:]
    for tag in TAGS:
        lines.extend(block(tag))
    lines.extend(TAIL)
    bat = _JOBS / "run_p2_abq_modes_MANUAL.bat"
    # CRLF, ASCII-safe content
    bat.write_bytes(("\r\n".join(lines) + "\r\n").encode("ascii"))
    assert bat.read_bytes().count(b"call \"%ABAQUS%\" python") == 3
    print(f"wrote {bat}")
    for tag, c in checks.items():
        print(f"  {tag}: {json.dumps(c, ensure_ascii=False)}")
    print("3/3 pre-flight checks passed; NO solve will be run (existing .odb reused).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
