# 澄清判分元数据审计（v7，W5c-6d）

- 有 `expected_clarifications` 的题：**69** 条
- 命中缺陷：**1** 条（其中 exam **1** 条）

| task_id | family | 期望字段 | 现在的 clarify_wrong_keys | 本族正确键 | 问题 |
|---|---|---|---|---|---|
| `L3_naca4412_wingbox` | wingbox | ['n_ribs'] | ['n_stringers_per_skin'] | `n_stringers_per_skin` | **把本族正确键登记成错族键** |

## 待拍板

「问对了 + 多问一句键名正确但不必要的问题」算 PASS 还是 FAIL？RUBRIC 未预注册。当前实现走 R19 的严格一侧（含任何错族键即 FAIL），但把本族正确键当错族键用，理由写错了。

## 禁止做法

不得为了让 C-033 从 22/25 变 23/25 而在本轮改元数据 —— 那是事后改判分（R18）。正确顺序：老王先拍板 over-clarify 政策 ⇒ 修元数据 + 把子串匹配改成 token 边界匹配⇒ 重打分（两模型同规格重打）⇒ 旧数字留档（D10）。
