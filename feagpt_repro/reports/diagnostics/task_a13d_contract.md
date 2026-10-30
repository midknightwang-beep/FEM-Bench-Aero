# TASK_CONTRACT — T-A13d（N-28：澄清判据的字符串匹配边界加固）

- task_id: **T-A13d**（N-28 独立立项；续 T-A13c）
- agent / date: 蜗子 / 2026-10-30
- SOT read: `CLAIMS.md`（C-032 headline / C-041 supporting）/ `RUBRIC.md`（v6.4，R1–R69）/ `reports/INDEX.md` / `CONFLICT.md`（N-28）

## SOT 实读（开工前，全部现场读）

| 项 | 值 |
|---|---|
| HEAD | `c237b56`（memory+report，T-A13c 收口后） |
| 当前 headline（唯一） | **C-032**（v6c 55 条 / exam 25）—— **本轮不得动**（R48） |
| 当前考卷 | `tasks/tasks.jsonl`，sha256 `caf0f6c3be8131c5b817a0bacfcca8ad3893fcfb95e29d8d9b525866a63e195a` |
| 当前 rubric | v6.4（R1–R69） |
| 门禁（本轮 pre-flight 实读） | 负控 **65/65**；`check_claims` **33 claims / 68 artifacts / 57 语义项 全过** |
| 判据实现（**唯一一处**） | `score_baseline.py:169 judge_clarify_field_level`；`score_l2.py` / `negative_controls.py` 均 **import**，无第二份实现（已 grep 确认） |
| 受影响成绩单 | `l2_scores_v7_{glm,ds}.json`、`baseline_scorecard_L3_v7_{glm,ds}.json` |

## ★★ 必须先说清的一件事：N-28 不是新发现，是旧账未清

我在 T-A13c 里把 N-28 记成「新发现」——**这是错的**。`_audit_clarify_meta.py`（W5c-6d，早于本轮）
第 13 行已明确记录：

> ② **匹配方式有隐患**：`judge_clarify_field_level` 用子串 `in` 判错族键
> ⇒ 若把 `n_stringers` 登记为错族键，它会在 `n_stringers_per_skin` 里**命中**，把正确答案判错

它指向的正是同一条子串通道，并给出了正确处置顺序。**但两者覆盖的是同一函数的两侧、互不重叠**：

| | 旧账（W5c-6d，`_audit_clarify_meta.py`） | 本轮补（N-28 的 alias 侧） |
|---|---|---|
| 代码位置 | `hit_wrong = [k for k in wrong if k in text]` | `hit = [a for a in al if a in text]` |
| 出错的**方向** | **假红**（写对了正确键却被错族键的子串吃掉 ⇒ 判 FAIL） | **假通过**（写的是别的键却被短别名的子串吃掉 ⇒ 判 PASS） |
| 后果 | 数字偏低（会被察觉） | 数字偏高（**不会被察觉**） |
| 当时是否量化 | 只查了「wrong key 是正确键的子串」 | 本轮量化：3 个字段、15 条题位 |
| 是否已修 | **没有**（脚本结论是「记录缺陷、下轮定夺」） | 本轮一并修 |

⇒ 本轮**不重复记账，而是把旧账结清**：`CONFLICT.md` 的 N-28 必须改成「旧账未清（W5c-6d 已记假红侧）」，
并注明本轮补的是 alias 侧。**不得**让 N-28 冒充新发现。

## 只改 X（单变量：判据的**匹配方式**，一个函数、三行）

1. `score_baseline.py` 新增私有助手 `_alias_hit(alias, text)`，`judge_clarify_field_level` 的
   **两处**裸子串（`hit_wrong` 与 `hit`）都改用它。规则：

   ```python
   def _alias_hit(alias, text):
       """别名命中：**纯 ASCII 标识符按 token 边界**，其余（中文/短语）按子串。"""
       if re.fullmatch(r'[A-Za-z0-9_]+', alias):
           return re.search(r'(?<![A-Za-z0-9_])' + re.escape(alias) + r'(?![A-Za-z0-9_])', text) is not None
       return alias in text
   ```

   **为什么只约束 ASCII**：中文没有词边界概念，且 25 个 alias 中 21 个是中文短语
   （`翼肋`/`孔径`/`多少根长桁`…）—— 对它们加边界只会把「翼肋数量」判成不命中，
   **把判据改坏**。真正的子串风险只在 4 个纯 ASCII 标识符上（`n_ribs`/`hole_d`/`n_frames`/`n_stringers`）。

2. 顺手清理 `hit_wrong` 的**死代码**：现有写法是

   ```python
   hit_wrong = [k for k in wrong if k in text] if isinstance(wrong, list) else \
       [k for k in (wrong if isinstance(wrong, list) else []) if k in text]
   ```

   两个分支**完全等价**（右侧的 `if isinstance(wrong, list)` 恒为 True —— 因为它是 False 分支）。
   这是纯重构，**行为等价的构造性论证**：False 分支里 `isinstance(wrong, list)` 必为 False ⇒ 列表为空 ⇒
   结果恒 `[]`；而 True 分支已返回真值 ⇒ 整式恒等于 `[k for k in wrong if k in text] if isinstance(wrong, list) else []`。

3. **RUBRIC**：新增红线 **R70「判据的字符串匹配必须有边界」**（通用条款，跨判据）；R17 下加一句指向 R70。

## ★ 本轮**不**改的东西（R69：放宽/收紧都必须写明边界）

| 不改 | 为什么 |
|---|---|
| 考卷 `tasks/tasks.jsonl` | R65：v7 冻结 |
| `clarify_wrong_keys` / `clarify_aliases` **元数据** | 那是**改判分输入**，且绑定 over-clarify 政策（`_audit_clarify_meta.py` 的开放问题：问对了+多问一句键名正确但不必要的算 PASS 还是 FAIL）—— **政策未预注册，本轮不碰** |
| over-clarify 政策 | 同上；本轮只修字符串匹配，**不表态** |
| 任何模型 / prompt / 候选 | 本轮不跑模型 |
| headline | R48 |
| L2 的「字面命中键名」口径 | R19 的选择，不改 |

**边界（R69 三条齐全）**：
- **哪里仍必须为 0**：改后 L2 两模型与 L3 两模型的**判类变化数必须为 0**（逐条比，不是抽样）。
- **例外必须带 reason**：若出现任何判类变化，必须逐条写明任务 id、旧判、新判、原因；**且不得把变化吸收进对外数字**。
- **例外不得进入对外数字**：C-041 / C-032 / C-040 的数字**一个都不许动**。

## 验收命令 + 期望输出

```bash
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# ① 构造性零差���：改造前先落一份「旧判据」基线，再逐条比（不是「看着差不多」）
"$PY" _diff_judge_a13d.py --out reports/diagnostics/judge_diff_a13d.json   # 必须 n_changed=0

# ② L3 逐叶子零差异（R67：先声明允许项，再逐条比）
"$PY" score_baseline.py --reuse …          # 重出两份 L3 成绩单（步骤见 INDEX）
"$PY" _regress_scorecard.py --base … --new …   # 必须 RESULT: PASS

# ③ L2 两模型重判（判据变了 ⇒ 必须重跑，不许改旧成绩单）
"$PY" score_l2.py --cand candidates_l2_v7_glm --out reports/l2_scores_v7_glm.json --label "…"
"$PY" score_l2.py --cand candidates_l2_v7_ds  --out reports/l2_scores_v7_ds.json  --label "…"

# ④ 两道闸，顺序固定
"$PY" negative_controls.py                    # 必须 66/66（新增 NC-64）
"$PY" check_claims.py --json "$TEMP/…"        # 必须全过
```

**期望**（这是**预注册**的预期，不是事后解释）：
- L2：glm `49/64`、ds `36/64` 及三档分母**逐数不变**
- L3：`_regress_scorecard.py` 出 `RESULT: PASS`，TSR/SFR/MSR **逐叶子不变**

## 停止条件（R-A11）

- 考卷 sha 变化 ⇒ 立刻停（v7 冻结）
- **L2 或 L3 出现任何判类变化** ⇒ 停，写 CONFLICT，**不许吸收进数字**（先证明「失效是真的」再动）
- 中文别名的判定有任何变化 ⇒ 停（说明边界正则设计错了，它只该约束 ASCII）
- 负控 / `check_claims` 不全绿 ⇒ 停
- 若发现 `judge_clarify_field_level` 还有第三份实现 ⇒ 停（本轮前提是「只有一处」）

## post-hoc?

**是，但已授权且方向受限。** 判据在 T-A13a/b/c 已冻结出分，本轮改它**形式上就是事后修正**。
三条约束使它可接受：
1. **老王已拍板立项**（N-28 是我主动登记、他批准做，不是我自己想改）；
2. **改动只有一处、且是纯字符串正确性**（不加权、不改阈值、不改字段语义）；
3. **真实数据零差异**（104 条 clarify 文本逐条比，见 `judge_diff_a13d.json`）⇒
   本轮**不改变任何对外数字**，只消除一个潜伏漂移面。

**★ 更正（写契约时我说错了一句，实测推翻）**：原写「改动方向只能是关掉假通过通道 —— 让数字有
**下降**的可能、没有**上升**的可能」。**这是错的**：探针 P6 证明同一处改动会**同时修掉假红**
（`wrong_keys=['n_stringers']` 时，模型写 `n_stringers_per_skin` 会被子串吃掉而误判 FAIL），
那一侧会让数字**上升**。
⇒ 准确的表述是「**双向修正，两侧都在真实数据上 0 触发**」；正因如此，**必须**先有构造性零差异，
否则无法排除净效应非零。**不得**事后把它读成「单方向的加强」。

**不得**在零差异不成立时把结果「读成」改进（例：「改完 ds 从 36 变 38，说明判据更公平」——停，那是
引入了未知变量，必须回退并另立项）。

## 交付报告路径

`feagpt_repro/reports/diagnostics/task_a13d_n28_report.md`
