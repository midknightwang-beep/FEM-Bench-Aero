"""D35 同 test 集对比：把「test 集换了」这个混淆项彻底摘掉。

D34 的 test 是 7 条（含 ``sweep20_taper060``），D35 是 6 条（它进了 train）。
直接拿 6.18 % 和 3.01 % 相减，等于拿两套不同的考卷比分数，不能这么报。

这里固定**同一份 6 条 test 集**（D35 的口径），只换训练集：

* ``A_d34``            18 条 = D34 原样（``sweep20_taper060`` 不在训练集里）
* ``B_moved_only``     19 条 = A + 换边过来的 ``sweep20_taper060``
* ``C_moved_plus_new`` 20 条 = B + 新点 ``sweep30_taper080``（落地配置）
* ``D_new_only``       19 条 = A + 新点，**不加换边那条**（反事实对照）

D 存在的意义：回答「光补一条新算例够不够」。若 C 与 D 差不多，说明真正
起作用的是换边（免费），补的算例只是锦上添花；若 D 明显不如 C，两条都要。

判据：只报 MAPE 与其 bootstrap 区间，不报「提升了几个百分点」这种不带
区间的说法。n=6，区间一定会很宽 —— 那是事实，不该被措辞藏掉。
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
MOVED = "naca4412_wingbox_sweep20_taper060"
NEW = "naca4412_wingbox_sweep30_taper080"
TARGETS = ("max_disp", "max_w", "max_von_mises", "max_von_mises_midsurface")
BOOT = 4000


def mape(pred, true):
    p, t = np.asarray(pred), np.asarray(true)
    return float(np.mean(np.abs(p - t) / t) * 100.0)


def boot_ci(pred, true, rng, n=BOOT):
    rel = np.asarray(pred) / np.asarray(true) - 1.0
    idx = rng.integers(0, len(rel), size=(n, len(rel)))
    vals = np.abs(rel[idx]).mean(axis=1) * 100.0
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def main() -> int:
    rows = B.load_family("wingbox")
    by_id = {r["case_id"]: r for r in rows}
    train_now = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    print(f"train {len(train_now)} / test {len(test)}")
    print("test cases:", ", ".join(r["case_id"].replace("naca4412_wingbox_", "")
                                   for r in test))

    cfg = {
        "A_d34": [r for r in train_now if r["case_id"] not in (MOVED, NEW)],
        "B_moved_only": [r for r in train_now if r["case_id"] != NEW],
        "C_moved_plus_new": train_now,
        "D_new_only": [r for r in train_now if r["case_id"] != MOVED],
    }

    rng = np.random.default_rng(20261024)
    result = {}
    for key in TARGETS:
        print(f"\n=== target {key} ===")
        print(f"{'config':<20}{'n_tr':>5}{'alpha':>10}{'LOO':>8}"
              f"{'testMAPE':>10}{'95% CI':>20}{'maxAPE':>9}")
        for name, tr in cfg.items():
            pred, info = B.fit_m3(tr, KEY := key, B._alpha_grid(), quad=True)
            p = np.array(pred(test))
            t = np.array([r[key] for r in test])
            m = mape(p, t)
            lo, hi = boot_ci(p, t, rng)
            mx = float(np.max(np.abs(p / t - 1.0)) * 100.0)
            result.setdefault(key, {})[name] = {
                "n_train": len(tr), "alpha": info["alpha"],
                "loo_mape": info["loo_mape"], "test_mape": m,
                "ci95": [lo, hi], "max_ape": mx,
                "per_case": {r["case_id"]: round(float(pp / tt - 1) * 100, 2)
                             for r, pp, tt in zip(test, p, t)},
            }
            print(f"{name:<20}{len(tr):>5}{info['alpha']:>10.0e}"
                  f"{info['loo_mape']:>8.2f}{m:>9.2f}%"
                  f"  [{lo:>5.2f},{hi:>5.2f}]{mx:>8.1f}%")

    # planform 考点逐条：这是唯一构成未变的组，最值得单独看
    print("\n=== 逐条误差（max_disp），重点看 sweep40_taper040 ===")
    print(f"{'case':<44}" + "".join(f"{k:>14}" for k in cfg))
    for i, r in enumerate(test):
        cid = r["case_id"]
        line = f"{cid:<44}"
        for name in cfg:
            line += f"{result['max_disp'][name]['per_case'][cid]:>13.2f}%"
        print(line)

    payload = {"note": "同一 6 条 test 集，四种训练集；超参用 baseline._alpha_grid()",
               "test_cases": [r["case_id"] for r in test],
               "boot": BOOT, "seed": 20261024, "by_target": result}
    (OUT / "same_test_set_d35.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {(OUT / 'same_test_set_d35.json').name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
