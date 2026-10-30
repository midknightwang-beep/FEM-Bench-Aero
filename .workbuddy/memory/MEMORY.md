# 工程长期备忘（蜗子 / 老王）

> **SOT**：`AGENTS.md`（协议）> `CLAIMS.md`（claim/数字）> `RUBRIC.md`（口径+红线）> `reports/INDEX.md`（路径）。**不复制会漂的数字**（现场实读），只留方法/坑/约定；细节见 `YYYY-MM-DD.md`。

## 执行协议
- **R-A1..A12 见 `AGENTS.md`**（不复述）。
- **开工顺序**：`git status` → `negative_controls` → `check_claims`（R59，顺序不可反，反了 mtime 过期）→ 填 §3 `TASK_CONTRACT` → 复述「只改 X／验收 Y／停止 Z」→ 老王确认。命令与解释器**照抄 `AGENTS.md` §0 命令块**（T-A12a：不要凭记忆写 `python`）。
- **发现不一致写 `CONFLICT.md`**（3 选项+证据+建议），**不许边做边修**；已证伪路线不重做（prompt v3/v3b，C-035）。

## 环境铁律
- 🚨 **Abaqus 在 agent 内必失败** = 沙箱注入 `tsbx.dll`（pre.exe `__fastfail`、.dat 无错、ODB 空骨架）⇒ 只能 **WorkBuddy 外 cmd 跑 bat**。
- venv = `…/envs/default/Scripts/python.exe`：数据集/求解/负控都要 venv，**只有 `check_claims` 用系统 python**。
- **不许并行 ccx/abaqus** ⇒ 已固化 `solver.run()` 全局锁 `.solve.lock`（R61）；bat 里 `resummarize` 先于 `make_dataset`。

## 验证纪律
- 只认独立复算：平衡+解析解+双码交叉。**门禁不许印没量过的数字**。**判据按族**：翼盒 500 N（vM 中位差 <5%）；柱壳 内压+端弯+端剪（`max|u|` 只报）；开孔板 拉伸（<1%）；加筋板 1000 N。
- **收口顺序（R59）**：`negative_controls` → `check_claims`（反了 mtime 过期）；pre-flight 用 `--json "$TEMP/…"`。

## 通用坑
- **★★★ 位置耦合会伪装成确定性**：`stats['L1']`（全局累计）、`i % 3`（族内序号）、`cands[:n]` 都「看起来确定、实际依赖位置」。判断法：**shuffle 一下数据集，这条还是这道题吗**。一轮改写 48/55 条 L2 + 37/55 条 NL（N-16/N-18）且无闸发现。
- **★★ 冻结要冻结「整行」不是「参数」**：`case_id→style_idx` 只防序号漂移、防不了措辞改动；整行复用才是构造性保证（R65/S-52）。
- **★★ 判据自己漏了比没判据更危险**：`\b` 在 `_d30` 处不成立（`_` 是 word 字符）⇒ 只抓 5/19 条、给了个好看的假数。写完判据先拿已知命中样本验召回。
- **★★ 判据在子集上失效 ⇒ 隔离+双报，不改题**（R66/S-53）：改题连历史一起废，继续算进单一数字是知情不改；两分母不同 ⇒ 一并适用 R54。**先证「失效」是真的**——我上一版就错判过（以为 C-032 的 clarify 被 L2 污染，实测它读的是 L3 的 4 条）⇒ **不盲从自己上一版写的结论**。
- **★★ 汇总/明细/「跑完了」都会骗人**：`batch_summary` 漏写、明细**键名不符**（`case` vs `case_id`）、长期「没跑完」的检查同时掩盖「跑通了会红」。**接入明细先打印「命中数/总数」，命中 0 必须报错**。重生成权威 artifact 前先证明「除目标键外零差异」。
- **★★ 负控五条**：①不只断言「是否红」，还要断言**「红的原因对不对」**（强判据吃弱判据⇒弱判据永假绿）；②变异锚点**现取不写死**（复发两次：NC-49/NC-27）；③锚点缺失判红不 skip；④新闸测「自比 A==B」；⑤消掉漂移面要配闸防它长回来。
- **★★★ 变异锚点写死的不是数字，是「基线长什么样」**（NC-56 d 第三次复发）：那一向的变异是「status 设 scored + 只给 all 的 passed」，靠的是**另一侧原本为 None**；artifact 一升到 `scored`（两侧都是整数）这向就**退化成空操作**、当场红。⇒ 做变异时问「**这个差异是不是由基线状态供给的**」，是的话必须**显式构造差异**（删掉另一侧），不能靠「原本没有」。
- **★★ sha256 只证「文件没被换」不证「数对」**（R62）：claim 计数必须有闸比对 artifact；**建完闸先查自己刚写的东西有没有绕开它**。无工具读的=无闸（R58）；协议不写死计数（R63）；旧版进 `reports/archive/`。
- **★ 口径参数漏传⇒假 FAIL**（漏 `--spec` 印 `residual 99.99999%`）⇒ **先怀疑参数再怀疑模型**。
- **★ markdown 表格的裸竖线会切单元格**：C-038 正文引正则 `(?:^|_)` ⇒ 该行变 9 格、status 被读成 coverage、**claim 总数少 1 而闸一声不响**。含正则竖线一律写 `&#124;`。
- **★★★ 恒真式在外观上与正常闭合一模一样**（N-26）：都印 `ok=True`、都印一行 `A = B + C + …`，只有把式子代进去看才发现左右恒等。`_denom_audit(exam_full_ids)` 的 pool 取自已剔除 clarify/unresolved 的 `den_rows` ⇒ `n_tasks_total ≡ n_counted` ⇒ 那条 `[FATAL] 不闭合` **从未生效过**。⇒ **判闭合问「这个等式有没有可能不成立」，不是「它是不是 True」**；且同文件里 `_EAUDIT` 是真闭合、`_FAUDIT` 是假闭合 —— **一处真一处假可以写在同一段代码里**。
- **★★ 放宽必须有边界（R69）**：任何「允许例外/允许违规」的闸必须同时写明 ① 哪里仍必须为 0 ② 例外必须带 reason ③ 例外不得进入对外数字。反例：旧 README 的「`--scope all` 必须 rc=0」——一句**字面为假**的闸门口径，照做的 Agent 只能阻塞或静默忽略。**能判的不变量优于需要维护的名单**（故 `r32` 用动态判据而非 allowlist）。

## 数字与口径
- headline 只一条标 status 列，第二模型一律 `supporting`；不引 `eval_runs/`（gitignore）。**MSR 是条件通过率** ⇒ 95.2% 可「高于」90.9% 而 TSR 低 4 pp，须与 TSR/SFR 并列；bridge 表是唯一允许跨版本相减的场景；跨模型先看 `only_b`。
- **★★ 并列的比率先核分母**：spec 数 vs 算例目录数（×2 树）不是同一分母。**分母不等时连并列都不该有**；对外表必须单列「分母口径」。

## 协作约定
- 决策先可视化 → 更新看板（必跑 `node _dash_check.js`）；里程碑收口三同步（看板+两份 README+记忆）；岔路口先问老王（推荐项+理由+代价）。落盘三铁律：拍板即落盘／大输出只留路径／日志带检索词。

## 当前状态
> 只记「在哪、卡在哪」，数字实读。
- 代理模型线冻结（D37），KPI = TSR/FPR/修复/拒答/澄清。**三层口径别混**：数据集 v1.1 = 64 条案例 ／ **考卷 v7 = 64 条任务（C-037）** ／ **headline 仍是 C-032（v6c 55 条、exam 25）**——**v7 candidates 已跑（C-040，supporting，2026-10-29）**，但 headline 未切（R48，属 `v7-status`）。
- ✅ 协议侧 R1–R69 / RUBRIC v6.3 / 负控 64/64 / `check_claims` 33-67-57 全绿；✅ 数据层 **C-036 GATED**。
- **v7 双模型成绩（C-040，实读）**：legacy exam glm TSR 23/25·SFR 20/22·MSR 20/22、ds 22/25·20/21·19/21；exam_v11 两模型全对（9/9）；exam_full glm 32/34 (94.1%)、ds 31/34 (91.2%)。**exam_full 高于 legacy 是换分母的抬升，不是变强**。2×2 与 C-033 在 **pass/fail 层**逐条一致（cfrp45s_d40 的类别由 `no_output` 变 `clarify_wrong`，失败形态变了、成败没变）。
- **两处双分母**：exam `legacy 25`（与 C-032 同卷可比）／`full 34`；L2 clarify `all 64`／`informative 45`（invalid 19，`status=not_run` 如实）。都只禁相减、不禁并列。
- **headline 已拍板不切（2026-10-30，方案 A）**：C-032 保持唯一 headline、C-040 维持 `supporting`、**T-A12c 取消**；`v7-status` 关闭。
- **L2 澄清层已首次跑分（C-041，supporting，2026-10-30）**：glm `clarify_all` **49/64 (76.6%)** ／ `clarify_informative` **30/45 (66.7%)** ／ `invalid` **19/19**；`clarify_ok` 49 ／ `fabricated` 13 ／ `clarify_wrong` 2。**★ 64 与 45 的差不是泄漏，是族构成（N-27）**：15 条失败**全在翼盒**（24/39），非翼盒三族全对（13/13、7/7、5/5），而泄漏 19 条里 16 条正属这三族 ⇒ **`clarify_informative` 不得当「L2 真信号」单独引用**。失败集中在翼盒 `rib_thickness`/`stringer_height`/`sweep_deg` 各 1/6。
- **L2 与 L3 不是同一指标**：L3 判 spec 保真（TSR/SFR/MSR），L2 判「会不会追问」⇒ **不得并列成一张表**。L2 判据是**字面命中键名**（L2 零 `clarify_aliases`，属 R19 的选择）。
- **两道 dev 题（`L3_stiffened_panel_800x600[_str3]` 的 `length`/`width` 角色缺陷）长期挂 dev**：不对外、不排 v8；要修只能 v8 新卷 + 重冻结 + bridge（R65）。R32 `--scope all` 实测 4 条违规**全部落在 dev**、`gate_ok=true`。
- **环境级坑（会长回来）**：单次调用累计删除 ≥50 个文件会被沙箱拒绝 ⇒ 一趟 59 条 msr 必在第 ~53 条处锁删不掉（N-22）⇒ 一律分批（`--only`），单批 ≤40；硬杀进程必留 `.solve.lock`（finally 不执行）。
