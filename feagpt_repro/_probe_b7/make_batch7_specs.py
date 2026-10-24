#!/usr/bin/env python
"""M5 batch 7 -- T4 open-hole coupon: more points on dimensions already declared.

Four cases, from 老王's calls of 2026-10-08 (**D28** + two more, see below).
The open-hole family is the dataset's only closed-form family (Howland), and
D23 declared all of its axes *before* any of them had data - including the size
dimension, deliberately (``_open_hole_size_extrapolation`` has matched nothing
since 2026-10-06).  Batch 7 gives the declared rules their first data:

``open_hole_panel_600x300_d30``  val / sweep
    Footprint 400x200 -> 600x300 with ``lambda`` held at 0.1 (d = 30).  The
    **size dimension's first data**.  The physics is the point: Howland's
    finite-width ``Kt`` sees only ``lambda = d/width``, so the theory predicts
    the *same* Kt as the 400x200 baseline - the analytic yardstick does not
    move when the specimen does, which is exactly what makes a size
    extrapolation falsifiable (cf. the barrel's per-size closed forms,
    ``verify_barrel_size.py``).

``open_hole_panel_400x200_d50``  val / sweep
    ``lambda`` 0.1 -> 0.25, footprint unchanged.  A second point on the lambda
    axis (the val slot already holds d40 at 0.2); the finite-width relief is
    much stronger here (Howland gross ~3.36 at 0.25 vs 3.03 at 0.2), and the
    trend probe already runs 0.1/0.2/0.3, so the domain is measured.

``open_hole_panel_600x300_d60``  test / sweep
    Footprint **and** lambda off the anchor at once (0.2 @ 600x300): a corner
    of the table train has seen no part of.  This is the point that forced
    **D28**: without it, such a coupon hit both val regions (lambda first -
    "first hit decides") and would have been graded val, the permissive
    reading D25 already rejected for the barrel.  老王's call (2026-10-08):
    declare the corner rule *before* the data lands, so the predicate ships
    with the batch that exercises it.

``open_hole_panel_400x200_d40_offcentre``  test / feature
    The off-centre form at ``lambda = 0.2`` (hole still at (120, 60); edge
    margin 40 mm).  The family's second off-centre case: the first one
    (d20) is the form's existence proof, this one asks whether the *effect*
    moves with lambda the way the stress field says it must.

Thickness: 老王's call (2026-10-08) is **not** to declare the thickness
dimension this round - the panel family (D16) does not declare one either, and
declaring a rule with no data would be an empty predicate.  The gap is recorded
in ``manifest.limitations`` instead.

Load: the family default (sigma_gross = 10 MPa via a total end force).  Not
touched - batch 7 is about geometry, and changing two things at once would
make the comparison against the baseline unreadable.

Mesh: the family default (4 mm far field, 72 hole-edge divisions), same as the
shipped three.  600x300 grows the node count ~2.3x (measured on the pilot) -
still trivial next to the barrel.

Usage::

    python _probe_b7/make_batch7_specs.py
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPRO = HERE.parent
sys.path.insert(0, str(REPRO))

from feagpt import manifest as M, open_hole  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402

#: ``(params, expected split, expected role, note)`` - D23 declared, D28 corner,
#: thickness deliberately undeclared (see module docstring).
CASES = (
    ({"length": 600.0, "width": 300.0, "hole_d": 30.0}, "val", "sweep",
     "尺寸单维外推（400x200->600x300，λ=0.1 不变；Howland Kt 只看 λ，理论读数不动——"
     "尺寸外推的可证伪点；尺寸维首条数据，D23 时即声明）"),
    ({"hole_d": 50.0}, "val", "sweep",
     "λ 单维外推 0.1->0.25（λ 维第二点，有限宽修正在此显著；趋势探针已量过 0.1/0.2/0.3）"),
    ({"length": 600.0, "width": 300.0, "hole_d": 60.0}, "test", "sweep",
     "双维角点（λ=0.2 与 600x300 同时 ≠ 锚点；D28 谓词的首条数据——"
     "声明前它会落 val，宽松读法已在入库前补上）"),
    ({"hole_d": 40.0, "hole_x": 120.0, "hole_y": 60.0}, "test", "feature",
     "偏心形式 × λ=0.2（族第二条偏心：第一条是存在性证明，这条量偏心效应随 λ 的变化）"),
)


def name_for(params: dict) -> str:
    """``open_hole_panel_<L>x<W>_d<d>[_offcentre]`` - the shipped three's shape.

    ``_offcentre`` is appended when the hole sits anywhere but the centroid,
    matching the existing ``..._d20_offcentre``; only dimensions that are off
    the default get a token, so ``400x200_d50`` reads like the family it
    belongs to.
    """
    L = params.get("length", open_hole.OpenHoleParams.length)
    W = params.get("width", open_hole.OpenHoleParams.width)
    d = params.get("hole_d", open_hole.OpenHoleParams.hole_d)
    name = f"open_hole_panel_{L:g}x{W:g}_d{d:g}"
    if params.get("hole_x") is not None or params.get("hole_y") is not None:
        name += "_offcentre"
    return name


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=str(HERE / "_batch7_specs"))
    ap.add_argument("--workdir", default="outputs_b7")
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"{'case':46s} {'split':6s} {'role':9s} {'class':16s}  reason")
    tally: Counter = Counter()
    bad: list[str] = []
    for params, expect_side, expect_role, note in CASES:
        name = name_for(params)
        spec = open_hole.make_spec(name, workdir=args.workdir, **params)
        spec.description = f"开孔板放量（M5 batch7 / T4，D28）：{note}"
        spec.to_json(out_dir / f"{name}.spec.json")

        rt = FEASpec.from_json(out_dir / f"{name}.spec.json")
        side, why = M.split_of(rt)
        role = M.infer_role(rt)
        tally[side] += 1
        ok = side == expect_side and role == expect_role
        if not ok:
            bad.append(f"{rt.name}: expected {expect_side}/{expect_role}, "
                       f"got {side}/{role}")
        p = open_hole.parse_params(rt)
        print(f"{'  ' if ok else '!!'}{rt.name:44s} {side:6s} {role:9s} "
              f"{M.geometry_class(rt):16s}  {why}")
        print(f"      {p.length:g}x{p.width:g}x{p.thickness:g} d={p.hole_d:g} "
              f"λ={p.lambda_ratio:.3f} centre={p.center()} "
              f"edge_margin={p.edge_margin():g} mm  ({note})")

    print(f"\ntally: {dict(tally)}  (planned: "
          f"{dict(Counter(e for _p, e, _r, _n in CASES))})")
    if bad:
        for b in bad:
            print("FAIL:", b)
        return 2
    print(f"OK - {len(CASES)} spec(s) -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
