"""D35 batch: the sweep x taper interaction gets a train anchor.

One case: ``naca4412_wingbox_sweep30_taper080`` -- sweep 0 -> 30 deg **and**
tip_chord_ratio 1.0 -> 0.8, both keeping every other axis on its anchor
(span 2000, skin 3.0, ribs 5, chord 1000, no web).

Why this case, measured not assumed
-----------------------------------
D34's residual diagnosis (``_probe_m11/residual_diag.py``) isolated the last
large error mechanism in the whole baseline: the two test cases that move
both planform knobs sit at 13.3 % / 15.7 % while every taper-neutral point is
at -3.2 %.  Cause is structural, not numeric: train held **0** cases with
``sweep>0 & taper!=1``, so the interaction column ``s^2*(taper-1)`` was
identically zero and could not be estimated at all -- no basis change can fix
that, only a sample can.

D35 changes ``_wingbox_swept_and_tapered`` from "both knobs off-neutral =>
holdout" to the D31-style split ("... and at least one outside the train
envelope").  That alone already moves ``sweep20_taper060`` into train
(measured: 1 case, ``_probe_m12/d35_landed.json``).  This case is the second,
deliberately placed where the exam is:

* ``sweep=30`` is the top of train's sweep envelope (0/10/20/30), i.e. the
  station nearest the val point ``sweep40`` and the test point
  ``sweep40_taper040`` -- an interior point placed next to the extrapolation,
  not in the middle of nowhere.
* ``taper=0.8`` is an *interior* value of train's taper set {0.6,0.8,0.9,1.0},
  unlike ``sweep20_taper060`` whose taper sits on the 0.6 boundary.

Why exactly one, not two
------------------------
The interaction is a single coefficient.  With two interaction points train
gets one residual degree of freedom to check it against; a third would buy
nothing that the next milestone cannot test more cheaply.  One axis, one
case -- if the interaction turns out not to matter, that has to be visible in
the numbers rather than averaged away by extra samples.

What this batch deliberately does NOT do
----------------------------------------
* it does not touch ``sweep40_taper040``.  Both its axes are outside train's
  envelope (40 > 30, 0.4 < 0.6), so it remains the double-extrapolation exam.
  Moving it into train would make the gate quiet, not green.
* it does not add another sweep station or another taper station on their own.
  A single-axis anchor teaches nothing about the cross product.
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
    ("sweep30_taper080", 30.0, 0.8,
     "D35 交互锚点：sweep 顶端站(30) x taper 内部值(0.8)，"
     "给 s^2*(taper-1) 一个 train 样本"),
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
                                   f" | D35 interaction anchor: sweep_deg {sweep:g}"
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
