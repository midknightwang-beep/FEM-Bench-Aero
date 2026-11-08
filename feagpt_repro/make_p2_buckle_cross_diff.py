"""C6-P2 first dual-code buckling cross-diff (diagnostic, 2026-11-08).

ONE case, ONE reference load, two codes.  This is NOT a threshold input:
the design decision Q3 says only lambda1 is judged and both codes must use
the same P_ref; this measurement shows how far apart the two codes are on
the same deck semantics, which decides whether a cross-code threshold can
ever be meaningful.

Sources (both git-tracked artifacts / real-machine outputs):
  ccx    : reports/diagnostics/p2_ccx_barrel_buckle_smoke.txt (verbatim .dat tail)
  abaqus : _p2_abq_jobs/.../<case>.dat (external job, user-run outside WorkBuddy)
The raw table excerpts are embedded in the output JSON so the numbers stay
recomputable after the (gitignored) job directory is gone.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from extract_buckle_dat import parse_ccx_text, parse_abaqus_text  # noqa: E402

_CCX_LOG = _HERE / "reports/diagnostics/p2_ccx_barrel_buckle_smoke.txt"
_ABQ_DAT = (_HERE / "_p2_abq_jobs/fuselage_barrel_d1600_l1600_str8_frm3_buckle"
            / "fuselage_barrel_d1600_l1600_str8_frm3_buckle.dat")
_OUT = _HERE / "reports/diagnostics/p2_buckle_cross_diff_v2_2026-11-08.json"


def main() -> int:
    ccx_log = _CCX_LOG.read_text(encoding="utf-8")
    ccx_excerpt = ccx_log.split("--- .dat tail ---", 1)[1]
    ccx = parse_ccx_text(ccx_excerpt)

    abq_text = _ABQ_DAT.read_text(encoding="utf-8", errors="replace")
    abq = parse_abaqus_text(abq_text)
    # verbatim table excerpt for offline recomputation
    start = abq_text.find("E I G E N V A L U E")
    end = abq_text.find("THE ANALYSIS HAS BEEN COMPLETED", start)
    abq_excerpt = abq_text[start:end if end > start else None].rstrip()

    lam_c = [m["lambda"] for m in ccx]
    lam_a = [m["lambda"] for m in abq]
    n = min(len(lam_c), len(lam_a))
    rows = []
    for i in range(n):
        c, a = lam_c[i], lam_a[i]
        rel = abs(c - a) / ((c + a) / 2)
        rows.append({"mode": i + 1, "lambda_ccx": c, "lambda_abaqus": a,
                     "rel_diff": round(rel, 6)})

    out = {
        "what": "C6-P2 v2 first dual-code buckling cross-diff (1 case, diagnostic)",
        "date": "2026-11-08",
        "status": "diagnostic; NOT a threshold input; NOT truth",
        "case": "fuselage_barrel_d1600_l1600_str8_frm3_buckle",
        "reference_load": {"kind": "pressure", "magnitude": 0.1,
                           "pressure_sign": -1.0,
                           "note": "external pressure, same P_ref on both codes"},
        "ccx": {"dialect": "ccx", "lambdas": lam_c,
                "source": "reports/diagnostics/p2_ccx_barrel_buckle_smoke.txt",
                "solve": "rc=0, 656 s, 2 modes"},
        "abaqus": {"dialect": "abaqus", "lambdas": lam_a,
                   "source": "external job .dat (user-run bat, 2026-11-08 09:31)",
                   "sta": "THE ANALYSIS HAS COMPLETED SUCCESSFULLY",
                   "solve": "0 errors, 1 warning (more eigenvalues in range than requested), 125 s"},
        "rows": rows,
        "lambda1_rel_diff": rows[0]["rel_diff"],
        "findings": [
            "Cross-code lambda1 relative difference is ~38%, far beyond the P1 modal f1 threshold of 1%.",
            "Abaqus returns a repeated root (two identical lambdas) for the axisymmetric barrel; ccx splits it slightly. Repeated eigenvalues are physical, so the spectrum check must be non-decreasing, not strictly monotonic.",
            "A cross-code lambda threshold near 1% is impossible on this formulation difference. The P1 same-code self-comparison (candidate and reference solved by the SAME code) is the natural way to cancel it -- requires a decision before the 6-case pilot.",
            "One case is not a distribution. The Q3 threshold stays 'measure first, fix later' until the 6-case pilot produces the lambda spread.",
        ],
        "raw_excerpts": {"ccx_dat_tail": ccx_excerpt.strip(),
                         "abaqus_dat_table": abq_excerpt},
        "repro": [
            "python extract_buckle_dat.py --self-test   # 12/12 pins",
            "python make_p2_buckle_cross_diff.py        # this artifact",
        ],
    }
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {_OUT}")
    for r in rows:
        print(f"  mode {r['mode']}: ccx={r['lambda_ccx']:.6g}  abq={r['lambda_abaqus']:.6g}"
              f"  rel={r['rel_diff']:.2%}")
    print(f"  lambda1 rel diff = {rows[0]['rel_diff']:.2%} (diagnostic, not a threshold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
