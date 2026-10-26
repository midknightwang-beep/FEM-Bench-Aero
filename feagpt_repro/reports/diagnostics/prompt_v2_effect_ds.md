# C-029 vs C-031 跨模型诊断（同考卷 v6c）

> 诊断文件（R37）。同 paper sha / 同判据 ⇒ R30 允许出差值；**不进 headline**。

- A = `C-031 v6c x dsv4pro (paper v6c, candidates dsv4pro)`（candidates_l3_v6c_dsv4pro）exam TSR **20/25**
- B = `C-033 v6c x dsv4pro prompt-v2 (paper v6c, candidates ds_p2)`（candidates_l3_v6c_ds_p2）exam TSR **22/25**

## 1. exam 逐题 2×2

| 格 | 条数 | 题 |
|---|---:|---|
| both_pass | 20 | L3_fuselage_barrel_d2000_l2000_str12_frm4<br>L3_naca4412_wingbox_n_ribs3_chord1000<br>L3_naca4412_wingbox_n_ribs3_chord800<br>L3_naca4412_wingbox_n_ribs5_chord800<br>L3_naca4412_wingbox_n_ribs7_chord800<br>L3_naca4412_wingbox_recombination_algorithm3<br>L3_naca4412_wingbox_size_skin2<br>L3_naca4412_wingbox_size_skin4<br>L3_naca4412_wingbox_size_span1600<br>L3_naca4412_wingbox_size_span2400<br>L3_naca4412_wingbox_size_span2400_skin2<br>L3_naca4412_wingbox_size_span3000_skin1p5<br>L3_naca4412_wingbox_str3<br>L3_naca4412_wingbox_str3_T<br>L3_naca4412_wingbox_str5<br>L3_naca4412_wingbox_sweep40_taper040<br>L3_naca4412_wingbox_taper090<br>L3_open_hole_panel_400x200_d20_offcentre<br>L3_open_hole_panel_400x200_d40_offcentre<br>L3_open_hole_panel_600x300_d60 |
| only_a | 0 | — |
| only_b | 2 | L3_fuselage_barrel_d1600_l1600_str8_frm3<br>L3_stiffened_panel_600x600_str3 |
| neither | 3 | L3_naca4412_wingbox<br>L3_naca4412_wingbox_web1_offcentre<br>L3_open_hole_panel_400x200_d20_cfrp45s_d40 |

## 2. dev 逐题 2×2

| 格 | 条数 |
|---|---:|
| both_pass | 22 |
| only_a | 0 |
| only_b | 0 |
| neither | 8 |

## 3. 共同失败题的失败字段（判「同因」还是「异因」）

**字段集完全相同**（同一批字段错 ⇒ 更像题面/prompt 诱导）：

- `L3_naca4412_wingbox_web1_offcentre`：['extra.end_torque', 'extra.torque_axis_dof']

**字段集不同**：

| 题 | 共同错 | 仅 A 错 | 仅 B 错 |
|---|---|---|---|
| `L3_open_hole_panel_400x200_d20_cfrp45s_d40` | [] | ['params.layup'] | [] |

**无字段明细**（clarify/contract/solver 类，不过 spec_fidelity）：

- `L3_naca4412_wingbox`

## 4. category 分布

| category | A | B |
|---|---:|---:|
| clarify_ok | 0 | 2 |
| clarify_wrong | 0 | 1 |
| fabricated | 3 | 0 |
| no_output | 0 | 1 |
| spec_fail | 2 | 1 |
| spec_pass | 20 | 20 |
