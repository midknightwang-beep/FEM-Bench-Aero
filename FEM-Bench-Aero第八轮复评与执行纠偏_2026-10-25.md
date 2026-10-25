# FEM-Bench-Aero 第八轮复评与执行纠偏（W5b-3b/3c/4 后）

> **复评日期**：2026-10-25（第八轮）
> **复评对象**：W5b-0（key 打通）、W5b-3b（T1 检索泄漏修正）、W5b-3c（考卷 v6 → v6b）、W5b-3/4（55 条候选 + C-028）
> **复评方式**：只读核对 + 官方 artifact 交叉检查（成绩单 / 考卷 / 候选 / CLAIMS / RUBRIC / INDEX / W5B_PLAN）+ 字段级重算；**除本文件外未改动任何项目文件**
> **结论先行**：
> **W5b 全链跑通了，C-028 是项目第一个 exam n≥20 的官方 headline（17/25 = 68.0%，CI95 [48.0, 84.0]）；但它不是可对外发布的干净成绩，而是“含已知缺陷的下界”。**
> 8 条 exam 失败中：**2 条是考卷 R32 不可解**（gold 有 `stringer_flange_width`、题面没给）、**4 条是生成器 SYS prompt 未列开孔板键名**、**1 条是模型侧腹板位置/多余键**、**1 条是生成器 3 轮未收敛**。另有 **4 条 TSR 通过但全链 MSR 失败**（3 条试建闸 contract + 1 条 barrel pipeline）。
> **exam MSR 47.6% 不含任何 solver 失败**（3 条 solver OOM 全在 dev，只影响全链 56.8%），所以 47.6% 是真实的模型/契约失败，不是算力压低。**T1 的 train 12/13 全部是自检索**（`T1_nn == task_id`），value_added 唯一公平的对照是 exam T1 0/25——技术上是 PASS，但地板是稻草人。
> **v6 → v6b 只改了 8 条 `exam_stratum` 标签，题面零改动；但 exam 族构成从 14/6/3/2 变成 18/4/2/1（翼盒占 72%），C-028 没披露这个第三变量。**
> **判定：W5c 先修 R32/prompt/`split_v2`/scorecard 口径，重生成 55 条、重打分、再换第二模型；C-028 冻结为 known-defect lower bound，不作为最终对外 headline。**

---

## 目录

- [0. 复评摘要](#0-复评摘要)
- [1. 变化与交付](#1-变化与交付)
- [2. 已验证的改进（credit）](#2-已验证的改进credit)
- [3. 新发现的问题](#3-新发现的问题)
- [4. W5b-5 与 W5c 准入评估](#4-w5b-5-与-w5c-准入评估)
- [5. 下一步任务执行建议](#5-下一步任务执行建议)
- [6. 防跑偏机制（R33–R40 建议）](#6-防跑偏机制r33r40-建议)
- [7. 评分卡](#7-评分卡)
- [8. 待拍板](#8-待拍板)
- [附录 A　证据索引与复现命令](#附录-a证据索引与复现命令)
- [附录 B　失败矩阵与 v6→v6b 差异](#附录-b失败矩阵与-v6v6b-差异)
- [附录 C　语义漂移清单（第二轮）](#附录-c语义漂移清单第二轮)

---

## 0. 复评摘要

### 0.1 三句话结论

1. **W5b 跑通了，基础设施是 A。** key 打通 → 55/55 候选（44 spec + 4 clarify + 7 unresolved，0 error，16 分 13 秒）→ 成绩单 + 三栏 CI + 负控 31/31 + `check_claims` 20 条 active / 24 个 artifact / 21 项语义检查全过；C-028 的 17/25、CI [48.0, 84.0]、`underpowered=False` 都是真的。
2. **但 C-028 是“含缺陷的下界”，不是能力上限。** 8 条 exam 失败里：2 条考卷 R32 不可解、4 条 prompt 键名缺失、1 条模型侧腹板/多余键、1 条未收敛；另有 4 条 TSR 通过但全链 MSR 失败。68.0% 只能作为 **known-defect lower bound** 引用；**但也不能把 8 条全算成卷子/prompt 错——C/D 是模型侧，需一次受控的 prompt 修复实验来拆分。**
3. **下一步不是发榜，而是 W5c 修复 + 重冻结 + 重生成。** 先做 R32 全量审计与 prompt 键名表，再改题面/`split_v2` 冻结 v6c，重生成 55 条并重打分；第二模型可以现在做**诊断**，官方对比必须等 v6c。

### 0.2 执行总评

| 工作块 | 评分 | 一句话判断 |
|---|---|---|
| W5b-0：key 打通 | **A** | setx + 1 条冒烟 + 55 条全量；key 只走 env，产物齐全 |
| W5b-3b：T1 检索泄漏 | **A−** | exam 内插题“检索到自己”已修；**train 自检索仍在**（12/12 自命中） |
| W5b-3c：v6 → v6b | **B+** | 只改 8 条 `exam_stratum` 标签、题面零改动；理由（T1 四族地板）成立；**族构成代价未进 C-028** |
| W5b-4：C-028 | **B** | 首个 n≥20 headline；但 8 条失败含 3 类系统性缺陷；成绩单 `exam_definition`/`value_added.basis` 仍是 W4d 口径；证据链引了未追踪文件 |
| W5b-6：字段级归因 | **B−** | 探针脚本可用；分析落在 gitignore 的 `eval_runs/`；“没有一条是模型能力不足”是过度归因；A/C 两类有重叠 |
| **总体** | **B / 24/30** | 基础设施 A；科学有效性 C+；**对外发布 No-Go，W5c 修复后再评** |

> **和第七轮 28/30 的关系**：第七轮的 28 是**纸面审计分**（W5b 还没跑）；第八轮的 24 是**实测分**。统计有效性从 1 升到 2，但任务/判分/证据/版本/文档各掉 1——不是工作退步，是第一次真跑把纸面缺口打出来了。24 → 28 的路径就是 W5c。

---

## 1. 变化与交付

### 1.1 提交与 tag

| commit | 时间 | 内容 |
|---|---|---|
| `36e700b` | 18:33 | W5b-3b：修 T1 检索库泄漏（内插考题 `split_v2` 仍是 train）+ v6 三栏地板 + 三栏 CI |
| `2e21370` | 18:38 | W5b-3c：考卷 v6 → v6b（内插 6 条全给翼盒）— 四族 T1 地板可算 |
| `69c69aa` | 18:39 | 记忆：v6b + T1 检索泄漏 + train 池必须剔 `exam_stratum` |
| `b8bd3f0` | 19:50 | W5b-3/4 收口：C-028 = v6b 考卷 × 55 条候选，exam TSR 17/25 (68.0%) |

**tag**：`v1.0-l3-v6b`（当前考卷）；`v1.0-l3-v6` / `v1.0-l3-v5` / `v1.0-l3-v4` 保留历史。

### 1.2 新增/修改的关键文件

| 文件 | 作用 |
|---|---|
| `feagpt_repro/reports/baseline_scorecard_L3_v6b.json` | C-028 官方成绩单（55 条 per_task + exam 三栏 + MSR） |
| `feagpt_repro/reports/bootstrap_ci_L3_v6b.json` | exam 25 / 三栏 / 四族 bootstrap CI（B=4000, seed=20261025） |
| `feagpt_repro/reports/trivial_baselines_L3_v6b.json` | v6b 地板（T0 0/25、T1 0/25、T2 25/25） |
| `feagpt_repro/reports/papers/tasks_v6b.jsonl` / `nl_human_v6b.jsonl` | v6b 考卷快照（165 行 / 55 条 L3） |
| `feagpt_repro/candidates_l3_v6/` | 55 条候选（由 v6b 考卷生成；**目录名仍叫 v6，不是 v6b**） |
| `feagpt_repro/_probe_w5b4_fail_fields.py` | 字段级失败探针（可复跑） |
| `feagpt_repro/_probe_interp_w5b3b.py` | 内插名额方案对比探针 |
| `feagpt_repro/compare_scorecards.py` | R30 跨口径闸（rc=3） |
| `feagpt_repro/.gitignore` | 新增 `.env` / `.env.*` 条目 |
| `FEM-Bench-Aero/RUBRIC.md` | v4.3：新增 R32 + v6b 实测三栏 + 难度方向性声明 |

### 1.3 C-028 官方数字（逐项核对）

| 指标 | 值 | 分母/说明 |
|---|---:|---|
| exam TSR | **17/25 = 68.0%** | CI95 [48.0, 84.0]，n=25 ⇒ `underpowered=False` |
| exam SFR | **14/21 = 66.7%** | 21 = 25 − 3 clarify − 1 no_output |
| exam MSR | **10/21 = 47.6%** | 同上分母；**0 条 solver** |
| 全链 MSR | **25/44 = 56.8%** | 44 = 55 − 4 clarify − 7 unresolved；含 3 条 dev solver OOM |
| dev TSR | 19/30 = 63.3% | 仅诊断（R15） |
| boundary | 5/6 = 83.3% | 分栏 n 小，只报不判 |
| extrapolation | 7/13 = 53.8% | 分栏 n 小，只报不判 |
| interpolation | 5/6 = 83.3% | 分栏 n 小，只报不判 |
| boundary+extrap | 12/19 = 63.2% | 与合并 25 的 68.0% 相差 +4.8pp（内插抬高） |
| T1 exam | 0/25 | value_added Δ68.0pp；**T1 train 12/13 是自检索，见 §3.6** |
| FPR | 编造 0/4、过度澄清 0、问错字段 0 | 4 条 clarify 全过 |
| turns | 1 轮 4 / 2 轮 1 / 3 轮 50 | 7 条 3 轮未收敛（1 exam + 6 dev） |

### 1.4 覆盖与可复现

- **55/55 文件覆盖**，`candidates_missing=[]`、`partial_candidates=false`；但“覆盖”是**文件覆盖**，不是“55 条都产出合法 spec”：实际是 **44 spec + 4 clarify + 7 unresolved**。
- 成绩单 `provenance` = `tasks_path: reports/papers/tasks_v6b.jsonl`，`tasks_sha256: 4c089c62…6ffe8`，`candidates_dir: candidates_l3_v6`，`n_candidates: 55`。
- `reports/check_claims.json`：**20 条 active / 24 个 artifact / 21 项语义检查全过**（S-17..S-20 新增 C-028 的 TSR/三栏/全链 MSR/exam MSR）。
- `reports/negative_controls_31.json`：**31/31 全绿**（PC-1 + NC-1..22 + NC-15b + NC-23..29）。

---

## 2. 已验证的改进（credit）

| 改进 | 实测 |
|---|---|
| **W5b-0 key 打通** | key 只读 `WORKBUDDY_PUBLISHABLE_KEY`；1 条冒烟 + 55 条全量；55/55 文件、0 error；生成 16 分 13 秒 |
| **C-028 首个 n≥20** | 17/25 (68.0%)、CI [48.0, 84.0]、`underpowered=False`；R12 的统计门槛首次满足 |
| **三栏并列** | boundary 5/6、extrap 7/13、interp 5/6；RUBRIC §1.1.1 明确“内插抬高 +4.8pp”，没有掩盖 |
| **FPR 干净** | 编造 0/4、过度澄清 0、问错字段 0；澄清字段级判据（R17）有效 |
| **T1 内插泄漏已修** | 内插考题 `split_v2=train` 会检索到自己；现按 `exam_stratum` 排除，T1 exam 0/25（**但 train 自检索仍在，见 §3.6**） |
| **v6b 四族地板可算** | train 池 13/0/0/0 → 9/2/1/1；T0/T1 四族齐全；T1 exam 0/25、T2 25/25 |
| **R30 跨口径闸** | `compare_scorecards.py` 对 v4 vs v6b 返回 rc=3；不把 5/11 与 17/25 相减 |
| **R31 覆盖记账** | `n_tasks_in_paper` / `candidates_missing` / `partial_candidates` 落进成绩单；NC-28 咬覆盖 |
| **R32 新红线** | 明确“gold 的每个判分字段必须能从 NL 推出”；把 2 条 wingbox 的题面缺口从“模型失败”改判为“卷子失败” |
| **负控/自检** | 31/31；`check_claims` 20/24/21 全过；tags `v1.0-l3-v6b`；v6 原稿留档（D10） |
| **诚实披露** | C-028 / RUBRIC / README 都写了“含已知缺陷的下界”“不可与 C-021 直接比”；这在基准项目里是稀缺品质 |

---

## 3. 新发现的问题

### 3.1 C-028 的 8 条 exam 失败：6 条系统性缺陷 + 2 条模型侧

C-028 的 headline 是 17/25；8 条失败逐条如下（字段来自成绩单 `per_task.failed_fields` + `_probe_w5b4_fail_fields.py`）：

| task_id | 族 | 栏 | 判类 | 失败字段 | 归因 |
|---|---|---|---|---|---|
| `L3_naca4412_wingbox_str3` | wingbox | interp | no_output | 3 轮修复未收敛 | **D**：生成器收敛性 |
| `L3_naca4412_wingbox_str3_T` | wingbox | extrap | spec_fail | `airfoil.stringer_flange_width` | **B**：题面没给 gold 字段（R32） |
| `L3_naca4412_wingbox_str5` | wingbox | boundary | spec_fail | `airfoil.stringer_flange_width` | **B**：题面没给 gold 字段（R32） |
| `L3_naca4412_wingbox_web1_offcentre` | wingbox | extrap | spec_fail | `airfoil.web_chordwise`、`extra.end_torque`、`extra.torque_axis_dof` | **C**：腹板位置 + 多余键 |
| `L3_open_hole_panel_400x200_d20_cfrp45s_d40` | panel | extrap | spec_fail | `params.hole_d`、`params.layup`、`material.ply_material (not in gold)` | **A/C**：prompt 键名 + 多余键 |
| `L3_open_hole_panel_400x200_d20_offcentre` | panel | extrap | spec_fail | `params.hole_d`、`hole_x`、`hole_y`、`load.kind` | **A**：prompt 未给开孔键名 |
| `L3_open_hole_panel_400x200_d40_offcentre` | panel | extrap | spec_fail | `params.hole_d`、`hole_x`、`hole_y`、`extra.end_tension` | **A/C**：prompt 键名 + 多余键 |
| `L3_open_hole_panel_600x300_d60` | panel | extrap | spec_fail | `params.hole_d`、`extra.end_tension` | **A/C**：prompt 键名 + 多余键 |

**三类系统性缺陷：**

- **A（4 条 panel，最大块）**：`gen_candidates_v2.js` 的 SYS prompt 只约定了长桁类键名（`n_stringers_per_skin` / `stringer_height` / `stringer_kind` / `stringer_flange_width`），**从未列出开孔板 `params.hole_d / hole_x / hole_y`、`params.layup`、`material.ply_material`**。题面写得很清楚（“中心孔直径 60 mm”“孔心 (120, 60)”），模型输出 `params={length,width,thickness}`，三个孔键一个都没有。这不是模型没读到信息，是**契约没给全**——与 M7 教训同源。
- **B（2 条 wingbox）**：gold `airfoil.stringer_flange_width` 有值，题面只写“blade 长桁（高 20 mm、厚 2.5 mm）”，没给缘条宽度；SYS prompt 明令“用户没给的尺寸不得编造”⇒ 模型正确省略 ⇒ 判 fail。**这是 R32 的实证：题面与 gold 不一致，任务不可解。**
- **C（1 条 web + 3 条 panel 的多余键部分）**：模型把载荷信息记进 `extra.end_torque` / `torque_axis_dof` / `extra.end_tension`，gold 无此键 ⇒ `(not in gold)`；同时 `web_chordwise` 位置也错。**多余键是否是错误，RUBRIC 尚未表态**；但 `web_chordwise` 是几何值，若题面给了位置而模型写错，这是模型侧错误，不是“多余键”可解释的。
- **D（1 条）**：`str3` 3 轮未收敛（孤例）。

**关键判断：**

> `eval_runs/w5b4_defect_analysis_20261025.md` 的“没有一条是模型能力不足的干净样本”是**过度归因**。A 类（prompt）和 B 类（R32）确实是系统性缺陷；但 **C 类的 `web_chordwise` 和 D 类的未收敛是模型/生成器侧问题**，不能全算到“卷子/prompt”头上。68.0% 是下界成立，但“全部不是模型问题”不成立。**要用一次受控的 prompt 修复实验来量化 A 类到底能回收几条，而不是先宣布“没有能力失败”。**

### 3.2 另有 4 条 TSR 通过但全链 MSR 失败——第二瓶颈是 contract，不是 solver

| task_id | 族 | 栏 | MSR 失败类 |  gates |
|---|---|---|---|---|
| `L3_fuselage_barrel_d2000_l2000_str12_frm4` | barrel | extrap | model | `pipeline=false` |
| `L3_naca4412_wingbox_size_span1600` | wingbox | boundary | contract | R19 试建闸 |
| `L3_naca4412_wingbox_size_span2400` | wingbox | interp | contract | R19 试建闸 |
| `L3_naca4412_wingbox_sweep40_taper040` | wingbox | extrap | contract | R19 试建闸 |

- 14 条 spec-correct 的 exam 任务中，只有 **10 条全链通过**（10/14 = 71.4%）；4 条损失 = 3 条 contract + 1 条 barrel pipeline。
- **这 3 条 contract 是 TSR PASS、SFR PASS，但 builder 构造失败**；需要区分“模型参数错”还是“builder 对合法组合不支持”。建议 W5c-0 把 gold spec 也过同一试建闸：gold 能建 ⇒ 模型错；gold 不能建 ⇒ 任务/契约错。
- **barrel 的 100% TSR 是假象**：barrel exam 2 条 = 1 条 clarify（`d1600`）+ 1 条 spec pass（`d2000_l2000_str12`），后者全链失败；barrel 的 MSR 是 **0/1**。`stiffened_panel` 的 1/1 也是 **clarify**，MSR 分母为 0，没有 spec 级证据。**族级 TSR 不能替代全链 MSR。**

### 3.3 exam MSR 47.6% 不含 solver；全链 56.8% 才含 3 条 dev solver

- 3 条 solver 失败全部是 **dev**（`exam_stratum=None`）：`d1800_l2000`（143,426 节点）、`d2000_l2000_str8`（158,548）、`d2000_l2000_t2_str8`（158,548）；都是本机内存阈值。
- **exam MSR 10/21 里 solver = 0**；47.6% 是真实的模型/契约失败，不是算力压低。
- 全链 MSR 25/44 (56.8%) 含这 3 条；剔除后 **25/41 = 61.0%**；dev MSR 15/23 (65.2%)，剔除 3 条后 **15/20 = 75.0%**。
- C-028 的写法“solver 3 条……剔除后参考值 MSR 25/41”容易被读成“exam MSR 也被算力压低”；**应改成三行：exam 10/21（0 solver）、dev 15/23（3 solver；剔除 15/20）、full 25/44（剔除 25/41）**。

### 3.4 v6 → v6b 只改标签，但 exam 族构成变了；C-028 没披露

- 机器 diff：v6 与 v6b 共 165 行，**只有 8 行变化，全部是 `exam_stratum`**；`split_v2` 全是 train；`input`/NL **零改动**。
- 移出 interp 的 4 条：`fuselage_barrel_d2000_l2000_str8_frm3`、`open_hole_panel_400x200_d20`、`open_hole_panel_400x200_d20_cfrp090s`、`stiffened_panel_600x600`。
- 新增 interp 的 4 条：`naca4412_wingbox_recombination_algorithm3`、`size_skin2`、`size_span2400`、`str3`。
- 族构成：v6 = **14/6/3/2** → v6b = **18/4/2/1**；翼盒占 exam 的 **72%**；train 池 13/0/0/0 → 9/2/1/1。
- 改的理由成立（v6 会把 barrel/panel/stiffened 的 train 抽空，T1 地板只有 1/4 族可算；1 个点的族没有“包络”可内插），RUBRIC §1.1/§7 已记录。**但 C-028 的“与 C-021 不可比”只列了两个变量（30→55、题面消歧），漏了第三个：v6→v6b 的族构成变化。**
- 被移出的 4 条来自 panel（exam 0/4）和 barrel/stiffened；把它们换回翼盒，方向上是**抬高** headline。68.0% 不是 v6 预注册构成（14/6/3/2）的成绩，必须写成“v6b 构成下的成绩”。

### 3.5 `split_v2` 根因没修：6 条 interp 仍是 `split_v2=train`

- 内插 6 条：`split_v2=train`、`exam_stratum=interpolation`；`score_baseline.py` 的 `is_exam` 兼容两者，`dev` 30 条也按 `is_exam` 正确排除了它们。
- **但 `by_split.train` n=19 仍包含这 6 条**：15/19 (78.9%) 不是纯 train；纯 train 是 10/13 (76.9%)。任何只用 `split_v2` 的下游工具（旧脚本、外部复现、T1 以外的检索）都会把它们当 train，发生泄漏。
- RUBRIC §6 NC-19 已经给了“内插豁免”（`split=train` + `stratum=interpolation` 记账），但这只是**在负控里放行**，不是修数据模型。建议 v6c 直接把 6 条改成 `split_v2=interpolation_test`，或至少在 `by_split` 里排除 `is_exam` 并标“train (incl. interp exam)”。
- **C-011 仍写“族 wingbox 2 / open_hole 2 / barrel 1 / panel 1”**（v6 旧名额），与 C-027 的“v6b 全翼盒 6”矛盾；`check_claims` S-03 只查条数 6，没查族分布。

### 3.6 T1 的 train 12/13 全部是自检索；value_added 的地板是稻草人

- `trivial_baselines_L3_v6b.json` 的 `per_task`：**12 条 T1 PASS 全部满足 `T1_nn == task_id`**；T1 train 12/13 = 92.3%，本质是“把题面自己检索回来”。
- 唯一的 T1 失败是 `open_hole_panel_400x200_d20_cfrp090s`（最近邻是另一个 panel，不是自己）。
- **exam T1 0/25 是公平的**（exam 任务已从检索库排除），所以 C-028 的 value_added 用 0/25 没问题；但 T1 报告里的 train 12/13 会误导读者以为地板很强。**T1 必须在 train 上做 leave-one-out**；exam 0/25 只是“fair but weak”，不是强地板。
- 建议加 **T1+（family-mode / 最近邻 + 参数适配）** 与 **per-family T1**；否则 value_added 的 Δ≥10 门槛永远被 0 地板轻易满足，不能证明 LLM 的增量。

### 3.7 官方成绩单内部口径矛盾（W4d 字符串没更新）

`reports/baseline_scorecard_L3_v6b.json` 的顶层字段与 v6b 三栏不一致：

| 字段 | 现值 | 应为 |
|---|---|---|
| `note` | “W4d L3 主基线（W4e 修正……）” | W5b-4 / C-028 / v6b |
| `exam_definition` | `exam = boundary_holdout + extrapolation_test；dev = train + val（R15）` | 加 `exam_stratum`（三栏 25；boundary+extrap 19 只报不判） |
| `value_added.basis` | `exam（boundary+extrap）TSR，T1 同任务集 exam_pct` | `exam 三栏 25`（T1 也是 25） |
| `by_split.train` | n=19（含 6 条 interp exam） | 纯 train 13，或标“含内插考题” |
| `msr_section` | 只有 by_split，无 by_family/by_stratum | 加 exam MSR 的族/栏分解 |

- 根因：`score_baseline.py` 第 213/219/260 行仍是 v4 的硬编码字符串；v6b 支持只改了 `is_exam`/`exam_by_stratum`，没改这些文案。
- `check_claims` S-17..S-20 只核对 C-028 文本与成绩单数字，**不核对成绩单自己的 `exam_definition`/`value_added.basis`**；所以 21 项全过，但读者仍会被 19/25 两个定义弄混。

### 3.8 证据链引用了未追踪文件（R25/R26 回归）

- `eval_runs/w5b4_defect_analysis_20261025.md`（5,343 B）在 `.gitignore` 的 `feagpt_repro/eval_runs/` 下，**未被 git 追踪**；但 C-028、RUBRIC §1.1.1、README、`reports/INDEX.md` 第 135 行都把它当“诊断明细”引用。
- 官方 artifact（成绩单）本身有 `failed_fields`（`score_baseline.py` 第 144/202 行；失败行确实带该字段），所以分析不是唯一证据；但**官方文档不应指向 `eval_runs/`**。建议把分析移到 `reports/diagnostics/w5b4_defect_analysis_v6b.md`（入库），或删掉引用、只留可复跑的探针命令。
- **W5B_PLAN W5b-6 的“遗留：成绩单本身仍不存 `failed_fields`”是过期信息**；成绩单失败行已有 `failed_fields`。`_probe_w5b4_fail_fields.py` 的 docstring 也这么写，需同步修正。

### 3.9 硬编码的 live key 仍在被追踪的 `gen_candidates.js`

- `feagpt_repro/gen_candidates.js:12-13` 仍有：
  ```js
  publishableKey: process.env.WORKBUDDY_PUBLISHABLE_KEY ||
                  'wbpk_<redacted>',
  ```
- `W5B_PLAN §6.0` 自己写明：“仓库 `gen_candidates.js:13` 遗留同值 fallback（**未轮换**，与线上取回值逐字符一致）”。
- `gen_candidates_v2.js` 已是 env-only；**v1 脚本的 fallback 应删除**，并轮换该 key（publishable + Origin 校验，风险低于私钥，但“tracked + live”仍是凭据卫生问题）。`.gitignore` 新增 `.env` 是好事，但不能替代删除硬编码。

### 3.10 统计与构成：n=25 满足 R12，但精度和族平衡不足

- CI [48.0, 84.0] 宽 36pp；n=25 是 R12 的最低线；族级 n：wingbox 18、panel 4、barrel 2、stiffened 1，全部 <10，族级结论只能“只报不判”。
- headline 的 17/25 = wingbox 14 + panel 0 + barrel 2（1 clarify + 1 spec pass）+ stiffened 1（clarify）。**翼盒占 72%；barrel/stiffened 的 100% 是 clarify 或小样本，不是 spec 级能力。**
- 6 条 interp 全翼盒；合并 68.0% 比 boundary+extrap 63.2% 高 4.8pp；三栏披露是正确做法，但 headline 仍混入了更容易的内插。
- **结论：`underpowered=False` 是“按任务数 n=25”的统计门槛，不是“族级/构成级”的充分性。** 对外只能写“headline 可判”，不能写“四族都可判”。

### 3.11 生成器一次通过率 4/55，50 条要 3 轮

- turns 分布 1:4 / 2:1 / 3:50；7 条 3 轮未收敛。**一次通过率 7.3%**。
- 这不是说 68% 无效——修复循环是协议的一部分，C-028 也如实报告了 turns——但说明 **schema/prompt 的可读性很差**；panel 键名缺失很可能也是 3 轮修复失败的一个原因。第二模型必须用**同样的 ≤3 轮预算**，否则不可比。
- 建议成绩单增加 `first_pass_valid` / `n_unresolved` / `turns_histogram`；C-028 目前只在正文写了 turns，没进结构化字段。

### 3.12 不是问题的部分（避免过度纠偏）

- FPR 0/4、澄清字段级判据、SFR 14/21、负控 31/31、`check_claims` 20/24/21、tags、paper 快照、55 条零缺失、16 分 13 秒——这些都是真的，不需要重做。
- C-028 的“与 C-021 不可直接比”“68% 是下界”“题面消歧⇒难度下降”都是主动披露，方向正确；本轮是**补第三变量和口径**，不是推翻成绩。
- 3 条 solver OOM 是机器内存边界，不是模型失败；不要为了“好看”把它们从 MSR 里静默删掉——要**显式分列**。

---

## 4. W5b-5 与 W5c 准入评估

### 4.1 W5b-5 第二模型：现在只能做诊断，不能做官方对比

- v6b 考卷含 2 条 R32 不可解、4 条 prompt 键名缺失、1 条模型侧多余键、1 条未收敛；第二模型若直接跑 v6b，结果会被同样的缺陷污染，**不能用于“模型 A vs 模型 B”的官方结论**。
- 但**现在跑诊断有价值**：如果两个模型都在同一批 panel/flange 任务上失败，说明缺陷是 harness/paper 级；如果只有当前模型失败，说明是模型级。建议：
  - 用同一 `--tasks reports/papers/tasks_v6b.jsonl`、同一 `--max-turns 3`、同一 schema；
  - 输出到 `candidates_l3_v6b_<model>`，成绩单标 `diagnostic`，不占官方路径；
  - 官方第二模型对比等 v6c。
- 模型 id 必须先用 SDK 实测可用列表，不猜（W5B_PLAN 原话）。

### 4.2 W5c 准入条件（Go/No-Go）

| 条件 | 现状 | 结论 |
|---|---|---|
| C-028 可复现 | 成绩单 + 候选 + 考卷 sha 齐全 | ✅ |
| n≥20 | 25 | ✅ |
| 三栏 + CI | 有 | ✅ |
| R32 干净 | **2 条 exam 不可解** | ❌ |
| prompt 键名完整 | **4 条 panel 缺键** | ❌ |
| `split_v2` 语义一致 | **6 条 interp 仍是 train** | ❌ |
| 成绩单口径字符串 | **W4d 旧文案** | ❌ |
| T1 公平地板 | **train 自检索；exam 0/25** | ⚠️ |
| 证据全部入库 | **诊断分析在 eval_runs** | ❌ |
| 第二模型 | 未跑 | ⏳ |

**判定：W5c 是“修复 + 重冻结 + 重生成”轮，不是“再扩量”轮。** 先修 R32/prompt/`split_v2`/scorecard，再谈第二模型和发榜。

---

## 5. 下一步任务执行建议

### 5.1 W5c 任务表

| ID | 优先级 | 做什么 | 验收 | 证据 |
|---|---|---|---|---|
| **W5c-0** | **P0** | **R32 全量审计**：对 25 条 exam × `GRADED_FIELDS[family]`，逐字段检查 gold 有值 ⇒ NL 有数字/词元或显式默认；输出 `reports/r32_audit_v6b.json`（入库） | 0 条不可解；2 条 flange + web/extra 的结论有脚本依据 | 新脚本 `r32_audit.py`；NC-30 |
| **W5c-1** | **P0** | **生成器键名表 + 契约 smoke**：SYS prompt 补 `hole_d/hole_x/hole_y`、`layup`、`ply_material`、`load.kind`、`web_chordwise`、`extra` 允许键；每个族用 1 条 gold spec 过 schema+builder | 4 族 gold 全建；1 条/族冒烟通过；未过不得 55 条盲跑 | `gen_candidates_v2.js`；NC-31 |
| **W5c-2** | **P0** | **考卷 v6c**：2 条 flange 题面补 `stringer_flange_width`；web/extra 口径拍板；6 条 interp `split_v2=interpolation_test`；重新冻结 `papers/tasks_v6c.jsonl` + `nl_human_v6c.jsonl` + `SHA256SUMS`，tag `v1.0-l3-v6c` | R32 审计 0 违规；NC-19 无需豁免；老题改动逐条留档 | `make_nl_human.py`；`_verify_tasks_v6.py`；负控 |
| **W5c-3** | **P0** | **重生成 55 条 + 重打分 + CI**：v6c 考卷 × 新候选；`score_baseline.py` → `msr_l3.py` → `bootstrap_ci.py`；新 claim **C-029**；v6b→v6c 做 **bridge 表**（R22） | 55/55 文件；exam 25；三栏；CI；bridge 逐项可解释 | `reports/baseline_scorecard_L3_v6c.json` 等 |
| **W5c-4** | P1 | **第二模型**：v6c 上跑第二个模型；同 prompt/同 ≤3 轮；各自 CI + 差异；模型 id 先 SDK 实测 | 两模型同卷同预算；差异有 CI；不混入 C-029 | 新 claim / diagnostic 分文件 |
| **W5c-5** | P1 | **T1 公平地板**：train leave-one-out；exam 用 family-mode T1+；per-family T1；value_added 重算 | train T1 不再自命中；exam T1 有非零可能；Δ 仍 ≥10 或如实下降 | `trivial_baselines.py`；NC-32 |
| **W5c-6** | P1 | **口径/证据修复**：`exam_definition`/`value_added.basis`/`note` 从 paper 生成；MSR 加 by_family/by_stratum；`failed_fields` 已在；诊断分析移 `reports/`；C-011/INDEX/W5B_PLAN 修正；删 `gen_candidates.js` fallback + 轮换 key | S-21..S-28 全过；无 `eval_runs` 引用；无 tracked live key | `score_baseline.py`；`check_claims.py`；`reports/` |
| **W5c-7** | P2 | **负控扩展**：NC-30 R32 不可解 / NC-31 prompt 缺键 / NC-32 T1 自检索 / NC-33 成绩单旧文案 / NC-34 claim 引未追踪 / NC-35 跨卷 task-id 不同 | 31 → **37**；全绿 | `negative_controls.py`；RUBRIC §6 |
| **W5c-8** | P2 | **v1.1 新几何**（W5B_PLAN 路径 B）：6–10 条新 case，扩 exam 精度；不在 W5c 内混判据 | 新几何 truth + 双求解器 + gate；n≥30 | 后续里程碑 |

### 5.2 顺序建议

```text
W5c-0 R32 审计 ──► W5c-1 prompt/契约 smoke ──► W5c-2 v6c 冻结
                                                   │
                                                   ▼
                              W5c-3 重生成 55 + 重打分 + bridge
                                                   │
                         ┌─────────────────────────┴──────────┐
                         ▼                                    ▼
                 W5c-4 第二模型（官方）              W5c-5 T1+ 地板
                         │                                    │
                         └──────────────► W5c-6 口径/证据 ◄───┘
                                                   │
                                                   ▼
                                          W5c-7 负控 / W5c-8 v1.1
```

**为什么这个顺序**：prompt 键名和 R32 是“题面/prompt 级”改动，必须先于重生成；`split_v2` 是“标签级”改动，可以和 v6c 一起冻结；T1+ 不影响 LLM 候选，可以和第二模型并行；口径/证据是收口项，最后统一。

### 5.3 成本估计

- W5c-0/1/2：0.5–1 天（脚本 + 改题 + 负控）。
- W5c-3：55 条生成 16 分钟 + MSR 22 分钟 + 打分/CI 几分钟；主要是等。
- W5c-4：第二模型 16–30 分钟（取决于模型速度）。
- W5c-5/6/7：0.5–1 天。
- **总计约 2 天**；比“直接发榜再返工”便宜。

---

## 6. 防跑偏机制（R33–R40 建议）

> 现有 R1–R32 保留；以下为第八轮建议新增，**待拍板后写入 RUBRIC**。

| 红线 | 内容 | 触发点 |
|---|---|---|
| **R33** | **R32 审计是考卷冻结闸**：每条 exam 任务的每个 `GRADED_FIELDS` 字段，gold 有值 ⇒ NL 必须有依据或显式默认；否则不得进 exam | v6c 冻结前；NC-30 |
| **R34** | **生成器键名表必须齐全**：SYS prompt 必须列出四族全部 `KNOWN_KEYS`；每族 gold spec 必须过 schema+builder 的契约 smoke；未过不得全量生成 | W5c-1；NC-31 |
| **R35** | **solver/算力失败必须单列**：OOM/超内存记 `compute_bound`，不计入模型能力；成绩单必须同时给 `exam_msr`（不含 solver）、`dev_msr`、`full_msr_excl_solver` | 成绩单生成；C-028 修正 |
| **R36** | **`split_v2` 必须语义正确**：exam 任务不得以 `split_v2=train` 存在（除非 `split_v2=interpolation_test`）；所有工具必须用 `is_exam`；`by_split` 必须排除 exam 或显式标注 | v6c；NC-19 重写 |
| **R37** | **官方文档不得引用 `eval_runs/`**：CLAIMS/RUBRIC/README/INDEX 里的每个路径必须被 git 追踪；`check_claims` 扫描文本路径 | W5c-6；NC-34 |
| **R38** | **成绩单摘要字符串必须由 paper 生成**：`exam_definition`/`value_added.basis`/`note` 不得硬编码 W4d 文案；`check_claims` 语义检查 | W5c-6；S-23 |
| **R39** | **跨卷比较按 task-id，不按条数**：成绩单存 `exam_task_ids_sha256` + `exam_by_family`；`compare_scorecards` 在 task-id 集不同时 rc=3；构成变化必须 bridge（R22） | v6b vs v6c；NC-35 |
| **R40** | **T1 必须 leave-one-out**：检索库不得包含目标自身；train T1 自命中即无效；value_added 必须用 per-family、非自检索的地板 | W5c-5；NC-32 |

**新增语义检查（S-21..S-28）建议：**

| ID | 检查 | 期望 |
|---|---|---|
| S-21 | C-011 内插族分布 | v6b = wingbox 6（不是 2/2/1/1） |
| S-22 | C-028 的 26/55、25/55、161→206 字 | 从 v4/v6b paper 实算，不硬编码 |
| S-23 | 成绩单 `exam_definition` / `value_added.basis` | 含 `exam_stratum` / 三栏 25 |
| S-24 | `by_split.train` | 纯 train 13 或显式标注含 interp |
| S-25 | C-028 的 SFR 14/21、dev 19/30、FPR 0/4、solver 3 | 与成绩单一致 |
| S-26 | C-028 的 55/55 | 同时给 44 spec / 4 clarify / 7 unresolved |
| S-27 | 所有 active claim 文本路径 | 全部被 git 追踪，无 `eval_runs` |
| S-28 | 成绩单 exam task-id 集 | 与 `tasks_v6b.jsonl` 的 exam 集逐 id 相等 |

---

## 7. 评分卡

> **第七轮 28/30 是纸面审计；第八轮 24/30 是实测。** 两者不可直接比；统计有效性 +1，任务/判分/证据/版本/文档各 −1。

| # | 维度 | 第七轮 | 第八轮 | 依据 |
|---|---|---:|---:|---|
| 1 | 目标一致性 | 3 | 3 | 仍是评测基础设施；W5b 按计划推进 |
| 2 | 任务有效性 | 3 | **2** | R32 2 条不可解；4 条 panel prompt 缺键；v6b 族构成偏移；`split_v2` 不一致 |
| 3 | 判分有效性 | 3 | **2** | 负控 31/31 仍强；但 MSR/solver 混写、T1 自检索、contract 归因未清、成绩单旧文案 |
| 4 | 证据等级 | 3 | **2** | 官方 artifact 齐全；但诊断分析在 `eval_runs` 未追踪；C-011 的族分布文本仍是 v6 的 2/2/1/1（v6b 是 wingbox 6） |
| 5 | 可复现性 | 3 | **3** | C-028 命令 + 55 候选 + paper sha + 16 分 13 秒；可复跑 |
| 6 | 版本治理 | 3 | **2** | v6b tag/paper 有；但 INDEX 仍写“待生成”、W5B_PLAN 仍写 `tasks_v6.jsonl`、候选目录叫 v6 |
| 7 | 文档真实性 | 3 | **2** | C-028 主动披露缺陷（加分）；但 6 处新漂移 + “没有模型失败”过度归因 + 未追踪引用 |
| 8 | 统计有效性 | 1 | **2** | n=25、CI 落地；但族 n<10、翼盒 72%、T1 0/25、构成变化；仍不能做族级结论 |
| 9 | 范围纪律 | 3 | **3** | 没混新几何/新判据；v6b 只改标签；R30 闸 |
| 10 | 计划执行 | 3 | **3** | W5b-0..4 全按计划；55 条零缺失；负控/自检全绿 |
| **总分** | | **28/30** | **24/30** | 基础设施 A；科学有效性 C+；对外发布 No-Go |

**一句话**：**这不是“项目变差了”，而是“第一次真跑把纸面 28 分打成了实测 24 分”。** 把 W5c 的 8 项做完，回到 28 是现实的；在 R32/prompt/`split_v2` 修好之前，任何“68.0% 对外 headline”都会被专家一问就穿。

---

## 8. 待拍板

| # | 决策 | 选项 | 建议 |
|---|---|---|---|
| **D1** | **C-028 的定位** | (a) 冻结为 **known-defect lower bound**，官方 headline 等 v6c；(b) 直接作为官方 headline 发布 | **(a)**；C-028 保留为诊断/历史，CLAIMS 标 `diagnostic lower bound`，v6c 出 C-029 再切 headline |
| **D2** | **W5c 修复范围** | (a) 最小：2 条 flange + prompt 键名 + `split_v2`；(b) 完整：再加 web/extra 口径 + 3 条 contract 审计 + panel 全键 + 成绩单/证据 | **(b)**；panel 是 4/25，contract 是 3/25，不修就等于把 7 条已知缺陷带进 v6c |
| **D3** | **第二模型时机** | (a) 现在跑 v6b 诊断，v6c 再跑官方；(b) 等 v6c 一次跑 | **(a)**；诊断能区分“模型问题”与“harness 问题”，成本 16–30 分钟 |
| **D4** | **T1+ 地板** | (a) 加 train leave-one-out + family-mode T1+；(b) 保持 T1 0/25 | **(a)**；否则 value_added 永远是 0 地板，Δ≥10 没有信息量 |
| **D5** | **key 卫生** | (a) 删 `gen_candidates.js` fallback + 轮换 key；(b) 保持现状 | **(a)**；publishable 也要按凭据管理，尤其 W5B_PLAN 已写明“与线上同值” |

---

## 附录 A　证据索引与复现命令

### A.1 官方 artifact

| 文件 | 用途 |
|---|---|
| `feagpt_repro/reports/baseline_scorecard_L3_v6b.json` | C-028 成绩单（55 per_task + exam 三栏 + MSR + provenance） |
| `feagpt_repro/reports/bootstrap_ci_L3_v6b.json` | exam 25 / 三栏 / 四族 CI |
| `feagpt_repro/reports/trivial_baselines_L3_v6b.json` | T0/T1/T2 地板（含 per_task） |
| `feagpt_repro/reports/papers/tasks_v6b.jsonl` | v6b 考卷快照（165 行；sha256 见成绩单 provenance） |
| `feagpt_repro/reports/papers/nl_human_v6b.jsonl` | v6b NL 快照（55 L3） |
| `feagpt_repro/reports/papers/tasks_v6.jsonl` | v6 原稿（作废留档，D10） |
| `feagpt_repro/reports/negative_controls_31.json` | 负控 31/31 |
| `feagpt_repro/reports/check_claims.json` | 20 active / 24 artifact / 21 semantics 全过 |
| `feagpt_repro/reports/INDEX.md` | 官方 vs 诊断索引（**第 74 行仍写 v6b 待生成，需修**） |
| `FEM-Bench-Aero/CLAIMS.md` | C-001..C-028（**C-011 族分布需修**） |
| `FEM-Bench-Aero/RUBRIC.md` | v4.3（R32；§1.1.1；**§1.1.1 的“同因”需细化**） |
| `FEM-Bench-Aero/W5B_PLAN.md` | W5b 计划（**W5b-2/W5b-6/17 项等需修**） |

### A.2 复现命令

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# 1) 重新打分（v6b 考卷 × v6 候选）
"$PY" score_baseline.py --candidates candidates_l3_v6 \
  --tasks reports/papers/tasks_v6b.jsonl \
  --report reports/baseline_scorecard_L3_v6b.json \
  --trivial reports/trivial_baselines_L3_v6b.json \
  --label "C-028 v6b (paper v6b, candidates v6)"

# 2) 全链 MSR（会写回同一成绩单的 msr_section）
"$PY" msr_l3.py --candidates candidates_l3_v6 \
  --tasks reports/papers/tasks_v6b.jsonl \
  --report reports/baseline_scorecard_L3_v6b.json

# 3) CI
"$PY" bootstrap_ci.py --scorecard reports/baseline_scorecard_L3_v6b.json \
  --out reports/bootstrap_ci_L3_v6b.json

# 4) 跨口径闸：必须 rc=3
"$PY" compare_scorecards.py \
  --a reports/baseline_scorecard_L3_v4.json \
  --b reports/baseline_scorecard_L3_v6b.json; echo "rc=$?"

# 5) 地板
"$PY" trivial_baselines.py --levels L3 \
  --tasks reports/papers/tasks_v6b.jsonl \
  --out trivial_baselines_L3_v6b.json --out-dir reports

# 6) 失败字段探针（诊断，输出到 eval_runs 不占官方路径）
"$PY" _probe_w5b4_fail_fields.py \
  --scorecard reports/baseline_scorecard_L3_v6b.json \
  --tasks reports/papers/tasks_v6b.jsonl \
  --candidates candidates_l3_v6 \
  --out eval_runs/probe_w5b4_fail_fields_v6b.json

# 7) 自检
"$PY" check_claims.py
"$PY" negative_controls.py
```

---

## 附录 B　失败矩阵与 v6→v6b 差异

### B.1 exam 25 的 TSR/MSR 矩阵

| 族 | exam n | TSR | MSR | 备注 |
|---|---:|---|---:|---|
| wingbox | 18 | 14/18 (77.8%) | 10/16 (62.5%) | 1 clarify + 1 no_output 出分母；3 contract + 3 spec_fail |
| open_hole_panel | 4 | 0/4 (0%) | 0/4 (0%) | 4 条 spec_fail；prompt 键名 |
| fuselage_barrel | 2 | 2/2 (100%) | 0/1 (0%) | 1 clarify；1 spec pass 但 pipeline fail |
| stiffened_panel | 1 | 1/1 (100%) | 0/0 (n/a) | 1 clarify；无 spec 证据 |
| **合计** | **25** | **17/25 (68.0%)** | **10/21 (47.6%)** | MSR 分母 21 = 25−3 clarify−1 no_output |

### B.2 三栏 TSR/MSR

| 栏 | n | TSR | MSR | 备注 |
|---|---:|---|---:|---|
| boundary | 6 | 5/6 (83.3%) | 4/6 (66.7%) | 1 spec_fail + 1 contract |
| extrapolation | 13 | 7/13 (53.8%) | 3/11 (27.3%) | 2 clarify 出分母；4 panel + 1 web + 1 flange + 1 barrel + 1 contract |
| interpolation | 6 | 5/6 (83.3%) | 3/4 (75.0%) | 1 no_output + 1 contract 出分母 |

### B.3 v6 → v6b 的 8 行

| 动作 | task_id | 族 | split_v2 | exam_stratum |
|---|---|---|---|---|
| 移出 interp | `fuselage_barrel_d2000_l2000_str8_frm3` | barrel | train | interpolation → None |
| 移出 interp | `open_hole_panel_400x200_d20` | panel | train | interpolation → None |
| 移出 interp | `open_hole_panel_400x200_d20_cfrp090s` | panel | train | interpolation → None |
| 移出 interp | `stiffened_panel_600x600` | stiffened | train | interpolation → None |
| 新增 interp | `naca4412_wingbox_recombination_algorithm3` | wingbox | train | None → interpolation |
| 新增 interp | `naca4412_wingbox_size_skin2` | wingbox | train | None → interpolation |
| 新增 interp | `naca4412_wingbox_size_span2400` | wingbox | train | None → interpolation |
| 新增 interp | `naca4412_wingbox_str3` | wingbox | train | None → interpolation |

- **没有 NL/input 改动**；老 30 条 `input` 逐字节一致（机器 diff：0 条变化）。
- 族构成 14/6/3/2 → 18/4/2/1；train 池 13/0/0/0 → 9/2/1/1。
- `split_v2` 6 条 interp 仍是 `train`；这是 §3.5 的根因。

---

## 附录 C　语义漂移清单（第二轮）

> 第七轮的 5 处漂移已修（C-010 165、C-011 条数 6、C-019 31、C-027 “C-021 11”、README RUBRIC 4.3）。第八轮新增/剩余：

| # | 位置 | 现文 | 应为 | 检查 |
|---|---|---|---|---|
| 1 | `CLAIMS.md` C-011 | 内插族 “wingbox 2 / open_hole 2 / barrel 1 / panel 1”；“考卷 v6” | v6b：**wingbox 6**；考卷 v6b | S-21 |
| 2 | `reports/INDEX.md` L74 | v6b **“待生成”**、“冻结待跑”、key 阻塞 | 已生成 55/55、C-028 已完成 | S-27 |
| 3 | `W5B_PLAN.md` W5b-2 | 冻结稿 `papers/tasks_v6.jsonl` | `tasks_v6b.jsonl`（v6 是作废原稿） | S-27 |
| 4 | `W5B_PLAN.md` §5 | `check_claims --semantic` **17 项** | 21 项（S-17..S-20 新增） | S-27 |
| 5 | `W5B_PLAN.md` W5b-6 | 成绩单“仍不存 failed_fields” | 失败行已有 `failed_fields`（`score_baseline.py:144/202`） | S-27 |
| 6 | `W5B_PLAN.md` W5b-5 | “可直接换 `--model` 跑”（暗示官方） | 先诊断；官方等 v6c | 文档 |
| 7 | `baseline_scorecard_L3_v6b.json` | `exam_definition` = boundary+extrap；`value_added.basis` = boundary+extrap；`note` = W4d | 三栏 25；v6b；C-028 | S-23 |
| 8 | `RUBRIC.md` §1.1.1 | “open_hole_panel 4/4 全败，**同因** hole_d/hole_x/hole_y” | 4/4 主导是 hole_d；但还有 layup/load.kind/extra/ply_material，A/C 混合 | 文档 |
| 9 | `RUBRIC.md` §1.1.1 | 只列 “2 条 wingbox 败于 flange” | 还应列 `web1_offcentre`（web_chordwise + extra） | 文档 |
| 10 | `RUBRIC.md` 版本表 | v4.3 排在 v4.2/v4.1 之前 | 按时间 v4.1→v4.2→v4.3 | 文档 |
| 11 | C-028 | “55/55 覆盖” | 44 spec + 4 clarify + 7 unresolved（文件覆盖 ≠ 全合法） | S-26 |
| 12 | C-028 | “solver 3 条……剔除后 MSR 25/41” | 明写 **exam 10/21（0 solver）**；25/41 是 full/diagnostic | S-25 |
| 13 | C-028 | “与 C-021 差异至少两个变量” | 补第三变量：v6→v6b 族构成 14/6/3/2 → 18/4/2/1 | 文档 |
| 14 | `eval_runs/w5b4_defect_analysis` | 被 CLAIMS/RUBRIC/README/INDEX 引用 | 移 `reports/diagnostics/`（入库）或删引用 | S-27 |
| 15 | `gen_candidates.js` | 硬编码 live key fallback | 删除 + 轮换 | 安全 |

---

> **本轮只读核对；除本文件外未改动任何项目文件。**
> 下一轮复评入口：W5c-2 的 v6c 冻结 + W5c-3 的 C-029 成绩单；在此之前，C-028 只能作 known-defect lower bound 引用。
