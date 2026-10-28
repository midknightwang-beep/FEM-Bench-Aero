# 工程长期备忘（蜗子 / 老王）

> **SOT 优先级**：`AGENTS.md`（协议）> `FEM-Bench-Aero/CLAIMS.md`（claim 与数字）> `RUBRIC.md`（判分口径 + 红线 R1–R61）> `feagpt_repro/reports/INDEX.md`（artifact 路径）。
> **不复制会漂的数字**（现场实读），只留跨会话生效的**方法、坑、约定**。逐批细节见 `YYYY-MM-DD.md`；2026-10-28 二次压缩，全文 `MEMORY_ARCHIVE_20261028_pre_compact.md`。

## 执行协议（效力最高）
- **R-A1..A12 全文见 `AGENTS.md`**（核心：单变量／先冻结／要 artifact／语义自检／分母闭合／不跨版本直减／headline 唯一／负控编号／范围锁／失败即停／七段报告）。
- **开工顺序**：`git status` → `check_claims` → `negative_controls` → 填 §3 `TASK_CONTRACT` → 复述「只改 X／验收 Y／停止 Z」→ 老王确认 → 才动手。
- **发现不一致写 `CONFLICT.md`**（3 选项 + 证据 + 建议），不许边做边修。已证伪路线不许重做（prompt v3/v3b，C-035）。

## 环境铁律
- 🚨 **Abaqus 在 agent 内必失败** = WorkBuddy 沙箱注入 `tsbx.dll`（pre.exe `__fastfail`，~19 s 延迟后挂、.dat 无错、ODB 空骨架；`dangerouslyDisableSandbox` 无效） ⇒ 只能 **WorkBuddy 外普通 cmd 跑 bat**。
- venv = `C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe`（系统 python 无 numpy/gmsh）。**负控也要 venv**（NC-52 真跑求解）⇒ 文档「两道文本闸可用系统 python」已过期。
- **不许并行跑 ccx/abaqus** ⇒ 已升级为机制 `feagpt/solver.py` `run()` 全局锁 `.solve.lock`（R61/S-47/NC-52）。手工 bat 里 `resummarize.py` 必须先于 `make_dataset`。

## 验证纪律
- 只认独立复算：平衡（唯一不变量）+ 解析解 + 双码交叉。**门禁不许印没量过的数字**。
- **判据按族**：翼盒 500 N 端载（登记判据 = **vM 逐节点中位差 < 5%**，`max|u|`/峰值只报不判）；柱壳 内压+端弯+端剪（D20 剔端载环，`max|u|` 只报）；开孔板 拉伸（<1%）；加筋板 1000 N。跨族套用产出整片假 FAIL。
- **收口顺序（R59）**：`negative_controls` → `check_claims`；反了官方 JSON 记的 `mtime` 过期。pre-flight 一律 `--json "$TEMP/…"`；`check_claims.json` 的 mtime diff 是预期噪声。

## 通用坑（已成闸的见 CLAIMS/RUBRIC，此处只留尚未成闸的）
- **★★「跑不完」≠「跑通了」**：`check_forms` 被记「未完成」数月，串行跑完才暴露真 FAIL。**一直没跑完的检查等于没检查**，它同时掩盖「跑通了会红」。
- **★★ 汇总/明细都会骗人，判据永远是产物**：`batch_summary.json` 会**漏写**（9 条只写 1 条）；d36 明细**有 rows 但键名不符**（`case` vs `case_id`）⇒ 39 条翼盒从未被逐条读，`None` 被当正常值放行。**接入任何明细先打印「命中数/总条数」，命中 0 必须报错，不许静默降级**。
- **★★ 等级高于证据 = R2 的镜像**：无读数不得计入 field-level；**继承来的 PASS 与实测的 PASS 必须分开标**。
- **★ 验证工具的口径参数漏传 ⇒ 假 FAIL**：`verify_solvers` 漏 `--spec` 退回全节点求和，ccx 是 total force（施加+反力抵消）⇒ 印 `residual 99.99999%`。**先怀疑参数再怀疑模型**。
- **★ 负控变异锚点现取，不写死**（写死 `NC-23..48` 在区间变 `..49` 时误判）；锚点缺失判红不得 skip。新闸上线必须同时测「自比 A==B」（可比性闸曾把 `comparability(x,x)` 也拒了）。
- **★ 判据只认结构化字段 + 自指标记**，别用自然语言表述（曾把被测条自己过滤掉）；同一文件「当前」二字只能出现一处。
- **★ 无工具读的文件 = 无闸（R58）**：只管数据类 SOT；AGENTS/CLAUDE 是协议文本，别用闸校验它自己所属的规约。**换完数据源要立刻 grep 新源有没有被闸读**——T-A8 把对外表换成 `gate4_v11`/`verify_dataset_v11` 后，两个闸对它们仍 0 命中（N-12）。
- **★★ sha256 只证「文件没被换」，不证「数是对的」（R62）**：claim 正文的计数必须有闸与 artifact 逐项比对，否则漂了也全绿（C-003 从 34/15/6 漂到 39/18/7，48 项语义检查全程绿）。**判据解析不出来一律判红、不得 skip**；**建完闸第一件事是检查自己刚写的东西有没有绕开它**（我曾把同一组数字抄进闸不覆盖的另一个文件）。「上一代」也只许留一份，旧的进 `reports/archive/`。

## 数字与口径
- headline 只有一条标在 status 列，第二模型一律 `supporting`；数字不引用 `eval_runs/`（gitignore）。
- **MSR 是条件通过率**（分母 = 产出 spec 且非澄清题）⇒ 95.2% 可「高于」90.9% 而 TSR 低 4 pp，报数必须与 TSR/SFR 并列。bridge 表是唯一允许跨版本相减的场景；跨模型对比先看 2×2 的 `only_b`。生成侧细节见归档。
- **★★ 并列的比率必须先核分母**：对外表的「关 1 55/55」是 spec 数、「关 4 110/110」是算例目录数（×2 树）——**从来不是同一个分母**，只因为两边都恰好全过才多年没暴露。分母不等时连并列都不该有（R54 加强版）；对外表必须单列「分母口径」。
- **★ 命令的"工作目录"也是口径**：CLAIMS 里 C-001/C-002 写 `FEM-Bench-Aero/…` 而闸脚本都在 `feagpt_repro/` 跑 ⇒ 这两条命令从来没跑通过，却因「artifact 在 + sha 对」一直绿灯。R26 之外再要一条：**command 必须能在默认工作目录实跑通**。

## 协作约定
- 决策先可视化 → 更新看板（必跑 `node _dash_check.js`，划分表用 `_dash_sync_splits.py` 回填）。里程碑收口三同步：看板 + README + 记忆。
- 岔路口先问老王（推荐项 + 理由 + 代价）。落盘三铁律：拍板即落盘／大输出不进对话只留路径／日志带检索词。

## 当前状态
> 只记「在哪、卡在哪」，数字实读。
- 代理模型线冻结（D37），对外 KPI = TSR/FPR/修复/拒答/澄清。**数据集 v1.1 = 64 条，考卷仍是 v6c 的 55 条任务**——别混说。
- ✅ 卡点①（v1.1 双码）已解：`verify_dataset` 64 paired PASS，双码 9/9（8 gated + 1 柱壳 reported-only）。
- 卡点②：prompt 已到顶（C-035），剩余失败属模型行为。
- 下一主任务 = **v7**（9 条接进任务层，exam 25 → 34）；一落地 C-032 的 23/25 不可比（R30/R39），须转 historical。
