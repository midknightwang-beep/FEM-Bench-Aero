# DATA — 数据集本体的获取、校验与版本匹配

> 这份文件回答三件事：**数据在哪拿**、**拿到的是不是完整的那一份**、**它和你要跑的卷配不配**。
> 配不配这件事比前两件更容易出事 —— 配错了不会报错，只会让模型「看起来变差」。

---

## 1. 数据集本体是什么

`FEM-Bench-Aero/modeling/` 下每个目录是一条算例，含：

| 文件 | 作用 |
|---|---|
| `spec.json` | **金标准**：这条算例的规范化 FEASpec（评测时被判分器当标准答案） |
| `truth.json` | 真值：求解得到的位移/应力等参考量（物理保真度闸用） |
| `model.inp` | CalculiX 输入卡（可直接跑） |
| `model.msh` | 网格 |
| `model.step` | 几何 |
| `model.results.json` | 求解结果摘要 |

**它为什么不在 git 里**：解包后约 236 MB，而 git 仓本体只有几 MB。数据以归档包单独分发，
仓库里只放代码、任务卷、候选集与成绩单 artifact。

---

## 2. 获取方式

**本仓库不含下载地址** —— 数据集不随仓库分发，也没有公开的发布页。可用的获取途径：

| 途径 | 形态 | 说明 |
|---|---|---|
| **向维护者索取归档包** | 单个 `.tar.gz`（约 **85 MB**）+ 同名 `SHA256SUMS.txt` | 推荐。拿到后按 §3 校验 |
| **内部介质** | 同上 | 适用于内网环境 |

包内结构（解包后）：

```
<dest>/
├── MANIFEST.md          # 包自述
├── manifest.json        # 机读清单：n_cases / splits / by_family
└── modeling/            # 55 条算例目录
```

> ⚠️ **包的版本与卷的版本必须匹配**，见 §5。这是本项目已知最容易踩的坑。

---

## 3. 校验：两件事都要做

### 3.1 sha256 校验（确认「文件没被换」）

包目录里有一个 `SHA256SUMS.txt`，格式是 `sha256sum` 生成的：

```
<64位hex> *<路径>/FEM-Bench-Aero-v1.0-data.tar.gz
```

**注意那个 `<路径>`**：它记录的是**打包那台机器上的绝对路径**（`*/f/FEA_Archive_...` 这种形式），
所以 `sha256sum -c SHA256SUMS.txt` 在你的机器上会因为找不到该路径而失败 —— **这不是包坏了**。

正确做法是手工比对：

```bash
# Linux / macOS / Git Bash
sha256sum <DATA_DIR>/FEM-Bench-Aero-v1.0-data.tar.gz

# Windows PowerShell
Get-FileHash <DATA_DIR>\FEM-Bench-Aero-v1.0-data.tar.gz -Algorithm SHA256
```

然后与 `SHA256SUMS.txt` 第一列逐字符比对。当前 v1.0 包的指纹是：

```
8cec47ce65486d00a6cad8777894f3f996d703a5aa70d6c0d0411ec0fc181dd3
```

> 维护者**重新打包**后这条会变；以包自带的 `SHA256SUMS.txt` 为准，本文这条只是给你一个「应该是它」的凭据。

### 3.2 条数校验（确认「数据齐」）—— 这一步才是关键

sha256 只能证明「文件没被换」，**证明不了「里面是你要的那几条」**。所以解包后必须核条数：

```bash
cd <REPO>/feagpt_repro
python fetch_data.py --src <DATA_DIR>/FEM-Bench-Aero-v1.0-data.tar.gz
```

`fetch_data.py` 会做：sha256 比对 → 解包 → 读包内 `manifest.json` 的 `n_cases` → 数
`modeling/` 实际目录数 → 两者不等即 `[FATAL]` 且 `rc=2`。

`fetch_data.py` 只跟**包自己的** manifest 对账，**它不知道你要跑的卷要几条**。
跨过这一层的检查在评测侧：

```bash
cd <REPO>/feagpt_repro
python score_baseline.py --candidates candidates_l3_v6c_glm_p2 \
  --tasks reports/papers/tasks_v6c.jsonl --report /tmp/x.json
```

若数据不全，会在**开跑前**硬报（`rc=2`，不产出任何成绩）：

```
[dataset] 金标准数据集不完整：… 里有 55 条 spec.json，但卷内 64 条任务里有 9 条缺：…
```

这条闸（`require_dataset(expect_ids=…)`，2026-10-30 加入）存在的原因很实在：
**空目录 / 不全的目录在旧版下能跑出一张看起来合法的假成绩单**（实测 `exam TSR 3/25 (12.0%)`，无任何警告）。

---

## 4. 求解器 CalculiX（只有 MSR 需要）

- **复现 TSR / SFR 不需要求解器** —— 判分器只用 Python 标准库。
- **MSR 需要 `ccx`**，本项目**不随仓库分发**（`tools/` 不入 git）。安装方式：
  - 官网 <http://www.dhondt.de/> 下载对应平台的 `ccx`（v2.20+ 均可）
  - 或用包管理器（`apt install calculix-ccx` / `conda install -c conda-forge calculix`）
- 路径通过环境变量指定：

```bash
export FEAGPT_CCX=/path/to/ccx          # Windows Git Bash: export FEAGPT_CCX="C:/path/to/ccx.exe"
"$PY" msr_l3.py --candidates <CAND> --tasks <TASKS> --report <OUT> --only <一条题>
```

单条题约 **7 秒**（实测，4 核）。先单条试通再跑全量。

---

## 5. ★ 版本匹配（最容易踩的坑）

**三个版本号必须分清**：

| 名字 | 是什么 | 条数 |
|---|---|---|
| **数据包 v1.0** | 归档包里 `modeling/` 的实际条数 | **55** |
| **考卷 v6c** | `reports/papers/tasks_v6c.jsonl` 的 L3 题（= 对外 headline C-032 用的卷） | **55** |
| **考卷 v7** | `tasks/tasks.jsonl` 的 L3 题（当前主卷，含 v1.1 新增 9 条） | **64** |

⇒ **`v1.0 包 + v6c 卷` 完全匹配（缺 0）；`v1.0 包 + v7 卷` 缺 9 条。**
v7 卷新加的 9 条属数据集 v1.1 增量，**尚未进 v1.0 数据包**。

差集是**可复算的**，不靠本文手抄 —— 用 `_c1_pack_gap.py` 现算：

```bash
cd <REPO>/feagpt_repro
"$PY" _c1_pack_gap.py --src <DATA_DIR>/FEM-Bench-Aero-v1.0-data.tar.gz \
                      --out reports/diagnostics/data_pack_volume_gap.json
```

**当前实测结果**（`reports/diagnostics/data_pack_volume_gap.json`，2026-10-30）：

| 卷 | L3 题数 | 覆盖 | 缺 |
|---|---|---|---|
| v6c | 55 | 55 | **0** ✅ |
| v7 | 64 | 55 | **9** ⚠️ |

### 该怎么办
- **只想复现 headline（C-032）** → 用 `v1.0 包 + v6c 卷`，一切正常（[QUICKSTART.md](QUICKSTART.md) §4 的默认路径）。
- **想跑 v7 卷** → 需要数据集 v1.1（64 条）。**目前没有分发版本**；若你只有 v1.0 包，
  评测会在开跑前被 §3.2 那条闸拦住，你会明确看到「缺 9 条」，不会拿到一张假成绩单。

---

## 6. 已知问题（维护者清楚，尚未修）

| 现象 | 原因 | 规避 |
|---|---|---|
| `SHA256SUMS.txt` 用 `sha256sum -c` 失败 | 里面记的是打包机的绝对路径 | 手工 `sha256sum <file>` 比对（§3.1） |
| **`check_claims.py` 在 clone 里红几项，sha 值对不上** | **行尾**：仓库无 `.gitattributes`，`core.autocrlf` 在 checkout 时把 LF 转 CRLF，而本仓工作区是**逐文件混合态** | 见 §6.1 —— **这不是你的环境问题，且暂无单一配置能全绿** |
| 缺 `node_modules` ⇒ `S-39`/`S-43` 红 | 自检里有一项要 `node --print-prompt-sha`，依赖 `ajv` | `npm install`（见 §6.1） |
| 空目录能骗过前置闸 | **已修**（2026-10-30）：`require_dataset` 现在查 `spec.json` 实存与覆盖 | 升级到含该修的版本 |

### 6.1 ★ 关于行尾与 sha256（务必先读，能省你几小时）

这个项目的一部分证据是 **sha256 锚定**的（成绩单 `provenance.*_sha256`、`check_claims` 的声称值、`S-57` 的卷指纹）。
而**仓库里没有 `.gitattributes`**，`core.autocrlf` 会在 checkout 时把 LF 转成 CRLF。实测（T-B1）：

```
入库文件总数 : 1511
两侧 sha 相同: 580      ← 本机本来就是 CRLF 的那批
两侧 sha 不同: 931      ← 本机是 LF 的那批，clone 后被转成 CRLF
```

⇒ **本仓工作区是逐文件混合态**：老文件多为 CRLF，后来用脚本新写的多为 LF。
**因此不存在一种统一的 `core.autocrlf` 设置能让全部锚点同时对上** ——
关掉它（得到全 LF）会弄坏 CRLF 那一批（实测：卷指纹 `caf0f6c3…` 立刻变 `6e7437b1…`，`S-57` 转红）；
打开它（得到全 CRLF）会弄坏 LF 那一批（实测：`S-59` 的修正表 sha 对不上）。

**给你的建议（按目的选）**：

| 你想做什么 | 该怎么做 |
|---|---|
| **验证 headline 数字能不能复现**（最重要、也是唯一稳的） | 什么都不用管 —— 直接按 [QUICKSTART.md](QUICKSTART.md) §4 跑。判分**只读内容、不校验 sha**，实测 `23/25 (92.0%)` 逐字可复现 |
| **跑 `check_claims` 全套自检** | 先 `npm install`（解 `S-39`/`S-43`）；**其余 sha 类红项目前无法在非维护者环境全绿**，请把这些红项当**已知限制**读，不要据此判断"仓库坏了"或"数字不可信" |
| **要一个能全绿的干净环境** | 等**档 2**（加 `.gitattributes` 固定行尾 + 重算全部 sha 锚点）—— 这是一次"全链重新封存"，维护者尚未排期 |

> **一句判断**：行尾问题影响的是**证据的可移植性**，不是**数字的正确性**。
> 不要因为 sha 对不上就怀疑成绩 —— 复现数字那条路是通的、而且已经逐字验过。

