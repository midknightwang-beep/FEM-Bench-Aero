# FEM-Bench-Aero 第十一轮复评与执行纠偏（C-032/C-033 后）

> **复评日期**：2026-10-27（第十一轮）
> **复评对象**：W5c-6d/6f/6g/6h（`cb56503`）——修 prompt 后双模型同 harness 重跑（C-032 glm / C-033 dsv4pro）+ MSR 条件口径 R54
> **复评方式**：只读核对 + 官方 artifact 交叉检查（C-029..C-033 成绩单、prompt sha、T1+、负控 48、`check_claims` 41 语义、CLAIMS/README/INDEX/RUBRIC）；**除本文件外未改动任何项目文件**
> **结论先行**：
> **第十轮的 3 个 P1 全部修好了，而且修得对：** 顶层 `model` 改为从候选实测（C-031 现在是 deepseek，不再误写 glm）；`n_clarify_excluded` 拆成 clarify / unresolved / solver / counted 四类并闭合；prompt 删掉了“未提长桁→0”的盲填授权，加数量铁律，**没有把 `expected_clarifications` 注入生成器（避免泄题）**。
> **结果：C-032（glm）exam 23/25 (92.0%) 成为新 headline；C-033（deepseek）22/25 (88.0%)，比 C-031 的 80.0% 回收 +2**（正是 C-031 编造的两条）；两模型 `spec_pass` 仍都是 20/25，2×2 = both 22 / only_a 1 / only_b 0 / neither 2；C-033 是首例 R53 合规的跨模型对比。
> **但“收口”还有两个真实副作用：** ①**C-032 的 dev 22/30，比 C-029 的 23/30 少 1**（exam 同为 23/25；prompt 修的是隐患，但 dev 有 1 条反向变化，需定位）；②**C-033 仍剩 1 条编造 + 1 条问错字段**（FPR 1/4 = 25%），prompt 修复回收了 2 条但没清零。另有 C-033 字段级 **90.94%（Δ+5.0pp BELOW）**、C-033 exam MSR 95.2% > C-032 90.9% 但 TSR 88 < 92（R54 条件分母）、C-033 1 条 unresolved——这些都是已披露的 P2，不阻塞 W5d。
> **判定：C-032 作官方 headline，C-033 作 supporting；项目已具备开 W5d（干净跨模型榜单/协议/第三方复现）的条件。C-033 剩余的 1 条编造 + 1 条问错字段作为已知限制，留 prompt v3；C-032 的 dev 22 vs 23 需先定位是哪一条。**

---

## 目录

- [0. 复评摘要](#0-复评摘要)
- [1. 变化与交付](#1-变化与交付)
- [2. 已验证的改进（credit）](#2-已验证的改进credit)
- [3. 剩余问题](#3-剩余问题)
- [4. W5d 准入评估](#4-w5d-准入评估)
- [5. 下一步任务执行建议](#5-下一步任务执行建议)
- [6. 防跑偏机制（R55–R57 建议）](#6-防跑偏机制r55r57-建议)
- [7. 评分卡](#7-评分卡)
- [8. 待拍板](#8-待拍板)
- [附录 A　证据索引与复现命令](#附录-a证据索引与复现命令)
- [附录 B　C-032/C-033 vs C-029/C-031](#附录-bc-032c-033-vs-c-029c-031)
- [附录 C　第十轮 P1 逐项判定](#附录-c第十轮-p1-逐项判定)
- [附录 D　文档/口径漂移清单](#附录-d文档口径漂移清单)

---

## 0. 复评摘要

### 0.1 三句话结论

1. **第十轮 3 个 P1 全修了，而且修法正确。** `model` 从候选实测（S-36）；分母四类拆分 + 两层闭合（S-37）；prompt 删盲填授权、加数量铁律，**没有注入 expected_clarifications**（S-38，避免泄题）。负控 44→**48/48**；`check_claims` 23/35/36→**25/43/41**；RUBRIC v4.9。
2. **C-032 成为新 headline：exam 23/25 (92.0%)，与 C-029 逐题类别完全相同**；C-033 22/25 (88.0%)，比 C-031 的 80.0% **回收 +2**（正是 C-031 编造的两条）；2×2 = **both 22 / only_a 1 / only_b 0 / neither 2**；两模型 `spec_pass` 仍都 20/25。**跨模型差距从 3 条缩到 1 条，且那 1 条是 C-032 更好。**
3. **两个真实副作用：** C-032 的 **dev 22/30**（C-029 是 23/30，exam 同为 23/25；需定位哪条 dev 被 prompt 改反）；C-033 仍剩 **1 条编造 + 1 条问错字段**（FPR 25%）、**1 条 unresolved**、字段级 **+5.0pp BELOW**。这些是 P2，不阻塞 W5d，但必须写进限制。

### 0.2 执行总评

| 工作块 | 评分 | 一句话判断 |
|---|---|---|
| W5c-6d：prompt 修复 | **A** | 删“未提长桁→0”+ 数量铁律；不注入 expected_clarifications；S-38/S-39 |
| W5c-6f：model 字段 | **A** | 顶层 model 从候选实测；C-031/C-032/C-033 全对；S-36 |
| W5c-6g：分母拆分 | **A** | clarify/unresolved/solver/counted 四类；两层闭合；S-37 |
| W5c-6h：first-pass/turns | **A−** | C-032 1:3/2:50/3:2；C-033 1:2/2:48/3:5；C-032 dev 1 条反向 |
| C-032/C-033 跨模型 | **A−** | C-032 92.0 headline；C-033 88.0 supporting；2×2；字段 99.34 vs 90.94；C-033 剩 1 编造 + 1 问错 |
| **总体** | **A / 29/30** | 基础设施 A；科学有效性 A−；**W5d 已具备条件** |

> **和第十轮 28/30 的关系**：3 个 P1 全清（+1），C-032/C-033 跨模型（+0.5），C-032 dev 1 条反向 + C-033 剩余 2 条（−0.5），净 +1 ⇒ 29/30。

---

## 1. 变化与交付

### 1.1 提交与 tag

| commit | 时间 | 内容 |
|---|---|---|
| `cb56503` | 10-27 00:17 | W5c-6d/6f/6g/6h：修 prompt 后双模型同 harness 重跑（C-032/C-033）+ MSR 条件口径 R54 |

**tag**：`v1.0-l3-v6c`（当前考卷，未变）；C-032（glm-5.3-flash）headline；C-033（deepseek-v4-pro）supporting；C-029/C-031 为旧 prompt 历史。

### 1.2 新增/修改的关键文件

| 文件 | 作用 |
|---|---|
| `feagpt_repro/reports/baseline_scorecard_L3_v6c_p2.json` | C-032 官方成绩单（glm prompt-v2） |
| `feagpt_repro/reports/baseline_scorecard_L3_v6c_ds_p2.json` | C-033 官方成绩单（deepseek prompt-v2） |
| `feagpt_repro/candidates_l3_v6c_glm_p2/` / `candidates_l3_v6c_ds_p2/` | 55/55 候选（same prompt v2） |
| `feagpt_repro/reports/baseline_scorecard_L3_v6c.json` | C-029（旧 prompt，历史） |
| `feagpt_repro/reports/baseline_scorecard_L3_v6c_dsv4pro.json` | C-031（旧 prompt，历史；model 字段已修） |
| `feagpt_repro/reports/negative_controls_48.json` | 48/48（NC-30..46） |
| `feagpt_repro/reports/check_claims.json` | 25 active / 43 artifacts / 41 semantic 全过 |
| `feagpt_repro/_audit_clarify_meta.py` | 澄清元数据审计探针（--out/--md） |
| `feagpt_repro/_diag_model_diff.py` | 跨模型逐题差异（2×2） |
| `FEM-Bench-Aero/RUBRIC.md` | v4.9：R50–R54、§7.6 跨模型对比 |
| `FEM-Bench-Aero/CLAIMS.md` | C-032/C-033；R50–R54；C-019 48/48 |

### 1.3 C-032 / C-033 官方数字

| 指标 | C-032（glm） | C-033（dsv4pro） | C-029（glm 旧） | C-031（dsv4pro 旧） |
|---|---:|---:|---:|---:|
| exam TSR | **23/25 = 92.0%** | **22/25 = 88.0%** | 23/25 = 92.0% | 20/25 = 80.0% |
| exam SFR | 20/22 = 90.9% | 20/21 = 95.2% | 20/22 = 90.9% | 20/25 = 80.0% |
| exam MSR | 20/22 = 90.9% | **20/21 = 95.2%** | 19/22 = 86.4% | 20/22 = 90.9% |
| dev TSR | **22/30 = 73.3%** | 22/30 = 73.3% | **23/30 = 76.7%** | 22/30 = 73.3% |
| dev MSR | 21/29 = 72.4% | 22/29 = 75.9% | 19/29 = 65.5% | 22/28 = 78.6% |
| full MSR | 41/51 = 80.4% | 42/50 = 84.0% | 38/51 = 74.5% | 42/50 = 84.0% |
| boundary | 6/6 | 6/6 | 6/6 | 6/6 |
| extrapolation | 11/13 = 84.6% | 11/13 = 84.6% | 11/13 = 84.6% | 9/13 = 69.2% |
| interpolation | 6/6 | 5/6 = 83.3% | 6/6 | 5/6 = 83.3% |
| FPR | 0/4 | **1/4 = 25%** | 0/4 | 4/4 = 100% |
| turns | 1:3 / 2:50 / 3:2 | 1:2 / 2:48 / 3:5 | 1:4 / 2:48 / 3:3 | 2:52 / 3:3 |
| first pass | 3/55 | 2/55 | 4/55 | 0/55 |
| unresolved | 0 | **1** | 0 | 1 |
| solver | 0 | 0 | 4 | 0 |
| value_added 任务级 | 92.0%（Δ92 PASS） | 88.0%（Δ88 PASS） | 92.0% | 80.0% |
| value_added 字段级 | **99.34%（Δ+13.4 PASS）** | **90.94%（Δ+5.0 BELOW）** | 99.34%（Δ+13.4） | 87.42%（Δ+1.5 BELOW） |
| verdict_split | 无（两尺度 PASS） | **任务 PASS / 字段 BELOW** | 无 | 任务 PASS / 字段 BELOW |
| 2×2 | — | — | — | — |

**2×2（C-032 vs C-033，逐题）**：both 22 / only_a 1 / only_b 0 / neither 2。两模型 `spec_pass` 都是 **20/25**。

### 1.4 覆盖与可复现

- C-032/C-033：各 55/55 文件；C-032 `n_unresolved=0`；C-033 `n_unresolved=1`。
- 同卷硬证据：`tasks_sha256 = 9c1faa3a…`；同 prompt 硬证据：`prompt_sha = ce225186cafa…`（S-39 守）。
- `check_claims`：25 active / 43 artifacts / 41 semantic，`n_fail=0`、`all_ok=True`。
- `negative_controls_48`：48/48，含 NC-43（model 字段）、NC-44（分母闭合）、NC-45（prompt 盲填）、NC-46（MSR 条件口径）。
- `compare_scorecards.py`：C-032 vs C-033 同卷同 prompt，**不是跨卷混比**；C-029/C-031 与 C-032/C-033 因 prompt sha 不同，不可直减。

---

## 2. 已验证的改进（credit）

| 改进 | 实测 |
|---|---|
| **P1：model 字段** | 顶层 `model` 从候选实测；C-031 现在是 `deepseek-v4-pro`；C-032/C-033 全对；S-36/NC-43 |
| **P1：分母拆分** | `n_counted + n_clarify_excluded + n_unresolved_excluded + n_solver_excluded` 闭合；C-033 4 + 1；C-032 4 + 0；S-37/NC-44 |
| **P1：prompt 修复** | 删“未提长桁→0”盲填授权 + 数量铁律；**不注入 expected_clarifications**（防泄题）；S-38/NC-45 |
| **prompt sha 可追溯** | C-032/C-033 prompt sha `ce225186…` == 当前源码；S-39 |
| **C-032** | exam 23/25 92.0；逐题类别与 C-029 完全相同；FPR 0/4；字段 99.34% |
| **C-033** | exam 22/25 88.0（C-031 80.0 +2）；FPR 4/4→1/4；字段 87.42→90.94；**首例 R53 合规跨模型** |
| **2×2 归因** | both 22 / only_a 1 / only_b 0 / neither 2；spec_pass 20/20；差距从 3 条缩到 1 条 |
| **R54 MSR 条件口径** | C-033 exam MSR 95.2% > C-032 90.9%，但分母 21 vs 22 且排除的是失败题；口径落盘 + 排除项点名；S-40/NC-46 |
| **compare_scorecards 自比** | 修 R53 误伤自比；NC-29/35 恢复 |
| **负控/自检** | 48/48；25/43/41；RUBRIC v4.9；R50–R54 |

---

## 3. 剩余问题

### 3.1 P2：C-032 的 dev 22/30，比 C-029 的 23/30 少 1

- C-032 exam 23/25（与 C-029 相同），但 dev **22/30**（C-029 23/30）；总 TSR 45/55（C-029 46/55）。
- C-032 dev categories：spec_pass 21 / spec_fail 8 / clarify_ok 1；C-029 是 22 / 7 / 1。**prompt 修复后有 1 条 dev 从 pass 变 fail**。
- 这不是“prompt 修错了”——exam 同 23、FPR 0/4、字段 99.34 都证明修得对；但**dev 的 1 条反向变化必须定位**：是哪条题、哪个字段、是否与“数量类字段铁律”有关。
- 建议：`_diag_model_diff.py` 或 per_task 对比 C-029 vs C-032 的 dev，找出唯一翻转题；在 C-032 claim/INDEX 写明“dev 22 是 prompt v2 的已知代价，不是模型退步”。

### 3.2 P2：C-033 仍剩 1 条编造 + 1 条问错字段

- C-033 exam 22/25；3 条失败 = **1 条 `clarify_wrong`（问错字段）+ 1 条 `spec_fail` + 1 条 `no_output`**；FPR **1/4 = 25%**（C-031 4/4，C-032 0/4）。
- prompt 修复回收了 C-031 的 2 条编造（80→88），但没清零：仍有 1 条编造/问错、1 条无输出。
- **这是 prompt v2 的已知限制**，不是新缺陷；建议：
  - 在 C-033 claim/INDEX 明写“3 条失败的具体题/字段/FPR 25%”；
  - prompt v3 再针对 `clarify_wrong`（问错字段）做一次小修，但不要注入 expected_clarifications；
  - 不因此阻塞 W5d——C-033 是 supporting，headline 是 C-032。

### 3.3 P2：C-033 字段级 90.94%（Δ+5.0pp BELOW）

- C-033 任务级 88.0%（Δ88pp PASS），字段级 **90.94%（Δ+5.0pp BELOW 10pp）**；`verdict_split` 已落盘（R49）。
- C-032 字段级 99.34%（Δ+13.4pp PASS）；地板 85.93%。
- 三档：地板 85.93 / C-033 90.94 / C-032 99.34；C-033 比地板高 5pp，但仍低于 10pp 判据；**字段尺度上 C-033 仍接近“族级众数”**。
- 建议：W5d 榜单必须并列任务级/字段级，不能只引 88% 任务级。

### 3.4 P2：C-033 exam MSR 95.2% > C-032 90.9%，但 TSR 88 < 92（R54）

- C-033 exam MSR 20/21 = 95.2%；C-032 20/22 = 90.9%。分母 21 vs 22；C-033 的 1 条 no_output 被 `n_unresolved_excluded` 排除，C-032 没有排除。
- **MSR 是条件通过率**：分母不同、排除项不同，排名可以相反；TSR 是 25 分母，88 < 92。
- R54/S-40 已要求口径落盘 + 排除项点名；credit。W5d 不得用 MSR 单独排名。

### 3.5 P2：C-033 1 条 unresolved

- C-033 `n_unresolved=1`（`cfrp090s` 3 轮无输出）；C-032 0；C-031 1。
- 全链分母 50 vs 51；full MSR 42/50 84.0 vs 41/51 80.4；**不可直减**。
- 已通过 `n_unresolved_excluded` 显式拆分；credit；但 W5d 要并列“unresolved 1”。

### 3.6 P2：C-032 的 solver 0 vs C-029 的 4

- C-032 `n_solver_excluded=0`；C-029 4（1 exam + 3 dev）。C-032 的候选 `glm_p2` 没有撞 158,548 节点阈值；C-029 有。
- C-032 full MSR 41/51 80.4% vs C-029 38/51 74.5%；**不是“模型变强”，是候选网格不同**。
- C-032 的 `failure_class_counts = {'model': 10}`；C-029 是 solver 4 / model 8 / contract 1。**C-032 的 10 条 model 失败 vs C-029 的 8 model + 4 solver + 1 contract**；全链失败结构不同，不可直减。
- 建议 W5d 并列 solver/unresolved/contract 的分层，不要只报 full MSR。

### 3.7 P2：turns/first-pass 变化

- C-032：1:3 / 2:50 / 3:2；first 3；C-029：1:4 / 2:48 / 3:3；first 4。
- C-033：1:2 / 2:48 / 3:5；first 2；C-031：2:52 / 3:3；first 0。
- prompt v2 让 C-033 的 first-pass 从 0 升到 2，但 3 轮从 3 升到 5；C-032 的 first 从 4 降到 3。**prompt 修复不是单调改善**；W5d 必须同预算并列 first-pass/turns。

### 3.8 P2：C-032 的 model 失败 10 条 vs C-029 的 8 条

- C-032 `failure_class_counts = {'model': 10}`；C-029 model 8 + solver 4 + contract 1。
- C-032 的 10 条 model 失败包含 dev 8 spec_fail + exam 2 spec_fail；C-029 的 8 条 + 4 solver + 1 contract；失败结构不同。
- 建议 W5d 用同一失败分层口径并列，不要只报 TSR。

### 3.9 P2：旧 prompt 的 C-029/C-031 仍 active

- C-029/C-031 是 prompt v1 的历史口径；C-032/C-033 是 prompt v2 的当前口径。S-29 已把 headline 唯一指向 C-032；S-34 把 C-031/C-033 标 supporting。
- **C-029 的 92.0 与 C-032 的 92.0 不可直接相减**（prompt sha 不同）；C-031 的 80.0 与 C-033 的 88.0 也不可直减（prompt 不同，虽然 +2 是同一批题的回收）。C-033 claim 已写“C-031 与 C-032/C-033 仍不可相减”；credit。
- 建议 INDEX/README 明确“C-029/C-031 = prompt v1 历史；C-032/C-033 = prompt v2 当前”。

### 3.10 P2：README 日期仍写 2026-10-26

- README “当前状态 · 2026-10-26”；当前 2026-10-27，C-032/C-033 已落地。建议改成 2026-10-27，并把 C-032/C-033 写进“当前状态”。

### 3.11 P2：旧负控 31/37/39/41/44/47/48 并存

- 当前 48/48；旧六份是历史。建议 INDEX 标历史或归档 `reports/archive/`。

### 3.12 P2：key 轮换仍未执行

- W5c-6b R46 已证明“轮换不需要重签 artifact”；同应用轮换仍未验证。建议 D5-b 做一次验证；可行则轮换。

### 3.13 不是问题的部分（避免过度纠偏）

- C-032 的 92.0、C-033 的 88.0、C-029 的 92.0、C-031 的 80.0；2×2；字段 99.34/90.94；T1+ 85.93；48/48；25/43/41；R50–R54；S-36–S-40；prompt 不泄题——都是真的，不需要重做。
- C-033 的 88.0 比 C-031 的 80.0 高 2 条，是 prompt 修复的真实回收；**不是模型变强**，credit 已写。
- C-032 的 92.0 与 C-029 的 92.0 相同，说明 prompt 修的是隐患，不是补分；**但 dev 22 vs 23 的 1 条反向必须定位**。
- C-033 的 3 条失败里 1 条编造 + 1 条问错 + 1 条无输出；FPR 25%；**已披露，不阻塞 W5d**。

---

## 4. W5d 准入评估

### 4.1 Go / No-Go

| 条件 | 现状 | 结论 |
|---|---|---|
| 同卷同 prompt | `tasks_sha256 9c1faa3a…`；`prompt_sha ce225186…` | ✅ |
| headline 唯一 | S-29 = C-032 | ✅ |
| 第二模型 supporting | S-34 = C-031/C-033 | ✅ |
| model 字段 | S-36 全对 | ✅ |
| 分母闭合 | S-37 四类；C-033 4+1 | ✅ |
| prompt 不泄题 | S-38 未注入 expected_clarifications | ✅ |
| prompt sha 可追溯 | S-39 | ✅ |
| 双尺度 | C-032 PASS；C-033 `verdict_split` | ✅ |
| MSR 条件口径 | S-40；C-033 21 vs C-032 22 | ✅ |
| 负控/自检 | 48/48；25/43/41 | ✅ |
| C-032 dev 1 条反向 | **22 vs 23，未定位** | ⚠️ P2 |
| C-033 1 编造 + 1 问错 | **FPR 25%，未清零** | ⚠️ P2 |
| C-033 字段 BELOW | **+5.0pp < 10pp** | ⚠️ P2 |

**判定：W5d 可以开。** 三个 ⚠️ 是已披露的 P2：C-032 dev 定位是 W5d 的第一件小事；C-033 剩余 2 条是 prompt v3 的事；字段 BELOW 是 W5d 必须并列的尺度。**不因这三个 P2 延迟 W5d。**

### 4.2 能说什么 / 不能说什么

| 可以说 | 不能说 |
|---|---|
| C-032 exam 23/25 (92.0%)，C-033 22/25 (88.0%)，同卷同 prompt | “deepseek 88% 是能力上限” |
| 2×2 both 22 / only_a 1 / only_b 0 / neither 2 | “两模型一样强” |
| 两模型 spec_pass 都是 20/25 | “差距全部来自建模能力” |
| C-033 比 C-031 回收 +2（prompt 修复） | “deepseek 提升了 8pp” |
| C-033 字段级 90.94%（+5.0 BELOW） | “C-033 有显著增量” |
| C-033 exam MSR 95.2% > C-032 90.9%，但分母不同、TSR 相反 | “C-033 全链更强” |
| C-032 dev 22/30 是 prompt v2 的已知代价 | “C-032 dev 退步” |

---

## 5. 下一步任务执行建议

### 5.1 任务表

| ID | 优先级 | 做什么 | 验收 | 证据 |
|---|---|---|---|---|
| **W5d** | **P0** | **干净跨模型榜单/协议**：C-032/C-033 同卷同 prompt；2×2 + 逐题差异；任务级/字段级双尺度；失败分层；CI；第三方复现脚本 | 两模型同 harness；排名有 CI；不混分母；可复现 | 新 `reports/w5d_*` |
| **W5d-0** | **P0** | **定位 C-032 dev 22 vs C-029 23 的 1 条反向** | 找出题/字段；写进 C-032 claim/INDEX | `_diag_model_diff.py`；per_task |
| **W5d-1** | **P1** | **C-033 剩余 1 编造 + 1 问错字段**：写进 C-033 claim/INDEX；prompt v3 再修（不注入 expected_clarifications） | C-033 的 3 条失败点名；FPR 25% 明示 | C-033；prompt v3 |
| **W5d-2** | **P1** | **字段级 BELOW**：W5d 榜单必须并列 99.34 vs 90.94；不单独引任务级 88% | 双尺度同表 | W5d 报告 |
| **W5d-3** | **P1** | **MSR 条件口径**：C-033 21 vs C-032 22；排除项点名；分母不等不出 Δ | 同 R54/S-40 | W5d 报告 |
| **W5d-4** | **P2** | **solver/unresolved/contract 分层**：C-032 0 solver vs C-029 4；C-033 1 unresolved | 同表并列 | W5d 报告 |
| **v1.1** | **P2** | **新几何 6–10 条**：扩 exam 精度；n≥30；族级 CI | 新几何 truth + 双求解器 + 闸 | 后续 |
| **key D5-b** | **P2** | 只换 key、endpoint 不变；可行则轮换；不可行记录 | 结论/日期/决策人 | W5B_PLAN §6.0b |

### 5.2 顺序建议

```text
W5d-0 定位 C-032 dev 1 条反向
        │
        ▼
W5d 榜单/协议（C-032/C-033 同 harness）
        │
        ├──► W5d-1 C-033 剩余 2 条 / prompt v3（可并行）
        ├──► W5d-2 字段级双尺度
        ├──► W5d-3 MSR 条件口径
        └──► W5d-4 solver/unresolved/contract 分层
        │
        ▼
v1.1 新几何
```

**为什么先 W5d-0**：C-032 的 dev 22 vs 23 是唯一一个“prompt 修复带来的反向变化”；不定位就写进榜单，读者会问“为什么 prompt 修了 dev 还降”。这是 0.5 天的活，先做。

### 5.3 成本估计

- W5d-0：0.2 天（逐题对比）。
- W5d：1–2 天（榜单/协议/第三方复现）。
- W5d-1：0.5 天（prompt v3 + 1 条/族冒烟 + C-033 重跑可选）。
- W5d-2/3/4：0.5 天（报告表）。
- **总计约 2–3 天**到 W5d 收口。

---

## 6. 防跑偏机制（R55–R57 建议）

> R1–R54 保留；以下为第十一轮建议新增，待拍板后写入 RUBRIC。

| 红线 | 内容 | 触发点 |
|---|---|---|
| **R55** | **prompt 修复必须做逐题回归**：prompt 版本变更后，必须对比新旧 prompt 的 per_task 差异；任何“exam 不变但 dev 变”的反向变化必须定位并写进 claim | W5d-0；S-41；NC-47 |
| **R56** | **跨模型榜单必须并列任务级/字段级/分层**：不得只引任务级 TSR 或只引 MSR；字段级 BELOW 必须同表 | W5d；S-42 |
| **R57** | **prompt v3 不得注入 expected_clarifications**：修复只能靠规则/词汇/数量铁律，不得把答案传给生成器 | W5d-1；S-38 延续 |

**新增语义检查（S-41..S-42）建议：**

| ID | 检查 | 期望 |
|---|---|---|
| S-41 | C-032 dev 22 vs C-029 23 | 唯一翻转题/字段已点名；claim/INDEX 有记录 |
| S-42 | W5d 跨模型表 | 任务级/字段级/失败分层三列齐全；MSR 分母不等不写 Δ |

---

## 7. 评分卡

> **第十轮 28/30 → 第十一轮 29/30**：3 个 P1 全清（+1），C-032/C-033 跨模型（+0.5），C-032 dev 1 条反向 + C-033 剩余 2 条（−0.5）。

| # | 维度 | 第九轮 | 第十轮 | 第十一轮 | 依据 |
|---|---|---:|---:|---:|---|
| 1 | 目标一致性 | 3 | 3 | **3** | 评测基础设施主轴不变；W5c-6d..6h 按计划 |
| 2 | 任务有效性 | 3 | 3 | **3** | exam R32/R41 0；dev 4 R41 已知；prompt 澄清冲突已修 |
| 3 | 判分有效性 | 3 | 3 | **3** | R50–R54；48/48；四类分母；双尺度 |
| 4 | 证据等级 | 3 | 2 | **3** | 25/43/41；model 字段修复；prompt sha；C-031/C-033 可溯源 |
| 5 | 可复现性 | 3 | 3 | **3** | 同卷 sha + 同 prompt sha；48/48；C-032/C-033 命令 |
| 6 | 版本治理 | 2 | 3 | **3** | C-032 headline；C-033/C-031 supporting；C-029/C-031 历史 |
| 7 | 文档真实性 | 2 | 3 | **3** | C-033 claim 主动披露 FPR 25%/字段 BELOW/剩余 2 条；C-032 dev 未定位是 P2 |
| 8 | 统计有效性 | 2 | 2 | **2** | n=25；CI；字段级三档；族 n<10；C-033 CI 宽 |
| 9 | 范围纪律 | 3 | 3 | **3** | 第二模型 supporting；不抢 headline；不混分母 |
| 10 | 计划执行 | 3 | 3 | **3** | 3 个 P1 全清；48/48；25/43/41；C-032/C-033 |
| **总分** | | **27/30** | **28/30** | **29/30** | 基础设施 A；科学有效性 A−；**W5d 已具备条件** |

**一句话**：**这一轮把“prompt 修复”做成了一次可归因的跨模型实验——exam 不变、C-033 +2、2×2 只剩 1 条差异；剩下的 dev 1 条反向和 C-033 2 条失败是已披露的 P2，不是阻塞项。** 开 W5d。

---

## 8. 待拍板

| # | 决策 | 选项 | 建议 |
|---|---|---|---|
| **D1** | **C-032/C-033 定位** | (a) C-032 headline、C-033 supporting、C-029/C-031 prompt v1 历史；(b) 两模型并列 | **(a)**；S-29/S-34 已定 |
| **D2** | **W5d 时机** | (a) 现在开，W5d-0 先定位 C-032 dev 1 条；(b) 先修 C-033 剩余 2 条再开 | **(a)**；C-033 剩余是 supporting 的 P2；W5d 是里程碑 |
| **D3** | **C-033 剩余 2 条** | (a) 写进 claim/INDEX，prompt v3 再修；(b) 现在就修 prompt v3 | **(a)**；不阻塞 W5d；prompt v3 可与 W5d 并行 |
| **D4** | **C-032 dev 1 条反向** | (a) 先定位再写榜单；(b) 不定位 | **(a)**；否则读者会问“prompt 修了 dev 怎么降” |
| **D5** | **v1.1 新几何** | (a) W5d 之后；(b) 现在 | **(a)**；先完成两模型榜单/协议 |
| **D6** | **key 轮换** | (a) 验证“只换 key、endpoint 不变”；(b) 接受现状 | **(a)**；W5c-6b 已证明不需要重签 artifact |

---

## 附录 A　证据索引与复现命令

### A.1 官方 artifact

| 文件 | 用途 |
|---|---|
| `feagpt_repro/reports/baseline_scorecard_L3_v6c_p2.json` | C-032（glm prompt-v2）headline |
| `feagpt_repro/reports/baseline_scorecard_L3_v6c_ds_p2.json` | C-033（dsv4pro prompt-v2）supporting |
| `feagpt_repro/reports/baseline_scorecard_L3_v6c.json` | C-029（prompt v1，历史） |
| `feagpt_repro/reports/baseline_scorecard_L3_v6c_dsv4pro.json` | C-031（prompt v1，历史；model 已修） |
| `feagpt_repro/reports/trivial_baselines_L3_v6c.json` | T1+ family / oracle / 字段命中 |
| `feagpt_repro/reports/negative_controls_48.json` | 48/48 |
| `feagpt_repro/reports/check_claims.json` | 25/43/41 |
| `feagpt_repro/reports/papers/tasks_v6c.jsonl` | 考卷 sha `9c1faa3a…` |

### A.2 复现命令

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# C-032 / C-033 生成（prompt v2）
node gen_candidates_v2.js --tasks reports/papers/tasks_v6c.jsonl --levels L3 \
  --out candidates_l3_v6c_glm_p2 --limit 55 --model glm-5.3-flash --max-turns 3
node gen_candidates_v2.js --tasks reports/papers/tasks_v6c.jsonl --levels L3 \
  --out candidates_l3_v6c_ds_p2 --limit 55 --model deepseek-v4-pro --max-turns 3

# 打分 + MSR + CI
for m in glm_p2 ds_p2; do
  "$PY" score_baseline.py --candidates candidates_l3_v6c_$m \
    --tasks reports/papers/tasks_v6c.jsonl \
    --report reports/baseline_scorecard_L3_v6c_$m.json \
    --trivial reports/trivial_baselines_L3_v6c.json
  "$PY" msr_l3.py --candidates candidates_l3_v6c_$m \
    --tasks reports/papers/tasks_v6c.jsonl \
    --report reports/baseline_scorecard_L3_v6c_$m.json
  "$PY" bootstrap_ci.py --scorecard reports/baseline_scorecard_L3_v6c_$m.json \
    --out reports/bootstrap_ci_L3_v6c_$m.json
done

# 自检
"$PY" check_claims.py
"$PY" negative_controls.py
```

---

## 附录 B　C-032/C-033 vs C-029/C-031

| 指标 | C-032 glm p2 | C-033 dsv4pro p2 | C-029 glm v1 | C-031 dsv4pro v1 |
|---|---:|---:|---:|---:|
| exam TSR | 23/25 92.0% | 22/25 88.0% | 23/25 92.0% | 20/25 80.0% |
| exam SFR | 20/22 90.9% | 20/21 95.2% | 20/22 90.9% | 20/25 80.0% |
| exam MSR | 20/22 90.9% | 20/21 95.2% | 19/22 86.4% | 20/22 90.9% |
| dev TSR | **22/30 73.3%** | 22/30 73.3% | **23/30 76.7%** | 22/30 73.3% |
| full MSR | 41/51 80.4% | 42/50 84.0% | 38/51 74.5% | 42/50 84.0% |
| FPR | 0/4 | **1/4 25%** | 0/4 | 4/4 100% |
| turns | 1:3/2:50/3:2 | 1:2/2:48/3:5 | 1:4/2:48/3:3 | 2:52/3:3 |
| first | 3 | 2 | 4 | 0 |
| unresolved | 0 | **1** | 0 | 1 |
| solver | 0 | 0 | 4 | 0 |
| 字段级 | 99.34% (+13.4) | 90.94% (+5.0 BELOW) | 99.34% (+13.4) | 87.42% (+1.5 BELOW) |
| 任务级 | 92.0% | 88.0% | 92.0% | 80.0% |

**2×2（C-032 vs C-033）**：both 22 / only_a 1 / only_b 0 / neither 2。`spec_pass` both 20/25。

### B.1 C-033 的 3 条 exam 失败

| 类别 | 条数 | 说明 |
|---|---:|---|
| `clarify_wrong` | 1 | 问了错字段（不是 expected_clarifications 的字段） |
| `spec_fail` | 1 | 与 C-032 同题同字段（C-032 也失败） |
| `no_output` | 1 | 3 轮无输出（`cfrp090s`） |
| **FPR** | **1/4** | 1 条编造；C-031 是 4/4 |

**⇒ prompt v2 回收了 C-031 的 2 条编造，但没清零；剩余 1 编造 + 1 问错是已知限制。**

---

## 附录 C　第十轮 P1 逐项判定

| 第十轮 P1 | 第十一轮状态 | 证据 |
|---|---|---|
| P0 prompt“未提长桁→0” | ✅ | 删盲填授权 + 数量铁律；不注入 expected；S-38 |
| P1 C-031 model 字段 | ✅ | 顶层 = provenance = deepseek；S-36 |
| P1 n_clarify 混 unresolved | ✅ | 四类拆分；C-033 4+1；S-37 |
| P2 C-031 first-pass 0/unresolved 1 | ✅ 记录 | C-033 first 2/unres 1；C-031 历史 |
| P2 C-031 80 vs C-029 92 | ✅ | C-033 88；+2；2×2 |
| P2 MSR/TSR 排名相反 | ✅ | R54/S-40；C-033 21 vs C-032 22 |
| P2 T1+ | ✅ | 0/25；字段 85.93；oracle 0/25 |
| P2 README 日期 | ⚠️ | 仍 2026-10-26 |
| P2 key 轮换 | ⚠️ | 仍未执行 |
| P2 旧负控 | ⚠️ | 31/37/39/41/44/47/48 并存 |

---

## 附录 D　文档/口径漂移清单

| # | 位置 | 现文 | 应为 |
|---|---|---|---|
| 1 | `README.md` 当前状态 | 2026-10-26 | 2026-10-27；C-032/C-033 |
| 2 | C-032 dev 22/30 | 未写“1 条反向” | 定位后点名题/字段 |
| 3 | C-033 3 条失败 | 未逐条点名 | `clarify_wrong` / `spec_fail` / `no_output` |
| 4 | `reports/` 旧负控 | 31/37/39/41/44/47/48 并存 | INDEX 标历史/归档 |
| 5 | C-029/C-031 | prompt v1 历史 | INDEX/README 明示“旧 prompt” |
| 6 | C-033 `field_level` | 90.94% BELOW | W5d 表并列，不单独引 88% |

---

> **本轮只读核对；除本文件外未改动任何项目文件。**
> 下一轮复评入口：W5d 榜单/协议（C-032/C-033 同 harness）+ W5d-0 定位 C-032 dev 1 条反向；v1.1 新几何在 W5d 之后。
