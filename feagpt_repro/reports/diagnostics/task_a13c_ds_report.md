# T-A13c 交付报告 —— L2 clarify 第二模型（ds）

- 日期：2026-10-30
- 单变量：`candidates(model)`，glm-5.3-flash → deepseek-v4-pro
- 提交：`bf05ae0`（本轮）← `ea452a1`（记忆）← `423c946`（T-A13b）← `4042098`（T-A13a）
- 门禁：负控 **65/65**；`check_claims` **33 claims / 68 artifacts / 57 语义项 全过**

## 一、单变量成立性（逐条核对，不是口头声明）

| 冻结项 | 实读 |
|---|---|
| 考卷 `tasks/tasks.jsonl` | `caf0f6c3be81…`（未变） |
| L2 prompt `prompt_sha256` | `03129c56d83b…`，ds 候选 **64/64 逐条相同** |
| 呈现 `presentation` | `spec_json_raw_name`，64/64（未遮 name，与 glm 一致） |
| 判据 `score_baseline.py` | **git 未修改**（一行未动） |
| L3 侧 | `SYS`／`msr_l3.py`／两份 L3 成绩单／生成器 **全部 git 未修改** |

⇒ 唯一的差异来源就是模型本身。

## 二、成绩

| 模型 | `clarify_all` | `clarify_informative` | `invalid`（泄漏 19） | clarify_ok / fabricated / clarify_wrong |
|---|---|---|---|---|
| glm-5.3-flash | **49/64 = 76.6%** | **30/45 = 66.7%** | **19/19** | 49 / 13 / 2 |
| deepseek-v4-pro | **36/64 = 56.2%** | **21/45 = 46.7%** | **15/19 = 78.9%** | 36 / 20 / 8 |

`missing` 两模型均为 0（候选都齐 64/64）。

## 三、★ 最重要的结果：N-27 被 ds 独立证实（并部分推翻原读法）

| 族 | glm 全卷 | glm 泄漏/干净 | ds 全卷 | ds 泄漏/干净 |
|---|---|---|---|---|
| wingbox | 24/39 | 3/3 / 21/36 | **15/39** | 2/3 / 13/36 |
| open_hole_panel | 13/13 | 10/10 / 3/3 | 11/13 | 9/10 / 2/3 |
| fuselage_barrel | 7/7 | 5/5 / 2/2 | 5/7 | 3/5 / 2/2 |
| stiffened_panel | 5/5 | 1/1 / 4/4 | 5/5 | 1/1 / 4/4 |

三条结论：

1. **族排序未反转**（两模型都是 wingbox 最差）⇒ 判据没有系统性偏向某个模型，契约的停止条件未触发。
2. **`invalid` 从 19/19 掉到 15/19** —— 同一批泄漏题，glm 全对、ds 掉 4 条。而且掉的 4 条
   **全是 `fabricated`（3 条，直接给 spec）或问别的字段（1 条 `sweep40` 问 `n_stringers_per_skin`）**——
   **根本没走追问路径**，泄漏存不存在都不影响它的行为。
   ⇒ **「泄漏 ⇒ 那 19 条必然全对」被证伪**。glm 的 19/19 是**能力 + 族构成**的结果，不是泄漏。
3. **跨模型一致的盲区**：`rib_thickness` **1/6**、`stringer_height` **1/6**、`sweep_deg` **1/6** ——
   **两模型恰好都是 1/6**。三项如此一致，说明它们是**题面/判据层面的系统性难点**，不是模型随机波动。

唯一**字段级**反转：`tip_chord_ratio` glm **5/5** vs ds **0/5**（ds 三条给 spec、一条问其它矛盾）。
其余 ds 弱于 glm 的项目：`skin_thickness` 4/7、`n_stringers` 4/6。

## 四、★ 新发现 N-28：判据的潜伏假通过通道（本轮 0 触发）

```python
al = aliases.get(f) or [f]           # L2 无 clarify_aliases ⇒ al = [f]
hit = [a for a in al if a in text]   # ★ 裸子串，无边界
```

三个被省略字段是别的键名的子串：

| 字段 | 被谁包含 | 题数 |
|---|---|---|
| `n_stringers` | `n_stringers_per_skin` | 6 |
| `thickness` | `skin_thickness` / `rib_thickness` / `stringer_thickness` | **7** |
| `width` | `stringer_flange_width` | 2 |

**后果**：模型问「肋厚」（`rib_thickness`）而题面省略的是笼统 `thickness` 时，判据会**判对**。

**实测**：用 `(?<![A-Za-z0-9_])f(?![A-Za-z0-9_])` 逐条复算两模型全部 PASS 条目（49 + 36），
**每一条都含独立键名命中**（模型写 `structure.params.n_stringers`，前面是点）⇒ **本轮 0 条触发，数字不假**。

**为什么不在本轮修**：改 `judge_clarify_field_level` = 改判分。判据在 T-A13a 已冻结提交、T-A13b/c 已据此出分 ⇒
**跑完后改就是 post-hoc**（R-A2）。即使能出零差异证据，也必须走独立任务（跑前冻结 → 零差异 → 负控），
否则同样的口子下一轮可以用来「结果不好看就改判据」而不被发现。

**已排为 T-A13d**，处置写在 `CONFLICT.md` N-28：改独立命中 + 零差异（L2 两模型逐数不变、L3 两份成绩单
`_regress_scorecard` 出 `RESULT: PASS`；L3 的 25 个 alias 里纯标识符且被别的键包含的 **= 0 条**）+ 负控两向 + R69 边界。

## 五、本轮代码改动与它们的自证

| 文件 | 改动 | 自证 |
|---|---|---|
| `report_l2_clarify.py` | `--scores` 支持逗号分隔多文件；新增 `by_model` 块（第一个为顶层 primary，顶层字段向后兼容） | **单模型重生成 vs 旧 artifact：removed 0 / changed 0，只新增 `by_model`** —— 构造性零差异 |
| `check_claims.py` | S-53 增 (e)：逐块断言（每块 `all == inf + inv`、两侧报分、顶层必须是其中一块且逐数相等） | NC-63 (a) 正向须绿 + 四向须红 |
| `negative_controls.py` | NC-63 五向，每向断言**红的原因对** | 65/65 全绿 |

**★ 闸的诚实边界**：`by_model` 只能保证「在场的块各自自洽」，**守不了「该在场的模型缺席」**。
后者靠 claim 文本点名（C-041 明确列了两个模型）+ 跑分命令入库；少跑一个模型是流程问题，不是判据问题。

## 六、N-27 拍板 (a) 的落地

老王选 (a)「只如实标注、不动口径」。已落地四处并**经 ds 结果复核仍然成立**：

1. `CLAIMS.md` C-041「边界一：64 与 45 的差不是泄漏」—— 补入 ds 的独立反证；
2. `RUBRIC.md` R66「新增适用边界（N-27）」；
3. `README.md` / `reports/INDEX.md` 的 L2 段落；
4. `CONFLICT.md` N-27 标注「✅ 已拍板（2026-10-30）取 (a)」+ 边界。

→ 因为两模型的族构成同样偏翼盒（wingbox 39/64），**(a) 在第二模型上依然成立，不需要升格为 N-28 级别的改口径**。

## 七、下一步可选单子

1. **T-A13d**：判据独立命中加固（N-28）—— 有完整零差异预案，风险最低。
2. **L2 第三模型**：若要谈「模型间差异」，两个样本只能说「谁在这套判据下过得多」，
   仍不足以排除单次采样波动（R54 只禁排名，没解决 n=2 的问题）。
3. **N-25**：同一条柱壳两次结果不同的成因（需单独重跑同一条 `.inp` 数次）。
4. **L3 v8 卷**：两道 dev 题的 `length`/`width` 角色缺陷要消除只能走 v8 + 重冻结 + bridge（R65）。
