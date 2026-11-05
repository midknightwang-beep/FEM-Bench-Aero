# L2 prompt arm 对比（glm-5.3-flash，n=16）

- base：`candidates_l2i_v2_glm` prompt_sha `03129c56d83b…`
- strict：`candidates_l2i_v3s_glm` prompt_sha `99466166dc04…`
- 通过：base **2/16**（12.5%）→ strict **10/16**（62.5%）
- 配对：base对&strict错 **0** / base错&strict对 **8** ⇒ McNemar 精确双侧 **p = 0.0078**
- 判类逐条相同 **7/16**（43.8%），pass 翻转 **8** 条
- 转写错误（题面已给却被改坏）题数：base **12** → strict **5**
- 追问数（本卷一律记错）：base **2** → strict **0**

| task_id | 族 | split | base | strict | base 失败字段 | strict 失败字段 |
|---|---|---|---|---|---|---|
| `L2i_fuselage_barrel_d1600_l1600_str8_frm3` | fuselage_barrel | extrapolation_test | spec_bad | spec_ok | mesh.leading_edge_threshold, mesh.refine_at_leading_edge, mesh.size_chord, mesh.size_span, extra.moment_axis, extra.shear_axis | — |
| `L2i_fuselage_barrel_d1800_l2000_str8_frm3` | fuselage_barrel | val | spec_bad | spec_ok | mesh.leading_edge_threshold, mesh.refine_at_leading_edge, mesh.size_chord, mesh.size_span, extra.moment_axis, extra.shear_axis | — |
| `L2i_fuselage_barrel_d2000_l1800_str8_frm3` | fuselage_barrel | extrapolation_test | spec_bad | spec_ok | mesh.leading_edge_threshold, mesh.refine_at_leading_edge, mesh.size_chord, mesh.size_span, extra.moment_axis, extra.shear_axis | — |
| `L2i_fuselage_barrel_d2000_l2000_str8_frm3` | fuselage_barrel | train | spec_bad | spec_ok | extra.moment_axis, extra.shear_axis | — |
| `L2i_naca4412_wingbox` | wingbox | train | spec_bad | spec_ok | airfoil.stringer_flange_width | — |
| `L2i_naca4412_wingbox_n_ribs3_chord1000` | wingbox | boundary_holdout | spec_bad | spec_ok | airfoil.stringer_flange_width | — |
| `L2i_naca4412_wingbox_n_ribs6_chord1000` | wingbox | extrapolation_test | spec_ok | spec_ok | — | — |
| `L2i_naca4412_wingbox_n_ribs7_chord1000` | wingbox | val | spec_ok | spec_ok | — | — |
| `L2i_open_hole_panel_400x200_d20` | open_hole_panel | train | spec_bad | spec_bad | mesh.leading_edge_threshold, mesh.refine_at_leading_edge, mesh.size_chord, mesh.size_span, mesh.size (not in gold) | mesh.size_chord, mesh.size_span, mesh.size (not in gold) |
| `L2i_open_hole_panel_400x200_d20_cfrp45s` | open_hole_panel | val | clarify_wrong | spec_ok | — | — |
| `L2i_open_hole_panel_400x200_d20_cfrp45s_d40` | open_hole_panel | extrapolation_test | clarify_wrong | spec_bad | — | mesh.size_chord, mesh.size_span, mesh.size (not in gold) |
| `L2i_open_hole_panel_400x200_d20_offcentre` | open_hole_panel | extrapolation_test | spec_bad | spec_bad | mesh.algorithm_2d, mesh.leading_edge_threshold, mesh.min_jacobian, mesh.recombination_algorithm, mesh.recombine, mesh.refine_at_leading_edge | mesh.size_chord, mesh.size_span, mesh.size (not in gold) |
| `L2i_stiffened_panel_600x600` | stiffened_panel | train | spec_bad | spec_bad | mesh.leading_edge_threshold, mesh.refine_at_leading_edge, mesh.size_chord, mesh.size_span, mesh.size (not in gold) | mesh.algorithm_2d, mesh.leading_edge_threshold, mesh.min_jacobian, mesh.recombination_algorithm, mesh.recombine, mesh.refine_at_leading_edge |
| `L2i_stiffened_panel_600x600_str3` | stiffened_panel | extrapolation_test | spec_bad | spec_bad | mesh.size_chord, mesh.size_span, mesh.size (not in gold) | mesh.size (not in gold) |
| `L2i_stiffened_panel_700x600_str4` | stiffened_panel | extrapolation_test | spec_bad | spec_ok | mesh.algorithm_2d, mesh.leading_edge_threshold, mesh.min_jacobian, mesh.recombination_algorithm, mesh.recombine, mesh.refine_at_leading_edge | — |
| `L2i_stiffened_panel_800x600` | stiffened_panel | val | spec_bad | spec_bad | mesh.size_chord, mesh.size_span, mesh.size (not in gold) | mesh.size_chord, mesh.size_span, mesh.size (not in gold) |
