# T-B1 验收报告：第三方可用性（clone + fetch_data 能否复现 headline C-032）

> 任务：以第三方视角走通「clone → 取数据 → 复现 headline」。
> 合同：`task_b1_contract.md`。单变量：**无**（只读验收，不改判据/artifact/分母/卷）。
> 开工门禁实况：负控 **68/68**、`check_claims` **33 claims / 68 artifacts / 60 语义项 全过**。

---

## 0. 结论先说

**分三层，三层结论不同：**

| 层 | 结论 | 依据 |
|---|---|---|
| **代码 + 候选层（TSR/SFR）** | ✅ **真可复现** | 在真 clone + 独立 venv（**零第三方包**）里跑出 exam **23/25 (92.0%)**、SFR **20/22 (90.9%)**，与 C-032 **共同叶子改动 0** |
| **数据层（fetch_data）** | ⚠️ **技术上可用，分发上不可用** | `fetch_data.py` 本身跑通（SHA256 + 条数核对有效），但归档包**没有任何公开获取渠道**，用法示例是**作者本机绝对路径** |
| **字节层（sha256 锚点）** | ❌ **不成立** | 干净 clone 后 **931/1511（61.6%）** 入库文件 sha256 改变；`check_claims` 在 clone 里**红 6 项** |

**一句话**：这个 benchmark 目前**只能在本机复现，别人拿不到、也无法逐字节复现**。这不是「代码写错了」，是**分发与仓库卫生**没做。数字本身是干净的。

---

## 1. 实测能走通的部分

### 1.1 TSR / SFR：真独立环境下逐字段一致

| 项 | 实测 |
|---|---|
| 环境 | `mktemp -d` → `git clone` → `python -m venv`（**不装任何包**，仅标准库） |
| 数据 | `fetch_data.py --src <tar.gz>` → 解出 `modeling/` 55 条，SHA256 与条数核对通过 |
| 命令 | C-032 命令列第 2 条（`score_baseline.py`）原样执行 |
| 结果 | `EXAM TSR 23/25 (92.0%)`、`SFR 20/22 (90.9%)`、`DEV 22/30 (73.3%)`、`SFR 21/29` |
| 与官方 artifact 比对 | **共同叶子改动 0**（1559 / 1064 叶子，新增 150、删除 645 全是 `msr` 与 `provenance.judge_overrides` 相关，**无一处数字不同**） |

> **这一条很重要**：判分器**不依赖 gmsh / numpy / ccx**，只用标准库就能算出 headline 的 TSR 与 SFR。第三方装 Python 就能验。

### 1.2 候选已入库，不必重跑 LLM

| 候选目录 | 入库文件 | 说明 |
|---|---|---|
| `candidates_l3_v6c_glm_p2`（C-032 用的就是这个） | 55 | 重打分即可，**不需要 API key** |
| `candidates_l3_v6c` | 55 | 同上 |
| `candidates_l2_v7_glm` / `_ds` | 64 / 64 | L2 层同样可重打分 |
| `candidates_l3_v7_glm` / `_ds` | 65 / 64 | v7 层同上 |

**这是可复现性的关键前提**，而且已满足：C-032 命令列的第 1 条（`node gen_candidates_v2.js`，要 LLM）**可以跳过**，从第 2 条起重跑就能得到同样的 23/25。

### 1.3 fetch_data 的两道核对是有效的

```
[OK] SHA256 校验通过: 8cec47ce65486d00…
modeling 目录条数: 55（manifest 期望 55）
[OK] 数据集本体就绪：…/modeling（55 条）—— evaluate.py 可用
```

### 1.4 缺数据时的报错信息**是对的**（虽然退出码错）

```
[dataset] 缺少金标准数据集：[.../FEM-Bench-Aero/modeling]（git 里没有数据集本体）。
先跑 `python fetch_data.py --src <FEM-Bench-Aero-v1.0-data.tar.gz>` 解包后再评测；
否则所有候选都会被判 spec_fail，看起来像模型全错（W5a' 已加此闸防静默空转）。
```

文字指引准确、指明了后果、指对了下一步。**这条设计是好的**（W5a′ 的意图完全达到）。

### 1.5 MSR 路径技术上跑得通（单条实证）

用「项目 venv（含 gmsh/numpy）+ `FEAGPT_CCX` 指向本机 ccx」在 clone 目录跑单条：

```
[ok] L3_open_hole_panel_400x200_d40: gates={'mesh_quality': True, 'semantics': True,
     'fidelity_disp': True, 'spec_fidelity': True} fidelity=0.0% wall=6.9s
[msr_l3] 分母闭合 全卷: 55 = counted 1 + clarify 4 + unresolved 0 + notrun 50 …
```

⇒ MSR 不是「算不出来」，是「要装三件东西 + 跑 55 条」。

---

## 2. 阻断项（按严重度）

### ★★★ D-1 仓库没有 origin，第三方无法 clone

```
$ git remote -v
(空)
```

仓库从未推送到任何平台。**「clone」这一步第三方当前无法执行** —— 这是可用性的第一道门，且不是技术问题。

### ★★★ D-2 数据本体没有分发渠道

`feagpt_repro/fetch_data.py` 的用法示例：

```
python fetch_data.py --src F:/FEA_Archive_20261024/FEM-Bench-Aero-v1.0-data.tar.gz
```

- 这是**作者本机绝对路径**，且全仓无 URL / release / 对象存储地址。
- 归档 89.5 MB，不在 git（`modeling/` 入库文件数 = **0**）。
- README 的「拿数据本体」一行写的是 `--src <FEM-Bench-Aero-v1.0-data.tar.gz>`（尖括号占位），**没说从哪拿**。

⇒ 第三方即使 clone 成功，也会停在这里。**这是复现链的硬断点。**

### ★★★ D-3 行尾转换让 61.6% 的 sha256 锚点在换机后断裂

```
$ git config --get core.autocrlf
true
$ ls .gitattributes
No such file or directory

$ python _b1_eol_scan.py <clone>
入库文件总数 : 1511
两侧 sha 相同: 580
两侧 sha 不同: 931  <-- 换机后锚点会断
clone 缺失   : 0
按后缀分布   : {'.json': 636, '.py': 128, '.md': 54, '.log': 43, '.slide': 24,
                '.bat': 9, '.html': 7, '.inp': 6, '.jsonl': 5, '.step': 5, …}
```

**机理**：git 索引里全是 LF；`core.autocrlf=true` 在 checkout 时把 LF 转 CRLF。本仓工作区是**混合态**（部分文件历史由 Python/Write 写成 LF、部分工具写成 CRLF）⇒ 同一份代码，本机与 clone 的字节不同。

**后果**：整个项目的证据机制（R25/R26/R29 的 sha256 锚点、S-57 `paper_sha256`、S-59 修正表 sha、成绩单 `provenance.tasks_sha256`）**都建立在 sha256 上**。换成混合态后：
- 本机是 CRLF 的文件 → clone 后仍 CRLF → sha 一致（580 个）
- 本机是 LF 的文件 → clone 后变 CRLF → **sha 断裂（931 个）**

⇒ **同一套判据，换台机器后时红时绿，取决于该文件当初是用什么工具写的。** 这是 N-26「同名不同义」的字节版。

### ★★★ D-4 clone 后 `check_claims` 红 6 项（README 明确指引第三方跑这条）

README 的「查证据是否可复现」一行让人跑 `check_claims.py --semantic`。在干净 clone 里实测：

```
active claims 33 条 / artifact 68 个 / 语义项 60 条 -> 结构 0 项 + 语义 6 项失败
红线条 R26/R29：CLAIMS 自检未过，不得对外引用这些数字。
```

| 项 | 红的原因 | 根因归类 |
|---|---|---|
| S-39 / S-43 | `node --print-prompt-sha` **无输出** | **缺 `node_modules`**：`Error: Cannot find module 'ajv'` ⇒ 需 `npm install` |
| S-49 | `C-001: 条数=64 ≠ artifact 55`、`目录数=128 ≠ …` | **数据包 55 条 vs 文档声称 64 条**（D-5） |
| S-50 | `行「关 1 网格…」分母 64 既不是 spec 数 55` | 同上 |
| S-59 | `成绩单 v7 glm/ds 记的表 sha 与磁盘不一致（artifact 过期）` | **D-3 行尾** |

**注**：`npm install` 这条**不是项目缺陷** —— 已核查 `package.json` 两个依赖在公开 registry 都存在且版本命中：

```
registry.npmjs.org/@tencent-ai%2Fworkbuddy-cloud-sdk  -> 200；版本 0.1.4-dev.ca27990.202610161713 存在
registry.npmjs.org/ajv                                -> 200
```

⇒ 第三方跑 `npm install` 即可解。但**文档里没写这一步**（README 无任何 npm 指引）。

### ★★ D-5 数据包 55 条 vs 考卷 64 条（v7 无法复现）

- `fetch_data.py` 核对的是 `manifest['summary']['n_cases']` = **55**（数据包自带 manifest）。
- 仓库里的卷是 **v7 = 64 条**（`tasks/tasks.jsonl`，sha `caf0f6c3…`）。
- README 承认「v1.1 的 9 条内插案例尚未进数据包」，但**没有任何闸守这条交叉一致性**：`fetch_data` 只跟数据包自己的 manifest 对账，不会发现「你手上是 55，卷要 64」。

⇒ 第三方用当前数据包跑 v7 卷（C-037/C-040），**必然缺 9 条 gold**。而 S-49/S-50 在 clone 里报的正是这个症状。

### ★★ D-6 空 `modeling/` 目录能骗过前置闸，静默产出假成绩

> ✅ **已修（T-C1，R73 / NC-67，2026-10-30）**：`require_dataset(fea, expect_ids=None)` 改为三级
> （目录存在 → 有 `spec.json` → 覆盖任务卷），三处调用点传期望集。**同一实验重跑**：
> `mkdir modeling` 后 `rc=2`、报「金标准目录存在但里面没有任何 spec.json」、**不再产出任何成绩**。
> 只有 5 条时 `rc=2` 报「缺 51 条」并给样例。以下原文保留作为缺陷记录。

`require_dataset()` 只检查**目录是否存在**：

```python
need = [os.path.join(fea, 'modeling')]
missing = [p for p in need if not os.path.isdir(p)]
```

实测：在 clone 里 `mkdir modeling`（**空目录**）后重跑：

```
EXAM  TSR 3/25 (12.0%)  SFR 0/22 (0.0%)
分类(exam): {'clarify_ok': 3, 'spec_fail': 22}
```

**12.0% 这个数字看起来完全像一个合法成绩**（"模型很差"），而实际是"数据没到位"。没有任何警告。这正是该闸注释里说要防的「静默空转」—— 闸挡住了「目录完全不存在」，**挡不住「目录存在但内容不完整/为空」**。

与既有坑族同源：*「口径参数漏传 ⇒ 假 FAIL ⇒ 先怀疑参数再怀疑模型」*。这里是「数据没解全 ⇒ 假 FAIL」。

### ★★ D-7 环境类失败时退出码是 0（两处）

> 🚫 **本条已被 T-C1 实测证伪 —— 是我的测量错误，不是项目缺陷。**
> 当时用 `"$PY" xxx.py … 2>&1 | tail -3; echo "rc=$?"` 取退出码，**`$?` 拿到的是 `tail` 的**（永远 0）。
> 不用管道重测：`score_baseline.py` 缺数据 → **`rc=2`**；`sys.exit(main())` 三个脚本都有、一直是对的。
> 最小复现：`"$PY" -c "import sys; sys.exit(2)" 2>&1 | tail -3; echo $?` → 印 `0`；
> 同一句去掉管道 → 印 `2`。
> **教训**：`$?` 必须**紧跟在被测命令后面**，中间不能有任何命令（连 `echo "=== 标题 ==="` 都会吃掉它）；
> 同族错误在本轮又复发一次（分节 `echo` 夹在中间）。**判据自己得先证明对**。
> 以下原文保留，作为错误痕迹。

| 场景 | 输出 | 退出码 |
|---|---|---|
| 缺数据跑 `score_baseline.py` | `[dataset] 缺少金标准数据集…` | ~~**0**~~ **实测 2（原文错）** |
| 缺 gmsh 跑 `msr_l3.py` | `环境错误：缺少依赖 ['gmsh','numpy']…` | ~~**0**~~ 未复测（同族测法错误，结论不可信） |

两者都 `return 2`（源码里确实写了 `return 2`），但被 `main()` 的调用方吞掉。⇒ **CI / 批处理无法用退出码判断成败**，只能靠 grep 文本。这与项目自己「环境失败不得计为模型失败（R16）」的意图矛盾 —— 判据是对的，退出码没传出去。

### ★★ D-8 MSR 需要 CalculiX，而 `tools/` 整个目录未入库

```
$ git ls-files | grep -c '^tools/'
0
$ which ccx
（无）
```

- ccx 发现顺序：`$FEAGPT_CCX` → 向上 4 层找 `tools/calculix/**/ccx_static.exe` → PATH。
- 指引**存在**，但只在 `requirements.txt` 的**注释**里：`CalculiX is NOT a pip package: ccx must be on PATH, or dropped under tools/calculix/<version>/, or pointed at with FEAGPT_CCX.`
- **README 完全没提** ⇒ 第三方按 README 走，会在 MSR 这步撞墙，且不知道该撞的是什么。

### ★ C-032 的 headline artifact 缺 `provenance.judge_overrides`

官方 `baseline_scorecard_L3_v6c_p2.json` 的 provenance 键里**没有** `judge_overrides`；用当前代码重跑会**有**（T-P1a 新增）。

- **数字完全一致**（共同叶子改动 0）⇒ 不是数字错，是 **artifact 未随代码重生成**。
- 但严格来说：**任何人用当前代码重跑 C-032，都得不到与发布版逐字节相同的文件**。

### ★ 仓库卫生：工具侧记忆与内部评审文档入库

| 内容 | 入库数量 | 说明 |
|---|---|---|
| `.workbuddy/memory/*.md` | 20 | 工具侧工作记忆（个人工作日志），不是 benchmark 内容 |
| `.workbuddy/applications.yaml`、`.wbapp_*.genie` | 2 | 本机应用描述 |
| 根目录 `FEM-Bench-Aero第X轮复评与执行纠偏_*.md` | 十余份 | 内部评审留档 |
| 根目录 `_snap_dash_pre_d*.html`、`datasets_usage_guide.html` | 数份 | 过程快照 |

⇒ 第三方 clone 后会看到一堆与 benchmark 无关的内部文档，且这些也在 D-3 的 931 个 sha 断裂文件里（`.md` 54 个）。

---

## 3. 完整卡点序列（第三方按 README 走，会依次撞）

| 步 | 动作 | 结果 |
|---|---|---|
| 1 | `git clone <url>` | ❌ **无 origin**（D-1） |
| 2 | 读 README「从这里开始」 | ⚠️ 第一屏全是内部编号（C-032/R42/W5c），**没有「5 分钟上手」** |
| 3 | `fetch_data.py --src <tar.gz>` | ❌ **不知道 tar.gz 从哪来**（D-2） |
| 4 | （若已拿到）解包 | ✅ SHA256 + 条数核对通过；但只有 55 条（D-5） |
| 5 | `score_baseline.py`（TSR/SFR） | ✅ **23/25 (92.0%)** —— 但需先有 `modeling/` 目录，空目录会静默给 12.0%（D-6） |
| 6 | `msr_l3.py`（MSR） | ❌ 缺 gmsh/numpy → ❌ 缺 ccx（未入库）→ 才轮到跑 55 条求解（D-8） |
| 7 | `npm install`（prompt sha 相关闸需要） | ⚠️ 文档没写；但依赖公开可装（D-4） |
| 8 | `check_claims.py --semantic` | ❌ **红 6 项**（D-3/D-4/D-5） |

---

## 4. 修法建议（三档，按「投入 / 收益」排）

### 档 1：分发与文档（不改代码、不改数字）—— 收益最大

1. **建远端仓库**并推送（解 D-1）。
2. **给数据包一个可下载地址**（GitHub Release / 对象存储 / Zenodo DOI），并把 `fetch_data.py` 的用法示例从本机绝对路径改成 URL 示例（解 D-2）。
3. **README 顶部加「5 分钟上手」**：三条命令 + 三件外部依赖（Python / Node+`npm install` / CalculiX）+ 数据包下载页链接（解 D-3 的文档面、D-8）。
4. **README 明写 v1.1 的 9 条未进数据包**，并给出「只跑 55 条」与「跑 64 条需自建 9 条」两条路径（解 D-5 的误导面）。

### 档 2：仓库卫生（一次性，但要重算 sha）—— 解 D-3

5. **加 `.gitattributes`**（例如 `* -text`，彻底禁止行尾转换），重新 checkout 规范化工作区 ⇒ 之后本机与 clone 字节一致。
6. **重算所有 sha256 锚点**（成绩单 `provenance.*_sha256`、`CLAIMS.md` 声称值、`check_claims` 基线）⇒ 这是**一次性大改**，必须单独立项、单独立项票，且要证明「除 sha 外零差异」。

> ⚠️ **档 2 的代价必须说清**：它会改动 931 个文件的字节、所有 sha 锚点、`paper_sha256` 链。**这等于一次「全链重新封存」**，风险远大于档 1。若短期只要「别人能跑」，**档 1 就够**（第三方 `git config core.autocrlf false` + 按文档跑，sha 断言才可能对上 —— 但 D-3 仍会在 `check_claims` 里红）。

### 档 3：闸的健壮性（改代码，需单独立项）

7. **`require_dataset` 加强**：不只看目录存在，还要看 `modeling/` 下是否有 `n_cases` 个含 `spec.json` 的子目录（解 D-6）。这条**最值得做**，因为它挡的是「假失败被当战绩」。→ **✅ 已做（T-C1，R73 / NC-67）**：三级化并接任务卷覆盖，实测空目录 `rc=2` 且不出成绩。
8. **把 `return 2` 真正传到退出码**（解 D-7）。→ **❌ 取消：D-7 是我的测量错误（管道吃了退出码），`sys.exit(main())` 一直正确、实测 `rc=2`。无需修改。**
9. **`fetch_data` 增加交叉一致性检查**：数据包条数 vs 当前卷所需案例数，不一致给警告（解 D-5）。→ **◐ 部分做（T-C1）**：跨卷差集已由 `_c1_pack_gap.py` 落盘（`reports/diagnostics/data_pack_volume_gap.json`），且**评测侧**已硬拦（`require_dataset(expect_ids=…)`）；`fetch_data` 本体的跨卷检查仍未加（它不该知道卷，属评测侧职责 —— 记此判断以便将来不再重复讨论）。
10. **C-032 artifact 按当前代码重生成**（数字不变，只补 `judge_overrides`）—— 需老王拍板，属改官方 artifact。→ **仍待拍板**（T-C1 未动）。

---

## 5. 诚实边界（我没验的）

| 项 | 原因 |
|---|---|
| `pip install -r requirements.txt` 能否成功 | **沙箱无外网**（`ERROR: Could not find a version that satisfies the requirement numpy (from versions: none)`）。这是**我的实验环境限制，不是项目缺陷**，第三方有网即可 |
| `npm install` 能否成功 | 同上；已用 registry API 确认两个依赖公开存在且版本命中 |
| MSR 全 55 条能否复现 `20/22` | 需 ccx + 55 条求解（单条 6.9s，柱壳更慢，估 30–60 分钟）。本轮只单条实证路径可通，**未全量重跑** |
| `check_claims` 在「装了 node_modules + 有 64 条数据」的 clone 里能否全绿 | 同上，受限于无外网与数据包只有 55 条。**D-3 的行尾问题与这两条无关，会独立存在** |

---

## 6. go / no-go

**对「第三方能否复现 headline 的 TSR/SFR」：GO**（已实测 23/25，逐字段一致），**前提是拿到数据包**。

**对「第三方能否用这个 benchmark」：NO-GO（当前）**，卡在 D-1 + D-2 两个分发断点，与 D-3 的字节不可复现。

**对「数字本身是否可信」：不受影响** —— 本轮**没有发现任何数字错误**。所有失败都是「别人拿不到 / 拿不全 / 拿到的字节不同」，不是「算错了」。

---

## 7. 产物

| 文件 | 内容 |
|---|---|
| `reports/diagnostics/task_b1_contract.md` | 本合同 |
| `reports/diagnostics/task_b1_report.md` | 本报告 |
| `_b1_compare.py` | 复现结果 vs 官方 artifact 的逐叶子比对器 |
| `_b1_eol_scan.py` | 本仓 vs clone 的逐文件 sha256 差异扫描器（**注意 `core.quotepath=false`**：首版用默认 quotepath 把 88 个中文路径误报成「缺失」，已修正为 0 缺失） |
