"""Archive the three Abaqus scaling jobs' small text evidence verbatim.

Big files (.inp ~7 MB, .odb ~23 MB) are anchored by sha256 only; small
text files (.sta / .dat table / .msg accepted-eigenvalues block) are copied
verbatim so the numbers can be recomputed on another machine.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_JOBS = _HERE / "_p2_abq_scaling"
_OUTDIR = _HERE / "reports" / "diagnostics" / "p2_abq_scaling_evidence_2026-11-08"
_OUT = _HERE / "reports" / "diagnostics" / "p2_abq_scaling_evidence_manifest_2026-11-08.json"
TAGS = ("p100", "p050", "p020")
BASE = "fuselage_barrel_d1600_l1600_str8_frm3_buckle"

_OUTDIR.mkdir(parents=True, exist_ok=True)
manifest = {
    "what": "EX01 P0-1 Abaqus 3-tier scaling: verbatim small-text evidence + big-file sha256",
    "date": "2026-11-08",
    "source_root": "_p2_abq_scaling/ (user ran run_p2_abq_scaling_MANUAL.bat outside WorkBuddy)",
    "jobs": {},
}
for tag in TAGS:
    d = _JOBS / f"{BASE}_{tag}_abq"
    job = {"dir": str(d.relative_to(_HERE)).replace("\\", "/"), "files": {}}
    for suffix in ("sta", "dat", "msg", "inp", "odb"):
        p = next(d.glob(f"*.{suffix}"))
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        rec = {"path": p.name, "bytes": p.stat().st_size, "sha256": h, "archived": False}
        if suffix in ("sta", "dat", "msg"):
            dst = _OUTDIR / f"{tag}.{suffix}"
            shutil.copyfile(p, dst)
            rec["archived"] = True
            rec["archive_path"] = str(dst.relative_to(_HERE)).replace("\\", "/")
            assert hashlib.sha256(dst.read_bytes()).hexdigest() == h
        job["files"][suffix] = rec
    # quick semantic assertions on the archived text
    sta = (_OUTDIR / f"{tag}.sta").read_text(encoding="utf-8", errors="replace")
    dat = (_OUTDIR / f"{tag}.dat").read_text(encoding="utf-8", errors="replace")
    msg = (_OUTDIR / f"{tag}.msg").read_text(encoding="utf-8", errors="replace")
    assert "THE ANALYSIS HAS COMPLETED SUCCESSFULLY" in sta
    assert "MODE NO      EIGENVALUE" in dat
    assert "ACCEPTED EIGENVALUES" in msg
    job["checks"] = {"sta_completed": True, "dat_has_table": True, "msg_has_accepted": True}
    manifest["jobs"][tag] = job
    print(f"  {tag}: sta/dat/msg archived verbatim; inp/odb anchored by sha256")

# cross-check against the recomputation artifact
rec = json.loads((_HERE / "reports" / "diagnostics" /
                  "p2_abq_scaling_2026-11-08.json").read_text(encoding="utf-8"))
for tag in TAGS:
    for suffix in ("msg", "dat", "sta", "inp"):
        assert manifest["jobs"][tag]["files"][suffix]["sha256"] == \
               rec["abaqus"][tag]["sha256"][suffix], f"{tag}.{suffix} sha mismatch"
manifest["cross_check"] = "all 12 sha256 values match p2_abq_scaling_2026-11-08.json"
_OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {_OUT}")
print("  12/12 sha256 cross-check OK (U13 evidence chain closed)")
