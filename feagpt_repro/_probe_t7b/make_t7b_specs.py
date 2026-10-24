#!/usr/bin/env python
"""T7 build-out (D30): specs for the layup family and the thickness axis.

Two new scalar axes on the open-hole family, per the rule adopted 2026-10-24:

    M  stacking sequence  - ``[0/90]s`` is the laminate anchor
    T  wall thickness     - the ply sum, 2.0 mm is the anchor
    L  lambda_ratio       - 0.1
    S  footprint          - 400 x 200

    axes off the anchor: 0 -> train, 1 -> val, >=2 -> test

The coupon geometry, the mesh size and therefore the mesh are **identical** to
the shipped ``[0/90]s`` case: only the ``*ELASTIC`` card and (for the thickness
axis) the shell thickness change.  That is deliberate - it is exactly the pair
of ingredients the D25 fingerprint carries, so a material or thickness variant
cannot silently collide with its sibling.

Usage::

    python make_t7b_specs.py --list              # show the planned batch
    python make_t7b_specs.py --only cfrp45s      # write one spec
    python make_t7b_specs.py --all               # write the whole batch
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feagpt import open_hole  # noqa: E402
from feagpt.laminate import (LayupSpec, OrthotropicMaterialSpec, Ply,  # noqa: E402
                             layup_to_params)
from feagpt.manifest import open_hole_off_axes  # noqa: E402

MAT = OrthotropicMaterialSpec()

#: ``key -> (case suffix, plies [(angle, ply thickness)], geometry kwargs)``
#:
#: The ply thicknesses are chosen so the total lands on a declared thickness:
#: 4 x 0.5 = 2.0 (the anchor) and 4 x 0.25 = 1.0 (the thin variant).  A stack
#: whose ply sum disagrees with ``params["thickness"]`` is refused by
#: ``laminate.layup_from_params`` - two truths, no picking one.
BATCH = {
    # ---- material axis: same 2.0 mm, same geometry, different stack --------
    "cfrp45s": dict(
        suffix="cfrp45s",
        plies=[(45.0, 0.5), (-45.0, 0.5), (-45.0, 0.5), (45.0, 0.5)],
        geom={},                       # 400x200, d20, t2.0 -> 1 axis (M) -> val
    ),
    "cfrpqi": dict(
        suffix="cfrpqi",
        plies=[(0.0, 0.25), (45.0, 0.25), (-45.0, 0.25), (90.0, 0.25),
               (90.0, 0.25), (-45.0, 0.25), (45.0, 0.25), (0.0, 0.25)],
        geom={},                       # quasi-isotropic, 2.0 mm -> 1 axis -> val
    ),
    # ---- thickness axis: same stack, same geometry, thinner skin -----------
    "cfrp090s_t1": dict(
        suffix="cfrp090s_t1",
        plies=[(0.0, 0.25), (90.0, 0.25), (90.0, 0.25), (0.0, 0.25)],
        geom={},                       # [0/90]s at 1.0 mm -> 1 axis (T) -> val
    ),
    # ---- two axes at once -> test ------------------------------------------
    "cfrp45s_t1": dict(
        suffix="cfrp45s_t1",
        plies=[(45.0, 0.25), (-45.0, 0.25), (-45.0, 0.25), (45.0, 0.25)],
        geom={},                       # M + T -> 2 axes -> test
    ),
    "cfrp45s_d40": dict(
        suffix="cfrp45s_d40",
        plies=[(45.0, 0.5), (-45.0, 0.5), (-45.0, 0.5), (45.0, 0.5)],
        geom={"hole_d": 40.0},         # M + L -> 2 axes -> test
    ),
}


def build(key: str):
    item = BATCH[key]
    lay = LayupSpec(plies=tuple(Ply(a, t) for a, t in item["plies"]), material=MAT)
    params = dict(item["geom"])
    params["thickness"] = lay.total_thickness
    name = f"open_hole_panel_400x200_d20_{item['suffix']}"
    spec = open_hole.make_spec(name, layup=layup_to_params(lay), **params)
    spec.analysis.solver = "ccx"
    return spec, lay


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--out-dir", default=None)
    a = ap.parse_args()

    keys = list(BATCH) if a.all else (a.only or [])
    if a.list or not keys:
        print(f"{'key':<14} {'code':<16} {'t':<5} axes")
        print("-" * 62)
        for k in BATCH:
            spec, lay = build(k)
            print(f"{k:<14} {lay.code:<16} {lay.total_thickness:<5g} "
                  f"{open_hole_off_axes(spec)}")
        return 0

    out = Path(a.out_dir) if a.out_dir else Path(__file__).resolve().parent
    out.mkdir(parents=True, exist_ok=True)
    for k in keys:
        spec, lay = build(k)
        p = out / f"{spec.name}.spec.json"
        spec.to_json(p)
        axes = open_hole_off_axes(spec)
        print(f"{k:<14} {lay.code:<16} t={lay.total_thickness:<5g} "
              f"axes={len(axes)} {axes}")
        print(f"   -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
