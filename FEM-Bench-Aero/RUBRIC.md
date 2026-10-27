# RUBRIC.md — L3 判分口径预注册（W4e/W4f → W5a，专家第四/五轮 R18）

> **版本**：v5.4（2026-10-27 **T-A5「求解串行硬约束」**轮，新增 **R61**：`feagpt/solver.py` 的 `run()` 必须经过全局求解锁 `.solve.lock`——**并行跑 ccx/abaqus 会静默空转、返回码仍 0**，所以把「并行」做成不可能，而不是靠纪律；锁超 1 h 视为崩溃残留自动接管。新增 **S-47**（机制在场 + 无残留锁）/ **NC-52 两向**，负控 53→**54/54**、语义 47→**48**。同轮修掉 `check_forms.py` 的 `DEFAULT_REFERENCE` 陈旧路径（原先指向仓库里不存在的 `outputs_str/…` ⇒ T5 恒 FAIL、整份 check_forms VERDICT: FAIL）。v5.3 见下：
> v4.7（2026-10-25 W5c-6c 跨模型对比轮，新增红线 **R47–R49**（分母显式 / 不得事后择优 / 双尺度分裂必须标出）+ **§7.6**（含「跨模型对比作为归因工具」的判读表）；S-33/S-34/S-35 三条语义检查守住；`score_baseline.py` 修字段级命中率**静默排除编造题**的 bug（分母改显式分流 + `verdict_split` 自动落盘）。v4.6 见下：
> v4.6（2026-10-25 W5c-6b，新增红线 **R42–R46** 治理闸（headline 唯一 / 投影不冒充实测 / value_added 双尺度 / MSR 字段齐全 / key 决策留痕）+ **§7.5**；S-29/S-30/S-31 三条语义检查守住前三项；`value_added` 增字段级尺度与 T1+ 地板。v4.5 见下：v4.5（2026-10-25，W5c 新增红线 **R33–R41** + **§7.1 契约登记表** / **§7.2 死字段**（blade 剖面无缘条宽）/ **§7.3 数值角色**（R41）/ **§7.4 契约试建闸边界**（gold 也过闸）+ §1.1.1 改为 A/B/C/D 四类归因；R32 语义收口为「4 类 + 2 处局限」；三栏 exam 见 §1.1；变更记录见文末）。
> **纪律（R18）**：本文件冻结后，跑基线期间不得再改；每次改动必须新开版本号 + 记录原因。
> **post-hoc 声明**：W4d 版口径（EXEC_CONFIG_KEYS / METADATA_KEY_NAMES / bc_skip）是看过
> 30 条候选后调整的，属 **post-hoc**——其成绩（C-020，已 superseded）只能作开发参考；
> v2 口径冻结于 v4 重跑前（C-021）；v3 口径冻结于 v5 考卷重生成（W5b）之前。

## 1. 层次（红线 R15）

| 集合 | 定义 | 条数 | 用途 |
|---|---|---:|---|
| **exam（C-021 口径，v4 考卷 / 30 条 L3）** | `boundary_holdout + extrapolation_test` | **11**（boundary 4 + extrap 7） | **历史上唯一对外 headline**（C-021 = TSR 5/11）；**n=11 underpowered** |
| **exam（v6 的 boundary+extrap，55 条 L3 全量）** | `exam_stratum ∈ {boundary, extrapolation}` | **19**（boundary 6 + extrap 13） | **只报不判**（n=19 < 20，不满足 R12/R24） |
| **exam（v6 headline）** | `exam_stratum ∈ {boundary, extrapolation, interpolation}` | **25**（6 + 13 + 6） | **W5b 起的对外 headline**（见 §1.1；R12 分母 = 25） |
| dev | `train + val`（内插留出后） | 30 | 开发/诊断，不进对外 |

> **三个数不许混**（R30）：C-021 = **11**、v6 boundary+extrap = **19**、v6 headline 合并 = **25**。
> 任何「提升/下降」的对比必须同栏同口径；跨栏只能写「口径变了，不可直接比」。

### 1.1 三栏 exam（v6 预注册，2026-10-25 老王拍板）

- **为什么分三栏**：`interpolation_test`（训练包络内的点）明显比 boundary/extrap **更容易**，
  合并报会虚高；但只报 boundary+extrap 又永远只有 **19 条 < 20**，无法满足 R12/R24 的功效门槛
  （6 + 13 = 19 是数据集固定值，不随内插条数变化）⇒ 两者互斥，必须显式取舍。
- **拍板结论**：headline = **合并 25 条**（6 boundary + 13 extrapolation + 6 interpolation），
  **三栏明细必须并列给出**，并在任何对外引用处写明「与 C-021 的 **11 条**口径不可直接比较」（R30）。
- **R12/R24 的分母 = 合并 25**；分栏各自 n 太小（6/13/6）只报不判。
- `exam_stratum` 字段由 `make_nl_human.py --interp-quota` 写入考卷；`score_baseline.py`
  的 `is_exam` 判据 = `split_v2 ∈ exam_splits 或 exam_stratum 非空`（**向后兼容**：
  v4/v5 考卷没有该字段 ⇒ 行为与旧版完全一致，C-021 仍可复现）。
- 内插留出名额（**v6b 定案：全给翼盒 6 条**，`--interp-quota "wingbox:6"`），从 `train` 按 `task_id`
  字典序取前 N 条（**确定性选择，可复现**）。
- **为什么从「按族 2/2/1/1」改成「全翼盒 6」**（v6 → v6b，实测驱动）：
  ① L3 的 train 分布是 wingbox 15 / open_hole 2 / barrel 1 / panel 1，按 2/2/1/1 抽会把
     **barrel、open_hole、panel 三族的 train 抽空**（1→0、2→0、1→0）⇒ train 池只剩翼盒 13 条；
  ② 后果不是「dev 变小」而是**地板算不出来**：`trivial_baselines` 的 T0 众数池缺 3 族、
     T1 检索库只剩翼盒 ⇒ **T1 地板只有 1/4 族可算**，value_added 的对照项失真（T1 记 0 会让任何成绩都"有增量"）；
  ③ 而且 train 只有 1 条的族抽出来当「内插」**本身无意义**——1 个点没有包络可内插。
  ⇒ 改为全翼盒后：train 池 = 9/2/1/1、**4/4 族地板可算**；代价是 exam 族构成更偏翼盒（18/4/2/1）。
  v6 原始稿留档 `papers/tasks_v6.jsonl`，采用版 `papers/tasks_v6b.jsonl`（D10：改划分必须留档旧基线）。

#### 1.1.1 v6b 实测结果（W5b-4，C-028）：三栏**分栏差距巨大**，合并报确实会虚高

| 栏 | n | TSR | CI95（B=4000） | 读法 |
|---|---:|---|---|---|
| boundary | 6 | **5/6 (83.3%)** | [50.0, 100.0] | 分栏 n 小，只报不判（R12） |
| extrapolation | 13 | **7/13 (53.8%)** | [23.1, 76.9] | 最难的一栏，唯一低于合并值 |
| interpolation | 6 | **5/6 (83.3%)** | [50.0, 100.0] | 训练包络内，明显更容易 |
| **合并 headline** | **25** | **17/25 (68.0%)** | **[48.0, 84.0]** | n≥20 ⇒ `underpowered=False`，可判 |

- **实证了 §1.1 的担心**：若只报 boundary+extrap（19 条）会是 12/19 (63.2%)，加内插 6 条后升到 68.0%
  —— 内插确实把合并值抬了 **+4.8pp**。因此三栏并列不是形式要求，是独立信息。
- **★ 难度方向性偏差（必须在任何对外引用处声明）**：v6b 题面相对 v4 做了系统性消歧
  （**26/55 新增「坐标系」约定、25/55 新增显式载荷方向 `[x,y,z]`**，题面均长 161 → 206 字）。
  这是 W5b-3a 为通过语义完备性检查（NC-20/R21）而加的正确改动，但客观上降低了难度
  ⇒ **禁止把 68.0% 与 C-021 的 45.5% 相减表述为「提升」**（R30）。
- **★ 68.0% 是含已知缺陷的下界**（W5b-4 探针 + W5c-0 `r32_audit.py` 实证），8 条 exam 失败**须按四类分开归因，
  不能笼统说「没有一条是模型能力不足」**：

  | 类 | 条数 | 失败字段 | 性质 | W5c 处置 |
  |---|---:|---|---|---|
  | A 契约/键名 | 4（`open_hole_panel` 全族） | `params.hole_d`（4/4）+ `hole_x/hole_y`（2）+ `layup`（1）+ `material.ply_material` 自创键（1）+ `extra.end_tension` 自创键（2） | **harness 侧**：SYS prompt 从未列开孔板键名 | R34 键名表 + 禁用键（NC-31） |
  | B 题面缺依据（R32） | 2 exam / 4 全卷 | `airfoil.stringer_flange_width`（`str3_T`）、`airfoil.web_chordwise`（`web1_offcentre`；dev 的 `web1`/`web2` 同因） | **卷子侧**：gold 有值、题面无依据 | v6c 补题面（C-030），`r32_audit` 4 → 0 |
  | C 模型侧 | 1（`web1_offcentre`） | `extra.end_torque` / `extra.torque_axis_dof` 自创键 | **模型侧**：自创键（键名即契约，R19） | 只靠 R34 明示允许键收窄，不豁免 |
  | D 收敛性 | 1（`str3`） | 3 轮未收敛 | **生成器侧**（孤例） | 记录 `turns_histogram`/`n_unresolved`，不改判据 |

  A/C 在同一题上**有重叠**（`web1_offcentre` 既有 B 也有 C），所以「8 条里 6 条是系统性缺陷」的说法要精确到字段，
  不能按题计。诊断明细 `feagpt_repro/reports/diagnostics/w5b4_defect_analysis_v6b.md`（R37：官方文档不再引 `eval_runs/`）。

## 2. TSR（主 KPI，行为正确性）

- 完备题：`spec_fidelity` PASS ⇒ TSR PASS。
- 澄清题（`expected_clarifications` 非空）：
  - **字段级判据（R17）**：候选 clarify 文本必须命中 `clarify_aliases[field]` 中至少一个别名
    （正确键名或语义短语），**且不含** `clarify_wrong_keys` 中任何错族键名（键名即契约 R19）。
  - 单字关键词（'肋'/'孔'/'框'/'长桁'）**不得**作为通过依据（W4d 版已废弃）。
  - 静默编造 spec ⇒ TSR FAIL（FPR 编造）。
- 3 轮未收敛 / LLM 错误 ⇒ FAIL。

## 3. SFR（字段保真）

- 判层：**工程层**（L3 only）——`GRADED_FIELDS[family]` + material 必判三项 + mesh/load/extra
  gold 权威逐键。
- **R20**：`fabricated`（澄清题静默编造）⇒ SFR 一律 FAIL，与 TSR 编造口径一致。
- 执行配置键 `EXEC_CONFIG_KEYS`（REPORTED NOT GATED，填错单独报告）：
  - `mesh`: algorithm_2d, element_order, leading_edge_threshold, min_jacobian,
    recombination_algorithm, recombine, refine_at_leading_edge
  - `analysis`: incremental, initial_increment, outputs, step_type, total_time
  - `extra`: sweep_index, shear_axis, moment_axis（数据集内部编码键）
  - `load.direction` 且 `kind=pressure`（内压径向为数据集内部约定）
- **死字段豁免**：wingbox 且候选 `n_stringers_per_skin=0/缺` 时 `stringer_*` 四键不判。
- **builder-default 声明（R19）**：barrel 的 `stringer_height=25/stringer_thickness=2.5`、
  panel 的 `20/2.5` 为 builder dataclass 默认，gold params 不含这些键 ⇒ SFR 不判；
  考卷 v4 已在 NL 明示尺寸，模型显式写对/省略均可，**写 0 ⇒ builder 校验拒（真实错误）**。
- **bc 块**：pipeline 不消费 `spec.bc`（边界由各族 builder 代码决定），非翼盒族 gold bc 是
  死模板值 ⇒ bc 键值不判；但 **bc 自创键照罚**（模型写出 builder 不认识的键 = 编造）。
- **自创键白名单（收紧后）**：仅 `note / units / unit_system / description / *_units / *_note`；
  `type / element(s) / order / application / point` 等一律照罚（W4d 版白名单过宽，已收）。
- **material 块自创键**（ply_material 等）照罚。

## 4. MSR（全链可用率，R14/R16）

- 全链 = 契约闸（含 FEASpec 试建）+ ccx 求解 + 关1 网格 + 关4 语义 + fidelity + spec_fidelity。
- **依赖预检（R16）**：gmsh/numpy 缺失 ⇒ 环境错误退出，绝不记候选 FAIL。
- **分母（R23，v3 修订）**：按**任务属性**排除——`expected_clarifications` 非空的澄清题与
  无 spec 产出的未收敛候选一律不计分母，**无论澄清题是否被模型静默编造出 spec**
  （编造已由 FPR 单独计数，双重计数违反 R23）。v2 文字「编造被拒候选不计」按此执行。
- 失败分层 `env / contract / model / solver`；env 单独计数，不进 MSR。
- 汇总：`exam.msr` / `dev.msr` / `by_split` 落盘成绩单（P1-1/P1-2，不再手算；NC-22 检查）。
- **★ solver 单列（R35，v4.5 修）**：solver/算力失败（OOM、超本机内存阈值）**记 `compute_bound`，
  不计模型能力失败**，但**只许单列、不许静默删除**。成绩单必须给齐四行 ——
  `exam_msr` / `exam_msr_excl_solver` / `dev_msr` / `dev_msr_excl_solver`，加全链
  `msr` / `msr_excl_solver`，并标 `solver_in_exam` / `solver_in_dev` 归属。
  **原始口径（含 solver）与剔除口径必须并列**：求解失败对模型确实是失败，剔掉是「能力上限口径」，
  只留一个都会被误读。
  **★ 且 solver 桶是「候选相关」的，不是题目固有属性**：同一题 `barrel_d2000_l2000_str12_frm4`
  在 v6b 旧候选 4.2 s 就被 pipeline 拒（`class=model`），换 v6c 新候选后算到 169,606 节点才撞
  158,548 阈值（`class=solver`）。⇒ **「剔除 solver 后的分母/得分」同样不可跨版本直减**
  （R30/R39 的不可比判定一并适用于剔除口径）。
  *（v4.5 之前的实现缺陷：`msr_l3.py` 注释写「exam MSR 不含 solver」而代码里 `exam_msr` **含**
  solver —— 属于「注释与实现口径相反」，数字本身没错，但会让复核者按注释读出错误结论。）*
- 解释器：`C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe`（gmsh 在 venv）。

## 5. value_added

- `exam` TSR_LLM − `exam` TSR_T1（同任务集 exam 口径，**不用 all_pct**）。
- `n_exam < 20` ⇒ `underpowered=true`，**不得判 PASS**（R12/R24）。

## 6. 负控

- 每次改判分/考卷必跑负控套件（R5/R6）；未全绿不得跑基线。
- 套件 = **44 条**：`PC-1` + `NC-1..22`（W4d 15 / W4e NC-15..19 / W5a NC-20 载荷方向完备、
  NC-21 MSR 分母、NC-22 exam.msr）+ **`NC-15b`**（澄清双向探针，W4e）+ **`NC-23..26`**
  （W5a' artifact 入库 / git 追踪 / 官方·诊断分文件 / **NC-26 缺 gold 数据集必须硬报错**）
  + **`NC-27..29`**（W5b-3：**NC-27** 文本计数漂移必须被语义检查抓到、**NC-28** 候选未覆盖全卷必须标记、**NC-29** 跨口径混比必须拒绝）。
- **计数口径（P1-2/P1-3 修正）**：旧文写「PC-1 + NC-1..22」= 23 是**漏计 NC-15b** 的错账；
  实际为 24（W5a 时）／28（W5a' 收口）／**31**（W5b-3：再补 NC-27..29）／**39**（W5c：再补 NC-30..37）／**41**（W5c-6b：再补 **NC-38** headline 唯一反向、**NC-39** T1+ 地板反向）／**44**（W5c-6c：再补 **NC-40** 分母不闭合、**NC-41** 第二模型抢 headline、**NC-42** 双尺度分裂被隐藏）。**报负控必须报总数 + 编号集合**，只报「全绿」不算。
- 产物：`reports/negative_controls_54.json`（入库，R25；`_53` 为上一代；`_51`/`_50`/`_49`/`_48`/`_47`/`_44`/`_41`/`_39`/`_37`/`_31` 已移入 `reports/archive/`）；`negative_controls.py` 读最新成绩单，
  缺成绩单时相关条目显式记 `skip` 而不是静默消失（W5a 教训：NC-15 曾因澄清题迁移而无声消失）。
- **NC-19 判据已随 v6b 三栏同步（W5b-4）**：原判据「exam 集的 split_v2 必须 ∈ 留出集」
  在 v6b 下**假红**——内插题按设计就是从 `train` 留出的（`split_v2` 仍 `train`、
  `exam_stratum='interpolation'`，见 §1.1）。新不变式：exam 行要么 split 属留出集，
  要么（`split=train` 且 `stratum=interpolation`，**记账为「内插豁免 N」**）；其余组合一律 BAD。
  **核心「不得混入未留出的 train」未放宽**，并已做反向验证（伪造一条 `split=train, stratum=None`
  的 exam 行 ⇒ NC-19 立即 BAD）。

## 7. 任务构建期检查（R21 + R32，W5b-4 扩充）

- L3 任务 NL 必须给**坐标系约定 + 载荷方向**（向量或明确轴向文字），禁止「法向」类未定义裸词。
- `tasks.jsonl` 每条 L3 行带 `coordinate_convention` 字段；NC-20 构建期检查。
- **★ R32（W5b-4 新增）：gold 的每个判分字段都必须能从 NL 推出。**
  对 `GRADED_FIELDS[family]` 中在 gold 有非空值的字段，NL 必须给出依据，**或**该字段显式登记为
  「按族默认值」（进默认值表 / `EXEC_CONFIG_KEYS`）。否则该任务是**不可解题**，不得进 exam。
  - 实证来源：`airfoil.stringer_flange_width` 在 gold 有值，题面只写「blade 长桁（高 20 mm、厚 2.5 mm）」，
    模型按系统提示「用户没给的尺寸不得编造」正确省略 ⇒ 被判 `spec_fail`。这不是模型错，是**卷子错**。
  - R21 只覆盖了「载荷方向完备」（NC-20），**未覆盖本类**；R32 是它的补集。
  - **已脚本化（W5c-0）**：`r32_audit.py` 逐 family 遍历 `GRADED_FIELDS` + `mesh/load/bc/analysis/extra`，
    对每个判分字段给出 `derivable_nl` / `derivable_contract`（题面没写但契约唯一确定：材料卡、词汇表、族默认）/
    `exempt:{dead|exec_config|default|clarify|bc_skip}` / **VIOLATION**。有 1 条 VIOLATION ⇒ 不得冻结考卷（**R33**）。
    局限（写在脚本 docstring 里）：数值判据是「题面出现过该数（含单位换算）」，**必要不充分**，是筛查器不是证明器。
  - **实测（W5b-4 卷）**：v6b 上 4 处 VIOLATION —— `str3_T` 缺缘条宽 + **3 条 web 任务题面完全没提中间腹板**
    （旧 `make_nl_human` 从 `structure.params` 取 `n_web/web_pos`，而 gold 的腹板在 `airfoil.web_chordwise`，
    params 是空的 ⇒ 永远取不到）。v6c 修复后 **0 违规**（1812 个判分字段全部分类）。

### 7.1 契约登记表（题面不写也算可推的四种情形，W5c-1）

| 类别 | 内容 | 判据 |
|---|---|---|
| 材料卡 | `Aluminium 2024-T3` ⇒ E=73100 MPa / ν=0.33 / ρ=2.78e-9 / 屈服 345 | 题面只写「铝 2024-T3」即可 |
| 词汇表 | 面内拉伸（端部均布）/ 翼尖集中力 ⇒ `load.kind="tip_force"`；内压/均压 ⇒ `"pressure"`；翼型 `code="4412"`（不是 "NACA4412"）；bc ⇒ `{"root_surface":"root","clamp":true}` | SYS prompt「词汇约定」段 + NC-31 咬键名 |
| 族默认 | 无锥度 ⇒ `tip_chord_ratio=1.0`；无后掠 ⇒ `sweep_deg=0`；无中间腹板 ⇒ `web_chordwise=[]`；无长桁 ⇒ `n_stringers(_per_skin)=0` | 题面无触发词 |
| 执行配置 | `EXEC_CONFIG_KEYS`（网格算法/分析步/内部编码轴向） = REPORTED NOT GATED | 只报不判 |

### 7.2 死字段（W5c 新增一条）

- 无长桁（`n_stringers_per_skin=0`）时的 `stringer_*`：模板默认值，不可知 ⇒ 不判（沿用 W4d）。
- **`blade` 剖面的 `stringer_flange_width`：不判。** 依据不是"模型没写就放过"，而是物理 + 代码：
  `feagpt/sections.py::tee` 在 `flange_width<=0` 时**直接返回 `blade()`**，`geometry.py` 对 blade 只挤出单条竖板，
  flange 完全不参与建模；`check_forms` T5 反向证明 `blade ≡ T(flange=0)`；gold 34 条翼盒该值**全部是模板默认 30.0**。
  判定用 **gold 的 `stringer_kind`**（不用候选的——否则模型写 `kind="blade"` 就能顺手豁免缘条宽）。
  `T` 剖面缘条宽是**真实几何**，必须在题面给出（v6c 的 `str3_T` 已补「缘条宽 30 mm」）。

### 7.3 数值角色（R41，W5c 重打分轮新增）

- **问题**：`length`/`width` 同时判分且值不等时，题面若只写「800 × 600 mm」，两个数**都出现过**（`num_derivable` 判定为 `derivable_nl`），
  但「哪个是 length」**不可判**。模型按工程惯例「长 × 宽」读，若模板写的是 `{width} × {length}`，就会被判错——**错在卷子，不在模型**。
- **实证**：`stiffened_panel_800x600` / `_str3` 旧模板 `f"{width} × {length}"` ⇒ 题面「600 × 800」，gold 是 `length=800, width=600`；
  v6c 的候选把 `length` 写成 600、`width` 写成 800，被判 `params.length/width` 失败（**2 条 dev，0 条 exam**）。
  同类任务里 11 条开孔板恰好是 `length` 在前，所以没暴露——**这不是「已修」，是「恰好没踩」**，故必须升为红线。
- **判据**：审计对 `params.length`/`params.width` 这一对，若两值不等，则要求
  ①题面显式含「长度/宽度」标记，**或** ②两个数在题面里的先后顺序为 `length → width`。都不满足 ⇒ `VIOLATION`。
- **修法**：模板一律显式标注角色（`长度 X mm × 宽度 Y mm（length × width）`），不靠顺序隐含。
- **成本口径**：v6c 已冻结、候选已生成，**不为此重跑**（exam 收益 0，重生成 3 h+）；作为 dev 侧**已知下界**登记在 C-030。
  下一版卷子（若开 v6d）修模板后重生成即可回收 2 条 dev。

### 7.4 契约试建闸（R19）的边界与「gold 也过同一闸」（W5c）

- **它是干什么的**：`FEASpec.from_dict()` 在进求解器之前构造一遍，抓 **未知键（TypeError）** 与 **族/取值非法（ValueError）**。
  失败即 `failure_class=contract`，不浪费求解时间。
- **它不管什么**（实测边界，**别误当 schema required 校验**）：删掉 `material.youngs_modulus` 仍能构造成功。
  缺字段由 `spec_fidelity`（SFR）抓，不靠试建闸。因此「contract PASS」≠「spec 完整」。
- **★ gold 也要过同一闸**（专家第八轮 §3.2 点名的疑问）：C-028 有 3 条 exam 任务 **TSR PASS + SFR PASS 但 MSR contract 失败**，
  只看候选分不清「模型参数错」还是「builder 不支持这个合法组合」。`audit_contract.py` 把 **gold spec** 过同一道闸：

  | 结果 | 判定 |
  |---|---|
  | gold 能建、候选不能建 | **模型 spec 质量问题**（判 model，合理） |
  | gold 也不能建 | **任务/契约缺陷（harness）**，不得计入模型能力，须修 builder 或改卷子 |

- **v6c 实测**：**55/55 gold 全部可建**（`reports/contract_audit_v6c.json`，rc=0）⇒ 那 3 条 contract 失败一律判 model，
  **不是 harness 背锅**。负控 **NC-37** 做反向验证（给 gold 注入 `material.ply_material` ⇒ 必须 rc=1）。

### 7.5 治理闸（R42–R46，W5c-6b 新增）

> 这五条不判模型对不对，判**账本与产物自相矛盾**。四条已有机器闸，R46 只能靠留痕。

| 红线 | 一句话 | 机器闸 | 为什么必须有（实证） |
|---|---|---|---|
| **R42** headline 唯一 | 恰好一条 active claim 的状态列带「（对外 headline）」 | **S-29** | W5c 收口后 README 仍写 C-028 68.0%、C-021/C-025/C-026 各自自称 headline，而 29 项语义检查**没有一条**检查唯一性 ⇒ 22 条 active 全过却互相矛盾 |
| **R43** 投影不冒充实测 | 「可达/paper-clean」必须与实测并列并标投影 | **S-30** | C-029 曾写 dev「真实可达 25/30」，实际 7 条 dev spec_fail 中 **5 条是模型侧**，修卷子只能回收 2 条 |
| **R44** value_added 双尺度 | 任务级 + **字段级**；T1+ 非空 | `trivial_baselines.py` 的 `T1plus_family` / `n_fail_exam` | 三个地板在 exam 上全是 0 ⇒ Δ92pp 对 0 地板，技术上 PASS、科学上不硬；字段级尺度才有区分度（85.93% → 99.34%） |
| **R45** MSR 字段齐全 | 九字段非空，别名由同一变量写出 | **S-31** | `msr_excl_solver` 有数、`full_msr_excl_solver`/`dev_msr_pct` 是**缺键** ⇒ 复核者只能手算，手算就会漂 |
| **R46** key 决策留痕 | 轮换/重建/endpoint/provenance 四项分开评估并记录 | 无（靠 `W5B_PLAN` §6.0b 留痕） | 「轮换 ⇒ provenance 重签 ⇒ 代价高」经复核**错两处**：endpoint 是硬编码常量、provenance 不记 key/endpoint |

**★ R42 的判据形态本身是个坑**：第一版用「正文含『对外 headline』且不含否定词」判，结果 C-029
自己写了「不是实测 / 不是又一个下界」**被自己的否定词过滤掉**（FAKE FAIL）；C-028 的状态列里
写了指针「对外 headline = C-029」又被当成第二个 headline（FAKE PASS 反向）。⇒ **判据要用结构化字段，
不要用自然语言表述**。

### 7.6 跨模型对比：三条闸 + 它作为「归因工具」的用法（R47–R49，W5c-6c 新增）

> 同一张卷跑第二个模型（C-031 `deepseek-v4-pro` vs C-029 `glm-5.3-flash`）暴露了三个口径问题，
> 也顺带证明了跨模型对比最大的价值**不在排名，而在归因**。

| 红线 | 一句话 | 机器闸 | 实证 |
|---|---|---|---|
| **R47** 分母必须显式落盘 | 命中率分母禁止 `if 值存在` 隐式过滤；`n_counted + n_excluded == n_exam` 必须闭合 | **S-33** | C-031 的 3 条 `fabricated` 被静默跳过 ⇒ 算出与 C-029 **一字不差**的 99.34%（87.42% 才对）。同数字、反含意 |
| **R48** 不得事后择优 | headline 开跑前定死；新模型只能并列报 + 标 supporting | **S-34** | 同卷试 N 个模型取最好 = 事后挑样本，与预注册原则冲突 |
| **R49** 分裂必须标出 | 任务级 PASS / 字段级 BELOW（或反之）⇒ 成绩单写 `verdict_split`，文档并列引两侧 | **S-35** | C-031 任务级 Δ80 pp PASS、字段级 Δ**+1.5** pp BELOW |

**★ 跨模型对比是判定「缺陷归谁」的最强工具**（方法论，比分数重要）：

| 观测 | 归因 | 处置 |
|---|---|---|
| 同题、**同失败字段**在两个模型上复现 | **A/B 类**：题面或 prompt 诱导，不是模型个性 | 修 prompt / 修题面 |
| 只有某模型错、另一模型对 | **C 类**：模型能力或指令遵循 | 记为该模型局限，不改卷子 |
| 两模型 `spec_pass` 条数相同、只在某一条腿（澄清/编造）上分叉 | 任务是**可解的**，差距来自「守不守规则」 | 归因到指令遵循，别吹建模能力 |

**实证（C-031）**：两模型 `spec_pass` 都是 **20/25**；两条 `spec_fail` **同题同字段**
（`web1_offcentre` 自创 `extra.end_torque`+`torque_axis_dof`、`cfrp45s_d40` 的 `layup` 标量）
⇒ 这两处是 **prompt 约束仍不够强**，不是"模型太笨"；唯一实质差异是 3 条澄清题
（glm 澄清 3/3、dsv4pro 编造 3/3）。其中 `stiffened_panel_600x600_str3` 的 `n_stringers`
**直接由 SYS prompt 的「未提长桁→长桁数=0」授权** ⇒ 与题面的 `expected_clarifications` 打架，
属**我方 prompt 内部矛盾**，下一轮必修。

### 7.7 生成端 + 产物端：四条闸（R50–R53，W5c-6d/6f/6g 新增）

> §7.5/§7.6 守的是**账本**（文档是否自相矛盾、分母是否闭环）；本节守的是**输入端**——
> prompt 有没有偷偷给答案，以及「改了 harness 之后有没有把被比较的对象全部重跑」。
> 起因：第十轮复评把 C-031 的三个缺口定性为「prompt 授权 + 模型标签 + 分母混类」，
> 三条都不是模型能力问题，而是**我方产物与 harness 的问题**。

| 红线 | 一句话 | 机器闸 | 反面实证 |
|---|---|---|---|
| **R50** prompt 不得盲填、不得泄题 | ① 题面**提到**某特征却没给数量 ⇒ 必须澄清，prompt 不得授权默认值；② prompt **不得**注入 `expected_clarifications`（等于把判据给模型） | **S-38** / **NC-45** | 旧 prompt「未提长桁→长桁数=0」× 题面「若干根长桁」+ 登记 `expected_clarifications=['n_stringers']` ⇒ 自相矛盾。deepseek 被诱导、glm 没被诱导 ⇒ **不能记成模型错** |
| **R51** 模型标签必须是实测值 | 成绩单顶层 `model` == `provenance.model`，两者都读自**候选文件里生成时 pin 的 id**；禁止默认值、禁止命令行声称覆盖 | **S-36** / **NC-43** | C-031（deepseek-v4-pro）顶层 `model` 写着 `glm-5.3-flash` —— 36 项语义检查里**没有一条**核对它 |
| **R52** 分母四类拆开 + 两层闭合 | 层A（准入）：`n_counted + clarify + unresolved + notrun + env + unknown = n_tasks_total`；层B（原始分母内部）：`n_counted = n_solver_excluded + n_counted_excl_solver`。`n_clarify_excluded` **只含** `expected_clarifications` 题 | **S-37** / **NC-44** | C-031 `n_clarify_excluded=5` = 4 条澄清 + 1 条 `cfrp090s` 无输出；C-029 的 4 是 4 条纯澄清 ⇒ **两个数不同类**，并排放就被读成同口径 |
| **R53** harness 变了必须全量重跑 | 改 prompt / 改 decode / 改预算后，**所有被比较的模型都要重新生成**；禁止用「A 模型旧 prompt × B 模型新 prompt」的成绩做对比 | 人工 + `provenance.model` / `tasks_sha256` / `prompt_sha256` 三件对齐 | C-029（旧 prompt）与 C-032（新 prompt）**不可并列**；同理 C-031 不能再与 C-032 拼成「模型对比」 |
| **R54** MSR 是条件通过率，比之前先对齐分母与 SFR | MSR 分母只含「产出 spec 且非 `expected_clarifications` 的题」；`msr_definition` 与 `n_no_spec_excluded_ids` 必须写进成绩单（**不得只把分母改小**）；跨成绩单比 MSR 前先对齐分母，**分母不同时 pct 不得直减、不得据此排名** | **S-40** / **NC-46** | C-033 exam MSR 95.2% > C-032 的 90.9%，但 TSR 低 4 pp——C-033 分母 **21**（排除 `cfrp45s_d40` 无输出），C-032 是 **22**，**被排除的恰好是失败题 ⇒ 分母小的 pct 更好看**（与 C-031「MSR 反直觉」同源，这次发生在 MSR 内部） |
| **R55** prompt 修复必须做逐题回归 | prompt 版本变更后必须对比新旧 `per_task`；**「exam 不变但 dev 变」的反向变化必须逐题定位并写进 claim**，且给出闭合断言（旧通过 + fail→pass − pass→fail == 新通过）。**净额相同也可能是成对抵消** | **S-41** / **NC-47** | C-032 的 dev −1 实为 **+1 / −2**：`stiffened_800x600_str3` 由 `600/800`（读反）纠正为 `800/600`（题面 R41 修正被兑现）；两条柱壳 `extra.end_moment` = `5e4` 与 `5e6` 而 gold `5e7`（×10⁻³ / ×10⁻¹ 量级偏差，与 prompt 无关） |
| **R56** 跨模型榜单必须三列并排 | 任务级 TSR / 字段级命中率 / 失败分层（model·solver·contract·unresolved）**缺一不可**；MSR 分母不等时**不出 Δ、不得据此排名**；表必须带「能说什么/不能说什么」与限制段 | **S-42** / **NC-47** | 同一对模型 TSR 92>88、字段级 PASS>BELOW，而**条件 MSR 90.9<95.2**（分母 22 vs 21，被排除的是失败题）⇒ 只引一列可得出任意结论（C-034 / `make_w5d_leaderboard.py`） |
| **R57** prompt v3 仍不得注入 `expected_clarifications` | ①**不得**注入 `expected_clarifications`；②**不得**靠改 `clarify_wrong_keys` 元数据把 FAIL 变 PASS（那等于事后改判分）；③**prompt 每次变更都必须做消融并落档；净收益 ≤ 0 一律否决，否决后 sha 必须回到基线** | **S-38** / **S-43** / **NC-45** / **NC-48** | C-033 剩余 1 编造 + 1 问错字段；v3/v3b 两版实测**零收益 + 失败点迁移**（glm 3/3/3、deepseek 2/2/2）⇒ 否决、回退 v2（C-035） |
| **R58** 官方文档必须被 gate 读 | 被 §0 指定为「开工必读」的**数据类** SOT（CLAIMS / RUBRIC / `reports/INDEX.md` / 当前成绩单）**必须至少被一条语义检查实读**；`AGENTS.md`/`CLAUDE.md` 属协议文本、由 §7 声明兜底，不在本闸范围；没有闸读它的文件视为未校验，不得当作 SOT | **S-44** / **NC-49** | S-00..S-43 共 44 项里**没有一条读 INDEX.md**（grep = 0），于是 INDEX §2 写「⓪ 当前官方 headline（C-029）」、§1 写（C-032），两处并存；agent 照 INDEX 重跑 v1 代基线**不会报错**（两代 exam 同为 23/25） |
| **R59** 收口顺序固定：负控 → check_claims | 官方 `reports/check_claims.json` 必须在 `negative_controls_<N>.json` **之后**写；判据：C-019 记录的 artifact `mtime` == 实际 mtime，且 check_claims.json 的文件 mtime ≥ 负控 json 的 mtime | **S-45** / **NC-50** | 第十二轮 §3.4 实测 check 22:18:28 早于负控 22:19:45，C-019 记录 mtime 差 103 s——**内容与 sha 全对、只有元数据过期**，人工比对才抓到 |
| **R60** dataset/求解类脚本必须用项目 venv | `verify_dataset`/`check_forms`/`score_baseline`/`msr_l3`/`eval_dataset`/`dedup_dataset`/`run_pipeline` 一律用 `…/envs/default/Scripts/python.exe`；缺 numpy/gmsh = **环境问题**，不得记数据失败（R16） | **S-46** / **NC-51** | 第十二轮 §3.5：系统 python 跑 `verify_dataset` 直接 `No module named numpy`，换 venv 才打出 `55 paired + 9 modeling-only` |
| **R61** ccx/abaqus 绝不并行（硬约束） | `solver.run()` 必须经过全局求解锁 `feagpt_repro/.solve.lock`；第二个求解直接抛错；锁超 1 h 视为崩溃残留、自动接管 | **S-47** / **NC-52** | 并行两个 ccx 会**静默空转、返回码仍 0**（结果为空），「返回 0 就算成功」会把它当成功；本仓库踩过两次（`check_forms` 未停就起柱壳 ccx；第十二轮 §3.2） |

**★ R52 的层次修正（本轮实测后改写，专家原稿把两层混写）**：
专家第十轮原文写 `n_counted + n_clarify_excluded + n_unresolved_excluded + n_solver_excluded = n_exam`，
这会把 solver 失败**加两次**——solver 失败在**原始口径下是计入分母的**（对模型确实是失败），
只是在「剔除 solver 口径」里被拿掉。若照原式实现，C-029 会算出 `51 + 4 + 0 + 4 = 59 ≠ 55`。
⇒ 拆成层A（准入排除）与层B（原始分母内部剔除）两条闭合，各自独立断言，实现见 `msr_l3.py::_denom_audit`。

**★ R50 的边界（**没有**采纳「把 `expected_clarifications` 传给生成器」这条建议）**：
第十轮建议里给了「或把 expected_clarifications 直接传给生成器，让模型知道这些字段该问」这个选项。
**否决**：`expected_clarifications` 就是该维度的判据本身，传给生成器等于在 holdout 上泄题，
会把这个维度变成「照着答案念」。改法是**在 prompt 里写通用规则**（题面提了特征却没给数量 ⇒ 必须澄清），
让模型自己判断哪条题触发，规则对全部任务一视同仁。

## 8. 产物纪律（W5a'，R25/R26/R27/R28）

- **官方 artifact 唯一出处 = `feagpt_repro/reports/`**（入库）；`eval_runs/` 是被 gitignore 的
  工作目录，任何写在这里的「官方数字」都不可复现，且重跑即覆盖（C-021 的 v4 成绩单曾因此被 v5 覆盖）。
- 文件名必须带版本：成绩单 `baseline_scorecard_L3_v4.json`（官方）/ `..._v5_rescore.json`（诊断）；
  考卷快照 `papers/tasks_v4.jsonl`、`papers/tasks_v5.jsonl`（+ `SHA256SUMS`）。
- 生成成绩单时脚本自动写入 `provenance`（考卷路径 + sha256 + 候选目录），
  复现时用它对齐「这份数字当时用的是哪张卷子」。
- `python check_claims.py` 每条 active CLAIM 检查：存在 → git 追踪 → 不在 `eval_runs/` →
  与 command 的 `--report/--json` 路径一致 → 同路径不被两条 claim 占用；记录 sha256/mtime。
- 诊断结果（旧候选 × 新考卷）**不得**占用官方路径，且必须在 `reports/INDEX.md` 标 diagnostic。

## 9. 版本记录

| 版本 | 时间 | 变更 | 原因 |
|---|---|---|---|
| v1（post-hoc） | 2026-10-25 W4d | 初版（工程层口径） | 看过 30 条候选后调整 |
| v2 | 2026-10-25 W4e/f | exam/dev 分栏 + 澄清字段级 + SFR 编造对齐 + 试建闸 | 专家第四轮 R15-R20 |
| v3 | 2026-10-25 W5a | MSR 分母按任务属性排除（R23）+ R21 任务构建期方向检查 + NC-20..22 + exam.msr/dev.msr 汇总 | 专家第五轮 P0-1/P0-3/P1-1/P1-2；考卷 v5（坐标系写死 + panel 澄清题迁移 str3） |
| **v3.1** | 2026-10-25 W5a' | **仅文档/计数/产物纪律**：负控计数 23→24→**28**（补 NC-15b、NC-23..26）+ 新增 §8 产物纪律；**判分口径零改动** | 专家第六轮 P1-2（RUBRIC 说 NC-1..22 = 23，实为 24）+ R25–R28。**不触发重跑**（口径未变，C-021 仍有效） |
| **v4** | 2026-10-25 W5b | **§1.1 三栏 exam 预注册**：headline = 合并 25（boundary 6 + extrap 13 + interp 6）、三栏明细并列、R12 分母 = 25；新增 `exam_stratum` 字段约定；**判分细则未动** | 老王拍板「扩卷路径 A + headline 全 exam 25」；发现「headline=boundary+extrap 恒为 19」与 R12 的 n≥20 互斥，必须显式取舍 |
| **v4.1** | 2026-10-25 W5b-3 | **仍无判分口径改动**：§1 表拆成 11 / 19 / 25 三行；§6 负控 28→**31**（NC-27..29）；新增 R29 语义计数 / R30 跨口径不可比 / R31 生成前预检。**C-021 与 C-027 均不需重跑** | 专家第七轮 P1-1..P1-6（5 处语义计数漂移 + `check_claims` 只做结构检查抓不到） |
| **v4.2** | 2026-10-25 W5b-3b | §1.1 内插名额由「按族 2/2/1/1」改为「全翼盒 6」（v6 → v6b）：原名额把 barrel/open_hole/panel 三族 train 抽空 ⇒ T1 地板只有 1/4 族可算。**exam 仍 25、判分口径零改动** | 老王拍板 A；实测 `_probe_interp_w5b3b.py` + `trivial_baselines` v6b（T1 0/25、四族齐全） |
| **v4.3** | 2026-10-25 W5b-4 | ①新增红线 **R32**（考卷构建期必须断言 gold 的每个判分字段都能从 NL 推出，否则属不可解题、不得进 exam）；②新增 §1.1.1 登记 v6b 实测三栏（boundary 5/6、extrap 7/13、interp 5/6）+ 难度方向性偏差声明；③**判分细则仍零改动** | W5b-4 探针实证：`stringer_flange_width` gold 有值但题面未给 ⇒ 模型无解却被判 fail（2 条 exam）；`open_hole_panel` 4/4 全败于 prompt 未给键名 |
| **v4.4** | 2026-10-25 W5c 修复轮 | R33–R40 八条新红线；§7 契约登记表 + §7.2 死字段（`blade` 无缘条宽）；§1.1.1 归因细化（A/C 混合，web1_offcentre 补列）；负控 31 → **39**（NC-30..37）；语义检查 21 → **29** 项（S-21..S-28 + 复活的 S-19/S-20 由「静默消失」改为响亮失败） | 第八轮复评 24/30；`r32_audit.py` 4→0 违规、T1 leave-one-out（train 12/13 全是自命中）、成绩单文案由考卷生成 |
| **v5.4** | 2026-10-27 T-A5 | 新增 **R61**（求解串行硬约束：`solver.run()` 加全局锁 `.solve.lock`；超 1 h 自动接管）；**S-47**（机制在场 + 无残留锁）/ **NC-52 两向**；负控 53→**54**、语义 47→**48**；修 `check_forms.py` `DEFAULT_REFERENCE`（`outputs_str/…` 不存在 ⇒ T5 恒 FAIL）并让 `_reference_spec` 同时认 `<dir>/spec.json`；旧负控 `_51` 归档 |
| **v5.3** | 2026-10-27 T-A4 | 新增 **R59**（收口顺序固定）/ **R60**（dataset 用 venv）；**S-45**（C-019 记录 mtime == 实际 + 文件时间顺序）/ **S-46**（INDEX bash 块 `PY=` 指向 venv、dataset 调用走 `$PY`）/ **NC-50 两向** / **NC-51 两向**；负控 51→**53**、语义 45→**47**；**F-1**：负控内容不变不重写 json；旧负控 `_50` 归档 |
| **v5.2** | 2026-10-27 T-A3 | 新增 **R58**（官方导航必须被 gate 读）；**S-44**（INDEX 的 headline 指向唯一 + 负控编号/总数与最新 `negative_controls_<N>.json` 实读对齐，均只认结构化记号）/ **NC-49 四向**（⓪ 段指回 C-029 / NC 区间回退 / 去掉历史标记 / 锚点缺失）；负控 50→**51**；语义项 44→**45**；`check_claims.py` 增 `index_consistency` / `_latest_nc_json`；旧负控 `_48`、`_49` 归档 |
| **v5.1** | 2026-10-27 W5d-1 | **R57 扩写**（prompt 变更必须消融留档、净收益 ≤0 否决、否决后 sha 回基线）；**S-43**（消融结论 vs 当前 prompt sha 必须一致）/ **NC-48**（采纳但未换 / 采纳且已换合法 / 缺 decision）；负控 49→**50**；新产物 `diagnostics/prompt_v3_ablation.{json,md}`（C-035）+ `_diag_prompt_ablation.py`；旧负控 `_49` 归档 |
| **v5.0** | 2026-10-27 W5d | 新增 **R55**（prompt 修复逐题回归 + 闭合断言）/ **R56**（榜单三列并排、分母不等不出 Δ）/ **R57**（prompt v3 不得注入 `expected_clarifications`）；**S-41**（dev 反向必须定位且 CLAIMS 引用）/ **S-42**（三列齐 + `msr_delta_allowed` 必须由分母算）；**NC-47**（四向变异）；负控 48→**49**；新产物 `w5d_leaderboard.{json,md}`（C-034）与 `diagnostics/dev_reversal_v6c_p2.{json,md}`；`_diag_dev_reversal.py`（新）/ `make_w5d_leaderboard.py`（新）；旧负控 `{31,37,39,41,44,47}` 归档到 `reports/archive/` |
| **v4.9** | 2026-10-26 W5c-6h | 新增 **R54**（MSR 条件通过率：口径落盘 + 排除项点名 + 分母不同禁止直减/排名）；**S-40** / **NC-46**（三向变异：删口径 / 只改小分母不点名 / 点名清空）；负控 47→**48**；`msr_l3.py` 增 `msr_definition` 与 `n_no_spec_excluded_ids` 并在打印时提示条件分母；`_diag_model_diff.py` 增「§0 MSR 口径对齐」段，分母不等时明确写「不出 Δ」；`compare_scorecards.comparability` 放行**自比**（R53 误伤，NC-29/NC-35 曾因此转红） |
| **v4.8** | 2026-10-26 W5c-6d/6f/6g | 新增 **R50**（prompt 不得盲填、不得注入 `expected_clarifications`）/ **R51**（顶层 `model` == `provenance.model`，读实测值）/ **R52**（MSR 分母四类拆开 + 两层闭合，**修正专家原稿把 solver 加两次的写法**）/ **R53**（改 harness 后所有被比较的模型必须重跑，不得混两代 prompt）+ **§7.7**；S-36/S-37/S-38；负控 44→**47**；`gen_candidates_v2.js` 删「未提长桁→长桁数=0」授权、增「数量类字段铁律」与 `--only` 冒烟口；`score_baseline.py` 顶层 `model` 改读候选文件；`msr_l3.py` 增 `denominator_audit` / `exam_denominator_audit` 且不闭合即退出 |
| **v4.7** | 2026-10-25 W5c-6c 跨模型轮 | 新增 **R47**（比率分母必须显式落盘、加和闭合）/ **R48**（第二模型只作可重复性证据，不得事后择优）/ **R49**（value_added 双尺度结论相反必须标 `verdict_split`）+ **§7.6**；S-33/S-34/S-35；`score_baseline.py` 修口径 bug：字段级命中率旧版用 `if r.get('n_fields_gated')` 隐式过滤，把 `fabricated`/`clarify_wrong` 当成「不存在」⇒ C-029 与 C-031 算出同一个 99.34%（C-031 实为 87.42%）|
| **v4.6** | 2026-10-25 W5c-6b 收口轮 | 新增 **R42–R46** 五条治理红线 + **§7.5 治理闸表**；S-29（headline 唯一，**只认状态列自指标记**——按正文判会被 C-029 自己的否定词过滤）/ S-30（dev 投影不冒充实测）/ S-31（MSR 九字段齐 + 别名一致）；`value_added` 增**字段级**尺度（地板 85.93% → LLM 99.34%，Δ+13.4 pp）与 **T1+ family-mode** 地板（含 `n_fail_exam` 缺口分布）；§6 负控 37→**41** 条计数（含新增 NC-38/NC-39）；`evaluate.py` 增 `n_fields_gated`（剔除恒 pass 的只报不判项，否则命中率口径不可比） |
| **v4.5** | 2026-10-25 W5c 重打分轮 | 新增 **R41 数值角色**（+ §7.3）+ §7.4 契约试建闸边界（gold 55/55 可建）；R33 改**两端口径**（exam 0 违规 + 非 exam 白名单逐字相等）；R32 局限补第二处「数值出现 ≠ 字段角色可判」；**§4 / R35 补四行口径**（`exam_msr` 与 `exam_msr_excl_solver` 并列，原注释「exam MSR 不含 solver」与实现相反）+ 修顶层 `msr` 一直为 null（NC-36 抓到） | v6c 自查发现 `stiffened_panel_800x600`/`_str3` 旧模板 `{width} × {length}` 使题面「600 × 800」与 gold `length=800` 角色相反 ⇒ 模型正确读法被判错（2 条 dev，0 条 exam） |
