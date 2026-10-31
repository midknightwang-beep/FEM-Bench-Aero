# T-F7 契约：`.gitattributes` 不进公开集（仓库行为配置必须随库分发）

> 立项时间：2026-10-31 21:40
> 依据：`ROADMAP.md` §13 第 1 位（T-F2 现场发现）
> 拍板人：老王（2026-10-31 21:36，「开F-7」）

## 0. 立项时的事实（现场实测，不是假设）

| 事实 | 实测值 |
|---|---|
| `classify('.gitattributes')` | `(False, '根目录内部材料')` |
| `classify('.gitignore')` | `(True, 'KEEP:根目录必需')` |
| 公开集 KEEP 是否含 `.gitattributes` | **否**（`n_keep=1123`，它在 `drop_categories['根目录内部材料']` 里） |
| 公开快照目录里有没有它 | **无**（`_handoff/public_snapshot/.gitattributes` 不存在） |
| 主仓对该文件的属性回答 | `eol: crlf` / `text: auto` |
| 快照建成的库对同一文件的回答 | `eol: unspecified` / `text: unspecified` |
| 主仓对 `run_xval_v11.sh` 的回答 | `eol: lf`（`*.sh` 例外） |
| 快照建成的库对同一 `.sh` 的回答 | 同一条命令在快照库里 → 无规则 |

⇒ **F-7 不是「漏了一个文件」，而是「默认拒绝 + 手工名单」这个结构必然复发**：
`ROOT_KEEP` 是一份手抄清单，`.gitignore` 被手工加了进去，`.gitattributes` 没加。
两者作用完全相同（都在定义仓库行为），待遇却不同 —— 而这**不会有任何闸报错**，
因为 P6 比的是「快照 vs manifest」，manifest 本身就是 `classify()` 产出的（自证循环）。

**伤害是具体的**：第三方 clone 公开库后，`* text=auto eol=crlf` 与 `*.sh text eol=lf`
两条规则**全部消失**。D3 花一整轮解决的「换机行尾不一致」（61.6% 的 sha 锚点断裂），
在公开库侧**原样复活**；且 `*.sh` 在 Windows 上会被 checkout 成 CRLF ⇒ POSIX 下 shebang 直接失败。

## 1. 只改什么（allowlist）

| 文件 | 动作 |
|---|---|
| `feagpt_repro/_d4_public_set.py` | ① `classify()` 把「根目录 `.git*` 配置文件」改为**结构性规则**（不再是名单里的一项）；② 新增判据 **P8**（仓库行为配置必须与源库同步 + 生效性实测）；③ 自检 7 向 → **12 向** |
| `feagpt_repro/reports/diagnostics/task_f7_{contract,report}.md` | 新建 |
| `feagpt_repro/reports/diagnostics/f7_attr_evidence.json` | 新建（V1 的双向对照取证；立项时漏写，执行中补登） |
| `feagpt_repro/reports/diagnostics/public_manifest.json` | 随 emit 重建（新增 `repo_configs` / `repo_attr_probe` 两个字段） |
| `FEM-Bench-Aero/ROADMAP.md` | §6 的 D4 行、§13（F-7 退出）、版本历史 |
| `.workbuddy/memory/MEMORY.md` + 当日日志 | D 段/F-7 状态 |

**不改**：`.gitattributes` 的内容（一个字都不动）、`.gitignore`、`check_claims.py`、
`negative_controls.py`、任何成绩单 / claim 数字 / rubric / 考卷 / 候选 / headline。

## 2. 为什么这是「判据面」而不是「加一个字符串」

只把 `.gitattributes` 塞进 `ROOT_KEEP` 能修好今天，但下次加 `.gitmodules` / `.editorconfig`
（本次实测：两者也都是 `(False, '根目录内部材料')`）就会以**同样的方式**静默漏掉，且依然无人报错。

所以本轮做两件事，缺一不可：
- **规则结构化**：根目录下 `basename` 以 `.git` 开头且不是 `.git` 目录 ⇒ 一律 KEEP。新增同类文件自动覆盖，不需要维护名单（R69：能判的不变量优于需要维护的名单）。
- **加判据**：P8 不看名单，而是**从源库现取**「根目录 `.git*` 配置文件」集合去比快照，双向（缺了红、多给也红），并且**真问一次 git 的规则解释结果**（`check-attr`），证明「文件在」且「规则真的生效」—— 只比 sha 会退化成「文件没被换」，证不了效果。

## 3. 验收什么

| # | 验收项 | 判据 |
|---|---|---|
| V1 | **修复前必须能红**（双向对照） | 旧规则快照建库：`check-attr eol -- feagpt_repro/_d3_normalize_eol.py` = `unspecified`；新规则快照 = `crlf` |
| V2 | 公开集确实多了它 | `n_keep` 1123 → **1124**；`.gitattributes` 出现在 `keep` 且分类为 `KEEP:根目录仓库配置`；`.gitignore` 与该文件**同组** |
| V3 | P8 自检 **5 向**（含「不许过严」） | `--self-test` **12/12**、`rc=0`：内容漂移红 / 缺失红 / 多给红 / 一致且生效须绿 / 生效性子断言真的会红 |
| V4 | P8 在真实快照上绿 | `--check` 报 `P8 ok`，且 `repo_attr_probe` 两边一致 |
| V5 | 闸不退化 | 负控 **69/69**；claims **33/68/61** 全过；自检连跑两次结果一致 |
| V6 | 主仓没被误伤 | `.gitattributes` 逐字节未变（sha256 前后相同）；`git ls-files --eol` 里 `w/lf` 仍只有那两个 `*.sh` |

## 4. 停止条件

出现任一即停，不边做边修：负控或 claims 转红、P8 在真实快照上红且原因不是分类规则、
需要改动 `.gitattributes` 的内容、需要改动任何成绩 / 分母 / headline。

## 5. 明确不做（留给后面的单子）

- 不动 `ROOT_KEEP` 里 `LICENSE` / `LICENSE-DATA` / `README.md` 三项 —— 它们不是「仓库行为配置」，
  不属于本轮这条规则；它们该不该进公开集是另一个问题（当前判定：该进，人工确认过）。
- 不动 `_handoff/public_snapshot` 的发布流程（D1 已验收）；本轮只让它重建后含 `.gitattributes`。
- 不重跑任何模型，不动任何成绩 / 分母 / headline。
