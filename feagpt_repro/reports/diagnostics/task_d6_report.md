# T-D6 报告：离线 bundle 能不能重建仓库

> 任务号：T-D6（D 段最后 0.5）
> 时间：2026-10-31 22:40 → 23:0x
> 契约：`task_d6_contract.md`（同目录）
> 证据：`d6_bundle_evidence.json`（闸产出，实读）

## 1. 一句话

**能。** 但本轮真正交出来的不是「clone 成功」，而是**一个会红的闸** —— 因为**我打的第一个包
`verify` 全绿、`fsck` 全绿、`status` 全绿、`clone` 退出码 0，而它是个空仓库。**

## 2. 立项时先撞到的两件事（都不是原来以为的那件事）

| 本以为 | 实测 |
|---|---|
| 「包在，验一下就行」 | 包里 `HEAD=3059d90`（2026-10-30 22:18），**落后 25 个提交 / 少 34 个文件**，D 段后半程（T-D2 数据包、T-D3 行尾、T-F2、T-F7）**整段不在包里**。验它只能证明「一个过期副本是完整的」 |
| 「第三方能不能离线拿到」 | bundle 在 `_handoff/` 里，`.gitignore:74` 把整个目录忽略（`git ls-files _handoff` = 0）⇒ 它是**老王的本地离线副本**，不是分发物。第三方离线获取由 D1（远端）+ D2（Release）负责 |

⇒ 所以本轮顺序是**先重打、再验**，并且验收口径写成「这个文件能否重建出仓库」，不写「第三方能否拿到」。

## 3. 本轮真踩到的坑：静默的空仓库

用 `git bundle create x --branches --tags` 打出来的包**没有 `HEAD` 引用**（实测四种组合，只有
`git bundle create x HEAD --branches` 才有）。后果：

```
[ok  ] C1   verify=ok，records a complete history     ← 绿
[ok  ] C3   clone 成功                                 ← 绿（退出码 0）
[ok  ] C4   git fsck --full 干净                       ← 绿（空仓库当然干净）
[ok  ] C8   clone 工作区干净                           ← 绿（同上）
[BAD ] C3b  clone 里没有 HEAD 提交（空仓库）
[BAD ] C6   ls-tree 取不到：fatal: Not a valid object name HEAD
```

**四个「看起来在验证」的信号同时给出成功**，只有「到底有几个文件」能戳破。这与本项目反复踩的
「恒真式在外观上与正常闭合一模一样」（N-26）、「自检全绿可能是假绿」是同一族：**空的东西最干净**。

所以闸把这条单独立成 **C2b**，并且**判据落在根因而不是后果**：`C3b`（空仓库）会不会红**取决于包的引用构成** ——
只有 1 个分支时 git 会自动选中它（自检夹具里就是 `files=3`、C3b 不红），有 6 个 tag 时它选不出来（真库上红）。
**后果依赖环境，根因才稳定。**

## 4. 闸：12 条判据 + 七向自检（第 ⑦ 向见 §7c）

`_d6_bundle_verify.py`（可复跑，`--json` 落证据，退出码 0/2/1）：

| 判据 | 查什么 |
|---|---|
| C1 | `git bundle verify` + **必须 `records a complete history`**（verify 通过但缺 prerequisite 的包，clone 会缺对象） |
| C2 | 读得出 `refs/heads/main`（唯一 head 兜底） |
| **C2b** | **包内有 `HEAD` 引用** —— 上一节那个坑 |
| C3 | 干净临时目录 `git clone`，**不碰网络、不碰源 `.git`** |
| C3b | clone 的 HEAD 等于包声明的 main；空仓库单独报 |
| C4 | clone 里 `git fsck --full` 无 missing / broken |
| C5 | 提交数与源库同一提交相等（119） |
| C6 | `git ls-tree -r` **整棵树逐条相比**（mode/type/**blob sha**/path）⇒ 文件集+内容+权限位一次覆盖（1561） |
| C7 | `git ls-files --eol` 与源库**逐行相同** ⇒ D3 的行尾成果在离线路径上也成立 |
| C8 | clone 工作区 `status --porcelain` 为空 ⇒ 行尾若解错会立刻显形 |
| C9 | 新鲜度：`behind_by` + 「落后的那些提交是否只改了文档」 |
| C10 | 离线数据链：clone 里用**本地** tarball 跑 `fetch_data.py` ⇒ 64 条 == `manifest.summary.n_cases`（代理变量全清） |

**自检六向（`--self-test`，6/6 rc=0）**：

| 向 | 断言 | 实测 |
|---|---|---|
| ① 好包须绿 | 无红无黄 | `[]`，behind=0（防过严） |
| ② 截断包须红 | C1/C2 红 | `['C1','C2']` |
| ③ 落后且改代码须红 | C9 红 | `['C9']`，behind=2 |
| ④ 落后仅改文档须黄 | 无红、C9 黄 | `['C9']`（warn），behind=1 —— **R75 的边界：放宽只在这个谓词下成立** |
| ⑤ 红的原因对得上 | 报 verify/clone，不是「找不到文件」 | `['C1','C2']` |
| ⑥ 无 HEAD 包须红 | C2b 红 | `['C2b']` |

## 5. 验收（契约 V1–V8）

| # | 项 | 结果 |
|---|---|---|
| V1 | 旧包确实过期 | `rev-list --count 3059d90..HEAD` = **25**；文件 1523 vs 1557（差 **34**） |
| V2 | 新包完整 | `is okay` + `records a complete history`；**8 refs**（HEAD + main + 6 tag）；38,424,098 B（36.64 MiB），`sha256 941d1112…a2152` |
| V3 | 干净环境能重建 | clone 成功、HEAD=3a2cfdd、提交数 119=119、`fsck --full` 干净 |
| V4 | 内容逐字节对上 | `ls-tree -r` 整树逐条相同，**1561 个文件** |
| V5 | D3 行尾在离线路径成立 | `ls-files --eol` **0 行不同**；`status --porcelain` **0 条** |
| V6 | 离线数据链 | 本地 tarball 解出 **64 条 == manifest 期望 64**，全程无网络 |
| V7 | 闸自身会红 | 自检 **6/6**，六向原因各不相同 |
| V8 | 闸不退化 | 负控 **69/69**；claims **33/68/61** 全过（连跑两次） |

补充实测（不进闸，只量化「重建出来的仓库能干什么」）：离线 clone 里跑 `check_claims` →
**结构 0 项 + 语义 4 项失败**：`S-39` / `S-43`（`node --print-prompt-sha` rc=1，缺 `node_modules` → 已登记的 **F-1**）、
`S-45`（clone 后 mtime 必然变，D5b 已定性为结构性）、`S-61`（hook 不入库 → D5b 已登记）。
比 D5b 在 `7eb0d00` 上实测的 5 项**少一个 S-59**（F-2 之后不再红；未追根因，此处不展开）。
⇒ **离线路径不是「降级可用」，它的待办清单与远端 clone 是同一张。**

## 6. 现场自纠（四条，前三条都是自检抓出来的）

1. **夹具无 `.gitattributes` ⇒ C7 假红**：自检临时仓库的文件行尾由 **clone 端 `core.autocrlf`** 决定，
   两边配置不同就红。真仓库有 `* text=auto eol=crlf` 兜底才不会。**判据没错，是夹具不真。**
2. **夹具用一个当前 HEAD 打「旧包」⇒ ③④ 退化成空操作**：`git bundle create x --branches <sha>` 里
   `main` 仍指向最新提交 ⇒ `behind_by` 恒为 0，两向都「绿」。改成**在提交之间逐次打包**（`on_commit` 回调），
   才真的产生 behind=2 / behind=1。**「变异由基线状态供给」的又一例（NC-56 同族）。**
3. **`os.path.relpath` 跨盘抛 `ValueError`**：包在 `C:` 临时目录、仓库在 `F:` ⇒ 直接崩。
   顺手又踩了一次「`cmd | tail` 吃掉退出码」：崩了却印 `RC=0`，改成重定向到文件再取 rc。
4. **manifest 的条数在 `summary.n_cases`，不是顶层**：写成 `man.get('n_cases')` 得到 `None` ⇒ 比对
   退化成 `64 != None`（恒假）。判据自己取不到基准时必须**判红**，不能静默——已加显式 `None` 检查。

## 7. 已知问题 / 未验证

- **bundle 不进仓库**（`_handoff/` 被忽略）⇒ 仓库里**没有闸能发现包里没有 bundle**。谁把 `_handoff/` 清了，
  闸会报「找不到 bundle」（那是好的），但「包该在哪、要不要上 Release」是**分发决策**，本轮不拍。
- **bundle 与 HEAD 的差值必然 ≥1**：记录 bundle 状态的那次提交本身也会进入 HEAD。闸用
  「落后的提交是否只改文档/证据」这条**谓词**把它和黄区分开（`metadata_only`），`--strict` 时黄也算红。
  **收口后实测**：包在 `3a2cfdd`、HEAD 已前进，闸输出
  `[warn] C9 包落后 1 个提交，但落后部分只动了文档/证据（5 个）⇒ metadata_only`，`rc=0`；
  加 `--strict` 则 `rc=2`。**留着这个黄不是偷懒 —— 它恰好证明这条放宽有边界**：
  第一次提交时包里缺的是闸本身的代码（`_d6_bundle_verify.py`），那一版**必须红**，
  所以先重打到 `3a2cfdd` 才收口；后来的提交只动文档，才允许黄。
- **没有自动重建**：不做 hook 自动重打（触发器自己要有闸，D5b 的教训）。靠「每次收口跑一次闸」。
- `S-59` 从 D5b 的 5 项里消失的原因**未查明**，只记录现象。

## 7b. 后续重打（T-B1KPI 之后，2026-11-01）

**为什么重打**：B1KPI 加进了 `_b1_repair_kpi.py`（新闸本身）等 6 个非文档文件，闸立刻红：

```
[BAD ] C9  包落后 5 个提交，且其中有 6 个非文档文件被改过
           （['.workbuddy/memory/2026-11-01.md', 'feagpt_repro/_b1_repair_kpi.py',
             'feagpt_repro/reports/check_claims.json']）⇒ 包代表不了当前状态
```

**这条红是对的**，与 §7 定的边界一致：落后部分含代码 ⇒ 必须重打，不能按 `metadata_only` 放行。

| | `3a2cfdd`（D6 收口时，历史值） | `f46eef8`（第一次重打） | `c117c02`（含 §7c 修复，最终） |
|---|---|---|---|
| 大小 / sha256 | 38,424,098 B / `941d1112…a2152` | 38,466,095 B / `f03a1dca…3e3cd` | **38,475,979 B / `d952a541…e57a8c`** |
| refs / tag | 8 / — | 9 / 7 | **9 / 7** |
| 提交数 | 119 | 124 | **125** |
| 整树文件数 | 1561 | 1566 | **1566** |
| `behind_by` | 1（→ metadata_only 黄） | 0 | **0** |

**为什么要打两次**：第一次重打（`f46eef8`）之后才发现 C9 的 `doc_only` 是手抄名单（§7c），
修它要改 `_d6_bundle_verify.py` —— **闸自己的代码变了，包就又不代表当前状态了**。
这正是 C9 存在的意义：它连「判据自身的改动」也一起管住。

**这次 `refs` 从 8 变 9 不是新加了 tag**：`git tag | wc -l` = 7，`list-heads` 输出 9 行 = HEAD + main + 7 tag。
§5 表里写的「8 refs（HEAD + main + 6 tag）」当时就少算了一个 —— **手抄 refs 明细本身就是会错的地方**，
以后只报 `refs=N`（`list-heads` 行数）与 `tag=M`（`git tag | wc -l`），不手抄名单。

**顺带撞到：公开快照也过期了，同一个病。** `_d4_public_set.py --check` 报 2 红：
`P6 快照与 manifest 不一致：缺 8 个（如 feagpt_repro/_b1_repair_kpi.py）`、
`P4b 脱敏不可逆 1 个：feagpt_repro/reports/check_claims.json[快照内容 ≠ 原文经同一替换后的结果]`。
重建后 1127 → **1135 个文件**（脱敏 60 个 / 76 处），P0–P8 全过。

⇒ **两个分发产物（bundle、公开快照）都会随仓库前进而过期，而且过期是无声的**：
bundle 至少还有 C9 会红（且能按 `metadata_only` 分档），快照的 P6 只会「缺 N 个」，
**没有任何东西提醒「什么时候该重建」**。这一条登记为 **F-9**（见 ROADMAP §13）。

### 7c. 顺带修掉 C9 自己的一个缺陷（F-10）：`doc_only` 也是手抄名单

重打之后想把「证据更新」这笔提交也按 `metadata_only` 放行，结果 C9 说
`check_claims.json` 是**非文档文件**。回读代码才看清首版的判据长这样：

```python
DEFAULT_DOC_ONLY = {
    'feagpt_repro/reports/diagnostics/task_d6_report.md',
    'feagpt_repro/reports/diagnostics/d6_bundle_evidence.json',
    'FEM-Bench-Aero/ROADMAP.md',
    '.workbuddy/memory/MEMORY.md',
    '.workbuddy/memory/' + '2026-10-31.md',   # ← 写死了日期
}
```

两个后果，都是必然复发型：

1. **写死了 `2026-10-31.md`** ⇒ 第二天（11-01）的日志就不在名单里，C9 必红。
   当时为了不复用这个「日期」，专门拆成 `'2026-10-31.md'` 拼字符串 —— **防住了自指，没防住日期**。
2. **`check_claims.json` / `public_manifest.json` 从来不在名单** ⇒ **每一轮收口都会红一次**，
   于是这条放宽对实际工作流等于无效：人会习惯性地说「又是那个红」，而不是去查。

这是 T-F7 的**同一个根因第二次出现**：默认拒绝 + 手抄名单必然漏。修法也一样 —— 换成结构性规则：

```python
METADATA_EXT = ('.md', '.json', '.jsonl', '.log')
def is_metadata(rel):                       # 只看目录 + 扩展名，不看文件名、不写日期
    p = rel.replace('\\', '/')
    if os.path.splitext(p)[1].lower() not in METADATA_EXT: return False
    if p.startswith('feagpt_repro/reports/'): return True      # 证据目录：无配置、无代码
    if p.startswith('.workbuddy/memory/'):    return True
    return p == 'FEM-Bench-Aero/ROADMAP.md'
```

**规则没有被改宽**，反而更可判：`.py`/`.sh` 永远不是 metadata（`reports/` 下那个
`run_xval_v11.sh` 也照样红）；`feagpt_repro/reports/` 之外的 `.json`（`schema_task.json`、
`manifest.json` 这类会改被测行为的配置）也照样红。

自检同步加第 ⑦ 向「分类规则正反例」（8 例，含**任意日期**的日志须为真、`reports/` 下的 `.sh` 须为假），
并把 ③④ 两向的**夹具路径改成真实形状**（`feagpt_repro/a.py` / `feagpt_repro/reports/diagnostics/DOC.md`）——
否则走默认规则时用裸名 `a.py`/`DOC.md` 根本测不出规则对不对（又一次「夹具不真」）。
自检 **7/7 rc=0**。

## 8. 下一步（一个）

`ROADMAP` §13 现第 1 位：**B1 补算 FPR / 修复成功率 / 收敛轮数**（零重跑，只用已有 `turns_histogram`），
这是当前最便宜的实际产出。
