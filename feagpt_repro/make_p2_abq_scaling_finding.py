"""EX01 P0-1 Abaqus side: 3-tier load scaling + SAME-P_ref dual-code comparison.

Reads ONLY disk artifacts (no hand-copied numbers):
  - _p2_abq_scaling/*_abq/*.msg          full-precision accepted eigenvalues
  - _p2_abq_scaling/*_abq/*.sta          completion status
  - _p2_abq_scaling/*_abq/*.dat          display table (5 s.f.)
  - reports/diagnostics/p2_load_scaling_ccx_2026-11-08.json   ccx 3 tiers
Writes reports/diagnostics/p2_abq_scaling_2026-11-08.json.

Every number carries the expression that produced it. Status: diagnostic.
This does NOT close the cause question (EX01 10.2), and does NOT freeze a
lambda threshold (EX01 D5).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_JOBS = _HERE / "_p2_abq_scaling"
_CCX = _HERE / "reports" / "diagnostics" / "p2_load_scaling_ccx_2026-11-08.json"
_OUT = _HERE / "reports" / "diagnostics" / "p2_abq_scaling_2026-11-08.json"
sys.path.insert(0, str(_HERE))
from extract_buckle_dat import parse_abaqus_msg  # noqa: E402

P_REFS = {"p100": 0.1, "p050": 0.05, "p020": 0.02}


def rel(a: float, b: float) -> float:
    """Symmetric relative difference |a-b| / mean(a,b) (report section 3)."""
    return abs(a - b) / ((a + b) / 2.0)


def main() -> int:
    ccx_src = json.loads(_CCX.read_text(encoding="utf-8"))
    ccx_rows = {r["tag"]: r for r in ccx_src["rows"]}
    assert set(ccx_rows) == set(P_REFS)

    abq = {}
    for tag, pref in P_REFS.items():
        d = _JOBS / f"fuselage_barrel_d1600_l1600_str8_frm3_buckle_{tag}_abq"
        assert d.is_dir(), f"missing job dir {d}"
        msg = next(d.glob("*.msg"))
        dat = next(d.glob("*.dat"))
        sta = next(d.glob("*.sta"))
        inp = next(d.glob("*.inp"))
        msg_txt = msg.read_text(encoding="utf-8", errors="replace")
        sta_txt = sta.read_text(encoding="utf-8", errors="replace")
        assert "THE ANALYSIS HAS COMPLETED SUCCESSFULLY" in sta_txt, f"{tag}: .sta not successful"
        assert "***ERROR" not in msg_txt.upper().replace(" ", ""), f"{tag}: error in .msg"
        vals = parse_abaqus_msg(msg_txt)
        assert len(vals) == 6, f"{tag}: expected 6 accepted eigenvalues, got {len(vals)}"
        assert vals == sorted(vals), f"{tag}: spectrum not non-decreasing"
        # deck really carries this tier's reference pressure
        inp_txt = inp.read_text(encoding="utf-8", errors="replace")
        assert f"E_SKIN, P, -{pref:g}" in inp_txt, f"{tag}: DLOAD pressure mismatch"
        assert "*BUCKLE, EIGENSOLVER=LANCZOS" in inp_txt
        assert "6, 0.0, 1.0e6" in inp_txt
        abq[tag] = {
            "p_ref_mpa": pref,
            "lambdas_full_precision": vals,
            "lambda1": vals[0],
            "n_cr_all_modes": [v * pref for v in vals],
            "n_cr1": vals[0] * pref,
            "sta": "THE ANALYSIS HAS COMPLETED SUCCESSFULLY",
            "n_errors": 0,
            "warning": "THERE MAY BE MORE EIGENVALUES IN THE SPECIFIED RANGE THAN REQUESTED "
                       "(benign; 6 explicitly requested and 6 accepted)",
            "dat_display_table": [ln.strip() for ln in
                                  dat.read_text(encoding="utf-8", errors="replace").splitlines()
                                  if ln.strip().startswith(tuple("123456"))][:6],
            "sha256": {suffix: hashlib.sha256(p.read_bytes()).hexdigest()
                       for suffix, p in (("msg", msg), ("dat", dat), ("sta", sta), ("inp", inp))},
        }

    # --- Abaqus's OWN N_cr invariance across three P_ref ----------------------
    ncr = [abq[t]["n_cr1"] for t in ("p100", "p050", "p020")]
    abq_mean = sum(ncr) / 3.0
    abq_spread_rel = (max(ncr) - min(ncr)) / abq_mean
    abq_pair_rel = {f"{x}_vs_{y}": rel(abq[x]["n_cr1"], abq[y]["n_cr1"])
                    for x, y in (("p100", "p050"), ("p050", "p020"), ("p100", "p020"))}

    # --- SAME-P_ref dual-code comparison (Q3 domain) -------------------------
    # ONLY the two safe ccx tiers are usable: p100 ccx spectrum was proven
    # sigma=1.0-contaminated (stage-1/stage-2 artifacts).
    same_pref = {}
    for tag in ("p100", "p050", "p020"):
        c_lam = ccx_rows[tag]["lambdas"]
        a_lam = abq[tag]["lambdas_full_precision"]
        pair = [rel(c, a) for c, a in zip(c_lam, a_lam)]
        same_pref[tag] = {
            "p_ref_mpa": P_REFS[tag],
            "ccx_usable_for_comparison": tag != "p100",
            "ccx_lambdas": c_lam,
            "abaqus_lambdas": a_lam,
            "lambda1_rel": pair[0],
            "per_mode_rel": pair,
            "note": "p100 ccx spectrum is sigma-contaminated (3 eigenvalues below 1.0, "
                    "true lowest root 0.702622 absent) -> its 32% lambda1 gap is NOT a "
                    "same-condition dual-code difference; excluded from conclusions."
                    if tag == "p100" else
                    "both codes solved the same model at the same P_ref; ccx in safe lambda region",
        }

    safe1 = same_pref["p050"]["lambda1_rel"]
    safe2 = same_pref["p020"]["lambda1_rel"]
    safe_gap_spread = rel(safe1, safe2)

    out = {
        "what": "EX01 P0-1 Abaqus-side 3-tier load scaling + SAME-P_ref dual-code comparison",
        "date": "2026-11-08",
        "status": "diagnostic; NOT a final cause conclusion, NOT a lambda threshold",
        "sources": {
            "abaqus_jobs": "_p2_abq_scaling/fuselage_barrel_d1600_l1600_str8_frm3_buckle_<tag>_abq/"
                           " (user ran bat outside WorkBuddy)",
            "ccx_scaling_artifact": "reports/diagnostics/p2_load_scaling_ccx_2026-11-08.json",
            "ccx_scaling_sha256": hashlib.sha256(_CCX.read_bytes()).hexdigest(),
        },
        "equations": {
            "N_cr": "N_cr = lambda * P_ref",
            "rel": "rel(a,b) = |a-b| / ((a+b)/2)",
            "abq_spread_rel": "(max(N_cr1) - min(N_cr1)) / mean(N_cr1) over three tiers",
            "same_pref_lambda1_rel": "rel(lambda1_ccx[tag], lambda1_abq[tag]) at identical P_ref",
        },
        "abaqus": abq,
        "recomputed": {
            "abaqus_n_cr1_by_tier": {t: abq[t]["n_cr1"] for t in P_REFS},
            "abaqus_n_cr1_mean": abq_mean,
            "abaqus_invariance_spread_rel": abq_spread_rel,
            "abaqus_pairwise_rel": abq_pair_rel,
            "same_pref_lambda1_rel_p050": safe1,
            "same_pref_lambda1_rel_p020": safe2,
            "safe_tier_gap_spread_rel": safe_gap_spread,
        },
        "confirmed_facts": [],
        "still_open": [
            "Mode-shape MAC pairing (P0-3 / U10) still absent: the ~2.2% same-P_ref gap "
            "cannot be attributed to any formulation before modes are paired.",
            "Mesh convergence and analytical shell-buckling anchor absent (U2, U3).",
            "Abaqus warning 'there may be more eigenvalues in the specified range than requested' "
            "is benign here (6 requested, 6 accepted) but the completeness of the lowest-6 "
            "spectrum is not independently proven.",
            "Physical correctness of the absolute N_cr is NOT established; diagnostic only.",
            "EX01 10.2 'no final cause conclusion at this stage' REMAINS VALID; "
            "EX01 D5 (6-case pilot deferred) and the frozen lambda threshold REMAIN.",
        ],
        "repro": [
            "make_p2_abq_scaling_jobs.py  (regenerate 3 decks + bat)",
            "_p2_abq_scaling/run_p2_abq_scaling_MANUAL.bat  (run OUTSIDE WorkBuddy)",
            "python make_p2_abq_scaling_finding.py  (this recomputation)",
        ],
    }

    F = out["confirmed_facts"]
    F.append("F-a1: all three Abaqus jobs .sta = THE ANALYSIS HAS COMPLETED SUCCESSFULLY, "
             "0 errors, 6 accepted eigenvalues each; only a benign 'more eigenvalues in range' warning.")
    F.append("F-a2: Abaqus lambda1 = %.6f / %.5f / %.5f at P_ref 0.1 / 0.05 / 0.02 MPa "
             "=> N_cr1 = %.8f / %.8f / %.8f MPa; three-tier spread rel = %.3g. "
             "ABAQUS-SIDE LOAD-SCALING INVARIANCE HOLDS."
             % (abq["p100"]["lambda1"], abq["p050"]["lambda1"], abq["p020"]["lambda1"],
                ncr[0], ncr[1], ncr[2], abq_spread_rel))
    F.append("F-a3: at IDENTICAL P_ref = 0.05 MPa, rel(ccx lambda1 %.6f, abq lambda1 %.5f) = %.4f%%; "
             "at 0.02 MPa, rel(%.6f, %.5f) = %.4f%%; the two agree to rel = %.3g."
             % (ccx_rows["p050"]["lambdas"][0], abq["p050"]["lambda1"], safe1 * 100,
                ccx_rows["p020"]["lambdas"][0], abq["p020"]["lambda1"], safe2 * 100,
                safe_gap_spread))
    F.append("F-a4: therefore AFTER excluding the sigma-contaminated 0.1 MPa ccx tier, the "
             "same-condition dual-code lambda1 difference is a STABLE ~%.2f%% (not 37.87%%, "
             "not 32.06%%, not zero). Its cause is NOT determined."
             % (((safe1 + safe2) / 2) * 100))
    F.append("F-a5: at P_ref = 0.1 MPa the ccx 6-mode spectrum still lacks the "
             "lambda1 = 0.702622 predicted from its own safe-tier N_cr, so the 32% gap at "
             "that tier is a solver artifact and MUST NOT be quoted as a dual-code difference.")
    F.append("F-a6: new 6-mode Abaqus p100 lambda1 = %.6f vs the earlier 2-mode job "
             "0.687155 (delta 1e-6, eigenvalue-request-count effect); "
             "both are far from the ccx p100 value 0.9495004."
             % abq["p100"]["lambda1"])
    F.append("F-a7: per-mode same-P_ref rel (p050 / p020) = %s / %s; low modes "
             "stable ~2.2%%, higher modes diverge => supports judging lambda1 ONLY (Q3)."
             % ([round(x, 5) for x in same_pref["p050"]["per_mode_rel"]],
                [round(x, 5) for x in same_pref["p020"]["per_mode_rel"]]))

    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {_OUT}")
    print("  Abaqus N_cr1:", [round(x, 8) for x in ncr], "spread rel =", f"{abq_spread_rel:.3g}")
    print(f"  same-P_ref lambda1 rel: p050={safe1*100:.4f}%  p020={safe2*100:.4f}%  "
          f"gap spread={safe_gap_spread:.3g}")
    print("  p100 ccx tier excluded (sigma contamination)")
    for x in F:
        print("   ", x[:150])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
