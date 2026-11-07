"""Strip dead keys from the 8 frozen v2 modal spec.json files.

Decided 2026-11-07 (option A, user-confirmed): the v2 pilot specs inherited
dead keys from their v1.1 base cases -- keys the generator ignores but the
recursive full-key spec_fidelity gate grades, so a model that follows SYS
(which forbids them) is red even for a perfect transcription.

Removal rule (measured against feagpt source, not guessed):
  - airfoil stringer detail keys when n_stringers_per_skin == 0: the whole
    stringer block never runs (str_stations empty) => dead in all 7 such cases.
  - stringer_flange_width when stringer_kind == "blade": blade() builds a
    single vertical web and drops flange_width (feagpt/sections.py:73-82) =>
    dead even for str3 (n=3).  SYS also forbids flange_width for blades.
  - extra keys outside {end_shear, end_moment}: SYS forbids self-invented
    extra keys (end_torque / torque_axis_dof / sweep_index are v1.1
    experiment residue).

Zero-perturbation proof (this script runs it): re-generate the ccx deck from
the stripped spec (deck_only, scratch dir) and compare sha256 against the
frozen deck -- identical bytes => identical solve input => truth.json stays
valid without re-solving (R61 lock untouched).
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

_ROOT = _HERE.parent
_V2 = _ROOT / "FEM-Bench-Aero" / "modeling_v2"

from make_v2_modal_cases import CASES, v2_name  # noqa: E402
from feagpt.spec import FEASpec                 # noqa: E402
from feagpt import pipeline                     # noqa: E402

STRINGER_KEYS = ("stringer_height", "stringer_thickness",
                 "stringer_kind", "stringer_flange_width")
EXTRA_ALLOWED = ("end_shear", "end_moment")


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def strip_spec(spec: dict, name: str) -> list[str]:
    """Remove dead keys in place; return human-readable removal log."""
    removed = []
    af = spec.get("airfoil") or {}
    n_str = af.get("n_stringers_per_skin")
    kind = af.get("stringer_kind")
    for k in STRINGER_KEYS:
        if k not in af:
            continue
        if n_str == 0:
            af.pop(k)
            removed.append(f"airfoil.{k} (n_stringers_per_skin=0, dead)")
        elif k == "stringer_flange_width" and kind == "blade":
            af.pop(k)
            removed.append(f"airfoil.{k} (blade ignores it, SYS forbids)")
    extra = spec.get("extra") or {}
    for k in [k for k in extra if k not in EXTRA_ALLOWED]:
        extra.pop(k)
        removed.append(f"extra.{k} (self-invented, SYS forbids)")
    if not removed:
        raise SystemExit(f"{name}: nothing to strip -- rule mismatch, stop")
    return removed


def main() -> int:
    print(f"stripping {_V2} (8 cases)\n")
    for v11 in CASES:
        name = v2_name(v11)
        d = _V2 / name
        sp = d / f"{name}.spec.json"
        frozen_inp = d / f"{name}.inp"
        spec = json.loads(sp.read_text(encoding="utf-8"))

        removed = strip_spec(spec, name)

        # contract gate upfront: stripped spec must still build
        FEASpec.from_dict(json.loads(json.dumps(spec)))

        # zero-perturbation proof: deck from stripped spec == frozen deck
        with tempfile.TemporaryDirectory(prefix="v2_strip_check_") as td:
            res = pipeline.run(FEASpec.from_dict(json.loads(json.dumps(spec))),
                               outdir=Path(td), step_export=False,
                               deck_only=True, solver_name="ccx")
            new_inp = Path(res.artifacts["inp"])
            s_new, s_old = sha256(new_inp), sha256(frozen_inp)
        same = s_new == s_old
        if not same:
            print(f"[FAIL] {name}: deck sha changed after strip!\n"
                  f"  frozen: {s_old}\n  new:    {s_new}")
            return 1

        # only now write the stripped spec
        sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")
        print(f"[ok] {name}")
        for r in removed:
            print(f"     - {r}")
        print(f"     deck sha unchanged: {s_old[:16]}  (truth stays valid)")
    print("\n8/8 stripped, deck bytes identical everywhere -- "
          "SHA256SUMS now needs only the 8 spec.json rows recomputed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
