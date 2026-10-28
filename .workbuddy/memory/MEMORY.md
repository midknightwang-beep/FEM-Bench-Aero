# 工程长期备忘（蜗子 / 老王）

> **SOT 优先级**：`AGENTS.md`（协议）> `CLAIMS.md`（claim 与数字）> `RUBRIC.md`（判分口径 + 红线 R1–R64）> `reports/INDEX.md`（artifact 路径）。
> **不复制会漂的数字**（现场实读），只留跨会话生效的方法、坑、约定。逐批细节见 `YYYY-MM-DD.md`；全文 `MEMORY_ARCHIVE_20261028_pre_compact.md`。

## 执行协议
- **R-A1..A12 见 `AGENTS.md`**（单变量／先冻结／要 artifact／语义自检／分母闭合／不跨版本直减／headline 唯一／负控编号／范围锁／失败即停／七段报告）。
- **开工顺序**：`git status` → `check_claims` → `negative_controls` → 填 §3 `TASK_CONTRACT` → 复述「只改 X／验收 Y／停止 Z」→ 老王确认。
- **发现不一致写 `CONFLICT.md`**（3 选项 + 证据 + 建议）。已证伪路线不重做（prompt v3/v3b，C-035）。

## 环境铁律
- 🚨 **Abaqus 在 agent 内必失败** = 沙箱注入 `tsbx.dll`（pre.exe `__fastfail`，~19 s 后挂、.dat 无错、ODB 空骨架）⇒ 只能 **WorkBuddy 外普通 cmd 跑 bat**。
- venv = `C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe`。「数据集/求解类」与**负控**都要 venv（NC-52 真跑求解）；**只有 `check_claims` 可用系统 python**。
- **不许并行跑 ccx/abaqus** ⇒ 已升级为机制 `solver.run()` 全局锁 `.solve.lock`（R61）。手工 bat 里 `resummarize.py` 必须先于 `make_dataset`。

## 验证纪律
- 只认独立复算：平衡 + 解析解 + 双码交叉。**门禁不许印没量过的数字**。
- **判据按族**：翼盒 500 N（登记判据 = **vM 逐节点中位差 < 5%**，`max|u|`/峰值只报不判）；柱壳 内压+端弯+端剪（D20，`max|u|` 只报）；开孔板 拉伸（<1%）；加筋板 1000 N。
- **收口顺序（R59）**：`negative_controls` → `check_claims`；反了 mtime 过期。pre-flight 一律 `--json "$TEMP/…"`。

## 通用坑
- **★★「跑不完」≠「跑通了」**：`check_forms` 被记「未完成」数月，串行跑完才暴露真 FAIL。
- **★★ 汇总/明细都会骗人**：`batch_summary` 会**漏写**；d36 明细**键名不符**（`case` vs `case_id`）⇒ 39 条翼盒从未被逐条读。**接入明细先打印「命中数/总数」，命中 0 必须报错不许静默降级**。
- **★★ 负控不能只断言「是否红」，还要断言「红的原因对不对」**：强判据（如逐字节比对）会吃掉任何变异 ⇒ 弱判据永远得不到证伪，一直是"被顺手抓到"的假绿。
- **★★ 消掉一个漂移面后要防它长回来**：改成「不写死」也必须配一条 lint（S-51），否则下一个人又抄回去。
- **★★ 重生成权威 artifact 前先证明「除目标键外零差异」**：dry-run 到临时路径 + 逐键 flat 比对（`make_manifest` 会重算 `split_of`，直接跑可能静默改掉 25/17/22）。
- **★ 等级高于证据 = R2 镜像**：无读数不得计入 field-level；继承的 PASS 与实测的 PASS 必须分开标。
- **★ 口径参数漏传 ⇒ 假 FAIL**：`verify_solvers` 漏 `--spec` 印 `residual 99.99999%`。**先怀疑参数再怀疑模型**。
- **★ 负控变异锚点现取不写死**（写死区间遇扩号即误判）；锚点缺失判红不得 skip。新闸要测「自比 A==B」。
- **★ 判据只认结构化字段 + 自指标记**；同一文件「当前」二字只许出现一处。
- **★★ sha256 只证「文件没被换」不证「数是对的」（R62）**：claim 正文计数必须有闸与 artifact 逐项比对。**建完闸第一件事是检查自己刚写的东西有没有绕开它**。「上一代」只许留一份，旧的进 `reports/archive/`。
- **★ 无工具读的文件 = 无闸（R58，只管数据类 SOT）**：换完数据源立刻 grep 新源有没有被闸读；协议文本不写死计数（R63）。

## 数字与口径
- headline 只一条标在 status 列，第二模型一律 `supporting`；数字不引 `eval_runs/`（gitignore）。
- **MSR 是条件通过率** ⇒ 95.2% 可「高于」90.9% 而 TSR 低 4 pp，报数须与 TSR/SFR 并列。bridge 表是唯一允许跨版本相减的场景；跨模型对比先看 2×2 的 `only_b`。
- **★★ 并列的比率先核分母**：spec 数 vs 算例目录数（×2 树）从来不是同一个分母，只因为两边都恰好全过才多年没暴露。**分母不等时连并列都不该有**；对外表必须单列「分母口径」。
- **★ 命令的"工作目录"也是口径**：command 必须能在文档默认目录实跑通（R26 之外）。

## 协作约定
- 决策先可视化 → 更新看板（必跑 `node _dash_check.js`）。里程碑收口三同步：看板 + README + 记忆。
- 岔路口先问老王（推荐项 + 理由 + 代价）。落盘三铁律：拍板即落盘／大输出不进对话只留路径／日志带检索词。

## 当前状态
> 只记「在哪、卡在哪」，数字实读。
- 代理模型线冻结（D37），对外 KPI = TSR/FPR/修复/拒答/澄清。**数据集 v1.1 = 64 条，考卷仍是 v6c 的 55 条任务**——别混说。
- ✅ 协议侧 R1–R64 / RUBRIC v5.6 / 负控 56/56 / `check_claims` 28-54-52 全绿；✅ 数据层 **C-036 GATED**（64 paired、check_forms 54/0、gate4 128/128、eval 64-63-0）。
- 下一主任务 = **v7**（9 条接进任务层，exam 25 → 34）；一落地 C-032 的 23/25 不可比（R30/R39），须转 historical。
