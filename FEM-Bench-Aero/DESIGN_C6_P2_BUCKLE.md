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
- **已备好待跑**：`make_p2_abq_jobs.py` 生成 2 条 abaqus deck（加筋板 1 + 柱壳 1）+
  `feagpt_repro/_p2_abq_jobs/run_p2_abq_MANUAL.bat`；deck 六项自检全绿
  （`*BUCKLE`/SUBSPACE 在、`*STATIC`/`OUTPUT=2D`/`NUMBER INTERVAL` 不在、参考载荷在步内），
  bat 带 `.sta` 存在性检查与 eigenvalue 命中打印。作业目录不入库，换机用脚本重生成。

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
