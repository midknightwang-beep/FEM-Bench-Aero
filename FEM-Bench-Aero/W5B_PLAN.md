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
| **A. ID 内插留出 ✅ 已拍板** | 55 条全 L3（19 exam）+ 从 train 挑 **6 条**标 `interpolation_test`（**v6b 定案：全给翼盒**，理由见 §7） | **25** | 0 次建模/求解 | **采用**（C-027 已冻结 v6b） |
| B. 新增几何 | 造 6–10 条新几何建 truth | 25–29 | 2–3 天 | 不做（留给 v1.1） |
| C. 只报 19 + CI | 不扩 | 19 | 0 | 否决（违反 R12/R24） |

**配套拍板 2：headline 口径 = 合并 25 条**。
起草时发现一条算术互斥必须记下来：`boundary_holdout = 6`、`extrapolation_test = 13` 是数据集固定值，
**「headline = boundary+extrap」永远是 19 条 < 20**，与 R12/R24 的 n≥20 门槛不可同时满足。
故取「headline = 合并 25（含 6 条 interp），三栏明细并列，R12 分母 = 25」，
并在所有对外引用处写明**与 C-021 的 11 条口径不可直接比**（三个数：C-021 = **11**、v6 boundary+extrap = **19**、v6 headline 合并 = **25**；已写入 RUBRIC §1.1 v4 与 R30）。

**代价（必须同引）**：
1. 内插题明显更容易 ⇒ 合并数会比 C-021 的 45.5% 高，这是题目构成变化不是模型变好；
2. barrel / panel 的 train 条数被抽空（各只剩 val），dev 的可比性下降；
3. 三栏各自 n 只有 6 / 13 / 6，**分栏只报不判**。


## 3. 执行顺序（合并省一次生成）

| 步 | 做什么 | 验收 | 状态 |
|---|---|---|---|
| **W5b-0（阻塞项）** | 拿 `WORKBUDDY_PUBLISHABLE_KEY` | `node gen_candidates_v2.js --limit 1` 出 1 条合法候选 | ✅ **已完成**（2026-10-25 19:01，见 §6.0 key 出处；冒烟产物 `eval_runs/_smoke_key_v6b/`） |
| W5b-1 | **v5 考卷重生成 30 条**（R28）——可并入 W5b-3：v6 里这 30 条逐字节未变（已机器验证），故直接生成 v6 的 55 条即可 | `candidates_l3_v6/` 55 条、`turns_used` 全记录 | ✅ **已完成**（55/55 条，spec 44 / clarify 4 / unresolved 7 / error 0，零缺失） |
| W5b-2 | 扩卷 + 冻结考卷 v6 | **已完成**：`tasks.jsonl` 165 行（L3 55）、exam 25、老题零改动（`_verify_tasks_v6.py` PASS）、tag `v1.0-l3-v6b`、`papers/tasks_v6.jsonl` | ✅ C-027 |
| W5b-3 | 生成 55 条候选（v6 全量） | 与 W5b-1 合并执行；**命令见 §6**（`--limit 55` 不可省） | ✅ **已完成**（16 分 13 秒） |
| W5b-4 | 一次打分 + CI：`score_baseline.py` → `msr_l3.py` → `bootstrap_ci.py` | exam 25；三栏分列 CI；`score_baseline.py` 已支持 `exam_stratum` | ✅ **已完成 = C-028**：exam TSR 17/25 (68.0%) CI95 [48.0, 84.0]，`underpowered=False`；MSR 全链 25/44、exam 10/21；R30 闸 rc=3 |
| W5b-5 | 第二模型（**先用 SDK 实测可用 id，不猜**） | 两模型 TSR 差异 + 各自 CI | ⏭ **下一步**（v6b 考卷 + C-028 已就绪，可直接换 `--model` 跑） |
| W5b-6 | 失败归因字段级（env/contract/model/solver + 失败键清单） | 每条失败有原因，落 `reports/` | ✅ **已完成（pre-C-028）**：`_probe_w5b4_fail_fields.py` 逐条给出失败字段；三类缺陷归因见 `eval_runs/w5b4_defect_analysis_20261025.md`。**遗留**：成绩单本身仍不存 `failed_fields`（只有 note），建议 W5c 把它落进 per_task |


关键纪律：
- **v5 的 30 条候选只在「v6 里这 30 条逐字节没变」时才能复用**——要机器比对，不靠记忆；
- 生成前先跑 `check_claims.py` + `negative_controls.py`（R6：负控不绿不跑基线）；
- 全程串行求解（环境铁律：并行 ccx 会静默空转）。

## 4. 不做的事（明确）

- ❌ 不在 n=11 上做任何调优、prompt 迭代、模型选择；
- ❌ 不把 C-025 的 4/11 当模型成绩（旧候选 × 新卷，已标 diagnostic）；
- ❌ 不用单模型成绩做榜单（W5d 才谈榜单协议）；
- ❌ 不新增几何同时改判据（混叠，无法归因）。

## 5. 第七轮整改（W5b-3a，✅ 已完成 2026-10-25）

| 项 | 结果 |
|---|---|
| 文档语义计数 5 处漂移（P1-1..P1-4） | C-010 **165**（L3 55）/ C-011 内插 = **v6 interp 6** / C-019 coverage **31** / C-027·RUBRIC·W5B_PLAN·看板 的「C-021 的 N 条」统一 **11**（19·25 分列）/ README RUBRIC **v4.1** |
| `check_claims.py --semantic`（P1-5/R29） | 默认开；17 项，期望值全部从 artifact 实读 ⇒ 全过 |
| 负控（R29/R30/R31） | **31/31**：NC-27 语义计数漂移 / NC-28 覆盖不全 / NC-29 跨口径混比 |
| 跨口径闸（R30） | `compare_scorecards.py`（rc=3 拒绝混比） |
| 覆盖记账（R31） | 成绩单 `n_tasks_in_paper` / `candidates_missing` / `partial_candidates` |

## 6. W5b-3 生成命令（key 不在对话/仓库里传）

> **★ 坑**：`gen_candidates_v2.js` 的 `--limit` **默认 30**。v6 有 55 条，**不显式给 `--limit 55` 就只会生成 30 条**，
> 然后成绩单会「看着 exam n=25、其实部分任务没打分」。已加 `partial_candidates` + NC-28 咬它，但正确做法是别漏。
>
> **★ 坑（2026-10-25 更新）**：key 只读 `process.env.WORKBUDDY_PUBLISHABLE_KEY`（无 fallback，**脚本不装 dotenv ⇒ `.env` 文件写了也不读**）。
> ~~必须在同一个窗口里设 key + 跑 node~~ —— 该限制**已解除**：key 已 `setx` 进用户级环境变量，新开窗口自动继承，
> 沙箱内 `export` 亦可。W5b-0 冒烟（`--limit 1`）已实测通过，产出 `eval_runs/_smoke_key_v6b/L3_naca4412_wingbox.json`。

### 6.0 key 的出处（W5b-0 查实，免得下次再找一遍）

| 项 | 值 |
|---|---|
| 变量 | `WORKBUDDY_PUBLISHABLE_KEY` |
| 实质 | WorkBuddy 云服务应用「FEM基线评测」`wbapp_Tl8jf0GeqRmnK59Hr64PuS` 的 `publicConfig.publishableKey`（`wbpk_` 前缀、**无权限语义**、服务端按 Origin 校验），**不是**模型厂商 key，**无需到任何网站注册申请** |
| 取法 | `workbuddy_cloud_service` → `action=activate` + `applicationMode=reuse` + `applicationId=wbapp_Tl8jf0GeqRmnK59Hr64PuS`（`inspect` 只列应用、**不返回 key**） |
| 本机现状 | 已 `setx` 到用户级环境变量（新开窗口生效）；仓库 `gen_candidates.js:13` 遗留同值 fallback（**未轮换**，与线上取回值逐字符一致） |
| 反例 | ① 建 `.env` 无效（无 dotenv）；② 本窗口设、另开窗口跑 = 不生效；③ `.gitignore` 原先没有 `.env` 条目（已补 `.env` / `.env.*`） |

两种执行方式（任选，产物相同）：
- **A（推荐）**：直接在 WorkBuddy 内跑，key 已继承，不用管
- **B（备选）**：外部 cmd，同窗口内 `set WORKBUDDY_PUBLISHABLE_KEY=<值>` 后立刻跑

```bat
cd /d "F:\AI FEA Modeling DataSets\feagpt_repro"
set WORKBUDDY_PUBLISHABLE_KEY=<你的 key>   REM 方式 B 才需要这行

REM ① 冒烟 1 条（R31：不许直接 55 条盲跑）
node gen_candidates_v2.js --tasks reports/papers/tasks_v6b.jsonl --levels L3 --out _smoke_v6 --limit 1


REM ② 全量 55 条（--limit 必须显式给 55）
node gen_candidates_v2.js --tasks reports/papers/tasks_v6b.jsonl --levels L3 --out candidates_l3_v6 --limit 55

REM ③ 回读条数（必须是 55）
dir candidates_l3_v6\*.json | find /c ".json"
```

拿到 `candidates_l3_v6/` 后，在 WorkBuddy 内（不需要 key）：

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
"$PY" score_baseline.py --candidates candidates_l3_v6 --tasks reports/papers/tasks_v6b.jsonl \
  --report reports/baseline_scorecard_L3_v6b.json --trivial reports/trivial_baselines_L3_v6b.json \
  --label "C-028 v6b (paper v6b, candidates v6)"
"$PY" msr_l3.py --candidates candidates_l3_v6 --tasks reports/papers/tasks_v6b.jsonl \
  --report reports/baseline_scorecard_L3_v6b.json
"$PY" bootstrap_ci.py --scorecard reports/baseline_scorecard_L3_v6b.json
"$PY" compare_scorecards.py --a reports/baseline_scorecard_L3_v4.json \
  --b reports/baseline_scorecard_L3_v6b.json     # 必须 rc=3（口径不同）
```

> **★ 已改（2026-10-25 19:0x，W5b-0 执行时查实）**：
> 1. `--trivial` 原写 `trivial_baselines_L3.json` —— 那是 **v4 考卷（exam 11）** 的地板，套到 v6b（exam 25 三栏）
>    就是 R30 跨口径混用。已有同口径的 `reports/trivial_baselines_L3_v6b.json`（T0 0/25、T1 0/25、T2 25/25），必须用它。
> 2. 成绩单文件名由 `baseline_scorecard_L3_v6.json` 改为 **`..._v6b.json`**：考卷是 v6b、地板是 v6b，成绩单叫 v6 会留下口径错位的隐患（v6 已作废，见 §7）。
> 3. §6 开头那条「必须在外部 cmd 同窗口设 key」的前提**已不成立**：key 已 `setx` 进用户级环境变量，
>    且实测沙箱内 `export` 后可直接跑（W5b-0 冒烟已通过）。外部 cmd 只是备选路径。

## 7. v6 → v6b：内插名额修正（2026-10-25 老王拍板 A）

| 项 | v6（作废） | **v6b（采用）** |
|---|---|---|
| 内插名额 | wingbox 2 / open_hole 2 / barrel 1 / panel 1 | **wingbox 6**（`--interp-quota "wingbox:6"`） |
| exam 总数 | 25（6 + 13 + 6） | **25（6 + 13 + 6）** |
| train 池（族分布） | 13 / **0 / 0 / 0** | **9 / 2 / 1 / 1** |
| 可算 T1 地板的族 | **1 / 4** | **4 / 4** |
| exam 族构成 | 14 / 6 / 3 / 2 | 18 / 4 / 2 / 1 |

**为什么改**（实测，不是偏好）：
1. L3 的 train 分布是 wingbox 15 / open_hole 2 / barrel 1 / panel 1，按 2/2/1/1 抽会把
   **barrel、open_hole、panel 三族的 train 全抽空** ⇒ train 池只剩翼盒；
2. 后果不是"dev 变小"，而是**地板算不出来**：`trivial_baselines` 的 T0 众数池缺 3 族、
   T1 检索库只剩翼盒 ⇒ **T1 地板只有 1/4 族可算**，value_added 的对照项失真
   （T1 记 0/25 会让任何成绩都"有增量"）；
3. 更根本：train 只有 1 条的族抽出来当"内插"**本身无意义**——1 个点没有包络可内插。

**同时修掉的 bug（W5b-3b）**：内插考题 `split_v2` 仍是 `train`，原 `trivial_baselines`
检索库取 `split_v2=='train'` ⇒ **T1 会检索到它自己**（gold 逐字段相同、距离 0），
interp 栏地板虚高 100%、value_added 被算成负数。现改为「检索库/众数池 = train 且 `exam_stratum` 为空」。

**可复现**：`python _probe_interp_w5b3b.py`（4 种名额方案的 train 池/族构成对比）；
`python trivial_baselines.py --levels L3 --tasks reports/papers/tasks_v6b.jsonl --out trivial_baselines_L3_v6b.json --out-dir reports`
（⇒ T0 0/25、T1 0/25、T2 25/25，三栏全 0；四族齐全无 WARN）。
