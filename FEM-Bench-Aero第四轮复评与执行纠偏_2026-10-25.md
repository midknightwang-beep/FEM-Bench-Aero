# FEM-Bench-Aero 第四轮复评与执行纠偏（W4c / W4d 后）

> **复评日期**：2026-10-25（第四轮）
> **复评对象**：W4c（契约与口径）、W4d（L3 主基线）、成绩单、负控、任务/契约、MSR 与 CLAIMS
> **复评方式**：只读核对 + 按 split 重算 + MSR 复跑 + 候选/契约逐条比对
> **结论先行**：
> **W4c/W4d 把"评测基础设施"真正立起来了；但 L3 的 headline 数字不是留出集成绩。**
> **30 条 L3 里有 9 条 train、10 条 val；真正的留出考卷是 boundary 4 + extrap 7 = 11 条。按留出集重算：TSR 7/11（63.6%）、SFR 8/10（80%）、MSR 6/11（54.5%）、T1 地板 0/11；value_added 应为 +63.6 pp（n=11，underpowered），不是 +36.7 pp（n=30）。**
> **此外，MSR 的 13 条失败里 6 条是 `No module named 'gmsh'`——环境失败被记成了模型失败；C-020 的"13 条全为模型 spec 质量"不成立。**

---

## 目录

- [0. 复评摘要](#0-复评摘要)
- [1. 变化与交付](#1-变化与交付)
- [2. 已验证的改进（credit）](#2-已验证的改进credit)
- [3. 新发现的问题](#3-新发现的问题)
- [4. 修正后的成绩单](#4-修正后的成绩单)
- [5. 下一步任务执行建议](#5-下一步任务执行建议)
- [6. 防跑偏机制（更新）](#6-防跑偏机制更新)
- [7. 评分卡](#7-评分卡)
- [8. 待拍板](#8-待拍板)
- [附录 A　证据索引](#附录-a证据索引)
- [附录 B　复现命令](#附录-b复现命令)
- [附录 C　负控清单（扩展）](#附录-c负控清单扩展)

---

## 0. 复评摘要

### 0.1 三句话结论

1. **基础设施是真进步。** W4c 修掉了上一轮的全链包装 bug、`bc/extra` 漏判、`gate3` 汇总、`fetch_data` 的 `F:` 陷阱、`validate_schema` 的 GBK 崩溃；W4d 建成了 L3 30 条任务 + 4 条澄清题 + schema 校验/错误反馈修复循环 + 全链 MSR + 15/15 负控 + 可引用模型 id。L1 冒烟也诚实地改成了 **SFR 0/19**。
2. **但 headline 数字不是留出集成绩。** L3 的 30 条包含 **train 9 + val 10**；真正的留出考卷是 **boundary 4 + extrap 7 = 11**。按留出集：TSR **7/11（63.6%）**、SFR **8/10（80%）**、MSR **6/11（54.5%）**、T1 **0/11**；value_added 应为 **+63.6 pp（n=11，underpowered）**，不是 README/CLAIMS 写的 **+36.7 pp（n=30）**。
3. **MSR 有一半失败是环境造成的。** `msr_l3.py` 用了缺 `gmsh` 的解释器；13 条 pipeline 失败里 **6 条是 `ModuleNotFoundError: No module named 'gmsh'`**，不是模型 spec 质量。用项目 Python 复跑 d1600，真实的失败是 `stringer_height must be > 0, got 0.0`——仍然失败，但归因不同。**MSR 11/30 不能作为能力估计，C-020 的"13 条全为模型质量"必须更正。**

**一句话**：**这是"基础设施已经能用、成绩单还不能引用"的状态。下一步不是继续加功能，而是把"考卷 = 留出集"和"失败归因 = 真实原因"这两件事钉死。**

### 0.2 执行总评

| 工作块 | 评分 | 一句话判断 |
|---|---|---|
| W4c：契约与口径 | **A−** | 上一轮 P0 全部落地；`spec_fidelity` 工程层 + 契约拒绝 + 负控 15/15 |
| W4d：L3 主基线 | **B−** | 基础设施建成；但 headline 混入 train/val，MSR 环境失败，任务/契约有缺口 |
| 总体 | **21/30** | **统计有效性 1 分 ⇒ 不允许把 18/30、11/30、+36.7 pp 作为对外成绩** |

### 0.3 最重要的建议

> **把"考卷"定义钉死：只报 boundary_holdout + extrapolation_test 的 11 条；train/val 单列为开发集。**
> **把 MSR 用项目 Python 重跑，先做 `gmsh` 预检；环境失败不得计为模型失败。**
> **再把 barrel 的 stringer 尺寸、额外键拒绝、澄清字段匹配修好，然后重跑一次 L3。**

---

## 1. 变化与交付

### 1.1 提交

| commit | 内容 | 关键文件 |
|---|---|---|
| `efa2b6f` | W4c 修契约与口径 | `evaluate.py`、`spec.py`、`negative_controls.py`、`gate3_all55.py`、`fetch_data.py`、`validate_schema.py` |
| `95e1018` | W4b 正式成绩单（L1 spec-copy smoke） | `CLAIMS.md` C-017/C-018 |
| `b2e9b74` | W4d L3 主基线 | `candidates_l3_v2/`、`gen_candidates_v2.js`、`msr_l3.py`、`score_baseline.py`、`schema_task.json`、`tasks.jsonl` |
| `3e47495` | W4d 收口记忆 | `MEMORY.md` |

### 1.2 上一轮 P0 的采纳对照

| 上一轮要求 | 状态 | 实测证据 |
|---|---|---|
| 解包候选 + `FEASpec` 严格化 | ✅ | `evaluate.py` 解包；`spec.py` 严格化；NC-11 报 `raise` |
| `spec_fidelity` 补 `bc/analysis/extra` | ✅ | `GRADED_FIELDS` + `bc/extra` 判定；NC-9/10/13 FAIL |
| 成绩单全链 + 全候选 + SFR/MSR | ✅ 基础设施 | `msr_l3.py` 全链；`baseline_scorecard_L3.json` 四指标 |
| 生成侧补契约 | ⚠️ 部分 | `response_format` 已加；`bc/extra` schema 仍是裸对象；barrel stringer 尺寸未 required |
| 可复现 | ⚠️ 部分 | fetch/schema 修好；MSR 用错解释器；LLM 仍走 WorkBuddy 云 |
| 关闭旧 claim | ✅ | C-017/C-018；C-020 新增 |
| 负控扩展 | ✅ | **15/15**（NC-1..14） |
| L3 接入 | ✅ | 30 条 + 4 条澄清题 |
| 关 3 汇总 | ✅ | `n_gated_pass=49`、`reported_only=6` |
| L3 split 统一 | ✅ | L3 = train 9 / val 10 / boundary 4 / extrap 7 |

---

## 2. 已验证的改进（credit）

| 改进 | 实测 |
|---|---|
| 全链契约拒绝 | 包装候选解包；无 `structure`/`airfoil` 拒绝；`bc` 空拒绝；barrel `extra.end_shear` 缺失拒绝 |
| `spec_fidelity` 工程层 | `mesh/load/bc/analysis/extra` 按 gold 权威判定；执行配置键只报不判；死字段豁免 |
| 负控 | **15/15**（PC-1 + NC-1..14，含 NC-11 契约拒绝、NC-13 L3 删块、NC-14 工程层四探针） |
| L3 任务层 | 30 条；4 条澄清题（`clarify_keywords` 可审计）；split 统一 |
| L3 生成 | `glm-5.3-flash`（可引用 id）；`json_object` + schema 校验 + 错误反馈修复 ≤3 轮；无 logits 级约束已如实标注 |
| L1 冒烟 | **SFR 0/19**（不再说 2/2）；归因 `airfoil.chord×12 + bc.clamp×7` 已落盘 |
| MSR | 全链 ccx；`msr_l3.py` 串行；输出 by-task；`fidelity ≤0.024%` 的翼盒全绿 |
| 关 3 汇总 | `n_gated_pass=49`；`reported_only=6`；`all_gated_ok=True` |
| 数据归档 | `fetch_data.py` 改 Python `tarfile`（不再被 `F:` 陷阱坑） |
| schema 校验 | `validate_schema.py` 加 UTF-8；55/55 + 2 反向探针 |
| 文档 | README 顶部接入 W4d；CLAIMS 有 C-017/C-018/C-020；旧 claim 标 superseded/retracted |

> 这些是"从考卷骨架到可跑基线"的关键一步。下面的问题不是否定这些，而是说：**成绩单还不能引用。**

---

## 3. 新发现的问题

### 3.1 P0-1　headline 混入 train/val，留出集成绩被平均掉

**实测（`baseline_scorecard_L3.json`）**

| split | n | TSR | MSR |
|---|---:|---:|---:|
| train | 9 | 8/9（88.9%） | 2/9（22.2%） |
| val | 10 | 3/10（30.0%） | 3/10（30.0%） |
| boundary_holdout | 4 | 4/4（100%） | 4/4（100%） |
| extrapolation_test | 7 | 3/7（42.9%） | 2/7（28.6%） |
| **全部** | **30** | **18/30（60.0%）** | **11/30（36.7%）** |
| **留出考卷（boundary+extrap）** | **11** | **7/11（63.6%）** | **6/11（54.5%）** |

**问题**

- README、CLAIMS C-020、看板都写 **TSR 18/30、MSR 11/30**，但这两个数把 **train 8/9** 和 **val 3/10** 混进了分母。
- 真正的 generalization 估计是 **留出 11 条**：TSR 63.6%、MSR 54.5%。两个数碰巧接近 60%，但构成完全不同——train 的 8/9 掩盖了 val 的 3/10。
- `by_split` 字段其实已经在成绩单里，但 headline 没有用它。这是**选择性报告**，不是数据问题。

**修法（P0）**

1. 成绩单分两栏：
   - **exam** = `boundary_holdout + extrapolation_test`（11 条）→ 对外 headline；
   - **dev** = `train + val`（19 条）→ 只作开发/诊断，不进对外。
2. `n_tasks_exam_expected` 改为 11；`underpowered` 改为 `n_exam < 20`（当前为 true）。
3. `value_added` 用 **exam** 的 TSR 与 **exam** 的 T1（0/11），不是 all-30。
4. README/CLAIMS/看板统一改为"留出 7/11（63.6%），n=11 underpowered"；30 条总数只作"任务层规模"。

---

### 3.2 P0-2　MSR 的 13 条失败里 6 条是 `gmsh` 环境失败

**实测（`msr_pipeline_failure_attribution.json`）**

| 失败类型 | 条数 | 性质 |
|---|---:|---|
| `ModuleNotFoundError: No module named 'gmsh'` | **6** | **环境/解释器** |
| `TypeError: unexpected keyword`（`spar_web_thickness` / `ply_material` / `distribution` / `support` / `edge_support`） | **7** | 模型自创键（真实模型问题） |

**复跑验证**：用项目 Python 重跑 `L3_fuselage_barrel_d1600_l1600_str8_frm3`，真实失败是：

```
ValueError: fuselage_barrel: stringer_height must be > 0, got 0.0
```

不是 gmsh。也就是说：**6 条"gmsh 失败"里至少 1 条的真实原因是模型/任务问题，其余 5 条未知**。

**问题**

- `msr_l3.py` 用 `sys.executable` 启动 `run_pipeline.py`；运行 MSR 的解释器缺 `gmsh`，于是 6 条在 import 阶段就失败，被记为 `pipeline: false`。
- 失败归因文件写的是 gmsh，C-020 却写"13 条全为模型 spec 质量"——**两者矛盾，且都不准确**。
- MSR 11/30 因此不是有效的能力估计；它至少低估了 6 条的可能性，也错报了失败原因。

**修法（P0）**

1. `msr_l3.py` 启动时做**依赖预检**：`import gmsh`、`import numpy` 失败 ⇒ **直接报环境错误并退出**，不得把候选记为 FAIL。
2. 用项目 Python（或声明 `--python`）跑全链；README 写死解释器路径。
3. 失败归因分三层：`env` / `contract` / `model` / `solver`；环境失败单独计数，不进 MSR 分母。
4. 重跑 6 条 gmsh 案例；更新 C-020 的归因与 MSR。
5. 在 CLAIMS 中把当前 MSR 11/30 标为 **superseded（环境污染）**，新 claim 写"待重跑"。

---

### 3.3 P0-3　barrel 的 stringer 尺寸：任务没说、schema 没要求、builder 却要求

**实测**

- 5 条 barrel L3 候选的 `structure.params` 里，`stringer_height` 全是 `0` 或 `None`，`stringer_thickness` 全是 `0` 或 `None`。
- 5 条 barrel 的 MSR 全部失败；d1600 的真实错误是 `stringer_height must be > 0`。
- `schema_task.json` 的 barrel 分支 required 只有：
  `diameter / length / thickness / n_stringers / n_frames`——**没有 stringer 尺寸**。
- L3 的 barrel NL 只说"8 根长桁、3 个普通框（blade 剖面）"，**没给 stringer 高度/厚度**。
- `gen_candidates_v2.js` 的 system prompt 却说：
  "stringer_height/stringer_thickness/stringer_kind/stringer_flange_width 仅当 n_stringers_per_skin>0 时才需要填写"——
  它用的是 **wingbox 的键名** `n_stringers_per_skin`，不是 barrel 的 `n_stringers`；模型因此把 stringer 尺寸填成 0。

**这是一个任务/契约设计缺陷，不是单纯的模型能力问题。**

**修法（P0）**

1. **任务层**：barrel 的 NL 要么给出 stringer 高度/厚度，要么明确写"按族默认值（20 / 2.5 mm）"；同时把默认值写进 `truth.json` 的 `assumptions`。
2. **schema**：barrel 的 `params` 增加 `stringer_height` / `stringer_thickness`（条件 required：`n_stringers > 0`），或明确 `additionalProperties: false` + 不要求，让模型**省略**而不是填 0。
3. **prompt**：把 `n_stringers_per_skin` 的规则改成按族键名；barrel 用 `n_stringers`，且"未给尺寸时省略，不要填 0"。
4. **builder**：要么对缺失/0 的 stringer 尺寸使用默认值，要么在契约层拒绝；不能等到 `_validate` 才报错。
5. **SFR**：`GRADED_FIELDS['fuselage_barrel']` 增加 `stringer_height` / `stringer_thickness`（若它们影响模型），或明确声明为 builder-default 不判。

> 同类问题也出现在 panel：`GRADED_FIELDS['stiffened_panel']` 只有 `length/width/thickness/n_stringers`，没有 stringer 尺寸；panel 候选若省略/填错，SFR 可能 PASS、MSR 失败。

---

### 3.4 P0-4　额外键：schema 允许、SFR 不罚、builder 崩溃

**实测**

- panel 候选的 `bc` 里出现 `support` / `edge_support`；open_hole 的 `load`/`material` 里出现 `distribution` / `ply_material`；wingbox 出现 `spar_web_thickness`。
- `spec_fidelity` 只判 `GRADED_FIELDS` 里的键；`bc` 对非翼盒 `bc_skip`；`material` 只判 `name/E/nu`；`load` 只判任务输入出现过的键。
- 结果：这些**额外键不被罚**，SFR 可能 PASS；`FEASpec` 构造器 / builder 遇到未知 kwarg 直接 `TypeError`，MSR 失败。
- `schema_task.json` 的 `structure.params`、`bc`、`analysis`、`extra` 大多没有 `additionalProperties: false`，所以 schema 也放行。

**影响**

- SFR 与 MSR 的差距（64% vs 36.7%）有相当一部分来自这里：**SFR 判"关键字段对"，MSR 判"能不能建"**。
- 一个 agent 可以"字段都对、模型建不出来"仍拿 SFR 高分。这不是 benchmark 想要的信号。

**修法（P0）**

1. **schema**：所有 block 设 `additionalProperties: false`；`bc`/`extra` 按族给 required 键。
2. **spec_fidelity**：白名单外的额外键一律 FAIL（`METADATA_KEY_NAMES` 只保留真正的元数据；`distribution`/`support`/`ply_material` 不在白名单）。
3. **契约闸**：在 `run_pipeline` 前做一次 `FEASpec` 构造 + builder `_validate` 的"试建"，失败 ⇒ `contract` 闸 FAIL，不进求解。
4. **负控**：NC-16（panel 加 `bc.support`）、NC-17（open_hole 加 `load.distribution`）⇒ 必须 FAIL。

---

### 3.5 P0-5　澄清判分用单字关键词，panel 的错字段被判对

**实测**

4 条澄清题的 `clarify_keywords` 是**单字**：

| 任务 | 缺字段 | keyword | 候选实际问的 |
|---|---|---|---|
| `L3_naca4412_wingbox` | `n_ribs` | `肋` | `n_ribs` ✅ |
| `L3_open_hole_panel_400x200_d20` | `hole_d` | `孔` | 开孔直径 ✅ |
| `L3_fuselage_barrel_d1600...` | `n_frames` | `框` | 静默编造 ❌ |
| `L3_stiffened_panel_600x600` | `n_stringers` | `长桁` | **`n_stringers_per_skin`（错键）** ❌→✅ |

判分逻辑是 `any(k in text for k in kws)`。panel 候选问的是 **wingbox 的键** `n_stringers_per_skin`，不是 panel 的 `n_stringers`；但因为文本里有"长桁"，被判 `clarify_ok`。

**影响**

- TSR 18/30 里至少有 **1 条是错字段被判对**（panel，train）。
- 单字关键词可被任何"顺带提一句"的澄清文本命中；这是可被 gaming 的判据。
- C-020 的"问对=对"没有在字段级落实。

**修法（P0）**

1. 判分改为**字段级**：候选必须问 `expected_clarifications` 里的字段（接受同义键/别名表），不是命中单字。
2. `clarify_keywords` 改为字段名/别名列表（如 `['n_stringers','长桁根数']`），并要求"问题指向该字段"。
3. 新增负控 **NC-15**：问错字段但含关键词 ⇒ 必须 FAIL。
4. 对 4 条澄清题重判，更新 TSR。

---

### 3.6 P0-6　SFR 把"编造"计为 PASS；rubric 是看过 30 条候选后改的

**（a）SFR 与"编造=错"不一致**

`score_baseline.py`：

```python
spec_cat = sel('spec_pass', 'spec_fail', 'fabricated')
sfr_p = sum(1 for r in spec_cat if r['category']=='spec_pass'
            or (r['category']=='fabricated' and r.get('n_fail')==0))
```

barrel d1600 是 `fabricated`（澄清题静默编造 `n_frames`），但它的字段 17/17 全对，于是 **SFR PASS**。TSR 正确地 FAIL，SFR 却 PASS。C-020 说"问对=对，编造=错"，但这句话只对 TSR 成立。

**（b）rubric 是 post-hoc 改的**

`evaluate.py` 里明确写着：

- `EXEC_CONFIG_KEYS`：`# W4d 拍板（2026-10-25，工程层判+配置层只报）`
- `METADATA_KEY_NAMES`：`# W4d 补充（实测 30 条候选后）`
- `bc_skip`：非翼盒 `bc` 不判

其中"实测 30 条候选后"是明确的信号：**评分规则是在看到模型输出之后调整的。** 即使调整有理（执行配置确实不该判），也必须**预注册**，否则 SFR/TSR 与上一版不可比，也无法排除"为了让分数好看而放宽"。

**修法（P0）**

1. SFR 明确二选一：① 编造一律 FAIL；或 ② SFR 只作"字段保真"参考，不进 TSR/对外 headline。当前 C-020 的 64% 应标注"含 1 条编造"。
2. 把 `EXEC_CONFIG_KEYS` / `METADATA_KEY_NAMES` / `bc_skip` 写成**预注册文档**（`RUBRIC.md`），在跑基线**之前**冻结；W4d 这版标注为"post-hoc，需重跑确认"。
3. 重跑时同时给"严格 rubric"与"工程层 rubric"两列，差值必须解释。

---

### 3.7 P1 级问题

| # | 问题 | 证据 | 修法 |
|---|---|---|---|
| P1-1 | `C-019` 行格式损坏 | `CLAIMS.md` 第 25 行有重复片段 | 重写为一行；15/15 |
| P1-2 | `gen_candidates_v2.js` 仍有硬编码 fallback key | `process.env... || 'wbpk_...'` | 删除 fallback；只读 env |
| P1-3 | L3 考卷 v3 未冻结/tag | tag 仍 `v1.0-rc`；`tasks.jsonl` 三轮修改 | 打 `v1.0-l3-v3`；记录 sha256 |
| P1-4 | MSR 分母含 4 条澄清题 | `msr_l3.py` 分母 30；无 spec 计 FAIL | 分母改为 spec-required（25/26）；澄清单列 |
| P1-5 | `by_split` 只有 TSR | `score_baseline.py` | 增加 SFR/MSR by split |
| P1-6 | `bc_skip` 造成族间不对称 | 非翼盒 bc 不判 | 至少判 bc 的键集合/类型；或声明 builder 不消费 |
| P1-7 | barrel/panel stringer 尺寸不在 `GRADED_FIELDS` | 见 §3.3 | 加入或声明 builder-default |
| P1-8 | `negative_controls.json` 打印含 emoji 崩溃 | GBK 控制台 | 结果文件去 emoji 或 print 前转义 |
| P1-9 | C-020 "翼盒 12 条中 11" 分母不清 | 翼盒 15 条含 1 澄清 | 改为"spec-required 14 条中 11"或给明细 |
| P1-10 | `trivial_baselines_L3` 的 `all_pct` 被当成 exam | T1 all 23.3% 由 train 7/9 驱动；exam 0/11 | `score_baseline` 改用 `exam_pct` |
| P1-11 | `n_tasks_exam_expected=30` | 留出 11 | 改为 11；`underpowered=true` |
| P1-12 | L3 prompt/schema 用 wingbox 键名 | `n_stringers_per_skin` vs `n_stringers` | 按族统一键名 |

---

## 4. 修正后的成绩单

### 4.1 对外（留出 11 条）

| 指标 | 值 | 说明 |
|---|---|---|
| TSR | **7/11（63.6%）** | boundary 4/4 + extrap 3/7 |
| SFR | **8/10（80.0%）** | boundary 4/4 + extrap 4/6（含 1 条 fabricated 的字段保真） |
| MSR | **6/11（54.5%）** | boundary 4/4 + extrap 2/7；**2 条 extrap 因 gmsh 未有效评测：d1600 复跑仍失败于 `stringer_height=0`，d2000_str12 待复跑 ⇒ 真值 ∈ [6/11, 7/11]** |
| T1 地板 | **0/11（0%）** | `trivial_baselines_L3.json` exam |
| value_added | **+63.6 pp** | 7/11 vs 0/11；**n=11 < 20 ⇒ underpowered，不得判 PASS** |
| FPR | 编造 1/4、过度澄清 1 | 澄清题 4 条 |

### 4.2 开发集（19 条，不进对外）

| split | TSR | MSR |
|---|---:|---:|
| train | 8/9（88.9%） | 2/9（22.2%） |
| val | 3/10（30.0%） | 3/10（30.0%） |

> **train TSR 8/9 但 MSR 2/9** 是一个非常重要的信号：模型"能答对字段"，但"建不出模型"。差距主要来自 barrel/panel 的 stringer 尺寸、额外键、extra 格式。这正是 §3.3/§3.4 要修的。

### 4.3 族别 MSR

| 族 | MSR |
|---|---:|
| wingbox | 11/15（73.3%） |
| open_hole_panel | 0/6 |
| fuselage_barrel | 0/5 |
| stiffened_panel | 0/4 |

> MSR 是**翼盒单族**的成绩；其余三族 0，且其中 6 条是 gmsh/TypeError 环境或契约问题。C-020 的"MSR 11/30"应改为"翼盒 11/15；其余三族 0，待修契约/环境后重跑"。

---

## 5. 下一步任务执行建议

> 原则：**先修度量与契约，再重跑；不要在当前成绩单上继续加功能。**
> 建议分三个工作块，W4e/W4f 为 P0，W5 为扩量。

### 5.1 W4e（1 天）：把成绩单修到可引用

| # | 任务 | 具体动作 | 验收 |
|---|---|---|---|
| 1 | MSR 用项目 Python 重跑 | `msr_l3.py` 加 `import gmsh` 预检；用 `C:/Users/.../Scripts/python.exe`；失败分 `env/contract/model/solver` | 6 条 gmsh 案例有真实归因；MSR 可复现 |
| 2 | 成绩单分 exam/dev | exam = boundary+extrap（11）；dev = train+val（19）；headline 用 exam | `n_tasks_exam_expected=11`；`underpowered=true` |
| 3 | value_added 用 exam T1 | `T1_retrieval['exam_pct']`（0/11），不是 `all_pct` | Δ=+63.6pp，标 underpowered |
| 4 | SFR 与"编造=错"对齐 | fabricated ⇒ SFR FAIL，或 SFR 不进 headline | 两条口径一致 |
| 5 | 澄清判分字段级 | 用 `expected_clarifications` + 别名表，不用单字关键词 | panel 错键被判 FAIL |
| 6 | `by_split` 全指标 | TSR/SFR/MSR by split | 一张表可审计 |
| 7 | C-019/C-020 更正 | 修格式；MSR 标 superseded；新增 held-out claim | CLAIMS 一致 |

### 5.2 W4f（1–2 天）：把契约修到"可建"

| # | 任务 | 具体动作 | 验收 |
|---|---|---|---|
| 8 | barrel stringer 尺寸 | NL 给默认值或明说"默认 20/2.5"；schema 条件 required；prompt 按族键名 | 5 条 barrel 能建 |
| 9 | 额外键拒绝 | schema `additionalProperties:false`；`spec_fidelity` 白名单外 FAIL；契约试建 | panel `support`、open_hole `distribution` FAIL |
| 10 | panel stringer 尺寸 | `GRADED_FIELDS` 加入或声明 builder-default | SFR 与 MSR 对齐 |
| 11 | rubric 预注册 | 新建 `RUBRIC.md`：工程层/配置层/死字段/元数据白名单；跑前冻结 | 重跑前后 rubric 不变 |
| 12 | 冻结 L3 v3 | tag `v1.0-l3-v3` + sha256；记录 30 条任务 | 可复现 |

### 5.3 W5（3–5 天）：重跑与扩量

| # | 任务 | 验收 |
|---|---|---|
| 13 | 用冻结 v3 + 预注册 rubric 重跑 L3 | 给出 exam 11 条的 TSR/SFR/MSR + CI |
| 14 | 留出集扩到 ≥20 | 新增 interior/boundary 点；n≥20 才判 value_added |
| 15 | L2 澄清基线 | L2 的 clarify 题型单独成绩 |
| 16 | A3 修复基线 | 注入缺陷 + 闸报告 → 修复成功率 |
| 17 | 失败样本回流 | 每条失败有 env/contract/model/solver 归因 |

### 5.4 明确不要做

- ❌ 不要把 18/30、11/30、+36.7 pp 写进对外材料；
- ❌ 不要在修好 gmsh 预检前重跑/引用 MSR；
- ❌ 不要在没有冻结 v3 的情况下继续改考卷；
- ❌ 不要用单字关键词判澄清；
- ❌ 不要再用 `all_pct` 当 exam；
- ❌ 不要在 post-hoc rubric 上继续调参。

---

## 6. 防跑偏机制（更新）

### 6.1 新增红线条

| # | 红线 | 违反示例 |
|---|---|---|
| **R15** | **对外 headline 只能用留出集（boundary+extrap）；train/val 单列开发集** | 用 18/30 当 generalization |
| **R16** | **环境失败不得计为模型失败**；MSR 启动必做依赖预检 | gmsh 缺失记成 pipeline FAIL |
| **R17** | **澄清判分必须字段级**；单字关键词不得作为通过依据 | panel 问 `n_stringers_per_skin` 判对 |
| **R18** | **rubric 必须预注册**；看过模型输出后修改的 rubric 标 post-hoc，需重跑 | "实测 30 条候选后"加白名单 |
| **R19** | **schema / builder / grader 三者必须一致**；可判的 spec 必须可建 | barrel stringer 尺寸 schema 不要求、builder 要求 |
| **R20** | **SFR 与 TSR 的"编造"口径必须一致**；不一致时不得并列报告 | fabricated 计 SFR PASS |

### 6.2 负控扩展

现有 15 条保留，新增：

| 编号 | 注入 | 期望 | 当前 |
|---|---|---|---|
| **NC-15** | 问错字段但含关键词（panel 问 `n_stringers_per_skin`） | FAIL | ❌ 当前判对 |
| **NC-16** | panel `bc.support` 额外键 | FAIL | ❌ 当前 SFR 可能 PASS |
| **NC-17** | open_hole `load.distribution` 额外键 | FAIL | ❌ 当前 SFR 可能 PASS |
| **NC-18** | MSR 运行器缺 gmsh | **环境错误退出**（不是候选 FAIL） | ❌ 当前记 FAIL |
| **NC-19** | 成绩单把 train/val 计入 headline | 检查器拒绝 | 待加 |

### 6.3 CLAIMS 修正

| claim | 处置 |
|---|---|
| C-020（TSR 18/30 / MSR 11/30 / +36.7pp） | **superseded**（混入 train/val + gmsh 环境） |
| 新 C-021 | 留出 11 条：TSR 7/11、SFR 8/10、MSR 6/11（2 条待重跑）、T1 0/11、Δ+63.6pp underpowered |
| 新 C-022 | 开发集 19 条：train 8/9+2/9、val 3/10+3/10，仅诊断 |
| 新 C-023 | L3 v3 冻结：tag + sha256 |
| C-019 | 修格式；15/15 有效 |

### 6.4 节奏（不变）

- 每周十维评分卡 + 红线条；
- 每个 W 块结束做完整复评 + 负控 + 全链正控；
- 每 2 个里程碑独立复评；
- 执行人不能给自己的评分器签字。

---

## 7. 评分卡

| # | 维度 | 分数 | 理由 |
|---|---|---:|---|
| 1 | 目标一致性 | 3 | benchmark/verifier 主轴未变 |
| 2 | 任务有效性 | 2 | L3 30 条 + 澄清题；但 barrel/panel 契约缺口、task v3 未冻结 |
| 3 | 判分有效性 | 2 | 工程层 + 契约拒绝 + 15 负控；但澄清单字、SFR 编造、额外键漏判 |
| 4 | 证据等级 | 2 | MSR 有、by_split 有；但 headline 混入 train/val、失败归因错 |
| 5 | 可复现性 | 2 | fetch/schema 修好；MSR 解释器错；LLM 云服务仍限内部 |
| 6 | 版本治理 | 2 | git 全程；tag 仍 v1.0-rc；L3 v3 未 tag |
| 7 | 文档真实性 | 2 | README/CLAIMS 大体诚实；C-020 的"13 条全模型质量"不成立 |
| 8 | 统计有效性 | 1 | headline n=30 混 train/val；exam n=11；value_added 用 all_pct |
| 9 | 范围纪律 | 3 | 红线条与不做清单在 |
| 10 | 计划执行 | 2 | W4c/W4d 按期，但成绩单不可引用 |
| **总分** | | **21/30** | **统计有效性 1 ⇒ No-Go（对外引用）** |

> 说明：21 vs CLAIMS 自评 29。差异全部来自"headline 混入 train/val + MSR 环境失败 + post-hoc rubric"三项；修完 W4e/W4f 可回到 26–28。

---

## 8. 待拍板

| # | 事项 | 建议 |
|---|---|---|
| 1 | 是否承认 L3 headline 必须改为留出 11 条 | **接受**；18/30 只作开发集 |
| 2 | 是否承认 MSR 11/30 受 gmsh 污染、需重跑 | **接受**；C-020 标 superseded |
| 3 | 是否接受"环境失败不计模型失败" | **接受**；MSR 预检 |
| 4 | 是否接受澄清判分改字段级 | **接受**；单字关键词不可用 |
| 5 | 是否接受 barrel/panel 契约补齐 + 额外键拒绝 | **接受**；这是"可建"的前提 |
| 6 | 是否接受 rubric 预注册（`RUBRIC.md`） | **接受**；post-hoc 必须标 |
| 7 | 是否接受 L3 v3 冻结/tag | **接受**；否则成绩不可复现 |
| 8 | 下一步先做 W4e 还是 W4f | **先 W4e（度量）再 W4f（契约）**；两者可并行，但重跑必须在两者之后 |

---

## 附录 A　证据索引

| 结论 | 证据 |
|---|---|
| L3 30 条含 train 9/val 10 | `tasks/tasks.jsonl`；`baseline_scorecard_L3.json == by_split` |
| 留出 11 条 TSR 7/11 | `baseline_scorecard_L3.json` per_task + split |
| SFR 8/10 | 同上（spec_pass + fabricated 字段保真） |
| MSR 6/11 | 同上 msr_section + split |
| T1 exam 0/11、all 23.3% | `trivial_baselines_L3.json` |
| value_added 36.7pp 用 all_pct | `score_baseline.py` 第 133 行 |
| 6 条 gmsh | `msr_pipeline_failure_attribution.json` |
| d1600 真实错误 | 复跑 `evaluate.py`：`stringer_height must be > 0` |
| barrel 候选 stringer 0/None | `candidates_l3_v2/*barrel*.json` |
| schema barrel required 无 stringer 尺寸 | `schema_task.json` barrel 分支 |
| panel 问错键 | `candidates_l3_v2/L3_stiffened_panel_600x600.json`；`clarify_keywords=['长桁']` |
| 单字关键词 | `tasks/tasks.jsonl` 的 4 条 clarify 题 |
| fabricated 计 SFR | `score_baseline.py` 第 91-103 行；d1600 sfr_pass |
| post-hoc rubric | `evaluate.py` "W4d 补充（实测 30 条候选后）" |
| C-019 格式损坏 | `CLAIMS.md` 第 25 行 |
| 硬编码 fallback key | `gen_candidates_v2.js` 第 16-18 行 |
| 负控 15/15 | `eval_runs/negative_controls.json` |
| 关 3 49 | `gate3_all55_d37.json` |
| fetch tarfile / schema UTF-8 | `fetch_data.py` / `validate_schema.py` |

## 附录 B　复现命令

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# 按 split 重算
"$PY" - <<'PY'
import json
sc=json.load(open('eval_runs/baseline_scorecard_L3.json',encoding='utf-8'))
tasks={json.loads(l)['task_id']:json.loads(l) for l in open('tasks/tasks.jsonl',encoding='utf-8') if json.loads(l)['input_level']=='L3'}
per={r['task_id']:r for r in sc['per_task']}
msr={r['task_id']:r for r in sc['msr_section']['per_task']}
for sp in ['train','val','boundary_holdout','extrapolation_test']:
    ids=[t for t in tasks if tasks[t]['split_v2']==sp]
    print(sp, len(ids), 'TSR', sum(per[t]['tsr_pass'] for t in ids), 'MSR', sum(msr.get(t,{}).get('msr_pass',False) for t in ids))
PY

# MSR 单条复跑（项目 Python，含 gmsh）
"$PY" evaluate.py --task-id L3_fuselage_barrel_d1600_l1600_str8_frm3 \
  --spec candidates_l3_v2/L3_fuselage_barrel_d1600_l1600_str8_frm3.json

# 负控
PYTHONIOENCODING=utf-8 "$PY" negative_controls.py

# schema
PYTHONIOENCODING=utf-8 "$PY" validate_schema.py
```

## 附录 C　负控清单（扩展）

| 编号 | 注入 | 期望 | 当前 |
|---|---|---|---|
| PC-1 | gold raw spec（全链） | PASS | ✅ |
| NC-1..7 | 字段注入 / L2 错值 / 静默默认 | FAIL | ✅ |
| NC-8 | L3 30 条存在 | 结构检查 | ✅ |
| NC-9 | 删 `bc` | FAIL | ✅ |
| NC-10 | 删 `extra.end_shear` | FAIL | ✅ |
| NC-11 | 包装候选 | 拒绝契约 | ✅ |
| NC-12 | 未知 family | 拒绝 | ✅ |
| NC-13 | L3 删 mesh/load/bc/extra | FAIL | ✅ |
| NC-14 | 工程层四探针 | 口径护住 | ✅ |
| **NC-15** | 问错字段但含关键词 | FAIL | ❌ 待加 |
| **NC-16** | panel `bc.support` | FAIL | ❌ 待加 |
| **NC-17** | open_hole `load.distribution` | FAIL | ❌ 待加 |
| **NC-18** | MSR 缺 gmsh | 环境错误退出 | ❌ 待加 |
| **NC-19** | headline 含 train/val | 检查器拒绝 | ❌ 待加 |

---

> **本文件是第四轮复评的产物，不修改任何既有项目文件。**
> 本轮复跑了 1 条 gmsh 失败案例、按 split 重算了 L3 指标、逐条比对了 5 条 barrel 候选与 4 条澄清题；产物在 `eval_runs/`（已 gitignore）。
> 下一轮请先确认：**exam = 11 条留出集；MSR 预检；澄清字段级；rubric 预注册。**
