# l3_v6c_p2_sysfix vs l3_v6c_ds_p2_sysfix —— 跨模型诊断

> 诊断文件（R37）。**不进 headline**。

> 模型：A `glm-5.3-flash` / B `deepseek-v4-pro`；prompt_sha256：A `6b90daf07bbe…` / B `6b90daf07bbe…`

> **R30：同 paper sha / 同 prompt sha / 同判据 ⇒ 允许出差值。**

- A = `l3_v6c_p2_sysfix`（candidates_l3_v7sysfix_glm）exam TSR **23/25**
- B = `l3_v6c_ds_p2_sysfix`（candidates_l3_v7sysfix_ds）exam TSR **22/25**

## 0. exam MSR 口径对齐（R54）

| | MSR（条件） | MSR 分母 | exam SFR | 被排除的模型侧无输出 |
|---|---|---:|---|---|
| A | 20/22 | 22 | 20/22 | — |
| B | 19/22 | 22 | 20/23 | — |

> R54：两侧 exam MSR 分母相同（22）⇒ 允许出 Δ。

- exam MSR：A 20/22 · B 19/22（Δ -4.5 pp）

## 1. exam 逐题 2×2

| 格 | 条数 | 题 |
|---|---:|---|
| both_pass | 22 | L3_fuselage_barrel_d2000_l2000_str12_frm4<br>L3_naca4412_wingbox<br>L3_naca4412_wingbox_n_ribs3_chord1000<br>L3_naca4412_wingbox_n_ribs3_chord800<br>L3_naca4412_wingbox_n_ribs5_chord800<br>L3_naca4412_wingbox_n_ribs7_chord800<br>L3_naca4412_wingbox_recombination_algorithm3<br>L3_naca4412_wingbox_size_skin2<br>L3_naca4412_wingbox_size_skin4<br>L3_naca4412_wingbox_size_span1600<br>L3_naca4412_wingbox_size_span2400<br>L3_naca4412_wingbox_size_span2400_skin2<br>L3_naca4412_wingbox_size_span3000_skin1p5<br>L3_naca4412_wingbox_str3<br>L3_naca4412_wingbox_str3_T<br>L3_naca4412_wingbox_str5<br>L3_naca4412_wingbox_sweep40_taper040<br>L3_naca4412_wingbox_taper090<br>L3_open_hole_panel_400x200_d20_offcentre<br>L3_open_hole_panel_400x200_d40_offcentre<br>L3_open_hole_panel_600x300_d60<br>L3_stiffened_panel_600x600_str3 |
| only_a | 1 | L3_fuselage_barrel_d1600_l1600_str8_frm3 |
| only_b | 0 | — |
| neither | 2 | L3_naca4412_wingbox_web1_offcentre<br>L3_open_hole_panel_400x200_d20_cfrp45s_d40 |

## 2. dev 逐题 2×2

| 格 | 条数 |
|---|---:|
| both_pass | 22 |
| only_a | 1 |
| only_b | 1 |
| neither | 6 |

## 3. 共同失败题的失败字段（判「同因」还是「异因」）

**字段集完全相同**（同一批字段错 ⇒ 更像题面/prompt 诱导）：

- `L3_naca4412_wingbox_web1_offcentre`：['extra.end_torque', 'extra.torque_axis_dof']
- `L3_open_hole_panel_400x200_d20_cfrp45s_d40`：['params.layup']

## 4. category 分布

| category | A | B |
|---|---:|---:|
| clarify_ok | 3 | 2 |
| fabricated | 0 | 1 |
| spec_fail | 2 | 2 |
| spec_pass | 20 | 20 |
