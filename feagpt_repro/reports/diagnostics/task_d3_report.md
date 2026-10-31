# T-D3 执行报告：行尾规范化（统一 CRLF）

> 拍板：2026-10-31 老王选方案 A。契约 `task_d3_contract.md`，测量 `task_d3_measure.md`（数字是**规范化前**快照）。
> 提交 `9020ba5`（14 文件）。本文所有数字为执行后实读。

---

## 0 结论

**未发现任何数字错误**（与 T-B1 同款结论）。行尾断裂已消除：干净 clone 与主仓**逐文件 sha 全同（1549/1549）**，
此前是 **954 个不同**。`S-57`（考卷锚点）与 `S-59`（修正表锚点）在 clone 里现在**同时绿**——
这正是 §测出的「不存在单一配置全绿」被解开的地方。

顺带发现两个**与行尾无关**的缺陷（F-4 已修、F-5 待立项）。

---

## 1 契约 §3 逐项验收

| # | 验收项 | 结果 | 证据 |
|---|---|:--:|---|
| V1 | 工作区行尾统一 | **过** | 真实字节统计：CRLF 1479 / LF 2（仅两个 `*.sh`，属性要求 LF）/ 单行 15 / 二进制 41 / 空 12；**`BAD` 桶 = 0** |
| V2 | 规范化不产生提交 | **过** | 规范化前后 `git diff` 均为空；提交只含 `.gitattributes` + 7 处锚点 + 2 个闸产物 + 5 个新文件，**没有 900+ 文件的内容 diff** |
| V3 | 换机一致（关键） | **过** | 新 clone 复算 `1549` 个文件：**相同 1549 / 不同 0 / 缺失 0**（执行前为 954 不同） |
| V4 | 判据不退化 | **过** | 负控 **69/69**；claims **33 条 / 68 artifact / 61 语义项 全过**（连跑两次，S-45 绿） |
| V5 | clone 里判据可跑 | **过** | clone 内只剩 4 项红，全部非行尾：S-39/S-43（缺 `node_modules`）、S-45（clone 内没有先跑负控）、S-61（hook 不入库）。**S-57 与 S-59 均绿** |
| V6 | 公开集不退化 | **过** | 快照 1118 文件 / 12.5 MB；P0–P6 全过（P4b 脱敏可逆逐字节一致） |
| V7 | F-4 已修 | **过** | `tasks.jsonl.sha256` 已从 v6b 旧值 `4c089c62…` 改为当前卷 `caf0f6c3…`；扫描器 T1b 转绿 |

### 关键对比（这是选择 A 的最终兑现）

| 量 | 执行前 | 执行后 |
|---|---|---|
| 主仓与干净 clone 字节不同的文件 | **954** | **0** |
| 全仓文本 `w/lf` + `w/mixed` | 913 + 42 | **2**（两个 `.sh`，属属性要求） |
| clone 里行尾造成的判据红项 | 1 项（A 卷 S-59 / B 卷 S-57，取决于卷） | **0 项** |

---

## 2 改了什么（逐条，含留痕）

1. **`.gitattributes`**（新增）：`* text=auto eol=crlf`；`*.bat`/`*.cmd` 显式 CRLF；`*.sh` 强制 LF。
2. **工作区 955 个文本规范化**（913 LF + 42 mixed → CRLF）：用 `_d3_normalize_eol.py`，**逐文件校验三件**
   （转换后纯 CRLF / 归一回 LF 与原文逐字节相等 / 行数不变），任一不成立则整批不写。
3. **7 处活锚点重算**（`_d3_fix_anchors.py`，旧值 = 目标文件的 LF 版 sha，新值 = 磁盘现状 sha，出现次数必须吻合）：

| 锚点文件 | 字段 | 旧 → 新 |
|---|---|---|
| `baseline_scorecard_L3_v7_glm.json` | `provenance.judge_overrides.sha256` | `517b32d0…` → `c9d60bc1…` |
| `baseline_scorecard_L3_v7_ds.json` | 同上 | `517b32d0…` → `c9d60bc1…` |
| `baseline_scorecard_L3_v4.json` | `tasks_sha256`（2 处） | `f8e0182b…` → `7f241a91…` |
| `msr_l3_v4.json` | `tasks_sha256` | `f8e0182b…` → `7f241a91…` |
| `papers/SHA256SUMS` | 考卷行 + `nl_human` 行 | `f8e0182b…`→`7f241a91…`；`99d5e408…`→`7d224b08…` |
| `tasks/tasks.jsonl.sha256` | F-4 | `4c089c62…`（v6b）→ `caf0f6c3…`（当前卷） |

**没动的**：21 条历史快照 `_snap_*.json` 里的旧值（无判据读，改了反而制造"历史也重新封存过"的假象）；
任何分数 / 通过数 / 分母；任何判据逻辑。

---

## 3 新发现

### F-5（**待立项**）`latest_scorecard()` 按 `mtime` 选被测对象

`negative_controls.py:42` 用 `max(cands, key=os.path.getmtime)` 选「最新成绩单」。
本轮重算锚点时，`baseline_scorecard_L3_v4.json` 的写入时间**晚于** v7 两份 ⇒ 负控立刻改咬 v4，
`NC-33`（成绩单口径字符串）与 `NC-36`（语义项不静默消失）由绿转红，而两者检查的字段**一个字节都没被改**。

这不是本轮引入的问题，是**时间耦合**：
- **clone 之后必然存在**——所有文件 mtime = checkout 时间，`max()` 退化成 `listdir` 顺序，**选谁不确定**；
- 这与「位置耦合会伪装成确定性」同族，只是耦合变量从**下标**换成了**时间戳**。

**本轮止血**：把 `v7_glm` 的 mtime 设为最新（恢复「v7 才是当前卷成绩单」的事实，mtime 不入库、不影响提交）。
**根治需立项**：改判据属契约 §1 禁止项，建议下一轮把它改成按 `provenance.tasks_sha256 == 当前卷 sha` 选，
或按显式文件名清单选。**在此之前，「换机跑负控」的结果不可复现**——这条要写进对外说明。

### F-4（**已修**）`tasks.jsonl.sha256` 过期且无闸守

记的是 v6b 卷 sha，`grep` 全仓无任何判据读它（R58：无工具读的 = 无闸）。已改为当前卷值。
**未加闸**：给它建判据需要单独立项（会改 claims 计数），本轮不扩范围。

### 教训（测量错误，B 段）

**我差点提交一个"修了不存在的问题"的改动**：以为 Python 写 JSON 是 LF，给 `check_claims.py` /
`negative_controls.py` 加了 `newline='\r\n'`。随后规范化器报「已处理 0 个」才反应过来——
**Windows 上 Python 文本模式默认 `os.linesep` 就是 `\r\n`**，这些产物本来就是 CRLF。
已 `git checkout --` 回滚，最终提交里**不含**这两处改动。
⇒ 与「★★ 改别人的结论之前先读原文」同类：**动手改判据之前，先证明被修的东西真的坏了**。

---

## 4 遗留（按优先级）

| # | 项 | 影响 | 下一步 |
|---|---|---|---|
| 1 | **F-5** `latest_scorecard` 时间耦合 | 换机跑负控结果不可复现 | 单独立项，改选择规则 |
| 2 | F-1 缺 `npm install` 指引 | clone 后 S-39/S-43 红 | `QUICKSTART.md` 已加故障表一行，正文待补 |
| 3 | F-2 `package-lock.json` 被 gitignore | 1118 磁盘 vs 1117 追踪 | 决定是否入库 |
| 4 | 新文件默认 LF | Write/新脚本产物会带回 LF | **提交前跑 `_d3_normalize_eol.py`**（幂等，dry-run 可先看） |

---

## 5 复现

```bash
"$PY" _d3_normalize_eol.py --self-test        # 5 向，rc=0
"$PY" _d3_normalize_eol.py                    # dry-run：应为「待处理 0 个」
git ls-files --eol | grep -c "w/lf"           # 应为 2（两个 *.sh）

"$PY" _d3_eol_anchor_scan.py --self-test      # T1a/T2/T3 绿；T1b 应已转绿（F-4 已修）
"$PY" _d3_fix_anchors.py                      # dry-run：7 条应全部显示「待替换」，旧值次数吻合

# 换机一致性（唯一硬证据）
git clone -q <repo> "$TEMP/eol_c" && "$PY" _b1_eol_scan.py "$TEMP/eol_c"   # 期望 不同数 = 0
```
