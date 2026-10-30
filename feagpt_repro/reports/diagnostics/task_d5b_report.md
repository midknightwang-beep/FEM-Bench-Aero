# T-D5b 交付报告：给「hook 是否已装」建判据

- **任务**：ROADMAP §6 D5b / RUBRIC **R74**
- **日期**：2026-10-30
- **契约**：`task_d5b_contract.md`
- **单变量**：无（不触碰任何判分口径、卷、候选、成绩）

## 1. 问题

T-D5 建的 `check_commit.py` 靠 `.git/hooks/pre-commit` 触发，而 **hook 在 `.git/` 里、不入库**。

⇒ 新 clone、换机、`git init` 重建后，这道闸**静默消失**：

```
它不运行 ⇒ 所以不会有任何东西报错 ⇒ 与「压根没装这道闸」完全等价
```

这是 **R58「无工具读的 = 无闸」落在「触发器」上的形态**。T-D5 当时已把它写成已知缺口，本轮补上。

## 2. 关键设计决策：判据放哪

| 方案 | 否决理由 |
|---|---|
| 放进 `check_commit.py` 当 G7 | **hook 内恒真**（能跑说明已装），且不带 hook 时没人跑它 ⇒ 同语反复，自监督不成立 |
| 两者都放 | 同一判据写两遍，迟早不一致（T-A11a 的老账） |
| **放进 `check_claims.py`（S-61）** ✅ | §0 硬规则「任一命令不全绿即停」⇒ 自动获得强制力；**不依赖 hook 自身存在** |

判据实现独立成 `hook_guard.py`（可单独 `--self-test`），**S-61 只做薄包装**，不重复实现。

## 3. 判据 H0–H4

| id | 判据 | 失败时 |
|---|---|---|
| H0 | 在 git 工作副本内 | 非 git ⇒ `applicable=False`，**不是失败** |
| H1 | **生效** hooks 目录下有 `pre-commit` | 红（附 `--install-hook` 命令） |
| H2 | 内容含 `check_commit.py` | 红（这是别的钩子） |
| H3 | 内容里的脚本路径可解析、存在、**等于当前脚本** | 红（僵尸路径 / 另一个副本） |
| H4 | 可执行位 | **仅 POSIX 且 `core.filemode != false` 时判**；否则 `not_run` 并写明「本向在此平台未被验证」 |

**★ 不写死 `.git/hooks`**：判据用 `git rev-parse --git-path hooks` 取**生效**目录。**实测该命令会跟随 `core.hooksPath`**（设 `.husky` ⇒ 返回 `.husky`；设绝对路径 ⇒ 返回绝对路径）。

这条实测推翻了原方案「`core.hooksPath` 非空即红」：把 hook 装进 `.husky` 并**纳入版本控制**是**更**好的做法，一刀切判红会把人逼去删一个合法配置（R69：能判的不变量优于需要维护的名单；R73：查实体不是查容器）。

## 4. 验证

### 4.1 `hook_guard.py --self-test` 八向（每向断言「红的是**哪一条**」）

```
正向①默认路径装了            红=无
H1 hook 缺失（新 clone）      红=H1    → msg 含 --install-hook
H2 是别的钩子                 红=H2
H3 指向僵尸脚本               红=H3    → msg 含「不存在」
H3 指向另一个副本             红=H3    → msg 含「当前脚本是」
H1 hooksPath 改道到空目录     红=H1    → msg 含 core.hooksPath
正向②hooksPath 改道且已装     红=无    ← 不得误红
H0 非 git 目录 ⇒ 无对象       红=无  [not_applicable]
自检: 8/8 ok
```

`expect_red` 用**精确集合**（多红也算错）—— 只断言「红了」会放过「红的原因不对」，多红一条又会把人引去修错的地方。

### 4.2 接线后行为（真实仓库，非模拟）

| 场景 | 实测 |
|---|---|
| 正常 | `[ok] S-61 生效目录=…\.git\hooks；H1=ok H2=ok H3=ok H4=skip` |
| **移走 hook** | `[FAIL] S-61 … H1=BAD H2=skip H3=skip；红=H1`，**只有 1 项失败**（不级联） |
| 移走 hook + `--skip-hook-guard` | `[skip] S-61`，语义项计数 **61→60**（skip 不计入，不冒充通过） |
| `hook_guard.py` 改名 | `[FAIL] S-61 … 无法导入 hook_guard.py（缺判据即红，不 skip）` |
| 非 git 目录 | `hook_guard_state()` 返回 `(True, 'not_applicable：…（无对象，不是失败；也不等于已验证）')` |

**恢复保证**：移走 hook 前后 sha256 都是 `4422a4c17d4b24e3…`（逐字节一致），没有靠「大概恢复了」蒙过去。

### 4.3 既有闸不受影响

- 负控 **69/69**（未加 NC → C-019 的 69 链、S-44/NC-49 循环依赖均未触发）
- `check_claims` **33 claims / 68 artifacts / 语义项 61 条 → 全过**

## 5. 三条现场自纠（都是自检抓出来的，不是读代码看出来的）

**① 八向「全绿」是假绿。** 首版自检 8 向全部通过，但明细里每行都带 `[not_applicable]` —— 我定义了 `_mk_repo()` 却忘了在 `probe()` 里调用，临时目录根本没 `git init`，于是 `applicable=False`、8 向全是「红=无」。

**通过/失败那一列看不出来。** 是明细行把它抓出来的。这与 N-26（恒真式外观与正常闭合一样）、NC-47（判据没跑起来与判据通过外观一样）同族，也是本项目反复出现的形态。

**② 「`core.hooksPath` 非空即红」被实测推翻**（见 §3）。

**③ 差点记成「没红」。** 第一次验证「移走 hook 会红」时用了 `grep -E "S-61|失败" | head -3`，S-61 那行因为顺序靠后被 `head` 截掉，只看到三行 `[ok]`。加宽 `grep` 后才是 `[FAIL]`。**`head`/`tail` 截断会制造假的「没红」，与 `$?` 被管道吃掉（T-B1 的 D-7）是同一类测量错误。**

## 6. 边界（R69）

- **例外只有一处**：`check_claims.py --skip-hook-guard`。用途 = CI / 第三方只跑复现。使用时 S-61 标 `skip`、**不计入语义项总数**，须在当次报告写明原因 —— 与 `git commit --no-verify` 同等对待。
- **不自动豁免**：不通过「检测 CI 环境变量」之类静默放行。
- **不进入对外数字**：S-61 是环境完整性判据，不是成绩。
- **本判据的边界**：只保证「哨兵还在、且指向当前脚本」，**不保证哨兵判得对**（那是 `check_commit.py --self-test` 的事）；也管不了钩子链上别的 hook 是否被改。

## 7. 未验证项（如实标注）

| 项 | 状态 |
|---|---|
| H4 可执行位**在 POSIX 上**的判红 | **未验证** —— 本机 `os.name=nt`、`core.filemode=false`，该向走 `not_run`。代码写了，但没有跑过红的那一侧 |
| macOS / Linux CI 上 S-61 的表现 | 未验证 |

## 8. 文件清单

| 文件 | 动作 |
|---|---|
| `feagpt_repro/hook_guard.py` | **新建**（判据 + 八向自检） |
| `feagpt_repro/check_claims.py` | S-61 + `hook_guard_state()` + `--skip-hook-guard` |
| `FEM-Bench-Aero/RUBRIC.md` | R74 + 版本行 v6.8→**v6.9**（CRLF 保持，383 行） |
| `FEM-Bench-Aero/README.md` | RUBRIC 版本引用 v6.8→v6.9（**S-15 当场报红抓出来的**） |
| `AGENTS.md` / `CLAUDE.md` | 补一句「这件事由 S-61 守」（不写任何计数，S-51/S-56 仍绿） |
| `FEM-Bench-Aero/ROADMAP.md` | D5b 标 ✅ + 看板 + §13 重排 + v2.2 |
| `reports/diagnostics/task_d5b_{contract,report}.md` | 新建 |

## 9. 顺手证明既有闸在工作

改 RUBRIC 版本号后 `check_claims` 立刻报：

```
[FAIL] S-15  README 引用的 RUBRIC 版本      声称=6.8 实测=全部 = 6.9
```

不是我去找的，是闸抓的。修 README 后转绿。
