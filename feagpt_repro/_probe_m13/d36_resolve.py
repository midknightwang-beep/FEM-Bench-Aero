"""D36: close the pre-registration -- measured value against the frozen prediction.

``d36_prediction_preregistered.json`` is **never rewritten**.  It is the record
of what the model claimed before the solve existed, and the only way it stays
worth anything is if a later script cannot touch it.  This script reads it, reads
the measured ``truth.json``, and writes a *separate* ``..._resolved.json``.

What the numbers mean:

* the model's error at 35 is an **honest out-of-sample error** -- 35 was outside
  train when the prediction was made, so this is not an in-sample residual;
* sign convention: negative = model under-predicts the deflection;
* the measured value being *above* every prediction is the interesting case: it
  says the 30 -> 40 region is under-predicted as a whole, not just at 40, which
  is a different disease from "one bad station" and it is the one that a station
  at 35 can actually treat.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
TRUTH = OUT / "outputs" / "naca4412_wingbox_sweep35" / "naca4412_wingbox_sweep35.truth.json"


def sape(pred: float, obs: float) -> float:
    return (pred - obs) / obs * 100.0


def main() -> int:
    pre = json.loads((OUT / "d36_prediction_preregistered.json").read_text(encoding="utf-8"))
    truth = json.loads(TRUTH.read_text(encoding="utf-8"))
    sc = truth["scalars"]
    obs35 = float(sc["max_disp"])
    print(f"measured max_disp @ sweep35 = {obs35:.5f} mm  (node {sc['max_disp_node']}, "
          f"{sc['n_nodes']} nodes)")

    res = {
        "probe": "D36 prediction resolved against measurement",
        "preregistered_file": "d36_prediction_preregistered.json (unmodified)",
        "measured": {"max_disp": obs35,
                     "max_w": float(sc["max_w"]),
                     "max_von_mises": float(sc["max_von_mises"]),
                     "max_von_mises_midsurface": float(sc["max_von_mises_midsurface"]),
                     "n_nodes": int(sc["n_nodes"]),
                     "node": int(sc["max_disp_node"])},
        "scores": {},
    }

    print(f"\n{'estimate':<34}{'pred (mm)':>12}{'APE vs measured':>18}")
    for tier in ("M3q", "M5q"):
        p = float(pre[tier]["sweep35"]["pred"])
        e = sape(p, obs35)
        res["scores"][tier] = {"pred": p, "ape": e}
        print(f"{tier + ' (ridge, D35 dataset)':<34}{p:>12.5f}{e:>17.2f}%")
    q = float(pre["independent_quad_0123"]["pred_35"])
    res["scores"]["parabola_0123"] = {"pred": q, "ape": sape(q, obs35)}
    print(f"{'parabola through 0/10/20/30':<34}{q:>12.5f}{sape(q, obs35):>17.2f}%")

    worst = max(res["scores"].items(), key=lambda kv: abs(kv[1]["ape"]))
    above = all(res["scores"][k]["ape"] < 0 for k in res["scores"])
    print(f"\nworst estimator: {worst[0]} ({worst[1]['ape']:+.2f} %)")
    print(f"every estimate under-predicts: {above}")
    res["all_under_predict"] = above
    res["worst"] = {"name": worst[0], "ape": worst[1]["ape"]}

    # ratio table on the taper-neutral line -- the whole point of the station
    ratios = pre["independent_quad_0123"]["ratios_vs_0"]
    res["taper_neutral_ratios"] = {
        "stations": [0, 10, 20, 30, 35, 40],
        "ratio": list(ratios[:4]) + [obs35 / (ratios[0] * 0 + 1.0) / 1.0, ratios[4]],
    }
    u0 = None
    for p in pre["independent_quad_0123"]["points"]:
        if p["sweep"] == 0.0:
            u0 = float(p["obs"])
    if u0:
        r35 = obs35 / u0
        res["taper_neutral_ratios"]["ratio"][4] = r35
        print(f"\ntaper-neutral ratio vs 0 deg: 35 deg -> {r35:.4f} "
              f"(30 deg {ratios[3]:.4f}, 40 deg {ratios[4]:.4f})")
        # increment growth: is the axis still steepening between 30 and 40?
        inc = [ratios[1] - ratios[0], ratios[2] - ratios[1],
               ratios[3] - ratios[2], r35 - ratios[3], ratios[4] - r35]
        res["increments"] = {"between": ["0-10", "10-20", "20-30", "30-35", "35-40"],
                             "delta": inc}
        print("increments: " + " / ".join(f"{d:+.4f}" for d in inc))
        # per-degree slope, which is what "superlinear" has to mean
        slope = [inc[0] / 10, inc[1] / 10, inc[2] / 10, inc[3] / 5, inc[4] / 5]
        res["slope_per_deg"] = {"between": ["0-10", "10-20", "20-30", "30-35", "35-40"],
                                "slope": slope}
        print("slope per deg: " + " / ".join(f"{s:.5f}" for s in slope) +
              f"   (30-35 -> 35-40 change {sape(slope[4], slope[3]):+.2f} %)")

    p = OUT / "d36_prediction_resolved.json"
    p.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
