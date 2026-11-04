# L2 prompt 复现性检查（同一 prompt 两遍）（glm-5.3-flash，n=16）

- 第1遍：`candidates_l2i_v3sm_glm` prompt_sha `24cf0978369f…`
- 第2遍：`candidates_l2i_v3sm2_glm` prompt_sha `24cf0978369f…`
- 通过：第1遍 **16/16**（100.0%）→ 第2遍 **14/16**（87.5%）
- 配对：第1遍对&第2遍错 **2** / 第1遍错&第2遍对 **0** ⇒ McNemar 精确双侧 **p = 0.5000**
- 判类逐条相同 **14/16**（87.5%），pass 翻转 **2** 条
- 转写错误（题面已给却被改坏）题数：第1遍 **0** → 第2遍 **1**
- 追问数（本卷一律记错）：第1遍 **0** → 第2遍 **0**

| task_id | 族 | split | 第1遍 | 第2遍 | 第1遍 失败字段 | 第2遍 失败字段 |
|---|---|---|---|---|---|---|
| `L2i_fuselage_barrel_d1600_l1600_str8_frm3` | fuselage_barrel | extrapolation_test | spec_ok | spec_ok | — | — |
| `L2i_fuselage_barrel_d1800_l2000_str8_frm3` | fuselage_barrel | val | spec_ok | spec_ok | — | — |
| `L2i_fuselage_barrel_d2000_l1800_str8_frm3` | fuselage_barrel | extrapolation_test | spec_ok | spec_ok | — | — |
| `L2i_fuselage_barrel_d2000_l2000_str8_frm3` | fuselage_barrel | train | spec_ok | spec_ok | — | — |
| `L2i_naca4412_wingbox` | wingbox | train | spec_ok | spec_ok | — | — |
| `L2i_naca4412_wingbox_n_ribs3_chord1000` | wingbox | boundary_holdout | spec_ok | spec_ok | — | — |
| `L2i_naca4412_wingbox_n_ribs6_chord1000` | wingbox | extrapolation_test | spec_ok | spec_ok | — | — |
| `L2i_naca4412_wingbox_n_ribs7_chord1000` | wingbox | val | spec_ok | spec_ok | — | — |
| `L2i_open_hole_panel_400x200_d20` | open_hole_panel | train | spec_ok | spec_ok | — | — |
| `L2i_open_hole_panel_400x200_d20_cfrp45s` | open_hole_panel | val | spec_ok | spec_ok | — | — |
| `L2i_open_hole_panel_400x200_d20_cfrp45s_d40` | open_hole_panel | extrapolation_test | spec_ok | spec_ok | — | — |
| `L2i_open_hole_panel_400x200_d20_offcentre` | open_hole_panel | extrapolation_test | spec_ok | spec_ok | — | — |
| `L2i_stiffened_panel_600x600` | stiffened_panel | train | spec_ok | spec_bad | — | mesh.algorithm_2d, mesh.element_order, mesh.leading_edge_threshold, mesh.min_jacobian, mesh.recombination_algorithm, mesh.recombine |
| `L2i_stiffened_panel_600x600_str3` | stiffened_panel | extrapolation_test | spec_ok | llm_error | — | — |
| `L2i_stiffened_panel_700x600_str4` | stiffened_panel | extrapolation_test | spec_ok | spec_ok | — | — |
| `L2i_stiffened_panel_800x600` | stiffened_panel | val | spec_ok | spec_ok | — | — |
