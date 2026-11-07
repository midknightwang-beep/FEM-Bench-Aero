"""Generate truth.json for the 8 modeling_v2 modal pilot cases.

Every number is READ from on-disk artifacts at run time (R-A3: no
hand-copied values):

  * topology    <- v1.1 base-case ``truth.json`` (identical geometry,
                   the modal case only changes the analysis step)
  * spec_sha256 <- sha256 of the frozen v2 ``spec.json``
  * f_hz_ccx    <- ``modeling_v2/verify_v2_p1_ccx.json`` (solve summary)
  * f_hz_abq    <- parsed from ``<case>_abq.dat`` via extract_modal_dat
  * n_nodes     <- ``*NODE`` block line count in the frozen ccx deck
                   (the deck IS the mesh that was solved)

Self-checks before any file is written: 10 modes, positive, strictly
monotonic, f1 cross-code relative difference < 1% (the decided gate).

Usage::

    python make_v2_truth.py            # write 8 truth.json files
    python make_v2_truth.py --check    # verify existing files instead
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from extract_modal_dat import extract  # noqa: E402
from make_v2_modal_cases import CASES, _V2  # noqa: E402

_ROOT = _HERE.parent
_V11 = _ROOT / "FEM-Bench-Aero" / "modeling"
_SUMMARY_CCX = _V2 / "verify_v2_p1_ccx.json"
N_MODES = 10
F1_THRESHOLD_REL = 0.01


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _n_nodes_from_deck(deck: Path) -> int:
    """Count node-definition lines in the ``*NODE`` keyword block."""
    in_block = False
    n = 0
    for ln in deck.read_text(encoding="utf-8", errors="replace").splitlines():
        s = ln.strip()
        if s.upper().startswith("*"):
            in_block = s.upper().startswith("*NODE")
            continue
        if in_block and s and not s.startswith("**"):
            n += 1
    return n


def _spectrum_checks(name: str, f_ccx: list, f_abq: list) -> None:
    for tag, f in (("ccx", f_ccx), ("abq", f_abq)):
        if len(f) != N_MODES:
            raise SystemExit(f"{name}/{tag}: expected {N_MODES} modes, got {len(f)}")
        if any(x <= 0 for x in f):
            raise SystemExit(f"{name}/{tag}: non-positive frequency {f}")
        if any(b <= a for a, b in zip(f, f[1:])):
            raise SystemExit(f"{name}/{tag}: not strictly monotonic {f}")
    rel = abs(f_ccx[0] - f_abq[0]) / ((f_ccx[0] + f_abq[0]) / 2)
    if rel >= F1_THRESHOLD_REL:
        raise SystemExit(f"{name}: f1 cross-code diff {rel:.4%} >= "
                         f"{F1_THRESHOLD_REL:.0%} -- reference is not self-consistent")


def build_one(ccx_summary_rows: dict) -> dict:
    out = {}
    for base in CASES:
        name = f"{base}_modal"
        v2dir = _V2 / name
        spec = v2dir / f"{name}.spec.json"
        deck = v2dir / f"{name}.inp"
        abq_dat = v2dir / f"{name}_abq.dat"
        for p in (spec, deck, abq_dat):
            if not p.exists():
                raise SystemExit(f"missing artifact: {p}")

        f_ccx = ccx_summary_rows[name]["f_hz"]
        f_abq = [m["f_hz"] for m in extract(str(abq_dat), "abaqus",
                                            expect=N_MODES)["modes"]]
        _spectrum_checks(name, f_ccx, f_abq)

        base_truth = _V11 / base / "truth.json"
        if not base_truth.exists():
            raise SystemExit(f"v1.1 base truth missing: {base_truth}")
        bt = json.loads(base_truth.read_text(encoding="utf-8"))

        out[name] = {
            "schema_version": 1,
            "case_id": name,
            "structure_family": bt.get("structure_family", "wingbox"),
            "spec_sha256": _sha256(spec),
            "topology": bt["topology"],
            "scalars": {
                "n_nodes": _n_nodes_from_deck(deck),
                "n_modes": N_MODES,
                "f_hz_ccx": f_ccx,
                "f_hz_abq": f_abq,
                "f1_gate": {
                    "judged": "f1 (fundamental frequency)",
                    "threshold_rel": F1_THRESHOLD_REL,
                    "note": ("decided 2026-11-07 option A; candidate judging "
                             "uses same-code self-comparison (ccx vs ccx); "
                             "modes 2+ recorded, not judged (S4 formulation "
                             "divergence, hypothesis unverified)"),
                },
                "solver_meta": {
                    "ccx": "ARPACK, n_modes=10, freq range [0, 1e6]",
                    "abaqus": "LANCZOS, n_modes=10, freq range [0, 1e5]",
                    "cross_diff_artifact": "modeling_v2/verify_v2_p1.json",
                },
            },
        }
    return out


def main(argv=None) -> int:
    check_only = argv is not None and "--check" in argv
    summary = json.loads(_SUMMARY_CCX.read_text(encoding="utf-8"))
    rows = {r["case"]: r for r in summary["rows"]}
    if summary.get("n_ok") != len(CASES):
        raise SystemExit(f"ccx summary not fully ok: {summary.get('n_ok')}")
    truth = build_one(rows)

    if check_only:
        bad = 0
        for name, want in truth.items():
            p = _V2 / name / "truth.json"
            got = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
            ok = got == want
            bad += 0 if ok else 1
            print(f"[{'ok ' if ok else 'BAD'}] {name}")
        print(f"truth check: {len(truth) - bad}/{len(truth)} match")
        return 1 if bad else 0

    for name, t in truth.items():
        p = _V2 / name / "truth.json"
        p.write_text(json.dumps(t, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
        print(f"[truth] {name}: n_nodes={t['scalars']['n_nodes']} "
              f"f1_ccx={t['scalars']['f_hz_ccx'][0]:.4f} "
              f"f1_abq={t['scalars']['f_hz_abq'][0]:.4f}")
    print(f"wrote {len(truth)} truth.json files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
