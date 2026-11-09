# SOT（机器生成的一页真相 / 不要手改）

> 生成时间 2026-11-09 22:08 · `python sot.py` 重建 · 权威顺序 AGENTS > CLAIMS > RUBRIC > INDEX
> **这一页取代 §0 的五文件整读。** 需要细节时按指针读单个 artifact；禁止整读 CLAIMS/RUBRIC/tasks*.jsonl。

## 1. 唯一 headline（对外数字只认这一条）

- **C-032** · **L3 主基线（prompt **v2f** 代 = p2 + CONFLICT N-34 的 SYS 修正，2026-11-04 换代）—— 对外 headline**：考卷 v6c（`tasks_sha256 = 9c1faa3a…`，与 p2 代**逐字节相同**）× `candidates_l3_v7sysfix_glm`，`glm-5.3-flash`（R13，同模型同卷；**判分器、考卷、判分修正表全同 p2 代，唯一变量
- artifact：`feagpt_repro/reports/baseline_scorecard_L3_v6c_p2.json + feagpt_repro/reports/bootstrap_ci_L3_v6c_p2.json + feagpt_repro/reports/diagnostics/prompt_v2_effect_glm.md + feagpt_repro/reports/diagnostics/dev_reversal_v6c_p2.json + feagpt_repro/reports/diagnostics/dev_reversal_v6c_p2.md（v2f 换代的全过程与 p2 代归档见正文末段「诊断/归档（非成绩单）」说明——两者不作成绩单 artifact）` · status：**active（对外 headline）**

## 2. 当前考卷（换卷即换 sha，数字不可跨卷相减）

- `reports/papers/tasks_v8.jsonl` · 声明 208 条 · 实读 208 条
- sha 声明 `54d8352bfdec` · 实读前缀 `54d8352bfdec4015` · 一致

## 3. 版本锚点

- RUBRIC **v6.27**（mtime 2026-11-05 23:45）
- prompt sha `6b90daf07bbe070d`（baseline_scorecard_L3_v6c_ds_p2.json，mtime 2026-11-04 23:48）

## 4. 两道闸（读缓存，不是本次重跑；收口时必须重跑全量）

- check_claims：all_ok=True · 36 claims / 83 artifacts · check_claims.json @ 2026-11-09 22:08
- negative_controls：all_ok=True · 87/87 · negative_controls_87.json @ 2026-11-09 22:07

## 5. 里程碑看板（估算，非 artifact，不得进 claim）

| 段 | 权重 | 完成度 |
|---|---:|---:|
| A 让「能考」（0–30 天） | 25% | 89% |
| B 让「能教」（30–90 天） | 30% | 57% |
| C 让「能用」（90–180 天） | 35% | 0% |
| D 分发与可用性（横切） | 10% | 100% |
| 合计 | **100%** | ≈ 49% |

## 6. 下一步（只有一条）

- P2 已收口（见 DECISION_C6_P2.md）：主线 = 外部复现 1 人 → headline 决策 → SOT 减重
- 来源：DECISION_C6_P2.md

## 7. 本次任务的读取预算（写进 TASK_CONTRACT）

- 读取 ≤30k tokens：本页 + 本任务直接相关的 1 个 artifact；禁止整读 CLAIMS/RUBRIC/tasks*.jsonl。
- 写入 ≤10k tokens：每任务最多 1 条 claim + 1 个 artifact + 1 段记忆（≤2KB）。
- 闸：开工读本页；收口跑全量 `negative_controls.py` → `check_claims.py`。
- 发现新方向 → 写 CONFLICT 并停，不继续挖。
