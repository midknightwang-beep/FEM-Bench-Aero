#!/usr/bin/env python
"""How wide does D20's end-load exclusion band have to be before the gate holds?

The batch-6 D1600 case trips gate 3 at 1.13 %, and the breach is *local*: its
peak node sits 6.1 mm from the plane the end shear/moment are applied on, and the
node-by-node error is ~21 % at the loaded rim but < 1 % over the middle 800 mm.
D20 removes only the ring itself (2,588 nodes), so the boundary layer stays in
the comparison.

This sweeps a plain axial band - drop every node with ``z < band`` or
``z > L - band`` - over the registered D20 metric, for the four batch-6 cases
*and* the two already-shipped barrel cases, so a proposal to widen the band can
be judged against the cases it would also re-score.

Reads what is on disk; runs no solver.

Usage::

    python _probe_b6/b6_gate3_band_sweep.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPRO = HERE.parent
sys.path.insert(0, str(REPRO))

from feagpt import post, fuselage                            # noqa: E402
from feagpt.spec import FEASpec                              # noqa: E402
from verify_barrel import _disp, _numag, _rel, TOL_CROSS     # noqa: E402

BANDS = (0.0, 25.0, 50.0, 100.0, 150.0, 200.0, 300.0)

#: ``(label, ccx dir, abaqus dir, spec path)``
SETS = (
    ("b6 D1600      ", "outputs_b6", "outputs_b6_abaqus",
     "_m5_probe/_batch6_specs/fuselage_barrel_d1600_l2000_str8_frm3.spec.json"),
    ("b6 L1600      ", "outputs_b6", "outputs_b6_abaqus",
     "_m5_probe/_batch6_specs/fuselage_barrel_d2000_l1600_str8_frm3.spec.json"),
    ("b6 t2         ", "outputs_b6", "outputs_b6_abaqus",
     "_m5_probe/_batch6_specs/fuselage_barrel_d2000_l2000_t2_str8_frm3.spec.json"),
    ("b6 D1600+L1600", "outputs_b6", "outputs_b6_abaqus",
     "_m5_probe/_batch6_specs/fuselage_barrel_d1600_l1600_str8_frm3.spec.json"),
    ("b3 str8_frm3  ", "outputs_b3", "outputs_b3_abaqus",
     "outputs_b3/fuselage_barrel_d2000_l2000_str8_frm3/"
     "fuselage_barrel_d2000_l2000_str8_frm3.spec.json"),
    ("b3 str12_frm4 ", "outputs_b3", "outputs_b3_abaqus",
     "outputs_b3/fuselage_barrel_d2000_l2000_str12_frm4/"
     "fuselage_barrel_d2000_l2000_str12_frm4.spec.json"),
)


def peak_in_band(data: dict, L: float, band: float) -> tuple[float, int]:
    """max |u| over nodes whose z lies in ``[band, L - band]``."""
    best, bn = -1.0, -1
    for tag, u in _disp(data).items():
        z = data["nodes"][tag][2]
        if z < band or z > L - band:
            continue
        m = _numag(u)
        if m > best:
            best, bn = m, tag
    return best, bn


def main() -> int:
    print(f"D20 band sweep - TOL_CROSS = {TOL_CROSS:g} %")
    print("=" * 96)
    head = "  ".join(f"{b:>8g}" for b in BANDS)
    print(f"{'case':16s} {head}")
    print("-" * 96)

    rows: dict = {}
    for label, cdir, adir, specp in SETS:
        spec = FEASpec.from_json(REPRO / specp)
        p = fuselage.parse_params(spec)
        name = Path(specp).stem.replace(".spec", "")
        ccx = post.load_any(REPRO / cdir / name / f"{name}.frd")
        abq = post.load_results_json(REPRO / adir / name / f"{name}.odb.json")
        cells, rec = [], {}
        for b in BANDS:
            sc, nc = peak_in_band(ccx, p.length, b)
            sa, na = peak_in_band(abq, p.length, b)
            e = _rel(sc, sa)
            rec[str(b)] = {"ccx": round(sc, 6), "abq": round(sa, 6),
                           "pct": round(e, 5), "same_node": nc == na,
                           "pass": e < TOL_CROSS}
            cells.append(f"{e:>7.4f}{'*' if e >= TOL_CROSS else ' '}")
        rows[label] = rec
        print(f"{label:16s} " + "  ".join(cells))
    print("-" * 96)
    print("  * = over the registered 1 % gate;   band 0 = the whole model")
    (HERE / "_b6_band_sweep.json").write_text(
        json.dumps({"tolerance_pct": TOL_CROSS, "bands_mm": list(BANDS),
                    "cases": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(f"report -> {HERE / '_b6_band_sweep.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
