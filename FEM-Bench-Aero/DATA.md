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

**它为什么不在 git 里**：解包后 **236 MB（55 条）/ 276 MB（64 条）**，而 git 仓本体只有几 MB。
数据以归档包单独分发，仓库里只放代码、任务卷、候选集与成绩单 artifact。

---

## 2. 获取方式

数据集走 **GitHub Release** 分发（不随仓库分发）：

> **下载页**：<https://github.com/midknightwang-beep/FEM-Bench-Aero/releases/tag/data-v1.0-v1.1>

| 资产 | 条数 | 大小 | 对应考卷 |
|---|---|---|---|
| `FEM-Bench-Aero-v1.0-data.tar.gz` | **55** | 85.4 MiB | `reports/papers/tasks_v6c.jsonl`（55 题 = headline **C-032**） |
| `FEM-Bench-Aero-v1.1-data.tar.gz` | **64** | 100.2 MiB | `tasks/tasks.jsonl`（64 题 = 当前主卷 v7） |
| `SHA256SUMS.txt` | — | — | 两个包的指纹（裸文件名，`sha256sum -c` 直接可用） |

**v1.1 是 v1.0 的超集**：多 9 条（1 `fuselage_barrel` + 5 `naca4412_wingbox` + 2 `open_hole_panel`
+ 1 `stiffened_panel`），v1.0 的 55 条在 v1.1 里**逐字节相同**（384/384 文件 sha256 一致，实测）。

命令行下载（无需登录）：

```bash
BASE=https://github.com/midknightwang-beep/FEM-Bench-Aero/releases/download/data-v1.0-v1.1
curl -L -O "$BASE/FEM-Bench-Aero-v1.1-data.tar.gz"   # 想跑 v7 卷用这个
curl -L -O "$BASE/FEM-Bench-Aero-v1.0-data.tar.gz"   # 只复现 headline 用这个
curl -L -O "$BASE/SHA256SUMS.txt"
```

包内结构（解包后，两版相同）：

```
<dest>/
├── MANIFEST.md          # 包自述（人读，按 split 分组）
├── manifest.json        # 机读清单：n_cases / splits / by_family
└── modeling/            # v1.0 = 55 条 / v1.1 = 64 条算例目录
```

> ⚠️ **包的版本与卷的版本必须匹配**，见 §5。这是本项目已知最容易踩的坑。

---

## 3. 校验：两件事都要做

### 3.1 sha256 校验（确认「文件没被换」）

Release 附件里的 `SHA256SUMS.txt` 用**裸文件名**，和两个包放同一目录即可直接校验：

```bash
sha256sum -c SHA256SUMS.txt
```

期望两行都 `OK`：

```
FEM-Bench-Aero-v1.0-data.tar.gz: OK
FEM-Bench-Aero-v1.1-data.tar.gz: OK
```

Windows PowerShell（清单格式不适用，逐个算）：

```powershell
Get-FileHash .\FEM-Bench-Aero-v1.1-data.tar.gz -Algorithm SHA256
```

当前两个包的指纹：

| 包 | sha256 |
|---|---|
| v1.0（55 条） | `8cec47ce65486d00a6cad8777894f3f996d703a5aa70d6c0d0411ec0fc181dd3` |
| v1.1（64 条） | `8b6295d16f8505bca80971432c205e819d3e466c2a19a26407c08e2d76af0a4e` |

> 维护者**重新打包**后这两条会变；以 Release 附件里的 `SHA256SUMS.txt` 为准。
> **注意不要用包内自带的那份**：`v1.0` 包里的 `SHA256SUMS.txt` 记的是打包机绝对路径（`*/f/FEA_Archive_...`），
> `-c` 会失败 —— 那是旧格式，不是包坏了。

### 3.2 条数校验（确认「数据齐」）—— 这一步才是关键

sha256 只能证明「文件没被换」，**证明不了「里面是你要的那几条」**。所以解包后必须核条数：

```bash
cd <REPO>/feagpt_repro
"$PY" fetch_data.py --src <DATA_DIR>/FEM-Bench-Aero-v1.1-data.tar.gz   # 跑 v7 卷用 v1.1
"$PY" fetch_data.py --src <DATA_DIR>/FEM-Bench-Aero-v1.0-data.tar.gz   # 只复现 headline 用 v1.0
```

`fetch_data.py` 会做：sha256 比对 → 解包 → 读包内 `manifest.json` 的 `n_cases` → 数
`modeling/` 实际目录数 → 两者不等即 `[FATAL]` 且 `rc=2`。

`fetch_data.py` 只跟**包自己的** manifest 对账，**它不知道你要跑的卷要几条**。
跨过这一层的检查在评测侧：

```bash
cd <REPO>/feagpt_repro
"$PY" score_baseline.py --candidates candidates_l3_v6c_glm_p2 \
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

**四个版本号必须分清**：

| 名字 | 是什么 | 条数 |
|---|---|---|
| **数据包 v1.0** | Release 里 `FEM-Bench-Aero-v1.0-data.tar.gz` 的 `modeling/` | **55** |
| **数据包 v1.1** | Release 里 `FEM-Bench-Aero-v1.1-data.tar.gz`（= 当前仓库 `modeling/` 磁盘态） | **64** |
| **考卷 v6c** | `reports/papers/tasks_v6c.jsonl` 的 L3 题（= 对外 headline C-032 用的卷） | **55** |
| **考卷 v7** | `tasks/tasks.jsonl` 的 L3 题（当前主卷，含 v1.1 新增 9 条） | **64** |

⇒ **`v1.0 包 + v6c 卷` 完全匹配；`v1.1 包 + v7 卷` 完全匹配。**
混用（`v1.0 包 + v7 卷`）会有缺口，会在开跑前被 §3.2 那条闸拦住。

差集是**可复算的**，不靠本文手抄 —— 用 `_c1_pack_gap.py` 现算：

```bash
cd <REPO>/feagpt_repro
"$PY" _c1_pack_gap.py --src <DATA_DIR>/FEM-Bench-Aero-v1.1-data.tar.gz \
                      --out reports/diagnostics/data_pack_volume_gap.json
```

**当前实测结果**（`reports/diagnostics/data_pack_volume_gap.json`，v1.1 包口径）：

| 卷 | L3 题数 | 覆盖 | 缺 |
|---|---|---|---|
| v6c | 55 | 55 | **0** ✅ |
| v7 | 64 | 64 | **0** ✅ |

> `v1.0 包`对 v7 卷是有缺口的（这正是 v1.1 存在的理由）—— 把上面的 `--src` 换成
> `FEM-Bench-Aero-v1.0-data.tar.gz` 即可复算那张缺口表，本文不写死这几条。

### 该怎么办
- **只想复现 headline（C-032）** → `v1.0 包 + v6c 卷`（[QUICKSTART.md](QUICKSTART.md) §4 的默认路径）。
  用 `v1.1 包`也可以：它是超集，55 条逐字节相同。
- **想跑 v7 卷** → 用 `v1.1 包`，64 条齐。

---

## 6. 已知问题（维护者清楚，尚未修）

| 现象 | 原因 | 规避 |
|---|---|---|
| `SHA256SUMS.txt` 用 `sha256sum -c` 失败 | **已修**（2026-10-31）：Release 附件改用裸文件名。仅 `v1.0` 包**内**自带的那份仍是打包机绝对路径 | 用 Release 附件里的那份（§3.1） |
| `check_claims.py` 在 clone 里红几项，sha 值对不上 | **已修**（2026-10-31 / T-D3）：仓库加了 `.gitattributes`，行尾统一 CRLF，7 处活锚点重算 | 见 §6.1；重新 clone 即可 |
| 缺 `node_modules` ⇒ `S-39`/`S-43` 红 | 自检里有一项要 `node --print-prompt-sha`，依赖 `ajv` | `npm install`（见 §6.1） |
| 空目录能骗过前置闸 | **已修**（2026-10-30）：`require_dataset` 现在查 `spec.json` 实存与覆盖 | 升级到含该修的版本 |

### 6.1 ★ 关于行尾与 sha256（2026-10-31 已修，历史备查）

这个项目的一部分证据是 **sha256 锚定**的（成绩单 `provenance.*_sha256`、`check_claims` 的声称值、`S-57` 的卷指纹）。

**2026-10-31 之前**仓库没有 `.gitattributes`，`core.autocrlf` 会在 checkout 时把 LF 转成 CRLF，
而工作区本身是逐文件混合态。实测（T-B1）：

```
入库文件总数 : 1511
两侧 sha 相同: 580      ← 本机本来就是 CRLF 的那批
两侧 sha 不同: 931      ← 本机是 LF 的那批，clone 后被转成 CRLF
```

那时的结论是「不存在单一 `core.autocrlf` 设置能让全部锚点对上」：关掉（全 LF）会弄坏 CRLF 那一批，
打开（全 CRLF）会弄坏 LF 那一批 —— 两条路各红一项、且不是同一项。

**现已修复（T-D3，方案 A 统一 CRLF）**：仓库加了 `.gitattributes`（`* text=auto eol=crlf`，`*.sh` 例外），
955 个文本文件规范化为 CRLF，7 处受影响的活锚点重算。验收是**从 GitHub 匿名 clone** 后
`_b1_eol_scan.py` 报 **0 差异**（1550/1550 文件逐字节相同），且 clone 里 `S-57` 与 `S-59` **同时绿**。

⇒ **你 clone 下来的字节与维护者本机一致**，sha 类判据不再需要「当已知限制读」。

**仍然存在的红项只有 3 个，原因都不是行尾**（2026-10-31 在 `383860f` 的干净 clone 里实测）：

| 红项 | 真正原因 | 解法 |
|---|---|---|
| `S-39` | `node --print-prompt-sha` 无输出（缺 `node_modules`） | `npm install` |
| `S-43` | 同上 | 同上 |
| `S-61` | `.git/hooks` 不入库，新 clone 没有 pre-commit hook | `"$PY" check_commit.py --install-hook` |

> **一句判断**：行尾问题影响的是**证据的可移植性**，不是**数字的正确性**。
> 现在这条也通了——如果你 clone 后仍见 sha 对不上，先确认克隆的是 `9020ba5` 之后的提交。

