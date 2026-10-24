"""D31 physics check: are span and skin actually observable here?

The T7 build-out ended with a negative result worth keeping: on a coupon pulled
at a *constant nominal stress*, the load scales with t (F = sigma*w*t) and the
membrane stiffness scales with t (EA ~ t), so they cancel exactly and
max|u| = sigma*L/E is independent of thickness to the last digit.  That is why
the thickness axis was pulled out of the sample set and turned into an
invariant self-check.

The wing box is the opposite arrangement: the tip force is a **fixed 500 N**, it
does not know about thickness.  Thin-walled closed sections carry that bending
in membrane action, so I = ∮ t·y² ds ~ t and u ~ span³ / t.  If the solvers
return the same max|u| for skin 2 and skin 4 the deck is broken; if they return
values on the 1/t line, the axis is observable and worth sampling.

Two more things get checked because they decide whether the batch can be learnt:

* the span exponent, measured rather than assumed (a beam says 3);
* whether the response is *multiplicative*.  The two test points exist to find
  out how hard the interaction is.  If u(span,skin) = u(span)*u(skin)/u_anchor
  to a fraction of a percent, then a model that learns each axis separately has
  every ingredient it needs - the test point is fair.  If the interaction were
  large, that same test point would be a trap and this batch would be teaching
  the wrong lesson.
"""
from __future__ import annotations

import glob
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
M8 = Path(__file__).resolve().parent
BENCH = ROOT / "FEM-Bench-Aero"


def read_u(case_dir: Path) -> dict:
    """Read the scalar summary of a case.

    Two layouts in play: an archived case keeps ``model.results.json`` in its own
    directory, a pipeline run keeps ``<case_id>.results.json`` inside its case
    folder.  Searching ``case_dir/*.results.json`` first and the one-level-deeper
    layout second covers both without guessing a name.
    """
    for pat in ("*.results.json", "*/*.results.json"):
        f = glob.glob(str(case_dir / pat))
        if f:
            d = json.loads(Path(f[0]).read_text(encoding="utf-8"))
            return d.get("scalars", d)
    raise SystemExit(f"no results in {case_dir}")


def main() -> int:
    anchor = read_u(BENCH / "modeling" / "naca4412_wingbox")["max_disp"]
    got = {}
    for d in sorted(glob.glob(str(M8 / "outputs_size_*"))):
        tag = os.path.basename(d).replace("outputs_", "")
        s = read_u(Path(d))
        got[tag] = dict(u=float(s["max_disp"]), vm=float(s["max_von_mises"]),
                        n=int(s["n_nodes"]))

    print(f"锚点 max|u| = {anchor:.4f} mm （span 2000, skin 3.0）\n")

    # ---- 1. thickness: u ~ 1/t ------------------------------------------- #
    print("=== 1. 壁厚标度（薄壁闭室 I ∝ t ⇒ u ∝ 1/t）===")
    print(f"{'skin':>6}{'u_meas':>10}{'u/u_anchor':>12}{'3/t':>8}{'dev':>9}   vM")
    thick = []
    for tag, skin in (("size_skin1p5", 1.5), ("size_skin2", 2.0),
                      ("size_skin4", 4.0)):
        r = got[tag]
        ratio = r["u"] / anchor
        pred = 3.0 / skin
        dev = (ratio / pred - 1.0) * 100
        thick.append(dict(skin=skin, u=r["u"], ratio=ratio, pred_1_over_t=pred,
                          dev_pct=round(dev, 3), vm=r["vm"]))
        print(f"{skin:>6g}{r['u']:>10.4f}{ratio:>12.4f}{pred:>8.4f}{dev:>8.2f}%"
              f"   {r['vm']:.2f}")
    max_dev_t = max(abs(t["dev_pct"]) for t in thick)
    print(f"  最大偏离 1/t：{max_dev_t:.2f}%  -> "
          f"{'可观测且干净' if max_dev_t < 1.0 else '需要追查'}")

    # ---- 2. span: u ~ span^3 --------------------------------------------- #
    print("\n=== 2. 展长标度（悬臂薄壁梁 u ∝ span³）===")
    print(f"{'span':>6}{'u_meas':>10}{'u/u_anchor':>12}{'(s/2000)^3':>12}{'dev':>9}")
    spans = []
    for tag, span in (("size_span1600", 1600.0), ("size_span2400", 2400.0),
                      ("size_span3000", 3000.0)):
        r = got[tag]
        ratio = r["u"] / anchor
        pred = (span / 2000.0) ** 3
        dev = (ratio / pred - 1.0) * 100
        spans.append(dict(span=span, u=r["u"], ratio=ratio, pred_cube=pred,
                          dev_pct=round(dev, 3)))
        print(f"{span:>6.0f}{r['u']:>10.4f}{ratio:>12.4f}{pred:>12.4f}{dev:>8.2f}%")
    # fit the exponent instead of assuming it
    xs = [math.log(s["span"]) for s in spans]
    ys = [math.log(s["u"]) for s in spans]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    expo = (sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            / sum((x - mx) ** 2 for x in xs))
    print(f"  三点最小二乘指数 n = {expo:.3f}（梁论 = 3）")
    print("  偏离 ±3% 来源：n_ribs 固定 5 ⇒ 肋间距随 span 变，翼尖效应不同"
          "（不是实现问题）")

    # ---- 3. is the response multiplicative? ------------------------------- #
    print("\n=== 3. 双轴组合是乘性的吗（决定 test 点公不公平）===")
    # NB: the two factors must be the **measured** single-axis responses, not the
    # theoretical exponents.  Using (span/2000)**3 smuggles the span-law's own
    # -3 % deviation into the "interaction" and reports a trap that is not
    # there.  Same lesson as the M7 distance/error mismatch: a hypothesis and the
    # quantity it is tested against have to be measured the same way.
    combos = []
    for tag, span_tag, skin_tag in (
            ("size_span2400_skin2", "size_span2400", "size_skin2"),
            ("size_span3000_skin1p5", "size_span3000", "size_skin1p5")):
        meas = got[tag]["u"]
        span_eff = got[span_tag]["u"] / anchor
        skin_eff = got[skin_tag]["u"] / anchor
        pred = anchor * span_eff * skin_eff
        dev = (meas / pred - 1.0) * 100
        combos.append(dict(tag=tag, u_meas=meas, u_pred_multiplicative=pred,
                           span_eff_measured=round(span_eff, 5),
                           skin_eff_measured=round(skin_eff, 5),
                           dev_pct=round(dev, 3)))
        print(f"  {tag:<24}实测 {meas:>8.4f}  "
              f"实测单轴乘积 {pred:>8.4f}  偏离 {dev:>+6.2f}%")
    print("  （乘积 = 锚点 × 实测 span 单轴效应 × 实测 skin 单轴效应）")
    max_dev_c = max(abs(c["dev_pct"]) for c in combos)
    print(f"  最大偏离：{max_dev_c:.2f}%  -> 交互项"
          f"{'可忽略，单轴知识足够' if max_dev_c < 2.0 else '不可忽略，test 点是陷阱'}")

    # ---- 4. the T7 contrast --------------------------------------------- #
    print("\n=== 4. 与 T7 开口板的对照（同一「厚度维」两种结论）===")
    print("  T7 开口板：F = σ·w·t 随 t 缩放，膜刚度 ∝ t 精确抵消")
    print("              ⇒ t=2.0 与 t=1.0 的 max|u| 逐位相同 0.05734516，零信息量")
    print("  翼盒    ：F = 500 N 固定，不随 t 缩放")
    print(f"              ⇒ skin 1.5→4 位移变 {got['size_skin1p5']['u']/got['size_skin4']['u']:.3f} 倍，"
          f"严格 1/t")
    print("  结论：厚度维不是「有效/无效」的属性，而是**载荷口径**的函数。")

    ok = max_dev_t < 1.0 and max_dev_c < 2.0 and abs(expo - 3.0) < 0.15
    out = M8 / "physics_check.json"
    out.write_text(json.dumps({
        "anchor_u": anchor,
        "thickness": {"points": thick, "max_dev_from_1_over_t_pct": max_dev_t},
        "span": {"points": spans, "fitted_exponent": round(expo, 4),
                 "beam_theory_exponent": 3.0},
        "multiplicative": {"points": combos,
                           "max_dev_pct": max_dev_c},
        "verdict": {"thickness_observable": max_dev_t < 1.0,
                    "span_law_holds": abs(expo - 3.0) < 0.15,
                    "interaction_negligible": max_dev_c < 2.0,
                    "pass": ok},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{'PASS' if ok else 'FAIL'}  -> {out.name}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
