# 工程长期备忘（蜗子 / 老王）

> 只留**跨会话仍要生效**的东西；逐批过程细节在 `.workbuddy/memory/YYYY-MM-DD.md`。
> 2026-10-25 压缩重写（代理模型线已冻结，D01–D37 历史细节查 `MEMORY_ARCHIVE_20261024_full.md` 与当日日志）。

## 环境铁律
- 🚨 **Abaqus agent 内失败头号嫌疑 = WorkBuddy 沙箱注入 `tsbx.dll`**（pre.exe `__fastfail`；签名：~19s 延迟 + Input File Processor error + .dat 无错 + ODB 空骨架）。`dangerouslyDisableSandbox` 无效。可靠路径 = **WorkBuddy 外普通 cmd 手工 bat**（solve + `abaqus python abaqus_odb.py`）。
- **手工 bat 顺序**：先 `resummarize.py --roots …` 再 `make_dataset`。反了不报错、只打 `max|u|=n/a` ⇒ 收口必须逐目录数文件（**6 个**）。
- numpy/gmsh 用 venv `…\envs\default\Scripts\python.exe`（系统 Python 无 gmsh 会假报 pipeline 失败）。ccx = `tools/calculix/calculix_2.23_4win/ccx_static.exe`；Abaqus = `D:\Program Files\SIMULIA\Commands\abaqus.bat`。
- **绝不并行跑 abaqus/ccx**（静默空转、rc 仍 0）。只认真 FRD / 真 ODB 读数，不信「命令返回 0」。
- ccx 壳展开成实体：方程 ≈ 14.9×壳节点；本机 33GB 上限 ⇒ ≤158,548 节点可算、188,674 已失败。

## 验证纪律
- 只认独立复算：平衡（唯一不变量）+ 解析解 + 双码交叉。**门禁不许印没量过的数字**（命令+数字+产物路径落盘）。
- **判据按族**：双码载荷口径不可跨族套用 —— 翼盒 500 N 端载+根截面反力；柱壳 内压+端弯+端剪（D20 剔端载环）；开孔板 面内拉伸；加筋板 1000 N。套错产出 9900 % / 700 % 整片假 FAIL。
- 双码位移：barrel 登记判据 = D20 `structure_peak`，model-wide `max|u|` 只 REPORTED NOT GATED；小位移区相对误差骗人，先看绝对差。
- 变体结果完全相同 = 报警信号；改网格/判据 ⇒ 重签基线但必须留档旧基线（D10）。
- 闸门报数报**判据组数**不是快照条数。回看最后一行 VERDICT 前那句话。

## 契约与数据集
- 唯一契约 `spec.FEASpec`；求解器选择在写 deck 之前；结果两码归一 `{nodes:{DISP,FORC,STRESS}}`。spec 加字段 ⇒ spec_sha256/truth.json 全档失效须重导。
- `modeling/`(ccx 可发布) + `_xval/`(abaqus 禁发布)；case 六件套 = spec/step/msh/inp/results/truth。门禁：minJ ≥ 0.30 且零 tri3／平衡 < 1e-3%／双码 `max|u|` 差 < 1% + vM 逐节点中位差 < 5%。
- **划分是规则**：`manifest.HOLDOUT_REGIONS` + `split_of(spec)`（吃 spec 不是 case_id，首个命中即定）；eval 断言复现 D12。
- **去重指纹** = msh 逐字节 + SHELL SECTION 厚度表 + `*ELASTIC` 材料律块（只按 mesh 判会误删壁厚变体）。
- 常用：`check_forms.py`／`verify_hole.py`／`verify_barrel*.py`／`check_semantics.py`／`verify_dataset.py`／`eval_dataset.py`／`make_manifest.py --json <path> --md`／`make_dataset.py --solver ccx|abaqus`／`run_pipeline.py --deck-only`。
- **`check_forms` / `make_manifest` 不传 `--json` 就只打印不写盘**。

## 高价值坑（跨族通用）
- **「模型不行」第一嫌疑 = 特征没给全**（M7：漏 `is_T`/`web_pos` 使 test 14.8 %、补齐后 10.7 %，结论反转）。诊断假设与被测对象必须同口径。
- **标准化欧氏距离不能当可信度指标**（corr(distance,|err|) = −0.046）；必逐轴判训练包络。
- **补覆盖点 ≫ 补同质样本**；**标准化系数不是幂指数**（指数 = `w / sd(log x_f)`）；**交互项必须用实测单轴响应相乘**。
- **厚度维退化取决于载荷口径不是轴的属性**：载荷随 t 缩放则与膜刚度精确抵消；载荷固定则 `u∝1/t`。
- **只打印不参与判定的检查不是检查**（`verify_dataset` pairing MISMATCH 而 `all_ok` 不含它 ⇒ 仍 PASS）。
- **铺层平衡必须按有符号配对**（`a>90°` 折回 `180−a`）；准各向同性可用 `G=E/(2(1+ν))` 独立验 CLT。
- **翼盒坐标系：x 弦向 / y 法向（载荷 DOF 2）/ z 展向**。`max_w` 是展向位移；但 `max|v|/max_disp`≈0.999 ⇒ `max_disp` 本身已是弯曲挠度。
- **峰值是「离散选择」不是「光滑泛函」**（31 条翼盒 `max_disp_node` 21 个不同节点）⇒ 给 vM 峰值补样本白费。
- **报 MAPE 必须同报中位+最大+bootstrap CI**；跨里程碑比 MAPE 必须先对齐 test 集。
- **共线模型要报条件数**（先标准化再按秩剔除）；**`_wingbox_planar_shape` 返回 `(tip_chord_ratio, sweep_deg)`**，解包反了全案判成锥度 0。
- **★ 改划分规则后必须 grep 出所有「把旧结论硬编码进期望值」的检查**；修法不是改期望值而是守**二分两端**。
- **★ 结论依赖数据集的脚本重跑即毁档**：探针输出名必须带里程碑标签 + 支持 `--out`。
- **★★ 往结构化数组插条目：锚点唯一 ≠ 锚点正确**：必须断言相对位置（`index(HEAD) < index(新) < index(TAIL)`）。
- **看板数据字段一律脚本回读**。
- **★ 新闸上线必须同时测「自比/A==B」用例**：R53 的可比性闸把 `comparability(x,x)` 也拒了（旧批次 `prompt_sha256` 未记录）⇒ NC-29/NC-35 当场转红。约束「A 与 B 不同」之前先想 A==B 该不该放行。
- **★「修了缺陷」必须证明没顺带动难度**：C-032 与 C-029 逐题类别完全相同，才能说「修的是隐患、不是补分」；只报分数变化区分不了这两种。
- **★ 分母小的那个 pct 更好看**：MSR 是条件通过率（分母 = 产出 spec 的非澄清题），被排除的往往是**失败题** ⇒ 95.2% 能「高于」90.9% 而 TSR 低 4 pp（R54）。
- **★ 往结构化数组末尾追加项要补尾逗号**：最后一项无逗号，直接插其后 ⇒ 语法错（看板 r68 踩过一次）。插完必须跑该文件的语法/自检。
- **★ `failed_fields` 的路径根不统一**：`extra.*` 挂在 spec 顶层，`params.*` 实际在 `spec.structure` 下。按字面路径取 ⇒ 全 None 且被误分类。下游工具必须两种根都试并记录命中根。
- **★ 比率/计数必须与成绩单自报值交叉核对**：dev 通过数用「spec_pass 计数」得 22→21，成绩单是 23→22 —— **TSR 把 `clarify_ok` 也算通过**。口径不同要 rc≠0，不能各说各话。

## 协作约定
- 决策环节**先可视化梳理** → 更新看板（DATA 区），必跑 `node _dash_check.js`。
- **里程碑收口三同步：看板 + 两份 README + 记忆**。岔路口先问老王（推荐项+理由+代价，不摆中立选项）。
- 落盘三铁律：拍板即落盘／大输出不进对话只留路径／日志带检索词（线名+实体+日期）。

## 当前状态（2026-10-25）
- **代理模型线（M7/M14/D01–D37）完全冻结**（D37 拍板）；对外 KPI = TSR/FPR/修复/拒答/澄清。计划看 `FEM-Bench-Aero/ROADMAP.md`。
- **W1–W5d 全部收口**；**对外 headline = C-032（v6c × `candidates_l3_v6c_glm_p2`，prompt v2 代）**：考卷 v6c（C-030，sha `9c1faa3a…`）。
- **★★ 数据集 v1.1 = 64 条（数据集 ≠ 考卷）**：新增 9 条**内插留出**（55→64，train 25 / val 17 / **test 22**，train 与 val 一条未动）。划分用**声明式**：新 spec 打 `extra.split_tag = v11_interior_holdout`，`manifest.split_of()` 在族谓词**之前**认它——不能用参数谓词（内插点每轴都在包络内，数值谓词会把 D12 锁定的 11 条重新划分）。**考卷仍是 v6c 的 55 条任务**，v7 待建。**内插物理判据**：`_v11/verify_v11_interpolation.py`，峰值量必须严格落在两锚点之间（7/7 PASS）——不依赖 gold，查「参数有没有真的进模型」。**⏸ 双码待外部跑**：9 条只有 ccx，`verify_dataset` 报 `9 modeling-only ⇒ CHECK`；deck 已备，`_v11/run_v11_abaqus.bat` 必须在 WorkBuddy 外执行。
- **★ 判据的假设会冒充模型的错**：柱壳长度轴上 `max_von_mises` 三点 249.35/248.16/249.40（差 0.5%，基本持平）——根部峰值由端部弯矩÷截面模量决定，都不随长度变 ⇒ **应力在长度轴不单调**，该轴只判位移、应力只报。
- **★★ 跨模型榜单 = C-034（`reports/w5d_leaderboard.{json,md}`）：三列并排是硬要求（R56）**——同一对模型**三个口径排名相反**：任务级 TSR 92.0% vs 88.0%、字段级 99.34%(PASS) vs 90.94%(BELOW)、**条件 MSR 90.9% vs 95.2%（deepseek 反而更高，因分母少 1 条且那条是失败题）**。⇒ **只引任一列都能得出「某模型更强」**，必须并排 + 归因。
- **★★ prompt 已到顶 = C-035（别再改措辞）**：为清零 C-033 剩余失败做了 **v3**（数量铁律扩到尺寸 + 澄清列表准入）与 **v3b**（+5 步自检放 SYS 末），**exam 澄清题三版完全一致**（glm 3/3/3、deepseek 2/2/2），但失败点在迁移（多问 → 填 0 → 未收敛）⇒ 打地鼠、零收益 ⇒ **否决、回退 v2**（sha `ce225186…`）。剩余失败属**模型行为**（缺失信息处理），要动只能改 harness 口径（语义回填闸 → D7 待拍板）。**R57 扩写：prompt 变更必须消融留档、净收益 ≤0 否决、否决后 sha 回基线（S-43/NC-48）**。
- **★ 别把「本族合法键」当成「本题该问的键」**：`n_stringers_per_skin` 在翼盒族合法，但题面没提长桁时登记为「不该问」是对的——判分元数据没问题，是模型多问（自我修正 D6 的前提）。
- **★ dev 反向变化必须机器定位（R55）**：C-032 dev 23→22 实为 **+1/−2**——`stiffened_800x600_str3` 由 600/800 纠正为 800/600（题面 R41 修正被兑现，不重生成恒为 0）；两条柱壳 `extra.end_moment` 写 5e4/5e6 而 gold 5e7（×10⁻³/×10⁻¹ 量级偏差，与 prompt 无关）。产物 `diagnostics/dev_reversal_v6c_p2.md`，S-41/NC-47 守。
- **★★ 双模型同 harness（R53 合规，`prompt_sha256 = ce225186…` 两者逐字相同）**：C-032（glm）exam **23/25 (92.0%)** / MSR 20/22；C-033（`deepseek-v4-pro`）exam **22/25 (88.0%)** / MSR 20/21（**条件分母 21**）。**2×2 = both 22 / only_a 1 / only_b 0 / neither 2** ⇒ 纯损失非互补；**两模型 `spec_pass` 同 20/25** ⇒ 差距不来自建模能力。**C-031（prompt v1，20/25）与 C-032/C-033 不可相减**（R53）。
- **★ R50 修复的净效果可精确断言**：删「未提长桁→0」授权后，**glm 的 exam 逐题类别与 C-029 完全相同**（⇒ 修的是对别家的隐患，92.0% 不依赖坏 prompt）；**deepseek 回收 +2**（`n_frames`/`n_stringers`，正是 C-031 编造的两条）⇒ **C-031 的 80.0% 有 2 条是 prompt 下界**，`n_ribs` 那条才是模型侧。
  exam **TSR 23/25 (92.0%)**、TSR **CI95 [80.0, 100.0]**、SFR 20/22、三栏 **boundary 6/6 · extrapolation 11/13 · interpolation 6/6**；
  dev 23/30（**下界**）。`n_unresolved` 7→**0**、`underpowered=False`、FPR 编造 0/4。
  **MSR（R35 四行，原始/剔除 solver 并列）**：exam **19/22 (86.4%)** → 剔 solver **19/21 (90.5%)**；dev **19/29** → 剔 **19/26**；full **38/51 (74.5%)** → 剔 **38/47 (80.9%)**；CI95 MSR **[72.7, 100.0]**。exam 分母 22 = 25 − 3 澄清题（R23）。
  **★★ value_added 双尺度（R44，第九轮 §3.3 收口）**：任务级地板 T0/T1/T1+ **全 0/25**、族内 oracle 也 **0/25** → LLM 92.0%；
  **字段级 85.93% → 99.34%（Δ+13.4 pp）**，两个尺度都过 10 pp。**「地板恒 0」≠「地板太弱」**：`spec_fidelity` 全或无 ×
  族内参数逐条唯一 ⇒ 不读输入策略的 TSR 天花板就是 0（T1+ 已命中 86% 字段、最好一条只差 1 个字段，仍 25 条无一全对）。
- **★ 第二模型 C-031（`deepseek-v4-pro`，同卷 v6c，35 个 id 实测取）：exam TSR 20/25 (80.0%)**、SFR 20/25、dev 22/30；MSR exam 20/22、dev 22/28、full 42/50、**solver 0 条**。**supporting，不作 headline（R48）**。
  **★★ 它的产出不是分数而是三条归因**：①两模型 `spec_pass` **都是 20/25** ⇒ 12 pp 差**不来自建模能力**；
  ②2 条 `spec_fail` **同题同字段**、dev `stiffened_panel_800x600/_str3` 的 `length/width` 也**两模型同错**（R41 题面）
  ⇒ **失分主因是题面/prompt，不是模型差异**；③唯一实质差异 = 缺失信息处理（glm 澄清 3/3 vs 本模型编造 3/3，FPR 100%）。
  逐题 2×2：both 20 / only_a 3 / **only_b 0** / neither 2 ⇒ **纯损失不是互补**。
  **★ 我方 prompt 缺陷（必修）**：SYS 里「未提长桁→长桁数=0」**直接授权**把 `n_stringers` 填 0，而题面期望澄清 ⇒ **prompt 与 `expected_clarifications` 打架**；glm 没被诱导、dsv4pro 被诱导 ⇒ 不能记成模型错。
  **★ 反直觉**：C-031 的 **exam MSR 90.9% > C-029 的 86.4%** 但 TSR 低 12 pp——MSR 分母 22 **排除 4 条 clarify 题**，而它编造的 3 条**恰好全在这 4 条里** ⇒ **TSR 与 MSR 分母不同（25 vs 22），排名可相反，不得互相替代**。
- **★ 92.0% 不是「模型变强 24 pp」**——bridge 四格拆开（`reports/diagnostics/bridge_w5c_table.md`，**唯一允许相减的场景**）：
  A v6b×旧候选×旧口径 **17/25** → B 新口径 **18/25**（判分修正 blade 死字段 +1，唯一翻转 `wingbox_str5`）
  → C v6c×旧候选 **18/25**（**考卷修复对已定型候选 +0：改题面必须配重生成才有收益——本表最有价值的一格**）
  → D v6c×新候选 **23/25**（重生成 +5 = R34 补 prompt 键名 4 条 + R32 补题面依据 1 条）。
- **剩余 2 条 exam 失败全是 C 类（模型侧）**：`cfrp45s_d40` 的 `params.layup` 写成标量 `2`；`web1_offcentre` 的 `extra.end_torque` 自创键。
  **卷子已无可解性缺陷 ⇒ 92.0% 是「缺陷已清」的成绩，不是又一个下界。**
- **★ W5c 自查出新缺陷（第八轮报告没发现）**：加筋板模板 `f"{width} × {length}"` ⇒ 题面「600 × 800」而 gold `length=800/width=600`；
  两数都在题面出现过（`num_derivable` 判 derivable）但**字段角色不可判**，模型按惯例读反被判错。
  ⇒ **R41 数值角色** + RUBRIC **§7.3** + `r32_audit._role_pos()` 闸。影响 **2 条 dev、0 条 exam**；模板已修，v6c 候选不重生成。
- **R33 改两端口径**：exam 必须 0 违规；非 exam 允许违规但**白名单逐字相等、只许缩小**（新违规自动变红）。
  审计：v6b all=**8** → v6c all=**4**（全 dev）→ v6c exam=**0**（rc=0）。`r32_audit` JSON 带 `violations_by_task`。
- **★★ 比率分母藏 bug**：`if r.get('某字段')` 式的列表推导会**静默排除**整类样本。实证：字段级命中率跳过 `fabricated` ⇒ C-029 与 C-031 算出同一个 99.34%（真值 87.42%）。**分母必须显式分流 + 落盘构成 + 加和闭合**（R47）。
  同类：跨模型时 **TSR 分母 25、MSR 分母 22** ⇒ 排名可以相反（实证 80% vs 92% 但 MSR 90.9% vs 86.4%）。
- **★ 跨模型对比的价值在归因不在排名**：同题同字段复现 ⇒ 题面/prompt 的错；只有一方错 ⇒ 模型个性。**先看 2×2 的 `only_b`，再看分数**。
- **★★ 判据别用自然语言表述**：S-29（headline 唯一）第一版按「正文含某词且不含否定词」判，把 **C-029 自己**过滤掉了
  （它写了「不是实测」「不是又一个下界」）；改结构化后，C-028 的 status 里塞的**指针**又冒充了第二个 headline。
  ⇒ **只认结构化字段 + 自指标记**（`（对外 headline）`），并配反向负控（NC-38）。
- **★ 成本判断也要实测**：「轮换 key ⇒ provenance 重签 ⇒ 代价高」错两处——endpoint 是**硬编码常量**、
  `provenance` **不记 key/endpoint** ⇒ 换 key 不需要重签任何 artifact。**凭印象估的代价会挡住本来该做的事**（R46）。
- **★ solver 桶是「候选相关」的，不是题目固有属性**：同题 `barrel_d2000_l2000_str12_frm4` 在 v6b 旧候选 4.2s 就被 pipeline 拒
  （class=model），v6c 新候选算到 169,606 节点才撞 158,548 阈值（class=solver）⇒ **「剔除 solver 后的分母/得分」同样不可跨版本直减**。
- **★ 观测量也可能一直是空的**：成绩单顶层 `msr` 键在 W5c 之前**恒为 null**（score_baseline 不写、msr_l3 只写 msr_section）；
  同类还有「先 bootstrap 后 msr」会静默产出 null 的 MSR CI ⇒ **正确顺序 score → msr → bootstrap**，且**注释与实现不符要当 bug 记**。
- 考卷 v6b（C-027，tag `v1.0-l3-v6b`）保留为历史卷；v6c = v6b + **10 行**（4 条 NL 补 R32 缺项 + 6 条 `split_v2→interpolation_test`），
  L1/L2 110 条逐字节不变，`_verify_tasks_v6c.py` **PASS**（含「题面只做 insert 不改写」的 difflib 断言）。
- **官方 artifact 唯一出处 = `feagpt_repro/reports/`**（入库），诊断放 `reports/diagnostics/`（**R37：官方文档不引 `eval_runs/`**）；
  入口 `reports/INDEX.md`（官方 vs 诊断）。
- **C-028（v6b，17/25 = 68.0%）已降级为 `diagnostic lower bound`**（第八轮 D1），**与 C-029 不可相减**：
  同 25 条 exam id 但**题面已改**（paper sha 不同，`compare_scorecards.py` 增了这条硬理由）；与 C-021 的 45.5% 另加 exam 11→25、族构成变化。
  **C-025 v5 重打分 4/11 是诊断不是成绩**（旧候选不能评新考卷，R28）。
- **红线 R1–R57**（R42 headline 唯一 / R43 投影不冒充实测 / R44 value_added 双尺度 / R45 MSR 字段齐 / R46 key 决策留痕 / **R47 比率分母显式落盘且加和闭合** / **R48 第二模型只作可重复性证据、不得事后择优** / **R49 双尺度结论相反必须标 `verdict_split`** / **R50 prompt 不得盲填、不得注入 `expected_clarifications`** / **R51 模型标签读实测** / **R52 分母四类拆开 + 两层闭合** / **R53 改 harness 必须全量重跑（`prompt_sha256` 三件对齐才可比）** / **R54 MSR 是条件通过率：口径落盘 + 排除项点名 + 分母不同不得直减/排名** / **R55 prompt 修复逐题回归、dev 反向必须定位并闭合** / **R56 跨模型榜单三列并排、分母不等不出 Δ** / **R57 prompt v3 不得注入 `expected_clarifications`**）；R25 artifact 入 `reports/`；R26 `check_claims.py`（**负控 50/50**，含 NC-23..48；语义 **44** 项；27 claims / 49 artifacts）；R27 官方/诊断分文件；R28 旧候选不评新考卷；
  **R29 语义计数必须自检**（`check_claims.py --semantic` 默认开，**29 项**，期望值全从 artifact 实读；
  **缺 MSR ⇒ S-19/S-20 必须响亮失败，不得静默消失**，NC-36 三端守）；
  **R30 跨口径不得直接比**；**R31 生成前 key 预检 + 1 条冒烟**；**R33–R41** 见 CLAIMS 正文。
- **判分无放水**：`spec_fidelity` 所有循环按 **gold 键集**遍历 ⇒ 单边缺=FAIL、自创键=FAIL，候选**不能靠漏写缩小分母**
  （`n_fields` 差异来自自创键**加**进去）。这条要能随时复述。
- **扩卷缺口（实测）**：55 条全 L3 化后 exam 上限 **19**（差 1 条到 n≥20）；推荐 6 条 `interpolation_test` 内插留出 ⇒ 25，**三栏分报**。
- 生成口径：SDK 无 json_schema logits 约束 ⇒ json_object + ajv（放宽 required）+ 错误反馈修复 ≤3 轮；pin `glm-5.3-flash`；**`gen_candidates_v2.js --limit` 默认 30**，v6 55 条必须显式 `--limit 55`。
- **key 出处（2026-10-25 查实）**：`WORKBUDDY_PUBLISHABLE_KEY` 不是模型厂商 key，是 **WorkBuddy 云服务应用「FEM基线评测」`wbapp_Tl8jf0GeqRmnK59Hr64PuS` 的 publicConfig.publishableKey**（`wbpk_<appid中段>_<secret>`，**无权限语义**，服务端靠 Origin 校验）⇒ 取法：`workbuddy_cloud_service` action=activate + reuse 该 appId 回读（inspect 不返回 key）；或看仓库遗留 `gen_candidates.js:13` 的 fallback（**与线上同值、未轮换**）。**无 dotenv ⇒ `.env` 文件根本不读**，只认真实环境变量；已 `setx` 到用户级（新开窗口生效）。
- 已知红线级坑：**「总数对上」≠「复现对了」**（`_bridge_v3/tasks` 打 exam 同为 5/11 但 dev 10/19）；**拿现态判历史产物必假红/假绿**（NC-21 用当前卷核旧成绩单分母）；**负控检查对象要动态取**（NC-15 曾静默消失）。
