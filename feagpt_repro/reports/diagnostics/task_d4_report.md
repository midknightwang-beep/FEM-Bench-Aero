# T-D4 交付报告：公开分发集（白名单默认拒绝）

- **任务**：T-D4（ROADMAP §6 D4 → 升级为「公开集生成」）
- **日期**：2026-10-31
- **单变量**：无（不涉及 paper / prompt / rubric / candidates / 分母 / headline 六维度）
- **状态**：**P1–P9 全过**；但快照内自检 **7 红**，其中 **4 红由本任务引入** ⇒ 见 §5，需拍板

## 1. SOT（改前 / 改后）

| 项 | 改前 | 改后 |
|---|---|---|
| HEAD | `fc32af3` | `fc32af3` + 本轮提交 |
| headline | C-032（唯一） | 未动 |
| paper / prompt sha | 未动 | 未动 |
| 负控 | 69/69 | 69/69（逐数相同） |
| claims / artifacts / 语义项 | 33 / 68 / 61 | 33 / 68 / 61（逐项相同） |

## 2. 改了什么

| 文件 | 动作 |
|---|---|
| `feagpt_repro/_d4_public_set.py` | 新建：清单器 + 快照生成器（含渲染层脱敏）+ 校验器 + 5 向自检 |
| `feagpt_repro/reports/diagnostics/public_manifest.json` | 新建：1108 个文件的分发清单（可复算，含逐类计数与脱敏记录） |
| `LICENSE` | 新建：代码 MIT |
| `LICENSE-DATA` | 新建：数据 CC BY 4.0 |
| `README.md`（根） | 新建：仓库首页（零本机路径、零成绩数字，只给指针） |
| `task_d4_contract.md` / `task_d4_report.md` | 新建 |

**本机既有文件改动数 = 0**（`git status` 逐行核对，见 §4 P8）。

## 3. 公开集构成（实测）

| 类别 | 文件数 | 体积 |
|---|---|---|
| KEEP：`feagpt_repro/` 代码与证据 | 997 | 8.6 MB |
| KEEP：`FEM-Bench-Aero/` 文档与数据 | 103 | 3.5 MB |
| KEEP：根目录必需（`.gitignore`/LICENSE×2/README） | 4 | ~0 |
| KEEP：引用闭包拉回（claim artifact 在 `_probe_m14/`） | 4 | ~0 |
| **公开集合计** | **1108** | **12.1 MB** |
| 移出：探针/调试产物 | 252 | 48.3 MB |
| 移出：根目录内部材料（评审/调研/快照/看板） | 43 | 10.5 MB |
| 移出：技术设计报告 | 28 | 5.2 MB |
| 移出：汇报图表 | 22 | 5.0 MB |
| 移出：汇报幻灯 | 56 | 1.0 MB |
| 移出：内部记忆/应用（`.workbuddy/` + `.genie`） | 25 | 0.5 MB |
| **移出合计** | **429** | **70.6 MB** |

## 4. 判据逐项

| # | 判据 | 结果 | 证据 |
|---|---|---|---|
| P1 | 内部材料零残留 | ✅ | 快照 1108 个文件里 drop 类 0 命中（闭包拉回的 4 个已计入 keep） |
| P2 | 对外文档引用必含 | ✅ | QUICKSTART/DATA/RUBRIC/CLAIMS/INDEX 引用的既有文件全部在快照内 |
| P3 | claim artifact 必含 | ✅ | CLAIMS 引用的 58 个 `reports/**` artifact 全部在快照内 |
| P4 | 本机路径零泄露 | ✅ | 扫 1054 个文本文件，命中 0（脱敏 55 个文件 / 70 处） |
| P4b | 脱敏可逆 | ✅ | 快照内容 == 原文经同一替换后的结果（逐字节） |
| P5 | 受限标识类字样 | ✅ | 0 命中 |
| P6 | 体量与清单对账 | ✅ | 快照 1108 个文件与 manifest KEEP 集合逐条一致 |
| P7 | 可独立成库 | ✅ | `git init -b main` + 单提交：**1107 追踪 / 1 提交 / 工作区 0 脏 / 库 2.2 MB** |
| P8 | 本机零影响 | ✅ | `git status` 中**既有文件被改 = 0**（只有本轮新增文件） |
| P9 | 既有闸不变 | ✅ | 负控 69/69；claims 33 / artifacts 68 / 语义 61 全过，逐项与改前相同 |

自检 `--self-test`：**5/5**（正向 + P1/P2b/P4/P5 各一向，每向断言「红的是哪一条」）。

## 5. ★ 快照内自检：7 红，其中 4 红是本任务引入

把快照 `git init` + 单提交后，在**快照里**跑 `check_claims.py`：

| 判据 | 快照内 | 原因 | 是否 D4 引入 |
|---|---|---|---|
| **C-013** | 红 | claim 引用的 `SHA256SUMS.txt` 在本机**外部归档**目录，公开仓库里没有；脱敏又把该路径改成占位符 | **是** |
| **S-46** | 红 | 判据校验「dataset 命令必须用项目 venv」，而脱敏把 `PY=<本机 venv 绝对路径>` 换成了 `{{VENV_PY}}` ⇒ 判据认不出 | **是** |
| **S-51** | 红 | 判据对象是 `AGENTS.md`/`CLAUDE.md`，按拍板 ① 已移出公开集 ⇒ 缺锚点判红（不 skip） | **是** |
| **S-56** | 红 | 同上 | **是** |
| S-39 | 红 | `node_modules/` 被 `.gitignore` 忽略 ⇒ `node --print-prompt-sha` rc=1 | 否（T-D5b 已发现，follow-up F-1） |
| S-43 | 红 | 同上 | 否 |
| S-61 | 红 | pre-commit hook 未装（新库天然没有） | 否（T-D5b 已发现） |

> **S-45 / S-59 这次没红**，但**不能据此说它们好了**：`emit` 用 `copy2/copystat` 保留了原 mtime，而真实 `git clone` 不保留 ⇒ 真实 clone 里 S-45 仍会红。**快照 ≠ clone**，这一点必须在下一轮用真 clone 复验。

**这 7 项不是「D4 做错了」，是「D4 把账翻出来了」**：如果不做这一步，第三方拿到仓库跑一遍自检就看到一片红，而且没人知道为什么。

## 6. 五个判据坑（都是自检/校验抓出来的，不是读代码看出来的）

**① 正则交替顺序写反 ⇒ 9 个假「缺失」。** P3 用 `\.(?:json|jsonl|md)`，`json` 先匹配把 `tasks_v6c.jsonl` 截成 `tasks_v6c.json` ⇒ 报 9 个 artifact 缺失，全是假的。修成 `jsonl|json` 后归零。**同族：`$?` 被管道吃掉——测量工具错了，结论就越像真的。**

**② 一刀切删「探针」会毁掉 claim 的证据链。** C-007 / C-008 两条 active claim 的 artifact 就是 `_probe_m14/all_loo.json`、`_probe_m14/h_convergence.json`。按目录名判「探针=垃圾」会直接违反 R-A3。解法是**引用闭包**：被对外文档/CLAIMS 引用且真实存在的文件，优先于目录名规则，但**只拉回具体文件，不拉整个目录**。

**③「提及」≠「引用」。** 闭包第一版把 `AGENTS.md`/`CLAUDE.md`/`CONFLICT.md` 也拉回了——因为 RUBRIC/CLAIMS 正文里**描述规则适用范围**时写了这三个裸文件名。规则改成「token 必须含 `/` 才算引用」，三个协议文件随即回落到移出侧。

**④ 判据文件自身包含被检测词 ⇒ 自指误报。** 脚本里直接写出检测词（受限标识类词、本机用户目录前缀），P4/P5 会把自己判红。解法：检测词用 `_m('密','级')` 拆开拼接、示例路径用 `_m('C:','/Users/')`，运行时字符串完全等价，检测能力不变。**契约文档同理**：把受限标识类用词改写为中性表述。

**⑤ P1 不能用 `classify()` 重新判。** 闭包拉回的文件在分类规则里仍属 drop 类，重新 `classify` 会把它们误报为「残留」。改成「`classify` 判 False **且**不在 `pulled_by_reference` 里」。

**另：`rc=$?` 又踩了一次管道坑。** `"$PY" ... --check ... | tail -14; echo rc=$?` 拿到的是 `tail` 的退出码（0），而实际是 2。这是项目里已记录过的 D-7 同族错误，本报告一律改成「重定向到文件再取 rc」。

## 7. 已知问题 / 未验证（全部登记，不擅自改）

| id | 问题 | 影响 | 建议处置 |
|---|---|---|---|
| **F-2** | `feagpt_repro/package-lock.json` 被 `.gitignore` 忽略 ⇒ 在原库被追踪、在新库**进不去**（1108 磁盘 vs 1107 追踪，差的正是它） | 第三方 `npm install` 拿到的是最新依赖，不是锁定版本 | 在 D3 一并处理 `.gitignore` 例外（本轮不改既有文件） |
| **F-3** | 公开集里 `check_claims` 有 4 项无法自愈的红（C-013 / S-46 / S-51 / S-56） | 第三方照 AGENTS §0 自检会撞红，且「缺锚点判红」是项目既定原则 | **需拍板**：给 `check_claims` 加 `--public` 模式（显式豁免并标 skip），或保留一份不含内部事故编号的公开版协议文件 |
| — | 快照 ≠ clone（mtime 被 copystat 保留） | S-45 在快照里绿、在真 clone 里红 | 下一轮用真 clone 复验 |
| — | 脱敏改变了 55 个文件的字节 | 不含任何 sha 锚点对象（`tasks.jsonl` / `reports/papers/*` / `candidates_*` 全部零改动，已逐项核对） | D3 重算锚点时一并封存 |

## 8. 命令

```bash
PY="<项目 venv 的 python>"   # 见 AGENTS.md §0，本报告不写死路径
cd feagpt_repro
"$PY" _d4_public_set.py --self-test                      # 5/5
"$PY" _d4_public_set.py --emit ../_handoff/public_snapshot
"$PY" _d4_public_set.py --check ../_handoff/public_snapshot   # rc=0
```

## 9. 下一步（一个）

**D3 行尾规范化**，且必须在 push 之前做。它同时要解决 F-2（`.gitignore` 例外）与重算锚点。我会先做小样本实测，给出「全局 CRLF / 全局 LF + 重算锚点」两条路的代价对比再动手 —— 不自作主张。

在此之前需要老王拍板一件事：**F-3 走哪条**（`--public` 模式 / 公开版协议文件 / 接受 4 项红并写进 QUICKSTART）。
