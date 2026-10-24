"""D35 机制拆解：`sweep40_taper040` 的误差从 15.19 % 掉到 3.18 %，到底是谁干的。

D35 同时动了两件事，必须分开算账，否则「补了点所以变好了」是一句没有
因果的口号：

* **B 只换边**：``sweep20_taper060`` test -> train，不加新算例。
* **C 换边 + 新点**：再加 ``sweep30_taper080``（当前落地的配置）。
* **A 基线**：D34 配置（18 train，``sweep20_taper060`` 在 test 里）。

三配置共用同一个 test 点 ``sweep40_taper040``（D35 前后它都是 test，
构成没变），所以误差差值是干净的。同时打印每个配置的**预测值**，因为
误差变小有两种完全不同的可能：

1. 预测值真的朝真值移动 —— 模型学到了东西；
2. 系数整体缩放，恰好在这个点上凑对了 —— 那就不可复现。

判据：看 ``pred`` 与 ``true`` 的比值，不看单个误差百分比。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "feagpt_repro"))

import numpy as np                          # noqa: E402

import baseline as B                        # noqa: E402

KEY = "max_disp"
TARGET = "naca4412_wingbox_sweep40_taper040"
MOVED = "naca4412_wingbox_sweep20_taper060"
NEW = "naca4412_wingbox_sweep30_taper080"
# NB: 超参网格必须用 baseline 自己的（logspace(-3,3,25)）。手写一个近似网格会
# 选到不同的 alpha，出来的 APE 就不是 baseline 口径的数 —— 那只能拿来比方向，
# 不能当结论。这里直接用同一个函数，保证三种配置可比且与对外数一致。
GRID = B._alpha_grid()


def main() -> int:
    rows = B.load_family("wingbox")
    by_id = {r["case_id"]: r for r in rows}
    train_now = [r for r in rows if r["split"] == "train"]
    print(f"当前 train {len(train_now)} 条；{MOVED} split={by_id[MOVED]['split']}；"
          f"{NEW} split={by_id[NEW]['split']}")

    configs = {
        "A_d34": [r for r in train_now if r["case_id"] not in (MOVED, NEW)],
        "B_moved_only": [r for r in train_now if r["case_id"] != NEW],
        "C_moved_plus_new": train_now,
    }
    for k, v in configs.items():
        print(f"  {k:<18} train={len(v)}")

    tgt = by_id[TARGET]
    print(f"\n目标点 {TARGET}: true {KEY} = {tgt[KEY]:.6f} mm "
          f"(sweep={tgt['sweep']:g} taper={tgt['taper']:g})")

    print(f"\n{'config':<18}{'alpha':>10}{'LOO':>8}{'pred':>10}{'pred/true':>10}{'APE':>8}")
    out = {}
    for name, tr in configs.items():
        pred, info = B.fit_m3(tr, KEY, GRID, quad=True)
        p = float(pred([tgt])[0])
        ape = abs(p - tgt[KEY]) / tgt[KEY] * 100.0
        out[name] = {"alpha": info["alpha"], "loo_mape": info["loo_mape"],
                     "pred": p, "ratio": p / tgt[KEY], "ape": ape,
                     "n_train": len(tr)}
        print(f"{name:<18}{info['alpha']:>10.0e}{info['loo_mape']:>8.2f}"
              f"{p:>10.4f}{p / tgt[KEY]:>10.4f}{ape:>7.2f}%")

    # 新点在 train 里的残差：若模型已经能拟合它们，说明 s^2 项吸收了交互
    print("\n两个交互点在各自训练集内的拟合残差（train 内误差，不是外推）：")
    for name in ("B_moved_only", "C_moved_plus_new"):
        tr = configs[name]
        pred, _ = B.fit_m3(tr, KEY, GRID, quad=True)
        for cid in (MOVED, NEW):
            if cid not in {r["case_id"] for r in tr}:
                continue
            r = by_id[cid]
            p = float(pred([r])[0])
            print(f"  {name:<18}{cid:<40}true {r[KEY]:.4f} pred {p:.4f} "
                  f"err {(p - r[KEY]) / r[KEY] * 100.0:+.2f}%")

    # sweep 响应形状：固定 taper 与其余特征，扫 sweep 看模型曲线
    # （用 A 与 C 两个模型，看「曲率」是否真的变了）
    print("\n模型对 sweep 的响应形状（其余特征取目标点，只扫 sweep）：")
    print(f"{'sweep':>7}{'A_d34':>12}{'C_now':>12}")
    for sw in (0, 10, 20, 30, 35, 40):
        row = dict(tgt)
        row["sweep"] = float(sw)
        pa, _ = B.fit_m3(configs["A_d34"], KEY, GRID, quad=True)
        pc, _ = B.fit_m3(configs["C_moved_plus_new"], KEY, GRID, quad=True)
        print(f"{sw:>7}{float(pa([row])[0]):>12.4f}{float(pc([row])[0]):>12.4f}")

    payload = {"target": TARGET, "true": tgt[KEY],
               "configs": out,
               "note": "同一 test 点、三种训练集；pred/true 越接近 1 越好，"
                       "看比值不看单点误差百分比"}
    (Path(__file__).resolve().parent / "why_planform_fixed.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n-> why_planform_fixed.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
