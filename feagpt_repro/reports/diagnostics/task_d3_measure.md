# D-3 行尾规范化：两条路的代价测量（只测不改）

> 状态：**测量完成 → 2026-10-31 老王拍板方案 A（统一 CRLF）→ 已执行**。执行结果见 `task_d3_report.md`。
> ⚠️ **本文件里的数字是「规范化之前」的快照，不得当成现状读**（工作区现已是 1474 个文本全 CRLF）。
> 保留它的意义是留证：为什么选 A、以及选 B 会付出什么。
> 关联：T-B1 报告 D-3（机理）／记忆「行尾两端各有一批锚点，不存在单一配置全绿」。
> 复现命令见 §6，数字一律实读，不手抄。

---

## 0 一句话结论

两条路在 git 层面**都不产生任何提交**；差别全在「换机 clone 后有多少 sha256 锚点失效」——实测
**统一 CRLF 失 28 条 / 统一 LF 失 428 条（16 倍）**，且 clone 后判据**各只红 1 项，但不是同一项**
（CRLF 卷红 S-59、LF 卷红 S-57）。

---

## 1 现状（实读）

| 项 | 值 | 取法 |
|---|---|---|
| 被追踪文件 | 1543（文本 1502） | `git ls-files` |
| 工作区行尾 | LF 912 / CRLF 521 / mixed 42 / 单行 27 | `git ls-files --eol` |
| **索引（blob）行尾** | **1475 个文本全部 `i/lf`** | 同上 |
| `core.autocrlf` | `true` | `git config --get` |
| `.gitattributes` | 不存在 | — |

> **本仓的行尾问题不是「两套内容」，是「一套内容 + 一台机器在 checkout 时按工具历史各转各的」**：
> blob 里只有 LF 一套，`autocrlf=true` 在 checkout 时转 CRLF，而工作区的 912 个 LF 文件是
> 后续被 Python/Write 直接写成 LF 的（绕过了 checkout）。⇒ 同一 commit，本机与 clone 字节不同。

---

## 2 四条硬事实（都是 clone 实测，不是推理）

### 事实 1 —— 转行尾**不产生任何提交**

| clone 方式 | `git status --porcelain` 脏文件数 | 文本行尾 |
|---|---|---|
| `-c core.autocrlf=true`（A 卷） | **0** | 1475 全部 `w/crlf` |
| `-c core.autocrlf=false`（B 卷） | **0** | 全部 `w/lf` |

⇒ 「统一 CRLF 要改 954 个文件」这句话容易吓人，但**那不是 954 个提交**——因为 blob 里存的是 LF，
CRLF 工作区会被 `autocrlf` 归一回 LF，git 认为内容没变。**是一次 checkout 重做，不是一次大提交。**

### 事实 2 —— 锚点本身就分裂成两套

扫全仓正文里的 64 位 hex 共 **8998 条**，反查「它指向哪个文件的哪个行尾版本」：

| 桶 | 条数 | 说明 |
|---|---|---|
| 指向 **CRLF 版** | **428** | 统一 LF 后失效 |
| 指向 **LF 版** | **28** | 统一 CRLF 后失效 |
| 两版皆可 | 0 | — |
| 查无此文件 | 8542 | 外部归档 / 数据包 / 工具输出的 sha，与行尾无关 |

**28 条 LF 锚点分布**（这才是「统一 CRLF」的真实账单）：

| 条数 | 位置 | 性质 |
|---|---|---|
| 21 | `_snap_*.json` 等历史诊断快照（12 个文件） | **死锚点**：无判据读，不影响任何数字 |
| 2 | `reports/baseline_scorecard_L3_v4.json` | 活（历史成绩单） |
| 1 | `reports/baseline_scorecard_L3_v7_ds.json` | **活**（当前 v7 成绩单） |
| 1 | `reports/baseline_scorecard_L3_v7_glm.json` | **活**（当前 v7 成绩单） |
| 1 | `reports/msr_l3_v4.json` | 活（历史） |
| 2 | `reports/papers/SHA256SUMS` | 活（对外证据包） |

⇒ **统一 CRLF 真正要重算的活锚点 ≈ 7 条**，其中必须动的只有 2 条（两份 v7 成绩单里记的修正表 sha，即 S-59）。

### 事实 3 —— clone 后判据各红 1 项，**不是同一项**

| 判据项 | A 卷（全 CRLF） | B 卷（全 LF） | 归因 |
|---|:--:|:--:|---|
| S-39 / S-43 | 红 | 红 | 缺 `node_modules`（与行尾无关，`npm install` 自愈） |
| S-45 | 红 | 红 | mtime / 收口顺序（与行尾无关） |
| S-61 | 红 | 红 | hook 不入库（与行尾无关） |
| **S-57**（`paper_sha256`） | 绿 | **红** | 记的是考卷 **CRLF 版** ⇒ 统一 LF 后对不上 |
| **S-59**（修正表 sha） | **红** | 绿 | 记的是修正表 **LF 版** ⇒ 统一 CRLF 后对不上 |

**这是「不存在单一配置全绿」的直接证据**：同一份仓库里，考卷锚点认 CRLF、修正表锚点认 LF。
不管选哪边，都必然要重算被放弃的那一半——**差别只在那一半有多大（2 条 vs 全部考卷下游）**。

### 事实 4（**新发现 F-4**）—— `tasks/tasks.jsonl.sha256` 已过期，且无闸守

```
文件内容 : 4c089c62…  feagpt_repro/tasks/tasks.jsonl
实际当前卷: caf0f6c3…  （192 行、CRLF）
4c089c62… 实际是 reports/papers/tasks_v6b.jsonl 的 sha（165 行、v6b 旧卷）
```

`grep -rn "tasks.jsonl.sha256"` 全仓：**只有 manifest 清单和本次新写的扫描脚本提到它，没有任何判据读它**。
⇒ 卷从 v6b 升到当前卷时这个文件没跟着更新，**漂了而无人报错** —— R58「无工具读的 = 无闸」的又一例。
本项**独立于行尾问题**（即使不规范化，它也是错的），但两条路都必须顺带修它。

---

## 3 两条路的完整成本表

| 维度 | **A：统一 CRLF** | **B：统一 LF** |
|---|---|---|
| `.gitattributes` 写法 | `* text=auto eol=crlf` + `*.bat` 显式声明 | `* text=auto eol=lf` + `*.bat eol=crlf` 例外 |
| git 提交量 | 0（只多一个 `.gitattributes`） | 0（同上） |
| 工作区字节变化 | 954 个文件（912 LF + 42 mixed → CRLF） | 563 个文件（521 CRLF + 42 mixed → LF） |
| **clone 后失效锚点** | **28 条** | **428 条** |
| 其中活锚点 | ≈ **7 条**（必须动 2 条） | 数十~百条（含考卷下游全链） |
| clone 后判据红 | S-59 一处（需重算 2 份 v7 成绩单里修正表 sha） | S-57 一处（需重算 R32 两份审计 artifact 的 `paper_sha256` + 考卷 sha 下游） |
| Windows clone | 天然一致 | 天然一致 |
| Linux/macOS clone | **需 `.gitattributes` 的 `eol=crlf` 才能一致**（不加就断） | 天然一致（git 标准做法） |
| `.bat` 风险 | 无（本来就要 CRLF） | **有**：9 个 `.bat` 必须留 CRLF，需例外规则 |
| 后续维护心智 | 与「Windows 默认 checkout」一致，第三方不会意外踩 | 与 git 主流实践一致，但需常年维护 `*.bat` 例外 |

---

## 4 推荐：**A（统一 CRLF）**，附三条边界

**理由**：活锚点代价 7 条 vs 数十条，判据只需修 **1 项**（S-59 两条 sha），且与「第三方在 Windows 上 clone 的默认结果」一致——
本项目全部证据链（R25/R26/R29 的 sha256 锚点、成绩单 `provenance`）都产在 Windows 上，
**把工作区对齐到「Windows 默认 clone」比对齐到「git 标准」的返工量小一个量级**。

**边界（R75 同源，写死）**：
1. **`.gitattributes` 必须在同一次改动里落地**，否则只修了本机、Linux clone 仍断——**「本机绿」证明不了「换机绿」**。
2. **28 条失败锚点必须逐条说明处置**（21 条死锚点可留旧值；7 条活锚点必须重算并留痕），**不得整批静默覆盖**。
3. **重算锚点属于「改对外数字载体」**，按 R71 只能修「记录与实际不符」这一类事实错误，**不得借机调整任何成绩单数字**。

**若你更看重「与 git 标准一致 / 将来可能上 Linux CI」，选 B 也成立**，代价是：多改 400 条锚点、`.bat` 需例外、
S-57 那条要连带重算 R32 审计 artifact——**我不建议在推送前做 B**，因为它把「首次公开」和「全链重新封存」绑在一起。

---

## 5 拍板点（只问一件）

D-3 选 **A（统一 CRLF）** 还是 **B（统一 LF）**？

- 选 A：我按上面三条边界执行，产出 = `.gitattributes` + 工作区规范化 + 7 条活锚点重算留痕 + F-4 修正，**然后才推送**。
- 选 B：同样流程，但锚点重算范围扩到「所有记 CRLF 版的活锚点」，并加 `*.bat` 例外；**预计多花一轮**。
- 也可以选 **先推、D-3 之后再补**：那我需要在推送说明里明写「本仓已知行尾问题，换机后部分 sha 锚点会断」——
  **但这与「证据可复现」的对外承诺相冲，我不推荐**。

---

## 6 复现

```bash
# 1) 行尾分布与锚点扫描（自检 + 全量）
"$PY" _d3_eol_anchor_scan.py --self-test           # rc=0；T1b 会红（那是在报 F-4，不是脚本坏）
"$PY" _d3_eol_anchor_scan.py --json "$TEMP/d3_anchors.json"

# 2) 两条路的 clone 实测（A=CRLF 卷 / B=LF 卷）
git -c core.autocrlf=true  clone -q <repo> "$TEMP/eol_a"
git -c core.autocrlf=false clone -q <repo> "$TEMP/eol_b"
"$PY" _b1_eol_scan.py "$TEMP/eol_a"    # 954 个文件与主仓字节不同
"$PY" _b1_eol_scan.py "$TEMP/eol_b"    # 563 个
cd "$TEMP/eol_a/feagpt_repro" && "$PY" check_claims.py   # 红 S-39/S-43/S-45/S-59/S-61
cd "$TEMP/eol_b/feagpt_repro" && "$PY" check_claims.py   # 红 S-39/S-43/S-45/S-57/S-61
```

> ⚠️ 上面两条 `check_claims` 的红项里，**只有 S-59（A 卷）/ S-57（B 卷）是行尾造成的**，
> 其余四项在两种卷上都红、与行尾无关（缺依赖 / mtime / hook 不入库）。把它们混在一起数「红了几项」会得出错误结论。
