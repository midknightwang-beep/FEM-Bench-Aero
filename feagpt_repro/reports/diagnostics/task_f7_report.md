# T-F7 报告：`.gitattributes` 不进公开集

> 任务：`ROADMAP.md` §13 第 1 位（T-F2 现场发现的 F-7）
> 日期：2026-10-31 21:40 – 22:2x
> 单变量：**D4 公开集的分类规则**（`classify()` 如何处理根目录配置文件）

## 1. 结论先行

F-7 的真相不是「漏了一个文件」，而是「**默认拒绝 + 手抄名单**」这个组合必然复发：

- `ROOT_KEEP` 是一份手写清单，`.gitignore` 被手工加了进去，作用完全相同的 `.gitattributes` 没加；
- 漏了**没有任何闸会报** —— P6 比的是「快照 vs manifest」，而 manifest 恰恰由 `classify()` 产出（自证循环）；
- 后果可量化：第三方 clone 公开库后，D3 花一整轮建立的 `* text=auto eol=crlf` 与 `*.sh text eol=lf` **两条规则全部消失**。

修法因此不是「往名单里加一个串」，而是两件事一起做：**规则结构化** + **加一条不依赖名单的判据 P8**。

## 2. SOT（改前 / 改后）

| 项 | 改前 | 改后 |
|---|---|---|
| headline | C-032（未动） | C-032（未动） |
| paper sha256 | `tasks_v7.jsonl`（未动） | 同左 |
| prompt sha256 | `ce225186…`（未动） | 同左 |
| rubric 版本 | v6.10（未动） | v6.10（未动） |
| 公开集 | 1123 个 / 12.4 MB，移出 431 个 | **1124 个 / 12.43 MB，移出 430 个 / 71.12 MB** |
| 分类计数 | `KEEP:根目录必需 = 4`（含 `.gitignore`） | `KEEP:根目录必需 = 3`、**`KEEP:根目录仓库配置 = 2`**（`.gitignore` + `.gitattributes` 同组） |
| 判据数 | P0–P7（10 条） | **P0–P8（11 条）** |
| 自检向数 | 7 | **12** |

（数字全部来自 `public_manifest.json` 与 `--check` 实读，未手抄。）

## 3. 改了什么

### 3.1 分类规则：从名单改为结构（`classify()`）

```python
# 旧：ROOT_KEEP = {'.gitignore', 'LICENSE', 'LICENSE-DATA', 'README.md'}
# 新：ROOT_KEEP = {'LICENSE', 'LICENSE-DATA', 'README.md'}   # 仓库行为配置不在这里

def _is_repo_config(p):
    if '/' in p or '\\' in p:
        return False
    return p.startswith('.git') and p != '.git'
```

新增分类 `KEEP:根目录仓库配置`。`.gitignore` 从 `ROOT_KEEP` 移出后由同一条规则命中 —— **两者落在同一个分类里，这是「同类同待遇」的可见证据**，而不是靠注释保证。

**顺带收益**（实测，非推测）：`.editorconfig`、`.gitmodules` 在旧规则下同样是 `(False, '根目录内部材料')`；新规则下它们若将来入库会自动 KEEP，不需要再改代码。

### 3.2 新判据 P8：仓库行为配置必须随库分发**且真的生效**

三件事，缺一不可：

1. **同步**：`manifest.repo_configs` 由 `build_manifest()` **从源库现取**（不写名单），快照里缺 ⇒ 红、sha256 不符 ⇒ 红；
2. **反向**：快照根目录有、源库没有的 `.git*` 文件 ⇒ **也红**（防「反向放水」：凭空塞一个改行为的文件同样是错）；
3. **生效**：在临时 bare git-dir + `GIT_WORK_TREE` 指向快照，`git check-attr --all -- <样本>`，把结果与**源库**的回答逐项比。
   只比 sha256 只能证「文件没被换」，证不了「规则真的作用于某个文件」—— 这是 C 段「sha256 不证数对」的同族问题。
   问 git 而不是自己解析 `.gitattributes`：规则只有一处，第二处实现就是 bug（T-D3 的行尾规范化器就是栽在这上面）。

`manifest` 新增两个字段：`repo_configs`（路径 → `{sha256, bytes}`）、`repo_attr_probe`（样本路径 + 源库的属性解释）。

### 3.3 自检 7 向 → 12 向

| 向 | 断言 |
|---|---|
| ⑧ P8 内容漂移 | 文件在、内容不符 ⇒ **P8 红且 P6 绿**（把「分类规则漏了」与「emit 写漏了」分开） |
| ⑨ P8 缺失 | 源库有、快照无 ⇒ P8 红 + P6 红（F-7 的现状形态） |
| ⑩ P8 多给 | 快照有、`repo_configs` 无（keep 含它 ⇒ P6 绿）⇒ 只有 P8 红 |
| ⑪ P8 一致且生效须绿 | 断言 `'P8' not in fails` **且** note 里出现「生效已实测」——只断言「没红」等于允许 P8 整段不跑 |
| ⑫ P8 生效性真的会红 | `.gitattributes` 的 sha **与 manifest 一致**、但声明的规则不作用于样本 ⇒ 必须由「生效性」单独抓出来（没有这一向，生效性检查可能是个永不触发的新增代码，N-26 恒真式同款） |

## 4. 验收（逐项）

| # | 验收项 | 结果 |
|---|---|---|
| V1 | 修复前后双向对照 | `f7_attr_evidence.json`：源库 `run_xval_v11.sh` = `[['eol','lf'],['text','set']]`、`_d3_normalize_eol.py` = `[['eol','crlf'],['text','auto']]`；**修复后快照逐项相同**（`source_vs_after_fix_equal=true`）；**删掉 `.gitattributes` 后两者属性全空**（`source_vs_without_equal=false`） |
| V2 | 公开集确实多了它 | `n_keep` 1123 → **1124**；`KEEP:根目录仓库配置 = 2` |
| V3 | 自检 | **12/12，rc=0** |
| V4 | P8 在真实快照上绿 | `P8 ok：仓库行为配置 2 个与源库逐字节一致；生效已实测（run_xval_v11.sh → [['eol','lf'],['text','set']]）` |
| V5 | 闸不退化 | 负控 **69/69 ok**；claims **active 33 / artifact 68 / 语义项 61 → 全过**（连跑两次，S-45 绿） |
| V6 | 主仓没被误伤 | `.gitattributes` **未改**（`git diff --stat` 空、`git status` 无它）；快照内该文件的 blob sha 与 `HEAD:.gitattributes` **完全相同**（`7db82c5f`）⇒ 既没被脱敏改到、也没被重写行尾 |
| V7 | 快照其余判据不退化 | `--check` 报 P1/P2/P3/P4/P4b/P5/P6/P7 全 ok（P3 = 58 个 claim artifact 全在快照内） |

## 5. 现场自纠（都是自检抓出来的，不是读代码看出来的）

1. **首版自检 8/12，其中 3 个 BAD 全是脚手架自己造的假红**：`mk()` 用 `open(..., 'w')` 写文件，**Windows 文本模式默认把 `\n` 写成 CRLF**，于是 `P8` 拿工作区字节算的 sha256 对不上，正向、⑪、⑫ 三向一起红。
   ⇒ 与 T-D3 那次「以为 `json.dump` 写 LF 就去加 `newline='\r\n'`」是同一个坑的镜像：**先怀疑脚手架，再怀疑判据**。修法 `newline=''`。
2. **⑩ 第一次构造不干净**：用了 `check(snap, m)`，而 `m.keep` 不含 `.gitignore` ⇒ P6 也红，断言 `'P6' not in got` 失败。断言是对的，构造是错的 —— 改成 `make_m(d)` 后再从 `repo_configs` 里 pop 掉它，让「红只红在 P8」。
3. **`1124 个 / 12.4 MB` 与上一轮记录的 `12.5 MB` 差 0.1**：不是体积变了，是 MB 取整位不同（实际 12.43 MB）。已按本轮实读值改 ROADMAP，不再沿用旧的四舍五入。

## 6. 已知问题 / 未验证

- **P8 的 sha256 是「工作区字节」**，`.gitattributes` 在 Windows 上是 CRLF 版、Linux 上是 LF 版。它只在「manifest 与快照同一次运行产出」这个前提下自洽（`main()` 里 `--check` 传的正是现算的 manifest）⇒ **不得把它当跨机锚点**；跨机比对需要改用 `git hash-object`（按 attributes 归一化）。已在代码里写死这段前提，不留给下一个人踩。
- **未在干净 clone 后重跑 `--check`**：本轮只在本机验证。按 D3 的教训「本机绿证明不了换机绿」，这一条仍是缺口；但它属于「离线 bundle / 干净 clone 验证」那条单子（§13 现第 1 位），不在本轮范围。
- **分类计数变化本身不是闸**：`KEEP:根目录仓库配置 = 2` 掉了回去，没有任何东西会报 —— 真正守住它的是 P8。记录这个区别，免得以后把「计数好看」当成验证。
- **顺带发现、本轮不修**：`.workbuddy/memory/MEMORY.md` 的「历史索引」表缺 T-D2 / T-D3 / T-F2 / T-F3 四行（报告文件都在，只是索引没登记）。这是「文档没有闸守 ⇒ 会漂」的又一例（T-R1 同族）。本轮只补了 T-F7 一行，不顺手补齐 —— 补索引应配一条「报告文件 ↔ 索引行」的闸，单独立项。

## 7. 下一步（一个）

**离线 bundle 验证**：`_handoff/FEM-Bench-Aero_3059d90.bundle` 存在但从未在干净环境实测 clone。它是 D 段剩下的最后 0.5，也是把上面「未验证项」一次性关掉的唯一机会（干净 clone 里跑 `--check` + `check_claims`）。
