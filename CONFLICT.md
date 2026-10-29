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
