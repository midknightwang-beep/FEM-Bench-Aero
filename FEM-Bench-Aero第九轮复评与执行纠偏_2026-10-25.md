# FEM-Bench-Aero 第九轮复评与执行纠偏（W5c / C-029 后）

> **复评日期**：2026-10-25（第九轮）
> **复评对象**：W5c 收口（`83bfc4d`）——考卷 v6c、C-029、C-030、R32/R41 审计、契约试建闸、bridge 四格、负控 39/39、`check_claims` 22/34/29
> **复评方式**：只读核对 + 官方 artifact 交叉检查（成绩单 / 考卷 / bridge / 审计 / CLAIMS / RUBRIC / README / INDEX / W5B_PLAN）+ 字段级重算；**除本文件外未改动任何项目文件**
> **结论先行**：
> **W5c 做成了。C-029 是项目第一个“exam 题面干净、0 条未收敛、涨幅可拆解”的官方 headline：exam 23/25 (92.0%)、SFR 20/22 (90.9%)、exam MSR 19/22 (86.4%)、full MSR 38/51 (74.5%)；三栏 6/6 · 11/13 · 6/6；R32/R41 审计在 exam 上 0 违规；契约试建闸 gold 55/55 全可建；bridge 17→18→18→23 把“判分修正 +1 / 考卷修复 +0 / 重生成 +5”拆得干干净净。**
> **但 C-029 还不算“完全收口”，剩 4 个 P1：** ①**headline 文档漂移**——README 仍写“官方 = v6b C-028 68.0%、下一步 W5c”，C-021/C-025/C-026 三条 active claim 仍写“正式对外 headline = C-021”；②**dev “真实可达 25/30” 是纸面修复后的投影，不是实测**——dev 7 条 spec_fail 里只有 2 条是 R41 卷子缺陷，另外 5 条是模型侧（web1/web2 自创键、cfrp090s/cfrpqi layup、cfrp45s layup+material），修卷子只能回收 2 条，5 条模型失败仍在；③**T1+ 仍是 `null`**——只做了 leave-one-out（train 0/13），exam T1 0/25，value_added 的 92pp 仍是对着 0 地板；④**key 只止血未轮换**——硬编码 fallback 已删，但 key 仍在 git 历史，`W5B_PLAN` 的“重建应用 ⇒ endpoint 变 ⇒ provenance 重签”把轮换成本说重了，值得重新评估。
> **判定：C-029 可以作为当前官方 headline（带 4 个 P1 caveat）；下一步先跑 W5b-5 第二模型，同时做 W5c-6b headline/证据收口；不得把 92.0% 说成“能力上限”、不得把 dev 25/30 说成“实测”、不得把 value_added 说成“强证据”。**

---

## 目录

- [0. 复评摘要](#0-复评摘要)
- [1. 变化与交付](#1-变化与交付)
- [2. 已验证的改进（credit）](#2-已验证的改进credit)
- [3. 剩余问题（P1/P2）](#3-剩余问题p1p2)
- [4. C-029 准入评估](#4-c-029-准入评估)
- [5. 下一步任务执行建议](#5-下一步任务执行建议)
- [6. 防跑偏机制（R42–R46 建议）](#6-防跑偏机制r42r46-建议)
- [7. 评分卡](#7-评分卡)
- [8. 待拍板](#8-待拍板)
- [附录 A　证据索引与复现命令](#附录-a证据索引与复现命令)
- [附录 B　C-029 数字 vs artifact](#附录-bc-029-数字-vs-artifact)
- [附录 C　第八轮 P0/P1 逐项判定](#附录-c第八轮-p0p1-逐项判定)
- [附录 D　文档漂移清单（第三轮）](#附录-d文档漂移清单第三轮)

---

## 0. 复评摘要

### 0.1 三句话结论

1. **W5c 是项目至今质量最高的一轮。** R32 审计从 v6b 的 8 处违规降到 v6c 的 4 处（且 **exam 0 违规**，25 条 × 856 字段，rc=0）；R41 新闸抓出 2 条 dev 的 `length/width` 角色缺陷；契约试建闸证明 **gold 55/55 全可建**（C-028 的 3 条 contract 失败是模型问题，不是 builder 背锅）；SYS prompt 补键名后 **7 条未收敛 → 0**，50 条 3 轮 → 3 条 3 轮；C-029 的 92.0% 有 bridge 四格支撑，不是“模型突然变强”。
2. **C-029 的 exam 是干净的，剩余 2 条失败都是模型侧。** `cfrp45s_d40` 把 `layup` 写成标量 `2`（题面给了完整 `[45,-45,-45,45]`，SYS prompt 给了 schema）；`web1_offcentre` 写了 `extra.end_torque`/`torque_axis_dof` 自创键（prompt 明令禁止、gold 无此机制）。**卷子已无可解性缺陷；92.0% 不是又一个下界。**
3. **但“收口”还没完成。** README 仍把 C-028 当官方 headline、把 W5c 当“下一步”；C-021/C-025/C-026 仍写“正式对外 headline = C-021”；dev “真实可达 25/30”把“纸面修复后的投影”说成了“真实”；T1+ 没做；key 仍留在 git 历史。**这 4 个 P1 不影响 exam 数字，但影响对外叙事和下一轮的可信度。**

### 0.2 执行总评

| 工作块 | 评分 | 一句话判断 |
|---|---|---|
| W5c-0：R32/R41 审计 | **A** | v6b 8 → v6c 4；exam 0；1812 字段全分类；局限（筛查器非证明器）主动写明 |
| W5c-1：prompt 键名 + 契约试建 | **A** | 0 未收敛；4 一次通过 + 48 二次通过；gold 55/55 可建；NC-31/NC-37 |
| W5c-2：考卷 v6c | **A** | 只改 10 行；tag `v1.0-l3-v6c`；L1/L2 110 条与其余 45 条 L3 逐字节不变；exam 0 R32 |
| W5c-3：C-029 重打分 + bridge | **A−** | 23/25 92.0%；SFR 20/22；MSR 19/22；bridge 四格；**但 dev 25/30 是投影、MSR 别名有 null** |
| W5c-5：T1 公平地板 | **B+** | leave-one-out 做了（train 0/13，自命中 0）；**T1+ 仍 `null`**，value_added 仍是 0 地板 |
| W5c-6：证据/文档 | **B+** | 22/34/29、S-27、diagnostics 入库；**但 README/C-021/C-025/C-026 仍指向旧 headline** |
| **总体** | **A− / 27/30** | 基础设施 A；科学有效性 B+；**4 个 P1 是收口项，不是 exam 有效性问题** |

> **和第八轮 24/30 的关系**：W5c 把第八轮 8 个 P0 全部落地，分数从 24 回到 27；离 28+ 只差 headline 文档、T1+、dev 投影和 key 四个收口项。

---

## 1. 变化与交付

### 1.1 提交与 tag

| commit | 时间 | 内容 |
|---|---|---|
| `83bfc4d` | 21:30 | W5c 收口：C-029 证据链闭合（MSR 四行）+ 修两个口径 bug + 负控 39/39 |
| `b8bd3f0` | 19:50 | W5b-3/4：C-028（v6b × 55 条，exam 17/25） |
| `2e21370` | 18:38 | W5b-3c：v6 → v6b（内插全翼盒） |

**tag**：`v1.0-l3-v6c`（当前考卷）；`v1.0-l3-v6b`（历史卷）；`v1.0-l3-v6` / `v5` / `v4` 留档。

### 1.2 新增/修改的关键文件

| 文件 | 作用 |
|---|---|
| `feagpt_repro/reports/baseline_scorecard_L3_v6c.json` | C-029 官方成绩单（55 per_task + exam 三栏 + MSR 四行 + `exam_task_ids_sha256` + `turns_histogram` + `first_pass_valid` + `n_unresolved`） |
| `feagpt_repro/reports/bootstrap_ci_L3_v6c.json` | exam 25 / 三栏 / 四族 CI（B=4000, seed=20261025） |
| `feagpt_repro/reports/trivial_baselines_L3_v6c.json` | T0/T1/T2 地板（T1 leave-one-out；T1+ 未实现） |
| `feagpt_repro/reports/papers/tasks_v6c.jsonl` / `nl_human_v6c.jsonl` | v6c 考卷快照（165 行 / 55 条 L3；sha `9c1faa3a…`） |
| `feagpt_repro/candidates_l3_v6c/` | 55 条 v6c 候选（0 unresolved） |
| `feagpt_repro/r32_audit.py` + `reports/r32_audit_v6b_before.json` / `r32_audit_v6c.json` / `r32_audit_v6c_exam.json` | R32/R41 审计（v6b 8 → v6c 4；exam 0） |
| `feagpt_repro/audit_contract.py` + `reports/contract_audit_v6c.json` | 契约试建闸（gold 55/55 可建） |
| `feagpt_repro/reports/diagnostics/bridge_w5c_table.md` + B/C 成绩单 | bridge 四格（17 → 18 → 18 → 23） |
| `feagpt_repro/reports/diagnostics/w5b4_defect_analysis_v6b.md` | v6b 诊断分析（已从 `eval_runs/` 移入官方 diagnostics，R37） |
| `feagpt_repro/reports/negative_controls_39.json` | 负控 39/39（NC-30..37） |
| `feagpt_repro/reports/check_claims.json` | 22 active / 34 artifacts / 29 semantic 全过 |
| `feagpt_repro/gen_candidates.js` | **删除硬编码 fallback**，只读 env，缺 key 直接 rc=2 |
| `FEM-Bench-Aero/RUBRIC.md` | v4.5：R33–R41、§7.1 契约登记表、§7.2 blade 死字段、§7.3 R41、§7.4 契约试建闸 |

### 1.3 C-029 官方数字（逐项核对）

| 指标 | 值 | 说明 |
|---|---:|---|
| exam TSR | **23/25 = 92.0%** | CI95 [80.0, 100.0]；n=25 ⇒ `underpowered=False` |
| exam SFR | **20/22 = 90.9%** | 22 = 25 − 3 clarify |
| exam MSR | **19/22 = 86.4%** | 剔 solver **19/21 = 90.5%**；1 条 exam solver |
| 全链 MSR | **38/51 = 74.5%** | 剔 solver **38/47 = 80.9%**（`msr_excl_solver`） |
| dev TSR | 23/30 = 76.7% | 下界；见 §3.2 |
| dev MSR | 19/29 = 65.5% | 剔 solver 19/26 = 73.1%；3 条 dev solver |
| boundary | 6/6 = 100% | 分栏 n 小，只报不判 |
| extrapolation | 11/13 = 84.6% | 2 条失败都在此栏 |
| interpolation | 6/6 = 100% | |
| 三栏 CI | TSR [80,100] / SFR [77.3,100] / MSR [72.7,100] | bootstrap 4000 |
| T1 exam | 0/25 | leave-one-out；T1 train 0/13（旧版 12/13 全是自命中） |
| FPR | 编造 0/4、过度澄清 0、问错字段 0 | |
| turns | 1:4 / 2:48 / 3:3 | 一次通过 4/55 = 7.3%；未收敛 **0**（C-028 是 7） |
| exam 族构成 | 18 / 4 / 2 / 1 | wingbox / panel / barrel / stiffened |
| 失败 | 2 exam（model）+ 4 solver（1 exam + 3 dev） | 0 contract exam；0 unresolved |

### 1.4 覆盖与可复现

- **55/55 文件**，`candidates_missing=[]`、`partial_candidates=false`、`n_unresolved=0`。
- `provenance` = `tasks_path: reports/papers/tasks_v6c.jsonl`，`tasks_sha256: 9c1faa3a731f29369facf2eafce49c6c168fb7f12a28a55d85af971b58b063e5`，`candidates_dir: candidates_l3_v6c`，`n_candidates: 55`。
- `check_claims`：22 active / 34 artifacts / 29 semantic，`n_fail=0`，`all_ok=True`。
- `negative_controls_39.json`：39/39，含 NC-30（R33 两端）、NC-31（prompt 键名）、NC-32（T1 LOO）、NC-33（成绩单文案）、NC-34（不引 `eval_runs`）、NC-35（同条数≠同批题）、NC-36（语义项不静默消失）、NC-37（契约反向）。
- `compare_scorecards.py`：C-028 vs C-029 **rc=3**（同 25 id 但 paper sha 不同）；C-021 vs C-029 **rc=3**（11 vs 25、分层不同、sha 不同）。

---

## 2. 已验证的改进（credit）

| 改进 | 实测 |
|---|---|
| **R32 审计脚本化** | v6b 8 处 → v6c 4 处；**exam 0 违规**（25×856 字段，rc=0）；4 处全部是 2 条 dev 的 R41 `length/width` 角色；1812 字段全分类 |
| **prompt 键名表** | 开孔板 `hole_d/hole_x/hole_y`、`layup`、`ply_material` 等补齐；**未收敛 7 → 0**；50 条 3 轮 → 3 条 3 轮；2 条 2 轮 |
| **考卷 v6c** | 只改 10 行：4 条 R32（`str3_T` 缘条宽 + 3 条 web 腹板位置）+ 6 条 `split_v2 → interpolation_test`；L1/L2 110 条与其余 45 条 L3 逐字节不变；tag `v1.0-l3-v6c` |
| **C-029** | exam 23/25 (92.0%)、SFR 20/22 (90.9%)、MSR 19/22 (86.4%)、full 38/51 (74.5%)；三栏 6/6 · 11/13 · 6/6；`underpowered=False` |
| **bridge 四格** | A 17/25 → B 18/25（blade 死字段 +1，唯一翻转 `str5`）→ C 18/25（考卷修复对旧候选 +0）→ D 23/25（重生成 +5）；**92% 不是“模型变强 24pp”** |
| **契约试建闸** | `audit_contract.py` 把 gold 过同一道 R19 闸：**55/55 可建**；C-028 的 3 条 contract 失败是模型问题；NC-37 反向注入 `ply_material` 必 rc=1 |
| **R35 MSR 四行** | exam 19/22→19/21、dev 19/29→19/26、full 38/51→38/47（`msr_excl_solver`），`solver_in_exam`/`solver_in_dev` 归属；4 条 solver 全是柱壳 |
| **T1 leave-one-out** | train 12/13 自命中 → **0/13**；exam 0/25；`t1_leave_one_out=true`；NC-32 |
| **成绩单文案** | `note`/`exam_definition`/`value_added.basis` 由考卷生成；S-23 检查 `w4d=False` |
| **`split_v2` 根因** | 6 条 interp 改 `interpolation_test`；`by_split` 只含非 exam，train=13；S-24 |
| **证据纪律** | v6b 诊断分析移入 `reports/diagnostics/`；S-27 全部 active claim 路径被 git 追踪；无 `eval_runs` 引用 |
| **负控/自检** | 39/39；22/34/29；S-21..S-28；R33–R41；`compare_scorecards` rc=3 |
| **key 止血** | `gen_candidates.js` 删除硬编码 fallback，只读 env，缺 key 直接 rc=2；W5B_PLAN 记录“仍在 git 历史” |

---

## 3. 剩余问题（P1/P2）

### 3.1 P1：headline 文档仍指向旧版本（README / C-021 / C-025 / C-026）

这是本轮最明显的收口缺口：

| 位置 | 现文 | 应为 |
|---|---|---|
| `README.md` “看当前计划” | “对外 headline 现已切到 **C-028**：17/25 (68.0%)……下一步 = W5c” | **C-029：23/25 (92.0%)……下一步 = W5b-5 第二模型** |
| `README.md` “看基线成绩单” | “**官方 = baseline_scorecard_L3_v6b.json（C-028，exam 17/25）**” | **官方 = baseline_scorecard_L3_v6c.json（C-029，exam 23/25）**；C-028 = diagnostic |
| `CLAIMS.md` C-021 | “**正式对外 headline**” | 历史口径 / `superseded by C-029` |
| `CLAIMS.md` C-025 | “**正式对外 headline 仍是 C-021**” | C-029 当前；C-021 历史 |
| `CLAIMS.md` C-026 | “**官方 headline = C-021 v4 5/11**” | C-029 当前；C-028 diagnostic；C-021 历史 |
| `reports/INDEX.md` 第 110–111 行 | “19 条 active / 21 个 artifact”“31/31” | **22 / 34 / 39**（顶部已更新，这两行是旧账） |
| `W5B_PLAN.md` 第 79 行 | `check_claims` “**28 项**” | **29 项**（S-00..S-28） |

- **后果**：读者从 README 进入，会以为官方仍是 68.0%，而 INDEX/CLAIMS 的 C-029 是 92.0%；`check_claims` 的 29 项语义检查**没有一条**检查“当前 headline 是否唯一”，所以 22 条 active 全过。
- **建议**：W5c-6b 统一更新 README/C-021/C-025/C-026，并加 **S-29：恰好一条 active claim 标注“对外 headline”，且必须是 C-029**；C-021/C-025/C-026 标 `historical`/`superseded`/`diagnostic`。

### 3.2 P1：dev “真实可达 25/30” 是纸面修复后的投影，不是实测

- C-029 写：“dev TSR 23/30（**下界**）……**真实可达 25/30**”；`bridge_w5c_table.md` 同样写“dev 23/30 记为下界，真实可达 25/30”。
- 但 dev 的 7 条 spec_fail 实际是：

| 类型 | 条数 | 任务 | 性质 |
|---|---:|---|---|
| R41 数值角色 | 2 | `stiffened_panel_800x600`、`_str3` | **卷子缺陷**；修模板后可回收 |
| 模型侧 | 5 | `web1`、`web2`（`extra.end_torque`/`torque_axis_dof` 自创键）；`cfrp090s`、`cfrpqi`（`layup`）；`cfrp45s`（`layup` + `material.E1/E2` 自创） | **模型失败**；修卷子不会自动变对 |

- **25/30 的真实含义**：把 2 条 R41 修掉后的 dev TSR，**5 条模型失败仍然失败**。它不是“模型真实可达 25/30”，而是“卷子干净时的 dev 投影”；当前实测仍是 **23/30**。
- **建议**：C-029/bridge 改成“dev 23/30 实测；paper-clean 投影 25/30（2 条 R41 修掉后）；5 条模型侧失败仍在”；不要把 25/30 当实测或能力上限。若要回收，开 v6d 重生成 2 条 dev 候选（exam 收益 0，成本约 3h）或明确只做诊断。

### 3.3 P1：T1+ 仍是 `null`，value_added 仍是对着 0 地板

- `trivial_baselines_L3_v6c.json`：`t1_leave_one_out=true`，T1 train **0/13**、exam **0/25**、all **0.0%**；`T1plus_family=null`。
- 第八轮 D4 建议的“train leave-one-out + family-mode T1+”只完成了前半；exam T1 仍是 0/25，C-029 的 value_added 92.0pp 是对着 0 地板，**技术上 PASS、科学上不硬**。
- **建议**：W5c-5b 加 family-mode T1+（或 per-family T1）并重算 value_added；若短期不做，C-029 应明确写“value_added 的技术对照是 0/25，不构成强证据”，不要把 Δ92pp 当核心卖点。

### 3.4 P1：key 只止血未轮换

- `gen_candidates.js` 的硬编码 fallback 已删（credit），但 W5B_PLAN 自己写明：**key 仍在 git 历史（commit `efa2b6f`）**；当前判断是“publishable、无权限语义、服务端 Origin 校验 ⇒ 可接受”。
- W5B_PLAN 说“真正消除须重建应用 + 轮换 ⇒ endpoint 变 ⇒ 所有 artifact 的 provenance 要重签，代价高”。**这个成本判断值得复核**：轮换 publishable key 未必需要改 endpoint；若 endpoint 不变，provenance 不需要重签。即使需要重建应用，也应把“轮换”与“endpoint 变更”拆开评估，而不是直接归为“代价高、可接受”。
- **建议**：D5-b 重新评估一次“只轮换 key、endpoint 不变”的可行性；若可行，轮换并把旧 key 从历史中视为已失效；若不可行，明确接受风险并记录决策人/日期。

### 3.5 P2：MSR 别名字段为 `null`（数据在，但命名不一致）

- `msr_section` 的 `msr_excl_solver = 38/47 (80.9%)` **存在**，C-029 的 full 剔除口径有据；但 `full_msr_excl_solver` / `full_msr_excl_solver_pct` 是 `null`，`dev_msr_pct` 也是 `null`（`dev_msr` 19/29 存在，65.5% 可手算）。
- 这不影响 C-029 的数字，但会让读者按字段名找不到“full 行”；`check_claims` S-19 只核对 `msr` 38/51，不核对 `msr_excl_solver`/`dev_msr_pct`。
- **建议**：要么把 `full_msr_excl_solver` 设为 `msr_excl_solver` 的别名并补 `dev_msr_pct`，要么删掉未用别名；加 S-30 检查 `msr_excl_solver`/`exam_msr_excl_solver`/`dev_msr_excl_solver` 非空。

### 3.6 P2：一次通过率 4/55、2 轮 48、3 轮 3

- C-029 的 92.0% 是在 **2 轮 schema 修复**后取得的；一次通过率仍 7.3%。修复循环是协议的一部分，C-029 也如实报告 turns，但：
  - 第二模型必须用**同样的 ≤3 轮预算**，否则不可比；
  - 3 条 3 轮任务全在 dev（`cfrp090s`、`stiffened_800x600_str3` 等），exam 的 2 条失败是 2 轮——exam 的 92% 不是“3 轮硬修出来的”；
  - 建议把 `first_pass_valid` / `turns_histogram` / `n_unresolved` 作为固定字段（已做），并在第二模型报告里并列。
- **不是缺陷，是可比性约束**。

### 3.7 P2：92.0% 的 CI [80,100] 很宽、族级 n<10

- n=25 是 R12 的最低线；CI 宽 20pp；族级 n：wingbox 18、panel 4、barrel 2、stiffened 1，全部 <10；`exam_by_family` 只能报不能判。
- 92.0% 是“headline 可判”，不是“四族都可判”；对外只能写“exam 25 条 23/25，CI [80,100]”，不能写“模型在四族都达到 92%”。
- **建议**：v1.1 新几何（W5B 路径 B）优先于继续挖 L3；n≥30 才能让族级 CI 有意义。

### 3.8 P2：INDEX/W5B_PLAN 仍有旧计数

- `INDEX` 第 110–111 行“19 active / 21 artifact”“31/31”；`W5B_PLAN` 第 79 行“28 项”；当前是 **22 / 34 / 29 / 39**。
- 这些是收口文档的旧账，不影响 artifact；建议 W5c-6b 一并改，并加 S-29（headline 唯一）/S-30（MSR 别名）后重跑 `check_claims`。

### 3.9 P2：旧负控文件 31/37 仍在 reports/

- `negative_controls_31.json`、`negative_controls_37.json`、`negative_controls_39.json` 三份并存；C-019 指向 39；INDEX 顶部指向 39；旧的两份是历史。建议在 INDEX 标“历史”，或移到 `reports/archive/`；不要让读者以为 31 是当前。

### 3.10 不是问题的部分（避免过度纠偏）

- C-029 的 exam 23/25、SFR 20/22、MSR 19/22、三栏 6/6·11/13·6/6、FPR 0/4、0 未收敛、R32 exam 0、contract 55/55、bridge 四格、39/39、22/34/29、compare rc=3——都是真的，不需要重做。
- C-028 的降级、C-021 的历史化、bridge 的“B→C=0”、solver 桶的“候选相关”——都是主动披露，方向正确；本轮是**补收口**，不是推翻。
- 2 条 exam 失败是模型侧；不要为了“好看”改判据；92.0% 已经是“卷子干净”的成绩。

---

## 4. C-029 准入评估

### 4.1 Go / No-Go

| 条件 | 现状 | 结论 |
|---|---|---|
| exam R32/R41 0 违规 | `r32_audit_v6c_exam` 25×856，rc=0 | ✅ |
| gold 全可建 | `contract_audit_v6c` 55/55 | ✅ |
| 候选 0 未收敛 | `n_unresolved=0` | ✅ |
| 剩余 exam 失败全为模型侧 | 2 条（layup 标量、自创 extra 键） | ✅ |
| 涨幅可拆解 | bridge 17→18→18→23 | ✅ |
| 跨口径闸 | C-028/C-021 vs C-029 rc=3 | ✅ |
| 负控/自检 | 39/39；22/34/29 | ✅ |
| headline 文档唯一 | **README/C-021/C-025/C-026 仍指旧** | ❌ P1 |
| dev 25/30 实测 | **投影，5 条模型失败仍在** | ❌ P1 |
| T1+ | **`null`** | ❌ P1 |
| key 轮换 | **仅删 fallback；历史仍在** | ❌ P1 |

**判定：C-029 可以作为当前官方 headline（exam 有效性成立），但 4 个 P1 必须在本轮收口；在收口前，对外引用只写“exam 23/25 (92.0%)，CI [80,100]，2 条失败为模型侧”，不要写“能力上限/四族 92%/dev 25/30/value_added 强证据”。**

### 4.2 C-029 能说什么 / 不能说什么

| 可以说 | 不能说 |
|---|---|
| exam 25 条 TSR 23/25 (92.0%)，CI95 [80.0, 100.0] | “模型能力 92%”/“四族都 92%” |
| 三栏 6/6 · 11/13 · 6/6，分栏 n 小只报不判 | “extrapolation 也达到 100%” |
| SFR 20/22；MSR 19/22（剔 solver 19/21） | “全链 92%” |
| 与 C-028/C-021 不可相减；bridge 拆为 +1 判分 +5 重生成 | “模型从 68% 提升到 92%”/“从 45.5% 提升到 92%” |
| 2 条剩余失败是模型侧（layup 标量、自创 extra 键） | “卷子还有缺陷” |
| dev 23/30 实测；paper-clean 投影 25/30，5 条模型失败仍在 | “dev 真实 25/30” |
| T1 0/25 是公平但很弱的地板；T1+ 待做 | “value_added 92pp 证明模型强” |

---

## 5. 下一步任务执行建议

### 5.1 W5c 收口 + W5b-5 任务表

| ID | 优先级 | 做什么 | 验收 | 证据 |
|---|---|---|---|---|
| **W5b-5** | **P0** | **第二模型（v6c）**：先用 SDK 实测可用 id；同 `tasks_v6c`、同 SYS prompt、同 `--max-turns 3`；生成 55 条；score + msr + bootstrap | 两模型同卷同预算；各自 CI；差异有 bridge/诊断；不混入 C-029 | 新候选目录 + 诊断成绩单；C-031 |
| **W5c-6b** | **P1** | **headline/证据收口**：README（两处）、C-021/C-025/C-026 状态、INDEX 110–111、W5B 79；`full_msr_excl_solver`/`dev_msr_pct` 别名；加 S-29/S-30/S-31；重跑 check_claims/负控 | 所有当前文档只指 C-029；22/34/**32**；39/39；无旧 headline | `check_claims.json`；README/CLAIMS/INDEX |
| **W5c-5b** | **P1** | **T1+ family-mode / per-family**：在 v6c 上重算 value_added；T1+ 非 null | T1+ 有数；value_added 不再对 0 地板；C-029 更新或加注 | `trivial_baselines_L3_v6c.json`；NC-38 |
| **W5c-6c** | **P1** | **dev 25/30 口径**：改成“23/30 实测 + paper-clean 25/30 投影 + 5 条模型失败仍在”；若要回收 2 条 dev，开 v6d 重生成或明确不做 | C-029/bridge 文本一致；不把 25/30 当实测 | C-029；bridge 表 |
| **W5c-6d** | **P2** | **key 轮换评估**：只换 key、endpoint 不变是否可行；可行则轮换；不可行则记录接受决策 | D5-b 有结论/日期/决策人 | W5B_PLAN §6.0 |
| **W5d** | **P2** | **榜单/协议/第三方复现**：两模型 + 三栏 + CI + 失败分层；外部复现脚本 | W5d 协议 | 后续 |
| **v1.1** | **P2** | **新几何 6–10 条**（W5B 路径 B）：扩 exam 精度；不混判据 | n≥30；族级 CI 有意义 | 后续 |

### 5.2 顺序建议

```text
W5b-5 第二模型 ────────────────┐
                               ├──► W5d 榜单/协议
W5c-6b headline/证据收口 ──────┤
W5c-5b T1+ ────────────────────┤
W5c-6c dev 25/30 口径 ─────────┘
                               │
                               ▼
                        v1.1 新几何（下一里程碑）
```

**为什么先跑 W5b-5**：C-029 的 exam 已经干净，第二模型是当前科学价值最高的一步；headline 收口是文档工作，可以并行，不阻塞第二模型。T1+ 和 dev 口径是 C-029 的注脚，不改变 exam 数字。

### 5.3 成本估计

- W5b-5：生成 16–30 分钟 + MSR 25–40 分钟 + 打分/CI 几分钟；主要是等。
- W5c-6b：0.5 天（文档 + 2 个语义检查 + 重跑）。
- W5c-5b：0.5 天（T1+ 实现 + 重算）。
- W5c-6c：0.2 天（文本）；若开 v6d 重生成 2 条 dev，约 3h。
- **总计约 1.5–2 天**（不含 W5d/v1.1）。

---

## 6. 防跑偏机制（R42–R46 建议）

> R1–R41 保留；以下为第九轮建议新增，待拍板后写入 RUBRIC。

| 红线 | 内容 | 触发点 |
|---|---|---|
| **R42** | **当前 headline 唯一**：恰好一条 active claim 标注“对外 headline”，且必须是当前版本；旧 headline 必须标 `historical`/`superseded`/`diagnostic` | W5c-6b；S-29；NC-38 |
| **R43** | **dev/投影不得冒充实测**：任何“可达/预计/paper-clean”数字必须与实测并列并标注“投影”；dev 不得进对外 headline | W5c-6c；S-30 |
| **R44** | **T1+ 必须非空**：value_added 的对照地板必须是 leave-one-out + family-mode（或 per-family）；T1+ 为 `null` 时 value_added 只能标“技术 PASS，证据弱” | W5c-5b；NC-39 |
| **R45** | **MSR 别名必须一致**：`msr_excl_solver`/`exam_msr_excl_solver`/`dev_msr_excl_solver` 必须有数；`full_msr_excl_solver`/`dev_msr_pct` 要么补数要么删除；不得靠手算进 claim | W5c-6b；S-31 |
| **R46** | **key 轮换决策留痕**：删 fallback 只止血；是否轮换、endpoint 是否变、provenance 是否重签，必须有决策记录 | W5c-6d |

**新增语义检查（S-29..S-31）建议：**

| ID | 检查 | 期望 |
|---|---|---|
| S-29 | active claim 中“对外 headline”标注 | 恰好 1 条 = C-029；C-021/C-025/C-026/C-028 为历史/诊断 |
| S-30 | C-029 的 dev 25/30 | 必须与“23/30 实测 / paper-clean 25/30 / 5 条模型失败”同现 |
| S-31 | `msr_section` 四行 | `exam_msr`/`exam_msr_excl_solver`/`dev_msr`/`dev_msr_excl_solver`/`msr`/`msr_excl_solver` 全非空 |

---

## 7. 评分卡

> **第八轮 24/30 是 W5b 的实测低谷；第九轮 27/30 是 W5c 修复后的实测。** 4 个 P1 是收口项，不是 exam 有效性问题。

| # | 维度 | 第七轮 | 第八轮 | 第九轮 | 依据 |
|---|---|---:|---:|---:|---|
| 1 | 目标一致性 | 3 | 3 | **3** | 评测基础设施主轴不变；W5c 按计划 |
| 2 | 任务有效性 | 3 | 2 | **3** | exam R32/R41 0 违规；4 条 R41 全在 dev；exam 25 全可解 |
| 3 | 判分有效性 | 3 | 2 | **3** | R35 四行、R33–R41、39/39；blade 死字段是 post-hoc 但有代码/check_forms 依据 |
| 4 | 证据等级 | 3 | 2 | **3** | 22/34/29；bridge；R32/contract 审计；diagnostics 入库；别名 null 是 P2 |
| 5 | 可复现性 | 3 | 3 | **3** | v6c tag；C-029 命令；0 未收敛；compare rc=3 |
| 6 | 版本治理 | 3 | 2 | **2** | v6c tag 有；README/C-021/C-025/C-026/INDEX/W5B 仍指旧 headline |
| 7 | 文档真实性 | 3 | 2 | **2** | C-029 主动披露 bridge/缺陷；但 README 旧、dev 25/30 投影、T1+ 弱 |
| 8 | 统计有效性 | 1 | 2 | **2** | n=25、CI 落地；但 CI [80,100] 宽、族 n<10、T1 0/25 |
| 9 | 范围纪律 | 3 | 3 | **3** | 没混新几何/新判据；bridge 单变量；R30/R39 |
| 10 | 计划执行 | 3 | 3 | **3** | W5c-0..6 全落地；39/39；22/34/29 |
| **总分** | | **28/30** | **24/30** | **27/30** | 基础设施 A；科学有效性 B+；4 个 P1 收口后回到 28–29 |

**一句话**：**W5c 把“评测器自己挖的坑”填平了，C-029 的 92.0% 是可信的卷面成绩；但“可信的成绩”和“干净的对外叙事”之间还差 4 个收口项——headline 文档、dev 投影、T1+、key。**

---

## 8. 待拍板

| # | 决策 | 选项 | 建议 |
|---|---|---|---|
| **D1** | **C-029 的官方 headline 地位** | (a) 作为当前官方 headline（带 4 个 P1 caveat）；(b) 等 4 个 P1 全部收口后再切 | **(a)**；exam 有效性已成立；4 个 P1 是文档/地板，不是数字 |
| **D2** | **dev 25/30** | (a) 标“23/30 实测 + paper-clean 25/30 投影 + 5 条模型失败仍在”；(b) 开 v6d 重生成 2 条 dev 回收 | **(a)**；exam 收益 0；dev 只作诊断；若将来用 dev 做结论，再开 v6d |
| **D3** | **T1+ 时机** | (a) 现在做 family-mode/per-family T1+；(b) 等第二模型后 | **(a) 并行**；value_added 当前对 0 地板，不补就一直是弱证据 |
| **D4** | **W5b-5 第二模型** | (a) 现在跑 v6c；(b) 等收口后 | **(a)**；C-029 exam 已干净；同 prompt/同 ≤3 轮即可比 |
| **D5** | **key 轮换** | (a) 重新评估“只换 key、endpoint 不变”，可行则轮换；(b) 接受现状并记录 | **(a)**；先把“轮换”和“endpoint 变更”拆开算，再决定 |
| **D6** | **headline 收口** | (a) 本轮 W5c-6b 一次改完 README/C-021/C-025/C-026/INDEX/W5B + S-29/S-30；(b) 留给 W5d | **(a)**；现在有 5 个入口指向旧 headline，越晚越乱 |

---

## 附录 A　证据索引与复现命令

### A.1 官方 artifact

| 文件 | 用途 |
|---|---|
| `feagpt_repro/reports/baseline_scorecard_L3_v6c.json` | C-029 官方成绩单（55 per_task + exam 三栏 + MSR + `exam_task_ids_sha256` + `turns_histogram`） |
| `feagpt_repro/reports/bootstrap_ci_L3_v6c.json` | TSR/SFR/MSR CI + by_family + by_stratum |
| `feagpt_repro/reports/trivial_baselines_L3_v6c.json` | T0/T1/T2（T1 LOO；T1+ null） |
| `feagpt_repro/reports/papers/tasks_v6c.jsonl` / `nl_human_v6c.jsonl` | v6c 考卷快照（sha `9c1faa3a…`） |
| `feagpt_repro/reports/r32_audit_v6c_exam.json` | exam 25×856，0 违规 |
| `feagpt_repro/reports/r32_audit_v6c.json` | all 55×1812，4 违规（2 dev R41） |
| `feagpt_repro/reports/contract_audit_v6c.json` | gold 55/55 可建 |
| `feagpt_repro/reports/diagnostics/bridge_w5c_table.md` + B/C json | bridge 17/18/18/23 |
| `feagpt_repro/reports/negative_controls_39.json` | 39/39 |
| `feagpt_repro/reports/check_claims.json` | 22/34/29 |

### A.2 复现命令

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# 1) R32/R41 审计（exam 必须 rc=0）
"$PY" r32_audit.py --tasks reports/papers/tasks_v6c.jsonl --scope exam \
  --out reports/r32_audit_v6c_exam.json
"$PY" r32_audit.py --tasks reports/papers/tasks_v6c.jsonl --scope all \
  --out reports/r32_audit_v6c.json

# 2) 契约试建闸（gold 55/55）
"$PY" audit_contract.py --tasks reports/papers/tasks_v6c.jsonl \
  --out reports/contract_audit_v6c.json

# 3) T1/T0/T2 地板
"$PY" trivial_baselines.py --levels L3 --tasks reports/papers/tasks_v6c.jsonl \
  --out reports/trivial_baselines_L3_v6c.json

# 4) C-029 打分 + MSR + CI
"$PY" score_baseline.py --candidates candidates_l3_v6c \
  --tasks reports/papers/tasks_v6c.jsonl \
  --report reports/baseline_scorecard_L3_v6c.json \
  --trivial reports/trivial_baselines_L3_v6c.json \
  --label "C-029 v6c (paper v6c, candidates v6c)"
"$PY" msr_l3.py --candidates candidates_l3_v6c \
  --tasks reports/papers/tasks_v6c.jsonl \
  --report reports/baseline_scorecard_L3_v6c.json
"$PY" bootstrap_ci.py --scorecard reports/baseline_scorecard_L3_v6c.json \
  --out reports/bootstrap_ci_L3_v6c.json

# 5) bridge B/C
"$PY" score_baseline.py --candidates candidates_l3_v6 \
  --tasks reports/papers/tasks_v6b.jsonl \
  --report reports/diagnostics/bridge_w5c_B_v6b_oldcand.json
"$PY" score_baseline.py --candidates candidates_l3_v6 \
  --tasks reports/papers/tasks_v6c.jsonl \
  --report reports/diagnostics/bridge_w5c_C_v6c_oldcand.json

# 6) 自检
"$PY" compare_scorecards.py --a reports/baseline_scorecard_L3_v6b.json \
  --b reports/baseline_scorecard_L3_v6c.json      # 必须 rc=3
"$PY" compare_scorecards.py --a reports/baseline_scorecard_L3_v4.json \
  --b reports/baseline_scorecard_L3_v6c.json      # 必须 rc=3
"$PY" check_claims.py
"$PY" negative_controls.py
```

---

## 附录 B　C-029 数字 vs artifact

| 指标 | C-029 文本 | 成绩单字段 | 一致？ |
|---|---|---:|---|
| exam TSR | 23/25 (92.0%) | `exam.tsr` 23/25 | ✅ |
| exam SFR | 20/22 (90.9%) | `exam.sfr` 20/22 | ✅ |
| exam MSR | 19/22 (86.4%) | `msr_section.exam_msr` 19/22 | ✅ |
| exam MSR 剔 solver | 19/21 (90.5%) | `exam_msr_excl_solver` 19/21 | ✅ |
| dev TSR | 23/30 (76.7%) | `dev.tsr` 23/30 | ✅ |
| dev MSR | 19/29 (65.5%) | `dev_msr` 19/29；`dev_msr_pct=null` | ⚠️ 19/29 = 65.5 可手算，但 pct 字段未写 |
| dev MSR 剔 solver | 19/26 (73.1%) | `dev_msr_excl_solver` 19/26 | ✅ |
| full MSR | 38/51 (74.5%) | `msr` 38/51 | ✅ |
| full MSR 剔 solver | 38/47 (80.9%) | `msr_excl_solver` 38/47；`full_msr_excl_solver=null` | ⚠️ 数据在别名下 |
| 三栏 | 6/6 · 11/13 · 6/6 | `exam_by_stratum` | ✅ |
| solver | 1 exam + 3 dev | `solver_in_exam` 1 / `solver_in_dev` 3 | ✅ |
| 未收敛 | 0 | `n_unresolved=0` | ✅ |
| turns | 1:4 / 2:48 / 3:3 | `turns_histogram` | ✅ |
| first pass | 4/55 | `first_pass_valid=4` | ✅ |
| T1 | 0/25；train 0/13 | `trivial_baselines` T1 | ✅ |
| T1+ | — | `T1plus_family=null` | ❌ 未实现 |
| dev 25/30 | “真实可达” | 无字段；23/30 实测 | ❌ 投影 |

### B.1 dev 7 条 spec_fail 的拆分

| task_id | 失败字段 | 性质 |
|---|---|---|
| `L3_naca4412_wingbox_web1` | `extra.end_torque`、`extra.torque_axis_dof` | 模型侧（自创键） |
| `L3_naca4412_wingbox_web2` | 同上 | 模型侧 |
| `L3_open_hole_panel_400x200_d20_cfrp090s` | `params.layup` | 模型侧 |
| `L3_open_hole_panel_400x200_d20_cfrp45s` | `params.layup` + `material.name/youngs_modulus/poisson_ratio` + `material.E1/E2 (not in gold)` | 模型侧 |
| `L3_open_hole_panel_400x200_d20_cfrpqi` | `params.layup` | 模型侧 |
| `L3_stiffened_panel_800x600` | `params.length`、`params.width` | **R41 卷子** |
| `L3_stiffened_panel_800x600_str3` | `params.length`、`params.width` | **R41 卷子** |

**⇒ 2 条卷子 + 5 条模型；paper-clean 25/30 只回收 2 条，5 条模型失败仍在。**

---

## 附录 C　第八轮 P0/P1 逐项判定

| 第八轮项 | 第九轮状态 | 证据 |
|---|---|---|
| W5c-0 R32 审计 | ✅ | `r32_audit_v6c_exam` 0；`r32_audit_v6c` 4（2 dev R41） |
| W5c-1 prompt 键名 + 契约 smoke | ✅ | 0 unresolved；gold 55/55；NC-31/NC-37 |
| W5c-2 v6c 冻结 | ✅ | 10 行；tag `v1.0-l3-v6c`；`_verify_tasks_v6c` PASS |
| W5c-3 重生成 + 重打分 + C-029 | ✅ | 23/25；SFR 20/22；MSR 19/22；bridge |
| W5c-4 第二模型 | ⏳ | 未跑；W5b-5 下一步 |
| W5c-5 T1+ | ⚠️ 部分 | LOO 做了；T1+ null |
| W5c-6 口径/证据 | ⚠️ 部分 | 22/34/29、S-27；README/C-021/C-025/C-026 旧 |
| W5c-7 负控 39 | ✅ | 39/39 |
| W5c-8 v1.1 新几何 | ⏳ | 未开 |
| key fallback | ✅ 删除 | `gen_candidates.js` env-only；历史仍未轮换 |
| C-021/C-028 状态 | ⚠️ | C-028 diagnostic；C-029 headline；C-021/C-025/C-026 仍写旧 |
| dev 25/30 | ❌ | 投影；5 条模型失败仍在 |
| MSR 四行 | ⚠️ | `msr_excl_solver` 38/47；`full_msr_excl_solver`/`dev_msr_pct` null |
| headline 文档 | ❌ | README 两处 + C-021/C-025/C-026 + INDEX 110–111 + W5B 79 |

---

## 附录 D　文档漂移清单（第三轮）

| # | 位置 | 现文 | 应为 |
|---|---|---|---|
| 1 | `README.md` “看当前计划” | C-028 68.0%；下一步 W5c | C-029 92.0%；下一步 W5b-5 |
| 2 | `README.md` “看基线成绩单” | 官方 = v6b C-028 | 官方 = v6c C-029；C-028 diagnostic |
| 3 | `CLAIMS.md` C-021 | “正式对外 headline” | 历史口径 / superseded by C-029 |
| 4 | `CLAIMS.md` C-025 | “正式对外 headline 仍是 C-021” | C-029 当前；C-021 历史 |
| 5 | `CLAIMS.md` C-026 | “官方 headline = C-021 v4 5/11” | C-029 当前 |
| 6 | `reports/INDEX.md` 110–111 | 19 active / 21 artifact；31/31 | 22 / 34 / 39 |
| 7 | `W5B_PLAN.md` 79 | 28 项 | 29 项（S-00..S-28） |
| 8 | `CLAIMS.md` C-029 | dev “真实可达 25/30” | 23/30 实测；paper-clean 25/30 投影；5 条模型失败仍在 |
| 9 | `bridge_w5c_table.md` | dev “真实可达 25/30” | 同上 |
| 10 | `RUBRIC.md` §6 | “套件 = 31 条”开头 | 当前 39 条（后文已写 39，开头旧） |

---

> **本轮只读核对；除本文件外未改动任何项目文件。**
> 下一轮复评入口：W5b-5 第二模型的诊断/官方成绩单 + W5c-6b headline 收口；C-029 的 exam 数字可以引用，但对外叙事必须先完成这 4 个 P1。
