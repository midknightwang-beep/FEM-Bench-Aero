# FEM-Bench-Aero 项目复评与执行纠偏（第二轮）

> **复评日期**：2026-10-24（第二轮）
> **复评对象**：W1–W3 执行后的数据集、任务层、评测器、schema、文档与单一数字源
> **复评依据**：`ROADMAP.md`、`STAGE_GATE_M14.md`、`dataset_card.md`、`git log`、`tasks/`、`evaluate.py`、`gate3_all55_d37.json`、`external_numbers.*`
> **复评方式**：只读核对 + 两次受控实验（故意改错参数，验证评测器是否会拒绝）
> **结论先行**：
> **方向已经摆正，骨架已经搭起，但评测器目前"会把错答案判成对"——W4 之前必须先修判分，否则第一份 LLM 基线成绩单不可信。**

---

## 目录

- [0. 复评摘要](#0-复评摘要)
- [1. 这一轮发生了什么](#1-这一轮发生了什么)
- [2. 逐项核验：声称 vs 实测](#2-逐项核验声称-vs-实测)
- [3. 新发现的问题](#3-新发现的问题)
- [4. 对 W4 的直接影响](#4-对-w4-的直接影响)
- [5. 纠偏方案](#5-纠偏方案)
- [6. 防跑偏机制](#6-防跑偏机制)
- [7. 更新后的路线图](#7-更新后的路线图)
- [8. 待拍板](#8-待拍板)
- [附录 A　证据索引](#附录-a证据索引)
- [附录 B　复现命令](#附录-b复现命令)
- [附录 C　负控清单](#附录-c负控清单)
- [附录 D　评分卡模板](#附录-d评分卡模板)

---

## 0. 复评摘要

### 0.1 三句话结论

1. **方向对了，而且执行速度很快。** W1–W3 一天内完成了 git、目录瘦身、单一数字源、任务层、评测器、ID test、schema、关 3 机读化、澄清闸、README 拆分——上一版建议的主干基本落地。
2. **但考卷的"判分规则"还不成立。** 受控实验证明：把 `rib_thickness` 从 4 改成 8，评测器仍判 **PASS**（保真偏差 0.46 % < 1 %）；L2 里"问对了问题、但把答案填错"也判 **PASS**。这说明当前 TSR 度量的是"下游模型像不像"，不是"答案对不对"。
3. **此外还有三处"证据通胀"和一处"可复现性缺口"**：关 3 的 55/55 里有 6 条柱壳是"只报不判"、15 条只判了位移标量；ID test 主要是边界外推而非内插；L2/L3 任务有泄漏与标签不实；数据集本体没有进 git，`v1.0-rc` 标签里没有任何 `modeling/` 数据。

**一句话**：**这是一套已经搭好的考卷，但阅卷老师还没学会扣分。先把阅卷规则修好，再让考生进场。**

### 0.2 执行总评

| 工作块 | 评分 | 一句话判断 |
|---|---|---|
| W1：git / 瘦身 / 单一数字源 | **A−** | git 与瘦身执行干净；单一数字源建了但没维护，数据本体未入库 |
| W2：任务层 / 评测器 / ID test / schema | **B−** | 架构正确；评测器判分有效性不成立，L2/L3 任务构造有缺陷 |
| W3：关 3 机读化 / 澄清闸 / README 拆分 | **B** | 方向对；关 3 的 55/55 口径被高估，单一数字源未同步 |
| **总体** | **B** | **方向正确、骨架完成、判分未验证；W4 前必须修 P0** |

### 0.3 一个必须先做的决定

> **W4 拆成两步：W4a 修判分（3–5 天）→ W4b 跑 LLM 基线。**
> 不要直接在现有评测器上跑基线。否则第一份 TSR 成绩单会把"参数错但模型像"的候选算作成功，后续所有"能力提升"都建立在假阳性上，返工成本 = 重跑全部基线。

---

## 1. 这一轮发生了什么

### 1.1 从"答案册"到"考卷"的骨架

上一版评估的判断是：**数据集是可信答案册，但不是可参加的考卷**。W1–W3 的工作正是补考卷接口：

```
W1  git + 瘦身 + 单一数字源
W2  任务层（L1/L2）+ 评测器 + ID test + schema + dataset card
W3  关 3 机读化 + 澄清评测闸 + README/SPEC/DECISIONS 拆分
```

这条路径与上一版 §7.1 的 0–30 天计划基本一致。**方向不需要再讨论，问题在落地质量。**

### 1.2 提交与交付清单

| commit | 内容 | 实际文件 |
|---|---|---|
| `894dbd0` | W1-1 首批提交 | 604 个文件入库；`.gitignore`；`v1.0-rc` 标签 |
| `5e214c5` | W1-3 单一数字源 | `external_numbers.json/.md`；`make_external_numbers.py`；对外文档 41→55 |
| `0b1919f` | W1 收口 | 记忆日志 |
| `3c7f1d6` | W2 任务层 | `tasks/tasks.jsonl`（110 行）；`tasks/nl_human.jsonl`（30 行）；`evaluate.py`；`schema.json`；`dataset_card.md` |
| `0a67200` | W2 收口 | README W2 段；冒烟 3/3 记录 |
| `2cd0381` | W3 | `gate3_all55_d37.json`；`gate3_all55.py`；澄清闸；`README/SPEC/DECISIONS` 拆分 |

### 1.3 上一版建议的采纳对照

| 上一版建议 | 状态 | 实测证据 |
|---|---|---|
| 主轴改为 Agent 评测基准 | ✅ 已采纳 | `ROADMAP.md` §0/§2 |
| 代理模型线冻结 | ✅ 已采纳 | `ROADMAP.md` §5；`BASELINE.md` 降为附录 |
| B/C 移出对外文档 | ✅ 已采纳 | 对外 md/pptx grep 无 B/C 承诺 |
| git + DVC | ⚠️ 半采纳 | git 完成；DVC 未做；`modeling/` 与 `_xval/` 被 `.gitignore` 排除 |
| A1 + A3 先行 | ⚠️ 半采纳 | A1 评测器有；A3（修复）未建 |
| 55 条冻结为 v1.0 | ⚠️ 半采纳 | `v1.0-rc` 标签存在，但**不含数据集本体**；`manifest` 未改成 ID/OOD 两套 |
| L2/L3 输入 | ⚠️ 半采纳 | L2 55 条、L3 30 条已生成；L3 **未接入评测器**，L2 有泄漏 |
| ID test | ⚠️ 半采纳 | 6 条已划出；但 4/5 轴是边界外推，不是内插 |
| schema 统一 | ⚠️ 半采纳 | 任务层规范化；发布本体未动；schema 用"实测值枚举"，会泄漏答案空间 |
| 关 3 机读化 55/55 | ⚠️ 半采纳 | 34 field-level + 15 scalar-disp + 6 reported-only；`all_ok=True` 把 reported-only 算成 PASS |
| 打包与发布 | ⚠️ 半采纳 | `dataset_card.md`、`schema.json` 有；无 loader、无数据归档、无 `fetch_data` |
| 负样本/拒答、修复题、扩族、多工况 | ❌ 未开始 | 计划在 v1.1，符合排期 |

---

## 2. 逐项核验：声称 vs 实测

> 这一节只做一件事：把 ROADMAP/README/commit message 里的"声称"和磁盘上的"实测"逐条对齐。**任何一条对不上，都记为漂移。**

### 2.1 W1

| 声称 | 实测 | 判定 |
|---|---|---|
| `git init` + tag `v1.0-rc` | `git log` 6 个 commit；`v1.0-rc` 存在；604 个文件 | ✅ |
| 仓库可 clone、哈希可复现 | 可 clone；但 `modeling/` 0 个文件入 tag | ⚠️ **数据不可复现** |
| 目录 9.7 GB → 0.4 GB | 当前 `feagpt_repro` **952 MB**（`eval_runs` 561 MB + probes）；归档包 2.8 GB 在 `F:/FEA_Archive_20261024/` | ⚠️ 数字已过期，非致命 |
| 对外材料 41 → 55 口径统一 | 两份 final_draft 已更新；pptx 已更新 | ✅ |
| 单一数字源 | `external_numbers.*` 存在；但**关 3 仍引用 `gates_all55_d36` 的 34 条**，未引用新 `gate3_all55_d37` | ❌ **源未维护** |

**W1 结论**：工程动作干净，但"可复现"只做到了代码层，没做到数据层；"单一数字源"建了但没接新产物。

### 2.2 W2

| 声称 | 实测 | 判定 |
|---|---|---|
| 任务层 110 行 = L1 55 + L2 55 | `wc -l` = 110；L1 55、L2 55 | ✅ |
| split_v2 = train/val/id_test/extrapolation_test | L1：train 19 / val 17 / id_test 6 / extrapolation 13 | ✅ 结构成立 |
| ID test = 6 条，train 包络内整类留出 28.6 % | 6 条已划出；但 **4/5 轴是边界点**（span 1600 是下界、skin 4.0 是上界、n_ribs 3 是下界、n_stringers 5 是上界） | ⚠️ **是边界留出，不是内插** |
| L2 的 `expected_clarifications` 来自"轮换省略字段" | 实测只有 3 个字段：wingbox 34 条全 omits `rib_thickness`、open_hole 11 条全 omits `width`、barrel/panel 10 条 omits `n_stringers` | ❌ **没有轮换** |
| L2 不会泄漏答案 | **6/55** 条的 `description` 里写着或暗示了被省略的值：5 条显式（`12 stringer(s)` / `8 stringer(s)` / `0 stringer(s)` / `3 stringer(s)` / `3 stringer(s)`），1 条语义（`plain panel` 暗示 0 根长桁） | ❌ **有泄漏** |
| 30 条"人工 NL" | `make_nl_human.py` 用三种模板 + spec 实读填充生成；`input_source` 标成 `human` | ❌ **标签不实**（是"人工设计模板"，不是人工撰写） |
| L3 可评测（"L3 = L1 同款三闸"） | `tasks.jsonl` 里没有 L3；`evaluate.py` 不读 `nl_human.jsonl`；`--task-id L3_...` 会 KeyError | ❌ **L3 未接入** |
| 冒烟 TSR 3/3 PASS | 3 条 barrel + 1 条 L2，全部用 **gold spec**；`fidelity=0.0 %` | ⚠️ 是 pipeline 自洽，不是 agent 成绩 |
| schema 55/55 过校验 | 无 `validate_schema.py`；`jsonschema` 未安装；README 的 55/55 无法从仓库一条命令复现 | ⚠️ **不可复现** |
| 评测器能判对错 | 受控实验：`rib_thickness` 4→8，三闸全 PASS（保真 0.4584 %） | ❌ **判分有效性不成立** |

**W2 结论**：任务层的"形"已经搭好，但"神"还没到位：**没有参数级真值、L2/L3 构造有缺陷、冒烟是自洽而非评测**。

### 2.3 W3

| 声称 | 实测 | 判定 |
|---|---|---|
| 关 3 机读化 55/55，`out_of_scope` 清零 | `n_pass=55`、`all_ok=True`；但 `evidence_levels` = field 34 / scalar 21 | ⚠️ 数字对，口径不对 |
| 其余 21 条 = 双码 + 解析锚点 | 代码只比 `max_disp` 标量；**没有计算 Howland / Navier / 薄壁闭式解**；柱壳 6 条 `gate_status=REPORTED-ONLY`，`checks` 的 `pass` 恒为 True | ❌ **既非全判，也非解析锚点** |
| 澄清闸能抓"静默默认" | `_clar_bad` 能抓；但"问对问题 + 填错值"仍 PASS（受控实验） | ⚠️ 只抓了"没问"，没抓"答错" |
| README 拆分三件套 | `README.md` 965 行、`SPEC.md` 331、`DECISIONS.md` 247 | ✅ |
| 单一数字源同步 | 未同步：`external_numbers` 仍写"关 3 翼盒 34" | ❌ |

**W3 结论**：方向正确，但**"关 3 55/55"和"out_of_scope 清零"是两个被高估的表述**。诚实的表述是：**34 条 field-level、15 条 scalar-disp-gated、6 条 reported-only**。

---

## 3. 新发现的问题

> 按"会不会让 W4 白跑"排序。P0 = W4 前必须修；P1 = W4 同期；P2 = v1.1。

### 3.1 P0-1　评测器没有参数级真值校验（最严重）

**现象**

`evaluate.py` 的三道闸是：

1. 关 1：`minJ ≥ 0.30`；
2. 关 4：`topology.compare`（面数/曲线数等语义计数）；
3. 保真：`|max_disp − gold| / gold < 1 %`。

**它没有把候选 spec 与 truth spec 的字段逐项比对。**

**受控实验（本轮新增，产物在 `eval_runs/`，已 gitignore）**

| 实验 | 候选 | 结果 |
|---|---|---|
| 正控 | gold spec | PASS（保真 0.0 %） |
| **NC-1** | `rib_thickness` 4.0 → **8.0**，其余全 gold | **PASS**：minJ 0.6249、语义 10/10、保真 **0.4584 %** |
| **NC-2** | L2 正确提问 `rib_thickness`，但 `final_spec` 填 **8.0** | **PASS**：clarify PASS、三闸 PASS、保真 0.4584 % |

**为什么这是致命的**

- 一个 agent 只要把拓扑做对、把 `max_disp` 做到 1 % 内，就可以**任意写错** `rib_thickness`、`stringer_height`、`stringer_thickness`、`mesh.size_chord`、`material.density`、`material.yield_strength` 等字段，仍然拿满分。
- 这些字段里，`rib_thickness` 是**真实的几何参数**；它在 2 倍误差下只让位移变 0.46 %。说明 1 % 的位移容差**不足以反推参数正确性**。
- TSR/FPR 会系统性高估；W4 的"基线能力"会虚高；后续"提升"无法归因。

**根因**

- 1 % 容差是从"双码同网格"判据继承来的；它适合"两个求解器算同一模型"，不适合"判断候选模型是否等于真值模型"。
- 缺少"分级字段表"（哪些字段必须精确、哪些允许容差、哪些不判）。

**修法（P0）**

新增 `spec_fidelity` 闸，作为**强制闸**：

```text
normalize(candidate) vs normalize(gold)
按族定义 GRADED_FIELDS：
  wingbox：chord, span, skin_thickness, n_ribs, rib_thickness,
           spar_chordwise, n_stringers_per_skin, stringer_height,
           stringer_thickness, stringer_kind, stringer_flange_width,
           tip_chord_ratio, sweep_deg, web_chordwise
  panel：length, width, thickness, n_stringers
  barrel：diameter, length, thickness, n_stringers, n_frames
  hole：length, width, thickness, hole_d, hole_x, hole_y, layup
判据：
  整数/枚举/数组：精确相等
  浮点：相对误差 < 1e-6（或按字段声明容差）
  材料：E、nu、layup 必判；density/yield 只报不判（声明）
  网格：size_chord/size_span/recombine/algorithm 必判（若任务输入含网格）
输出：逐字段 {field, expected, actual, pass}，任一 FAIL ⇒ 整体 FAIL
```

同时把 `fidelity_disp` 降为**辅助闸**（只用于"模型是否算得动/算得像"），不再承担"答案是否正确"的职责。

**验收**：NC-1、NC-2 必须从 PASS 变 FAIL；gold 必须仍 PASS。

---

### 3.2 P0-2　关 3「55/55」口径不成立

**现象**

`gate3_all55_d37.json` 的顶层是 `n_pass: 55, all_ok: true`；但逐条看：

| 族 | 条数 | 实际判据 | 状态 |
|---|---:|---|---|
| wingbox | 34 | 逐节点位移 + vM 中位差（引用旧报告） | field-level |
| open_hole_panel | 11 | 只判 `max_disp < 1 %` | scalar-disp-gated |
| stiffened_panel | 4 | 只判 `max_disp < 1 %` | scalar-disp-gated |
| fuselage_barrel | 6 | **无任何闸**；`max_disp` 差 2.4 %、`max_w` 3.2 %、vM 23 % 都标 `pass: true` | **REPORTED-ONLY** |

柱壳行的代码逻辑是：每个 check 都写 `pass: True`，`gated = []`，然后 `row['pass'] = all(...) = True`。所以 **6 条柱壳是"零闸 PASS"**。

**为什么这是问题**

- 对外说"55/55 双码验证"会被评审直接问穿；`dataset_card` 已经诚实写了"仅翼盒 34/34"，但 `gate3_all55_d37` 的顶层数字和 commit message 又在说"55/55"。
- 更糟的是：`external_numbers.md` 仍写"关 3 = 翼盒 34"，与 `gate3_all55_d37` 的"55/55"**互相矛盾**。单一数字源没有起到作用。

**修法（P0）**

1. **状态分级**，禁止把 reported-only 计入 PASS：
   - `GATED-PASS` / `GATED-FAIL` / `REPORTED-ONLY` / `NOT-EVALUATED`。
2. `gate3_all55_d37.json` 顶层改为：
   ```json
   {"n_cases":55, "n_gated_pass":49, "n_reported_only":6, "n_fail":0,
    "evidence_levels":{"field":34,"scalar_disp":15,"reported_only":6}}
   ```
3. 柱壳要么补 D20 场级证据（从归档包解包重算），要么在 dataset_card / external_numbers / README 三处统一写"6 条柱壳的双码为 reported-only，不作 PASS"。
4. `external_numbers` 改为读 `gate3_all55_d37`，并显示分级。

**验收**：顶层不再出现"55/55 PASS"；任一处对外表述都能追到 `gate_status`。

---

### 3.3 P0-3　ID test 是边界留出，不是内插

**现象**

当前 6 条 ID test 的取值：

| 轴 | 留出值 | 留出后 train 值域 | 性质 |
|---|---|---|---|
| `span` | 1600 | 2000–2400 | **低于下界**（外推） |
| `skin_thickness` | 4.0 | 2.0–3.0 | **高于上界**（外推） |
| `n_ribs` | 3 | 5 | **低于下界**（外推） |
| `n_stringers_per_skin` | 5 | 0–3 | **高于上界**（外推） |
| `tip_chord_ratio` | 0.9 | 0.6–1.0 | **内插** ✅ |

**5 个轴里 4 个是边界外推。** 这与"ID test 用来区分'不会建模'与'不会外推'"的设计目的直接冲突：它测的仍然主要是外推。

**修法（P0/P1）**

- **最小改动**：把当前 6 条重命名为 `boundary_holdout`，在 dataset_card 和 ROADMAP 里如实写"边界留出"；不要叫 ID test。
- **正确做法（v1.1）**：新增**内插留出**——留出点必须在剩余 train 的凸包内部，例如：
  - `span = 2400`（1500–3000 之间）
  - `skin = 3.0`（1.5–4.0 之间）
  - `n_ribs = 5`（3–9 之间）
  - `n_stringers = 3`（0–5 之间）
  - `taper = 0.8`（0.6–1.0 之间）
- 这需要新增 5 条 solve（或从现有 case 重新组合），成本可控。**不要**为了省这 5 条，把边界留出继续叫 ID test——那会让"ID vs OOD 泛化差"这个指标失去意义。

**验收**：每个 ID test 轴，留出值必须严格位于剩余 train 的 min/max 之间；脚本断言。

---

### 3.4 P0-4　L2/L3 任务构造缺陷

#### （a）L2 没有轮换

`make_tasks.py :: make_l2_input` 的注释写"每 case 轮换省略字段"，但代码是：

```python
for k in pool:
    if k in a:
        target = ('airfoil', k); break
```

**永远取池子的第一个可用字段。** 实测：

| 族 | L2 条数 | 省略字段 |
|---|---:|---|
| wingbox | 34 | 全部 `rib_thickness` |
| open_hole_panel | 11 | 全部 `width` |
| fuselage_barrel | 6 | 全部 `n_stringers` |
| stiffened_panel | 4 | 全部 `n_stringers` |

55 条 L2 只覆盖 **3 个字段**，而池子里至少有 10 个可省字段。

**修法**：`pool[hash(case_id) % len(pool)]` 或按 manifest 顺序轮换；生成后断言"每个字段至少出现 N 次"。

#### （b）L2 泄漏答案

**6/55** 条 L2 的 `description` 写出了或暗示了被省略的值：

- **5 条显式**：
  - `fuselage_barrel_d2000_l2000_str12_frm4`：`12 stringer(s)`；
  - `fuselage_barrel_d2000_l2000_str8_frm3`：`8 stringer(s)`；
  - `stiffened_panel_600x600`：`0 stringer(s)`；
  - `stiffened_panel_600x600_str3`：`3 stringer(s)`；
  - `stiffened_panel_800x600_str3`：`3 stringer(s)`。
- **1 条语义暗示**：
  - `stiffened_panel_800x600`：`plain panel`（即 0 根长桁）。

> 另外 2 条（`fuselage_barrel_d1800_l2000_str8_frm3`、`..._t2_str8_frm3`）只是描述里的 `0.818 %` / `4.6787 mm` 恰好含数字 8，**不是泄漏**，不计入。

**修法**：L2 输入删除 `description`，或做"敏感值替换"；生成后断言被省略的值不出现在 `json.dumps(input)` 的任何位置。

#### （c）L3 未接入评测器

`tasks.jsonl` 没有 L3；`nl_human.jsonl` 是独立文件；`evaluate.py` 默认 `--task-id` 查 `tasks.jsonl`，查 L3 会直接 `KeyError`。即使显式传 `--tasks tasks/nl_human.jsonl`，`evaluate_one` 也**不读 `input.nl`**——它只是把候选 spec 当 L1 一样跑三闸，NL 完全没有参与。所以"L3 评测 = L1 同款"这句话在代码层不成立。

**修法**：
- 新增 `tasks/nl_tasks.jsonl`（或 `--tasks tasks/nl_human.jsonl`）；
- `evaluate.py` 增加 `--levels L3`，对 L3 走"候选 spec → 三闸 + spec_fidelity"；
- 或者把 L3 合并进 `tasks.jsonl`，用 `input_level=L3` 区分。

#### （d）L3 的"人工"标签不实

`make_nl_human.py` 用三套模板（描述 / 任务单 / 图纸）把 spec 数字填进去；`input_source` 写 `human`。

**修法**：改为 `input_source: template_human_designed`；dataset_card 和 README 同步。**不要在没有人工撰写的情况下写 "human"。**

#### （e）两条 L3 任务自相矛盾

| 任务 | 期望澄清 | 实际 NL |
|---|---|---|
| `L3_naca4412_wingbox` | `rib_thickness` | NL 明写"肋壁厚 4 mm" |
| `L3_naca4412_wingbox_n_ribs5_chord800` | `stringer_height` | 该 case `n_stringers=0`，根本没有长桁 |

**修法**：生成后加静态断言——`expected_clarifications` 的字段必须**不在 NL 文本中**，且该字段在 gold 里**有非零意义**。

#### （f）L3 信息量过高

30 条 NL 的平均长度约 130 字，几乎把 spec 的所有参数（含网格尺寸、梁位、材料）都念了一遍。这不是"工程意图"，是"把答案口语化"。

**修法（可分两步）**：
- v1.0：保留"L3-verbalized"（口语化 spec），但如实命名，不要宣称测"理解"；
- v1.1：增加"L3-underspecified"——只给工程意图（结构形式、载荷、约束），把网格/材料默认/梁位等留给模型补默认，并把这些默认值写进 truth 的 `assumptions`。

---

### 3.5 P0-5　数据集本体没有版本化

**现象**

- `.gitignore` 明确排除 `FEM-Bench-Aero/modeling/` 与 `_xval/`。
- `v1.0-rc` 标签里 `modeling/` 文件数 = **0**。
- 一个全新 clone **无法运行** `evaluate.py`：`truth_ref`、gold spec、`model.msh` 都不在。

**后果**

- "第三方 1 天复现"不成立。
- `v1.0` 冻结只是"冻结了清单"，不是"冻结了数据"。
- 任何一次误删/覆盖都无法从 git 恢复。

**修法（P0）**

- 最小方案：打 `FEM-Bench-Aero-v1.0-data.tar.gz`（475 MB）+ `SHA256SUMS`，放在内网共享盘/对象存储；`README` 写清路径；提供 `fetch_data.py --src <path>` 解包并校验。
- 更好方案：DVC 或 git-lfs，把 `modeling/` 纳入版本；`dvc.lock` 入库。
- 无论哪种，`v1.0` 标签必须在"代码 + 清单 + 数据可获取"三者同时成立后才打。

---

### 3.6 P1-1　schema 的"实测值枚举"会泄漏答案空间

**现象**

`schema.json` 对翼盒的枚举是**数据集里出现过的所有值**：

```json
"chord":   {"enum": [800.0, 1000.0]},
"span":    {"enum": [1600.0, 2000.0, 2400.0, 3000.0]},
"n_ribs":  {"enum": [3, 5, 7, 9]},
"sweep_deg": {"enum": [0, 10, 20, 30, 35, 40]},
"taper":   {"enum": [0.4, 0.6, 0.8, 0.9, 1.0]}
```

**如果用它做"JSON Schema 约束解码"，候选只能从这些值里选——而 test 的答案也在里面。** 这把"生成"退化成了"从答案簿里挑一个"，同时泄漏了参数空间。

**修法**

- 拆成两份：
  - `schema_task.json`：类型 + 物理范围（`minimum` / `maximum` / `multipleOf`），**不含**观测值枚举；用于约束解码。
  - `schema_truth.json`：严格枚举，用于数据集校验与反向探针（死 airfoil、越界参数必须拒）。
- 两份都进 CI；`validate_schema.py` 对 55 条 gold + 55 条 normalized 各跑一遍。
- README 的"55/55 过"改为一条可复现命令。

---

### 3.7 P1-2　单一数字源没有维护

**现象**

| 文件 | 内容 | 问题 |
|---|---|---|
| `external_numbers.md` | "关 3 双码 … 34 \| gates_all55_d36" | 未引用新 `gate3_all55_d37`；与 W3 的"55/55"矛盾 |
| `external_numbers.md` | "基线 max_disp 2.631 %" | 未带 M14 的"selection bias / all-LOO 5.35 % / p90 14.09 %" |
| `external_numbers.py` | `g1 = load('gates_all55_d36.json')` | 源文件写死旧版本 |
| README（主） | 未提 M14 的 vM 未收敛 ≥13 % | 外部读者看不到最重要的限制 |

**修法**

- `make_external_numbers.py` 读最新 `gate3_all55_d37`；输出 `claim_level` 与 `source_date`。
- 增加 `--check`：若源文件 mtime 早于最新 `STAGE_GATE`，退出非零。
- 把 M14 三条硬限制写进 `external_numbers.md` 与主 README：
  1. vM 峰值未收敛（12→6 mm 仍 +12.9 %，≥13 % 偏不安全低估）；
  2. 2.63 % 是"组合插值"成绩，不是"新设计"成绩；对外承诺写 **5–9 %**；
  3. 全体留一 5.35 %、p90 14.09 %、最大 33.10 %。

---

### 3.8 P1-3　主 README 没有接入新工作

**现象**

`FEM-Bench-Aero/README.md` 仍是 M1–M5 的旧叙事（1341 行），开头没有一句话提到：

- `ROADMAP.md`（当前主计划）
- `dataset_card.md`（v1.0 卡）
- `tasks/` 与 `evaluate.py`（考卷）
- `M14` 的新发现（vM 未收敛、2.63 % 选择偏置）
- `schema.json`（契约）

外部读者从 README 进入，**看不到"这是 benchmark"**，只会以为这是一个数据集仓库。

**修法**

- README 前 30 行改为"当前状态 / 从这里开始"：
  ```
  这是什么 → 怎么用（fetch data → tasks → evaluate）→ 当前限制 → 历史
  ```
- 把 M1–M5 的长叙事移到 `HISTORY.md`；
- 链接 `ROADMAP` / `dataset_card` / `SPEC` / `DECISIONS` / `tasks` / `evaluate`。

---

### 3.9 P1-4　两套 split 并存

**现象**

- `manifest.json`：train 25 / val 17 / test 13。
- `tasks.jsonl`：train 19 / val 17 / id_test 6 / extrapolation_test 13。

同一批数据有两套划分。`dataset_card` 解释了"v1.0 用 manifest、任务层用 split_v2"，但外部用户很容易用错：**用 manifest.train 训练，就会把 id_test 的 6 条一起训进去。**

**修法**

- 明确唯一权威：**benchmark 用 `tasks.jsonl.split_v2`；`manifest.split` 只作历史/数据集层**。
- 在 manifest 里加 `split_v2` 字段（或生成 `splits_v2.json`），让两套树有单一映射。
- 在 README / dataset_card 用一句话写死："训练/评测请使用 `tasks.jsonl` 的 `split_v2`，不要使用 `manifest.split`。"

---

### 3.10 P1-5　其他工程问题

| 问题 | 证据 | 修法 |
|---|---|---|
| `equilibrium` 声明了但未实现 | `tasks.jsonl` gates 含 `equilibrium`；`evaluate.py` 只实现 3 闸 | 补平衡闸（ΣFORC 残差 < 1e-3 %），或从 task 声明中删掉 |
| `mesh_quality` 的 `n_nodes` 永远 None | `evaluate.py` 的 `(mesh.get('node_count') or (mesh.get('element_types') and None))` | 从 mesh 摘要正确读取 |
| `evaluate.py` 依赖 `sys.executable` | 用 `python -I` 跑会 `No module named numpy` | README 写死项目 Python 路径；或加 `--python` |
| `eval_runs` 561 MB | 冒烟 3 条 + 2 次受控实验 | 定期清理；评测器默认输出到临时目录 |
| `make_tasks.py` 有死代码 | `f'T{...}' if False else ...` | 清理 |
| `n_nodes` / `n_tri3` 未进入 task 级报告 | 评测结果中为 null | 补齐，便于审计 |
| 无 schema 校验脚本 | 仓库无 `validate_schema.py` | 新增并进 CI |
| `_cand_*` 冒烟产物入库 | `git ls-files tasks` 含 3 个 `_cand_*` | 移到 `tests/fixtures` 或 gitignore |

---

## 4. 对 W4 的直接影响

### 4.1 如果现在跑 LLM 基线，会发生什么

假设一个 agent 把结构拓扑建对、把 `max_disp` 做到 1 % 内，但：

- `rib_thickness` 写错；
- `stringer_height` 写错；
- `mesh.size_chord` 写错；
- `material.density` / `yield_strength` 写错；

**当前评测器会判 PASS。** 于是：

- 第一份 TSR 成绩单虚高；
- 后续每轮"提升"都可能是"更会猜参数"而不是"更会建模"；
- 当有人用严格判据复评时，成绩会大幅回撤，**推翻已交付结论**。

这正是上一版评估警告的"改考卷"风险的另一种形式：**不是改题目，是改判分。**

### 4.2 W4 的正确顺序

```
W4a  修判分（3–5 天）
  1. spec_fidelity 闸（字段级）
  2. 负控套件 NC-1…NC-8 全绿
  3. L2 答案校验 + 泄漏清理 + 轮换
  4. L3 接入评测器
  5. 关 3 状态分级 + 单一数字源同步
  6. 数据归档 + fetch_data + SHA256SUMS

W4b  跑 LLM 基线（3–5 天）
  1. 通用大模型 + JSON Schema 约束解码（用 schema_task，不用 schema_truth）
  2. 在 ID / OOD 分报 TSR、FPR、拒答、澄清、成本
  3. 保留每条失败的结构化归因
```

### 4.3 W4 的验收标准

| 项 | 判据 |
|---|---|
| 正控 | gold spec 在所有 split 上 PASS |
| 负控 | NC-1…NC-8 全部 FAIL（见附录 C） |
| 判分 | 每条结果含 `gates.*.pass` + `spec_fidelity.fields.*` |
| 分报 | `ID-TSR` 与 `OOD-TSR` 分开；不许只报总 TSR |
| 可复现 | 第三方按 README 在 1 天内跑出同一份成绩 |
| 数据 | `v1.0` 标签下能 `fetch_data` 校验通过 |
| 诚实 | 成绩单不得把 smoke / gold 结果当基线 |

---

## 5. 纠偏方案

### 5.1 P0 —— W4 前必须完成

#### ① `spec_fidelity` 闸（字段级真值）

- 新增 `evaluate.py :: spec_fidelity(candidate, gold, family)`。
- 按族定义 `GRADED_FIELDS`（见 §3.1）。
- 输出逐字段四元组：`{field, expected, actual, pass}`。
- 任一 FAIL ⇒ `overall_pass = False`。
- `fidelity_disp` 保留为辅助闸，不再承担"答案正确"的职责。
- 把 `spec_fidelity` 加进 `tasks.jsonl` 的 `gates` 列表。

**验收**：NC-1/NC-2 由 PASS 变 FAIL；gold 仍 PASS。

#### ② 负控套件（评测器的"红队"）

固定 8 条（附录 C），每次改评测器都跑：

- NC-1 错肋厚 → FAIL；
- NC-2 L2 问对填错 → FAIL；
- NC-3 错长桁数 → FAIL；
- NC-4 错网格尺寸 → FAIL；
- NC-5 错载荷大小 → FAIL；
- NC-6 错材料 E → FAIL；
- NC-7 L2 静默默认 → FAIL（已有）；
- NC-8 L3 缺字段不追问 → FAIL（需先接 L3）。

**验收**：8/8 FAIL；正控 1/1 PASS。

#### ③ L2/L3 修复

- L2 轮换省略字段（hash 或顺序轮换），覆盖 ≥8 个字段；
- L2 输入删除 `description` 或做值替换；断言省略值不在输入中；
- L3 并入任务层（或独立 `--tasks`），`evaluate.py --levels L3` 可跑；
- `input_source` 改 `template_human_designed`；
- 生成后断言：`expected_clarifications` 的字段不在 NL 中，且在 gold 中有意义。

#### ④ 关 3 状态分级

- 顶层改为 `n_gated_pass / n_reported_only / n_fail`；
- 柱壳 6 条标 `REPORTED-ONLY`，不计入 PASS；
- `external_numbers` 同步；
- 对外表述统一为"34 field-level + 15 scalar-disp + 6 reported-only"。

#### ⑤ 数据版本化

- `FEM-Bench-Aero-v1.0-data.tar.gz` + `SHA256SUMS`；
- `fetch_data.py --src <path>` 解包 + 校验；
- README 写清获取方式；
- `v1.0` 标签只在数据可获取后打（当前是 `v1.0-rc`，合理）。

#### ⑥ 单一数字源同步

- `make_external_numbers.py` 读 `gate3_all55_d37`；
- 增加 M14 三条限制；
- 增加 `--check`（源过期则非零退出）；
- 生成 `external_numbers.md` 后，主 README / dataset_card / ROADMAP 三处引用同一模板。

### 5.2 P1 —— W4 同期

- schema 拆两份（task / truth）+ `validate_schema.py` + CI；
- 主 README 重写前 30 行，链接 ROADMAP/dataset_card/tasks/evaluate；
- split 统一：manifest 加 `split_v2` 或生成 `splits_v2.json`；
- 补 `equilibrium` 闸（或删声明）；
- `evaluate.py` 修 `n_nodes` / `n_tri3`；
- 清理 `_cand_*` / `eval_runs` / 死代码；
- README 写死项目 Python 路径（或 `--python`）。

### 5.3 P2 —— v1.1

- 负样本 / 拒答题（柱壳 1–4 长桁、T 截面柱壳、越界参数、几何不可建）；
- 修复题（注入缺陷 + 闸报告 → A3）；
- 扩族（四族各 ≥20，按参数覆盖补）；
- 训练中未见的结构族；
- 多工况包线题；
- 内插型 ID test（真正的 interior holdout）；
- 场量导出 / 场级代理（若启动）。

---

## 6. 防跑偏机制

> 这是本轮的**核心交付**。前面所有的评估结论都会过期；只有这套机制能保证下一次不跑偏。

### 6.1 十维评分卡（每轮同一套）

每个维度 0–3 分，总分 30。**≥24 且无单项 ≤1 才允许进入下一里程碑。**

| # | 维度 | 0 分 | 1 分 | 2 分 | 3 分 |
|---|---|---|---|---|---|
| 1 | 目标一致性 | 在做非产品指标 | 有偏移 | 基本对齐 | 完全对齐 benchmark/verifier |
| 2 | 任务有效性 | 输入泄漏/不可解 | 有缺口 | 可用但有噪声 | 无泄漏、难度分层、可解 |
| 3 | 判分有效性 | 错答案能 PASS | 只判下游 | 有字段级但覆盖不全 | 字段级 + 负控全绿 |
| 4 | 证据等级 | 无证据 | 控制台 | 部分机读 | 全量机读 + 分级 |
| 5 | 可复现性 | 新机跑不通 | 缺数据 | 有数据但无校验 | 一条命令 + 校验 |
| 6 | 版本治理 | 无 git | 有 git 无 tag | tag 不含数据 | 代码/数据/任务全版本化 |
| 7 | 文档真实性 | 数字造假 | 有过期数字 | 小误差 | 单一数字源 + 可追溯 |
| 8 | 统计有效性 | 无 CI/泄漏 | 有 CI 但 n 小 | 预注册 | 预注册 + 冻结 test + 分报 |
| 9 | 范围纪律 | 无限扩张 | 有偏移 | 基本守界 | 红线条全守 |
| 10 | 计划执行 | 未启动 | 部分 | 按期但质量打折 | 按期且验收全过 |

**本轮自评（建议由独立复评人复核）**

| 维度 | 分数 | 理由 |
|---|---:|---|
| 1 目标一致性 | 3 | ROADMAP 已转向 benchmark，代理线冻结 |
| 2 任务有效性 | 1 | L2 泄漏、L3 未接入、ID test 是边界留出 |
| 3 判分有效性 | 1 | 错答案能 PASS |
| 4 证据等级 | 2 | 关 3 有分级但被高估；单一源未同步 |
| 5 可复现性 | 1 | 数据未入库、无 fetch |
| 6 版本治理 | 2 | git + tag，但 tag 无数据 |
| 7 文档真实性 | 2 | 大体诚实，但 "human"/"55/55" 有过期或过强表述 |
| 8 统计有效性 | 1 | test 13 条、ID test 边界化 |
| 9 范围纪律 | 3 | B/C 移出、代理冻结、不做清单明确 |
| 10 计划执行 | 2 | W1–W3 按期，但验收打折 |
| **总分** | **18/30** | **未达 24 ⇒ 不应进入 W4b；先做 W4a** |

> 这张表就是"防跑偏"的第一道闸：**分数不达标，不允许开下一阶段。**

### 6.2 红线条（不可逾越）

| # | 红线 | 违反示例 |
|---|---|---|
| R1 | v1.0 冻结后不改 test / task | 为提升基线把 test 点挪进 train |
| R2 | reported-only / not-evaluated 不得计入 PASS | "55/55"里含 6 条零闸柱壳 |
| R3 | 对外数字必须有 artifact + command | 手抄 2.63 % 而不带 M14 caveat |
| R4 | `human` 标签只能用于人工撰写的数据 | 模板生成却标 `input_source: human` |
| R5 | 评测器改动必须过负控套件 | 改完 `spec_fidelity` 不跑 NC-1 |
| R6 | 负控未全绿不得跑 LLM 基线 | 直接跑 W4b |
| R7 | 不得用 test / id_test 做训练或调参 | 用 id_test 选提示词 |
| R8 | 不得复活代理模型 KPI | 又把 max_disp MAPE 当主指标 |

### 6.3 负控套件（评测器必须能拒绝）

**每次改 `evaluate.py` / `spec_fidelity` / task 生成器，必须重跑。**

| 编号 | 注入 | 期望 | 当前 |
|---|---|---|---|
| PC-1 | gold spec | PASS | ✅ |
| NC-1 | `rib_thickness` 4→8 | FAIL | ❌ 仍 PASS |
| NC-2 | L2 问对、填 8.0 | FAIL | ❌ 仍 PASS |
| NC-3 | `n_stringers_per_skin` 0→3 | FAIL | 待测 |
| NC-4 | `mesh.size_chord` 12→20 | FAIL | 待测 |
| NC-5 | `load.magnitude` 500→600 | FAIL | 待测 |
| NC-6 | `material.youngs_modulus` 73100→60000 | FAIL | 待测 |
| NC-7 | L2 静默默认 | FAIL | ✅ 已能抓 |
| NC-8 | L3 缺字段不追问 | FAIL | 未接入 |

**验收**：PC-1 PASS + NC-1…NC-8 全 FAIL。任何一条不满足，评测器不得用于基线。

### 6.3.1 区分度检查（防止"人人都能过"）

一个 benchmark 只要"能判对错"还不够，还必须"能分出高下"。每次评测同时跑三条基线：

| 基线 | 做法 | 用途 |
|---|---|---|
| **T0 常数基线** | 永远输出 train 里最常见的 spec（不读输入） | 测泄漏与先验：T0 高 = 题目/描述泄漏 |
| **T1 检索基线** | 从 train 取最近邻 spec（只做检索，不调 LLM） | 测"是否只是背诵" |
| **T2 gold 上界** | 数据集规范 spec | 上界 100 %，用于验证评测器 |

判据：

- `LLM TSR` 必须显著高于 `T1 TSR`（建议 ≥ 10 pp），否则说明题目太容易、泄漏、或判分太松；
- 报告 `value_added = TSR_LLM − TSR_T1`；
- 按难度分层报告：锚点 / 单轴 / 双轴 / 新形式 / 新族；
- 如果 T0 已经很高，先查 L2 的 `description` 泄漏与 schema 枚举泄漏，不要先调 LLM。

> 这与代理模型线的"常数地板"是同一条纪律：**没有地板，就没有资格谈提升。**



### 6.4 主张账本（Claim Ledger）

新建 `CLAIMS.md`（或 `claims.json`），每条对外主张一行：

| 字段 | 含义 |
|---|---|
| `claim_id` | C-001 |
| `statement` | 一句话主张 |
| `artifact` | JSON/文件路径 |
| `command` | 复现命令 |
| `date` | 生成日期 |
| `level` | GATED / REPORTED / NOT-EVALUATED |
| `coverage` | 55/55、34/55、单点 |
| `status` | active / superseded / retracted |

**规则**：
- `external_numbers.md` 只能从 `claims.json` 生成；
- 任何对外文档引用的数字必须出现在 `claims.json`；
- 过期主张标 `superseded`，不删除（保留历史）。

### 6.5 节奏与角色

| 频率 | 动作 | 负责人 | 产物 |
|---|---|---|---|
| 每周 30 分钟 | 十维评分卡 + 红线条自查 | 执行人 | `weekly_check.md` 追加一行 |
| 每个 W 块结束 | 完整复评（本文档模板）+ 负控 | 执行人 + 独立复评人 | `STAGE_GATE_WX.md` |
| 每 2 个里程碑 | 独立复评（换人/外部） | 独立复评人 | `REVIEW_<date>.md` |
| 每次 release | 冻结、tag、归档、发布 | 执行人 | `RELEASE.md` + `SHA256SUMS` |

**角色分离**：
- **执行人**不能给自己的评测器签字；
- **独立复评人**必须亲自跑负控，不能只看报告；
- **决策人**只在评分卡达标时批准进入下一阶段。

### 6.6 复评模板（下次直接套）

```markdown
# <里程碑> 复评
## 0. 结论（Go / Conditional-Go / No-Go）
## 1. 声称 vs 实测（逐条表）
## 2. 十维评分卡（分数 + 理由）
## 3. 红线条检查（R1–R8）
## 4. 负控结果（PC-1 + NC-1…NC-8）
## 5. 新增漂移（按 P0/P1/P2）
## 6. 纠偏动作与验收
## 7. 是否允许进入下一阶段
```

---

## 7. 更新后的路线图

### 7.1 W4a（3–5 天）：修判分

| 任务 | 交付物 | 验收 |
|---|---|---|
| `spec_fidelity` 闸 | `evaluate.py` 新闸 + 逐字段报告 | NC-1/NC-2 变 FAIL |
| 负控套件 | `tests/negative_controls.py` | 8/8 FAIL + 1/1 PASS |
| L2 轮换 + 去泄漏 | 新 `tasks.jsonl` | 覆盖 ≥8 字段；泄漏 0 |
| L3 接入 | `evaluate.py --levels L3` | 30 条可跑 |
| 关 3 分级 | 新 `gate3_all55` + external_numbers | 34/15/6 分级 |
| 数据归档 | tar.gz + SHA256SUMS + `fetch_data.py` | 新机可校验 |
| 单一源同步 | `make_external_numbers.py --check` | 0 stale |

### 7.2 W4b（3–5 天）：跑基线

| 任务 | 交付物 | 验收 |
|---|---|---|
| schema_task 约束解码 | 生成模块 | 合法率 ≥ 95 % |
| 通用大模型基线 | P1 成绩单 | 逐任务可溯源 |
| **T0/T1/T2 对照** | 常数 / 检索 / gold 三条基线 | `value_added = TSR_LLM − TSR_T1` ≥ 10 pp |
| ID/OOD 分报 | TSR/FPR/拒答/澄清 | 分列 + CI |
| 难度分层 | 锚点/单轴/双轴/新形式/新族 | 每层样本数与 TSR |
| 失败归因 | 结构化报告 | 每失败一条归因 |

### 7.3 30–90 天

- A1 稳定 + A3 修复闭环（修复成功率 ≥ 70 %）；
- 消融（约束 / 修复 / RAG）；
- v1.1 数据：负样本、修复题、扩族、多工况；
- 内插型 ID test。

### 7.4 90–180 天

- RAG + 失败回流；
- 专家盲评 + 效率对比；
- 原型 V1（NL→澄清→生成→求解→云图→报告）；
- 屈曲/模态扩展规划。

---

## 8. 待拍板

| # | 事项 | 建议 |
|---|---|---|
| 1 | 是否接受 W4 拆成 W4a（修判分）+ W4b（跑基线） | **接受**；否则基线不可信 |
| 2 | 是否接受 `spec_fidelity` 为强制闸 | **接受**；这是 benchmark 的底线 |
| 3 | 是否接受把当前 `id_test` 重命名为 `boundary_holdout`，v1.1 再补真内插 | **接受**；不要用边界留出冒充 ID |
| 4 | 是否接受数据归档 + `fetch_data`（替代 DVC 的最小方案） | **接受**；先让 v1.0 可复现 |
| 5 | 是否接受"关 3 = 34 field + 15 scalar + 6 reported-only"的统一表述 | **接受**；停止说 55/55 |
| 6 | 是否接受十维评分卡 + 红线条 + 负控 + 主张账本作为常设机制 | **接受**；这是防跑偏的核心 |
| 7 | 是否接受 M14 的对外口径（承诺 5–9 %，不承诺 3 %） | **接受**；写入 external_numbers 与 README |
| 8 | 是否接受 T0/T1/T2 平凡基线作为常设对照 | **接受**；没有地板就没有资格谈提升 |

---

## 附录 A　证据索引

| 结论 | 证据 |
|---|---|
| git 6 个 commit / v1.0-rc | `git log --oneline`；`git tag -n` |
| 604 个文件入库；`modeling/` 0 个 | `git ls-files \| wc -l`；`git ls-tree -r v1.0-rc \| grep modeling \| wc -l` |
| 任务层 110 行 = L1 55 + L2 55 | `wc -l feagpt_repro/tasks/tasks.jsonl` |
| split_v2：19/17/6/13 | `tasks.jsonl` 统计 |
| L2 省略字段：34/11/6/4 | `tasks.jsonl` 统计 |
| L2 泄漏 6/55（5 显式 + 1 语义） | `tasks.jsonl` 的 `description` 比对 |
| L3 30 条、8 条澄清型、4 条 id_test | `tasks/nl_human.jsonl` 统计 |
| L3 未接入 | `grep -rn "nl_human" evaluate.py` 无命中 |
| 受控实验 NC-1 | `eval_runs/L1_naca4412_wingbox/evaluation.json` |
| 受控实验 NC-2 | `eval_runs/L2_naca4412_wingbox/evaluation.json` |
| 关 3 分级 | `gate3_all55_d37.json :: cases[*].gate_status` |
| 柱壳零闸 | `gate3_all55_d37.json` 中 `fuselage_barrel` 行 |
| external_numbers 仍写 34 | `external_numbers.md` 第 15 行 |
| M14 的 vM 未收敛 | `STAGE_GATE_M14.md` §3.5 |
| M14 的 2.63 % 选择偏置 | `STAGE_GATE_M14.md` §4.4 |
| 主 README 未提新工作 | `grep -n "ROADMAP\|tasks\|evaluate\|M14" FEM-Bench-Aero/README.md` 无命中 |
| schema 枚举 | `schema.json :: allOf[0].then.properties.airfoil` |
| 无 schema 校验脚本 | `ls feagpt_repro \| grep schema` 无命中 |
| `eval_runs` 561 MB | `du -sm feagpt_repro/eval_runs` |

## 附录 B　复现命令

> 受控实验产物在 `eval_runs/`（已 gitignore），不影响仓库；两次实验分别是 L1 与 L2 的负控。

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# 任务层统计
"$PY" - <<'PY'
import json, collections
rows=[json.loads(l) for l in open('tasks/tasks.jsonl',encoding='utf-8')]
print(collections.Counter((r['input_level'],r['split_v2']) for r in rows))
print(collections.Counter((r['family'],r['expected_clarifications'][0]) for r in rows if r['input_level']=='L2'))
PY

# 负控 NC-1：错肋厚（当前会 PASS —— 这就是问题）
"$PY" evaluate.py --task-id L1_naca4412_wingbox \
  --spec "C:/Users/22207/AppData/Local/Temp/probe_wrong_rib_thickness.json"

# 负控 NC-2：L2 问对但填错（当前会 PASS）
"$PY" evaluate.py --task-id L2_naca4412_wingbox \
  --spec "C:/Users/22207/AppData/Local/Temp/probe_l2_wrong.json"

# 关 3 分级核对
"$PY" - <<'PY'
import json, collections
d=json.load(open('../FEM-Bench-Aero/gate3_all55_d37.json',encoding='utf-8'))
print(collections.Counter((r['family'], r.get('gate_status','field-level')) for r in d['cases']))
PY
```

## 附录 C　负控清单

| 编号 | 注入方式 | 期望 | 验收命令 |
|---|---|---|---|
| PC-1 | gold spec | PASS | `evaluate.py --use-gold` |
| NC-1 | `rib_thickness` 4→8 | FAIL | 附录 B |
| NC-2 | L2 问对、填 8.0 | FAIL | 附录 B |
| NC-3 | `n_stringers_per_skin` 0→3 | FAIL | 新增 |
| NC-4 | `mesh.size_chord` 12→20 | FAIL | 新增 |
| NC-5 | `load.magnitude` 500→600 | FAIL | 新增 |
| NC-6 | `material.youngs_modulus` 73100→60000 | FAIL | 新增 |
| NC-7 | L2 静默默认 | FAIL | `_clar_bad.json` |
| NC-8 | L3 缺字段不追问 | FAIL | 新增 |

**规则**：负控脚本必须能一条命令跑完；结果写入 `eval_runs/negative_controls.json`；每次改评测器都更新。

## 附录 D　评分卡模板

```markdown
## 十维评分卡（<里程碑>）

| # | 维度 | 分数 | 理由 | 证据 |
|---|---|---:|---|---|
| 1 | 目标一致性 | /3 | | |
| 2 | 任务有效性 | /3 | | |
| 3 | 判分有效性 | /3 | | |
| 4 | 证据等级 | /3 | | |
| 5 | 可复现性 | /3 | | |
| 6 | 版本治理 | /3 | | |
| 7 | 文档真实性 | /3 | | |
| 8 | 统计有效性 | /3 | | |
| 9 | 范围纪律 | /3 | | |
| 10 | 计划执行 | /3 | | |
| **总分** | | **/30** | | |

判定：≥24 且无单项 ≤1 → Go；否则 Conditional-Go / No-Go。
```

---

> **本文件是第二轮复评的产物，不修改任何既有项目文件。**
> 本轮为验证判分有效性运行了两次受控实验（NC-1 / NC-2），产物在 `feagpt_repro/eval_runs/`，已被 `.gitignore` 排除。
> 下一轮复评请直接套用 §6.6 模板，并先跑附录 C 的负控清单。
