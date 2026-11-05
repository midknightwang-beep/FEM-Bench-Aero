# T-L27c v4：SYS 修正（CONFLICT N-34 收口）

> 日期：2026-11-04　｜　触发：老王拍板「改 SYS」（N-34 选项 A）　｜　状态：**diagnostic + 换代**，headline 待 v6c 复验

## 0. 一句话结论

把 SYS 第 40 行那句「网格键 size_chord/size_span（翼盒）、**size（板壳类）**」改成「网格键 size_chord/size_span（**四族通用**）」之后：

- **`size` 多余键从 12 处降到 0**（四族 64 个 gold 的 mesh 键集实测完全一致，本来就没有 `size`）；
- **glm 在 L2 信息完备题上从 3/16 → 13/16（base）、10/16 → 16/16 & 15/16（strict）**，配对 McNemar **p = 0.0312**、b = 0（纯单向）；
- **ds 对这次修正不敏感**（strict 下 8 → 10/12，p = 0.69），它的瓶颈是「把 schema 规范意见当澄清理由」，属另一条线；
- **L3 的 exam 判分段零回归**（glm 23/25 → 23/25）。

## 1. 唯一变量

| | 改前 | 改后 |
|---|---|---|
| SYS 第 40 行 | `网格键 size_chord/size_span（翼盒）、size（板壳类）。` | `网格键 size_chord/size_span（四族通用）。` |
| `PROMPT_SHA`（L3） | `ce225186cafa…` | `6b90daf07bbe…` |
| `PROMPT_SHA_L2` | `03129c56d83b…` | `c8de26d43bf7…` |
| `PROMPT_SHA_REFUSE` | `094cd870f2b0…` | `b4c2dd6e8f55…` |
| `PROMPT_SHA_L2_STRICT` | `99466166dc04…` | `f6cb45f73874…` |

三处判断，都写进了源码注释：

1. **不只删「、size（板壳类）」，连「（翼盒）」也一并改对。** 实测 64 个 gold 覆盖四族，mesh 键集**完全一致**（9 键：`size_chord`/`size_span` + 7 个执行配置键），板壳类同样用这两个键 —— 留着「（翼盒）」等于修了一半，会让模型以为板壳类另有一套。
2. **刻意不在 SYS 里提「size」这个词。** 上一轮 C 臂的覆盖段原文写「…**没有 size 这个键**」，结果 ds 反而追问了 4 条（覆盖段把原本可忽略的矛盾显式化了）。⇒ 修 prompt 时「点名否定」比「不说」更容易诱发追问。
3. **SYS 其余部分一字未动**，题面、rubric、判分器一个字节没改。

## 2. L2 信息完备题（16 条诊断卷）：错误模式归零

### 2.1 分数

| 模型 | 旧 base | 新 base | 旧 strict | 新 strict 第 1 遍 | 第 2 遍 |
|---|---|---|---|---|---|
| glm-5.3-flash | 3/16 | **13/16** | 10/16 | **16/16** | 15/16 |
| deepseek-v4-pro | 4/16 | 1/16 | 13/16 | **14/16** | 13/16 |

> **★ 本表为 2026-11-05 N-35 修正后的口径**（`extra` 的 7 个数据集记账键不再判分）。旧口径：
> glm 2→8→10→16 & 14、ds 3→1→8→10 & 12。旧代成绩单归档在 `reports/archive/l2i_*__pre_n35.json`，
> 逐 arm 对照见 `n35_bridge.md`（`_n35_bridge.py` 现读生成，不手抄）。

### 2.2 配对检验（旧 strict → 新 strict，同一 16 条、同一模型）

| 模型 | 前 → 后 | b（前对后错） | c（前错后对） | McNemar 精确双侧 |
|---|---|---|---|---|
| glm | 10/16 → 16/16 | **0** | 6 | **p = 0.0312** |
| ds | 13/16 → 14/16 | 1 | 2 | p = 1.0000 |

**b = 0 比 p 值更有信息量**：glm 是「零个 case 变差、只有改善」，不是均值为零的噪声能产生的形状。

### 2.3 产物侧硬证据（`_l27c_check_mesh_keys.py`）

| 候选目录 | 给出 spec | mesh 键有问题 | 形态 |
|---|---|---|---|
| base（旧 SYS）glm | 14 | **9** | 多写 `size` + 缺 `size_chord`/`size_span` |
| base（旧 SYS）ds | 7 | **3** | 同上 |
| **base（新 SYS）glm** | 16 | **2** | 缺 5 个执行配置键（**多余键 0 处**） |
| **新 SYS 全部候选（L2 + L3，两模型）** | — | — | **多余 `size` = 0** |

⇒ 旧 SYS 下 12 条问题题**全部**是「多出一个 `size`、少了 `size_chord`/`size_span`」这个完全一致的模式，不是随机转写失误，是**按那句话执行的必然结果**；新 SYS 下这个模式**彻底消失**。

## 3. L3：exam 判分段零回归

### 3.1 v7 卷（64 条）

| 模型 | 旧 prompt | 新 prompt 第 1 遍 | 第 2 遍 |
|---|---|---|---|
| glm | **23/25**（TSR）、20/22（SFR） | **23/25**、20/22 | — |
| ds | 23/25 | 22/25 | **23/25** |

- glm 两份成绩单的 `exam` 块**逐字段完全一致**；全卷判分段（`structure`/`airfoil`/`mesh`/`load`/`material`/`bc`）**58/64 相同**，差异 6 条全落在 **dev**，键为 `params.layup`（写成了标量）、`stringer_*`（自创键）、`stiffened_panel_800x600_str3` 的 `length`/`width`（**已知 dev 缺陷**，长期挂 dev 不对外）。
- ds 两遍 **22 / 23**，跨度本身就说明那条 23→22 落在噪声内（翻转全在 `clarify_ok ↔ fabricated ↔ spec_fail` 之间，与 mesh 键无关）。

### 3.2 v6c 卷（55 条，C-032/C-033 的 artifact）

v6c 的 55 条 L3 与 v7 **逐字节完全相同**（实测 55/55，R65「跨版只许加行」）⇒ 新 prompt 下的 v6c 成绩可直接**用 v7 候选按 v6c 卷取子集重打分**得到，不必重跑一轮生成。

| | p2 代（旧） | v2f 代（新） | 变化 |
|---|---|---|---|
| glm exam TSR | 23/25 | **23/25** | 0（逐题类别相同） |
| glm exam SFR | 20/22 | **20/22** | 0 |
| glm dev TSR | 22/30 | **23/30** | +1（采样波动，见下） |
| ds exam TSR | 22/25 | **22/25** | 0 |
| ds exam SFR | 20/21 (95.2%) | **20/23 (87.0%)** | 分母 21→23，分子 20 不动 |
| ds dev TSR | 22/30 | **23/30** | +1 |

**glm 全卷 55 条只有 1 条判类变化，且不在 exam**：`L3_fuselage_barrel_d2000_l2000_t2_str8_frm3` `spec_fail → spec_pass`。查其原因**不是 mesh 键**，而是 `extra.end_moment` 这次写成 **5e7**（50 kN·m 换算对），p2 代同题写 **5e6**（×10⁻¹）⇒ **单位换算碰对，属采样波动**，不能算成 SYS 修正的收益（p2 代 C-032 的 dev 分析里记的正是这两条柱壳的同一缺陷）。

**ds 全卷 4 条判类变化，可逐条归因**：

| 题 | p2 → v2f | 归因 |
|---|---|---|
| `L3_naca4412_wingbox` | `clarify_wrong → clarify_ok` | **R71 判分修正表（T-P1a）生效**，与 prompt 无关（p2 代成绩单早于修正表） |
| `L3_open_hole_panel_400x200_d20_cfrp45s_d40` | `no_output → spec_fail` | 模型这次给了 spec 但保真失败（**SFR 分母 +1 的来源**） |
| `L3_fuselage_barrel_d1600_l1600_str8_frm3` | `clarify_ok → fabricated` | **唯一实质退步**，单遍不可与采样波动分离 |
| `L3_open_hole_panel_400x200_d20`（dev） | `fabricated → clarify_ok` | 变好，同为单遍不可分辨 |

⇒ **「换代」在这两份成绩单上是「组成变了」不是「分数掉了」**：ds 的 SFR pct 从 95.2% 降到 87.0%，分子 20 一个没动、分母从 21 涨到 23（模型开始产出更多 spec，其中 2 条保真失败）。**按 R54 两个 pct 不得直减。**

### 3.3 MSR：复用 + 定点点跑的边界

改 prompt 会让 51 条 spec 全部重新生成 ⇒ 严格做法是重跑 51 条全链（≈50 min/模型）。但 MSR 的输入只有 spec 里**进流水线的那部分**：

- 剔除 `name` / `description`（纯文本，不进流水线）后逐字节相同 ⇒ **求解结果按构造成立**，直接复用；
- 不同的条目（glm **8 条**、ds **3 条**）+ 旧代「无 spec」但新代给了 spec 的条目（ds `cfrp45s_d40`）**必须重跑**。

⇒ `msr_l3.py --reuse <旧成绩单> --force <重跑名单>`：glm 复用 43 / 重跑 8，ds 复用 47 / 重跑 4。**复用源与 force 名单写进 `msr_section.provenance`**，不是口头约定。

**结果**：glm 全卷 **41/51、exam 20/22、dev 21/29**（与 p2 代逐数相同，2 条 dev 互换净额 0）；ds 全卷 **41/51**、exam **19/22**、dev 22/29，`n_solver_excluded=1`（`str12_frm4` 撞 158,548 节点阈值 ⇒ N-25 复发，±1 不可解读）。

**这条边界要记着**：复用是「同一份求解输入的复用」，不是「同一个 task_id 的复用」。旧版 `--reuse` 只按 task_id 取结果 —— 本轮先自己比对了 spec 子集才敢用，**这个比对如果省掉，就等于把旧 spec 的分数贴到新 spec 上**。

## 4. L2 v7（64 条澄清题）：把「跨天波动」和「SYS 效应」分开

### 4.1 三次测量

| 模型 | 旧 prompt（5 天前） | 旧 prompt（**今日对照**） | 新 prompt 第 1 遍 | 第 2 遍 |
|---|---|---|---|---|
| glm | 49/64 | — | 46/64 | 48/64 |
| ds | 36/64 | **40/64** | **52/64** | **46/64** |

### 4.2 为什么必须跑「旧 SYS 今日对照」

ds 从 36 跳到 52 是 +16 条，幅度太大，不能直接归给「改了一句 mesh 键名」。于是把 SYS 临时改回旧表述（sha 验回 `ce225186`）跑了全量 64 条对照，再改回新表述（sha 验回 `6b90daf0`）。

**结论分两层**：

- **跨天波动 ≈ +4 条**（同 prompt、5 天前 36 → 今日 40）—— 服务端/采样波动，与 SYS 无关；
- **SYS 效应 ≈ +6 ~ +12 条**（今日旧 40 vs 今日新 46~52，**两遍区间不重叠**）—— 真实提升。

**机制猜测（未验证，只作解释）**：旧 SYS 里那个不存在的键 `size` 让模型把注意力放在「怎么把这个键凑出来」，从而更容易选择「给一个 spec 试试」而不是「按规则追问」；改对后不再有这个诱因。**这只是解释，不是证据** —— 证据是上面那组对照。

### 4.3 glm 的 46/48 不是回归

glm 旧 49、新 46/48：同一 prompt 两遍就差 2 条，而且跨 prompt 有 **11/64 条判类翻转**（全是 wingbox 的澄清题，多出来的追问理由是「`n_stringers_per_skin=0` 与给定 `stringer_*` 矛盾」这种**内部一致性检查**，与 mesh 无关）。⇒ 49 落在 [46, 48] 的边缘，**这个差不可解读**。

## 5. 新发现：CONFLICT N-35（判分口径未适配新题型）

修 SYS 之后，L2 信息完备题的失败字段变成了另一类东西：

```
extra.split_tag / extra.v11_bracket / extra.v11_interior_holdout / extra.v11_template
extra.moment_axis / extra.shear_axis / extra.sweep_index
mesh.algorithm_2d / mesh.element_order / mesh.leading_edge_threshold / ...
```

根因：`EXEC_CONFIG_KEYS` 一个集合装了**两类来源不同的键**，而 `engineering_layer` 这个开关只能一起开关：

| 类 | 键 | L2 题面给了吗 | 该不该判 |
|---|---|---|---|
| 真实执行配置 | mesh 的 7 个（`algorithm_2d` 等） | 给了 | **该判**（逐字转写的考点） |
| 数据集构建元信息 | `split_tag`/`v11_*`/`sweep_index`/`shear_axis`/`moment_axis` | 给了 | **任何层都不该判**（`v11_bracket` 甚至是一句中文描述） |

`score_l2.py` 调判分器时不传 `engineering_layer` ⇒ 豁免在 L3 生效、在 L2 从不生效 ⇒ 这些键全部按 FAIL 计。

**三套口径重算**（旧口径混装 / B 只剥 extra 7 键 / A 剥 extra 7 + mesh 7 = **14** 键）：

| arm | 旧口径（HEAD） | **B（拍板项，已落地）** | A（连 mesh 考点一起丢） |
|---|---|---|---|
| glm 新 base | 8/16 | **13/16** | 15/16 |
| glm 新 strict 第 2 遍 | 14/16 | **15/16** | 16/16 |
| ds 新 strict 第 1 遍 | 10/16 | **14/16** | 14/16 |

**已拍板 B 并落地（2026-11-05）**：`evaluate.py` 拆出 `DATASET_META_KEYS`、`r32_audit.py` 同步、
`S-63` + `NC-84` 双向守。逐题实测见 `n35_key_split.json`（8 批次、等价差全 0、mesh 考点值 4 条）。

**边界（更正）**：本条**不影响任何已发布数字** —— L2 v7 的 64 条是澄清题、判分走 clarify 分支、
**根本不经过** `spec_fidelity`，实测两臂全流程对比 **46/64、52/64 逐题零差异**。
（旧稿此处写「剥离后 glm 49/64、ds 36/64 一个不差」是**自相矛盾的**：已发布值是 46/64 与 52/64，
且剥键对澄清题不可能有影响 —— 见 `CONFLICT.md` N-35 边界⑥。）影响面仅限尚未进卷的 `informative` 题型。

## 6. 边界与诚实说明

1. **headline 的卷是 v6c，不是 v7。** C-032/C-033 的 artifact 是 `baseline_scorecard_L3_v6c_p2.json` / `_v6c_ds_p2.json`（55 条）。v6c 与 v7 的 55 条 L3 逐字节相同，故 v6c 一代用「v7 候选按 v6c 卷重打分」得到，结果见 §3.2。
2. **ds 的单遍数字不得引用**（既有红线）。本轮给了两遍，跨度 6 条（L2 v7）到 1 条（L3），必须带区间。
3. **「旧 SYS 今日对照」只跑了一遍**（40/64），无法给区间；新 SYS 给了两遍。所以「+6 ~ +12」这个区间是按「旧值单点 vs 新值两遍」估的，**下界保守**。
4. **`description`/`name`/`analysis` 三段会随 prompt 变**，但它们不在 `GRADED_FIELDS` 里，不参与判分 —— 这正是 L3 判分段 58/64 相同、而整份 JSON 逐字节不同的原因。
5. **SYS 文本与 gold 的语义一致性没有可靠的机器判据**。试过「抽词元核 gold」，被「没有 size 这个键」这种否定句骗过（两个 arm 都判红）。⇒ 本轮**不加假闸**，改由**产物侧**的 `_l27c_check_mesh_keys.py` 间接守（判模型实际写了哪些键，不判 prompt 文本）。

## 7. 换代落地清单（谁被换掉了、谁没有）

### 7.1 换掉的 artifact

| 官方路径 | 新内容 | 旧内容归档到 |
|---|---|---|
| `reports/baseline_scorecard_L3_v6c_p2.json` | glm v2f 代（exam 23/25、SFR 20/22、MSR 41/51） | `reports/archive/baseline_scorecard_L3_v6c_p2__pre_sysfix.json` |
| `reports/bootstrap_ci_L3_v6c_p2.json` | 由新成绩单重算（TSR [80.0, 100.0] 等，逐数同旧） | （覆盖，旧值已在 git 历史） |
| `reports/baseline_scorecard_L3_v6c_ds_p2.json` | ds v2f 代（exam 22/25、SFR 20/23、MSR 19/22） | `reports/archive/baseline_scorecard_L3_v6c_ds_p2__pre_sysfix.json` |
| `reports/bootstrap_ci_L3_v6c_ds_p2.json` | 由新成绩单重算（SFR [69.6, 100.0]、MSR [72.7, 100.0]） | （覆盖） |
| `reports/l2_clarify_dual.json` + `.md` | 两模型 v2f 第 1 遍（glm 46/64、ds 52/64） | `reports/archive/l2_clarify_dual__pre_sysfix.json` + `.md` |
| `reports/w5d_leaderboard.json` + `.md` | 由新两份成绩单重算（2×2 不变；MSR 分母 22 vs 22 ⇒ 可减） | （覆盖） |
| `reports/diagnostics/model_diff_v6c_p2_glm_vs_ds.json` + `.md` | 由新两份成绩单重算 | （覆盖） |

**没有换的**：`baseline_scorecard_L3_v7_{glm,ds}.json`（C-040，v7 不是 headline 卷 ⇒ 只在 CLAIMS 里加换代说明、不换 artifact）；`trivial_baselines_L3_v6c.json`（地板与 prompt 无关）；考卷 `tasks_v6c.jsonl` / `tasks_v7.jsonl`（一个字节没动）。

### 7.2 每条 CLAIMS 改了哪些数字

| claim | 变 | 不变 |
|---|---|---|
| C-032 | `prompt_sha256`、候选目录、dev TSR 22→23 | exam TSR / SFR / MSR / CI（逐数相同） |
| C-033 | SFR 分母 21→23（pct 95.2→87.0）、三栏 11/13→10/13 与 5/6→6/6、MSR 20/21→19/22（full 42/50→41/51）、`n_solver_excluded` 0→1、`n_unresolved` 1→0、字段级命中率 90.94→95.02% | exam TSR 22/25（不变） |
| C-040 | 加「v2 代」标记 + v2f 重跑值（未入册） | 全部数字 |
| C-041 | 六个总数全变、prompt sha、候选目录；**新增「两遍区间重叠 ⇒ 不得排名」** | 掩码（64/45/19）、族级落盘结构 |
| C-034 | 三列方向由「相反」变「同向」，但并排要求不变 | 2×2 |

### 7.3 顺带修掉的一个闸 bug（S-42）

`check_claims.w5d_leaderboard_ok()` 里那条「MSR 行不得出现 Δ」**是无条件**的，而它的报错文字写的是「分母不等时禁止」。v2f 代分母变成 22 vs 22（`cfrp45s_d40` 进分母）⇒ Δ 合法、闸照红。

- **实现比说明严**这件事本身是老问题的新形态（同族于 N-34：闸的名义与闸的行为不是同一件事）；
- 修法：按 `msr_delta_allowed` 分支，且**允许 Δ 时双向核值**（md 里的 Δ 必须等于 json 的 `msr_delta_pp`，防手改）；
- 同时修了生成器的一处自相矛盾：`make_w5d_leaderboard.py` 的限制段是**硬编码**「分母 X vs Y ⇒ 不可直减」，而同一份 md 第 13 行已经印出 Δ ⇒ **一份 artifact 自己说两句话**。现在文案由 `msr_delta_allowed` 渲染。

## 8. 下一步（需要老王拍板的只有一件）

1. **N-35 的 A/B/C**（`EXEC_CONFIG_KEYS` 拆不拆）—— 推荐 B，理由与代价见 `CONFLICT.md`。
2. 其余按 `ROADMAP.md` §13 排序，本报告不动排序。
