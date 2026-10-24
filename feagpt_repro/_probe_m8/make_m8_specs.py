"""D31 batch: wing-box size axes (span, skin_thickness).

Eight cases, four per axis role:

  train (1 axis off the anchor, everything else neutral)  -> lets the model
      learn the axis at all.  Today span/skin have exactly ONE value across all
      23 archived boxes, which is why a ridge fit assigns them coefficient 0.000
      (measured in _probe_m7) and the beam prior degenerates into a constant.

  val   (1 axis outside the train envelope)               -> single-dimension
      extrapolation, the reading every family shares.

  test  (2 axes out of envelope, or 2 axes off the anchor) -> double
      extrapolation / interaction, which train has never seen (D15's reading).

Load-bearing physics check, not a guess: the tip force is a **fixed 500 N**, so
(unlike the T7 coupon, where F = sigma*w*t scaled with t and cancelled the
membrane stiffness exactly) thickness here MUST change the response.  If the
solvers return the same max|u| for skin 2 and skin 4, the deck is wrong.
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

#: (tag, span, skin_thickness, extra airfoil overrides, note)
CASES = [
    # ---- train: one axis off the anchor, rest neutral ---------------------- #
    ("size_span1600",      1600.0, 3.0, {}, "span 低档（train 包络下界）"),
    ("size_span2400",      2400.0, 3.0, {}, "span 高档（train 包络上界）"),
    ("size_skin2",         2000.0, 2.0, {}, "薄壁（train 包络下界）"),
    ("size_skin4",         2000.0, 4.0, {}, "厚壁（train 包络上界）"),
    # ---- val: one axis outside the train envelope -------------------------- #
    ("size_span3000",      3000.0, 3.0, {}, "span 超包络 -> val"),
    ("size_skin1p5",       2000.0, 1.5, {}, "壁厚超包络 -> val"),
    # ---- test: two axes at once ------------------------------------------- #
    ("size_span3000_skin1p5", 3000.0, 1.5, {}, "双轴超包络 -> test"),
    ("size_span2400_skin2",   2400.0, 2.0, {}, "包络内双轴组合（交互项未见过）-> test"),
]


def build(tag: str) -> FEASpec:
    spec = FEASpec.from_json(ANCHOR)
    for t, span, skin, extra, _n in CASES:
        if t != tag:
            continue
        af = replace(spec.airfoil, span=float(span),
                     skin_thickness=float(skin), **extra)
        cid = f"naca4412_wingbox_{tag}"
        return replace(spec, name=cid, description=f"D31 size axis: {_n}",
                       airfoil=af)
    raise SystemExit(f"unknown tag {tag!r}")


def main() -> int:
    args = sys.argv[1:]
    if "--list" in args:
        print(f"{'tag':<24}{'span':>7}{'skin':>6}{'role':<10}note")
        for tag, span, skin, extra, note in CASES:
            spec = build(tag)
            print(f"{tag:<24}{span:>7.0f}{skin:>6.1f}"
                  f"{infer_role(spec):<10}{note}")
        return 0
    only = [a.split("=", 1)[1] for a in args if a.startswith("--only=")]
    todo = [c for c in CASES if not only or c[0] in only]
    for tag, *_ in todo:
        spec = build(tag)
        p = OUT / f"{spec.name}.spec.json"
        p.write_text(json.dumps(spec.to_dict(), ensure_ascii=False, indent=1),
                     encoding="utf-8")
        print(f"{spec.name:<46} span={spec.airfoil.span:>6.0f} "
              f"skin={spec.airfoil.skin_thickness:g}  -> {p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
