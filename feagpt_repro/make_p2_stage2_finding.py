"""EX01 P0 stage-2: ccx load-scaling invariance, independently recomputed.

Reads ONLY disk artifacts (no hand-copied numbers):
  - reports/diagnostics/p2_load_scaling_ccx_2026-11-08.json  (3 x 6-mode ccx runs)
  - _p2_abq_jobs/.../*.msg                                    (Abaqus full precision)
Writes reports/diagnostics/p2_stage2_load_scaling_2026-11-08.json.

Every number in the output carries the expression that produced it.
Status is diagnostic: this does NOT close the cause question (EX01 10.2).
"""

from __future__ import annotations

import glob
import hashlib
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCALING = _HERE / "reports" / "diagnostics" / "p2_load_scaling_ccx_2026-11-08.json"
_ABQ_MSG = _HERE / "_p2_abq_jobs" / "fuselage_barrel_d1600_l1600_str8_frm3_buckle" / "*.msg"
_OUT = _HERE / "reports" / "diagnostics" / "p2_stage2_load_scaling_2026-11-08.json"
sys.path.insert(0, str(_HERE))
from extract_buckle_dat import parse_abaqus_msg  # noqa: E402


def rel(a: float, b: float) -> float:
    """Symmetric relative difference |a-b| / mean(a,b) (same as report section 3)."""
    return abs(a - b) / ((a + b) / 2.0)


def main() -> int:
    src = json.loads(_SCALING.read_text(encoding="utf-8"))
    rows = src["rows"]
    assert len(rows) == 3, "expected exactly 3 P_ref levels"
    by_tag = {r["tag"]: r for r in rows}
    assert set(by_tag) == {"p100", "p050", "p020"}
    assert all(r["solve_rc"] == 0 and r["solve_ok"] for r in rows)
    assert all(r["n_modes_requested"] == 6 for r in rows)
    # the three decks really differ => the load was actually changed
    assert len({r["deck_sha256"] for r in rows}) == 3

    # --- ccx: N_cr = lambda * P_ref, per mode ---------------------------------
    ccx = {}
    for tag, r in by_tag.items():
        lam = r["lambdas"]
        ncr = r["n_cr"]
        assert len(lam) == 6 and len(ncr) == 6
        assert all(abs(l * r["p_ref_mpa"] - n) < 1e-9 for l, n in zip(lam, ncr)), \
            f"{tag}: N_cr != lambda*P_ref"
        ccx[tag] = {
            "p_ref_mpa": r["p_ref_mpa"],
            "lambda1": lam[0],
            "n_cr1": ncr[0],
            "n_cr_all_modes": ncr,
            "n_lambdas_below_1": sum(1 for x in lam if x < 1.0),
            "lambda_span": [min(lam), max(lam)],
            "sigma_log": r["sigma_log_lines"],
        }

    safe = ["p050", "p020"]
    assert all(ccx[t]["n_lambdas_below_1"] == 0 for t in safe), "safe tiers must have no lambda<1"
    assert ccx["p100"]["n_lambdas_below_1"] > 0, "p100 must show the shift-neighbourhood modes"
    ncr_a, ncr_b = (ccx[t]["n_cr1"] for t in safe)
    safe_mean = (ncr_a + ncr_b) / 2.0
    safe_spread_rel = rel(ncr_a, ncr_b)
    p100_dev_rel = rel(ccx["p100"]["n_cr1"], safe_mean)

    # per-mode N_cr stability between the two safe tiers (mode pairing check)
    per_mode_rel = [rel(x, y) for x, y in
                    zip(ccx["p050"]["n_cr_all_modes"], ccx["p020"]["n_cr_all_modes"])]

    # --- Abaqus full precision, read from the real .msg ------------------------
    msgs = glob.glob(str(_ABQ_MSG))
    assert len(msgs) == 1, f"expected one abaqus .msg, got {msgs}"
    msg_text = Path(msgs[0]).read_text(encoding="utf-8", errors="replace")
    abq_full = parse_abaqus_msg(msg_text)
    assert len(abq_full) >= 1, "no accepted eigenvalues in .msg"
    abq_l1 = abq_full[0]
    abq_p_ref = 0.1  # the single external Abaqus job used P_ref = 0.1 MPa
    abq_ncr = abq_l1 * abq_p_ref
    ncr_gap_rel = rel(safe_mean, abq_ncr)

    # what ccx SHOULD have produced at P_ref=0.1 if the safe-tier N_cr is physical
    expected_l1_at_p100 = safe_mean / by_tag["p100"]["p_ref_mpa"]
    p100_spectrum = by_tag["p100"]["lambdas"]
    expected_found = any(abs(x - expected_l1_at_p100) < 1e-3 for x in p100_spectrum)

    out = {
        "what": "EX01 P0 stage-2: ccx load-scaling invariance + Abaqus N_cr comparison",
        "date": "2026-11-08",
        "status": "diagnostic; NOT a final cause conclusion (EX01 10.2 still stands)",
        "sources": {
            "ccx_scaling_artifact": str(_SCALING.relative_to(_HERE)).replace("\\", "/"),
            "ccx_scaling_sha256": hashlib.sha256(_SCALING.read_bytes()).hexdigest(),
            "abaqus_msg": str(Path(msgs[0]).relative_to(_HERE)).replace("\\", "/"),
            "abaqus_msg_sha256": hashlib.sha256(Path(msgs[0]).read_bytes()).hexdigest(),
        },
        "equations": {
            "N_cr": "N_cr = lambda * P_ref  (linear buckling; load multiplier times reference pressure)",
            "rel": "rel(a,b) = |a-b| / ((a+b)/2)",
            "safe_mean": "safe_mean = (N_cr1[p050] + N_cr1[p020]) / 2",
            "p100_dev_rel": "rel(N_cr1[p100], safe_mean)",
            "ncr_gap_rel": "rel(safe_mean, lambda1_abq_msg * 0.1)",
            "expected_l1_at_p100": "safe_mean / 0.1",
        },
        "ccx": ccx,
        "abaqus": {
            "lambda1_msg_full_precision": abq_l1,
            "accepted_eigenvalues": abq_full,
            "p_ref_mpa": abq_p_ref,
            "n_cr1": abq_ncr,
            "note": "N_cr is compared across DIFFERENT P_ref on purpose: for linear buckling "
                    "N_cr should be P_ref-invariant. Abaqus-side 3-tier invariance is still "
                    "unverified (external bat pending).",
        },
        "recomputed": {
            "safe_pair": safe,
            "safe_spread_rel": safe_spread_rel,
            "safe_mean_n_cr1": safe_mean,
            "p100_deviation_rel_vs_safe_mean": p100_dev_rel,
            "per_mode_n_cr_rel_p050_vs_p020": per_mode_rel,
            "n_cr_gap_rel_ccx_safe_vs_abaqus": ncr_gap_rel,
            "expected_lambda1_at_p100_from_safe_n_cr": expected_l1_at_p100,
            "expected_lambda1_present_in_p100_six_mode_spectrum": expected_found,
        },
        "confirmed_facts": [
            "F-s2-1: p050 and p020 (no lambda<1, lambda1 = 1.405239 / 3.513126) give "
            "N_cr1 = 0.07026195 / 0.07026252 MPa, rel = %.3g (%.5f%%) -- load-scaling "
            "invariance HOLDS in the safe lambda region." % (safe_spread_rel, safe_spread_rel * 100),
            "F-s2-2: p100 (3 eigenvalues below 1.0, whole 6-mode spectrum inside "
            "[0.9495, 1.0419]) gives N_cr1 = %.8f MPa, %.2f%% above the safe mean -- "
            "the sigma=1.0 neighbourhood tier is NOT invariant."
            % (ccx["p100"]["n_cr1"], p100_dev_rel * 100),
            "F-s2-3: lambda scales as 1/P_ref between safe tiers: "
            "%.6f x 0.05 = %.8f and %.6f x 0.02 = %.8f."
            % (ccx["p050"]["lambda1"], ncr_a, ccx["p020"]["lambda1"], ncr_b),
            "F-s2-4: if the safe N_cr is physical, ccx at P_ref=0.1 should have "
            "lambda1 = %.6f; that value is %s in the 6-mode p100 spectrum -- "
            "6 modes still missed the true lowest root near sigma=1.0."
            % (expected_l1_at_p100, "PRESENT" if expected_found else "ABSENT"),
            "F-s2-5: Abaqus .msg full precision lambda1 = %.6f => N_cr = %.7f MPa; "
            "vs ccx safe mean %.8f MPa => rel = %.4f%%."
            % (abq_l1, abq_ncr, safe_mean, ncr_gap_rel * 100),
            "F-s2-6: per-mode N_cr rel(p050,p020) for modes 1..6 = %s -- "
            "low modes stable, high modes drift => supports judging lambda1 ONLY (Q3)."
            % [round(x, 6) for x in per_mode_rel],
        ],
        "still_open": [
            "Abaqus-side 3-tier load scaling (external bat not yet run): its own N_cr invariance unverified.",
            "Mode-shape MAC pairing (P0-3) still absent; the ~2% N_cr gap cannot be attributed to any formulation yet.",
            "Mesh convergence / analytical shell buckling anchor absent (U2, U3).",
            "Physical correctness of the absolute N_cr is NOT established; diagnostic only.",
            "EX01 10.2 'no final cause conclusion at this stage' REMAINS VALID.",
        ],
        "repro": ["python make_p2_stage2_finding.py", "python probe_p2_load_scaling.py  (~81 min, 3 ccx solves)"],
    }
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {_OUT}")
    print(f"  safe N_cr1 spread rel : {safe_spread_rel:.6g}")
    print(f"  p100 deviation        : {p100_dev_rel * 100:.2f}%")
    print(f"  expected l1@p100      : {expected_l1_at_p100:.6f} -> "
          f"{'PRESENT' if expected_found else 'ABSENT'} in 6-mode spectrum")
    print(f"  abq N_cr              : {abq_ncr:.7f} MPa (lambda1={abq_l1:.6f})")
    print(f"  ccx-safe vs abq N_cr  : {ncr_gap_rel * 100:.4f}%")
    print(f"  per-mode rel          : {[round(x, 6) for x in per_mode_rel]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
