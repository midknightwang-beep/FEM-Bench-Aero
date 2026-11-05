# v7 → v8 单变量对照（L27d / R65）

> 本表**不给任何 Δ** —— 两卷分母不同（全卷 192/208、L2 64/80），按 R54 禁止相减。

## 卷

| | 文件 | sha256 | 行数 |
|---|---|---|---|
| v7 | `reports/papers/tasks_v7.jsonl` | `caf0f6c3be81…` | 192 |
| v8 | `reports/papers/tasks_v8.jsonl` | `54d8352bfdec…` | 208 |

## B1 老行有没有动（逐层）

| 层 | v7 | v8 | 丢失 | 新增 |
|---|---:|---:|---:|---:|
| L1 | 64 | 64 | **0** | 0 |
| L2 | 64 | 80 | **0** | 16 |
| L3 | 64 | 64 | **0** | 0 |

## B2 L3 层

- L3 行集合差：丢失 0 / 新增 0
- L3 行集合差为空 ⇒ v7 的 L3 成绩单（C-032/C-033/C-040）仍然代表 v8 的 L3 层，**不需要重跑**

## B3 L2 层新增了什么

- 新增 **16** 条；全部 `expected_clarifications == []`：True；全部 `L2i_` 前缀：True
- 每族：{'wingbox': 4, 'open_hole_panel': 4, 'fuselage_barrel': 4, 'stiffened_panel': 4}

## B3b 澄清层数字有没有变（现读两份成绩单）

| 模型 | 块 | v7 | v8 |
|---|---|---:|---:|
| glm | `clarify_all` | 46/64 | 46/64 |
| glm | `clarify_informative` | 27/45 | 27/45 |
| glm | `invalid_subset` | 19/19 | 19/19 |
| glm | `strata.informative`（新增层） | — | 13/16 |
| ds | `clarify_all` | 52/64 | 52/64 |
| ds | `clarify_informative` | 33/45 | 33/45 |
| ds | `invalid_subset` | 19/19 | 19/19 |
| ds | `strata.informative`（新增层） | — | 1/16 |

## 判据

- `B1_old_rows_preserved` = **True**
- `B2_L3_unchanged` = **True**
- `B3_added_are_informative` = **True**
- `B3b_clarify_numbers_unchanged` = **True**
