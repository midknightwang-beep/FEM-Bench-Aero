# DATASET v1.1 —— 9 条内插留出（interior holdout）

> **状态：数据层已闭合 —— `CLAIMS` C-036 GATED（`check_forms 54/54`、双码配对 `64/64`、`gate4 128/128`、`eval 64 cases / 0 failures`）。**
> 生成器 `feagpt_repro/_v11/make_v11_specs.py`；物理校验 `feagpt_repro/_v11/verify_v11_interpolation.py`；
> 双码脚本 `feagpt_repro/_v11/run_v11_abaqus.bat`（**必须在 WorkBuddy 之外的普通 cmd 里跑**）——
> 已于 2026-10-28 21:32 跑完，9/9 真跑通，见 §4。
> 日期：2026-10-27 建；2026-10-28 双码闭合；2026-10-28 T-A10 入 claim 账本（C-036）。

## 0. 一句话

数据集从 **55 → 64** 条，`test` 侧 **13 → 22**；新增的 9 条全部取在**已有锚点之间**，
用来补上「内插留出」这块空白（原 25 条 exam 里内插只有 6 条、且全在翼盒一族）。

**注意口径**：这里改的是**数据集本体**（`modeling/`）。
**考卷仍是 v6c 的 55 条任务**（`tasks_v6c.jsonl`，sha `9c1faa3a…`）——把新几何接进考卷要在任务层
另建 v7，并重跑基线，那一步**还没做**（见 §5）。

## 1. 为什么加内插点

`feagpt_repro/feagpt/manifest.py` 自己写着 `ID_TEST_RENAME = 'boundary_holdout'`，
原注释是「真内插留出（interior holdout）＝ v1.1」。缺内插点有两个具体后果：

1. **统计精度不够**：exam n=25 ⇒ TSR 的 CI95 宽到 [80.0, 100.0]，4 pp 的差距被判「不显著」；
2. **测不出「按参数生成」还是「背样本」**：边界/外插点考的是外推抗性，内插点考的是参数是否真的进了模型
   ——两者是不同的能力，缺一头就有一半没测。

## 2. 九条新案例（每条都夹在两个已存在的锚点之间）

| 新案例 | 参数轴 | 锚点 A → 锚点 B（max\|u\|, mm） | 新值 | 新案例 max\|u\| (mm) | 夹逼 |
|---|---|---|---|---|---|
| `naca4412_wingbox_size_skin2p5` | 壁厚 | 3.542304（skin2）→ 2.365439（skin3 基型） | 2.5 | **2.836541** | ✅ |
| `naca4412_wingbox_n_ribs6_chord1000` | 肋数 | 2.365439（ribs5 基型）→ 2.358054（ribs7） | 6 | **2.362133** | ✅ |
| `naca4412_wingbox_str4` | 长桁/侧 | 2.219397（str3）→ 2.135447（str5） | 4 | **2.175530** | ✅ |
| `naca4412_wingbox_size_chord900` | 弦长 | 4.526728（chord800）→ 2.365439（chord1000） | 900 | **3.207841** | ✅ |
| `naca4412_wingbox_taper070` | 锥度 | 3.384152（taper060）→ 2.752089（taper080） | 0.7 | **3.028376** | ✅ |
| `open_hole_panel_400x200_d30` | 孔径 | 0.057497（d20）→ 0.059402（d40） | 30 | **0.058277** | ✅ |
| `fuselage_barrel_d2000_l1800_str8_frm3` | 柱长 | 2.551120（l1600）→ 2.631031（l2000） | 1800 | **2.609166** | ✅ |
| `open_hole_panel_500x250_d45` | 双轴角点 | 400×200/d40 → 600×300/d60 | 500×250/d45 | 0.058507 | 只报（非单轴） |
| `stiffened_panel_700x600_str4` | 双轴角点 | 800×600/str3 → 600×600/str3 | 700×600/str4 | 0.014023 | 只报（非单轴） |

> **孔径轴三点单调**：d20 = 0.057497 → d30 = 0.058277 → d40 = 0.059402（孔越大越柔），方向与物理一致。
>
> 锚点与新值全部取自 `_v11/v11_interp_check.json`（由 `verify_v11_interpolation.py` 从各案例 `truth.json` 现读现比），不是我手抄的。
> 7 条单轴点**全部通过**严格夹逼（`_v11/v11_interp_check.json`，`n_fail=0`）；
> 2 条双轴角点与任何单一锚点都不构成「只差一个参数」，**只报数值、不作判定**。

## 3. 划分怎么落位（一条规则，不动既有 55 条）

新增 spec 打 `extra.split_tag = "v11_interior_holdout"`；`manifest.split_of()` 在**族谓词之前**
先认这个声明，命中即 `test`。实测：

```
v1.0：55 条 / 54 类 / train 25 · val 17 · test 13
v1.1：64 条 / 63 类 / train 25 · val 17 · test 22     ← train 与 val 一条没动
```

为什么用**声明**而不是写参数谓词：内插点的特征就是「每个轴都落在包络内」，
任何按数值写的谓词都会顺带命中一堆既有 train 条（那会把 D12 锁定的 11 条重新划分）。
声明式的好处是**只认领点了名的案例**——加 tag 进 exam，删 tag 回 train，不产生副作用。

## 4. 闸门状态

| 闸 | 结果 | 说明 |
|---|---|---|
| gate 4 语义（建模侧） | **9/9 PASS** | 每条 4–10 项拓扑/语义检查，`make_dataset.py` 逐条打印 |
| 网格质量 | **9/9** | minJ 0.506–0.637（阈值 0.30）；**tri3 = 0** |
| 节点上限 | **9/9 未越线** | 最大 `d2000_l1800` = 143,702 活节点（ccx 壳展开上限 158,548） |
| `eval_dataset.py` | **PASS** | 含 `rule_reproduces_D12`（11 条锁定划分未被改动）。产物 `eval_report_v11.json`：`python eval_dataset.py --root ../FEM-Bench-Aero --json ../FEM-Bench-Aero/eval_report_v11.json` |
| `dedup_dataset.py` | **0 重复** | 63 个等价类，无重复模型 |
| 内插物理校验 | **7/7 PASS** | `--strict` rc=0 |
| `verify_dataset.py` | **PASS** ✅ | 双码补齐后：`pairing: 64 paired, 0 modeling-only, 0 xval-only -> PASS`；`cross-tree mesh agreement 64/64 identical`；`case consistency 128/128 OK`；`stress definition agreement (D8) PASS`；`VERDICT: PASS` |
| 双码物理一致性（`verify_solvers.py`，逐条） | **9/9 实质通过**（8 gated + 1 reported-only） | 实测见 `reports/diagnostics/xval_v11_9cases.json`：翼盒 `max\|u\|` 0.268–0.401 %、vM 逐节点中位差 0.17–0.75 %；开孔板 0.101–0.185 %、中位差 0.01 %；加筋板 0.045 %、中位差 0.22 %；柱壳 1.495 % 但按 **D20 只报不判**（中位差 0.08 %） |
| `check_forms.py` | **54/54 PASS（VERDICT: PASS）** | 串行重跑完成（10m25s，无其他 ccx 并行）。**首次运行是 50 PASS + 1 FAIL**：`T5.invocation` 报参考案例不存在 —— 根因不是 v1.1 数据，而是 `check_forms.py` 的 `DEFAULT_REFERENCE` 指向 `outputs_str/naca4412_wingbox_str3` 这个**本仓库不存在**的旧输出目录（潜伏缺陷，见 §5.4）。修完 T5 由 1 项扩到 4 项，故总数 51 → 54 |
| `gate3_all55.py` | **57 gated_pass / 7 reported-only / 0 fail（rc=0）** | 取证分层：**39 field（34 条 d36 明细 + 5 条 2026-10-28 实测）+ 18 scalar-disp + 7 reported-only = 64**。★ T-A7 查出真因：d36 的明细键是 `case` 而脚本查 `case_id` ⇒ **39 条翼盒从来没被逐条读取过**，全部走「继承整体 PASS」；且翼盒登记判据是 **vM 逐节点中位差 < 5%**（`stress_field.gated=true`），`max\|u\|` 是 REPORTED NOT GATED。修后翼盒 `vm_median` 缺失 **0/39**。外部一致性由 **S-48（R62）** 守：`CLAIMS` C-003 行的三个分项计数、构成拆分与分母必须与 `gate3_all55_d37.json::evidence_levels` **逐项相等**（此处不复写数字，避免在闸的覆盖范围外再造一份会漂的副本）|
| **对外数字源**（T-A8） | **全部走 v1.1 活源** | 关 1 ← `manifest.readings`（现算，不再读 55 条聚合）；关 4 ← `gate4_v11.json`；自洽 ← `verify_dataset_v11.json`；划分复算 ← `eval_report_v11.json`。表新增**「分母口径」列**（R54：关 1/关 3/划分复算 = spec 数，关 4/自洽 = 算例目录数，两套不得相减）；基线与 M14 三条限制标注「v1 口径、v1.1 未重跑」 |

## 5. 待办与教训

### 5.1 待办

1. ~~**双码（Abaqus）**~~ ✅ **已完成**（2026-10-28 21:32，老王在**普通 cmd** 里跑 `run_v11_abaqus.bat`）。
   9/9 真跑通（不是「返回 0」——逐条核过 `.truth.json` 的 `n_nodes` / `max_disp` / `max_von_mises` 非零、
   `.odb.json` 有量；barrel 的 `2.64876` 与 `batch_summary.json` 的 `2.6487554` 逐位一致）。
   `verify_dataset` ⇒ `64 paired / VERDICT: PASS`。
   > ⚠ `batch_summary.json` **只写了 9 条中的 1 条**（barrel）——又一次印证「不能只信 summary 的 `ok:true`」：
   > 目录里 9 条产物齐全，但汇总文件自身的写入有 bug。判据必须是产物本身。
   > 不能在 agent 内跑的原因见旧记录：沙箱注入 `tsbx.dll` ⇒ `pre.exe` 阶段 `__fastfail`。
2. ~~**`check_forms.py` 串行重跑一次**~~ ✅ **已完成**（T-A5）：串行、无并行 ccx，结果 **54 PASS / 0 FAIL**，产物 `feagpt_repro/reports/check_forms_v11.json`，日志 `_v11/check_forms_v11.log`（首次失败证据留档 `_v11/check_forms_v11_fail1.log`）。
3. ~~**gate3 证据链（T-A7）**~~ ✅ **已完成**（2026-10-28，老王拍板 A）：`gate3_all55.py` 三分支化
   （d36 明细 / v1.1 实测 / **两者都没有 ⇒ pass=False 直接报红**），并修掉查了不存在的
   `case_id` 键、`max_disp_gap_pct` 键、以及按 `max|u|<1%` 判翼盒的口径错。
   详见 `CONFLICT.md` N-6 的「★ 执行时查出的真因」。
4. ~~**对外数字表（T-A8）**~~ ✅ **已完成**（2026-10-28）：`make_external_numbers.py` 全部改读 v1.1 活源——
   关 1 改为从 `manifest.readings` 现算（不再读 55 条聚合的 `gates_all55_d36.json`）、关 4 / 自洽 / 划分复算
   分别读新建的 `gate4_v11.json` / `verify_dataset_v11.json` / `eval_report_v11.json`。表新增
   **「分母口径」列**（R54：spec 数 vs 算例目录数，两套分母不得相减）；基线与 M14 三条限制显式标注
   「v1 口径、v1.1 未重跑」。详见 `CONFLICT.md` N-9 的处置记录。
5. ~~**闸覆盖补全（T-A10）**~~ ✅ **已完成**（2026-10-28）：新增 **S-49**（`C-001/2/4/5/036` 的正文计数
   == artifact 实读）/ **S-50**（对外数字表：分母口径列 + 每个 `A/B` 的 `B ∈ {spec 64, 目录 128}` +
   **重跑生成器逐字节比对**）/ **S-51**（协议文件不得写死计数）+ **NC-54 十向**；
   新增数据层 claim **C-036**（`check_forms 54/54`、`双码配对 64/64`、`gate4 128/128`、`eval 64/0`）；
   RUBRIC **v5.6**（R63/R64）。顺带修正 `manifest.summary.xval_cases_available` **55 → 64**
   （dry-run 逐键比对证明只此一键变化、splits 逐位相同）。详见 `CONFLICT.md` N-12/N-13/N-14。
6. **考卷 v7（未做）**：把 9 条接进任务层 ⇒ exam 25 → 34，才能收窄 CI。
   代价：换卷后 **C-032 的 23/25 不再可比**（R30/R39，paper sha 变），必须重生成两模型候选
   （约 2 × 15 min）+ 全链 MSR（约 2 × 40 min）+ 重跑 CI/榜单。**这是下一轮的主任务。**

### 5.2 本轮我自己踩的三个坑（都留在代码注释里）

1. **tag 写成键而不是值**：`extra.v11_interior_holdout = true` 对，但谓词读的是
   `extra.split_tag` 的**值** ⇒ 9 条先被族谓词分进了 train/val（train 一度变 29）。
   教训：写端与读端分开时，必须有一处**对着跑一遍**，不能各写各的。
2. **锚点不存在**：第一版柱壳挑 `d1800_l1800`，可集里没有 `d1800_l1600` ⇒ 构不成单轴夹逼，
   校验器直接 SKIP。改成 `d2000_l1800`（两端 `l1600`/`l2000` 都在集）才立得住。
3. **并行跑了 ccx**：`check_forms` 还在跑时我起了柱壳的 ccx，违反「绝不并行跑 ccx」。
   事后单独重算该条，标量与首次**逐位相同**（差异项 0）⇒ 本次未造成污染；但这是运气，不是许可。

### 5.3 一条判据被证伪（不是模型错）

第一版内插校验对 `max_von_mises` 也要求「落在两锚点之间」，柱壳那条判 FAIL。
实测三点应力是 **249.35 / 248.16 / 249.40**（差 0.5%，基本持平）——
根部峰值应力由「端部弯矩 ÷ 截面模量」决定，两者都不随长度变，长度只挪框的位置。
⇒ **应力在长度轴上不单调**，该轴只判位移、应力只报。
已改成按轴声明 `strict_metrics`，并把这个物理事实写进脚本注释：**别让判据的假设冒充模型的错**。


### 5.4 一条潜伏缺陷：T5 的参考路径指向不存在的目录（T-A5 修）

- `check_forms.py` 的 `DEFAULT_REFERENCE = "outputs_str/naca4412_wingbox_str3"` —— `outputs_str/` 这个目录**在本仓库不存在**（`ls outputs_str` 无此目录）⇒ `T5.invocation` 恒 `FileNotFoundError` ⇒ **整份 check_forms 恒 `VERDICT: FAIL`**。
- 之所以一直没暴露：check_forms 之前每次都跑不完（第十二轮 §3.2 就是 10 分钟无输出被终止），**从没跑到过 T5 之后**。这次串行跑完才看见。
- 修法：`DEFAULT_REFERENCE` 改为用 `__file__` 推出的绝对路径、指向数据集里真实存在的同族案例 `FEM-Bench-Aero/modeling/naca4412_wingbox_str3/spec.json`（锚定语义不变——它就是 T5 要复现的那条带凸缘长桁翼盒）；同时 `_reference_spec()` 现在**两种目录布局都认**：数据集六件套 `<dir>/spec.json` 与旧输出 `<dir>/<dir>.spec.json`（只认后者会让「拿数据集案例当参考」直接报错）。
- 教训：**「工具跑不完」和「工具跑通了」必须分开记**。前者掩盖了后者的真缺陷——如果一直把 check_forms 当成「未完成」而不去跑完一次，这条陈旧路径会永远躲着。
