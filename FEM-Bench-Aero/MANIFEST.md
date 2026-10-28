# FEM-Bench-Aero · 数据集清单（M4）

由 `make_manifest.py` 生成，**确定性**（无时间戳，重跑字节一致）。机器可读版是 `manifest.json`。

- 发布树 `modeling/`：**64 条 case**，**63 个几何等价类**
- 划分：train **25** / val **17** / test **22**（目标比例 60%:20%:20%）
- 角色：`ablation 1, baseline 3, degenerate 2, feature 10, sweep 48`
- 树内重复模型 **0**；跨集泄漏的等价类 **0**
- 交叉验证证据（`_xval/`，商业许可，**不发布**）：64 条

> **等价类**：几何（形状 + 壁厚）相同的 case 归为一类。同一类的成员**必须**在同一 split —— 这是「等价类不得跨集」的落地。

## train （25 条）

| case | 族 | 角色 | 等价类 | 节点 | max\|u\| (mm) | 峰值 vM | minJ | tri3 |
|---|---|---|---|---:|---:|---:|---:|---:|
| `fuselage_barrel_d2000_l2000_str8_frm3` | fuselage_barrel | baseline | `589369d3` | 158524 | 2.63103 | 249.3983 | 0.5159 | 0 |
| `naca4412_wingbox` | wingbox | baseline | `4afd1ea3(2)` | 5074 | 2.36544 | 10.6048 | 0.6249 | 0 |
| `naca4412_wingbox_n_ribs3_chord1000` | wingbox | sweep | `4cf4571c` | 4668 | 2.37234 | 10.4393 | 0.5965 | 0 |
| `naca4412_wingbox_n_ribs3_chord800` | wingbox | sweep | `1927d89d` | 3679 | 4.54015 | 15.9584 | 0.5950 | 0 |
| `naca4412_wingbox_n_ribs5_chord800` | wingbox | sweep | `791f1043` | 4057 | 4.52673 | 15.7618 | 0.5950 | 0 |
| `naca4412_wingbox_recombination_algorithm3` | wingbox | ablation | `4afd1ea3(2)` | 5281 | 2.36487 | 10.6097 | 0.5725 | 0 |
| `naca4412_wingbox_size_skin2` | wingbox | sweep | `621898f4` | 5074 | 3.54230 | 15.8945 | 0.6249 | 0 |
| `naca4412_wingbox_size_skin4` | wingbox | sweep | `226322ea` | 5074 | 1.77567 | 7.9846 | 0.6249 | 0 |
| `naca4412_wingbox_size_span1600` | wingbox | sweep | `950289bb` | 4273 | 1.25062 | 8.6686 | 0.6204 | 0 |
| `naca4412_wingbox_size_span2400` | wingbox | sweep | `a29aa8f4` | 5836 | 4.01972 | 12.5066 | 0.5966 | 0 |
| `naca4412_wingbox_str3` | wingbox | feature | `7af92379` | 7387 | 2.21940 | 10.1406 | 0.5228 | 0 |
| `naca4412_wingbox_str5` | wingbox | feature | `87013030` | 8205 | 2.13545 | 9.8692 | 0.5351 | 0 |
| `naca4412_wingbox_sweep10` | wingbox | sweep | `d8e081a5` | 5484 | 2.58760 | 9.8297 | 0.6266 | 0 |
| `naca4412_wingbox_sweep20` | wingbox | sweep | `47f64aa4` | 5222 | 3.16934 | 10.4759 | 0.4902 | 0 |
| `naca4412_wingbox_sweep20_taper060` | wingbox | sweep | `838838dd` | 7771 | 3.96104 | 9.4148 | 0.5523 | 0 |
| `naca4412_wingbox_sweep30` | wingbox | sweep | `19ca7eaf` | 5347 | 4.38434 | 13.4251 | 0.6353 | 0 |
| `naca4412_wingbox_sweep30_taper080` | wingbox | sweep | `e38d85cc` | 5302 | 4.70502 | 12.5760 | 0.5606 | 0 |
| `naca4412_wingbox_sweep35` | wingbox | sweep | `ce92e32b` | 5687 | 5.42926 | 15.6169 | 0.5725 | 0 |
| `naca4412_wingbox_taper060` | wingbox | sweep | `86cf8d83` | 7950 | 3.38415 | 11.4068 | 0.5593 | 0 |
| `naca4412_wingbox_taper080` | wingbox | sweep | `411d36da` | 5125 | 2.75209 | 10.7650 | 0.5484 | 0 |
| `naca4412_wingbox_taper090` | wingbox | sweep | `0218d6b2` | 4871 | 2.53636 | 10.5802 | 0.5492 | 0 |
| `naca4412_wingbox_web1` | wingbox | sweep | `4aae9b75` | 5369 | 2.96458 | 12.6971 | 0.5532 | 0 |
| `open_hole_panel_400x200_d20` | open_hole_panel | baseline | `8d80c9bb` | 9861 | 0.05750 | 30.3800 | 0.6084 | 0 |
| `open_hole_panel_400x200_d20_cfrp090s` | open_hole_panel | sweep | `ca16d791` | 9861 | 0.05735 | 49.0194 | 0.6084 | 0 |
| `stiffened_panel_600x600` | stiffened_panel | degenerate | `7ba2e122` | 46432 | 0.96175 | 2.9682 | 0.6167 | 0 |

<details><summary>分配理由</summary>

- `fuselage_barrel_d2000_l2000_str8_frm3` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_n_ribs3_chord1000` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_n_ribs3_chord800` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_n_ribs5_chord800` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_recombination_algorithm3` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_size_skin2` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_size_skin4` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_size_span1600` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_size_span2400` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_str3` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_str5` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_sweep10` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_sweep20` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_sweep20_taper060` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_sweep30` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_sweep30_taper080` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_sweep35` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_taper060` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_taper080` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_taper090` — 落在训练包络内（未命中任何留出区域）
- `naca4412_wingbox_web1` — 落在训练包络内（未命中任何留出区域）
- `open_hole_panel_400x200_d20` — 落在训练包络内（未命中任何留出区域）
- `open_hole_panel_400x200_d20_cfrp090s` — 落在训练包络内（未命中任何留出区域）
- `stiffened_panel_600x600` — 落在训练包络内（未命中任何留出区域）

</details>

## val （17 条）

| case | 族 | 角色 | 等价类 | 节点 | max\|u\| (mm) | 峰值 vM | minJ | tri3 |
|---|---|---|---|---:|---:|---:|---:|---:|
| `fuselage_barrel_d1800_l2000_str8_frm3` | fuselage_barrel | sweep | `f91e55e0` | 143402 | 2.80159 | 286.7960 | 0.5159 | 0 |
| `fuselage_barrel_d2000_l1600_str8_frm3` | fuselage_barrel | sweep | `a912e177` | 129632 | 2.55112 | 249.3506 | 0.5159 | 0 |
| `fuselage_barrel_d2000_l2000_t2_str8_frm3` | fuselage_barrel | sweep | `9c77e267` | 158524 | 4.67870 | 372.5256 | 0.5159 | 0 |
| `naca4412_wingbox_n_ribs7_chord1000` | wingbox | sweep | `db9dab06` | 5593 | 2.35805 | 10.7432 | 0.6083 | 0 |
| `naca4412_wingbox_n_ribs9_chord1000` | wingbox | sweep | `6085570a` | 5706 | 2.35033 | 10.6934 | 0.6337 | 0 |
| `naca4412_wingbox_size_skin1p5` | wingbox | sweep | `4227a599` | 5074 | 4.71648 | 21.2263 | 0.6249 | 0 |
| `naca4412_wingbox_size_span3000` | wingbox | sweep | `aba008bb` | 7116 | 7.74748 | 15.3412 | 0.5047 | 0 |
| `naca4412_wingbox_sweep40` | wingbox | sweep | `00195084` | 5697 | 7.01434 | 18.6518 | 0.4861 | 0 |
| `naca4412_wingbox_taper040` | wingbox | sweep | `d3d62cf4` | 14937 | 4.48886 | 12.2254 | 0.5064 | 0 |
| `naca4412_wingbox_web2` | wingbox | sweep | `60981a5c` | 5653 | 2.85579 | 11.5722 | 0.5784 | 0 |
| `open_hole_panel_400x200_d20_cfrp45s` | open_hole_panel | sweep | `e8219d41` | 9861 | 0.22585 | 42.8224 | 0.6084 | 0 |
| `open_hole_panel_400x200_d20_cfrpqi` | open_hole_panel | sweep | `1a539873` | 9861 | 0.07776 | 30.3105 | 0.6084 | 0 |
| `open_hole_panel_400x200_d40` | open_hole_panel | sweep | `68f73f8a` | 8682 | 0.05940 | 31.3227 | 0.6213 | 0 |
| `open_hole_panel_400x200_d50` | open_hole_panel | sweep | `32e9f572` | 7918 | 0.06092 | 32.3135 | 0.6266 | 0 |
| `open_hole_panel_600x300_d30` | open_hole_panel | sweep | `2db453f8` | 20736 | 0.08528 | 30.1900 | 0.5808 | 0 |
| `stiffened_panel_800x600` | stiffened_panel | degenerate | `652d537e` | 61834 | 1.56189 | 4.3026 | 0.6183 | 0 |
| `stiffened_panel_800x600_str3` | stiffened_panel | feature | `b8239f10` | 67797 | 0.02898 | 2.4047 | 0.5978 | 0 |

<details><summary>分配理由</summary>

- `fuselage_barrel_d1800_l2000_str8_frm3` — 尺寸单维外推（直径 1800 ≠ 2000）
- `fuselage_barrel_d2000_l1600_str8_frm3` — 尺寸单维外推（长度 1600 ≠ 2000）
- `fuselage_barrel_d2000_l2000_t2_str8_frm3` — 尺寸单维外推（壁厚 2 ≠ 3）
- `naca4412_wingbox_n_ribs7_chord1000` — 单维外推（肋 7 > 5，弦保持默认）
- `naca4412_wingbox_n_ribs9_chord1000` — 单维外推（肋 9 > 5，弦保持默认）
- `naca4412_wingbox_size_skin1p5` — 尺寸单维外推（壁厚 1.5 出 train 区间 [2, 4]）
- `naca4412_wingbox_size_span3000` — 尺寸单维外推（展长 3000 出 train 区间 [1600, 2400]）
- `naca4412_wingbox_sweep40` — 平面形状单维外推（后掠 40° > train 已学 35°，锥度中性）
- `naca4412_wingbox_taper040` — 平面形状单维外推（锥度 0.4 < train 已学 0.6，后掠中性）
- `naca4412_wingbox_web2` — 单维外推（腹板 2 > train 已学 1，位置仍等分）
- `open_hole_panel_400x200_d20_cfrp45s` — 复材单维外推（铺层 [45/-45]s≠[0/90]s；D30 标量轴计数 =1）
- `open_hole_panel_400x200_d20_cfrpqi` — 复材单维外推（铺层 [0/45/-45/90]s≠[0/90]s；D30 标量轴计数 =1）
- `open_hole_panel_400x200_d40` — 单维外推（孔径比 λ 0.200 > train 已学 0.1，孔仍居中）
- `open_hole_panel_400x200_d50` — 单维外推（孔径比 λ 0.250 > train 已学 0.1，孔仍居中）
- `open_hole_panel_600x300_d30` — 尺寸单维外推（600x300 ≠ train 已学 400x200）
- `stiffened_panel_800x600` — 平板尺寸单维外推（800x600 ≠ train 已学 600x600）
- `stiffened_panel_800x600_str3` — 平板尺寸单维外推（800x600 ≠ train 已学 600x600）

</details>

## test （22 条）

| case | 族 | 角色 | 等价类 | 节点 | max\|u\| (mm) | 峰值 vM | minJ | tri3 |
|---|---|---|---|---:|---:|---:|---:|---:|
| `fuselage_barrel_d1600_l1600_str8_frm3` | fuselage_barrel | sweep | `f8b43cc6` | 103715 | 3.00697 | 343.6255 | 0.4636 | 0 |
| `fuselage_barrel_d2000_l1800_str8_frm3` | fuselage_barrel | sweep | `e2d05ddc` | 143702 | 2.60917 | 248.1617 | 0.5159 | 0 |
| `fuselage_barrel_d2000_l2000_str12_frm4` | fuselage_barrel | sweep | `a9604f56` | 169606 | 2.56923 | 258.4794 | 0.5211 | 0 |
| `naca4412_wingbox_n_ribs6_chord1000` | wingbox | sweep | `b3016d21` | 5300 | 2.36213 | 10.6114 | 0.6204 | 0 |
| `naca4412_wingbox_n_ribs7_chord800` | wingbox | sweep | `006310d0` | 4352 | 4.51232 | 15.8507 | 0.5099 | 0 |
| `naca4412_wingbox_size_chord900` | wingbox | sweep | `cd44c190` | 4446 | 3.20784 | 12.7506 | 0.6372 | 0 |
| `naca4412_wingbox_size_skin2p5` | wingbox | sweep | `aec9b4e5` | 5074 | 2.83654 | 12.7140 | 0.6249 | 0 |
| `naca4412_wingbox_size_span2400_skin2` | wingbox | sweep | `08adca20` | 5836 | 6.02314 | 18.7392 | 0.5966 | 0 |
| `naca4412_wingbox_size_span3000_skin1p5` | wingbox | sweep | `58fefd58` | 7116 | 15.47333 | 30.7125 | 0.5047 | 0 |
| `naca4412_wingbox_str3_T` | wingbox | feature | `37f4725e` | 29447 | 2.11507 | 11.1847 | 0.5332 | 0 |
| `naca4412_wingbox_str4` | wingbox | feature | `5237ded5` | 6995 | 2.17553 | 10.0575 | 0.5060 | 0 |
| `naca4412_wingbox_sweep40_taper040` | wingbox | sweep | `808b798f` | 15681 | 9.86735 | 15.9405 | 0.5448 | 0 |
| `naca4412_wingbox_taper070` | wingbox | sweep | `ec5bfe48` | 6450 | 3.02838 | 11.0956 | 0.5702 | 0 |
| `naca4412_wingbox_web1_offcentre` | wingbox | feature | `02769a56` | 5574 | 3.06080 | 14.0702 | 0.5467 | 0 |
| `open_hole_panel_400x200_d20_cfrp45s_d40` | open_hole_panel | sweep | `a22486ac` | 8682 | 0.23270 | 41.4246 | 0.6213 | 0 |
| `open_hole_panel_400x200_d20_offcentre` | open_hole_panel | feature | `a4a89bc0` | 9349 | 0.05863 | 30.6932 | 0.6562 | 0 |
| `open_hole_panel_400x200_d30` | open_hole_panel | sweep | `bb04f712` | 9524 | 0.05828 | 30.5868 | 0.5481 | 0 |
| `open_hole_panel_400x200_d40_offcentre` | open_hole_panel | feature | `104c69f9` | 8082 | 0.06479 | 33.7727 | 0.6626 | 0 |
| `open_hole_panel_500x250_d45` | open_hole_panel | sweep | `e16d67d6` | 12863 | 0.05851 | 24.8856 | 0.5710 | 0 |
| `open_hole_panel_600x300_d60` | open_hole_panel | sweep | `634a9fb4` | 16151 | 0.08815 | 31.3501 | 0.6020 | 0 |
| `stiffened_panel_600x600_str3` | stiffened_panel | feature | `bc4990b0` | 51401 | 0.01526 | 1.7744 | 0.5367 | 0 |
| `stiffened_panel_700x600_str4` | stiffened_panel | feature | `e30e5c5d` | 61449 | 0.01402 | 1.6466 | 0.5561 | 0 |

<details><summary>分配理由</summary>

- `fuselage_barrel_d1600_l1600_str8_frm3` — 尺寸双维外推（直径 1600 ≠ 2000 且 长度 1600 ≠ 2000）
- `fuselage_barrel_d2000_l1800_str8_frm3` — v1.1 内插留出（spec.extra.split_tag = v11_interior_holdout，显式声明）
- `fuselage_barrel_d2000_l2000_str12_frm4` — 双维外推（长桁 12 与框 4 同时超出 train 包络）
- `naca4412_wingbox_n_ribs6_chord1000` — v1.1 内插留出（spec.extra.split_tag = v11_interior_holdout，显式声明）
- `naca4412_wingbox_n_ribs7_chord800` — 双维外推（肋 7 > 5 且 弦 800 ≠ 1000）
- `naca4412_wingbox_size_chord900` — v1.1 内插留出（spec.extra.split_tag = v11_interior_holdout，显式声明）
- `naca4412_wingbox_size_skin2p5` — v1.1 内插留出（spec.extra.split_tag = v11_interior_holdout，显式声明）
- `naca4412_wingbox_size_span2400_skin2` — 尺寸双轴组合外推（展长 2400 ≠ 2000 且 壁厚 2 ≠ 3；train 各站只动单轴，交互项未见过）
- `naca4412_wingbox_size_span3000_skin1p5` — 尺寸双维外推（展长 3000 出 train 区间 [1600, 2400] 且 壁厚 1.5 出 train 区间 [2, 4]）
- `naca4412_wingbox_str3_T` — 新截面形式（train 里没有锚定 'T' 形式）
- `naca4412_wingbox_str4` — v1.1 内插留出（spec.extra.split_tag = v11_interior_holdout，显式声明）
- `naca4412_wingbox_sweep40_taper040` — 新平面形状组合（后掠 40° × 锥度 0.4 兼具，至少一轴出 train 值域 ≤35° / ≥0.6）
- `naca4412_wingbox_taper070` — v1.1 内插留出（spec.extra.split_tag = v11_interior_holdout，显式声明）
- `naca4412_wingbox_web1_offcentre` — 新形式：腹板偏离等分（给定 [0.35] ≠ 等分 [0.475]；闭室不再等面积，Bredt-Batho 不再描述该截面）
- `open_hole_panel_400x200_d20_cfrp45s_d40` — 复材多维外推（铺层 [45/-45]s≠[0/90]s + λ=0.2≠0.1；D30 标量轴计数 ≥2）
- `open_hole_panel_400x200_d20_offcentre` — 新形式：偏心孔（(120, 60) 偏离形心 (200, 100)；train 只有中心孔，偏心后 Howland 无解析对照）
- `open_hole_panel_400x200_d30` — v1.1 内插留出（spec.extra.split_tag = v11_interior_holdout，显式声明）
- `open_hole_panel_400x200_d40_offcentre` — 新形式：偏心孔（(120, 60) 偏离形心 (200, 100)；train 只有中心孔，偏心后 Howland 无解析对照）
- `open_hole_panel_500x250_d45` — v1.1 内插留出（spec.extra.split_tag = v11_interior_holdout，显式声明）
- `open_hole_panel_600x300_d60` — 双维外推（λ 0.200 与 600x300 同时 ≠ 锚点 λ 0.1 / 400x200）
- `stiffened_panel_600x600_str3` — 族内新形式（光板 ⇒ 3 根长桁）
- `stiffened_panel_700x600_str4` — v1.1 内插留出（spec.extra.split_tag = v11_interior_holdout，显式声明）

</details>

## 多成员等价类（1 个）

- `4afd1ea3fd9f` → `naca4412_wingbox`, `naca4412_wingbox_recombination_algorithm3`（split: train）

## 已知限制

- val 共 17 条（64 条下 6:2:2 目标要求约 13 条）：val 的绝对数量仍是样本量的限制，不是划分规则的缺陷。
- 每个族都有 val 样本，val 的族代表性完整。
- 当前划分是**规则**（feagpt/manifest.py :: HOLDOUT_REGIONS）而不是显式表：每族声明留出区域，未命中区域即进 train。规则已按 D12 锁定口径 A 复现 11 条（见 manifest.py :: D12_LOCKED_SPLIT，由 eval_dataset 断言），并在 D15（后掠/锥形兼具 -> test）与 D16（单维外推 -> val）上扩展。
- 柱壳族（fuselage_barrel）的网格是**有包络的**（D19，2026-10-05）：n_stringers 只接受 0 或 ≥ 5，1–4 根会在框的外弧（r ≈ R 的框/蒙皮粘结线）上留下三角（3str/2frm 20、4str/2frm 16、4str/3frm 22）。五种修法（simple 重组 / 只细分框经线 / 蒙皮与框一起细分 / 框专用尺寸场 / 逐面 2-D 算法）已全部实测否决，故族 _validate 直接**拒绝**该区间，而不是建一个带三角的模型。数据集因此暂时拿不到 1–4 根长桁的柱壳；val 落在 10/12/16 根、train 落在 5–8 根，均未受影响。
- 柱壳族（fuselage_barrel）的双码交叉判据口径 = **D20（2026-10-05）**：门的量是「**剔除自由端端载环后的结构 max|u|**」（该环由族自己的 fuselage.barrel_nodes 圈定，不是写死的坐标带）与「沿轴 **截面形心挠度剖面**」（偏差对**尖端挠度**归一，避免近零截面把相对误差放大），两者容差仍 1 %。**模型全域 max|u| 仍如实印出，但不用于判绿/红**：实测 ccx 2.63102 vs abaqus 2.67818 mm = 1.79 %，峰值落在**自由端框的内缘自由边**上（框建成 30×3 平环板，只沿 r = 1000 与蒙皮粘接），是「节点力压在自由壳边」的局部效应：纯内压（光滑面力）两码只差 0.25 %，剔除该环后 0.42 %，把端载只压在筒壳环上（3226→644 节点）峰值仍在同一位置、差仅降到 1.11 %。
- 柱壳族（fuselage_barrel）的内压方向 = **D21（2026-10-05）修正**：`*DLOAD ... P` 是沿壳面法向的**带符号**压力，而壳体法向由建面方式决定 —— `occ.revolve` 建出的桶段蒙皮与拉伸翼盒蒙皮/平板矩形**法向相反**，所以写死 `-abs(p)` 的旧 deck 实际把桶段**由外向内压**：实测中面径向位移 −0.22725 mm，而薄壁闭式解 w = pR²/(Et) = **+0.22800 mm**。符号现由建面器声明（GeometryResult.pressure_dload_sign，默认 −1 保证翼盒/平板 23 条零扰动，桶段声明 +1）。修正后实测 +0.22725 mm，差 −0.329 %。⚠️ 门禁读数：只有 `pressure.radial-growth` 抓得住这个符号错 —— `pressure.hoop-membrane` 比的是 von Mises，压/拉状态下都为正，符号错也照样 PASS。
- 柱壳族（fuselage_barrel）**只支持 blade 截面长桁**（D22，2026-10-05）：建面器（geometry.build_fuselage_barrel）每条长桁只出一片平面径向腹板，**从不读 stringer_kind**，所以 T/L 等带翼缘截面会被静默建成 blade。实测 T(fw=30) 与 blade 逐位相同（158548 节点 / 157972 单元 / minJ 0.5159），而 topology 按 3 面/长桁要求 48 面、只观察到 16 —— gate 4 会 FAIL（非静默），但族 schema、_validate、_design_fuselage 三处都曾声称支持。现由 _validate **拒绝**非 blade（与 D19 同一 posture），并留档为待实现能力；副作用是 manifest._fuselage_new_form（新截面形式 → test）暂无数据可匹配，T3 的留出形态改由**双维外推**提供。
- 柱壳族（fuselage_barrel）的尺寸维**只朝收缩方向外推**（D27，2026-10-06）：CalculiX 在分解前会把每个壳单元**展开成实体**（这**不是** `OUTPUT=3D` 的代价 —— 关掉该参数后 `number of equations` 3489495、`nnz` 194129961、`.12d` 字节数 68750934 三项分毫不变），于是方程数 ≈ **14.9 × 壳节点数**（三点实测一致）。在本机 16491000 kB 内存 + 16866936 kB 交换（≈ 33 GB 提交上限）下，**实测可算的最大点是 158548 节点 / 2359690 方程，最小的失败点是 188674 节点 / 2816466 方程**（返回 0xC0000005，而 fork 已先报 0xC000012D = STATUS_COMMITMENT_LIMIT）；柱壳基线自身（158524 节点 / 2359690 方程）已贴着这道墙。长度只放大 20 % 即触墙（d2000_l2400 建出 188555 节点）。故原计划的 D1600+L3000 与 L3000 两条被换成它们的收缩孪生点 （D1600+L1600 与 L1600）；缺的「放大臂」估计需 48 GB 级内存才能补（未实测）。⚠️ 该上限**不是常数**：Windows 在那次崩溃后把页面文件自动扩到 24975728 kB（≈ 41 GB 提交），上面记的是**当时**实测值；扩容后未再复测放大方向 —— 即便可以，数十 GB 的常驻加重度换页也不适合当作可复现的数据集流水线。
- 开孔板族（open_hole_panel）的双维外推 = **D28（2026-10-08）**：λ 与 (L,W) 同时 ≠ 锚点（λ 0.1 / 400×200）→ **test**（插在偏心 test 之后、两个 val 谓词之前）。声明前这样的点会同时命中两个 val 谓词、按「首个命中」落 val —— 与柱壳 D25「双维 → test」哲学相悖的宽松读法，已在 batch7 角点（600×300+d60）入库前补上。
- 开孔板族（open_hole_panel）的**厚度维经实测判定退化、不作为样本轴入（D30，2026-10-24 老王拍板）**：在恒定名义应力口径下，载荷 `F = sigma * width * thickness` 与膜刚度 `E * thickness` 精确抵消，所以 `u = sigma * L / E` 与壁厚**无关**。实测（`_probe_t7b`）：[0/90]s 2.0 mm → max|u| 0.05734516，1.0 mm → **0.05734516**（逐位相同）；[45/-45]s 0.22584988 vs 0.22585092；孔边峰值 vM 差 0.02%~0.09%，低于任何闸门容差。唯一的区分度是总反力（4000 N vs 2000 N）。因此厚度变体作为样本**零信息量**（模型只要会几何就能「预测」），未入库；它改立为常设自检 `check_forms :: T7.thickness-invariance`（断言载荷比恰为 2、等效模量与 t 无关）——载荷若未按 t 缩放，两个厚度的位移会差 2 倍，这是很强的载荷口径探针。厚度要有可观测性必须引入弯曲/屈曲/面外载荷（`D ∝ t^3`），那属于新结构形式，不是本族的放量。
- 开孔板族的**材料维 = D29（2026-10-11）**：复材层合以 CLT 等效单层入库（老王拍板架构 B —— `*ELASTIC, TYPE=ENGINEERING CONSTANTS` 9 常数 + S4 均匀壳，两码同构；层间/逐层应力不进数据集，ccx COMPOSITE 卡只支持 S6/S8R 也不支持）。划分：复材首实例（锚点几何）→ sweep/**train**（T6 web1 先例），复材+几何单维 → val，双维 → test，偏心谓词优先。**去重指纹随之扩展**：model_sha256 在网格字节 + 壳厚之外加入 deck 的 `*ELASTIC` 块（材料律）——实测复材 [0/90]s d20 与铝 d20 网格逐字节同构、厚度同为 2.0，旧指纹判为同一模型（80695b4c759e），加材料块后 0 重复、老 40 条内部零新增重复（verify_dataset 实测）。等效单层的独立验证线 = `_probe_t7/verify_laminate.py`（加载端平均恒等式口径，TOL_EFF=3% 按实测链钉）：打样双码 E_eff 残差 −2.070% / −2.073%，两码差 0.003%，偏差为 4 mm 非结构 S4 对正交异性的系统离散。
- 开孔板族的**划分判据 = D30（2026-10-24）标量轴计数**：本族四条标量轴 **M** 铺层（`[0/90]s` 为锚点）、**T** 壁厚（2.0 mm）、**L** `lambda_ratio`（0.1）、**S** 尺寸（400×200）；偏离锚点 **0 轴 → train、1 轴 → val、≥2 轴 → test**，偏心孔仍走独立 test 谓词（谓词优先）。D30 是 D29 的维数化重述而非推翻：实测（`_probe_t7b/probe_d30_split.py`）**8/8** 已入库开口板 case 的划分零变化，D12 复现。本批新增 3 条：`cfrp45s`（[45/-45]s，M）→ val、`cfrpqi`（[0/45/-45/90]s 准各向同性，M）→ val、`cfrp45s_d40`（M+L）→ test；`cfrp090s` 仍是 0 轴锚点 → train。**可观测量分离度**：三种铺层 max|u| 分别为 0.0573 / 0.0778 / 0.2258 mm，孔边峰值 vM 49.02 / 30.31 / 42.82 MPa（准各向同性最低，符合孔边集中最弱）。**同时修掉 D29 契约的一处实现缺陷**：`LayupSpec.is_balanced` 原按角度 `% 180` 求和判定，会把 `-45°` 归一成 `135°` 而误拒合法平衡铺层 `[+45/-45]s`；改为**有符号配对**，并让 `a_matrix` 真算 A16/A26（原为硬写 0）、`validate_for_deck` 增加 `|A16|,|A26| < 1e-9*max(A11,A22,A66)` 的物理交叉校验。准各向同性铺层另用**各向同性恒等式 `G = E/(2(1+nu))`** 独立验 CLT（实测 20616.463 vs 20616.463，不依赖任何铺层公式）。
- 翼盒族的**尺寸维划分 = D31（2026-10-24）train 区间**：`span` 与 `skin_thickness` 从 D25 式「精确锚点」扩为训练**区间** `WINGBOX_TRAIN_SPAN = (1600, 2400)`、`WINGBOX_TRAIN_SKIN = (2.0, 4.0)`。核心二分：**出区间 = 外推**（val 单轴出 / test 双轴出），**出锚点但仍在区间内 = 扫点**（train）。D25 的「连续维只采过一个点 ⇒ 只能等号」不是错，是**采样不足的表现**——主动补档位就造出了 interior，区间才诚实（D18「8 学 up to 8」的连续版）。test 三入口：两轴同时出区间 / 一轴出区间 + 他轴（ribs>5、sweep>20、tcr<0.6、webs>1、非锚定长桁）/ 两轴出锚点但都在区间内（交互点）。**`chord` 绝不算「他轴」**（800/1000 两档都在 train，列进去会把 3 条 chord800 重贴成 test）。落地前实测（`_probe_m8/probe_d31_landed.json`）**44 条存量 0 漂移**；补 8 条后 52 条 / 51 类 / 21-17-14（翼盒 17-7-7）。**物理核对**（`_probe_m8/physics_check.json`）：壁厚严格 `1/t`（skin 1.5→4 位移 2.656 倍、偏差 0.30%）、展长三点指数 2.899（梁论 3，±3% 偏离来自 n_ribs 固定 5 致肋距随 span 变）、交互项 0.06%/0.17%（可忽略 ⇒ 区间内双轴交互点作 test 是公平的）。**厚度维在翼盒上可观测、在开口板上不可观测**（D30）——差别全在**载荷随不随该轴缩放**：开口板 `F ∝ t` 与膜刚度 `∝ t` 精确抵消，翼盒固定 500 N 无抵消。判定某轴是否退化，先问载荷口径。
- 翼盒族的**标量代理目标口径 = D32（2026-10-24 老王拍板）**：主目标 `max_disp`（合位移；实测 `max|v|/max_disp` = **0.99899–0.99973**，浮动 0.07 % ⇒ 它本身就是弯曲挠度，不需要另立「法向挠度」），副目标 `max_w`（展向位移 `max|DISP[2]|`，**只报不判**，仅用于 `span` 指数的交叉检验）。**不把 `max_w` 定为代理目标**，四条实测理由（`_probe_m9/w_vs_disp_diag.json`、`baseline_d31.json`）：① 它绕开了全库唯一会崩的轴 —— `sweep40_taper040` 上 `max_w` ×1.716 而 `max_disp` ×4.171，敏感度只有 **41 %**，用它考核等于挑了一个对数据集最大缺陷不敏感的量；② 量级仅弯曲位移的 **1.9 %–5.7 %**，是泊松耦合次级量，工程上不是关注对象；③ **跨族不可用**（开孔板纯面内 ≡ 0、加筋板近刚性 ≡ 1），一个只有翼盒能用的指标不能当族间统一目标；④ 与双码闸门口径分家（`verify_solvers.py` 按 `DISP` 三向量逐节点中位比，不按单分量）。**跨目标比 MAPE 必须下掉同一条样本**：各自剔各自最差会翻转结论 —— 统一下掉 `sweep40` 时 `max_disp` **3.82 %** 优于 `max_w` **4.48 %**，分别剔则是 3.82 % vs 2.15 %。应力峰值（`vM` 中面/外表面）**不设为可学目标**：1 参数梁标度律已 10.39 %/12.22 %，最优 10 特征学习器 9.51 %/10.68 %，差 **0.88/1.54 pp** 且 4000 次 bootstrap 的 95 % CI 均跨 0；机制是峰值位置在31 条翼盒里散落在 **21/25 个不同节点**，**峰值是离散选择而非光滑泛函**。所以本数据集的应力真值用于**求解器验证**，不用于标量代理建模。
- 翼盒族的**后掠轴划分 = D33（2026-10-24 老王拍板）**：`WINGBOX_TRAIN_MAX_SWEEP` 20° → **30°**，新增 train 站 `naca4412_wingbox_sweep30`（仅 `sweep_deg=30`，锥度中性 1.0、其余全锚定）。目的不是放宽考试而是**把唯一的外推机制变成可内插**：实测后掠响应**超线性**（相对 0° 的位移比 **1.000 / 1.094 / 1.340 / 1.853 / 2.965**，增量 +0.094 / +0.246 / +0.514 / +1.112 严格递增，`_probe_m10/physics_sweep_axis.json`），0–20° 割线外推到 40° 差 **−43.4 %**（与 M7 的 −41.5 % 同源，两种口径互证）。补 30° 后 `sweep40` 仍是 **val**、`sweep40_taper040` 仍是 **test**（考试点一个没删），但外推距离 20° → **10°**；`sweep30` 处二次趋势预测误差 **−6.2 %** ⇒ 该点确含新信息，不是冗余叠加；4 站拟合到 40° 的残差从 −22.9 %（3 站二次）降到 −14.1 %（4 站二次）/−7.2 %（4 站三次）。落地前实测（`_probe_m10/probe_d33_split.json`）**52 条存量 0 条换边**、D12 复现 **11/11**；落地后 **53 条 / 52 类 / 22-17-14**（翼盒 18-7-7）。
- 翼盒族的**代理模型形式口径 = D34（2026-10-24 老王拍板「改形式」）**：`sweep` 项在 `log y` 中以 **二次**（而非线性）进入，基为 `s = sweep_deg/20` 的 `[s, s²]`，**过原点**（`sweep=0` 处修正恰为 0，无后掠是自然原点而非抛物线上任意一点）。判据：主判据是**零泄漏的 `LOO@30`**（从 train 删掉 30° 那行再预测它），保护是 train LOO 整体不得劣化 >15 %、条件数 <1e6，`val` 仅作确认，`test` 只报一次。实测（`_probe_m11/sweep_form.json`，M5 档口径）：`LOO@30` **−22.14 % → −1.07 %**、`val` 单点 `sweep40` **−34.54 % → −3.17 %**、test MAPE **7.74 % → 6.18 %**（CI [−4.46, +0.23]，**n=7 下跨 0，不显著**）、`planform_out` 组 **25.70 % → 15.70 %**。**三次基被否**：train 里 `sweep>0` 仅 3 行且几何完全相同 ⇒ `s²`/`s³` 只在这 3 行非零，3 点定 3 参数**恰好可逆**，三次式在那 3 行拟合到机器零、40° 分支全靠硬猜；实测四个指标全不如二次（`LOO@30` −1.07 → +6.02）。**「加站数就升阶」不是配方。****该形式只对 `max_disp` 采纳**：同样改动在 `max_w` 上 val 6.01→**1.93** 但 test 8.33→**13.49**、最大 APE 26.8→**65.1 %**（崩），vM 两目标同样 test 恶化；机制在系数上可见（`max_disp` 二次项 +0.064·s+0.232·s²，线性项为正、抛物线平缓；`max_w` 是 −0.069·s+0.214·s²，线性项为负、原点处向下弯）。**D34-b（对 D32 的限定）**：`val` 只有 7 条、其中 `sweep>0` 仅 1 条（taper 中性），在本轮 4 个目标上 `val` **一律**选中二次基而 `test` 只在 `max_disp` 上支持它 ⇒ **形式类决策不能用 val 选**，须用「留最高站位」LOO；D32 的「val 选」仍适用于**档位**选择。**剩余 15.7 % 不是形式问题**（`_probe_m11/residual_diag.json`）：train 中「`sweep>0` 且 `taper≠1`」的样本数 = **0** ⇒ 交互项 `s²·(taper−1)` 在 train 上恒等于零，**不是估不准而是不可估**；残差结构为 taper 中性 −3.17 %、两个 taper 角点 +13.31 / +15.70 %。**换任何基都学不到，只有补一条带锥度的后掠算例。****副产品**：`n_web` 与 `web_pos` 在 train 上**完全共线**（奇异值 1.3e-15，train 只有 1 条带腹板算例 ⇒ 两列都只在同一行非零），`is_T` 恒为 0 ⇒ M3 的 10 个特征实际只有 **8 个可辨识方向**；这解释了 M7「`n_web` 1→2 外推 +14.5 % 为第二不稳轴」——那条路在 train 上根本没有信息。
