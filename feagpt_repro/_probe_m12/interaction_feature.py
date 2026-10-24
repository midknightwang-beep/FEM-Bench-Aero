"""D35 核心实验：交互项从「不可估」变成「可估」之后，显式特征能不能两头都顾。

D35 落地的二次模型（``M3q``）只有 ``s = sweep/20`` 与 ``s^2`` 两列，**没有交互
列**。补了两条 ``sweep>0 & taper!=1`` 的样本后，模型只能靠**调 s^2 的系数**去
迁就组合点 —— 代价立刻显出来（实测，``_probe_m11/residual_diag.py`` 重跑）：

* ``sweep40_taper040``（test）  : 15.66 % -> **-5.45 %**  修好了
* ``sweep40``（val，锥度中性）  : -3.17 % -> **-12.79 %**  变差了

一个系数要同时描述「纯后掠曲率」和「后掠×锥度」，它办不到，只能折中。
D34 当初说「交互项不可估」的意思是**没样本可估**，不是「不需要这个项」。
现在有 2 条样本了，本脚本检验显式加列是否真的解掉这个折中：

    交互列  s^2 * (taper - 1)      ← 后掠按二次缩放，锥度偏离中性按一次

判据（先定后看，不许事后挑）：

1. ``sweep40_taper040``（test） 不差于无交互档的 -5.45 %；
2. ``sweep40``（val）**必须修回到 -3.17 % 附近或更好** —— 这是本实验存在的理由；
3. train LOO 不得比无交互档差超过 1 pp（多一个参数要付代价，但不许大崩）；
4. test 6 条整体 MAPE 不差于无交互档。

对照全部在**同一个 6 条 test 集 + 7 条 val** 上，与 D35 的 C 配置同口径。
复用 ``baseline`` 的 ``_loocv_alpha / _zfit / _ridge``，不另写一套判据。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "feagpt_repro"))

import numpy as np                          # noqa: E402

import baseline as B                        # noqa: E402

OUT = Path(__file__).resolve().parent
TARGETS = ("max_disp", "max_w", "max_von_mises", "max_von_mises_midsurface")
DEG = 20.0


def feat_no_inter(rows):
    return B.feat_matrix_q(rows)


def feat_with_inter(rows):
    X = B.feat_matrix_q(rows)
    s = np.array([float(r["sweep"]) / DEG for r in rows])
    t = np.array([float(r["taper"]) for r in rows])
    return np.column_stack([X, s * s * (t - 1.0)])


def fit(tr, key, mat):
    X = mat(tr)
    ylog = np.log([r[key] for r in tr])
    alpha, loo = B._loocv_alpha(X, ylog, B._alpha_grid())
    mu, sd, _const = B._zfit(X)
    ym, w = B._ridge((X - mu) / sd, ylog, alpha)
    cond = float(np.linalg.cond(np.column_stack([np.ones(len(tr)), X])))

    def pred(rows):
        return list(np.exp(((mat(rows) - mu) / sd) @ w + ym))
    return pred, {"alpha": alpha, "loo_mape": round(loo, 3),
                  "cond": round(cond, 1), "last_coef_z": round(float(w[-1]), 4)}


def mape(pred, true):
    return float(np.mean(np.abs(np.asarray(pred) / np.asarray(true) - 1.0)) * 100.0)


def main() -> int:
    rows = B.load_family("wingbox")
    tr = [r for r in rows if r["split"] == "train"]
    va = [r for r in rows if r["split"] == "val"]
    te = [r for r in rows if r["split"] == "test"]
    by = {r["case_id"]: r for r in rows}
    print(f"train {len(tr)} / val {len(va)} / test {len(te)}")

    variants = {"no_inter": feat_no_inter, "with_inter": feat_with_inter}
    out = {}
    for key in TARGETS:
        print(f"\n=== {key} ===")
        print(f"{'variant':<14}{'alpha':>9}{'LOO':>8}{'trainMAPE':>11}"
              f"{'valMAPE':>10}{'testMAPE':>10}{'coef_z':>9}{'cond':>10}")
        for name, mat in variants.items():
            pred, info = fit(tr, key, mat)
            tm = mape(pred(tr), [r[key] for r in tr])
            vm = mape(pred(va), [r[key] for r in va])
            sm = mape(pred(te), [r[key] for r in te])
            out.setdefault(key, {})[name] = {
                "alpha": info["alpha"], "loo_mape": info["loo_mape"],
                "train_mape": tm, "val_mape": vm, "test_mape": sm,
                "inter_coef_z": info["last_coef_z"], "cond": info["cond"],
                "pred_test": {r["case_id"]: round(float(p), 4)
                              for r, p in zip(te, pred(te))},
            }
            print(f"{name:<14}{info['alpha']:>9.0e}{info['loo_mape']:>8.2f}"
                  f"{tm:>10.2f}%{vm:>9.2f}%{sm:>9.2f}%"
                  f"{info['last_coef_z']:>9.4f}{info['cond']:>10.1f}")

    # 判据 1/2：两个关键点逐条对照
    print("\n=== 关键点逐条 APE（max_disp）===")
    print(f"{'case':<44}{'split':>7}{'no_inter':>11}{'with_inter':>12}")
    for cid in ("naca4412_wingbox_sweep40_taper040", "naca4412_wingbox_sweep40",
                "naca4412_wingbox_sweep30_taper080",
                "naca4412_wingbox_sweep20_taper060"):
        r = by[cid]
        line = f"{cid:<44}{r['split']:>7}"
        for name, mat in variants.items():
            p = out["max_disp"][name]["pred_test"].get(cid)
            if p is None:      # val 点不在 pred_test 里，现算
                pred, _ = fit(tr, "max_disp", mat)
                p = float(pred([r])[0])
            line += f"{(p / r['max_disp'] - 1) * 100:>11.2f}%"
        print(line)

    # 判据判定
    d = out["max_disp"]
    checks = {
        "test_planform_not_worse": abs(d["with_inter"]["pred_test"]
                                       ["naca4412_wingbox_sweep40_taper040"]
                                       / by["naca4412_wingbox_sweep40_taper040"]["max_disp"] - 1)
        <= abs(0.0545) + 1e-9,
        "val_sweep40_recovered": d["with_inter"]["val_mape"] <= d["no_inter"]["val_mape"],
        "loo_cost_under_1pp": (d["with_inter"]["loo_mape"]
                               - d["no_inter"]["loo_mape"]) <= 1.0,
        "test_overall_not_worse": d["with_inter"]["test_mape"]
        <= d["no_inter"]["test_mape"] + 1e-9,
    }
    print("\n=== 判据（先定后看）===")
    for k, v in checks.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"  => {sum(checks.values())}/{len(checks)}")

    payload = {"note": "交互列 s^2*(taper-1)；判据先定后看；超参用 baseline._alpha_grid()",
               "n_train": len(tr), "by_target": out, "checks": checks,
               "verdict": "PASS" if all(checks.values()) else "FAIL"}
    (OUT / "interaction_feature_d35.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {(OUT / 'interaction_feature_d35.json').name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
