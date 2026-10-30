# L2 澄清题：双口径（CONFLICT N-17 → 拍板 C'）

- 卷：`tasks.jsonl`　任务表：`tasks/tasks.jsonl`
- 状态：**not_run**（L2 未跑满，`passed` 如实为空）
- 判据：check_l2_leak.py 语义前缀匹配（d<N>/frm<N>/str<N>/...）；数值撞车不算泄漏（例：str4 揭示 n_stringers，不揭示 rib_thickness）

## 两套分母必须并列

| 口径 | 分母 n | 含义 |
|---|---|---|
| `clarify_all` | **64** | 全卷 L2 澄清题（含 name 泄漏的无效子集） |
| `clarify_informative` | **45** | name 未泄漏被省略值的可判子集（真的在考「会不会追问」） |
| （无效子集，不进任何单一口径） | 19 | spec.name 直接写出被省略值 ⇒ clarify 判据无效（N-17） |

> 两个分母不同（clarify_all 64 ≠ clarify_informative 45）⇒ 禁止相减、禁止据此排名（R54）；R66 要求无效子集隔离并双报，只报一侧即 S-53 红。

## 无效子集明细（19 条）

| family | case_id | 省略字段 | name 里的证据 |
|---|---|---|---|
| fuselage_barrel | `fuselage_barrel_d1600_l1600_str8_frm3` | `n_frames` | `frm3` |
| fuselage_barrel | `fuselage_barrel_d2000_l1600_str8_frm3` | `n_stringers` | `str8` |
| fuselage_barrel | `fuselage_barrel_d2000_l1800_str8_frm3` | `n_stringers` | `str8` |
| fuselage_barrel | `fuselage_barrel_d2000_l2000_str12_frm4` | `n_frames` | `frm4` |
| fuselage_barrel | `fuselage_barrel_d2000_l2000_t2_str8_frm3` | `n_stringers` | `str8` |
| wingbox | `naca4412_wingbox_n_ribs9_chord1000` | `n_ribs` | `n_ribs9` |
| wingbox | `naca4412_wingbox_size_skin2p5` | `skin_thickness` | `skin2` |
| wingbox | `naca4412_wingbox_sweep40` | `sweep_deg` | `sweep40` |
| open_hole_panel | `open_hole_panel_400x200_d20` | `length` | `400x200` |
| open_hole_panel | `open_hole_panel_400x200_d20_cfrp090s` | `hole_d` | `d20` |
| open_hole_panel | `open_hole_panel_400x200_d20_cfrp45s_d40` | `width` | `400x200` |
| open_hole_panel | `open_hole_panel_400x200_d20_cfrpqi` | `length` | `400x200` |
| open_hole_panel | `open_hole_panel_400x200_d20_offcentre` | `hole_d` | `d20` |
| open_hole_panel | `open_hole_panel_400x200_d30` | `hole_d` | `d30` |
| open_hole_panel | `open_hole_panel_400x200_d40_offcentre` | `width` | `400x200` |
| open_hole_panel | `open_hole_panel_400x200_d50` | `length` | `400x200` |
| open_hole_panel | `open_hole_panel_500x250_d45` | `hole_d` | `d45` |
| open_hole_panel | `open_hole_panel_600x300_d30` | `hole_d` | `d30` |
| stiffened_panel | `stiffened_panel_700x600_str4` | `n_stringers` | `str4` |
