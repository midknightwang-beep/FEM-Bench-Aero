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
| C-009 | 评测器判分有效性：负控 9/9（PC-1 PASS + NC-1..8 FAIL） | feagpt_repro/eval_runs/negative_controls.json | `python negative_controls.py` | 2026-10-24 | GATED | 9 条 | active |
| C-010 | 任务层 140 行 = L1 55 + L2 55（轮换 13 字段、泄漏 0）+ L3 30（template_human_designed） | feagpt_repro/tasks/tasks.jsonl | `python make_tasks.py --dry` | 2026-10-24 | GATED | 140 | active |
| C-011 | boundary_holdout 6 条（翼盒 train 边界锚点整类留出 28.6%）；**真内插 ID test = v1.1** | feagpt_repro/tasks/tasks.jsonl | `python make_tasks.py --dry` | 2026-10-24 | GATED | 6/21 | active |
| C-012 | schema 双份 55/55 过 + 反向探针（死 airfoil 拒 / 越界 55° 拒） | FEM-Bench-Aero/schema_truth.json, schema_task.json | `python validate_schema.py` | 2026-10-24 | GATED | 55/55 | active |
| C-013 | 数据本体可获取：v1.0-data.tar.gz 86 MB + SHA256SUMS + fetch_data 全链验证 | F:/FEA_Archive_20261024/SHA256SUMS.txt | `python fetch_data.py --src <path>` | 2026-10-24 | GATED | 55/55 | active |
| C-017 | **L1 spec-copy smoke（W4b，非模型基线）**：考卷 19 条 SFR **0/19**（boundary 0/6、extrap 0/13）；归因 airfoil.chord×12 + bc.clamp×7——无 schema 约束解码时 LLM 指令遵循失败（airfoil 整组缺失/bc 块丢失），非建模能力结论；n=19 UNDERPOWERED | feagpt_repro/eval_runs/baseline_scorecard.json | `python score_baseline.py candidates` | 2026-10-24 | GATED (spec-only) | 19/19 | active |
| C-018 | 「LLM 基线 TSR 2/2 = 100%」 | eval_runs/baseline_scorecard.json（22:08 旧快照） | — | 2026-10-24 | — | 2 条 | **superseded**（partial + skip_solve + 旧快照，被 C-017 取代；红线 R11/R14） |
| C-021 | **L3 主基线（W4e/W4f 重跑，考卷 v4 + RUBRIC v2 预注册口径，正式对外）**：glm-5.3-flash（R13）+ json_object/schema 校验/错误反馈修复循环≤3 轮。**headline = 留出集 exam 11 条（boundary 4 + extrap 7，R15）**：**TSR 5/11 (45.5%)、SFR 5/10 (50%)、MSR 4/10 (40%)**（全链 ccx，失败分层 model 8 + contract 3（试建闸拦下 cfrp layup 错块），env 0）；**value_added Δ+45.5pp vs T1 exam 0/11 —— n=11 < 20 ⇒ UNDERPOWERED 不得判 PASS（R12）**；FPR：编造 2/4（barrel d1600 静默填 n_frames、panel 600x600 静默填 n_stringers）、过度澄清 1、问错字段 0（字段级判据 R17）；dev（train+val 19 条，仅诊断）：TSR 11/19、SFR 9/13。负控 21/21。考卷 v4 实锤修正：barrel/panel NL 补长桁尺寸（builder 默认实读）+ n_stringers=0 改写「无长桁」+ 澄清题字段级别名 | feagpt_repro/eval_runs/baseline_scorecard_L3.json | `python score_baseline.py --candidates candidates_l3_v3` + venv `python msr_l3.py` | 2026-10-25 | GATED (exam headline + full-chain MSR) | 30/30 生成 / exam 11 | active |
| C-020 | **L3 主基线（W4d，正式）**：glm-5.3-flash + json_object/schema 校验/错误反馈修复循环≤3 轮（SDK 无 logits 级 json_schema，如实标注）；考卷 v3（n=30，ec 澄清题 4 条）；拍板口径「工程层判+配置层只报 / 问对=对编造=错」。**TSR 18/30 (60%)**、**SFR 16/25 (64%)**、**MSR 11/30 (36.7%)**（全链 ccx，翼盒有 spec 12 条中 11 条全绿、fidelity ≤0.024%）；**value_added Δ+36.7pp PASS**（T1 地板同任务集 23.3%，n=30≥20 满足 R12）；FPR：编造 1/4（柱壳静默填 n_frames）、过度澄清 1；MSR 失败 13 条全为模型 spec 质量（语义自创键/字段错位/单位换算，归因见 msr_pipeline_failure_attribution.json）；考卷三轮修正实锤：ec 伪缺 bug / CFRP 材料卡缺失 / 网格尺寸+孔位硬编码（gold 4.0 写成 3mm） | feagpt_repro/eval_runs/baseline_scorecard_L3.json | `python score_baseline.py` + `python msr_l3.py`（venv） | 2026-10-25 | GATED | 30/30 | **superseded（W4e 专家第四轮）**：headline 混入 train/val（应只报留出 11 条，R15）+ MSR 6 条 gmsh 环境失败被记为模型失败（R16）+ SFR 计入 1 条编造（R20）+ rubric post-hoc（R18）。留出集重算见 C-021 |
| C-019 | 评测器负控全绿（W4d 15/15；W4e 起为 PC-1 + NC-1..19 共 21 条，含字段级澄清双向探针/bc与material自创键/MSR预检/exam集检查） | feagpt_repro/eval_runs/negative_controls.json | `python negative_controls.py` | 2026-10-25 | GATED | 21 条 | active |
| C-014 | 「关 3 55/55 全部双码验证」 | — | — | 2026-10-24 | — | — | **retracted**（被 C-003 取代；reported-only 不得计入 PASS，红线 R2） |
| C-015 | 「30 条人工 NL」 | tasks/nl_human.jsonl | — | 2026-10-24 | — | 30 | **superseded**（实为 template_human_designed，红线 R4；老王人工抽检后可升级） |
| C-016 | 「ID test 测内插」 | — | — | 2026-10-24 | — | — | **retracted**（边界留出 ≠ 内插，被 C-011 取代；内插留出 = v1.1） |

## 十维评分卡（W4a/W4d 后自评，模板见专家复评 §6.6/附录 D）

| # | 维度 | W3 时 | W4a 后 | W4d 后 | W4f 后 | 依据 |
|---|---|---:|---:|---:|---|
| 1 | 目标一致性 | 3 | 3 | 3 | 3 | ROADMAP 主轴不变（评测基础设施） |
| 2 | 任务有效性 | 1 | 2 | 3 | 3 | L3 考卷 v4 冻结（tag+sha256）；barrel/panel 契约缺口已补 |
| 3 | 判分有效性 | 1 | 3 | 3 | 3 | 字段级澄清（R17）+ SFR 编造对齐（R20）+ 负控 21/21 + RUBRIC.md 预注册（R18） |
| 4 | 证据等级 | 2 | 3 | 3 | 3 | C-021 exam 口径 GATED；MSR 失败分层 env/contract/model/solver（env=0） |
| 5 | 可复现性 | 1 | 3 | 3 | 3 | 一条命令 + venv + 考卷 v4 tag/sha256 + RUBRIC 冻结 |
| 6 | 版本治理 | 2 | 2 | 3 | 3 | git 全程 + 考卷 v4 tag v1.0-l3-v4 |
| 7 | 文档真实性 | 2 | 3 | 3 | 3 | C-020 主动标 superseded；C-021 如实报 underpowered |
| 8 | 统计有效性 | 1 | 1 | 2 | 2 | exam n=11 underpowered 如实标注不判 PASS（R12/R15）；扩到 n≥20 = W5 |
| 9 | 范围纪律 | 3 | 3 | 3 | 3 | 红线 R1–R20 挂账 |
| 10 | 计划执行 | 2 | 3 | 3 | 3 | W4a–W4f 六轮按期收口 |
| **总分** | | **18/30** | **26/30** | **29/30** | **29/30** | C-021 可对外引用（headline 带 underpowered 标注）；留出集扩到 n≥20 = W5 前置 |

## 红线条（R1–R20，挂账常设）

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
