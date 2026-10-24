"""D35 前置普查：翼盒族的 (sweep, taper) 联合分布 + 各自的 split。

为什么要普查：D34 的残差诊断（``_probe_m11/residual_diag.py``）证明
「sweep>0 且 taper≠1」在 train 上 **0 条**，所以 ``s^2*(taper-1)`` 恒为零、
交互项不可估。要补这个空位，先得知道空位在哪儿、有多大，以及现有 test 点
靠什么机制被判成 test —— 否则补完还是会被同一条规则判进 test。

输出：``planar_census.json``
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "feagpt_repro"))

from feagpt.manifest import split_of          # noqa: E402
from feagpt.spec import FEASpec               # noqa: E402

BENCH = ROOT / "FEM-Bench-Aero"
OUT = Path(__file__).resolve().parent

AXES = ("sweep", "taper", "span", "skin", "ribs", "chord", "n_web")


def read_case(cid: str) -> dict:
    spec = FEASpec.from_json(BENCH / "modeling" / cid / "spec.json")
    af = spec.airfoil
    split, reason = split_of(spec)
    return {
        "case": cid,
        "split": split,
        "reason": reason,
        "sweep": float(getattr(af, "sweep_deg", 0.0) or 0.0),
        "taper": float(getattr(af, "tip_chord_ratio", 1.0) or 1.0),
        "span": float(af.span),
        "skin": float(af.skin_thickness),
        "ribs": int(getattr(af, "n_ribs", 5)),
        "chord": float(getattr(af, "chord", 1000.0)),
        "n_web": int(getattr(af, "n_webs", 0) or 0),
    }


def main() -> int:
    man = json.loads((BENCH / "manifest.json").read_text(encoding="utf-8"))
    rows = [read_case(c["case_id"]) for c in man["cases"]
            if c["family"] == "wingbox"]
    rows.sort(key=lambda r: (r["split"], r["taper"], r["sweep"]))

    print(f"wingbox cases: {len(rows)}\n")
    print(f"{'case':<38}{'split':<7}{'sweep':>7}{'taper':>7}"
          f"{'span':>7}{'skin':>6}{'ribs':>6}{'chord':>7}{'web':>4}  reason")
    for r in rows:
        print(f"{r['case']:<38}{r['split']:<7}{r['sweep']:>7.0f}{r['taper']:>7.2f}"
              f"{r['span']:>7.0f}{r['skin']:>6.1f}{r['ribs']:>6d}{r['chord']:>7.0f}"
              f"{r['n_web']:>4d}  {r['reason'][:44]}")

    # 关键格子：sweep>0 且 taper!=1
    print("\n== 关键格子 sweep>0 & taper!=1 ==")
    cell = [r for r in rows if r["sweep"] > 0 and abs(r["taper"] - 1.0) > 1e-9]
    if not cell:
        print("  (空)")
    for r in cell:
        print(f"  {r['case']:<38}{r['split']:<7}sweep={r['sweep']:g} "
              f"taper={r['taper']:g}  {r['reason'][:60]}")

    # 逐轴已学值域 —— 新点必须落在这些值域内才谈得上「内部组合」
    print("\n== 逐轴已学值（按 split）==")
    for sp in ("train", "val", "test"):
        sub = [r for r in rows if r["split"] == sp]
        if not sub:
            continue
        print(f"  {sp:<6}n={len(sub):<3}", end="")
        for ax in AXES:
            vals = sorted({r[ax] for r in sub})
            print(f" {ax}={[round(v, 3) for v in vals]}", end="")
        print()

    (OUT / "planar_census.json").write_text(
        json.dumps({"rows": rows,
                    "grid_sweep_gt0_taper_ne1": [r["case"] for r in cell]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {(OUT / 'planar_census.json').name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
