# TASK_CONTRACT — T-A13a / T-A13b（L2 clarify 双口径首次跑分）

- task_id: **T-A13a**（搭链路，不跑模型） / **T-A13b**（跑模型出分，单变量 = candidates）
- agent / date: 蜗子 / 2026-10-30
- SOT read: `CLAIMS.md` / `RUBRIC.md`（v6.1，R1–R69）/ `reports/INDEX.md` / `reports/baseline_scorecard_L3_v7_{glm,ds}.json`

## SOT 实读（开工前，全部现场读）

| 项 | 值 |
|---|---|
| HEAD | `4b332bb`（T-A12b） |
| 当前 headline（唯一） | **C-032**（v6c 55 条 / exam 25） |
| 当前考卷 | `tasks/tasks.jsonl` = `reports/papers/tasks_v7.jsonl`，sha256 `caf0f6c3be8131c5b817a0bacfcca8ad3893fcfb95e29d8d9b525866a63e195a` |
| 当前 L3 prompt sha | `ce225186cafa5d55c445e30e201b658a37834ec67be8c80a45201b3508423f22` |
| 当前 rubric | v6.1（R1–R69） |
| 门禁 | 负控 **63/63**；`check_claims` **32 claims / 65 artifacts / 57 语义项 全过** |
| L2 双口径 artifact | `reports/l2_clarify_dual.json`：`clarify_all n=64` ／ `clarify_informative n=45` ／ invalid 19，**`status=not_run`** |

## 侦察结论：L2 至今**没有任何可跑链路**（不是「跑过但没分」，是「一次都没跑过」）

`find` 全仓 **零个** `L2_*` 候选文件。要跑，缺三样东西：

| # | 缺什么 | 证据 |
|---|---|---|
| 1 | **输入渲染**：`gen_candidates_v2.js:138` 只发 `t.input.nl`，而 L2 的 `input` **只有 `spec_normalized`、没有 `nl`**（64/64 条）⇒ 直接 `--levels L2` 会发「工程任务描述：undefined」 | 逐条统计：`with nl: 0`、`input_source: template 64/64` |
| 2 | **判分元数据**：L2 **零** `clarify_aliases`、**零** `clarify_wrong_keys`（L3 都有）⇒ `judge_clarify_field_level` 退化成 `al = aliases or [f]` = **必须字面命中键名** | 逐条统计：`with aliases: 0 / with wrongkeys: 0 / with ec: 64` |
| 3 | **打分器路由**：`score_baseline.py:289` 写死 `if t['input_level'] == 'L3'` ⇒ L2 候选被**静默跳过**（不是报错） | 源码 |
| 4（附带） | v1 生成器 `gen_candidates.js:43` **有** L2 分支，但：提示写「缺失项标 MISSING」而卷子**根本没有 MISSING 占位**（直接删键）；用 `CLARIFY:` 文本前缀而非 `{"clarify":[...]}`；SYS 缺 R50 数量铁律；不回写 `prompt_sha256`（R53 无法溯源） | 源码 |

## 单变量

- **T-A13a**：`prompt`（新增 L2 专用输入渲染 + 判分链路）。**不跑模型、不动 paper、不动 L3 prompt**。
- **T-A13b**：`candidates(model)`。除候选集外一切冻结。

## 为什么必须拆成两个

R-A1：搭链路（新 prompt 版 + 新打分器）与跑模型是两个变量。且 **R-A2 要求判分口径在跑之前冻结** —— 先搭好、审过、提交，再跑；否则「看完结果再调判据」= post-hoc。

## allowlist

**T-A13a**
- `feagpt_repro/gen_candidates_v2.js`（加 `SYS_L2` 常量 + `--levels L2` 分支 + `--mask-name` 开关；**`SYS` 字节不动**）
- `feagpt_repro/score_l2.py`（新建；`import judge_clarify_field_level`，不复制实现）
- `feagpt_repro/negative_controls.py`（新增 NC-62，`score_l2` 判据自证伪）
- `feagpt_repro/reports/l2_clarify_dual.{json,md}`（`status` 由 `not_run` 升 `ready`/`scored`，由 `report_l2_clarify.py` 重生成）
- `feagpt_repro/check_claims.py`（仅当需要加闸；否则不动）
- `FEM-Bench-Aero/CLAIMS.md` / `reports/INDEX.md` / `RUBRIC.md`（登记链路与 prompt sha）

**T-A13b**：`candidates_l2_v7_<model>/` + `reports/l2_clarify_dual.{json,md}` + CLAIMS/INDEX 的分数登记。

**默认不改**：`tasks/tasks.jsonl`（R65 冻结，sha 必须仍为 `caf0f6c3…`）、`gen_candidates_v2.js` 的 `SYS`、`RUBRIC` 的红线条、headline（C-032）、任何 L3 artifact。

## 唯一需要老王拍板的口径（T-A13b 开跑前）

**Q1：`spec_normalized.name` 给不给模型？**
- (甲) 给 ⇒ 沿用 C-038 现成双口径 64/45（S-53 零改动）。代价：64 里 19 条靠 `name` 直接看到答案（`..._d30` 省略 `hole_d`），真信号只有 45 条。
- (乙) **遮掉（换成中性 `case_<8 位 hash>`）** ⇒ 泄漏源消失，64 条全部可判，主口径 = 64；45/19 掩码仍并列显示作历史口径对照（S-53 要求两块都在 ⇒ **不用改闸**）。
- **推荐 (乙)**：L2 从未跑过 ⇒ 现在遮**零历史损失**；且遮蔽是**加强**题（去泄题），不是掩盖缺陷（与 R66「不得改题掩盖」方向相反）。

**Q2：clarify 判据用字面键名，还是补 13 个字段的语义别名？**
- (甲) **字面键名（推荐）**：SYS 已给全四族键名总表 + 明确要求「每条问题必须写出缺失字段的键名」⇒ 判的是**遵守输出格式**，不是猜键名，与 R19 一致。零新元数据、跑前可冻结、无 post-hoc 风险。
- (乙) 补中英别名：更公平，但等于**跑前新增判分元数据**，且放宽（R69 要求边界）。
- 两者都落在 sidecar/代码里，不动 `tasks.jsonl`。

**Q3：先跑哪个模型？**
- 推荐先 **glm-5.3-flash**（与 C-032 headline 同 model）跑 64 条；出数后再跑 ds 作 supporting。
- 成本：纯 LLM、无求解（澄清题判 fabricate 不需要跑 pipeline）⇒ 分钟级，不占 `.solve.lock`。

## 验收命令 + 期望输出

```bash
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
node gen_candidates_v2.js --print-prompt-sha          # L3 必须仍 = ce225186…（SYS 未动）
"$PY" score_l2.py --self-test                          # 伪候选判据自证伪：全对→全过、改键名→该条红
"$PY" negative_controls.py                             # 63 → 64（+NC-62），全绿
"$PY" check_claims.py --json "$TEMP/…"                  # 全过；S-53 随 status 升 scored 自动加严
"$PY" _regress_scorecard.py …                          # L3 两份成绩单零差异（本轮不该碰 L3）
```

## 停止条件（R-A11）

- `tasks/tasks.jsonl` sha 变了 ⇒ 立刻停（碰了冻结件）
- L3 prompt sha 变了 ⇒ 立刻停（SYS 被动到）
- 任一 L3 成绩单出现叶子差异 ⇒ 停
- 负控/`check_claims` 不全绿 ⇒ 停
- 跑出来的分与 `check_l2_leak` 的掩码不自洽（如被遮后 19 条与 45 条差异仍显著）⇒ 停，写 `CONFLICT.md`（可能是第二个泄漏通道）

## post-hoc?

**no**。T-A13a 只搭链路不产生分数；T-A13b 的判据在跑之前冻结并提交。

## 交付报告路径

`feagpt_repro/reports/diagnostics/task_a13_l2_report.md`
