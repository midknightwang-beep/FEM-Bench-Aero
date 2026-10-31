# T-B1KPI 报告：修复成功率 / 收敛轮数补算（零重跑）

> 收口时间：2026-11-01
> 闸：`feagpt_repro/_b1_repair_kpi.py`（9 条对账判据 C1–C9 + **十向自检** + `--json`）
> 证据：`feagpt_repro/reports/diagnostics/b1_repair_kpi.json`
> 契约：`task_b1kpi_contract.md`

## 1. 一句话

B1 缺的两项补上了，**L1 修复成功率 98.1%–100%，远超 B3 的 70% 阈值**；但这个 100% 是**闸严格度的影子**——所有 spec 题首轮结构校验**无一条通过**，而首轮失败几乎全部集中在 `material` 的三个 required 键和 prompt 自己教错的 `size` 键上。**修复循环把它全遮住了。**

## 2. 立项时的读数本身是错的（先更正，再干活）

| ROADMAP 原话 | 实测 |
|---|---|
| B1 = **4/8**，后四项（FPR / 修复成功率 / 收敛轮数 / 拒答准确率）「从未按定义算过」 | **FPR 早就算过了**：`fpr` 块在 v7_glm / v7_ds / v6c_p2 / v6c_ds_p2 **四份**成绩单里都在；C-040 / C-032 / C-033 正文都报了数字（glm 0/5、ds 1/5；v6c 代 0/4、1/4） |
| ⇒ 真实缺口 | 只有**两项**：修复成功率、收敛轮数。第八项拒答准确率**不是「没算」而是「不可算」**——它没有题型（B5 五类题只完成了扩族），分母不存在 |

⇒ B1 现状 **5/8 → 本轮补到 7/8**。剩下那一项（拒答准确率）**卡在题型上，不卡在统计上**，本轮不碰。

这是「文档没有闸守 ⇒ 会漂」的第 N 次复现（T-R1 同族）。**本轮只更正读数，不建闸**（见 §9）。

## 3. `turns_used` 到底是什么（读源码，不推测）

`gen_candidates_v2.js:185-256`：

```js
for (let turn = 1; turn <= maxTurns; turn++) {
  turnsUsed = turn;
  ...调用 LLM...
  if (r.parse_error) { valHistory.push({turn, errors: [...]}); }        // 继续下一轮
  else if (r.clarify && !r.spec) { clarify = r.clarify; break; }         // 通过：break
  else {
    if (t.input_level === 'L2') break;
    if (ok && !cerr.length) break;                                      // 通过：break
    valHistory.push({turn, errors});  spec = null;  ...推回错误...      // 继续下一轮
  }
}                                                                        // 跑满不 break
```

⇒ **`turns_used` 是「LLM 调用轮数」，不是「修复轮数」**；修复轮数 = `turns_used - 1`。

而且这里有个**必须搞清楚的细节**，首版就栽在这上面：

| 情形 | `len(validation_history)` |
|---|---|
| 某轮通过 / 出澄清 | `turns_used - 1`（通过那轮不留校验记录） |
| 跑满 3 轮仍失败 | `turns_used`（第 3 轮的错误也 push 了） |

首版把不变量写成单一等式 `turns_used == len(vh) + 1`，被 `cfrp45s_d40`（3 轮全失败）当场判红。**那是我的判据漏了「耗尽」分支，不是数据错**（§8 自纠一）。

## 4. 三层结果（必须三层分开读，缺一层这个 KPI 就是自欺）

| run | 题数 | **L1 结构层修复成功率** | L2 修复去向 | **L3 语义通过率** | 修复轮中位 | ≤1 轮占比 | 首轮通过 |
|---|---|---|---|---|---|---|---|
| C-040 v7 × glm | 64 | **59/59 = 100.0%** | spec 59 | **48/59 = 81.4%** | 1 | 96.6% | 5（**全是澄清题**） |
| C-040 v7 × ds | 64 | **61/61 = 100.0%** | spec 59 + clarify 2 | **50/59 = 84.7%** | 1 | 95.1% | 3（**全是澄清题**） |
| C-032 v6c × glm | 55 | **52/52 = 100.0%** | spec 51 + clarify 1 | **41/51 = 80.4%** | 1 | 96.2% | 3（**全是澄清题**） |
| C-033 v6c × ds | 55 | **52/53 = 98.1%** | spec 51 + clarify 1 | **42/51 = 82.4%** | 1 | 90.6% | 2（**全是澄清题**） |

三层定义：

- **L1**：首轮 schema/contract 未过的题，在 `max_turns=3` 内产出可判记录（`spec` 或 `clarify` 非空）的比例。**B3 的 70% 阈值只管这一层。**
- **L2**：修出来的东西是 spec 还是 clarify。
- **L3**：结构修好之后，`spec_fidelity` 是否全对（取成绩单 `category`，不重算 TSR）。**这一层才是模型能力那一面。**

唯一未收敛：`L3_open_hole_panel_400x200_d20_cfrp45s_d40`（C-033），3 轮都卡在 `/structure/params/layup must be number` —— 同一字段连错三次。

**L3 与成绩单 TSR 的闭合关系**（已机器化，判据 C9）：`spec_pass + clarify_ok == tsr.pass`，四份成绩单全部成立（53/53、54/54、45/45、44/44）。

## 5. 核心发现一：L1 = 100% 是闸严格度的影子，不是模型能力

**所有 spec 题首轮结构校验全部未过**：glm v7 **0/58**、ds v7 **0/61**、glm v6c 0/51、ds v6c 0/51。

首轮通过的清一色是澄清题——它们第 1 轮只输出 `clarify`，根本不进 spec 校验。

⇒ 所以「修复成功率 100%」这个数的真实含义是：**闸很严，而错误反馈足够清楚，模型照着改就能改对格式。** 它证明的是**闭环可读性**，不是建模能力。同一批题 L3 只有 80.4%–84.7%。

**这也是为什么不能只报一个 100%**：把 L1 当成模型成绩，等于用「模型会读错误信息」冒充「模型会建模」。

## 6. 核心发现二：首轮失败几乎全部集中在两个**可修**的点上

### 6.1 `material` 的三个 required 键

| run | `youngs_modulus` | `poisson_ratio` | `yield_strength` | 分母 |
|---|---|---|---|---|
| v7 glm | 58 | 58 | 58 | 59 |
| v7 ds | 61 | 61 | 47 | 61 |
| v6c glm | 52 | 52 | 52 | 52 |
| v6c ds | 53 | 53 | 45 | 53 |

`schema_task.json` 的 `properties.material.required` = `[name, youngs_modulus, poisson_ratio, density, yield_strength]`（**5 个全 required**）。

而 SYS prompt 里 `material` 只写成 `"material":{...}`（`gen_candidates_v2.js:23`）—— **一个 required 键都没列**。

⇒ **这不是随机的模型错误，是 prompt 与 schema 不同步**。58 条题里有 58 条首轮失败，原因同一个。

### 6.2 prompt 教了一个 schema 不接受的键

`gen_candidates_v2.js:40` 原文：

> 网格键 **size_chord/size_span（翼盒）、size（板壳类）**

而 `schema_task.json` 的 `properties.mesh`：

```json
"required": ["size_chord", "size_span"],
"properties": { "size_chord": …, "size_span": …, "order": …, "refine_le": … }
```

**`size` 根本不在 properties 里**（`additionalProperties` 直接拒）。而且 `mesh.required` 是**所有族**都要 `size_chord/size_span`，没有「板壳类用 `size`」这个分支。

实测后果（一因两果，同一条 prompt）：

| 现象 | v7 glm | v7 ds |
|---|---|---|
| `size` 被当自创键拒 | **21** | **21** |
| 同时 `size_chord` / `size_span` 报 required 缺失 | **21 / 21** | **22 / 22** |

按族核实：`size` 被拒的题全部是板壳类（open_hole_panel 12、stiffened_panel 3、fuselage_barrel 6）——**正是 prompt 说的那一批**。

⇒ 这是「文档描述了一个不存在的能力」的又一形态（T-D2 的 README `--url` 同族）：**prompt 描述了一个不被接受的键，而模型完全照着做了。**

### 6.3 其余自创键

`type`（glm 48 / ds 1）：模型把 `analysis` 写成 `{"type": "static"}`，而 schema 的 analysis 只收 `solver/step_type/incremental/initial_increment/total_time/outputs`。

**同一 prompt 下 glm 犯 48 次、ds 只犯 1 次** ⇒ 这一项是模型行为差异，不是 prompt 缺陷。与 6.1/6.2 性质不同，不能混为一谈。

## 7. 核心发现三：修复循环把上面这些全遮住了

如果没有这道闸，读到的只有：

```
turns_histogram = {1: 5, 2: 57, 3: 2}
n_unresolved = 0
```

看起来「一切正常，几乎没有失败」。**实际上 64 条题里有 59 条首轮都错了**，其中 58 条错在同一个 required 缺失上。

这是「**闸把真问题挡在了外面**」的典型案例：修复循环做得越好，越看不出 prompt 与 schema 不同步。

**必须讲清的边界**：发现 6.1/6.2 只能推出「首轮错误高度集中、且指向 prompt 与 schema 不同步」，**不能**推出「修了 prompt 首轮通过率就会从 0 涨到 X%」——模型可能改对了这里又错那里。真要量化，得改 prompt 重跑一批（本轮明确不做）。

## 8. 闸与判据

9 条对账判据。**核心设计：不重新实现 turns 语义，而是拿两份独立产物对账**——候选文件由生成阶段写出，成绩单由评分阶段写出，两个不同的程序。

| 判据 | 对账什么 | 红了意味着 |
|---|---|---|
| C1 | 候选实读 `turns_used` 直方图 == 成绩单 `turns_histogram` | 两套统计口径漂了 |
| C2 | `first_pass_valid` == 直方图 `turns=1` 计数 | 同上 |
| C3 | 成绩单 `n_unresolved` == 候选侧「spec 与 clarify 均空」条数 | 「未收敛」两套定义 |
| C5 | 轮次与校验记录数自洽（**双分支**：通过 `turns-1`、耗尽 `turns`） | 我对 turns 语义的理解错了 |
| C6 | 分母（首轮未过题数）> 0 | 空壳：全首轮通过时 100% 无意义 |
| C7a | 成绩单里有的题，候选目录里必须也有 | 覆盖不足 |
| C7b | 逐题形态（spec/clarify/空）与 `category` 大类一致 | 判分器与生成器产物对不上 |
| C8 | 给了 spec 的题，类别必须落在 `{spec_pass, spec_fail, fabricated}` | 出现未知类别 ⇒ 分项漏计 |
| C9 | `spec_pass + clarify_ok == tsr.pass` | 判分器两个出口对不上 |

**十向自检**（`--self-test`，10/10 rc=0）：好数据须绿、篡改直方图、篡改 first_pass、缺候选、破坏 turns（通过分支）、无产出却提前停止（耗尽分支）、分母为 0、category 不符、未知类别、顶层 TSR 不符。

## 9. 现场自纠（四条，全是自检/实测抓出来的）

1. **C5 判据漏了「耗尽」分支**。写成 `turns_used == len(vh)+1`，被 `cfrp45s_d40`（3 轮全失败）判红。**先怀疑自己的判据**：回去读源码，确认跑满 3 轮不 break、第 3 轮错误也 push ⇒ 改成双分支，且**更严**（还多抓「提前停止」）。
2. **C7 用错了字段**。`per_task` 的键名**不统一**：澄清题有 `expected`，spec 题没有这个键。用 `t.get('expected') or []` 会把 spec 题一律判成「无期望澄清」，而 `fabricated` 那几条恰好就是「没有 `expected` 键」的 ⇒ 1 条真的 `fabricated` 被误判成形态不符。改用判分器自己的布尔 `ec`。
3. **C8 首版是恒真式**。写成 `sum(spec_cat.values()) == len(repaired_spec)` —— Counter 的值之和按定义就等于元素个数，**任何未知类别都能「闭合」**。自检 `bad_closure` 那一向因此永远绿，我一开始还以为是断言写错了。改成「类别必须落在已知集合」后才真的会红。与 N-26「恒真式外观与正常闭合一模一样」同族。
4. **夹具不真**。「好数据须绿」那一向被 C5 判红——因为夹具按 `turns-1` 造校验史，而真实的**耗尽**题是 `turns` 条。**判据没错，是夹具不真**（T-D6 同族）。

另外一条不算自纠但值得记：**首版 `bad_hist` 那一向也永远绿**，因为我传的假直方图 `{1:1,2:1,3:1}` 恰好**等于**实读值——造假数据没造坏，看起来像判据有病。

## 10. 边界与明确不做的

- **不重跑任何模型**，不调 prompt，不改任何成绩 / 分母 / headline / rubric / 考卷。
- **拒答准确率不可算**：`status=not_computable`，不进任何分子分母，**不印数字**（R-A3）。它卡在 B2/B5 的题型上。
- **不修** 6.1/6.2 那两处 prompt 与 schema 不同步：改 prompt 会改变被测行为，必须单独立项 + 重生成 + 按 R53 记 `prompt_sha256`，不是本轮「只读补算」该做的事。
- **不给 ROADMAP 加闸**（本轮撞见的「B1 读数过期」只更正）。
- **不把 `size` 类检查机器化**（「prompt 提到的键必须在 schema 里存在」是个好判据，但要解析中文 prompt，容易假红，得单独设计）。

## 11. 下一步（一个）

**把 6.1 / 6.2 立成「prompt 与 schema 对齐」单子**：列出 prompt 正文里提到的所有键、逐个问 `schema_task.json` 收不收；再把各块 required 清单显式写进 SYS prompt。**收益是可量化的省一轮**（59 条题里 58 条首轮都错在同一处），但**必须先立项、先冻结 sha、重跑一批才敢说省了多少**。
