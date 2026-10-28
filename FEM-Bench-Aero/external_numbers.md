# 对外数字源（单一来源，勿手抄）

> 由 `feagpt_repro/make_external_numbers.py` 从权威 JSON 生成；更新数据集后必须重跑本脚本再改对外文档。

| 项 | 数值 | 分母口径 | 来源 |
|---|---|---|---|
| 算例规模 | 64 条 × 2 棵求解器树 = 128 个算例目录 | 64 条 spec | manifest.summary |
| 几何等价类 | 63（重复 0、跨 split 泄漏 0） | 64 条 spec | manifest.summary |
| 划分 | train 25 / val 17 / test 22 | 64 条 spec | manifest.cases 实算 |
| — fuselage_barrel | 1-3-3（共 7） | 7 条 spec | manifest.cases 实算 |
| — open_hole_panel | 2-5-6（共 13） | 13 条 spec | manifest.cases 实算 |
| — stiffened_panel | 1-2-2（共 5） | 5 条 spec | manifest.cases 实算 |
| — wingbox | 21-7-11（共 39） | 39 条 spec | manifest.cases 实算 |
| 关 1 网格 | **64/64**（最差 minJ 0.4636 @ `fuselage_barrel_d1600_l1600_str8_frm3`、tri3 0、阈值 minJ ≥ 0.3） | 64 条 spec（两树 msh 逐字节相同，不重复计） | manifest.readings（eval_dataset 逐条复算） |
| 关 3 双码 | **39 field-level + 18 scalar-disp-gated + 7 reported-only**（不说 64/64） | 64 条 spec | gate3_all55_d37 |
| 关 4 语义 | 128/128 | 128 个算例目录（两树各一份） | gate4_v11 |
| 自洽 | 128/128、重复 0、配对 64/64 | 128 个算例目录（配对按 64 条 spec 计） | verify_dataset_v11 |
| 划分复算 | 0 failures | 64 条 spec | eval_report_v11 |
| 基线（已冻结为附录） | max_disp test 2.631 %，CI [0.89, 4.51]，常数地板 49.439 | **v1（55 条，翼盒 test 6 条）—— 不可与 v1.1 并列** | baseline_d36_final |

## M14 硬限制（对外承诺必读，W4a 纠偏 P1-2）

> **版本**：以下三条全部属于 v1（55 条时代；翼盒 34 条）。**v1.1（翼盒 39 条）未重跑**，不可当作 v1.1 成绩，也不可与本表上方任何一格并列相减。

1. **vM 峰值未收敛**：12→6 mm 仍 +12.9 %，应力真值带 ≥13 % 偏不安全低估 —— ⚠ **证据缺口**：无机器可读 artifact —— h_convergence.json 只记录 max_disp 的收敛；该结论目前只在 STAGE_GATE_M14.md 正文，须补 artifact 后才可升为 GATED
2. **位移良定义（12→6 mm 变化 −0.48 %）**（`h_convergence.json`）；2.63 % 是「组合插值」成绩，不是「新设计」成绩；对外承诺写 5–9 %，不写 3 % —— STAGE_GATE_M14 §4.4
3. **全体 34 条留一 5.35 %**（中位 2.57 / p90 14.09 / 最大 33.10） —— `_probe_m14/all_loo.json`（现读，n_cases=34）；报数必须带 p90+max

## 分母口径警告（R54，T-A8）

- 关 1 / 关 3 / 划分复算的分母是 **spec 数**；关 4 / 自洽的分母是 **算例目录数**（= spec 数 × 2 树）。
- **两套分母不得相减、不得互算百分比差**。本表已单列「分母口径」列，引用时须连同该列一起引。
- 基线段的分母是 **v1 数据集的 v1 划分**，与 v1.1 任何一格都不可比（R30/R39）。
- M14 三条限制的分母是 **v1 翼盒 34 条**，同样与 v1.1 不可比。
