"""D36 batch: a sweep station at 35 deg, taper neutral.

One case: ``naca4412_wingbox_sweep35`` -- sweep 0 -> 35 deg, tip_chord_ratio
left at 1.0, every other axis on its anchor (span 2000, skin 3.0, ribs 5,
chord 1000, no web, no stringer).

Why taper-neutral, deliberately
-------------------------------
D35 bought the interaction anchor (30 x 0.8) and paid for it on the *pure
sweep* side: val ``sweep40`` (taper neutral) went -3.17 % -> -12.79 % and the
whole val set 5.79 -> 6.86 %, because the fitted model has **one** ``s^2``
coefficient and D35 handed it two different jobs -- bend the taper-neutral
curve and the interaction at the same time.  A second interaction point would
make that worse, not better.  What is missing is a station on the *taper
neutral* line between 30 and 40, which is the only place the pure curvature
can be pinned without touching the interaction.

So: one axis, one case, and it is the axis that is currently damaged.

Why 35 exactly
--------------
It is the midpoint of the gap the exam has to be extrapolated across
(30 -> 40).  Anything below 30 adds nothing (train already has 0/10/20/30);
anything at 40 collapses the exam into the training set, which makes the gate
quiet rather than green.  35 shortens the extrapolation to 5 deg and leaves
``sweep40`` (val) and ``sweep40_taper040`` (test) exactly where they are.

What this batch deliberately does NOT do
----------------------------------------
* it does not move ``sweep40`` into train.  A 5 deg extrapolation is still an
  extrapolation; if the answer at 40 becomes right only because 40 is inside
  the envelope, the exam has been deleted, not passed.
* it does not add a second taper-neutral station at 25 deg.  Two new stations
  would cost two solves and would let a curvature error hide in the gap
  between them; one station at the midpoint is the cheapest honest test.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "feagpt_repro"))

from feagpt.manifest import split_of        # noqa: E402
from feagpt.spec import FEASpec             # noqa: E402

BENCH = ROOT / "FEM-Bench-Aero"
OUT = Path(__file__).resolve().parent
ANCHOR = BENCH / "modeling" / "naca4412_wingbox" / "spec.json"

#: (tag, sweep_deg, tip_chord_ratio, note)
CASES = [
    ("sweep35", 35.0, 1.0,
     "D36 纯后掠曲率中间站：锥度中性，把 30->40 的外推距离从 10° 压到 5°"),
]


def build(tag: str) -> FEASpec:
    spec = FEASpec.from_json(ANCHOR)
    for t, sweep, taper, note in CASES:
        if t != tag:
            continue
        af = replace(spec.airfoil, sweep_deg=float(sweep),
                     tip_chord_ratio=float(taper))
        cid = f"naca4412_wingbox_{tag}"
        return replace(spec, name=cid,
                       description=f"Default NACA4412 wing box (FeaGPT reproduction)"
                                   f" | D36 pure-sweep station: sweep_deg {sweep:g}"
                                   f" x tip_chord_ratio {taper:g} ({note})",
                       airfoil=af)
    raise SystemExit(f"unknown tag {tag!r}")


def main() -> int:
    args = sys.argv[1:]
    if "--list" in args:
        print(f"{'tag':<20}{'sweep':>7}{'taper':>7}{'split':<8}note")
        for tag, sweep, taper, note in CASES:
            side, _why = split_of(build(tag))
            print(f"{tag:<20}{sweep:>7.0f}{taper:>7.1f}{side:<8}{note}")
        return 0
    only = [a.split("=", 1)[1] for a in args if a.startswith("--only=")]
    todo = [c for c in CASES if not only or c[0] in only]
    for tag, *_ in todo:
        spec = build(tag)
        side, why = split_of(spec)
        p = OUT / f"{spec.name}.spec.json"
        p.write_text(json.dumps(spec.to_dict(), ensure_ascii=False, indent=1),
                     encoding="utf-8")
        print(f"{spec.name:<46} sweep={spec.airfoil.sweep_deg:>5g} "
              f"taper={spec.airfoil.tip_chord_ratio:g}  split={side} ({why})")
        print(f"  -> {p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
