# FEM-Bench-Aero 第五轮复评与 W5 准入评估（W4e / W4f 后）

> **复评日期**：2026-10-25（第五轮）
> **复评对象**：W4e/W4f 整改后的 L3 考卷 v4、RUBRIC v2、成绩单、MSR、负控与 W5 准入条件
> **复评方式**：只读核对 + 按 split 重算 + v2/v3 候选逐条比对 + MSR 分母复核
> **结论先行**：
> **W4e/W4f 把上一轮的核心 P0 基本修掉了：exam/dev 分栏、RUBRIC 预注册、v4 tag/sha256、MSR 依赖预检与失败分层、barrel/panel 契约、澄清字段级、SFR 编造对齐、负控 21/21。**
> **但 W5 只能"有条件启动"：当前 11 条 exam 里有 3 条翼盒失败是任务欠定义（NL 只写"法向"），不是模型能力；MSR 分母还把"编造的澄清题"算进去了；n=11 < 20，underpowered。**
> **W5 判定：Conditional-Go —— 可启动"修题 + 扩量"（W5a/W5b），不可用 45.5% 做模型调优或对外能力承诺。**

---

## 目录

- [0. 复评摘要](#0-复评摘要)
- [1. 变化与交付](#1-变化与交付)
- [2. 已验证的改进（credit）](#2-已验证的改进credit)
- [3. 新发现的问题](#3-新发现的问题)
- [4. W5 准入评估](#4-w5-准入评估)
- [5. 下一步任务执行建议](#5-下一步任务执行建议)
- [6. 防跑偏机制（更新）](#6-防跑偏机制更新)
- [7. 评分卡](#7-评分卡)
- [8. 待拍板](#8-待拍板)
- [附录 A　证据索引](#附录-a证据索引)
- [附录 B　复现命令](#附录-b复现命令)

---

## 0. 复评摘要

### 0.1 三句话结论

1. **W4e/W4f 是实质整改。** exam/dev 分栏落地；`RUBRIC.md` 在 v4 重跑前冻结；`v1.0-l3-v4` tag + `tasks.jsonl.sha256` / `nl_human.jsonl.sha256` / `schema_task.json.sha256`；MSR 加 `gmsh/numpy` 预检与 `env/contract/model/solver` 分层（env=0）；barrel/panel 长桁尺寸补齐；澄清判分改字段级；SFR 编造对齐（R20）；负控 **21/21**；`gen_candidates_v2.js` 的硬编码 fallback key 已删。
2. **headline 现在诚实了，但也暴露了任务欠定义。** 留出 11 条：**TSR 5/11（45.5%）、SFR 5/10（50%）、MSR 4/10（40%）、T1 0/11、value_added +45.5 pp（UNDERPOWERED）**。其中 **3 条翼盒失败都是 `load.direction`**：NL 只写"法向"，v3 候选写 `[0,1,0]`（正确），v4 候选写 `[0,0,1]` / `[0,0,-1]`（错）。这是任务没给坐标系，不是模型不会建模。
3. **MSR 分母仍有一处口径不一致。** barrel d1600 是澄清题静默编造，`msr_l3.py` 仍把它计入分母（`denominator=True`）；RUBRIC 说"澄清/未收敛/编造被拒候选不计"。C-021 的 MSR 4/10 若按 RUBRIC 应为 4/9；all-23 的 12/23 应为 12/22。

**一句话**：**基础设施已经够 W5 用；但 W5 的第一件事不是扩量，是"把 3 条载荷方向任务补清楚、把 MSR 分母对齐"，然后用现有候选重打一次分（不重新生成），再做扩量。**

### 0.2 执行总评

| 工作块 | 评分 | 一句话判断 |
|---|---|---|
| W4e：度量修复 | **A−** | exam/dev、MSR 预检、澄清字段级、SFR 编造、负控 21/21 全部落地 |
| W4f：契约与 v4 | **A−** | RUBRIC 预注册、v4 tag/sha256、barrel/panel 契约、key 清理 |
| 总体 | **26/30** | 统计有效性 1（n=11）⇒ 可扩量，不可对外承诺 |

### 0.3 最重要的建议

> **W5 拆成 W5a（修题 + 重打分 + MSR 对齐，1 天）→ W5b（扩到 n≥20，2–3 天）→ W5c（L2/A3）→ W5d（第二模型/榜单）。**
> **W5a 不需要重新调模型**：用现有 v3 候选 + 修正后的 NL 重新判分，就能把 45.5% 里"任务欠定义"的那部分剥出来。

---

## 1. 变化与交付

### 1.1 提交与 tag

| commit | 内容 |
|---|---|
| `28e66bb` | W4e/W4f：exam 留出口径 + 契约三层一致 + rubric 预注册 |
| `9249063` | 考卷 v4 `schema_task.json.sha256` |
| `06a1407` | 第四轮复评文档归档 |
| `dd66f39` | 记忆收口 |

**tag**：`v1.0-l3-v4`（考卷 v4 冻结）；`v1.0-l3-v4` 与 `v1.0-rc` 并存。

### 1.2 新增/修改的关键文件

| 文件 | 作用 |
|---|---|
| `FEM-Bench-Aero/RUBRIC.md` | L3 判分口径预注册（exam/dev、TSR/SFR/MSR、R17/R20/R19） |
| `FEM-Bench-Aero/CLAIMS.md` | C-021（exam 11 条正式成绩）、C-020 superseded、C-019 21/21 |
| `feagpt_repro/tasks/tasks.jsonl` + `.sha256` | 考卷 v4；L3 split 统一；澄清别名 |
| `feagpt_repro/tasks/nl_human.jsonl` + `.sha256` | L3 NL v4（barrel/panel 补长桁尺寸、offcentre 补孔位） |
| `feagpt_repro/candidates_l3_v3/` | v4 考卷上的 30 条候选（glm-5.3-flash） |
| `feagpt_repro/eval_runs/baseline_scorecard_L3.json` | exam/dev 分栏 + MSR 失败分层 |
| `feagpt_repro/msr_l3.py` | gmsh/numpy 预检、失败分层、spec-required 分母 |
| `feagpt_repro/negative_controls.py` | PC-1 + NC-1..19 → **21/21** |

---

## 2. 已验证的改进（credit）

| 改进 | 实测 |
|---|---|
| exam/dev 分栏 | `exam_definition` = boundary+extrap；`underpowered=true`；`exam`/`dev`/`sfr_all` 三个字段 |
| RUBRIC 预注册 | `RUBRIC.md` 冻结于 v4 重跑前；明确 R17/R20/R19，并承认 W4d 版是 post-hoc |
| v4 冻结 | `v1.0-l3-v4` tag；`tasks.jsonl.sha256`、`nl_human.jsonl.sha256`、`schema_task.json.sha256` |
| MSR 环境预检 | `gmsh/numpy` 缺失 ⇒ rc=2；`env` 失败不进分母；本轮回 `env=0` |
| MSR 失败分层 | `model 8 / contract 3 / env 0`；`gate_fail_counts` 可审计 |
| barrel/panel 长桁尺寸 | v3 候选全部写 `stringer_height=25 / stringer_thickness=2.5`；5 条 barrel 能建 |
| offcentre 孔位 | NL 已写 `(120,60)`；不再欠定义 |
| 澄清字段级 | `clarify_aliases` / `clarify_wrong_keys`；`clarify_wrong_field=0` |
| SFR 编造对齐 | fabricated 2 条（barrel d1600、panel 600x600）均不计 SFR PASS |
| 负控 | **PC-1 + NC-1..19 = 21/21** |
| 硬编码 key | `gen_candidates_v2.js` 只读 `process.env.WORKBUDDY_PUBLISHABLE_KEY`，无 fallback |
| C-019 修复 | 单行、21/21、可审计 |
| fetch/schema/gate3 | `fetch_data` 用 `tarfile`；`validate_schema` UTF-8；`gate3 n_gated_pass=49` |

> 这些是"从能跑到能引用"的关键一步。下面的问题不是否定这些，而是说：**W5 的扩量不能建在一个还有任务歧义的 11 条考卷上。**

---

## 3. 新发现的问题

### 3.1 P0-1　翼盒 `load.direction`：NL 只写"法向"，3 条 exam 失败是猜坐标系

**实测（exam per_task；候选目录：W4d 版 `candidates_l3_v2` = 下文"v3 候选"，W4e/W4f 版 `candidates_l3_v3` = 下文"v4 候选"）**

| exam case | 失败字段 | v3 候选 | v4 候选 | gold |
|---|---|---|---|---|
| `L3_naca4412_wingbox_n_ribs3_chord800` | `load.direction` | `[0,1,0]` | `[0,0,1]` | `[0,1,0]` |
| `L3_naca4412_wingbox_size_skin4` | `load.direction` | `[0,1,0]` | `[0,0,1]` | `[0,1,0]` |
| `L3_naca4412_wingbox_n_ribs7_chord800` | `load.direction` | `[0,1,0]` | `[0,0,-1]` | `[0,1,0]` |

**NL 原文**：

```
"翼尖施加 500 N 集中力（法向），根部固支，展向悬臂。"
```

**问题**

- "法向"没有给出坐标轴。翼盒的 deck 坐标系是 x=弦向、y=弯曲方向、z=展向；"法向"可被理解为 y（翼型法向）或 z（展向/翼面法向）。
- v3 候选猜 `[0,1,0]`（对），v4 候选猜 `[0,0,1]`（错）。**同一个任务，模型两次猜了不同方向**；这说明任务本身没有把方向钉死。
- v4 的 `spec_fidelity` 现在判 `load.direction`（正确，上一轮 L3 漏判已修），所以这 3 条从"碰巧对"变成"明确错"。
- 这 3 条占 exam 11 条的 **27%**；45.5% 的 headline 里有相当一部分是"猜坐标系"而不是"建模能力"。

**修法（P0，W5a）**

1. NL 明确写：`沿 +y（翼型法向/弯曲方向）`，或直接给方向向量 `[0,1,0]`；barrel/panel 同理给坐标系。
2. 在 `tasks.jsonl` 增加 `coordinate_convention` 字段（或 NL 里写死），并在 `RUBRIC.md` 登记"载荷方向属于任务输入，不属于隐藏约定"。
3. **不重新生成**：用现有 v3 候选（`[0,1,0]`）在修正后的 NL/判据下重打分，得到"任务修正后的 TSR"；再用 v4 候选对比，分离"模型猜错"与"任务欠定义"。
4. 新增负控 **NC-20**：任务 NL 未给方向 ⇒ 检查器拒绝（任务构建期），而不是等模型猜错。

---

### 3.2 P0-2　v3→v4 的分数下降没有桥接

**实测**

| 口径 | v3（W4d 重算留出） | v4（W4e/W4f 正式） | Δ |
|---|---:|---:|---:|
| exam TSR | 7/11（63.6%） | 5/11（45.5%） | **−18.1 pp** |
| boundary | 4/4 | 2/4 | −2 |
| extrap | 3/7 | 3/7 | 0 |

**下降的成分（至少三种，必须拆开）**

1. **判据变严（正确）**：v4 判 `load.direction`、`params.layup`、`load.application` 等，v3 的 L3 判据漏判了部分字段。
2. **任务变严/变清楚（部分正确）**：v4 给 barrel/panel 补了长桁尺寸、offcentre 补了孔位；这些是修 bug，不是改难度。
3. **模型输出变了（需解释）**：v3 候选 `[0,1,0]`，v4 候选 `[0,0,1]`；同一模型、同一任务，方向变了。可能是 prompt/schema 改动或模型侧随机性。

**问题**

- README/CLAIMS 直接写"v4 TSR 5/11"，没有解释为什么从 v3 的 63.6% 掉到 45.5%。读者会以为是模型退步，或以为是改考卷。
- 项目自己的 D34-b 纪律要求"形式/口径改动必须两侧判据对照"；这里改的是考卷 + 判据 + prompt，三件事同时发生，**不能归因**。

**修法（P0，W5a）**

做一张 2×2 桥接表（同一 11 条 exam）：

| | v3 候选 | v4 候选 |
|---|---|---|
| **v3 判据** | A（旧成绩） | B（新候选旧判据） |
| **v4 判据** | C（旧候选新判据） | D（新成绩） |

- A→C：判据变严的贡献；
- A→B：模型/prompt 变化的贡献；
- C→D：候选变化的贡献；
- 三者的差必须能解释 63.6→45.5 的 18.1 pp。
- 桥接表落盘 `eval_runs/bridge_v3_v4.json`，进 CLAIMS。

---

### 3.3 P0-3　MSR 分母把"编造的澄清题"算进去了

**实测**

- `L3_fuselage_barrel_d1600_l1600_str8_frm3` 是澄清题（`expected_clarifications=['n_frames']`），模型静默编造 spec。
- `msr_l3.py` 的逻辑是：有 spec ⇒ `denominator=True`；没有 spec ⇒ `denominator=False`。
- 于是 d1600 的 `denominator=True`，`msr_pass=False`，被计入 MSR。
- `RUBRIC.md` 却写："分母 = spec-required 任务（澄清/未收敛/编造被拒候选不计）"。
- C-021 的 **MSR 4/10** 包含 d1600；若按 RUBRIC 排除，应为 **4/9（44.4%）**；all-23 的 12/23 应为 12/22（54.5%）。

**问题**

- 同一件事（d1600 编造）同时进了 FPR（编造 2/4）和 MSR（model fail），双重计数。
- MSR 的 headline 4/10 与 RUBRIC 文字不一致；读者无法判断哪个是权威。

**修法（P0，W5a）**

1. 在 `msr_l3.py` 中：`if t.get('expected_clarifications'): denominator=False`（无论是否产出 spec）；编造只进 FPR。
2. 或者反过来：明确"MSR 也考编造题，编造算 model fail"，并改 RUBRIC；**二选一，写死**。
3. 成绩单增加 `exam.msr` / `dev.msr` 汇总字段（当前只有 all-23 的 `msr_section`，C-021 的 4/10 是手算的）。
4. 重算 C-021 的 MSR；若排除 d1600，headline 改为 4/9（44.4%）。

---

### 3.4 P1 级问题

| # | 问题 | 证据 | 修法 |
|---|---|---|---|
| P1-1 | `exam.msr` 不在成绩单摘要里 | `msr_section` 只有 12/23；C-021 的 4/10 是手算 | 加 `exam.msr` / `dev.msr` |
| P1-2 | `by_split` 只有 TSR/SFR，没有 MSR | `by_split` 结构 | 每 split 加 MSR |
| P1-3 | `negative_controls` 结果含 emoji，GBK 打印崩 | `n_ok=21/21` 但 print 报 `UnicodeEncodeError` | 结果文件去 emoji 或 print 转义 |
| P1-4 | C-021 未记录"v3→v4 下降" | CLAIMS C-021 | 加桥接表与解释 |
| P1-5 | exam 族别不平衡 | 11 条：wingbox 5、barrel 2、open_hole 2、panel 1 | W5b 扩量时按族补 |
| P1-6 | 只有 glm-5.3-flash 一个模型 | scorecard `model` | W5d 加第二模型，验证区分度 |
| P1-7 | `RUBRIC` 说"bc 自创键照罚"，但 `bc` 对非翼盒不判值 | `bc_skip` | 至少判 bc 键集合；或在 RUBRIC 明确"只罚键名" |
| P1-8 | `C-021` MSR 4/10 与 RUBRIC 不一致 | 见 §3.3 | 统一后重写 |
| P1-9 | TSR 5/11 无置信区间 | `tsr` 无 CI | W5b 加 bootstrap CI |
| P1-10 | `C-020` 的 "MSR 11/30" 已在 CLAIMS 标 superseded，但 `README` 历史段未清理 | README 历史叙事 | 保持历史可，但顶部已用 C-021；无需改历史 |

---

## 4. W5 准入评估

### 4.1 W5 的定义（ROADMAP）

W5 = "重跑与扩量"：用冻结 v3/v4 + 预注册 rubric 重跑；留出集扩到 ≥20；L2 澄清基线；A3 修复基线；失败样本回流。

### 4.2 准入条件核对

| 条件 | 状态 | 说明 |
|---|---|---|
| 考卷冻结 + tag/sha256 | ✅ | `v1.0-l3-v4` + 三个 sha256 |
| rubric 预注册 | ✅ | `RUBRIC.md` 冻结于重跑前 |
| MSR 环境预检 | ✅ | gmsh/numpy 预检；env=0 |
| 契约三层一致 | ✅ 基本 | barrel/panel 长桁尺寸、额外键、澄清字段级 |
| 负控全绿 | ✅ | 21/21 |
| 澄清字段级 | ✅ | `clarify_aliases`/`clarify_wrong_keys`；wrong_field=0 |
| SFR 编造对齐 | ✅ | fabricated 不计 PASS |
| **exam 任务无歧义** | ❌ | 3 条翼盒 `load.direction` 只写"法向" |
| **MSR 分母一致** | ❌ | 编造澄清题被计入 |
| **留出 n≥20** | ❌ | 当前 11 |
| **第二模型** | ❌ | 只有 glm-5.3-flash |
| **CI** | ❌ | TSR/SFR/MSR 无区间 |

### 4.3 判定

> **Conditional-Go。**
>
> - **可以启动**：W5a（修题 + 重打分 + MSR 对齐）与 W5b（扩到 n≥20）。
> - **不可以启动**：用当前 45.5% 做模型调优、做对外能力承诺、或把 v3→v4 的下降解释为模型退步。
> - **理由**：基础设施（冻结、预注册、负控、MSR 分层）已经够 W5 用；但考卷还有 27% 的 exam 失败来自任务欠定义，n=11 也不足以判断模型改进。W5 本身（扩量）就是修复 n 的手段，所以不是"等一切完美再开始"，而是"先修题、再扩量、再调模型"。

---

## 5. 下一步任务执行建议

### 5.1 W5a（1 天）：修题 + 重打分 + MSR 对齐

| # | 任务 | 具体动作 | 验收 |
|---|---|---|---|
| 1 | 修 `load.direction` NL | 翼盒 NL 写"沿 +y（弯曲方向）"或给向量；barrel/panel 同理 | 3 条翼盒不再猜方向 |
| 2 | 用现有候选重打分（不重新生成） | 用 v3 候选（`[0,1,0]`）在修正 NL/判据下重跑 `score_baseline` | 得到"修题后 TSR" |
| 3 | v3→v4 桥接表 | A/B/C/D 四格；拆判据/模型/任务 | `bridge_v3_v4.json`；18.1 pp 可解释 |
| 4 | MSR 分母对齐 | 澄清题一律不计分母；或改 RUBRIC 并写死 | C-021 MSR 4/9 或 4/10 二选一 |
| 5 | 成绩单加 `exam.msr`/`dev.msr` | `msr_l3.py` 汇总 | 不再手算 |
| 6 | 更新 C-021 | 写桥接、MSR 口径、underpowered | CLAIMS 自洽 |
| 7 | 修负控 emoji 打印 | 去 emoji 或转义 | GBK 控制台可跑 |

### 5.2 W5b（2–3 天）：扩到 n≥20

| # | 任务 | 具体动作 | 验收 |
|---|---|---|---|
| 8 | 扩 L3 考卷 | 用剩余 25 条 case 派 L3，或新增几何；按族平衡 | exam ≥20 |
| 9 | 内插型 ID test | 留出内插点（v1.1 计划） | 与 boundary/extrap 分列 |
| 10 | 重跑 T0/T1/T2 | 新 exam 上重算地板 | T1 exam 地板可引用 |
| 11 | 重跑 L3 基线 | 冻结 v5 + 预注册 rubric（如需改） | exam n≥20，给 CI |
| 12 | 第二模型 | 至少再加一个可引用模型 | 两模型 TSR 差异 + CI |
| 13 | 失败归因 | env/contract/model/solver + 字段级 | 每条失败有原因 |

### 5.3 W5c（2–3 天）：L2 / A3

| # | 任务 | 验收 |
|---|---|---|
| 14 | L2 澄清基线 | 澄清题 TSR/FPR；字段级 |
| 15 | A3 修复基线 | 注入缺陷 + 闸报告 → 修复成功率/轮数 |
| 16 | 失败样本回流 | 回流池 + 专家确认 |

### 5.4 W5d（2–3 天）：榜单与协议

| # | 任务 | 验收 |
|---|---|---|
| 17 | 榜单协议 | 固定 exam、固定 rubric、CI、模型 id/日期 |
| 18 | 第三方复现 | 新机 fetch + 一条命令跑出同一成绩 |
| 19 | 发布说明 | v1.0-l3-v5 + dataset card + RUBRIC |

### 5.5 明确不要做

- ❌ 不要用 45.5% 做模型调优的基线（先修题、先扩量）；
- ❌ 不要把 v3→v4 的下降说成"模型退步"（先做桥接）；
- ❌ 不要在 n=11 上判 value_added PASS；
- ❌ 不要在未冻结 v5 的情况下继续改考卷；
- ❌ 不要用单模型成绩做对外榜单。

---

## 6. 防跑偏机制（更新）

### 6.1 新增红线条

| # | 红线 | 违反示例 |
|---|---|---|
| **R21** | **任务 NL 必须给坐标系/载荷方向**；不得用"法向"这类未定义词 | 翼盒 3 条因 `[0,0,1]` 失败 |
| **R22** | **口径/考卷/prompt 同时变化时必须做桥接表**；不能只报新分 | v3 63.6%→v4 45.5% 无解释 |
| **R23** | **MSR 分母必须与 RUBRIC 一致**；编造澄清题不得双重计数 | d1600 同时进 FPR 和 MSR |
| **R24** | **n_exam < 20 不得做模型调优/对外承诺**；只能做扩量 | 用 5/11 判"模型行不行" |

### 6.2 负控扩展

| 编号 | 注入 | 期望 | 当前 |
|---|---|---|---|
| **NC-20** | 任务 NL 未给载荷方向 | 任务构建期拒绝 | ❌ 待加 |
| **NC-21** | MSR 分母含澄清/编造题 | 检查器拒绝 | ❌ 待加 |
| **NC-22** | 成绩单缺 `exam.msr` | 检查器拒绝 | ❌ 待加 |

### 6.3 CLAIMS 更新

| claim | 处置 |
|---|---|
| C-021（exam 5/11 / SFR 5/10 / MSR 4/10 / Δ+45.5pp） | 保留，补桥接表与 MSR 口径；若排除 d1600，MSR 改 4/9 |
| 新 C-024 | v3→v4 桥接：判据/模型/任务各贡献多少 pp |
| 新 C-025 | 修题后重打分（用 v3 候选，不重新生成） |
| C-020 | 已 superseded；保持 |

### 6.4 节奏（不变）

- 每周十维评分卡 + 红线条；
- 每个 W 块结束做完整复评 + 负控 + 全链正控；
- 每 2 个里程碑独立复评；
- 执行人不能给自己的评分器签字。

---

## 7. 评分卡

| # | 维度 | 分数 | 理由 |
|---|---|---:|---|
| 1 | 目标一致性 | 3 | benchmark/verifier 主轴未变 |
| 2 | 任务有效性 | 2 | v4 冻结、offcentre 补孔位；但 3 条翼盒载荷方向欠定义 |
| 3 | 判分有效性 | 3 | 负控 21/21、字段级澄清、SFR 编造对齐；MSR 分母待统一 |
| 4 | 证据等级 | 3 | C-021 exam 口径、失败分层、tag/sha256 |
| 5 | 可复现性 | 3 | v4 tag + sha256 + venv + fetch/schema 修复 |
| 6 | 版本治理 | 3 | git + tag v1.0-l3-v4 + 考卷 sha256 |
| 7 | 文档真实性 | 2 | C-021 诚实标 underpowered；但 v3→v4 下降未解释 |
| 8 | 统计有效性 | 1 | n=11、无 CI、value_added underpowered |
| 9 | 范围纪律 | 3 | 红线条 R1–R20 在 |
| 10 | 计划执行 | 3 | W4e/W4f 按期收口 |
| **总分** | | **26/30** | **统计有效性 1 ⇒ 不可对外承诺；W5 可 Conditional-Go** |

> 与 CLAIMS 自评 29 的差异：任务有效性（载荷方向）−1、文档真实性（下降未解释）−1、统计有效性（n=11/无 CI）−1。

---

## 8. 待拍板

| # | 事项 | 建议 |
|---|---|---|
| 1 | 是否承认 3 条翼盒失败是任务欠定义，不是模型退步 | **承认**；修 NL 后重打分 |
| 2 | 是否接受 W5 拆成 W5a（修题+桥接+MSR）/W5b（扩量）/W5c（L2/A3）/W5d（榜单） | **接受** |
| 3 | 是否接受"n_exam<20 不做模型调优/对外承诺" | **接受**；R24 |
| 4 | 是否接受 MSR 分母排除澄清/编造题 | **接受**；C-021 MSR 改 4/9 或写死 4/10 |
| 5 | 是否接受桥接表（A/B/C/D）作为 W5a 的硬交付 | **接受**；R22 |
| 6 | 是否接受 W5b 扩到 n≥20 后才跑第二模型与 CI | **接受** |
| 7 | 是否接受 `load.direction` 写进 NL 而非隐藏约定 | **接受**；R21 |

---

## 附录 A　证据索引

| 结论 | 证据 |
|---|---|
| exam 11 条 TSR 5/11、SFR 5/10 | `baseline_scorecard_L3.json :: exam` |
| MSR exam 4/10（分母 10） | `msr_section.per_task` 按 split 统计；boundary 4 den 2 pass、extrap 6 den 2 pass |
| 3 条翼盒 `load.direction` 失败 | `per_task` failed_fields；v3 候选 `[0,1,0]` vs v4 `[0,0,1]` |
| NL 只写"法向" | `tasks/nl_human.jsonl` 三条翼盒 |
| offcentre 已补孔位 | `nl_human.jsonl` 含 `(120,60)` |
| barrel 候选 stringer 25/2.5 | `candidates_l3_v3/*barrel*.json` |
| d1600 编造且 denominator=True | `msr_section.per_task` 第一条 |
| RUBRIC 说澄清不计 | `RUBRIC.md` §4 |
| 负控 21/21 | `eval_runs/negative_controls.json` |
| v4 tag/sha256 | `git tag`、`tasks/*.sha256`、`schema_task.json.sha256` |
| key fallback 已删 | `gen_candidates_v2.js` 第 18 行 |
| C-019 单行 | `CLAIMS.md` |

## 附录 B　复现命令

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# exam/dev 与 MSR 按 split 汇总
"$PY" - <<'PY'
import json
sc=json.load(open('eval_runs/baseline_scorecard_L3.json',encoding='utf-8'))
print('exam',sc['exam'])
print('dev',sc['dev'])
msr={r['task_id']:r for r in sc['msr_section']['per_task']}
tasks={json.loads(l)['task_id']:json.loads(l) for l in open('tasks/tasks.jsonl',encoding='utf-8') if json.loads(l)['input_level']=='L3'}
for sp in ['boundary_holdout','extrapolation_test']:
    ids=[t for t in tasks if tasks[t]['split_v2']==sp and msr.get(t,{}).get('denominator')]
    print(sp,'MSR',sum(msr[t]['msr_pass'] for t in ids),'/',len(ids))
PY

# 三条翼盒的 load.direction 对照
"$PY" - <<'PY'
import json,os
for tid in ['L3_naca4412_wingbox_n_ribs3_chord800','L3_naca4412_wingbox_size_skin4','L3_naca4412_wingbox_n_ribs7_chord800']:
    print('===',tid)
    for ver in ['candidates_l3_v2','candidates_l3_v3']:
        p=f'{ver}/{tid}.json'
        if os.path.exists(p):
            s=json.load(open(p,encoding='utf-8')).get('spec') or {}
            print(' ',ver,s.get('load'))
PY

# 负控
PYTHONIOENCODING=utf-8 "$PY" negative_controls.py
```

---

> **本文件是第五轮复评的产物，不修改任何既有项目文件。**
> 本轮比对了 exam per_task、v2/v3 候选的 `load.direction`、MSR 分母与 RUBRIC 口径；未改动 `eval_runs/` 之外的任何产物。
> **W5 准入结论：Conditional-Go —— 先 W5a 修题/桥接/MSR，再 W5b 扩到 n≥20；在 n≥20 之前，45.5% 只能作 underpowered 的现状描述，不能作能力结论。**
