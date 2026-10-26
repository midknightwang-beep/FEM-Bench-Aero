# C-029 v6c (paper v6c, candidates v6c) vs C-032 v6c x glm prompt-v2 (paper v6c, candidates glm_p2) —— prompt/harness 消融（同模型）

> 诊断文件（R37）。**不进 headline**。

> 模型：A `glm-5.3-flash` / B `glm-5.3-flash`；prompt_sha256：A `UNKNOWN…` / B `ce225186cafa…`

> **★ R53：两代 prompt_sha256 不同 ⇒ 本表只能作同一 harness 变量的消融证据，不得把 A/B 当作两份可并列引用的成绩，更不得跨模型拼比。**

- A = `C-029 v6c (paper v6c, candidates v6c)`（candidates_l3_v6c）exam TSR **23/25**
- B = `C-032 v6c x glm prompt-v2 (paper v6c, candidates glm_p2)`（candidates_l3_v6c_glm_p2）exam TSR **23/25**

## 1. exam 逐题 2×2

| 格 | 条数 | 题 |
|---|---:|---|
| both_pass | 23 | L3_fuselage_barrel_d1600_l1600_str8_frm3<br>L3_fuselage_barrel_d2000_l2000_str12_frm4<br>L3_naca4412_wingbox<br>L3_naca4412_wingbox_n_ribs3_chord1000<br>L3_naca4412_wingbox_n_ribs3_chord800<br>L3_naca4412_wingbox_n_ribs5_chord800<br>L3_naca4412_wingbox_n_ribs7_chord800<br>L3_naca4412_wingbox_recombination_algorithm3<br>L3_naca4412_wingbox_size_skin2<br>L3_naca4412_wingbox_size_skin4<br>L3_naca4412_wingbox_size_span1600<br>L3_naca4412_wingbox_size_span2400<br>L3_naca4412_wingbox_size_span2400_skin2<br>L3_naca4412_wingbox_size_span3000_skin1p5<br>L3_naca4412_wingbox_str3<br>L3_naca4412_wingbox_str3_T<br>L3_naca4412_wingbox_str5<br>L3_naca4412_wingbox_sweep40_taper040<br>L3_naca4412_wingbox_taper090<br>L3_open_hole_panel_400x200_d20_offcentre<br>L3_open_hole_panel_400x200_d40_offcentre<br>L3_open_hole_panel_600x300_d60<br>L3_stiffened_panel_600x600_str3 |
| only_a | 0 | — |
| only_b | 0 | — |
| neither | 2 | L3_naca4412_wingbox_web1_offcentre<br>L3_open_hole_panel_400x200_d20_cfrp45s_d40 |

## 2. dev 逐题 2×2

| 格 | 条数 |
|---|---:|
| both_pass | 21 |
| only_a | 2 |
| only_b | 1 |
| neither | 6 |

## 3. 共同失败题的失败字段（判「同因」还是「异因」）

**字段集完全相同**（同一批字段错 ⇒ 更像题面/prompt 诱导）：

- `L3_naca4412_wingbox_web1_offcentre`：['extra.end_torque', 'extra.torque_axis_dof']
- `L3_open_hole_panel_400x200_d20_cfrp45s_d40`：['params.layup']

## 4. category 分布

| category | A | B |
|---|---:|---:|
| clarify_ok | 3 | 3 |
| spec_fail | 2 | 2 |
| spec_pass | 20 | 20 |
