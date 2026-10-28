# AGENTS.md — FEM-Bench-Aero 执行规约（所有执行 Agent 必读）

> **适用对象**：任何基于复评文档、专家意见、任务计划在本仓库执行任务的 Agent / LLM / 会话。
> **性质**：这是**执行协议**，不是项目数字。项目的数字以 live 文件为准；本文件只规定“怎么改、怎么验、什么时候停”。
> **优先级**：用户当前指令 > 本文件 > 复评文档/计划 > Agent 自己的推断。冲突时停下来问，不要自行取舍。

---

## 0. 开工前必须先读的 5 个文件 + 2 个命令

| # | 文件 | 你要从中确认什么 |
|---|---|---|
| 1 | `FEM-Bench-Aero/CLAIMS.md` | 当前唯一 **headline** 是哪条 claim；哪些是 supporting / historical / diagnostic |
| 2 | `FEM-Bench-Aero/RUBRIC.md` | 当前 rubric 版本；**R42–R64 红线判定表** + 分母/判分口径（**R1–R41 不在此文件**，见 `CLAIMS.md` 的「红线条（R1–R64，挂账常设）」） |
| 3 | `feagpt_repro/reports/INDEX.md` | 官方 artifact vs 诊断；当前成绩单路径；当前考卷 sha |
| 4 | 当前成绩单（INDEX 指向的那份 `reports/baseline_scorecard_*.json`） | `model` / `prompt_sha` / `tasks_sha256` / 分母构成 / headline 数字 |
| 5 | 当前考卷 + prompt | `reports/papers/tasks_v6c.jsonl` 的 sha；`gen_candidates_v2.js` 的 prompt sha |

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
python check_claims.py --json "$TEMP/check_claims_preflight.json"   # 必须 all_ok=True；条数以本次输出为准（R63：不写死，写死必漂）
python negative_controls.py     # 必须全绿；条数以本次输出为准（R63）
git status --short              # 先看清工作区；有别人未提交的改动时不要覆盖
```

> **⚠ dataset / 求解类脚本必须用项目 venv**（R60）：`verify_dataset` / `check_forms` / `score_baseline` / `msr_l3` / `eval_dataset` / `dedup_dataset` / `run_pipeline` 一律用 `…/envs/default/Scripts/python.exe`；**系统 python 缺 numpy/gmsh**，报 `ModuleNotFoundError` 是**环境问题、不得记成数据失败**（R16）。
>
> **⚠ `negative_controls.py` 也必须用 venv**（T-A10 实测：系统 python 直接 `ModuleNotFoundError: numpy`）：NC-52 会真的跑一次求解冒烟，链路 import 到 `feagpt.geometry`。**只有 `check_claims.py` 可以用系统 python**（纯文本/JSON 解析）。旧版这句写的是「两道文本闸可用系统 python」，已证伪。

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

## 7. 当前 SOT 快照（2026-10-28，仅供定位；以 live 文件为准）

| 项 | 当前值 |
|---|---|
| 唯一 headline | **C-032**（`reports/baseline_scorecard_L3_v6c_p2.json`，glm-5.3-flash，prompt v2） |
| supporting | **C-033**（`reports/baseline_scorecard_L3_v6c_ds_p2.json`，deepseek-v4-pro） |
| 历史 | C-029/C-031（prompt v1）、C-028（v6b）、C-021（v4） |
| W5d 产物 | C-034 `reports/w5d_leaderboard.{json,md}`；C-035 prompt v3/v3b 消融否决、回退 v2 |
| 当前 paper | `reports/papers/tasks_v6c.jsonl`，sha `9c1faa3a…` |
| 当前 prompt | `gen_candidates_v2.js`，sha `ce225186…` |
| 当前 rubric | v5.6（**R42–R64 判定表在 RUBRIC**；**R1–R41 在 `CLAIMS.md` 红线条**） |
| 门禁 | 负控全绿、`check_claims` 全过 —— **条数以 §0 实读为准**（R63：本表不写死计数） |
| 已知 P2 | C-032 dev 22/30 已由 W5d-0 定位（`reports/diagnostics/dev_reversal_v6c_p2.md`，+1/−2）；C-033 1 编造 + 1 问错（W5d-1 prompt v3/v3b 消融否决，回退 v2，C-035）；C-033 字段级 +5.0pp BELOW |
| 下一步 | ① **T-A10 已完成**（S-49/S-50/S-51 + C-036 + NC-54 + RUBRIC v5.6）；② **v7 paper**（9 条 v1.1 案例接进任务层，exam 25→34）→ **v7 candidates**（两模型重生成 + MSR + CI/榜单）→ C-032/C-033 转 historical |

> **不要相信这张表本身**：每次开工前用 §0 的 5 个文件 + 2 个命令重新确认；表只是“你可能在哪”的路标。

---

## 8. 怎么用这份文件

1. 把 `AGENTS.md` 放在仓库根目录；`CLAUDE.md` 只写一行“遵守 AGENTS.md”。
2. 给任何 Agent 的任务开头写：
   > “先读 `AGENTS.md`，填 §3 的 `TASK_CONTRACT`，复述单变量/验收/停止条件；我确认后再动手。”
3. 验收时用 §4 清单 + §5 红灯 + `git diff`；不要只看 Agent 的总结。
4. 发现偏差：让 Agent 写 `CONFLICT.md`，不要让它“边做边修”。

---

> **一句话**：**先读 SOT，再签合同；一个任务一个变量；数字必须有 artifact；分母必须闭合；失败就停，不要修到绿。**
