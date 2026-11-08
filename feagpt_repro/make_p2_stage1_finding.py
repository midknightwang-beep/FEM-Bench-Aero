"""EX01 P0 stage-1 finding: 6-mode ccx run exposes modes missed at 2 modes.

Reads the archived p100 .dat verbatim and E1/E3 artifacts, recomputes the
relative differences independently, and writes a stage-1 diagnostic artifact.
No final cause conclusion: the remaining ~32% gap still needs mode-shape
pairing and formulation isolation (P0-3 / P1).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from extract_buckle_dat import extract                     # noqa: E402
from extract_buckle_dat import parse_abaqus_msg              # noqa: E402

_DAT = (_HERE / "reports/diagnostics/p2_scaling_ccx"
        / "fuselage_barrel_d1600_l1600_str8_frm3_buckle_p100.dat")
_E1 = _HERE / "reports/diagnostics/p2_buckle_cross_diff_v2_2026-11-08.json"
_ABQ_MSG = (_HERE / "_p2_abq_jobs/fuselage_barrel_d1600_l1600_str8_frm3_buckle"
            / "fuselage_barrel_d1600_l1600_str8_frm3_buckle.msg")
_OUT = _HERE / "reports/diagnostics/p2_stage1_six_modes_2026-11-08.json"


def rel(a: float, b: float) -> float:
    return abs(a - b) / ((a + b) / 2)


def main() -> int:
    six = extract(str(_DAT), "ccx", expect=6)["lambdas"]
    e1 = json.loads(_E1.read_text(encoding="utf-8"))
    two = e1["ccx"]["lambdas"]
    abq_dat = e1["abaqus"]["lambdas"]
    abq_full = (parse_abaqus_msg(_ABQ_MSG.read_text(encoding="utf-8", errors="replace"))
                if _ABQ_MSG.exists() else [])

    # where did the old "lambda1/lambda2" go in the 6-mode spectrum?
    mapping = []
    for old in two:
        hits = [i + 1 for i, v in enumerate(six) if abs(v - old) < 1e-9]
        mapping.append({"old_value": old, "six_mode_index": hits})

    new_l1 = six[0]
    abq_l1 = abq_full[0] if abq_full else abq_dat[0]
    out = {
        "what": "EX01 P0 stage-1: ccx 6-mode buckling on the SAME 0.1 MPa case",
        "date": "2026-11-08",
        "status": "stage-1 diagnostic; p050/p020 scaling still running; NOT final",
        "source_dat": str(_DAT.relative_to(_HERE)),
        "p_ref_mpa": 0.1, "n_modes_requested": 6,
        "six_lambdas": six,
        "n_cr_mpa": [round(v * 0.1, 8) for v in six],
        "previous_two_mode_lambdas": two,
        "previous_two_mode_are_these_indices": mapping,
        "n_lambdas_below_1": sum(1 for v in six if 0 < v < 1.0),
        "sigma_log": "sigma=1.000000,d[0]=0.949500 (fixed shift, d[0] now the true lowest root)",
        "abaqus_lambda1_full_precision": abq_l1,
        "abaqus_lambda1_dat_rounded": abq_dat[0],
        "rel_diff_old_pair": round(rel(two[0], abq_dat[0]), 6),
        "rel_diff_new_l1_vs_abaqus_l1": round(rel(new_l1, abq_l1), 6),
        "findings": [
            "The 2-mode request MISSED three eigenvalues below 1.0 (0.9495 / 0.9582 / 0.9592).",
            "The values previously reported as lambda1/lambda2 (1.008207 / 1.009420) are modes 4 and 5 of the 6-mode spectrum.",
            "Therefore the 37.87% figure was NOT a same-mode difference: it compared a shifted higher mode pair with the Abaqus fundamental pair. EX01 C3 is confirmed for this case.",
            "A residual ~32% gap remains between the new ccx lambda1 (0.9495) and Abaqus lambda1 (0.687155); its cause is still unassigned and REQUIRES mode-shape pairing (MAC) before any formula attribution.",
            "Load-scaling invariance (p050 / p020) is still running; N_cr stability is not yet established.",
        ],
        "repro": [
            "python extract_buckle_dat.py reports/diagnostics/p2_scaling_ccx/fuselage_barrel_d1600_l1600_str8_frm3_buckle_p100.dat --dialect ccx --expect 6",
            "python make_p2_stage1_finding.py",
        ],
    }
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {_OUT}")
    print(f"6 lambdas: {six}")
    print(f"below 1.0: {out['n_lambdas_below_1']}; old pair -> indices {mapping}")
    print(f"old rel={out['rel_diff_old_pair']:.4%}  new lambda1 rel vs abq full={out['rel_diff_new_l1_vs_abaqus_l1']:.4%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
