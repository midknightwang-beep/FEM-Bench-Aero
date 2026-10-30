# P-1 over-clarify 影响面量化（只读探针）

- known_keys：**13** 个纯 ASCII 键名
- L3 有 `expected_clarifications` 的题：**5** 条

## L3（判据：命中 expected 且不含 wrong_keys）

| 模型 | 题数 | 有「多问」 | 多问且命中 expected | 多问撞上 wrong_keys |
|---|---|---|---|---|
| glm | 5 | 0 | 0 | 0 |
| ds | 5 | 1 | 1 | 1 |

## L2（判据：字面命中 omitted_field；L2 无 wrong_keys）

| 模型 | 题数 | PASS 且「多问」 | 只多问未命中 expected |
|---|---|---|---|
| glm | 64 | 3 | 2 |
| ds | 64 | 1 | 7 |

## 若采纳「问句条数上限」（P-1 选项 B 的代价）

单位：**当前 PASS 且超过上限**的题数（只有这些会翻 FAIL）。

| 层 | 上限 | glm | ds |
|---|---|---|---|
| L2 | ≤2 | 0 | 8 |
| L3 | ≤2 | 0 | 0 |
| L2 | ≤3 | 0 | 3 |
| L3 | ≤3 | 0 | 0 |

> 读法：上限越严，**掉的全在 ds 一侧**（glm 一条都不掉）⇒ 用条数当阈值等于按模型调参，这正是 P-1 建议「只观测、不设罚」的第二个理由。

## L3 逐题（有「多问」的才列）

| task | 模型 | expected | wrong_keys | over_ask | 命中 expected |
|---|---|---|---|---|---|
| `L3_naca4412_wingbox` | ds | ['n_ribs'] | ['n_stringers_per_skin'] | ['n_stringers_per_skin'] | True |

## 诚实边界

- 只统计**纯 ASCII 键名**的「多问」；中文措辞的多问（如「还想确认一下肋壁厚」）不计 ⇒ 本表是**下界**。
- ★ 「同一文本里提到某键」≠「向用户提问该键」。本次 L2 命中的 4 条（glm 3 / ds 1）**已逐条人工复核，4/4 是假阳性**：模型写的是「题面给了 stringer_height/stringer_thickness/stringer_kind，但没给根数」= **解释上下文**，不是多问。⇒ 任何「按语义判多问」的判据都会误伤，这是 P-1 选 A（观测不罚）的主要依据。
- ★ 条数（`n_questions`）必须 json.loads 后再取 len：`clarify` 是「字符串里装的 JSON 数组」，按标点切分会得到假分布（首版 glm 3 / ds 8 的假象就是这样来的）。
- ★ `cap_impact` 只统计「当前 PASS 且超过上限」的题 —— 只有这些会翻 FAIL；非 PASS 的题不受上限影响。
