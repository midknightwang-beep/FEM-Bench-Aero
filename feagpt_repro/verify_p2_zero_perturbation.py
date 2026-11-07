"""C6-P2 implementation step 1 verification (2026-11-07).

Two independent checks, both read-only against the frozen volumes:

1. ZERO PERTURBATION -- after adding the ``buckle`` branch to spec.py /
   inp_writer.py, regenerate one static deck per family and one v2 modal
   deck, and compare sha256 of the generated .inp against the frozen deck
   (line endings normalized, since the frozen volume was CRLF-normalized).
   Any byte difference in a static/frequency deck is a regression.

2. BUCKLE DECK SHAPE -- build one buckle deck from an existing v1.1
   stiffened-panel spec and assert: *BUCKLE present, *STATIC absent,
   the reference load is INSIDE the step, no static extra end loads.

No solver is launched here (R61 lock untouched); the ccx smoke run is a
separate step.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from feagpt.spec import FEASpec          # noqa: E402
from feagpt import pipeline              # noqa: E402

_ROOT = _HERE.parent
_V11 = _ROOT / "FEM-Bench-Aero" / "modeling"
_V2 = _ROOT / "FEM-Bench-Aero" / "modeling_v2"

STATIC_CASES = [
    ("naca4412_wingbox", "wingbox"),
    ("fuselage_barrel_d1600_l1600_str8_frm3", "barrel"),
    ("open_hole_panel_400x200_d30", "open_hole"),
    ("stiffened_panel_600x600", "panel"),
]
MODAL_CASE = "naca4412_wingbox_modal"


def norm_sha(p: Path) -> str:
    """sha256 of the text with CRLF folded to LF (EOL-only differences ignored)."""
    return hashlib.sha256(p.read_text(encoding="utf-8")
                          .replace("\r\n", "\n").encode("utf-8")).hexdigest()


def gen_deck(spec: FEASpec, td: str, dialect: str = "ccx") -> Path:
    res = pipeline.run(spec, outdir=Path(td), step_export=False,
                       deck_only=True, solver_name=dialect)
    return Path(res.artifacts["inp"])


def main() -> int:
    bad = 0
    print("=== 1) zero-perturbation (static + frequency) ===")
    for name, label in STATIC_CASES:
        sp = _V11 / name / "spec.json"
        if not sp.exists():
            print(f"  [SKIP] {name}: no v1.1 spec")
            continue
        with tempfile.TemporaryDirectory(prefix="p2_zero_") as td:
            deck = gen_deck(FEASpec.from_json(sp), td)
            frozen = _V11 / name / "model.inp"
            a, b = norm_sha(deck), norm_sha(frozen)
            ok = a == b
            bad += not ok
            print(f"  [{('ok' if ok else 'FAIL'):4}] static/{label:<10} {name}  {a[:12]}")
    # v2 modal deck (frequency branch must be untouched too)
    sp = _V2 / MODAL_CASE / f"{MODAL_CASE}.spec.json"
    with tempfile.TemporaryDirectory(prefix="p2_zero_") as td:
        deck = gen_deck(FEASpec.from_json(sp), td)
        frozen = _V2 / MODAL_CASE / f"{MODAL_CASE}.inp"
        a, b = norm_sha(deck), norm_sha(frozen)
        ok = a == b
        bad += not ok
        print(f"  [{'ok' if ok else 'FAIL':4}] frequency/modal    {MODAL_CASE}  {a[:12]}")

    print("\n=== 2) buckle deck shape (no solve) ===")
    base = "stiffened_panel_600x600"
    d = json.loads((_V11 / base / "spec.json").read_text(encoding="utf-8"))
    d["analysis"]["step_type"] = "buckle"
    d["analysis"]["buckling"] = {
        "n_modes": 1,
        "reference_load": {"kind": "pressure", "magnitude": 0.1,
                           "pressure_group": "panel", "pressure_dload_sign": -1.0},
    }
    spec = FEASpec.from_dict(d)
    with tempfile.TemporaryDirectory(prefix="p2_buckle_") as td:
        deck = gen_deck(spec, td)
        txt = deck.read_text(encoding="utf-8")
        lines = txt.splitlines()
        checks = {
            "*BUCKLE present": "*BUCKLE" in txt,
            "*STATIC absent": "*STATIC" not in txt,
            "one *STEP": sum(1 for x in lines if x.strip().upper() == "*STEP") == 1,
            "reference load in step": any(x.startswith("*DLOAD") for x in lines[
                next(i for i, x in enumerate(lines) if x.strip().upper() == "*BUCKLE"):]),
            "no end-shear CLOAD": "end_shear" not in txt,
        }
        for k, v in checks.items():
            bad += not v
            print(f"  [{'ok' if v else 'FAIL':4}] {k}")
        step_i = next(i for i, x in enumerate(lines) if x.strip().upper() == "*STEP")
        print("  --- step section ---")
        for x in lines[step_i:]:
            print("   ", x)
    print(f"\n{'ZERO PERTURBATION + BUCKLE SHAPE: ALL GREEN' if not bad else f'FAILURES: {bad}'}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
