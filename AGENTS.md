# AGENTS.md — FEM-Bench-Aero 执行规约（所有执行 Agent 必读）

> **适用对象**：任何基于复评文档、专家意见、任务计划在本仓库执行任务的 Agent / LLM / 会话。
> **性质**：这是**执行协议**，不是项目数字。项目的数字以 live 文件为准；本文件只规定“怎么改、怎么验、什么时候停”。
> **优先级**：用户当前指令 > 本文件 > 复评文档/计划 > Agent 自己的推断。冲突时停下来问，不要自行取舍。

---

## 0. 开工前：读一页 SOT + 跑两道闸（不再整读五文件）

> **2026-11-09 专家审查结论**：§0 原先要求的五文件（CLAIMS 142 KB + RUBRIC 157 KB +
> INDEX 68 KB + 成绩单 68 KB + 考卷 289 KB）合计约 **24.5 万 tokens，已超过 200k 上下文**
> ——每个会话开工前就接近上限，必然压缩/重读/漂移。**这是 token 飞涨的根因，不是模型的问题。**

**开工三件事（替代原来的五文件整读）：**

| # | 做什么 | 你要从中确认什么 |
|---|---|---|
| 1 | 读 `FEM-Bench-Aero/SOT.md`（机器生成一页，≈3 KB） | 唯一 headline + 数字 / 当前卷 path+sha+条数 / prompt sha / rubric 版本 / 两道闸状态 / 下一步 1 条 |
| 2 | `"$PY" negative_controls.py --brief` | 一行结论：N/N + all_ok |
| 3 | `"$PY" check_claims.py --brief` | 一行结论：claims/artifacts + all_ok |

- **`SOT.md` 由 `python sot.py` 生成，禁止手改**；它过期时 `python sot.py --check` 会红。
- 需要细节时**按 SOT 里的指针读单个 artifact**；**禁止整读 CLAIMS.md / RUBRIC.md / tasks*.jsonl**
  （CLAIMS 48k + RUBRIC 53k + 卷 98k tokens，一次整读就把预算烧光）。
- 数字一律以 artifact 实读为准（R63）；SOT 只是指针与摘要，不产出新数字。

**读取/写入预算（写进每个任务的 TASK_CONTRACT）：**

```markdown
- 读取 ≤30k tokens：SOT.md + 本任务直接相关的 1 个 artifact；禁止整读 CLAIMS/RUBRIC/tasks*.jsonl。
- 写入 ≤10k tokens：每任务最多 1 条 claim + 1 个 artifact + 1 段记忆（≤2KB）。
- 闸：开工跑 --brief；只在收口跑全量 negative_controls + check_claims。
- 停止条件：超出预算、或发现新方向 → 写 CONFLICT，不继续挖。
```

**前置检查命令（venv 路径；换机请改这一行）：**

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
# 两道闸都用项目 venv（本机路径；换机请改这一行 —— 只有 check_claims 能用系统 python，负控不行）
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
"$PY" negative_controls.py      # 必须全绿；条数以本次输出为准（R63）—— **必须先跑**（R59）
"$PY" check_claims.py --json "$TEMP/check_claims_preflight.json"   # 必须 all_ok=True；条数以本次输出为准（R63）
git status --short              # 先看清工作区；有别人未提交的改动时不要覆盖
"$PY" check_commit.py --audit   # 工作区必须干净（除白名单）；rc=0 才开工
```

> **⚠ 为什么命令块里写成 `"$PY"` 而不是 `python`**（T-A12a）：旧版这里写裸 `python`，紧跟的下一条 ⚠ 又说「负控必须用 venv」—— **同一节自相矛盾**，而 CLAUDE.md 只是照抄了它的命令块。任何一个 Agent 按字面执行都会在负控上 `ModuleNotFoundError: numpy`，然后把它记成环境/数据失败（R16 红线）。**修的是根，不是抄本。**

> **⚠ 提交闸（D5）：`check_commit.py` + pre-commit hook**
> 本仓库已装 `.git/hooks/pre-commit`，`git commit` 时会自动跑 `check_commit.py`。它守的判据是**「暂存区 == 工作区全部非白名单改动」**——堵的是 T-C1 那次「只 `add` 了新增文件、12 个改动全漏在工作区」的事故（当时 `git status` 是绿的、所有门禁也是绿的，因为门禁跑的是**工作区**，不是**提交**）。
> **★ hook 不入库**（`.git/` 不被追踪）⇒ **新 clone / 换机后必须跑一次 `"$PY" check_commit.py --install-hook`，否则这道闸等于不存在。**
> **这件事现在有闸守（D5b / R74）**：`check_claims.py` 的 **S-61** 会在每次 §0 自检里查「生效 hooks 目录下有没有 pre-commit、内容是不是 `check_commit.py`、它指向的脚本是不是**当前**这一份、有没有被 `core.hooksPath` 改道」—— 任一条不成立就红，**不再依赖「人记得装」**。判据本身在 `hook_guard.py`，可用 `"$PY" hook_guard.py --self-test` 单独验它自己会不会红。CI 或第三方只跑复现时可用 `check_claims.py --skip-hook-guard` 显式跳过（会标 `skip` 而非通过，按 R69 须在当次报告写明原因，且不得进入对外数字）。
> 白名单是例外，规则写在 `feagpt_repro/commit_allowlist.json` 自己身上（每条必须带 `reason`；文件一旦入库、或磁盘上已消失，闸即判红强制清理；名单内文件不得进入任何对外数字）。
> `--no-verify` 能绕过，但**等于主动放弃这条闸**，只在确认「就是要提交半截」时才用，并须在报告里写明原因。

> **⚠ 公开分发集：`check_claims.py --public`（T-F3 / R75）**
> 公开快照里，五类判据的**对象按拍板不存在**（本机外部归档的 `SHA256SUMS.txt`、被渲染层脱敏的 `PY=`、移出的 `AGENTS.md`/`CLAUDE.md`、不分发的 `.git/hooks`、以及因协议文件不齐而失去对象的版本判据），所以它们判红**不代表代码错**。加 `--public` 后这些项标 `exempt` + 原因、**不计入通过数**，在输出里单列。
> **它是放宽，所以边界写死（R75）**：① 只在显式加参数时生效，**绝不自动**（不得写成「文件不存在就跳过」——那会让删文件成为逃避手段）；② 只对「失败原因确实是公开集造成」生效：协议文件**存在且**写死计数、`PY=` 是裸 `python`、非目标 claim 的 artifact 缺失，**仍判红**；③ 豁免项不得进入任何对外数字，也不得说成「全绿」。
> **用法前提**：加了 `--public` 之后**仍然红的项才是要处理的**（例如缺 `node_modules` ⇒ 先按 `QUICKSTART.md` 装依赖）。**它不是一个「让自检变绿」的开关。**
> 判据本体在 `check_claims.py`；边界自检 `"$PY" _f3_public_exempt_selftest.py`（六向，含三向「本该红」）。

> **⚠ 提交前必须过一遍行尾规范化（T-D3 / D-3）**
> 仓库用 `.gitattributes` 统一 CRLF（`*.sh`/`*.cmd` 之外），因为 **blob 里只有 LF 一套**、`autocrlf` 在 checkout 转 CRLF，
> 而新写出来的文件默认是 LF（Write 工具、不走 git 的脚本产物）——不处理就会重新制造「本机 LF / clone CRLF」的漂移面，
> 也就是 D-3 里 61.6% 锚点断裂的成因。提交前跑：
> `"$PY" _d3_normalize_eol.py`（dry-run，看「待处理」是否为 0）→ 需要时加 `--apply`（幂等，只动行尾）。
> **扫描源已含未追踪文件**（`--cached --others --exclude-standard`），所以新文件**不必先 `add` 也能被看见**，且它会逐个点名待处理文件。这条是补出来的：旧版只扫 `git ls-files`（已追踪）⇒ 每个新文件都漏一次，且**漏得毫无征兆** —— 工具自己复验报「待处理 0」、`git status --porcelain` 也干净（`text=auto` 归一后工作区与索引无差异）⇒ 两条检查都说没事，只有跨仓库 clone 才看得见。
> **本机自查证明不了换机**：唯一硬证据是干净 clone 后 `"$PY" _b1_eol_scan.py <clone>` 报「不同数 = 0」。
> 工作区正常态 = `git ls-files --eol` 里 `w/lf` 只剩两个 `*.sh`。

> **⚠ dataset / 求解类脚本必须用项目 venv**（R60）：`verify_dataset` / `check_forms` / `score_baseline` / `msr_l3` / `eval_dataset` / `dedup_dataset` / `run_pipeline` 一律用 `…/envs/default/Scripts/python.exe`；**系统 python 缺 numpy/gmsh**，报 `ModuleNotFoundError` 是**环境问题、不得记成数据失败**（R16）。
>
> **⚠ `check_claims.py` 是唯一能用系统 python 的脚本**（纯文本/JSON 解析）；其余一律 venv。旧版这条写的是「两道文本闸可用系统 python」，已被 T-A10 实测证伪。

> **⚠ 绝不并行跑 ccx/abaqus（R61）**：`feagpt/solver.py` 的 `run()` 已加**全局求解锁** `feagpt_repro/.solve.lock`——第二个求解会直接抛错而不是静默空转（并行时返回码仍可能是 0，结果却是空的）。锁超过 1 h 视为崩溃残留，自动接管并警告。**手工跑 bat / 外部 abaqus 时也要确认没有别的求解在跑。**

> **⚠ 收口顺序固定（R59）**：`negative_controls.py` → `check_claims.py`，**不许反**。反了官方 JSON 里记录的 artifact `mtime` 会与实际值不一致（内容/sha 都对、只有元数据过期），由 **S-45** 判红。**S-45 检查的是「磁盘上现有」的官方 JSON**：若上一次 artifact 是旧序写的，本次 `check_claims` 会先判红、写完即修复 ⇒ **再跑一次 `check_claims` 即绿，收口必须跑到 S-45 绿为止**。

> **⚠ pre-flight 必须写临时 JSON**：`--json "$TEMP/check_claims_preflight.json"`。官方 `reports/check_claims.json` 记录了每个 artifact 的 `mtime`，pre-flight 直接写它 ⇒ **每开一个任务工作区就先多一个 diff**（sha256 不变），与 C5「`git diff` 只含 allowlist」字面冲突。**官方 JSON 只在任务收口时写一次**，且顺序必须是 **先 `negative_controls.py` → 后 `check_claims.py`**（负控会重写自己的 json，反序会让官方 JSON 记到过期的 mtime）。

> **硬规则**：以上任一命令不全绿、或你无法说出“当前 headline / 当前 paper sha / 当前 prompt sha / 当前分母”，**停止，不要开始任务**。先修 SOT（source of truth），再谈执行。

---

## 1. 十二条执行规则

### R-A1　一个任务只改一个变量
一个任务只能改以下**一个**维度：
`paper` / `prompt` / `rubric` / `candidates(model)` / `denominator` / `headline`。

- 两个以上必须改 ⇒ 拆成两个任务，中间加 **bridge**（单变量对比表）。
- 禁止“顺手把题面、prompt、判分一起修”——这是历史上所有归因失败的源头。
- 如果任务描述里出现“同时/顺便/一起”，先停下来拆任务。

### R-A2　先冻结，后运行
- 运行前记录：paper sha256、prompt sha256、rubric 版本、schema sha、候选目录、model id。
- 运行后**不得静默修改**上述任何一项。
- 看完结果再改 rubric/prompt/paper = **post-hoc**：必须新开版本号、写 `post-hoc` 声明、做 bridge，并在 claim 里标注；否则结果作废。
- 禁止“改完再跑一遍，只报新数”。

### R-A3　官方数字必须有 artifact
- CLAIMS / README / RUBRIC / INDEX 里的每个数字，必须指向 **git 追踪的 `feagpt_repro/reports/` 文件**，并附一条可复现命令。
- **禁止引用 `eval_runs/`**（被 gitignore，重跑即覆盖）。
- **禁止手抄数字**；禁止“我跑过，结果大概是……”。
- 诊断结果放 `reports/diagnostics/`，文件名带 `diagnostic`/版本；不得占用官方路径。

### R-A4　语义自检，不是结构自检
- 每次改 claim/README/RUBRIC/INDEX，必须跑 `python check_claims.py --semantic`。
- “文件存在、被 git 追踪”**不算通过**；数字必须与 artifact 实读一致。
- 数字不一致时：**先改 artifact（或确认 artifact 错），再改文本**；禁止反过来把 claim 改成“看起来对”的数。
- 计数类文本（行数、条数、负控数、exam 数、族分布）必须从 artifact 重新计算，不得沿用上一版。

### R-A5　分母必须显式、闭合
- 任何比率必须写清：`分子/分母`、分母怎么来的、排除了什么、为什么排除。
- 禁止 `if 字段存在` 这类隐式过滤；编造/答非所问/无输出**记 0，不得排除**。
- MSR 分母必须两层表述：
  - 层A（准入）：`n_counted + n_clarify_excluded + n_unresolved_excluded + n_notrun + n_env + n_unknown = n_tasks_total`
  - 层B（原始分母内部）：`n_counted = n_solver_excluded + n_counted_excl_solver`
  **solver 在原始分母内（对模型是失败），只在「剔除 solver 口径」里拿掉；不得与层A 的排除项相加。**
- 字段级命中率的分母：`fabricated` / 答非所问 / 无输出 **记 0，不排除**（R47/S-33）；不要把 MSR 的准入排除套到字段级。
- 分母不闭合 ⇒ 任务未完成；不要写“约等于/基本一致”。

### R-A6　不跨版本直减
以下任一不同 ⇒ **禁止**写“提升/下降/回收 X pp”：
- paper sha 不同
- prompt sha 不同
- model 不同
- 分母不同（含 clarify/unresolved/solver 排除不同）
- 候选集不同

只能同条件相减；单变量变化只允许用 **bridge 表**逐格相减，并写明“这是唯一允许相减的场景”。`compare_scorecards.py` 返回 `rc=3` 时，不得绕过。

### R-A7　当前 headline 唯一
- 恰好一条 active claim 在**状态列**（`check_claims.py` 的 S-29 所判字段）带「（对外 headline）」；当前是 **C-032**。**正文里提及这串字不算**（历史 claim 会用「不再是对外 headline」「headline 见 C-032」这类否定/引用句式，字面 grep 会命中多条）。
- 旧 headline 必须标 `historical` / `diagnostic` / `superseded`；第二模型必须标 `supporting`，不得自称 headline。
- 新增 headline 前先跑 `check_claims.py` 的 S-29；两条 headline = 失败。
- 不得用“也可以算 headline”“并列第一”绕过。

### R-A8　模型与 prompt 必须可追溯
- 成绩单必须记录：`model`、`prompt_sha`、`tasks_sha256`、`candidates_dir`、`n_candidates`。
- 顶层 `model` 必须等于 `provenance.model`；不得用默认值（历史 bug：C-031 顶层写成 glm）。
- 跨模型对比必须同 paper sha、同 prompt sha、同 `--max-turns`；否则只能标 diagnostic。
- 模型 id 必须来自 SDK 实测可用列表，不得猜。

### R-A9　负控先绿，且要报总数 + 编号
- 任何基线/重打分前：`check_claims.py` + `negative_controls.py` 必须全绿。
- 报告必须写“总数 + 编号集合”，**且总数与编号以最新 `negative_controls_<N>.json` 实读为准、不写死在文档里**（R63），只写“全绿”不算。
- 缺一条负控 = 失败，不是 skip；不得为了跑通而弱化/跳过负控。
- 负控文件版本化（`negative_controls_<N>.json`，N = 实读条数）；根目录**只留最新一份**，旧版本归档 `reports/archive/`，不得混用。

### R-A10　范围锁
- 只改 `TASK_CONTRACT` 的 allowlist 内文件；**默认不改** paper / rubric / prompt / headline / 其他模型 / 其他报告。
- 禁止“顺便修一下文档/代码”；发现范围外问题，写进报告的“follow-up”，不要动手。
- 禁止无备份删除文件；禁止 `git reset --hard` / `git checkout --` / `git clean -f` 在未确认 `git status` 时使用。
- 工作区有别人未提交的改动时，先停下来问；不要覆盖。

### R-A11　失败即停，不要“修复到绿”
出现以下任一情况，**停止并报告**，不要自行选择修哪边：
- 数字与 artifact 不一致
- 分母不闭合
- `model` / `prompt_sha` / `tasks_sha256` 对不上
- 负控/语义检查失败
- 发现两个 headline
- 发现旧候选被用在新 paper 上

报告必须给 **3 个选项**（修 artifact / 修文本 / 标 diagnostic）+ 证据 + 建议，由用户拍板；不得静默改 claim 或 artifact。

### R-A12　交付模板：没有报告 = 没做完
每个任务结束必须交固定报告：
1. 任务 id + 单变量
2. SOT（改前/改后）：headline、paper sha、prompt sha、rubric 版本、model
3. 改了哪些文件（allowlist 对照）
4. 跑了哪些命令 + 实际输出（含计数）
5. 通过/失败项（逐项，不得只写“全绿”）
6. 已知问题 / 未验证项
7. 下一步（一个，不要列五个）

---

## 2. 六条应对措施

### C1　先填 `TASK_CONTRACT`，再动手
没有合同不开工；合同模板见 §3。Agent 必须先复述合同（“我将只改 X，验收是 Y，停止条件是 Z”），用户/verifier 确认后再执行。

### C2　写/验分离
- 一个 Agent 写，另一个 Agent **只读验收**；写的人不能自己宣布通过。
- 验收 Agent 只跑 §0 的命令 + §4 清单 + `git diff`，不改文件。
- 没有第二个 Agent 时，至少让用户按 §4 清单手工核一遍。

### C3　5 分钟 pre-flight
开工前固定跑：`git status` → `check_claims --json "$TEMP/…"`（**只看，不写官方**）→ `negative_controls` →（如涉及跨版本）`compare_scorecards` →（如涉及考卷）`r32_audit --scope exam`。**收口时顺序相反：负控 → check_claims**（R59；S-45 会把反序判红）。
任一失败：先修 SOT，不要开始任务。

### C4　冻结清单（sha manifest）
在 `TASK_CONTRACT` 里写死：
- paper sha256
- prompt sha256
- rubric 版本
- schema sha256
- 候选目录 + model id
- 运行后回读 sha；不一致 ⇒ 本次结果作废，不得进 claim。

### C5　diff allowlist
提交前必须看 `git status --short` 和 `git diff --stat`：
- allowlist 之外的文件出现 ⇒ 停下，解释或回退。
- 不 review 就 `git add -A` = 红线。
- 不提交与任务无关的格式化/重命名/删除。

### C6　可回滚
- 任务前先提交当前 SOT（或至少 `git stash -u`）。
- 任务失败：回滚**任务提交**，不要 `reset --hard` 整条分支。
- 禁止 `--no-verify`；hook 失败先查原因。

---

## 3. `TASK_CONTRACT` 模板（复制到任务开头）

```markdown
# TASK_CONTRACT
- task_id:
- agent / date:
- SOT read: CLAIMS.md / RUBRIC.md / reports/INDEX.md / scorecard:
- 当前 headline（唯一）:
- 当前 paper path + sha256:
- 当前 prompt path + sha256:
- 当前 rubric 版本:
- 当前 model / scorecard:
- 单变量（paper|prompt|rubric|candidates|denominator|headline）:
- 为什么只有这一个变量:
- allowlist（精确到文件/目录）:
- 默认不改: paper / rubric / prompt / headline / 其他模型 / 其他报告
- 验收命令 + 期望输出:
- 停止条件:
- post-hoc?（yes/no；yes 必须新版本 + bridge + 标注）:
- 交付报告路径:
```

---

## 4. 开工前 10 项清单（Agent 自检；verifier 复核）

- [ ] 我读完了 CLAIMS / RUBRIC / INDEX / 当前成绩单
- [ ] 我能说出当前唯一 headline、paper sha、prompt sha
- [ ] 这个任务只改一个变量
- [ ] allowlist 明确；没有范围外文件
- [ ] 分母构成明确（counted/excluded 各自是什么）
- [ ] model / prompt / tasks 的 provenance 明确
- [ ] 开工前 `check_claims` 与 `negative_controls` 已全绿
- [ ] 我知道验收命令和期望输出
- [ ] 我知道停止条件，且不会“修复到绿”
- [ ] 我会交 §1 R-A12 的固定报告

---

## 5. 红灯清单（出现任一，立即停）

- “全部通过”但不给总数/编号
- 一个任务改了多个变量
- 把 claim 改成匹配某个数，而不是先核对 artifact
- 在官方 claim 里引用 `eval_runs/`
- 用旧候选评新 paper
- 看完结果再改 rubric/prompt/paper，且没有 post-hoc 标注/bridge
- 成绩单 `model` 与 `provenance.model` 不一致
- 无 `git status` 就 `reset --hard` / 删除文件
- 说“测试通过”但没跑命令
- 弱化/跳过负控
- 出现第二个 headline
- 比率没有分母
- 用默认 model 而不是实测 model id
- 跑完后改了 paper/prompt 但没有新 sha/bridge
- “差异很小，忽略不计”——不，分母/模型/paper 不同就是不同条件

---

## 6. 发现冲突时的处理（`CONFLICT.md`）

不要改任何文件，先写一页：

```markdown
# CONFLICT
- 冲突点:
- SOT 文件 / 行:
- 期望值:
- 实际值:
- 证据（artifact / 命令输出）:
- 3 个选项:
  A. 修 artifact（说明为什么 artifact 错）
  B. 修文本（说明为什么文本错）
  C. 标 diagnostic（说明为什么不能判）
- 建议 + 风险:
```

交给用户拍板；Agent 只执行被选中的选项，并在交付报告里记录决策。

---

## 7. SOT 去哪读（本文件**不存**任何会漂的值 —— R63 / S-56）

> 旧版本这里是一张「当前值」快照表（headline 路径、paper sha、prompt sha、rubric 版本、下一步）。
> **那张表本身就是漂移源**：到 2026-10-30 时它还写着**早已过期的 rubric 版本**、下一步还写着「v7 paper → v7 candidates」，
> 而这两件事都已做完（C-037 冻结、C-040 跑完）。R63 的结论是「不产生副本」，所以本节改成**读法指引**。

| 你要确认的 | 读哪里 | 谁在守 |
|---|---|---|
| 当前唯一 **headline** | `FEM-Bench-Aero/CLAIMS.md`：状态列带「（对外 headline）」的那条 | **S-29**（恰好一条） |
| **rubric 版本 / 规则范围** | `RUBRIC.md` **顶部版本行** + 红线判定表 | **S-56**（协议里出现版本号或规则范围即红） |
| **考卷 / prompt 及其 sha** | `feagpt_repro/reports/INDEX.md` + `reports/papers/` | **S-52**（冻结件不得漂移） |
| **headline 数字 / 分母构成** | INDEX 指向的那份 `reports/baseline_scorecard_*.json` | **S-19 / S-20 / S-54** |
| **下一步该干什么** | `feagpt_repro/reports/INDEX.md` 导航表 + `CONFLICT.md` 未决项 + 最新一轮复评文档 | 本文件**不写** |

> **这张表也不是答案，只是索引**：任何一项都必须回原文件实读才能引用。§0 的 2 个命令会把不一致变成红灯。

---

## 8. 怎么用这份文件

1. 把 `AGENTS.md` 放在仓库根目录；`CLAUDE.md` 只写一行“遵守 AGENTS.md”。
2. 给任何 Agent 的任务开头写：
   > “先读 `AGENTS.md`，填 §3 的 `TASK_CONTRACT`，复述单变量/验收/停止条件；我确认后再动手。”
3. 验收时用 §4 清单 + §5 红灯 + `git diff`；不要只看 Agent 的总结。
4. 发现偏差：让 Agent 写 `CONFLICT.md`，不要让它“边做边修”。

---

> **一句话**：**先读 SOT，再签合同；一个任务一个变量；数字必须有 artifact；分母必须闭合；失败就停，不要修到绿。**
