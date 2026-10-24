"""D31 reconnaissance: wing-box size axes (span, skin_thickness).

Read-only probe.  Two questions, both answered by measurement rather than by
reading the code:

1. Would a new "size axis" rule change the split of any of the 23 archived
   wing boxes?  The split is frozen (D12), so the answer must be **zero**.
2. What does the rule say about the candidate new points?

The rule under test is *not* D30's "count the axes off the anchor" reading.
That reading is right for the open-hole family, whose train set is a single
point (the anchor itself).  The wing box is different: chord 800 and 1000 are
both in train, ribs 3 and 5 are both in train - train covers an *interval* on
several axes, not a point.  So the wing box reads a per-axis train envelope,
and only an *excursion outside* that envelope counts as an axis leaving train.

That is also why span and skin_thickness need an explicit decision: today their
envelope is the single value 2000 / 3.0 (all 23 cases agree), so "the model has
learnt span" is meaningless - it has seen one value.  D25 met the same thing on
the barrel and answered with an exact anchor *precisely because* a continuous
axis sampled once has no interior.  The way out is the way in: sample the axis a
few times, and only then can an interior be claimed.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "feagpt_repro"))

from feagpt.spec import FEASpec                      # noqa: E402
from feagpt.manifest import split_of, infer_role      # noqa: E402

BENCH = ROOT / "FEM-Bench-Aero"

# --------------------------------------------------------------------------- #
# the rule under test
# --------------------------------------------------------------------------- #
#: Span range train is to cover (inclusive).  Three stations: 1600 / 2000 / 2400.
TRAIN_SPAN = (1600.0, 2400.0)
#: Skin thickness range train is to cover (inclusive).  Three plates: 2 / 3 / 4.
TRAIN_SKIN = (2.0, 4.0)


def size_axes_off(spec) -> list[str]:
    """Wing-box size axes sitting *outside* the train envelope."""
    if getattr(spec.structure, "family", "") != "wingbox":
        return []
    af = spec.airfoil
    out = []
    span = float(af.span)
    skin = float(af.skin_thickness)
    if not (TRAIN_SPAN[0] - 1e-9 <= span <= TRAIN_SPAN[1] + 1e-9):
        out.append(f"span {span:g} 出训练包络 [{TRAIN_SPAN[0]:g},{TRAIN_SPAN[1]:g}]")
    if not (TRAIN_SKIN[0] - 1e-9 <= skin <= TRAIN_SKIN[1] + 1e-9):
        out.append(f"壁厚 {skin:g} 出训练包络 [{TRAIN_SKIN[0]:g},{TRAIN_SKIN[1]:g}]")
    return out


def other_axes_off(spec) -> list[str]:
    """The axes D14/D24/D25 already police, read at their *existing* anchors.

    Copied here (not imported) on purpose: this probe must be able to run
    against the *old* rule set, so it cannot depend on the new one existing.
    """
    if getattr(spec.structure, "family", "") != "wingbox":
        return []
    af = spec.airfoil
    out = []
    if int(af.n_ribs) > 5:
        out.append(f"ribs {int(af.n_ribs)} > 5")
    if float(getattr(af, "sweep_deg", 0.0) or 0.0) > 20.0:
        out.append(f"sweep {float(af.sweep_deg):g} > 20")
    if float(getattr(af, "tip_chord_ratio", 1.0) or 1.0) < 0.6:
        out.append(f"tcr {float(af.tip_chord_ratio):g} < 0.6")
    try:
        if int(af.n_webs) > 1:
            out.append(f"webs {int(af.n_webs)} > 1")
    except AttributeError:
        pass
    nstr = int(getattr(af, "n_stringers_per_skin", 0) or 0)
    kind = str(getattr(af, "stringer_kind", "blade") or "blade")
    if nstr > 0 and kind != "blade":
        out.append(f"stringer 形式 {kind!r}")
    return out


def predicted_split(spec) -> tuple[str, str]:
    """What the candidate D31 rule would say (0 axes -> fall back to today)."""
    sz = size_axes_off(spec)
    ot = other_axes_off(spec)
    n = len(sz) + len(ot)
    if len(sz) >= 2:
        return "test", f"尺寸双轴外推（{'；'.join(sz)}）"
    if len(sz) == 1:
        if ot:
            return "test", f"尺寸 × 他轴双维外推（{'；'.join(sz + ot)}）"
        return "val", f"尺寸单维外推（{sz[0]}）"
    return None, ""


# --------------------------------------------------------------------------- #
# 1. does the rule touch any archived case?
# --------------------------------------------------------------------------- #
def load_archived() -> list[tuple[str, FEASpec]]:
    out = []
    for p in sorted(glob.glob(str(BENCH / "modeling" / "*" / "spec.json"))):
        cid = os.path.basename(os.path.dirname(p))
        out.append((cid, FEASpec.from_json(Path(p))))
    return out


def main() -> int:
    cases = load_archived()
    wb = [(c, s) for c, s in cases if getattr(s.structure, "family", "") == "wingbox"]
    print(f"归档翼盒 {len(wb)} 条 / 全库 {len(cases)} 条\n")

    print("=== 1. 新规则对存量案例的影响 ===")
    changed = []
    for cid, spec in cases:
        old, why = split_of(spec), ""
        new, nwhy = predicted_split(spec)
        if new is None:
            continue
        if new != old:
            changed.append((cid, old, new))
        print(f"  {cid:<46}{old:<7}-> {new:<6} 命中")
    print(f"\n  存量命中新谓词：{len(changed)} 条；split 变化：{len(changed)} 条")
    if changed:
        for cid, o, n in changed:
            print(f"    ! {cid}: {o} -> {n}")
    ok_stock = not changed

    # ------------------------------------------------------------------ #
    # 2. candidate points
    # ------------------------------------------------------------------ #
    anchor = next(s for c, s in wb if c == "naca4412_wingbox")
    base_af = replace(anchor.airfoil)

    #: (tag, span, skin, extra airfoil overrides, intent)
    CAND = [
        ("span1600",       1600.0, 3.0, {}, "train 低档"),
        ("span2400",       2400.0, 3.0, {}, "train 高档"),
        ("skin2",          2000.0, 2.0, {}, "train 薄壁"),
        ("skin4",          2000.0, 4.0, {}, "train 厚壁"),
        ("span3000",       3000.0, 3.0, {}, "超包络单轴 -> val"),
        ("skin1p5",        2000.0, 1.5, {}, "超包络单轴 -> val"),
        ("span3000_skin1p5", 3000.0, 1.5, {}, "超包络双轴 -> test"),
        ("span2400_skin2", 2400.0, 2.0, {}, "包络内双轴组合 -> ?"),
        ("span3000_ribs7", 3000.0, 3.0, {"n_ribs": 7}, "尺寸 x ribs -> test"),
    ]
    print("=== 2. 候选点位预测（规则判定，未求解）===")
    print(f"{'tag':<20}{'span':>7}{'skin':>6}{'ribs':>6}  {'split':<6}{'reason'}")
    rows = []
    for tag, span, skin, extra, intent in CAND:
        af = replace(base_af, span=span, skin_thickness=skin, **extra)
        spec = replace(anchor, name=tag, airfoil=af)
        sp, why = predicted_split(spec)
        sp = sp or "train"
        rows.append(dict(tag=tag, span=span, skin=skin, extra=extra,
                         split=sp, reason=why or "落在训练包络内",
                         intent=intent, role=infer_role(spec)))
        print(f"{tag:<20}{span:>7.0f}{skin:>6.1f}"
              f"{int(af.n_ribs):>6}  {sp:<6}{why or '落在训练包络内（默认）'}")

    # ------------------------------------------------------------------ #
    # 3. will the thickness axis be observable here?
    # ------------------------------------------------------------------ #
    print("\n=== 3. 厚度轴可观测性（与 T7 的对照）===")
    truth = {}
    for c, s in wb:
        t = json.loads((BENCH / "modeling" / c / "truth.json").read_text(encoding="utf-8"))
        truth[c] = t.get("scalars", t)
    u0 = truth["naca4412_wingbox"]["max_disp"]
    F = float(anchor.load.magnitude)
    print(f"  锚点：span 2000, skin 3.0, 翼尖集中力 F = {F:g} N（**不随厚度缩放**）")
    print(f"        max|u| = {u0:.4f} mm")
    for t in (2.0, 4.0):
        est = u0 * (3.0 / t)          # membrane-dominated: u ~ 1/t
        est3 = u0 * (3.0 / t) ** 3    # bending-dominated: u ~ 1/t^3
        print(f"        skin {t:g} mm 预测 max|u| ≈ {est:.4f}（1/t 膜）或 {est3:.4f}（1/t³ 弯）")
    print("  对照 T7 开口板：载荷 F = σ·w·t ∝ t 与膜刚度 EA ∝ t 精确抵消 ⇒ 零区分度。")
    print("  翼盒载荷是**固定 500 N 翼尖力**，不随 t 缩放 ⇒ 厚度必然改变响应（这才是可观测的厚度维）。")

    out = ROOT / "feagpt_repro" / "_probe_m8" / "probe_d31.json"
    out.write_text(json.dumps({
        "stock_hits": len(changed),
        "stock_split_changes": len(changed),
        "rule_is_non_disruptive": ok_stock,
        "train_span": list(TRAIN_SPAN),
        "train_skin": list(TRAIN_SKIN),
        "candidates": rows,
        "anchor_u": u0,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n落盘：{out}")
    return 0 if ok_stock else 1


if __name__ == "__main__":
    sys.exit(main())
