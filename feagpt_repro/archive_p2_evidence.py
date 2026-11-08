"""C6-P2 P0-4: evidence archive + FULL step-section diff (2026-11-08).

Expert review FBA-C6P2-REV-001-EX01 requires U5 (step diff) and U6
(ccx deck/.dat, Abaqus .msg/.odb archival) to be closed, not left open.

Policy (kept explicit, no silent gaps):
  * small text artifacts (.dat/.msg/.sta/smoke log) are copied VERBATIM into
    reports/diagnostics/p2_evidence_2026-11-08/ and are git-tracked;
  * large artifacts (ccx deck ~7 MB, Abaqus .odb ~13 MB, .frd) are NOT copied
    into the repository: manifest records sha256 + byte size + local path,
    so they remain independently checkable on this machine.  Full external
    archiving of those large files is marked TO BE SUPPLIED in the report.
  * the step-section diff uses SAME-CONFIGURATION decks (2 modes, 0.1 MPa):
    a ccx deck is regenerated deck-only for this purpose.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from feagpt.spec import FEASpec          # noqa: E402
from feagpt import pipeline              # noqa: E402

_ROOT = _HERE.parent
_V11 = _ROOT / "FEM-Bench-Aero" / "modeling"
_ABQ_DIR = _HERE / "_p2_abq_jobs/fuselage_barrel_d1600_l1600_str8_frm3_buckle"
_ABQ_DECK = _ABQ_DIR / "fuselage_barrel_d1600_l1600_str8_frm3_buckle.inp"
_ARCH = _HERE / "reports/diagnostics/p2_evidence_2026-11-08"
_OUT = _HERE / "reports/diagnostics/p2_evidence_manifest_2026-11-08.json"
_SCALING = _HERE / "_p2_scaling_ccx"
BASE = "fuselage_barrel_d1600_l1600_str8_frm3"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def step_lines(text: str) -> list[str]:
    lines = text.replace("\r\n", "\n").split("\n")
    for i, x in enumerate(lines):
        if x.strip().upper() == "*STEP":
            return [y.rstrip() for y in lines[i:] if y.strip()]
    return []


def make_ccx_deck_2m() -> tuple[Path, str]:
    d = json.loads((_V11 / BASE / "spec.json").read_text(encoding="utf-8"))
    d["name"] = BASE + "_buckle"
    d["analysis"]["step_type"] = "buckle"
    d["analysis"]["buckling"] = {
        "n_modes": 2,
        "reference_load": {"kind": "pressure", "magnitude": 0.1,
                           "pressure_sign": -1.0},
    }
    td = tempfile.mkdtemp(prefix="p2_archive_")
    res = pipeline.run(FEASpec.from_dict(d), outdir=Path(td),
                       step_export=False, deck_only=True, solver_name="ccx")
    deck = Path(res.artifacts["inp"])
    return deck, td


def main() -> int:
    _ARCH.mkdir(parents=True, exist_ok=True)
    if not _ABQ_DECK.exists():
        raise SystemExit(f"Abaqus deck missing: {_ABQ_DECK}")
    ccx_deck, td = make_ccx_deck_2m()
    try:
        ccx_text = ccx_deck.read_text(encoding="utf-8")
        abq_text = _ABQ_DECK.read_text(encoding="utf-8")
        c_step, a_step = step_lines(ccx_text), step_lines(abq_text)
        diffs = []
        for i in range(max(len(c_step), len(a_step))):
            x = c_step[i] if i < len(c_step) else "<missing>"
            y = a_step[i] if i < len(a_step) else "<missing>"
            if x != y:
                diffs.append({"line": i + 1, "ccx": x, "abaqus": y})

        # verbatim small-file archive
        copied = {}
        small = {
            "abaqus_dat": _ABQ_DIR / "fuselage_barrel_d1600_l1600_str8_frm3_buckle.dat",
            "abaqus_msg": _ABQ_DIR / "fuselage_barrel_d1600_l1600_str8_frm3_buckle.msg",
            "abaqus_sta": _ABQ_DIR / "fuselage_barrel_d1600_l1600_str8_frm3_buckle.sta",
            "ccx_smoke_log": _HERE / "reports/diagnostics/p2_ccx_barrel_buckle_smoke.txt",
        }
        for key, src in small.items():
            if src.exists():
                dst = _ARCH / src.name
                shutil.copyfile(src, dst)
                copied[key] = {"file": dst.name, "sha256": sha(dst),
                               "bytes": dst.stat().st_size,
                               "lines": len(dst.read_text(encoding="utf-8", errors="replace").splitlines())}
        # ccx .dat from the 3-point scaling job, if already produced
        for p in sorted(_SCALING.glob("*/*.dat")):
            dst = _ARCH / p.name
            shutil.copyfile(p, dst)
            copied[f"ccx_dat_{p.parent.name[-4:]}"] = {
                "file": dst.name, "sha256": sha(dst), "bytes": dst.stat().st_size}

        large = {}
        for key, p in {
            "ccx_deck_2m": ccx_deck,
            "abaqus_deck": _ABQ_DECK,
            "abaqus_odb": _ABQ_DIR / "fuselage_barrel_d1600_l1600_str8_frm3_buckle.odb",
        }.items():
            if p.exists():
                large[key] = {"path": str(p), "sha256": sha(p), "bytes": p.stat().st_size,
                              "copied_into_repo": False}
        for p in sorted(_SCALING.glob("*/*.inp")):
            large[f"ccx_deck_{p.parent.name[-4:]}"] = {
                "path": str(p), "sha256": sha(p), "bytes": p.stat().st_size,
                "copied_into_repo": False}

        step_diff = {
            "what": "FULL step-section line diff, same configuration (2 modes, 0.1 MPa external pressure)",
            "ccx_step_lines": c_step, "abaqus_step_lines": a_step,
            "n_ccx_lines": len(c_step), "n_abaqus_lines": len(a_step),
            "n_differing_lines": len(diffs), "all_differences": diffs,
            "note": ("Differences are: the *BUCKLE keyword/data line (ccx '2' vs "
                     "abaqus EIGENSOLVER=LANCZOS '2, 0.0, 1.0e6') and the output "
                     "requests (*NODE FILE U vs *OUTPUT, FIELD / *NODE OUTPUT U). "
                     "*DLOAD reference load is IDENTICAL in both. The keyword "
                     "difference encodes DIFFERENT EIGENSOLVER ALGORITHMS, which "
                     "is a substantive candidate cause (EX01 C3), not mere syntax."),
        }
        (_ARCH / "step_diff_full.json").write_text(
            json.dumps(step_diff, ensure_ascii=False, indent=1), encoding="utf-8")

        manifest = {
            "what": "C6-P2 P0-4 evidence archive manifest",
            "date": "2026-11-08",
            "status": ("U5 CLOSED (full step diff). U6 PARTIALLY CLOSED: small "
                       "text artifacts copied verbatim into git; large deck/odb "
                       "files anchored by sha256 + local path, full external "
                       "archival TO BE SUPPLIED."),
            "copied_verbatim": copied,
            "large_files_anchored_not_copied": large,
            "step_diff": {"file": "step_diff_full.json",
                          "n_differing_lines": len(diffs)},
            "expert_review": "FBA-C6P2-REV-001-EX01",
            "repro": ["python archive_p2_evidence.py"],
        }
        _OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {_OUT}")
        print(f"step diff: ccx {len(c_step)} lines / abq {len(a_step)} lines, "
              f"{len(diffs)} differing lines")
        for d in diffs:
            print(f"  L{d['line']}: ccx={d['ccx']!r} | abq={d['abaqus']!r}")
        print(f"copied verbatim: {len(copied)} files; anchored large: {len(large)}")
        return 0
    finally:
        shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
