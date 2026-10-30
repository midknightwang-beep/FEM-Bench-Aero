# TASK_CONTRACT — T-C1（档 1 分发与文档 + 档 3 D-6 前置闸实质化）

> 依 `AGENTS.md` R-A1/A3/A11/R59/R67/R69。本合同在动手前写定，执行中不改；要改先写 `CONFLICT.md`。

## 1. 单变量

**两个互不干扰的子任务，各自单变量：**

| 子任务 | 单变量 | 明确不动 |
|---|---|---|
| **C1a 档 1（分发与文档）** | 只新增/修改**文档与分发脚本** | 不动任何 `.py` 判据、不动任何 artifact、不动任何数字 |
| **C1b 档 3 D-6（前置闸）** | 只改 `evaluate.require_dataset` 的**检查深度** | 不动任何判据口径、不动任务卷、不动候选、不动分数 |

## 2. 起点（T-B1，`661b752`）已实测的缺陷

| 编号 | 缺陷 | 实测证据 |
|---|---|---|
| D-1 | `git remote -v` 为空，第三方无法 clone | 空输出 |
| D-2 | 数据包无分发渠道；`fetch_data.py` 用法示例是作者本机绝对路径 | `F:/FEA_Archive_20261024/…` 出现在 docstring |
| D-5 | 数据包 55 条 vs v7 卷 64 条；`fetch_data` 只跟数据包自己的 manifest 对账，无跨卷交叉闸 | `fetch_data` 输出 55 条通过 |
| **D-6** | **空 `modeling/` 目录骗过 `require_dataset`（只 `isdir` 检查）⇒ 静默产出 `exam TSR 3/25 (12.0%)` 假成绩，无任何警告** | clone 里 `mkdir modeling` 后实跑 |

## 3. 本轮要做的（范围写死）

### C1a 档 1 —— 让「别人拿得到、拿得到之后知道自己在拿什么」
1. 新增 `FEM-Bench-Aero/QUICKSTART.md`：**5 分钟上手**，从零到看到 headline，全程只写**相对路径与占位符**，不写作者本机路径。
2. 新增 `FEM-Bench-Aero/DATA.md`：数据包的获取与校验口径 —— 包内容、sha256 核对方法、**55 vs 64 的差异必须写明**（v6c 卷 55 条全覆盖；v7 卷 64 条缺 9 条），以及缺数据时的正确失败形态。
3. `README.md` 顶部加一行指向 `QUICKSTART.md`（不改已有内容与数字）。
4. 生成**可分发的仓库快照**：`git bundle`（`_handoff/`，gitignore）—— 这是**在没有远端服务器时唯一能让第三方拿到完整历史的手段**，同时给出「一键建远端并推送」的命令清单。
5. **不做**：不擅自创建远端（无凭据、且属老王决策），不清理 `.workbuddy/memory`（D-10，改索引风险与 D-3 同级，另立）。

### C1b 档 3 D-6 —— 前置闸从「查目录存在」改成「查数据在」
`evaluate.require_dataset(fea=None, expect_ids=None)` 三级：
1. `modeling/` 必须是目录（保留原行为与原文案）；
2. **新**：`modeling/*/spec.json` 实际数量必须 > 0 —— 挡空目录 / 挡解包失败 / 挡解到别处；
3. **新**：给了 `expect_ids`（任务卷的 task_id 列表）时，逐条要求 `modeling/<case_id>/spec.json` 存在；缺失时**报出缺失条数与样例**（不得只说「不全」）。

三处真实调用点（`score_baseline` / `msr_l3` / `r32_audit`）传 `expect_ids`；`negative_controls` 的 NC-26 保持位置参数调用（`fea` 仍是第一参数）。

## 4. 验收标准（全部实测，不许推算）

| # | 验收项 | 判据 |
|---|---|---|
| V1 | **零数字变化** | 重跑 `score_baseline`（v6c×glm_p2 与 v7×glm/ds）后与入库 artifact **逐叶子比对：改动 0、删除 0**，新增只允许 provenance 里的闸字段 |
| V2 | **空目录必红** | 在 clone 里 `mkdir modeling` ⇒ `require_dataset` 返回错误串、`rc=2`（不是 0） |
| V3 | **不全必红** | 造一个只有 5 条 spec.json 的 modeling ⇒ 报「缺 N 条」并给样例 |
| V4 | **本机不误报** | 本机 v7（64/64）、v6c（55/55）覆盖率 100%，三道闸全绿 |
| V5 | **新闸可被证伪** | 新增 **NC-67 四向**（空目录 / 目录非空但无 spec / 覆盖率不足 / 正常不误报），每向断言**红的原因对**（R69） |
| V6 | **第三方可见文案里零本机路径** | `grep -rn 'F:/' QUICKSTART.md DATA.md` 为空；`fetch_data.py` docstring 的示例改为占位符（仅文案，不改逻辑） |
| V7 | **收口** | R59 顺序：负控 → `check_claims`，全绿 |

## 5. 停止条件（R-A11）

出现以下任一即停，给三选项，不自行决定：
- V1 出现任何数字变化；
- V3 修法要求改任务卷或改判据口径；
- 需要真正创建远端仓库或上传数据包（缺凭据 / 属老王决策）；
- 发现 D-3（行尾）与 D-6 修法耦合。

## 6. post-hoc？

**否**。本轮不动任何分数、不新增/修改 claim 的数字。若 V1 出现数字变化即视为违反单变量，按 §5 停止。
