"""D33 batch: the sweep axis gets an intermediate station (20 deg -> 30 deg).

One case.  Only ``airfoil.sweep_deg`` moves (20 -> 30); taper stays neutral at
1.0 and every other axis sits on its anchor, so the point is a *sweep station*,
not a combination.

Why a middle station, measured not assumed
------------------------------------------
M9 left exactly one extrapolation mechanism in the whole dataset that still
fails badly: the planform axis.  In the M8 baseline the single test case tagged
``planform_out`` (``sweep40_taper040``) carries the largest error of any group
(32.9 % APE, ``FEM-Bench-Aero/baseline_d31.json :: test_group_ape``), and the
M7 axis sweep measured the same thing on the archived sweep pair: 20 -> 40 deg
is **-41.5 %**, i.e. super-linear in the extrapolation distance.

Train currently knows sweep at {0, 10, 20}.  Three stations on a curved axis is
enough to fit a chord but not a curvature, and 40 sits 20 deg past the last
station.  Adding 30 (a) turns the axis into four stations so a curvature term is
identifiable, and (b) halves the extrapolation distance 40 has to cover
(20 deg -> 10 deg) **without touching any truth value already published**: the
val point sweep40 and the test point sweep40_taper040 keep their splits, they
are simply measured against a closer envelope.

What this batch deliberately does NOT do
----------------------------------------
* it does not move sweep40 into train.  If it did, the planform axis would have
  no out-of-envelope case left to test on - the gate would go quiet, not green.
  The point of a middle station is to make extrapolation *fair*, not to delete
  the exam.
* it does not add taper stations, ribs stations, or another web.  One axis, one
  case: if the error does not move, the axis was not the cause and that has to
  be visible.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "feagpt_repro"))

from feagpt.spec import FEASpec            # noqa: E402
from feagpt.manifest import infer_role     # noqa: E402

BENCH = ROOT / "FEM-Bench-Aero"
OUT = Path(__file__).resolve().parent
ANCHOR = BENCH / "modeling" / "naca4412_wingbox" / "spec.json"

#: (tag, sweep_deg, note)
CASES = [
    ("sweep30", 30.0,
     "D33 后掠中间档：train 第 4 个 sweep 站（0/10/20/30），"
     "把 40 deg 的外推距离从 20 deg 缩到 10 deg"),
]


def build(tag: str) -> FEASpec:
    spec = FEASpec.from_json(ANCHOR)
    for t, sweep, note in CASES:
        if t != tag:
            continue
        af = replace(spec.airfoil, sweep_deg=float(sweep))
        cid = f"naca4412_wingbox_{tag}"
        return replace(spec, name=cid,
                       description=f"Default NACA4412 wing box (FeaGPT reproduction)"
                                   f" | D33 sweep station: sweep_deg {sweep:g},"
                                   f" taper neutral 1.0 ({note})",
                       airfoil=af)
    raise SystemExit(f"unknown tag {tag!r}")


def main() -> int:
    args = sys.argv[1:]
    if "--list" in args:
        print(f"{'tag':<16}{'sweep':>7}{'taper':>7}{'role':<10}note")
        for tag, sweep, note in CASES:
            spec = build(tag)
            print(f"{tag:<16}{sweep:>7.0f}"
                  f"{spec.airfoil.tip_chord_ratio:>7.1f}"
                  f"{infer_role(spec):<10}{note}")
        return 0
    only = [a.split("=", 1)[1] for a in args if a.startswith("--only=")]
    todo = [c for c in CASES if not only or c[0] in only]
    for tag, *_ in todo:
        spec = build(tag)
        p = OUT / f"{spec.name}.spec.json"
        p.write_text(json.dumps(spec.to_dict(), ensure_ascii=False, indent=1),
                     encoding="utf-8")
        print(f"{spec.name:<46} sweep={spec.airfoil.sweep_deg:>5g} "
              f"taper={spec.airfoil.tip_chord_ratio:g}  -> {p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
