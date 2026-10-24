"""D33 physics check: is the sweep axis curved, and does a 4th station buy anything?

The whole justification for adding ``sweep30`` is a *shape* claim: the response
does not grow linearly with sweep, so extrapolating 20 -> 40 from stations
{0, 10, 20} is an extrapolation over a curvature train has never seen.  If that
were false -- if the axis were linear -- a middle station would be pure ballast
and the honest move would be to say so and not add the case.

This script measures it on the five archived sweep stations, taper neutral
throughout, everything else on its anchor.  No solver is run; it only reads
``model.results.json`` of cases already on disk.

Four questions, in order:

1. **is the axis curved?**  successive growth factors of ``max_disp`` along
   0 -> 10 -> 20 -> 30 -> 40.  Linear growth gives equal factors.
2. **does a linear extrapolation fail the way M7 said?**  the 0-20 secant
   continued to 40, compared with the measured value.  M7 reported -41.5 % on
   the archived pair; the number here should land in the same place, and if it
   does not, one of the two measurements is wrong.
3. **is the new station informative?**  if the 0/10/20 quadratic already
   predicts 30 to within a couple of percent, the point teaches nothing.  It has
   to be *measurably* off the old trend to be worth a solve.
4. **does the 4-station fit close the gap at 40?**  quadratic on {0,10,20} vs
   quadratic and cubic on {0,10,20,30}, each extrapolated to 40.

Point 4 is the honest test and it can fail: a cubic through four points is
interpolation, and extrapolating an interpolant is exactly how extrapolation
gets worse.  If the cubic is worse than the quadratic, that is the finding --
"add stations, raise the order" is not a recipe, and the report has to say so.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "FEM-Bench-Aero"
OUT = Path(__file__).resolve().parent

#: taper neutral, all other axes on their anchors -- only sweep moves
STATIONS = {
    0.0: "naca4412_wingbox",
    10.0: "naca4412_wingbox_sweep10",
    20.0: "naca4412_wingbox_sweep20",
    30.0: "naca4412_wingbox_sweep30",
    40.0: "naca4412_wingbox_sweep40",
}
TARGETS = ("max_disp", "max_w")


def read(cid: str) -> dict:
    p = BENCH / "modeling" / cid / "model.results.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    return {k: float(d[k]) for k in TARGETS}


def poly_eval(xs: list[float], ys: list[float], order: int, at: float) -> float:
    c = np.polyfit(np.asarray(xs, float), np.asarray(ys, float), order)
    return float(np.polyval(c, at))


def ape(pred: float, obs: float) -> float:
    return (pred - obs) / obs * 100.0


def main() -> int:
    fails: list[str] = []
    val = {s: read(cid) for s, cid in STATIONS.items()}
    for s, cid in STATIONS.items():
        if not (BENCH / "modeling" / cid / "model.results.json").exists():
            fails.append(f"missing result for {cid}")
    if fails:
        print("\n".join(fails))
        return 1

    doc: dict = {"stations_deg": sorted(STATIONS), "cases": {str(int(k)): v
                                                            for k, v in STATIONS.items()},
                 "values": {}, "findings": {}, "fails": fails}

    print("=" * 88)
    print("sweep stations (taper 1.0, all other axes on anchor) -- ccx truth")
    print(f"  {'sweep':>6}{'max_disp':>12}{'grow':>8}{'max_w':>12}{'grow':>8}")
    prev = None
    for s in sorted(val):
        row = f"  {s:>6.0f}{val[s]['max_disp']:>12.5f}"
        g1 = val[s]["max_disp"] / val[prev]["max_disp"] if prev is not None else float("nan")
        row += f"{g1:>8.4f}" if prev is not None else f"{'-':>8}"
        row += f"{val[s]['max_w']:>12.5f}"
        g2 = val[s]["max_w"] / val[prev]["max_w"] if prev is not None else float("nan")
        row += f"{g2:>8.4f}" if prev is not None else f"{'-':>8}"
        print(row)
        prev = s
        doc["values"][str(int(s))] = {k: round(v, 6) for k, v in val[s].items()}

    # ---- 1. curvature ------------------------------------------------------ #
    growth = {k: round(val[s][k] / val[0.0][k], 4) for s in sorted(val) for k in TARGETS}
    print("\n[1] value relative to sweep 0 (a straight axis would be a linear ramp)")
    for k in TARGETS:
        seq = [val[s][k] / val[0.0][k] for s in sorted(val)]
        steps = [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]
        print(f"  {k:<9} " + "  ".join(f"{v:6.3f}" for v in seq)
              + "   increments " + " ".join(f"{d:+.3f}" for d in steps))
        doc["findings"].setdefault("curvature", {})[k] = {
            "relative_to_0": [round(v, 4) for v in seq],
            "increments": [round(d, 4) for d in steps],
            "monotone_increasing_increment": all(
                steps[i + 1] > steps[i] for i in range(len(steps) - 1)),
        }
        if not all(steps[i + 1] > steps[i] for i in range(len(steps) - 1)):
            fails.append(f"{k}: increments are not monotonically increasing "
                         f"-> the axis is not super-linear as claimed")

    # ---- 2. the linear extrapolation M7 measured --------------------------- #
    print("\n[2] linear (secant 0-20) continued to 40 -- the M7 number, re-measured")
    for k in TARGETS:
        secant = val[0.0][k] + 2 * (val[20.0][k] - val[0.0][k])
        e = ape(secant, val[40.0][k])
        print(f"  {k:<9} predict {secant:9.5f}  actual {val[40.0][k]:9.5f}"
              f"  {e:+7.1f} %")
        doc["findings"].setdefault("linear_extrapolation", {})[k] = {
            "predicted": round(secant, 6), "actual": round(val[40.0][k], 6),
            "ape_pct": round(e, 2)}

    # ---- 3. is the new station off the old trend? ------------------------- #
    print("\n[3] quadratic through {0, 10, 20} evaluated at 30 -- is the new point informative?")
    for k in TARGETS:
        p30 = poly_eval([0, 10, 20], [val[s][k] for s in (0.0, 10.0, 20.0)], 2, 30)
        e = ape(p30, val[30.0][k])
        print(f"  {k:<9} predict {p30:9.5f}  actual {val[30.0][k]:9.5f}"
              f"  {e:+7.1f} %")
        doc["findings"].setdefault("station_30_vs_old_trend", {})[k] = {
            "predicted": round(p30, 6), "actual": round(val[30.0][k], 6),
            "ape_pct": round(e, 2)}

    # ---- 4. does the 4th station close the gap at 40? --------------------- #
    print("\n[4] extrapolate to 40: 3 stations vs 4 stations")
    print(f"  {'target':<9}{'fit':<26}{'predict':>10}{'actual':>10}{'APE':>9}")
    for k in TARGETS:
        obs = val[40.0][k]
        rows = [
            ("quad {0,10,20}", poly_eval([0, 10, 20],
                                          [val[s][k] for s in (0.0, 10.0, 20.0)], 2, 40)),
            ("quad {0,10,20,30}", poly_eval([0, 10, 20, 30],
                                             [val[s][k] for s in (0.0, 10.0, 20.0, 30.0)],
                                             2, 40)),
            ("cubic {0,10,20,30}", poly_eval([0, 10, 20, 30],
                                              [val[s][k] for s in (0.0, 10.0, 20.0, 30.0)],
                                              3, 40)),
        ]
        store = {}
        for name, pred in rows:
            e = ape(pred, obs)
            print(f"  {k:<9}{name:<26}{pred:>10.5f}{obs:>10.5f}{e:>8.1f}%")
            store[name] = {"predicted": round(pred, 6), "ape_pct": round(e, 2)}
        doc["findings"].setdefault("extrapolation_to_40", {})[k] = store

    verdict = "PASS" if not fails else "CHECK"
    print(f"\nVERDICT: {verdict}  ({len(fails)} failure(s))")
    for f in fails:
        print(f"  - {f}")
    doc["verdict"] = verdict
    p = OUT / "physics_sweep_axis.json"
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {p}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
