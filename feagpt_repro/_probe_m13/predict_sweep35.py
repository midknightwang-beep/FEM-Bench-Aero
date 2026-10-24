"""D36: state the model's prediction at 35 deg BEFORE the solve exists.

This is a pre-registration, not a diagnostic.  The point of adding a station is
to find out whether the pure-sweep curvature is currently wrong; if the
prediction is written down *after* the measurement, any answer can be narrated
as a success.  So this runs first and the JSON is the evidence of what was
claimed.

Three numbers come out, and the third is what makes the other two trustworthy:

1. ``pred_35``  -- what the D35 model (54 cases, ``M5q`` / ``M3q``, quad sweep)
   says the tip deflection will be at sweep 35, taper neutral.
2. ``pred_40``  -- the same model at the existing val point.  The measured value
   there is known, so this doubles as a **self-check of the harness**: if it
   does not reproduce the -12.79 % that ``same_test_set.py`` reported for
   ``sweep40``(val), this script is not measuring the model the report cites
   and nothing else it prints may be used.
3. ``quad0123_at_35`` -- an *independent* estimate: a parabola through the four
   **measured** taper-neutral stations 0/10/20/30, evaluated at 35.  It shares
   no code path with the ridge model (no features, no standardisation, no
   alpha), so agreement between it and ``pred_35`` means the point is
   confirmatory; disagreement means the point carries real information.

Also printed: ``quad0123_at_40`` -- the same parabola at 40.  Its error against
the measured 40 is the *pure-sweep* curvature bias, i.e. exactly the quantity a
station at 35 is meant to shrink.  If that bias is already small, D36 is a
wasted solve and should be dropped rather than run out of habit.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "feagpt_repro"))

import numpy as np                                    # noqa: E402

from baseline import fit_m3, fit_m5, load_family, _alpha_grid   # noqa: E402

OUT = Path(__file__).resolve().parent
BENCH = ROOT / "FEM-Bench-Aero"
KEY = "max_disp"


def sape(pred: float, obs: float) -> float:
    """Signed relative error in percent -- sign matters here (over/under)."""
    return (pred - obs) / obs * 100.0


def anchor_row() -> dict:
    """The wing-box anchor, as a feature row with no targets."""
    spec = json.loads((BENCH / "modeling" / "naca4412_wingbox" / "spec.json")
                      .read_text(encoding="utf-8"))
    a = spec["airfoil"]
    return {
        "case_id": "naca4412_wingbox_sweep35",
        "chord": float(a["chord"]),
        "span": float(a["span"]),
        "skin_t": float(a["skin_thickness"]),
        "n_ribs": float(a["n_ribs"]),
        "n_str": float(a["n_stringers_per_skin"]),
        "is_T": 1.0 if a.get("stringer_kind") == "T" else 0.0,
        "web_pos": float((a.get("web_chordwise") or [0.0])[0]),
        "n_web": float(len(a.get("web_chordwise") or [])),
        "E": float(spec["material"]["youngs_modulus"]),
        "F": float(spec["load"]["magnitude"]),
    }


def with_planform(base: dict, sweep: float, taper: float = 1.0) -> dict:
    r = dict(base)
    r["sweep"] = float(sweep)
    r["taper"] = float(taper)
    return r


def quad_through(pts: list[tuple[float, float]]):
    """Least-squares parabola through measured (sweep, u) points."""
    A = np.array([[s * s, s, 1.0] for s, _ in pts])
    b = np.array([u for _, u in pts])
    coef, *_ = np.linalg.lstsq(A, b, rcond=None)
    return lambda s: float(coef[0] * s * s + coef[1] * s + coef[2])


def main() -> int:
    rows = load_family("wingbox")
    tr = [r for r in rows if r["split"] == "train"]
    va = [r for r in rows if r["split"] == "val"]
    te = [r for r in rows if r["split"] == "test"]
    print(f"dataset: {len(rows)} wingbox cases -> train {len(tr)} / val {len(va)} / test {len(te)}")

    grid = _alpha_grid()
    base = anchor_row()
    probe35 = [with_planform(base, 35.0)]
    probe40 = [with_planform(base, 40.0)]

    out: dict = {"probe": "D36 blind prediction at sweep 35 deg",
                 "dataset": {"n": len(rows), "train": len(tr),
                             "val": len(va), "test": len(te)},
                 "target": KEY}

    # -- harness self-check: reproduce the published sweep40 (val) error ----- #
    def truth_of(cid: str, rows_):
        for r in rows_:
            if r["case_id"] == cid:
                return r[KEY]
        raise KeyError(cid)

    u40_val = truth_of("naca4412_wingbox_sweep40", va)
    u30 = truth_of("naca4412_wingbox_sweep30", tr)
    u0 = truth_of("naca4412_wingbox", tr)
    print(f"measured taper-neutral: 0 deg {u0:.5f} / 30 deg {u30:.5f} / 40 deg {u40_val:.5f} mm")

    fails: list[str] = []
    for tier, fitter in (("M3q", lambda: fit_m3(tr, KEY, grid, quad=True)),
                         ("M5q", lambda: fit_m5(tr, KEY, "u", grid, quad=True))):
        pred, info = fitter()
        p35 = float(pred(probe35)[0])
        p40 = float(pred(probe40)[0])
        e40 = sape(p40, u40_val)
        p30 = float(pred([r for r in tr if r["case_id"] == "naca4412_wingbox_sweep30"])[0])
        e30 = sape(p30, u30)
        print(f"\n[{tier}] alpha={info['alpha']:.4g} trainLOO={info['loo_mape']:.2f} %")
        print(f"    30 deg  pred {p30:.5f}  obs {u30:.5f}  APE {e30:+.2f} %   (in-sample)")
        print(f"    35 deg  pred {p35:.5f}  obs <not measured yet>")
        print(f"    40 deg  pred {p40:.5f}  obs {u40_val:.5f}  APE {e40:+.2f} %   (val, kill-check)")
        out[tier] = {"alpha": info["alpha"], "train_loo_mape": info["loo_mape"],
                     "sweep30": {"pred": p30, "obs": u30, "ape": e30, "role": "train-in-sample"},
                     "sweep35": {"pred": p35, "obs": None},
                     "sweep40": {"pred": p40, "obs": u40_val, "ape": e40, "role": "val"}}

    # -- kill-check on the published number --------------------------------- #
    m5_e40 = out["M5q"]["sweep40"]["ape"]
    print(f"\n[kill-check] M5q at sweep40(val): {m5_e40:+.2f} %  "
          f"(published in same_test_set_d35.json; must be about -12.8 %)")
    if abs(m5_e40 + 12.79) > 1.0:
        fails.append(f"harness does not reproduce the published sweep40(val) error: "
                     f"{m5_e40:+.2f} % vs about -12.79 %")

    # -- independent, measured-only estimate -------------------------------- #
    pts = [(0.0, u0), (10.0, truth_of("naca4412_wingbox_sweep10", tr)),
           (20.0, truth_of("naca4412_wingbox_sweep20", tr)), (30.0, u30)]
    q = quad_through(pts)
    q35, q40 = q(35.0), q(40.0)
    q30 = q(30.0)
    print("\n[independent] parabola through measured 0/10/20/30 deg taper-neutral:")
    print(f"    fit at 30 deg {q30:.5f} (obs {u30:.5f}, {sape(q30, u30):+.2f} % - fit residual)")
    print(f"    at 35 deg     {q35:.5f}")
    print(f"    at 40 deg     {q40:.5f}   obs {u40_val:.5f}  APE {sape(q40, u40_val):+.2f} %")
    print(f"    ratios vs 0 deg: " + " / ".join(
        f"{u0 and v / u0:.4f}" for v in (u0, pts[1][1], pts[2][1], u30, u40_val)))

    out["independent_quad_0123"] = {
        "points": [{"sweep": s, "obs": v} for s, v in pts],
        "pred_30": q30, "pred_35": q35, "pred_40": q40,
        "ape_40": sape(q40, u40_val),
        "ratios_vs_0": [v / u0 for _, v in pts] + [u40_val / u0],
    }

    # -- how far apart are the two estimates? ------------------------------- #
    for tier in ("M3q", "M5q"):
        gap = sape(out[tier]["sweep35"]["pred"], q35)
        print(f"[agreement] {tier} vs measured-only parabola at 35 deg: {gap:+.2f} % apart")
        out[tier]["sweep35"]["gap_vs_measured_parabola"] = gap

    out["verdict"] = "PASS" if not fails else "CHECK"
    out["fails"] = fails
    print(f"\nVERDICT: {out['verdict']}  ({len(fails)} failure(s))")
    for f in fails:
        print(f"  - {f}")

    p = OUT / "d36_prediction_preregistered.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {p}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
