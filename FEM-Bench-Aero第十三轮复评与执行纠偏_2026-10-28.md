# FEM-Bench-Aero 第十三轮复评与执行纠偏（v1.1 双码闭合 + T-A4..A9 后）

> **复评日期**：2026-10-28（第十三轮）
> **复评对象**：T-A4（R59/R60）、T-A6（check_forms 串行/陈旧路径）、T-A5（R61 串行 ccx）、v1.1 双码闭合（9/9、64 paired PASS）、T-A7（gate3 三分支）、T-A9（R62/S-48 claim 计数入闸）、T-A8（external_numbers 活源 + N-9 分母）
> **复评方式**：只读核对 + 官方 artifact 交叉检查（`check_claims` 27/50/49、负控 55/55、`RUBRIC` v5.5、`CLAIMS` R1–R62、`external_numbers.md`、`check_forms_v11` 54/0、`verify_dataset` 64 paired、`DATASET_V11`）；**除本文件外未改动任何项目文件**
> **结论先行**：
> **v1.1 数据层真正闭合了。** 9 条新案例 **9/9 双码真跑通**；`check_forms` **54 PASS / 0 FAIL**；`verify_dataset` **64 paired / VERDICT PASS**；`gate4_v11` **128/128**；`eval_report_v11` **64 cases / 63 classes / 0 failures**；`manifest` **64 / 63 类 / 25-17-22**。数据侧从 55 到 64 的扩量，**质量、双码、串行、内插物理都收口**。
> **协议侧也扩到位了：** R59（负控→check 顺序）、R60（venv）、R61（ccx 串行）、R62（claim 正文计数入闸）；负控 **51→55**；语义 **45→49**；`RUBRIC` **v5.5**；`check_claims` **27 claims / 50 artifacts / 49 semantic** 全过；`external_numbers.md` 把 55/110 与 64/128 的分母口径分开了。
> **但现在只剩两件事，而且有先后：** ① **T-A10**——`C-001/2/4/5` 与 `external_numbers.md` 还没有闸（N-12），建议先于 v7；② **v7**——9 条新案例还没进任务层，exam 仍 25，paper 仍 v6c 55；v7 要把 exam 25→34，C-032 的 23/25 换卷后不可比（R30/R39），两模型要重生成 + MSR + CI/榜单。
> **另外发现一处 1 行漂移：** `CLAUDE.md` 仍写 **27/49/49**，live `check_claims` 已是 **27/50/49**（T-A8 把 artifacts 49→50；AGENTS/CLAUDE 没有同步）。**判定：协议 + v1.1 数据 A；v7 是唯一通往 30 的路径；T-A10 先于 v7；评分 29/30。**

---

## 目录

- [0. 复评摘要](#0-复评摘要)
- [1. 变化与交付](#1-变化与交付)
- [2. 已验证的改进（credit）](#2-已验证的改进credit)
- [3. 剩余问题](#3-剩余问题)
- [4. v1.1 收口与 v7 准入](#4-v11-收口与-v7-准入)
- [5. 下一步任务执行建议](#5-下一步任务执行建议)
- [6. 防跑偏机制（R63–R64 建议）](#6-防跑偏机制r63r64-建议)
- [7. 评分卡](#7-评分卡)
- [8. 待拍板](#8-待拍板)
- [附录 A　证据索引与复现命令](#附录-a证据索引与复现命令)
- [附录 B　v1.1 数据层闭环](#附录-bv11-数据层闭环)
- [附录 C　第十二轮 P1 逐项判定](#附录-c第十二轮-p1-逐项判定)
- [附录 D　文档/口径漂移清单](#附录-d文档口径漂移清单)

---

## 0. 复评摘要

### 0.1 三句话结论

1. **v1.1 数据层闭合。** 9 条新案例 9/9 双码；`check_forms` 54/0；`verify_dataset` 64 paired PASS；`gate4_v11` 128/128；`eval_report_v11` 64/63/0；`manifest` 64/63/25-17-22；内插 7/7 严格 + 2 双轴只报；网格 64/64、节点 9/9、dedup 0。**55→64 的扩量到此数据侧完成。**
2. **协议侧扩到 R62。** R59/R60/R61/R62；负控 55/55；语义 49；`RUBRIC` v5.5；`check_claims` 27/50/49 全过；`external_numbers.md` 分开 55/110 与 64/128 的分母；T-A7 把 gate3 从“34/15/6 继承 PASS”修成 39 field + 18 scalar + 7 reported-only 的三分支；T-A9 把 claim 正文计数入闸（S-48）。
3. **只剩 T-A10 + v7。** T-A10：C-001/2/4/5 与 external_numbers 仍无闸（N-12），建议先于 v7；v7：9 条进任务层，exam 25→34，C-032 23/25 换卷后不可比，两模型重生成 + MSR + CI/榜单。**另：CLAUDE/AGENTS 的 artifacts 49 已落后 live 50，一行漂移待修。**

### 0.2 执行总评

| 工作块 | 评分 | 一句话判断 |
|---|---|---|
| T-A4：R59/R60 | **A** | 负控→check 顺序、venv 入规；S-45/S-46；NC-50/51 |
| T-A5：R61 串行 ccx | **A** | 全局锁 + S-47 + NC-52；RUBRIC v5.4 |
| T-A6：check_forms | **A** | 陈旧参考路径修复；50 PASS/1 FAIL → **54 PASS/0 FAIL** |
| v1.1 双码闭合 | **A** | 9/9 真跑通；`verify_dataset` **64 paired PASS** |
| T-A7：gate3 三分支 | **A** | 真因是 39 条翼盒从未逐条读取；39/18/7；R62 前身 |
| T-A9：R62/S-48 | **A** | claim 正文计数入闸；55/55；NC-53 四向 |
| T-A8：external 活源 | **A−** | 55/110 与 64/128 分母分开；但 CLAUDE/AGENTS 的 49→50 未同步；N-12/T-A10 留尾 |
| **总体** | **A / 29/30** | 协议 + v1.1 数据 A；v7 是唯一 30 的路径 |

> **和第十二轮 29/30 的关系**：v1.1 从“9 Abaqus + check_forms 未完成”到“9/9 + 54/0 + 64 paired PASS”（+0.5），T-A4..A9 协议扩到 R62（+0.5），但 v7 未开、T-A10 未做、CLAUDE 49/50（−1），净持平 ⇒ 29/30。

---

## 1. 变化与交付

### 1.1 提交

| commit | 时间 | 内容 |
|---|---|---|
| `6170f3b` | 10-27 22:58 | T-A4：R59 收口顺序 + R60 venv（S-45/S-46 / NC-50/51，RUBRIC v5.3） |
| `cdef350` | 10-27 23:15 | T-A6：check_forms 陈旧参考路径 + 串行重跑（50 PASS/1 FAIL → 54 PASS/0 FAIL） |
| `405a4c9` | 10-27 23:16 | T-A5：R61 求解串行硬约束（全局锁 + S-47 + NC-52，RUBRIC v5.4） |
| `c73d9f5` | 10-28 21:51 | v1.1 双码闭合验收：9/9 真跑通 + verify_dataset 64 paired PASS |
| `92bc19e` | 10-28 21:59 | T-A7：gate3 证据链三分支化 —— 真因是 39 条翼盒从未被逐条读取 |
| `8efdbbe` | 10-28 22:09 | T-A9：R62/S-48 —— claim 正文的计数入闸（N-10） |
| `e976131` | 10-28 22:22 | T-A8：对外数字表换活数据源 —— 55 与 110 从来不是同一个分母 |
| `a29242e` | 10-28 22:23 | T-A8 收口：27/50/49；N-9 结案 |
| `6be1cfc` | 10-28 22:24 | memory：T-A8 落盘 |

**HEAD**：`6be1cfc`；工作区 clean。

### 1.2 新增/修改的关键文件

| 文件 | 作用 |
|---|---|
| `FEM-Bench-Aero/gate4_v11.json` | 128/128 PASS（v1.1 活源） |
| `FEM-Bench-Aero/verify_dataset_v11.json` | 128/128 OK / 64 paired / VERDICT PASS |
| `FEM-Bench-Aero/eval_report_v11.json` | 64 cases / 63 classes / 0 failures / PASS |
| `FEM-Bench-Aero/external_numbers.md` / `.json` | 对外数字表；分母口径列；55/110 vs 64/128 |
| `FEM-Bench-Aero/gate3_all55_d37.json` | gate3 39 field + 18 scalar + 7 reported-only |
| `feagpt_repro/reports/check_forms_v11.json` | 54 PASS / 0 FAIL |
| `feagpt_repro/reports/check_claims.json` | 27 claims / 50 artifacts / 49 semantic 全过 |
| `feagpt_repro/reports/negative_controls_55.json` | 55/55（NC-50..53） |
| `FEM-Bench-Aero/RUBRIC.md` | v5.5：R59–R62；S-45..S-48；NC-50..53 |
| `FEM-Bench-Aero/CLAIMS.md` | R1–R62；C-001/2/4/5 待 T-A10 入闸 |
| `FEM-Bench-Aero/DATASET_V11.md` | v1.1 64 条；双码 9/9；check_forms 54/0；verify PASS |
| `FEM-Bench-Aero/README.md` | 对外数字表链接；分母口径警告 |

### 1.3 当前 SOT（live）

| 项 | 值 |
|---|---|
| 唯一 headline | **C-032**（`baseline_scorecard_L3_v6c_p2.json`，glm-5.3-flash，prompt v2，exam 23/25 92.0%） |
| supporting | **C-033**（`baseline_scorecard_L3_v6c_ds_p2.json`，deepseek-v4-pro，exam 22/25 88.0%） |
| 历史 | C-029/C-031（prompt v1）、C-028（v6b）、C-021（v4） |
| W5d | C-034 榜单；C-035 prompt v3/v3b 否决、回退 v2 |
| 当前 paper | `reports/papers/tasks_v6c.jsonl`，sha `9c1faa3a…`；**55 条 L3 / exam 25** |
| 当前 prompt | `gen_candidates_v2.js`，sha `ce225186…`（v2） |
| 当前 rubric | **v5.5（R42–R62 在 RUBRIC；R1–R41 在 CLAIMS）** |
| 门禁 | 负控 **55/55**；`check_claims` **27/50/49**（CLAUDE/AGENTS 仍写 49，见 §3.3） |
| 数据集 | **64 条（train 25 / val 17 / test 22；63 类；128 算例目录）** |
| 数据层 | **9/9 双码；check_forms 54/0；verify 64 paired PASS；gate4 128/128；eval 64/63/0** |
| 下一主任务 | **T-A10（C-001/2/4/5 + external_numbers 入闸）→ v7 paper → v7 candidates** |

---

## 2. 已验证的改进（credit）

| 改进 | 实测 |
|---|---|
| **v1.1 双码** | 9 条新案例 9/9 真跑通；`_xval/` 补齐；`verify_dataset` **64 paired / VERDICT PASS** |
| **check_forms** | 54 PASS / 0 FAIL（修复陈旧参考路径 + 串行） |
| **gate4** | 128/128 PASS（64 条 × 2 树） |
| **eval_dataset** | 64 cases / 63 classes / 0 failures / PASS；D12 复现 PASS |
| **内插物理** | 7/7 严格单轴；2 双轴只报；`v11_interp_check` |
| **T-A7 gate3** | 39 field + 18 scalar-disp + 7 reported-only；加和 64=64；真因是 39 条翼盒从未逐条读取（键名 `case` vs `case_id`） |
| **T-A9 R62** | S-48 四判据；claim 正文计数入闸；NC-53 四向；负控 55/55 |
| **T-A8 external** | 64/63/25-17-22；关1 64/64、关3 39/18/7、关4 128/128、自洽 128/128；55/110 与 64/128 分母分开 |
| **R59/R60/R61** | 负控→check 顺序；venv；ccx 串行；S-45/46/47；NC-50/51/52 |
| **R62/S-48** | claim 正文计数必须等于 artifact；`check_claims` 49 semantic；NC-53 |
| **负控** | 51→55；旧 53/54 归档；C-019 55/55；三份文档统一“旧十二份归档” |
| **自审** | `DATASET_V11` / memory 记录 summary 漏写、等级高于证据、口径参数假 FAIL、并行 ccx 等坑 |

---

## 3. 剩余问题

### 3.1 P1：v7 未开，9 条新案例未进任务层

- `papers/` 仍只有 v4/v5/v6/v6b/v6c；`tasks_v6c.jsonl` 仍 55 条；exam 仍 25；`candidates` 没有 v7。
- v1.1 数据 64 条已 PASS，但**任务层仍 55**；9 条新案例只在 `modeling/`，不在 `tasks`。
- v7 的代价：exam 25→34；C-032 的 23/25 换卷后不可比（R30/R39）；两模型重生成（约 2×15 min）+ 全链 MSR（约 2×40 min）+ CI/榜单。
- **建议**：P1，v7 是唯一主任务；按 R-A1 拆成 **v7 paper**（单变量=paper）与 **v7 candidates**（单变量=candidates）；C-032/C-033 在 v7 落地后标 historical/supporting，v7 新成绩单成为新 headline（C-036+）。

### 3.2 P1：T-A10（N-12）——C-001/2/4/5 与 external_numbers 仍无闸

- `CONFLICT.md` N-12：`C-001/2/4/5` 与 `external_numbers.md` 没有语义检查；`check_claims` 的 49 项只覆盖部分 artifact。
- `external_numbers.md` 是**对外数字表**，与 C-001/2/4/5（数据集规模/网格/双码/自洽）直接相关；T-A8 刚把它换成活源，但没有闸；下一次改 64→? 仍可能漂。
- **建议**：P1，T-A10 先于 v7：给 C-001/2/4/5 + external_numbers 加 S-49/S-50；负控 NC-54；`external_numbers.md` 的分母口径（spec 64 / 算例 128）必须显式；T-A10 完成后再开 v7 paper。

### 3.3 P2：CLAUDE/AGENTS 的 artifacts 49 已落后 live 50

- T-A8 新增三份 v1.1 活源（`gate4_v11` / `verify_dataset_v11` / `eval_report_v11`）⇒ `check_claims` **artifacts 49→50**；`a29242e` 的官方 JSON 是 27/50/49。
- `CLAUDE.md` 仍写 **27/49/49**；`AGENTS.md` 的 §0/§7 也需核对（T-A8 只改了 `check_claims.json`）。
- **风险**：下一个 agent 按 49 校验，会以为 artifact 丢了，或把 50 当成多出来的。R62/S-48 只管 claim 正文计数，**不管协议文件里的 counts**。
- **建议**：P2，一行改 49→50；加 S-49 “协议文件（AGENTS/CLAUDE）的 counts 必须等于 `check_claims` 实读”，或把 counts 从协议文件里改成“以 §0 实读为准”不写死。

### 3.4 P2：v1.1 数据层缺少一条 CLAIM（C-036?）

- v1.1 的 64/9/54/128/64-63-0 证据散在 `DATASET_V11` + `gate4_v11` + `verify_dataset_v11` + `eval_report_v11` + `external_numbers`；`CLAIMS` 里没有一条 **v1.1 数据层 claim**（C-036 尚未占用，grep 为空）。
- 这会让“v1.1 数据层已闭合”只存在于文档，不在 claim 账本；T-A10 正好可以把 C-001/2/4/5 + external 的闸补上，并新增 C-036 记录 64/9/54/128。
- **建议**：P2，T-A10 同时新增 **C-036 v1.1 数据层**（64 paired PASS / 9/9 双码 / 54/0 check_forms / 128/128 gate4 / 64-63-0 eval），artifact 用三份 v1.1 活源；C-032 仍是模型 headline，C-036 是数据层 claim，不冲突。

### 3.5 P2：C-032/C-033 的 v7 状态

- v7 落地后，C-032 的 23/25 是 v6c 口径；v7 的 34 条 exam 是新口径；S-29 只能有一个 headline。
- **建议**：P2，v7 paper 冻结时同步写 `replace` 关系；C-032/C-033 标 historical/supporting；v7 新成绩单（C-037+）成为新 headline；INDEX/README/CLAIMS 同步。

### 3.6 P2：external_numbers 的 55/110 与 64/128 已分开，但要保持

- T-A8 已把“关 1/关 3/划分复算”的分母（spec 64）与“关 4/自洽”的分母（算例 128）分开；这是正确的。
- 下一次若改数据规模（v7? 64 不变；v1.2?），必须同时更新两套分母；`external_numbers.md` 的表尾“分母口径警告”要保留。
- **建议**：P2，T-A10 的 S-49 把“分母列存在 + 两类分母不混”写进闸。

### 3.7 P2：`check_forms` 54/0 与 `check_claims` 27/50/49 的收口顺序

- `negative_controls_55` mtime 22:06；`check_claims.json` 22:23；顺序是负控→check，符合 R59；这是 T-A4 的整改生效。
- `check_claims` 27/50/49；`CLAUDE` 27/49/49 是唯一不一致；见 3.3。
- **建议**：P2，下次收口保持负控→check；`check_claims` 的 mtime 记录与 negative 对齐。

### 3.8 不是问题的部分（避免过度纠偏）

- v1.1 的 64 paired PASS、9/9 双码、54/0 check_forms、128/128 gate4、64-63-0 eval、7/7 内插——都是真的，不需要重做。
- T-A7 的 39/18/7、T-A9 的 S-48、T-A8 的 64/128、R59–R62、55/55、49 semantic——都是真的，不需要重做。
- C-032/C-033 的 23/25、22/25 仍是 v6c 的有效成绩；v7 不是“修 C-032”，是新卷。

---

## 4. v1.1 收口与 v7 准入

### 4.1 准入门槛

| 条件 | 现状 | 结论 |
|---|---|---|
| 64 条数据层 | manifest 64 / 63 类 / 25-17-22 | ✅ |
| 9 条双码 | 9/9；`verify_dataset` 64 paired | ✅ |
| check_forms | 54/0 | ✅ |
| gate4 / eval | 128/128；64-63-0 | ✅ |
| 内插物理 | 7/7 strict + 2 双报 | ✅ |
| T-A10（C-001/2/4/5 + external） | **未做** | ⏳ P1 |
| v7 paper | **未开** | ⏳ P1 |
| v7 candidates | **未开** | ⏳ P1 |

**判定：v1.1 数据层已闭合；v7 可以开，但建议先做 T-A10（1 天内的闸），再做 v7 paper/candidates。**

### 4.2 v7 的顺序

```text
T-A10（C-001/2/4/5 + external 入闸；S-49/NC-54）──► v7 paper（单变量=paper；exam 25→34）
                                                        │
                                                        ▼
                                              v7 candidates（两模型；MSR；CI；榜单）
                                                        │
                                                        ▼
                                  C-032/C-033 → historical；v7 新 headline（C-037+）
```

**为什么 T-A10 先**：v7 会改 `tasks`/paper，`external_numbers` 和 C-001/2/4/5 的数据集指标仍是 v1.1 的 64；如果 T-A10 没做，v7 落地后对外数字表与数据集 claim 仍可能漂。T-A10 是 1 天内的闸，先做再开 v7。

---

## 5. 下一步任务执行建议

### 5.1 任务表

| ID | 优先级 | 做什么 | 验收 | 证据 |
|---|---|---|---|---|
| **T-A10** | **P1** | C-001/2/4/5 + `external_numbers.md` 入闸；S-49/S-50；NC-54；新增 C-036 v1.1 数据层 claim（64/9/54/128/64-63-0） | `check_claims` 全过；external 分母口径进闸；C-036 入库 | `check_claims.py`；`external_numbers.md`；`CLAIMS` |
| **T-A10b** | **P2** | `CLAUDE.md`/`AGENTS.md` 的 artifacts 49→50；或改成“以 §0 实读为准”不写死 | 协议 counts == live | `CLAUDE`/`AGENTS` |
| **v7-paper** | **P1** | 9 条接进任务层；`tasks_v7` / exam 25→34；冻结 sha；C-032/C-033 标 historical | paper freeze；S-29 唯一 headline 切 v7；`TASK_CONTRACT` 单变量=paper | 新 `papers/tasks_v7.jsonl`；C-037 |
| **v7-cand** | **P1** | 两模型 × v7；同 prompt v2；同 ≤3 轮；MSR；CI；榜单 | 两模型同卷同 prompt；C-032 23/25 不可比（R30/R39）；新 headline | 新 scorecard/CI；C-038 |
| **v7-status** | **P2** | v7 落地后 C-032/C-033 标 historical/supporting；INDEX/README/CLAIMS 切 v7 | S-29 唯一；INDEX/README/CLAIMS 同步 | 文档 |
| **T-A10c** | **P2** | `check_claims` 的 mtime/负控顺序保持；下次收口负控→check | 27/50/49；55/55；mtime 对齐 | `check_claims.json` |
| **v1.1 归档** | **P2** | `DATASET_V11` 标 PASS；三份 v1.1 活源入 C-036；旧 v1.1 过程文件归档 | C-036 + 三 artifact；DATASET_V11 PASS | `CLAIMS`/`DATASET_V11` |

### 5.2 顺序与成本

- T-A10：0.5–1 天（加闸 + 负控 + C-036）。
- T-A10b：10 分钟。
- v7-paper：0.5–1 天（9 条 NL/task/冻结/核对）。
- v7-cand：两模型各 15 分钟生成 + 各 40 分钟 MSR + CI/榜单，约 2–3 小时（等）。
- **总计约 2–3 天到 v7 榜单。**

---

## 6. 防跑偏机制（R63–R64 建议）

> R1–R62 保留；以下为第十三轮建议新增，待拍板后写入 RUBRIC。

| 红线 | 内容 | 触发点 |
|---|---|---|
| **R63** | **协议文件里的 counts 必须与 live 一致**：`AGENTS.md`/`CLAUDE.md`/`README` 里的 claims/artifacts/semantic/负控数，必须由 S-49 实读 `check_claims`/`negative_controls` 核对；不能写死后不更新 | T-A10b；S-49；NC-54 |
| **R64** | **对外数字表必须有分母口径列 + 闸**：spec 数（64）与算例数（128）不得混；`external_numbers.md` 的每一行都要能追溯到 artifact；C-001/2/4/5 + external 入闸 | T-A10；S-50；NC-54 |

**新增语义检查/负控建议：**

| ID | 检查 | 期望 |
|---|---|---|
| S-49 | 协议文件 counts（AGENTS/CLAUDE） | == `check_claims` / `negative_controls` 实读 |
| S-50 | `external_numbers.md` 行 | 每行有分母口径 + artifact；spec/算例两类分母不混 |
| NC-54 | 两向变异 | 协议 counts 写旧 / external 分母混写 ⇒ 必须红 |

---

## 7. 评分卡

> **第十二轮 29/30 → 第十三轮 29/30**：v1.1 数据闭合 +0.5，T-A4..A9 协议 +0.5；v7 未开、T-A10 未做、CLAUDE 49/50 −1，净持平 ⇒ 29/30。

| # | 维度 | 第十一轮 | 第十二轮 | 第十三轮 | 依据 |
|---|---|---:|---:|---:|---|
| 1 | 目标一致性 | 3 | 3 | **3** | 评测基础设施主轴不变；v1.1 数据闭合；v7 按计划 |
| 2 | 任务有效性 | 3 | 3 | **3** | v6c exam 25 仍有效；v1.1 64 数据 PASS；v7 未开 |
| 3 | 判分有效性 | 3 | 3 | **3** | R59–R62；S-45..S-48；55/55；49 semantic |
| 4 | 证据等级 | 3 | 3 | **3** | 27/50/49；v1.1 三活源；external 64/128；`check_claims` 50 vs CLAUDE 49 是 P2 |
| 5 | 可复现性 | 3 | 3 | **3** | check_forms 54/0；verify 64 paired；gate4 128/128；eval 64-63-0 |
| 6 | 版本治理 | 3 | 3 | **3** | R1–R62；v5.5；旧负控归档；C-032/C-033 当前 |
| 7 | 文档真实性 | 3 | 3 | **3** | `external_numbers` 分母警告；`DATASET_V11` 自审；T-A7 真因 |
| 8 | 统计有效性 | 2 | 2 | **2** | v6c n=25；v1.1 64 但 v7 未开；CI 仍宽 |
| 9 | 范围纪律 | 3 | 3 | **3** | T-A4..A9 单变量；T-A10 未夹带 |
| 10 | 计划执行 | 3 | 3 | **3** | v1.1 9/9 + 54/0 + 64 paired；T-A4..A9 落地 |
| **总分** | | **29/30** | **29/30** | **29/30** | 协议 A；v1.1 数据 A；**v7 是唯一通往 30 的路径** |

**一句话**：**协议和数据层都收口了；现在不是“还差什么技术”，是“还差 v7 这一张新卷”。** T-A10 是 v7 前的最后一道闸；v7 落地后，统计有效性 2→3，总分 30。

---

## 8. 待拍板

| # | 决策 | 选项 | 建议 |
|---|---|---|---|
| **D1** | **T-A10 时机** | (a) 先做 T-A10（C-001/2/4/5 + external 入闸 + C-036）；(b) 直接 v7 | **(a)**；T-A10 0.5–1 天，避免 v7 落地后 external/数据 claim 漂 |
| **D2** | **v7 顺序** | (a) paper 先、candidates 后；(b) 同时 | **(a)**；R-A1 单变量；C-032 23/25 换卷后不可比 |
| **D3** | **v7 模型** | (a) 两模型同 prompt v2；(b) 只跑 glm | **(a)**；v7 新卷，两模型都重生成；C-033 继续 supporting |
| **D4** | **C-032/C-033 状态** | (a) v7 落地后 historical/supporting；(b) 保持 active headline | **(a)**；S-29 唯一 headline 切 v7 |
| **D5** | **CLAUDE/AGENTS 49/50** | (a) 改成 50；(b) 改成“以 §0 实读为准”不写死 | **(b)** 长期更稳；短期 (a) 也行 |
| **D6** | **v1.1 数据 claim** | (a) T-A10 新增 C-036；(b) 只留 DATASET_V11 | **(a)**；数据层闭合应进 claim 账本 |

---

## 附录 A　证据索引与复现命令

### A.1 官方 artifact

| 文件 | 用途 |
|---|---|
| `reports/check_claims.json` | 27/50/49；S-48 |
| `reports/negative_controls_55.json` | 55/55；NC-53 |
| `reports/check_forms_v11.json` | 54/0 |
| `FEM-Bench-Aero/verify_dataset_v11.json` | 64 paired / PASS |
| `FEM-Bench-Aero/gate4_v11.json` | 128/128 |
| `FEM-Bench-Aero/eval_report_v11.json` | 64/63/0 |
| `FEM-Bench-Aero/external_numbers.md` | 64/128 分母口径 |
| `FEM-Bench-Aero/gate3_all55_d37.json` | 39/18/7 |
| `FEM-Bench-Aero/manifest.json` | 64 / 63 / 25-17-22 |

### A.2 复现命令

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
SYS="python"

# 门禁（pre-flight 用临时 JSON，不写官方）
"$SYS" check_claims.py --json "$TEMP/check_claims_preflight.json"
"$SYS" negative_controls.py

# 数据层
"$PY" verify_dataset.py --root ../FEM-Bench-Aero
"$PY" eval_dataset.py --root ../FEM-Bench-Aero
"$PY" check_forms.py --root ../FEM-Bench-Aero        # 串行，勿与其他 ccx 并行

# v1.1 内插校验
"$PY" _v11/verify_v11_interpolation.py --strict
```

---

## 附录 B　v1.1 数据层闭环

| 项 | 值 | 状态 |
|---|---|---|
| 数据集 | 64 条 / 63 类 / 25-17-22 | ✅ |
| 算例目录 | 128（64×2） | ✅ |
| 双码 | 9/9 新案例；`verify_dataset` 64 paired | ✅ |
| check_forms | 54 PASS / 0 FAIL | ✅ |
| gate4 | 128/128 | ✅ |
| eval_dataset | 64 cases / 63 classes / 0 failures | ✅ |
| 内插物理 | 7/7 strict + 2 双报 | ✅ |
| 网格 | 64/64；worst minJ 0.4636；tri3 0 | ✅ |
| 节点 | 9/9 未越线；最大 143,702 | ✅ |
| 关 3 | 39 field + 18 scalar + 7 reported-only | ✅ |
| 基线 | v1 55 条冻结；v1.1 未重跑；不可并列 | ✅ 标注 |
| v7 | 未开；exam 仍 25 | ⏳ |

---

## 附录 C　第十二轮 P1 逐项判定

| 第十二轮 P1 | 第十三轮状态 | 证据 |
|---|---|---|
| 9 条 Abaqus | ✅ | 9/9；verify 64 paired PASS |
| check_forms | ✅ | 54/0 |
| v1.1 数据 close | ✅ | gate4 128/128；eval 64-63-0；dedup 0 |
| v7 | ⏳ | 未开；paper 55/exam 25 |
| T-A3 顺序 | ✅ | 负控 22:06 → check 22:23 |
| venv | ✅ | R60；check_forms/verify 用 venv |
| 并行 ccx | ✅ | R61/S-47/NC-52；T-A6 串行 |
| check_claims mtime | ✅ | pre-flight temp；官方收口写 |
| T-A10 | ⏳ | N-12；C-001/2/4/5 + external 未入闸 |
| CLAUDE 49/50 | ⚠️ | live 50；CLAUDE/AGENTS 49 |

---

## 附录 D　文档/口径漂移清单

| # | 位置 | 现文 | 应为 |
|---|---|---|---|
| 1 | `CLAUDE.md` | check_claims 27/49/49 | **27/50/49**（T-A8 新增三活源） |
| 2 | `AGENTS.md` §0/§7 | 需核对 49/50 | 同 live 或改“以 §0 实读为准” |
| 3 | `CLAIMS` | 无 v1.1 数据 claim（C-036 未占用） | T-A10 新增 C-036 |
| 4 | `external_numbers.md` | 已分开 55/110 vs 64/128 | 保持；T-A10 加闸 |
| 5 | `DATASET_V11` | 64/9/54/128 已写 | 标 PASS；C-036 引用 |
| 6 | `README` | 对外数字表链接 | v7 落地后切 v7 headline |

---

> **本轮只读核对；除本文件外未改动任何项目文件。**
> 下一轮复评入口：T-A10（C-001/2/4/5 + external 入闸 + C-036）→ v7 paper → v7 candidates；v7 落地后 C-032/C-033 标 historical/supporting。
