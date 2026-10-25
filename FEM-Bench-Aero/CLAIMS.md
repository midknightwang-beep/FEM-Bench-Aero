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
| C-020 | **L3 主基线（W4d，正式）**：glm-5.3-flash + json_object/schema 校验/错误反馈修复循环≤3 轮（SDK 无 logits 级 json_schema，如实标注）；考卷 v3（n=30，ec 澄清题 4 条）；拍板口径「工程层判+配置层只报 / 问对=对编造=错」。**TSR 18/30 (60%)**、**SFR 16/25 (64%)**、**MSR 11/30 (36.7%)**（全链 ccx，翼盒有 spec 12 条中 11 条全绿、fidelity ≤0.024%）；**value_added Δ+36.7pp PASS**（T1 地板同任务集 23.3%，n=30≥20 满足 R12）；FPR：编造 1/4（柱壳静默填 n_frames）、过度澄清 1；MSR 失败 13 条全为模型 spec 质量（语义自创键/字段错位/单位换算，归因见 msr_pipeline_failure_attribution.json）；考卷三轮修正实锤：ec 伪缺 bug / CFRP 材料卡缺失 / 网格尺寸+孔位硬编码（gold 4.0 写成 3mm） | feagpt_repro/eval_runs/baseline_scorecard_L3.json | `python score_baseline.py` + `python msr_l3.py`（venv） | 2026-10-25 | GATED (full-chain MSR) | 30/30 | active |
| C-019 | 评测器负控 15/15（PC-1 + NC-1..14，含契约拒绝/L3 删块/NC-14 工程层口径四探针） | feagpt_repro/eval_runs/negative_controls.json | `python negative_controls.py` | 2026-10-25 | GATED | 15 条 | active |（PC-1 + NC-1..13，含契约拒绝/L3 删块） | feagpt_repro/eval_runs/negative_controls.json | `python negative_controls.py` | 2026-10-24 | GATED | 14 条 | active |
| C-014 | 「关 3 55/55 全部双码验证」 | — | — | 2026-10-24 | — | — | **retracted**（被 C-003 取代；reported-only 不得计入 PASS，红线 R2） |
| C-015 | 「30 条人工 NL」 | tasks/nl_human.jsonl | — | 2026-10-24 | — | 30 | **superseded**（实为 template_human_designed，红线 R4；老王人工抽检后可升级） |
| C-016 | 「ID test 测内插」 | — | — | 2026-10-24 | — | — | **retracted**（边界留出 ≠ 内插，被 C-011 取代；内插留出 = v1.1） |

## 十维评分卡（W4a/W4d 后自评，模板见专家复评 §6.6/附录 D）

| # | 维度 | W3 时 | W4a 后 | W4d 后 | 依据 |
|---|---|---:|---:|---:|---|
| 1 | 目标一致性 | 3 | 3 | 3 | ROADMAP 主轴不变（评测基础设施） |
| 2 | 任务有效性 | 1 | 2 | 3 | L3 主口径落地（30 条 + 4 澄清型 + clarify_keywords 可审计） |
| 3 | 判分有效性 | 1 | 3 | 3 | spec_fidelity 工程层口径 + 负控 15/15（NC-14 四探针护口径） |
| 4 | 证据等级 | 2 | 3 | 3 | C-020 全链 MSR GATED（翼盒 fidelity ≤0.024%） |
| 5 | 可复现性 | 1 | 3 | 3 | score_baseline/msr_l3/negative_controls 一条命令；venv 说明落盘 |
| 6 | 版本治理 | 2 | 2 | 3 | git 全程（W4a–W4d 逐 commit）+ 考卷版本三轮留痕 |
| 7 | 文档真实性 | 2 | 3 | 3 | C-020 如实标注修复循环非 logits 级约束、MSR 失败归因落盘 |
| 8 | 统计有效性 | 1 | 1 | 2 | L3 n=30≥20 + 同任务集 T1 对照；boundary/extrap 子集仍小 |
| 9 | 范围纪律 | 3 | 3 | 3 | 红线 R1–R14 挂账 |
| 10 | 计划执行 | 2 | 3 | 3 | W4a–W4d 四轮按期收口 |
| **总分** | | **18/30** | **26/30** | **29/30** | **≥24 且无单项 ≤1 ⇒ 基线成绩单可对外引用（C-020）** |

## 红线条（R1–R14，挂账常设）

R1 v1.0 冻结后不改 test/task ｜ R2 reported-only 不得计入 PASS ｜ R3 对外数字必须有 artifact+command（引 CLAIMS）
｜ R4 `human` 标签只用于人工撰写 ｜ R5 评测器改动必跑负控 ｜ R6 负控未全绿不得跑基线
｜ R7 不得用 test/boundary_holdout 训练或调参 ｜ R8 不得复活代理模型 KPI ｜ R9 SFR≠MSR≠TSR 不得互称
｜ R10 候选必须过契约校验（拒绝静默降级）｜ R11 成绩单必须覆盖全部考卷（partial 显式警告）
｜ R12 n<20 不判 value_added ｜ R13 模型 id 必须可引用 ｜ R14 skip_solve 不得称基线（正式基线必含全链 MSR）
