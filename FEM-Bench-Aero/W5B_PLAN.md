# W5B_PLAN — 扩量 + CI + 第二模型（专家第六轮 Conditional-Go 之后）

> 起草：2026-10-25（W5a' 收口后）。上游依据：`FEM-Bench-Aero第六轮复评与执行纠偏_2026-10-25.md` §5.2。
> **本文件是计划，不是成绩**。任何数字在跑出来之前不得进 `CLAIMS.md`、README、对外文档。

## 0. 一句话

W5a' 把证据钉进了 git，**科学上空缺只剩一个：exam n=11**。W5b 的全部工作就是把它做厚、加上区间、再加一个模型；
在此之前不得做任何调优与外承诺（R12/R24）。

## 1. 现状盘点（脚本实测，可复现）

```bash
cd feagpt_repro && python _probe_expand.py     # 2026-10-25 实测输出
```

| 族 | train | val | boundary | extrap | exam | 全部 L1 |
|---|---:|---:|---:|---:|---:|---:|
| wingbox | 15 | 7 | 6 | 6 | **12** | 34 |
| open_hole_panel | 2 | 5 | 0 | 4 | **4** | 11 |
| fuselage_barrel | 1 | 3 | 0 | 2 | **2** | 6 |
| stiffened_panel | 1 | 2 | 0 | 1 | **1** | 4 |
| 合计 | 19 | 17 | 6 | 13 | **19** | 55 |

- 当前 L3 考卷 = 30 条（额度 wingbox 15 / open_hole 6 / barrel 5 / panel 4），其中 exam **11**。
- **把 55 条全部做成 L3，exam 上限只有 19**（= boundary 6 + extrap 13）——**差 1 条到 n≥20**。
- 族别极不均衡：panel 只有 1 条 exam、barrel 2 条，任何按族结论都无统计意义（P1-7）。

## 2. 三条路（老王 2026-10-25 拍板：**A**）

| 路径 | 做法 | exam 规模 | 成本 | 结论 |
|---|---|---|---|---|
| **A. ID 内插留出 ✅ 已拍板** | 55 条全 L3（19 exam）+ 从 train 挑 **6 条**标 `interpolation_test` | **25** | 0 次建模/求解 | **采用**（C-027 已冻结 v6） |
| B. 新增几何 | 造 6–10 条新几何建 truth | 25–29 | 2–3 天 | 不做（留给 v1.1） |
| C. 只报 19 + CI | 不扩 | 19 | 0 | 否决（违反 R12/R24） |

**配套拍板 2：headline 口径 = 合并 25 条**。
起草时发现一条算术互斥必须记下来：`boundary_holdout = 6`、`extrapolation_test = 13` 是数据集固定值，
**「headline = boundary+extrap」永远是 19 条 < 20**，与 R12/R24 的 n≥20 门槛不可同时满足。
故取「headline = 合并 25（含 6 条 interp），三栏明细并列，R12 分母 = 25」，
并在所有对外引用处写明**与 C-021 的 19 条口径不可直接比**（已写入 RUBRIC §1.1 v4）。

**代价（必须同引）**：
1. 内插题明显更容易 ⇒ 合并数会比 C-021 的 45.5% 高，这是题目构成变化不是模型变好；
2. barrel / panel 的 train 条数被抽空（各只剩 val），dev 的可比性下降；
3. 三栏各自 n 只有 6 / 13 / 6，**分栏只报不判**。


## 3. 执行顺序（合并省一次生成）

| 步 | 做什么 | 验收 | 状态 |
|---|---|---|---|
| **W5b-0（阻塞项）** | 拿 `WORKBUDDY_PUBLISHABLE_KEY`（当前 shell 未设，只读 env、无 fallback） | `node gen_candidates_v2.js --limit 1` 出 1 条合法候选 | ⛔ 阻塞 |
| W5b-1 | **v5 考卷重生成 30 条**（R28）——可并入 W5b-3：v6 里这 30 条逐字节未变（已机器验证），故直接生成 v6 的 55 条即可 | `candidates_l3_v6/` 55 条、`turns_used` 全记录 | ⛔ 等 key |
| W5b-2 | 扩卷 + 冻结考卷 v6 | **已完成**：`tasks.jsonl` 165 行（L3 55）、exam 25、老题零改动（`_verify_tasks_v6.py` PASS）、tag `v1.0-l3-v6`、`papers/tasks_v6.jsonl` | ✅ C-027 |
| W5b-3 | 生成 55 条候选（v6 全量） | 与 W5b-1 合并执行 | ⛔ 等 key |
| W5b-4 | 一次打分 + CI：`score_baseline.py` → `msr_l3.py` → `bootstrap_ci.py` | exam 25；三栏（boundary/extrap/interp）分列 CI；`score_baseline.py` 已支持 `exam_stratum`（向后兼容已验：v4 仍 5/11） | 待 |
| W5b-5 | 第二模型（**先用 SDK 实测可用 id，不猜**） | 两模型 TSR 差异 + 各自 CI | 待 |
| W5b-6 | 失败归因字段级（env/contract/model/solver + 失败键清单） | 每条失败有原因，落 `reports/` | 待 |


关键纪律：
- **v5 的 30 条候选只在「v6 里这 30 条逐字节没变」时才能复用**——要机器比对，不靠记忆；
- 生成前先跑 `check_claims.py` + `negative_controls.py`（R6：负控不绿不跑基线）；
- 全程串行求解（环境铁律：并行 ccx 会静默空转）。

## 4. 不做的事（明确）

- ❌ 不在 n=11 上做任何调优、prompt 迭代、模型选择；
- ❌ 不把 C-025 的 4/11 当模型成绩（旧候选 × 新卷，已标 diagnostic）；
- ❌ 不用单模型成绩做榜单（W5d 才谈榜单协议）；
- ❌ 不新增几何同时改判据（混叠，无法归因）。
