# T-D6 契约：离线 bundle 能不能重建仓库（D 段最后 0.5）

> 立项时间：2026-10-31 22:40
> 依据：`ROADMAP.md` §13 第 1 位（D 段 92% 里没算满的那半分）
> 拍板人：老王（2026-10-31 22:35，「开始离线 bundle 验证」）

## 0. 立项时的事实（现场实测，不是假设）

| 事实 | 实测值 |
|---|---|
| 现有 bundle | `_handoff/FEM-Bench-Aero_3059d90.bundle`，38,172,727 B，`sha256 038cc56a…b803` |
| 它的 HEAD | `3059d90`（2026-10-30 22:18，T-C1 收口时的记忆提交） |
| 它的 refs | 8 条（main + 6 tag + HEAD），`git bundle verify` = `is okay`，`records a complete history` |
| 它含多少提交 / 多少文件 | 93 提交 / 1523 文件 |
| 当前 HEAD | `2698612`，118 提交 / 1557 文件 |
| **差距** | **落后 25 个提交、少 34 个文件** |
| 差距覆盖了哪些工作 | T-D2（数据包 Release）、T-D3（行尾统一）、T-F2（lock 入库）、T-F7（`.gitattributes` 进公开集）—— **D 段的后半程整段不在包里** |
| bundle 在不在仓库里 | **不在**：`.gitignore:74` 的 `_handoff/` 把整个目录忽略；`git ls-files _handoff` = 0 |

⇒ 两个结论，缺一个这轮就会做错：

1. **「验证旧包」几乎证明不了什么**：旧包自洽（verify 全绿）但落后 25 个提交，验它只能得出「一个过期副本是完整的」。**D 段要的是「当前状态可离线恢复」，不是「某个旧副本没坏」**。所以本轮必须**先重打，再验**。
2. **bundle 是「本地离线副本」，不是分发物**。它躺在被 gitignore 的 `_handoff/` 里，第三方 clone 仓库拿不到。所以验收口径只能是「老王手上这个文件能否重建出仓库」，**不能**写成「第三方能否离线拿到」——后者 D1（远端）与 D2（Release）已经负责，别混。

## 1. 只改什么（allowlist）

| 文件 | 动作 |
|---|---|
| `_handoff/FEM-Bench-Aero_2698612.bundle` | 新建（`--branches --tags`，覆盖到当前 HEAD 的全部历史） |
| `_handoff/FEM-Bench-Aero_3059d90.bundle` | **删除**（落后 25 个提交，留着只会被误取；文件名里的 sha 就是它唯一的身份标识） |
| `feagpt_repro/_d6_bundle_verify.py` | 新建（可复跑的闸 + `--self-test` 负向 + `--json` 证据） |
| `feagpt_repro/reports/diagnostics/task_d6_{contract,report}.md` | 新建 |
| `feagpt_repro/reports/diagnostics/d6_bundle_evidence.json` | 新建（闸产出的取证） |
| `FEM-Bench-Aero/ROADMAP.md` | §6 D 段行、§1 看板、§13（首位退出）、版本历史 |
| `.workbuddy/memory/MEMORY.md` + 当日日志 | D 段状态（D 段全程完成） |

**不改**：任何源码功能、`check_claims.py` / `negative_controls.py` 的判据、任何成绩 / 分母 / rubric / 考卷 / headline、`.gitattributes`、`.gitignore`。

## 2. 为什么「跑一次 clone」不够，非要写个闸

一次手工 clone 成功，只能证明「我今天这条路径能通」。而 bundle 的性质是**会随时效腐坏**：它不随提交自动更新，仓库每前进一次它就旧一分，且**没有任何东西会报错**（和 `.gitignore` 拦住 `package-lock.json` 是同一族：状态静默漂移，无人报警）。

所以本轮交的是**闸**，不是一次截图：

- `_d6_bundle_verify.py` 每次运行都：`git bundle verify` → 干净临时目录 `git clone`（**不碰网络、不碰源 `.git`**）→ 逐项比对 → 出 JSON。
- 闸里有一条**新鲜度**判据：`behind_by = 源 HEAD 与 bundle HEAD 之间的提交数`。`behind_by = 0` 绿；`behind_by > 0` 时再问一句「落后的那些提交**只改了文档/证据**吗」——是则判 `metadata_only`（黄，不算坏），否则判红。这条谓词是精确可验的：**任何代码改动落在包里没有的提交上，必然红**。
- 自检造三个坏包（截断 / 错头 / 缺 tag）证明闸会红，且红的原因分得开。

## 3. 验收什么

| # | 验收项 | 判据 |
|---|---|---|
| V1 | 旧包确实过期（不然「重打」这一步是白做） | `git rev-list --count 3059d90..HEAD` = **25**；文件差 **34** |
| V2 | 新包完整 | `git bundle verify` = `is okay` + `records a complete history`；refs = main + 6 tag |
| V3 | 干净环境能重建 | 临时目录 clone：`HEAD` == 源 `HEAD`；提交数相等；`git fsck --full` 无 missing |
| V4 | 重建出来的内容逐字节对上 | `git ls-tree -r HEAD` 输出（mode/type/sha/path）源与 clone **完全相同**；文件数 1557 |
| V5 | D3 的行尾成果在离线路径上也成立 | clone 里 `git ls-files --eol` 与源库**逐行相同**；`git status --porcelain` 为空（换成错行尾就会显示改动） |
| V6 | 离线数据链通（不留「有代码没数据」） | clone 里用**本地** `FEM-Bench-Aero-v1.1-data.tar.gz` 跑 `fetch_data.py` → `modeling/` 条数 == `manifest.n_cases`（64） |
| V7 | 闸自身会红 | `--self-test` 三向：截断包 / 错头包 / 落后且有代码改动 ⇒ 都必须红；另有一向「好包须绿」防过严 |
| V8 | 闸不退化 | 负控 **69/69**；claims **33/68/61** 全过（连跑两次） |

## 4. 停止条件

出现任一即停，不边做边修：负控或 claims 转红；新 bundle `verify` 失败；clone 出来与源在同一提交上不一致（那说明打包方式有问题，先查原因不改判据）；V6 需要联网才能完成（那说明「离线」这个前提本身不成立）。

## 5. 明确不做（留给后面的单子）

- **不动** bundle 的存放位置与分发方式。要不要把 bundle 也传到 Release、让第三方能离线拿到，是 D1/D2 的延伸决策，**本轮不拍**。
- **不把 bundle 纳入自动重建**（如每次 commit 后重建）——那需要 hook，而 hook 不入库（F-3 / D5b 已有教训：触发器自己要有闸）。本轮只做到「有闸、可复跑、过期会被抓」。
- 不重跑任何模型，不动任何成绩 / 分母 / headline。
