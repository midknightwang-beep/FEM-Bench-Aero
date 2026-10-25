# FEM-Bench-Aero 第七轮复评与执行纠偏（W5a' / W5b-2 后）

> **复评日期**：2026-10-25（第七轮）
> **复评对象**：W5a'（reports/ + check_claims + 负控 28/28 + C-021 复现 + CI）与 W5b-2（考卷 v6：55 条 L3 / exam 25）
> **复评方式**：只读核对 + check_claims 复跑 + v6 任务统计 + 文档计数一致性检查
> **结论先行**：
> **第六轮的三个 P0 全部落地：官方 artifact 入 `reports/`、`check_claims.py` 19 条 active / 21 个 artifact 全过、C-021 用 `papers/tasks_v4.jsonl` 逐项复现、负控 28/28、bootstrap CI 落地、v6 考卷 55 条 L3 / exam 25 冻结。**
> **W5b 已经具备执行条件；唯一阻塞是 `WORKBUDDY_PUBLISHABLE_KEY` 未设置（`candidates_l3_v6` 尚未生成）。**
> **此外有 5 处文档计数漂移（C-010 140→165、C-011 v1.1→v6、C-019 27→28、C-027/ RUBRIC / W5B_PLAN 把 C-021 写成 19 条、README RUBRIC v3.1/v4 混用），`check_claims` 是结构检查、抓不到——建议加语义计数检查。**

---

## 目录

- [0. 复评摘要](#0-复评摘要)
- [1. 变化与交付](#1-变化与交付)
- [2. 已验证的改进（credit）](#2-已验证的改进credit)
- [3. 新发现的问题](#3-新发现的问题)
- [4. W5b 准入评估](#4-w5b-准入评估)
- [5. 下一步任务执行建议](#5-下一步任务执行建议)
- [6. 防跑偏机制（更新）](#6-防跑偏机制更新)
- [7. 评分卡](#7-评分卡)
- [8. 待拍板](#8-待拍板)
- [附录 A　证据索引](#附录-a证据索引)
- [附录 B　复现命令](#附录-b复现命令)

---

## 0. 复评摘要

### 0.1 三句话结论

1. **第六轮的 P0 全部修好了。** `reports/` 入库（22 个文件：v4/v5 成绩单、桥接 A/B/C/D、bootstrap CI、MSR、负控 28、T1 地板、v4/v5/v6 考卷快照）；`check_claims.py` 复跑 **19 条 active / 21 个 artifact 全过**；C-021 用 `papers/tasks_v4.jsonl` 重跑得 **exam 5/11、MSR 4/9、dev 11/19**，逐项一致；负控 **28/28**；考卷 v6 冻结为 **55 条 L3 / exam 25（boundary 6 + extrap 13 + interp 6）**。
2. **W5b 只差一把 key。** `candidates_l3_v6` 尚未生成；`W5B_PLAN.md` 的 W5b-0 明确写"拿 `WORKBUDDY_PUBLISHABLE_KEY`（当前 shell 未设，只读 env、无 fallback）"。除此之外，v6 考卷、RUBRIC v4、三栏口径、CI、`reports/`、负控全部就绪。
3. **还剩 5 处文档计数漂移。** C-010 仍写"140 行 = L1 55 + L2 55 + L3 30"（实际 165 = 55+55+55）；C-011 仍写"真内插 ID test = v1.1"（v6 已有 interp 6）；C-019 coverage 列写 27（实际 28）；C-027 / RUBRIC §1 / W5B_PLAN 写"C-021 的 19 条"（C-021 是 **11**；19 是 v6 全 L3 的 boundary+extrap；25 是 v6 headline）；README 同时写 RUBRIC v3.1 与 v4。`check_claims` 只查 artifact 存在/追踪/路径，抓不到这些**语义**漂移。

**一句话**：**工程上已经可以跑 W5b；先把 key 设上，再把 5 处计数改对、给 `check_claims` 加语义检查。**

### 0.2 执行总评

| 工作块 | 评分 | 一句话判断 |
|---|---|---|
| W5a'：artifact 入库 + 自检 + CI | **A** | 第六轮 P0 全部落地；C-021 可逐项复现 |
| W5b-2：考卷 v6 | **A−** | 55 条 L3 / exam 25 冻结；三栏预注册；老题零改动 |
| 总体 | **28/30** | 可跑 W5b；文档语义计数与 key 是剩余项 |

---

## 1. 变化与交付

### 1.1 提交与 tag

| commit | 内容 |
|---|---|
| `266cb85` | W5a'：reports/ + check_claims + 负控 27/27 + C-021 复现 + CI |
| `1abad3f` | make_nl_human 名额可配（默认与 v5 冻结稿逐字节一致） |
| `03a97f2` | W5b-2：考卷 v6 冻结（C-027），L3 30→55、exam 11→25 |
| `861dfc7` | clean-clone 端到端复现 + 缺 gold 前置闸（NC-26，负控 28/28） |

**tag**：`v1.0-l3-v4` / `v1.0-l3-v5` / **`v1.0-l3-v6`**。

### 1.2 新增/修改的关键文件

| 文件 | 作用 |
|---|---|
| `feagpt_repro/reports/` | 官方 artifact 唯一出处：v4/v5 成绩单、bridge A/B/C/D、bootstrap CI、MSR、负控 28、T1 地板、v4/v5/v6 考卷快照 |
| `feagpt_repro/reports/INDEX.md` | 官方 vs 诊断；一条一条复现命令；版本对照表 |
| `feagpt_repro/check_claims.py` | 19 active / 21 artifact：存在 + git 追踪 + 路径一致 + sha256 |
| `feagpt_repro/bootstrap_ci.py` | exam 任务 bootstrap 95% CI（B=4000, seed=20261025） |
| `feagpt_repro/export_msr.py` | 从成绩单抽 `msr_section` |
| `FEM-Bench-Aero/W5B_PLAN.md` | W5b 执行计划（A 路径：interp 6 → exam 25） |
| `feagpt_repro/tasks/tasks.jsonl` | v6：165 行 = L1 55 + L2 55 + L3 55；exam 25 |
| `feagpt_repro/reports/papers/tasks_v6.jsonl` | v6 考卷快照（165 行） |

---

## 2. 已验证的改进（credit）

| 改进 | 实测 |
|---|---|
| 官方 artifact 入库 | `git ls-files feagpt_repro/reports` 非空；22 个文件 |
| CLAIMS 自检 | `check_claims.py`：**19 active / 21 artifact / 0 fail**；sha256 + mtime 落盘 |
| C-021 可复现 | `score_baseline.py --tasks papers/tasks_v4.jsonl` ⇒ exam **5/11**、SFR 5/10、dev 11/19、问错字段 0；`msr_l3.py` ⇒ exam MSR **4/9** |
| bootstrap CI | exam TSR 45.5% **CI95 [18.2, 72.7]**；SFR 50% [20.0, 80.0]；MSR 44.4% [11.1, 77.8] |
| 负控 | **28/28**（PC-1 + NC-1..22 + NC-15b + NC-23..26） |
| C-019 | 28/28；文本已自证"21/23 是漏计 NC-15b 的错账" |
| C-024 | 桥接归因改为 **−3 wingbox load.direction + 1 d2000 extra**；不再说"全部 3 条" |
| C-025 | 明确 diagnostic；旧候选不能评新考卷（R28） |
| C-027 | v6：55 L3 / exam 25（boundary 6 + extrap 13 + interp 6）；L1/L2 零改动；老 30 条 L3 仅新增 `exam_stratum` |
| 三栏 exam | `exam_stratum` 字段；`score_baseline.py` 的 `is_exam` 向后兼容（v4/v5 无字段 ⇒ 旧行为） |
| clean-clone | `fetch_data.py` + 一条命令复现 C-021；缺 gold 时 `require_dataset()` 硬报错（NC-26） |
| 考卷快照 | `papers/tasks_v4/v5/v6.jsonl` + `nl_human_v4/v5/v6.jsonl` + `SHA256SUMS` |
| CI | `bootstrap_ci.py`；`check_claims.py` + `negative_controls.py` 作为 W 块收口必跑 |

> 这一轮把"证据"真正钉住了。下面只剩文档语义计数与 key。

---

## 3. 新发现的问题

### 3.1 P0-0　唯一阻塞：`WORKBUDDY_PUBLISHABLE_KEY` 未设置

**实测**

- `candidates_l3_v6` 不存在（`ls -d candidates_l3_v6` 无）。
- `W5B_PLAN.md` W5b-0 写："拿 `WORKBUDDY_PUBLISHABLE_KEY`（当前 shell 未设，只读 env、无 fallback）"。
- `gen_candidates_v2.js` 只读 `process.env.WORKBUDDY_PUBLISHABLE_KEY`，无 fallback（安全上正确）。

**影响**

- W5b-3（生成 55 条候选）无法启动；W5b-4（打分）、W5b-5（第二模型）、W5b-6（归因）全部排队。
- 这不是代码缺陷，是**外部依赖**；但它是当前唯一的硬阻塞。

**修法**

1. 在终端设置环境变量（不要把 key 写进仓库/聊天）：
   ```powershell
   $env:WORKBUDDY_PUBLISHABLE_KEY = '<key>'
   ```
2. 先跑 `node gen_candidates_v2.js --limit 1` 验证 1 条合法候选。
3. 再跑 55 条全量。

---

### 3.2 P1-1　C-010 任务层计数 140 未更新到 165

**实测**

| 来源 | 数值 |
|---|---|
| C-010 文本 | "任务层 140 行 = L1 55 + L2 55 + **L3 30**" |
| 当前 `tasks.jsonl` | **165 行 = L1 55 + L2 55 + L3 55** |
| C-027 | v6 = 55 L3 / exam 25 |

**影响**：C-010 是 active claim；`check_claims` 只查 artifact 存在，不查行数，所以全过。读者按 C-010 会以为 L3 只有 30 条。

**修法**：C-010 改为 "165 行 = L1 55 + L2 55 + L3 55（v6）"；或标 superseded、由 C-027 取代。加语义检查（见 §3.6）。

---

### 3.3 P1-2　C-011 "真内插 ID test = v1.1" 已过时

**实测**

- C-011 仍写："boundary_holdout 6 条；**真内插 ID test = v1.1**"。
- v6 已有 **interp 6 条**（`exam_stratum=interpolation`，wingbox 2 / open_hole 2 / barrel 1 / panel 1），C-027 冻结。

**修法**：C-011 改为 "boundary 6 + v6 interp 6（C-027）"；或标 superseded。

---

### 3.4 P1-3　C-019 coverage 列写 27，实际 28

**实测**

- C-019 文本："**28/28** = PC-1 + NC-1..22 + NC-15b + NC-23..26"。
- C-019 coverage 列："27 条"；`RUBRIC.md` v3.1 版本记录也写"负控 23→24→27"。
- `reports/negative_controls_28.json`：`n_cases=28, n_ok=28`。

**修法**：coverage 改 28；RUBRIC v3.1 记录补 NC-26；加语义检查。

---

### 3.5 P1-4　"C-021 的 19 条" 是三处相同的计数错误

**实测**

| 来源 | 原文 | 实际 |
|---|---|---|
| C-027 | "与 C-021 的 **19 条**口径不可直接比" | C-021 exam = **11** |
| RUBRIC §1 | "exam（19 条，全 L3 化后）… v4 口径，C-021 用过" | C-021 用过 **11**（30 条 L3 时） |
| W5B_PLAN | "与 C-021 的 **19 条**口径不可直接比" | C-021 = **11** |

**正确的三个数**

| 口径 | 条数 | 构成 |
|---|---:|---|
| C-021（v4，30 条 L3） | **11** | boundary 4 + extrap 7 |
| v6 的 boundary+extrap（55 条 L3 全量） | **19** | boundary 6 + extrap 13 |
| v6 headline（合并 exam） | **25** | boundary 6 + extrap 13 + interp 6 |

**影响**

- 读者会把 C-021 的 11 条误当成 19 条；"不可直接比"的对象也错了。
- 这是纯文本错误，但直接关系到"官方 headline 的分母"，属于对外数字的可信度问题。

**修法**：三处统一改成 "C-021 = 11；v6 boundary+extrap = 19；v6 headline = 25"；RUBRIC §1 表格拆成三行。

---

### 3.6 P1-5　`check_claims` 是结构检查，抓不到语义计数

**实测**

- `check_claims.py` 逐条检查：artifact 存在、git 追踪、路径一致、sha256；**不检查 claim 文本里的数字**。
- 因此 C-010（140 vs 165）、C-011（v1.1 vs v6）、C-019（27 vs 28）、C-027（19 vs 11）全部 PASS。

**修法（P1，W5b 前）**

1. 加一个 `claims_semantic_check`（可以是 `check_claims.py` 的一个 `--semantic` 模式）：
   - C-010：解析 "任务层 (\d+) 行"，对比 `tasks.jsonl` 行数；
   - C-019：解析 "(\d+)/(\d+)"，对比 `negative_controls_28.json` 的 `n_cases/n_ok`；
   - C-021：解析 "exam (\d+) 条"，对比 `baseline_scorecard_L3_v4.json` 的 `exam.n`；
   - C-027：解析 "exam (\d+)"，对比 `tasks_v6.jsonl` 的 `exam_stratum` 计数；
   - README/RUBRIC 的版本号与 `RUBRIC.md` 的 "版本：vX" 一致。
2. 新增负控 **NC-27**：把 C-010 文本改成 140、artifact 仍是 165 ⇒ 语义检查必须 FAIL。
3. 进 W 块收口必跑（与 `check_claims.py` 一起）。

---

### 3.7 P1-6　README 的 RUBRIC 版本与 W5b 状态不一致

**实测**

- README 第 12 行："判分口径 RUBRIC.md **v4**"。
- README 第 13 行："判分口径见 RUBRIC.md（**v3.1** 预注册）"。
- `RUBRIC.md` 顶部："**版本：v4**"。
- README "看当前计划" 仍写 "下一步 W5b = v5 重生成 + exam 扩到 n≥20 + CI + 第二模型"；实际 W5b-2（v6 exam 25）已完成，下一步是 W5b-3 生成（等 key）。

**修法**：README 第 13 行改 v4；"看当前计划" 改为 "W5b-2 已完成（v6 exam 25）；W5b-3 等 key"。

---

### 3.8 P1-7　W5b 的统计与族别风险（已在 W5B_PLAN 记录，复评保留）

| 风险 | 说明 |
|---|---|
| 合并 25 的构成变化 | interp 6 更容易 ⇒ 合并 TSR 会比 C-021 的 45.5% 高；**不是模型变好**，必须三栏并列 |
| 分栏 n 小 | boundary 6 / extrap 13 / interp 6；**只报不判** |
| 族别不平衡 | v6 exam 25：wingbox 14、open_hole 6、barrel 3、panel 2；barrel/panel 仍不足以做族级结论 |
| 单模型 | 仍只有 glm-5.3-flash；W5b-5 加第二模型 |
| CI 宽度 | v4 n=11 的 TSR CI [18.2,72.7]；v6 n=25 会窄一些，但三栏仍宽 |

---

## 4. W5b 准入评估

### 4.1 条件核对

| 条件 | 状态 | 说明 |
|---|---|---|
| 官方 artifact 入库 | ✅ | `reports/` 22 文件 |
| CLAIMS 自检 | ✅ 结构 | 19 active / 21 artifact / 0 fail |
| C-021 可复现 | ✅ | `papers/tasks_v4.jsonl` ⇒ 5/11、MSR 4/9 |
| 负控 | ✅ | 28/28 |
| CI | ✅ | bootstrap v4/v5 |
| v6 考卷冻结 | ✅ | 55 L3 / exam 25；tag `v1.0-l3-v6` |
| RUBRIC v4 预注册 | ✅ | 三栏 exam；向后兼容 |
| clean-clone | ✅ | fetch_data + 一条命令；NC-26 |
| **候选生成 key** | ❌ | `WORKBUDDY_PUBLISHABLE_KEY` 未设 |
| **v6 基线** | ⏳ | `candidates_l3_v6` 未生成 |
| **第二模型** | ⏳ | W5b-5 |
| **语义 CLAIMS 检查** | ❌ | 5 处计数漂移 |

### 4.2 判定

> **Go for W5b-3（生成）/ W5b-4（打分）/ W5b-5（第二模型）/ W5b-6（归因），条件是设置 key。**
>
> - 这是本轮第一次给出无条件的 "Go"（除外部 key 外）；科学、判分、证据、版本、CI 都已就绪。
> - 但**对外引用仍只能用 C-021（5/11, n=11 underpowered）**；v6 的 25 条基线在跑出来之前不进 CLAIMS/README/对外。
> - 文档计数漂移是 P1，可与 W5b-3 并行修；不要因为改文档而停止生成。

---

## 5. 下一步任务执行建议

### 5.1 W5b-0（用户侧，10 分钟）：设置 key

| # | 任务 | 验收 |
|---|---|---|
| 1 | 终端设置 `WORKBUDDY_PUBLISHABLE_KEY`（不写进仓库/聊天） | `echo $env:WORKBUDDY_PUBLISHABLE_KEY` 非空 |
| 2 | `node gen_candidates_v2.js --limit 1` | 1 条合法候选；无 `llm_error` |

### 5.2 W5b-3（0.5 天）：v6 全量生成

| # | 任务 | 验收 |
|---|---|---|
| 3 | 生成 55 条候选到 `candidates_l3_v6/` | 55 个 JSON；`turns_used` 全记录 |
| 4 | 生成后先跑 `score_baseline.py`（不跑 MSR） | exam 25 的 TSR/SFR；三栏明细 |
| 5 | 失败归因初筛 | 区分 env/contract/model；先修 contract 类 |

### 5.3 W5b-4（1–2 天）：v6 正式成绩

| # | 任务 | 验收 |
|---|---|---|
| 6 | `score_baseline.py --tasks papers/tasks_v6.jsonl --report reports/baseline_scorecard_L3_v6.json` | exam 25；三栏；`provenance` 落盘 |
| 7 | `msr_l3.py --tasks ... --report ...` | 全链 MSR；失败分层 env=0 |
| 8 | `bootstrap_ci.py` | 合并 25 与三栏各自 CI |
| 9 | 与 C-021 的对照 | 写明"构成变化，不可直接比"；给三栏 |
| 10 | CLAIMS 新 claim | C-028：v6 正式成绩；artifact `reports/...v6.json` |

### 5.4 W5b-5（1 天）：第二模型

| # | 任务 | 验收 |
|---|---|---|
| 11 | 用 SDK 实测可用 id（不猜） | 第二模型 id 可引用 |
| 12 | 同 v6 考卷跑第二模型 | 两模型 TSR 差异 + 各自 CI |
| 13 | 区分度检查 | 若两模型差异 < CI 宽度，说明当前 n 仍不足 |

### 5.5 W5b-6（0.5 天）：失败归因

| # | 任务 | 验收 |
|---|---|---|
| 14 | 字段级失败清单 | 每条失败有 `failed_fields` |
| 15 | env/contract/model/solver 分层 | env 不计模型失败 |
| 16 | 失败样本回流池 | 可进入 v1.1 数据扩展 |

### 5.6 文档清理（与 W5b-3 并行，0.5 天）

| # | 任务 | 验收 |
|---|---|---|
| 17 | C-010 165；C-011 v6 interp；C-019 28；C-027/RUBRIC/W5B_PLAN 三数 11/19/25 | 文本与 artifact 一致 |
| 18 | README RUBRIC v4；W5b-2 已完成、W5b-3 等 key | 一致 |
| 19 | `check_claims.py --semantic` + NC-27 | 语义计数不符 ⇒ FAIL |
| 20 | `reports/INDEX.md` 加 v6 状态 | 官方/诊断/待跑三分 |

### 5.7 明确不要做

- ❌ 不要把 v6 的 25 条合并 TSR 与 C-021 的 11 条 45.5% 直接比；
- ❌ 不要因为 interp 更容易就把合并 25 当成"模型变好"；
- ❌ 不要在 n=25 之前做调优/对外承诺；
- ❌ 不要用单模型成绩做榜单；
- ❌ 不要把 key 写进仓库/聊天。

---

## 6. 防跑偏机制（更新）

### 6.1 新增红线条

| # | 红线 | 违反示例 |
|---|---|---|
| **R29** | **CLAIMS 语义计数必须自检**；文本数字与 artifact 不一致 ⇒ FAIL | C-010 140 vs 165 |
| **R30** | **v6 合并 25 与 C-021 的 11 条不得直接比**；三栏必须并列 | 用 25 条合并数说"从 45.5% 提升" |
| **R31** | **W5b 生成前必须 key 预检 + 1 条冒烟**；不得直接 55 条盲跑 | 先 `--limit 1` |

### 6.2 负控扩展

| 编号 | 注入 | 期望 | 当前 |
|---|---|---|---|
| **NC-27** | C-010 文本 140、artifact 165 | 语义检查 FAIL | ❌ 待加 |
| **NC-28** | v6 候选缺失却出成绩单 | 成绩单要求 `n_candidates=55` | ❌ 待加 |
| **NC-29** | 合并 25 与 C-021 11 混比 | 报告检查器拒绝 | ❌ 待加 |

### 6.3 节奏（不变）

- 每周十维评分卡 + 红线条；
- 每个 W 块结束：`check_claims.py`（结构 + 语义）+ `negative_controls.py` + 全链正控；
- 每 2 个里程碑独立复评；
- 执行人不能给自己的评分器签字。

---

## 7. 评分卡

| # | 维度 | 分数 | 理由 |
|---|---|---:|---|
| 1 | 目标一致性 | 3 | benchmark/verifier 主轴未变 |
| 2 | 任务有效性 | 3 | v6 55 L3 / exam 25；三栏预注册；坐标系写死 |
| 3 | 判分有效性 | 3 | 负控 28/28；R17/R20/R21/R23；MSR 分母 |
| 4 | 证据等级 | 3 | reports/ 入库；check_claims 19/21；bootstrap CI |
| 5 | 可复现性 | 3 | C-021 用 papers/tasks_v4 逐项复现；clean-clone + fetch_data |
| 6 | 版本治理 | 3 | tag v4/v5/v6 + sha256 + 考卷快照 |
| 7 | 文档真实性 | 2 | 5 处语义计数漂移；README 版本混用 |
| 8 | 统计有效性 | 2 | C-021 n=11 underpowered；v6 n=25 已冻结但未跑；CI 已有 |
| 9 | 范围纪律 | 3 | 红线 R1–R28 在 |
| 10 | 计划执行 | 3 | W5a'/W5b-2 按期 |
| **总分** | | **28/30** | **≥24 且无单项 ≤1 ⇒ Go for W5b** |

> 与 CLAIMS 自评 29 的差异：文档真实性 −1（语义漂移）。统计有效性 2 是因为 v6 基线尚未跑；W5b-4 会补齐。

---

## 8. 待拍板

| # | 事项 | 建议 |
|---|---|---|
| 1 | 是否由用户在终端设置 `WORKBUDDY_PUBLISHABLE_KEY` 并启动 W5b-3 | **是**；唯一阻塞 |
| 2 | 是否接受 W5b 三栏（boundary 6/extrap 13/interp 6）+ 合并 25 的口径 | **接受**；RUBRIC v4 已预注册 |
| 3 | 是否接受 C-021 的 11 条与 v6 的 25 条不可直接比 | **接受**；R30 |
| 4 | 是否接受文档计数清理 + `check_claims --semantic` 与 W5b-3 并行 | **接受** |
| 5 | 是否接受 W5b-5 第二模型在 W5b-4 之后 | **接受** |
| 6 | 是否接受 v6 正式成绩先不对外，待三栏 + CI + 失败归因齐全 | **接受** |

---

## 附录 A　证据索引

| 结论 | 证据 |
|---|---|
| reports/ 入库 | `git ls-files feagpt_repro/reports` = 22 |
| check_claims 全过 | `check_claims.py` 输出 19 active / 21 artifact / 0 fail |
| C-021 复现 | `reports/baseline_scorecard_L3_v4.json` exam 5/11；`msr_l3_v4.json` exam 4/9 |
| CI | `reports/bootstrap_ci_L3_v4.json` TSR [18.2,72.7] |
| 负控 28/28 | `reports/negative_controls_28.json` |
| v6 55 L3 / exam 25 | `tasks/tasks.jsonl`；`exam_stratum` 6/13/6 |
| v6 快照 | `reports/papers/tasks_v6.jsonl` 165 行；`nl_human_v6.jsonl` 55 行 |
| C-010 140 vs 165 | `CLAIMS.md` C-010；`tasks.jsonl` 165 |
| C-011 v1.1 vs v6 | `CLAIMS.md` C-011；v6 interp 6 |
| C-019 27 vs 28 | `CLAIMS.md` C-019 coverage；`negative_controls_28.json` n_cases 28 |
| C-027 19 vs 11 | `CLAIMS.md` C-027；C-021 exam 11 |
| README v3.1/v4 | README 第 12/13 行；RUBRIC 顶部 v4 |
| 无 v6 候选 | `ls candidates_l3_v6` 无；W5B_PLAN W5b-0 阻塞 |
| key 未设 | `gen_candidates_v2.js` 只读 env；W5B_PLAN |

## 附录 B　复现命令

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# CLAIMS 自检（结构）
"$PY" check_claims.py

# C-021 复现（v4 考卷 × v4 候选）
"$PY" score_baseline.py --candidates candidates_l3_v3 \
  --tasks reports/papers/tasks_v4.jsonl \
  --report reports/baseline_scorecard_L3_v4.json \
  --trivial reports/trivial_baselines_L3.json --label "C-021 official"

# bootstrap CI
"$PY" bootstrap_ci.py --scorecard reports/baseline_scorecard_L3_v4.json

# 负控
PYTHONIOENCODING=utf-8 "$PY" negative_controls.py

# v6 任务核对
"$PY" _verify_tasks_v6.py
"$PY" - <<'PY'
import json, collections
rows=[json.loads(l) for l in open('tasks/tasks.jsonl',encoding='utf-8') if json.loads(l)['input_level']=='L3']
print(collections.Counter(r.get('exam_stratum') for r in rows))
PY
```

---

> **本文件是第七轮复评的产物，不修改任何既有项目文件。**
> 本轮复跑了 `check_claims.py`、核对了 v6 任务统计、C-021 快照、bootstrap CI 与 5 处文档计数；未改动任何产物。
> **W5b 结论：Go（唯一阻塞 = `WORKBUDDY_PUBLISHABLE_KEY`）；先 W5b-0 key + 1 条冒烟，再 W5b-3 全量生成。**
