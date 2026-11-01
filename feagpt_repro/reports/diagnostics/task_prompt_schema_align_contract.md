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
- 不改 `tasks.jsonl`、不改考卷、不改任何成绩单、不改 headline。
- 不补 `analysis` 的 optional 键白名单（缺陷 ③，§0.3）。
- 不把「prompt 提到的键必须存在于 schema」做成常驻闸：解析中文 prompt 假红风险高（报告 §10 已登记），本轮只做一次性核对，清单落报告。
- 不为 `--sys-file` 写负控（它不参与任何对外数字）；但必须验「不传参时 sha 不变」。
