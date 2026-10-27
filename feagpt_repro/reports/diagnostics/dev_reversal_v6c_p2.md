# dev 反向变化定位（W5d-0）：C-029 v6c (paper v6c, candidates v6c) → C-032 v6c x glm prompt-v2 (paper v6c, candidates glm_p2)

> 诊断文件（R37），不进 headline。**净额 −1 不等于只有一个变动源**——必须逐题拆开。

## 0. 结论先行

- dev **23 → 22（净 -1）**，实际拆成 **fail→pass 1 条** 与 **pass→fail 2 条**（其余 0 条）。
- 闭合：`old 23 + fail->pass 1 - pass->fail 2 = new 22` ⇒ **闭合**。
- A 侧 `prompt_sha256` **未记录**（该批生成时还没有这个字段）= `UNKNOWN`，B 侧 = `ce225186cafa…` ⇒ 按 R53 只能作「A→B 的方向性观察」，**不是可并列的两份成绩**。
- 新增失败字段里 **2 个属量级/单位偏差（×10^n）** ⇒ 与「澄清策略」无关，prompt 改动未涉及载荷量纲 ⇒ **判为采样波动/模型侧，不得记作 prompt 副作用**。

## 1. 逐题翻转

| 题 | 方向 | 旧类别 → 新类别 | 失败字段 |
|---|---|---|---|
| `L3_fuselage_barrel_d2000_l1600_str8_frm3` | **pass->fail** | spec_pass → spec_fail | `extra.end_moment` |
| `L3_fuselage_barrel_d2000_l2000_t2_str8_frm3` | **pass->fail** | spec_pass → spec_fail | `extra.end_moment` |
| `L3_stiffened_panel_800x600_str3` | **fail->pass** | spec_fail → spec_pass | `params.length、params.width` |

## 2. 字段级证据（gold vs 旧候选 vs 新候选）

| 题 | 字段 | gold | 旧候选 | 新候选 | 分类 | 说明 |
|---|---|---|---|---|---|---|
| `fuselage_barrel_d2000_l1600_str8_frm3` | `extra.end_moment` | 50000000 | 50000000 | 50000 | **magnitude_unit_error** | ×10^-3（50000.0 vs gold 50000000） |
| `fuselage_barrel_d2000_l2000_t2_str8_frm3` | `extra.end_moment` | 50000000 | 50000000 | 5000000 | **magnitude_unit_error** | ×10^-1（5000000 vs gold 50000000） |
| `stiffened_panel_800x600_str3` | `params.length` | 800.0 | 600 | 800 | matched |  |
| `stiffened_panel_800x600_str3` | `params.width` | 600.0 | 800 | 600 | matched |  |

## 3. 判读口径（下次别重新发明）

- **pass→fail 且字段是量级差**：判采样波动/模型侧，**不得**写成「prompt 修复的代价」。
- **fail→pass 且旧失败字段现与 gold 一致**：判「题面修正被兑现」——提醒：考卷改了但候选没重生成时，这一格**恒为 0**（bridge 表 C 格），只有重生成才拿得到。
- **净额相同但翻转成对抵消**：必须同时报两个方向，只报净额会掩盖真实变动源。
