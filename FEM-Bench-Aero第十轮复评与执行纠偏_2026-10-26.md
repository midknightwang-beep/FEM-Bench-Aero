# FEM-Bench-Aero 第十轮复评与执行纠偏（W5c-6b/6c、C-031 后）

> **复评日期**：2026-10-26（第十轮）
> **复评对象**：W5c-6b（第九轮 4 个 P1 收口 + T1+ + R42–R46）、W5c-6c（第二模型 C-031：deepseek-v4-pro + 分母口径 bug + R47–R49）、清理提交 `38b26f1`
> **复评方式**：只读核对 + 官方 artifact 交叉检查（C-029/C-031 成绩单、T1+、审计、负控 44、`check_claims` 36、CLAIMS/README/INDEX/W5B_PLAN）；**除本文件外未改动任何项目文件**
> **结论先行**：
> **第九轮的 4 个 P1 全部清了，T1+ 也真正落地了。** README/C-021/C-025/C-026 都改成 C-029；dev 25/30 改成“23/30 实测 + paper-clean 投影 + 5 条模型失败仍在”；T1+ family-mode 落地（exam 0/25、字段命中 85.93%、oracle 0/25）；MSR 别名补全；负控 39→**44/44**；`check_claims` 22/34/33→**23/35/36**。C-029 仍是唯一 headline，C-031 标 supporting（R48）。
> **但第二模型这一轮不是“干净的模型对比”，而是“一次高价值的归因实验”：** 两模型 `spec_pass` 都是 **20/25**，92.0% vs 80.0% 的 12 pp **全部来自 3 条澄清题**——glm `clarify_ok` 3/3，deepseek `fabricated` 3/3（FPR **100%**，4/4）。其中 `stiffened_panel_600x600_str3` 的 `n_stringers=0` 是 **SYS prompt“未提长桁→0”直接授权**的，而题面 `expected_clarifications` 要求澄清 ⇒ **prompt 与题面自相矛盾，属我方缺陷**。**C-031 的 80% 是 prompt 缺陷压低的下界，不是 deepseek 的能力；在修 prompt 并重生成之前，不得用它做模型排名。**
> **另有两个 artifact 完整性问题：** ①`baseline_scorecard_L3_v6c_dsv4pro.json` 顶层 `model` 仍写 **glm-5.3-flash**（provenance 里才是 deepseek-v4-pro），跨模型 artifact 的模型标签错了；②C-031 的 `n_clarify_excluded=5` 把 **4 条编造澄清 + 1 条未收敛**混在一个字段里（C-029 是 4 条纯澄清），分母构成不可直接比。
> **判定：C-029 继续作官方 headline；C-031 只作 supporting/诊断。下一步 P0 = 修 prompt（“未提长桁→0”与 expected_clarifications 对齐）+ 重生成两模型（C-032/C-033），再做 W5d 的干净跨模型对比；C-031 的 model 字段与分母口径同轮修。**

---

## 目录

- [0. 复评摘要](#0-复评摘要)
- [1. 变化与交付](#1-变化与交付)
- [2. 已验证的改进（credit）](#2-已验证的改进credit)
- [3. 剩余问题](#3-剩余问题)
- [4. C-031 准入评估](#4-c-031-准入评估)
- [5. 下一步任务执行建议](#5-下一步任务执行建议)
- [6. 防跑偏机制（R50–R53 建议）](#6-防跑偏机制r50r53-建议)
- [7. 评分卡](#7-评分卡)
- [8. 待拍板](#8-待拍板)
- [附录 A　证据索引与复现命令](#附录-a证据索引与复现命令)
- [附录 B　C-031 vs C-029](#附录-bc-031-vs-c-029)
- [附录 C　第九轮 P1 逐项判定](#附录-c第九轮-p1-逐项判定)
- [附录 D　文档/口径漂移清单](#附录-d文档口径漂移清单)

---

## 0. 复评摘要

### 0.1 三句话结论

1. **第九轮的 4 个 P1 全清了，且 T1+ 做得比要求更好。** 不是“补个字段”，而是把“地板恒 0”的成因讲清楚了：全或无判分 × 族内参数逐条唯一 ⇒ 最强的不读输入策略（逐字段族级众数）能命中 **85.93%** 受判字段、最好一条只差 1 个字段，但 25 条无一全对；族内 oracle 也是 0/25。value_added 因此给了**任务级 + 字段级双尺度**，C-029 字段级 **99.34%（Δ+13.4pp）**，C-031 **87.42%（Δ+1.5pp BELOW）**——三档分明，证明字段级指标有区分度。
2. **C-031 的价值在归因，不在分数。** 两模型 `spec_pass` 都是 20/25；2 条 exam `spec_fail` 同题同字段；dev 6/7 同题同字段；唯一实质差异是缺失信息处理：glm 问、deepseek 编。3 条编造里 **1 条（`stiffened_panel_600x600_str3` 的 `n_stringers=0`）是 SYS prompt“未提长桁→0”直接授权，另 2 条（`n_frames`/`n_ribs`）是模型未问**——**80% 是“prompt + 模型”的混合下界，不是干净的 deepseek 能力。**
3. **两个 artifact 完整性问题必须修：** C-031 成绩单顶层 `model` 写成了 `glm-5.3-flash`；`n_clarify_excluded=5` 把 4 条编造 + 1 条未收敛混在一起。**修完 prompt、model 字段、分母口径，再谈 W5d 的跨模型榜单。**

### 0.2 执行总评

| 工作块 | 评分 | 一句话判断 |
|---|---|---|
| W5c-6b：第九轮 P1 收口 | **A** | 4 个 P1 全清；S-29..S-32；T1+；负控 44/44；22/34/33 |
| W5b-5：C-031 第二模型 | **A−** | 55/55、9 min 生成、41 min MSR；跨模型归因扎实；**但 prompt 缺陷 + model 字段错 + 分母混类** |
| 38b26f1：清理过程备份 | **A** | 删除 `_bak_c031_pre_msr.json`，正式 artifact 唯一 |
| **总体** | **A− / 28/30** | 基础设施 A；科学有效性 B+/A−；**3 个 P1 收口后进 W5d** |

> **和第九轮 27/30 的关系**：第九轮的 4 个 P1 全清（+1），T1+ 和 C-031 落地（+1），但 C-031 的 prompt/model 字段/分母三个新缺口（−1），净 +1 ⇒ 28/30。

---

## 1. 变化与交付

### 1.1 提交与 tag

| commit | 时间 | 内容 |
|---|---|---|
| `032c32c` | 10-25 22:01 | W5c-6b：第九轮 4 个 P1 清零 + T1+ 地板 + R42–R46 |
| `ca851a5` | 10-26 21:29 | W5c-6c：第二模型 C-031（deepseek-v4-pro）+ 分母口径 bug + R47–R49 |
| `38b26f1` | 10-26 21:29 | 清理：删掉过程备份 `_bak_c031_pre_msr.json`，正式 artifact 唯一 |

**tag**：`v1.0-l3-v6c`（当前考卷）；C-029（glm-5.3-flash）为 headline；C-031（deepseek-v4-pro）为 supporting（R48）。

### 1.2 新增/修改的关键文件

| 文件 | 作用 |
|---|---|
| `feagpt_repro/reports/baseline_scorecard_L3_v6c_dsv4pro.json` | C-031 官方成绩单（deepseek-v4-pro；55 per_task + MSR + value_added 双尺度） |
| `feagpt_repro/reports/bootstrap_ci_L3_v6c_dsv4pro.json` | C-031 CI（TSR [64,96]、MSR [77.3,100]） |
| `feagpt_repro/candidates_l3_v6c_dsv4pro/` | 55 条 deepseek 候选（0 missing；1 unresolved） |
| `feagpt_repro/reports/trivial_baselines_L3_v6c.json` | T1+ family / oracle / 字段命中率 / 缺口分布 |
| `feagpt_repro/reports/baseline_scorecard_L3_v6c.json` | C-029 成绩单更新（T1+、字段级、MSR 别名） |
| `feagpt_repro/reports/negative_controls_44.json` | 负控 44/44（NC-30..42） |
| `feagpt_repro/reports/check_claims.json` | 23 active / 35 artifacts / 36 semantic 全过 |
| `feagpt_repro/reports/diagnostics/bridge_w5c_table.md` | bridge 四格 + dev 口径修正 |
| `feagpt_repro/reports/diagnostics/score_v6c_t1plus.log` / `t1plus_v6c_run.log` | T1+ 复现日志 |
| `FEM-Bench-Aero/RUBRIC.md` | v4.7：R42–R49、§7.5 治理闸、§7.6 跨模型对比 |
| `FEM-Bench-Aero/CLAIMS.md` | C-029 字段级/ T1+；C-031；C-019 44/44；R47–R49 |

### 1.3 C-031 官方数字

| 指标 | C-031（deepseek-v4-pro） | C-029（glm-5.3-flash） |
|---|---:|---:|
| exam TSR | **20/25 = 80.0%** | 23/25 = 92.0% |
| exam SFR | 20/25 = 80.0% | 20/22 = 90.9% |
| exam MSR | **20/22 = 90.9%** | 19/22 = 86.4% |
| dev TSR | 22/30 = 73.3% | 23/30 = 76.7% |
| dev MSR | 22/28 = 78.6% | 19/29 = 65.5% |
| full MSR | 42/50 = 84.0% | 38/51 = 74.5% |
| boundary | 6/6 = 100% | 6/6 = 100% |
| extrapolation | **9/13 = 69.2%** | 11/13 = 84.6% |
| interpolation | **5/6 = 83.3%** | 6/6 = 100% |
| CI95 TSR | [64.0, 96.0] | [80.0, 100.0] |
| FPR | **4/4 = 100%** | 0/4 = 0% |
| turns | 2:52 / 3:3 | 1:4 / 2:48 / 3:3 |
| first pass | **0/55** | 4/55 |
| unresolved | **1** | 0 |
| solver | 0 | 4（1 exam + 3 dev） |
| value_added 任务级 | 80.0%（Δ80pp PASS） | 92.0%（Δ92pp PASS） |
| value_added 字段级 | **87.42%（Δ+1.5pp BELOW）** | **99.34%（Δ+13.4pp PASS）** |
| verdict_split | **任务 PASS / 字段 BELOW** | 两尺度 PASS |

### 1.4 覆盖与可复现

- C-031：55/55 文件、`candidates_missing=[]`、`partial_candidates=false`、`n_unresolved=1`。
- `provenance` = `tasks_path: reports/papers/tasks_v6c.jsonl`，`tasks_sha256: 9c1faa3a…`（与 C-029 逐字节相同），`candidates_dir: candidates_l3_v6c_dsv4pro`，`model: deepseek-v4-pro`，`n_candidates: 55`。
- `check_claims`：23 active / 35 artifacts / 36 semantic，`n_fail=0`、`all_ok=True`。
- `negative_controls_44`：44/44，含 NC-38..42（headline 唯一、dev 投影、T1+、分母闭合、第二模型不抢 headline、双尺度分裂）。
- `compare_scorecards.py`：C-029 vs C-031 同卷（同 sha）**不是 R30 的跨卷问题**，但两者是不同模型；C-031 标 supporting，不得与 C-029 做“谁更强”的 headline。

---

## 2. 已验证的改进（credit）

| 改进 | 实测 |
|---|---|
| **第九轮 P1-1：headline 文档** | README 两处改 C-029；C-021/C-025/C-026 历史化/诊断化；S-29：唯一 headline = C-029；NC-38 反向 |
| **P1-2：dev 25/30** | 改成“23/30 实测 + paper-clean 投影 25/30 + 5 条模型侧失败仍在”；S-30；不再把投影当实测 |
| **P1-3：T1+** | `T1plus_family`（族级众数，不读输入）+ `T1plus_family_oracle`（上界，只报不判）；exam 0/25、train 3/13、字段命中 **85.93%**、缺口 min 1/中位 3/max 5；S-32/NC-39 |
| **P1-4：key** | fallback 已删；W5B_PLAN §6.0b 纠正“轮换 ⇒ endpoint 变 ⇒ provenance 重签”的两处错误：endpoint 是硬编码常量、provenance 不含 key/endpoint；同应用轮换未验证，R46 |
| **MSR 别名** | `dev_msr_pct` 65.5、`full_msr_excl_solver` ≡ `msr_excl_solver` 38/47；九字段全非空；S-31 |
| **负控/自检** | 39 → **44/44**；`check_claims` **23/35/36**；S-33（分母闭合）、S-34（第二模型不抢 headline）、S-35（双尺度分裂） |
| **C-031 第二模型** | `deepseek-v4-pro`；55/55；9 min 生成；41 min MSR；同卷 sha 硬证据；provenance 记 model |
| **跨模型归因** | 两模型 spec_pass 都是 20/25；2 条 exam spec_fail 同题同字段；dev 6/7 同题同字段；唯一差异 = 澄清/编造 |
| **分母 bug** | 字段级命中率原 `if n_fields_gated` 把 fabricated 静默排除；改为按 category 显式分流 ⇒ C-029 99.34% 不变、C-031 87.42%；三档 85.93/87.42/99.34 |
| **R47–R49** | 分母显式落盘 + 第二模型不择优 + 双尺度分裂必须标 `verdict_split`；NC-40/41/42 |
| **清理** | 删除 `_bak_c031_pre_msr.json`，正式 artifact 唯一 |

---

## 3. 剩余问题

### 3.1 P0：prompt 的“未提长桁→0”与题面 `expected_clarifications` 自相矛盾；C-031 的 80% 是“1 条 prompt 授权 + 2 条模型未问”的混合下界

- C-031 在 3 条 exam 澄清题上全部 `fabricated`：`barrel_d1600_frm3`（`n_frames`）、`naca4412_wingbox`（`n_ribs`）、`stiffened_panel_600x600_str3`（`n_stringers`）；另有 1 条 dev 编造（`open_hole_panel_400x200_d20`），FPR **4/4 = 100%**。
- 其中 `stiffened_panel_600x600_str3` 的 `n_stringers=0` 是 SYS prompt 明确授权的：
  > “未提长桁→长桁数=0”
  而题面把它列为 `expected_clarifications`（期望模型问）。**prompt 规则与题面直接打架**：glm 没被诱导（3/3 clarify_ok），deepseek 被诱导（3/3 fabricated）。
- 后果：
  - 两模型 `spec_pass` 都是 **20/25**；92.0% vs 80.0% 的 12pp **全部来自这 3 条**；
  - C-031 的 TSR 80%、SFR 20/25、FPR 100% 都含这个 prompt 缺陷；
  - **C-031 的 80% 不能当作 deepseek 的能力**；也不能据此说“glm 比 deepseek 强 12pp”。
- **修法**：SYS prompt 的默认规则必须让位于题面的 `expected_clarifications`——用户没给、且题面标记为 expected clarification 的字段，必须问，不得填 0；或把 `expected_clarifications` 直接传给生成器，让模型知道“这些字段该问”。
- **验收**：修 prompt 后重生成 **两个模型**（C-032/C-033）；C-031 的 3 条 fabricated 必须变 clarify_ok；两模型的 spec_pass/TSR 才能做干净对比。

### 3.2 P1：C-031 成绩单顶层 `model` 写错（glm-5.3-flash）

- `baseline_scorecard_L3_v6c_dsv4pro.json` 顶层 `model = "glm-5.3-flash"`；`provenance.model = "deepseek-v4-pro"`；C-031 claim 也说 deepseek。
- **这是跨模型 artifact 的模型标签错误**：读者只读 `model` 会以为第二模型还是 glm；`check_claims` 的 36 项语义没有一条核对“顶层 model == provenance.model”。
- **修法**：`score_baseline.py` 的顶层 `model` 从 `--model`/provenance 取，不用默认值；重生成/修正 C-031；加 **S-36：顶层 model == provenance.model**；**NC-43：注入错误 model 必须 FAIL**。

### 3.3 P1：`n_clarify_excluded` 把“编造澄清”和“未收敛”混在一起

- C-031：`n_denominator=50`、`n_clarify_excluded=5`；但 5 = **4 条 clarify（其中 3 条 fabricated + 1 条 dev fabricated）+ 1 条 unresolved**（`cfrp090s` 3 轮无输出）。
- C-029：`n_denominator=51`、`n_clarify_excluded=4`（4 条纯 clarify，0 unresolved）。
- **两个 5/4 不是同一类**：C-031 的 5 含 1 条 no_output；`n_unresolved` 在 `msr_section` 里是 `null`（顶层 `n_unresolved=1`）。
- **修法**：MSR 分母拆成 `n_clarify_excluded` + `n_unresolved_excluded` + `n_solver_excluded` + `n_counted`，四者加和闭合；加 S-37/NC-44。R47 已经要求“分母显式落盘且加和闭合”，但字段名还没拆开。

### 3.4 P2：C-031 的 first-pass 0/55、turns 2:52、unresolved 1

- C-031 一次通过 **0/55**；2 轮 52；3 轮 3；1 条未收敛。C-029 是 1:4 / 2:48 / 3:3，0 未收敛。
- 说明 deepseek 的 raw first-pass 更依赖 schema 修复循环；**第二模型必须用同样的 ≤3 轮预算**，否则不可比。C-031 的 80% 是“2 轮修复后”的成绩，不是 raw 能力。
- **不是缺陷，是可比性约束**；建议在 C-031 claim/INDEX 里把 first-pass/turns 与 TSR 并列。

### 3.5 P2：C-031 的 80% vs C-029 的 92%——12pp 全部是 3 条澄清题

- 两模型 `spec_pass` 都是 20/25；C-029 的 23 = 20 spec + 3 clarify_ok；C-031 的 20 = 20 spec + 0 clarify（3 fabricated）。
- 三栏：boundary 6/6 相同；extrapolation 11/13 vs 9/13（差 2 条 = 2 条 fabricated? 或 1 fabricated + 1 spec_fail）；interpolation 6/6 vs 5/6（差 1 条 = fabricated）。
- **结论：这 12pp 不是建模能力差异，是缺失信息处理差异**；C-031 的 `spec_pass` 与 C-029 持平，说明其规格跟随能力并不弱；弱的是“该问不问、直接编”。
- **禁止**写“glm 比 deepseek 强 12pp”；只能写“在未修 prompt 的同一 harness 下，deepseek 在澄清题上 3/3 编造，glm 3/3 提问”。

### 3.6 P2：MSR 与 TSR 排名相反，分母不同，不得互相替代

- C-031 exam MSR **20/22 = 90.9%** > C-029 **19/22 = 86.4%**，但 TSR **80.0% < 92.0%**。
- 原因：MSR 分母 22 排除了 3 条 clarify（C-031 的 3 条 fabricated 恰好全在其中）；C-029 的 3 条 clarify 是合法澄清，也被排除；C-029 的 exam MSR 还含 1 条 solver；C-031 0 solver。
- full 分母 50 ≠ 51（C-031 多排 1 条 no_output）；dev 分母 28 ≠ 29。
- **结论：TSR 与 MSR 分母不同（25 vs 22），排名可以相反；full MSR 不可跨模型直减。** 这一条 C-031 claim 已写明，credit；但对外摘要必须并列，不能只引 MSR 90.9%。

### 3.7 P2：T1+ 的“0/25”不是地板太弱，而是全或无判据的必然

- T1+ family：exam **0/25**、train 3/13、字段命中 **85.93%**、缺口 min 1 / 中位 3 / max 5；族内 oracle 也是 **0/25**。
- 解释：`spec_fidelity` 全或无 × 族内几何参数逐条唯一 ⇒ 最强“不读输入”策略能命中 86% 字段、最好一条只差 1 个字段，但 25 条无一全对；oracle 也 0/25。
- **value_added 双尺度**：C-029 任务级 92pp、字段级 99.34%（+13.4）；C-031 任务级 80pp、字段级 87.42%（+1.5 BELOW）。三档 85.93/87.42/99.34 证明字段级有区分度。
- **这是本轮最好的方法论改进之一**；建议 W5d 继续用双尺度，不要把任务级 0 地板当“模型强”的唯一证据。

### 3.8 P2：README 日期仍写 2026-10-25

- README “当前状态 · 2026-10-25”；当前已是 2026-10-26，且 C-031 已落地。日期不改变数字，但会让读者以为 C-031 是“昨天之前”的产物。
- 建议 W5c-6e 顺手改成 2026-10-26，并把 C-031 的 supporting 状态写进“当前状态”行。

### 3.9 P2：key 轮换仍未执行

- W5c-6b R46 已纠正成本判断：endpoint 是 `gen_candidates.js:10` 的硬编码常量、provenance 不含 key/endpoint ⇒ **轮换不需要重签 artifact**；但“同应用轮换是否可行”仍未验证（未做轮换操作）。
- 建议：D5-b 做一次“只换 key、endpoint 不变”的验证；可行则轮换；不可行则记录接受决策（决策人/日期）。

### 3.10 P2：旧负控 31/37/39/41 与当前 44 并存

- `negative_controls_31/37/39/41/44.json` 五份并存；C-019/INDEX/README 都指向 44；旧四份是历史。建议在 INDEX 标“历史”，或移到 `reports/archive/`。

### 3.11 P2：C-031 的 SFR 20/25 与 C-029 的 20/22 不可直减

- C-031 SFR 分母 25（3 条 fabricated 计入并失败）；C-029 分母 22（3 条合法澄清排除）；两者都是 20 pass，但百分比 80.0% vs 90.9% 不可直接说“C-031 差 10.9pp”。
- 建议在 C-031 claim/INDEX 明写“SFR 分母不同不可直减”；C-031 claim 已写，credit；摘要也要。

### 3.12 不是问题的部分（避免过度纠偏）

- C-029 的 92.0/90.9/86.4、C-031 的 80.0/80.0/90.9、三栏、44/44、23/35/36、T1+、字段级三档、R47–R49、同卷 sha、C-031 supporting——都是真的，不需要重做。
- C-031 的 2 条 exam spec_fail 与 C-029 同题同字段；dev 6/7 同题同字段；这是**强归因证据**，不是缺陷。
- 92.0% 仍是 C-029 的 headline；C-031 的 80% 不改变 C-029 的地位。

---

## 4. C-031 准入评估

### 4.1 Go / No-Go

| 条件 | 现状 | 结论 |
|---|---|---|
| 同卷 sha 一致 | `9c1faa3a…`，逐字节相同 | ✅ |
| 55/55 覆盖 | `n_unresolved=1`，文件 55 | ✅（覆盖≠全合法） |
| 第二模型不抢 headline | C-031 supporting（R48/S-34） | ✅ |
| 跨模型归因 | spec_pass 20/20；2 条 spec_fail 同题；dev 6/7 同题 | ✅ |
| 字段级双尺度 | 87.42/+1.5 BELOW；`verdict_split` | ✅ |
| MSR 分母说明 | 22/25、50/51 不可直减 | ✅ |
| prompt 干净 | **“未提长桁→0”与 expected_clarifications 冲突** | ❌ P0 |
| 顶层 model 正确 | **写 glm-5.3-flash，provenance 是 deepseek** | ❌ P1 |
| 分母构成可拆 | **n_clarify_excluded=5 混 4 编造 + 1 未收敛** | ❌ P1 |
| first-pass/turns 可比 | 0/55、2:52/3:3、1 unresolved | ⚠️ P2 |

**判定：C-031 可以作为“第二模型 supporting / 归因证据”引用，但不能作为“deepseek 的能力”或“glm vs deepseek 排名”引用。** 修 prompt + model 字段 + 分母口径后，重生成两模型（C-032/C-033），才是 W5d 的干净跨模型对比。

### 4.2 C-031 能说什么 / 不能说什么

| 可以说 | 不能说 |
|---|---|
| 两模型 spec_pass 都是 20/25；2 条 spec_fail 同题同字段；dev 6/7 同题 | “glm 比 deepseek 强 12pp” |
| C-031 在 3 条澄清题上 3/3 编造；glm 3/3 提问 | “deepseek 建模能力差” |
| C-031 的 80% 是“未修 prompt”下的下界 | “deepseek 的 TSR 是 80%” |
| C-031 字段级 87.42%（+1.5 BELOW） | “C-031 有显著增量” |
| C-031 exam MSR 90.9% > C-029 86.4%，但分母不同、TSR 相反 | “C-031 全链更强” |
| C-031 0 solver，C-029 4 solver；full 分母 50≠51 | “C-031 更省算力/更稳” |
| C-031 supporting，不抢 headline | “C-031 是第二官方 headline” |

---

## 5. 下一步任务执行建议

### 5.1 任务表

| ID | 优先级 | 做什么 | 验收 | 证据 |
|---|---|---|---|---|
| **W5c-6d** | **P0** | **修 prompt 的“未提长桁→0”**：让 `expected_clarifications` 优先；缺失字段该问就问；或把 expected_clarifications 传给生成器 | C-031 的 3 条 fabricated → clarify_ok；两模型同 prompt | `gen_candidates_v2.js`；NC-43 |
| **W5c-6e** | **P0** | **重生成两模型（C-032 glm / C-033 dsv4pro）** + 重打分 + CI + 双尺度 | 两模型同卷同 prompt 同 ≤3 轮；C-032 为 headline；C-033 supporting | 新 scorecard/CI；C-032/C-033 |
| **W5c-6f** | **P1** | **C-031 model 字段**：顶层 `model` 从 provenance/--model 取；重生成/修正；S-36/NC-43 | `model=deepseek-v4-pro`；无 glm | `score_baseline.py`；C-031 |
| **W5c-6g** | **P1** | **分母拆分**：`n_clarify_excluded` / `n_unresolved_excluded` / `n_solver_excluded` / `n_counted` 四项闭合；S-37/NC-44 | C-031 的 5 拆成 4+1；C-029 的 4+0 | `msr_l3.py`；C-031 |
| **W5c-6h** | **P2** | **first-pass/turns 并列**：C-031 0/55、2:52、1 unresolved；C-029 4/55、1:4/2:48/3:3 | 第二模型报告含 raw first-pass | C-031 claim/INDEX |
| **W5d** | **P1** | **干净的跨模型榜单/协议**：C-032/C-033 同 harness；双尺度；失败分层；第三方复现 | 两模型同卷同 prompt；排名有 CI；不混分母 | 后续 |
| **v1.1** | **P2** | **新几何 6–10 条**：扩 exam 精度；n≥30；族级 CI 有意义 | 新几何 truth + 双求解器 + 闸 | 后续 |
| **key D5-b** | **P2** | 只换 key、endpoint 不变的可行性验证；可行则轮换；不可行记录决策 | 有结论/日期/决策人 | W5B_PLAN §6.0b |

### 5.2 顺序建议

```text
W5c-6d 修 prompt ──► W5c-6e 重生成 glm/dsv4pro（C-032/C-033）
                              │
                              ├──► W5c-6f model 字段 / 6g 分母拆分（可并行）
                              │
                              ▼
                          W5d 干净跨模型榜单/协议
                              │
                              ▼
                          v1.1 新几何
```

**为什么先修 prompt 再重生成**：C-031 的 80% 是 prompt 缺陷压低的下界；不修 prompt，重生成只是把同一个缺陷再跑一遍。**修 prompt + 重生成两模型**才能把“澄清能力”和“建模能力”分开；这是 W5d 的前置。

### 5.3 成本估计

- W5c-6d：0.2 天（prompt 改动 + 1 条/族冒烟）。
- W5c-6e：两模型各 10–30 分钟生成 + 40 分钟 MSR + 几分 CI；约半天等。
- W5c-6f/6g：0.5 天（脚本 + 重跑 + 语义检查）。
- W5d：1–2 天。
- **总计约 2–3 天**到干净的跨模型榜单。

---

## 6. 防跑偏机制（R50–R53 建议）

> R1–R49 保留；以下为第十轮建议新增，待拍板后写入 RUBRIC。

| 红线 | 内容 | 触发点 |
|---|---|---|
| **R50** | **prompt 默认规则必须让位于题面 `expected_clarifications`**：题面标记为“该问”的字段，prompt 不得授权填 0/默认值；生成器应读 `expected_clarifications` | W5c-6d；S-36；NC-43 |
| **R51** | **成绩单顶层 `model` 必须等于 provenance.model**：跨模型 artifact 的模型标签不得用默认值 | W5c-6f；S-37；NC-44 |
| **R52** | **分母四类必须拆开并闭合**：`n_counted` + `n_clarify_excluded` + `n_unresolved_excluded` + `n_solver_excluded` = `n_exam`；`n_clarify_excluded` 不得混入 no_output | W5c-6g；S-38；NC-45 |
| **R53** | **第二模型只作 supporting，不得择优**：C-031 的 80% 是 prompt-defect lower bound；修 prompt 前不得写“模型排名”；W5d 才谈榜单 | R48 延续；S-34 |

**新增语义检查（S-36..S-38）建议：**

| ID | 检查 | 期望 |
|---|---|---|
| S-36 | C-031 顶层 `model` | `deepseek-v4-pro` == `provenance.model` |
| S-37 | MSR 分母四类 | 加和 = `n_exam`；C-031 5 = 4 clarify + 1 unresolved |
| S-38 | C-031 prompt-defect 标注 | 80% 必须与“3 条 fabricated、prompt 未修”同现 |

---

## 7. 评分卡

> **第九轮 27/30 → 第十轮 28/30**：4 个 P1 清 + T1+ + C-031 归因（+2），C-031 prompt/model 字段/分母（−1）。

| # | 维度 | 第八轮 | 第九轮 | 第十轮 | 依据 |
|---|---|---:|---:|---:|---|
| 1 | 目标一致性 | 3 | 3 | **3** | 评测基础设施主轴不变；W5c-6b/6c 按计划 |
| 2 | 任务有效性 | 2 | 3 | **3** | exam R32/R41 0；dev 4 R41 已知；prompt 澄清冲突是 harness，不是卷子 |
| 3 | 判分有效性 | 2 | 3 | **3** | R47–R49；44/44；双尺度；C-031 model 字段是 artifact，不是判分 |
| 4 | 证据等级 | 2 | 3 | **2** | C-031 顶层 model 错、n_clarify 混类；其余 23/35/36 强 |
| 5 | 可复现性 | 3 | 3 | **3** | 同卷 sha；C-031 命令；T1+ 日志；44/44 |
| 6 | 版本治理 | 2 | 2 | **3** | C-029 headline；C-031 supporting；README/C-021/C-025/C-026 已改；README 日期 10-25 是 P2 |
| 7 | 文档真实性 | 2 | 2 | **3** | C-031 claim 主动披露 80% 是 prompt 下界、字段级 BELOW、MSR 分母反转；credit |
| 8 | 统计有效性 | 2 | 2 | **2** | n=25、CI；T1+ 双尺度；族 n<10；C-031 CI [64,96] 宽 |
| 9 | 范围纪律 | 3 | 3 | **3** | 第二模型 supporting；不抢 headline；不混分母 |
| 10 | 计划执行 | 3 | 3 | **3** | 4 个 P1 清；T1+；44/44；23/35/36 |
| **总分** | | **24/30** | **27/30** | **28/30** | 基础设施 A；科学有效性 B+/A−；3 个 P1 收口后进 W5d |

**一句话**：**这一轮把“第二模型”从分数变成了归因工具——真正的发现是“两模型建模能力相同，差异在澄清”，而我们的 prompt 把 deepseek 诱导成编造。** 修 prompt、修 model 字段、拆分母，再谈榜单。

---

## 8. 待拍板

| # | 决策 | 选项 | 建议 |
|---|---|---|---|
| **D1** | **C-029 / C-031 定位** | (a) C-029 headline、C-031 supporting；(b) 两模型并列 headline | **(a)**；C-031 的 80% 是 prompt 下界，不能并列 |
| **D2** | **先修 prompt 重跑，还是先补 C-031 口径** | (a) 先修 prompt + 重生成两模型（C-032/C-033）；(b) 先补 model 字段/分母，再重跑 | **(a)**；prompt 是 P0，model/分母可并行 |
| **D3** | **C-031 model 字段** | (a) 现在修 + S-36/NC-43；(b) 等下轮 | **(a)**；跨模型 artifact 的模型标签不能再错 |
| **D4** | **分母拆分** | (a) 现在拆 `n_unresolved_excluded`；(b) 保持 `n_clarify_excluded=5` | **(a)**；C-031 的 5 与 C-029 的 4 不同类 |
| **D5** | **W5d 时机** | (a) C-032/C-033 之后；(b) 现在用 C-031 做榜单 | **(a)**；C-031 的 prompt 缺陷未修 |
| **D6** | **key 轮换** | (a) 验证“只换 key、endpoint 不变”，可行则轮换；(b) 接受现状 | **(a)**；W5c-6b 已证明不需要重签 artifact |

---

## 附录 A　证据索引与复现命令

### A.1 官方 artifact

| 文件 | 用途 |
|---|---|
| `feagpt_repro/reports/baseline_scorecard_L3_v6c.json` | C-029（glm）headline |
| `feagpt_repro/reports/baseline_scorecard_L3_v6c_dsv4pro.json` | C-031（deepseek）supporting；**顶层 model 错** |
| `feagpt_repro/reports/bootstrap_ci_L3_v6c*.json` | 两模型 CI |
| `feagpt_repro/reports/trivial_baselines_L3_v6c.json` | T1+ family / oracle / 字段命中 |
| `feagpt_repro/reports/negative_controls_44.json` | 44/44 |
| `feagpt_repro/reports/check_claims.json` | 23/35/36 |
| `feagpt_repro/reports/papers/tasks_v6c.jsonl` | 考卷 sha `9c1faa3a…` |

### A.2 复现命令

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# C-031 生成（prompt 修复前）
node gen_candidates_v2.js --tasks reports/papers/tasks_v6c.jsonl --levels L3 \
  --out candidates_l3_v6c_dsv4pro --limit 55 --model deepseek-v4-pro --max-turns 3

# C-031 打分 + MSR + CI
"$PY" score_baseline.py --candidates candidates_l3_v6c_dsv4pro \
  --tasks reports/papers/tasks_v6c.jsonl \
  --report reports/baseline_scorecard_L3_v6c_dsv4pro.json \
  --trivial reports/trivial_baselines_L3_v6c.json
"$PY" msr_l3.py --candidates candidates_l3_v6c_dsv4pro \
  --tasks reports/papers/tasks_v6c.jsonl \
  --report reports/baseline_scorecard_L3_v6c_dsv4pro.json
"$PY" bootstrap_ci.py --scorecard reports/baseline_scorecard_L3_v6c_dsv4pro.json \
  --out reports/bootstrap_ci_L3_v6c_dsv4pro.json

# 自检
"$PY" check_claims.py
"$PY" negative_controls.py
```

---

## 附录 B　C-031 vs C-029

| 指标 | C-029 glm | C-031 dsv4pro | 差 | 可比性 |
|---|---:|---:|---:|---|
| exam TSR | 23/25 92.0% | 20/25 80.0% | −12pp | 同卷；差 = 3 澄清 |
| exam SFR | 20/22 90.9% | 20/25 80.0% | −10.9pp | **分母不同**（22 vs 25） |
| exam MSR | 19/22 86.4% | 20/22 90.9% | +4.5pp | 分母同 22，但 C-031 的 3 fabricated 被排除 |
| dev TSR | 23/30 76.7% | 22/30 73.3% | −3.4pp | 同 30 |
| dev MSR | 19/29 65.5% | 22/28 78.6% | +13.1pp | **分母不同**（29 vs 28） |
| full MSR | 38/51 74.5% | 42/50 84.0% | +9.5pp | **分母不同**（51 vs 50），不可直减 |
| boundary | 6/6 | 6/6 | 0 | 同 |
| extrapolation | 11/13 84.6% | 9/13 69.2% | −15.4pp | 同 13 |
| interpolation | 6/6 100% | 5/6 83.3% | −16.7pp | 同 6 |
| FPR | 0/4 | 4/4 100% | +100pp | 4 条 clarify；C-031 3 exam + 1 dev |
| first pass | 4/55 | 0/55 | −4 | 同 55 |
| unresolved | 0 | 1 | +1 | 同 55 |
| solver | 4 | 0 | −4 | 候选相关 |
| 字段级 value_added | 99.34% (+13.4) | 87.42% (+1.5 BELOW) | −11.9pp | 同地板 85.93 |
| 任务级 value_added | 92.0% | 80.0% | −12pp | 同 25 |

### B.1 C-031 的 3 条 exam fabricated

| task_id | 缺失字段 | 模型输出 | 题面 | 性质 |
|---|---|---|---|---|
| `L3_fuselage_barrel_d1600_l1600_str8_frm3` | `n_frames` | 填 0 | expected clarify | 模型侧（prompt 未授权？） |
| `L3_naca4412_wingbox` | `n_ribs` | 填 2 | expected clarify | 模型侧 |
| `L3_stiffened_panel_600x600_str3` | `n_stringers` | 填 0 | expected clarify | **prompt“未提长桁→0”直接授权** |

**⇒ 3 条里至少 1 条是 prompt 直接授权，另 2 条是模型未问；两者都要修。**

---

## 附录 C　第九轮 P1 逐项判定

| 第九轮 P1 | 第十轮状态 | 证据 |
|---|---|---|
| P1-1 headline 文档漂移 | ✅ | README/C-021/C-025/C-026 改 C-029；S-29；唯一 headline |
| P1-2 dev 25/30 投影 | ✅ | 23/30 实测 + paper-clean 25/30 + 5 条模型失败；S-30 |
| P1-3 T1+ null | ✅ | T1plus_family 0/25、字段 85.93%、oracle 0/25；S-32 |
| P1-4 key 未轮换 | ⚠️ 部分 | fallback 已删；R46 纠正成本；轮换未执行 |
| MSR 别名 null | ✅ | S-31；full alias 38/47；dev_msr_pct 65.5 |
| 旧计数 | ✅ | 23/35/36；W5B 32 |
| W5b-5 第二模型 | ✅ | C-031 55/55；9 min；41 min |
| 第二模型干净度 | ❌ | prompt 冲突 + model 字段 + 分母混类 |

---

## 附录 D　文档/口径漂移清单

| # | 位置 | 现文 | 应为 |
|---|---|---|---|
| 1 | `baseline_scorecard_L3_v6c_dsv4pro.json` | `model = glm-5.3-flash` | `deepseek-v4-pro` |
| 2 | C-031 `msr_section` | `n_clarify_excluded=5` | `4 clarify + 1 unresolved` 分开 |
| 3 | `msr_section.n_unresolved` | `null` | `1` |
| 4 | `README.md` 当前状态 | 2026-10-25 | 2026-10-26；C-031 supporting |
| 5 | C-031 claim | 80% 已标 prompt 下界（credit） | 再加“顶层 model 字段错”提示？或修完删除 |
| 6 | `reports/` 旧负控 | 31/37/39/41 与 44 并存 | INDEX 标历史或归档 |
| 7 | C-031 `first_pass` | 0/55（claim 未列） | 与 TSR 并列 |
| 8 | C-031 `SFR 20/25` | 与 C-029 20/22 并列 | 明写分母不同 |

---

> **本轮只读核对；除本文件外未改动任何项目文件。**
> 下一轮复评入口：C-032/C-033（修 prompt 后重生成两模型）+ C-031 model 字段/分母修复；W5d 的干净跨模型榜单在 C-032/C-033 之后。
