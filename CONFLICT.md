# CONFLICT

> **第二轮**（2026-10-27 晚）。触发：老王更新 `AGENTS.md` 后要求「重新检查」。
> 第一轮（4 条：计数漂移 / R-A5 公式 / §7 下一步 / 协议未入库）**已全部关闭**，见 §1。
> 按 `AGENTS.md` §6 + R-A11：**本轮不改任何 claim / artifact / paper / rubric / INDEX 正文**，只写这一页交老王拍板。
> 全部结论来自 pre-flight 实读命令，输出贴在每条的「证据」里。

---

## 1. 上一轮 4 条冲突：全部 RESOLVED（逐条给 live 证据）

| 旧冲突 | 更新后 `AGENTS.md` 写的 | live 实读 | 结论 |
|---|---|---|---|
| C-1 计数漂移 | §0：`27 claims / 49 artifacts / 44 semantic`、`50/50`；§7 同 | `check_claims` → `active claims 27 条 / artifact 49 个 / 语义项 44 条 -> 全过`；`negative_controls` → `负控: 50/50 ok` | ✅ 一致 |
| C-1 负控编号 | §R-A9：`NC-1..22 + NC-15b + NC-23..48` | artifact 实读 50 个 id = `PC-1` + `NC-1..48` + `NC-15b`（22+1+26+1 = 50） | ✅ 一致 |
| C-1 rubric | §7：`v5.1（R1–R57）` | `RUBRIC.md` 首行 `v5.1`；`CLAIMS.md:63` `## 红线条（R1–R57，挂账常设）` | ✅ 一致（但归属见 N-3） |
| C-2 R-A5 公式 | §R-A5 已改为两层：层A 六项相加 = 总数；层B `n_counted = n_solver_excluded + n_counted_excl_solver`，并明写「solver 在原始分母内……不得与层A 的排除项相加」 | `msr_l3.py` 的 `denominator_audit`：`55 = counted 51 + clarify 4 + unresolved 0 + notrun 0 + env 0 + unknown 0`；`counted 51 = solver 0 + counted_excl_solver 51` | ✅ 一致，且与 R52 实现逐字对齐 |
| C-3 §7 下一步 | §7：①9 条 v1.1 的 Abaqus 双码；②考卷 v7 | `verify_dataset`：`55 paired, 9 modeling-only -> MISMATCH`；`manifest.json` = 64 cases（25/17/22） | ✅ 一致 |
| C-4 协议入库 | （问题消除） | `git ls-files AGENTS.md CLAUDE.md` 两者均返回 ⇒ 已 tracked | ✅ 关闭 |

**headline / sha 三元组（§7 表逐行核对，全部一致）**：

```
top model = glm-5.3-flash        prov model = glm-5.3-flash     ← 顶层 == provenance（R-A8）
paper sha = 9c1faa3a731f2936     （tasks_v6c.jsonl 现读一致）
prompt sha = ce225186cafa5d55    （gen_candidates_v2.js --print-prompt-sha 现读一致）
exam TSR = 23/25 (92.0%)         MSR exam = 20/22   full = 41/51   solver_excl = 0
dev TSR = 22/30 (73.3%)          C-033 字段级 = 90.94%（Δ+5.0 BELOW）  ← §7 的 P2 描述属实
headline 结构判定：仅 C-032 的 status 列带「（对外 headline）」；C-031/C-033 = supporting；S-29 PASS
```

> 结论：**上一轮提的四条，老王全部按推荐 A 改了，且改对了**。协议现在与 live SOT 一致，可以照它开工。

---

## 2. 本轮新发现（重新检查才暴露出来的）

### N-1（高）`INDEX.md` §2 的「⓪ 当前官方 headline」仍写 **C-029**，且命令会重造 C-029 的成绩单

- **冲突点**：`AGENTS.md` §0 第 3 行要求「从 `reports/INDEX.md` 确认官方 artifact vs 诊断、**当前成绩单路径**」。而 INDEX 内部自相矛盾：§1 表说 headline = C-032，§2 复现命令的第一段却标着 C-029 是「当前官方 headline」。
- **SOT 文件 / 行**：
  - `feagpt_repro/reports/INDEX.md:12`（§1）：「**官方 headline（对外唯一可引用）** | `baseline_scorecard_L3_v6c_p2.json` …… **C-032**」← 正确
  - `feagpt_repro/reports/INDEX.md:49`（§2 注释）：「`# ⓪ 当前官方 headline（C-029，考卷 v6c × 候选 v6c）——先跑这三条就够`」← **与第 12 行冲突**
  - `feagpt_repro/reports/INDEX.md:53-62`：`score_baseline.py --candidates candidates_l3_v6c … --report reports/baseline_scorecard_L3_v6c.json --label "C-029 v6c (paper v6c, candidates v6c)"` + `msr_l3.py …`（全链 ccx 25–40 min）
- **期望值**：INDEX 的「当前官方 headline」只应指向 C-032（`baseline_scorecard_L3_v6c_p2.json` / `candidates_l3_v6c_glm_p2` / prompt v2）。
- **实际值**：§2 ⓪ 段指向 C-029（prompt **v1** 代、`candidates_l3_v6c`），并在其后另行标注「prompt v2 代……当前官方 headline = C-032」（第 78 行）——**同一文件里两个「当前」**。
- **证据**：
  ```
  $ sed -n '12p;49p;53p;78p' feagpt_repro/reports/INDEX.md
  :12  | **官方 headline（对外唯一可引用）** | `baseline_scorecard_L3_v6c_p2.json` … **C-032**（prompt v2 代…）
  :49  # ⓪ 当前官方 headline（C-029，考卷 v6c × 候选 v6c）——先跑这三条就够
  :53  "$PY" score_baseline.py --candidates candidates_l3_v6c \
  :78  # ===== prompt v2 代（W5c-6d，R50 修复后重跑；**当前官方 headline = C-032**）=====

  $ grep -n "INDEX" check_claims.py | wc -l
  0                      ← 44 项语义检查里**没有一条**读 INDEX.md，所以这条漂移没人拦
  ```
- **风险**：这是**导航级**错误，不是文风问题。一个按 §0 走的 agent 会：先读 INDEX → 命中 ⓪「当前官方 headline = C-029」→ 用 `candidates_l3_v6c`（prompt v1 代）重跑 `score_baseline` + 全链 MSR（25–40 min）→ 得到 23/25 的**同分但不同代**成绩 → 在 CLAIMS 里写成「headline 维持在 C-029」。正好踩 §5 红灯「用旧候选评新 paper」「跑完改了 paper/prompt 但没有新 sha/bridge」，且**不会报错**（数字看起来完全正常，因为两代 exam 都是 23/25）。
- **3 个选项**：
  - **A（推荐）改文本**：把 `INDEX.md:49` 的「当前官方 headline（C-029…）」改成「prompt v1 代对照（C-029，`historical`，**不是当前 headline**；复现只用于 `prompt_v2_effect_glm` 消融）」，并把 ⓪ 段标题改为「⓪ 开工先跑（与 headline 无关的三条前置闸）」。**只改注释与标题，不动任何命令、不动任何数字**。
  - B. 改 artifact：不适用——C-029 的成绩单本身没错（它是历史成绩，且已被 C-032 取代），错的是 INDEX 给它加了「当前」二字。
  - C. 标 diagnostic：不适用（这是路径指向，不是统计口径）。
- **建议 + 风险**：选 **A**。风险极低（纯注释/标题），收益是消除「同一个 INDEX 两个当前 headline」。**必须在下一个任务开工前修**，否则 R-A11 的「发现两个 headline」这一条会在下一个 agent 身上复现（只不过这次是文档里的两个，不是 claim 里的两个）。

### N-2（中低）`INDEX.md:24` 负控编号写成 `NC-23..47`，但同格又在列举 `NC-48`，总数 50/50

- **冲突点**：R-A4 要求「计数类文本必须从 artifact 重新计算」。这一格的范围与总数/枚举自相矛盾。
- **SOT 文件 / 行**：`feagpt_repro/reports/INDEX.md:24`（§1「负控」行）
- **期望值**：`NC-23..48`（全仓唯一正确写法，`CLAIMS.md` C-019 已写 `NC-43..48`）
- **实际值**：`NC-1..22 + NC-15b + **NC-23..47**（含 NC-43..46……**NC-47 四向**……**NC-48 三向**）= **50/50**` —— 区间差 1，与「= 50/50」不闭合（22+1+25+1 = 49）。
- **证据**：
  ```
  $ python -c "import json; d=json.load(open('reports/negative_controls_50.json')); print(len(d['results']))"
  50     ids = PC-1 + NC-1..48 + NC-15b   ⇒ NC-23..48 才是对的

  $ grep -rn "NC-23\.\.47" --include=*.md FEM-Bench-Aero feagpt_repro/reports AGENTS.md CLAUDE.md
  feagpt_repro/reports/INDEX.md:24   ← 全仓仅此一处
  ```
- **风险**：低（不影响任何判定），但它出现在**做 pre-flight 时第一眼看的文件**里；一个较真的 agent 会发现「范围与总数不闭合」，按 R-A11 应当停下写 CONFLICT —— 也就是**这条会持续制造假冲突**，消耗下一轮的时间。
- **3 个选项**：**A（推荐）改文本**：`NC-23..47` → `NC-23..48`（一字）；B. 不动，靠人说「以 json 为准」→ 假冲突会复现；C. 把该格的编号段整段删掉只留 `= 50/50` → 丢掉了 R-A9 要求的「总数 + 编号集合」。
- **建议**：选 **A**。

### N-3（低）`AGENTS.md` 把「R1–R57 红线」归给 `RUBRIC.md`，但 RUBRIC 只有 R42–R57

- **冲突点**：§0 第 2 行说读 `RUBRIC.md` 可确认「R1–R57 红线」。实际 RUBRIC 的红线表只有 **16 行 = R42–R57**；R1–R41 的挂账清单在 `CLAIMS.md:63` 的「红线条（R1–R57，挂账常设）」。
- **SOT 文件 / 行**：`AGENTS.md:14`（§0 第 2 行）、`AGENTS.md:252`（§7 rubric 行）；对照 `RUBRIC.md` 红线表首行 L222 = `R42`、末行 L274+ = `R57`；`CLAIMS.md:63`
- **期望值**：读 R1–R41 应去 `CLAIMS.md`；RUBRIC 提供 R42–R57 的完整判定表 + 判分口径。
- **实际值**：`grep -c "^| \*\*R" RUBRIC.md` = **16**（R42…R57 连续，无缺号）；R1–R41 在 RUBRIC 里只出现在版本记录散文里。
- **证据**：
  ```
  $ python -c "import re;s=open('FEM-Bench-Aero/RUBRIC.md').read();n=[int(x) for x in re.findall(r'\n\| \*\*R(\d+)\*\*',s)];print(len(n),min(n),max(n))"
  16 42 57
  $ sed -n '63p' FEM-Bench-Aero/CLAIMS.md
  ## 红线条（R1–R57，挂账常设）
  ```
- **风险**：低但真实 —— agent 会「在 RUBRIC 里找不到 R15/R33/R41」，然后要么以为红线丢了（触发 R-A11 假停），要么直接跳过 R1–R41。
- **3 个选项**：**A（推荐）改文本**：§0 第 2 行 →「当前 rubric 版本；**R42–R57 红线判定表**（R1–R41 见 `CLAIMS.md` 红线条）；分母/判分口径」；§7 行同理加一句归属。B. 把 R1–R41 搬进 RUBRIC → 等于重排官方文档、风险远大于收益。C. 不动。
- **建议**：选 **A**（一行改动，把「去哪找」说准）。

### N-4（低）`R-A7` 的判据是自然语言，字面搜索会找到 **6** 条 headline

- **冲突点**：R-A7 写「恰好一条 active claim **标注**『对外 headline』」。按字面 grep，`CLAIMS.md` 有 **6** 条 claim 含这串字（C-025 / C-028 / C-029 / C-021 / C-030 / C-032），因为其中 5 条是在正文里**否定或引用**（「不再是对外 headline」「当前 headline 见 C-029」）。
- **SOT 文件 / 行**：`AGENTS.md:79`（R-A7）；对照 `RUBRIC.md:222`（R42 的判据已写对：「**状态列**带『（对外 headline）』」）与 `check_claims.py` 的 S-29（读 `status` 字段）
- **期望值 / 实际值**：结构化判定 = **1 条（C-032）**，S-29 PASS；字面判定 = 6 条。
- **证据**：
  ```
  $ grep -c "对外 headline" CLAIMS.md   →  6 行命中（其中 5 行是否定/引用）
  status 列实读：C-032 = **active（对外 headline）**；其余含该词的行 status 分别为
    C-029「superseded…**不再是对外 headline**」/ C-028「diagnostic lower bound…headline 见 C-029」等
  ```
- **风险**：中低 —— 正是 S-29 第一版栽过的坑（「判据别用自然语言表述」，当时把 C-029 自己过滤掉了）。同一坑第三次以「协议措辞」的形式出现。
- **3 个选项**：**A（推荐）改文本**：R-A7 第一句补「**以 status 列（`check_claims` 的 S-29）为准**，正文提及不算」，与 R42 措辞对齐。B. 清掉正文里的所有「对外 headline」字样 → 会失去「C-029 已被取代」这个关键说明，不划算。C. 不动，靠执行者理解 → 下次仍会误判。
- **建议**：选 **A**。

### N-5（低，工程卫生）pre-flight 自己会把工作区弄脏：`check_claims.json` 记录 artifact 的 `mtime`

- **冲突点**：§0 要求每次开工先跑 `check_claims`；而该命令会把每个 artifact 的 `mtime` 写进**已被 git 追踪**的 `reports/check_claims.json`。于是「先跑 pre-flight」必然产生一个 diff，与 C5「`git diff` 只含 allowlist 文件」字面冲突。
- **SOT 文件 / 行**：`feagpt_repro/reports/check_claims.json`（`results[].mtime`）；`AGENTS.md` §0 / C5
- **实际值**：本轮只跑了 §0 的两个命令，`git status` 就出现 `M feagpt_repro/reports/check_claims.json`（`git diff` = 1 行：`"mtime": 1793105624 → 1793108196`，`sha256` 未变）。
- **证据**：
  ```
  $ git diff feagpt_repro/reports/check_claims.json
  -   "mtime": 1793105624
  +   "mtime": 1793108196      ← 只是 negative_controls_50.json 的 mtime，sha256 逐位相同
  ```
- **风险**：低（无判定影响），但会训练出「对 diff 麻木」的习惯，正好削弱 C5。
- **3 个选项**：**A（推荐）改代码（小）**：把 `mtime` 从 `check_claims.json` 里去掉（身份用 `sha256` 已经足够；`mtime` 无判定作用），或加 `--no-write` 只打印；**这属于改 harness，必须单独一个任务 + 单变量 contract**。B. 把 `check_claims.json` 加进 `.gitignore` → 违反 R-A3「官方数字必须有 git 追踪的 artifact」。C. 在 §0 注明「跑完 pre-flight 后 `check_claims.json` 的 mtime 差异属预期」→ 最省事，但留下噪声。
- **建议**：本轮只做 **C**（一行说明）；**A** 排进 follow-up，不夹带。

---

### N-6（高）`gate3_all55.py` 把 v1.1 新增的 5 条翼盒标成 **field-level**，但该文件里没有它们的场级读数

- **冲突点**：翼盒分支（`gate3_all55.py:48-65`）不自己算场级，而是到 `gates_all55_d36.json::gate3_dual_solver` 里按 `case_id` 找明细；**找不到时 `idx = None`**，于是 `pass = wingbox_ref.get('pass')`（整体 PASS）且 `disp_gap_pct = None`。v1.1 新增的 5 条翼盒在 d36 写于 2026-10-24，**当时这些 case 还不存在** ⇒ 必然 `idx is None` ⇒ **等级是 field-level，证据是空的**。
- **这正是红线 R2 的镜像**：R2 说「reported-only 不得计入 PASS」，而这里是「无读数不得计入 field-level」。
- **SOT 文件 / 行**：`feagpt_repro/gate3_all55.py:51-65,121`；artifact `FEM-Bench-Aero/gate3_all55_d37.json`
- **实际值**（本轮实跑，64 条 manifest）：
  ```
  gate3_all55: gated_pass=57 reported_only=7 fail=0 (field=39, scalar_disp=18)
  新增 5 条翼盒：evidence_level='field-level (displacement nodes + vM median)', pass=True, disp_gap_pct=None
  ```
  其中 `n_gated_pass=57` 把 5 条无证据的算成了 GATED。
- **证据（本轮已实测，可补真读数）**：`reports/diagnostics/xval_v11_9cases.json`（由 `parse_xval_v11_log.py` 从 `_v11_xval_9cases.log` 转录，未做算术）

  | case | max\|u\| 差 | vM 逐节点中位差 | p90 |
  |---|---|---|---|
  | naca4412_wingbox_n_ribs6_chord1000 | 0.385 % | 0.37 % | 36.69 % |
  | naca4412_wingbox_size_chord900 | 0.401 % | 0.29 % | 38.97 % |
  | naca4412_wingbox_size_skin2p5 | 0.392 % | 0.32 % | 35.15 % |
  | naca4412_wingbox_str4 | 0.291 % | 0.75 % | 67.51 % |
  | naca4412_wingbox_taper070 | 0.268 % | 0.17 % | 24.68 % |

  中位差全在 0.17–0.75 %（门槛 5 % 内），max\|u\| 全在 0.27–0.40 %（门槛 1 % 内）⇒ **实测结论与「PASS」一致，问题只在证据链断裂，不是结论错**。
  p90 高（25–68 %）是翼盒族已知特性：峰值落在 spar/rib 交汇的网格依赖点上，中位差才是判据（C-003 的 field-level 定义）。
- **3 个选项**：
  - **A（推荐）补证据**：`gate3_all55.py` 翼盒分支在 `idx is None` 时读 `reports/diagnostics/xval_v11_9cases.json`，把这 5 条标成 `field-level (measured 2026-10-28)` 并带上 `disp_gap_pct` / `vm_median_gap_pct`。对外表述随之变 **39 field + 18 scalar-disp + 7 reported-only**。代价：gate3 多一个输入文件依赖，须同时改 `check_claims` 的 artifact 清单（或确认它在 allowlist 里）。
  - **B（保守）降级**：把这 5 条按 `scalar-level` 判（只比 `max_disp < 1 %`），不声称场级。代价：明明测了逐节点中位差却不用，等于**低估**证据，且与翼盒族其余 34 条口径不一致。
  - **C（不改判定，只改标注）**：保留 PASS 但把 `evidence_level` 改成 `field-level (inherited, no per-case reading)`，并从 `n_gated_pass` 里剔除（`57 → 52`）。代价：artifact 内部自相矛盾（PASS 却不计入 gated_pass）。
- **建议**：**A**。理由：实测数字已经在手，B 是丢弃证据、C 是制造内部矛盾；A 只改「证据从哪来」，不改任何阈值、不改判定方向，符合 R-A1 单变量（变量 = 证据来源，不是 rubric）。

> **★ 执行时查出的真因（比上面的初判更严重，2026-10-28 老王拍板 A 之后）**
>
> 按 A 改代码时发现：`gates_all55_d36.json::gate3_dual_solver` **`rows` 是存在的**（34 条明细全在），
> 但明细键名是 **`case`**，脚本查的是 **`case_id`** ⇒ `item.get('case_id')` 恒 `None`
> ⇒ **34 条一次都没命中过**，全部走 `idx is None` 的「继承整体 PASS」。
>
> 即：**问题不是「新增 5 条没证据」，而是「39 条翼盒从来没有任何一条被逐条读取过」**。
> 旧版 `n_gated_pass` 里那 34 条与 5 条一样，都是 `wingbox_ref['pass']` 的一个复制品。
> 这解释了为什么 `disp_gap_pct` 一直是 `None`——不是新 case 缺，是**所有翼盒都缺**。
>
> 第二层：即使命中，旧代码取的是 `idx.get('max_disp_gap_pct')`，而 d36 的字段是
> `max_disp.gap_pct`（嵌套）。而且 **`max_disp.gated = false`** —— 翼盒登记判据不是
> `max|u| < 1%`，而是 **`stress_field.median_pct < 5%`**（`stress_field.gated = true,
> tol_pct = 5.0`），`max|u|` 与 vM 峰值都是 REPORTED NOT GATED。**按 1% 判翼盒是口径错**
> （我第一版就是这么写的，已改回与 d36 同口径）。
>
> 修完实测：`gate3_all55: cases=64 gated_pass=57 reported_only=7 fail=0 (field=39, scalar_disp=18)`，
> `headline_cn = 39 field (34 d36 + 5 measured) + 18 scalar-disp + 7 reported-only`，
> **翼盒 vm_median 缺失 0 条**（39/39 都有真读数），`rc=0`。

### N-7（中）`gate3_all55.py` 第 141 行的对外表述是**硬编码**，与实际计数不符

- **冲突点**：脚本自己算出 `field=39, scalar_disp=18, reported_only=7`，但第 141 行 `print` 写死「34 field + 15 scalar-disp + 6 reported-only」；第 117–119 行的 `note` 也是写死的。
- **SOT 文件 / 行**：`feagpt_repro/gate3_all55.py:117-119,141`
- **实际值**：实际 39/18/7（64 条），文本说 34/15/6（55 条）。
- **违反**：R-A4「计数类文本（行数、条数、负控数、exam 数、族分布）必须从 artifact 重新计算，不得沿用上一版」。
- **风险**：中。`CLAIMS.md` C-003 的「34 field + 15 scalar-disp + 6 reported-only」是**同一组数字的另一个副本**；脚本 console 输出又一份。两份都会随 64 条过期，且没有任何闸能同时看住（`check_claims` 只读 claim 文本 + artifact 的 sha，不读脚本 print）。
- **3 个选项**：**A（推荐）**改成从 `report` 现算打印 + `note` 现算拼字符串；B. 删掉这行 print，只留 `gated_pass/reported_only/fail` 数值；C. 不改，等 v7 一并重写。
- **建议**：**A**，且与 N-6 同一次提交（同属 gate3 证据链，不是两个变量）。

### N-8（低，命名债）`gate3_all55_d37.json` 装的是 64 条，文件名还带 `all55`

- **冲突点**：v1.1 把数据集扩到 64 条，artifact 未改名；`check_forms_v11.json` 同理（54 项，名字不带项数，尚可）。
- **SOT 文件**：`FEM-Bench-Aero/gate3_all55_d37.json`（被 `CLAIMS.md` C-003 的 artifact 列引用）
- **风险**：低，纯命名。但它是「文件名暗示分母」的典型陷阱——下一个读的人会以为还是 55 条。
- **3 个选项**：**A（推荐）**不改名（改名要同步改 C-003 + `check_claims` 的 artifact 清单，属于跨文件连锁），改为在 `note` 字段首句写明「文件名保留历史，内容为 64 条（v1.1）」；B. 改名 `gate3_all64_v11.json` + 同步三处引用；C. 不动。
- **建议**：**A**，并在 `DATASET_V11.md` 的 artifact 表里注明。

### N-9（中，新发现）`external_numbers.md` 前段跟到 64 条、后段仍读 `*_d36` 死快照 ⇒ 表内自相矛盾

- **冲突点**：生成器 `make_external_numbers.py` 前 7 行读 `manifest.json`（活数据，已跟到 64 条：算例 64×2=128、等价类 63、划分 25/17/22、族分布 7/13/5/39），但后 5 行读的是 `gates_all55_d36.json` / `gate4_d36.json` / `verify_dataset_d36.json` / `eval_report_d36.json` 四份 **10-24 的静态快照** ⇒ 同一张表里「64 条」和「关 1 网格 55/55」「关 4 语义 110/110」「自洽 110/110」并存。
- **SOT 文件 / 行**：`feagpt_repro/make_external_numbers.py:37-39,138,143,145`；输出 `FEM-Bench-Aero/external_numbers.md`
- **实际值**（重跑生成器后）：
  ```
  | 算例规模 | 64 条 × 2 棵求解器树 = 128 个算例目录 | manifest.summary |
  | 关 1 网格 | 55/55（最差 minJ 0.4636、tri3 0） | gates_all55_d36 |   ← 旧
  | 关 3 双码 | 39 field-level + 18 scalar-disp-gated + 7 reported-only（不说 64/64） | gate3_all55_d37 |
  | 关 4 语义 | 110/110 | gate4_d36 |                                  ← 旧
  | 自洽 | 110/110、重复 0、配对 True | verify_dataset_d36 |            ← 旧
  ```
- **风险**：中。这是**对外数字表**，一旦对外引用「自洽 110/110」而实际是 128，就是给外部一个错数。而且它不会被任何闸发现（`check_claims` 不读 `external_numbers.md`）。
- **已做的最小修复**：把两处硬编码的「（不说 55/55）」改成从 `g3all['n_cases']` 现算 —— 这属 N-7 拍板的「计数一律现算」范围，零风险。
- **3 个选项**：**A（推荐）**做一个独立任务：为关 1 / 关 4 / 自洽三项各生成一份 v1.1 的活 artifact（`check_forms_v11.json` 已有 54/54；`verify_dataset.py --json` 可出 128/128；关 4 需重跑 `gate4`），再把 `make_external_numbers.py` 的四个 `_d36` 引用换成 v1.1 版；B. 只改文本，把后 5 行标注「（v1.0/55 条口径，未随 v1.1 重算）」——诚实但对外表半旧；C. 整表退回 55 条口径，等 v7 一并重算 —— 会让已更新的前 7 行又变错。
- **建议**：**A**，作为 **T-A8** 单独立项（变量 = 对外数字表的数据源），不夹在 T-A7 里。
- **处置（2026-10-28，T-A8 已完成）**：按 **A** 落地，但执行时范围比原判更大。
  1. **新建三份 v1.1 活 artifact**：`gate4_v11.json`（128/128）、`verify_dataset_v11.json`（128/128）、
     `eval_report_v11.json`（0 failures）。命令即生成命令（R26），全部用 venv。
  2. **关 1 改为从 `manifest.readings` 现算**，不再读 `gates_all55_d36.json`。理由：gate1 的真相
     本来就是逐条 readings，而 `min_jacobian` / `n_tri3` **每一条**都被 `eval_dataset.py` 用
     `msh_quality` 与 `model.inp` 独立复算过（不是抽检）⇒ 从 manifest 现算不产生副本，读快照才产生副本。
  3. **表加「分母口径」列**（R54）：关 1/关 3/划分复算 = **spec 数**；关 4/自洽 = **算例目录数**
     （= spec 数 × 2 树）。原表把 55/55 与 110/110 并列却都不标分母——**那两个数从来不是同一个分母**，
     只是恰好都"全过"才没暴露。表尾新增「分母口径警告」段。
  4. **基线与 M14 三条限制标注版本**：基线是 v1（翼盒 test 6 条）冻结，v1.1 翼盒 test 11 条
     ⇒ 不可并列（R30/R39）；M14「全体 34 条留一」原先是硬编码字面量，改为从
     `_probe_m14/all_loo.json` 现读（n_cases=34 就是 artifact 里的值），并标注「v1 口径、v1.1 未重跑」。
  5. **溢出发现两处**（不在 N-9 原描述里，但同属「对外表写死数字」）：
     - `FEM-Bench-Aero/README.md` 的**目录布局**写着「manifest 53 条 → 52 等价类」「gate4.json 80/80 PASS」
       「verify_report.json 80/80 OK」——**比 55 更旧的 40/53 条口径**。已改为不报数、只述用途，
       并加一句「各闸当前读数只在 `external_numbers.md`」⇒ README 不再是第二个数字源。
     - README 的「门禁结论」表：关 1 55/55 → **64/64**、关 4 110/110 → **128/128**、
       自洽 110/110 & 跨树 55/55 & 配对 55/55 → **128/128 & 64/64 & 64/64**。
       关 3 那一行是 D34/D36 的实测记录（翼盒 34 + 其余 21），**保留原样**并加指针说明当前分级只看
       `external_numbers.md`（改数字会让 D34 假 FAIL 的实证失真）。
  6. **CLAIMS 四条同步**：C-001（55→64 条 / 110→128 目录）、C-002（关 1 55/55→64/64，artifact 改为
     `manifest.json::readings`）、C-004、C-005（110/110→128/128、配对 55→64，artifact 改 `_v11`）。
- **遗留（→ N-12）**：这批新 artifact 与 C-001/C-002/C-004/C-005 的计数**仍然无闸**——
  `grep "gate4_v11\|verify_dataset_v11\|external_numbers" check_claims.py negative_controls.py` = **0 命中**。
  S-48 只覆盖 C-003。这与 N-10 同型，须另立任务（S-49）。

### N-10（高，新发现）C-003 的三个计数**没有任何闸**校验

- **冲突点**：`check_claims.py` 里 `grep -n "gate3\|C-003"` = **0 命中**。它对 artifact 只做通用的「文件存在 + sha256 记录」，**不校验 claim 文本里的数字是否等于 artifact 里的数字**。所以 C-003 的「34 field + 15 scalar-disp + 6 reported-only」可以从 55 条时代一直漂到 64 条时代而全程绿灯——正是本轮 T-A7 之前的状态。
- **SOT 文件**：`feagpt_repro/check_claims.py`（48 项语义检查里没有一项覆盖 C-003）；`FEM-Bench-Aero/CLAIMS.md:11`；artifact `FEM-Bench-Aero/gate3_all55_d37.json`
- **证据**：
  ```
  $ grep -n "gate3\|C-003" feagpt_repro/check_claims.py
  （无输出）
  $ python check_claims.py    # 在 C-003 写着 34/15/6、artifact 已是 39/18/7 的状态下
  active claims 27 条 / artifact 49 个 / 语义项 48 条 -> 全过      ← 全绿
  ```
- **正是 R58 说的那类洞**：「没有任何工具读的文件 = 没有闸」。C-003 是**数据类** claim（R58 边界内），本该被闸读，却没有。
- **风险**：高。它是「关 3」这个对外数字的唯一 claim，三个计数全无护栏；下一轮 v7 换卷时它还会再漂一次，而没有任何东西会响。
- **3 个选项**：**A（推荐）**新增 **S-48 + NC-53**：断言 `CLAIMS.md` C-003 行里的 `N field` / `N scalar-disp` / `N reported-only` 三个整数分别等于 `gate3_all55_d37.json` 的 `evidence_levels.field` / `.scalar_disp` / `.reported_only`；负控三向（改大 / 改小 / 删掉该行）必须判红。B. 让 C-003 改成**指针式**（只写「见 gate3_all55_d37.json 的 evidence_levels」，不写数字）——彻底消除漂移面，但 CLAIMS 的可读性下降，且对外引用要两跳。C. 不管，靠人工 review。
- **建议**：**A**，作为 **T-A9** 单独立项。这条闸与 S-44（INDEX 与负控编号对齐）同源，都是「文本里的计数必须等于 artifact 里的计数」，可以直接复用 S-44 的解析骨架。
- **处置（2026-10-28，T-A9 已完成，`8efdbbe`）**：按 **A** 落地 **R62 / S-48 / NC-53 四向**。执行时把判据从「三向」扩到四条——除三个计数逐项相等外，还加 **(b) 加和闭合（三者之和 == `n_cases`）**、**(c) 构成闭合（`N 条 d36` + `N 条 <日期> 实测` == field）**、**(d) 分母对齐（`不说 N/N` == `n_cases`）**；负控相应扩到四向（field−1 / scalar−2 / d36+1 / 删分母）。**关键设计：任一计数解析不出来一律判红，不得 skip**——锚点缺失与写错同罪，丢了就没人核，闸会退化成永远绿（R29 同源）。实测：负控 **55/55**、语义 **49/49** 全过，S-48 明细 `field=39; scalar-disp=18; reported-only=7; 加和 64=64; 构成 34d36+5实测; 分母 64/64`。
  > 同轮发现并修掉一处制度性混乱：根目录原同时留 `_53`、`_54` 两份「上一代」负控，而 RUBRIC 写「`_53` 为上一代」、CLAIMS 写「`_54` 为上一代」，两处互相矛盾。现已把 `_53`/`_54` 一并移入 `reports/archive/`，根目录只留现行 `_55`。

### N-12（高，T-A8 执行时发现）换完数据源，新数据源**依然没有闸**

- **冲突点**：`grep -n "gate4_v11\|verify_dataset_v11\|eval_report_v11\|external_numbers" check_claims.py negative_controls.py`
  = **两文件均 0 命中**。也就是说：
  - `external_numbers.md` / `.json`（**对外数字的唯一来源**）没有任何工具读；
  - 新建的 `gate4_v11.json` / `verify_dataset_v11.json` / `eval_report_v11.json` 没有任何工具读；
  - C-001 / C-002 / C-004 / C-005 的 `coverage` 列（64/64、128/128）**不受 S-48 管**——S-48 只解析 C-003 那一行。
- **为什么算高**：这正是 N-10 的同型，而 N-10 的代价是 C-003 从 `34/15/6` 漂到 `39/18/7` **全程绿灯**。
  T-A9 只给一条 claim 加了闸，其余四条仍裸奔；而 T-A8 刚刚把这四条指向了新 artifact，
  **下一轮只要有人改数据集而不重跑生成器，`external_numbers.md` 就会再次变成 55/64 混杂，且无任何信号。**
- **风险**：高。它不制造错数，但它保证「错数不会被发现」。
- **3 个选项**：
  - **A（推荐）**：把 S-48 泛化成 **S-49**——对 C-001/C-002/C-004/C-005 逐条断言
    「claim 的 `coverage` 分子/分母 == 其 artifact 的实读计数」；再对 `external_numbers.md` 加一条
    「md 里的每个闸门读数 == 生成器从 artifact 现读的值」（等价于 `make_external_numbers.py --check` 的严格版：不一致就 rc≠0）。负控两向（改 claim 计数 / 改 md 数字）。
  - B. 让 C-001/C-002/C-004/C-005 全部改成**指针式**（只写 artifact 名不写数），彻底消除漂移面。
    代价：CLAIMS 的可读性下降（这是对外引用的一跳入口），且 `coverage` 列会整体失去意义。
  - C. 不管，等 v7 换卷时一起做。风险：v7 恰好是**最会改这批计数**的动作（64→73 条），
    没有闸就是在裸奔——与当初「T-A3 先于 v7」同一条理由。
- **建议**：**A**，作为 **T-A10** 单独立项，且**排在 v7 之前**。理由与 T-A9 完全相同：
  v7 会把 exam 25→34 并重算一批计数，闸先于它会便宜得多。
- ✅ **处置（T-A10 已完成）**：选 A 并扩成三条闸 + 一条 claim + 十向负控。
  - **S-49**（`claim_counts_consistent`）：覆盖 **C-001 / C-002 / C-004 / C-005 / C-036** 五条，
    判据逐条落到结构化记号（规模 = 条数×树数=目录数；关 1 按**正文自己声明的阈值**现算通过数；
    关 4 / 自洽 / 配对直接对 artifact；C-036 对四份 v1.1 活源）。**任一锚点解析不出即判红**。
  - **S-50**（`external_numbers_consistent`）：没有采用「逐行对 artifact」这种脆弱做法，
    而是把 `make_external_numbers.py` 重构出**纯函数 `build()`**，让闸**重跑生成器并逐字节比对**
    （把「陈旧」和「手改」一次性覆盖），另加三条语义判据：分母口径列在场 / 每个 `A/B` 的
    `B ∈ {spec 64, 目录 128}` 且 `A==B` / 两套分母都出现。
  - **S-51**（`protocol_no_hardcoded_counts`）：新增 R63 —— 协议文件**不得写死**可推导计数。
    ★ 这里改了原提议：专家 §6 建议「写死 counts + S-49 核对」，老王拍板改为
    **「不写死，以 §0 实读为准」**。理由是这些数就是两个闸脚本自己的输出，抄进文档
    等于制造第二数据源，而**第二数据源必然漂**（N-1/N-2/N-10/N-12 全是这个形态）。
    原提议还会让 R58「不用闸校验协议文本」的边界失效；改法既消掉漂移面，又保住边界。
  - **C-036**：新增 v1.1 数据层 claim（`check_forms 54/54`、`双码配对 64/64`、
    `gate4 128/128`、`eval 64/0`）。★ 它补的正是原账本的空白：**`check_forms 54/0` 与「9/9 双码」
    此前不在任何 claim 里**，却在 DATASET_V11 与对外文档反复使用。
  - **NC-54 十向**，且**每向断言「红的原因对」**——因为 S-50 的陈旧判据几乎能吃下任何变异，
    若只断言「是否红」，(a) 缺分母列与 (b) 分母混写这两条会永远得不到证伪。
  - 实测：`check_claims` 28/54/52 全过；负控 56/56；NC-54 十向全红且原因命中。

### N-13（中，T-A10 执行时发现）`manifest.summary.xval_cases_available` 停在 55

- **冲突点**：`manifest.json` 的 `summary.xval_cases_available` = **55**，而 `verify_dataset_v11.json`
  的 `pairing.paired` = **64**（`_xval/` 9 个目录 10-28 21:32 就跑完了）。`MANIFEST.md` 同段也写「55 条」。
- **根因**：这两个字段由 `make_manifest.py` 的 `paired` 写入，而 **manifest 自 10-24 之后没重跑过** ——
  双码补跑只往 `_xval/` 加了目录，没有回头重生成清单。**没有任何闸读这个字段**（S-49 只读 `n_cases`
  与 `cases[].readings`），所以它漂了整整一天没人发现。
- **处置**：先 dry-run 到临时路径**逐键比对**，确认重生成只改这一个键：
  ```
  差异键数 = 1
    /summary/xval_cases_available   new=64  old=55
  splits 相同: True {'train': 25, 'val': 17, 'test': 22}
  ```
  确认后重生成 `manifest.json` + `MANIFEST.md`，`git diff` 各 **1 行**。
- **为什么不能直接重生成**：R-A2「先冻结后运行」——`make_manifest` 会重算 `split_of(spec)`，
  若划分规则被动过，重跑就会静默改掉 25/17/22。**必须先证明「除目标键外零差异」再落盘。**

### N-14（中，T-A10b）`AGENTS.md` §7 快照比专家指出的过期更多

- **专家指出**：CLAUDE 仍写 27/49/49（实测确认）。
- **实际**：`AGENTS.md` 有 **5 处**，且不只计数：
  1. `:21` §0 → 27/49/49（应 27/50/49）
  2. `:26` §0 → 「`check_claims` / `negative_controls` **两道文本闸可用系统 python**」
     —— **实测证伪**：`python negative_controls.py` 直接 `ModuleNotFoundError: No module named 'numpy'`
     （NC-52 要真跑求解冒烟，链路 import `feagpt.geometry`）。**专家自己的附录 A.2 也写了 `SYS="python"`
     然后拿它跑负控，照抄会失败。**
  3. §0 表格 → 「R42–R58 红线判定表 / R1–R58」落后 4 条红线
  4. §7 → 「rubric v5.2」落后 3 个版本
  5. §7 → 下一步仍写「9 条 v1.1 的 Abaqus deck 已备，在 WorkBuddy 外跑 bat」——**10-28 21:32 已完成**
- **处置**：按 D5(b) 去掉全部写死计数（改「以 §0 实读为准」），并修 2/3/4/5 四处事实；
  新增 **S-51** 防计数被抄回去。

### N-15（高，v7 paper 开工前）「9 条只当 dev」会把 test 变成 dev

- **冲突点**：老王在 v7 开工前拍板「exam 保持 25，9 条只当 dev」。但实测 9 条在
  `manifest.json` 里的 `split` **全部是 `test`**：
  ```
  naca4412_wingbox_taper070 / open_hole_panel_400x200_d30 / stiffened_panel_700x600_str4 …
  9 条全部 test；全量 {'test': 22, 'val': 17, 'train': 25}
  ```
  而 v6c 的「dev」= **30 条 = train 13 + val 17，一条 test 都没有**。
- **为什么是冲突**：把 9 条 test 放进 dev，dev 就不再与 test 互斥。此后任何一轮
  基于 dev 的调参（prompt 措辞、判分细则、阈值）都会直接污染这 9 条，
  它们**再也不能当留出证据**——不是"数字不可比"，是**证据不再独立**。
  这条比 R30/R39 更根本：R30 说的是"不同卷不能相减"，这里连"卷"的定义都会被破坏。
- **而且它达不到原目的**：exam 仍 25，CI 仍宽，统计有效性仍是 2/3。v1.1 造这 9 条
  的原始动机（`DATASET_V11` §1：exam n=25 ⇒ CI95 宽到 [80.0, 100.0]，4 pp 差异判不显著）
  一条都没被解决。
- **3 个选项**：
  - **A（推荐）双分母并列**：9 条进 exam 的**新栏** `interpolation_v11`，
    同时报两个分母——`exam_legacy = 25`（与 C-032 **同卷可比**）与 `exam_full = 34`（含新增）。
    R54 只禁止**跨分母相减**，不禁止**并列报告**；桥表（bridge）本来就是为这种场景存在的。
    ⇒ 既保住与 C-032 的可比性，又用上这 9 条、把 CI 收窄。
  - B（原拍板）：9 条当 dev。代价见上——dev 与 test 不再互斥，且统计不改善。
    若坚持 B，必须同时在 `DATASET_V11` 与 `RUBRIC` 显式登记「dev 含 9 条 test，
    因此 v7 起 dev 不再是留出集」，并且此后**不得**再用 dev 数字做任何"新设计泛化"的论证。
  - C：9 条标 `heldout_ungraded`，既不进 exam 也不进 dev。最保守、无污染，
    但等于 v7 只做了数据层，任务层白扩。
- **建议**：**A**。理由：它是唯一同时满足「保住 C-032 可比」「用上 9 条」「不污染留出」的方案，
  且实现代价很小（多一栏 `exam_stratum=interpolation_v11` + 成绩单多两个分母字段）。
  **B 的代价是永久的，A 的代价只是一栏字段。**
- **待老王重新拍板后再开 v7 paper。**
- **✅ 已拍板（老王，2026-10-28）：A —— 双分母并列。** 落实要求：9 条标
  `exam_stratum = interpolation_v11`，成绩单同时报 `exam_legacy = 25` 与 `exam_full = 34`；
  R54 只禁跨分母相减，不禁并列。

### N-16（**高，阻断 v7 paper**）数据集扩容会**改写已有 case 的 L2 卷子**

- **怎么发现的**：按 R-A2「先冻结后运行」，跑完 `make_tasks.py`（55→64）后，
  把 `tasks/tasks.jsonl`（183 行）与 git HEAD 版（165 行）逐条比对，**不按行号按 `task_id`**：
  ```
  L1: 旧 55 新 64  字节级差异 0        ← 干净
  L3: 旧 55 新 55  字节级差异 0        ← 干净
  L2: 旧 55 新 64  字节级差异 48  ★★★
  ```
- **不是键序、是内容**：
  ```
  L2_fuselage_barrel_d2000_l2000_str12_frm4   ['n_frames']        -> ['thickness']
  L2_fuselage_barrel_d2000_l2000_str8_frm3    ['thickness']       -> ['n_stringers']
  L2_naca4412_wingbox                         ['rib_thickness']   -> ['n_stringers_per_skin']
  L2_naca4412_wingbox_n_ribs3_chord1000       ['n_stringers_per_skin'] -> ['stringer_height']
  ...  48/55 条被改写（只有 7 条恰好不动）
  ```
  覆盖分布也整体漂移：旧 `rib_thickness:5 / n_stringers_per_skin:5 / stringer_height:5 …`
  → 新 `rib_thickness:5 / n_stringers_per_skin:6 / stringer_height:6 …`。
- **根因（一行代码）**：`make_tasks.py:156`
  ```python
  l2, omitted = make_l2_input(norm, fam, rotate_idx=stats['L1'])   # ← stats['L1'] = 已处理 L1 累计数
  ```
  `rotate_idx` 取的是**全局累计计数**，而 v1.1 的 9 条新 case **散布在 manifest 中间**
  （idx 3 / 11 / 16 / 19 / 28 / 40 / 52 / 56 / 61），不是追加在末尾
  ⇒ 排在每个新 case 之后的老 case，`rotate_idx` 全部 +1，省略字段沿池子整体滑动一格。
  注释写着「按 case 序轮换」——**看起来是确定性轮换，实际是位置耦合**：
  只要数据集条数/顺序变化，已发布卷子就会被静默改写。
- **为什么这是硬问题**（比 N-15 更根本）：
  1. **v6c 的 L2 子集失去可复现性**：`tasks.jsonl` 是唯一真源，一旦重生成，
     老 55 条的 L2 题目就变了；v6c 的 L2 成绩此后只能引用存档成绩，**不能重跑**。
  2. **v7 vs v6c 的 L2 不是同一张卷**：`input` 少的是不同字段 ⇒ 题目难度/考点都变了，
     跨版本比较 L2 通过率是**伪造的归因**（R30/R54 管的是"分母不同"，这里连"题不同"）。
  3. **现有闸一个都抓不到**：S-48 只查「claim 的计数 == artifact 计数」，
     S-49 同理，`verify_dataset` 只看目录不读 tasks.jsonl ⇒
     **L2 内容漂移目前处于零闸状态**（R58：没有工具读的东西等于没校验）。
  4. 它同时也证明 **R-A2 缺一环**：我这次是"跑了全量生成才发现"，
     如果没做逐条比对（本可以只 `wc -l` 看一眼 183 行就过），这条会直接进 v7。
- **3 个选项**：
  - **A（推荐）显式冻结映射表 + 稳定派生**：新建 `tasks/l2_omit_map.json`
    （`case_id → omitted_field`）。生成时**先查表，命中即用**；未命中（新 case）才按
    **族内稳定序号**轮换，并把结果**追加写表**。首次建表时用 git HEAD 的 `tasks.jsonl`
    读出旧值 ⇒ **老 55 条逐字节恢复原状**，新 9 条为新增。此后任何人扩容都不会改动已有条目。
    代价：一个 json + 约 20 行代码。收益：把「已发布卷子」变成**显式冻结件**，
    正好补上 R-A2 现在缺的那一环。
  - **B 改成 `stable_hash(case_id) % len(pool)`**：确定性、与位置无关、扩容不动老条目。
    **但旧值无法恢复**（hash ≠ 旧位置）⇒ v6c 的 L2 子集永久失去可复现性，
    只能接受「v6c 的 L2 引用存档成绩、不再重跑」。比 A 少写一个 json，代价是丢掉一段可复现性。
  - **C 接受漂移 + 登记降级**：`CLAIMS`/`RUBRIC` 显式登记「L2 子集跨版本不可比」，
    headline 只用 L3/exam，L2 只报字段级覆盖、不参与任何纵向对比。
    代价：**「澄清能力」这一维度的跨版本证据全废**，而 L2 正是 v6c 里唯一测 clarify 的层。
- **建议**：**A**。它是唯一同时做到「恢复旧值」「永久防漂」「不牺牲 L2 维度」的方案。
- **无论选哪个都要加闸**（这条比选项本身更重要）：新增 **S-52**
  「重生成 `tasks.jsonl` 后，老 `task_id` 的 L2/L3 条目必须与冻结基线逐字节一致，
  否则红」。理由同 S-51：**消掉一个漂移面之后，必须防它长回来** ——
  L2 这次是「恰好在数据集扩容时」暴露的，下一次可能是「某人调了 manifest 排序」。
- **本轮已做的止损**：`git checkout -- tasks/tasks.jsonl` ⇒ 回到
  `9c1faa3a731f29369facf2eafce49c6c168fb7f12a28a55d85af971b58b063e5`（165 行），
  **v6c 冻结件完好**。v7 paper 暂停在此，等拍板。
- **✅ 已拍板（老王，2026-10-28）：A + 加 S-52。** 已落地：`tasks/l2_omit_map.json`
  （64 条，`lockfile` 语义；初始 55 条由 git HEAD 反推）+ `make_tasks.py` 改为查表
  （命中即用；未命中按**族内稳定序号**轮换并追加；已有条目改写即抛错）+ 幂等实测通过。
  **老 55 条 L1/L2/L3 字节级差异全部 = 0。**

### N-17（高，v7 candidates 之前）L2 澄清题有 **19/64 条** `name` 自己写出答案

- **怎么发现的**：N-16 修完后，逐条核对新登记的 9 条省略字段，发现
  `open_hole_panel_400x200_d30` 省略的正是 `hole_d`，而 `spec.name` 就写着 `d30`。
- **实质**：L2 靠「删一个字段、要求模型澄清」出题，但 `spec.name = case_id`，
  而 case_id 是人给的**描述性名字**，经常把设计变量写在自己身上。
  ```
  省略 hole_d(=30)    而 name = "open_hole_panel_400x200_d30"        ⇒ 答案在题面
  省略 n_frames(=3)   而 name = "fuselage_barrel_..._str8_frm3"      ⇒ 答案在题面
  省略 sweep_deg(=40) 而 name = "naca4412_wingbox_sweep40"           ⇒ 答案在题面
  ```
  模型读 `name` 就知道，不必澄清；此时判它「clarify 失败」是**判据的错，不是模型的错**
  —— 与 M7「诊断假设与被测对象必须同口径」是同一类。
- **量化**（`check_l2_leak.py`，可复跑，判据印在 docstring 里）：
  ```
  $ python check_l2_leak.py --out reports/l2_name_leak_2026-10-28.json --md ...md
  L2 总数 64；name 泄漏被省略值 19 条；干净 45 条（informative 70.3%）
  按族: {open_hole_panel: 10, fuselage_barrel: 5, wingbox: 3, stiffened_panel: 1}
  ```
  **老 14 / 新 5**（本轮新增 9 条里占了 5 条）⇒ **是既存缺陷，不是本轮引入**，
  但本轮把它量化了出来。
- **判据为什么这么做**：不能用裸数字碰撞。反例：
  `naca4412_wingbox_str4` 省略 `rib_thickness`(4.0)，`str4` 揭示的是 `n_stringers`(=4)，
  与 rib_thickness 只是**数值撞车** ⇒ 判不泄漏（W4a 已定的口径）。
  所以必须按**语义前缀**（`d<N>`→hole_d、`frm<N>`→n_frames…）匹配。
  ★ 第一版用 `\bd(\d+)` 写错边界（`_d30` 里 `_` 是 word 字符，`\b` 不成立）
  ⇒ 只抓到 5 条、漏了 14 条。**判据自己漏了比没判据更危险**（它给了一个好看的假数）。
- **为什么必须处理**：L2 这一层一旦开跑，那 19 条的 clarify 分数就是**假的**；
  而且它会被读成「模型不会追问」，其实是**题面把答案给了**。
  ★ **更正（2026-10-28 复查，我自己上一版写过头的）**：原文写「C-032 报了 clarify
  通过率，其中 19 条的下限被 name 抬高了上限」——**这句错**。实测：
  `score_baseline.py` 只读 `input_level == 'L3'`，C-032 的 `fpr.n_clarify_tasks = 4`
  是 **L3 的 4 条**，与这 64 条 L2 **毫无关系**；且 L3 的 prompt 只发 `input.nl`
  （`gen_candidates_v2.js:138`，**task_id 不进 prompt**），5 条 L3 澄清题的题面
  逐条核过（「若干个普通框」「若干翼肋」「若干根长桁」「孔周加密」，均未给数）。
  ⇒ **N-17 不污染任何已发布数字**，它是 L2 轨道的**潜伏缺陷**（全仓无
  `clarification.json`，L2 从未跑过模型）。**仍然必须在 L2 开跑前定口径**，
  但优先级从「已污染」降为「待上膛」。这条更正已落 CLAIMS C-038。
- **3 个选项**：
  - **A 抹掉 name 里的数值语义**（如 L2 的 name 统一改成 `case_<序号>`）：
    最干净，但**会改写老 55 条的 L2 题面** —— 刚用 N-16 冻结住的东西又要动，
    与「保住 C-032 同卷可比」直接冲突。
  - **B 从 `expected_clarifications` 移除这 19 条**：等于**改卷**（期望答案变了），
    同样破坏可比性，而且 L2 分母从 64 掉到 45。
  - **C'（推荐）不动题、只改评分口径**：`tasks.jsonl` **零改动**；
    评分时用 `check_l2_leak.py` 的 `scan()` **现算** informative 子集，
    clarify 分数**双报**——`clarify_all(n=64)` 与 `clarify_informative(n=45)`
    （与 N-15 的双分母同构，R54 只禁跨分母相减、不禁并列）。
    代价：评分脚本要接一个函数；收益：**零数据改动、保住同卷可比、且口径可被闸复算**。
  - D 只登记不复算：`CLAIMS` 写「19/64 条 L2 的 name 含答案」但分数照旧。
    代价：对外数字里仍含已知无效子集，等于知道错了不改。
- **建议**：**C'**。核心理由：**判据的错不该算到模型头上，但也不该靠改题来遮** ——
  改题会连历史一起废掉，改口径只影响这一维的分子分母，且能被闸独立复算。
- **✅ 老王拍板（2026-10-28）：C'** —— 不动题、只改口径、双口径并列。
  **已落实**：
  - `report_l2_clarify.py`（新）→ `reports/l2_clarify_dual.json` + `.md`：
    `clarify_all n=64` ／ `clarify_informative n=45` ／ `invalid n=19`，`delta_allowed=false`，
    `status=not_run`（L2 未跑，`passed` 如实为空，不是漏算）。
    闭合断言写在函数里：`all − inf == invalid`、`invalid ∩ informative = ∅`。
  - **S-53**（新闸，`check_claims.py`）：两块必须在 + 闭合 + **掩码与现算一致**
    （防 artifact 过期 ⇒ 数字看着对其实换了一批题）+ `delta_allowed is False`（R54）
    + `status=scored` 时两侧都必须有整数 `passed`（防只报有利一侧）。
  - **NC-56 四向**：缺一块 / 掩码过期 / 允许相减 / 只报一侧分 —— 都必须红，
    且**四向各自成为唯一失败项**（否则「缺一块」会一次吃掉后三条，使它们长期假绿）。
  - **R66**（新红线）：判据在某子集上无效时，必须**隔离 + 双报**；不得改题掩盖、
    不得继续算进单一对外数字；两个分母不同 ⇒ 禁止相减/排名（R54 一并适用）。
  - **边界写清楚**：S-53 现在只能守 artifact 的两个分母在场；「成绩单必须采用它」
    要到 L2 首次跑分那一轮，靠 `status` 从 `not_run` 升为 `scored` 自动加严——
    **不假装现在就守住了还没发生的事**。
- **配套闸（建议同时加 S-53）**：评分脚本必须调用 `check_l2_leak.scan()`
  产出 informative 掩码；成绩单若只报单一口径（无 informative 拆分）即红。
  否则「双报」会退化成一句写在文档里的承诺（R58：没工具读的承诺等于没有）。
- ~~**待老王拍板。**~~ 已拍板 C'（见上）。不影响 v7 paper 的 NL 生成（那是 L3，不走这段逻辑）。

### N-19（高，已按既有口径处置）v1.1 元数据被当成判分字段 ⇒ 9 条题**不可解**

- **怎么发现的**：v7 卷跑 `r32_audit --scope all` 得 **34 处 VIOLATION**，其中 **30 处**
  是 `extra.split_tag` / `extra.v11_template` / `extra.v11_bracket` / `extra.v11_interior_holdout`
  报「题面无依据」。
- **实质**：`evaluate.py` 的判分循环对 `gold['extra']` **逐键判等**，豁免表只有
  `EXEC_CONFIG_KEYS['extra'] = {sweep_index, shear_axis, moment_axis}`（W4d 定的
  「gold 内部编码键，NL 任务书永远不会提及」）。v1.1 的 4 个键是**数据集构建记账信息**
  （哪一版内插、夹逼哪两个锚点、划分标签），性质与 `sweep_index` **完全同类**，
  但不在豁免表里 ⇒ **模型必须凭空产出 `split_tag='v11_interior_holdout'` 才算 PASS**。
  题面根本不可能写这些 ⇒ **9 条必然全 FAIL**，而报告会把它读成「模型不行」。
  **这就是 M7 那条：判据的假设在冒充模型的错。**
- **范围实测**（不是推断）：
  ```
  split_tag 9 / v11_template 9 / v11_bracket 9 / v11_interior_holdout 8
  —— 全部只出现在新增的 9 条里；老 55 条一个都没有
  ```
  ⇒ 补豁免**不改变任何历史数字**（C-030/C-032 的 55 条口径逐位不变）。
- **处置（✅ 已做）**：把 4 个键并入 `EXEC_CONFIG_KEYS['extra']`（`evaluate.py`）。
  理由：这是把 v1.1 元数据归入**既有类别**，不是新开口径 —— 与 W4d 拍板
  「执行配置键 REPORTED NOT GATED」同一条。`r32_audit.py` 复用同一常量，自动同步。
- **不动的部分**：`spec.extra` 本身**一个字节都不改**（改 spec 会动 `spec_sha256`
  ⇒ `truth.json` 全档失效须重导，这是 D 系铁律）。
- **验收**：重跑 `r32_audit --scope all`，违规应从 34 → **4**，且剩下 4 处必须精确等于
  白名单 `{stiffened_panel_800x600, _str3} × {params.length, params.width}`（C-030 已登记的
  已知下界，冻结行原样保留）。



---


### N-20（高，**已定论** + 已处置）求解锁残留 ⇒ 6 条**假 solver 失败**，且 `classify_failure` 把它归成「算力不足」

- **现象**：v7 × glm 首跑全链 MSR 报 `44/59 (74.6%)`、失败分层 `{'model': 9, 'solver': 6}`。
  而 **C-032 的 solver 是 0 条**（`baseline_scorecard_L3_v6c_p2.json` 实读 `n_solver_excluded=0`）
  ⇒ 「v7 的题突然更吃算力」这个解释站不住。
- **★ 我在这条上写错过一次，记下来防复发**：中途我曾「自我更正」说「C-032 其实有 4 条 solver」，
  理由是实读 `baseline_scorecard_L3_v6c.json` 得到 `n_solver_excluded=4`。
  **读错文件了** —— 那个是 **C-029**（prompt v1 代），不是 C-032。
  C-032 的成绩单是 `baseline_scorecard_L3_v6c_p2.json`（prompt v2 代，`n_solver_excluded=0`），
  `reports/INDEX.md` 第 12 行写得很清楚。**教训：比对基线要去 INDEX 认人，不能凭文件名里的 `v6c` 前缀认。**
  原判断（C-032 solver 0）成立，改回来。
- **真正站得住的证据是成因**：这 6 条的 detail 明确写着锁冲突
  `RuntimeError: 检测到另一个求解正在进行…R61 禁止并行`（见 N-22），与求解规模无关。
  而 C-029 那 4 条 solver 的 `failure_detail` 已被截断成 stdout 尾巴（只剩 "deck written …"），
  **成因永远无法复核** —— 这正是 N-21 的代价，不是可以含糊过去的地方。
- **根因（两层，都不在模型侧）**：
  1. `.solve.lock` **残留**（持有者 `pid 1044` 已不存在、机器上无任何 ccx 进程），
     从该时刻起每条求解都抛
     `RuntimeError: 检测到另一个求解正在进行：锁 …R61 禁止并行 ccx/abaqus`；
  2. `msr_l3.classify_failure()` 只看 `pipeline.actual.startswith('rc=')` ⇒ 把这类异常
     **一并归成 `solver`**。而 R16 明写「env 不计模型失败」⇒ 这是**把环境事故记成算力不足**，
     再按「剔除 solver」把它从分母拿掉，等于替模型掩盖了 6 条真失败。
- **证据（独立复算，不靠推理）**：
  - 单条探针复跑 `L3_open_hole_panel_500x250_d45`（清锁后）：
    `overall_pass = True`，四关全 True —— 它在首跑里被记成 solver 失败。
  - 该条 ccx 自己的 `.sta` 显示 `1 step 1 inc` 正常收敛、`.dat` 无错误。
  - 复跑 `L3_stiffened_panel_800x600`：`spec_fidelity pass=False`（`params.length` 800↔600 反）
    ⇒ 它本来就是 **model** 失败，只是在首跑里被锁冲突挡在前面、误记成 solver。
- **处置（已做）**：
  - `classify_failure()` 增加锁冲突分支 ⇒ `env`（判在 `rc=` 之前）；
  - 清锁、重跑 glm 全链；首跑的 44/59 **作废**，不进任何 claim。
- **★ 根因已定论（第三次复现把它钉死了）**：`try/finally` 在**进程被硬杀时根本不执行** ——
  Windows 上 `TerminateProcess` 不会跑 `finally`，Python 的 `KeyboardInterrupt` 路径才会。
  本轮第三次撞到时拿到了确证：锁里写着 `pid 16568`，而 `Get-CimInstance` 查 python/ccx
  **一个进程都没有**，锁的 mtime 正是我强杀那次 msr 的时刻。
  ⇒ 三次事故同一个成因：**长任务被我杀掉 ⇒ finally 没跑 ⇒ 锁留下 ⇒ 下一条全被判 solver 失败**。
  这不是「偶发」，是「我杀进程就必然复现」。已如实登记，不写成环境玄学。
- **★ 为什么不加「pid 探活自动接管」**（看起来更聪明的做法）：代价不对称。
  - 假接管（把**正在跑**的求解当成残留）⇒ 两个 ccx 并行 ⇒ **静默空转、返回码仍 0**（R61 原话），
    结果是空结果被当成功，且**没有任何闸能事后发现**；
  - 假不接管（把残留当成在跑）⇒ 只是浪费 1 小时或手工删一次锁，**立刻报错、看得见**。
  ⇒ 保持现有「按 age 超时（1h）接管 + 其余一律拒绝」，宁可多删一次锁，不赌 pid 不重用。
- **闸的盲区（已补）**：S-47 只查「锁机制在场 + 当前无残留锁」，查不出「这次跑出来的失败原因里
  有没有锁冲突」。已加 **S-55 = `msr_l3.py` 出口硬断言**：凡 `failure_class == 'solver'` 的条目，
  其 `failure_gates` + `failure_detail` 不得含 `.solve.lock` / `检测到另一个求解正在进行`，
  命中即 `return 5` 拒出单（不是警告 —— 出了单就会被引成数字）。
  注：**这条闸能立起来的前提是 N-21 的修复**。修之前 detail 是空字符串，S-55 查空气必绿。

### N-21（**高，本轮新发现**）失败的「原因」从来没落过盘 —— 所有非 pipeline 环节的失败在 artifact 里都是**空字符串**

- **现象**：`failure_detail` 在 v6c/v7 所有成绩单里，凡 `failure_class == 'model'` 的条目**全是 `''`**。
  实测 `eval_runs/L3_stiffened_panel_800x600_str3/evaluation.json`：`overall_pass=False`，
  唯一失败闸是 `spec_fidelity`（14 个字段里 12 个对、`params.length` 期望 800 实得 600、
  `params.width` 期望 600 实得 800），但成绩单上只看得见 `class=model`，**原因一个字没有**。
- **根因**（两处叠加，单独任一都不致命）：
  1. `gates = {k: bool(v.get('pass')) for k, v in r['gates'].items()}` —— 把每个闸**压成布尔**，
     `field/expected/actual/detail/failed` 结构化诊断全部丢弃；
  2. `failure_detail` 只取 `gates['pipeline'].detail or .actual`。
     而 pipeline **只有在 rc≠0 时才有 detail**；`spec_fidelity` / `mesh_quality` / `semantics` /
     `fidelity_disp` 失败时 pipeline 是 **pass**、detail 是 `None`
     ⇒ `or` 链一路落到 `''`。
- **为什么这比「少一个字段」严重得多**：
  - 任何闸都**没有对象可查**。S-55（锁冲突不得记成 solver）在修之前必然绿 —— 它查的是空串（R58：无工具读的=无闸）；
  - N-20 就是这么被漏掉的：我事后只能**重跑单条探针**才还原出「本来该是 model 失败」；
  - **历史数字的失败分层不可复核**：C-032 的 9 条 model 失败、C-033 的同类，原因从未落盘，
    只能说「当时归成 model」，无法再验证那个归类对不对。
- **处置（已做，本轮）**：
  - 新增 `_gate_diag()`：收集**每个失败闸**的 `field/expected/actual/detail/failed[...]` 等结构化字段，
    落成 `per_task[].failure_gates`；`detail` 只留尾部 1200 字（报错总在尾）。
  - 新增 `_diag_text()`：把所有失败闸的诊断摊成文本，供 `classify_failure()` 归类 ——
    此前它实际只对「pipeline 挂掉」这一种情况有输入，其余全靠 `return 'model'` 兜底。
  - `failure_detail` 改从 `_diag_text()` 取，**兜底写 `NO_DIAGNOSTIC_CAPTURED` 而不是空串**
    （空串会被下游 `or` / `if` 静默吃掉）；判 FAIL 却无任何失败闸诊断时**当场打印告警**。
  - `contract` 分支**故意不收窄也不放宽**：仍只认 pipeline 的 `contract_ok/contract_buildable`。
    扩到全闸会把历史归 `model` 的条目翻成 `contract`，改变 `failure_breakdown` 的跨版本口径 ——
    那是「改判分」，与本轮「只加诊断」冲突（R-A1 单变量）。
- **代价与边界（如实写）**：
  - 这是**报告层**改动，不动任何 `pass/fail` 判定 ⇒ 不影响 TSR/SFR/MSR 任一数字；
    但 `failure_breakdown` 的**可比性**在改动点前后需要说明：v6c 旧成绩单没有 `failure_gates`，
    v7 有。**跨版本比 failure_breakdown 时不得假装同口径。**
  - 未回填历史：v6c/v7 首轮 artifact 的 `failure_detail` 仍是 `''`，**不回填、不修补**，
    只在 v7 正式跑（run2）起才有完整原因。
- **闸的补法（下一步）**：S-55 已随本条目落地（依赖 detail 非空才有效）；
  另建议 S-56：`msr_section.per_task` 里凡 `msr_pass == False` 且 `denominator == True` 的条目，
  `failure_detail` 不得为空且不得为 `NO_DIAGNOSTIC_CAPTURED` —— 即「判失败必须说得出为什么」。

### N-22（**高，环境级，会必然复发**）沙箱的批量删除保护会拦下 `unlink()` ⇒ 求解锁释放失败 ⇒ 一次 msr 跑到 ~53 条必炸

- **现象（两轮一模一样，不是巧合）**：v7 × glm 两条独立的全链 MSR（run1 与 run2）都在**尾部 6 条**失败：
  `open_hole_panel_500x250_d45`、`600x300_d30`、`600x300_d60`、`stiffened_panel_600x600`、
  `800x600`、`800x600_str3`。run1 把它们记成 `solver`，run2 记成 `env` —— 归类变了，**失败位置一条不差**。
- **真因（这次有 detail 才看得见，靠 N-21 的修复）**：第一条的 `failure_gates.pipeline.detail` 里写着
  ```
  [safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]
  {"count":50,"threshold":50,"scope":"turn","targets":["…\.solve.lock"],"targetCount":1}
  ```
  即：**环境注入的批量删除保护在「单次调用累计第 50 次删除」处拒绝这次 `unlink()`**。
  而这次删除恰好是 `_release_solve_lock()` 释放求解锁 —— 删除被拒 ⇒ 该步抛异常 ⇒
  `run_pipeline` rc=1 **且锁留在原地**。
  紧接着的 5 条，`RuntimeError: 检测到另一个求解正在进行…持有者 {"pid": 29356, …}`，
  锁年龄 31s → 38s → 551s → 655s → 665s：**同一个已死的持有者**，一条条把后面全挡死。
- **为什么正好在第 50 次**：每条任务释放一次锁 = 一次 `unlink`。59 条里第 50 次落在第 53 条附近
  ⇒ **任何 ≥50 条的单次 msr 在 agent 内都必然在这里断**，与模型、与题面完全无关。
  这也解释了 run1 我误判成「求解锁残留」：现象相同，成因不同（那次确实是残留，这次是**被拦着不让删**）。
- **处置（已做）**：
  - `msr_l3.py` 增 `--force <id列表>`：与 `--reuse 本成绩单` 合用，只重跑指定几条，
    其余逐字节复用；分母与闭合仍按**全卷**重算（rows 覆盖全部任务，不会因只跑 6 条而变小）。
  - 长跑分批原则：**单次调用内任务数 < 50**（保守取 ≤40）。
  - 若要一次跑完整卷，只能在 WorkBuddy 外 `cmd` 里跑 bat —— 与「Abaqus 在 agent 内必失败」
    同一条环境铁律（沙箱注入层会干预进程行为），不是代码问题。
- **教训（比修法重要）**：我上一轮把它写成「求解锁残留（我自己造成的）」，**只对了表层**。
  真因是环境拦删除；而当时 detail 没落盘（N-21），所以只能看见「锁在、持有者已死」，
  于是一次次手工删锁、删完下次照炸。**「现象能用手工绕过」不等于「根因已找到」。**
- **闸的盲区**：目前没有任何闸能发现「环境拒绝了 unlink」。可行方向：跑完后若同时出现
  `failure_class=env` 与锁冲突标记，就**直接 FATAL 并提示用 `--force` 补齐**，
  而不是把 `44/59` 印成一份看起来正常的成绩（本轮就是差点这么用了）。

### N-23（高，逻辑不一致）`env` 失败仍留在 MSR 分母里，而同一份输出印着「不进分母」

- **现象**：v7 glm run2 的日志里两句话互相矛盾：
  ```
  环境失败 6 条——不进 MSR 分母（R16），请检查解释器后重跑。
  [msr_l3] 分母闭合 全卷: 64 = counted 59 + clarify 5 + … + env 0 + unknown 0
  ```
  「6 条不进分母」和「env 0」不可能同时成立。
- **根因**：`msr_l3.py` 有**两条**记录失败的行路径，只有一条遵守了 R16：
  - `evaluate_one` **抛异常**那条：`'denominator': cat != 'env'` ✅；
  - `pipeline` **rc≠0** 那条：先 `rows.append(denominator=True)`，再看 gates 判失败、
    才 `classify_failure()` 得出 `env` ❌ —— 此时分母已经定死了。
  于是 env 条目既被计进 `counted`，又被 `_excl_class` 认成 `env`（后者只在
  `not denominator` 的池子里统计），两边都"没看见"它。
- **为什么必须修**：R16 是红线（环境事故不计模型失败）。留在分母里等于**把环境事故算成模型分数低**，
  这正是 N-20 那条要防的错，只是这次方向相反（不是剔出去掩盖失败，而是算进来压低分数）。
- **处置（已做）**：`if row['failure_class'] == 'env': row['denominator'] = False` +
  `excluded_reason` 落盘。此后 `counted` 与 `env` 两侧数字才互斥且闭合。
- **口径影响（如实写）**：修后若仍有 env 条目，MSR 分母会从 59 变 53、点估计随之变
  ⇒ **与 C-032 的 51 分母不可直接相减**（R53/R54）。本轮的正确做法是**把它跑成功**
  （`--force` 定点重跑），而不是把它排除掉让数字好看；排除只是兜底。

### N-24（中，已定性 + 判据已跟上，**数据集标签未动**）9 条 v11 的 `split_v2` 是 `extrapolation_test`，与 `exam_stratum=interpolation_v11` 不同名

- **现象**：跑负控时 NC-19（「exam 集与 split 语义一致」）由绿转红，报 9 条「非 exam 却是留出 split」，
  其中打印出来的 3 条是 `L3_fuselage_barrel_d2000_l1800_str8_frm3`、
  `L3_naca4412_wingbox_n_ribs6_chord1000`、`L3_naca4412_wingbox_size_chord900`。
- **实测（全卷 9 条 v11 逐条看）**：`exam_stratum` 全是 `interpolation_v11`，
  `split_v2` **全是 `extrapolation_test`**（9/9）。交叉表：
  `('interpolation_v11','extrapolation_test')->9`，而 legacy 三栏分别是
  `boundary↔boundary_holdout`、`extrapolation↔extrapolation_test`、`interpolation↔interpolation_test` 一一对应。
  ⇒ v11 这一桶**借用了 extrapolation 的 split 标签**，与自己的 stratum 不同名。
- **为什么 NC-19 会红（而且是假红）**：它的不变式②写的是「**非 exam** 行 split 不得是留出」，
  用的是 legacy `is_exam`。v7 按 C-037 把 9 条 v11 定成 `exam_full` 但**不是** legacy exam
  ⇒ 9 条合法行被一次全判红。**判据没跟上双分母口径**，不是数据错了。
- **处置（已做）**：不变式②改用 `is_exam_full`（旧成绩单无该键时回落 `is_exam`）；
  另加 v11 专用不变式：**进了 exam_full 的 v11 行必须是留出**（否则等于 dev 题混进考卷、稀释 headline）；
  并把「v11 的 split_v2 与 stratum 不同名」的条数**计数进 NC-19 的 actual**
  （`v11 9/9 为留出（split_v2 与 stratum 不同名，属已知口径）`），条数一变就会被看见 ——
  不写死常数（R63），也不静默放过。
- **★ 没有做的事（需要老王拍板，不擅自改）**：**没有**去改数据集里这 9 条的 `split_v2`。
  因为 `split_v2` 是**考卷定义**的一部分，改了它等于改卷面（R65/S-52 冻结纪律）；
  而且从哪边改都说得通（是 v11 该改叫 `interpolation_test`，还是它本来就是从 extrapolation 池里挑的）。
  这条先如实挂着，等拍板。
- **判据可证伪的证据（不是「我改完就绿了」）**：这轮 NC-19 **确实是先红了**，
  红在真实的 9 条身上；改完后再绿。红的原因被逐条核对过（上面实测），不是靠调判据把红色抹掉。

### N-25（**高**）同一条柱壳在**同一套物理参数**下两次运行结果不同 ⇒ legacy exam MSR 的 ±1 不可解读

- **现象**：`L3_fuselage_barrel_d2000_l2000_str12_frm4`（2.5M 自由度的最大柱壳）在 ds 上翻了一次：
  C-033（`baseline_scorecard_L3_v6c_ds_p2.json`）记**通过** → v7 `solver` 失败（rc=1、236s，"solver failed"、
  `N: 2528201 / nnz: 140660073`）。这是 **legacy exam MSR 从 20/21 变 19/21 的唯一来源**（其余 20 条零变化）。
  **glm 侧同一条没有翻转**：C-032 与 v7 都是通过（C-032 exam MSR 20/22 == v7 20/22，TSR/MSR 逐条零变化）。
  （注意：更早的 C-029 时代这条是 solver 失败，但那是 prompt v1 代、候选不同，**不能拿来当复现性证据**。）
- **关键证据（排除了「候选不同」这个解释）**：把两次候选逐叶子比 ——
  **物理参数完全一致**，差异只有 4 个叶子且全是命名/元数据：
  `spec.name`、`spec.description`、`raw_len`、`validation_history[0].errors[k]`（已修正的校验历史）。
  ⇒ 网格、载荷、材料、几何一模一样，**同一条`.inp` 级别的输入，两次跑出不同结论**。
- **为什么这条必须记**：它是「legacy exam MSR 19/22 → 20/22」这类 ±1 变化的**唯一来源**。
  如果不记，下一轮很容易把「exam MSR +1」读成模型变强 —— 那是拿一次求解抖动当结论。
  **TSR/SFR（spec 层）是确定性的**：两模型 legacy exam 逐条零变化，跨版本可比；
  **MSR（solve 层）在这一条上不是**。
- **可能成因（未验证，不写成结论）**：2.5M 自由度、`N: 2528201 / nnz: 140660073` 的稀疏系统已接近
  该机内存/迭代上限；ccx 的 `solver failed` 通常是迭代不收敛或内存不足。**没有做**进一步定位
  （要单独重跑几次同一 `.inp` 才谈得上结论），因此只如实登记「结果不可复现」，不猜原因。
- **处置**：
  - C-040 正文把它点名为「±1 不可解读」的原因，不给任何「模型进步」的表述；
  - 跨版本比 MSR 时**先看这条**；报告里凡出现 exam MSR 的差值，必须附「含 1 条求解不可复现题」；
  - 未改题、未剔题（剔掉它就是挑数据，R54 的同类问题）。

### N-26（**高，已处置**）`exam_full` 的分母闭合断言是**代数恒真式** ⇒ `[FATAL] 分母不闭合` 对这条路径**从未生效**

- **发现途径**：第十四轮专家意见把它列为 P1-4，但描述是「**审计展示与字段命名**问题」
  （「`n_tasks_total=29` 会被误读成 exam_full 只有 29 条」）。我去核成因，发现**不是展示问题**。
- **现象（v7 改前，实读）**：

  ```text
  glm  exam_full_denominator_audit:  n_tasks_total 30 = counted 30, clarify 0, unresolved 0
  ds   exam_full_denominator_audit:  n_tasks_total 29 = counted 29, clarify 0, unresolved 0
  ```

  `n_tasks_total` **恒等于** `n_counted`，`clarify`/`unresolved` 恒为 0。真值应为
  glm `34 = 30 + 4 + 0`、ds `34 = 29 + 4 + 1`。
- **根因（`msr_l3.py:481`）**：`_FAUDIT = _denom_audit(exam_full_ids)`，而
  `exam_full_ids = exam_ids + v11_ids`，**两者都取自 `den_rows`（已剔除 clarify/unresolved）**。
  `_denom_audit` 的 pool 因此只含 `denominator=True` 的行 ⇒
  `closure_ok` 的判据 `n_tasks_total == n_counted + clarify + unres + …` 左右两边恒等 ⇒ **恒真**。
  同一个函数、另一处调用 `_EAUDIT` 传的是 `[r['task_id'] for r in rows …]`（**全量**）⇒ legacy 那份是真闭合。
  **一处真、一处假，写在同一段代码里。**
- **后果不是「少个字段」**：`_FAUDIT['closure_ok']` 被写进 `:483` 的 `if not (…)` 判据，
  也就是那句 `[FATAL] 分母不闭合（R52）——拒绝出 MSR`。**exam_full 这一路的闭合从未被真正检查过**，
  而它输出的「闭合」文本一直在对外宣告一个同义反复。
- **为什么没有任何闸发现**：NC-58 的「四桶不闭合须红」测的是 **`exam_full_closure.ok`**
  （`:516`，那条是真算术：`len(exam_ids)+len(v11_ids)+len(dev_ids) == len(den_rows)`）——
  **两条路径互不覆盖**。这是「新闸测了 A==B，但 A 和 B 都不是目标」的变体。
- **处置（T-A12b）**：
  1. 传参源改 `den_rows` → 全量 `rows`（新增 `exam_full_all_ids`，**counted 集 `exam_full_ids` 不动，MSR 分母零变化**）；
  2. `_FAUDIT` 加 `units` 字段写明是全量口径；`exam_full_closure` 加 `units` 写明是 counted 口径
     （两个 `exam_full` 同名不同义：顶层 34 / msr 内 30）；
  3. **S-54(e) 用 `per_task` 独立复算**：`n_tasks_total` 必须等于 `per_task` 里 `exam_stratum is not None`
     的条数 —— **不看 audit 自己怎么说**，这是唯一的真判据；
  4. 加「总账 == counted 且 per_task 更多」的死循环断言（N-26 复发即红）；**NC-61 四向**守。
- **★ 教训（比这条 bug 更重要）**：专家把它归成「展示问题」、我第一遍也只写成「字段命名有歧义」。
  **恒真式在外观上与正常闭合一模一样**（都印 `ok=True`、都印一行 `A = B + C + …`），
  只有把式子代进去看才发现左右恒等。⇒ **判闭合时必须问「这个等式有没有可能不成立」**，
  而不是「它是不是 True」。R68 那条「建闸前先看字段在真实 artifact 里是否非空」是同一个方向。

---

### N-27（中，**改变 C-038 的读法**）L2 双口径 64/45 的差**不是泄漏**，是族/字段构成 + 模型盲区

**现象（T-A13b 首次跑分实测，`reports/l2_scores_v7_glm.json`）**

| 口径 | 结果 |
|---|---|
| `clarify_all` | **49/64 = 76.6%** |
| `clarify_informative` | **30/45 = 66.7%** |
| `invalid`（name 泄漏 19 条） | **19/19 = 100.0%** |

按 R66 的设计读法，「19 条全对、干净 45 条只有 66.7%」会被读成「泄漏让那 19 条变简单」。
**按族拆开就不是这个意思**：

| 族 | 全卷 | 泄漏 19 | 干净 45 |
|---|---|---|---|
| open_hole_panel | **13/13** | 10/10 | 3/3 |
| fuselage_barrel | **7/7** | 5/5 | 2/2 |
| stiffened_panel | **5/5** | 1/1 | 4/4 |
| wingbox | **24/39** | 3/3 | 21/36 |

⇒ **15 条失败全部在翼盒**；非翼盒三族**全对**，而泄漏 19 条里 16 条正属这三族。
两个分母的**族构成**不同（泄漏集 = 16 条易族 + 3 条翼盒；干净集 = 36 条翼盒）⇒
**64 与 45 的差主要是构成差，不是泄漏净效应**。

**失败集中在三个字段**（各 6 条）：`rib_thickness` **1/6**、`stringer_height` **1/6**、`sweep_deg` **1/6**
（13 条 `fabricated` = 静默填值，2 条 `clarify_wrong` = 问了**别的**字段）。
唯一能同时看到泄漏/干净两格的字段是 `sweep_deg`：**泄漏 1/1 vs 干净 0/5** —— 方向与「泄漏有帮助」一致，
但 **n=1，只能记为线索，不是结论**。

**为什么这仍然必须记**：C-038 的原文把 `clarify_informative` 定义成「真的在考会不会追问的可判子集」。
实测它同时是**「翼盒占了 36/45」**的子集 —— 把它当「L2 的真信号」单独引用，等于把一个族的表现当成全卷表现。

**三个处置（待老王定，本轮不改口径）**
- **(a) 只如实标注，不动口径（推荐）**：两个分母照 R66 双报，并在 CLAIMS/README 写明「差的主因是族构成，
  不是泄漏」；代价 = 0，信息最全。
- **(b) 按族分层再双报**（翼盒 / 非翼盒各一套分母）：能真正隔离族效应；代价 = 分母从 2 套变 4 套，
  S-53 要改口径 + 新增负控向，且每格 n 变小（翼盒 39 / 非翼盒 25）。
- **(c) 遮 name 重跑一遍作对照**：`--mask-name` 已经实现（T-A13a），一次 64 条重跑即可**直接测泄漏净效应**；
  代价 = 多一版候选 + 一个新的呈现变量（prompt 不变、只是呈现层）。

**建议**：**(a) 现在做**；(c) 留作「想量化泄漏」时的单独立项（它才是能回答「泄漏咬没咬」的实验；
冒烟 2 条显示 glm 在 `..._d30` 上照问不照填，但那只是方向性证据）。**(b) 不建议** —— 分母再拆一层会让
每格 n 掉到 20 上下，配 R54「不得相减」就只剩「不能说」，信息量反而下降。

> **✅ 已拍板（老王 2026-10-30）：取 (a)** —— 只如实标注、**不动口径**。已落地三处：
> ① `CLAIMS.md` C-041「必读边界一：64 与 45 的差不是泄漏」；
> ② `RUBRIC.md` R66 的「新增适用边界（N-27）」；③ `README.md` / `reports/INDEX.md` 的 L2 段落。
> **边界（R69）**：`clarify_informative` 仍必须照 R66 双报（不得只报一侧），
> 但**不得**被当作「L2 的真信号」单独引用；(c) 若要做得单独立项（会新增一个呈现变量）。
> **★ 该处置不随第二个模型改变**：T-A13c（ds）跑完后，若两模型的族构成同样偏翼盒，则 (a) 仍成立；
> 若 ds 的失败分布与 glm 明显不同（族排序反转），则须另立 N-28 而不是改本条。

### N-28（中，**判据的潜伏假通过通道**；**✅ 已关闭（T-A13d）**）

> **★ 定性更正（T-A13d 开工时发现，比原记录更准确）**：本条目在 T-A13c 里被记成「新发现」——**错了**。
> `_audit_clarify_meta.py`（W5c-6d，早于本轮）第 13 行已明确写：「**匹配方式有隐患**：`judge_clarify_field_level`
> 用子串 `in` 判错族键 ⇒ `n_stringers` 会在 `n_stringers_per_skin` 里**命中**」—— 指向的就是同一条通道。
> 两者是**同一函数的两端、互不重叠**：旧账记的是 `hit_wrong` 那侧的**假红**（数字偏低、会被察觉），
> T-A13c 补的是 `hit` 那侧的**假通过**（数字偏高、**不会被察觉**）。⇒ 本条应读作「**旧账未清 + 补上另一半**」，
> 不是「新发现」。**当时没有量化、也没有修**（`_audit_clarify_meta.py` 的结论原文是「记录缺陷、下轮定夺」）。

**现象（T-A13c 判公平性时发现）**：`score_baseline.judge_clarify_field_level` 的命中判定是**裸子串**

```python
al = aliases.get(f) or [f]          # L2 没有 clarify_aliases ⇒ al = [f]
hit = [a for a in al if a in text]  # ★ a in text —— 无边界
```

而 L2 的被省略字段里有三个**是别的键名的子串**：

| 被省略字段 | 被哪些键包含 | 该字段的题数 |
|---|---|---|
| `n_stringers` | `n_stringers_per_skin` | 6 |
| `thickness` | `skin_thickness` / `rib_thickness` / `stringer_thickness` | **7** |
| `width` | `stringer_flange_width` | 2 |

⇒ **模型问「肋厚多少」（`rib_thickness`）而题面省略的是笼统的 `thickness` 时，判据会判对。**
这不是「问错字段也过」的假想：`thickness` 有 7 条题，而 `rib_thickness`/`skin_thickness`/`stringer_thickness`
恰好都是模型最常主动追问的键（ds 的 8 条 `clarify_wrong` 里就有 4 条在问长桁/蒙皮厚度相关键）。

**实测影响：本轮 0 条触发。**
用 `(?<![A-Za-z0-9_])f(?![A-Za-z0-9_])` 逐条复算两模型全部 PASS 条目（glm 49 + ds 36）：
**每一条都含独立键名命中**（模型写的是 `structure.params.n_stringers`，前面是点，天然独立）
⇒ **C-041 的数字不假**。

**为什么本轮不修（而不是修不了）**：修它 = 改 `judge_clarify_field_level` = **改判分**。
判据在 T-A13a 已冻结并提交、T-A13b/c 已据此出分 ⇒ **跑完之后改判据就是 post-hoc**（R-A2）。
即使能给出「零差异」证据，形式上也必须走「跑前冻结 → 冻结后零差异 → 负控」的独立任务，
否则下一轮遇到「结果不好看」时，同样的口子可以用来改判据而不被发现。

**处置（下一轮独立单子，建议 T-A13d）**
1. 判据改成**独立命中**：`re.search(r'(?<![A-Za-z0-9_])' + re.escape(a) + r'(?![A-Za-z0-9_])', text)`；
   中文别名不受影响（`翼肋` 之类没有标识符边界问题），纯 ASCII 别名才受约束。
2. **零差异证据**（构造性，不是「看着差不多」）：
   - L2 两模型：预期 `49/64`、`36/64` 逐数不变（本轮已用同一正则复算过，0 条触发）；
   - L3 两份成绩单：25 个 alias 里**纯标识符且被别的键包含的 = 0 条**，预期 TSR/SFR/MSR 逐叶子不变，
     仍须用 `_regress_scorecard.py` 出 `RESULT: PASS`（R67 纪律：先声明允许项，再逐条比）。
3. **负控**（新向）：造一条「省略 `n_stringers`、模型只写 `n_stringers_per_skin`」的候选 ⇒ **必须红**；
   再造一条「省略 `n_stringers`、模型写 `n_stringers`」⇒ 必须绿（防判据过严）。
4. **边界（R69）**：改边界后仍须允许「`structure.params.n_stringers`」「`n_stringers（根数）`」这类写法 ——
   即边界只约束**标识符字符**，不约束 `_` 之外的分隔符；且**不得**顺手把中文别名一起收紧。

**★ 教训**：`a in text` 这种写法在「键名恰好是另一个键名的前缀/后缀」时是**静默的假通过**，
它不会像漏判那样留下「本该过却没过」的痕迹，只会让数字**偏高**。
与 N-26（恒真式）、N-17（name 泄漏）同族：**错的方向都是「看起来更好」**。

**✅ 处置结果（T-A13d，2026-10-30，老王拍板立项）**

1. `score_baseline.py` 新增 `_alias_hit(alias, text)`：**纯 ASCII 标识符按 token 边界**
   `(?<![A-Za-z0-9_])X(?![A-Za-z0-9_])`，**非 ASCII（中文短语）仍按子串** ——
   中文没有词边界，25 个 alias 里 21 个是中文，加边界等于**把判据改坏**（`翼肋` 会判不中「翼肋数量」）。
2. `judge_clarify_field_level` 的**两处**裸子串（`hit_wrong` 与 `hit`）都改走它；
   顺手清掉 `hit_wrong` 里那两个完全等价的分支（死代码，行为等价已论证）。
3. **构造性零差异**（三路判据，不是「看着差不多」）：
   - 旧逻辑**逐字副本**（oracle）/ 用真实 `_alias_hit` **组合**（composed）/ **真实调用点**（actual）；
   - 8 向合成探针：4 向必须分歧（P1/P4/P5 假通过 True→False、P6 假红 False→True）、
     4 向必须不变（点前缀 / 中文括号 / 两个中文别名）—— **探针必须真分歧，否则它没在测任何东西**；
   - 真实数据：**104 条 clarify 文本 × 三路 0 变化**；
   - 四份成绩单 **L2 661+660 叶子 / L3 2098+2137 叶子逐叶子零差异，无 allow 项** ⇒ **对外数字零变动**。
4. 新增 **R70**（红线）+ **S-58**（静态三层）+ **NC-64 六向**；负控 65→**66**，语义项 57→**58**。

**★ 本轮不碰的（R69 边界）**：`clarify_wrong_keys` / `clarify_aliases` **元数据不改** ——
那是「改判分输入」，且绑定 over-clarify 政策（本文件同族问题「问对了+多问一句键名正确但不必要的
算 PASS 还是 FAIL」**至今未预注册**）。本轮只修**字符串匹配这一层**，对政策**不表态**。

**★ 教训升级**：写契约时我说「改动方向只能是关掉假通过、让数字有下降的可能、没有上升的可能」——
**这是错的**，探针 P6 当场推翻（假红修复会让数字**上升**）。⇒ 任何「这次改动只会更严」的直觉都要用探针证伪，
**双向性**是这类通道的常态。

---

### N-29（**高，4 条 CFRP 题结构性不可解**）`schema_task.json` 把 `layup` 声明成 `number`，与 gold 真值（dict）冲突 ⇒ 无解闭环

**发现于** T-PSA（prompt 与 schema 对齐）执行途中，2026-11-01。**与 T-PSA 不是同一件事**，方向相反：T-PSA 是让 prompt 服从 schema，本条是 schema 自身声明错。

#### 现象

`task_b1kpi_report.md` §4 记「唯一未收敛：`L3_open_hole_panel_400x200_d20_cfrp45s_d40`（C-033），3 轮都卡在 `/structure/params/layup must be number`」。
本轮把它当单题异常去查，实测是**4 条题 × 2 模型共 8 条全部命中**，不是单题。

#### 三方对照（全部实读）

| 来源 | `layup` 的形态 | 取法 |
|---|---|---|
| `schema_task.json:394-396` | `{"type": "number"}` | 直接读 |
| gold `modeling/open_hole_panel_400x200_d20_cfrp45s_d40/spec.json` | **dict**：`plies[4]{angle,thickness}` + `material{E1,E2,E3,nu12,nu13,nu23,G12,G13,G23,name}` | 直接读 |
| `tasks.jsonl` 的 8 条 CFRP（L1/L2） | **dict**（8/8） | 直接读 |
| `gen_candidates_v2.js:34`（SYS prompt） | 教模型写 **dict** | 直接读 |
| `evaluate.py:100-101` `GRADED_FIELDS['open_hole_panel']` | **含 `layup`** ⇒ `_field_equal` 对 dict 走 `==`，**真判** | 直接读 |

⇒ **照 prompt 写 dict 被 schema 拒；照 schema 写 number 被评分器判 FAIL。两个出口都是错的。**

#### 实测：两条「逃法」，都过闸、都必 FAIL

| 模型 | 4 条候选的最终 `layup` | ajv 重放 | 评分后果 |
|---|---|---|---|
| glm v7 | **改成整数**（4 / 4 / 4 / 2）—— 铺层角度与单层厚全丢 | 全部 `ajv=true` | gold 是 dict ⇒ `_field_equal(int, dict)` False ⇒ **spec_fidelity FAIL** |
| ds v7 | **直接删掉 `layup` 键** | 3 条 `ajv=true`，1 条（`cfrp45s_d40`）`spec=null` 3 轮耗尽 | 单边缺 ⇒ `cv='<missing>'` ⇒ **FAIL** |

⇒ 闸把「写对」判红、把「写错」判绿，模型只能二选一，**4 条题拿 0 分是被 schema 逼出来的，不是能力问题**。

> 口径更正：B1KPI 报告说「唯一未收敛」只对 ds 成立。glm 那 4 条是**收敛到错误答案**（turns 2/2/2/3，全部过闸），不是「没收敛」。两种表现同一个根因。

#### 引入历史（`git log -L394,396`）

`28e66bb`（W4e/W4f 专家第四轮整改）**新增**了这一项：之前 `open_hole_panel.params` 的 properties 里**根本没有 `layup`**。
加它的目的应是「让 `layup` 出现在 properties 里、免得被 `additionalProperties:false` 拒」——**但类型随手写了 `number`，补了键没补类型**。

#### 同族

与 **N-19**（v1.1 元数据被当判分字段 ⇒ 9 条题不可解）同族：**schema/元数据的一处声明，让题目在结构上不可解，而报告会把它读成「模型不行」**。
与 N-26（恒真式）也不同族：那条是闸失效判绿，本条是闸**有效但判错对象**。

#### 三个选项

| 选项 | 做法 | 代价 | 风险 |
|---|---|---|---|
| **A（最小修 bug）** | `layup` → `{"type": "object"}` | 动约束解码器 ⇒ 4 条题行为变 ⇒ 必须重跑；S-39 链条同样要走 | 低。只松开类型，不放宽 `required`，不会让别的题变容易 |
| **B（把 layup 子树写全）** | `object` + `required:[plies,material]` + `plies.items.{angle,thickness}` + `material` 10 键（与 prompt 第 34 行逐字一致） | 同上，但约束更紧 | 中。约束越紧，模型越容易在细节上失败 —— 但那时失败是**可归因的**（真·能力问题） |
| **C（不动，另立单）** | 保持现状 | 零 | 4 条题继续固定拿 0 分，且对外表必须注明「4/64 结构性不可解」，否则 TSR 被低估 |

**明确不可取**：在 prompt 里教模型「`layup` 写数字」——那是把 4 条题正式判死，且与数据集真值矛盾。

#### 建议

1. **选 A**（先让题可解，把「不可解」这个污染项从能力评测里摘出去），**若选 A 后仍大面积失败，再升到 B**。
2. **必须与 T-PSA 阶段 2 的同一轮重跑合并**：两者都要全量重生成，跑两次是双倍成本。归因仍可分离——`layup` 只影响 4 条 CFRP 题，其余 60 条不含该键，**按族切一刀就能把两处改动的效果分开**。
3. 无论选哪个，`CLAIMS.md` / 对外表都要先写清「4 条 CFRP 题在旧 schema 下结构性不可解」，否则 C-033 的 TSR 会被当成模型弱项读。

#### 待拍板

**A / B / C，以及是否与 T-PSA 阶段 2 合并重跑。** 未拍板前本文件不动 `schema_task.json` 一个字节。

### N-30（**高，schema 与 gold 的键集双向不一致**；`mesh` 的执行配置豁免是**死代码**）

**发现于** T-PSA 阶段 2 执行途中（2026-11-01），触发点是 **p3 批 TSR 从 92.0% 塌到 36.0%**。与 N-29 同族（都是 schema 自身声明错），但**面更宽、方向是双向的**。

#### 现象与走势

| 批次 | 首轮结构通过 | TSR（exam 25 条） | 说明 |
|---|---|---|---|
| 基线 v7 glm（p2 prompt） | 0/59 | **23/25 = 92.0%** | 首轮必错，修 1–2 轮后基本对 |
| p3（C1–C4 全部写入 prompt） | **39/59 = 66.1%** | **9/25 = 36.0%** | 结构全绿，答案塌了 |

⇒ **这是一次「闸变松、答案变错」的回归**：结构口径一个红点都没有，只有判分口径能看出来。

#### 根因（三方对照，全部实读）

| 块 | `schema_task.json` 声明的键 | gold 里实际有的键 | 后果 |
|---|---|---|---|
| `mesh` | `size_chord`/`size_span`/**`order`**/**`refine_le`** | `size_chord`/`size_span` + 7 个执行键（`algorithm_2d`/`element_order`/`leading_edge_threshold`/`min_jacobian`/`recombination_algorithm`/`recombine`/`refine_at_leading_edge`） | **双向错**：前向 — 写 `order`/`refine_le` 过 ajv，但 gold 无此键 ⇒ `spec_fidelity` 判「自创键」= **FAIL**；反向 — 7 个执行键 schema `additionalProperties=false` **拒收**，模型根本写不进去 |
| `extra` | `end_shear`/`end_moment`/**`end_tension`** | `end_shear`/`end_moment`（柱壳 7/7）+ `end_torque`/`torque_axis_dof`/`moment_axis`/`shear_axis`/`split_tag`/`sweep_index`/`v11_*` | `end_tension` 是**陷阱键**（schema 合法、gold 64/64 都没有）；`end_torque`/`torque_axis_dof` **schema 拒收但 3 条 gold 有** ⇒ 那 3 条结构性不可解 |
| `material`/`load`/`bc`/`analysis` | 与 gold 完全一致（5/3/2/6 键） | 同 | 无问题 |

**关键一点：`EXEC_CONFIG_KEYS` 救不了自创键。** `evaluate.py:219` 的豁免只在「**gold 有的键**、值填错」这个分支里生效（`for k in sorted(gh.keys())`）；而自创键检查在 `evaluate.py:238-248`，**完全不查 `EXEC_CONFIG_KEYS`**。
所以「`element_order` 等 7 个键是豁免的」这句话在本数据集里**从未被执行过**——模型写不进去，豁免分支永远走不到。**这是第二处「按定义恒不成立」的死代码**（同 N-26 族，但表现形式不同：那条是恒真，这条是恒不触发）。

#### 为什么 p3 会踩上去（归因链）

C4 把 `ALLOWED_HINT`（原本只在**修复轮**把错误推回给模型时才附上的「允许键清单」）前置到首轮。而那份清单的内容来自 **ajv 错误原文**：

```
/mesh 不允许的键 "size"，请删除。mesh 允许键: size_chord/size_span/order/refine_le
```

⇒ **清单本身是 schema 生成的，所以清单把 schema 的错误也一起搬进了首轮 prompt**。模型照单全收，38/59 条写上了 `order`/`refine_le`。

> 这条同时解释了 T-B1KPI 的「L1 修复成功率 100%」：修复轮给的是同一份清单，清单里 5 个键有 3 个（`size_chord`/`size_span`/`size`→已拒）是对的，模型照着改自然能过闸——**过闸不等于答对**。

#### 与 N-29 的关系

| | N-29 | N-30 |
|---|---|---|
| 覆盖面 | 4 条 CFRP 题 | **全部 64 条**（`mesh` 双向不一致影响每一题） |
| 方向 | 单向错（类型） | **双向错**（多声明 + 少声明） |
| 表现 | 题不可解，2 条逃法都 FAIL | 闸变松：写错能过闸，然后判分 FAIL |

#### 三个选项

| 选项 | 做法 | 代价 | 风险 |
|---|---|---|---|
| **A（改 schema 对齐 gold）** | `mesh` 删 `order`/`refine_le`、补 7 个执行键；`extra` 删 `end_tension`、补 `end_torque`/`torque_axis_dof` | 动约束解码器 ⇒ 全量重跑 + S-39 链条 | 中。补上执行键后模型会写它们，值几乎必然不对 ⇒ 靠 `EXEC_CONFIG_KEYS` 豁免才不 FAIL，**豁免链要同时验** |
| **B（只改 prompt 绕开陷阱键）** | 本轮已做：prompt 明写「`mesh` 只写 `size_chord`/`size_span`，不写 `order`/`refine_le`」 | 零（已在 p4 里） | 低，但**只是绕开，不是修**：schema 仍然对任何第三方解封者说谎 |
| **C（不动，登记）** | 保持现状 | 零 | 每个新接手的人都会再踩一次；p3 那次塌陷已证明代价 |

**本轮已按 B 处置**（schema 一个字节没动），A/C 待拍板。

#### 建议

1. **短期按 B 收口**，把 p4 的数字作为 T-PSA 阶段 2 的结果。
2. **中期选 A**，但必须与 N-29 合并成一次 schema 整改 + 一次全量重跑（两处都动 schema，分开跑是双倍成本）。
3. 无论选哪个，`schema_task.json` 与 gold 的键集一致性**应当有闸**——本轮只做了一次性人工核对，没有常驻判据。这是缺口，已登记进 `ROADMAP.md` §13。

#### 待拍板

**A / B / C。** 未拍板前本文件不动 `schema_task.json` 一个字节。

### N-31（**高，方法论**）`temperature: 0` 不等于可复现 ⇒ 单次冒烟不能作为「prompt 改动有效」的证据，±1~2 条差异不可归因

**发现于** T-PSA 阶段 2 第三轮（p5c），2026-11-01。触发点：p5c 的 6 条冒烟显示「两条 fabricated 都修好了」，全量跑完同一条题又变回 `fabricated`。

#### 实测（同题 / 同 prompt / 同模型 / 连跑两次）

固定条件：`L3_fuselage_barrel_d1600_l1600_str8_frm3`、`prompt_sha256 = c37862f9…`、`deepseek-v4-pro`、`--max-turns 3`；
生成器 `gen_candidates_v2.js:223` 显式 `temperature: 0`。

| 运行 | `turns_used` | 输出 | `n_frames` |
|---|---|---|---|
| run1 | 1 | **spec** | **0**（`fabricated`，判分 FAIL） |
| run2 | 2 | **clarify `["n_frames"]`** | —（`clarify_ok`，判分 PASS） |

⇒ **同一条题、同一个 prompt，两次运行给出「编造 vs 澄清」两种相反行为。** 闸与判分都没错，是**被测对象本身不可复现**。

#### 后果（本轮直接受害者）

1. 我据 6 条**单次**冒烟判定 p5c「有效」（两条回归都回到 `clarify_ok`），全量跑完不成立。
2. 同一 prompt 在两套卷上对同一模型反向：ds 的 exam TSR **v7 92.0%→84.0%（降）、v6c 88.0%→92.0%（升）**。
   ⇒ 若只跑一套卷，会得出完全相反的两个结论，而两个都会写成「实测」。
3. `p2 / p4 / p5c` 三代的差异中，凡是 **±1~2 条**的部分都在这个噪声带内，**不得归因到 prompt**。

#### 哪些结论仍然稳（远超噪声）

| 指标 | 基线 | 改后 | 是否可归因 |
|---|---|---|---|
| 结构首轮错误 `material` 缺失 | 174 条 | **0** | 可（三个数量级） |
| 结构首轮错误 `mesh` required 缺 | 42 | **0** | 可 |
| 结构首轮错误 `size` 被拒 | 21 | **0** | 可 |
| 首轮有效题数 | glm 5 / ds 3 | **47 / 57** | 可（54 条题的差别） |
| exam TSR（glm） | 92.0% | 92.0% | 无变化 |
| exam TSR（ds） | 92.0 / 88.0 | 84.0 / 92.0 | **不可归因，按噪声处理** |
| `fabricated` 条数（ds） | 0 | 1~2 | **不可归因**（同题两次运行即 0↔1） |

#### 同族与区别

与 **N-26**（恒真式）不同族：那条是「判据恒成立、永远判绿」；本条是**判据没问题、被测对象随机**。
与 **B 段「L1 修复成功率 100%」** 有共同点：都是**把随机性/时机读成了能力**。

#### 三个选项

| 选项 | 做法 | 代价 |
|---|---|---|
| **A（默认，本轮采用）** | 如实标注噪声带：只把「结构错误清零」「首轮有效题数」作为可归因收益；±1~2 条一律写「低于单次运行噪声，不归因」 | 零 |
| **B（提高分辨率）** | 给 `gen_candidates_v2.js` 加 `--repeat N`，同题跑 N 次取多数/中位 | 每轮成本 ×N；N=3 起 |
| **C（物理固定）** | 若厂商支持 `seed`，固定 seed 并记录 | 依赖厂商；换模型即失效 |

**建议**：A 立刻生效（本轮报告必须这么写）；B 在下一轮对外发布前做一次（至少对 exam 25 条做 N=3），否则 C-032/C-033 的 CI 会被读成「精确到 1 条」。

### N-32（**高，结构性阻塞**）换 prompt 必须重算 MSR，而 MSR 依赖求解器 ⇒ 求解器缺失时 **prompt 迭代无法闭环**

**发现于** T-PSA 阶段 2 收口时（2026-11-01）。p5c 的四批候选与四份成绩单都已跑完，但在准备把 C-032/C-033 切到 p5c 时被卡住。

#### 卡在哪（两条闸串起来的死锁）

| 闸 | 要求 | 实测 |
|---|---|---|
| **S-39** | C-032/C-033 成绩单的 `provenance.prompt_sha256` == **生成器当前 SYS** 的 sha256 | 改 prompt ⇒ 旧成绩单立刻不等 ⇒ 必须换代 |
| **S-37** | 每份成绩单必须有 `msr_section` 且四类分母闭合 | p5 成绩单**没有** `msr_section`（没跑过 `msr_l3.py`）⇒ 实测 `ok=False`，**没有静默跳过**（这点是对的） |

⇒ 改 prompt → 必须换代成绩单 → 必须有 MSR → MSR 要跑求解器。

#### 求解器实测：不在

`solver.py` 的三级查找全部落空：

| 级 | 位置 | 实测 |
|---|---|---|
| 1 | `$FEAGPT_CCX` / `$FEAGPT_ABAQUS` | 未设 |
| 2 | `tools/calculix/<ver>/ccx_static.exe` | **目录不存在**；且 `tools/calculix/` 在 `.gitignore:38` ⇒ 本来就不入库 |
| 3 | `PATH` 上的 `ccx` / `ccx_static` / `ccx_2.*` / `abaqus` | 全无 |

残留证据只有历史日志（`_probe_m10/ccx_sweep30.log` 等）⇒ **这台机器曾经跑过求解，现在二进制没了。**

#### 后果

1. 本轮 T-PSA 的 p5c **不能作为对外记录**：它的准确率数字（glm 92.0% / ds 92.0%，v6c）无法配上 MSR，而 C-032/C-033 是 GATED 的对外 headline。
2. 因此 `gen_candidates_v2.js` 的 `SYS` **已回滚到 `ce225186…`**，C-032/C-033 仍指向 p2 成绩单，闸全绿。
3. p5c 的全部实测产物（4 批候选 + 4 份成绩单 + prompt 文本 `reports/diagnostics/prompt_p5c_sys.txt`，sha `c37862f9…`）**全部保留**，作为「已实测、待 MSR 重算即可采纳」的候选。

#### 更一般的判断（这条比本轮更重要）

**这个仓库的 prompt 迭代成本 = 一次全量重生成 + 一次全量求解**。只要求解器缺位，任何 prompt 改动都只能是「实验」，无法进入 CLAIMS。这不是本轮才有的问题——它意味着**未来所有 prompt/schema 改动都会被同一处卡住**。

#### 三个选项

| 选项 | 做法 | 代价 | 风险 |
|---|---|---|---|
| **A（推荐，下一步）** | 在**有求解器**的环境完成 p5c 换代：① 4 批 `msr_l3.py` ② `bootstrap_ci.py` ③ 改 `_sc_paths[2]/[3]` ④ 更新 C-032/C-033/C-040 | 一次全量求解（4 批，估计 1–2 小时） | 低。所有候选与 sha 已冻结，重跑的是判分不是生成 |
| **B（解耦，风险高）** | 改 S-37/S-39 口径：允许「MSR 与 prompt 代际不同步」但必须带 `reason` 与代际标注 | 改闸 | 中高。这正是 R75 说的「放宽最容易顺手改宽判定条件」；要写谓词，且会让对外表出现混代数字 |
| **C（保持现状）** | SYS 留在 `ce225186`，p5c 只作实验记录 | 零 | 低。但结构错误清零、首轮有效 3→28 的收益不进入对外记录 |

**本轮已执行 C**（回滚 + 全量保留证据）；**A 待拍板**。

#### ★★ 更正（2026-11-01 15:30，本条的前提不成立 —— 「求解器缺失」是错的）

**结论**：本机**有**求解器，`solver.py` 能自动发现它，实测单条 rc=0、6.2 秒。**N-32 的阻塞不存在，A 不必等「有求解器的环境」，现在就能做。**

**证据（实测，不是推断）**：
```
F:\AI FEA Modeling DataSets\tools\calculix\calculix_2.23_4win\
  ccx_static.exe   ccx_i4.exe   ccx_dynamic.exe   （同级还有 calculix_2.23_4win.zip）
solver._calculix_candidates() -> 3 个候选，全部 exists=True
msr_l3.py --only L3_open_hole_panel_400x200_d40 -> rc=0, wall=6.2s, gates 全 True
```

**我为什么判错**：上一轮查了三处就下结论，**漏掉了唯一命中的那一处**：
| 查过 | 结果 |
|---|---|
| `$FEAGPT_CCX` | 未设 ⇒ 无 |
| `feagpt_repro/tools/calculix/` | 不存在（**查错了层级**：`solver.py` 是向上走 4 层找**仓库根**的 `tools/`） |
| PATH | 无 `ccx*` ⇒ 无 |
| **仓库根 `tools/calculix/`** | **没查** ← 就在这儿 |

而 `solver.py:146-165` 的探测顺序写得很清楚：`$FEAGPT_CCX` → 向上 4 层找 `<root>/tools/calculix/**/{ccx_static,ccx_i4,ccx_dynamic}.exe` → PATH。**代码里早写了，我没读就下了结论。**

**同族教训**（比我犯的错更值钱）：
1. **「我查了三个地方都没有」≠「它不存在」** —— 判据/检查的**搜索空间**必须从代码里取，不能自己拍。`solver.py` 就是那个「规则表」，绕过它另写一套探测路径，等于 N-33 里「第二处实现就是 bug」的同一件事。
2. **一个错的阻塞判断，代价是整条工作线停了**：本轮据此把 `SYS` 回滚、把 p5c 降级为「实验」、还在报告里写了「结构性阻塞」。**回滚本身是对的（当时证据不足），但结论「求解器缺失」是错的**，必须一起改。
3. 附带影响：`RUBRIC` v6.11 与 T-PSA 报告 §11/§12 里「本机无求解器」的措辞要跟着更正（见下）。

**★ 同一次判断里的第二个错（当场自纠，留痕）**：我一度把这段写成「文档缺陷 **F-11**：`QUICKSTART.md` §5 与 `DATA.md` §4 的 `--report /tmp/my_c032.json` 会 `FileNotFoundError`，第三方会踩」。**这是假的，已撤回** —— 回原文看：`QUICKSTART.md:138` 明写「**`--report` 必须指向 §4 已经生成的那个成绩单文件**」，而 §4（`score_baseline.py`）正是**先用同一路径**生成 `/tmp/my_c032.json`。文档是对的。**是我抽了 §5 一条命令单独跑、跳过了 §4 的前置生成**。

**教训**：验证文档里的命令，**必须按文档顺序整节跑**。单抽一条跑出来的 `FileNotFoundError`，证明的是「前置步骤没做」，不是「文档写错」。这与本条的第一个错是同一个毛病：**我按自己的路径去试，而不是按既有的规则去试**（前者另写一套探测、后者跳过前置步骤）。⇒ 同族于「判据红了先怀疑脚手架」：**命令崩了，先怀疑自己的跑法**。

> 事实澄清（保留，有用）：`msr_l3.py` 确实是「读已有成绩单 + 合并 MSR 段」（`sc = json.load(open(report_path))`），所以它**不能**凭空新建成绩单 —— 但这一点文档已经写对了。

**处置**：A 立即执行（不再等外部环境）；本条的「三个选项」保留作历史，但 B/C 已无必要。

---


### N-33（中，**判据缺陷，已在 v6.11 修掉**）S-44(b) 的两个根因：把「上界」当「最新一条」的代理 + 从含正文的整行提取「覆盖」

**发现时点**：T-PSA 阶段 2 收口，加 NC-70 后 `check_claims` 报 `S-44` 红。**红是误报，INDEX 是对的** —— 但顺着查下去挖出两个真缺陷。

**根因一（代理错）**：旧判据断言「主区间上界 == artifact 最大 NC 编号」，把「上界」当成「最新一条」的代理，**隐含要求 NC 编号连续**。实际编号一直跳号：

```
70 条 = PC-1 + NC-1..67 + NC-15b + NC-70        （实测，无 NC-68/NC-69）
```

⇒ 旧文里「69/69」的 **69 是条数**，不是「NC-69 这条负控」。本轮新增 NC-70 后，`max(NC)=70` 而主区间上界 67 ⇒ 判红，**报的是「INDEX 漏报」，实际是判据的假设破了**。

**根因二（提权，更严重）**：改成「逐条覆盖」后，第一版实现从**整行**提取 `NC-\d+` 当「点名」。而 INDEX 第 26 行在括号里**逐条描述每条负控**（`**NC-49 四向**`…`**NC-67 五向**`）⇒ **每条编号在正文里都被提到过** ⇒ 覆盖**永远成立**。

**这一条是被负控抓出来的**：改完判据跑全量负控，`NC-49` 的 N-2 向（主区间上界 67→66）由「红」退化成「**漏判**」—— NC-67 靠正文那句「**NC-67 五向**」仍判已覆盖。若只看 `check_claims` 全绿，这个退化**不会暴露**（`check_claims` 当时确实全绿）。

**修正（v6.11，已入库）**：
1. 删掉「上界 == 最大编号」代理，改**逐条覆盖**：每条 id 必须落在某 `NC-a..b` 区间内或被显式点名。
2. 覆盖**只从结构化清单段读**：`C-0xx：` 之后、第一个 `（` 之前。找不到清单段**判红**（不许回退整行扫，否则根因二原样复活）。
3. 反向加「区间不得虚报」：区间声称 `NC-a..b` 存在的编号必须真在 artifact 里（防把区间写成 `NC-23..70` 抹平跳号这种**编数**）。

**六向自检**（每向断言红的原因对）：原样绿 / 漏报最新一条红 / 区间抹平跳号红 / 分子≠分母红 / 主区间上界减 1 红 / 清单段缺失红。**NC-49 四向恢复「正向过 + 三向全红」**。

**判断法（可复用）**：**这条判据在「行内既有清单又有逐条说明」的文本上还成立吗？** 同族于 N-28（子串匹配假通过）与「提及 ≠ 引用」：只要判据从**自然语言正文**里取「声明」，正文越详细，判据越松 —— 最终松到恒真。R58 原文就写着「只认结构化记号，不按自然语言判读」，这次是它被自己违反。

**边界（诚实说）**：本修正只保证「INDEX 声称的清单与 artifact 一致」；**守不了「INDEX 该写而没写某个 artifact」以外的内容漂移**（比如成绩单路径写错但编号对）—— 那要靠 S-29/S-44(a) 与 artifact 实读。

**三个选项**：**A（已执行）** 改判据实现、不新增 R 编号（记 v6.11）；B 新增 R76 单列这条规则（会扩大 R 表与循环依赖）；C 保持旧判据、把 INDEX 改成 `NC-23..68`（**编数**，明确否决）。

---

### N-34（中，**已按 A 修正 SYS（2026-11-04 老王拍板）**）SYS 说「板壳类用 `size`」，而四族 gold 都没有 `size` —— 改对过、被回滚带走、无闸报错

**发现时点**：T-L27c v3（L2 prompt 单变量消融）。C 臂加覆盖段后 glm 从 10/16 到 16/16，**而这条覆盖段覆盖的是 SYS 自己的一句错话** —— 顺着查下去才发现它一直在。

#### 事实

`gen_candidates_v2.js` 的 `SYS` 常量（**L3 与 L2 共用**）第 40 行：

```
网格键 size_chord/size_span（翼盒）、size（板壳类）
```

实测 `FEM-Bench-Aero/modeling/*/spec.json` 全部 64 个 gold：**mesh 段只有 `size_chord` / `size_span`，没有任何一个 gold 有 `size`**。四族一致（含开孔板、加筋板、柱壳）。

后果（`spec_fidelity` 的两条规则同时触发）：模型按 prompt 写 `size` ⇒ ① `size_chord`/`size_span` 缺失 ⇒ FAIL；② `size` 是 gold 没有的键 ⇒ 按**自造键**判 FAIL。**一个错误指令吃两次罚。**

#### 来历：改对过，被回滚带走，且没有任何闸报错

| 时点 | 状态 | 证据 |
|---|---|---|
| `b2e9b74`（2026-10-25，W4d L3 主基线） | 这句错话引入，存在于 `ce225186` | `git log -S "size（板壳类）" -- feagpt_repro/gen_candidates_v2.js` |
| p3 / p4（T-PSA 阶段 2） | **已改对** | `_psa_fix_mesh_keys.py` 的 `OLD1`（p3 版）与 `NEW1`（p4 版）**都含**「板壳类也用这两个键名——没有 size 这个键」 |
| 2026-11-01 | SYS **回滚到 `ce225186`**（p5c 作废，为「不换代」）⇒ 更正**跟着回滚一起消失** | `.workbuddy/memory/2026-11-01.md`「SYS 已回滚 `ce225186`」 |
| 回滚当时 | **无任何闸报错** | 闸只锚「sha 变没变」（S-39），不锚「这个 sha 对应的那句话对不对」 |

⇒ **可复用的判断法：回滚能证「回到原样」，证不了「原样是对的」。** 锚点闸守同一性，正确性必须另有一条闸。同族于 N-19（「口径一致」不等于「口径对」）。

#### 影响范围：已发布数字 **零变动**（实测，不是推断）

| 已发布口径 | 受影响 | 证据 |
|---|---|---|
| **L3 v7（C-032 来源卷）** | **否** | 复算 `candidates_l3_v7_{glm,ds}` 共 118 个给出 spec 的候选 ⇒ **mesh 段失败 0 条**；复算 FAIL 数 glm 11 / ds 9，与已发布 `sfr_all`（48/59、50/59）完全吻合 |
| **L2 v7（64 条）** | **否** | 64 条 `expected_clarifications` **全部非空** ⇒ 题型是「应追问」，不判 spec 保真 |
| L2 informative 诊断卷（16 条） | **是** | base arm 12 条问题题 **全部**多写 `size`；C 臂修好后 0 条。本来就未进对外数字 |

**L3 为什么没中招**：L3 是 NL 输入、无 spec 呈现，模型凭工程常识自己写 `size_chord`/`size_span`，恰好对。L2 informative 把 spec 摊开给模型看，模型看到题面写 `size_chord`、prompt 说「板壳类用 size」，一部分选择听 prompt ⇒ 合并/改名 ⇒ 被罚。

#### 已补的闸（本轮入库，不依赖拍板）

`_l27c_check_mesh_keys.py` —— 判据落在**候选产物实际写了哪些 mesh 键**，不判 prompt 文本。

**为什么判效果而不判文本**（第一版写错、值得记）：第一版读 `SYS`、抽 `\bsize\b` 词元再核 gold，结果 base 与 meshfix **两个 arm 都判红** —— 因为覆盖段原文是「…**没有 size 这个键**」，这句话**提到**了 `size`，是否定它。⇒ **「是否出现某词」这条轴根本无法区分肯定与否定**，同于 R77 ⑧（不做关键字判文本对错的闸）。改判效果后双向清楚：base 红在「多写 size」、C 臂绿。

#### 三个选项

- **A（推荐，但需要拍板）**：改 `SYS` 那句话（删「、size（板壳类）」六个字），**同步全量重跑 L3 + L2**，让 `ce225186` 变成新 sha，`C-032/C-033/C-040/C-041` 一起换代（R53 全量重跑，约 110 条 + MSR）。**代价**：headline 变数、R65 桥接、一次全量跑；**收益**：新卷不再被这句错话污染，且 §13 第 10 项要继续做就必须先修它。
- **B**：SYS 不动，只在**每一份带 spec 呈现的输入**里加覆盖段（本轮 C 臂的做法）。**代价**：prompt 里同时存在一句话和一句「上文不算」，对 ds 反而增加追问（实测 1→4 条）；**收益**：零换代风险。**不推荐**：它把一个矛盾显式化，对一部分模型是噪声源。
- **C**：SYS 不动、也不加覆盖段，只在文档里记着。**明确否决**：下一版卷会原样再中招，且这次的教训就是「记在文档里的缺陷没人执行就没人验」。

**建议**：走 **A**，但**排在 §13 第 10 项之前** —— 因为第 10 项（信息完备题型）恰恰是把 spec 摊给模型看的题型，不修这句就是拿带缺陷的 prompt 测「模型会不会追问」。

**边界（诚实说）**：本条的「零变动」结论**只覆盖 mesh 段**。`SYS` 里是否还有别的键名与 gold 冲突，**没有系统性核过** —— 本轮只核了 `mesh` 段（因为它是这轮实验的变量）。要系统性核，得把 `GRADED_FIELDS` 与 `EXEC_CONFIG_KEYS` 的每个键反向扫一遍 `SYS` 文本，那是另一个任务。

#### 执行结果（2026-11-04，老王拍板 A 并已落地）

**改法**：`网格键 size_chord/size_span（翼盒）、size（板壳类）。` → `网格键 size_chord/size_span（四族通用）。`

三点判断：

1. **连「（翼盒）」一起改对**，不是只删六个字。实测 64 个 gold 覆盖四族、mesh 键集**完全一致**（9 键），板壳类同样用这两个键 —— 留着「（翼盒）」等于修一半。
2. **刻意不在 SYS 里提「size」这个词**。上一轮 C 臂覆盖段原文「…**没有 size 这个键**」反而让 ds 追问了 4 条（把矛盾显式化）。⇒ **修 prompt 时「点名否定」比「不说」更容易诱发追问。**
3. 其余一字未动；题面、rubric、判分器零改动。

**四个 sha 全变**：`ce225186`→**`6b90daf0`**（SYS）／`03129c56`→**`c8de26d4`**（L2）／`094cd870`→**`b4c2dd6e`**（REFUSE）／`99466166`→**`f6cb45f7`**（L2_STRICT）。

**效果一：错误模式彻底归零**

| | 旧 SYS | 新 SYS |
|---|---|---|
| 多余 `size` 键（L2 informative，两模型） | **12 条题**（glm 9/14、ds 3/7，形态完全一致） | **0**（L2+L3、两模型、全部候选） |

**效果二：glm 显著、ds 不敏感**

| 模型 | 旧 SYS base | 新 SYS base | 旧 SYS strict | 新 SYS strict 两遍 | 配对（旧 strict → 新 strict） |
|---|---|---|---|---|---|
| glm | 3/16 | **13/16** | 10/16 | **16/16、15/16** | b=0/c=6，**p=0.0312** |
| ds | 4/16 | 1/16 | 13/16 | **14/16、13/16** | b=1/c=2，p=1.0000 |

> **★ 本表是 N-35 修正后的口径（2026-11-05 重算）**。旧口径（未拆 `DATASET_META_KEYS`）的对应值是
> glm 2→8→10→16/14、ds 3→1→8→10/12，配对 ds 为 b=2/c=4、p=0.6875。逐 arm 的新旧对照见
> `feagpt_repro/reports/diagnostics/n35_bridge.md`（由 `_n35_bridge.py` 从两份 artifact 现读生成，不手抄）。
> **两套口径下本条结论不变**：glm 显著、ds 不可分辨；且新口径下 ds 的 SYS 效应更小（p 从 0.6875 升到 **1.0000**）。

⇒ 与 T-L27c v3 的结论同型：**补漏式修法不可假设跨模型通用**。ds 的问题不在 mesh 键，在于「把 schema 规范意见当成澄清理由」。

**效果三：L3 零回归**

- v7 卷：glm exam **23/25 → 23/25**（SFR 20/22 → 20/22），`exam` 块逐字段一致；全卷判分段 58/64 相同，差异 6 条**全在 dev**。ds 两遍 22/23（旧 23），跨度在噪声内。
- v6c 卷（C-032/C-033 的 artifact）：见 `reports/diagnostics/task_l27c_v4_report.md` §7。

**效果四：L2 v7 必须做「旧 SYS 今日对照」才能归因**

ds 从 36/64 跳到 52/64（+16）幅度太大。把 SYS 临时改回旧表述（sha 验回 `ce225186`）跑全量 64 条得 **40/64**，再改回（sha 验回 `6b90daf0`）。⇒ 拆成 **跨天波动 ≈ +4**（同 prompt 5 天前 36 → 今日 40）＋ **SYS 效应 ≈ +6~+12**（今日旧 40 vs 今日新 46~52，两遍区间不重叠）。

**不做这一步，就会把服务端波动算成 prompt 红利。**

**遗留（由本轮新开）**：`CONFLICT` N-35 —— ✅ **已解决（2026-11-05，拍板 B：拆 `DATASET_META_KEYS`）**，见下节。

---

### N-35（中，**判分口径未适配新题型**）✅ **已修（拍板 B，2026-11-05）** `EXEC_CONFIG_KEYS` 一个集合混装两类键 —— `engineering_layer` 开关在 L2 轨道上把这两类一起关掉了

**发现于** T-L27c v4（2026-11-04），SYS 修正后跑 L2 informative 小样本时暴露。

#### 现象

`score_l2.py` 调 `judge_l3_candidate()` **不传 `engineering_layer`**（默认 `False`），而 `score_baseline.py` 传 `engineering_layer=(task['input_level'] == 'L3')`。
后果：`evaluate.py:232` 的 `if engineering_layer and k in EXEC_CONFIG_KEYS.get(holder, ())` 这个豁免分支，**在 L3 生效、在 L2 从不生效**。

L2 informative 的失败字段里因此大量出现这些键：

```
extra.split_tag / extra.v11_bracket / extra.v11_interior_holdout / extra.v11_template
extra.moment_axis / extra.shear_axis / extra.sweep_index
mesh.algorithm_2d / mesh.element_order / mesh.leading_edge_threshold / mesh.min_jacobian / …
```

#### 根因：一个集合装了两类来源不同的键

`EXEC_CONFIG_KEYS` 的注释把豁免前提写得很清楚：「gold 内部编码键（数据集离散索引/方向轴表示，**NL 任务书永远不会提及**）」。这个前提在 L3 成立（输入是自然语言），在 **L2 informative 不成立**（输入是整份 spec JSON）。

但「前提不成立」不等于「这些键都该判」。它们其实是两类：

| 类 | 键 | L2 题面给了吗 | 该不该判 |
|---|---|---|---|
| **真实执行配置** | `algorithm_2d` / `element_order` / `leading_edge_threshold` / `min_jacobian` / `recombination_algorithm` / `recombine` / `refine_at_leading_edge`（mesh 7 个） | 给了 | **该判** —— 这正是「逐字转写」的考点 |
| **数据集构建元信息** | `sweep_index` / `shear_axis` / `moment_axis` / `split_tag` / `v11_bracket` / `v11_template` / `v11_interior_holdout`（**7 个** —— 原稿写「6 个」是笔误，它自己列了 7 个名字） | 给了 | **任何层都不该判** —— 模型产出它们无工程意义，`v11_bracket` 甚至是一句中文描述（「柱长 1600 ↔ 2000（d2000 系列的 l1600 / l2000 两条都在集）」），要求逐字转写不合常理 |

⇒ 用**同一个布尔开关**控制两类键，必然顾此失彼：打开就丢掉 mesh 考点，关上就压住分数。

#### 量化（16 条 informative 诊断卷，三套口径逐题重算）

★ **原稿这张表只有一个「剥离后」列，把选项 A 的效果当成了 B 的预期值**（`15/16` 是**连 mesh 7 键一起剥**
得到的）。拍板后按三个 arm 重算，逐题实测见 `feagpt_repro/reports/diagnostics/n35_key_split.json`：

| arm | 旧口径（HEAD，两键混装） | **B：只剥 extra 7 键**（拍板项） | A：extra 7 + mesh 7 = **14** 键全剥 |
|---|---|---|---|
| glm 新 base | 8/16 | **13/16** | 15/16 |
| glm 新 strict 第 1 遍 | 16/16 | 16/16 | 16/16 |
| glm 新 strict 第 2 遍 | 14/16 | **15/16** | 16/16 |
| ds 新 strict 第 1 遍 | 10/16 | **14/16** | 14/16 |

⇒ **B 与 A 的差就是「mesh 转写考点」值多少分**：glm base 2 条、glm strict 第 2 遍 1 条、合计 **4 条**
（`n35_key_split.json` 的 `mesh_keys_cost_total`）。这 4 条是模型真的没把 `algorithm_2d`/`element_order`
等 7 个执行配置逐字转写对 —— **这正是该题型要考的东西**，不该跟着元信息一起豁免。

glm 第二遍旧口径失败的那 2 条，全部由这两类键造成（1 条 mesh 6 键、1 条 extra 4 键）—— **没有一条是多写 `size`**（N-34 已修净）。

#### 处置：**已拍板 B（老王 2026-11-04），2026-11-05 落地**

- `evaluate.py` 拆出 **`DATASET_META_KEYS`**（`extra` 7 键），判分时**无条件跳过**（放在 `engineering_layer`
  分支之前，不依赖任何开关）；`EXEC_CONFIG_KEYS` 原样只留 mesh 7 + analysis 5，L3 豁免行为一字未动。
- 跳过**不做静默 continue**：记进 `dataset_meta_skipped` 随结果返回（每份 `spec_fidelity` 都有
  `n_dataset_meta_skipped`），报告里看得到跳过了什么。
- `r32_audit.py` 同步认新集合（**同一类豁免只装在判分器一个调用点 = 没装**：审计会把这些键读成
  「题面推不出 ⇒ VIOLATION」，而判分器其实不看它们 ⇒ 两边对同一份卷给出两个结论）。
- **闸**：`S-63` + `_n35_key_guard.py`（A–G 八向，**行为判据**，不读键名名单）；负控 `NC-84` 五向守变异
  （真码不误报 / mesh 并入元信息集必红 / 回到旧态必红 / 只清空元信息集必红 / 放宽自创键必红）⇒ 负控 **84/84**。

**实测四条（缺一不算完）**：

| 判据 | 结果 | 证据 |
|---|---|---|
| L3 零回归 | v6c 两模型 **42→42**，55×2 **逐题相同** | `n35_key_split.json` J1 |
| L2 v7 零回归 | **46/64、52/64**，64×2 **判类零差异** | 两臂 `score_l2` 全流程对比 |
| 等价性 | 「判分时跳过」≡「把这些键从 gold/候选里物理删掉」，8 批次**等价差全 0** | 同上 J2 |
| 正向增量 | 被元信息键压住的 **15 条**题全部转绿，无一转红；mesh 考点仍值 **4** 条 | 同上 J2/J3/J6 |

**口径变更的连带处理（R-A2）**：判分口径属 rubric 层 ⇒ 旧代诊断成绩单**归档不覆盖**
（`reports/archive/l2i_*__pre_n35.json` 16 份、`l27c_v*__pre_n35.*` 16 份），新代重出，
并出一份 **bridge 表**（`diagnostics/n35_bridge.md`，16 arms / 6 组配对，由脚本现读生成、不手抄）。
**新旧结论对照**：只有 1 处显著性翻转（v3 ds base→strict 从 p=0.0625 变 **p=0.0039**，即更显著）、
1 处效应方向翻转（v3 ds strict→meshfix 从 +2 变 −2，两口径下都不显著）⇒ **没有任何已发表结论被推翻**。

#### 边界（诚实说）

①本条只覆盖 `mesh` 与 `extra` 两处；`analysis` 段 5 个键、`load.direction` 未逐一验证（L2 的 16 条里 `extra` 为空的 8 条不受本条影响）。
②`extra.moment_axis` / `shear_axis` 在 gold 里**确实存在**（柱壳 4 条），不是自创键；它们被豁免的理由是「NL 任务书不会提及」，不是「gold 没有」。
③与 **N-30** 是互补关系、不是同一条：N-30 说的是「自创键检查根本不查这个集合」（豁免**恒不触发**），本条说的是「gold 有、候选没写」这条路径上豁免**被开关关掉**。两条都要修才闭合。**本次仍只修了后者** —— 自创键路径**一个字未动**（`_n35_key_guard.py` 的 G 向专门守这条不许被顺手放宽）。
④本题型**仍未进卷**：`informative` 层现在只是 diagnostic，**不得**据此宣称「L2 已装上该题型」或「L2 抗退化」。
⑤**题面侧未剥离那 7 个键**（B 的可选第②点）。判分侧已完全等价于「键不存在」（J2 等价差 0），所以不影响任何分数；题面清洁留给题型进卷时一起做（那时是新卷，天然不带）。
⑥**原稿④里有一句话必须更正**：它写「剥掉这 13 个键后 L2 v7 的 glm **49/64**、ds **36/64**，与已发布值一个不差（实测）」——这句话**自身矛盾**（已发布值是 **46/64**、**52/64**），而且 L2 v7 的 64 条全是 ec=1、判分走 clarify 分支、**根本不经过** `spec_fidelity`，剥键对它**不可能**有任何影响。已删。实测两臂全流程对比：**46/64、52/64 逐题零差异**。这是「文档写了一个没人能复算的数字」的又一例（与 R-A3 同源）。

---

## 3. 门禁与工作区实况（本轮 pre-flight 原始结果）

```
$ git status --short
 M .workbuddy/memory/2026-10-27.md          ← 我自己上一轮的记忆
 M .workbuddy/memory/MEMORY.md              ← 同上
 M feagpt_repro/reports/check_claims.json    ← 本轮 pre-flight 写的 mtime（见 N-5）
?? CONFLICT.md                               ← 本文件
（AGENTS.md / CLAUDE.md 已 tracked，无未提交改动）

$ python check_claims.py
active claims 27 条 / artifact 49 个 / 语义项 44 条 -> 全过

$ python negative_controls.py
负控: 50/50 ok -> reports/negative_controls_50.json
红线条 R6：负控全绿 ⇒ 允许跑 LLM baseline。

$ python verify_dataset.py --root ../FEM-Bench-Aero
pairing: 55 paired, 9 modeling-only, 0 xval-only -> MISMATCH     ← 等 §7 的 Abaqus 双码
```

---

## 4. 拍板记录（老王，2026-10-27 22:00）

> 原文：「5 条新发现我都按 live 复核，全部成立……**同意全 A**；**N-5 用 C+**（pre-flight `check_claims.py --json "$TEMP/..."`，官方 JSON 收口再写），**T-A2 加 `⓪b` 历史段和 `CLAUDE.md` 一行**；根因是 check_claims 不读 INDEX，**建议 T-A3 gate 先于 v7**。」

| 编号 | 决策 | 落实位置 |
|---|---|---|
| N-1 | **A** | `INDEX.md` §2：⓪ 段改为「前置闸（与 headline 无关）」；其后插入 `⓪-hist` 段，明确 C-029 = prompt v1 代 historical / 不是当前 headline / 仅供消融复现（R53） |
| N-2 | **A** | `INDEX.md:24`：`NC-23..47` → `NC-23..48` |
| N-3 | **A** | `AGENTS.md:14` + §7 rubric 行：改为「R42–R57 判定表在 RUBRIC；R1–R41 在 CLAIMS 红线条」 |
| N-4 | **A** | `AGENTS.md` R-A7：改为「在**状态列**（S-29 所判字段）带『（对外 headline）』；正文提及不算」 |
| N-5 | **C+**（比原 C 更进一步） | `AGENTS.md` §0 命令块 + 新增警示段：pre-flight 必须 `--json "$TEMP/check_claims_preflight.json"`；**官方 JSON 只在收口写一次，且先负控后 check_claims**；`CLAUDE.md` 第 1 条同步 |
| 追加 | T-A2 范围加 `⓪b` 历史段 + `CLAUDE.md` 一行 | 均已执行（`⓪b` 段已标 prompt v1 代 historical + 与 C-032/C-033 不可拼比） |
| 追加 | **T-A3 先于 v7** | 下一步执行：让 `check_claims.py` 读 `INDEX.md`（新增 S-44）+ 负控 NC-49 |

执行顺序：**T-A2（文本）→ T-A3（gate）→ 考卷 v7**。T-A3 必须在 v7 之前，因为 v7 会重写 INDEX 的 headline 段与成绩单路径，没有闸就是裸奔。

---

## 5. 执行状态

| 任务 | 状态 |
|---|---|
| **T-A2**（文本：INDEX ⓪/⓪b/负控行 + AGENTS 三处 + CLAUDE.md 一行） | ✅ 已完成，验收见交付报告 |
| **T-A3**（gate：`check_claims` 读 `INDEX.md` → S-44 + NC-49） | ✅ 已完成（含 S-45/S-46/S-47 + NC-49..52） |
| **T-A4**（R59 收口顺序 + R60 venv + S-45/S-46） | ✅ `6170f3b`，RUBRIC v5.3 |
| **T-A5**（R61 全局求解锁 + S-47 + NC-52） | ✅ `405a4c9`，RUBRIC v5.4 |
| **T-A6**（`check_forms` 陈旧参考路径 → 54 PASS/0 FAIL） | ✅ `cdef350` |
| **Abaqus 双码**（v1.1 的 9 条） | ✅ **已完成**（老王在 WorkBuddy 外跑 `_v11/run_v11_abaqus.bat`，2026-10-28 21:32）。9/9 真跑通；`verify_dataset` = **64 paired / 0 modeling-only / VERDICT: PASS** |
| **T-A7**（gate3 证据链：N-6 + N-7 + N-8） | ✅ **已完成**（老王拍板 A）。真因比初判严重：d36 明细键是 `case` 而脚本查 `case_id` ⇒ **39 条翼盒从来没被逐条读取过**；且翼盒真判据是 vM 中位差 < 5%、不是 max\|u\| < 1%。修后 `gated_pass=57 / reported_only=7 / fail=0`，`headline = 39 field (34 d36 + 5 measured) + 18 scalar + 7 reported-only`，rc=0 |
| **T-A8**（N-9：`external_numbers.md` 后 5 行仍读 `*_d36` 死快照） | ✅ **已完成**（2026-10-28）：三份 v1.1 活 artifact + 关 1 改现算 + 「分母口径」列 + 基线/M14 标版本 + README 去数字 |
| **T-A9**（N-10：C-003 三计数无闸 → S-48 + NC-53） | ✅ **已完成**（`8efdbbe`）：R62/S-48 四条判据 + NC-53 四向；负控 55/55、语义 49/49 |
| **T-A10**（N-12：C-001/2/4/5 与 `external_numbers.md` 无闸） | ✅ **已完成**：S-49 / S-50 / S-51 + C-036 + NC-54 十向 + RUBRIC v5.6（R63/R64） |
| **T-A10b**（N-14：AGENTS/CLAUDE 计数与 §7 快照过期） | ✅ **已完成**：按 D5(b) 去掉写死计数，改「以 §0 实读为准」 |
| **考卷 v7**（接 v1.1 的 9 条进任务层） | ⏸ 未开工；按 R-A1 拆两步 + bridge，且 C-032 的 23/25 将不可比（R-A6） |

> 本轮起按 N-5 的 **C+**：pre-flight 走 `--json "$TEMP/check_claims_preflight.json"`，官方 `reports/check_claims.json` 只在收口写一次（先负控后 check_claims）。

---

## 6. N-37（中，**命名/范围冲突，待拍板**）「C6-P2」一个标签指了两件事

> 触发：2026-11-07 22:23 老王拍板「description 继续硬判，接着开工」，
> 蜗子做 C6-P2 可行性调研时实读 `PROPOSAL_C6_BUCKLING_MODAL.md` 发现口径不一致。
> **按 R-A11 / AGENTS 规约：只写这一页，不改任何 claim / artifact / paper / rubric，等老王拍板。**

### 证据（全部为本次实读）

| # | 来源 | 原文 / 实测 |
|---|---|---|
| 1 | `PROPOSAL_C6_BUCKLING_MODAL.md` §2 | **P2 线性屈曲**：加筋板轴压（N_x 扫描）、柱壳外压；语义量 λ_cr + 屈曲模态数；ccx / abq `*BUCKLE` |
| 2 | 同文件 §5 | 「起步 6–8 条：模态 4（腹板/肋数/展长变体）**+ 屈曲 2–4**（加筋板轴压 2、柱壳外压 1–2）」 |
| 3 | 同文件 §6 第 1 条 | 「P1 模态先 vs P2 屈曲先（推荐 P1；**若本职近期要交轴压校核，P2 提前**）」 |
| 4 | 蜗子 2026-11-07 夜收口报告 §10 / ROADMAP C6 行 / DATA.md §7.7 / MEMORY.md | 把「柱壳/加筋板 + 自主建模题」写成了 **C6-P2 扩卷**（是蜗子的推断，非拍板件） |
| 5 | `grep -rn "buckle&#124;BUCKLE" feagpt/*.py extract_modal_dat.py` | **零命中** ⇒ 屈曲在代码面完全未实现 |
| 6 | `feagpt/inp_writer.py:255-285` | frequency 分支**不按族分支**，只换 step 段；柱壳/加筋板可直接复用（载荷块省略、BC 保留） |
| 7 | `score_v2_modal.py` 硬编码面 | `V2_L1_` 前缀、`N_MODES=10`、`F1_THRESHOLD_REL=0.01`、固定 `modeling_v2/` 路径 ⇒ 扩卷需参数化 |
| 8 | `FEM-Bench-Aero/modeling/` 实读 | 柱壳 **7 条**可选；加筋板 5 条中 `stiffened_panel_800x600[_str3]` 两条长期挂 dev（length/width 角色缺陷）⇒ **实际只剩 3 条** |

### 三个选项（只能选一个，R-A1 不许并行）

| 选项 | 内容 | 代价 / 风险 |
|---|---|---|
| **A** | 按原提案正名：**C6-P2 = 线性屈曲**，现在开工（加筋板轴压 + 柱壳外压，λ_cr 先测后定） | 从 0 建 `*BUCKLE` 双码输出解析、载荷工况设计、λ 阈值实测；工作量约等于 P1 全链。**触发条件：老王近期有轴压校核需求** |
| **B（建议）** | 先做「模态扩卷（柱壳/加筋板）+ 自主建模题」，**正名为 C6-P1b**；屈曲保留为 C6-P2 | 补上 P1 两个最大诚实边界（只有翼盒一族、L1 是转写题不是自主建模），技术复用最厚；代价：屈曲后移；新族 f1 双码阈值必须重测（P1 的 1% 只在翼盒测过），SYS 需追加模态词汇段（新 prompt sha，R53） |
| **C** | A + B 并行 | 违反 R-A1 单变量；判分器与 prompt 同时改 ⇒ 归因失败。**不推荐** |

### 建议与判据定义域（N-36 教训）

**建议 B**：P1 收口报告 §7 已写明两个诚实边界——「L1 是转写题不是自主建模」「只有翼盒一族」；
P1b 正好补这两个洞，且 frequency 分支通用性已实测（证据 6）。
屈曲是**另一条物理链路**（载荷相关特征值），不该与「题型升级」混在一个任务里。

新题型进卷前必须写清定义域：①自主建模题的模态规则写在 SYS 追加段 ⇒ 测的是**规则应用、非自主发现**（C-042 同款边界）；
②柱壳 spec 的 `extra.end_shear/end_moment/shear_axis/moment_axis` 在模态步被忽略但仍在 spec_fidelity 全键比对内 ⇒
先声明「载荷键是否属于被考内容」，否则重演 N-36「零影响的真因是没有这种题」；
③新族 f1 阈值**先测后定**，不得沿用翼盒 1%；④dev 两条加筋板不进新卷。

### 待拍板后统一更正的落盘位置（现在不动）

`FEM-Bench-Aero/REPORT_C6_P1_MODAL.md` §10、`FEM-Bench-Aero/DATA.md` §7.7、
`FEM-Bench-Aero/ROADMAP.md` C6 行、`.workbuddy/memory/MEMORY.md` 当前状态段、
`.workbuddy/memory/2026-11-07.md` 十二节 —— 五处「C6-P2 扩卷」字样按拍板结果正名。
