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


---

## 7. v2 打样卷（模态线 C6-P1，2026-11-07 冻结）

`modeling_v2/` 是**独立 v2 数据线**（C6 拍板：数据层形态 A），8 条翼盒模态打样卷，
与 v1.1（64 条静力）并行、不互相补丁（R65）。**随 git 仓分发**（追踪体积 ~10 MB，
不含 `.frd/.12d` 等求解会话产物），不走 Release。

### 7.1 卷内容

| 项 | 值 |
|---|---|
| 案例数 | **8**（基准 + 展长/弦长/蒙皮/长桁/后掠/梯形/腹板 七个单变量轴） |
| 分析类型 | `*FREQUENCY`，`n_modes=10`（ccx ARPACK / abaqus LANCZOS 双码） |
| 冻结指纹 | `modeling_v2/SHA256SUMS.txt`（74 文件，`modeling_v2/` 内相对路径） |
| 真值 | 各 case `truth.json`：`f_hz_ccx` + `f_hz_abq` 双谱、`n_nodes`、`spec_sha256` |
| 交叉差 artifact | `verify_v2_p1.json`（40 对逐序号）+ `verify_v2_p1_ccx.json`（10 阶全谱） |

### 7.2 校验（在仓库根目录跑）

```bash
cd FEM-Bench-Aero/modeling_v2
sha256sum -c SHA256SUMS.txt
```

### 7.3 命名与 v1.1 的差异

| v1.1（`modeling/`） | v2（`modeling_v2/`） |
|---|---|
| `spec.json` / `model.inp` / `model.msh` | `<case>_modal.spec.json` / `<case>_modal.inp` / `<case>_modal.msh` |
| 静力 `*STATIC`，truth 是位移/应力标量 | 模态 `*FREQUENCY`，truth 是 f1–f10 双码频谱 |
| 不入库，Release 分发 | 入库，git 分发 |

### 7.4 判据口径（拍板 2026-11-07 方案 A）

- **f1 硬判 <1%**（实测双码 median 0.23% / max 0.73%）；高阶只记不判（S4 公式级差异，假设待核实）。
- **候选判分走「同码自比」**：候选 spec 与参考 spec 都走同一条 feagpt 管线、同一码求解，
  公式差异在差值中自动抵消；跨码 f2+ 差异**不进判据**。

### 7.5 死键修正（2026-11-07 深夜，老王拍板「修卷剥键+重冻结」）

第一轮实测前发现 8 条 gold `spec.json` 带死键（v1.1 base case 参数表残留）：
长桁细节键 8/8（7 条 `n_stringers_per_skin=0` 死键 + str3 的 `stringer_flange_width`
被 `blade()` 忽略且 SYS 明令不写）+ 自创 extra 键 2 条（`n_ribs5` 的 `sweep_index`、
`web1` 的 `end_torque`/`torque_axis_dof`）。模型守 SYS 不写这些键反而被判红
（判据 supply 链断裂）。修正：`make_v2_strip_dead_keys.py` 剥键 + **deck sha 逐位
一致**验证（8/8，truth 无需重出）+ `SHA256SUMS.txt` 只重算 8 条 spec 行（复算
74/74）。考卷呈现补 name/description 逐字照抄；判分器在 pipeline 闸前把
`name` 归一为 case_name（防模型 name 错位劫持产物路径 → `.dat` 假红）。

### 7.6 第一轮实测结果（2026-11-07，diagnostic）

成绩单：`feagpt_repro/reports/diagnostics/v2_modal_pilot_run1_2026-11-07.json`
（v2 pilot 线，**不进对外 headline**，headline 仍是 C-032）。
- **deepseek-v4-pro 8/8**；glm-5.3-flash 6/8。
- 跑通的条目 f1_rel 全部 0.0（同码自比，物理逐位一致）。
- glm 两红均为真红：材料块自创键 `E`（contract 拒绝）+ description 措辞漂移。
- 考卷 sha `b9eac76d…`、prompt sha `6b90daf0…`（SYS 未动）、冻结 sha `0aa7e3e3…`。

### 7.7 第二遍归因与收口报告（2026-11-07 夜）

- **glm 独立重跑**（同卷、同 prompt sha `6b90daf0`、同模型、同参数）：6/8 → **7/8**，
  两遍 f1_rel 全 0.0。`E` 键 contract 红只在第一遍出现 ⇒ 单次波动；
  `description` 把 `NACA4412` 润色成 `NACA 4412` **两遍逐字相同** ⇒ 稳定的字段保真弱点。
- 按「两遍区间重叠不得排名」：glm 记为 **`[6,7]/8`**，任一遍不单独引用；ds 8/8 仅一遍且为 pilot，同样不对外。
- 对照 artifact：`feagpt_repro/reports/diagnostics/v2_modal_pilot_stability_2026-11-07.json`
  （`freeze_bridge` 段说明第一遍冻结 sha 与提交前 EOL 规范化的关系：卷语义/deck 字节未变，两遍同卷）。
- **收口报告**：`REPORT_C6_P1_MODAL.md`（拍板链 → 实现链 → 判据口径 → 两轮实测 → 诚实边界 → 未决岔路口）。
- **已拍板（2026-11-07 22:23，老王）**：**description 继续硬判，不开豁免名单**。
  理由：递归全键判据不留名单（N-35）；为单个字段开口子需另配「防放水」反向闸（R69）
  并重出两遍成绩单 + bridge（R53），维护成本大于 1 条失分。代价：glm 稳定 `[6,7]/8`。
  判分器与两遍成绩单**均不改动**，不触发换代链。
- **已拍板（2026-11-07 晚，老王，CONFLICT N-37 选项 A）**：C6 后续 = **按原提案 `PROPOSAL_C6_BUCKLING_MODAL.md` §2 的 C6-P2 线性屈曲**（加筋板轴压 N_x 扫描 + 柱壳外压，语义量 λ_cr + 屈曲模态数，ccx/abq `*BUCKLE`，阈值先测后定）。「模态扩卷（柱壳/加筋板）+ 自主建模题」**不在本轮、不占 P2 名号**（蜗子上一条的推断已作废）。
- **下一步**：屈曲打样设计（`DESIGN_C6_P2_BUCKLE.md`）——先查双码 `*BUCKLE` 语法/输出与载荷工况，再出拍板单。

### 7.8 双码 λ 系统性差异送审报告（2026-11-08）

- 送审件：`REVIEW_C6_P2_FORMULATION_DIFFERENCE.md`（FBA-C6P2-REV-001，待审查稿）。
  按「已确认事实／待验证假设／待补充材料」三层编写，含公式与变量定义、适用口径、
  证据清单 E1–E10、核验点 K1–K10、成因类别 C1–C7、候选方案 S1–S6、决策事项 D1–D6，
  第 10 节预留专家审查意见与结论填写位；**不预设成因结论、不预设 λ 阈值**。
- 新增核验证据：`reports/diagnostics/p2_dual_deck_parity_2026-11-08.json`
  （两码 pre-`*STEP` 结构段**除 2 行 `*HEADING` 方言标签外 207190 行逐字节一致、0 差异行**，
  `*DLOAD`/`*BOUNDARY`/`*ELASTIC`/`S4` 逐值相同）⇒ deck 翻译层已排除，成因仍待专家核验。
- 缺失材料 U1–U12 在报告第 9 节统一标注「待补充」。
