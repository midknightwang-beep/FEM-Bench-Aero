# W5b-4 诊断：C-028（v6b）exam 8 条失败的字段级归因

> 产物性质：**诊断**，不是官方 artifact（R27）。官方成绩单见 `reports/baseline_scorecard_L3_v6b.json`。
> 探针：`feagpt_repro/_probe_w5b4_fail_fields.py`（可重跑，支持 `--out`）。
> 原始明细：`eval_runs/probe_w5b4_fail_fields_v6b.json`。
> 日期：2026-10-25

## 0. 一句话结论

exam 25 条里 8 条失败，**没有一条是"模型能力不足"的干净样本**，全部落在三类系统性缺陷上：
生成器 prompt 键名缺失（4 条）、考卷题面漏给 gold 字段（2 条）、判分对多余键过严（2 条，与第一类部分重叠）。
⇒ **68.0% 是这三类缺陷压低后的下界**，不是能力上限。

## 1. 逐条归因

| task_id | 层 | 判类 | 失败字段 | 归因类别 |
|---|---|---|---|---|
| `L3_naca4412_wingbox_str3` | interp | no_output | 3 轮修复未收敛 | **D**：生成器收敛性 |
| `L3_naca4412_wingbox_str3_T` | extrap | spec_fail | `airfoil.stringer_flange_width` | **B**：题面没给 gold 字段 |
| `L3_naca4412_wingbox_str5` | boundary | spec_fail | `airfoil.stringer_flange_width` | **B**：题面没给 gold 字段 |
| `L3_naca4412_wingbox_web1_offcentre` | extrap | spec_fail | `airfoil.web_chordwise`、`extra.end_torque`、`extra.torque_axis_dof` | **C**：多余键 + 腹板位置 |
| `L3_open_hole_panel_400x200_d20_cfrp45s_d40` | extrap | spec_fail | `params.hole_d`、`params.layup`、`material.ply_material (not in gold)` | **A**：prompt 未给开孔/铺层键名 |
| `L3_open_hole_panel_400x200_d20_offcentre` | extrap | spec_fail | `params.hole_d`、`params.hole_x`、`params.hole_y`、`load.kind` | **A**：prompt 未给开孔键名 |
| `L3_open_hole_panel_400x200_d40_offcentre` | extrap | spec_fail | `params.hole_d`、`params.hole_x`、`params.hole_y`、`extra.end_tension` | **A**：prompt 未给开孔键名 |
| `L3_open_hole_panel_600x300_d60` | extrap | spec_fail | `params.hole_d`、`extra.end_tension (not in gold)` | **A**：prompt 未给开孔键名 |

失败按族：**open_hole_panel 4/4 全败**、wingbox 4、barrel/stiffened 0。
按层：extrapolation 6、interpolation 1、boundary 1。

## 2. 三类缺陷的实证

### A. 生成器 prompt 没有约定开孔板 `hole_d / hole_x / hole_y` 键名（4 条，占一半失败）

题面写得很清楚：「中心孔直径 60 mm」「孔心位于 (120, 60) mm，直径 20 mm」。
但候选输出 `structure.params = {length, width, thickness}` —— **三个孔相关键一个都没有**。

⇒ 不是模型没读到信息，是 `gen_candidates_v2.js` 的 SYS prompt 只约定了长桁类键名
（`n_stringers_per_skin` / `stringer_height` / `stringer_kind` …），**从未列出开孔板键名**，
模型无从知道契约要求哪些键。**与 M7 教训同源：模型不行第一嫌疑 = 特征没给全。**
同一缺陷还外溢到 `load.kind`（模型给 `tip_force`/`pressure`，开孔板应为面内拉伸口径）。

### B. 考卷题面没给 gold 字段（2 条）

`gold.airfoil.stringer_flange_width` 有值，但题面只写「blade 长桁（高 20 mm、厚 2.5 mm）」，**没给缘条宽度**。
SYS prompt 明令「用户没给的尺寸参数不得编造」⇒ 模型正确地省略 ⇒ 判 fail。
这是**题面与 gold 不一致**：模型在这个字段上无解（信息不可得却要求命中）。

### C. 判分把"多余键"当失败（2 条，与 A 重叠）

模型把载荷信息同时记进 `extra.end_tension=6000` / `extra.end_torque` / `extra.torque_axis_dof`，
gold 无此键 ⇒ `spec_fidelity` 判 `(not in gold)`。属于**冗余记录**是否等同于错误的判分口径问题，
不是数值错误。RUBRIC 未对此明确表态，属未定义区。

### D. 单条收敛性（1 条）

`L3_naca4412_wingbox_str3` 3 轮修复未收敛（`UNRESOLVED`）。孤例，非系统性问题。

## 3. 构建期检查缺口（新增，建议入 R32）

R21 的构建期检查校验了「载荷方向完备」（NC-20），但**没有校验「gold 的每个 GRADED_FIELD 都必须能从 NL 推出」**。
B 类缺陷正是从这个缺口进来的。建议新增：

> **构建期断言**：对 `GRADED_FIELDS[family]` 中每个在 gold 里有非空值的字段，
> 该字段必须（a）在 NL 里给出依据，或（b）显式标记为「按族默认值」并纳入 `EXEC_CONFIG_KEYS`/默认值表。
> 否则该任务属于**不可解题**，不得进 exam。

## 4. 对结论的影响与建议

1. **C-028 的 68.0% 应如实登记为"含已知缺陷的下界"**，不得表述为能力上限。
2. 修 A 类（prompt 补键名）预计直接回收最多 4 条（+16pp exam TSR），但需重新生成候选 + 重打分 ⇒ 属新里程碑（W5c）。
3. 修 B 类需改题面 ⇒ **考卷要重新冻结**（D10：旧版本留档），成本高，建议与 W5c 一起做。
4. C 类需先在 RUBRIC 里定义「多余键」口径，否则每次都会重复计入失败。

## 5. 复现

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
"$PY" _probe_w5b4_fail_fields.py \
  --scorecard reports/baseline_scorecard_L3_v6b.json \
  --tasks reports/papers/tasks_v6b.jsonl \
  --candidates candidates_l3_v6 \
  --out eval_runs/probe_w5b4_fail_fields_v6b.json
```
