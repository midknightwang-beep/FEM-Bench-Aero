#!/usr/bin/env python
"""Read back the three batch4 coupons and report their Kt, both codes.

The dashboard prints a Kt per coupon, and the project rule is that a printed
number must be *on disk*, not remembered.  So the number is sourced here: the
three archived runs are re-read (ccx from FRD, abaqus from the ODB-derived
JSON), the hole-edge peak is reduced against both nominal-stress conventions,
and the result is written to ``_t4_probe/open_hole_readings.json``.

Howland's finite-width correction describes a hole **on the centreline**; the
off-centre coupon is therefore reported with its measured factors but *without*
a Howland comparison, rather than being compared against a solution that does
not apply to it.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPRO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPRO))

from feagpt import open_hole, post  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402

CASES = ("open_hole_panel_400x200_d20",
         "open_hole_panel_400x200_d40",
         "open_hole_panel_400x200_d20_offcentre")
ROOTS = {"ccx": "outputs_hole", "abaqus": "outputs_hole_abaqus"}


def _load(case: str, solver: str) -> dict:
    d = REPRO / ROOTS[solver] / case
    if solver == "ccx":
        return post.load_any(d / f"{case}.frd")
    return post.load_results_json(d / f"{case}.odb.json")


def _edge_vm(data: dict, p: "open_hole.OpenHoleParams") -> list[float]:
    cx, cy = p.center()
    rh = 0.5 * p.hole_d
    st = data["results"].get("STRESS") or {}
    out = []
    for t, (x, y, _z) in data["nodes"].items():
        if abs(math.hypot(x - cx, y - cy) - rh) < 1e-3 and t in st:
            out.append(post.von_mises(st[t]))
    return out


def main() -> int:
    report: dict = {}
    for case in CASES:
        spec = FEASpec.from_json(REPRO / ROOTS["ccx"] / case / f"{case}.spec.json")
        p = open_hole.parse_params(spec)
        F = float(spec.load.magnitude)
        lam = p.lambda_ratio
        cx, cy = p.center()
        centred = (abs(cx - 0.5 * p.length) < 1e-6
                   and abs(cy - 0.5 * p.width) < 1e-6)
        entry: dict = {
            "lambda": lam,
            "hole_d": p.hole_d,
            "centre": list(p.center()),
            "centred": centred,
            "length": p.length, "width": p.width, "thickness": p.thickness,
            "gross_stress": round(open_hole.gross_stress(F, p), 6),
            "net_stress": round(open_hole.net_stress(F, p), 6),
            "howland_net": round(open_hole.howland_kt_net(lam), 4),
            "howland_gross": round(open_hole.howland_kt_gross(lam), 4),
            "kirsch": open_hole.kirsch_kt(),
        }
        for solver in ("ccx", "abaqus"):
            data = _load(case, solver)
            prof = _edge_vm(data, p)
            peak = max(prof)
            ktg = peak / open_hole.gross_stress(F, p)
            ktn = peak / open_hole.net_stress(F, p)
            entry[solver] = {
                "peak_vm": round(peak, 4),
                "kt_gross": round(ktg, 4),
                "kt_net": round(ktn, 4),
                "n_edge": len(prof),
            }
            if centred:
                entry[solver]["err_gross_pct"] = round(
                    (ktg / open_hole.howland_kt_gross(lam) - 1.0) * 100.0, 4)
        report[case] = entry
        c, a = entry["ccx"], entry["abaqus"]
        tag = "" if centred else "  [off-centre: Howland does not apply]"
        print(f"{case}{tag}")
        print(f"  lambda {lam:.3f}  gross {entry['gross_stress']:.4f}  "
              f"net {entry['net_stress']:.4f} MPa")
        print(f"  ccx    Kt_gross {c['kt_gross']:.4f}  Kt_net {c['kt_net']:.4f}"
              f"  peak {c['peak_vm']:.4f}  edge {c['n_edge']}")
        print(f"  abaqus Kt_gross {a['kt_gross']:.4f}  Kt_net {a['kt_net']:.4f}"
              f"  peak {a['peak_vm']:.4f}  edge {a['n_edge']}")
        if centred:
            print(f"  Howland    Kt_gross {entry['howland_gross']:.4f}  "
                  f"Kt_net {entry['howland_net']:.4f}  |  "
                  f"err ccx {c['err_gross_pct']:+.3f} %  "
                  f"abq {a['err_gross_pct']:+.3f} %")

    out = REPRO / "_t4_probe/open_hole_readings.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nreport -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
