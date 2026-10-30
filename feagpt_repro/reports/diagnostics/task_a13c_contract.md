# TASK_CONTRACT — T-A13c（L2 clarify 第二模型：ds）

- task_id: **T-A13c**（续 T-A13b；同一判据、同一卷、同一 prompt，只换模型）
- agent / date: 蜗子 / 2026-10-30
- SOT read: `CLAIMS.md`（C-032 headline / C-041 supporting）/ `RUBRIC.md`（v6.3，R1–R69）/ `reports/INDEX.md` / `reports/l2_scores_v7_glm.json`

## SOT 实读（开工前，全部现场读）

| 项 | 值 |
|---|---|
| HEAD | `ea452a1`（memory，T-A13a/T-A13b 收口后） |
| 当前 headline（唯一） | **C-032**（v6c 55 条 / exam 25）—— 本轮**不得动**（R48） |
| 当前考卷 | `tasks/tasks.jsonl`，sha256 `caf0f6c3be8131c5b817a0bacfcca8ad3893fcfb95e29d8d9b525866a63e195a` |
| L3 prompt sha（必须不变） | `ce225186cafa5d55c445e30e201b658a37834ec67be8c80a45201b3508423f22` |
| L2 prompt sha（本轮必须与 glm 完全相同） | `03129c56d83b8bd37dc1393b649e7250d4bdda2edf680d83889ebae07c4c0d83` |
| 当前 rubric | v6.3（R1–R69，新增 R69） |
| 门禁 | 负控 **64/64**；`check_claims` **33 claims / 67 artifacts / 57 语义项 全过** |
| glm 的 L2 成绩（对照基线） | `clarify_all` **49/64 = 76.6%** ／ `clarify_informative` **30/45 = 66.7%** ／ `invalid` **19/19** |

## 老王拍板（本轮前置）

- **N-27 取 (a)**：只如实标注、不动口径 —— 两个分母照 R66 双报，同时写清「64 与 45 的差主要是族构成差，不是泄漏净效应」。**不**按族分层（b）、**不**遮 name 重跑（c）。
- 下一步 = 补第二模型（ds）跑同一批 64 条 L2。

## 单变量

**`candidates(model)`：glm-5.3-flash → deepseek-v4-pro。** 除模型外**一切冻结**：

| 冻结项 | 为什么 |
|---|---|
| 考卷 `tasks/tasks.jsonl`（sha `caf0f6c3…`） | R65：v7 冻结，改一个字节整卷作废 |
| L2 prompt（sha `03129c56…`） | 与 glm 完全同一段文本（`SYS_L2 = SYS + 追加段`）⇒ 两模型可比 |
| 呈现 `presentation = spec_json_raw_name` | 与 glm 一致（不遮 name；N-27 选 (a) 也不改这个） |
| 判据 `score_l2.py` | 判据 import 自 `score_baseline.judge_clarify_field_level`；**跑前已冻结并提交**（R-A2） |
| 双口径掩码 | `check_l2_leak.scan`，19/45 的划分与模型无关 |

## allowlist

- `feagpt_repro/candidates_l2_v7_ds/`（新建）
- `feagpt_repro/reports/l2_scores_v7_ds.json`（新建）
- `feagpt_repro/reports/l2_clarify_dual.{json,md}`（**双模型并列**：glm 与 ds 两块都在，不得只留一侧）
- `FEM-Bench-Aero/CLAIMS.md`（C-041 扩为双模型；C-038 同步）、`reports/INDEX.md`、`RUBRIC.md`（版本记录 + v6.4）、`README.md`（版本引用）
- `CONFLICT.md`（N-27 补「已拍板 (a)」；若发现两模型族构成不同则追加 N-28）

**默认不改**：`tasks/tasks.jsonl`、`gen_candidates_v2.js`（`SYS`/`SYS_L2` 都不动）、`score_l2.py` 的判据逻辑、headline、任何 L3 artifact。

## 验收命令 + 期望输出

```bash
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
node gen_candidates_v2.js --print-prompt-sha        # 必须仍 = ce225186…
node gen_candidates_v2.js --print-prompt-sha-l2     # 必须仍 = 03129c56…（与 glm 同一段）
"$PY" negative_controls.py                           # 必须 64/64
"$PY" check_claims.py --json "$TEMP/…"                # 必须全过
```

ds 成绩单必须自洽：`n_tasks_l2=64`、`n_candidates=64`、`n_missing=0`、
`clarify_all.passed + invalid.passed == `（不，两分母不构成加和关系，见下）——
**真正要闭合的是**：`clarify_all.n=64`、`clarify_informative.n=45`、`invalid.n=19`，
且 `clarify_all.passed` 与 `clarify_informative.passed + invalid.passed` **必须相等**
（19/19 全过时后者 = 45 侧通过数 + 19；否则差值 = 泄漏子集里未过的条数）。

## 停止条件（R-A11）

- `tasks/tasks.jsonl` sha 变了 ⇒ 立刻停
- L3 prompt sha 变了、或 L2 prompt sha 变了 ⇒ 停（不再是单变量）
- 负控 / `check_claims` 不全绿 ⇒ 停
- ds 的 `n_missing > 0` 或候选不齐 64/64 ⇒ 停，不许把缺的题从分母里剔掉（R-A5）
- 若 ds 与 glm 的**族排序**出现反转（例：某族 glm 全对、ds 全错）⇒ 停，查是不是判据对某模型系统性不利

## post-hoc?

**no**。判据、prompt、卷、掩码四样都在跑前冻结并已提交（T-A13a/b）。本轮唯一变量是模型名字。

## 交付报告路径

`feagpt_repro/reports/diagnostics/task_a13c_ds_report.md`
