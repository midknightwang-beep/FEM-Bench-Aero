# TASK_CONTRACT — T-A12a / T-A12b（第十四轮专家意见处置）

> 来源：`FEM-Bench-Aero第十四轮复评与执行纠偏_2026-10-30.md`（27/30）。
> 老王 2026-10-30 拍板：**headline 选 A**（C-032 保持唯一 headline，C-040 supporting，T-A12c 取消）；
> **`--scope all` 选 (b) 动态判据**（违规集必须 ⊆ dev 且每条带 reason，exam 违规集必须为空，不建 allowlist 文件）；
> **两道 dev 题（`L3_stiffened_panel_800x600` / `_str3`）长期挂 dev、不对外、不排 v8**。

## 共同前置（SOT 实读，2026-10-30 19:15）

| 项 | 实读值 |
|---|---|
| HEAD | `338bf4b` |
| 唯一 headline | C-032（`baseline_scorecard_L3_v6c_p2.json`，glm-5.3-flash，prompt v2） |
| 当前 rubric | **v6.0**（`RUBRIC.md` 顶部版本行；判定表含 R42–R68） |
| 当前卷 | `reports/papers/tasks_v7.jsonl`，sha `caf0f6c3…`（192 行 = L1/L2/L3 各 64） |
| 当前 prompt | `gen_candidates_v2.js`（v2；v3/v3b 已否决，C-035） |
| 门禁 | 负控 **60/60**、`check_claims` **32 claims / 65 artifacts / 55 语义项 全过**、`r32 --scope exam` rc=0、`--scope all` **rc=1**（4 条全 dev） |

---

## T-A12a — 协议 SOT 同步（单变量 = **协议文本**）

- **改什么**：`AGENTS.md` / `CLAUDE.md` / `CLAIMS.md` 三处「当前值」硬编码（rubric 版本、规则范围、下一步、解释器）。
- **不改什么**：paper / prompt / rubric 条款 / scorecard / headline / 任何成绩数字。
- **为什么只有这一个变量**：本轮发现的漂移**全部是协议里的副本**，与实际执行无关；成绩与 artifact 一个字节都不动。
- **allowlist**：`AGENTS.md`、`CLAUDE.md`、`FEM-Bench-Aero/CLAIMS.md`（**仅红线条二级标题**）、`feagpt_repro/check_claims.py`（新增 S-56）、`feagpt_repro/negative_controls.py`（新增 NC-59）、`feagpt_repro/reports/INDEX.md`（登记新产物）、`feagpt_repro/reports/diagnostics/task_a12_contract.md`。
- **核心决策（与专家方案的差异）**：协议里**一律不写** `vX.Y` 与 `R…–R…`，只写「以 `RUBRIC.md` 顶部为准」。
  专家建议「一次性改成 R1–R68 / v6.0」——**这是再写死一个会漂的数**，与 R63 的结论（不产生副本）相反；下一次加 R69 时它立刻又过期，且没有任何闸会响。
- **新增闸 S-56**：协议文件不得硬编码 rubric 版本 / 规则范围；`CLAIMS` 红线条标题不得带范围；venv-required 脚本不得用裸解释器调用。
- **新增负控 NC-59 四向**：四类改写各自必须让 S-56 变红，且**红的原因必须对**（分别命中 (a)/(b)/(c)/(d)）。
- **验收**：负控 **61/61**（+NC-59 一条，四向）；`check_claims` **56 语义项**全过（+S-56）；claims/artifacts 不变（32/65）；`git diff` 只含 allowlist。
- **停止条件**：任何 TSR/SFR/MSR/分母数字变化、任何负控失败、allowlist 外文件 → 停，写 `CONFLICT.md`。

## T-A12b — 审计闭合 + R32 闸口径（单变量 = **审计/闸判据**）

- **改什么**：`msr_l3.py` 的审计字段与传参源；`r32_audit.py` 的 all-scope 口径；`check_claims.py` S-54 扩展 + S-57；`negative_controls.py` NC-60；C-039/C-040 文本；README r32 口径。
- **不改什么**：**TSR / SFR / MSR 的任何分子或分母**。R67 纪律：改判分实现必须给出「除声明项外零差异」的构造性证据。
- **真根因（专家未识别，本轮新发现 N-26）**：`msr_l3.py:481` 的 `_FAUDIT = _denom_audit(exam_full_ids)`，而 `exam_full_ids` 来自 `den_rows`（已剔除 clarify/unresolved）⇒ pool 全是 counted 行 ⇒ `n_tasks_total ≡ n_counted` ⇒ `closure_ok` **代数恒真**，`:483` 的 `[FATAL] 分母不闭合` 对 exam_full 这一路从未生效。
  实测：glm `30 ≡ 30`、ds `29 ≡ 29`，clarify/unresolved 恒 0；真值应为 glm `34 = 30 + 4 + 0`、ds `34 = 29 + 4 + 1`。
  **修法：传参源 `den_rows` → `rows`**（与 `_EAUDIT` 一致），再补 `exam_full_task_closure` 字段。
- **其余**：`n_unresolved` 顶层/MSR 显式区分；补 `exam_full_msr_excl_solver`；`--scope all` 改动态判据（违规集 ⊆ dev 且每条带 reason，exam 必须空）。
- **验收**：`r32 --scope exam` rc=0；`--scope all` rc=1 且 S-57 绿；两份成绩单 `exam_full_task_closure.ok=true` 且 `34 = counted + clarify + unres`；`exam_full_msr_excl_solver` 存在；**全部 TSR/SFR/MSR 数字与改前逐数相等**。
- **停止条件**：任何成绩数字变化、exam scope 非 0、allowlist 与审计不一致 → 停。

## 不做（明确挂账）

- **T-A12c（切 headline）取消** —— 老王选 A。
- 两道 dev 题的 `length`/`width` 角色不可判**不修题面**（R65：v7 不能改老行），长期挂 dev、不进任何对外 claim。
- L2 clarify 双口径仍 `status=not_run`（模型从未跑 L2）。
