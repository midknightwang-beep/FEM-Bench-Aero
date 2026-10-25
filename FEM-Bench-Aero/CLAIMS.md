# CLAIMS — 主张账本（W4a 纠偏 6.4，防跑偏常设机制）

> 规则：对外文档（external_numbers / README / dataset_card）引用的每一条数字主张必须在本账本登记，
> 带 artifact + command + level；过期主张标 `superseded` 不删除。`external_numbers.md` 只能从本账本口径生成。
> level 含义：GATED = 有硬判据闸；REPORTED = 只报不判；NOT-EVALUATED = 无证据。

| claim_id | statement | artifact | command | date | level | coverage | status |
|---|---|---|---|---|---|---|---|
| C-001 | 数据集规模 55 条 × 2 树 = 110 算例目录 | manifest.json | `python -c "import json;print(json.load(open('FEM-Bench-Aero/manifest.json'))['summary'])"` | 2026-10-24 | GATED | 55/55 | active |
| C-002 | 关 1 网格 55/55（minJ 0.4636、tri3 0） | gates_all55_d36.json | `python -c "import json;d=json.load(open('FEM-Bench-Aero/gates_all55_d36.json'));print(d['gate1_mesh_quality'])"` | 2026-10-24 | GATED | 55/55 | active |
| C-003 | 关 3 双码 = 34 field + 15 scalar-disp + 6 reported-only（**不说 55/55**） | gate3_all55_d37.json | `python gate3_all55.py` | 2026-10-24 | 分级 | 55/55 | active |
| C-004 | 关 4 语义 110/110 | gate4_d36.json | `python check_semantics.py --root ../FEM-Bench-Aero` | 2026-10-24 | GATED | 110/110 | active |
| C-005 | 自洽 110/110、dup 0、配对 55/55 | verify_dataset_d36.json | `python verify_dataset.py --root ../FEM-Bench-Aero` | 2026-10-24 | GATED | 110/110 | active |
| C-006 | 代理基线 max_disp test 2.631 %（CI [0.89,4.51]，地板 49.44）——**附录口径，对外承诺写 5–9 %** | baseline_d36_final.json | `python baseline.py --boot 4000` | 2026-10-24 | GATED* | 6 test | active（带 M14 caveat） |
| C-007 | 全体 34 条留一 5.35 %（p90 14.09 / max 33.10） | _probe_m14/all_loo.json | `python _probe_m14/all_loo.py` | 2026-10-24 | GATED | 34 | active |
| C-008 | vM 峰值未收敛：12→6 mm 仍 +12.9 %，真值带 ≥13 % 偏不安全低估 | _probe_m14/h_convergence.json | `python _probe_m14/h_convergence.py` | 2026-10-24 | GATED | 锚点 1 几何 | active |
| C-009 | 评测器负控 9/9（PC-1 + NC-1..8） | feagpt_repro/eval_runs/negative_controls.json | `python negative_controls.py` | 2026-10-24 | GATED | 9 条 | **superseded**（被 C-019 取代；artifact 在 gitignore 的 eval_runs/，违反 R25） |
| C-010 | 任务层 **165 行** = L1 55 + L2 55（轮换 13 字段、泄漏 0）+ **L3 55**（考卷 v6 全 case，template_human_designed；W5b-2 由 L3 30 扩至 55，见 C-027） | feagpt_repro/tasks/tasks.jsonl | `python make_tasks.py --dry` | 2026-10-25 | GATED | 165 | active |
| C-011 | boundary_holdout **6 条**（翼盒 train 边界锚点整类留出 28.6%）；**真内插 ID test = 考卷 v6 的 `interpolation` 6 条**（C-027；族 wingbox 2 / open_hole 2 / barrel 1 / panel 1，从 train 确定性取） | feagpt_repro/tasks/tasks.jsonl | `python make_tasks.py --dry` | 2026-10-25 | GATED | boundary 6 / interp 6 | active |
| C-012 | schema 双份 55/55 过 + 反向探针（死 airfoil 拒 / 越界 55° 拒） | FEM-Bench-Aero/schema_truth.json, schema_task.json | `python validate_schema.py` | 2026-10-24 | GATED | 55/55 | active |
| C-013 | 数据本体可获取：v1.0-data.tar.gz 86 MB + SHA256SUMS + fetch_data 全链验证 | F:/FEA_Archive_20261024/SHA256SUMS.txt | `python fetch_data.py --src <path>` | 2026-10-24 | GATED | 55/55 | active |
| C-017 | **L1 spec-copy smoke（W4b，非模型基线）**：考卷 19 条 SFR **0/19**（boundary 0/6、extrap 0/13）；归因 airfoil.chord×12 + bc.clamp×7——无 schema 约束解码时 LLM 指令遵循失败（airfoil 整组缺失/bc 块丢失），非建模能力结论；n=19 UNDERPOWERED | feagpt_repro/reports/baseline_scorecard_L1_smoke.json | `python score_baseline.py candidates --report reports/baseline_scorecard_L1_smoke.json` | 2026-10-24 | GATED (spec-only) | 19/19 | active |
| C-018 | 「LLM 基线 TSR 2/2 = 100%」 | eval_runs/baseline_scorecard.json（22:08 旧快照） | — | 2026-10-24 | — | 2 条 | **superseded**（partial + skip_solve + 旧快照，被 C-017 取代；红线 R11/R14） |
| C-025 | **W5a 修题后重打分（R21 修法 3：不重新生成，现有候选 + 考卷 v5 + RUBRIC v3）— ⚠️ DIAGNOSTIC，不是模型成绩（R28）**：考卷 v5 = 四族 NL 写死坐标系+方向向量（coordinate_convention 30/30）+ panel 伪缺澄清题修正（600x600 gold n_stringers=0 信息完备曾误罚「编造」，ec 迁到 str3 真缺）。**exam TSR 4/11**（-1 = str3 ec 迁移对旧候选的系统性误罚：候选基于 v4 完整 NL 生成、考卷挖字段后旧候选不可能补问——「旧候选不能评新考卷」）；**dev TSR 12/19（+1 = 600x600 修题纠错：从误罚编造变如实 spec_pass）**；**MSR 12/21 (57.1%)、exam 4/8、dev 8/13**（R23 新分母；失败分层 model 6 + contract 3，env 0）。**正式对外 headline 仍是 C-021（v4 口径 5/11 / MSR 4/9）**，本条只证明「修题改了什么」，正式 v5 成绩待 W5b 用 v5 重生成候选后另立 | feagpt_repro/reports/baseline_scorecard_L3_v5_rescore.json | `python score_baseline.py --candidates candidates_l3_v3 --tasks reports/papers/tasks_v5.jsonl --report reports/baseline_scorecard_L3_v5_rescore.json` + venv `python msr_l3.py --tasks reports/papers/tasks_v5.jsonl --report reports/baseline_scorecard_L3_v5_rescore.json` | 2026-10-25 | GATED (full-chain MSR) · **diagnostic** | 30/30 生成 / exam 11 | active（diagnostic） |
| C-024 | **v3→v4 桥接表（R22）**：exam TSR A(v2候选×v3判据)=7/11 → B(v3目录候选×v3判据)=5/11 → C(v2候选×v4判据)=0/11 → D(v3目录候选×v4判据)=5/11。**A→D 净 −2 的逐条拆账（P1-3 修正）**：A→B = **−3 +1**（−3 条 wingbox `load.direction` 两代候选猜出不同方向 = 任务欠定义 R21；+1 条 `d2000_l2000_str12_frm4` 的 extra.end_shear/end_moment 由错变对）；A→C = −7 全落 v2 旧候选习惯键（analysis.type / bc.support 等纯描述键）；C→D = +5（判据收紧对 v4 新候选零影响，B=D=5 证明）。恒等式闭合 (A→C)+(C→D)=A→D | feagpt_repro/reports/bridge_v3_v4.json（含 bridge_A/B/C 三份逐格重算产物 + per_task 四列） | `python score_baseline.py --tasks <各版考卷> --report <各格报告>` + `_bridge_v3/`（b2e9b74 旧判据，sha256 见 reports/INDEX.md） | 2026-10-25 | GATED | exam 11 | active |
| C-026 | **官方产物索引（W5a'，R25/R27）**：`reports/` 为官方 artifact 唯一出处（`eval_runs/` 仅工作目录，被 gitignore）。索引明确「官方 vs 诊断」：**官方 headline = C-021 v4 5/11 / MSR 4/9；C-025 v5 重打分 4/11 = 诊断**；含考卷快照 `papers/tasks_v4.jsonl`（git 28e66bb 逐字节）与 `tasks_v5.jsonl`（tag v1.0-l3-v5）、逐版本候选目录对照、一条命令复现表 | feagpt_repro/reports/INDEX.md | `python check_claims.py` + `cat reports/INDEX.md` | 2026-10-25 | GATED | 6 类产物 | active |
| C-027 | **考卷 v6b 冻结（W5b，扩量前置；v6 → v6b 见下）**：55 条 L3（= 全部 55 个 case 的 L3 版），`exam_stratum` 三栏 **boundary 6 + extrapolation 13 + interpolation 6 = exam 25**（RUBRIC §1.1 预注册：headline = 合并 25、三栏明细并列、R12 分母 = 25；**与 C-021 的 11 条口径不可直接比**；三个数必须分清：C-021（v4，30 条 L3）= **11**，v6 的 boundary+extrap = **19**，v6 headline 合并 exam = **25**）。内插留出**全给翼盒 6 条**（`--interp-quota "wingbox:6"`，从 `train` 按 `task_id` 字典序确定性取）。**v6 → v6b 的原因（实测）**：v6 原名额 2/2/1/1 把 barrel(1→0)/open_hole(2→0)/panel(1→0) 三族的 train 抽空 ⇒ train 池只剩翼盒 13 条、`trivial_baselines` 的 T0 众数池缺 3 族、**T1 检索地板只有 1/4 族可算**（value_added 对照项失真）；且 train 只有 1 条的族抽出来当「内插」本身无意义（1 个点没有包络可内插）。改为全翼盒后 train 池 = 9/2/1/1、**4/4 族地板可算**。v6 原始稿留档 `papers/tasks_v6.jsonl`（不删，D10），v6b = `papers/tasks_v6b.jsonl`。**机器验收**：L1/L2 140→140 行内容零改动、老 30 条 L3 除新增 `exam_stratum` 外零改动（⇒ v5 候选对老题仍有效，R28 可证）、interp 全来自 train、dataset exam 与 stratum 一一对应 | feagpt_repro/reports/papers/tasks_v6b.jsonl + feagpt_repro/reports/papers/nl_human_v6b.jsonl + feagpt_repro/reports/papers/tasks_v6.jsonl（v6 原稿留档）+ feagpt_repro/reports/papers/SHA256SUMS | `python make_nl_human.py --quota "wingbox:34,open_hole_panel:11,fuselage_barrel:6,stiffened_panel:4" --interp-quota "wingbox:6"` + `python make_tasks.py` + `python _verify_tasks_v6.py` | 2026-10-25 | GATED | 55 L3 / exam 25（族构成 18/4/2/1） | active |
| C-021 | **L3 主基线（W4e/W4f 重跑，考卷 v4 + RUBRIC v2 预注册口径，正式对外 headline）**：glm-5.3-flash（R13）+ json_object/schema 校验/错误反馈修复循环≤3 轮。**headline = 留出集 exam 11 条（boundary 4 + extrap 7，R15）**：**TSR 5/11 (45.5%)、SFR 5/10 (50%)、MSR 4/9 (44.4%)**（全链 ccx，失败分层 model 8 + contract 3，env 0；W5a/R23 修订：原报 4/10 把编造澄清题 d1600 双重计数进 MSR，按任务属性排除后 4/9）；**value_added Δ+45.5pp vs T1 exam 0/11 —— n=11 < 20 ⇒ UNDERPOWERED 不得判 PASS（R12/R24）**；FPR：编造 2/4（barrel d1600 静默填 n_frames、panel 600x600 静默填 n_stringers）、过度澄清 1、问错字段 0（字段级判据 R17）；dev（train+val 19 条，仅诊断）：TSR 11/19、SFR 9/13。负控见 C-019。考卷 v4 实锤修正：barrel/panel NL 补长桁尺寸（builder 默认实读）+ n_stringers=0 改写「无长桁」+ 澄清题字段级别名；v3→v4 分数变化见 C-024 桥接表（净 -2 = −3 条 wingbox load.direction +1 条 d2000 extra 值修正） | feagpt_repro/reports/baseline_scorecard_L3_v4.json | `python score_baseline.py --candidates candidates_l3_v3 --tasks reports/papers/tasks_v4.jsonl --report reports/baseline_scorecard_L3_v4.json` + venv `python msr_l3.py --tasks reports/papers/tasks_v4.jsonl --report reports/baseline_scorecard_L3_v4.json` | 2026-10-25 | GATED (exam headline + full-chain MSR) | 30/30 生成 / exam 11 | active |
| C-020 | **L3 主基线（W4d，正式）**：glm-5.3-flash + json_object/schema 校验/错误反馈修复循环≤3 轮（SDK 无 logits 级 json_schema，如实标注）；考卷 v3（n=30，ec 澄清题 4 条）；拍板口径「工程层判+配置层只报 / 问对=对编造=错」。**TSR 18/30 (60%)**、**SFR 16/25 (64%)**、**MSR 11/30 (36.7%)**（全链 ccx，翼盒有 spec 12 条中 11 条全绿、fidelity ≤0.024%）；**value_added Δ+36.7pp PASS**（T1 地板同任务集 23.3%，n=30≥20 满足 R12）；FPR：编造 1/4（柱壳静默填 n_frames）、过度澄清 1；MSR 失败 13 条全为模型 spec 质量（语义自创键/字段错位/单位换算，归因见 msr_pipeline_failure_attribution.json）；考卷三轮修正实锤：ec 伪缺 bug / CFRP 材料卡缺失 / 网格尺寸+孔位硬编码（gold 4.0 写成 3mm） | feagpt_repro/eval_runs/baseline_scorecard_L3.json | `python score_baseline.py` + `python msr_l3.py`（venv） | 2026-10-25 | GATED | 30/30 | **superseded（W4e 专家第四轮）**：headline 混入 train/val（应只报留出 11 条，R15）+ MSR 6 条 gmsh 环境失败被记为模型失败（R16）+ SFR 计入 1 条编造（R20）+ rubric post-hoc（R18）。留出集重算见 C-021 |
| C-019 | 评测器负控全绿：**31/31** = PC-1 + NC-1..22（W4d 15 + W4e NC-15..19 + W5a NC-20..22）+ **NC-15b**（澄清双向）+ **NC-23..26**（W5a' artifact 入库/追踪/官方诊断分文件 + NC-26 缺 gold 必须硬报错，防静默算成 0/11）+ **NC-27..29**（W5b-3：NC-27 文本计数漂移必须被语义检查抓到 / NC-28 候选未覆盖全卷必须标记 / NC-29 跨口径混比必须拒绝）。**计数口径注意**：W4d 15/15、W4e/W5a 24/24 是同一套件的不同代数（旧文里「21 条」「23 条」均为漏计 NC-15b 的错账，P1-1/P1-2 已改） | feagpt_repro/reports/negative_controls_31.json | `python negative_controls.py` | 2026-10-25 | GATED | 31 条 | active |
| C-014 | 「关 3 55/55 全部双码验证」 | — | — | 2026-10-24 | — | — | **retracted**（被 C-003 取代；reported-only 不得计入 PASS，红线 R2） |
| C-015 | 「30 条人工 NL」 | tasks/nl_human.jsonl | — | 2026-10-24 | — | 30 | **superseded**（实为 template_human_designed，红线 R4；老王人工抽检后可升级） |
| C-016 | 「ID test 测内插」 | — | — | 2026-10-24 | — | — | **retracted**（边界留出 ≠ 内插，被 C-011 取代；内插留出 = v1.1） |

## 十维评分卡（模板见专家复评 §6.6/附录 D）

> **第六轮专家给的是 24/30**（我们的 W4f 自评 29 是虚高：证据/可复现/版本/文档各 −1、统计 −1）。
> W5a' 的整改就是把「证据 → 可复现 → 版本 → 文档」这四项从纸面变成机器可查；**统计有效性仍 1（n=11、无 CI）**，
> 所以对外依然不可承诺——这也是 W5b 必须先扩到 n≥20 的唯一理由。

| # | 维度 | W3 | W4f（自评） | 第六轮（专家） | W5a' 后 | 依据 |
|---|---|---:|---:|---:|---:|---|
| 1 | 目标一致性 | 3 | 3 | 3 | 3 | ROADMAP 主轴不变（评测基础设施） |
| 2 | 任务有效性 | 1 | 3 | 3 | 3 | 考卷 v4/v5 冻结（tag+sha256+`reports/papers/` 快照）；坐标系写死 30/30 |
| 3 | 判分有效性 | 1 | 3 | 3 | 3 | 字段级澄清（R17）+ SFR 编造对齐（R20）+ 负控 **31/31** + RUBRIC v4 预注册 |
| 4 | 证据等级 | 2 | 3 | 2 | **3** | `reports/` 入库 + `check_claims.py` 逐条 sha256/追踪检查（R25/R26） |
| 5 | 可复现性 | 1 | 3 | 2 | **3** | C-021 命令 `--tasks reports/papers/tasks_v4.jsonl` 重跑得 5/11、dev 11/19（逐项一致） |
| 6 | 版本治理 | 2 | 3 | 2 | **3** | 官方 `_v4` / 诊断 `_v5_rescore` 分文件（R27）+ `reports/INDEX.md` 版本对照 |
| 7 | 文档真实性 | 2 | 3 | 2 | **3** | C-019 24→**27**、C-024 归因改「−3+1」、C-009 superseded、README 链 INDEX 不链工作文件 |
| 8 | 统计有效性 | 1 | 2 | 1 | **1** | exam n=11、无 CI、单模型 ⇒ 不判 PASS（R12/R24）；**W5b 唯一硬缺口** |
| 9 | 范围纪律 | 3 | 3 | 3 | 3 | 红线条 R1–R31 挂账 |
| 10 | 计划执行 | 2 | 3 | 3 | 3 | W5a' 按专家 0.5 天口径收口 |
| **总分** | | **18/30** | **29/30** | **24/30** | **28/30** | 除统计有效性外全绿；W5b = 扩 n≥20 + CI + 第二模型才能动第 8 项 |

## 红线条（R1–R31，挂账常设）

R1 v1.0 冻结后不改 test/task ｜ R2 reported-only 不得计入 PASS ｜ R3 对外数字必须有 artifact+command（引 CLAIMS）
｜ R4 `human` 标签只用于人工撰写 ｜ R5 评测器改动必跑负控 ｜ R6 负控未全绿不得跑基线
｜ R7 不得用 test/boundary_holdout 训练或调参 ｜ R8 不得复活代理模型 KPI ｜ R9 SFR≠MSR≠TSR 不得互称
｜ R10 候选必须过契约校验（拒绝静默降级）｜ R11 成绩单必须覆盖全部考卷（partial 显式警告）
｜ R12 n<20 不判 value_added ｜ R13 模型 id 必须可引用 ｜ R14 skip_solve 不得称基线（正式基线必含全链 MSR）
｜ R15 对外 headline 只能用留出集（boundary+extrap）；train/val 单列开发集（W4e）
｜ R16 环境失败不得计为模型失败；MSR 启动必做依赖预检（W4e）
｜ R17 澄清判分必须字段级；单字关键词不得作为通过依据（W4e）
｜ R18 rubric 必须预注册（RUBRIC.md）；看过模型输出后修改的 rubric 标 post-hoc 需重跑（W4f）
｜ R19 schema / builder / grader 三者必须一致；可判的 spec 必须可建（试建闸，W4f）
｜ R20 SFR 与 TSR 的编造口径必须一致；不一致时不得并列报告（W4e）
｜ R21 任务 NL 必须给坐标系/载荷方向；不得用「法向」类未定义词（W5a）
｜ R22 口径/考卷/prompt 同时变化必须做桥接表；不能只报新分（W5a）
｜ R23 MSR 分母必须与 RUBRIC 一致；澄清/编造题不得双重计数（W5a）
｜ R24 n_exam<20 不得做模型调优/对外承诺；只能做扩量（W5a）
｜ **R25 官方 artifact 必须入库**（`feagpt_repro/reports/`，不得在 gitignore 的 `eval_runs/`）；每条 active CLAIM 必须可追溯到被 git 追踪的文件（W5a'）
｜ **R26 CLAIMS 自检必须可执行**：artifact 缺失/未追踪/路径与 command 不一致 ⇒ `check_claims.py` 失败；每 W 块收口必跑（W5a'）
｜ **R27 官方 vs 诊断必须分文件**；诊断结果不得占用官方 artifact 路径，同一路径不得被两条 active claim 占用（W5a'）
｜ **R28 旧候选不得评新考卷**；考卷变更后必须重生成候选，重打分只能标 diagnostic（W5a'）
｜ **R29 CLAIMS 语义计数必须自检**：claim/README/RUBRIC 文本里的数字必须等于 artifact 实读值（`check_claims.py --semantic`），不一致 ⇒ 失败。结构检查（在不在/是否追踪）**不算**通过（W5b-3）
｜ **R30 跨口径不得直接比**：C-021 的 **11** 条、v6 的 boundary+extrap **19** 条、v6 headline **25** 条是三个不同分母；混比必须被 `compare_scorecards.py` 拒绝（rc=3），只能三栏并列（W5b-3）
｜ **R31 生成前必须 key 预检 + 1 条冒烟**：不得直接 55 条盲跑；候选未覆盖全卷（`candidates_missing` 非空）的成绩单必须标 `partial_candidates` 且不得当正式成绩（W5b-3）
