# T-D3 契约：行尾规范化（统一 CRLF）

> 拍板日期：2026-10-31，老王选「方案 A 统一 CRLF」。
> 前置测量：`reports/diagnostics/task_d3_measure.md`（四条硬事实 + 28 vs 428 代价表）。

## §1 只改什么（范围）

| # | 改动 | 落点 |
|---|---|---|
| 1 | 新增行尾策略声明 | `.gitattributes`（新建） |
| 2 | 工作区文本统一为 CRLF | 954 个 `w/lf` / `w/mixed` 的被追踪文本文件（**不改索引、不改 blob**） |
| 3 | 重算被规范化打断的**活锚点** | 28 条 LF 锚点中活着的 7 条（见 §2 清单）；21 条历史快照 `_snap_*.json` 的旧值**保留不动**（无判据读，改了反而制造假象） |
| 4 | 修 F-4 | `feagpt_repro/tasks/tasks.jsonl.sha256`（记的是 v6b 旧卷 sha，且无闸守） |

**明确不做**：
- 不改任何判据逻辑（`check_claims.py` 一行不动）——**除非**规范化后被证明确实存在"判据自己依赖行尾"的缺陷，那要单独立项；
- 不改任何成绩单里的**分数/通过数/分母**（R71：只修「记录与实际不符」的事实错误）；
- 不动 `_snap_*.json` 等历史诊断产物的旧 sha 值；
- 不删除、不移动任何文件。

## §2 必须重算的活锚点（7 条，逐条留痕）

| 文件 | 条数 | 指向 | 处置 |
|---|---|---|---|
| `reports/baseline_scorecard_L3_v7_glm.json` | 1 | 修正表（LF 版） | 重算为 CRLF 版 sha |
| `reports/baseline_scorecard_L3_v7_ds.json` | 1 | 同上 | 同上 |
| `reports/baseline_scorecard_L3_v4.json` | 2 | 历史卷/表 | 重算（历史成绩单，不改分数） |
| `reports/msr_l3_v4.json` | 1 | 历史统计 | 重算 |
| `reports/papers/SHA256SUMS` | 2 | 论文包内文件 | 重算 |
| `tasks/tasks.jsonl.sha256` | 1 | 考卷（**已过期**） | 直接改为当前卷 CRLF sha（F-4） |

## §3 验收（全部要跑，缺一不算完成）

| # | 验收项 | 判据 |
|---|---|---|
| V1 | 工作区行尾统一 | `git ls-files --eol` 里文本文件**全部 `w/crlf`**，`w/lf` / `w/mixed` 计数为 0 |
| V2 | 规范化不产生提交 | `git status --porcelain` 除 `.gitattributes` 与本次改动外为空；`git diff --stat` 不出现 900+ 文件 |
| V3 | 换机一致（**关键**） | 新建干净 clone，逐文件 sha256 与主仓比对：**不同数 = 0** |
| V4 | 判据不退化 | 主仓 `negative_controls` 69/69 → `check_claims` 全过（顺序不可反，R59） |
| V5 | clone 里判据可跑 | 干净 clone 里 `check_claims` 只剩「缺 node_modules / 无 hook / mtime」这类**非行尾**红项，**S-57 与 S-59 必须都绿** |
| V6 | 公开集不退化 | `_d4_public_set.py --check` P0–P6 全过（含 P4b 脱敏可逆） |
| V7 | F-4 已修 | `tasks/tasks.jsonl.sha256` 的 sha == 当前卷 CRLF 版 sha，且扫描器 T1b 转绿 |

## §4 停止条件（命中任一即停，写 CONFLICT.md 给选项）

- V3 出现「不同数 > 0」且原因不是**预期内的 7 条活锚点**；
- V4 出现**新的**红项（非本次改动造成）；
- 规范化导致任何 `.inp` / `.msh` 类求解输入无法被工具读取；
- 发现 954 个文件里混有**非文本**被误转（`git ls-files --eol` 出现 `w/-text` 变化）。
