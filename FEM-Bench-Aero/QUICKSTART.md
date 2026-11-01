# QUICKSTART — 5 分钟从零到看见 headline

> 这份文件的唯一目标：**让没参与过这个项目的人，在没有作者帮助的情况下，自己跑出 `exam TSR 23/25 (92.0%)`。**
> 如果你在任何一步卡住，那不是你的问题 —— 请按 §6 反馈，那说明本文件还欠一句话。

---

## 0. 你会拿到什么，不会拿到什么

| 在 git 里（clone 就有） | 不在 git 里（要另外拿） |
|---|---|
| 判分器 `evaluate.py` / 成绩汇总 `score_baseline.py` / 负控 `negative_controls.py` | **数据集本体** `modeling/`（236 MB，64 条算例的 `spec.json` + `truth.json` + `model.inp`） |
| 任务卷 `tasks/tasks.jsonl`（v7，192 行）+ 历史快照 `reports/papers/tasks_v6c.jsonl`（v6c，165 行） | **求解器** CalculiX `ccx`（跑 TSR / SFR **不需要**；只有 MSR 需要） |
| **候选集**（`candidates_l3_v6c_glm_p2` 等，55 条 LLM 原始输出） | |
| 全部成绩单 artifact（`reports/`）与主张账本 `CLAIMS.md` | |

**关键前提**：候选集已在 git 里 ⇒ **复现 headline 不需要任何大模型 API key**。

---

## 1. 拿到仓库

仓库含 1500+ 文件、含完整历史。**直接 clone**（public 仓库，无需凭据）：

```bash
git clone https://github.com/midknightwang-beep/FEM-Bench-Aero.git repo
cd repo
```

离线环境可用 bundle（单个文件，含完整历史，可像仓库一样 clone）：

```bash
git clone FEM-Bench-Aero.bundle repo
```

> **优先 `git clone`，不要在 Windows 上用「Download ZIP」**：ZIP 是导出快照，不带 `.git`，
> 也没有 hooks 与 reflog；本项目证据是 sha256 锚定的，clone 是唯一被实测过的路径
> （2026-10-31 匿名 clone 后 1550/1550 文件逐字节一致）。

---

## 2. 拿到数据集本体

数据集（`modeling/`）**不进 git**，走 **GitHub Release** 分发：

> <https://github.com/midknightwang-beep/FEM-Bench-Aero/releases/tag/data-v1.0-v1.1>

| 你要跑 | 下哪个包 |
|---|---|
| headline **C-032**（v6c 卷，55 题） | `FEM-Bench-Aero-v1.0-data.tar.gz`（用 v1.1 也行，它是超集） |
| 当前主卷 **v7**（64 题） | `FEM-Bench-Aero-v1.1-data.tar.gz` |

包的内容、校验方法与**版本匹配**要求见 [DATA.md](DATA.md)（**别混用包和卷**）。

拿到包后，在 `feagpt_repro/` 下解包并校验：

```bash
cd repo/feagpt_repro
"$PY" fetch_data.py --src <DATA_DIR>/FEM-Bench-Aero-v1.1-data.tar.gz   # 或 v1.0
```

预期输出里会出现逐文件 SHA256 核对与 `条数 = 55` 之类的一行。**条数对不上就别往下走**。

---

## 3. 准备 Python

复现 **TSR / SFR** 只需要 **Python 3.10+ 标准库**，不装任何第三方包：

```bash
python -m venv .venv
# Linux/macOS
.venv/bin/python --version
# Windows
.venv\Scripts\python.exe --version
```

只有到 §5 跑 MSR 时才需要 `numpy` + `gmsh`（`pip install -r requirements.txt`）。

> 下文用 `$PY` 指代你刚建的解释器，例如
> `PY=.venv/bin/python`（Linux/macOS）或 `PY=.venv/Scripts/python.exe`（Windows Git Bash）。

### 3.5（可选）Node 依赖 —— 只有跑证据自检 `check_claims.py` 时才需要

§4 复现 headline **完全不需要** Node。但如果你想自己验一遍「仓库里的数字与 sha 没被改过」
（`check_claims.py`），其中两项（`S-39` / `S-43`）要用
`node gen_candidates_v2.js --print-prompt-sha` 算 prompt 的 sha256，而它依赖 `ajv`：

```bash
cd repo/feagpt_repro
npm install          # 只装 package-lock.json 里锁定的依赖（ajv 等）
```

没装就红这两项，报的是 `node --print-prompt-sha` 相关错误 —— **不是你 clone 错了，也不是数字错了**。
（这两项红了不影响 §4 的 `23/25 (92.0%)`：判分只读内容，不校验 sha。）

---

## 4. 复现 headline（**这一步验证的就是项目的核心主张**）

```bash
cd repo/feagpt_repro
"$PY" score_baseline.py \
  --candidates candidates_l3_v6c_glm_p2 \
  --tasks      reports/papers/tasks_v6c.jsonl \
  --trivial    reports/trivial_baselines_L3_v6c.json \
  --report     /tmp/my_c032.json \
  --label      "C-032 v6c x glm prompt-v2 (paper v6c, candidates glm_p2)"
```

**预期看到（逐字）：**

```
  EXAM  TSR 23/25 (92.0%)  SFR 20/22 (90.9%)   underpowered=False
```

这就是对外 headline（`CLAIMS.md` C-032）。它与你仓库里 `reports/baseline_scorecard_L3_v6c_p2.json`
的共同字段**应当逐字段相同**（多出来的 `msr_section` / `exam_v11` 字段要跑完 §5 才有）。

> **没跑出来怎么办**：现在的前置闸会明确告诉你差什么，不会静默给你一张假成绩单。
> - `缺少金标准数据集：…` → §2 没做
> - `金标准目录存在但里面没有任何 spec.json` → 解包失败或解到了别处
> - `金标准数据集不完整：… 里有 55 条，但卷内 64 条任务里有 9 条缺` → **包与卷版本不匹配**，见 [DATA.md](DATA.md)

---

## 5.（可选）跑 MSR —— 需要求解器

MSR 是「模型产出的 spec 真的能算出一个正确结果吗」，要真跑有限元，**需要 CalculiX `ccx`**
（本项目**不随仓库分发**求解器；安装方式见 [DATA.md](DATA.md) §4）。装好后：

```bash
cd repo/feagpt_repro
export FEAGPT_CCX=/path/to/ccx          # Windows Git Bash: export FEAGPT_CCX="C:/path/to/ccx.exe"
"$PY" msr_l3.py \
  --candidates candidates_l3_v6c_glm_p2 \
  --tasks      reports/papers/tasks_v6c.jsonl \
  --report     /tmp/my_c032.json
```

单条题约 **7 秒**（实测 `L3_open_hole_panel_400x200_d40`，本机 4 核）。跑全量前建议先单条试
（注意这里复用的是 §4 那个文件）：

```bash
"$PY" msr_l3.py --candidates candidates_l3_v6c_glm_p2 \
  --tasks reports/papers/tasks_v6c.jsonl --report /tmp/my_c032.json \
  --only L3_open_hole_panel_400x200_d40
```

预期：`rc=0`、最后印 `MSR = 1/1 (100.0%)`（只算你指定的那一条；其余记 `待补齐`，是正常的）。

> ⚠️ **`--report` 必须指向 §4 已经生成的那个成绩单文件**（上例里是 `/tmp/my_c032.json`）——
> `msr_l3` 的行为是**读入它、把 MSR 段合并进去、再写回**，不是新建。
> 指向一个不存在的路径会得到 `FileNotFoundError`（**已知待改进**：这里应该给一句人话提示）。
> 所以正确顺序永远是：**先 §4，再 §5**。

---

## 6. 卡住了 / 发现文档不对

请在反馈里带上三样东西：**你跑的命令**、**完整输出**、**你用的 Python 版本**。

已知的、维护者清楚但**尚未修**的问题（写在这里避免你以为是自己的错）：

| 现象 | 原因 | 现状 |
|---|---|---|
| ~~本仓库没有公开远端地址~~ | **已发布**（2026-10-31） | 直接 clone：`https://github.com/midknightwang-beep/FEM-Bench-Aero.git` |
| ~~数据包没有公开下载地址~~ | **已发布**（2026-10-31） | Release 页见 §2 与 [DATA.md](DATA.md) §2 |
| ~~`check_claims.py` 在 clone 里红几项，sha 值对不上~~ | **已修**（2026-10-31 / T-D3）：仓库加了 `.gitattributes`，行尾统一 CRLF，7 处活锚点重算 | 重新 clone 即可。行尾不再造成 sha 不一致（详见 [DATA.md](DATA.md) §6.1） |
| `check_claims.py` 的 `S-39`/`S-43` 红 | 缺 `node_modules`（有一项要 `node --print-prompt-sha`，依赖 `ajv`） | 按 **§3.5** 跑 `npm install` 即可 |
| `check_claims.py` 还红 `C-013`/`S-46`/`S-51`/`S-56`/`S-61` | 这五项的**对象不在公开集里**（外部归档的数据包清单、被脱敏的 `PY=`、按发布决定移出的 `AGENTS.md`/`CLAUDE.md`、以及不分发的 `.git/hooks`）—— 不是你的环境错 | 加 `--public` 重跑：它们会标 `exempt` 并写明原因，**不计入通过数**（R75）。**加了之后仍然红的项才是要处理的** |
| `fetch_data.py` 对不上 sha256 | 包没下全，或下的是另一个版本 | 用 Release 里的 `SHA256SUMS.txt` 跑 `sha256sum -c`，见 [DATA.md](DATA.md) §3.1 |

> **别把行尾问题当成「数字不可信」**：判分只读内容、不校验 sha ——
> §4 那条命令在任何平台上都能跑出 `23/25 (92.0%)`。sha 类红项影响的是**证据的可移植性**，不是**结论的正确性**。


---

## 7. 接下来读什么

| 想知道 | 看 |
|---|---|
| 这个 benchmark 到底在测什么 | [README.md](README.md) 开头「这是什么」 |
| 每个数字的出处与边界 | [CLAIMS.md](CLAIMS.md)（主张账本，**禁止手抄数字**） |
| 判分口径 / 九道闸 / 规则 | [RUBRIC.md](RUBRIC.md) |
| 数据集本身的已知限制 | [dataset_card.md](dataset_card.md) |
| 数据包的校验与版本 | [DATA.md](DATA.md) |
