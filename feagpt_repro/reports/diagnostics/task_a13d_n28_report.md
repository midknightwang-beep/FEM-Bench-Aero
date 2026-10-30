# T-A13d 交付报告 — N-28 判据边界加固（R70）

- 日期：2026-10-30　agent：蜗子
- 契约：`task_a13d_contract.md`
- 产物：`reports/diagnostics/judge_diff_a13d.json`（三路判据证据）

## 一、这次改了什么（一个函数、两处匹配）

```python
# score_baseline.py（新增）
def _alias_hit(alias, text):
    if re.fullmatch(r'[A-Za-z0-9_]+', alias):
        return re.search(r'(?<![A-Za-z0-9_])' + re.escape(alias) + r'(?![A-Za-z0-9_])',
                         text) is not None
    return alias in text

# judge_clarify_field_level 内两处（原来都是裸子串 `in text`）
hit_wrong = [k for k in (wrong if isinstance(wrong, list) else []) if _alias_hit(k, text)]
hit       = [a for a in al if _alias_hit(a, text)]
```

**只约束纯 ASCII 标识符**（`n_ribs`/`hole_d`/`n_frames`/`n_stringers` 共 4 个）；
21 个中文短语别名（`翼肋`/`孔径`/`多少根长桁`…）走原来的子串分支，**一行行为都不变** ——
中文没有词边界，加边界等于把判据改坏（`翼肋` 会判不中「翼肋数量」）。

## 二、★★ 最重要的一件事：N-28 是旧账，不是新发现

`_audit_clarify_meta.py`（**W5c-6d，早于本轮**）第 13 行原文：

> ② **匹配方式有隐患**：`judge_clarify_field_level` 用子串 `in` 判错族键
> ⇒ 若把 `n_stringers` 登记为错族键，它会在 `n_stringers_per_skin` 里**命中**，把正确答案判错

我在 T-A13c 里把它记成「新发现」——**错了**。两者是**同一函数的两端、互不重叠**：

| | 旧账（W5c-6d） | T-A13c 补的 |
|---|---|---|
| 位置 | `hit_wrong`（错族键侧） | `hit`（别名命中侧） |
| 方向 | **假红**（数字偏低，会被察觉） | **假通过**（数字偏高，**不会被察觉**） |
| 当时处置 | 「记录缺陷、下轮定夺」，**未修** | 本轮与旧账一并修 |

已在 `CONFLICT.md` 的 N-28 顶部加「定性更正」，并注明旧脚本的结论原文是「记录缺陷、下轮定夺」。

## 三、★★ 我写契约时说错了一句，被探针当场推翻

契约原写：「改动方向只能是关掉假通过通道 —— 让数字有**下降**的可能、没有**上升**的可能」。

**探针 P6 证明这是错的**：`wrong_keys=['n_stringers']` 时，模型写 `n_stringers_per_skin`
会被旧的裸子串吃掉而误判 FAIL —— 修掉它是**假红修复**，会让数字**上升**。

⇒ 准确表述是「**双向修正**」。已回改契约（保留原文并标注「实测推翻」），
并把「任何『这次改动只会更严』的直觉都要用探针证伪」写进 `CONFLICT.md` 的教训段。

## 四、构造性零差异证据（三路判据）

**为什么要三路**：只比「旧逻辑 vs 真实调用点」，在改前两者必然相同 —— 那是**自比**，证明不了任何事。
必须先证明「新匹配方式确实会与旧的不同」，再证明「最终实现就是被测的那一个」。

| 路 | 是什么 | 作用 |
|---|---|---|
| `oracle` | 旧判据的**逐字副本**，冻结在 `_diff_judge_a13d.py` 里 | 永不随源码漂移的参照物 |
| `composed` | 用**真实的** `_alias_hit` 组合出的判据 | 证明「新方式真的会分歧」 |
| `actual` | **真实的** `judge_clarify_field_level` | 证明最终实现 == 被测的那个 |

### 4.1 合成探针 8 向（4 须分歧 / 4 须不变）

| 探针 | 场景 | oracle | 新 | 判定 |
|---|---|---|---|---|
| P1 | 省略 `n_stringers`，只写 `n_stringers_per_skin` | True | **False** | ✅ 分歧（假通过已关） |
| P2 | `structure.params.n_stringers`（前是点） | True | True | ✅ 不变（不得过严） |
| P3 | `n_stringers（根数）`（后是中文括号） | True | True | ✅ 不变 |
| P4 | 省略 `thickness`，只写 `rib_thickness` | True | **False** | ✅ 分歧 |
| P5 | 省略 `width`，只写 `stringer_flange_width` | True | **False** | ✅ 分歧 |
| P6 | `wrong_keys=[n_stringers]`、写 `n_stringers_per_skin` | **False** | **True** | ✅ 分歧（假红已修） |
| P7 | 中文「翼肋数量」命中「翼肋」 | True | True | ✅ 不变 |
| P8 | 中文短语「多少根长桁」 | True | True | ✅ 不变 |

**探针必须真分歧**——若 4 向「须分歧」的探针没分歧，说明它没在测任何东西（那就是假绿）。

### 4.2 真实数据 + 四份成绩单

| 项 | 规模 | 变化 |
|---|---|---|
| clarify 文本 × 三路判据 | **104 条** | **0** |
| L2 glm 成绩单 | 661 叶子 | **0**（`_regress_scorecard` RESULT: PASS，无 allow 项） |
| L2 ds 成绩单 | 660 叶子 | **0** |
| L3 glm 成绩单 | 2098 叶子 | **0** |
| L3 ds 成绩单 | 2137 叶子 | **0** |

**最强的一条**：四份成绩单重跑后 `git diff --stat` **完全为空**（逐字节相同）。
L3 用 `msr_l3.py --reuse <自身>`（**不启动求解器**，判分重算、MSR 照抄）。

⇒ **C-032 / C-040 / C-041 的数字一个都没动。**

## 五、闸

- **R70**（新红线）：判据的字符串匹配必须有边界，且写明「ASCII 边界 / 中文子串 / 必须仍命中的三种写法」。
- **S-58**（新语义检查，三层）：`_alias_hit` 有 `re.escape`+两侧边界+ASCII 分流 / 判分函数体（去注释后）零裸子串且两处都调用 / 行为两向不得失效。
  ★ 静态层的价值：负控只覆盖它列举的路径；**只改 `hit_wrong` 那一处**这类回退，静态层能抓、负控未必。
- **NC-64 六向**：假通过已关（**且断言原因是「未命中」**）/ 两向不过严 / 假红已修（且无 `wrong_keys_hit`）/ 中文不变 / `thickness` 通道已关。

## 六、本轮**没做**的事（R69 边界）

| 没做 | 为什么 |
|---|---|
| `clarify_wrong_keys` / `clarify_aliases` **元数据** | 那是改**判分输入**，且绑定 over-clarify 政策（`_audit_clarify_meta.py` 的开放问题：问对了+多问一句键名正确但不必要的算 PASS 还是 FAIL）—— **政策至今未预注册**，本轮只修字符串匹配层，**对政策不表态** |
| 考卷 / prompt / 候选 / 模型 | 本轮不跑模型，v7 冻结（R65） |
| headline | R48 |

## 七、发现但未改的（留给下一轮）

- **`evaluate.py:437 evaluate_clarification` 是第二套 L2 评测路径**（旧 `clarification.json` 协议）。它用**精确字段名集合匹配**（`f not in asked`），**没有** N-28 风险，所以本轮不需要改。但两条 L2 路径并存这件事本身值得记：当前 L2 跑分走 `score_l2.py` → `judge_clarify_field_level`，不走它。
- **over-clarify 政策**仍未预注册（`_audit_clarify_meta.py` 提出，W5c-6d 至今）。它挡着「修元数据」这条路。
