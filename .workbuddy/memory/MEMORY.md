# 工程长期备忘（蜗子 / 老王）

> **SOT 优先级**：`AGENTS.md`（执行协议）> `FEM-Bench-Aero/CLAIMS.md`（claim 与数字）> `RUBRIC.md`（判分口径 + R42–R57）> `feagpt_repro/reports/INDEX.md`（artifact 路径）。
> **本文件不复制会漂移的数字**（计数、分数、sha 一律现场实读）——只留跨会话仍生效的**方法、坑与约定**。
> 逐批细节在 `.workbuddy/memory/YYYY-MM-DD.md`；2026-10-27 压缩重写，旧全文 `MEMORY_ARCHIVE_20261027_pre_compact.md`。

## 执行协议（2026-10-27 老王下达，效力最高）
- **R-A1..A12**：一个任务一个变量 / 先冻结后运行 / 数字必须有 artifact / 语义自检（不是结构自检）/ 分母两层闭合 / 不跨版本直减 / headline 唯一 / 模型与 prompt 可追溯 / 负控先绿并报编号 / 范围锁 / 失败即停 / 交七段固定报告。
- **开工顺序**：`git status` → `check_claims.py` → `negative_controls.py` → 填 §3 `TASK_CONTRACT` → 复述「只改 X / 验收 Y / 停止 Z」→ 老王确认 → 才动手。
- **发现任何不一致：写 `CONFLICT.md`（3 选项 + 证据 + 建议），不许边做边修。** 第一轮 4 条已由老王改完并复核通过；第二轮 N-1..N-5 见该文件。
- 被否决/已完成的路线不许重做：prompt v3/v3b 已证伪（C-035），别再改措辞。

## 环境铁律
- 🚨 **Abaqus 在 agent 内失败的头号嫌疑 = WorkBuddy 沙箱注入 `tsbx.dll`**（pre.exe `__fastfail`；签名：~19s 延迟 + Input File Processor error + .dat 无错 + ODB 空骨架）。`dangerouslyDisableSandbox` 无效。可靠路径 = **WorkBuddy 外普通 cmd 手工 bat**（solve + `abaqus python abaqus_odb.py`）。
- **手工 bat 顺序**：先 `resummarize.py --roots …` 再 `make_dataset`。反了不报错、只打 `max|u|=n/a` ⇒ 收口必须逐目录数文件（**6 个**）。
- numpy/gmsh 用 venv `…\envs\default\Scripts\python.exe`（系统 Python 无 gmsh 会假报 pipeline 失败）。ccx = `tools/calculix/calculix_2.23_4win/ccx_static.exe`；Abaqus = `D:\Program Files\SIMULIA\Commands\abaqus.bat`。
- **绝不并行跑 abaqus/ccx**（静默空转、rc 仍 0）。只认真 FRD / 真 ODB 读数，不信「命令返回 0」。（2026-10-27 又犯一次：`check_forms` 未停就起柱壳 ccx；事后单独重算逐位相同，未污染，但那是运气。）
- ccx 壳展开成实体：方程 ≈ 14.9×壳节点；本机 33GB 上限 ⇒ ≤158,548 节点可算、188,674 已失败。

## 验证纪律
- 只认独立复算：平衡（唯一不变量）+ 解析解 + 双码交叉。**门禁不许印没量过的数字**（命令 + 数字 + 产物路径落盘）。
- **判据按族**：双码载荷口径不可跨族套用 —— 翼盒 500 N 端载 + 根截面反力；柱壳 内压 + 端弯 + 端剪（D20 剔端载环）；开孔板 面内拉伸；加筋板 1000 N。套错产出 9900 % / 700 % 整片假 FAIL。
- 双码位移：barrel 登记判据 = D20 `structure_peak`，model-wide `max|u|` 只 REPORTED NOT GATED；小位移区相对误差骗人，先看绝对差。
- 变体结果完全相同 = 报警信号；改网格/判据 ⇒ 重签基线但必须留档旧基线（D10）。
- 闸门报数报**判据组数**不是快照条数；回看最后一行 VERDICT 前那句话。
- **判据的假设会冒充模型的错**：柱壳长度轴 `max_von_mises` 三点 249.35/248.16/249.40（差 0.5%）——根部峰值由「端部弯矩÷截面模量」决定，都不随长度变 ⇒ **应力在长度轴不单调**，该轴只判位移、应力只报（`strict_metrics` 按轴声明）。

## 契约与数据集
- 唯一契约 `spec.FEASpec`；求解器选择在写 deck 之前；结果两码归一 `{nodes:{DISP,FORC,STRESS}}`。spec 加字段 ⇒ `spec_sha256`/`truth.json` 全档失效须重导。
- `modeling/`（ccx 可发布）+ `_xval/`（abaqus 禁发布）；case 六件套 = spec/step/msh/inp/results/truth。门禁：minJ ≥ 0.30 且零 tri3／平衡 < 1e-3%／双码 `max|u|` 差 < 1% + vM 逐节点中位差 < 5%。
- **划分是规则**：`manifest.HOLDOUT_REGIONS` + `split_of(spec)`（吃 spec 不吃 case_id，首个命中即定）；`eval_dataset` 断言复现 D12。
- **v1.1 的声明式划分**：新 spec 打 `extra.split_tag = v11_interior_holdout`，`split_of()` 在族谓词**之前**认它。**不能用参数谓词** —— 内插点每轴都在包络内，任何数值谓词都会把 D12 锁定的 11 条重新划分。
- **内插物理判据**（`_v11/verify_v11_interpolation.py`）：内插点峰值量必须严格落在两锚点之间 —— 不依赖 gold，查的是「参数有没有真进模型」（厚度没进 `*SHELL SECTION` 这类错，单条 case 内部永远查不出来）。
- **去重指纹** = msh 逐字节 + SHELL SECTION 厚度表 + `*ELASTIC` 材料律块（只按 mesh 判会误删壁厚变体）。
- 常用：`check_forms.py`／`verify_hole.py`／`check_semantics.py`／`verify_dataset.py`／`eval_dataset.py`／`make_manifest.py --root <R> --json --md`／`make_dataset.py --solver ccx|abaqus --cases <dirs> --root <R>`／`run_pipeline.py --deck-only`／`score_baseline.py`／`msr_l3.py`／`bootstrap_ci.py`／`compare_scorecards.py`。
- **`check_forms` / `make_manifest` 不传 `--json` 就只打印不写盘**；`score_baseline` 顶层 `model` 读候选文件实测，命令行只做交叉核对。

## 高价值坑（跨族通用）
- **「模型不行」第一嫌疑 = 特征没给全**（M7：漏 `is_T`/`web_pos` 使 test 14.8%、补齐后 10.7%，结论反转）。诊断假设与被测对象必须同口径。
- **标准化欧氏距离不能当可信度指标**（corr(distance,|err|) = −0.046）；必逐轴判训练包络。
- **补覆盖点 ≫ 补同质样本**；**标准化系数不是幂指数**（指数 = `w / sd(log x_f)`）；**交互项必须用实测单轴响应相乘**。
- **厚度维退化取决于载荷口径不是轴的属性**：载荷随 t 缩放则与膜刚度精确抵消；载荷固定则 `u∝1/t`。
- **只打印不参与判定的检查不是检查**（`verify_dataset` pairing MISMATCH 而 `all_ok` 不含它 ⇒ 仍 PASS）。
- **★★ 「工具跑不完」≠「工具跑通了」**：`check_forms` 长期被记成「未完成」（每次 10 min 无输出被 kill），串行跑完才暴露 `DEFAULT_REFERENCE` 指向不存在的 `outputs_str/…` ⇒ T5 恒 FAIL、整份 VERDICT: FAIL。**一直没跑完的检查，等于没检查**——它同时掩盖「跑通了会红」。
- **★★ 没有闸的纪律会被反复违反 ⇒ 升级成机制**：「绝不并行跑 ccx」写过两次仍犯，因为并行时 **rc 仍为 0**、结果为空，「返回 0 就算成功」的判读看不见。解法不是再写一遍纪律，而是 `feagpt/solver.py` `run()` 加**全局求解锁** `.solve.lock`（第二个求解直接抛错；1 h 过期自动接管）⇒ **并行变得不可能**（R61/S-47/NC-52）。
- **★ 收口顺序（R59）**：`negative_controls` → `check_claims`；反了官方 JSON 记的 artifact `mtime` 会过期（内容/sha 全对，只有元数据旧）。S-45 查的是**磁盘上现有**的那个 JSON，所以修复那一次会先红、写完即绿——**收口必须跑到 S-45 绿为止**。F-1（负控内容不变不重写）是它稳定的前提。
- **★★ 没有任何工具读的文件 = 没有闸（已升级为红线 R58 + 闸 S-44）**：`check_claims` 新增 `index_consistency`，校验 `reports/INDEX.md` 的 headline 指向唯一（行内出现 headline 必须指向唯一 headline 或标 historical）与负控编号/总数同最新 `negative_controls_<N>.json` 对齐；反向 NC-49 四向。**R58 的边界**：只管**数据类** SOT（CLAIMS / RUBRIC / INDEX / 成绩单）；`AGENTS.md`/`CLAUDE.md` 是协议文本、由「§7 不要相信这张表」声明兜底——**不要用一个闸去校验它自己所属的规约**。：`check_claims.py` 从不读 `INDEX.md`（grep "INDEX" = 0 命中），所以 INDEX 里两个「当前 headline」逃过了 44 项语义检查。**新增/重要文档必须先被某个 gate 读，否则等于没校验。**
- **★★ 「当前」二字只能写在一个地方**：同一文件里两处标「当前」必漂移（INDEX §1 = C-032、§2 ⓪ 段 = C-029）。规则：官方状态只写一处，其余一律写指针（「见 §1」）。
- **★ 判据别用自然语言表述**：S-29 第一版按「正文含某词且不含否定词」判，把 C-029 自己过滤掉了；改结构化后 C-028 的 status 指针又冒充第二个 headline。⇒ 只认结构化字段 + 自指标记（`（对外 headline）`），并配反向负控。同坑第三次以「协议措辞」形式出现（R-A7 写「标注」⇒ 字面 grep 命中 6 条）。
- **★ 新闸上线必须同时测「自比/A==B」用例**：R53 的可比性闸把 `comparability(x,x)` 也拒了（旧批次 `prompt_sha256` 未记录）⇒ NC-29/NC-35 当场转红。约束「A 与 B 不同」之前先想 A==B 该不该放行。
- **★★ 分母小的那个 pct 更好看**：MSR 是**条件通过率**（分母 = 产出 spec 且非澄清题），被排除的往往是**失败题** ⇒ 95.2% 能「高于」90.9% 而 TSR 低 4 pp。**按口径报数时必须与 TSR/SFR 并列，分母不等不出 Δ**（R54）。
- **★★ 改 harness 后「修了缺陷」必须证明没顺带动难度**：C-032 与 C-029 逐题类别完全相同，才能说「修的是隐患、不是补分」；只报分数变化区分不了这两种（R55）。
- **★ prompt 变更必须消融留档、净收益 ≤0 一律否决、否决后 sha 回基线**：v3/v3b 试过，exam 澄清题三版完全一致（glm 3/3/3、deepseek 2/2/2）、失败点在迁移 ⇒ 打地鼠。**别把「还差一点」当「继续调措辞」的理由**（C-035 / S-43 / NC-48）。
- **★ 别把「本族合法键」当成「本题该问的键」**：`n_stringers_per_skin` 在翼盒族合法，但题面没提长桁时登记为「不该问」是对的 —— 元数据没问题，是模型多问。
- **★ `failed_fields` 的路径根不统一**：`extra.*` 挂在 spec 顶层，`params.*` 实际在 `spec.structure` 下。按字面路径取 ⇒ 全 None 且被误分类。下游工具必须两种根都试并记录命中根。
- **★ 比率/计数必须与成绩单自报值交叉核对**：dev 通过数用「spec_pass 计数」得 22→21，成绩单是 23→22 —— **TSR 把 `clarify_ok` 也算通过**。口径不同要 rc≠0，不能各说各话。
- **★ 往结构化数组插/追加条目**：锚点唯一 ≠ 锚点正确（必须断言相对位置 `index(HEAD) < index(新) < index(TAIL)`）；**末尾追加要补尾逗号**（末项无逗号，直接插其后 ⇒ 语法错，看板 r68 踩过）。改完必须跑该文件的语法/自检。
- **★ 写端/读端分开时必须对着跑一遍**：v1.1 的 tag 写成 `extra.<TAG>=true`（键），而谓词读 `extra.split_tag`（值）⇒ 9 条先被族谓词分进 train（train 一度 29）。
- **★ 锚点要先确认存在**：柱壳第一版挑 `d1800_l1800`，集里没有 `d1800_l1600` ⇒ 单夹逼不成立、校验器 SKIP。挑点位前先列全锚点。
- **★ 结论依赖数据集的脚本重跑即毁档**：探针输出名必须带里程碑标签 + 支持 `--out`/`--md`（R26 要求 command 里的输出路径 == artifact）。
- **★ 观测量也可能一直是空的**：成绩单顶层 `msr` 键曾恒为 null；「先 bootstrap 后 msr」会静默产出 null CI ⇒ **正确顺序 score → msr → bootstrap**，注释与实现不符要当 bug 记。
- **★ solver 桶是「候选相关」的**，不是题目固有属性 ⇒ 「剔除 solver 后的分母/得分」同样不可跨版本直减。
- **★ 成本判断也要实测**：「轮换 key ⇒ 重签 artifact ⇒ 代价高」错两处 —— endpoint 是硬编码常量、`provenance` 不记 key。**凭印象估的代价会挡住本来该做的事**（R46）。
- **★ 负控里的变异锚点不得写死会变的常量**：NC-49 第一版把 `NC-23..48` 写进变异输入，本轮恰好把主区间改成 `..49` ⇒ 锚点缺失 ⇒ 当场报「漏判」。**变异输入必须从被测产物现取**（正则取主区间再减 1），且**锚点缺失要判红、不得 skip**（R29 同源）。
- **★ 收口顺序：先负控、后 check_claims**；反序会让官方 JSON 记到过期 `mtime`（负控每次重写自己的 json，内容不变也重写）⇒ 官方 artifact 元数据抖动。pre-flight 一律 `--json "$TEMP/..."`（N-5 的 C+）。
- **★ 门禁会弄脏工作区**：`check_claims.json` 记录 artifact 的 `mtime` ⇒ 每次 pre-flight 都产生一个 diff（sha256 不变）。按 C5 审 diff 时要认得这是预期噪声。
- 其余：铺层平衡必须按有符号配对（`a>90°` 折回 `180−a`）；翼盒坐标 x 弦向 / y 法向（载荷 DOF 2）/ z 展向；`max_disp` 本身已是弯曲挠度；峰值是「离散选择」不是光滑泛函（31 条翼盒 `max_disp_node` 21 个不同节点）；报 MAPE 必须同报中位 + 最大 + bootstrap CI；共线模型要报条件数；`_wingbox_planar_shape` 返回 `(tip_chord_ratio, sweep_deg)`，解包反了全案判成锥度 0。

## 数字与口径（只记原则，数字现场实读）
- **headline 只有一条，标在 status 列**；第二模型一律 `supporting`。**数字不引用 `eval_runs/`**（被 gitignore，重跑即覆盖）。
- **bridge 表是唯一允许跨版本相减的场景**，最有价值的一格是「改题面但不重生成候选 ⇒ 得分 0 变化」。
- **跨模型对比的价值在归因不在排名**：先看 2×2 的 `only_b`（=0 ⇒ 纯损失、换模型无用），再看分数；同题同字段复现 ⇒ 题面/prompt 的错。
- **字段级命中率与任务级结论可以相反**（双尺度），相反时必须落 `verdict_split`，禁止只引有利一侧。
- 生成口径：SDK 无 json_schema logits 约束 ⇒ json_object + ajv（放宽 required）+ 错误反馈修复 ≤3 轮；`gen_candidates_v2.js --limit` 默认 30，跑 55 条必须显式 `--limit 55`；`--only` 定向冒烟、`--print-prompt-sha` 只印 sha 不跑模型。
- key：`WORKBUDDY_PUBLISHABLE_KEY` 是 WorkBuddy 云应用「FEM基线评测」「wbapp_Tl8jf0GeqRmnK59Hr64PuS」的 `publicConfig.publishableKey`（`wbpk_<appid中段>_<secret>`，无权限语义，服务端靠 Origin 校验）。**无 dotenv ⇒ `.env` 不读**，只认真实环境变量。

## 协作约定
- 决策环节**先可视化梳理** → 更新看板（DATA 区），必跑 `node _dash_check.js "<html>"`；看板划分表用 `_dash_sync_splits.py` 回填，不手改。
- **里程碑收口三同步：看板 + 两份 README + 记忆**。岔路口先问老王（推荐项 + 理由 + 代价，不摆中立选项）。
- 落盘三铁律：拍板即落盘／大输出不进对话只留路径／日志带检索词（线名 + 实体 + 日期）。

## 当前状态
> 数字全部现场实读，本节只记「在哪、卡在哪」。
- **代理模型线（M7/M14/D01–D37）冻结**（D37 拍板）；对外 KPI = TSR/FPR/修复/拒答/澄清。
- **headline / 支撑 / 历史**：见 `CLAIMS.md`；入口 `reports/INDEX.md`（官方 vs 诊断）。
- **数据集 v1.1 = 64 条**（train 25 / val 17 / test 22），**考卷仍是 v6c 的 55 条任务** —— **数据集 ≠ 考卷**，两个数不要混说；v7 待建（一落地旧成绩不可比）。
- **卡点①**：v1.1 新增 9 条只有 ccx，`verify_dataset` 报 `9 modeling-only ⇒ MISMATCH`；deck 已备，须在 **WorkBuddy 外**跑 `_v11/run_v11_abaqus.bat`。
- **卡点②**：prompt 已到顶（C-035），剩余失败属模型行为；要动只能改 harness 口径（语义回填闸，待老王拍板），或靠 v1.1 扩样本收窄 CI。
- **待拍板**：`CONFLICT.md` 第二轮 N-1..N-5（INDEX 两个「当前 headline」等）。
