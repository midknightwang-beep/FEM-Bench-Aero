# FEM-Bench-Aero 第六轮复评与执行纠偏（W5a 后）

> **复评日期**：2026-10-25（第六轮）
> **复评对象**：W5a 的修题（R21）、桥接表（R22）、MSR 分母（R23）、考卷 v5、成绩单与 CLAIMS
> **复评方式**：只读核对 + 按 split 重算 + 复现命令检查 + git 追踪检查
> **结论先行**：
> **W5a 的科学内容基本到位：load.direction 写死、panel 澄清题迁移、MSR 分母按任务属性排除、桥接表 A/B/C/D 闭合、负控 24/24、考卷 v5 冻结。**
> **但官方 artifact 全部写在 `eval_runs/`（被 gitignore）；C-021 的 v4 成绩单已被 v5 重打分覆盖；C-021 的命令现在复现的是 v5 而不是 v4。**
> **W5b 判定：Conditional-Go —— 先做 0.5 天的 W5a'（artifact 入库 + CLAIMS 自检），再扩量；在此之前，C-021/C-024/C-025 在 clean clone 上不可复现。**

---

## 目录

- [0. 复评摘要](#0-复评摘要)
- [1. 变化与交付](#1-变化与交付)
- [2. 已验证的改进（credit）](#2-已验证的改进credit)
- [3. 新发现的问题](#3-新发现的问题)
- [4. W5b 准入评估](#4-w5b-准入评估)
- [5. 下一步任务执行建议](#5-下一步任务执行建议)
- [6. 防跑偏机制（更新）](#6-防跑偏机制更新)
- [7. 评分卡](#7-评分卡)
- [8. 待拍板](#8-待拍板)
- [附录 A　证据索引](#附录-a证据索引)
- [附录 B　复现命令](#附录-b复现命令)

---

## 0. 复评摘要

### 0.1 三句话结论

1. **W5a 修对了科学问题。** 考卷 v5 的四族 NL 都写死了坐标系+方向（`coordinate_convention` 30/30）；panel 的"伪缺澄清题"从 600x600（gold n_stringers=0）迁到 str3（真缺）；MSR 分母按任务属性排除澄清/编造题（R23），exam MSR 从 4/10 修正为 4/9；桥接表 A=7/11、B=5/11、C=0/11、D=5/11 闭合；负控 **24/24**。
2. **但官方 artifact 没有入库。** `git ls-files feagpt_repro/eval_runs` = **0**；C-021/C-024/C-025/C-019 的 artifact 全部在 `eval_runs/`（被 `.gitignore` 第 52 行排除）。C-021 的 v4 成绩单已被 v5 重打分覆盖；C-021 的命令 `score_baseline.py --candidates candidates_l3_v3` 现在生成的是 v5（4/11、MSR 4/8），不是 C-021 的 v4（5/11、MSR 4/9）。
3. **W5b 可以启动，但先做 0.5 天的 artifact 入库与 CLAIMS 自检。** 否则 W5b 的成绩也会是"跑得出来、查不到"的临时文件；下一轮复评还会发现"官方数字和磁盘文件对不上"。

**一句话**：**科学上已经够 W5b；工程上还差一步"把证据钉进 git"。**

### 0.2 执行总评

| 工作块 | 评分 | 一句话判断 |
|---|---|---|
| W5a：修题 + 桥接 + MSR | **A−** | 科学内容到位；artifact 未入库 |
| 总体 | **24/30** | 统计有效性 1（n=11、无 CI）+ 证据/可复现各 2 ⇒ 可扩量，不可对外承诺 |

### 0.3 最重要的建议

> **W5b 之前插入 W5a'（0.5 天）：建 `reports/` 并把 v4/v5 成绩单、桥接表、负控、T0/T1/T2、MSR 的版本化产物提交；加 `check_claims.py` 断言每条 active CLAIM 的 artifact 存在且被 git 追踪。**
> **然后 W5b 用 v5 新生成候选（不是重打分旧候选），扩到 n≥20，再加 CI 与第二模型。**

---

## 1. 变化与交付

### 1.1 提交与 tag

| commit | 内容 |
|---|---|
| `4530ff8` | W5a：修题（R21）+ 桥接表（R22）+ MSR 分母（R23） |
| `e45bc01` | 记忆收口 |

**tag**：`v1.0-l3-v5`（考卷 v5 冻结）。

### 1.2 新增/修改的关键文件

| 文件 | 作用 |
|---|---|
| `FEM-Bench-Aero/RUBRIC.md` | v3：R21 任务构建期方向检查、R23 MSR 分母、NC-20..22 |
| `FEM-Bench-Aero/CLAIMS.md` | C-024（桥接）、C-025（v5 重打分）、C-021 MSR 改 4/9 |
| `feagpt_repro/tasks/*` + `.sha256` | 考卷 v5：四族 `coordinate_convention`；panel ec 迁 str3 |
| `feagpt_repro/_bridge_v3/` | v3 判据快照 + 28 条逐 case evaluation（已入库） |
| `feagpt_repro/msr_l3.py` | R23 分母、`exam_msr`/`dev_msr`/`by_split` |
| `feagpt_repro/negative_controls.py` | PC-1 + NC-1..22 + NC-15b = **24/24** |
| `feagpt_repro/score_baseline.py` | exam/dev/MSR 汇总；`--tasks` 支持 |
| `feagpt_repro/eval_runs/bridge_v3_v4.json` | **未入库**（C-024 artifact） |
| `feagpt_repro/eval_runs/baseline_scorecard_L3.json` | **未入库**；已被 v5 覆盖（C-021/C-025 artifact） |

---

## 2. 已验证的改进（credit）

| 改进 | 实测 |
|---|---|
| R21 坐标系写死 | v5 的 wingbox NL 含 "坐标系：x 弦向、y 弯曲方向（翼型法向）、z 展向"；四族 30/30 有 `coordinate_convention` |
| panel 澄清题修正 | 600x600（gold 0 根长桁）不再要求澄清；ec 迁到 `600x600_str3`（真缺 3 根） |
| MSR 分母 R23 | 澄清题/编造题不计分母；exam MSR **4/9**（C-021 修订），all **12/21**；`exam_msr`/`dev_msr`/`by_split` 落盘 |
| 桥接表 R22 | A=7/11、B=5/11、C=0/11、D=5/11；A→D 净 −2；B=D=5 证明新候选不受判据收紧影响 |
| 负控 | **24/24**（PC-1 + NC-1..22 + NC-15b），含 NC-20 载荷方向、NC-21 MSR 分母、NC-22 exam.msr |
| 考卷 v5 | tag `v1.0-l3-v5` + `tasks/nl_human.sha256` + `schema_task.sha256` |
| RUBRIC v3 | 预注册 R21/R23；版本记录 v1（post-hoc）/v2/v3 |
| C-025 的方法学 | 明确"旧候选不能评新考卷"；v5 重打分 4/11 是诊断，不是正式成绩；正式 v5 待 W5b 重生成 |

> 这些是实质进步。下面的问题不是否定科学，而是说：**证据没有钉住。**

---

## 3. 新发现的问题

### 3.1 P0-1　L3 官方成绩单/桥接/负控 artifact 全部在 gitignore 的 `eval_runs/`

**实测**

```
git ls-files feagpt_repro/eval_runs   -> 0
.gitignore:52  feagpt_repro/eval_runs/
```

| CLAIM | artifact | 是否被 git 追踪 |
|---|---|---|
| C-021（v4 正式 headline） | `eval_runs/baseline_scorecard_L3.json` | ❌ |
| C-024（桥接表） | `eval_runs/bridge_v3_v4.json` | ❌ |
| C-025（v5 重打分） | `eval_runs/baseline_scorecard_L3.json` | ❌ |
| C-019（负控 24/24） | `eval_runs/negative_controls.json` | ❌ |
| C-017（L1 冒烟） | `eval_runs/baseline_scorecard.json` | ❌ |

**影响**

- 一个新 clone 只能看到命令，看不到"当时跑出来的那份 JSON"；CLAIMS 的 "artifact + command" 只剩 command。
- `eval_runs/` 是工作目录，任何一次重跑都会覆盖；C-021 的 v4 成绩单已经被 v5 覆盖。
- 这不是"数字错了"，是"数字无法自证"——下一轮复评无法区分"当时的结果"和"现在的重跑"。

**修法（P0，W5a'）**

1. 新建 `reports/`（入库，不在 `.gitignore`），把以下版本化产物提交：
   ```
   reports/
     baseline_scorecard_L3_v4.json      # C-021
     baseline_scorecard_L3_v5_rescore.json  # C-025
     bridge_v3_v4.json                 # C-024
     negative_controls_24.json         # C-019
     trivial_baselines_L3.json
     msr_l3_v4.json
     msr_l3_v5_rescore.json
     INDEX.md                          # 哪个是官方、哪个是诊断
   ```
2. `score_baseline.py` / `msr_l3.py` 增加 `--report-dir`（默认 `reports/`），不再写 `eval_runs/`；或跑完复制到 `reports/`。
3. CLAIMS 的 artifact 路径改到 `reports/`；C-021 的命令加 `--tasks _bridge_v3/tasks/tasks.jsonl --report reports/baseline_scorecard_L3_v4.json`。
4. `msr_l3.py` 增加 `--tasks` / `--report`（当前硬编码 `tasks/tasks.jsonl` 与 `eval_runs/baseline_scorecard_L3.json`，无法复现 v4 MSR）。

---

### 3.2 P0-2　C-021 的文本与当前 scorecard 不一致

**实测**

| 来源 | exam TSR | exam MSR |
|---|---:|---:|
| README / CLAIMS C-021（官方 headline，v4） | **5/11（45.5%）** | **4/9（44.4%）** |
| 当前 `eval_runs/baseline_scorecard_L3.json`（v5 重打分） | **4/11（36.4%）** | **4/8（50.0%）** |

**问题**

- README 的"看基线成绩单"直接链到 `eval_runs/baseline_scorecard_L3.json`；读者点开看到的是 **v5 4/11**，而 headline 写的是 **C-021 v4 5/11**。
- C-021 的 artifact 路径就是这个文件；它已经被 C-025 的重打分覆盖。C-021 在 clean clone 上不可复现。
- C-025 本身是诊断（旧候选不能评新考卷），但它的输出占用了官方 artifact 的路径。

**修法（P0，W5a'）**

1. v4 与 v5 分开两个文件，`reports/INDEX.md` 写清：
   - **官方 headline = C-021 v4 5/11 / MSR 4/9（n=11 underpowered）**；
   - **v5 重打分 4/11 是诊断，不是模型成绩**；正式 v5 待 W5b 重生成。
2. README 的"看基线成绩单"链到 `reports/INDEX.md`，不要直接链工作文件。
3. C-021 的命令改为可复现 v4（指定 `--tasks _bridge_v3/tasks/tasks.jsonl`、`--report reports/baseline_scorecard_L3_v4.json`）。
4. `msr_l3.py` 同样支持 `--tasks/--report`。

---

### 3.3 P0-3　没有 CLAIMS 自检，artifact 缺失不会被发现

**问题**

- CLAIMS 规则写"artifact + command"，但没有脚本检查 artifact 是否存在、是否被 git 追踪、是否与 command 的输出路径一致。
- 这次 C-021/C-024/C-025/C-019 的 artifact 全部缺失，直到人工复评才发现。
- 同类问题已经发生过：C-020 的 MSR、C-017 的旧快照。**每轮都靠人查，不可持续。**

**修法（P0，W5a'）**

新建 `feagpt_repro/check_claims.py`：

```
1. 解析 CLAIMS.md 表格
2. 对每条 status=active 的 claim：
   - artifact 路径存在？
   - git ls-files --error-unmatch <artifact> 成功？（非 eval_runs/tmp）
   - command 里的 --report/--json 路径与 artifact 一致？
   - 若 artifact 是 JSON，记录 sha256 与 mtime
3. 任一失败 ⇒ rc=1；输出缺失清单
4. 进 CI / 每周检查
```

**新增负控 NC-23**：删一个 active claim 的 artifact ⇒ `check_claims.py` 必须 FAIL。

---

### 3.4 P1 级问题

| # | 问题 | 证据 | 修法 |
|---|---|---|---|
| P1-1 | C-019 仍写 21 条 | CLAIMS 第 28 行；实际 24/24 | 改 24；写 `PC-1 + NC-1..22 + NC-15b` |
| P1-2 | RUBRIC 说 "PC-1 + NC-1..22" = 23 | RUBRIC §6；实际 24（含 NC-15b） | 补 NC-15b；写 24 |
| P1-3 | C-024 "净 −2 全部来自 3 条 load.direction" 不准确 | per_task：−3 load +1 d2000；panel str3 另有变化 | 改成 "−3 load +1 d2000"；给逐条 diff |
| P1-4 | v5 重打分 4/11 与官方 5/11 并列出现，易误读 | README/CLAIMS C-025 | 明确"4/11 是诊断、5/11 是官方"；INDEX.md |
| P1-5 | 只有 glm-5.3-flash 一个模型 | scorecard `model` | W5b 加第二模型 |
| P1-6 | exam n=11、无 CI | `underpowered=true`；`tsr` 无 CI | W5b 扩到 ≥20 + bootstrap CI |
| P1-7 | exam 族别不平衡 | 11 条：wingbox 5、barrel 2、open_hole 2、panel 2 | W5b 按族补 |
| P1-8 | `score_baseline.py` 默认 candidate 目录仍是 `candidates_l3_v2` | 第 112 行 | 改 `candidates_l3_v3` 或要求显式 |
| P1-9 | `bridge_v3_v4.json` 的 `C=0/11` 是旧候选×新判据，不是纯判据效应 | C-024 | 在 CLAIMS 注明"旧候选习惯键"；避免读者误读为"判据坏了" |
| P1-10 | `_bridge_v3` 快照与当前 evaluator 的差异未版本化 | `_bridge_v3/evaluate.py` 499 行 | 在 `reports/` 记录 commit b2e9b74 与 sha256 |

---

## 4. W5b 准入评估

### 4.1 条件核对

| 条件 | 状态 | 说明 |
|---|---|---|
| 考卷 v5 冻结 | ✅ | tag `v1.0-l3-v5` + sha256 |
| RUBRIC v3 预注册 | ✅ | R21/R23 + 版本记录 |
| load.direction 写死 | ✅ | 四族 `coordinate_convention` |
| MSR 分母 R23 | ✅ | 澄清/编造不计；exam 4/9、all 12/21 |
| 桥接表 R22 | ✅ | A/B/C/D 闭合 |
| 负控 | ✅ | 24/24 |
| **官方 artifact 入库** | ❌ | `git ls-files eval_runs` = 0 |
| **C-021 可复现** | ❌ | 命令现在生成 v5；v4 文件被覆盖 |
| **CLAIMS 自检** | ❌ | 无 `check_claims.py` |
| **n_exam ≥20** | ❌ | 11 |
| **第二模型 / CI** | ❌ | 无 |

### 4.2 判定

> **Conditional-Go for W5b。**
>
> - **先做 W5a'（0.5 天）**：artifact 入库、C-021 可复现、`check_claims.py`、C-019/RUBRIC 计数修正。
> - **再启动 W5b（2–3 天）**：用 v5 考卷**新生成**候选（不是重打分旧候选）；扩到 n≥20；按族平衡；加 CI；加第二模型。
> - **不可以**：把 v5 重打分 4/11 当模型成绩；用 n=11 做调优/承诺；在 artifact 未入库时继续加功能。

---

## 5. 下一步任务执行建议

### 5.1 W5a'（0.5 天）：把证据钉进 git

| # | 任务 | 具体动作 | 验收 |
|---|---|---|---|
| 1 | 建 `reports/` | v4/v5 成绩单、桥接、负控、T0/T1/T2、MSR；`INDEX.md` 标注官方/诊断 | `git ls-files reports` 非空 |
| 2 | `--report-dir` | `score_baseline.py` / `msr_l3.py` 支持；默认写 `reports/` | 一条命令生成版本化文件 |
| 3 | `msr_l3.py --tasks/--report` | 支持 v4/v5 两套任务；不再硬编码 | C-021 v4 MSR 可复现 |
| 4 | C-021 命令 | 加 `--tasks _bridge_v3/tasks/tasks.jsonl --report reports/baseline_scorecard_L3_v4.json` | 重跑得到 5/11、4/9 |
| 5 | `check_claims.py` | 解析 CLAIMS、检查 artifact 存在+追踪+路径一致+sha256 | active claim 全过；NC-23 FAIL |
| 6 | 计数修正 | C-019 24；RUBRIC 24（含 NC-15b）；C-024 −3+1 | 文本与文件一致 |
| 7 | README 链接 | 链 `reports/INDEX.md`，不链工作文件 | 读者看到官方 vs 诊断 |

### 5.2 W5b（2–3 天）：重生成 + 扩量

| # | 任务 | 具体动作 | 验收 |
|---|---|---|---|
| 8 | v5 新生成 | 用 v5 NL + 修正后的坐标系/方向，重新生成 30 条候选（不是重打分旧候选） | 新 `candidates_l3_v5/` |
| 9 | 扩到 n≥20 | 用剩余 case 派 L3 或新增几何；按族平衡（wingbox/barrel/open_hole/panel） | exam ≥20 |
| 10 | 内插 ID test | 留出内插点；与 boundary/extrap 分列 | 三套 exam 分开报 |
| 11 | 重跑 T0/T1/T2 | 新 exam 上重算地板 | T1 exam 地板可引用 |
| 12 | 正式 v5 成绩 | 冻结 v6 + RUBRIC（如需）+ 预注册；给 bootstrap CI | exam n≥20，CI |
| 13 | 第二模型 | 至少再加一个可引用模型 | 两模型 TSR 差异 + CI |
| 14 | 失败归因 | env/contract/model/solver + 字段级 | 每条失败有原因 |

### 5.3 W5c（2–3 天）：L2 / A3

| # | 任务 | 验收 |
|---|---|---|
| 15 | L2 澄清基线 | 澄清题 TSR/FPR；字段级 |
| 16 | A3 修复基线 | 注入缺陷 + 闸报告 → 修复成功率/轮数 |
| 17 | 失败样本回流 | 回流池 + 专家确认 |

### 5.4 W5d（2–3 天）：榜单与协议

| # | 任务 | 验收 |
|---|---|---|
| 18 | 榜单协议 | 固定 exam、固定 rubric、CI、模型 id/日期 |
| 19 | 第三方复现 | 新机 fetch + 一条命令跑出同一成绩 |
| 20 | 发布说明 | v1.0-l3-v6 + dataset card + RUBRIC + reports |

### 5.5 明确不要做

- ❌ 不要在 artifact 未入库时继续加功能；
- ❌ 不要把 v5 重打分 4/11 当模型成绩（旧候选不能评新考卷）；
- ❌ 不要在 n=11 上做调优/对外承诺；
- ❌ 不要用单模型成绩做榜单；
- ❌ 不要让 `eval_runs/` 继续承载"官方数字"。

---

## 6. 防跑偏机制（更新）

### 6.1 新增红线条

| # | 红线 | 违反示例 |
|---|---|---|
| **R25** | **官方 artifact 必须入库**（`reports/`，非 `eval_runs/`）；每条 active CLAIM 可追溯到被 git 追踪的文件 | C-021 的 scorecard 被 v5 覆盖 |
| **R26** | **CLAIMS 自检必须进 CI**；artifact 缺失/未追踪/路径不一致 ⇒ 失败 | 本轮到人工复评才发现 |
| **R27** | **官方 vs 诊断必须分文件**；诊断结果不得占用官方 artifact 路径 | v5 重打分覆盖 v4 官方成绩单 |
| **R28** | **旧候选不得评新考卷**；考卷变更后必须重生成候选 | C-025 已遵守，但需写进流程 |

### 6.2 负控扩展

| 编号 | 注入 | 期望 | 当前 |
|---|---|---|---|
| **NC-23** | 删一个 active CLAIM 的 artifact | `check_claims.py` FAIL | ❌ 待加 |
| **NC-24** | artifact 在 `eval_runs/`（未追踪） | `check_claims.py` FAIL | ❌ 待加 |
| **NC-25** | 官方/诊断写同一路径 | `check_claims.py` FAIL | ❌ 待加 |

### 6.3 CLAIMS 更新

| claim | 处置 |
|---|---|
| C-021 | artifact 改 `reports/baseline_scorecard_L3_v4.json`；命令加 `--tasks _bridge_v3/tasks` |
| C-024 | artifact 改 `reports/bridge_v3_v4.json` |
| C-025 | artifact 改 `reports/baseline_scorecard_L3_v5_rescore.json`；标 diagnostic |
| C-019 | 24/24；artifact `reports/negative_controls_24.json` |
| 新 C-026 | `reports/INDEX.md`：官方 vs 诊断；v4/v5 口径 |

### 6.4 节奏（不变）

- 每周十维评分卡 + 红线条；
- 每个 W 块结束做完整复评 + 负控 + 全链正控 + **CLAIMS 自检**；
- 每 2 个里程碑独立复评；
- 执行人不能给自己的评分器签字。

---

## 7. 评分卡

| # | 维度 | 分数 | 理由 |
|---|---|---:|---|
| 1 | 目标一致性 | 3 | benchmark/verifier 主轴未变 |
| 2 | 任务有效性 | 3 | v5 坐标系写死、panel 澄清题修正；n=11 |
| 3 | 判分有效性 | 3 | 负控 24/24、R21/R23、MSR 分母 |
| 4 | 证据等级 | 2 | 科学证据强；官方 artifact 未入库/被覆盖 |
| 5 | 可复现性 | 2 | v5 tag/sha256；C-021 命令复现 v5 而非 v4 |
| 6 | 版本治理 | 2 | git + tag；scorecard 未版本化 |
| 7 | 文档真实性 | 2 | C-019 21 vs 24；C-024 归因；README 链接 v5 vs headline v4 |
| 8 | 统计有效性 | 1 | n=11、无 CI、underpowered |
| 9 | 范围纪律 | 3 | 红线 R1–R24 在 |
| 10 | 计划执行 | 3 | W5a 按期收口 |
| **总分** | | **24/30** | **统计有效性 1 ⇒ 不可对外承诺；W5b 可 Conditional-Go** |

> 与 CLAIMS 自评 29 的差异：证据 −1、可复现 −1、版本 −1、文档 −1、统计 −1；科学维度（任务/判分）已满分。

---

## 8. 待拍板

| # | 事项 | 建议 |
|---|---|---|
| 1 | 是否承认官方 artifact 未入库是 P0，先做 W5a' | **承认**；0.5 天 |
| 2 | 是否接受 `reports/` + `check_claims.py` 作为常设机制 | **接受**；R25/R26 |
| 3 | 是否接受 C-021 v4 官方、C-025 v5 诊断分文件 | **接受**；R27 |
| 4 | 是否接受 W5b 用 v5 新生成候选（不重打分旧候选） | **接受**；R28 |
| 5 | 是否接受 W5b 扩到 n≥20 后再做第二模型/CI | **接受** |
| 6 | 是否接受 v5 重打分 4/11 不作模型成绩 | **接受** |
| 7 | 是否接受 C-019/RUBRIC 计数改 24 | **接受** |

---

## 附录 A　证据索引

| 结论 | 证据 |
|---|---|
| `eval_runs` 未被 git 追踪 | `git ls-files feagpt_repro/eval_runs` = 0；`.gitignore:52` |
| C-021 artifact 被覆盖 | 当前 `eval_runs/baseline_scorecard_L3.json` exam 4/11、MSR 4/8；C-021 文本 5/11、4/9 |
| C-021 命令复现 v5 | `score_baseline.py` 默认 `tasks/tasks.jsonl`（v5）；C-021 命令未加 `--tasks` |
| `msr_l3.py` 硬编码任务/报告 | 第 64 行 `tasks/tasks.jsonl`；REPORT 固定 |
| 桥接 A/B/C/D | `eval_runs/bridge_v3_v4.json`；A=7、B=5、C=0、D=5 |
| v5 坐标系写死 | `tasks/nl_human.jsonl` 三条翼盒含"x 弦向、y 弯曲方向、z 展向" |
| panel ec 迁 str3 | `tasks/tasks.jsonl`：str3 ec=['n_stringers']；600x600 ec=None |
| 负控 24/24 | `eval_runs/negative_controls.json`；ids PC-1+NC-1..22+NC-15b |
| C-019 写 21 | `CLAIMS.md` 第 28 行 |
| RUBRIC 写 23 | `RUBRIC.md` §6 "PC-1 + NC-1..22"（漏 NC-15b） |
| `_bridge_v3` 已入库 | `git ls-files feagpt_repro/_bridge_v3` = 31 |
| `reports/` 不存在 | `ls reports` 无 |

## 附录 B　复现命令

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# 当前 scorecard（v5 重打分）
"$PY" - <<'PY'
import json
d=json.load(open('eval_runs/baseline_scorecard_L3.json',encoding='utf-8'))
print('exam',d['exam']); print('dev',d['dev']); print('msr',d['msr_section']['msr'])
PY

# 复现 C-021 v4（需要 v4 任务 + 独立 report）
"$PY" score_baseline.py --candidates candidates_l3_v3 \
  --tasks _bridge_v3/tasks/tasks.jsonl \
  --report reports/baseline_scorecard_L3_v4.json

# 桥接
cat eval_runs/bridge_v3_v4.json | head -40

# 负控
PYTHONIOENCODING=utf-8 "$PY" negative_controls.py

# 追踪检查
cd .. && git ls-files feagpt_repro/eval_runs | wc -l
```

---

> **本文件是第六轮复评的产物，不修改任何既有项目文件。**
> 本轮检查了 `eval_runs` 的 git 追踪、C-021 的 artifact 一致性、`msr_l3.py` 的硬编码路径、C-019/RUBRIC 计数与 v5 坐标系；未改动任何产物。
> **下一步：W5a'（artifact 入库 + check_claims）→ W5b（v5 重生成 + 扩到 n≥20 + CI + 第二模型）。**
