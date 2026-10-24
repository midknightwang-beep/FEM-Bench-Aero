#!/usr/bin/env python
"""T7 pilot spec: [0/90]s CFRP open-hole coupon, the T4 geometry unchanged.

The layup rides in ``structure.params["layup"]`` (a dict key, not a dataclass
field) so the archived specs - which carry no such key - keep their
``spec_sha256``.  Total thickness 2.0 mm = 4 x 0.5 mm plies, matching the T4
family thickness, so the gross stress convention (10 MPa -> 4000 N) is carried
over unchanged and the composite coupon is directly comparable to its
aluminium sibling.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feagpt import open_hole
from feagpt.laminate import (LayupSpec, OrthotropicMaterialSpec, Ply,
                             layup_to_params)

lay = LayupSpec(
    plies=(Ply(0.0, 0.5), Ply(90.0, 0.5), Ply(90.0, 0.5), Ply(0.0, 0.5)),
    material=OrthotropicMaterialSpec(),
)

spec = open_hole.make_spec(
    "open_hole_panel_400x200_d20_cfrp090s",
    thickness=2.0,
    layup=layup_to_params(lay),
)
spec.analysis.solver = "ccx"

out = Path(__file__).with_name(f"{spec.name}.spec.json")
spec.to_json(out)
print(f"layup code       : {lay.code}  (symmetric={lay.is_symmetric}, balanced={lay.is_balanced})")
print(f"total thickness  : {lay.total_thickness} mm")
print(f"params keys      : {sorted(spec.structure.params)}")
print(f"spec written     : {out}")
