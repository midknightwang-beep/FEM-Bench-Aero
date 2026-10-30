# TASK_CONTRACT

- task_id: **T-P1a**（P-1 选项 A 的第一半：修判分元数据的事实错误）
- agent / date: 蜗子 / 2026-10-30
- SOT read: `FEM-Bench-Aero/CLAIMS.md`、`FEM-Bench-Aero/RUBRIC.md`、`feagpt_repro/reports/INDEX.md`、两份 `baseline_scorecard_L3_v7_*.json`
- 当前 headline（唯一）: **C-032**（v6c × glm-5.3-flash，prompt v2 代）
- 当前 paper path + sha256: `feagpt_repro/tasks/tasks.jsonl` == `reports/papers/tasks_v7.jsonl`，`caf0f6c3be8131c5b817a0bacfcca8ad3893fcfb95e29d8d9b525866a63e195a`
- 当前 prompt sha256: L3 `ce225186…`、L2 `03129c56…`（**本任务不改 prompt**）
- 当前 rubric 版本: v6.5（→ 本任务升 v6.6）
- 当前 model / scorecard: glm `baseline_scorecard_L3_v7_glm.json`、ds `baseline_scorecard_L3_v7_ds.json`
- **单变量**: `rubric`（判分元数据——具体是一个任务的一条 `clarify_wrong_keys`）
- 为什么只有这一个变量:
  - paper/prompt/candidates/model/denominator/headline **全部不动**；
  - 卷文件 `tasks.jsonl` **也不动**（见下条），改动以**显式修正表**落地，修正表本身即判分口径的一部分；
  - 唯一结果是「同一条题上同一个候选的判定由 FAIL 变 PASS」，MSR 分母不含澄清题（R23）⇒ MSR 不变。
- **为什么不直接改 `tasks.jsonl`**（关键决定）:
  `tasks/tasks.jsonl` 与 `reports/papers/tasks_v7.jsonl` 同 sha，且 **S-52 的 `TASK_CHAIN` 语义是「跨版只许加行、不许改老行」**。改一行会让 S-52(c) 变红，并连带作废所有下游 sha 锚点（r32 artifact 的 `paper_sha256`、成绩单 provenance、S-57）。
  故本任务采用 **显式修正表** `tasks/clarify_wrong_keys_fix.json`：卷不动、sha 不变，修正可审计、可回滚，且新增一条**可判不变量**（本族正确键不得被登记为错族键，见 S-59）。
- allowlist（精确到文件）:
  1. `feagpt_repro/tasks/clarify_wrong_keys_fix.json`（新建）
  2. `feagpt_repro/score_baseline.py`（只加 `_effective_wrong_keys` + provenance 记录；**判定逻辑本身不改**）
  3. `feagpt_repro/reports/baseline_scorecard_L3_v7_glm.json`、`_ds.json`（重打分）
  4. `feagpt_repro/reports/bootstrap_ci_L3_v7_glm.json`、`_ds.json`（重算 CI）
  5. `feagpt_repro/reports/archive/`（旧成绩单留档，D10）
  6. `feagpt_repro/check_claims.py`（S-59）、`feagpt_repro/negative_controls.py`（NC-65）
  7. `FEM-Bench-Aero/RUBRIC.md`（v6.6 / R71）、`FEM-Bench-Aero/CLAIMS.md`（C-040）、`feagpt_repro/reports/INDEX.md`
  8. `feagpt_repro/reports/diagnostics/p1_*.md`、`task_p1a_contract.md`
- 默认不改: paper / prompt / candidates / 其他模型 / headline / `tasks/tasks.jsonl` / L2 任何数字
- 验收命令 + 期望输出:
  1. `"$PY" score_baseline.py --candidates candidates_l3_v7_{glm,ds} --tasks reports/papers/tasks_v7.jsonl …` → glm exam TSR **23/25 不变**；ds **22/25 → 23/25**；`provenance.judge_overrides.n_applied == 1`
  2. 逐题 diff：**只有 `L3_naca4412_wingbox` × ds 一条翻转**（1 条 / 64 条）
  3. `python -c` 复算 2×2 → **both 23 / only_glm 0 / only_ds 0 / neither 2**
  4. `negative_controls.py` 全绿（66 → 67）
  5. `check_claims.py` `all_ok=True`（含新 S-59）
  6. **L2 两份 `l2_scores_v7_*.json` 逐字节不变**（本任务不碰 L2）
- 停止条件:
  - 若翻转条数 ≠ 1 ⇒ 停，不得提交
  - 若 L2 数字有任何变化 ⇒ 停（说明改动泄漏到了不该动的地方）
  - 若 glm 数字变化 ⇒ 停
  - 若需要改 `tasks.jsonl` 才能通过 ⇒ 停，回来问
- **post-hoc? yes** —— 已看过结果才定政策。必须：新 rubric 版本号 + 显式声明 + bridge（旧 22/25 → 新 23/25）+ claim 内标注；旧 artifact 留档（D10）。
- 交付报告路径: `feagpt_repro/reports/diagnostics/p1_overclarify_policy.md`（决策材料，已写）+ 本文件
