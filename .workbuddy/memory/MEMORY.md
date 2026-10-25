# 工程长期备忘（蜗子 / 老王）

> 只留**跨会话仍要生效**的东西；逐批过程细节在 `.workbuddy/memory/YYYY-MM-DD.md`。
> 2026-10-24 压缩重写，完整旧版留档 `MEMORY_ARCHIVE_20261024_full.md`（细节查它或当日日志）。

## 环境铁律
- 🚨 **Abaqus agent 内失败头号嫌疑 = WorkBuddy 沙箱注入 `tsbx.dll`**（pre.exe `__fastfail`；签名：~19s 延迟 + Input File Processor error + .dat 无错 + ODB 空骨架，1 单元也崩）。`dangerouslyDisableSandbox` 无效；重启后 <15min 冷启动能跑是假象。可靠路径 = **WorkBuddy 外普通 cmd 手工 bat**（solve + `abaqus python abaqus_odb.py` 提取）。
- **手工 bat 顺序**：先 `resummarize.py --roots …` 再 `make_dataset`。反了不报错、只打 `max|u|=n/a`（提示不是闸，gate4 照旧绿）⇒ 收口必须逐目录数文件（**6 个**）。
- numpy/gmsh 用 venv `…\envs\default\Scripts\python.exe`。ccx = `tools/calculix/calculix_2.23_4win/ccx_static.exe`；Abaqus = `D:\Program Files\SIMULIA\Commands\abaqus.bat`。
- **绝不并行跑 abaqus/ccx**（静默空转：`AbaqusException: 0`、rc 仍 0）。只认真 FRD / 真 ODB 读数，不信「命令返回 0」。
- ccx 壳展开成实体：方程 ≈ 14.9×壳节点；本机 33GB 上限 ⇒ **≤158,548 节点可算、188,674 已失败**。查规模：起 ccx 读到 number of equations 即 taskkill。

## 验证纪律
- 只认独立复算：平衡（唯一不变量）+ 解析解 + 双码交叉。**门禁不许印没量过的数字**（命令+数字+产物路径落盘）。
- **判据按族（D34）**：双码载荷口径不可跨族套用 —— 翼盒 500 N 端载 + 根截面反力；柱壳 内压+端弯+端剪（D20 剔端载环）；开孔板 面内拉伸；加筋板 1000 N。套错会产出 9900 % / 700 % 的一整片假 FAIL。
- 双码位移：barrel 登记判据 = D20 `structure_peak`，model-wide `max|u|` 只 REPORTED NOT GATED；小位移区相对误差骗人，先看绝对差与该处幅值。
- 变体结果完全相同 = 报警信号；改网格/判据 ⇒ 重签基线是正常流程但必须留档旧基线（D10）。
- 闸门报数报**判据组数**不是快照条数（`regress_groups` 打 18 条快照，判定句是 `9/9 identical`）。回看最后一行的 VERDICT 前那句话。

## 契约与数据集
- 唯一契约 `spec.FEASpec`；**求解器选择在写 deck 之前**；结果两码归一 `{nodes:{DISP,FORC,STRESS}}`。spec 加字段 ⇒ spec_sha256/truth.json 全档失效须重导（留档旧值）。
- `modeling/`(ccx 可发布) + `_xval/`(abaqus 禁发布)；case 六件套 = spec/step/msh/inp/results/truth。门禁：minJ ≥ 0.30 且零 tri3／平衡 < 1e-3%／双码 `max|u|` 差 < 1% + vM 逐节点中位差 < 5%（素板双码天生空转报「不适用」）。
- **划分是规则**：`manifest.HOLDOUT_REGIONS` + `split_of(spec)`（吃 spec 不是 case_id，首个命中即定，未命中默认 train）；eval 断言复现 D12。等价类 = 族+几何+壁厚白名单。
- **去重指纹（D25/D29）= msh 逐字节 + SHELL SECTION 厚度表 + `*ELASTIC` 材料律块**。只按 mesh 判会误删壁厚变体；不加材料律则复材/铝同网格同厚度撞（80695b4c759e）。
- 复现命令：`check_forms.py`／`verify_hole.py`／`verify_barrel*.py`／`check_semantics.py`／`verify_dataset.py`／`eval_dataset.py`／`make_manifest.py --json <path> --md`／`make_dataset.py --solver ccx|abaqus`／`run_pipeline.py --deck-only`（只出 inp 不求解）。
- **`check_forms` / `make_manifest` 不传 `--json` 就只打印不写盘**。

## 高价值坑（跨族通用）
- **「模型不行」第一嫌疑 = 特征没给全**（M7）：漏 `is_T`/`web_pos` 时 test 14.8 % 输给 3 参物理；补齐后 10.7 %，结论反转。**诊断假设与被测对象必须同口径**。
- **标准化欧氏距离不能当可信度指标**（corr(distance,|err|) = −0.046）。可信判定必须**逐轴判训练包络**：`n_ribs` 安全 <3 %／`is_T` 可接受 4.8 %／`n_web`·`taper` 中等 11–15 %／**`sweep` 危险（20→40° 错 41.5 %，超线性）**。
- **补覆盖点 ≫ 补同质样本**：n 10→12 加两条同质 chord800 零收益（14.1→14.2 %）；n 12→13 加唯一带腹板的 web1 → 10.7 %。放量先补「新轴/新形式」锚点。
- **标准化系数不是幂指数**：指数 = `w / sd(log x_f)`。实测翼盒 span **+2.858**、skin **−0.992**、chord **−2.900**。
- **交互项必须用实测单轴响应相乘**，不能用理论指数（否则把标度偏差误报成交互）。
- **厚度维退化取决于载荷口径，不是轴的属性（D31）**：载荷随 t 缩放则与膜刚度精确抵消（T7 开口板 t=1/t=2 位移同 0.05734516）；翼盒 500 N 固定 ⇒ `u∝1/t`（skin 1.5→4 变 2.656 倍）。**判某轴是否退化，先问「载荷随不随它缩放」**。翼盒 `skin_thickness` = 主承力壁厚（蒙皮+前后梁+腹板），`rib_thickness` 独立。
- **只打印不参与判定的检查不是检查**：`verify_dataset` pairing 打了 MISMATCH 而 `all_ok` 不含它 ⇒ 41 vs 44 仍 PASS。
- **铺层平衡必须按有符号配对**（`a>90°` 折回 `180−a`），`% 180` 会把 −45° 变 135° 而误拒 `[±45]s`；用 A16/A26 实算交叉校验；准各向同性可用恒等式 `G=E/(2(1+ν))` 独立验 CLT。
- **翼盒坐标系：x 弦向 / y 法向（载荷 DOF 2）/ z 展向**。`max_w = max|DISP[2]|` 是**展向位移**不是法向挠度；但 `max|v|/max_disp = 0.99899–0.99973` ⇒ `max_disp` 本身已是弯曲挠度。
- **峰值是「离散选择」不是「光滑泛函」**：31 条翼盒 `max_disp_node` 有 21 个不同节点、vM 中面峰值 25 个 ⇒ 这是「应力不可学」的机制；**给 vM 峰值补样本是白费**。
- **报 MAPE 必须同报中位+最大+bootstrap CI**：单点离群就能把均值 3.81 抬到 7.96 %。**跨目标/跨里程碑比 MAPE 必须先对齐 test 集**（各剔各的最差会得出相反结论）。
- **baseline 口径五条**：超参一次选定／全部 log 空间拟合／常数地板用加权中位数（权重 1/y）／最强物理对手含自由指数幂律／**模型选择在 val 做、test 只报一次**。
- **共线模型要报条件数**：M2 三形状项在 train 共线 ⇒ 无正则 LSQ test 49665 %；正解是岭收缩 + 报条件数，结论应是「该形式在 train 不可辨识」而非「物理输给 ML」。**条件数必须先标准化再按秩剔除**。
- **`_wingbox_planar_shape` 返回 `(tip_chord_ratio, sweep_deg)`** —— 解包反了会把全案判成「锥度 0」。凡元组解包先确认 return 顺序。
- **★ 改划分规则后必须 grep 出所有「把旧结论硬编码进期望值」的检查**（D35）：`T1.role-and-split` 把旧口径写死成 `test`。修法不是改期望值（等于删检查），而是守**二分两端**。判据改动后要问「这条检查还咬得动吗」。
- **★ 结论依赖数据集的脚本，重跑即毁档**：`residual_diag.py` 覆盖了 D34 原件。凡此类探针输出名必须带里程碑标签 + 支持 `--out`。
- **★★ 往结构化数组插条目：锚点唯一 ≠ 锚点正确**（D34/D35 连踩两次）：`DECIDED` 末条与 `REVIEW` 末条都以同一串结尾，只差收尾空白（`\n];` vs `\n ];`）⇒ `assert count==1` 通过但写错数组，JS 直接 `Unexpected token '{'`。**必须断言相对位置**（`index(DECIDED) < index(新条目) < index(REVIEW)`）。
- **看板数据字段一律脚本回读**：`SPLITS.rows` 的 `cls` 曾 28/52 条漂移（`_dash_sync_splits.py` 修）。

## 协作约定
- 决策环节**先可视化梳理** → 更新看板（DATA 区），必跑 `node _dash_check.js`（条数硬编码须同步）。看板灵魂：每条结论可追溯到命令+实测数字+产物路径。
- **里程碑收口三同步：看板 + 两份 README + 记忆**。岔路口先问老王（推荐项+理由+代价，不摆中立选项）。

## 资产与判据索引（压缩版）
- **结构形式**：T1 放样放量（≠拉伸）／T2 复材／T3 柱壳／T4 开孔板 Kt（gross/net 差 11.1 %，Howland 只看 λ；size 单维须 hole_d 随 width 缩放钉 λ）／T5 加筋板／T6 多闭室翼盒（剪流是决定性可观测；vM 别用 inplane）／T7 复材铺层（CLT 等效模量，TOL_EFF 3 %）。
- **判据号**：D8 外表面峰值禁裸比｜D9 平板网格 3mm｜D10 零tri3+留档旧基线｜D11 判据字面不动｜D12 划分冻结｜D15 T1 几何口径｜D18–22 柱壳（blade-only、剔端载环）｜D25 尺寸精确锚点+指纹扩壳厚+材料律块｜D27 只朝收缩方向｜D28 角点谓词两轴 `!=`｜D29 T7 架构 B｜D30 开口板四条标量轴 + 厚度维退化定案｜D31 翼盒尺寸轴 train **区间**（span 1600–2400、skin 2–4，出区间=外推、出锚点但仍在区间=扫点；chord 不算他轴）｜D32 目标口径（主 `max_disp`、副 `max_w` 只报不判、应力峰值不设目标）｜D33 后掠中间档 `WINGBOX_TRAIN_MAX_SWEEP` 20→30｜**D34 sweep 项线性→二次**（基 `[s,s²]`，s=sweep/20 过原点；主判据**零泄漏 LOO@30**；只在 `max_disp` 采纳）｜**D34-b** 形式类决策不能用 val 选，须用「留最高站位」LOO｜**D35 平面形状组合由「一律留出」改包络二分**（两轴都非中性且至少一轴出 train 包络 ⇒ test；都在包络内 ⇒ train 内插交叉）。
- **D34/D35 核心数字**（全档 BASELINE.md §2.5–2.6、看板 r51/r52）：D34 sweep 项改二次只在 `max_disp` 采纳（`LOO@30` −22.14→−1.07）；
  D35 平面形状改包络二分 + `sweep30_taper080` 入 train，同 6 条 test `max_disp` 4.97→3.01；**代价必须同引**：val 变 6.86、
  `sweep40`(val) −12.79、train LOO 3.74。**显式交互列 `s²(taper−1)` 不落地**（5.3 倍外推 ⇒ −36.54 %，「样本可估」≠「可外推」）。
- **闸门现状（55 口径，D36）**：关 1 55/55（最差 minJ 0.4636）｜关 3 翼盒 34/34（其余 21 条分族取证，柱壳/加筋板无机器 JSON）｜
  关 4 110/110｜自洽 110/110｜配对 55/55｜退化自检 54 项｜regress 9/9（判据组数）｜eval 29/29。
  ⚠️ 对外**不存在「55 条全部双码验证」**——机器可读双码 PASS 只有翼盒 34 条。
- **双码实测区间**：位移差 0.15–0.50 %、vM 逐节点中位差 0.18–0.45 %、平衡残差 9e-5–2.6e-3 %。峰值位置两码**不同节点**（D8 常态）。
- **M7 六档（历史基准）**：常数 34.95／梁标度 31.60／梁+形状 14.84／岭 10 特征 10.72（LOO 3.97）／GP 13.95／物理+岭残差 10.63。
- **D31 教训**：`max_w` 数字更低是「题目变简单」不是「模型变好」（span 指数 1.95 vs 2.90，正好绕开会崩的 sweep 轴）；`max_w` 跨族无信息（开孔板 ≡0、加筋板 ≡1）。

## 当前状态与下一步
- **M1–M14 收口**；D34 / D35 / D36 已三同步。**双树 55×2 齐**。
  55 条 / 54 类 / train 25 · val 17 · test 13（翼盒 21-7-6），`WINGBOX_TRAIN_MAX_SWEEP` **30→35**。
- **★ M14 阶段评估已收口（2026-10-24，`FEM-Bench-Aero/STAGE_GATE_M14.md`）——判定 Conditional-Go**：
  路线已通可**结题验收**（110 算例 / 七闸全绿 / D01–D36 可追溯）；**直接移交放量不具备**，三个硬前置：
  **R1** 评估协议被三轮迭代污染（2.63 % 有选择偏置，同考点加 val 训练 1.09→18.35 %；对外承诺写 5–9 % 不写 3 %）；
  **R2** sweep×taper 形式失配（D34/35/36 三轮跷跷板根因）；**R3** 无适用域（距离-误差相关 −0.046，尾部 14–33 % 无法预警）。
  另：**R4 vM 峰值未收敛**（h 收敛 12→6 mm 仍 +12.9 %，应力真值带 ≥13 % 偏不安全低估；位移良定义 −0.48 %）；
  R5 多工况不在契约；R6 收敛只测 1 点；R7 **无 git**（已丢过 D34 产物）；R8 abaqus 非关键路径；R9 cfrp 顶层 material 语义；R10 同几何双样本。
  **全体 34 条留一**（`_probe_m14/all_loo.json`）：max_disp 5.35 %（中位 2.57 / p90 14.09 / max 33.10）——报数必须带 p90+max。
  **准入七条按序**：git init → 冻结模型+全新 held-out ≥10 只报一次 → 可分离交互+联合判据 → 适用域 → load_cases 进 schema → 极端几何补收敛 → 应力目标改形态或放弃。
- **★ 盲预测预注册（D36 方法论，长期生效）**：求解前把模型预测写死归档（`d36_prediction_preregistered.json` **永不改写**），
  求解后另写 `_resolved.json` 结算。脚本自带 kill-check（复算已知点对不上就不许用其余输出）。
- **D36 关键读法**（全档：当日日志 §17/18、BASELINE.md §2.7、看板 r52）：
  ① 逐度斜率 0.0094→0.1340 加速 ⇒ 曲率在增长，固定阶多项式追不上，40° 残差**不是基阶问题**；
  ② 主目标 test 3.01→**2.63 %**（配对 CI 跨 0，只报「方向一致的改善」）；
  ③ ★ **副指标退化 100 % 集中在一条样本**（`sweep40_taper040`）：`s²` 是标量 log 目标上的单一系数、无分量信息，
     位移原低估而 max_w/vM 原高估 ⇒ 抬系数同号三者一起上移。**test 只有 6 条时，平均 MAPE 会把「5 条不动+1 条崩」讲成整体变差**；
  ④ ★ **三次基判据对撞不换**：LOO@35 选 cubic 但双重外推考点 +1.09→+16.08 % ⇒ **挑战者两侧判据互斥即视为未证明**，现役不动；
  ⑤ 条件数口径：标准化 → 贪心 Gram-Schmidt 按秩剔除 → 再报 cond（lin 1.7 / quad 9.6 / cubic 70.5，剔 `is_T`+`n_web`）。
- **★★ D37 方向转向（2026-10-24 老王拍板）**：外部专家评估指出**没有考卷接口**（无任务输入 L2/L3、无 evaluate(candidate)、无榜单协议）。拍板：① **代理模型线完全冻结**（held-out 撤销，baseline_d36_final.json 降级可学性附录，KPI 换 TSR/FPR/修复/拒答/澄清）② B/C 子集移出对外文档 ③ 暂不改名加后缀标注。M14 准入②③④撤销（R1/R2/R3 随拍板吸收），R5/R7 保留。**新计划 = `FEM-Bench-Aero/ROADMAP.md`**。W1–W3 已收口（详见当日日志 21–23 节）。
- **★★★ W4c 修契约与口径（专家第三轮纠偏，2026-10-24 深夜，commit efa2b6f）——当前进行到 W4c 收尾/W4d 待跑**：
  专家第三轮（FEM-Bench-Aero第三轮复评与执行纠偏_2026-10-24.md）实锤：① 全链路径包装候选静默解成默认翼盒（skip_solve 修了全链没修）② bc/analysis/extra 漏判（柱壳候选 extra={} 端剪端弯全丢仍 23/23 PASS）③ L3 任务 mesh/load 键空完全不判 ④「冒烟 2/2」是旧快照（全量 2/5 SFR、全链 0/5 MSR）⑤ key 硬编码/无 response_format/model=auto 不可引用。评分卡 22/30 No-Go。
  **W4c 已落地**：FEASpec.from_dict 严格化（缺 structure/family 未知 => raise）；evaluate 全链解包+contract 闸（bc 空/柱壳缺 end_shear 不求解）；spec_fidelity 补 bc/analysis/extra（gold 权威全键判，L3 也判）；**负控 14/14**（新增 NC-9..13）；score_baseline partial 警告+underpowered（R12）；gen_candidates prompt 补 bc/extra+response_format+key 入 env；gate3 n_gated_pass 15→49；L3 boundary_holdout 统一（id_test 清零）；fetch_data tarfile；validate_schema UTF-8。
  **红线新增 R9–R14**（SFR≠MSR≠TSR / 候选契约校验 / 成绩单全覆盖 / n<20 不判 value_added / 模型 id 必录 / skip_solve 不得称基线）。
  **待办（已全部收口）**：W4b 成绩单（C-017，L1 smoke SFR 0/19）→ W4d L3 主基线（commit b2e9b74）。
- **★★★★ W4d L3 主基线收口（2026-10-25，commit b2e9b74，C-020，评分卡 29/30）——ROADMAP W1–W4 全部收口**：
  老王两项口径拍板：① **工程层判+配置层只报**（EXEC_CONFIG_KEYS=mesh gmsh 键/analysis 执行键/extra 内部编码键/
  pressure 方向 → REPORTED；死字段 stringer_* 豁免（ns=0）；元数据自创键白名单；语义编造照罚；**bc 只对 wingbox 判
  ——实锤 pipeline 不消费 spec.bc，非翼盒族 gold bc 是死模板值**）② **澄清题问对=对（clarify_keywords 落盘）、编造=错**。
  生成 = gen_candidates_v2.js（pin glm-5.3-flash；**SDK 无 json_schema logits 约束 ⇒ 约束解码 = json_object + ajv 校验
  + 错误反馈修复循环 ≤3 轮**，CLAIMS 如实标注）。负控 **15/15**（NC-14 工程层口径四探针）。
  **成绩单（n=30，考卷 v3）**：TSR 18/30 (60%)、SFR 16/25 (64%)、**全链 MSR 11/30 (36.7%)**（翼盒有 spec 12 条中 11 条
  全绿 fidelity≤0.024%；13 条 pipeline 失败全为模型 spec 质量——语义自创键/字段错位/单位换算，归因落盘
  msr_pipeline_failure_attribution.json）、**value_added Δ+36.7pp PASS**（T1 地板同任务集 23.3%，n≥20）。
  考卷三轮实锤修正（第三轮后停止迭代）：ec 伪缺 bug / CFRP 材料卡 11 常数从 gold 写全 / **网格尺寸 gold 4.0 硬编码成
  「3 mm」+ offcentre 孔位**。
  **坑**：① 全链 MSR 必须 venv 解释器（系统 Python 无 gmsh 假报 pipeline 失败）② 判分层豁免的元数据键必须在全链
  FEASpec 构造前剥离（dataclass 拒收未知键，两层口径要一致）③ SDK response_format 只有 json_object|text。
- 下一步候选（待老王拍板，按 ROADMAP）：
  ① W5 评审包：成绩单对外化（盲测协议预注册 D36 方法论沿用）+ 专家第四轮复评材料。
  ② v1.1 数据放量：L3 考卷扩量（按参数覆盖补 NL 变体）+ ID 内插留出 + 边界 holdout 扩容。
  ③ MSR 失败 13 条的修复率维度（KPI 含「修复」）——候选 spec 一轮反馈修复实验。
  ④ 翼盒「新形式」锚点：随 v1.1 数据放量按「参数覆盖」补，不再按 MAPE 补。
- **明确禁止**：**`sweep` 轴停手**（D34 换基 / D35 补交互 / D36 补中间站，三轮各付一次代价、边际为零）；
  不要再加交互特征（−36.54 %）；不要补 vM 峰值；不要在补数据的同时改模型形式（混叠）。
- 新形式必须自带退化自检（check_forms 常设闸）。
