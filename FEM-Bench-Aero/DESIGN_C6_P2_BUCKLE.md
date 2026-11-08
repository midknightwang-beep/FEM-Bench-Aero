# DESIGN C6-P2 — 线性屈曲打样设计（草案，待拍板）

> 状态：**✅ 设计已拍板（2026-11-07 晚，§8 四项全按推荐）**。老王先拍板「C6-P2 = 线性屈曲」（CONFLICT N-37 选项 A），
> 再拍板本文件 §8 四项；本文件是「接着开工」的第一份产物，实现按 §9 顺序推进。
> 出处：`PROPOSAL_C6_BUCKLING_MODAL.md` §2（P2 定义）、§5（6–8 条）、§6（λ/f 阈值先测后定）、
> ROADMAP §5 C6（数据层新一轮，不是 v1.1 补丁）。
> 优先级：**用户拍板 > AGENTS.md > 本文件**。数字一律现场实读 artifact，本文件不写死会漂的值。

## 1. 目标与边界

| 项 | 内容 |
|---|---|
| 分析类型 | 线性特征值屈曲（**不是**非线性后屈曲 / Riks，P3 明确不做） |
| 语义量 | λ_cr（临界载荷因子，= buckling factor）+ 屈曲模态数 |
| 案例族 | 加筋板轴压（N_x 扫描）、柱壳外压（提案 §2） |
| 双码 | ccx `*BUCKLE` / abaqus `*BUCKLE` |
| 数据层 | 形态 A：独立 v2 线，与 v1.1 / v8 完全并行（C6 原文「数据层新一轮」） |
| 起步规模 | 6–8 条打样（提案 §5），先打样后放量 |
| 验收 | λ 双码相对差阈值**先测后定**（提案 §6 第 4 条，不预写死） |

**边界**：headline 仍是 C-032；P2 全部数字 diagnostic，不与 v8 / L2 / L3 / P1 并列成表。
Abaqus 侧在 agent 内必失败（沙箱注入 `tsbx.dll`）⇒ 双码验收仍需老王在 WorkBuddy 外跑 bat（P1 同款流程）。

## 2. 官方语法证据（2026-11-07 实查，非记忆）

| 码 | 语法 | 数据行 | 载荷语义 |
|---|---|---|---|
| **ccx** | `*BUCKLE`（可选 `SOLVER`） | ① 需要的 buckling factors 数 ② 精度（默认 0.01） ③ 每次迭代的 Lanczos 向量数（默认 4×阶数） ④ 最大迭代数（默认 1000） | **buckling 步之前的载荷全部移除**；只缩放 buckling 步内指定的载荷直到屈曲；载荷不得含给定位移；只考虑该载荷引起的应力刚度，不含大变形刚度 |
| **Abaqus/Standard** | `*BUCKLE, EIGENSOLVER=SUBSPACE`（默认）或 `LANCZOS` | SUBSPACE：① 阶数 ② 最大特征值 ③ 迭代向量数 ④ 最大迭代数；LANCZOS：① 阶数 ② 最小特征值 ③ 最大特征值 ④ 块大小 ⑤ 最大 Lanczos 步数 | 特征值屈曲估计，`.dat` 出 eigenvalue 表 |

来源：CalculiX ccx 2.18 官方手册 `*BUCKLE`（feacluster / bconverged 镜像）、
Abaqus 2025 Keyword Reference `*BUCKLE`（VT / UCLouvain 官方镜像）、
CalculiX 官方论坛「A Guide to Modifying Abaqus Input Files」对两码数据行差异的对照。

### 2.1 实测修正（2026-11-07 夜，ccx 真机冒烟，`probe_p2_ccx_buckle.py`）

- 改完 `spec.py` / `inp_writer.py` 后先过**零扰动验证**（`verify_p2_zero_perturbation.py`）：
  4 族静力 + 1 条 v2 模态 deck 的 sha256 与冻结件**逐字节一致**（行尾归一后比较），
  buckle deck 形状五检全绿（`*BUCKLE` 在、`*STATIC` 不在、载荷在步内、无 extra 端载）。
- ccx 2.23 冒烟：1 条 `stiffened_panel_600x600`，参考载荷为步内 `*DLOAD E_PANEL, P, -0.1`，
  `*BUCKLE` 数据行**只写阶数**合法；`rc=0`、`.dat`/`.frd` 都有、单条约 142 s。
- `.dat` 确切排版（提取器照它写）：横幅 `B U C K L I N G   F A C T O R   O U T P U T`，
  表头两行 `MODE NO       BUCKLING` / `FACTOR`，数据行 `          1   0.3175812E+02`
  （阶号 + 科学计数法 λ）。两阶实测 `31.75812` / `37.72061`。
- **★ 这两个 λ 不是真值、不作为阈值依据**：参考载荷是探针自定的 -0.1 MPa 面压，
  P_ref 尚未按族定义；λ 随 P_ref 变化（λ×P_ref 才是临界载荷）。
- **Abaqus 侧数据行（`n, 1.0e6` / `EIGENSOLVER=SUBSPACE`）尚未真机验证** ⇒
  必须由老王在 WorkBuddy 外跑 bat（agent 内 `tsbx.dll` 必失败），小批 2 条先验再用。
### 2.2 Abaqus 首次真机失败实录（2026-11-08 早，老王在 WorkBuddy 外跑 bat）

**结论：v1 的两条 deck 都没拿到 eigenvalue，`.sta` 未生成，bat 的 `.sta` 闸正确拦住第二条。**
产物实读（`_p2_abq_jobs/stiffened_panel_600x600_buckle/`）：

| 证据 | 原文 / 数值 |
|---|---|
| `.dat` 末尾 | `ANALYSIS IS ENDED ... WITH 1 ERROR MESSAGES ON THE MSG FILE` |
| `.msg` 报错 | `***ERROR: INCREASE THE NUMBER OF ITERATIONS TO GET THE REQUESTED NUMBER OF EIGENVALUES.`（SUBSPACE 默认 30 次，`NUMBER OF EIGENVALUES CONVERGED UPTO THIS ITERATION = 0` 一路） |
| `.msg` 警告 | `***WARNING: THE DIFFERENTIAL MATRIX HAS 63539 NEGATIVE DIAGONAL ENTRIES`；迭代值 `-3.541038E+03`（**负特征值**） |
| `.dat` 设置 | `NUMBER OF EIGENVALUES 2`、`LARGEST EIGENVALUE OF INTEREST 1.00000E+06`、`MAXIMUM NUMBER OF ITERATIONS 30` |

**根因两处，都是我方设计错，不是 Abaqus 或操作问题**：
1. **物理错**：给加筋板用了 `kind="pressure"`（法向面压 = 横向弯曲），而提案要的是 **轴压 N_x（面内压缩）**。
   实读 `feagpt/geometry.py:1019`：`build_stiffened_panel` **明确拒绝 `tip_force`**，
   注释写「panel has no tip/root node group to carry a concentrated force」；
   现成能力只有「四边简支 + 法向面压」。负特征值正是「载荷不是压缩」的信号。
2. **求解设置错**：Abaqus `EIGENSOLVER=SUBSPACE` 默认 30 次迭代不收敛；
   P1 频率步已证 LANCZOS + 显式区间更稳。

**修正（v2，R-A1 只做一件事：用柱壳外压单族把双码链路打通）**：
- Abaqus buckle 数据行改 `*BUCKLE, EIGENSOLVER=LANCZOS` + `n, 0.0, 1.0e6`（避开 [0,0] 占位零值坑）。
- 柱壳：builder 的 `PRESSURE_DLOAD_SIGN` 正数 = **内压**（v1.1 静力 deck 实读 `E_SKIN, P, 0.05`）；
  外压需要反号 ⇒ `analysis.buckling.reference_load.pressure_sign = -1.0` 作为**相对乘数**
  （Q4 决议仍成立：族相关的 group/基准 sign 由 builder 传，压缩/外压方向是参考载荷自己的属性）。
- 加筋板轴压**从本轮移除**，另立一单（见 §11）。

### 2.3 加筋板轴压能力缺口（下一单，待拍板）

提案 §2 的「加筋板轴压（N_x 扫描）」在现有 feagpt 里**没有现成实现**：
builder 只有四边简支 + 法向面压，没有端部节点组可挂面内压缩载荷。
要做必须新增 builder 级能力（端部节点组 + 轴向 *CLOAD 分布 / 等效面内载荷），
并补一套物理自证（轴压杆/板的解析 λ 或网格收敛），否则重演「负特征值还以为跑通了」。
**这是实现方案决策，先出方案再拍板，不与双码链路打通并行。**

### 2.4 v2 ccx 侧复验（2026-11-08，`reports/diagnostics/p2_ccx_barrel_buckle_smoke.txt`）

- 零扰动重跑 **5/5** 全绿（改完 inp_writer 后再验）；新 deck 实读
  `*BUCKLE, EIGENSOLVER=LANCZOS` / `2, 0.0, 1.0e6` / `E_SKIN, P, -0.1`（外压符号正确）。
- ccx 2.23 柱壳外压真机：`rc=0`、`dat/frd` 都有、656 s/条，
  `.dat` 排版与 v1 完全一致（`B U C K L I N G FACTOR OUTPUT` / `MODE NO` / `BUCKLING FACTOR`），
  两阶 **λ = 1.008207 / 1.009420 全为正**（v1 的负特征值错误信号消失）。
- **★ 诚实边界**：λ≈1.008 的**绝对值合理性尚未核对**（0.1 MPa 参考外压下是否该如此早屈曲，
  需解析解或网格收敛自证）。本结果只证明「双码语法链路 + 载荷方向」成立，
  **不作 truth、不进阈值**；正式 P_ref 与打样卷定下后必须重算并做物理自证。

### 2.5 v2 Abaqus 真机成功 + 首份双码交叉差（2026-11-08 09:31，老王外部跑 bat）

- `.sta`：`THE ANALYSIS HAS COMPLETED SUCCESSFULLY`；`.msg`：**0 errors**、
  1 warning（`THERE ARE MORE EIGENVALUES IN THE SPECIFIED RANGE THAN REQUESTED`，
  区间内重根多于请求阶数，非错误）；`NUMBER OF NEGATIVE EIGENVALUES 0`（v1 负根问题消失）。
- `.dat` 排版（提取器照它写）：横幅 `E I G E N V A L U E    O U T P U T` →
  `BUCKLING LOAD ESTIMATE = ...` 三行说明 → `MODE NO      EIGENVALUE` →
  数据行 `       1      0.68716`（Abaqus 是定点小数，ccx 是科学计数法）。
- **两阶完全相同（重根）**：柱壳轴对称模态的物理现象 ⇒ 谱检查必须**非递减**，
  不能照抄 P1 频率提取器的「严格单调递增」，否则把正常重根判红。
- 提取器 `extract_buckle_dat.py`：**12/12 pins**（含两段真机片段、负 λ / 缺阶 /
  递减 / 横幅误命中 / 未知 dialect 等双向变异），并已对真机 `.dat` 实解析通过。
- **★ 首份双码交叉差**（`reports/diagnostics/p2_buckle_cross_diff_v2_2026-11-08.json`，
  内含两侧 raw 表格片段可离线复算）：同一 spec、同一 P_ref（-0.1 MPa 外压），
  **ccx λ = 1.008207 / 1.009420，Abaqus λ = 0.68716 / 0.68716，
  λ1 相对差 37.87%（λ2 37.99%）** —— 两阶一致 ⇒ 系统性公式级差异，不是配对错位。
- **判据含义（必须拍板）**：P1 模态 f1 的 1% 跨码阈值在屈曲上**不可能成立**；
  跨码阈值放宽到 ~40% 又等于没有鉴别力。可行路径是 **P1 同款「同码自比」**
  （候选与参考走同一码求解，公式差异在差值中抵消），Abaqus 侧降为链路一致性诊断。
  1 条样本不是分布，Q3 阈值仍「先测后定」；6 条打样时再验证同码自比的稳定性。
- **已备好待跑（v2）的 bat 已完成使命**；作业目录不入库（换机用 `make_p2_abq_jobs.py` 重生成），
  真机数字已固化进上面那份 diagnostics artifact。

**★ 与 P1 最大的不同**：模态步**载荷无关**（P1 直接省略整个 load 块，两码共用一张数据行即可）；
屈曲步**载荷相关**，且两码数据行语义完全不同 ⇒ 必须按 dialect 分别写 step 段，
并把「参考载荷」作为 spec 的一等公民显式定义，否则 λ 不可比。

## 3. 载荷工况与 λ 的定义域（判据先写清，N-36）

- **参考载荷 P_ref**：加筋板 = 轴压（面内均布 N_x 或等效端部压力）；柱壳 = 外压（面压）。
  两码 deck 必须由**同一个 P_ref** 生成，写在 spec 中、进冻结集。
- **λ_cr** = buckling factor，是「把 P_ref 乘多少倍达到屈曲」的无量纲标量；
  **N_cr = λ_cr × P_ref** 才是有量纲的临界载荷。
- **判据口径二选一（§8 Q3）**：判 λ1 相对差（与 P1 的 f1 同构）⇒ 必须保证两码 P_ref 逐值相同；
  或判 N_cr 相对差 ⇒ 允许 P_ref 不同但要把量纲写进 truth。**不允许两种混用**。
- **阶数**：起步建议只判 λ1（提案「一般只需要最低阶」）；λ2+ 只记不判（P1 高阶公式级差异的同款纪律）。
- **不进卷**：`stiffened_panel_800x600` / `_str3` 两条 dev 题（length/width 角色缺陷，长期挂 dev，不对外）；
  柱壳 extra 的 `end_shear/end_moment` 在 buckle 步被移除但仍在 spec_fidelity 全键比对内 ⇒
  **先声明这些键是否属于被考内容**，否则重演 N-36「零影响的真因是没有这种题」。

## 4. 实现面（拍板后才动）

| # | 环节 | 增量 | 复用 P1 资产 |
|---|---|---|---|
| 1 | `feagpt/spec.py` | `step_type` 加 `buckle`；新增 `buckling` 配置块（阶数 / 参考载荷定义 / eigensolver 选择） | `n_modes` 的 from_dict 校验范式 |
| 2 | `feagpt/inp_writer.py` | `buckle` 分支**按 dialect 分别写**数据行与载荷块；静力/模态分支不得回归（deck sha 逐字节验证，P1 同款零扰动证明） | frequency 分支骨架 |
| 3 | `feagpt/solver.py` | `*BUCKLE` 求解；R61 全局锁同样生效 | 现有锁 |
| 4 | `extract_buckle_dat.py`（新） | 解析 ccx `.dat` 的 buckling factor 表 + abaqus `.dat` eigenvalue 表；先跑真机回归 pin 再写解析 | `extract_modal_dat.py` 13 pins 的写法 |
| 5 | 打样卷生成 | 从 v1.1 加筋板/柱壳 spec 读入 → 换 step 段 → 双码 deck → 求解 → truth | `make_v2_modal_cases.py` 骨架 |
| 6 | 双码交叉差表 | λ 逐序号相对差（先测后定阈值） | `make_v2_cross_diff.py` 骨架 |
| 7 | 判分器与考卷 | 新卷 / 新判分器（P2 不与 P1 共用 `score_v2_modal.py`；P1 判分器有 `V2_L1_`/`N_MODES=10`/1% 阈值硬编码） | 递归全键 spec_fidelity + 同码自比思想 |
| 8 | 冻结 | `SHA256SUMS.txt` + EOL 规范化在前、清单生成在后（P1 踩过的坑） | 同款流程 |

## 5. 打样选材（实读 v1.1 `modeling/`）

| 族 | 可用条数 | 候选 | 说明 |
|---|---|---|---|
| 加筋板 | **3** | `stiffened_panel_600x600`、`600x600_str3`、`700x600_str4` | 5 条中 2 条 dev 缺陷排除 |
| 柱壳 | **7** | `fuselage_barrel_d1600_l1600_str8_frm3` 等 7 条（含 t2 壁厚、D25/D27 口径） | T3 已完整收口，参数轴齐全 |

规模选项见 §8 Q2（推荐 3+3=6 条，或 3+5=8 条）。

## 6. 判据定义域清单（新题型进卷前必须逐条答）

1. 判 λ1 还是 N_cr？两者分母/量纲不同，不得并列成表（R54）。
2. 参考载荷 P_ref 是否进 spec_fidelity 全键比对？进 ⇒ 题面必须给全；不进 ⇒ 必须写清豁免理由并配反向闸（R69）。
3. 屈曲模态数要不要判？提案列为语义量，但双码模态编号不保证同序（P1 高阶差异的教训）。
4. 阈值怎么定？**先测后定**：先跑 6–8 条双码真例出 λ 相对差分布，再拍板数值（不预写死 2%）。
5. 同码自比是否沿用？P1 靠「候选与参考走同一条管线」抵消公式差异；屈曲的载荷相关性能否同样抵消，待实测证明。
6. 无输出 / 求解失败 / 特征值阶数缺失一律**记 0 不排除**（R47 / R-A5）。

## 7. Abaqus 真机流程（不可省）

- agent 内 `abaqus` 必失败（`tsbx.dll`）⇒ 本机只跑 ccx；abaqus deck 由脚本生成后交老王在 WorkBuddy 外 cmd 跑 bat。
- P1 三坑要在 P2 提前防：路径带空格须带引号（`--abaqus-cmd`）；ccx 血统 inp 的 `OUTPUT=2D` 原生 Abaqus 不认（验收副本剥参数）；`.sta` 闸防假 rc=0。
- 新增坑位预判：Abaqus `*BUCKLE` 的 `NUMBER INTERVAL` 等输出参数是否合法、`*NODE FILE` vs `*OUTPUT, FIELD` 的模态/屈曲差异，真机跑一遍才知道 ⇒ 先小批量（2 条）验证再放量。

## 8. 请老王拍板的四件事（推荐项 + 理由 + 代价）

| # | 决策点 | 推荐 | 理由 | 代价 |
|---|---|---|---|---|
| **Q1** | 数据层落点 | **A：`modeling_v2/buckle/` 子卷**（同 v2 线、同冻结体系） | C6 形态 A 是「独立 v2 数据线」，P1 已在 `modeling_v2/`；子卷复用同一套 SHA256SUMS/EOL 流程 | 与 P1 共根目录，清单要分区；备选 B 新建 `modeling_v2_p2/` 独立卷更干净但多一套维护 |
| **Q2** | 规模与选材 | **A：6 条 = 加筋板 3 + 柱壳 3** | 提案 6–8 条起步；先小批验证双码语法/输出再放量 | 备选 B 8 条（柱壳 5）覆盖面大但真机方差时间；备选 C 先 3 条冒烟再放量，多一轮往返 |
| **Q3** | λ 判据口径 | **A：只判 λ1 相对差 + 两码 P_ref 逐值相同** | 与 P1 f1 同构、定义域最干净；提案也说「一般只需要最低阶」 | 备选 B 判 N_cr 需把量纲写进 truth；备选 C λ1+模态数会因双码模态编号不同序而误判 |
| **Q4** | 参考载荷的键层 | **A：新增 `analysis.buckling` 配置块（阶数 + 参考载荷），不碰现有 `load` 块** | N-35 教训：执行配置与数据集元信息分开；静力 `load` 块语义是强度载荷，混用会让旧判分器误判 | 备选 B 复用 `load` 块加新键 ⇒ 老闸/旧卷全链要重验（R53 换代链） |

**✅ 决议（2026-11-07 晚）：四项全按推荐** —— Q1 `modeling_v2/buckle/` 子卷、Q2 6 条（加筋板 3 + 柱壳 3）、
Q3 只判 λ1 且两码 P_ref 逐值相同、Q4 新增 `analysis.buckling` 配置块（不碰现有 `load`）。
拍板即落盘，实现按 §9 顺序推进；任一项事后变更须写 post-hoc 声明 + bridge（R-A2），不得静默改。

## 9. 拍板后的执行顺序（不含拍板前动作）

1. 冻结口径：考卷 sha / prompt sha / rubric 版本 / 候选目录 / model id 先记录（R-A2）。
2. 实现 §4 的 1–4，先做静力零扰动验证（改完 spec/inp_writer 后重生成 v1.1 基准 deck，sha 逐字节一致）。
3. 2 条小批量双码冒烟（ccx 在 agent 内、abaqus 由老王外部 bat）→ 确认 `.dat` 表格式 → 写提取器 + 真机回归 pin。
4. 6 条打样双码全跑 → λ 交叉差分布 → **拿实测数字回来拍阈值**（不预写死）。
5. truth 现读生成 → 卷冻结（SHA256SUMS + DATA.md 条目）→ 考卷接入 → 判分器 self-test（双向 pins）。
6. 收口顺序固定：负控 → check_claims → EOL 规范化 → add → 提交。

## 10. 执行摘要

- **已查实**：两码 `*BUCKLE` 都存在，但数据行语义完全不同、载荷语义与模态截然不同（载荷相关 + 步前载荷清除）⇒ 屈曲不是「把 P1 的 FREQUENCY 换成 BUCKLE」。
- **已查实**：`buckle` 在 feagpt 零实现；v1.1 可用加筋板只有 3 条（2 条 dev 排除）、柱壳 7 条。
- **待实测**：本机 ccx `.dat` 的 buckling factor 排版、Abaqus 侧输出与合法输出参数、λ 双码相对差分布。
- **本文件的四个岔路口拍板前，不写一行实现代码、不改任何 claim / artifact / paper / rubric。**

## 11. 专家审查决议（2026-11-08，FBA-C6P2-REV-001-EX01）

> 审查意见原件：`FEM-Bench-Aero/reviews/FBA-C6P2-REV-001-EX01.md`（sha256 `844770e3…`）；
> 送审报告已按意见修订为 **v1.1**：`FEM-Bench-Aero/REVIEW_C6_P2_FORMULATION_DIFFERENCE.md`。
> 本节为**决议口径**，取代 §9 中「6 条打样」的原执行顺序。

### 11.1 核心纠正（必须记住）

- **λ1 相对差 37.87% 是真实的，但「系统性 S4 公式差异」不成立**。ccx 2.23 日志
  `sigma=1.000000,d[0]=1.008207`；Abaqus 基本 λ = 0.687155（`.msg` 全精度）< 1；
  ccx 两阶紧贴 σ=1.0 ⇒ **ARPACK shift-invert 固定 σ=1.0 漏低阶模态**是首选排除项（C3）。
- 两阶相对差接近**不能**证明「非配对错位」：可能只是同一对移位模态。
- 「38% 超出纯数值误差」只能排除舍入/容差，**不能排除选错模态**。
- P1 的 8 条是 NACA4412 翼盒，与 P2 柱壳**不同族**；deck 逐字节一致只排除**文本层**，
  语义层（S4 解释、边界 DOF、压力刚度）与求解器算法层均未排除。
- Abaqus `.dat` 的 0.68716 是 5 位舍入；`.msg` 为 0.687155 / 0.687161 / 0.697166（近重根）。
  提取器已改用 `.msg` 全精度并用容差判重根（17/17 pins）。

### 11.2 方案与决策（专家裁定）

| 项 | 裁定 |
|---|---|
| S1 同码自比 | **采纳**，为 LLM 候选评分主路径；**必须先过 solver-health 闸**：λ 在安全区、载荷缩放不变、振型可配对、同码 gold 自比 0.0 |
| S2 跨码阈值放宽 | **不采纳**（阈值无鉴别力，会把求解器 artifact 制度化） |
| S3 统一单元/公式 | 仅当跨码硬比为硬性需求时立项；先做 P1 小样本隔离，不改全管线 |
| S4 先补证据 | **采纳且前置**，顺序改为「先 shift/模态（P0），再公式/网格/边界（P1）」 |
| S5 定性判据 | 可作过渡期「能跑通」闸，不替代 λ 数值判据 |
| S6 双轨分层报 | 可用，必须写清分母与不可比性，不相加、不排名 |
| D1 / D2 | 差异真实但**不支持「系统性」**；只做最小核验 K1/K3/K9 + K-shift + K-mode |
| D3 / D4 | S1 + S4 前置；跨码数字仅 diagnostic，不进 headline |
| **D5** | **6 条打样暂缓**，至少等 P0 闭环；否则 6 条可能全是 shift artifact |
| D6 | 加筋板轴压缺口另立任务，与本差异脱钩 |

### 11.3 执行顺序（覆盖 §9）

1. **P0（先做）**：载荷缩放 0.1/0.05/0.02 MPa 两码各跑 6 阶；振型 MAC 前 3 阶；
   完整归档与 step 全量 diff（已完成）；提取器 `.msg` 全精度（已完成）。
   通过标准：安全 λ 区间（建议 >1.5）下 `λ·P_ref` 稳定、振型可配对、ccx 不再紧贴 σ。
2. **P1**：无加筋圆柱壳 S4/S4R/实体对照、平板轴压、边界 DOF 矩阵、静力预载应力对照、
   同一柱壳双码模态 + MAC、3 档网格收敛。
3. **P2**：P0/P1 闭环前**不冻结 λ 阈值、不跑 6 条打样、不对外发布跨码数字**。
4. 物理正确性另设锚点（解析解／试验／高保真模型）与扰动测试：
   同码自比只能证明「与参考一致」，不能证明「物理正确」，且会被「抄参考」骗过。

### 11.4 本轮已完成

- 专家意见原件归档 + sha256；报告 v1.1（31 处精确修订、§10 填结论、§8.5 验证计划）。
- `extract_buckle_dat.py` 17/17 pins（`.msg` 全精度 + 容差近重根）。
- `archive_p2_evidence.py` + manifest + `step_diff_full.json`（U5 关闭、U6 部分关闭）。
- `probe_p2_load_scaling.py`（ccx 3 档 × 6 阶）与 `make_p2_abq_scaling_jobs.py`（Abaqus 3 档 × 6 阶 + 外部 bat）。
- **P0-1／P0-2 ccx 侧已完成（2026-11-08，见送审报告 §8.7、E15）**：3 档 × 6 阶全 `rc=0`；安全两档（0.05／0.02 MPa）`N_cr1` = 0.07026195 / 0.07026252 MPa，对称相对差 8.11e-06；0.1 MPa 档 0.09495004 MPa 偏离 29.89%，且 6 阶谱中不存在由安全 `N_cr` 反推的 λ1 = 0.702622 ⇒ **σ=1.0 邻域档即便 6 阶仍漏真最低根**。ccx 安全 `N_cr` 与 Abaqus 单档 `N_cr` = 0.0687155 MPa 相差 2.2259%（跨 P_ref，仅 diagnostic）。逐阶 `N_cr` 低 3 阶稳定、第 6 阶漂移 5.62% ⇒ 支持 Q3「只判 λ1」。
- **仍未闭环**：P0-3 振型 MAC；**Abaqus 侧 3 档 × 6 阶**（deck + 外部 bat 已备，8/8 自检 ×3，ccx 求解已结束、锁已释放 ⇒ 现可运行）；网格收敛／解析解锚点。**P0 不得宣告通过，6 条打样继续暂缓（D5），λ 阈值继续不冻结。**
