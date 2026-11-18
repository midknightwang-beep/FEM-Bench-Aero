"""Read the Abaqus ODB-derived JSON for the C5 barrel and gate STRUCTURE,
report cross-solver numbers as DIAGNOSTIC only.

Discipline (project memory, "跨求解器差异只记 diagnostic 不进 headline"):
-------------------------------------------------------------------------
The ccx gold (max_disp 2.8016 mm, max_vM 286.80 MPa) was produced by the SAME
solver as the candidate pipeline.  Abaqus is a DIFFERENT code.  A displacement
difference between them is a cross-solver diagnostic -- it is NOT a C5 pass/fail
criterion and never enters a headline number.  So this gate is deliberately
split:

  GATE (hard, rc=1 on fail):
    - .odb.json exists and parses;
    - node count == 143402 (same mesh as gold -- a mismatch means the wrong
      deck/odb, not a "solver difference");
    - DISP / STRESS_PEAK blocks present and non-empty;
    - all three numbers finite (no NaN/inf sneaking through).

  DIAGNOSTIC (printed, never gates):
    - max_disp vs gold 2.8016 mm  -> relative difference %;
    - max_vM (outer fibre) vs gold 286.80 MPa -> relative difference %.
    Also prints the ODB reduction candidates so the outer-fibre choice is
    visible rather than silently picked.

Usage:
  python check_c5_barrel_abq.py <name>.odb.json
  python check_c5_barrel_abq.py --self-test
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_TRUTH = (_HERE.parent / "FEM-Bench-Aero" / "modeling"
          / "fuselage_barrel_d1800_l2000_str8_frm3" / "truth.json")
GOLD_NODES = 143402


def _mag(d) -> float:
    return (d[3] if len(d) >= 4 else math.sqrt(sum(float(c) ** 2 for c in d[:3])))


def _vm(s) -> float:
    a, b, c, d, e, f = (list(s) + [0.0] * 6)[:6]
    return math.sqrt(0.5 * ((a - b) ** 2 + (b - c) ** 2 + (c - a) ** 2)
                     + 3.0 * (d * d + e * e + f * f))


def _fail_out(errors: list[str]) -> dict:
    """Full-shaped result for early exits.  report() must never KeyError on a
    missing/broken input -- a gate that crashes is not a gate that reports red."""
    return {
        "gate_ok": False,
        "errors": errors,
        "n_nodes": None,
        "max_disp_abq": float("nan"),
        "max_vm_abq_outer": float("nan"),
        "meta": {},
        "diagnostic": {
            "disp_diff_pct": None,
            "vm_diff_pct": None,
            "note": "cross-solver difference (Abaqus vs ccx gold) -- "
                    "diagnostic only, NOT a pass/fail criterion, NOT headline",
        },
    }


def check(odb_json: Path) -> tuple[bool, dict]:
    errs: list[str] = []
    if not odb_json.exists():
        return False, _fail_out([f"missing {odb_json}"])
    try:
        data = json.loads(odb_json.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, _fail_out([f"unparseable JSON: {exc}"])

    nodes = data.get("nodes") or {}
    res = data.get("results") or {}
    n_nodes = len(nodes)
    disp = res.get("DISP") or {}
    peak = res.get("STRESS_PEAK") or {}

    if n_nodes != GOLD_NODES:
        errs.append(f"node count {n_nodes} != gold {GOLD_NODES} "
                    "(wrong deck/odb or expanded-shell leak)")
    if not disp:
        errs.append("DISP block missing/empty")
    if not peak:
        errs.append("STRESS_PEAK block missing/empty")

    dmax = max((_mag(v) for v in disp.values()), default=float("nan"))
    vmax = max((_vm(v) for v in peak.values()), default=float("nan"))
    if not math.isfinite(dmax):
        errs.append("max_disp not finite")
    if not math.isfinite(vmax):
        errs.append("max_vM(STRESS_PEAK) not finite")

    truth = json.loads(_TRUTH.read_text(encoding="utf-8"))["scalars"]
    gold_d = float(truth["max_disp"])
    gold_v = float(truth["max_von_mises"])

    out = {
        "gate_ok": not errs,
        "errors": errs,
        "n_nodes": n_nodes,
        "max_disp_abq": dmax,
        "max_vm_abq_outer": vmax,
        "meta": data.get("meta") or {},
        "diagnostic": {
            "gold_disp": gold_d,
            "gold_vm_outer": gold_v,
            "disp_diff_pct": abs(dmax - gold_d) / gold_d * 100 if math.isfinite(dmax) else None,
            "vm_diff_pct": abs(vmax - gold_v) / gold_v * 100 if math.isfinite(vmax) else None,
            "note": "cross-solver difference (Abaqus vs ccx gold) -- "
                    "diagnostic only, NOT a pass/fail criterion, NOT headline",
        },
    }
    return not errs, out


def report(out: dict) -> None:
    n_nodes = out.get("n_nodes")
    print("=== GATE (hard) ===")
    print(f"  node count      : {n_nodes} (gold {GOLD_NODES}) "
          f"[{'ok' if n_nodes == GOLD_NODES else 'FAIL'}]")
    print(f"  DISP / STRESS_PEAK blocks: "
          f"[{'ok' if out.get('gate_ok') else 'FAIL'}]")
    for e in (out.get("errors") or []):
        print(f"    - {e}")
    print("=== DIAGNOSTIC (NOT a criterion) ===")
    d = out.get("diagnostic") or {}
    print(f"  max_disp  Abaqus {out['max_disp_abq']:.5f} mm  "
          f"vs ccx gold {d['gold_disp']:.5f} mm  "
          f"-> {d['disp_diff_pct']:.2f}% diff" if d.get("disp_diff_pct") is not None
          else "  max_disp n/a")
    print(f"  max_vM    Abaqus {out['max_vm_abq_outer']:.3f} MPa (outer)  "
          f"vs ccx gold {d['gold_vm_outer']:.3f} MPa  "
          f"-> {d['vm_diff_pct']:.2f}% diff" if d.get("vm_diff_pct") is not None
          else "  max_vM n/a")
    cands = ((out.get("meta") or {}).get("stress_candidates_max_vm") or {})
    if cands:
        print("  ODB stress reductions (which quantity each number is):")
        for k, v in cands.items():
            print(f"    {k}: {v}")
    print(f"  {d.get('note', '')}")


def self_test() -> int:
    """Build a synthetic ODB-shaped JSON from gold so the gate logic is
    exercised without a real run.  Also probe the three failure modes:
    wrong node count, missing block, non-finite number."""
    truth = json.loads(_TRUTH.read_text(encoding="utf-8"))["scalars"]
    base = {
        "nodes": {str(i): [0.0, 0.0, 0.0] for i in range(GOLD_NODES)},
        "results": {
            "DISP": {"1": [0.1, 0.2, truth["max_disp"]]},
            "STRESS_PEAK": {"2": [truth["max_von_mises"], 0.0, 0.0, 0.0, 0.0, 0.0]},
        },
        "meta": {},
    }
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "synthetic.odb.json"
        p.write_text(json.dumps(base), encoding="utf-8")
        ok, out = check(p)
        assert ok and out["n_nodes"] == GOLD_NODES, "happy path failed"

        bad = json.loads(json.dumps(base)); bad["nodes"] = {"1": [0, 0, 0]}
        p.write_text(json.dumps(bad), encoding="utf-8")
        ok2, _ = check(p)
        assert not ok2, "wrong node count must gate red"

        bad = json.loads(json.dumps(base)); bad["results"].pop("STRESS_PEAK")
        p.write_text(json.dumps(bad), encoding="utf-8")
        ok3, _ = check(p)
        assert not ok3, "missing STRESS_PEAK must gate red"

        bad = json.loads(json.dumps(base)); bad["results"]["DISP"]["1"] = [float("nan")] * 3
        p.write_text(json.dumps(bad), encoding="utf-8")
        ok4, _ = check(p)
        assert not ok4, "non-finite disp must gate red"

        # early-exit paths must report red, not crash report() (regression:
        # a wrong CLI flag used to produce KeyError: 'n_nodes')
        import contextlib, io
        ok5, out5 = check(Path(td) / "does_not_exist.json")
        assert not ok5, "missing file must gate red"
        with contextlib.redirect_stdout(io.StringIO()):
            report(out5)  # must not raise
        p.write_text("{not json", encoding="utf-8")
        ok6, out6 = check(p)
        assert not ok6, "unparseable JSON must gate red"
        with contextlib.redirect_stdout(io.StringIO()):
            report(out6)  # must not raise

    print("[self-test] 6/6 pass (happy + 3 failure modes + 2 early exits report red)")
    return 0


def main(argv=None) -> int:
    import hashlib
    argv = list(sys.argv if argv is None else argv)
    if len(argv) >= 2 and argv[1] == "--self-test":
        return self_test()
    if len(argv) < 2:
        print("usage: check_c5_barrel_abq.py <name>.odb.json [--json <path>] | --self-test")
        return 2
    odb_path = Path(argv[1])
    ok, out = check(odb_path)
    report(out)
    if "--json" in argv:
        idx = argv.index("--json")
        if idx + 1 >= len(argv):
            print("[ERR] --json needs a path")
            return 2
        dst = Path(argv[idx + 1])
        diag = out.get("diagnostic") or {}
        out["source"] = {"odb_json": str(odb_path),
                         "sha256": hashlib.sha256(odb_path.read_bytes()).hexdigest()
                         if odb_path.exists() else None,
                         "truth": str(_TRUTH)}
        out["formulas"] = {
            "max_disp": "max over DISP nodes of sqrt(ux^2+uy^2+uz^2)",
            "max_vm_outer": "max over STRESS_PEAK nodes of von Mises(s11..s31)",
            "disp_diff_pct": ("abs(max_disp_abq - gold_disp) / gold_disp * 100 "
                              "= abs(%.6f - %.6f) / %.6f * 100" %
                              (out.get("max_disp_abq", float("nan")),
                               diag.get("gold_disp", float("nan")),
                               diag.get("gold_disp", float("nan")))),
            "vm_diff_pct": ("abs(max_vm_abq - gold_vm_outer) / gold_vm_outer * 100 "
                            "= abs(%.4f - %.4f) / %.4f * 100" %
                            (out.get("max_vm_abq_outer", float("nan")),
                             diag.get("gold_vm_outer", float("nan")),
                             diag.get("gold_vm_outer", float("nan")))),
        }
        out["classification"] = ("cross-solver diagnostic; NOT a pass/fail "
                                 "criterion, NOT headline")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[json] {dst} ({dst.stat().st_size} bytes)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
