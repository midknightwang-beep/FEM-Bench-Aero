# RUBRIC.md — L3 判分口径预注册（W4e/W4f，专家第四轮 P0-6/R18）

> **冻结时间**：2026-10-25（考卷 v4 重跑**之前**）。
> **纪律（R18）**：本文件冻结后，跑基线期间不得再改；每次改动必须新开版本号 + 记录原因。
> **post-hoc 声明**：W4d 版口径（EXEC_CONFIG_KEYS / METADATA_KEY_NAMES / bc_skip）是看过
> 30 条候选后调整的，属 **post-hoc**——其成绩（C-020，已 superseded）只能作开发参考；
> 本 v2 口径在重跑（W5）前冻结，重跑成绩方为正式。

## 1. 层次（红线 R15）

| 集合 | 定义 | 用途 |
|---|---|---|
| **exam** | `boundary_holdout + extrapolation_test`（11 条） | **对外 headline 唯一来源** |
| dev | `train + val`（19 条） | 开发/诊断，不进对外 |
| 全集 30 | 任务层规模 | 只作「考卷规模」描述 |

## 2. TSR（主 KPI，行为正确性）

- 完备题：`spec_fidelity` PASS ⇒ TSR PASS。
- 澄清题（`expected_clarifications` 非空）：
  - **字段级判据（R17）**：候选 clarify 文本必须命中 `clarify_aliases[field]` 中至少一个别名
    （正确键名或语义短语），**且不含** `clarify_wrong_keys` 中任何错族键名（键名即契约 R19）。
  - 单字关键词（'肋'/'孔'/'框'/'长桁'）**不得**作为通过依据（W4d 版已废弃）。
  - 静默编造 spec ⇒ TSR FAIL（FPR 编造）。
- 3 轮未收敛 / LLM 错误 ⇒ FAIL。

## 3. SFR（字段保真）

- 判层：**工程层**（L3 only）——`GRADED_FIELDS[family]` + material 必判三项 + mesh/load/extra
  gold 权威逐键。
- **R20**：`fabricated`（澄清题静默编造）⇒ SFR 一律 FAIL，与 TSR 编造口径一致。
- 执行配置键 `EXEC_CONFIG_KEYS`（REPORTED NOT GATED，填错单独报告）：
  - `mesh`: algorithm_2d, element_order, leading_edge_threshold, min_jacobian,
    recombination_algorithm, recombine, refine_at_leading_edge
  - `analysis`: incremental, initial_increment, outputs, step_type, total_time
  - `extra`: sweep_index, shear_axis, moment_axis（数据集内部编码键）
  - `load.direction` 且 `kind=pressure`（内压径向为数据集内部约定）
- **死字段豁免**：wingbox 且候选 `n_stringers_per_skin=0/缺` 时 `stringer_*` 四键不判。
- **builder-default 声明（R19）**：barrel 的 `stringer_height=25/stringer_thickness=2.5`、
  panel 的 `20/2.5` 为 builder dataclass 默认，gold params 不含这些键 ⇒ SFR 不判；
  考卷 v4 已在 NL 明示尺寸，模型显式写对/省略均可，**写 0 ⇒ builder 校验拒（真实错误）**。
- **bc 块**：pipeline 不消费 `spec.bc`（边界由各族 builder 代码决定），非翼盒族 gold bc 是
  死模板值 ⇒ bc 键值不判；但 **bc 自创键照罚**（模型写出 builder 不认识的键 = 编造）。
- **自创键白名单（收紧后）**：仅 `note / units / unit_system / description / *_units / *_note`；
  `type / element(s) / order / application / point` 等一律照罚（W4d 版白名单过宽，已收）。
- **material 块自创键**（ply_material 等）照罚。

## 4. MSR（全链可用率，R14/R16）

- 全链 = 契约闸（含 FEASpec 试建）+ ccx 求解 + 关1 网格 + 关4 语义 + fidelity + spec_fidelity。
- **依赖预检（R16）**：gmsh/numpy 缺失 ⇒ 环境错误退出，绝不记候选 FAIL。
- 分母 = spec-required 任务（澄清/未收敛/编造被拒候选不计）。
- 失败分层 `env / contract / model / solver`；env 单独计数，不进 MSR。
- 解释器：`C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe`（gmsh 在 venv）。

## 5. value_added

- `exam` TSR_LLM − `exam` TSR_T1（同任务集 exam 口径，**不用 all_pct**）。
- `n_exam < 20` ⇒ `underpowered=true`，**不得判 PASS**（R12）。

## 6. 负控

- 每次改判分/考卷必跑负控套件（R5/R6）；未全绿不得跑基线。
- 套件：PC-1 + NC-1..19（W4e/W4f 新增 NC-15..19，见 negative_controls.py 文档头）。
