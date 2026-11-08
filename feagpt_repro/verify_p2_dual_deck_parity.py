"""C6-P2 dual-code deck parity check (expert-review evidence, 2026-11-08).

Question: on the ONE case where a 37.87% lambda1 difference was measured,
are the two codes really solving the same structural model?  This script
generates the ccx deck from the SAME spec used for the external Abaqus job,
then compares everything BEFORE *STEP line by line (nodes, elements, sets,
sections, material, BC).  Step sections are dialect-specific by design and
are reported, not compared.

Output: reports/diagnostics/p2_dual_deck_parity_2026-11-08.json
Read-only against frozen volumes; the ccx deck lives in a temp dir.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from feagpt.spec import FEASpec          # noqa: E402
from feagpt import pipeline              # noqa: E402

_V11 = _HERE.parent / "FEM-Bench-Aero" / "modeling"
_ABQ = (_HERE / "_p2_abq_jobs/fuselage_barrel_d1600_l1600_str8_frm3_buckle"
        / "fuselage_barrel_d1600_l1600_str8_frm3_buckle.inp")
_OUT = _HERE / "reports/diagnostics/p2_dual_deck_parity_2026-11-08.json"
BASE = "fuselage_barrel_d1600_l1600_str8_frm3"


def split_deck(text: str) -> tuple[list[str], list[str]]:
    """(pre-step lines, step lines). Comparison is on pre-step only."""
    lines = text.replace("\r\n", "\n").split("\n")
    for i, line in enumerate(lines):
        if line.strip().upper() == "*STEP":
            return lines[:i], lines[i:]
    return lines, []


def key_lines(lines: list[str]) -> dict:
    """Scan the WHOLE deck: in a *BUCKLE step the reference load is written
    inside the step, so it would be invisible to a pre-step-only scan."""
    out = {}
    for key in ("*ELEMENT, TYPE", "*SHELL SECTION", "*MATERIAL", "*ELASTIC",
                "*DENSITY", "*BOUNDARY", "*DLOAD", "*CLOAD", "*NSET, NSET=NZ0",
                "*STEP", "*BUCKLE"):
        hits = [(i, x.strip()) for i, x in enumerate(lines)
                if x.strip().upper().startswith(key.upper())]
        out[key] = {
            "n": len(hits),
            "first": [h[1] for h in hits[:3]],
            "with_data_line": [
                {"keyword": h[1],
                 "next": lines[h[0] + 1].strip() if h[0] + 1 < len(lines) else None}
                for h in hits[:3]],
        }
    return out


def drop_heading_data(lines: list[str]) -> tuple[list[str], list[str]]:
    """Remove *HEADING data lines (case description + dialect label).

    Those are free-text title lines: the two decks necessarily say
    "CalculiX deck" vs "Abaqus deck".  They are not solver input.  The
    keyword line itself is kept so the block structure is unchanged.
    """
    out, removed, in_heading = [], [], False
    for x in lines:
        s = x.strip()
        if s.upper().startswith("*HEADING"):
            in_heading = True
            out.append(x)
            continue
        if in_heading:
            if s.startswith("*"):
                in_heading = False
                out.append(x)
            else:
                removed.append(x)
            continue
        out.append(x)
    return out, removed


def main() -> int:
    if not _ABQ.exists():
        raise SystemExit(f"Abaqus deck missing: {_ABQ} (regenerate with make_p2_abq_jobs.py)")
    d = json.loads((_V11 / BASE / "spec.json").read_text(encoding="utf-8"))
    d["name"] = BASE + "_buckle"
    d["analysis"]["step_type"] = "buckle"
    d["analysis"]["buckling"] = {
        "n_modes": 2,
        "reference_load": {"kind": "pressure", "magnitude": 0.1,
                           "pressure_sign": -1.0},
    }
    spec = FEASpec.from_dict(d)
    with tempfile.TemporaryDirectory(prefix="p2_parity_") as td:
        res = pipeline.run(spec, outdir=Path(td), step_export=False,
                           deck_only=True, solver_name="ccx")
        ccx_text = Path(res.artifacts["inp"]).read_text(encoding="utf-8")
    abq_text = _ABQ.read_text(encoding="utf-8")

    c_pre, c_step = split_deck(ccx_text)
    a_pre, a_step = split_deck(abq_text)
    # normalise only blank trailing lines; do NOT hide any content differences
    def trim(xs: list[str]) -> list[str]:
        while xs and not xs[-1].strip():
            xs.pop()
        return xs
    c_pre, a_pre = trim(c_pre), trim(a_pre)
    raw_same = c_pre == a_pre
    c_cmp, c_head = drop_heading_data(c_pre)
    a_cmp, a_head = drop_heading_data(a_pre)
    same = c_cmp == a_cmp
    # report EVERY differing line, not only the first one (a first-diff-only
    # check can silently hide later structural differences)
    all_diffs = []
    for i in range(max(len(c_cmp), len(a_cmp))):
        x = c_cmp[i] if i < len(c_cmp) else "<missing>"
        y = a_cmp[i] if i < len(a_cmp) else "<missing>"
        if x != y:
            all_diffs.append({"line": i + 1, "ccx": x, "abaqus": y})

    out = {
        "what": "C6-P2 dual-code deck parity (pre-*STEP structural model)",
        "date": "2026-11-08",
        "case": spec.name,
        "status": "diagnostic evidence for expert review",
        "pre_step_identical_raw": raw_same,
        "pre_step_identical_excluding_heading": same,
        "heading_data_lines_excluded": {"ccx": len(c_head), "abaqus": len(a_head),
                                        "ccx_text": c_head, "abaqus_text": a_head},
        "n_differing_lines": len(all_diffs),
        "all_differences": all_diffs[:20],
        "n_pre_step_lines": {"ccx": len(c_pre), "abaqus": len(a_pre),
                             "compared": len(c_cmp)},
        "ccx_key_lines": key_lines(c_pre + c_step),
        "abaqus_key_lines": key_lines(a_pre + a_step),
        "ccx_step_section": [x.rstrip() for x in c_step if x.strip()][:12],
        "abaqus_step_section": [x.rstrip() for x in a_step if x.strip()][:12],
        "note": (
            "Identical pre-step text (excluding *HEADING free text) means "
            "nodes/elements/sets/sections/material/BC are byte-identical "
            "between codes. Step sections differ BY DESIGN (ccx *BUCKLE n; "
            "abaqus *BUCKLE, EIGENSOLVER=LANCZOS n,min,max; output requests "
            "differ). Under this evidence a lambda difference cannot be blamed "
            "on deck translation of the structural model; solver formulation "
            "and eigensolver behaviour remain hypotheses until independently "
            "checked. This script does NOT compare the step data lines, so a "
            "reference-load/keyword mismatch inside the step is only checked "
            "via the *DLOAD key-line listing, not by a full step diff."),
        "repro": ["python verify_p2_dual_deck_parity.py"],
    }
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {_OUT}")
    print(f"pre-*STEP identical (raw): {raw_same}")
    print(f"pre-*STEP identical (excluding {len(c_head)} heading lines): {same}")
    print(f"differing lines: {len(all_diffs)}")
    print(f"lines: ccx={len(c_pre)} abq={len(a_pre)} compared={len(c_cmp)}")
    print("ccx *DLOAD:", out["ccx_key_lines"]["*DLOAD"]["first"])
    print("abq *DLOAD:", out["abaqus_key_lines"]["*DLOAD"]["first"])
    print("ccx *BOUNDARY:", out["ccx_key_lines"]["*BOUNDARY"]["first"])
    print("abq *BOUNDARY:", out["abaqus_key_lines"]["*BOUNDARY"]["first"])
    if all_diffs:
        print("first diff:", json.dumps(all_diffs[0], ensure_ascii=False)[:400])
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
