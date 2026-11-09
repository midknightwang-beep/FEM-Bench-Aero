# 产品成绩单 v8（五模块 / 五分母并列）

> 拍板：老王 2026-11-09 22:4x，四项全按推荐 —— ①落本页（C-045）②C-041 的「glm 第二遍 48/64」
> 更正为 46 ③模块 B/C 的 MSR 标「未测」④模块 E 进对外口径。
> **本页不是 headline。** 唯一 headline 仍是 **C-032**（模块 A），一个数字都不改。
> 数字块由 `python make_product_report.py --out …` 生成、`--check` 守新鲜度；叙事部分手写。

## 1. 这张表解决什么

当前对外只有一条 headline（C-032，v6c 卷 / legacy exam 25 条），而产品实际是三层考卷
（v8 = L1 64 + L2 80 + L3 64）都有成绩。**读者只看到「208 条考卷」和「25 条成绩」，
会误以为覆盖率只有 12%**；实际上没被 headline 覆盖的部分早就有数，只是没以产品口径并列出来。

本页把它们并列，并在每处标明分母 —— 而不是挑一个最好看的数字对外。

## 2. 数字（机器生成）

<!-- NUMBERS:BEGIN（机器生成，勿手改；`python make_product_report.py --check` 守新鲜度）-->

| 模块 | 分母 | `glm-5.3-flash` | `deepseek-v4-pro` |
|---|---:|---|---|
| A L3 legacy exam（**唯一 headline**） | 25 | **23/25 = 92.0%**／MSR 20/22 | —（headline 只报 glm） |
| B L3 `exam_v11` | 9 | 9/9 = 100.0% | 9/9 = 100.0% |
| C L3 `exam_full` | 34 | 32/34 = 94.1% | [31,32]/34 |
| D L2 澄清层（`clarify_all` / `clarify_informative`） | 64 / 45 | 46/64 = 71.9%／27/45 = 60.0% | 52/64 = 81.2%／33/45 = 73.3% |
| E L2 信息完备层 | 16 | 13/16 = 81.2% | 1/16 = 6.2% |

来源（脚本逐格实读，sha256 见 `reports/product_report_v8.json`）：

- A：`reports/baseline_scorecard_L3_v6c_p2.json`（prompt `6b90daf0…` = v2f 代）
- B/C：`reports/baseline_scorecard_L3_v7sysfix_glm.json` + `reports/baseline_scorecard_L3_v7sysfix2_ds.json`（v2f 代试跑；该代只重算 TSR ⇒ MSR 未测）
- D：`reports/l2_clarify_dual.json`（prompt `c8de26d4` = v2f 代）
- E：`reports/diagnostics/l2_v8_scores_glm.json` + `reports/diagnostics/l2_v8_scores_ds.json`

> 全卷（含 dev 30）参考：A 模型的整卷 TSR 46/55 = 83.6%、MSR 41/51（同一 artifact）。

<!-- NUMBERS:END -->

## 3. 六条读法（缺一条这张表就是误导）

1. **五个分母不可相减**：25 / 34 / 64 / 45 / 16。任意两个百分比之差都不代表能力变化。
2. **`exam_full` 高于 legacy 是换分母**：v11 的 9 条两模型全对，任何「提升」叙述都必须是
   「分母变了」，不是「模型强了」（R54）。
3. **L2 与 L3 是两层，不可互比**：L2 测「会不会问对」，L3 测「会不会做对」。
4. **L2 两模型不得排名**：glm 是同一批候选两次打分均为 46（判分稳定，但只有一批候选）；
   ds 是两批候选 52 / 46。**「ds 比 glm 高 6 条」恰好等于 ds 自己的批间波动**。
5. **不得跨代引用**：本页全部为 **prompt v2f 代**（L3 `6b90daf0…`、L2 `c8de26d4…`）。
   p2 代（`ce225186…` / `03129c56…`）的数字不可混排。
6. **v8 卷的 208 条不是任何一格的分母**：它是任务池规模，成绩只覆盖各自的题集。

## 4. 两处如实标注（不修饰）

- **模块 B/C 的 MSR 未测**：v2f 代的 v7 试跑只重算了 TSR，成绩单里 `exam*/msr` 为 `null`。
  p2 代有 MSR（`exam_v11` 8/8、`exam_full` 28/30）但**跨代不可引用**，故本页写「未测」。
  补跑另立任务，不混进 headline 决策。
- **模块 E 的 6.2%**：ds 在 16 条「该答不该问」的题上只有 1 条通过（15 条属于该答却追问）。
  这是 B 段（让「能教」）最该补的题型，**不藏**。

## 5. 复现

```bash
python make_product_report.py --json reports/product_report_v8.json \
                             --out ../FEM-Bench-Aero/PRODUCT_REPORT_V8.md
python make_product_report.py --check      # 页面与 artifact 不一致则 rc=1
```

`reports/product_report_v8.json` 逐格记录 **value + 来源文件 + 来源 sha256**；
页面数字与 artifact 不符时 `--check` 会打出 diff。

## 6. 未做的事（明确边界）

- 不改 C-032 任何数字；不把 headline 重锚到 v8（那是方案 ②，需 bridge + 全套重出）。
- 不给 v8 卷新增跑分；本页只汇总既有 claim 的数。
- 不把 L2/L3 合成一个「总分」—— 那正是 R54 要防的读法。
