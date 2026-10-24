# 对外数字源（单一来源，勿手抄）

> 由 `feagpt_repro/make_external_numbers.py` 从权威 JSON 生成；更新数据集后必须重跑本脚本再改对外文档。

| 项 | 数值 | 来源 |
|---|---|---|
| 算例规模 | 55 条 × 2 棵求解器树 = 110 个算例目录 | manifest.summary |
| 几何等价类 | 54（重复 0、跨 split 泄漏 0） | manifest.summary |
| 划分 | train 25 / val 17 / test 13 | manifest.cases 实算 |
| — fuselage_barrel | 1-3-2（共 6） | manifest.cases 实算 |
| — open_hole_panel | 2-5-4（共 11） | manifest.cases 实算 |
| — stiffened_panel | 1-2-1（共 4） | manifest.cases 实算 |
| — wingbox | 21-7-6（共 34） | manifest.cases 实算 |
| 关 1 网格 | 55/55（最差 minJ 0.4636、tri3 0） | gates_all55_d36 |
| 关 3 双码 | **34 field-level + 15 scalar-disp-gated + 6 reported-only**（不说 55/55） | gate3_all55_d37 |
| 关 4 语义 | 110/110 | gate4_d36 |
| 自洽 | 110/110、重复 0、配对 True | verify_dataset_d36 |
| 划分复算 | 0 failures | eval_report_d36 |
| 基线（已冻结为附录） | max_disp test 2.631 %，CI [0.89, 4.51]，常数地板 49.439 | baseline_d36_final |

## M14 硬限制（对外承诺必读，W4a 纠偏 P1-2）

1. **vM 峰值未收敛**：12→6 mm 仍 +12.9 %，应力真值带 ≥13 % 偏不安全低估（位移良定义 −0.48 %）—— `_probe_m14/h_convergence.json`
2. **2.63 % 是「组合插值」成绩**，不是「新设计」成绩；对外承诺写 **5–9 %**，不写 3 % —— STAGE_GATE_M14 §4.4
3. **全体 34 条留一 5.35 %**（中位 2.57 / p90 14.09 / 最大 33.10）—— `_probe_m14/all_loo.json`；报数必须带 p90+max
