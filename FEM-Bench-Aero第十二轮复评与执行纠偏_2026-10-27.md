# FEM-Bench-Aero 第十二轮复评与执行纠偏（T-A2/T-A3 + v1.1 数据层后）

> **复评日期**：2026-10-27（第十二轮）
> **复评对象**：T-A2（N-1..N-5 文本纠偏，`dc6f60e`）、T-A3（gate 读 INDEX，S-44/NC-49，`de006f2`）、v1.1 数据扩量（55→64，`efb39c1`）及其收口状态
> **复评方式**：只读核对 + 官方 artifact 交叉检查（`check_claims` 27/49/45、负控 51/51、INDEX/AGENTS/CLAUDE、`RUBRIC` v5.2、`DATASET_V11`、`manifest` 64、`verify_dataset`）；**除本文件外未改动任何项目文件**
> **结论先行**：
> **T-A2/T-A3 把第十一轮的 5 条 N 全部收口了，而且 gate 现在真的读 INDEX：S-44 检查 headline 指向 + 负控编号，NC-49 四向，负控 50→51，语义 44→45，`RUBRIC` v5.1→v5.2（R58）。** 当前 live：**27 claims / 49 artifacts / 45 semantic；负控 51/51；INDEX 51；R1–R41 在 CLAIMS、R42–R58 在 RUBRIC**。这一轮协议侧是干净的。
> **但项目已经进入“数据层 v1.1”而尚未收口：** 数据集 **55→64**，test **13→22**，9 条新案例 **7/7 严格内插 PASS**、网格/节点/gate 4/eval_dataset/dedup 全过；但 **9 条只有 ccx、缺 Abaqus 双码**（`verify_dataset: 55 paired + 9 modeling-only -> MISMATCH`），**`check_forms` 未完成**（本轮被 kill，且审计自己承认并行跑过 ccx），**v7 考卷未开**（exam 仍 25，9 条新案例未进任务层）。
> **另有 3 个 P2：** ① T-A3 收口顺序反了——`check_claims.json` 22:18:28 写在 `negative_controls_51.json` 22:19:45 之前，与 T-A2 新写的“先负控后 check_claims”冲突，官方 JSON 的 mtime 记录是旧的（内容/sha 未变）；② `verify_dataset` 用系统 python 会 `No module named numpy`，必须用项目 venv（R16）；③ `check_forms` 并行 ccx 是“绝不并行 ccx”红线的违反，虽本次标量逐位相同，但过程不合规。
> **判定：协议侧 Go（T-A2/T-A3 收口）；数据侧先补 v1.1 的 Abaqus 9 条 + check_forms 串行，再开 v7；v7 是下一轮主任务，且 C-032 的 23/25 在换卷后不再可比（R30/R39）。评分 29/30。**

---

## 目录

- [0. 复评摘要](#0-复评摘要)
- [1. 变化与交付](#1-变化与交付)
- [2. 已验证的改进（credit）](#2-已验证的改进credit)
- [3. 剩余问题](#3-剩余问题)
- [4. v1.1 收口与 v7 准入](#4-v11-收口与-v7-准入)
- [5. 下一步任务执行建议](#5-下一步任务执行建议)
- [6. 防跑偏机制（R59–R61 建议）](#6-防跑偏机制r59r61-建议)
- [7. 评分卡](#7-评分卡)
- [8. 待拍板](#8-待拍板)
- [附录 A　证据索引与复现命令](#附录-a证据索引与复现命令)
- [附录 B　v1.1 数据层现状](#附录-bv11-数据层现状)
- [附录 C　第十一轮 P1 逐项判定](#附录-c第十一轮-p1-逐项判定)
- [附录 D　文档/口径漂移清单](#附录-d文档口径漂移清单)

---

## 0. 复评摘要

### 0.1 三句话结论

1. **T-A2/T-A3 收口干净。** N-1..N-5 全改；gate 现在实读 `INDEX.md`（S-44：headline 3 条命中、显式历史 2 条、越权 0 条；L24 主区间 `NC-23..49` / 总数 51；artifact 最大 NC-49、共 51 条）；NC-49 四向；负控 **51/51**；语义 **45**；`RUBRIC` v5.2（R58）；`AGENTS.md`/`CLAUDE.md` 已同步 27/49/45、51/51；pre-flight 用 `--json "$TEMP/..."`，不再弄脏官方 JSON。
2. **v1.1 数据层已到 64 条，但没收口。** 9 条新案例：7 条单轴严格夹逼 PASS，2 条双轴只报；网格 9/9（minJ 0.506–0.637，tri3=0）、节点 9/9 未越线（最大 143,702）、gate 4 9/9、eval_dataset PASS、dedup 0、内插物理 7/7。**但 9 条只有 ccx，Abaqus 双码没跑**（`verify_dataset: 55 paired + 9 modeling-only -> MISMATCH`），`check_forms` 未完成，**v7 未开**（exam 仍 25）。
3. **三个 P2：** T-A3 收口顺序 `check_claims` 先于 `negative_controls`（与“先负控后 check_claims”冲突；内容/sha 未变，mtime 旧）；`verify_dataset` 系统 python 缺 numpy、必须用项目 venv；`check_forms` 并行 ccx 违反“绝不并行 ccx”。**协议侧 Go；数据侧先补 v1.1，再开 v7。**

### 0.2 执行总评

| 工作块 | 评分 | 一句话判断 |
|---|---|---|
| T-A2：N-1..N-5 文本纠偏 | **A** | 5 条全 A；INDEX/AGENTS/CLAUDE 同步；pre-flight `--json` 临时路径；`⓪-hist`/`⓪b` 历史标记 |
| T-A3：gate 读 INDEX | **A** | S-44/NC-49；51/51；45 语义；R58；负控 50→51；`check_claims.py` 增 `index_consistency` |
| v1.1 数据层 | **B+** | 55→64；7/7 严格内插；网格/节点/gate 4/eval/dedup 全过；**9 条 Abaqus + check_forms 未完成** |
| 收口纪律 | **B** | T-A3 顺序反了（check 先于负控）；`check_forms` 并行 ccx；`verify_dataset` 系统 python |
| **总体** | **A− / 29/30** | 协议 A；数据层 B+；**v1.1 收口 + v7 是下一轮全部内容** |

> **和第十一轮 29/30 的关系**：T-A2/T-A3 收口（+0.5），v1.1 数据层 64 + 7/7（+0.5），但 9 Abaqus/check_forms 未完成、T-A3 顺序/并行 ccx/venv（−1），净持平 ⇒ 29/30。

---

## 1. 变化与交付

### 1.1 提交

| commit | 时间 | 内容 |
|---|---|---|
| `dc6f60e` | 22:06 | T-A2：协议与 INDEX 文本纠偏（N-1..N-5 全 A + N-5 用 C+） |
| `de006f2` | 22:18 | T-A3：让 gate 读 INDEX（S-44 / R58）+ NC-49 四向（RUBRIC v5.2） |
| `a4787a3` | 22:20 | memory：T-A2/T-A3 记录 + 两条通用坑 |

**HEAD**：`a4787a3`；工作区 clean。

### 1.2 新增/修改的关键文件

| 文件 | 作用 |
|---|---|
| `feagpt_repro/check_claims.py` | 增 `index_consistency` / `_latest_nc_json`；S-44；45 语义 |
| `feagpt_repro/negative_controls.py` | 增 NC-49 四向；负控 50→51 |
| `feagpt_repro/reports/negative_controls_51.json` | 当前 51/51 |
| `feagpt_repro/reports/check_claims.json` | 27 claims / 49 artifacts / 45 semantic 全过 |
| `feagpt_repro/reports/INDEX.md` | ⓪ 前置闸；⓪-hist C-029；⓪b C-031；L24 NC-23..49/51；当前 C-032 |
| `FEM-Bench-Aero/RUBRIC.md` | v5.2：R58（官方导航必须被 gate 读）+ S-44/NC-49 |
| `FEM-Bench-Aero/CLAIMS.md` | R1–R58 红线条；C-019 51/51；C-032/C-033 当前 |
| `AGENTS.md` / `CLAUDE.md` | 27/49/45、51/51；pre-flight `--json` 临时路径；先负控后 check_claims；R1–R41 在 CLAIMS / R42–R58 在 RUBRIC；R-A7 以 status 列为准 |
| `FEM-Bench-Aero/DATASET_V11.md` | v1.1 数据层：64 条；9 条新案例；7/7；Abaqus/check_forms 待办 |
| `feagpt_repro/_v11/` | 9 条 spec、ccx runs、Abaqus deck、`run_v11_abaqus.bat` |
| `feagpt_repro/reports/archive/` | 旧负控 31/37/39/41/44/48/49 归档 |

### 1.3 当前 SOT（live）

| 项 | 值 |
|---|---|
| 唯一 headline | **C-032**（`baseline_scorecard_L3_v6c_p2.json`，glm-5.3-flash，prompt v2，exam 23/25 92.0%） |
| supporting | **C-033**（`baseline_scorecard_L3_v6c_ds_p2.json`，deepseek-v4-pro，exam 22/25 88.0%） |
| 历史 | C-029/C-031（prompt v1）、C-028（v6b）、C-021（v4） |
| W5d | C-034 榜单；C-035 prompt v3/v3b 否决、回退 v2 |
| 当前 paper | `reports/papers/tasks_v6c.jsonl`，sha `9c1faa3a…`；**55 条 L3 / exam 25** |
| 当前 prompt | `gen_candidates_v2.js`，sha `ce225186…`（v2） |
| 当前 rubric | **v5.2（R42–R58 在 RUBRIC；R1–R41 在 CLAIMS）** |
| 门禁 | 负控 **51/51**；`check_claims` **27/49/45** |
| 数据集 | **64 条（manifest：train 25 / val 17 / test 22；63 类；xval 55）** |
| 数据层待办 | **9 条 Abaqus 双码未跑**；`check_forms` 未完成；v7 未开 |

---

## 2. 已验证的改进（credit）

| 改进 | 实测 |
|---|---|
| **N-1 导航** | INDEX L12 = C-032；L49 = “⓪ 前置闸（与 headline 无关）”；⓪-hist C-029、⓪b C-031 明标 historical；当前 C-032 块保留 |
| **N-2 负控编号** | L24 = `NC-23..49` / 51；S-44 实读 artifact 最大 NC-49、共 51 |
| **N-3 红线归属** | AGENTS §0 row 2 = R42–R58；R1–R41 指 `CLAIMS.md` 红线条；§7 同 |
| **N-4 status 列** | R-A7 补“以 status 列（S-29）为准，正文提及不算” |
| **N-5 pre-flight** | `check_claims.py --json "$TEMP/check_claims_preflight.json"`；官方 JSON 只在收口写；先负控后 check_claims（规则已写） |
| **S-44 / NC-49** | gate 读 INDEX：headline 3 命中 / 历史 2 / 越权 0；L24 51；NC-49 四向；负控 51/51 |
| **R58** | 被 §0 指定为必读的数据类 SOT 必须至少被一条语义检查实读；`AGENTS`/`CLAUDE` 由 §7 声明兜底 |
| **v1.1 数据** | 55→64；test 13→22；9 条新案例；7/7 严格单轴夹逼；2 条双轴只报；网格 9/9（minJ 0.506–0.637，tri3=0）；节点 9/9（最大 143,702）；gate 4 9/9；eval_dataset PASS（含 D12）；dedup 0；内插物理 7/7 |
| **v1.1 设计** | `extra.split_tag = "v11_interior_holdout"` 声明式划分；train/val 一条没动；`manifest` 25/17/22 |
| **自审** | `DATASET_V11` §5.2 主动记录三个坑：tag 写成键、锚点不存在、并行 ccx；`check_forms` 未完成如实标 |

---

## 3. 剩余问题

### 3.1 P1：v1.1 的 9 条 Abaqus 双码未跑，`verify_dataset` 仍 CHECK

- `verify_dataset --root ../FEM-Bench-Aero`（项目 venv）：
  ```
  === pairing: 55 paired, 9 modeling-only, 0 xval-only -> MISMATCH
  === cross-tree mesh agreement: 55/55 identical -> PASS
  case consistency: 119/119 OK
  VERDICT: CHECK
  ```
- 9 条新案例只有 ccx 侧；`_v11/runs_abaqus/` 有 9 个 deck；`run_v11_abaqus.bat` 必须在 **WorkBuddy 之外的普通 cmd** 跑（沙箱注入 `tsbx.dll` ⇒ `pre.exe` `__fastfail`）。
- 未跑双码 ⇒ gate 3 未过 ⇒ 数据集仍是 `55 paired + 9 modeling-only`，**v1.1 数据层未收口**；v7 不能建在这 9 条上。
- **建议**：P0，先在外部 cmd 跑 9 条 Abaqus；`verify_dataset` 必须 `64 paired / VERDICT: PASS`。

### 3.2 P1：`check_forms` 未完成，且本轮并行跑过 ccx

- `DATASET_V11` §4：`check_forms` 跑到 10 分钟无输出被终止，**未完成**；§5.2 承认 `check_forms` 还在跑时起了柱壳 ccx。
- 事后单独重算该条标量与首次**逐位相同**（差异项 0）⇒ 本次未造成污染；但 **“绝不并行 ccx”是环境铁律**，不能以“结果相同”作为许可。
- **建议**：P0，`check_forms.py` 串行重跑一次（用项目 venv，串行，不与其他 ccx 并行）；9 条必须 `PASS`；这是 v7 的前置。

### 3.3 P1：v7 未开，9 条新案例未进任务层

- `DATASET_V11` §5.1 第 3 条：v7 把 9 条接进任务层 ⇒ **exam 25 → 34**；换卷后 **C-032 的 23/25 不再可比**（paper sha 变，R30/R39）；必须重生成两模型候选（约 2×15 min）+ 全链 MSR（约 2×40 min）+ CI/榜单。
- 当前 `tasks_v6c.jsonl` 仍 55 条；`papers/` 没有 v7；`candidates` 没有 v7。
- **建议**：P1，v7 是下一轮主任务；按 R-A1 拆成 **v7 paper**（单变量=paper）与 **v7 candidates**（单变量=candidates）两个 `TASK_CONTRACT`；先 paper 后 candidates；C-032/C-033 在 v7 落地后标 historical。

### 3.4 P2：T-A3 收口顺序反了（check_claims 先于 negative_controls）

- `check_claims.json` mtime **22:18:28**；`negative_controls_51.json` mtime **22:19:45**；`check_claims` 的 `results` 里 C-019 artifact 的 mtime 是 1793110682（22:18），当前文件 22:19；`sha256`/内容未变，S-04 51/51 通过。
- 但 T-A2 新写的规则是 **“先 `negative_controls.py` → 后 `check_claims.py`”**；T-A3 实际反了，官方 `check_claims.json` 的 mtime 记录是旧的。功能上无害，**规则上不合规**；若不修，下一轮会有人按“先 check”继续。
- **建议**：P2，下一次收口按“负控 → check_claims”重跑一次；或在 `AGENTS` C3 明确“收口顺序 = 负控 → check”；`check_claims` 的 mtime 差异属 N-5 同类，不夹带。

### 3.5 P2：`verify_dataset` 用系统 python 缺 numpy，必须用项目 venv

- 复评时我先用系统 `python verify_dataset.py`，报 `ModuleNotFoundError: No module named 'numpy'`；换项目 venv 后正常输出 `55 paired + 9 modeling-only`。
- 这不是数据失败，是 **R16 环境预检**：`verify_dataset`/`check_forms`/`score_baseline`/`msr_l3` 必须用 `C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe`；`check_claims`/`negative_controls` 可用系统 python。
- **建议**：P2，在 `AGENTS.md` §0/`CLAUDE.md` 明确“dataset checks 用 venv”；pre-flight 的 `check_claims`/negative 不受影响。

### 3.6 P2：`check_claims` 的 mtime / `--no-write` follow-up

- pre-flight 已用 `--json "$TEMP/..."`，工作区不再被 pre-flight 弄脏；官方 `check_claims.json` 只在收口写。
- N-5 的 A（去掉 `mtime` 或加 `--no-write`）仍是可选 follow-up；`mtime` 有 provenance 价值，`--no-write` 更稳；单列任务，不夹带。

### 3.7 P2：v1.1 自审的三个坑

- `DATASET_V11` §5.2：① `extra.v11_interior_holdout = true` 是键，谓词读 `extra.split_tag` 的值 ⇒ 9 条先被族谓词分进 train/val；② 柱壳锚点 `d1800_l1600` 不存在，改 `d2000_l1800`；③ `check_forms` 并行 ccx。
- 前两条是“写端/读端/锚点”的实现坑，已修；第三条是过程违规（3.2）。
- **建议**：P2，v1.1 的 `TASK_CONTRACT` 把“写端/读端各跑一遍、锚点必须存在、ccx 串行”写进验收；不新增红线条，只作为任务合同。

### 3.8 P2：C-032/C-033 的 v7 状态

- v7 落地后，C-032 的 23/25 是 v6c 口径；v7 的 34 条 exam 是新口径；S-29 只能有一个 headline；C-032/C-033 必须标 `historical`/`supporting`，v7 新成绩单成为新 headline（C-036+）。
- **建议**：P2，v7 paper 冻结时同步写 `replace` 关系；`INDEX`/`README`/`CLAIMS` 的 current headline 切到 v7；C-032/C-033 保留为 v6c 历史。

### 3.9 不是问题的部分（避免过度纠偏）

- T-A2/T-A3 的 5 条收口、S-44/NC-49、51/51、27/49/45、R58、`RUBRIC` v5.2、INDEX/AGENTS/CLAUDE 同步、pre-flight `--json` 临时路径、`archive/` 归档——都是真的，不需要重做。
- v1.1 数据层的 7/7 严格内插、2 条双轴只报、网格/节点/gate 4/eval/dedup 全过——数据质量本身没问题；缺的是 Abaqus 和 check_forms。
- C-032/C-033 的 23/25、22/25 仍是 v6c 的有效成绩；v7 不是“修 C-032”，是新卷。

---

## 4. v1.1 收口与 v7 准入

### 4.1 准入门槛

| 条件 | 现状 | 结论 |
|---|---|---|
| 64 条数据层 | manifest 64 / 63 类 / 25-17-22 | ✅ |
| 9 条新案例语义/网格/节点 | 9/9；9/9；9/9 | ✅ |
| 内插物理 | 7/7 strict；2 双轴只报 | ✅ |
| Abaqus 双码 | **9 条 modeling-only** | ❌ P0 |
| `check_forms` | **未完成** | ❌ P0 |
| `verify_dataset` | **55 paired + 9 modeling-only -> CHECK** | ❌ P0 |
| v7 paper | **未开** | ⏳ P1 |
| v7 candidates | **未开** | ⏳ P1 |

**判定：v1.1 数据层“设计/质量”已成立，“双码/check_forms”未收口；v7 不能建在未收口的 9 条上。**

### 4.2 v7 的顺序

```text
① 9 条 Abaqus（外部 cmd） ──► verify_dataset 64 paired / PASS
② check_forms 串行 ─────────► 9 条 PASS
③ v7 paper（单变量=paper）──► tasks_v7 / exam 34 / freeze / sha
④ v7 candidates（单变量=candidates）──► 两模型 × 64/34；MSR；CI；榜单
⑤ C-032/C-033 → historical；v7 新 headline（C-036+）
```

**为什么不能先 v7**：9 条没有 Abaqus 双码，gate 3 未过；`check_forms` 未完成，结构形式未验证；把未收口的 9 条接进 v7，会把数据缺陷带进新 headline，且 C-032 23/25 一旦换卷就不可比。

---

## 5. 下一步任务执行建议

### 5.1 任务表

| ID | 优先级 | 做什么 | 验收 | 证据 |
|---|---|---|---|---|
| **v1.1-Abaqus** | **P0** | 在 WorkBuddy 外的普通 cmd 跑 `_v11\run_v11_abaqus.bat`；9 条双码 | `verify_dataset` = 64 paired / VERDICT PASS；gate 3 9/9 | `_v11/runs_abaqus/`；`_xval/` 9 个新目录 |
| **v1.1-forms** | **P0** | `check_forms.py` 串行重跑（项目 venv；不与其他 ccx 并行） | 9 条 PASS；日志完整 | `DATASET_V11` §4；`check_forms` 日志 |
| **v1.1-close** | **P0** | `verify_dataset` + `eval_dataset` + `dedup` + `gate 4` 全绿；`DATASET_V11` 标 PASS | 64 paired；0 重复；D12 PASS | `DATASET_V11` |
| **v7-paper** | **P1** | 9 条接进任务层；`tasks_v7` / exam 25→34；冻结 sha；C-032/C-033 标 historical | paper freeze；S-29 唯一 headline 切 v7；`TASK_CONTRACT` 单变量=paper | 新 `papers/tasks_v7.jsonl`；C-036 |
| **v7-cand** | **P1** | 两模型 × v7；同 prompt v2；同 ≤3 轮；MSR；CI；榜单 | 两模型同卷同 prompt；C-032 23/25 不可比（R30/R39）；新 headline | 新 scorecard/CI；C-037 |
| **T-A3-order** | **P2** | 下一次收口按“负控 → check_claims”重跑；官方 JSON 的 mtime 与 negative 对齐 | `check_claims` 27/49/45；51/51；mtime 顺序正确 | `check_claims.json`；`AGENTS` C3 |
| **venv** | **P2** | `AGENTS.md` §0/`CLAUDE.md` 明确 dataset checks 用项目 venv | `verify_dataset`/`check_forms`/`score`/`msr` 用 venv | `AGENTS`/`CLAUDE` |
| **check_claims A** | **P2** | 去 `mtime` 或加 `--no-write`（单列任务） | pre-flight 不写官方；收口写一次 | `check_claims.py` |
| **C-032/C-033 状态** | **P2** | v7 落地后标 historical/supporting；current headline 切 v7 | S-29 唯一；INDEX/README/CLAIMS 同步 | `CLAIMS`/`INDEX` |

### 5.2 顺序与成本

- v1.1-Abaqus：外部 cmd，9 条；取决于机器，通常 10–30 分钟。
- v1.1-forms：串行，约 10–20 分钟。
- v1.1-close：几分钟。
- v7-paper：0.5–1 天（9 条 NL/task/冻结/核对）。
- v7-cand：两模型各 15 分钟生成 + 各 40 分钟 MSR + CI/榜单，约 2–3 小时（等）。
- **总计约 1.5–2 天到 v7 榜单。**

---

## 6. 防跑偏机制（R59–R61 建议）

> R1–R58 保留；以下为第十二轮建议新增，待拍板后写入 RUBRIC。

| 红线 | 内容 | 触发点 |
|---|---|---|
| **R59** | **收口顺序固定**：官方 `check_claims.json` 必须在 `negative_controls` 之后写；先负控后 check；mtime 顺序必须与 manifest 一致 | 下一次收口；S-45；NC-50 |
| **R60** | **dataset 检查必须用项目 venv**：`verify_dataset`/`check_forms`/`score_baseline`/`msr_l3` 不得用系统 python；缺 numpy/gmsh = env 退出，不记数据失败（R16） | v1.1-close/v7；S-46；NC-51 |
| **R61** | **ccx 绝不并行**：`check_forms`/`verify_dataset`/`score`/`msr` 的 ccx 必须串行；并行 = 该次结果无效，重跑 | `check_forms`；S-47；NC-52 |

**新增语义检查/负控建议：**

| ID | 检查 | 期望 |
|---|---|---|
| S-45 | `check_claims.json` 与 `negative_controls_*.json` 的 mtime 顺序 | check 晚于 negative |
| S-46 | `verify_dataset`/`check_forms` 的解释器 | 项目 venv；缺依赖 rc=2，不记数据失败 |
| S-47 | ccx 串行证据 | 日志无并行 ccx；`check_forms` 有完整 PASS |
| NC-50..52 | 三向变异 | mtime 反序/系统 python/并行 ccx 必须被拒 |

---

## 7. 评分卡

> **第十一轮 29/30 → 第十二轮 29/30**：T-A2/T-A3 收口 +0.5，v1.1 数据层 64 +0.5；9 Abaqus/check_forms 未完成、T-A3 顺序/并行 ccx/venv −1。

| # | 维度 | 第十轮 | 第十一轮 | 第十二轮 | 依据 |
|---|---|---:|---:|---:|---|
| 1 | 目标一致性 | 3 | 3 | **3** | 评测基础设施主轴不变；v1.1/v7 按计划 |
| 2 | 任务有效性 | 3 | 3 | **3** | v6c exam 25 仍有效；v1.1 9 条数据质量 7/7；v7 未开 |
| 3 | 判分有效性 | 3 | 3 | **3** | S-44/NC-49；51/51；45；R58；R5.2 |
| 4 | 证据等级 | 2 | 3 | **3** | 27/49/45；51/51；gate 读 INDEX；`check_claims` mtime 旧是 P2 |
| 5 | 可复现性 | 3 | 3 | **3** | v1.1 `v11_interp_check`；`DATASET_V11`；`manifest` |
| 6 | 版本治理 | 3 | 3 | **3** | T-A2/T-A3；INDEX/AGENTS/CLAUDE；archive |
| 7 | 文档真实性 | 3 | 3 | **3** | `DATASET_V11` 主动记录三个坑；`check_forms` 未完成如实标 |
| 8 | 统计有效性 | 2 | 2 | **2** | v6c n=25；v7 未开；CI 仍宽 |
| 9 | 范围纪律 | 3 | 3 | **3** | T-A2 只改文本；T-A3 只加 gate；no artifact numbers |
| 10 | 计划执行 | 3 | 3 | **3** | 5 条 N 全清；v1.1 数据 64；但 9 Abaqus/check_forms 未完成 |
| **总分** | | **28/30** | **29/30** | **29/30** | 协议 A；数据层 B+；v1.1 收口 + v7 是 30 的唯一路径 |

**一句话**：**协议侧已经“有闸”；现在卡在数据侧的最后一公里——9 条 Abaqus、check_forms 串行、v7 换卷。协议不是瓶颈，数据收口才是。**

---

## 8. 待拍板

| # | 决策 | 选项 | 建议 |
|---|---|---|---|
| **D1** | **v1.1 Abaqus** | (a) 现在外部 cmd 跑 9 条；(b) 先 v7 | **(a)**；没有双码，v1.1 数据层不算收口，v7 不能建 |
| **D2** | **check_forms** | (a) 串行重跑；(b) 跳过 | **(a)**；9 条结构形式未验证，v7 前置 |
| **D3** | **v7 顺序** | (a) paper 先、candidates 后；(b) 同时 | **(a)**；R-A1 单变量；C-032 23/25 换卷后不可比 |
| **D4** | **v7 模型** | (a) 两模型同 prompt v2；(b) 只跑 glm | **(a)**；v7 是新卷，两模型都要重生成；C-033 继续 supporting |
| **D5** | **T-A3 顺序** | (a) 下次收口按负控→check 重跑；(b) 不管 | **(a)**；规则已写，顺序要守；mtime 旧是 P2 |
| **D6** | **venv** | (a) 写进 AGENTS/CLAUDE；(b) 靠记忆 | **(a)**；系统 python 缺 numpy，R16 |

---

## 附录 A　证据索引与复现命令

### A.1 官方 artifact

| 文件 | 用途 |
|---|---|
| `feagpt_repro/reports/check_claims.json` | 27/49/45；S-44 |
| `feagpt_repro/reports/negative_controls_51.json` | 51/51；NC-49 |
| `feagpt_repro/reports/INDEX.md` | C-032 headline；L24 51；⓪-hist/⓪b |
| `FEM-Bench-Aero/RUBRIC.md` | v5.2；R58 |
| `FEM-Bench-Aero/CLAIMS.md` | R1–R58；C-019 51；C-032/C-033 |
| `FEM-Bench-Aero/DATASET_V11.md` | 64 条；9 条；7/7；Abaqus/check_forms 待办 |
| `FEM-Bench-Aero/manifest.json` | 64 / 63 类 / 25-17-22 |
| `feagpt_repro/_v11/v11_interp_check.json` | 7/7 严格；2 双轴只报 |
| `feagpt_repro/_v11/runs_abaqus/` | 9 个 Abaqus deck |

### A.2 复现命令

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
SYS="python"

# 门禁（pre-flight 用临时 JSON，不写官方）
"$SYS" check_claims.py --json "$TEMP/check_claims_preflight.json"
"$SYS" negative_controls.py

# 数据层
"$PY" verify_dataset.py --root ../FEM-Bench-Aero
"$PY" eval_dataset.py --root ../FEM-Bench-Aero
"$PY" check_forms.py --root ../FEM-Bench-Aero        # 串行，勿与其他 ccx 并行

# 9 条 Abaqus（必须在 WorkBuddy 外的普通 cmd）
# _v11\run_v11_abaqus.bat

# v1.1 内插校验
"$PY" _v11/verify_v11_interpolation.py --strict
```

---

## 附录 B　v1.1 数据层现状

| 项 | 值 | 状态 |
|---|---|---|
| 数据集条数 | 55 → **64** | ✅ |
| 等价类 | 54 → **63** | ✅ |
| split | train 25 / val 17 / test 22 | ✅ |
| 9 条新案例 | 7 单轴 + 2 双轴 | ✅ |
| 内插严格夹逼 | **7/7 PASS**（`n_fail=0`） | ✅ |
| 网格 | 9/9；minJ 0.506–0.637；tri3=0 | ✅ |
| 节点上限 | 9/9；最大 143,702 < 158,548 | ✅ |
| gate 4 语义 | 9/9 | ✅ |
| `eval_dataset` | PASS（含 D12） | ✅ |
| `dedup` | 0 重复 | ✅ |
| `verify_dataset` | **55 paired + 9 modeling-only -> CHECK** | ❌ Abaqus |
| `check_forms` | **未完成** | ❌ |
| v7 考卷 | **未开** | ⏳ |

**9 条新案例**：`naca4412_wingbox_size_skin2p5`、`n_ribs6_chord1000`、`str4`、`size_chord900`、`taper070`、`open_hole_panel_400x200_d30`、`fuselage_barrel_d2000_l1800_str8_frm3`、`open_hole_panel_500x250_d45`、`stiffened_panel_700x600_str4`。前 7 条单轴严格夹逼；后 2 条双轴只报数值。

---

## 附录 C　第十一轮 P1 逐项判定

| 第十一轮 P1 | 第十二轮状态 | 证据 |
|---|---|---|
| T-A2 N-1..N-5 | ✅ | `dc6f60e`；INDEX/AGENTS/CLAUDE 同步 |
| T-A3 gate 读 INDEX | ✅ | S-44/NC-49；51/51；45；R58 |
| v1.1 数据 64 | ✅ | manifest 64；7/7；网格/节点/gate 4/eval/dedup |
| 9 条 Abaqus | ❌ | `verify_dataset: 55 paired + 9 modeling-only` |
| check_forms | ❌ | `DATASET_V11` §4 未完成；§5.2 并行 ccx |
| v7 | ⏳ | 未开；exam 仍 25 |
| T-A3 顺序 | ⚠️ | check 22:18 先于 negative 22:19 |
| venv | ⚠️ | 系统 python 缺 numpy；venv 正常 |
| check_claims mtime | ⚠️ | 官方 JSON mtime 旧；pre-flight 已用 temp |

---

## 附录 D　文档/口径漂移清单

| # | 位置 | 现文 | 应为 |
|---|---|---|---|
| 1 | `AGENTS.md` §0 | 未提 dataset checks 用 venv | 加一行“verify/check_forms/score/msr 用项目 venv”（R60） |
| 2 | `AGENTS.md` C3 | 已写“先负控后 check” | T-A3 实际顺序反了；下次收口按规则重跑 |
| 3 | `DATASET_V11` §4 | `check_forms` 未完成 | 串行重跑后标 PASS |
| 4 | `DATASET_V11` §4 | `verify_dataset` CHECK | 9 条 Abaqus 后标 PASS |
| 5 | `INDEX`/`README` | v7 未开 | v7 落地后切 headline；C-032/C-033 标 historical |
| 6 | `reports/check_claims.json` | mtime 22:18；negative 22:19 | 下次收口重跑；mtime 对齐 |

---

> **本轮只读核对；除本文件外未改动任何项目文件。**
> 下一轮复评入口：v1.1 的 Abaqus 9 条 + `check_forms` 串行 + `verify_dataset` 64 paired；之后 v7 paper/candidates。
