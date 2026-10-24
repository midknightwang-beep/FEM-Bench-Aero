"""D31 evidence: did sampling span/skin actually teach the model those axes?

The M7 finding that started this batch was a coefficient table: a ridge fit on
13 wing boxes gave `span` and `skin_t` weights of **exactly 0.000**.  Not small -
zero, because both axes were constant across the whole family, so a standardised
regressor has no variance to divide by.  The physics prior `u ~ span^3 / t` then
degenerated into a constant factor absorbed by the intercept, and the "hybrid
beam + ridge" tier (M5) tied the plain ridge tier (M3) to two decimal places.

An accuracy gain alone would not prove the axis was learnt: the test set also
grew, so the two numbers are not comparable on their own.  The coefficient is the
direct evidence, so this script reports it, alongside:

* the measured exponent each coefficient implies (a linear fit in log space with
  a coefficient of 3.0 on log(span) *is* u ~ span^3), against beam theory;
* how much of the sample set each axis now spans (how many distinct values);
* the residual accuracy, so the claim "it works" never floats free of a number.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "feagpt_repro"))
sys.path.insert(0, str(ROOT / "feagpt_repro" / "_probe_m7"))

import numpy as np                                   # noqa: E402

from learnability import (load_family, feat_matrix, FEATS,   # noqa: E402
                          ridge_fit, m3_ridge, m5_hybrid, m2_physics_shape)


def coeffs(rows, target="u"):
    tr = [r for r in rows if r["split"] == "train"]
    ev = [r for r in rows if r["split"] != "train"]
    pred, info = m3_ridge(tr, ev, target)
    X = feat_matrix(tr, [])
    y = np.log(np.array([r[target] for r in tr]))
    mdl = ridge_fit(X, y, info["alpha"])
    return dict(zip(FEATS, mdl[3])), info, tr, ev, pred


def main() -> int:
    rows = load_family("wingbox")
    out = {"n_cases": len(rows),
           "n_train": sum(1 for r in rows if r["split"] == "train"), "targets": {}}

    for target in ("u", "vm"):
        print("=" * 74)
        print(f"target: {target}")
        w, info, tr, ev, pred = coeffs(rows, target)
        print(f"  ridge alpha = {info['alpha']:g}   train LOOCV = {info['loo_mape']:.2f}%")
        # A standardised coefficient is d(log y) per **one standard deviation** of
        # the axis, so it is NOT the exponent.  The exponent is w / sd(log x):
        #     log y = sum_f w_f (log x_f - mean_f)/sd_f  =>  dlog y/dlog x_f = w_f/sd_f
        # Reading w = 0.2 as "the exponent is 0.2" would be a unit error of the
        # same species as the T4 Kt gross/net mix-up: right number, wrong scale.
        sd = {f: float(np.std(feat_matrix(tr, [])[:, FEATS.index(f)]))
              for f in FEATS}
        print("\n  标准化系数与隐含指数（exponent = w / sd(log x)）：")
        print(f"    {'feature':<9}{'w':>8}{'sd':>8}{'implied n':>11}   物理")
        order = sorted(FEATS, key=lambda f: -abs(w[f]))
        phys = {"span": "+3 (u~span^3)", "skin_t": "-1 (u~1/t)"}
        for f in order:
            n = w[f] / sd[f] if sd[f] > 1e-12 else float("nan")
            print(f"    {f:<9}{w[f]:>+8.3f}{sd[f]:>8.3f}{n:>11.3f}   "
                  f"{phys.get(f, '')}")

        # accuracy by split
        va = [r for r in ev if r["split"] == "val"]
        te = [r for r in ev if r["split"] == "test"]
        pv, _ = m3_ridge(tr, va, target)
        pt, _ = m3_ridge(tr, te, target)
        def mape(rs, ps):
            return float(np.mean([abs((p - r[target]) / r[target]) for r, p in zip(rs, ps)])) * 100
        print(f"\n  M3 岭回归: val MAPE {mape(va, pv):.2f}%   test MAPE {mape(te, pt):.2f}%")

        # axis coverage
        print("\n  各轴在样本里的取值个数：")
        cov = {}
        for f in ("span", "skin_t", "chord", "n_ribs", "sweep", "taper"):
            vals = sorted({round(float(r[f]), 6) for r in rows})
            cov[f] = len(vals)
            show = vals if len(vals) <= 6 else vals[:3] + ["..."] + vals[-2:]
            print(f"    {f:<8}{len(vals):>2} 种  {show}")
        implied = {f: (w[f] / sd[f] if sd[f] > 1e-12 else None) for f in FEATS}
        out["targets"][target] = {
            "implied_exponent": {k: (round(float(v), 4) if v is not None else None)
                                 for k, v in implied.items()},
            "alpha": float(info["alpha"]),
            "train_loocv_mape": round(float(info["loo_mape"]), 3),
            "coef": {k: round(float(v), 4) for k, v in w.items()},
            "val_mape": round(mape(va, pv), 3),
            "test_mape": round(mape(te, pt), 3),
            "axis_coverage": cov,
        }
        print()

    # ---- weak-regularisation control ------------------------------------- #
    # The alpha chosen by LOOCV trades bias for variance; with 17 samples it
    # shrinks the exponents towards zero.  Refitting at alpha -> 0 shows how much
    # of the gap to the physics is shrinkage and how much is the model.
    tr_all = [r for r in rows if r["split"] == "train"]
    X = feat_matrix(tr_all, [])
    y = np.log(np.array([r["u"] for r in tr_all]))
    w0 = ridge_fit(X, y, 1e-8)[3]
    sd0 = {f: float(np.std(X[:, FEATS.index(f)])) for f in FEATS}
    print("=" * 74)
    print("弱正则对照（alpha = 1e-8，几乎无收缩）——看指数是否回到物理值：")
    for f in ("span", "skin_t"):
        print(f"  {f:<8} w={w0[FEATS.index(f)]:+.3f}  "
              f"隐含 n = {w0[FEATS.index(f)] / sd0[f]:+.3f}")
    out["weak_reg"] = {f: round(float(w0[FEATS.index(f)] / sd0[f]), 4)
                       for f in ("span", "skin_t")}

    # ---- the headline: are span / skin_t awake? -------------------------- #
    ud = out["targets"]["u"]["coef"]
    ui = out["targets"]["u"]["implied_exponent"]
    span_w, skin_w = ud["span"], ud["skin_t"]
    awake = abs(span_w) > 1e-6 and abs(skin_w) > 1e-6
    print("=" * 74)
    print(f"原始标准化系数 span {span_w:+.3f} / skin_t {skin_w:+.3f}"
          f"   -> {'两轴已醒' if awake else '仍为 0'}")
    print(f"隐含指数     span {ui['span']:+.3f}（物理 +3，偏差 "
          f"{(ui['span'] / 3 - 1) * 100:+.1f}%）")
    print(f"             skin {ui['skin_t']:+.3f}（物理 -1，偏差 "
          f"{(ui['skin_t'] / -1 - 1) * 100:+.1f}%）")
    print(f"             chord {ui['chord']:+.3f}（物理 -3，独立旁证）")
    # M5 vs M3 separation: the prior can only earn its keep once the axis is live
    tr = [r for r in rows if r["split"] == "train"]
    te = [r for r in rows if r["split"] == "test"]
    p3 = m3_ridge(tr, te, "u")[0]
    p5 = m5_hybrid(tr, te, "u")[0]
    m3e = float(np.mean([abs((p - r["u"]) / r["u"]) for r, p in zip(te, p3)])) * 100
    m5e = float(np.mean([abs((p - r["u"]) / r["u"]) for r, p in zip(te, p5)])) * 100
    print(f"test MAPE：M3 {m3e:.2f}%  vs  M5（梁先验）{m5e:.2f}%  "
          f"-> {'先验开始起作用' if abs(m5e - m3e) > 0.5 else '仍无差别（先验被截距吸收）'}")

    out["span_coef"] = span_w
    out["skin_coef"] = skin_w
    out["span_exponent_implied"] = ui["span"]
    out["skin_exponent_implied"] = ui["skin_t"]
    out["chord_exponent_implied"] = ui["chord"]
    out["axes_awake"] = awake
    out["m3_test_mape"] = round(m3e, 3)
    out["m5_test_mape"] = round(m5e, 3)
    p = ROOT / "FEM-Bench-Aero" / "m8_d31_coefficients.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
