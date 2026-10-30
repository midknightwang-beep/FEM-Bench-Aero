# T-R1 任务契约：ROADMAP 对齐到当前 SOT

- **任务 id**：T-R1（单变量：ROADMAP 的分母与状态标注）
- **日期**：2026-10-30
- **发起**：老王拍板「现在就做这个 ROADMAP 对齐」

## 1. 为什么做

2026-10-30 22:22 回答「全量任务完成度」时实测到：`FEM-Bench-Aero/ROADMAP.md` 仍是 2026-10-24 起草稿，通篇按 **55 条口径**，且**完全没有 L2 澄清层这一整段**（L2 在 10-30 才首次跑通判分，晚于 ROADMAP 六天）。

后果：任何按该 ROADMAP 算的进度百分比，分子是新的、分母是旧的 ⇒ 分母失真。**用过期 WBS 算进度，比不算更危险**（与 R63「不制造第二数据源」同源）。

## 2. allowlist（只许改这三个）

| 文件 | 动作 |
|---|---|
| `FEM-Bench-Aero/ROADMAP.md` | 原地升 v2.0 |
| `feagpt_repro/reports/diagnostics/task_r1_contract.md` | 新建（本文件） |
| `feagpt_repro/reports/diagnostics/task_r1_report.md` | 新建 |

## 3. 明确不改（边界）

- ❌ 不改 `CLAIMS.md` / `RUBRIC.md` / `AGENTS.md` / `QUICKSTART.md` / `DATA.md`
- ❌ 不改任何脚本、任何 artifact、任何考卷、任何候选
- ❌ **不改任何数字**（本条是硬约束：ROADMAP 对齐不产生任何新成绩）
- ❌ 不动 headline、不动分母、不重跑模型
- ❌ 不为 ROADMAP 另存历史副本（`git show HEAD:...` 即旧版，另存 = 制造第二数据源，R63）

## 4. 数字纪律（本轮的核心风险）

ROADMAP 不在 R-A3 列举的四份文件（CLAIMS/README/RUBRIC/INDEX）内，**但精神适用**。故：

1. **凡可推导的条数/分数，只写指针**（`参见 C-0xx`），不手抄。
2. **凡必须出现的具体数**，一律标注它是**哪个时点的值**（v1.0 起草时点 = 2026-10-24），并在文首总声明「历史值，当前值以 CLAIMS 为准」。
3. **完成度百分比是估算、不是测量**：权重是判断，必须明文写出、可替换；不得写进任何 claim，不得被引用为项目指标。

## 5. 验收（可机械检查）

| # | 判据 | 检查法 |
|---|---|---|
| V1 | 四段权重明文且和为 100% | 目视 + 算术 |
| V2 | 有 L2 澄清层独立段 | 目视 |
| V3 | 每个工作项带状态标记 + 证据指针 | 目视 |
| V4 | 无「无指针的裸数字」 | 逐行 grep |
| V5 | 完成度标注了「估算/非 artifact」 | 目视 |
| V6 | 改后 `negative_controls` / `check_claims` 仍全绿 | 跑闸（R59 顺序） |
| V7 | 工作区只含 allowlist 文件改动 | `git status --porcelain` |

## 6. 停止条件

- 若发现 ROADMAP 的某条与 CLAIMS/artifact **实质冲突**且无法用指针化解 ⇒ 停，写 `CONFLICT.md`，给 3 选项（R-A11）。
- 若改文档导致任一闸变红 ⇒ 停，不自行改闸。

## 7. 复述

> **我只改 `ROADMAP.md` 一份文档（+ 两份 diagnostics 记录），验收是 V1–V7 七条，停止条件是「与 SOT 实质冲突」或「闸变红」。不改任何数字、不重跑、不动 headline。**
