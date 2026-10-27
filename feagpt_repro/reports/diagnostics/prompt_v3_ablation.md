# prompt v3 / v3b 消融：还能不能修好 C-033 的缺失信息处理（W5d-1）

> 诊断文件（R37）。**结论：不采纳**——两版都只是把失败点挪个位置，exam 澄清题始终 2/3。

## 0. 判定（规则先写死，再由数据算）

- 采纳条件：**两个模型**都「exam 澄清题全对」且「3 条对照题零回归」。
- 结论：**不采纳**。两版均未同时满足「exam 澄清题全对」+「对照零回归」⇒ **不采纳**，维持 v2（prompt sha 回到 `ce225186…`），否则按 R53 必须全量重跑 110 条候选 + 65 分钟 MSR，净收益为 0。

## 1. 三版 prompt 各自改了什么

| 版本 | 改动 | prompt sha |
|---|---|---|
| v2（现行） | 数量铁律（题面提到特征却没给数量 ⇒ 必须澄清）+ 惯例条款 | `ce225186…` |
| v3 | ①数量铁律**扩到尺寸**（`hole_d`）；②**澄清列表准入规则**：只能问题面出现过的参数、不得问「是否布置 X」、最多 2 条 | `e52f06a…` |
| v3b | v3 + **5 步自检清单放在 SYS 最后**（先圈特征词 → 问有没有给数 → 缺则只能输出 clarify） | `769a1eb…` |

## 2. 逐题结果（exam 澄清题 3 条 + dev 澄清题 1 条 + 对照 3 条）

### glm-5.3-flash

| 题 | 期望 | v2 | v3 | v3b |
|---|---|---|---|---|
| `fuselage_barrel_d1600_l1600_str8_frm3` | 澄清 ['n_frames'] | clarify_ok | clarify_ok | clarify_ok |
| `naca4412_wingbox` | 澄清 ['n_ribs'] | clarify_ok | clarify_ok | clarify_ok |
| `stiffened_panel_600x600_str3` | 澄清 ['n_stringers'] | clarify_ok | clarify_ok | clarify_ok |
| `open_hole_panel_400x200_d20` | 澄清 ['hole_d'] | clarify_ok | clarify_ok | clarify_ok |
| `stiffened_panel_600x600` | spec（不得澄清） | spec_ok | spec_ok | spec_ok |
| `open_hole_panel_400x200_d40` | spec（不得澄清） | spec_ok | spec_ok | spec_ok |
| `naca4412_wingbox_str3` | spec（不得澄清） | spec_ok | spec_ok | spec_ok |

- exam 澄清题正确数：v2 **3/3** → v3 **3/3** → v3b **3/3**
- 对照题回归：v2 无 / v3 无 / v3b 无

### deepseek-v4-pro

| 题 | 期望 | v2 | v3 | v3b |
|---|---|---|---|---|
| `fuselage_barrel_d1600_l1600_str8_frm3` | 澄清 ['n_frames'] | clarify_ok | fabricated（fill_zero） | clarify_ok |
| `naca4412_wingbox` | 澄清 ['n_ribs'] | clarify_wrong | clarify_ok | unresolved |
| `stiffened_panel_600x600_str3` | 澄清 ['n_stringers'] | clarify_ok | clarify_ok | clarify_ok |
| `open_hole_panel_400x200_d20` | 澄清 ['hole_d'] | fabricated（omit_key） | fabricated（omit_key） | clarify_ok |
| `stiffened_panel_600x600` | spec（不得澄清） | spec_ok | spec_ok | spec_ok |
| `open_hole_panel_400x200_d40` | spec（不得澄清） | spec_ok | spec_ok | spec_ok |
| `naca4412_wingbox_str3` | spec（不得澄清） | spec_ok | spec_ok | spec_ok |

- exam 澄清题正确数：v2 **2/3** → v3 **2/3** → v3b **2/3**
- 对照题回归：v2 无 / v3 无 / v3b 无

## 3. 读法（这条比分数重要）

> 下面是**全部 4 条澄清题**（3 条 exam + 1 条 dev，dev 已标注）；「exam 澄清题正确数」只数 exam 那 3 条。

- glm-5.3-flash：**v2（现行）** 错 无 → **v3** 错 无 → **v3b** 错 无
- deepseek-v4-pro：**v2（现行）** 错 `naca4412_wingbox`、`open_hole_panel_400x200_d20`（dev） → **v3** 错 `fuselage_barrel_d1600_l1600_str8_frm3`、`open_hole_panel_400x200_d20`（dev） → **v3b** 错 `naca4412_wingbox`

- 三版的 exam 澄清题正确数是否一致：**一致**（⇒ 零收益）；失败题是否在换：**在换**。

⇒ 这是**打地鼠**：总数不变、失败点迁移。继续调措辞只会换一个失败点，不会清零。剩余差距属**模型行为**（缺失信息处理策略），不属题面/prompt 缺陷——与 C-031/C-033 的三条归因一致。

## 4. 所以下一步该做什么

- **不采纳 v3/v3b**：prompt sha 回到 `ce225186…`，C-032/C-033/C-034 全部继续有效（S-39 会在 prompt 漂移时报警，这次是它替我们挡住了「无收益全量重跑」）。
- 若要把「缺失信息处理」变成可测量而不是靠模型自觉，只有一条口径级的做法：**在生成器里加语义回填闸**（题面提到特征但关键键缺失/为 0 ⇒ 反馈一次，要求澄清）。那属于**改 harness 口径**，必须老王拍板（D7），不能我单方面加。
- 提高统计精度（CI 太宽）仍然要靠 **v1.1 新几何（n≥30）**，不是靠 prompt。
