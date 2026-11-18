"""Generate the Abaqus STATIC deck for the C5 fuselage-barrel case.

Why this exists
---------------
The barrel (143402 nodes) hits CalculiX's scale wall on this machine -- all
four backends die (PaStiX 0xC0000005, SPOOLES SIGSEGV, PARDISO not linked,
ccx_i4 missing UCRT).  Abaqus/Standard is the fallback the owner has.  Abaqus
cannot run inside the agent sandbox (tsbx.dll), so this script only:

  1. rebuilds the deck in the ``abaqus`` dialect from the SAME candidate spec
     the C5 report uses (pipeline -> post -> truth unchanged);
  2. statically checks the deck carries the full combined load
     (internal pressure + end shear + end moment) and the right field output;
  3. reports the model scale so the owner can judge the memory budget BEFORE
     running the generated bat outside WorkBuddy.

No solver is launched here.  ``make_c5_barrel_abq_bat.py`` writes the bat that
the owner runs on the host.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from feagpt.spec import FEASpec          # noqa: E402
from feagpt import pipeline              # noqa: E402

CASE = "fuselage_barrel_d1800_l2000_str8_frm3"
CAND = _HERE / "candidates_l3_v6c_glm_p2" / f"L3_{CASE}.json"
RUNS = _HERE / "_c5_runs" / CASE
ABQ_DIR = RUNS / "abq"          # 分目录：绝不覆盖同目录的 ccx deck


def count_nodes_entities(deck: Path) -> tuple[int, int, dict[str, int]]:
    """Count *NODE rows and *ELEMENT rows by keyword from the deck text."""
    n_nodes = 0
    elem: dict[str, int] = {}
    mode = None
    with deck.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if s.startswith("*"):
                u = s.upper()
                mode = "node" if u.startswith("*NODE") else (
                    "elem" if u.startswith("*ELEMENT") else None)
                if mode == "elem":
                    # *ELEMENT, TYPE=S4, ELSET=... -> count rows separately
                    elem.setdefault("S4", 0)
                continue
            if not s or s.startswith("**") or mode is None:
                continue
            if mode == "node":
                n_nodes += 1
            elif mode == "elem":
                # first field is the element id, second would be nodes; the
                # *ELEMENT header already fixed the type, so count generically
                elem["rows"] = elem.get("rows", 0) + 1
    return n_nodes, elem.get("rows", 0), elem


def deck_checks(txt: str) -> dict[str, bool]:
    """Static checks that must ALL pass for the deck to be a valid Abaqus
    combined-load STATIC job with the field output the ODB reader expects."""
    up = txt.upper()
    return {
        "*STATIC present": "\n*STATIC\n" in up,
        "*DLOAD pressure P": ("*DLOAD" in up and ", P," in up),
        "end shear/moment *CLOAD": up.count("*CLOAD") >= 1,
        "*OUTPUT, FIELD": "*OUTPUT, FIELD" in up,
        "*NODE OUTPUT U,RF": ("*NODE OUTPUT" in up and "\nU, RF\n" in up),
        "*ELEMENT OUTPUT S,E": ("*ELEMENT OUTPUT" in up and "\nS, E\n" in up),
        "no OUTPUT=2D (ccx-only)": "OUTPUT=2D" not in up,
        "no SOLVER= (ccx-only)": "SOLVER=" not in up,
        "shell S4/S3 elements": ("TYPE=S4" in up or "TYPE=S3" in up),
        "abaqus dialect header": "ABAQUS DECK" in up,
    }


def main() -> int:
    ABQ_DIR.mkdir(parents=True, exist_ok=True)
    cand = json.loads(CAND.read_text(encoding="utf-8"))
    spec = FEASpec.from_dict(cand["spec"])
    print(f"[spec] {spec.name}  step={spec.analysis.step_type}  "
          f"extra={spec.extra}")
    print(f"[out ] {ABQ_DIR}")

    res = pipeline.run(spec, outdir=ABQ_DIR, solver_name="abaqus",
                       deck_only=True, step_export=False)
    if not res.ok:
        print("[FAIL] deck-only pipeline did not complete:")
        for m in (res.messages or [])[-6:]:
            print("       " + m)
        return 1

    deck = Path(res.artifacts["inp"])
    txt = deck.read_text(encoding="utf-8", errors="replace")
    checks = deck_checks(txt)
    bad = [k for k, v in checks.items() if not v]
    for k, v in checks.items():
        print(f"  [{'ok' if v else 'FAIL':4}] {k}")
    if bad:
        print(f"[FAIL] {len(bad)} deck checks failed: {bad}")
        return 1

    n_nodes, n_elem, detail = count_nodes_entities(deck)
    gold_nodes = 143402
    dof = n_nodes * 6
    print(f"\n[scale] nodes={n_nodes} (gold {gold_nodes}), "
          f"elements={n_elem}, detail={detail}")
    print(f"[scale] shell S4 -> approx {dof:,} DOF (6/node)")
    print(f"[deck] {deck}  ({deck.stat().st_size/1024:.0f} KB)")

    # write a small manifest the bat builder can consume without re-running
    manifest = {
        "case": CASE,
        "name": spec.name,
        "deck": str(deck),
        "abq_dir": str(ABQ_DIR),
        "n_nodes": n_nodes,
        "n_elem": n_elem,
        "dof_estimate": dof,
        "checks": checks,
    }
    mpath = ABQ_DIR / "c5_barrel_abq_manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                     encoding="utf-8")
    print(f"[manifest] {mpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
