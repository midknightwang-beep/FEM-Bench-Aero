# TASK_CONTRACT — T-A14「L2 clarify 按族分层口径说明」

> 老王 2026-10-30 拍板 **A1（可复算产物 + 闸）**。本文件在动手前写，事后不改数字段。

## 1. 合同

- **task_id**: T-A14
- **agent / date**: 蜗子 / 2026-10-30
- **SOT read**: `FEM-Bench-Aero/CLAIMS.md`（C-041 / C-032）、`FEM-Bench-Aero/RUBRIC.md`（R66 / R54 / R70 / R71）、`feagpt_repro/reports/INDEX.md`、`reports/l2_clarify_dual.json`
- **当前 headline（唯一）**: **C-032**（本轮不碰）
- **当前 paper path + sha256**: `tasks/tasks.jsonl` ／ `caf0f6c3be8131c5b817a0bacfcca8ad3893fcfb95e29d8d9b525866a63e195a`（本轮不碰）
- **当前 prompt path + sha256**: L2 专用 prompt `03129c56d83b8bd37dc1393b649e7250d4bdda2edf680d83889ebae07c4c0d83`（本轮不碰，**不重跑模型**）
- **当前 rubric 版本**: v6.6（本轮 → v6.7，仅登记口径，不改判据）
- **当前 model / scorecard**: `glm-5.3-flash` ／ `deepseek-v4-pro`，`reports/l2_scores_v7_{glm,ds}.json` + `reports/l2_clarify_dual.json`
- **单变量**: **无（纯派生 + 标注）** —— 不重跑模型、不改判据、不改分母、不改 prompt/paper。理由：族级数字本来就完全由已入库的 `per_task[].{family,pass,name_leak}` 决定，本轮只是把它**落盘 + 加闸**，不产生任何新测量。
- **allowlist（精确到文件）**:
  1. `feagpt_repro/score_l2.py`（`_block` 增 `by_family` + 族级闭合 FATAL）
  2. `feagpt_repro/report_l2_clarify.py`（透传 `by_family` + 逐块闭合断言 + md 增族级表）
  3. `feagpt_repro/reports/l2_scores_v7_glm.json`、`l2_scores_v7_ds.json`（**只许新增 `by_family` 键**）
  4. `feagpt_repro/reports/l2_clarify_dual.json` / `.md`
  5. `feagpt_repro/check_claims.py`（新增 S-60）
  6. `feagpt_repro/negative_controls.py`（新增 NC-66）
  7. `feagpt_repro/reports/negative_controls_<N>.json`（N 由实读决定）+ 旧份归档
  8. `FEM-Bench-Aero/RUBRIC.md`（新增 R72 + 版本头 v6.7 + 版本历史行；**并把上一轮我把 R71 插到 R70 前面的顺序错位摆回升序**）
  9. `FEM-Bench-Aero/CLAIMS.md`（C-041：族级数字改为指向 artifact；不改任何数）
  10. `feagpt_repro/reports/INDEX.md`、`FEM-Bench-Aero/README.md`（同上）
  11. `feagpt_repro/reports/diagnostics/task_a14_contract.md` / `task_a14_report.md`（本文件与交付报告）
- **默认不改**: paper / prompt / 判据（`judge_clarify_field_level`）/ 分母（64 / 45 / 19）/ headline / L3 任何产物 / `check_l2_leak.py`
- **验收命令 + 期望输出**:
  1. `python score_l2.py --cand candidates_l2_v7_glm --out …` 与 ds 各跑一次 ⇒ 除 `by_family` 外**逐叶子零差异**（用 `_regress_scorecard.py` 或等价逐叶子比对，allowlist 只允许 `by_family` 新增）
  2. `python report_l2_clarify.py --scores …,… --out … --md …` ⇒ 除 `by_model.*.*.by_family` 外零差异
  3. **既有数字逐数不变**：glm `49/64 · 30/45 · 19/19`；ds `36/64 · 21/45 · 15/19`；`category_counts` 四项不变
  4. **族级闭合**：每桶 `Σ by_family.n == n`、`Σ by_family.passed == passed`；且每族 `informative + invalid == all`（任务数与通过数两侧）
  5. `negative_controls.py` 全绿（含新 NC-66 多向）
  6. `check_claims.py` 全过（含新 S-60）
- **停止条件**（任一触发即停并给 3 选项，R-A11）:
  - 任一既有数字变动 ⇒ 说明我动了不该动的
  - 族级求和与总数不闭合
  - `per_task` 缺 `family` 字段（锚点缺失不得 skip）
  - 负控 / 语义检查出现绿色以外的结果且原因不明
- **post-hoc?**: **no**（本轮不产生任何新测量，只把已存在的派生量落盘；不涉及「看完结果改口径」）
- **交付报告路径**: `feagpt_repro/reports/diagnostics/task_a14_report.md`

## 2. 复述（C1 要求）

> **我只改**「族级分层这件事的可复算性与可审计性」：给 `score_l2.py` / `report_l2_clarify.py` 加 `by_family` 并断言闭合，给 `check_claims.py` 加 S-60、`negative_controls.py` 加 NC-66，把 RUBRIC 加 R72 登记口径，把 C-041 / INDEX / README 里的族级数字改成指向 artifact。
> **验收是**：两份 `l2_scores` 与 `l2_clarify_dual` 除新增 `by_family` 外逐叶子零差异、六个既有数字一个不变、族级闭合成立、两道闸全绿。
> **停止条件是**：任一既有数字变动、族级不闭合、`family` 锚点缺失，或闸出现原因不明的结果 —— 那就停下来给你三个选项，不自己修到绿。

## 3. 为什么这件事非做不可（动机）

`CLAIMS.md` C-041 正文写着「glm 15 条失败**全在翼盒**（24/39）、非翼盒三族全对」「ds 同样是翼盒最差（15/39）、非翼盒 21/25」「`rib_thickness`/`stringer_height`/`sweep_deg` **恰好都是 1/6**」—— 这些**族级与字段级**数字，在官方 artifact 里**一个都没有**：

- `l2_clarify_dual.json` 的 `by_model.<model>.{clarify_all,clarify_informative,invalid}.by_family` 全是 **`null`**；
- 顶层 `clarify_all.by_family` 只有**分母构成**（wingbox 39 / open_hole_panel 13 / fuselage_barrel 7 / stiffened_panel 5），不是通过数；
- 唯一的族级通过数表在 `reports/diagnostics/task_a13c_ds_report.md` —— 一份**手写**文档，**无生成器**（全仓 `grep` 只有它自己的合同提到它）。

⇒ 这违反 **R-A3「禁止手抄数字」**。而且 N-27 的核心结论（「64 与 45 的差是族构成差，不是泄漏净效应」）恰恰**完全建立在族级数字上** —— 结论比它引用的证据更"官方"，是本项目最忌讳的那种错位。

## 4. 已知的坑（开工前先记住）

1. **`by_family` 有两种含义，别混**：顶层 `clarify_all.by_family` 现有的是**分母构成**（每族多少题）；本轮给 `by_model.*` 加的是**每族 n/passed/pct**。两者同名不同义 —— 要么改名要么在 `_note` 里写死，**不得**让读的人以为是同一个东西。
2. **`by_model` 里 `passed=None` 的块**（`not_run`）不能有 `by_family` 数字：那会变成「用半批候选算族级」。与 `passed=None` 同处理。
3. S-53 已经守了「逐块 `all == informative + invalid`」，本轮 S-60 **不得重复它**（同一判据写两遍迟早不一致，T-A11a 的教训）—— S-60 只守**族级**：`Σ族 == 总数`、`每族 inf + inv == all`、顶层与 `by_model` 对应块逐数相等。
4. 上一轮我把 **R71 行插到了 R70 前面**（升序表被打破，`grep -n '^| \*\*R'` 可见 315 = R71、316 = R70）。本轮顺手摆回 —— 这是**我自己上一轮的错**，不是顺手改别人东西。
