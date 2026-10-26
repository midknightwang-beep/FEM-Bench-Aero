# C-032 v6c x glm prompt-v2 (paper v6c, candidates glm_p2) vs C-033 v6c x dsv4pro prompt-v2 (paper v6c, candidates ds_p2) —— 跨模型诊断

> 诊断文件（R37）。**不进 headline**。

> 模型：A `glm-5.3-flash` / B `deepseek-v4-pro`；prompt_sha256：A `ce225186cafa…` / B `ce225186cafa…`

> **R30：同 paper sha / 同 prompt sha / 同判据 ⇒ 允许出差值。**

- A = `C-032 v6c x glm prompt-v2 (paper v6c, candidates glm_p2)`（candidates_l3_v6c_glm_p2）exam TSR **23/25**
- B = `C-033 v6c x dsv4pro prompt-v2 (paper v6c, candidates ds_p2)`（candidates_l3_v6c_ds_p2）exam TSR **22/25**

## 0. exam MSR 口径对齐（R54）

| | MSR（条件） | MSR 分母 | exam SFR | 被排除的模型侧无输出 |
|---|---|---:|---|---|
| A | 20/22 | 22 | 20/22 | — |
| B | 20/21 | 21 | 20/21 | L3_open_hole_panel_400x200_d20_cfrp45s_d40 |

> **★ R54：两侧 exam MSR 分母不同（22 vs 21）⇒ pct 不得直减、不得据此排名。** 分母只含「产出 spec 的非澄清题」，模型侧无输出已在 TSR/FPR 记过；A/B 的差异中有一半可能只是分母不同造成的。若必须比，先对齐分母（用 SFR + 逐题 2×2）或改用 full MSR 同分母口径。

- exam MSR：A 20/22 · B 20/21（分母不同，不出 Δ）

## 1. exam 逐题 2×2

| 格 | 条数 | 题 |
|---|---:|---|
| both_pass | 22 | L3_fuselage_barrel_d1600_l1600_str8_frm3<br>L3_fuselage_barrel_d2000_l2000_str12_frm4<br>L3_naca4412_wingbox_n_ribs3_chord1000<br>L3_naca4412_wingbox_n_ribs3_chord800<br>L3_naca4412_wingbox_n_ribs5_chord800<br>L3_naca4412_wingbox_n_ribs7_chord800<br>L3_naca4412_wingbox_recombination_algorithm3<br>L3_naca4412_wingbox_size_skin2<br>L3_naca4412_wingbox_size_skin4<br>L3_naca4412_wingbox_size_span1600<br>L3_naca4412_wingbox_size_span2400<br>L3_naca4412_wingbox_size_span2400_skin2<br>L3_naca4412_wingbox_size_span3000_skin1p5<br>L3_naca4412_wingbox_str3<br>L3_naca4412_wingbox_str3_T<br>L3_naca4412_wingbox_str5<br>L3_naca4412_wingbox_sweep40_taper040<br>L3_naca4412_wingbox_taper090<br>L3_open_hole_panel_400x200_d20_offcentre<br>L3_open_hole_panel_400x200_d40_offcentre<br>L3_open_hole_panel_600x300_d60<br>L3_stiffened_panel_600x600_str3 |
| only_a | 1 | L3_naca4412_wingbox |
| only_b | 0 | — |
| neither | 2 | L3_naca4412_wingbox_web1_offcentre<br>L3_open_hole_panel_400x200_d20_cfrp45s_d40 |

## 2. dev 逐题 2×2

| 格 | 条数 |
|---|---:|
| both_pass | 20 |
| only_a | 2 |
| only_b | 2 |
| neither | 6 |

## 3. 共同失败题的失败字段（判「同因」还是「异因」）

**字段集完全相同**（同一批字段错 ⇒ 更像题面/prompt 诱导）：

- `L3_naca4412_wingbox_web1_offcentre`：['extra.end_torque', 'extra.torque_axis_dof']

**字段集不同**：

| 题 | 共同错 | 仅 A 错 | 仅 B 错 |
|---|---|---|---|
| `L3_open_hole_panel_400x200_d20_cfrp45s_d40` | [] | ['params.layup'] | [] |

## 4. category 分布

| category | A | B |
|---|---:|---:|
| clarify_ok | 3 | 2 |
| clarify_wrong | 0 | 1 |
| no_output | 0 | 1 |
| spec_fail | 2 | 1 |
| spec_pass | 20 | 20 |
