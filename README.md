# FEM-Bench-Aero

面向**飞机结构有限元建模**的可复现评测基准：给自然语言建模需求，考的是模型能不能
产出**可求解、可判分、spec 保真**的 FEM 模型，而不是能不能写出一段听起来像样的话。

- **考什么**：三层任务（L1 结构化 / L2 澄清 / L3 端到端建模），带冻结的题面、真值与判分器
- **怎么判**：`TSR`（任务成功率）、`SFR`（spec 保真率）、`MSR`（模型成功率）为主口径，
  另有 L2 澄清层指标；每条口径的分母构成与排除项都写在成绩单里
- **怎么验**：所有对外数字都能用仓库内脚本从 artifact 重算；不接受「我跑过」式结论

> **本 README 不写任何成绩数字。** 当前 headline 是哪条、分子分母是多少，
> 一律以 `FEM-Bench-Aero/CLAIMS.md` 与 `feagpt_repro/reports/` 下的 artifact 为准 ——
> 数字抄在文档里必然漂，所以这里只给指针。

## 5 分钟上手

```bash
git clone https://github.com/midknightwang-beep/FEM-Bench-Aero.git repo
cd repo/feagpt_repro
"$PY" score_baseline.py          # 复算 L3 成绩单（零第三方依赖，不需要求解器）
```

（`"$PY"` 换成你的 Python 可执行文件；Windows 上建议用项目 venv。）

完整步骤（含数据包获取、澄清层复算、需要求解器的部分）见
**[`FEM-Bench-Aero/QUICKSTART.md`](FEM-Bench-Aero/QUICKSTART.md)**。

## 数据

算例本体（几何 / 网格 / 真值）不在 git 里，走 **GitHub Release** 分发：

> <https://github.com/midknightwang-beep/FEM-Bench-Aero/releases/tag/data-v1.0-v1.1>

| 你要跑 | 下哪个包 |
|---|---|
| headline（v6c 卷，55 题） | `FEM-Bench-Aero-v1.0-data.tar.gz` |
| 当前主卷 v7（64 题） | `FEM-Bench-Aero-v1.1-data.tar.gz` |

```bash
curl -L -O <上文 Release 页里的包地址>
cd feagpt_repro && "$PY" fetch_data.py --src <下载好的 .tar.gz 路径>
```

校验方式与**版本匹配**要求见 **[`FEM-Bench-Aero/DATA.md`](FEM-Bench-Aero/DATA.md)**。

## 目录

| 路径 | 内容 |
|---|---|
| `FEM-Bench-Aero/` | 基准定义：题面、真值、判分口径、文档 |
| `feagpt_repro/` | 复现工具链：判分器、成绩单、负控、语义自检 |
| `feagpt_repro/tasks/` | 任务清单（当前卷 + 历史卷） |
| `feagpt_repro/reports/` | 官方 artifact：成绩单、桥接表、诊断记录 |
| `feagpt_repro/candidates_*/` | 各模型在各卷上的候选输出（评测记录） |

> 仓库根目录另有一批**项目过程文档**（各轮复评、汇报材料、临时快照），与基准本身无关，可忽略 ——
> 读基准请从上表那两个目录进。

## 文档地图

| 文档 | 读它做什么 |
|---|---|
| [`QUICKSTART.md`](FEM-Bench-Aero/QUICKSTART.md) | 从零复现一个成绩，5 分钟 |
| [`DATA.md`](FEM-Bench-Aero/DATA.md) | 数据包获取、校验、版本匹配 |
| [`RUBRIC.md`](FEM-Bench-Aero/RUBRIC.md) | 判分口径、红线规则、版本演进 |
| [`CLAIMS.md`](FEM-Bench-Aero/CLAIMS.md) | 每条对外结论 + 对应 artifact + 复现命令 |
| [`dataset_card.md`](FEM-Bench-Aero/dataset_card.md) | 数据集卡片：规模、覆盖、已知偏差 |
| [`MANIFEST.md`](FEM-Bench-Aero/MANIFEST.md) | 文件清单与摘要 |

## 许可

- **代码**（脚本、工具链）：MIT，见 [`LICENSE`](LICENSE)
- **数据与评测材料**（算例、真值、成绩单）：CC BY 4.0，见 [`LICENSE-DATA`](LICENSE-DATA)

## 引用

```bibtex
@misc{fembenchaero,
  title  = {FEM-Bench-Aero: a reproducible benchmark for LLM-driven aircraft structural FE modeling},
  author = {FEM-Bench-Aero contributors},
  year   = {2026},
  note   = {Code: MIT; Data: CC BY 4.0}
}
```

## 已知限制

存在若干已登记的口径边界与未解问题（例如分层面板类算例的角色缺陷、`package-lock.json`
未入库导致依赖树不能逐字节复现、`latest_scorecard` 按 `mtime` 选对象）。这些**写在文档里
而不是藏起来**：见 `FEM-Bench-Aero/DATA.md` 的「已知问题」与
`FEM-Bench-Aero/ROADMAP.md` 的「已证伪路线」。

> **行尾问题已解决**（2026-10-31 / T-D3）：仓库用 `.gitattributes` 统一 CRLF，
> 干净 clone 后 1550 个文件逐字节一致。此前「行尾会让 sha 锚点对不上」的说法不再成立。
