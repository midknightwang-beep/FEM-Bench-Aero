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
| **W5b-0（阻塞项）** | 拿 `WORKBUDDY_PUBLISHABLE_KEY` | `node gen_candidates_v2.js --limit 1` 出 1 条合法候选 | ✅ **已完成**（2026-10-25 19:01，见 §6.0 key 出处；冒烟产物 1 条，落在被 gitignore 的工作目录，未入库） |
| W5b-1 | **v5 考卷重生成 30 条**（R28）——可并入 W5b-3：v6 里这 30 条逐字节未变（已机器验证），故直接生成 v6 的 55 条即可 | `candidates_l3_v6/` 55 条、`turns_used` 全记录 | ✅ **已完成**（55/55 条，spec 44 / clarify 4 / unresolved 7 / error 0，零缺失） |
| W5b-2 | 扩卷 + 冻结考卷 v6 | **已完成**：`tasks.jsonl` 165 行（L3 55）、exam 25、老题零改动（`_verify_tasks_v6.py` PASS）、tag `v1.0-l3-v6b`、冻结稿 `papers/tasks_v6b.jsonl`（v6 原稿留档 `tasks_v6.jsonl`，D10）。**W5c 后现行卷 = `papers/tasks_v6c.jsonl`（tag `v1.0-l3-v6c`，C-030）** | ✅ C-027 → C-030 |
| W5b-3 | 生成 55 条候选（v6 全量） | 与 W5b-1 合并执行；**命令见 §6**（`--limit 55` 不可省） | ✅ **已完成**（16 分 13 秒） |
| W5b-4 | 一次打分 + CI：`score_baseline.py` → `msr_l3.py` → `bootstrap_ci.py` | exam 25；三栏分列 CI；`score_baseline.py` 已支持 `exam_stratum` | ✅ **已完成 = C-028**（后被降级为 diagnostic lower bound）→ **W5c 修复后重跑 = C-029**：exam TSR **23/25 (92.0%)** CI95 **[80.0, 100.0]**；三栏 6/6 · 11/13 · 6/6；R30 闸 rc=3 |
| **W5c-5b** | **T1+ family-mode 地板 + value_added 双尺度**（第九轮 §3.3 / R44） | `T1plus` 非 null；value_added 不再只对 0 地板 | ✅ **已完成（W5c-6b）**：`T1plus_family`（逐字段族级众数，众数只在 train 池取）exam **0/25**，但**字段命中率 85.93%**、缺口 min **1** / 中位 **3** / max **5** 字段；`T1plus_family_oracle`（族内池覆盖力上界，只报不判）**0/25** ⇒ **「0 地板」是全或无判据 × 族内参数唯一的必然**，已写进 C-029；**字段级尺度 85.93% → LLM 99.34%（Δ+13.4 pp）**，与任务级同判 PASS |
| W5b-5 | 第二模型（**先用 SDK 实测可用 id，不猜**） | 两模型 TSR 差异 + 各自 CI | ✅ **已完成（W5c-6c，C-031）**。模型 id 实测取（`llm.models.list()` 返回 **35 个**，`deepseek-v4-pro` 在其中，R13 不猜）；同 `tasks_v6c`（sha `9c1faa3a…`，与 C-029 **逐字节相同**）/ 同 SYS prompt / 同 `--max-turns 3` / `--limit 55`（9 min）。**结果：exam TSR 20/25 (80.0%)**（C-029 23/25）、SFR 20/25、dev 22/30。**★ 关键：`spec_pass` 两模型都是 20/25，2 条 `spec_fail` 同题同字段** ⇒ 那两处属 prompt 约束不足（A/B 类），不是模型个性；**唯一实质差异 = 缺失信息处理**（glm 澄清 3/3 vs dsv4pro 编造 3/3）。**字段级 87.42% vs 地板 85.93%（Δ+1.5 pp，未达 10 pp）** ⇒ 任务级 PASS / 字段级 BELOW **分裂已由 `verdict_split` 标注**（R49）。**C-031 定位 supporting，headline 仍是 C-029**（R48：不得事后择优） |
| W5b-6 | 失败归因字段级（env/contract/model/solver + 失败键清单） | 每条失败有原因，落 `reports/` | ✅ **已完成（pre-C-028）**：`_probe_w5b4_fail_fields.py` 逐条给出失败字段；四类缺陷（A 契约/C 模型/B 题面/D 收敛）归因见 `reports/diagnostics/w5b4_defect_analysis_v6b.md`（R37 已入库）。**已修正**：成绩单失败行**已存** `failed_fields`（`score_baseline.py` judge 返回值），旧文「仍不存」是过期信息 |


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
| `check_claims.py --semantic`（P1-5/R29） | 默认开；**32 项**（W5c 新增 S-21..S-28；W5c-6b 新增 **S-29 headline 唯一 / S-30 dev 投影口径 / S-31 MSR 九字段**），期望值全部从 artifact 实读 ⇒ 全过 |
| 负控（R29/R30/R31/R33–R49） | **44/44**：NC-27 语义计数漂移 / NC-28 覆盖不全 / NC-29 跨口径混比 / **NC-30 审计闸两端守（exam 0 + 非 exam 白名单 + 反向）** / NC-31 SYS prompt 键名齐 / NC-32 T1 leave-one-out / NC-33 成绩单文案由考卷生成 / NC-34 官方文档不引 `eval_runs/` / NC-35 同条数≠同批题 / **NC-36 语义项不得静默消失** |
| 跨口径闸（R30） | `compare_scorecards.py`（rc=3 拒绝混比） |
| 覆盖记账（R31） | 成绩单 `n_tasks_in_paper` / `candidates_missing` / `partial_candidates` |

## 6. W5b-3 生成命令（key 不在对话/仓库里传）

> **★ 坑**：`gen_candidates_v2.js` 的 `--limit` **默认 30**。v6 有 55 条，**不显式给 `--limit 55` 就只会生成 30 条**，
> 然后成绩单会「看着 exam n=25、其实部分任务没打分」。已加 `partial_candidates` + NC-28 咬它，但正确做法是别漏。
>
> **★ 坑（2026-10-25 更新）**：key 只读 `process.env.WORKBUDDY_PUBLISHABLE_KEY`（无 fallback，**脚本不装 dotenv ⇒ `.env` 文件写了也不读**）。
> ~~必须在同一个窗口里设 key + 跑 node~~ —— 该限制**已解除**：key 已 `setx` 进用户级环境变量，新开窗口自动继承，
> 沙箱内 `export` 亦可。W5b-0 冒烟（`--limit 1`）已实测通过，产出 1 条合法 `L3_naca4412_wingbox` 候选（未入库，R37）。

### 6.0 key 的出处（W5b-0 查实，免得下次再找一遍）

| 项 | 值 |
|---|---|
| 变量 | `WORKBUDDY_PUBLISHABLE_KEY` |
| 实质 | WorkBuddy 云服务应用「FEM基线评测」`wbapp_Tl8jf0GeqRmnK59Hr64PuS` 的 `publicConfig.publishableKey`（`wbpk_` 前缀、**无权限语义**、服务端按 Origin 校验），**不是**模型厂商 key，**无需到任何网站注册申请** |
| 取法 | `workbuddy_cloud_service` → `action=activate` + `applicationMode=reuse` + `applicationId=wbapp_Tl8jf0GeqRmnK59Hr64PuS`（`inspect` 只列应用、**不返回 key**） |
| 本机现状 | 已 `setx` 到用户级环境变量（新开窗口生效）。**W5c（D5）已删除 `gen_candidates.js` 的硬编码 fallback**（脚本现在只读 env、无 fallback，缺 key 直接 rc=2）。**★ 但 key 仍在 git 历史里（commit `efa2b6f`），删除 fallback 只止血不治病**。~~真正消除须重建应用 + 轮换 ⇒ endpoint 变 ⇒ 所有 artifact 的 provenance 要重签，代价高~~ ——**该成本判断 W5c-6d 复核后判定为错，见 §6.0b**（endpoint 是硬编码常量、provenance 不记 key/endpoint ⇒ 不需要重签）。**列为待拍板（D5-b）**；当前判断为可接受（publishable、无权限语义、服务端 Origin 校验） |
| 反例 | ① 建 `.env` 无效（无 dotenv）；② 本窗口设、另开窗口跑 = 不生效；③ `.gitignore` 原先没有 `.env` 条目（已补 `.env` / `.env.*`） |

### 6.0b D5-b 复核：把「轮换 key」与「改 endpoint」拆开算（W5c-6d / R46）

> 专家第九轮 §3.4 要求复核「轮换代价高」这个判断。**复核结论：原判断错了两处，成本被高估。**

| 环节 | 事实（实测） | 推论 |
|---|---|---|
| endpoint 从哪来 | `gen_candidates.js:10` / `gen_candidates_v2.js:16` 都是**硬编码常量** `https://fem-bench-baseline.app.workbuddy.host`，**不从 key 解析** | 轮换 key（同一应用）⇒ **endpoint 完全不变** |
| provenance 记什么 | 成绩单 `provenance` = `label` / `tasks_path` / `tasks_sha256` / `candidates_dir` / `n_candidates` / `generated_by`；候选文件只记 `model` | **不含 key、不含 endpoint ⇒ 无论怎么轮换都不需要重签 provenance** |
| 重建应用才会变什么 | appid 变 ⇒ 应用子域可能变 ⇒ 要改 `gen_candidates.js` 里**那一行常量** | 成本 = 改 1 行 + 1 次冒烟（R31），**不是重签全部 artifact** |

**⇒ 真实成本排序**：
1. **同应用轮换 publishable secret**：成本 ≈ 0（endpoint 与 provenance 都不动）。**是否支持「同应用轮换」本轮未验证**（未做任何轮换操作，避免影响 W5b-5）——动手前必须先测，不得凭本表当结论。
2. **重建应用**：成本 = 1 行 endpoint 常量 + 1 条冒烟 + 重跑一次 generating；provenance 仍不用重签。
3. **彻底消除历史泄漏**（`git filter-repo` 重写 `efa2b6f`）：会改所有 commit sha ⇒ **这一项才真正需要重签 tag/记录**，与轮换无关，要单独评估。

**待拍板 D5-b**：先测「同应用轮换」；可行则轮换（成本≈0）并记日期；不可行则走重建应用（1 行 + 冒烟），或明确接受风险并记录决策人/日期。

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
