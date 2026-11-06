# ODB Tools — Abaqus 批量求解+提取一条龙（两工具解耦的「提取侧」落地）

> 2026-11-06 老王拍板：**A**（同模型 × N 组载荷）+ **B**（求解+提取一条龙）+ **C**（提取可配置）。
> 纯标准库、零包依赖，整个目录可拷到任何有 Abaqus 的机器单独用。

## 文件

| 文件 | 运行环境 | 作用 |
|---|---|---|
| `odb_scalar.py` | `abaqus python` | 快速档：单 ODB → 标量 JSON（max\|U\|、RF 合力、膜应力 vM 峰 + 外表面 elementwise vM 峰）。几百字节/件 |
| `feagpt/abaqus_odb.py` | `abaqus python` | 全场档：DISP/FORC/STRESS/STRESS_PEAK 全节点 JSON（1–3 MB/件），与本工具共用数值核心 |
| `odb_batch.py` | 任意 Python 3 | 编排器：扫 job → 清陈旧产物 → 求解 → .sta 判据 → 提取 → 对账 manifest |

## 用法（WorkBuddy 外的 cmd 里跑——agent 沙箱跑不了 Abaqus）

```bat
:: 先看计划，不动任何文件（沙箱安全）
python odb_batch.py D:\jobs\case_20261106 --dry-run

:: 一条龙：标量档（默认），完成后删 odb 省盘
python odb_batch.py D:\jobs\case_20261106 --purge-odb

:: 全场档（桥接数据集用）+ 4 核
python odb_batch.py D:\jobs\case_20261106 --tier full --cpus 4

:: 只跑某几个 + 并行（注意 license token 数）
python odb_batch.py D:\jobs --only job1,job7 --parallel 2
```

job 布局：根目录下直接放 `<name>.inp`，或每个 job 一个子目录（每目录一个 `.inp`）。
产物：每个 job 一份 `.json.scalar`（或 `.odb.json`）+ 根目录一份 `run_manifest.json`。
**退出码 0 ⇔ 全部 job ok**；任何失败读 manifest 里的 `state` / `cleaned` / `abaqus_rc` / `extract_tail`。

## 四个历史事故的代码级防线（不是靠纪律）

| 坑（出处） | 防线 |
|---|---|
| Abaqus 批量循环静默空转（batch5） | 每个 job 必须落**终态**（ok/solve_failed/extract_failed）；`.sta` 缺失或无 `COMPLETED SUCCESSFULLY` ⇒ solve_failed，rc=1 |
| 陈旧空 ODB 骨架污染下一轮 | 求解前清 `_STALE_SUFFIXES` 全部陈旧产物，清理清单逐件记进 manifest 的 `cleaned` |
| summary 静默漏行（v11：9 跑 1 记） | `n_rows == n_jobs_scanned` 是**代码内断言**，行数不等直接拒绝写 manifest |
| 只产不汇、事后对不上 | manifest 随每 job 完成即成汇总，标量档直接带 `max_u_mag`/`vm_peak` 读数，无需二次 resummarize |

## 数值口径（与 `abaqus_odb.py` 同源钉死）

`_von_mises` / `_reorder` / FRD 分量表在两个提取器里逐字节一致，`odb_scalar.py --self-test`
（7 组 pin，任意 python 可跑）+ 仓库交叉对拍脚本（200 组随机向量）双闸守漂移。
膜应力 = 最外 section point 均值再按邻单元平均（CalculiX OUTPUT=2D 可比，实测中位差 1.6%）；
`vm_peak` = elementwise 最大（强度尺寸数，**不可**与 ccx OUTPUT=2D 直比）。

## 验收（老王真机一次过）

1. `python odb_scalar.py --self-test` → `SELF_TEST_OK 7/7`
2. `python odb_batch.py <真job目录> --dry-run` → 计划里的 job 清单与实际一致
3. 小批 2–3 个 job 真跑 → `run_manifest.json` 全 `ok`、`.json.scalar` 读数与手工提取一致
4. 抽 1 个 job 用 `--tier full` 重提取 → `meta.blocks` 与 `odb_scalar` 的标量在各自口径下对得上
