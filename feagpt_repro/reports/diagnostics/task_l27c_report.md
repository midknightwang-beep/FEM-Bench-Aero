# T-L27c：L2「信息完备」题型最小链路（4 条）—— 报告

> **状态**：diagnostic ／ **不进任何对外数字**（不进 headline、不进 `CLAIMS` 的可引用数、不作模型排名）
> **日期**：2026-11-04 ／ **上游**：T-L27b（`l27b_ec0_probe.json`）／ **下游**：§13 第 10 项
> **一句话**：「加题型」这条路**通了**，但通的过程撞出**三处实现漏项**，每一处都曾静默产出假成绩；
> 真正的交付物不是 4 条的成绩，而是**「两类分层报」这个形态**，以及守住它的 1 条负控 + 9 向自检。

---

## 1. 这一轮到底改了什么（四处，按发现顺序）

| # | 位置 | 症状 | 为什么危险 | 修法 |
|---|---|---|---|---|
| ① | `score_l2.classify()` | ec=0（信息完备）题给出正确 spec 被判 `fabricated`（实测 **59/59**） | 把「完整题面下的正确回答」记成**最重的错**，方向完全反了 | ec 为空时**委托** `judge_l3_candidate`（唯一实现，R58），本函数只改名（T-L27b，已收口） |
| ② | `check_l2_leak.scan()` | ec=0 题上 `r['expected_clarifications'][0]` **IndexError** | 信息完备题**没有**「被删的键」，掩码问题对它不存在 | ec 为空则 `continue`（对 v7 卷零影响：64 条全 ec=1） |
| ③ | `evaluate.case_id_of()` | 自造前缀 `L2i_` 不被三个 `hardcode replace` 命中 ⇒ 金标准定位到不存在的目录 ⇒ **4/4 判 `spec_bad / failed=['gold spec']`** | 成绩单**看着像模型全错** | 改为**行首结构性前缀** `^L\d+[a-z]*_`；`_c1_caseid_equiv.py` 断言对冻结卷 **357 条逐条等价** + 新增「派生卷前缀可解析」判据 |
| ④ | `score_l2.score()` | **从来没有** `require_dataset(expect_ids=…)` | `score_baseline.py`（L3 路径）自 T-C1 起就有，**同一类闸只装在一个评分器上 = 没装** | 补前置闸，缺金标准 `rc=2` 硬错；自检 ⑨ 两向断言之 |

**这四处的共同点**：没有一个会报错。①②③④全都在「安静地给一个看起来合理的错数字」。
⇒ 本轮真正的收获是一条纪律：**加新题型之前，先问「目标判分器认识这种题吗」**，
并且要**逐类输出走一遍**（给 spec / 该澄清 / 空输出），而不是只跑一遍看它没崩。

---

## 2. 「两类分层报」落地

`score_l2.py` 新增 `strata` 块（**不动任何既有键**）：

| 层 | 判定对象 | 分母来源 |
|---|---|---|
| `strata.informative` | 题面**完备** ⇒ 该**答**，判 spec 保真 | `expected_clarifications == []` |
| `strata.clarified` | 题面**缺键** ⇒ 该**问**，判键名对 | `expected_clarifications != []` |

★ **为什么不复用 `clarify_informative`**：那个键的分组轴是 **`name_leak`（掩码）**，
在 v7 卷上与「信息完备」**只是碰巧重合**（v7 的 L2 全 ec=1，而 ec=0 的题天然不被掩码）。
一旦混卷，两条轴就分叉，而键名还叫 `clarify_informative` ⇒ **同名字段不同源**，数字会静静地错。
故：**题型轴与掩码轴各报各的**，`strata._coverage` 明写本卷只覆盖哪一层
（本卷 = `informative_only`，`clarified` 为 `0/0`，**不是 0 分**）。

✅ **零成本接入已实证**：v7 卷 L2 全 ec=1 ⇒ `strata.clarified.n = 64`、`strata.informative.n = 0`；
两份真实成绩单重跑后 **逐条 `category`/`pass` 与三个分母全部一致**（glm 49/64、ds 36/64），
新增叶子 **+84** 且全部落在题型轴（NC-78 ② 由「逐字节」升级为「**纯增量**」断言：
旧叶子一个不丢、一个不改，新增只许来自 `strata`／`per_task[].stratum`）。

---

## 3. 4 条小卷的结果

卷：`tasks/tasks_l2_informative_v1.jsonl`（4 条 = 每族各 1 条，`sha256 = 2987e57066bf…`），
派生规则 = **取该族 L1 题的完整 `spec_normalized`、不删任何键**、`expected_clarifications = []`。

| 模型 | `strata.informative` | 明细 |
|---|---|---|
| `glm-5.3-flash` | **0/4** | 4 条**全部直接给 spec**（`turns=1`、无一条追问），但 4 条都没通过 spec 保真 |
| `deepseek-v4-pro` | **1/4** | 2 条**追问**（判 `clarify_wrong`／该答不答）、1 条 `spec_ok`（**29 字段全对**）、1 条 `spec_bad` |

逐条失败字段：

| 题 | glm | ds |
|---|---|---|
| `naca4412_wingbox_n_ribs3_chord1000` | `extra.sweep_index` | `mesh.*` 6 项（`algorithm_2d`/`element_order`/`leading_edge_threshold`/`min_jacobian`/`recombination_algorithm`/`recombine`） |
| `open_hole_panel_400x200_d20_cfrp45s_d40` | `mesh.size_chord`、`mesh.size_span`、`mesh.size`(不存在) | **追问** `["hole_x","hole_y"]` |
| `fuselage_barrel_d1600_l1600_str8_frm3` | `mesh.leading_edge_threshold`、`mesh.refine_at_leading_edge`、`mesh.size_chord`、`mesh.size_span`、`extra.moment_axis`、`extra.shear_axis` | **追问** `["n_stringers","n_frames"]`（两者**都在题面里**） |
| `stiffened_panel_600x600_str3` | `mesh.size_chord`、`mesh.size_span`、`mesh.size`(不存在) | **`spec_ok`（29/29）** |

### 3.1 题面完备性：三档独立证据（不靠构造声明）

1. **构造上**：v7 的 L2 题 = `make_l2_input()` 从 L1 完整 spec **删掉 1 个键**；本卷 = 从 L1 完整 spec **删 0 个键**
   ⇒ 同一构造族、同向更弱（同族 `make_tasks.py:238`）。
2. **同值核对**：逐字段比对题面 `input.spec_normalized` 与 `modeling/<case>/spec.json`，
   被判失败的字段（`mesh.size_chord`/`size_span`、`extra.moment_axis`/`shear_axis`、
   `mesh.refine_at_leading_edge`…）**题面里全部存在且与 gold 同值**。
3. **可满足性**：ds 在 `stiffened_panel` 上 **29/29 全对（含 mesh 段全对）** ⇒ 这套题面**是可答对的**。

⇒ 结论站得住：**不是题面缺信息，是答题方自己改的**。

### 3.2 诚实边界（必须随数字一起说）

- **`informative` 层测的是「schema 保真／无损转写」，不是建模能力。** 题面已给全 spec，
  答对 = 能按约定字段名一字不差地写回去。它**不能**用来宣称「模型会建模」。
- **glm 的 4 条失败集中在两类，都不是算错**：① 把 `mesh.size_chord`/`size_span` 合并写成 `mesh.size`
  （**值是同一个、字段名自己发明**）；② `extra.*`（轴向量、`sweep_index`）取值/键名不对。
  这是**格式与命名保真**问题，物理上没算错 —— 但 spec 保真判据严格按字段名（R44），故判失败。
- **`n = 4` 没有统计意义**：`0/4` 的 Wilson CI95 是 **[0, 49.0%]**，`1/4` 是 **[4.6%, 69.9%]**。
  本表只能排除两个极端（「必然答对」「必然答不对」），**不能排名**。
- **本卷只覆盖 `informative` 一层**（`_coverage = informative_only`）⇒ `strata.clarified` 的 `0/0`
  **不是 0 分**，是「本卷没有这类题」。
- 两模型的 `presentation` 相同（`spec_json_raw_name`）、`turns` 记录齐全，但**未做重复跑**
  ⇒ 不能据此谈稳定性（R77 ⑤：`n` 不足时必须明说「不可判」）。

---

## 4. 数学现实：加题**压不下**整体退化率

`R76` 的退化判据作用在 `clarified` 层。老卷最坏情形 = 按族 top2 命中 **31/64 = 48.4%**；
`informative` 层上穷举实测 **0/59**（`l27b_ec0_probe.json`）。把 N 条 ec=0 题加进 64 条老卷：

| N | 13 | 16 | 24 | 26 | 64 | **246** |
|---|---|---|---|---|---|---|
| 整体退化率 `(31+0)/(64+N)` | 40.3% | 38.8% | 35.2% | 34.4% | 24.2% | **10.0%** |

⇒ 要把整体从 48.4% 压到 10%，需要 **246 条** ec=0 题。
**所以加题的价值不在摊薄，而在「让两类型分开报」** —— `clarified` 层的老问题（穷举 2 键仍可命中）
继续如实可见，`informative` 层则**把这条路封死**。这才是根治的形态。

---

## 5. 扩到多少条？—— 13 和 26 都有同一个问题

**13 与 26 都不是 4 的倍数**，而分层必须**按族**（R72）：4 个族的分母会变成 `3/3/3/4` 或 `6/6/7/7`，
**族级不可比**，而族级正是本项目唯一被接受的论据层面（N-27 / T-A14 的教训）。

Wilson CI95 半径（两模型差异若在 10pp 量级，n 必须够大才判得出）：

| n | p=50% | p=25% | p=10% |
|---|---|---|---|
| 13 | [23.2, 70.9] | [8.2, 50.3] | [1.4, 33.3] |
| **16** | [28.0, 72.0] | [10.2, 49.5] | [3.5, 36.0] |
| 24 | [31.4, 68.6] | [12.0, 44.9] | [2.3, 25.8] |
| 26 | [32.1, 67.9] | [11.0, 42.1] | [4.0, 29.0] |
| 64 | [38.1, 61.9] | [16.0, 36.8] | [4.4, 19.0] |

⇒ **建议每族 4 条 = 16 条**（唯一在「4 族等分」与「成本」之间都成立的档）。
即便如此，`p≈50%` 时 CI 半径仍有 **±22pp** —— 这层的数字**只能判「有没有系统性崩」，不能排名**。
真要区分两模型，得 **≥ 24/族**（96 条），成本已接近重建一整卷。

---

## 6. 复算（照抄即可，`$PY` 见 `AGENTS.md` §0）

```bash
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
cd feagpt_repro
"$PY" _c1_caseid_equiv.py                     # 357 条等价 + 派生卷前缀可解析
"$PY" score_l2.py --self-test                 # ①..⑨ 九向
"$PY" score_l2.py --cand candidates_l2i_v1_glm --tasks tasks/tasks_l2_informative_v1.jsonl --label l2i_v1_glm
"$PY" score_l2.py --cand candidates_l2i_v1_ds  --tasks tasks/tasks_l2_informative_v1.jsonl --label l2i_v1_ds
"$PY" negative_controls.py                    # NC-79（改卷链路）+ NC-78（纯增量）
```

artifacts：`reports/diagnostics/l2i_v1_scores_{glm,ds}.json`、
`reports/diagnostics/l27b_ec0_probe.json`、`reports/negative_controls_79.json`。

---

## 7. 本轮**没做**的事（免得被当成做了）

- **没重跑 v7**：两份 `l2_scores_v7_*.json` 一个字节未动（它们缺 `strata` 字段，是**有意**的
  —— 冻结成绩单不因新增报告字段而变；新字段由任意一次重跑即可得到，NC-78 已守「纯增量」）。
- **没扩卷**：仍是 4 条，`informative` 层不具统计意义。
- **没改任何已发布数字**：headline `C-032`、四份成绩单、`CLAIMS` 的可引用数零变动。
- **没宣称 L2 抗退化**：`clarified` 层的穷举残余（48.4%）仍在，`informative` 层只是**新开一条**
  不被它污染的赛道。
