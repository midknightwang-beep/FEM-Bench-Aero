# _m4_probe —— M4 的负向测试留档

**`bad.json`** = 手改过 split 的 manifest 副本。改动只有一处：把
`naca4412_wingbox_recombination_algorithm3` 从 `train` 挪到 `test` —— 也就是把它
与**同一几何等价类**的基线 `naca4412_wingbox` 拆到划分的两边（这正是要防的泄漏）。

复现：

```
cd feagpt_repro
python eval_dataset.py --root ../FEM-Bench-Aero --manifest _m4_probe/bad.json
```

实测输出（退出码 **2**）：

```
[FAIL] recompute split  :: 1 case(s): ['naca4412_wingbox_recombination_algorithm3']
[FAIL] no_class_spans_splits  :: [{"class": "a796c5b1d217",
        "cases": ["naca4412_wingbox", "naca4412_wingbox_recombination_algorithm3"],
        "splits": ["test", "train"]}]
VERDICT: 2 CHECK(S) FAILED
```

留存它的唯一理由：**证明闸会咬人**。一个从没失败过的检查，和一个不存在的检查，
在证据强度上没有区别。

> 幂等测试（连跑两次 `make_manifest`，json 与 md 逐字节一致）的产物是临时的，未留档；
> 结论见 `README.md` §11.4 与看板证据卡 r30。
