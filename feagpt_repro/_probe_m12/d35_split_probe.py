"""D35 前置：把 D15 的「组合即留出」改造成 D31 式二分的**换边影响实测**。

不改 ``feagpt/manifest.py``（那是决策落地时的动作），本脚本只做
monkeypatch 模拟，回答三个问题：

1. 若把 ``_wingbox_swept_and_tapered`` 的条件从「两轴都非中性 ⇒ test」
   改成「两轴都非中性 **且至少一轴出 train 已学值域** ⇒ test」，
   现有 53 条里有几条换边？
2. 换边的是谁、换到哪边、理由是什么？
3. 候选新点 ``sweep30_taper080`` 落在哪边？

判据口径：换边清单必须**完整可见**，不许「大概只有一条」。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "feagpt_repro"))

from feagpt import manifest as mf          # noqa: E402
from feagpt.spec import FEASpec           # noqa: E402

BENCH = ROOT / "FEM-Bench-Aero"
OUT = Path(__file__).resolve().parent
ANCHOR = BENCH / "modeling" / "naca4412_wingbox" / "spec.json"


def _v2(spec) -> str | None:
    """D35 候选规则：组合的两轴都在 train 已学值域内 ⇒ 不是留出。"""
    tr, sw = mf._wingbox_planar_shape(spec)
    if tr == mf.PLANAR_SHAPE_NEUTRAL[0] or sw == mf.PLANAR_SHAPE_NEUTRAL[1]:
        return None
    if sw <= mf.WINGBOX_TRAIN_MAX_SWEEP + 1e-9 and tr >= mf.WINGBOX_TRAIN_MIN_TIP_RATIO - 1e-9:
        return None
    return (f"新平面形状组合（后掠 {sw:g}° × 锥度 {tr:g} 兼具，"
            f"至少一轴出 train 值域 [≤{mf.WINGBOX_TRAIN_MAX_SWEEP:g}°, "
            f"≥{mf.WINGBOX_TRAIN_MIN_TIP_RATIO:g}]）")


def split_v2(spec) -> tuple[str, str]:
    regions = []
    for side, pred in mf.HOLDOUT_REGIONS[mf.family_of(spec)]:
        regions.append((side, _v2 if pred is mf._wingbox_swept_and_tapered else pred))
    for side, pred in regions:
        why = pred(spec)
        if why:
            return side, why
    return mf.TRAIN, "落在训练包络内（未命中任何留出区域）"


def new_spec() -> FEASpec:
    spec = FEASpec.from_json(ANCHOR)
    from dataclasses import replace
    af = replace(spec.airfoil, sweep_deg=30.0, tip_chord_ratio=0.8)
    return replace(spec, name="naca4412_wingbox_sweep30_taper080",
                   description="Default NACA4412 wing box (FeaGPT reproduction)"
                               " | D35 sweep x taper interaction anchor:"
                               " sweep_deg 30, tip_chord_ratio 0.8",
                   airfoil=af)


def main() -> int:
    man = json.loads((BENCH / "manifest.json").read_text(encoding="utf-8"))
    cases = [c["case_id"] for c in man["cases"]]

    moved = []
    for cid in cases:
        spec = FEASpec.from_json(BENCH / "modeling" / cid / "spec.json")
        old_s, old_r = mf.split_of(spec)
        new_s, new_r = split_v2(spec)
        if old_s != new_s:
            moved.append({"case": cid, "family": mf.family_of(spec),
                          "old": old_s, "new": new_s,
                          "old_reason": old_r, "new_reason": new_r})

    print(f"存量 {len(cases)} 条：换边 {len(moved)} 条")
    for m in moved:
        print(f"  {m['case']:<44}{m['old']:>6} -> {m['new']:<6}")
        print(f"     旧: {m['old_reason']}")
        print(f"     新: {m['new_reason']}")

    spec = new_spec()
    s, r = split_v2(spec)
    print(f"\n候选新点 {spec.name}")
    print(f"  sweep={spec.airfoil.sweep_deg:g} taper={spec.airfoil.tip_chord_ratio:g}"
          f"  -> {s}  ({r})")
    if s != mf.TRAIN:
        print("  !! 不是 train，补了等于白补")

    # 换边后的 div 计数
    sides = {}
    for cid in cases:
        spec = FEASpec.from_json(BENCH / "modeling" / cid / "spec.json")
        sides.setdefault(split_v2(spec)[0], []).append(cid)
    sides.setdefault(s, []).append(spec.name)
    print("\n换边 + 新点后的分布：", {k: len(v) for k, v in sorted(sides.items())})

    payload = {"n_cases": len(cases), "moved": moved,
               "candidate": {"name": spec.name,
                             "sweep": float(spec.airfoil.sweep_deg),
                             "taper": float(spec.airfoil.tip_chord_ratio),
                             "split": s, "reason": r},
               "counts_after": {k: len(v) for k, v in sorted(sides.items())}}
    (OUT / "d35_split_probe.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {(OUT / 'd35_split_probe.json').name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
