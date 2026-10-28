# 工程长期备忘（蜗子 / 老王）

> **SOT 优先级**：`AGENTS.md`（协议）> `CLAIMS.md`（claim 与数字）> `RUBRIC.md`（判分口径 + 红线 R1–R65）> `reports/INDEX.md`（artifact 路径）。
> **不复制会漂的数字**（现场实读），只留跨会话生效的方法、坑、约定。逐批细节见 `YYYY-MM-DD.md`；旧全文 `MEMORY_ARCHIVE_20261028_pre_compact.md`。

## 执行协议
- **R-A1..A12 见 `AGENTS.md`**（协议 SOT，本文件不复述）。
- **开工顺序**：`git status` → `check_claims` → `negative_controls` → 填 §3 `TASK_CONTRACT` → 复述「只改 X／验收 Y／停止 Z」→ 老王确认。
- **发现不一致写 `CONFLICT.md`**（3 选项 + 证据 + 建议），**不许边做边修**。已证伪路线不重做（prompt v3/v3b，C-035）。

## 环境铁律
- 🚨 **Abaqus 在 agent 内必失败** = 沙箱注入 `tsbx.dll`（pre.exe `__fastfail`、.dat 无错、ODB 空骨架）⇒ 只能 **WorkBuddy 外 cmd 跑 bat**。
- venv = `C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe`。「数据集/求解类」与**负控**都要 venv；**只有 `check_claims` 可用系统 python**。
- **不许并行跑 ccx/abaqus** ⇒ 已固化为 `solver.run()` 全局锁 `.solve.lock`（R61）。bat 里 `resummarize.py` 先于 `make_dataset`。

## 验证纪律
- 只认独立复算：平衡 + 解析解 + 双码交叉。**门禁不许印没量过的数字**。**判据按族**：翼盒 500 N（**vM 中位差 < 5%**）；柱壳 内压+端弯+端剪（`max|u|` 只报）；开孔板 拉伸（<1%）；加筋板 1000 N。
- **收口顺序（R59）**：`negative_controls` → `check_claims`（反了 mtime 过期）；pre-flight 一律 `--json "$TEMP/…"`。

## 通用坑
- **★★★ 位置耦合会伪装成确定性**：`stats['L1']`（全局累计数）、`i % 3`（族内序号）、`cands[:n]` 都是「看起来确定、实际依赖位置」。判断法：**问「shuffle 一下数据集，这条还是这道题吗」**。一轮内改写 **48/55 条 L2 + 37/55 条 NL**（N-16/N-18）且无闸能发现。
- **★★ 冻结要冻结「整行」不是「参数」**：`case_id → style_idx` 只防序号漂移、防不了模板措辞改动；整行复用才是**构造性保证**。改老题须显式编辑冻结件——那正是要的（R65/S-52）。
- **★★ 判据自己漏了比没判据更危险**：`\b` 在 `_d30` 处不成立（`_` 是 word 字符）⇒ 泄漏判据只抓 5/19 条、给了个好看的假数。写完判据先拿已知命中样本验召回。
- **★★ 汇总/明细/「跑完了」都会骗人**：`batch_summary` 漏写、明细**键名不符**（`case` vs `case_id`）、`check_forms` 记「未完成」数月才暴露真 FAIL。**接入明细先打印「命中数/总数」，命中 0 必须报错**。重生成权威 artifact 前先证明「除目标键外零差异」（dry-run 到临时路径 + 逐键 flat 比对；`make_manifest` 会重算 `split_of`）。
- **★★ 负控五条**：①不只断言「是否红」，还要断言**「红的原因对不对」**（强判据吃弱判据 ⇒ 弱判据永假绿）；②变异锚点**现取不写死**（复发两次：NC-49/NC-27）；③锚点缺失判红不 skip；④新闸测「自比 A==B」；⑤消掉漂移面必须配闸防它长回来（S-51/S-52）。
- **★★ sha256 只证「文件没被换」不证「数是对的」（R62）**：claim 计数必须有闸比对 artifact；**建完闸先查自己刚写的东西有没有绕开它**。无工具读的 = 无闸（R58）；协议不写死计数（R63）；旧版进 `reports/archive/`。
- **★ 口径参数漏传 ⇒ 假 FAIL**（`verify_solvers` 漏 `--spec` 印 `residual 99.99999%`）⇒ **先怀疑参数再怀疑模型**。

## 数字与口径
- headline 只一条标 status 列，第二模型一律 `supporting`；不引 `eval_runs/`（gitignore）。**MSR 是条件通过率** ⇒ 95.2% 可「高于」90.9% 而 TSR 低 4 pp，须与 TSR/SFR 并列；bridge 表是唯一允许跨版本相减的场景；跨模型先看 `only_b`。
- **★★ 并列的比率先核分母**：spec 数 vs 算例目录数（×2 树）不是同一个分母，只因恰好全过才多年没暴露。**分母不等时连并列都不该有**；对外表必须单列「分母口径」。

## 协作约定
- 决策先可视化 → 更新看板（必跑 `node _dash_check.js`）；里程碑收口三同步（看板 + 两份 README + 记忆）；岔路口先问老王（推荐项 + 理由 + 代价）。落盘三铁律：拍板即落盘／大输出只留路径／日志带检索词。

## 当前状态
> 只记「在哪、卡在哪」，数字实读。
- 代理模型线冻结（D37），KPI = TSR/FPR/修复/拒答/澄清。**三层口径别混**：数据集 v1.1 = 64 条案例 ／ **考卷 v7 = 64 条任务（C-037）** ／ **headline 仍是 C-032（v6c 的 55 条、exam 25）**——v7 candidates 没跑。
- ✅ 协议侧 R1–R65 / RUBRIC v5.7 / 负控 57/57 / `check_claims` 29-58-53 全绿；✅ 数据层 **C-036 GATED**。
- **v7 双分母**：`exam_legacy = 25`（与 C-032 同卷可比）／`exam_full = 34`（+ `interpolation_v11` 9）；R54 只禁跨分母相减、不禁并列。
- 下一主任务 = **v7 candidates**，但**开工前必须先定 N-17**：19/64 条 L2 的 `spec.name` 直接写出被省略值 ⇒ clarify 判据本身无效（`check_l2_leak.py` 可复跑）。
