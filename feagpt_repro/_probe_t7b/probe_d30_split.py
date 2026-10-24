#!/usr/bin/env python
"""D30 probe: does a "scalar-dimension deviation count" rule reproduce D12?

The question this answers, before anything is written to the archive:

    Can the material dimension (layup) and the wall-thickness dimension be
    declared as two more *scalar axes* on the open-hole family, with the split
    read off as 0 axes off the anchor -> train, 1 -> val, >=2 -> test,
    **without moving a single one of the 41 shipped cases**?

If any shipped case changes split, the rule is wrong (or the anchor is) and
nothing gets built.  Read-only: it loads each case's spec.json, recomputes the
split under the candidate rule, and diffs against manifest.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from feagpt import manifest as M  # noqa: E402
from feagpt import open_hole  # noqa: E402
from feagpt.laminate import layup_from_params  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402

AERO = ROOT.parent / "FEM-Bench-Aero"

# --- the anchors the candidate rule measures against ------------------------ #
ANCHOR_LAMBDA = 0.1
ANCHOR_SIZE = (400.0, 200.0)
ANCHOR_THICKNESS = 2.0
ANCHOR_CODE = "[0/90]s"


def candidate(spec) -> tuple[str, list[str]]:
    """Return (split, reasons) under the candidate four-axis rule.

    Axes on the open-hole family, each a scalar the model can be pushed along:
      M  material/stacking  -- layup code off the laminate anchor
      T  wall thickness     -- total stack thickness off the anchor
      L  lambda_ratio       -- hole diameter / coupon width off the anchor
      S  footprint (L, W)   -- coupon size off the anchor
    """
    p = open_hole.parse_params(spec)
    reasons: list[str] = []

    # off-centre stays its own declared test region (D23), unchanged
    if M._open_hole_offcentre(spec):
        return "test", ["off-centre (unchanged)"]

    n = 0
    lay = layup_from_params(spec.structure.params or {})
    if lay is not None:
        if lay.code != ANCHOR_CODE:
            n += 1
            reasons.append(f"M:{lay.code}")
        if abs(lay.total_thickness - ANCHOR_THICKNESS) > 1e-9:
            n += 1
            reasons.append(f"T:{lay.total_thickness:g}mm")
    else:
        # isotropic (aluminium): the family's original anchor, no material axis
        if abs(float(p.thickness) - ANCHOR_THICKNESS) > 1e-9:
            n += 1
            reasons.append(f"T:{float(p.thickness):g}mm(iso)")

    if abs(p.lambda_ratio - ANCHOR_LAMBDA) > 1e-9:
        n += 1
        reasons.append(f"L:{p.lambda_ratio:.4g}")
    if not (abs(float(p.length) - ANCHOR_SIZE[0]) < 1e-9
            and abs(float(p.width) - ANCHOR_SIZE[1]) < 1e-9):
        n += 1
        reasons.append(f"S:{p.length:g}x{p.width:g}")

    split = "train" if n == 0 else ("val" if n == 1 else "test")
    return split, reasons or ["anchor (0 axes)"]


def main() -> int:
    mf = json.loads((AERO / "manifest.json").read_text(encoding="utf-8"))
    rows, moved = [], []

    for c in mf["cases"]:
        if c["family"] != open_hole.FAMILY:
            continue
        sp = AERO / "modeling" / c["case_id"] / "spec.json"
        if not sp.exists():
            rows.append((c["case_id"], c["split"], "?", "MISSING spec.json", "SKIP"))
            continue
        spec = FEASpec.from_json(sp)
        new, why = candidate(spec)
        ok = (new == c["split"])
        rows.append((c["case_id"], c["split"], new, ", ".join(why), "ok" if ok else "MOVED"))
        if not ok:
            moved.append((c["case_id"], c["split"], new))

    w = max(len(r[0]) for r in rows) + 2
    print(f"{'case':<{w}} {'shipped':<7} {'rule':<7} {'B?':<7} axes")
    print("-" * (w + 34))
    for cid, old, new, why, st in rows:
        print(f"{cid:<{w}} {old:<7} {new:<7} {st:<7} {why}")

    print()
    if moved:
        print(f"REGRESSION: {len(moved)} shipped case(s) would move")
        for cid, o, n in moved:
            print(f"  {cid}: {o} -> {n}")
        return 1
    print(f"D30 REPRODUCES D12: all {len(rows)} open-hole cases keep their split")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
