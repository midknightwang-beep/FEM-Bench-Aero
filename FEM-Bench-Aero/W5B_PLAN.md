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

## 2. 三条路（必须老王拍板）

| 路径 | 做法 | exam 规模 | 成本 | 风险 |
|---|---|---|---|---|
| **A. ID 内插留出（推荐）** | 55 条全 L3（19 exam）+ 从 train 里挑 **6 条落在训练包络内部的点**，标 `interpolation_test` 单独一栏 | **25** | 0 次建模/求解（真值现成） | 划分规则变更（D12 修订），须留档旧基线（D10） |
| **B. 新增几何** | 造 6–10 条新几何（内插 + 边界外），跑 pipeline + 双码 + 九闸建 truth | 25–29 | 2–3 天求解 + 双码核验 | 新 case 可能踩网格/收敛坑（vM 峰值未收敛这点仍未解） |
| **C. 只报 19 + CI** | 不扩，直接 19 条 exam + bootstrap CI | 19 | 0 | **违反 R12/R24**（n<20 不得判 value_added、不得对外承诺）。只能当内部诊断 |

**推荐 A**，理由：
1. 专家 §5.2 任务 10 明确要「内插 ID test 留出，与 boundary/extrap 分列」，A 正是这一步；
2. 零新建模成本，不等求解器、不引入新真值风险；
3. exam 25 条同时缓解族不平衡（内插名额按族分配：wingbox 2 / open_hole 2 / barrel 1 / panel 1）；
4. 代价只有一条：**划分规则要改**——`manifest.HOLDOUT_REGIONS` / `split_of()` 增加 `interpolation_test`，
   D12 需出修订记录并留档旧划分（老规矩）。

A 的替代性风险（必须同引）：内插题的 TSR 会**显著高于** boundary/extrap（题目更容易），
把三栏合起来报会虚高。**所以三套 exam 必须分开报**，headline 用「boundary + extrap」还是「全 exam」要先定死——
这是一条预注册事项（R18），不能等成绩出来再选。

## 3. 执行顺序（合并省一次生成）

| 步 | 做什么 | 验收 |
|---|---|---|
| **W5b-0（阻塞项）** | 拿 `WORKBUDDY_PUBLISHABLE_KEY`（当前 shell 未设，`gen_candidates_v2.js` 只读 env、无 fallback） | `node gen_candidates_v2.js --limit 1` 出 1 条合法候选 |
| W5b-1 | **v5 考卷重生成 30 条**（R28：旧候选不能评新考卷） | `candidates_l3_v5/` 30 条、`turns_used` 全记录 |
| W5b-2 | 扩卷：`make_nl_human.py` 额度参数化 → 55 条全 L3 + 6 条内插留出 → **冻结考卷 v6** | `tasks_v6.jsonl` + sha256 + tag `v1.0-l3-v6`；**逐条比对证明原 30 条 NL/ec 未改**（否则 v5 候选作废） |
| W5b-3 | 只生成新增 31 条（v6 独有任务） | 与 W5b-1 的 30 条合并成 `candidates_l3_v6/` 61 条 |
| W5b-4 | 一次打分 + CI：`score_baseline.py` → `msr_l3.py` → `bootstrap_ci.py` | exam ≥20；三栏（boundary/extrap/interp）分列 CI |
| W5b-5 | 第二模型（**先用 SDK 实测可用 id，不猜**） | 两模型 TSR 差异 + 各自 CI |
| W5b-6 | 失败归因字段级（env/contract/model/solver + 失败键清单） | 每条失败有原因，落 `reports/` |

关键纪律：
- **v5 的 30 条候选只在「v6 里这 30 条逐字节没变」时才能复用**——要机器比对，不靠记忆；
- 生成前先跑 `check_claims.py` + `negative_controls.py`（R6：负控不绿不跑基线）；
- 全程串行求解（环境铁律：并行 ccx 会静默空转）。

## 4. 不做的事（明确）

- ❌ 不在 n=11 上做任何调优、prompt 迭代、模型选择；
- ❌ 不把 C-025 的 4/11 当模型成绩（旧候选 × 新卷，已标 diagnostic）；
- ❌ 不用单模型成绩做榜单（W5d 才谈榜单协议）；
- ❌ 不新增几何同时改判据（混叠，无法归因）。
