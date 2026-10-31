# T-F2 契约：`package-lock.json` 入库（消除「规则与事实矛盾」）

> 立项时间：2026-10-31 21:2x
> 依据：`ROADMAP.md` §13 原第 1 位（D4 最后一个缺口）
> 拍板人：老王（2026-10-31 21:20，「继续下一步，package-lock.json 入库」）

## 0. 立项时的事实（现场实测，不是假设）

| 事实 | 实测值 |
|---|---|
| 主仓是否已追踪 `feagpt_repro/package-lock.json` | **是**（blob `2cc9a35c`，与磁盘一致） |
| `.gitignore` 是否仍写着忽略它 | **是**（第 58 行，来自 `98acf48` W4b-2） |
| 公开快照里是否含它 | 磁盘**有**（2958 B）、`git ls-files` **0**（被 `.gitignore` 挡住） |
| lock 锁的依赖 | 6 个，全部走 `registry.npmjs.org`（外部可装，非私有 registry） |

⇒ **F-2 不是「文件没入库」，而是「规则与事实自相矛盾」**：主仓靠历史遗留侥幸追踪着，
但只要有人做一次「清理（`git rm --cached` + 按 `.gitignore` 重加）」或按快照重建仓库，
它就会**静默消失**，而没有任何闸会报。

## 1. 只改什么（allowlist）

| 文件 | 动作 |
|---|---|
| `.gitignore` | 删掉 `feagpt_repro/package-lock.json` 一行，换成两行注释说明「必须入库」 |
| `feagpt_repro/_d4_public_set.py` | 新增判据 **P7**（快照做成的库必须能纳入全部文件）+ 自检两向 |
| `feagpt_repro/reports/diagnostics/task_f2_{contract,report}.md` | 新建 |
| `FEM-Bench-Aero/ROADMAP.md` | §13 的 F-2 行退出、新增 F-7、版本历史 |
| `feagpt_repro/reports/diagnostics/public_manifest.json` | 随 emit 重建 |

**不改**：`package.json` 的依赖集合、`package-lock.json` 内容本身、任何成绩单 / claim 数字 /
rubric / 考卷 / `check_claims.py` / `negative_controls.py`（本轮两道闸代码零改动）。

## 2. 验收什么

| # | 验收项 | 判据 |
|---|---|---|
| V1 | **修复前必须能红**（双向对照） | 用 `HEAD:.gitignore`（旧）与工作区（新）各建一个空库 `git add -A`：旧 = **2** 个文件（缺 lock），新 = **3** 个（含 lock） |
| V2 | 公开快照做成的库不缺文件 | 快照副本 `git init && git add -A`：`ls-files` 数 == 磁盘文件数（**1121 == 1121**） |
| V3 | P7 自检 | `_d4_public_set.py --self-test` **7/7**、`rc=0`；含「挡文件须红」与「不挡须绿」两向 |
| V4 | P7 在真实快照上绿 | `--check` 报 `P7 ok：1121 个文件全部可被新库纳入` |
| V5 | 闸不退化 | 负控 **69/69**；claims **33/68/61** 全过（连跑两次） |
| V6 | 主仓没被误伤 | `git ls-files` 里仍有 `feagpt_repro/package-lock.json`；`git check-ignore` 返回 **1**（不忽略） |

## 3. 停止条件

出现任一即停，不边做边修：负控或 claims 转红、P7 在真实快照上红且原因不是「规则矛盾」、
需要改动 `package-lock.json` 内容、需要新增依赖。

## 4. 明确不做（留给后面的单子）

- **不动 `.gitattributes`**。本轮实测发现它被 `classify()` 判成「根目录内部材料」而**不进公开集**
  ⇒ 第三方 clone 公开库后拿不到行尾规则，D3 的成果在公开库侧失效。**登记为 F-7，单独立项**
  （它要改 `classify()` 白名单，属于 D4 判据面，与 F-2 不是同一条变量）。
- 不重跑任何模型，不动任何成绩 / 分母 / headline。
