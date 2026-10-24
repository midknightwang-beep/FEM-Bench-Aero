# FEM-Bench-Aero 第三轮复评与执行纠偏（W4a / W4b 后）

> **复评日期**：2026-10-24（第三轮）
> **复评对象**：W4a（修判分）与 W4b（LLM 基线）之后的评测器、任务层、schema、候选生成、成绩单与数据归档
> **复评方式**：只读核对 + 复跑负控 + 全链对照实验（gold / 包装候选 / 解包候选）
> **结论先行**：
> **W4a 真正修好了上一轮的两个假阳性；但 W4b 不是"模型基线"，而是一次"L1 抄写冒烟"。当前 5 条候选的 spec 保真率是 2/5，全链模型成功率是 0/5；已提交的"2/2"来自只看到 2 条候选的旧成绩单。两条"通过"的柱壳候选 `bc/analysis/extra` 全空：d1600 解包后全链偏差 93.95%，d2000 包装路径偏差 7.93%（解的是默认翼盒）。**
> **在修好"候选契约 + 全链判分 + 成绩单口径"之前，不能宣称 W4b 完成。**

---

## 目录

- [0. 复评摘要](#0-复评摘要)
- [1. 变化与交付](#1-变化与交付)
- [2. 已验证的改进（credit）](#2-已验证的改进credit)
- [3. 新发现的问题](#3-新发现的问题)
- [4. 对下一阶段的影响](#4-对下一阶段的影响)
- [5. 纠偏方案](#5-纠偏方案)
- [6. 防跑偏机制（更新）](#6-防跑偏机制更新)
- [7. 更新后的路线图](#7-更新后的路线图)
- [8. 待拍板](#8-待拍板)
- [附录 A　证据索引](#附录-a证据索引)
- [附录 B　复现命令](#附录-b复现命令)
- [附录 C　负控清单（扩展）](#附录-c负控清单扩展)
- [附录 D　评分卡](#附录-d评分卡)

---

## 0. 复评摘要

### 0.1 三句话结论

1. **W4a 是实打实的进步。** `spec_fidelity` 上线后，上一轮的两个假阳性（肋厚 4→8、L2 问对填错）现在都被负控抓住；负控 **9/9**；L2 轮换到 13 个字段、泄漏清零；L3 30 条并入任务层；`boundary_holdout` 改名落地；schema 拆两份并 55/55 通过；关 3 分级为 34/15/6；CLAIMS 账本与 M14 硬限制都进了单一数字源。
2. **W4b 不是基线，是冒烟。** 成绩单用 `skip_solve=True`，只判 `spec_fidelity`，不跑求解；提交时只看到 **2 条**候选（22:08），之后又生成了 3 条（22:12–22:17），全量重跑是 **2/5（40%）**；两条"通过"的柱壳候选 `bc/analysis/extra` 全空：d1600 解包后全链偏差 **93.95%**，d2000 包装路径偏差 **7.93%**（解的是默认翼盒）。
3. **全链路径还有一个静默降级 bug。** 候选文件是 `{task_id, spec:{...}}` 包装，`evaluate.py` 全链路径把整个文件直接传给 `run_pipeline --spec`，`FEASpec` 读不到 `structure` 就默认成翼盒（`fea_case`），**不报错**。两条柱壳候选的全链结果都变成了默认翼盒（max_disp 2.365439），而不是柱壳（3.006972 / 2.569232）。**更严重的是 L3：** 任务输入只有 NL，`spec_fidelity` 拿不到 mesh/load 键；一个删掉 mesh/load/bc/extra 的 L3 候选仍然 **21/21 PASS**。

**一句话**：**W4a 修好了"判分字段"，但 W4b 暴露了"契约不完整 + 全链静默降级 + 成绩单口径错位"三个更底层的问题。先把这三件事修掉，再谈 LLM 能力。**

### 0.2 执行总评

| 工作块 | 评分 | 一句话判断 |
|---|---|---|
| W4a：修判分 | **A−** | 负控、L2、L3、schema、关 3、CLAIMS 都是真改进；但漏了 `bc/analysis/extra`，全链路径未修 |
| W4b-1：T0/T1/T2 地板 | **A−** | 地板设计正确（考卷 T0 0/19、T1 0/19、T2 19/19），但仍是 spec-only |
| W4b-2：LLM 基线 | **D** | 不是模型基线；只跑 L1、只判 spec、只覆盖 2 条；全量 2/5、全链 0/5 |
| **总体** | **22/30** | **统计有效性 1 分 ⇒ 未达 24 且单项 ≤1 ⇒ 不允许宣称 W4b 完成** |

### 0.3 最重要的建议

> **把 W4b 改名为"L1 spec-copy smoke"，不要写进对外成绩；先做 W4c（契约 + 全链判分 + 成绩单口径），再做 W4d（L3 + schema 约束解码的真基线）。**

---

## 1. 变化与交付

### 1.1 提交

| commit | 内容 | 关键文件 |
|---|---|---|
| `4e2d84e` | W4a 修判分（上一轮 P0 全项） | `spec_fidelity`、`negative_controls.py`、`make_tasks.py`、`schema_task/truth.json`、`validate_schema.py`、`fetch_data.py`、`CLAIMS.md`、`gate3_all55.py` |
| `c8bcf84` | W4b-1 T0/T1/T2 地板 | `trivial_baselines.py` |
| `98acf48` | W4b-2 LLM 链路 + 冒烟 2/2 | `gen_candidates.js`、`score_baseline.py`、`candidates/` |

### 1.2 上一轮 P0/P1 的采纳对照

| 上一轮要求 | 状态 | 实测证据 |
|---|---|---|
| P0-1 `spec_fidelity` 字段级闸 | ✅ 基本完成 | `evaluate.py :: spec_fidelity`；NC-1/2 由 PASS 变 FAIL（实测） |
| P0-2 负控套件 | ⚠️ 完成但覆盖不全 | **9/9**（实测）；缺 `bc/extra/包装` 三类 |
| P0-3 L2 轮换 + 去泄漏 | ✅ 完成 | L2 覆盖 **13 个字段**；`description` 已剥离；显式泄漏 **0** |
| P0-3 L3 接入 | ✅ 基本完成 | `tasks.jsonl` 140 行 = L1 55 + L2 55 + L3 30；`input_source=template_human_designed` |
| P0-4 关 3 分级 | ✅ 完成（汇总有 bug） | `gate3_all55_d37.json`：34 field + 15 scalar + 6 reported-only；但 `n_gated_pass=15` |
| P0-5 数据归档 | ⚠️ 数据对、脚本坏 | 归档 89.6 MB / 55 case / SHA256 匹配；`fetch_data.py` 用 shell `tar` 在 `F:` 路径上失败 |
| P1-1 schema 双份 | ✅ 完成（控制台 bug） | `schema_truth` + `schema_task` 各 55/55；反向探针 2/2 拒；GBK 控制台打印崩溃 |
| P1-2 单一数字源 | ✅ 完成 | `external_numbers.md` 已写 34/15/6 + M14 三条硬限制 |
| P1-3 主 README 接入 | ✅ 完成 | README 顶部已改为"从这里开始"，链接 ROADMAP/tasks/evaluate/CLAIMS |
| P1-4 split 统一 | ⚠️ L1/L2 完成，L3 漏 | L1/L2 = `boundary_holdout`；**L3 仍有 4 条 `id_test`** |
| P1-5 工程问题 | ⚠️ 部分 | `equilibrium` 仍未实现；`n_nodes` 仍为 None |
| 平凡基线 T0/T1/T2 | ✅ 完成 | 考卷 T0 **0/19**、T1 **0/19**、T2 **19/19** |
| LLM 基线 | ❌ 未成立 | 见 §3 |

---

## 2. 已验证的改进（credit）

这一节必须写在问题前面：**W4a 不是纸面改动，下面每一条都复跑过。**

| 改进 | 实测 |
|---|---|
| `spec_fidelity` 强制闸 | gold 23/23 PASS；NC-1（肋厚 4→8）FAIL；NC-2（L2 问对填错）FAIL |
| 负控套件 | **9/9 ok**（PC-1 PASS + NC-1..7 FAIL + NC-8 结构检查） |
| L2 轮换 | 翼盒 7 字段 × 34 条、开孔板 4 字段 × 11 条、柱壳 3 字段 × 6 条、平板 2 字段 × 4 条，**共 13 字段** |
| L2 去泄漏 | `description` 已从 L2 输入剥离；显式泄漏 **0** |
| L3 并入 | 140 行任务；30 条 L3；`input_source` 改为 `template_human_designed` |
| boundary_holdout | L1/L2 的 6 条已从 `id_test` 改名，理由与证据在 `make_tasks.py` 注释 |
| schema | `schema_truth` 55/55、`schema_task` 55/55；死 airfoil 拒、越界 55° 拒 |
| 关 3 分级 | 34 field + 15 scalar-disp + 6 reported-only；`external_numbers.md` 已同步 |
| M14 硬限制 | 未收敛 ≥13%、2.63% 组合插值、all-LOO 5.35% 全部进 `external_numbers.md` 与 README |
| CLAIMS 账本 | C-001…C-016；C-014/C-015/C-016 明确 retracted/superseded |
| 数据归档 | 89,571,593 B；55 个 case 目录；55 个 spec.json；SHA256 匹配 `SHA256SUMS.txt` |
| README | 顶部 30 行已变成"这是什么 / 从这里开始 / 三条硬限制" |
| 平凡基线 | 考卷（boundary 6 + extrap 13）T0 **0/19**、T1 **0/19**、T2 **19/19** |

> 这些是"项目从数据集变成 benchmark"的关键基础设施，W4a 完成得不错。下面的问题不是否定这些，而是说：**基础设施还差三块关键拼图。**

---

## 3. 新发现的问题

### 3.1 P0-1　全链路径的"包装 + 静默降级"bug

**现象**

`gen_candidates.js` 产出的候选是**包装格式**：

```json
{"task_id": "...", "input_level": "L1", "model": "auto", "clarify": null, "spec": { ... }}
```

`evaluate.py :: evaluate_one` 的全链路径把**整个候选文件**直接传给 `run_pipeline.py --spec`：

```python
subprocess.run([PY, run_pipeline.py, '--spec', cand_spec_path, ...])
```

`FEASpec.from_dict` 在顶层找不到 `structure`/`airfoil`，于是使用默认 `StructureSpec()`（`family="wingbox"`），**不报错**。

**实测**

| 对象 | 结果 |
|---|---|
| 包装的柱壳候选 `L1_fuselage_barrel_d1600...` | `fea_case` 的 truth：**family=wingbox**，5074 节点，max_disp **2.365439**（默认翼盒） |
| 同上，期望 | 柱壳 d1600：max_disp **3.006972** |
| 解包后的同一候选 | 正确建出柱壳（minJ 0.4636、语义 6/6），max_disp **0.181773**（缺 BC/端载） |
| gold 柱壳 spec | 正确建出柱壳，max_disp **3.006972**，全链 PASS |

**影响**

- 全链评测对**所有** LLM 候选都无效：它解的是默认翼盒，不是候选声明的模型。
- 更糟的是**静默**：没有报错、没有警告，`pipeline_rc=0`，`spec_fidelity` 甚至还 PASS（因为它在解包后的 candidate 上判）。这直接违反项目自己的设计原则"边界外显式拒绝，不做静默降级"。
- 若把这种结果拿去和真值比，会得出"候选很差"的错误结论；若只看 `spec_fidelity`，又会得出"候选很好"的错误结论。**两头都错。**

**修法（P0）**

1. `evaluate.py` 在全链路径**先解包** `{spec: ...}`，把解包后的 spec 写进 `run_dir/candidate.spec.json`，再传给 `run_pipeline`。
2. `FEASpec.from_dict` 改为**严格**：顶层既无 `structure` 又无 `airfoil` ⇒ `raise ValueError("not a FEASpec")`；`structure.family` 缺失 ⇒ `raise`，绝不默认 wingbox。
3. 新增负控 **NC-11**：传包装文件 ⇒ 必须 FAIL（而不是解默认翼盒）；**NC-12**：`structure.family` 改成未知值 ⇒ 必须 FAIL。

---

### 3.2 P0-2　`spec_fidelity` 漏判 `bc` / `analysis` / `extra`，候选"半成品"仍 PASS

**现象**

当前 `GRADED_FIELDS` 只覆盖：

- 翼盒：`airfoil` 15 个字段；
- 其他族：`structure.params` 的几何字段；
- 材料：`name/E/nu`（density/yield 只报不判）；
- 网格/载荷：任务输入里出现过的键。

**没有覆盖**：`bc`、`analysis`、`extra`。

**实测：LLM 候选的真实内容**

| 候选 | `bc` | `analysis` | `extra` | `spec_fidelity` | 全链 |
|---|---|---|---|---|---|
| 柱壳 d1600 | `{}` | `{}` | `{}` | **23/23 PASS** | 解包后 **93.95%** 偏差 |
| 柱壳 d2000_str12 | `{}` | `{}` | `{}` | **23/23 PASS** | 包装路径 **7.93%** 偏差（解的是默认翼盒） |
| 翼盒 n_ribs3_chord1000 | `{}` | `{}` | `{}` | **FAIL**（缺 `airfoil.chord` 等） | 未跑 |

柱壳的 `extra` 里是**端部剪力 50 kN + 端部弯矩 50 kN·m**——这是该工况的两个主载荷。候选把 `extra` 写成 `{}`，等于只保留了内压，**不是同一个模型**。但 `spec_fidelity` 不判 `extra`，所以 23/23 PASS。

**根因有三层**

1. **评分器**：`GRADED_FIELDS` 不含 `bc/analysis/extra`。
2. **任务提示**：`gen_candidates.js` 的 L1 prompt 只给了 `airfoil/params`、`load`、`mesh`、`material`，**没有给 `bc/analysis/extra`**。模型没有机会抄对这些块。
3. **schema**：`schema_task.json` 里 `bc/analysis/extra` 只是 `{"type":"object"}`，没有 required 字段，也没有 family 条件。约束解码同样不会要求它们。

**影响**

- "spec 保真率"会把**不可运行的半成品**算成 PASS。
- 全链 MSR 会为 0，但原因不是"模型不会建模"，而是"任务没给全 + 评分没判全"。
- 这会让 W4d 的 L3 基线同样失真：L3 的 NL 里虽然提到"根部固支 / 端部剪力 / 端部弯矩"，但模型不知道这些要落到 `bc`/`extra` 的哪些键上。

**修法（P0）**

1. **评分**：把以下块加入 `spec_fidelity`：
   - `bc`：`root_surface`、`clamp`（按族；非翼盒的 `edge`/`fixed_edges` 等）。
   - `analysis`：`step_type`（static）；`solver` 不作为真值（它是执行选择）。
   - `extra`：按族——柱壳 `end_shear/end_moment/shear_axis/moment_axis`；其余族只判 gold 中非空的键。
2. **任务输入**：L1 的 prompt 必须把 `bc/analysis/extra` 一并给出；L2 已给全量 spec；L3 的 NL 要明确说明"约束在根部/四边、端部剪力/弯矩"这些语义。
3. **schema**：`schema_task.json` 为 `bc/extra` 增加 family 条件 required；`schema_truth.json` 保持严格。
4. **负控**：新增 **NC-9**（删 `bc`）、**NC-10**（删 `extra.end_shear`）、**NC-13**（L3 候选删 mesh/load/bc/extra）⇒ 必须 FAIL。

#### 3.2.1　L3 专项：任务输入只有 NL ⇒ mesh/load/bc/extra 全部漏判

**实测**

`L3_naca4412_wingbox` 的任务输入只有 `input.nl`，`_input_mesh_load_keys()` 返回 `([], [])`。我构造一个"只保留几何/材料、删掉 mesh/load/bc/extra"的 L3 候选，跑 `spec_fidelity`：

```
pass True   fields 21   fail 0   failed []
```

**也就是说：L3 候选可以完全不带网格、载荷、边界和 extra，仍然 21/21 PASS。**

**原因**

`spec_fidelity` 的"考什么判什么"逻辑依赖任务输入里的 `mesh`/`load` 键：

- L1/L2 有 `spec_normalized`，键存在 ⇒ 会判；
- L3 只有 `nl`，键为空 ⇒ 回退到 `set(candidate) ∩ set(gold)`；候选没写 mesh/load，交集为空 ⇒ **不判**；
- `bc`/`analysis`/`extra` 本来就不在 `GRADED_FIELDS` 里 ⇒ 更不判。

**影响**

这是为 W4d 准备的 L3 主基线**最致命**的缺口：一个 agent 只要把几何参数和材料写对，就能在"没有任何可执行块"的情况下拿满分。全链虽然会失败，但当前成绩单不跑全链。

**修法（P0，并入 §3.2）**

- 评分器改为**按族契约**判定，而不是按任务输入键判定：
  ```
  REQUIRED_BLOCKS = {
    wingbox:          ['airfoil', 'mesh', 'load', 'bc', 'analysis'],
    open_hole_panel:  ['structure.params', 'mesh', 'load', 'bc', 'analysis'],
    fuselage_barrel:  ['structure.params', 'mesh', 'load', 'bc', 'analysis', 'extra'],
    stiffened_panel:  ['structure.params', 'mesh', 'load', 'bc', 'analysis'],
  }
  ```
  每个 block 的 required keys 写死；候选缺任一 ⇒ FAIL。任务输入只决定"给了什么"，不决定"该判什么"。
- L3 的 NL 要显式给出 BC/载荷语义（根部固支、翼尖 500 N、内压 + 端剪 + 端弯），并在 prompt 里映射到 `bc`/`extra` 的键。
- 新增负控 **NC-13**：L3 候选删 mesh/load/bc/extra ⇒ 必须 FAIL。

---

### 3.3 P0-3　成绩单是 `skip_solve` + 部分候选，已提交的 2/2 是旧快照

**现象**

- `score_baseline.py` 用 `evaluate_one(..., skip_solve=True)`，只判 `spec_fidelity`，**不跑求解**。
- 成绩单 `eval_runs/baseline_scorecard.json` 的时间是 **22:08:42**。
- 候选文件时间：22:06:41、22:08:41、22:12:12、22:14:34、22:17:31。
- 也就是说：**成绩单生成时只有 2 条候选**；之后生成的 3 条翼盒候选从未进入这份成绩单。
- 我把 5 条全部重跑：**2/5（40%）**；`boundary_holdout` 0/2、`extrapolation_test` 2/3；3 条翼盒候选的首失败字段都是 `airfoil.chord`——实际上它们的 `airfoil` 只有 `code`，整组字段都缺。

**再加上 §3.1/§3.2 的全链问题**：

| 口径 | 结果 | 含义 |
|---|---|---|
| 已提交的"2/2" | 100% | 只覆盖 2 条，且是 spec-only |
| 全量 spec_fidelity | **2/5（40%）** | 5 条 L1 候选的字段保真率 |
| 全链 MSR | **0/5（0%）** | 3 条 spec FAIL；2 条全链 FAIL（d1600 解包 93.95% / d2000 包装 7.93%） |

**影响**

- "TSR 2/2"会被当成模型能力；实际是"2 条柱壳候选抄对了字段，但模型不可运行"。
- 统计上 n=5、无 CI，`value_added` 却判 **PASS**（T1 0% → LLM 40%，Δ40 pp）。**n=5 的 40% 与 n=5 的 0% 不可分辨**，不能写 PASS。
- 这违反 CLAIMS 账本自己的规则：账本里**没有**任何 LLM 基线 claim，而 commit message 已经在说 2/2。

**修法（P0）**

1. `score_baseline.py` 默认跑**全链**（或至少同时输出 SFR 与 MSR 两列），不再用 `skip_solve` 当默认。
2. 评分前先**清点候选**：候选数 ≠ 任务数时打印 `WARNING: partial candidate set (5/110)`；成绩单必须记录 `n_candidates / n_tasks`。
3. `value_added` 在 `n < 20` 时一律判 **UNDERPOWERED**，并给 bootstrap CI；不得判 PASS。
4. 已提交的 `2/2` 在 CLAIMS 中登记为 **superseded**，新 claim 写"2/5 SFR / 0/5 MSR（n=5，underpowered）"。
5. 每次生成候选后**重跑成绩单**；用文件哈希或 mtime 断言"成绩单晚于全部候选"。

---

### 3.4 P0-4　LLM 基线不可外部复现，且生成未做 schema 约束

**现象**

| 项 | 实测 |
|---|---|
| 服务 | `@tencent-ai/workbuddy-cloud-sdk`，endpoint `https://fem-bench-baseline.app.workbuddy.host` |
| 凭证 | `gen_candidates.js` 里**硬编码** `wbpk_...` publishable key |
| 模型 | `models.find(m => m.disabled !== true)`，scorecard 记 `model: "auto"` |
| 约束解码 | 注释写 `response_format json_object`，**代码里没有设置**；仅用正则抽 JSON |
| 锁文件 | `package-lock.json` 被 `.gitignore` 排除；SDK 是 `0.1.4-dev...` 开发版 |
| 外部可复现 | 外部用户拿不到同一个 endpoint / key / 模型版本 |

**影响**

- 这不是"通用大模型基线"，是**内部云服务 + 匿名模型**的一次性冒烟；不能引用、不能对比、不能复现。
- 硬编码 key 即使"publishable"，也已经进入 git 历史；若它有 Origin 之外的能力，需要轮换。
- 未做 `response_format`/schema 约束，模型可以输出缺字段的 JSON——这正是 3 条翼盒候选 `airfoil` 只有 `code` 的直接原因。
- 项目非功能目标写的是"全流程可离线部署、数据不出域"；把任务 spec 发到外部云服务与该目标冲突（虽然当前数据是合成的，风险低，但原则要写清）。

**修法（P0）**

1. key 移到环境变量 `WORKBUDDY_PUBLISHABLE_KEY`；源码只读 env；`.env` 进 `.gitignore`；评估是否需要轮换。
2. 提交 `package-lock.json`；把 SDK 版本钉死；记录 endpoint。
3. **记录并固定模型**：scorecard 必须写 `model.id`、`model.name`、调用日期；`auto` 不可引用。
4. `gen_candidates.js` 设置 `response_format: {type: "json_object"}`；下一版改用 `schema_task.json` 做 structured output/约束解码。
5. 若基线要对外，改用有公开版本的模型；若只用内部服务，成绩单必须标 **"internal reference, not externally reproducible"**。

---

### 3.5 P0-5　L1 是"抄写题"，L3 才是建模题；基线却只跑了 L1

**现象**

`gen_candidates.js` 的 L1 prompt：

```text
请严格按以下参数生成 spec JSON（参数必须逐一采用，不得改动任何数值）：
{...airfoil...}
载荷: {...}；网格: {...}；材料: {...}
```

它把答案原样给出，只要求"照着抄"。3 条翼盒候选的 `airfoil` 只输出了 `code`，chord/span/蒙皮厚/肋数等整组字段缺失（首失败字段是 `airfoil.chord`）——这是**指令遵循/格式**失败，不是建模能力失败。

**L2** 是"给一个缺一个字段的 spec，问对问题"；**L3** 是"给自然语言，生成 spec"。后者才是产品要测的能力。

**修法（P0/P1）**

1. **基线主口径改为 L3**；L1 只作"格式/抄写"下限，L2 作"澄清"下限。
2. L3 的 prompt 要加：目标 schema（`schema_task`）、族参数说明、BC/载荷语义、失败时输出 `CLARIFY`。
3. 用 `schema_task` 做约束解码后，L1 应该接近 100%；届时 L1 的价值只剩"格式检查"，不应作为能力 headline。
4. 报告分列：`L1-SFR`、`L2-SFR`、`L3-SFR`、`L3-MSR`，不要合成一个 TSR。

---

### 3.6 P1 级问题

| # | 问题 | 证据 | 修法 |
|---|---|---|---|
| P1-1 | 关 3 汇总 `n_gated_pass=15`，漏了 34 条 field-level | `gate3_all55.py` 只统计 `gate_status=="GATED"`；`evidence_levels.field=34` | `n_gated_pass` 改为 49；`all_gated_ok` 纳入 field-level |
| P1-2 | L3 仍用 `id_test`，L1/L2 用 `boundary_holdout` | `tasks.jsonl`：L3 有 4 条 `id_test` | 对 L3 应用 `ID_TEST_RENAME`，统一为 `boundary_holdout` |
| P1-3 | `fetch_data.py` 在 Windows 上失败 | shell `tar` 把 `F:` 当远程主机：`Cannot connect to F: resolve failed` | 改用 Python `tarfile`，或加 `--force-local` / 传 `/f/...` |
| P1-4 | `validate_schema.py` 在 GBK 控制台崩溃 | `UnicodeEncodeError: '\u2705'` | 加 `sys.stdout.reconfigure(encoding='utf-8')`；或去掉 emoji |
| P1-5 | `equilibrium` 仍未实现 | tasks 声明 `equilibrium`；`evaluate.py` 无此闸 | 实现 ΣFORC 残差闸，或从 task 声明删除 |
| P1-6 | `mesh_quality.n_nodes` 仍为 None | `evaluate.py` 的表达式永远返回 None | 从 mesh 摘要正确读取 |
| P1-7 | `package-lock.json` 被 gitignore | `.gitignore` 尾部 | 提交锁文件；SDK 版本钉死 |
| P1-8 | CLAIMS 无 LLM 基线条目 | `CLAIMS.md` C-001…C-016 | 新增 C-017（2/5 SFR / 0/5 MSR）与 C-018（2/2 superseded） |
| P1-9 | README "跑评测 = --use-gold" 易误读 | README 第 13 行 | 改称"正控/冒烟"；LLM 命令单列 |
| P1-10 | `validate_schema` 依赖 `jsonschema`，但 README 未写环境 | 项目 env 有，`python -I` 无 | README 写死项目 Python 路径 |
| P1-11 | L2 prompt 说"缺失项标 MISSING"，任务实际是删键 | `make_tasks.make_l2_input` 用 `del`，无 `MISSING` 标记 | 要么加 `MISSING` 标记，要么改 prompt |
| P1-12 | `score_baseline.py` 只评 L1 | 只读 `input_level=='L1'` 的任务 | W4d 增加 L2/L3 分列 |

---

## 4. 对下一阶段的影响

### 4.1 现在不能说的话

- ❌ "W4b 完成，LLM 基线 TSR = 2/2 / 40%"——这是 spec-only、partial-set、skip-solve。
- ❌ "LLM 能建对柱壳"——两条柱壳候选 `bc/analysis/extra` 全空，解包后全链 93.95% 偏差。
- ❌ "候选很差，模型不行"——全链路径本身把包装候选解成了默认翼盒，失败里混着 harness bug。

### 4.2 现在能说的话

- ✅ W4a 的 `spec_fidelity` 能抓住**已登记字段**的错误（负控 9/9）。
- ✅ L2 的字段轮换与去泄漏已完成（13 字段、0 泄漏）。
- ✅ 数据归档可校验（55 case / SHA256）。
- ✅ 平凡基线地板成立（T0 0/19、T1 0/19、T2 19/19）。

### 4.3 正确的下一步

```
W4c（1–2 天）修契约与口径
  1. 解包候选 + FEASpec 严格化 + NC-11/12
  2. spec_fidelity 补 bc/analysis/extra + NC-9/10/13
  3. 成绩单全链 + 全候选 + SFR/MSR 双列 + n/CI
  4. prompt/schema 补 bc/extra；response_format 约束
  5. key 入 env、锁文件入库、模型版本记录

W4d（3–5 天）跑真基线
  1. L3 为主口径（NL→spec），L1/L2 作下限
  2. schema_task 约束解码
  3. 全链 MSR + 分族/分 split + 失败归因
  4. 与 T0/T1 地板对比，n≥20 才判 value_added
```

---

## 5. 纠偏方案

### 5.1 P0（W4c，1–2 天）

| # | 动作 | 交付物 | 验收 |
|---|---|---|---|
| 1 | 候选解包 + `FEASpec` 严格化 | `evaluate.py` / `spec.py` | NC-11/12 FAIL；gold PASS |
| 2 | `spec_fidelity` 补 `bc/analysis/extra`；按族 `REQUIRED_BLOCKS` 判，L3 也判 mesh/load | `GRADED_FIELDS` + 报告 | NC-9/10/13 FAIL；gold PASS |
| 3 | 成绩单全链 + 全候选 + 双口径 | `score_baseline.py` | `n_candidates/n_tasks` 必填；SFR/MSR 分列 |
| 4 | 生成侧补契约 | `gen_candidates.js` + `schema_task.json` | `response_format` 生效；`bc/extra` required |
| 5 | 可复现 | env key + lockfile + model id | 外部可读的 `REPRODUCE.md` |
| 6 | 关闭旧 claim | `CLAIMS.md` | 2/2 → superseded；新 claim 写 2/5 SFR / 0/5 MSR |

### 5.2 P1（W4c 同期）

- 修 `gate3_all55.py` 汇总（49 not 15）；
- L3 `id_test` → `boundary_holdout`；
- `fetch_data.py` 改 `tarfile`；
- `validate_schema.py` 加 UTF-8；
- 补 `equilibrium` 或删声明；
- 修 `n_nodes`；
- README 的"跑评测"改成"正控/冒烟"。

### 5.3 P2（W4d 之后）

- L3 真基线 + 约束解码；
- 内插型 ID test（v1.1）；
- L2 澄清基线；
- A3 修复题；
- 负样本/拒答、扩族、多工况。

---

## 6. 防跑偏机制（更新）

### 6.1 十维评分卡（本轮）

| # | 维度 | W4a 自评 | 本轮复评 | 理由 |
|---|---|---:|---:|---|
| 1 | 目标一致性 | 3 | 3 | 主轴仍是 benchmark/verifier |
| 2 | 任务有效性 | 2 | 2 | L2 修好；L3 仍 `id_test`；L1 是抄写题 |
| 3 | 判分有效性 | 3 | **2** | 字段级有了，但 `bc/analysis/extra` 漏判；L3 漏判 mesh/load；全链包装 bug |
| 4 | 证据等级 | 3 | 3 | 关 3 分级 + CLAIMS；汇总小 bug |
| 5 | 可复现性 | 3 | **2** | 归档可校验；`fetch_data` 坏、schema 校验 GBK 崩、LLM 不可外部复现 |
| 6 | 版本治理 | 2 | 2 | git + tag + 归档；tag 仍 `v1.0-rc` |
| 7 | 文档真实性 | 3 | **2** | README/CLAIMS 大体好；但 2/2 旧快照、C-013 "全链验证"不实 |
| 8 | 统计有效性 | 1 | **1** | n=5、无 CI、`value_added` 判 PASS |
| 9 | 范围纪律 | 3 | 3 | 红线条、不做清单仍在 |
| 10 | 计划执行 | 3 | **2** | W4a 按期；W4b 交付物未达"基线"定义 |
| **总分** | | 26/30 | **22/30** | **统计有效性 1 分 ⇒ 未达 24 且单项 ≤1 ⇒ No-Go** |

> **本轮结论：Conditional-Go → W4c，不允许进入 W4d，直到 P0 全绿。**

### 6.2 新增红线条

在 R1–R8 之外，新增：

| # | 红线 | 违反示例 |
|---|---|---|
| **R9** | **SFR ≠ MSR ≠ TSR**；每份成绩单必须标明是哪一种 | 把 `spec_fidelity` 的 2/5 写成 "TSR 40%" |
| **R10** | **候选契约必须先校验**；无 `structure`/`airfoil` 必须报错，不得默认翼盒 | 包装候选被解成 `fea_case` 翼盒 |
| **R11** | **成绩单必须覆盖全部候选**；候选数 ≠ 任务数必须标 partial | 22:08 的 2/2 当成 5 条的基线 |
| **R12** | **n < 20 不得判 value_added PASS**；必须给 CI | n=5 的 40% vs 0% 判 PASS |
| **R13** | **LLM 基线必须记录模型 id/版本/日期与 endpoint**；`auto` 不可引用 | `model: "auto"` |
| **R14** | **不得把 skip_solve 的 spec 检查称为"模型基线"** | "LLM 基线 TSR 2/2" |

### 6.3 负控套件（扩展）

现有 9 条保留，新增 5 条：

| 编号 | 注入 | 期望 | 当前 |
|---|---|---|---|
| PC-1 | gold raw spec（**全链**） | PASS | ✅（gold 柱壳实测 PASS） |
| NC-1..7 | 字段注入 / L2 错值 / 静默默认 | FAIL | ✅ 9/9 |
| NC-8 | L3 30 条存在 | 结构检查 | ✅（但非负控） |
| **NC-9** | 删 `bc` | FAIL | ❌ 预计仍 PASS（未判） |
| **NC-10** | 删 `extra.end_shear`（柱壳） | FAIL | ❌ 预计仍 PASS（未判） |
| **NC-11** | 传 `{task_id, spec:{...}}` 包装 | FAIL（拒绝契约） | ❌ 当前解成默认翼盒 |
| **NC-12** | `structure.family="unknown"` | FAIL（拒绝） | 待测（`BUILDERS` 可能已 raise） |
| **NC-13** | L3 候选删 mesh/load/bc/extra | FAIL | ❌ 当前 **21/21 PASS**（实测） |

**规则**：NC-9..13 全绿之前，不得宣称"评测器可用"。

### 6.4 新增"契约完整性"检查

在 `evaluate.py` 入口加一个 `contract_ok()`：

```text
- 顶层必须存在 structure.family 或 airfoil
- structure.family ∈ BUILDERS
- bc 非空（或族声明"无 BC"）
- 柱壳 extra 必须含 end_shear/end_moment
- 翼盒 bc 必须含 root_surface/clamp
```

失败 ⇒ `pipeline` 闸 FAIL，并给出明确原因，**不进入求解**。

### 6.5 CLAIMS 账本补两条

| claim_id | statement | level | status |
|---|---|---|---|
| C-017 | LLM L1 冒烟：spec_fidelity 2/5（boundary 0/2、extrap 2/3），全链 MSR 0/5，n=5，underpowered | GATED（spec）/ 全链 | active |
| C-018 | "LLM 基线 TSR 2/2" | — | **superseded**（只覆盖 2 条、skip_solve；被 C-017 取代） |

### 6.6 节奏与角色（不变）

- 每周十维评分卡 + 红线条自查；
- 每个 W 块结束做完整复评 + 负控 + **全链正控**；
- 每 2 个里程碑独立复评；
- 执行人不能给自己的评测器签字。

---

## 7. 更新后的路线图

### 7.1 W4c（1–2 天）：修契约与口径

| 工作 | 验收 |
|---|---|
| 解包 + 严格 FEASpec | NC-11/12 FAIL；gold PASS |
| `spec_fidelity` 补 `bc/analysis/extra`；L3 也判 mesh/load | NC-9/10/13 FAIL |
| 成绩单全链 + 全候选 + SFR/MSR | `n_candidates/n_tasks` 必填；n<20 标 underpowered |
| 生成侧 schema 约束 | `response_format` 生效；`bc/extra` required |
| 可复现 | env key、lockfile、model id、REPRODUCE.md |
| CLAIMS | 2/2 superseded；C-017 写入 |

### 7.2 W4d（3–5 天）：跑真基线

| 工作 | 验收 |
|---|---|
| L3 主基线（NL→spec） | L3-SFR + L3-MSR，分族/分 split |
| L1/L2 下限 | L1-SFR、L2-SFR（澄清） |
| schema_task 约束解码 | 合法率 ≥ 95% |
| 与 T0/T1 对比 | n≥20 才判 value_added；给 CI |
| 失败归因 | 字段级 + 契约级 + 求解级 |

### 7.3 30–90 天

- A3 修复闭环（修复成功率 ≥ 70%）；
- L2 澄清基线；
- v1.1：内插 ID test、负样本/拒答、修复题、扩族、多工况；
- 消融（约束 / 修复 / RAG）。

### 7.4 90–180 天

- RAG + 失败回流；
- 专家盲评 + 效率对比；
- 原型 V1；
- 屈曲/模态规划。

---

## 8. 待拍板

| # | 事项 | 建议 |
|---|---|---|
| 1 | 是否承认 W4b 不是基线，改名为"L1 spec-copy smoke" | **承认**；否则 2/2 会进入对外材料 |
| 2 | 是否按 W4c 先修契约/全链/口径，再跑 W4d | **接受**；这是唯一能避免假阳性的顺序 |
| 3 | 是否把 SFR / MSR / TSR 三词分开定义 | **接受**；写进 CLAIMS 与 README |
| 4 | 是否把 L3 作为主基线、L1 只作格式下限 | **接受**；L1 是抄写题 |
| 5 | 是否接受"n<20 一律 underpowered" | **接受**；W4d 至少 20 条 |
| 6 | 是否接受新增红线条 R9–R14 与负控 NC-9..13 | **接受**；否则下一轮还会重演 |
| 7 | 是否接受 LLM 基线必须记录模型 id/版本/endpoint | **接受**；`auto` 不可引用 |
| 8 | 是否接受把硬编码 publishable key 移入环境变量 | **接受**；并评估是否轮换 |

---

## 附录 A　证据索引

| 结论 | 证据 |
|---|---|
| 负控 9/9 | `eval_runs/negative_controls.json`（复跑） |
| spec_fidelity 抓 NC-1/2 | 同上 |
| L2 覆盖 13 字段、泄漏 0 | `tasks/tasks.jsonl` 统计；`description` 已剥离 |
| L3 30 条、`template_human_designed` | `tasks/tasks.jsonl` |
| L3 仍 `id_test` | `tasks.jsonl` L3 split 统计 |
| 包装候选被解成默认翼盒 | `eval_runs/L1_fuselage_barrel_d1600.../fea_case/fea_case.truth.json`（family=wingbox） |
| 包装候选全链 21.3% / 7.9% | 两次 `evaluate.py` 输出 |
| 解包候选全链 93.95% | `evaluate.py --spec <unwrapped>` 输出 |
| gold 柱壳全链 PASS | `evaluate.py --spec modeling/.../spec.json` 输出 |
| 候选 `bc/analysis/extra` 为空 | `candidates/*.json` |
| 成绩单 2/2 是旧快照 | `baseline_scorecard.json` mtime 22:08:42；候选 mtime 22:12–22:17 |
| 全量重跑 2/5 | `score_baseline.py candidates` 输出 |
| T0/T1/T2 | `eval_runs/trivial_baselines.json` |
| gate3 汇总 bug | `gate3_all55_d37.json`：`n_gated_pass=15`，`evidence_levels.field=34` |
| 数据归档 | `F:/FEA_Archive_20261024/FEM-Bench-Aero-v1.0-data.tar.gz`（89,571,593 B；55 case；SHA256 匹配） |
| fetch_data tar 失败 | `tar -tzf "F:/..."` → `Cannot connect to F: resolve failed` |
| validate_schema GBK 崩 | 默认控制台 `UnicodeEncodeError: '\u2705'`；`PYTHONIOENCODING=utf-8` 下 55/55 + 2/2 |
| 硬编码 key | `gen_candidates.js` 第 11 行 |
| 无 response_format | `gen_candidates.js` 的 create 调用 |
| package-lock 被忽略 | `.gitignore` 尾部 |
| README 顶部已接入 | `FEM-Bench-Aero/README.md` 前 20 行 |

## 附录 B　复现命令

> 以下命令会写 `eval_runs/`（已 gitignore）；负控会重写 `tasks/_nc_*.json`（确定性内容）。

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# 负控（9/9）
PYTHONIOENCODING=utf-8 "$PY" negative_controls.py

# 全量候选重打分（2/5）
"$PY" score_baseline.py candidates

# 全链：包装候选（会解成默认翼盒）
"$PY" evaluate.py --task-id L1_fuselage_barrel_d1600_l1600_str8_frm3 \
  --spec candidates/L1_fuselage_barrel_d1600_l1600_str8_frm3.json

# 全链：gold（应 PASS）
"$PY" evaluate.py --task-id L1_fuselage_barrel_d1600_l1600_str8_frm3 \
  --spec ../FEM-Bench-Aero/modeling/fuselage_barrel_d1600_l1600_str8_frm3/spec.json

# 全链：解包候选（应 FAIL，验证缺 bc/extra）
"$PY" evaluate.py --task-id L1_fuselage_barrel_d1600_l1600_str8_frm3 \
  --spec "C:/Users/22207/AppData/Local/Temp/probe_unwrapped_barrel.json"

# schema（需 UTF-8）
PYTHONIOENCODING=utf-8 "$PY" validate_schema.py

# 数据归档校验（Python tarfile，避开 GNU tar 的 F: 陷阱）
"$PY" -c "import tarfile; t=tarfile.open('F:/FEA_Archive_20261024/FEM-Bench-Aero-v1.0-data.tar.gz'); n=t.getnames(); print(len({x.split('/')[1] for x in n if x.startswith('modeling/') and x.count('/')>=2}), 'case dirs')"
```

## 附录 C　负控清单（扩展）

| 编号 | 注入 | 期望 | 当前 |
|---|---|---|---|
| PC-1 | gold raw spec（全链） | PASS | ✅ |
| NC-1 | `rib_thickness` 4→8 | FAIL | ✅ |
| NC-2 | L2 问对填错 8.0 | FAIL | ✅ |
| NC-3 | `n_stringers_per_skin` 0→3 | FAIL | ✅ |
| NC-4 | `mesh.size_chord` 12→20 | FAIL | ✅ |
| NC-5 | `load.magnitude` 500→600 | FAIL | ✅ |
| NC-6 | `E` 73100→60000 | FAIL | ✅ |
| NC-7 | L2 静默默认 | FAIL | ✅ |
| NC-8 | L3 30 条存在 | 结构检查 | ✅ |
| **NC-9** | 删 `bc` | FAIL | ❌ 未测（预计 PASS） |
| **NC-10** | 删 `extra.end_shear`（柱壳） | FAIL | ❌ 未测（预计 PASS） |
| **NC-11** | 传 `{task_id, spec:{...}}` 包装 | FAIL（拒绝契约） | ❌ 解成默认翼盒 |
| **NC-12** | `structure.family="unknown"` | FAIL（拒绝） | 待测 |
| **NC-13** | L3 候选删 mesh/load/bc/extra | FAIL | ❌ 当前 21/21 PASS（实测） |

## 附录 D　评分卡

```markdown
## 十维评分卡（W4b 后复评）

| # | 维度 | 分数 | 理由 |
|---|---|---:|---|
| 1 | 目标一致性 | 3 | benchmark/verifier 主轴未变 |
| 2 | 任务有效性 | 2 | L2 修好；L3 id_test 未统一；L1 是抄写题 |
| 3 | 判分有效性 | 2 | 字段级有；bc/analysis/extra 漏判；L3 漏判 mesh/load；包装 bug |
| 4 | 证据等级 | 3 | 关 3 分级 + CLAIMS；汇总小 bug |
| 5 | 可复现性 | 2 | 归档可校验；fetch_data/schema/LLM 三项不可复现 |
| 6 | 版本治理 | 2 | git + tag + 归档；tag 仍 rc |
| 7 | 文档真实性 | 2 | README/CLAIMS 好；2/2 旧快照与 C-013 不实 |
| 8 | 统计有效性 | 1 | n=5、无 CI、value_added PASS |
| 9 | 范围纪律 | 3 | 红线条与不做清单在 |
| 10 | 计划执行 | 2 | W4a 按期；W4b 未达基线定义 |
| **总分** | | **22/30** | **No-Go（统计有效性 ≤1）** |
```

---

> **本文件是第三轮复评的产物，不修改任何既有项目文件。**
> 本轮为验证全链行为运行了 3 次 `evaluate.py`（包装柱壳 ×2、解包柱壳 ×1、gold ×1）与 1 次负控、1 次全量重打分；产物均在 `eval_runs/`（已 gitignore）。
> 下一轮请先跑附录 C 的 **NC-9…NC-13**；全绿之前，不得把任何成绩单称为"LLM 基线"。
