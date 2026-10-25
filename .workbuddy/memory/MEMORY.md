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

## 协作约定
- 决策环节**先可视化梳理** → 更新看板（DATA 区），必跑 `node _dash_check.js`。
- **里程碑收口三同步：看板 + 两份 README + 记忆**。岔路口先问老王（推荐项+理由+代价，不摆中立选项）。
- 落盘三铁律：拍板即落盘／大输出不进对话只留路径／日志带检索词（线名+实体+日期）。

## 当前状态（2026-10-25）
- **代理模型线（M7/M14/D01–D37）完全冻结**（D37 拍板）；对外 KPI = TSR/FPR/修复/拒答/澄清。计划看 `FEM-Bench-Aero/ROADMAP.md`。
- **W1–W5c 全部收口**；**对外 headline = C-029（v6c，exam 25 条）**：考卷 v6c（C-030，sha `9c1faa3a…`）× `candidates_l3_v6c`。
  exam **TSR 23/25 (92.0%)**、TSR **CI95 [80.0, 100.0]**、SFR 20/22、三栏 **boundary 6/6 · extrapolation 11/13 · interpolation 6/6**；
  dev 23/30（**下界**）。`n_unresolved` 7→**0**、`underpowered=False`、FPR 编造 0/4。
  **MSR（R35 四行，原始/剔除 solver 并列）**：exam **19/22 (86.4%)** → 剔 solver **19/21 (90.5%)**；dev **19/29** → 剔 **19/26**；full **38/51 (74.5%)** → 剔 **38/47 (80.9%)**；CI95 MSR **[72.7, 100.0]**。exam 分母 22 = 25 − 3 澄清题（R23）。
  **★★ value_added 双尺度（R44，第九轮 §3.3 收口）**：任务级地板 T0/T1/T1+ **全 0/25**、族内 oracle 也 **0/25** → LLM 92.0%；
  **字段级 85.93% → 99.34%（Δ+13.4 pp）**，两个尺度都过 10 pp。**「地板恒 0」≠「地板太弱」**：`spec_fidelity` 全或无 ×
  族内参数逐条唯一 ⇒ 不读输入策略的 TSR 天花板就是 0（T1+ 已命中 86% 字段、最好一条只差 1 个字段，仍 25 条无一全对）。
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
- **红线 R1–R46**（R42 headline 唯一 / R43 投影不冒充实测 / R44 value_added 双尺度 / R45 MSR 字段齐 / R46 key 决策留痕）；R25 artifact 入 `reports/`；R26 `check_claims.py`（**负控 41/41**，含 NC-23..39；语义 **33** 项；22 claims / 34 artifacts）；R27 官方/诊断分文件；R28 旧候选不评新考卷；
  **R29 语义计数必须自检**（`check_claims.py --semantic` 默认开，**29 项**，期望值全从 artifact 实读；
  **缺 MSR ⇒ S-19/S-20 必须响亮失败，不得静默消失**，NC-36 三端守）；
  **R30 跨口径不得直接比**；**R31 生成前 key 预检 + 1 条冒烟**；**R33–R41** 见 CLAIMS 正文。
- **判分无放水**：`spec_fidelity` 所有循环按 **gold 键集**遍历 ⇒ 单边缺=FAIL、自创键=FAIL，候选**不能靠漏写缩小分母**
  （`n_fields` 差异来自自创键**加**进去）。这条要能随时复述。
- **扩卷缺口（实测）**：55 条全 L3 化后 exam 上限 **19**（差 1 条到 n≥20）；推荐 6 条 `interpolation_test` 内插留出 ⇒ 25，**三栏分报**。
- 生成口径：SDK 无 json_schema logits 约束 ⇒ json_object + ajv（放宽 required）+ 错误反馈修复 ≤3 轮；pin `glm-5.3-flash`；**`gen_candidates_v2.js --limit` 默认 30**，v6 55 条必须显式 `--limit 55`。
- **key 出处（2026-10-25 查实）**：`WORKBUDDY_PUBLISHABLE_KEY` 不是模型厂商 key，是 **WorkBuddy 云服务应用「FEM基线评测」`wbapp_Tl8jf0GeqRmnK59Hr64PuS` 的 publicConfig.publishableKey**（`wbpk_<appid中段>_<secret>`，**无权限语义**，服务端靠 Origin 校验）⇒ 取法：`workbuddy_cloud_service` action=activate + reuse 该 appId 回读（inspect 不返回 key）；或看仓库遗留 `gen_candidates.js:13` 的 fallback（**与线上同值、未轮换**）。**无 dotenv ⇒ `.env` 文件根本不读**，只认真实环境变量；已 `setx` 到用户级（新开窗口生效）。
- 已知红线级坑：**「总数对上」≠「复现对了」**（`_bridge_v3/tasks` 打 exam 同为 5/11 但 dev 10/19）；**拿现态判历史产物必假红/假绿**（NC-21 用当前卷核旧成绩单分母）；**负控检查对象要动态取**（NC-15 曾静默消失）。
