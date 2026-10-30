# T-D5b 任务契约：给「hook 是否已装」建判据（哨兵的哨兵）

- **任务 id**：T-D5b（ROADMAP §6 D5b）
- **日期**：2026-10-30
- **发起**：老王「现在做 D5b」

## 1. 要解决的问题

T-D5 装的 `check_commit.py` 靠 `.git/hooks/pre-commit` 触发，而 **`hook` 不入库**（`.git/` 不被追踪）。

⇒ 新 clone、换机、`git init` 重建后，**这道闸静默消失，且没有任何东西会报错** —— 因为它不运行，所以没人报错。这正是 R58 的形态（无工具读的 = 无闸），只是发生在「闸的触发器」上。

## 2. 核心判断：判据放哪

| 方案 | 优点 | 致命缺点 |
|---|---|---|
| 放进 `check_commit.py`（G7） | 零计数成本 | **hook 内恒真**（能跑说明已装）；不带 hook 时又没人跑它 ⇒ 自监督不成立 |
| **放进 `check_claims.py`（S-61）** ✅ | §0 硬规则「任一命令不全绿即停」⇒ 自动获得强制力；**不依赖 hook 本身存在** | 语义项 60→61 |
| 两者都放 | 覆盖最全 | 两处逻辑重复，改名/搬家时要改两份 |

**选 `check_claims.py` 的 S-61。** 判据实现独立成 `hook_guard.py`（可单独 `--self-test`），S-61 只做薄包装。

## 3. allowlist（精确到文件）

| 文件 | 动作 |
|---|---|
| `feagpt_repro/hook_guard.py` | 新建（判据 + 7 向自检） |
| `feagpt_repro/check_claims.py` | 新增 S-61 + `--skip-hook-guard` 开关 |
| `FEM-Bench-Aero/RUBRIC.md` | 新增 R74 + 版本行 v6.8→v6.9 |
| `AGENTS.md` / `CLAUDE.md` | 补一句「hook 已装由 S-61 守」（**不写任何计数**，R63） |
| `FEM-Bench-Aero/ROADMAP.md` | D5b → ✅ + 看板回改 |
| `reports/diagnostics/task_d5b_contract.md` / `_report.md` | 新建 |

## 4. 明确不改

- ❌ 不改 `check_commit.py` 的任何判据（G0–G6 一字不动）
- ❌ 不改任何判分口径 / 考卷 / 候选 / 成绩 / headline / 分母
- ❌ 不重跑任何模型
- ❌ 不动负控条数（**不加 NC** ⇒ C-019 的 69 链、S-44/NC-49 的循环依赖不触发）

## 5. 判据与验收

| # | 判据 | 检查法 |
|---|---|---|
| P1 | hook 缺失会红 | 隔离仓库删 hook → `hook_guard` 红，且**红的 id 是 H2** |
| P2 | hook 被换成别的会红 | 写入非本闸内容 → 红 **H3** |
| P3 | hook 指向僵尸脚本会红 | 脚本路径不存在 → 红 **H4** |
| P4 | hook 被 `core.hooksPath` 改道会红 | 设 `core.hooksPath=.husky` → 红 **H1**，且**只红 H1** |
| P5 | 非 git 环境 skip 不判红 | 普通目录 → `applicable=False`，各判据 `not_run` |
| P6 | 可执行位只在 POSIX 判 | `os.name!='posix'` 或 `core.filemode=false` ⇒ 该向标 skip 并说明原因 |
| P7 | 上游失败不级联 | H2 红时 H3/H4/H5 必须 `not_run`（NC-67 教训：两种失败给不同原因） |
| P8 | 本机实况绿 | 主仓库 `--self-test` 7/7 + S-61 实测绿 |
| P9 | 既有闸不变 | `check_claims` 其余 60 项逐项不变、负控 69/69 |

## 6. 停止条件

- 若 S-61 在**主仓库**判红而实况确实装了 hook ⇒ 停，先证明是判据错、不修改 hook 迁就。
- 若加 S-61 后 `check_claims` 出现「与本任务无关」的红 ⇒ 停，不改别的判据掩盖。
- 若必须改 `check_commit.py` 才能测通 ⇒ 停（说明判据边界划错了）。

## 7. 边界（R69：放宽必须有边界）

- **例外只有一处**：`check_claims --skip-hook-guard`，用途 = CI / 第三方只跑复现时的显式跳过。使用时 **S-61 标 skip 并计入 `n_skip`**，且必须在当次报告里写明原因 —— 与 `git commit --no-verify` 同等对待（AGENTS 已有该规范）。
- **不得自动豁免**：不通过「检测 CI 环境变量」之类的方式静默放行。
- **不得进入对外数字**：S-61 是环境完整性判据，不是成绩。

## 8. 复述

> **我只新增一条环境判据（`hook_guard.py` + S-61 + R74 + 若干文档指针），验收是 P1–P9，停止条件是「主仓库误报红」或「既有闸出现无关的红」。不改 `check_commit.py` 的判据、不改任何数字与口径、不加负控。**
