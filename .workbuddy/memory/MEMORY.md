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
- **W1–W5b-4 全部收口**（key 查实 → 55 条候选 → 打分/CI = **C-028**）；下一步 **W5b-5 第二模型**（换 `--model` 即可），计划见 `FEM-Bench-Aero/W5B_PLAN.md` §3。
- **考卷 v6b 已冻结**（C-027，tag `v1.0-l3-v6b`）：L3 55 条、exam **25 = boundary 6 + extrap 13 + interp 6**，
  内插**全给翼盒**（v6 的 2/2/1/1 把三族 train 抽空、T1 地板只剩 1/4 族可算 ⇒ 作废留档 `papers/tasks_v6.jsonl`）。
  口径 RUBRIC **v4.2** §1.1。**★ 内插考题 `split_v2` 仍是 train ⇒ 任何「train 池」必须先剔 `exam_stratum`**，
  否则 T1 检索到自己（地板 100%）把 value_added 算成负数。
- **官方 artifact 唯一出处 = `feagpt_repro/reports/`**（入库），`eval_runs/` 只作工作目录；入口 `reports/INDEX.md`（官方 vs 诊断）。
- **对外 headline = C-028（v6b，exam 25 条）：TSR 17/25 (68.0%)、SFR 14/21、exam MSR 10/21、全链 MSR 25/44**，TSR **CI95 [48.0, 84.0]**，
  n=25 ⇒ `underpowered=False`（R12 首次可判）。三栏 **boundary 5/6 · extrapolation 7/13 · interpolation 5/6**。
  **★ 与 C-021 的 5/11 (45.5%) 绝不可相减**（R30，compare rc=3）：差异含两变量 —— ①考卷 30→55、exam 11→25；
  ②**题面 26/55 新增「坐标系」、25/55 新增显式方向 `[x,y,z]`（W5b-3a 消歧）⇒ 难度下降**。45.5% 降为历史口径。
  **★ 68.0% 是「含已知缺陷的下界」**：`open_hole_panel` exam **4/4 全败**，同因生成器 SYS prompt **从未列出** `params.hole_d/hole_x/hole_y` 键名
  （M7 教训复刻：模型不行第一嫌疑 = 特征没给全 ⇒ 修 prompt 可回收最多 4 条/+16pp）；2 条 wingbox 败于 `airfoil.stringer_flange_width`
  —— **gold 有值但题面只给高/厚**，模型按「不得编造」正确处理却被判 fail ⇒ 新红线 **R32**（gold 判分字段必须可从 NL 推出）。
  **solver 3 条 = 柱壳 143,426/158,548 节点超本机内存**（已知阈值 158,548），算力边界非模型失败；剔除后参考 MSR 25/41 (61.0%)。
  复现：`score_baseline.py --tasks reports/papers/tasks_v4.jsonl --report reports/baseline_scorecard_L3_v4.json`（+ `msr_l3.py` 同参数，18 min）。
  **C-025 v5 重打分 4/11 是诊断不是成绩**（旧候选不能评新考卷，R28）。
- **红线 R1–R32**；R25 官方 artifact 必须入 `reports/`；R26 `check_claims.py` 自检（**负控 31/31** 含 NC-23..29）；R27 官方/诊断分文件；R28 旧候选不评新考卷；
  **R29 语义计数必须自检**（`check_claims.py --semantic` 默认开，17 项，期望值全从 artifact 实读）；
  **R30 跨口径不得直接比**（C-021=11 / v6 boundary+extrap=19 / v6 headline=25 三个数，`compare_scorecards.py` rc=3 拒绝）；
  **R31 生成前 key 预检 + 1 条冒烟**，候选未覆盖全卷的成绩单必须标 `partial_candidates`。
- **扩卷缺口（实测）**：55 条全 L3 化后 exam 上限 **19**（差 1 条到 n≥20）；推荐 6 条 `interpolation_test` 内插留出 ⇒ 25，**三栏分报**。
- 生成口径：SDK 无 json_schema logits 约束 ⇒ json_object + ajv（放宽 required）+ 错误反馈修复 ≤3 轮；pin `glm-5.3-flash`；**`gen_candidates_v2.js --limit` 默认 30**，v6 55 条必须显式 `--limit 55`。
- **key 出处（2026-10-25 查实）**：`WORKBUDDY_PUBLISHABLE_KEY` 不是模型厂商 key，是 **WorkBuddy 云服务应用「FEM基线评测」`wbapp_Tl8jf0GeqRmnK59Hr64PuS` 的 publicConfig.publishableKey**（`wbpk_<appid中段>_<secret>`，**无权限语义**，服务端靠 Origin 校验）⇒ 取法：`workbuddy_cloud_service` action=activate + reuse 该 appId 回读（inspect 不返回 key）；或看仓库遗留 `gen_candidates.js:13` 的 fallback（**与线上同值、未轮换**）。**无 dotenv ⇒ `.env` 文件根本不读**，只认真实环境变量；已 `setx` 到用户级（新开窗口生效）。
- 已知红线级坑：**「总数对上」≠「复现对了」**（`_bridge_v3/tasks` 打 exam 同为 5/11 但 dev 10/19）；**拿现态判历史产物必假红/假绿**（NC-21 用当前卷核旧成绩单分母）；**负控检查对象要动态取**（NC-15 曾静默消失）。
