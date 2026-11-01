# T-PSA 契约：SYS prompt 与 `schema_task.json` 对齐（方案 B）

> 立项时间：2026-11-01 08:45
> 拍板人：老王（2026-11-01 08:41，「按方案 B 来修」）
> 来源单子：`ROADMAP.md` §13 第 1 位；证据来自 `task_b1kpi_report.md` §6.1 / §6.2
> 方案 B 定义（报告 §11 原文）：「列出 prompt 正文里提到的所有键、逐个问 `schema_task.json` 收不收；再把各块 required 清单显式写进 SYS prompt。」

## 0. 立项时已实测的事实（不是假设）

### 0.1 前值 sha 快照（R53 口径，生成器自报）

| 对象 | sha256 | 取法 |
|---|---|---|
| `SYS`（L3 prompt） | `ce225186cafa5d55c445e30e201b658a37834ec67be8c80a45201b3508423f22` | `node gen_candidates_v2.js --print-prompt-sha` |
| `SYS_L2`（L2 prompt） | `03129c56d83b8bd37dc1393b649e7250d4bdda2edf680d83889ebae07c4c0d83` | `--print-prompt-sha-l2` |
| `gen_candidates_v2.js` | `549ae71309996dede66e458c019164797fc570e2d96a3c767816d9b415044f1d` | `sha256sum` |
| `schema_task.json` | `563a38f899cdc6e7f363e34ad0c842331ece1f83f6ae985990ba62c6ae07971d` | `sha256sum` |
| `tasks/tasks.jsonl` | `caf0f6c3be8131c5b817a0bacfcca8ad3893fcfb95e29d8d9b525866a63e195a` | `sha256sum` |

四份 prompt-v2 代成绩单（`v7_glm` / `v7_ds` / `v6c_p2` / `v6c_ds_p2`）的 `provenance.prompt_sha256` 全部是 `ce225186…`，与当前 SYS 一致。

### 0.2 首轮失败的分布（`task_b1kpi_report.md` §6，128 条候选实测）

| 缺陷 | 现象 | v7 glm | v7 ds |
|---|---|---|---|
| ① `material` 的 3 个 required 键在 prompt 里一个没写 | 首轮缺 `youngs_modulus` / `poisson_ratio` | 58 / 59 | 61 / 61 |
| ② prompt 教模型用 `size`，schema 不认 | `size` 被当自创键拒 | 21 | 21 |
| ②（同因另一果） | 同时 `size_chord` / `size_span` 报 required 缺失 | 21 / 21 | 22 / 22 |
| ③ `analysis` 写成 `{"type":"static"}` | 自创键被拒 | 48 | 1 |

**所有 spec 题首轮结构校验全部未过**（glm 0/58、ds 0/61）。

### 0.3 为什么 ③ 不在本次改动范围

报告 §6.3 已定性：同一 prompt 下 glm 犯 48 次、ds 只犯 1 次 ⇒ **模型行为差异，不是 prompt 缺陷**。方案 B 只要求「已提到的键都合法」+「required 显式化」，不要求补 optional 键白名单。故 ③ **本轮不动**，并作为归因控制项写进判据 P6。

### 0.4 方案 B 执行中发现的新问题（不在本契约范围，已登记）

`schema_task.json` 的 `open_hole_panel.params.layup` 声明为 `{"type":"number"}`，而 gold 真值是 dict（`plies` + `material` 10 键），评分器 `GRADED_FIELDS['open_hole_panel']` 含 `layup` ⇒ 真判。**照 prompt 写 dict 被 schema 拒、照 schema 写 number 被评分器判 FAIL，构成无解闭环**，即 C-033 卡 3 轮的根因。

这属于「schema 自身声明错」，与方案 B（prompt 服从 schema）方向相反，**必须单独拍板**，已登记 `CONFLICT.md` N-29。本契约不动 `schema_task.json` 一个字节。

## 1. 改动清单（3 处，全部在 `gen_candidates_v2.js` 的 `SYS` 常量内）

| # | 位置 | 前值（原文） | 后值（新增/改写） | 治哪条 |
|---|---|---|---|---|
| C1 | 第 23 行骨架之后 | （无） | 新增一行：顶层 7 个块 `name/material/structure/mesh/load/bc/analysis` 全部必填 | 顶层 `required` 显式化 |
| C2 | 第 42 行 | 「材料按名称给出 E/ν/密度/屈服（铝 2024-T3: E=73100 MPa, …）」 | 改写为显式列出 `material` 的 5 个 required 键名 + 值域 + 「不得新造键名」 | 缺陷 ① |
| C3 | 第 40 行末 | 「网格键 size_chord/size_span（翼盒）、size（板壳类）。」 | 改写为「所有族都必须写 size_chord 与 size_span，没有 size 这个键」+ 可选键名 | 缺陷 ② |

**C1/C2/C3 之外的任何字节都不动**（含 `SYS_L2` 追加段、`ALLOWED_HINT`、`relaxedSchema`、`contractErrors`）。

## 2. TASK_CONTRACT

**只改**：`gen_candidates_v2.js` 的 `SYS` 常量内上述 3 处文本。
**验收**：§3 的 P1–P7 判据全绿。
**停止**：
- 若影子批跑完发现 P6 不成立（`type` 自创键同时消失）⇒ 立刻停，说明改动范围失控，回滚重议；
- 若 P3 出现「首轮通过率不升反降」⇒ 停，先查是不是新 prompt 引入新歧义；
- 若发现 `schema_task.json` 也需要改才能让 P3 达标 ⇒ 停，交 §0.4 的 N-29 一并拍板，不擅自改。

## 3. 判据（文本层 2 条 + 结果层 3 条 + 回归层 2 条）

| 编号 | 层 | 判据 | 怎么算 |
|---|---|---|---|
| **P1** | 文本 | 新 `SYS` 里 `material` 的 5 个 required 键名全部出现 | 子串匹配 `youngs_modulus` / `poisson_ratio` / `density` / `yield_strength` / `name` |
| **P2** | 文本 | 新 `SYS` 里顶层 7 个 required 块名全部出现，且显式声明「必填」 | 子串匹配 + 关键词 |
| **P3** | 结果 | spec 题首轮 structure 通过率 > 基线 **0**（glm 0/58、ds 0/61） | 读候选文件的 `validation_history` 长度 |
| **P4** | 结果 | 新批 spec 题里 `material` required 缺失报错条数 **== 0** | 扫 `validation_history` 里的 `must have required property` |
| **P5** | 结果 | 新批 spec 题里 `size` 被当自创键拒的条数 **== 0** | 扫 `additionalProperties` 错误里的键名 |
| **P6** | 回归 | **`analysis.type` 自创键仍出现**（≥1 条）⇒ 证明只治了 ①②，没顺带治 ③ | 扫 `additionalProperties` 错误里的 `type` |
| **P7** | 回归 | `schema_task.json` 与 `tasks.jsonl` 的 sha256 == §0.1 前值 | `sha256sum` 直接比 |

P6 是**控制变量判据**：若 `type` 也消失了，说明我改的范围不止 ①②，归因失效，必须停。

## 4. 与 S-39 的硬约束：为什么分两阶段

`check_claims.py:2394-2406` 的 **S-39** 要求 C-032 / C-033 成绩单的 `provenance.prompt_sha256` == 生成器当前 `SYS` 的 sha256。

⇒ **一旦正式改 `SYS` 常量，四份 prompt-v2 代成绩单立刻与源码不等，S-39 必红**，此时若不重跑就提交不上；要重跑就得全量重生成 64 条 × 2 模型 + 重打分（含求解）。

因此本任务分两阶段：

| 阶段 | 做什么 | 动 SYS 常量？ | 门禁 | 谁拍板 |
|---|---|---|---|---|
| **阶段 1**（本轮） | 新增 `--sys-file` 参数指向外部 prompt 文件，跑**影子批**，量化收益 | **否**（`SYS` 字节不变，sha 不变） | 全绿可提交 | 本契约即授权 |
| **阶段 2** | 正式改 `SYS` + 全量重生成 + 重打分 + 更新 C-032/C-033 | 是 | 需重跑后才绿 | 拿阶段 1 的实测收益再拍 |

`--sys-file` 只影响候选生成，**默认不传参时行为与旧版逐字节一致**（S 系列闸不受影响，加完必须复验 `--print-prompt-sha` 仍是 `ce225186…`）。

## 5. 明确不做

- 不改 `schema_task.json`（含 `layup` 类型错，见 §0.4 / N-29）。
- 不改 `tasks.jsonl`、不改考卷、不改任何**旧**成绩单（新增 p3 成绩单，旧文件一律保留）。
- 不补 `extra.end_tension` 的正名（§6.5，方向是过严，不影响判据）。
- 不把「prompt 提到的键必须存在于 schema」做成常驻闸：解析中文 prompt 假红风险高（报告 §10 已登记），本轮只做一次性核对，清单落报告。
- 不为 `--sys-file` 写负控（它不参与任何对外数字）；但必须验「不传参时 sha 不变」。

## 6. 阶段 2（2026-11-01 10:48 老王拍板三项）

老王原话：「1、C4（允许键白名单）纳入正式改动；2、阶段 2现在做；3、全量重跑跑双模型」

### 6.1 改动范围：C1–C4（原 §1 的 3 处 → 4 处）

| # | 位置 | 前值 | 后值 | 治哪条 |
|---|---|---|---|---|
| C1 | 骨架之后、「铁律」前 | （无） | 顶层 7 块 `name/material/structure/mesh/load/bc/analysis` 全部必填 | 顶层 required 显式化 |
| C2 | 第 42 行 | 「材料按名称给出 E/ν/密度/屈服…」 | 显式列出 `material` 5 个 required 键名 + 值域 + 禁自造键 | 缺陷 ① |
| C3 | 第 40 行末 | 「网格键 size_chord/size_span（翼盒）、size（板壳类）」 | 「所有族都必须写 size_chord 与 size_span，没有 size 这个键」 | 缺陷 ② |
| **C4** | C1 之后 | （无） | 各块允许键白名单（mesh/load/bc/analysis/extra/material），来自 `ALLOWED_HINT` 的同一份清单，**前置到首轮** | 首轮通过率（阶段 1 证明 C1–C3 治好错但不省轮） |

**C4 与 schema 的逐条核对（写回前实测，不是抄）**：

| C4 写的 | `schema_task.json` 实际 | 一致 |
|---|---|---|
| mesh 两键必填 + order/refine_le | `required=[size_chord,size_span]`、`additionalProperties=false` | ✅ |
| load 三键必填 | `required=[kind,magnitude,direction]` | ✅ |
| bc `root_surface`/`clamp` | `required=None`、`addProps=false`（允许 `{}`） | ✅ |
| analysis 六键、不确定写 `{}` | `required=None`、6 个 props、`addProps=false` | ✅ |
| extra `end_shear`/`end_moment` | props 实际多一个 **`end_tension`** | ⚠️ 见 §6.5 |

### 6.2 后值 sha（R53 口径，生成器自报）

| 对象 | 前值 | 后值 |
|---|---|---|
| `SYS`（L3） | `ce225186cafa5d55c445e30e201b658a37834ec67be8c80a45201b3508423f22` | **`d9c0b02d041190891abd7c01147eb30094a754e27d823aeed6599951a0eb870e`** |
| `SYS_L2` | `03129c56d83b8bd37dc1393b649e7250d4bdda2edf680d83889ebae07c4c0d83` | **`5f327a443deb2a1d334f74712ffcb312fee77cf8643ccd0dbe304fbb9f11184c`** |
| `schema_task.json` | `563a38f899cdc6e7f363e34ad0c842331ece1f83f6ae985990ba62c6ae07971d` | **不变** |
| `tasks/tasks.jsonl` | `caf0f6c3be8131c5b817a0bacfcca8ad3893fcfb95e29d8d9b525866a63e195a` | **不变** |

**★ 行尾陷阱（本轮实测新登记）**：源文件是 CRLF（281 行全 CRLF），但 **Node 解析模板字面量时会把 `<CR><LF>` 规范化为 `<LF>`**（ES 规范），所以 `--print-prompt-sha` 报的是 **LF 版** sha。若直接用二进制保留 CRLF 去算，会得到 `184ce91f…` 这个假 sha。写回脚本因此按「LF 版替换 → 写回时还原 CRLF」处理。

### 6.3 重跑范围（为什么是两套卷）

`S-39` 锁 `_sc_paths[2]/[3]` = **`baseline_scorecard_L3_v6c_p2.json`（C-032）/ `_v6c_ds_p2.json`（C-033）**，两者 `prompt_sha256` 都必须是当前 SYS 的 sha。改 SYS ⇒ 必须重跑 **v6c 卷（55 条）** 才能让闸变绿。

`baseline_scorecard_L3_v7_glm/_ds.json`（C-040，supporting）同样挂着 `ce225186…`。S-39 不查，但 R53 的意图是「成绩单不得挂一个已不存在的 harness 的分数」⇒ 一并重跑。

| 批次 | 卷 | 条数 | 模型 | 新候选目录 | 新成绩单 |
|---|---|---|---|---|---|
| a | v7（`tasks/tasks.jsonl`） | 64 | glm-5.3-flash | `candidates_l3_v7_glm_p3` | `baseline_scorecard_L3_v7_glm_p3.json` |
| b | v7 | 64 | deepseek-v4-pro | `candidates_l3_v7_ds_p3` | `baseline_scorecard_L3_v7_ds_p3.json` |
| c | v6c（`reports/papers/tasks_v6c.jsonl`） | 55 | glm-5.3-flash | `candidates_l3_v6c_glm_p3` | `baseline_scorecard_L3_v6c_p3.json` |
| d | v6c | 55 | deepseek-v4-pro | `candidates_l3_v6c_ds_p3` | `baseline_scorecard_L3_v6c_ds_p3.json` |

**命名理由**：不叫 `v8`（v8 会被读成新考卷，而考卷没动）；沿用 `p2 → p3` 的 prompt 代际后缀。

**旧成绩单不覆盖**，一律保留（`_v6c_p2` / `_v6c_ds_p2` / `_v7_glm` / `_v7_ds`）——「按当前卷重跑 = 静默改历史证据」。

### 6.4 阶段 2 判据

| 编号 | 判据 | 合格线 |
|---|---|---|
| **Q1** | 重跑后 `--print-prompt-sha` == `d9c0b02d…`，且四份新成绩单 `provenance.prompt_sha256` 全部等于它 | 全等 |
| **Q2** | 四批候选条数 == 卷条数（64/64/55/55），无缺题 | 无缺 |
| **Q3** | 新批 **spec 题首轮结构通过率 > 0**（基线 v7 glm 0/58、ds 0/61） | >0 |
| **Q4** | `material` required 缺失报错条数 == 0；`size` 被拒条数 == 0 | ==0 |
| **Q5** | **回归控制**：`analysis.type` 自创键仍出现 ≥1 条（证明没把 C4 之外的行为一起改掉）——若为 0，需先查是不是 C4 把 `type` 一起劝住了（那是**预期内**，须在报告里说明，**不判红**） | 记录并解释 |
| **Q6** | `schema_task.json` / `tasks.jsonl` sha 未变 | 相等 |
| **Q7** | 旧成绩单与新成绩单**各自可读**，`tasks_sha256` 相同的只有同卷批次 | 一致 |

**Q5 的性质与阶段 1 的 P6 不同**：P6 是「只治 ①②，不许顺带治 ③」的控制变量；C4 明确写了「analysis 不要写 type」，所以 `type` 若消失是 C4 的**直接效果**，不构成归因失效，但必须在报告里点明「③ 是被 C4 顺带治好的，不是模型自然变好」。

### 6.5 本轮新发现（登记，不改）

- **`extra.end_tension` 的方向判断已更正**：`schema_task.json` 的 `extra` 块 `properties` 含 `end_tension`、`addProps=false`，所以它是 **schema 合法键**；但 **64 条 gold 里一次都没出现**（实读全扫）⇒ 写了会被 `spec_fidelity` 判「自创键」FAIL。
  所以 prompt 第 25 行禁止它是**符合判分口径的**，不是「过严」。真正的缺陷在 schema（见 N-30）。
  > 更正记录：本条初版写「方向是过严，不会造成假失败」——**该判断是错的**，判据是「gold 有没有」，不是「schema 收不收」。
- **N-29（`layup` 类型错）未修**：4 条 CFRP 题仍无解。本轮重跑后它们的 `layup` 仍会 FAIL，**这是已知项，不算本轮的回归**。

### 6.6 第一轮全量（p3）失败复盘：TSR 塌陷 → p4 修正

**p3 = C1–C4 全部写入后的 prompt（`d9c0b02d…`）。** 全量跑完后结构指标非常好，但 TSR 崩了：

| 批次 | 首轮结构通过 | TSR（exam 25） | TSR（spec 题全卷） |
|---|---|---|---|
| 基线 `candidates_l3_v7_glm` | 0/59 | 23/25 = **92.0%** | 48/59 = 81.4% |
| p3 `candidates_l3_v7_glm_p3` | 39/59 = **66.1%** | 9/25 = **36.0%** | 16/59 = 27.1% |

**根因（定位到具体键）**：C4 前置的 `ALLOWED_HINT` 内容来自 ajv 错误原文，而那条原文是
`mesh 允许键: size_chord/size_span/order/refine_le` —— **清单由 schema 生成，把 schema 的错误一起搬进了首轮**。
`order`/`refine_le` 是 schema 合法但 **gold 64/64 都没有**的键，`spec_fidelity` 判「自创键」⇒ FAIL；实测 p3 批 38/59 条写了它们。

**修正（p4，2026-11-01 13:0x）**：只动 prompt 两处，把 `mesh` 收紧成「只写 `size_chord`/`size_span`，不写 `order`/`refine_le` 或任何别的网格键」。
后值 sha `58fca788…`（前值 `d9c0b02d…`）。脚本 `_psa_fix_mesh_keys.py`（带前后值断言，可复现）。
`SYS` 的 `--print-prompt-sha` 与 `node --check` 均已复验。

**p4 冒烟（4 条 p3 回归最严重的题，glm）**：4/4 `turns=1` 且 **TSR PASS（`n_fail=0`，`n_fields_gated` 22/22/16/16）**。⇒ 回归确实被修掉，可以全量。

**新增判据**：

| 编号 | 判据 | 合格线 | 为什么加 |
|---|---|---|---|
| **Q8** | p4 各批 `spec_fidelity` 通过数 **≥** 同卷基线 | ≥ | 结构口径看不出这类回归；不设这条，p3 会被当成成功 |
| **Q9** | prompt 里**教模型写**的每个键，必须在 **该族每条 gold** 中存在（或在 `EXEC_CONFIG_KEYS`/`METADATA` 白名单里） | 全在 | 一次性人工核对已做（见下），但**无常驻闸**——登记进 §13 |

**Q9 的一次性核对结果（2026-11-01，全扫 64 条 gold）**：`material` 5 键、`load` 3 键、`bc` 2 键、`analysis` 6 键、`mesh.size_chord/size_span` 在 **64/64 条**里都存在 ⇒ 教它们安全。
唯一越界的是 `mesh.order`/`refine_le`（已修为不写）与 `extra.end_tension`（prompt 已禁止，方向正确）。

**教训（写进报告）**：
1. **只算一个口径会漏掉最严重的回归**——p3 结构全绿而 TSR 塌 56 个百分点。**「闸通过」和「答案对」必须并列报**。
2. **修复轮的提示语本身就是证据来源**——`ALLOWED_HINT` 抄的是 schema 的错误，于是「修好它」等于「把错误提前」。



## 7. 阶段 2 收口顺序（R59）

1. 四批生成 → 打分（`score_baseline.py`）→ MSR（`msr_l3.py`）→ CI（`bootstrap_ci.py`）
2. 改 `check_claims.py` 的 `_sc_paths[2]/[3]` 指向最新 v6c 批（**只改路径，不改判据**）
3. 更新 CLAIMS C-032/C-033/C-040 数字
4. `negative_controls` → `check_claims`（连跑两次）
5. 行尾规范化 → 提交

### 7.1 p4 全量结果（第二轮，`58fca788…`）

| 卷 | 模型 | 批 | EXAM TSR | EXAM SFR | DEV TSR | 首轮有效 | exam 分类 |
|---|---|---|---|---|---|---|---|
| v7 | glm | p2（基线） | 23/25 = 92.0% | 20/22 = 90.9% | 21/30 = 70.0% | 5 | clarify_ok 3 / spec_fail 2 / spec_pass 20 |
| v7 | glm | **p4** | **23/25 = 92.0%** | 20/22 = 90.9% | **24/30 = 80.0%** | **47** | 同上（完全一致） |
| v7 | ds | p2（基线） | 23/25 = 92.0% | 20/21 = 95.2% | 22/30 = 73.3% | 3 | clarify_ok 3 / clarify_wrong 1 / spec_fail 1 / spec_pass 20 |
| v7 | ds | **p4** | **22/25 = 88.0%** | 20/23 = 87.0% | 22/30 = 73.3% | **57** | clarify_ok **2** / **fabricated 1** / spec_fail 2 / spec_pass 20 |
| v6c | glm | p2（基线） | 23/25 = 92.0% | 20/22 = 90.9% | — | — | — |
| v6c | glm | **p4** | **23/25 = 92.0%** | 20/22 = 90.9% | 22/30 = 73.3% | **43** | clarify_ok 3 / spec_fail 2 / spec_pass 20 |
| v6c | ds | p2（基线） | 22/25 = 88.0% | 20/21 = 95.2% | 22/30 = 73.3% | 2 | clarify_ok 2 / clarify_wrong 1 / no_output 1 / spec_fail 1 / spec_pass 20 |
| v6c | ds | **p4** | **21/25 = 84.0%** | 20/23 = 87.0% | 22/30 = 73.3% | **48** | clarify_ok **1** / **fabricated 1** / no_output 1 / spec_fail 2 / spec_pass 20 |

**结论一：效率收益确凿且很大。** 首轮就有效的题数 glm 5→47 / 43，ds 3→57 / 48（两套卷）。这是「省一轮 LLM 调用」的真实来源。

**结论二：glm 准确率不掉。** EXAM TSR 持平 92.0%，v7 的 DEV 还从 70.0% 涨到 80.0%。

**结论三：ds 掉 1 条，且是 `fabricated`（R20 红线）。** 两套卷一致地把一条 `clarify_ok` 变成 `fabricated`：
题面「**若干个**普通框」⇒ p4 直接写 `n_frames = 0`，而 prompt 自己写着「不得填 0」。基线是澄清（正确）。
⇒ **这是 p4 引入的行为回归，不是模型能力变化。**

### 7.2 三个修正变体的消融（影子 prompt，源码 sha 不动）

| 变体 | 改法 | 6 条冒烟结果（ds，p4 同题对照） |
|---|---|---|
| **p4**（基准） | — | 柱壳 `n_frames=0` fabricated；加筋板漏写 `n_stringers`；CFRP FAIL(2 轮)；3 条对照 PASS |
| **p5a** | material 白名单后加「数量铁律优先于写全」(+188) | **6/6 与 p4 逐条一致 ⇒ 完全无效**（位置太弱） |
| **p5b** | 改在 C1「七个块全部必填」句尾，加澄清豁免 (+75) | 加筋板→`clarify_ok`；**柱壳仍写 0**；CFRP 3 轮；3 条对照 PASS |
| **p5c** | p5b + 柱壳表行标注「`n_stringers`/`n_frames` 题面没给数 ⇒ 澄清」(+128) | **两条都回到 clarify 且 `clarify_ok=True`**；CFRP 同 p4；3 条对照全 PASS |

**为什么 p5a 无效、p5c 有效**：推压源不是「写全」这句抽象话，而是**四族键名总表**——它把 `n_frames` 列成了「要写的键」。加筋板那行本来就带「没给根数⇒澄清」的注解，所以 p5b 就修好了它；柱壳那行没有，必须单独标注。
⇒ **可复用的判据：要让模型「不写某键」，必须写在该键出现的那一行，写在别处无效。**

**p5c 定案**（老王 2026-11-01 拍板「升到 p5c 全量重跑」）。SYS sha 链：

```
ce225186（原始）→ d9c0b02d（C1-C4）→ 58fca788（p4：mesh 去掉 order/refine_le）→ c37862f9（p5c：澄清豁免 + 柱壳行标注）
```

`p4` 的四批候选与成绩单**全部保留**（`candidates_l3_*_p4` / `baseline_scorecard_L3_*_p4.json`），作为本次消融的对照证据，不删不覆盖。

### 7.3 p5c 全量结果与**收口时的阻塞**（2026-11-01）

p5c（`c37862f9…`）四批全部跑完，八份成绩单（两套卷 × 两模型 × p2/p4/p5c）齐备：

| 卷 | 模型 | 代 | EXAM TSR | EXAM SFR | DEV TSR | 首轮有效 | exam 分类 |
|---|---|---|---|---|---|---|---|
| v7 | glm | p2 | 23/25 = 92.0% | 20/22 = 90.9% | 21/30 = 70.0% | 5 | clarify_ok 3 / spec_fail 2 / spec_pass 20 |
| v7 | glm | p4 | 23/25 = 92.0% | 20/22 = 90.9% | 24/30 = 80.0% | 47 | 同上 |
| v7 | glm | p5c | 23/25 = 92.0% | 20/22 = 90.9% | 23/30 = 76.7% | 41 | 同上 |
| v7 | ds | p2 | 23/25 = 92.0% | 20/21 = 95.2% | 22/30 = 73.3% | 3 | clarify_ok 3 / clarify_wrong 1 / spec_fail 1 / spec_pass 20 |
| v7 | ds | p4 | 22/25 = 88.0% | 20/23 = 87.0% | 22/30 = 73.3% | 57 | clarify_ok 2 / **fabricated 1** / spec_fail 2 / spec_pass 20 |
| v7 | ds | p5c | 21/25 = 84.0% | 20/24 = 83.3% | 23/30 = 76.7% | 57 | clarify_ok 1 / **fabricated 2** / spec_fail 2 / spec_pass 20 |
| v6c | glm | p2 | 23/25 = 92.0% | 20/22 = 90.9% | 22/30 = 73.3% | 3 | clarify_ok 3 / spec_fail 2 / spec_pass 20 |
| v6c | glm | p4 | 23/25 = 92.0% | 20/22 = 90.9% | 22/30 = 73.3% | 43 | 同上 |
| v6c | glm | **p5c** | **23/25 = 92.0%** | 20/22 = 90.9% | **24/30 = 80.0%** | **28** | 同上 |
| v6c | ds | p2 | 22/25 = 88.0% | 20/21 = 95.2% | 22/30 = 73.3% | 2 | clarify_ok 2 / clarify_wrong 1 / no_output 1 / spec_fail 1 / spec_pass 20 |
| v6c | ds | p4 | 21/25 = 84.0% | 20/23 = 87.0% | 22/30 = 73.3% | 48 | clarify_ok 1 / **fabricated 1** / no_output 1 / spec_fail 2 / spec_pass 20 |
| v6c | ds | **p5c** | **23/25 = 92.0%** | 20/22 = 90.9% | 22/30 = 73.3% | **48** | clarify_ok 3 / spec_fail 2 / spec_pass 20 |

**★ 三代的准确率读法（必须按 N-31 读）**：
- **glm 六格全是 92.0%**——prompt 三代对它完全无影响，这是最稳的一条。
- **ds 在 84–92% 之间漂**，且同一 prompt 方向相反（v7 降 / v6c 升）⇒ **±1~2 条低于单次运行噪声，不得归因**（N-31 已用同题两次运行 `spec(n_frames=0)` vs `clarify(n_frames)` 实证）。
- **可归因的只有大效应**：结构首轮错误 `M/Z/S` 从 174/42/21 → **0/0/0**；首轮有效题数 3~5 → **28~57**。

**★ 收口时被阻塞（N-32）**：把 C-032/C-033 切到 p5c 需要重算 MSR（`S-37` 实测 p5 成绩单 `缺 msr_section`），而 MSR 依赖 ccx 求解器，**本机求解器不存在**（`$FEAGPT_CCX` 未设 / `tools/calculix/` 不在 / PATH 无）。
⇒ 本轮**已把 `SYS` 回滚到 `ce225186…`**，C-032/C-033 仍指向 p2 成绩单，闸全绿；p5c 全部产物保留为候选（prompt 文本见 `reports/diagnostics/prompt_p5c_sys.txt`，sha `c37862f9…`）。

> **产物的 sha 口径**：该文件按仓库行尾约定存为 **CRLF**，但 `c37862f9…` 是**把 CRLF 归一成 LF 之后**算的 —— 这与 `node gen_candidates_v2.js --print-prompt-sha` 一致（ES 规范会把模板字面量的 CRLF 归一化为 LF）。核 sha 时必须先归一，直接对文件字节算会得到另一个值。


**采纳 p5c 的完整步骤（待有求解器的环境执行）**：
1. 用 `_psa_build_p5.py --variant c` 或直接取 `prompt_p5c_sys.txt` 写回 `SYS`（sha 必须命中 `c37862f9…`）
2. 四批 `msr_l3.py`（`_v6c_glm_p5` / `_v6c_ds_p5` / `_v7_glm_p5` / `_v7_ds_p5`）→ `bootstrap_ci.py`
3. 改 `check_claims.py` 的 `_sc_paths[2]/[3]` → `_v6c_glm_p5` / `_v6c_ds_p5`（只改路径）
4. 更新 C-032 / C-033 / C-040 文本（数字 + `prompt_sha256 = c37862f9…`）
5. `negative_controls` → `check_claims` 连跑两次 → 行尾 → 提交




