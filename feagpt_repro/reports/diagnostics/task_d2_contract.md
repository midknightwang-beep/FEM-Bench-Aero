# T-D2 契约：数据包下载地址 + SHA256 清单

> 立项时间：2026-10-31 20:2x
> 依据：`ROADMAP.md` §13 原第 1 位（D 段唯一硬阻断）
> 拍板人：老王（2026-10-31 20:2x，选项「v1.0 + v1.1 各一份」）

## 1. 只改什么（allowlist）

| 文件 | 动作 |
|---|---|
| `FEM-Bench-Aero/DATA.md` | §2 获取方式改直链、§3.1 改 `sha256sum -c`、§5 补 v1.1、§6/§6.1 修掉过期表述 |
| `FEM-Bench-Aero/QUICKSTART.md` | §1 改直接 clone、§2 改 Release 双包、§6 三行过期项 |
| `FEM-Bench-Aero/ROADMAP.md` | §1 看板、§6 的 D2 行、§13 排序、版本历史 |
| `feagpt_repro/reports/diagnostics/data_pack_volume_gap.json` | 覆盖为 **v1.1 包**口径 |
| `feagpt_repro/reports/diagnostics/task_d2_{contract,report}.md` | 新建 |
| GitHub Release `data-v1.0-v1.1` | 3 个资产（v1.0 / v1.1 / SHA256SUMS.txt） |

**不改**：`modeling/` 内容、任何成绩单、任何 claim 数字、rubric、考卷、判据代码（`check_claims.py` / `negative_controls.py` 本轮零改动）。

## 2. 验收什么

| # | 验收项 | 判据 |
|---|---|---|
| V1 | 包指纹与 `DATA.md` 记录一致 | `sha256sum` 现算 == `8cec47ce…` |
| V2 | 包内容完整 | 解包后 384/384 文件与仓库磁盘逐字节相同；`n_cases` 与目录数相等 |
| V3 | v1.1 ⊃ v1.0 | 差集只有 9 条新增，反向 0 缺失 |
| V4 | 三个资产状态 | API 返回 `state=uploaded` |
| V5 | **匿名可下载**（最关键） | 不带任何 `Authorization` 头下载成功，sha256 逐个命中 |
| V6 | 清单自洽 | 用**下载来的** `SHA256SUMS.txt` 跑 `sha256sum -c`，rc=0 |
| V7 | 按文档能落地 | 干净 clone 里 `fetch_data.py --src <下载的包>` rc=0，条数 == manifest |
| V8 | 闸不退化 | 负控 69/69；claims 33/68/61 全过（连跑两次） |

## 3. 停止条件

- 出现任一：包指纹对不上、匿名下载失败、`fetch_data` 条数 ≠ manifest、负控或 claims 转红、需要改动判据代码才能过。
- 停下来的动作：不回滚已上传资产（Release 可留可删，由老王定），写报告说明卡在哪一步、证据是什么。

## 4. 明确不做

- 不重新打 v1.0 包（它的指纹已被历史记录引用）。
- 不把 `modeling/` 放进 git（236/276 MB，超仓库设计意图）。
- 不动 `package-lock.json`（F-2，独立任务）。
- 不改 F-5（`latest_scorecard` 时间耦合，独立任务）。
