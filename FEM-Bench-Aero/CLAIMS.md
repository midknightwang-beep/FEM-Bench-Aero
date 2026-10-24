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
| C-014 | 「关 3 55/55 全部双码验证」 | — | — | 2026-10-24 | — | — | **retracted**（被 C-003 取代；reported-only 不得计入 PASS，红线 R2） |
| C-015 | 「30 条人工 NL」 | tasks/nl_human.jsonl | — | 2026-10-24 | — | 30 | **superseded**（实为 template_human_designed，红线 R4；老王人工抽检后可升级） |
| C-016 | 「ID test 测内插」 | — | — | 2026-10-24 | — | — | **retracted**（边界留出 ≠ 内插，被 C-011 取代；内插留出 = v1.1） |

## 十维评分卡（W4a 后自评，模板见专家复评 §6.6/附录 D）

| # | 维度 | W3 时 | W4a 后 | 依据 |
|---|---|---:|---:|---|
| 1 | 目标一致性 | 3 | 3 | ROADMAP 主轴不变 |
| 2 | 任务有效性 | 1 | 2 | L2 轮换+去泄漏 ✅、L3 接入 ✅；ID 内插留 v1.1 |
| 3 | 判分有效性 | 1 | 3 | spec_fidelity 强制闸 + 负控 9/9（C-009） |
| 4 | 证据等级 | 2 | 3 | 关 3 分级 34/15/6 + CLAIMS 账本 |
| 5 | 可复现性 | 1 | 3 | fetch_data 全链验证（C-013）+ validate_schema 一条命令 |
| 6 | 版本治理 | 2 | 2 | git + tag；数据以归档包分发（DVC = v1.1 可选） |
| 7 | 文档真实性 | 2 | 3 | CLAIMS 账本 + human 标签改正 + 单一数字源同步 |
| 8 | 统计有效性 | 1 | 1 | test 13 条、n 小——W4b 分报 + T0/T1 对照后重评 |
| 9 | 范围纪律 | 3 | 3 | 红线 R1–R8 挂账 |
| 10 | 计划执行 | 2 | 3 | W4a 按期、负控全绿 |
| **总分** | | **18/30** | **26/30** | **≥24 且无单项 ≤1 ⇒ 允许进入 W4b** |

## 红线条（R1–R8，挂账常设）

R1 v1.0 冻结后不改 test/task ｜ R2 reported-only 不得计入 PASS ｜ R3 对外数字必须有 artifact+command（引 CLAIMS）
｜ R4 `human` 标签只用于人工撰写 ｜ R5 评测器改动必跑负控 ｜ R6 负控未全绿不得跑基线
｜ R7 不得用 test/boundary_holdout 训练或调参 ｜ R8 不得复活代理模型 KPI
