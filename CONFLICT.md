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
| **T-A8**（N-9：`external_numbers.md` 后 5 行仍读 `*_d36` 死快照） | ⏸ **待开工**（变量 = 对外数字表的数据源；需为关 1/关 4/自洽各出 v1.1 活 artifact） |
| **T-A9**（N-10：C-003 三计数无闸 → S-48 + NC-53） | ⏸ **待拍板**（推荐 A：断言 CLAIMS C-003 的三个整数 == artifact 的 `evidence_levels`；负控三向） |
| **考卷 v7**（接 v1.1 的 9 条进任务层） | ⏸ 未开工；按 R-A1 拆两步 + bridge，且 C-032 的 23/25 将不可比（R-A6） |

> 本轮起按 N-5 的 **C+**：pre-flight 走 `--json "$TEMP/check_claims_preflight.json"`，官方 `reports/check_claims.json` 只在收口写一次（先负控后 check_claims）。
