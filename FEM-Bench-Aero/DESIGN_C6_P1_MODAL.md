# DESIGN C6-P1 — 模态打样设计（拍板件，2026-11-07）

> 状态：**已拍板（2026-11-07，四项全按推荐）**：① v2 线根目录 = `modeling_v2/`；② 打样 8 条 = §2 推荐清单；③ ccx 特征值求解器 = ARPACK（不收敛再单列换 SUBSPACE）；④ Abaqus 真机 = 复用 odb_batch solve 段 + `.dat` 提取。§9 保留原始提案表述供追溯。
> 承 C6 四点拍板（2026-11-06）：P1 模态先行 / 数据层形态 A 独立 v2 线 / 6–8 条打样 / 双码阈值先测后定。
> 本文把「打样」落到具体单子：选材、deck 规格、提取口径、判据定义域、负控提案、执行顺序。
> 本文只设计，不改代码、不动 v1.1 数据；数字一律现场实读。

## 1. 打样目标与非目标

**目标**（打样 = 打通全链 + 产出阈值测量数据）：

1. 8 条翼盒案例以 `step_type=frequency` 在**双码**（ccx + 原生 Abaqus）上全部求解成功；
2. f1–f5 双码实测、交叉差表落 artifact（阈值先测后定的输入）；
3. 判据定义域写清成文（N-36 教训：新题型进卷前先定义域）；
4. 负控新增提案成文（实现任务的验收输入）。

**非目标**（本打样明确不做）：

- 不改评测器/判分层代码（打样阶段只测数据层；评测器扩展是打板后的单变量任务）；
- 不生成考卷、不跑 LLM 候选（R59 红线：判据没定型前不出成绩单）；
- P2 屈曲（λ_cr）不进本打样；
- 不预写任何阈值数值。

## 2. 打样选材：8 条（推荐，单变量轴覆盖）

选材池 = v6c train 池翼盒案例（39 个 L1/L2/L3 任务，**15 个唯一几何**）。8 条推荐 = 基准 + 7 个单变量轴，每个轴都是模态敏感参数：

| # | 案例（v2 命名） | 几何源（v1.1 现成 spec） | 单变量轴 | 模态意义 |
|---|---|---|---|---|
| 1 | `naca4412_wingbox_modal` | `naca4412_wingbox` | 基准（chord1000/span2000/5肋/skin3） | 对照锚 |
| 2 | `..._size_span2400_modal` | `_size_span2400` | 展长 +20% | 频率最大杠杆（f∝1/L²量级） |
| 3 | `..._n_ribs5_chord800_modal` | `_n_ribs5_chord800` | 弦长 −20% | 质量与刚度同降 |
| 4 | `..._size_skin2_modal` | `_size_skin2` | 蒙皮 3→2 mm | 刚度降 + 质量降，净效应待测 |
| 5 | `..._str3_modal` | `_str3` | 加 3 根长桁 | 质量升为主，f 预期下降 |
| 6 | `..._sweep20_modal` | `_sweep20` | 后掠 20° | 弯扭耦合，模态序可能变 |
| 7 | `..._taper060_modal` | `_taper060` | 梯形 0.6 | 弦向质量分布 |
| 8 | `..._web1_modal` | `_web1` | 中间腹板 +1 | 扭转刚度，弯扭分离度 |

命名规则：`<v1.1案例名>_modal` 后缀——**case 身份 = 几何参数，step_type 是名字里显式的新轴**（与翼盒族 `_t2`/`_str3` 命名惯例同构）。若老王想换成其他轴（如 sweep40、skin4），只换表行，结构不变。

## 3. Deck 规格（inp_writer 的 frequency 分支，代码现状已核实）

**代码现状实读**（2026-11-07）：

- `inp_writer.py` L255 写死 `*STEP, NLGEOM=NO` + `*STATIC`；spec 的 `step_type` 槽位**未被消费**；
- `*DENSITY` 已双路输出（L232/238）⇒ 模态质量的 deck 侧**不用改**；
- `*BOUNDARY` 在 step 段之前发射 ⇒ 模态约束写法兼容，不动；
- spec 材料**自带 density=2.78e-9 t/mm³**（2024-T3），翼盒全族现成。

**双码 step 段设计**（dialect 分支）：

```text
--- ccx（CalculiX）---                      --- abaqus（原生）---
*STEP                                       *STEP
*FREQUENCY, SOLVER=ARPACK                   *FREQUENCY, EIGENSOLVER=LANCZOS
5, 0.0, 1.0e6                               5, 0.0, 0.0
*NODE FILE                                  *NODE FILE
U                                           U
*END STEP                                   *END STEP
```

- ccx data 行 = `特征值数, 下界, 上界`；abaqus data 行 = `特征值数, 低频, 高频`（0,0=自动移位）；
- **load 段整个省略**（特征值问题载荷无关——这正是 P1 实现最薄的原因）；`_emit_load` 在 frequency 分支不调用；
- 输出请求只留 `U` 节点文件（振型形状；`.dat` 特征值表自动打印，无需额外请求）；
- 静力分支零改动（R-A1：本任务只加 frequency 分支这一个变量）。

## 4. 提取口径与换算公式（显式，钉死）

**来源 = 双码 `.dat` 纯文本**（沙箱可测，不依赖 abaqus python；ODB 提取留给后续 ODB 工具的 modal 档，不在本打样）：

| 量 | ccx `.dat` | abaqus `.dat` | 换算 |
|---|---|---|---|
| 特征值 λ | `E I G E N V A L U E` 表 | `E I G E N V A L U E  O U T P U T` 表 | 原始 λ 直接取 |
| 频率 f | **打印的是 λ** ⇒ `f = sqrt(λ) / (2π)` | 表内直接打印 `CYCLES/TIME` 列 | **换算公式写死在提取器，且 abaqus 侧同时用 λ 反算一遍做内部一致性 pin**（两条路必须逐字节一致，不一致=提取器 bug） |
| 有效质量 | **待核实**（ccx `.dat` 是否打印模态质量/参与因子，P1 首跑实测） | 自动打印 `E F F E C T I V E   M A S S` 表 | ccx 侧缺失则 v2 打样判据只用 f；有效质量作为 abaqus 侧诊断量，不进交叉判据 |

> **★ 实测修正（2026-11-07，首跑即测，打样第 5 步执行中记录）**：ccx 2.23 的 `.dat` 特征值表**并非只打 λ**——实际是 5 列行 `MODE, λ, RAD/TIME, CYCLES/TIME, 虚部`，与 abaqus 同构，`CYCLES/TIME` 直接可读；且表后自动打印 `P A R T I C I P A T I O N   F A C T O R S`（参与因子有了，有效质量仍无——判据只用 f 的决定不变）。提取器两码统一走「打印 f 为主 + λ→f 反算 pin（1e-4 相对容差，mis-parse 即 raise）」，旧式 λ-only 布局保留为兜底解析；回归 pin `SELF_TEST_OK 11 pins` 含真机表头文本。本行是设计假设被实测推翻的更正记录，原文（上表第二列）保留供追溯。

**提取器**：新 `extract_modal_dat.py`（纯文本解析，任意 python 可跑，沙箱内用已知 pin 值自检——含 λ→f 换算 pin：λ=4π² ⇒ f=1.0 Hz 整）。

**语义量 schema（v2 打样层）**：`f1..f5`（Hz，Cycles/time）、`n_modes_found`、`lam1..lam5`（原始 λ）；每个 case 一个 `truth_modal.json`（打样阶段 = 测量产物，冻结后才成 truth）。

## 5. 判据定义域（N-36 教训，先写清再写代码）

**掩码轴由 step_type 供给，不由族名供给**。同一翼盒几何可以两个 step_type 各一条（`_modal` 后缀区分），互不渗透：

| 判据 | static 任务 | frequency 任务 |
|---|---|---|
| `max_disp` / `max_w` / vM 系 | ✅ 定义域内 | ❌ 定义域外（不存在，不是 0 分、也不判红） |
| `f1..f5` / `n_modes_found` | ❌ 定义域外 | ✅ 定义域内 |
| 席位/负控的「语义项数」 | 按 step_type 分层计数，**两层不可相加或比大小**（沿用 N-35 分层纪律），`_coverage` 写明覆盖哪层 |

**频序判据**（frequency 定义域内的独立正向判据）：

1. `f_positive`：全部 f_i > 0（刚体模态泄漏 = 未加好约束，必须红）；
2. `f_monotonic`：f_1 ≤ f_2 ≤ … ≤ f_5（容差 1e-9；特征值乱序 = 求解器异常）；
3. `n_modes_found == 5`：缺阶记 0 不排除（R47 纪律）。

**双码交叉判据（先测后定）**：Δf_i = |f_abq − f_ccx| / ((f_abq + f_ccx)/2)。打样跑完 8×5=40 对，出**相对差分布表**（median/p90/max，逐阶）→ 老王拍板阈值 → 才代码化为判据。提案 §2 的建议值（f ≤1%）**只是谈判起点，不是预写判据**。

## 6. 数据层 v2 线布局（形态 A 落地）

```text
FEM-Bench-Aero/
  modeling/               # v1.1 线：64 案例，冻结不动（R65：只加行不改老行）
  modeling_v2/            # ★ v2 线根（推荐名，待拍板）：独立冻结卷
    naca4412_wingbox_modal/         # 8 条打样，命名见 §2
      spec.json                     # step_type=frequency, n_modes=5, load 段省略
      model.msh / model.step        # 几何网格层与 v1.1 同参同网格（单变量=step）
      truth_modal.json              # 双码实测（打样=测量产物；冻结后才成 truth）
    verify_v2_p1.json / VERIFY_V2_P1.md   # 双码交叉差表 + 阈值测量报告（official artifact）
```

- 生成脚本：新 `make_v2_modal_cases.py`（读 v1.1 翼盒 spec → 改 step_type → 写 v2 目录；**不复制不改 v1.1 任何文件**）；
- 冻结纪律：8 条打样测量完成、阈值拍板后，`SHA256SUMS` 记录并冻结 v2 卷；此后 R65（只加行）；
- bridge：v2 首冻结时写 `n35` 式 bridge 说明（v1.1 与 v2 无分数可比性，纯数据层并存）。

## 7. 负控新增提案（实现任务的验收输入，编号后补）

| # | 负控 | 红的条件 |
|---|---|---|
| 1 | step 类型误判 | 用 frequency 产物喂 static 判据 → 必须红（定义域闸防「判据自己漏了」） |
| 2 | 缺阶记 0 | 删掉 f3 条目 → 判 0 不排除（R47），分母不缩 |
| 3 | 频序闸 | 人为乱序 f 列表 → `f_monotonic` 红 |
| 4 | 刚体模态 | f1≈0 未约束 case → `f_positive` 红 |
| 5 | 换算 pin | λ=4π² 必须出 f=1.0 Hz；提取器对已知 pin 失手 → 红 |
| 6 | 定义域双向 | freq 任务缺 f 键红 + freq 任务多给 max_disp 也红（N-35 双向纪律） |

## 8. 执行顺序（实现任务单，打板后开工）

1. `spec.py`：`AnalysisSpec` 增 `n_modes`（默认 5）+ `step_type` 校验扩 `"frequency"`（单变量）；
2. `inp_writer.py`：frequency 分支（§3；静力分支零改动，diff 里不许出现静力行为变化）；
3. `extract_modal_dat.py`：新提取器 + `--self-test`（§4 换算 pin）；
4. `make_v2_modal_cases.py`：8 条生成 → 布局 §6；
5. ccx 8 条全跑（R61 全局锁生效中，串行）；`.cvg` + `.dat` 特征值表判完成；
6. **Abaqus 真机 8 条**：WorkBuddy 外 cmd（odb_batch 的 solve 段可复用——它扫 `<job>.inp` 求解判 `.sta`，提取段 modal 走 `.dat` 解析器；或临时用 `abaqus j=X input=X.inp interactive` 逐条跑，8 条约 15–20 分钟量级）；
7. `verify_v2_p1.json` 交叉差表 → **老王拍板阈值** → 判据代码化 + 负控实现（下一个任务）。

**打样验收（第 5–7 步完成的定义）**：

- [ ] ccx 8/8 收敛、abaqus 8/8 `.sta` COMPLETED；
- [ ] 双码 f1–f5 全正、单调、`n_modes_found==5`（§5 三条频序判据全过）；
- [ ] 交叉差表 40 对齐全，分布统计落 artifact；
- [ ] 期间现有闸零扰动：负控 87/87、claims 全绿（实现任务每步收口都复跑）。

## 9. 请老王拍板的四件事

1. **v2 线根目录名**：推荐 `modeling_v2/`（与 `modeling/` 平行，一眼可辨血缘）；
2. **打样 8 条清单**：推荐 §2 表格（基准 + span/chord/skin/长桁/后掠/梯形/腹板 七轴）；换行只换名字；
3. **ccx 特征值求解器**：推荐 ARPACK（默认，大规模更稳）；实测某 case 不收敛再单列换 SUBSPACE，不预换；
4. **Abaqus 真机跑法**：推荐复用 odb_batch 的 solve 段（batch 扫目录串行求解，manifest 留痕），提取段换 `.dat` 解析器；备选 = 逐条手工跑。

## 10. 停止条件

- 现有任一闸红 → 停，先修 SOT；
- ccx 某条不收敛 → 单列进 verify 报告（不隐藏、不换 case 凑数）；
- 双码差分布异常宽（某阶 >10%）→ 停下来查口径（多半是提取器 bug，先怀疑自己——SOUL 纪律）；
- 阈值没拍板前，不写任何「PASS/FAIL」类判据代码。
