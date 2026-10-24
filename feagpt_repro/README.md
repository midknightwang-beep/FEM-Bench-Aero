# feagpt_repro —— FeaGPT 流水线的可运行本地复现

把 FeaGPT（arXiv:2510.21993）那条 **自然语言 → 几何 → 网格 → 求解 → 结果** 的
GMSA 链路，落成一套能在本机一把跑通的 Python 脚本。

复现的对象是**工程链路和它的接口契约**，不是论文里的 LLM 智能体。

支持两个求解器后端：**CalculiX**（自由、可移植）和 **Abaqus**（工程实际工作流），
两者吃同一套物理描述、由同一套代码做结果归纳，并且可以**互相交叉验证**。

---

## 1. 复现了什么 / 没复现什么

先说清楚边界，免得把"流程复现"当成"论文复现"。

| 阶段 | FeaGPT 原文 | 本工程 | 说明 |
|---|---|---|---|
| ① 规划 Planning | Gemini 2.5 Pro + 向量知识库（σ>0.85 命中模板） | `planning.py`：规则解析器 | **输出同一个 `FEASpec`**，LLM 挂载点留在函数末尾注释里 |
| ② 几何 Geometry | FreeCAD Python API → STEP | `geometry.py`：gmsh OpenCASCADE | 本机无 FreeCAD；同类产物（薄壁曲面 + 可选 STEP），已如实标注 |
| ③ 网格 Meshing | Gmsh 曲率/薄壁自适应 | `meshing.py`：曲率自适应尺寸场 + **质量门禁** | 同思路，且门禁是硬门禁 |
| ④ 求解 Simulation | CalculiX → FRD | `solver.py`：**CalculiX 与 Abaqus 双后端** | 双方言 deck，各自结果通道 |
| ⑤ 分析 Analysis | scikit-learn / 代理模型 / NSGA-II | `post.py`：结果解析 → 峰值/逐节点 | **只做数据提取，不做 ML** —— 数据集产出只需这一步 |
| 阶段间接口 | **标准化 JSON** | `spec.py`：`FEASpec` | 这是复现的核心，上下游都只认它 |

**没复现的**：LLM 规划器、向量知识库、闭环优化、涡轮案例（7 叶/12 叶离心+预应力模态）。
本工程聚焦**机翼盒段**这一类可批量生成的静力算例。

---

## 2. 环境

| 组件 | 来源 | 说明 |
|---|---|---|
| Python ≥3.10 + numpy | 已有 | 翼型坐标、结果后处理 |
| **gmsh**（Python API） | `pip install gmsh` | 自带 OpenCASCADE 内核，几何+网格一把梭 |
| **CalculiX `ccx`** | <http://www.dhondt.de/calculix_2.23_4win.zip> | 非 pip 包。放 `tools/calculix/<ver>/`，或用 `FEAGPT_CCX` 指路径，或进 PATH |
| **Abaqus**（可选） | 本机 SIMULIA 安装 | `abaqus.bat` 在 PATH，或用 `FEAGPT_ABAQUS` 指路径 |

```bash
pip install -r requirements.txt
```

> **国内装包提示**：本机实测 pip 镜像速度差 **1400 倍**（清华 11–15 MB/s vs 官方源
> 0.008 MB/s）。装 gmsh 这种大 wheel 时直接 `-i https://pypi.tuna.tsinghua.edu.cn/simple`。

---

## 3. 快速开始

```bash
# 默认算例：NACA4412 翼盒，5 个翼肋，铝 2024-T3（CalculiX）
python run_pipeline.py --demo

# 换 Abaqus 后端（同一个模型、同一个物理）
python run_pipeline.py --demo --solver abaqus --out outputs_abaqus

# 自然语言驱动（规则解析版）
python run_pipeline.py --text "NACA4412 wing box, chord 1000 mm, span 2000 mm, 5 ribs, aluminium"

# 参数化研究（FeaGPT 那 432 个构型的缩小版）
python run_pipeline.py --sweep "airfoil.n_ribs=3,5,7" "airfoil.chord=800,1000"

# 加长桁（每侧蒙皮 3 条竖式长桁；算例自动改名 ..._str3）
python run_pipeline.py --demo --stringers 3 --out outputs_str

# 只要网格，不求解
python run_pipeline.py --demo --mesh-only

# 独立验证①：悬臂盒梁，解析解 + 网格敏感性 + 静力平衡
python verify_cantilever.py

# 独立验证②：同一模型两个求解器交叉验证（先跑上面两条 --solver 命令）
python verify_solvers.py

# 任一算例都可交叉验证（--case 指定算例目录名）
python verify_solvers.py --ccx outputs_str --abaqus outputs_str_abaqus --case naca4412_wingbox_str3

# T 形截面长桁（M3/T5）—— 截面族，参数进 spec，算例自动改名 ..._str3_T
python run_pipeline.py --spec ../feagpt_repro/_t5_probe/naca4412_wingbox_str3_T.spec.json

# 加筋平板壁板（M3/T2）—— 第一个真正的第二*结构族*：600×600×2 mm 铝板，四边简支，面压
python run_pipeline.py --spec _t2_probe/stiffened_panel_600x600.spec.json     --out outputs_panel          # 素板 n=0
python run_pipeline.py --spec _t2_probe/stiffened_panel_600x600_str3.spec.json --out outputs_panel         # 3 条 blade 长桁
python run_pipeline.py --spec _t2_probe/stiffened_panel_600x600_str3.spec.json --out outputs_panel_abaqus --solver abaqus

# 平板独立验证线：Navier 闭式解 + 载荷/平衡/对称不变量（不依赖任何解析模型的静力平衡也在这里）
python verify_panel.py --json ../FEM-Bench-Aero/panel_verify.json

# 开孔板独立验证线：Kirsch / Howland + 孔边收敛 + 平衡 + λ 趋势 + 双码（M5/T4）
python verify_hole.py --trend
python _t4_probe/open_hole_readings.py

# 多闭室翼盒独立验证线：Bredt-Batho 多闭室扭转 + 逐闭室剪流 + 闭室数效应 + 双码（M5/T6）
python verify_multi_cell.py --with-abaqus

# 柱壳尺寸/壁厚独立验证线：退化柱壳在**每个尺寸**上对薄壁闭式解 + FE 比值 vs 闭式比值（M5/batch6）
python verify_barrel_size.py --json ../FEM-Bench-Aero/verify_barrel_size.json

# 关 3 交叉验证（注意 ccx 的**根目录逐条不同**：outputs / outputs_str / outputs_T / outputs_panel）
python verify_solvers.py --ccx outputs        --abaqus outputs_abaqus        --case naca4412_wingbox
python verify_solvers.py --ccx outputs_str    --abaqus outputs_str_abaqus    --case naca4412_wingbox_str3
python verify_solvers.py --ccx outputs_panel  --abaqus outputs_panel_abaqus  --case stiffened_panel_600x600 \
       --spec _t2_probe/stiffened_panel_600x600.spec.json --force 36 --reaction-set all

# 把已有算例导成数据集 case（补 .msh + 语义真值，**不重跑求解**）
python make_dataset.py --solver ccx    --cases outputs outputs_str outputs_T outputs_panel           --root ../FEM-Bench-Aero
python make_dataset.py --solver abaqus --cases outputs_abaqus outputs_str_abaqus outputs_T_abaqus outputs_panel_abaqus --root ../FEM-Bench-Aero

# ★ 重导后必须跟去重（见 §10：源目录里仍留着重复件）
python dedup_dataset.py --root ../FEM-Bench-Aero --keep naca4412_wingbox --apply \
    --json ../FEM-Bench-Aero/dedup_report.json

# 数据集验收：关 4 语义 + 自洽性 + 去重 + 应力定义 + 零三角（硬闸）
python check_semantics.py --root ../FEM-Bench-Aero --json ../FEM-Bench-Aero/gate4.json
python verify_dataset.py  --root ../FEM-Bench-Aero --json ../FEM-Bench-Aero/verify_report.json

# M4：清单 / 索引 / 划分 —— 先生成，再独立复算校验（等价类不得跨 split）
python make_manifest.py --root ../FEM-Bench-Aero \
       --json ../FEM-Bench-Aero/manifest.json --md ../FEM-Bench-Aero/MANIFEST.md
python eval_dataset.py  --root ../FEM-Bench-Aero --json ../FEM-Bench-Aero/eval_report.json

# 分组回归：动了几何/分类器之后，种子的分组必须逐位一致（17 条：9 条老种子 + 8 条 D31 尺寸点）。
#   指纹里同时含单元数与质量，所以「有意重建网格」也会如实报 DIFF（D10 时是 7/9）；
#   那种情况下重签基线（--save 覆盖），并把旧基线另存留档（regress_baseline_groups_pre_d10.json）
python regress_groups.py --save regress_baseline_groups.json     # 改代码前
python regress_groups.py --check regress_baseline_groups.json    # 改代码后

# 退化自检：新结构形式必须能退回已信任的旧形式（T1：后掠/锥形→等直；T2：长桁数→0；
#   T5：翼缘宽→0；T6：腹板数→0；T7：复材单层→各向同性还原 + 铺层契约拒绝）。
#   现共 54 项，覆盖 T1/T2/T3/T4/T5/T6/T7。D30（2026-10-24）起 T7 由 6 项增至 10 项：
#   T7.clt-angle-ply（[+45/-45]s 手推闭式 + A16/A26 必须为 0）、T7.clt-quasi-isotropic
#   （准各向同性闭式 + 各向同性恒等式 G=E/(2(1+nu)) 独立验）、T7.d30-scalar-axes（M/T/L/S
#   四轴计数 → train/val/test）、T7.thickness-invariance（厚度维退化：断言载荷比恰为 2、
#   等效模量与 t 无关——恒定名义应力下 u=sigma*L/E 与壁厚无关，厚度变体零信息量）
python check_forms.py --json ../FEM-Bench-Aero/check_forms.json

# M7 / D31：尺寸维「先探针、后落地」的四步（2026-10-24）。顺序是被坑出来的，别调换。
cd _probe_m8
# ① 改划分规则**之前**，用 split_of 直测存量——0 漂移才准动规则（实测 44 条 0 变化）
python probe_d31_wingbox_size.py        # -> probe_d31.json / probe_d31_landed.json
# ② 物理核对：壁厚是否严格 1/t、展长是否三次幂、交互项是否可忽略（0.06 % / 0.17 %）
python physics_check.py                 # -> physics_check.json
# ③ abaqus 结果到手后：**先 resummarize 再 make_dataset**
#    手工 bat 只产 <case>.odb.json；直接 make_dataset 会照常导出五件、只打 max|u|=n/a（提示不是闸）
python ../resummarize.py --roots outputs_abaqus_size_*
python ../make_dataset.py --solver abaqus --cases outputs_abaqus_size_* --root ../../FEM-Bench-Aero
# ④ 双码批量交叉（8 条一次算完，比逐条跑 verify_solvers 省事；闸门口径与它一致）
python xval_m8.py                       # -> ../FEM-Bench-Aero/_xval_m8.json

# M8 算法侧 baseline（2026-10-24）：9 档 × 4 目标，val 选 / test 报，bootstrap 区间
#   探针 _probe_m7/learnability.py 只作历史记录；对外报数一律用这个
python baseline.py --boot 4000 --json ../FEM-Bench-Aero/baseline_d31.json

# M9：目标口径诊断（max_w 到底能不能当翼盒代理目标）-> w_vs_disp_diag.json
cd _probe_m9 && python diag_w_vs_disp.py
#   要点：超参一次选定（不是 val/test 各选一次）、全部 log 空间拟合、
#   常数地板用 MAPE 最优的加权中位数（不是算术平均）、最强物理对手含自由指数幂律（M2L/M2X）

# M10 / D33：后掠轴补中间档（20° → 30°）。同样「先探针、后落地」。
cd _probe_m10
python make_m10_specs.py --list         # 只有一条：仅 sweep_deg=30，锥度中性、其余全锚定
python probe_d33_split.py               # -> probe_d33_split.json（52 条 0 换边 / D12 11/11 / 新点落 train）
python physics_sweep_axis.py            # -> physics_sweep_axis.json（超线性 / 割线外推 −43.4 % / 30° 偏趋势 −6.2 %）
#   abaqus 侧：在 WorkBuddy **外**手工跑 run_m10_abq_MANUAL.bat（agent 内 abaqus 必崩，见 §6）
python ../resummarize.py --roots outputs_abaqus_sweep30
python ../make_dataset.py --solver abaqus --cases outputs_abaqus_sweep30 --root ../../FEM-Bench-Aero
python compare_d31_d33.py               # -> d33_vs_d31.json（主目标 −0.22 pp / planform −7.2 pp / 副目标 +4.16 pp）
python xval_m10.py                      # -> _xval_d33.json（单点双码：mesh 5347/5347、平衡 1.6e-4 %、vM 中位差 0.23 %）

# M11 / D34：模型形式（sweep 线性 -> 二次）。判据 = 零泄漏 LOO@30，val 只确认，test 只报
python _probe_m11/sweep_form.py         # 4 形式 x 2 档 = 8 组合 -> sweep_form.json（lin 必须复现 M3/M5）
python _probe_m11/verify_quad.py        # 四向拆台：其他目标 / 配对 bootstrap / 分机制 / 系数稳定性
python _probe_m11/residual_diag.py      # 剩余误差根因：交互项在 train 上零样本（不可估）
#   注意：xval_m10.py **不复制**检查逻辑，它 import _probe_m8/xval_m8 并只改 HERE 数据根
#   ⇒ 两个里程碑用的是同一份判据代码（两份实现是闸门互相漂移的常见来源）

# D34 收口：把门禁从 52 口径重量到 53 口径（纯后处理，不起求解器）
python _probe_m11/gate_all53.py         # -> ../FEM-Bench-Aero/gates_all53_d34.json
#   关 1 调 eval_dataset._recompute（与 verify_dataset 同源）→ 53/53、最差 minJ 0.4636、tri3 0
#   关 3 重定向 xval_m8._load 后跑 check_one 本体 → **只对翼盒 32 条**
#   ⚠️ 族专用判据不能跨族套用：xval_m8 写死 500 N 端载 + 根截面反力平衡，
#      硬套给柱壳/开孔板/加筋板会报 9900 % / 700 % / 100 % 的一整片假 FAIL（已实测）
python check_semantics.py --root ../FEM-Bench-Aero --json ../FEM-Bench-Aero/gate4_d34.json
#   -> 关 4：106/106（53 条 × 2 树）

# M12 / D35：补 sweep × taper 交互锚点。**先改划分规则，再补点**（不改规则新点必被判 test）
python _probe_m12/planar_census.py      # -> planar_census.json（普查 train 已学值域：sweep {0,10,20,30}、taper {0.6,0.8,0.9,1.0}）
python _probe_m12/d35_split_probe.py    # 改规则前先模拟：存量只换边 1 条（sweep20_taper060 test->train）
python _probe_m12/d35_landed.py         # 改规则后用真 split_of 逐条复核（预测 == 实测 PASS）
python _probe_m12/make_d35_specs.py     # 生成 sweep30_taper080（脚本内断言 split == train）
python run_pipeline.py --spec _probe_m12/naca4412_wingbox_sweep30_taper080.spec.json --out _probe_m12/outputs_sweep30_taper080
#   ★ 新增能力 --deck-only：只写 abaqus 方言 deck、不求解 —— 沙箱里不必先让它崩一次拿 .inp
python run_pipeline.py --spec _probe_m12/naca4412_wingbox_sweep30_taper080.spec.json --out _probe_m12/outputs_abaqus_sweep30_taper080 --solver abaqus --deck-only
#   abaqus 侧：在 WorkBuddy **外**手工跑 _probe_m12/run_d35_abq_MANUAL.bat（agent 内 abaqus 必崩，见 §6）
#   ⚠️ 顺序不可反：先 resummarize 再 make_dataset。反了不报错，只在摘要打 max|u|=n/a、gate4 照旧绿
python resummarize.py --roots _probe_m12/outputs_abaqus_sweep30_taper080
python make_dataset.py --solver abaqus --cases outputs_abaqus_sweep30_taper080 --root ../../FEM-Bench-Aero
python _probe_m12/xval_d35.py           # -> _xval_d35.json（判据零复制；mesh 5302/5302 坐标差 0、平衡 5.0e-4 %、vM 中位差 0.21 %）
python _probe_m12/physics_sweep_x_taper.py   # log 可加分解：交互 H 在三个组合点全为负（-12.6 / -7.8 / -25.9 %）
python _probe_m12/why_planform_fixed.py      # 机制拆解：pred/true 1.152 -> 1.073 -> 0.968 **跨过 1.0**（真学到）
python _probe_m12/same_test_set.py           # 同一 6 条 test 集上比 A/B/C/D 四配置（配置 D 是反事实）
python _probe_m12/interaction_feature.py     # 交互特征实验 —— 结论：**不落地**（5.3 倍外推，角点崩到 -36.5 %）

# M13 / D36：补纯后掠 35° 中间站。**先预注册再测量** —— 只补数据、不动形式、不动考点
python _probe_m13/make_d36_specs.py          # 生成 sweep35 spec（落位断言：旧规则 val / 新规则 train）
python _probe_m13/d36_split_probe.py         # 改常量前模拟：54 条存量 **0 换边**、D12 11/11
python _probe_m13/predict_sweep35.py         # ★ 预注册：磁盘上还没有 35° 测量值时把三条预测写死归档
#   ⚠️ --out 必须直接给「算例名目录」：xval_m8.check_one 找 outputs_<case 去前缀>，
#      写成 --out _probe_m13/outputs 会让双码脚本找不到 frd（D36 真踩过）
python run_pipeline.py --spec _probe_m13/naca4412_wingbox_sweep35.spec.json --out _probe_m13/outputs_sweep35 --solver ccx
python run_pipeline.py --spec _probe_m13/naca4412_wingbox_sweep35.spec.json --out _probe_m13/outputs_abaqus_sweep35 --solver abaqus --deck-only
#   abaqus 侧：在 WorkBuddy **外**手工跑 _probe_m13/run_d36_abq_MANUAL.bat
#   ⚠️ 顺序不可反：先 resummarize 再 make_dataset（反了不报错，只打 max|u|=n/a）
python resummarize.py --roots _probe_m13/outputs_abaqus_sweep35
python make_dataset.py --solver abaqus --cases _probe_m13/outputs_abaqus_sweep35 --root ../FEM-Bench-Aero
python _probe_m13/d36_resolve.py             # 结算预注册：三条估计全部低于实测（-7.07 / -8.14 / -5.38 %）
python _probe_m13/d36_assess.py              # 同 6 条 test 集 A/B -> d36_ab.json
python _probe_m13/sweep_form_d36.py          # 三次基可辨识性 -> 两侧判据对撞，不换形式
python _probe_m13/xval_d36.py                # -> _xval_d36.json（mesh 5687/5687 坐标差 0、平衡 2.6e-4 %、vM 中位差 0.20 %）

# 关 1 的证据：从**归档 .msh** 读回 minJ 与单元类型（不靠重建，也就不会「重建出对的、归档是错的」）
python diagnostics/msh_quality.py --tree ../FEM-Bench-Aero/modeling
# 三角长在哪个面上、那个面多窄（D10 定位：24 个全在后梁腹板四角）
python diagnostics/tri3_map.py ../FEM-Bench-Aero/modeling --size 12
# 五种 gmsh 配置逐个量：哪种清三角、代价多少（D10 选型，被否掉的方案也留了读数）
python diagnostics/probe_tri3.py

# 「没有静默漂移」：重导前存哈希、重导后对差异——每一条差异都必须是你预测到的
python diagnostics/hash_manifest.py write snap_before.json ../FEM-Bench-Aero
python diagnostics/hash_manifest.py diff  snap_before.json ../FEM-Bench-Aero \
       --only modeling --only _xval --gate changed    # 只看算例，0 变更为通过
```

每跑一个构型产出一个目录：

```
outputs/<case>/
  <case>.spec.json      # 该构型的完整规格（可复现）
  <case>.step           # 几何（若导出）
  <case>.msh            # 网格（两条路径都写：--mesh-only 与完整求解）
  <case>.inp            # 求解器 deck（CalculiX 或 Abaqus 方言）
  <case>.frd            # CalculiX 结果（仅 ccx）
  <case>.odb            # Abaqus 结果库（仅 abaqus）
  <case>.odb.json       # ODB 抽出的中间结果，逐节点（仅 abaqus）
  <case>.results.json   # 峰值位移/应力 + 位置
  <case>.nodes.csv      # 逐节点位移
  <case>.truth.json     # 语义真值（拓扑计数 + 关 4 结论），完整求解后落
```

---

## 4. 流水线怎么走

```
FEASpec (JSON)
   │
   ├─ geometry.build()              BUILDERS[spec.structure.family](gmsh, spec)
   │        └─ wingbox builder：gmsh OCC：上下蒙皮 / 前后梁腹板 / N 个翼肋 / 可选长桁
   │        └─ stiffened_panel builder：矩形蒙皮 + N 条竖式长桁（M3/T2）
   │        └─ occ.fragment() 让翼肋/长桁与蒙皮共节点，逻辑名经 outDimTagsMap 继承
   ├─ meshing.build_mesh()          曲率自适应尺寸场 + 最小 Jacobian 门禁
   ├─ meshing.referenced_nodes()    丢掉不被任何单元引用的节点（见 §5.4）
   ├─ inp_writer.write_inp(dialect) *SHELL SECTION / *BOUNDARY / *CLOAD / *STATIC
   │        ├─ 厚度表、约束自由度、压力作用组 **全部由 builder 声明**（见 §4 族契约）
   │        ├─ dialect="ccx"    → *NODE FILE, OUTPUT=3D（D8：外纤维；见 §5.1）
   │        └─ dialect="abaqus" → *OUTPUT, FIELD / *NODE OUTPUT / *ELEMENT OUTPUT
   ├─ solver.run()
   │        ├─ ccx     → .frd
   │        └─ abaqus  → .odb →（abaqus python abaqus_odb.py）→ .odb.json
   └─ post.summarize_data()         同一套归纳，求解器无关
```

**关键设计：求解器选择发生在写 deck 之前**（`pipeline.run`），因为两个代码说不同方言，
deck 内容取决于用哪个求解器。结果侧则相反——两条通道都归到同一个中间结构
（`{nodes, results: {DISP, FORC, STRESS}}`），所以 `post.py` 之后**一行都不分支**。

### 结构族（M2 抽象 / M3 验收）

`geometry.build()` 按 `spec.structure.family` 分发到 `BUILDERS` 里的 builder；未知族**直接报错**，
绝不回落到翼盒——那正是「跑得通但是错的」这类问题。

```python
BUILDERS = {"wingbox": build_wingbox, "stiffened_panel": build_stiffened_panel,
            "fuselage_barrel": build_fuselage_barrel}
def build(gmsh, spec, step_path=None): ...
```

一个 builder 的**全部契约**就是返回 `GeometryResult`。M2 时这份契约只有「逻辑组名 + span/chord
+ 包围盒 + `bc_groups`」，T2 一开工就发现**不够**：链路里还有四处写着翼盒的常识，换成平板就
「跑得通但结果错」。所以 M3 把契约扩成**按族声明**（M5/T3 又加了第五项）：

| 声明 | 你不声明会怎样（平板实测） |
|---|---|
| `bc_nodes(nodes) -> {组名: [节点]}` | `pipeline` 原来用 `abs(z)<1e-6` 找约束点——**平板整个蒙皮都在 z=0**，会把整块板钳死 |
| `clamp_dofs = (1,3)` | 原来固定 `*BOUNDARY, 1, 6`（全约束），而简支只该约束平动 |
| `shell_thickness = {"panel": t, "stringers": t_s}` | 原来按翼盒组名 + 读 `spec.airfoil.*` 建厚度表 |
| `pressure_group = "panel"` | 原来写死 `*DLOAD E_UPPER_SKIN` |
| `pressure_dload_sign = +1`（M5/T3 · D21） | 翼盒/平板蒙皮是**拉伸**出来的、柱壳蒙皮是**回转**出来的，法向朝向相反 ⇒ deck 硬编码的 `-abs(p)` 写在柱壳上就是**外压**（实测自由径向膨胀 −0.22725 mm，应为 +0.228）。默认 `-1`，柱壳声明 `+1` |

所以 `meshing` / `inp_writer` / `post` / `pipeline` 都不认识「翼盒」这个词。
翼盒族的参数仍在旧的 `airfoil` 块里（不动 = 不废既有归档），新族的参数放 `spec.structure.params`。

**默认值就是翼盒**：`bc_nodes=None` 时 `resolve_bc_nodes()` 仍走 z≈0 / z≈span 的老规则，
`clamp_dofs` 默认 `(1,6)`、`pressure_group` 默认 `"upper_skin"`。所以 9 条翼盒算例的 deck
**逐字节未变**（M3/T2 用哈希清单证明过，见 §10）。

### 翼盒的简化

只建**前后梁之间的闭合盒段**（`spar_chordwise=(0.25, 0.70)`），
前缘/后缘悬臂段不参与承力，按标准工程做法省略。

### 长桁的建模方式

`n_stringers_per_skin = N` 时，上下蒙皮各加 N 条**竖式长桁（blade stringer）**：
位于 `x = const` 平面、沿展向通长、顶边与蒙皮贴合、底边自由的一片竖板——
薄壁盒段里长桁的常规理想化。默认 `N = 0`，即不加强（保持既有基线不变）。

三个非显然之处（都踩过，见 §5.5）：

1. **长桁站位必须是蒙皮样条的控制点**。否则板顶边与蒙皮只是"靠得很近"而非共享边，
   布尔运算会吐出碎片或干脆不连——所以站位被插进截面点列（`_points_on_section(extra=...)`）。
2. **长桁也是 `dx ≈ 0` 的平面**，与翼梁的判据撞车。分类器改为按**弦向站位**区分两者
   （站位严格取在梁之间，集合不相交）。M2 之后分组由**建面打标**决定，
   这条判据降为交叉校验（见 §5.6）。
3. **上/下长桁不能用 `y > 0` 判**。NACA4412 有弯度，下蒙皮在 0.59c 处 `y = −10.3 mm`，
   20 mm 长桁会伸到 `y = +9.7 mm`——中心在 y=0 之上却明明属于下蒙皮。
   改成与**局部盒段中高线**比较。

### 长桁截面族（M3 / T5）

`airfoil.stringer_kind` 选截面：`"blade"`（默认，1 片竖板）或 `"T"`（加翼缘，`stringer_flange_width` 默认 30 mm）。
截面建在 `feagpt/sections.py`，builder 只负责**把返回的每条 segment 拉伸出去**——
它不再知道长桁是什么形状。未注册的截面名**抛 `ValueError`**，不回落 blade。

四条实测结论（不是推理）：

1. **T 形是 3 个面，不是 2 个。** 翼缘被腹板切开 → 腹板 1 + 翼缘 2 = 3
   （`diagnostics/t_stringer_probe.py`）。
2. **两片「贴在一起」的面在网格里根本不连着。** 各自拉伸的腹板与翼缘之间共享
   **0 个节点**——翼缘是一根悬空悬臂，而线性静力照样解得出位移，**三道数值门禁一条都不报警**。
   `occ.fragment` 才把它们粘起来（每对面共享 11 个节点）。所以 flanged 截面**必须过布尔**；
   blade 是单片，跳过布尔，几何与 M2 **逐字节相同**（回归是硬门）。
3. **关 4 的期望值必须乘「每根长桁的壳面数」。** 漏掉这个因子，带缘条的模型会
   **通过全部数值门禁而语义是错的**。这个数由截面定义给出，**不在已建模型上量**——
   否则关 4 就是拿构建器验它自己。
4. **翼缘宽 → 0 必须退化成 blade，且关 4 得跟着降为 1 面。** 否则关 4 会把**正确的**
   退化构建判成错。这就是 `check_forms.py` 存在的理由。

**网格尺寸上限**（`GeometryResult.mesh_size_cap`）：T 形翼缘是 15 mm 半宽的窄条，
blossom 全四边形在默认尺寸下直接失败（`1D mesh cannot be divided by 2`）。
我先假设「按翼缘半宽自适应」——**被数据证伪**：宽度 20/30/40/50/60 mm 下 minJ 为
0.485 / 0.533 / **0.433** / **0.225** / 0.594，**非单调**，宽度 50 处逼近门禁 0.30。
改成固定上限 12 mm 后，同样 5 种宽度 minJ 0.504 / 0.533 / 0.493 / 0.527 / 0.532 —— 每个宽度都稳。
落地方案 `min(0.8 × 翼缘半宽, size_chord)`，本算例实测恰为 12 mm。
`mesh_size_cap = None`（所有 M3 之前的模型）时尺寸场与从前**完全一致**。

### 加筋平板壁板（M3 / T2）—— 第一个第二个**结构族**

`structure.family = "stiffened_panel"`，参数在 `structure.params`（`feagpt/panel.py`）：
`length / width / thickness / n_stringers / stringer_height / stringer_thickness /
stringer_kind / stringer_flange_width`。默认 600×600×2 mm，3 条 blade 长桁。
**未认识的参数名直接 `ValueError`**，因为拼错的键会被静默忽略、于是建出另一个板。

一点与翼盒的本质差别：**平板不是「小翼盒」**。它没有翼梁/翼肋/弯度，所以它的
关 4 映射、支承规则、载荷类型全是另一套：

- **支承**：四边简支 = 轮廓上的节点约束**三向平动、转动自由**（`clamp_dofs=(1,3)`），
  这正是 Navier 闭式解假设的硬简支。规则放在 `panel.edge_nodes(nodes, params)`，
  它吃的是**节点表**而不是 gmsh 会话 —— 因为跨解算器的平衡检查只有 `{label: (x,y,z)}`。
- **载荷**：面压（`*DLOAD, P`）。声明里没有「翼尖节点组」可以挂集中力，所以
  `build_stiffened_panel` 遇到 `load.kind != "pressure"` **直接报错**——静默施加零载荷比失败更糟。
- **站位**：`length × (j+1)/(n+1)`，由 `n_stringers` 派生（一个数比两个数不容易冲突）。

**必须过布尔——这是实测出来的，不是设计偏好。** 长桁条与蒙皮是「贴在一起」的两个面。
`diagnostics/panel_bond_probe.py` 三种做法对照：

| 做法 | 蒙皮面数 | 每根条与蒙皮共享节点 | 结论 |
|---|---|---|---|
| 不做布尔 | 1 | **0** | 三根**悬空悬臂**；线性静力照样解得出位移，三道数值门禁一条都不报警 |
| `fragment([蒙皮],[条])` | **4** | **51**，共享 3 条边界曲线 | 采用 |

所以关 4 把「蒙皮面数 = n + 1」算成**精确值**：它不是记账约定，是「粘结真的发生了」的观测量。

同一件事在翼盒的 T5 上出现过一次（腹板与翼缘共享 0 节点），两次都是同一个教训：
**两个面在几何上贴合，不等于在网格里连着。**

**6 mm 网格不是拍的。** `diagnostics/panel_convergence.py` 把 FE 中心挠度对 Navier 闭式解
在 12 / 6 / 3 mm 上量了一遍：**−6.9 % / −0.63 % / −0.10 %**（单调向上收敛）。
6 mm 是误差已进入 2 % 验证门内的最粗尺寸。同一次研究还做了**软支承消融**
（把 `clamp_dofs` 改成只约束 z）作为对照：6 mm 下给出**完全相同**的数字（−0.95658），
证明这个 6.8 % 不是支承条件造成的。

**唯一的 spec 工厂**是 `panel.make_spec()`。验证线、退化自检、M5 放量都从它建模型——
三个调用方各留一份「600×600×2 + 3 根 blade + 6 mm」正是扫描扫出「其实从来不是同一个模型」的原因。

### 多闭室翼盒（M5 / T6）—— 翼盒族的新形式维，不是第五个族

`airfoil.web_chordwise` 给出一串**弦向站位**（0–1 的弦比），builder 在这些站位上各放一道
**贯穿上下蒙皮的中间腹板**。闭室数 `n_cells = n_webs + 1`，进 `truth.design`：

```
n_webs = len(web_chordwise)          n_cells = n_webs + 1
web_stations = [c × chord for c in web_chordwise]
```

四条**实测**结论：

1. **「腹板」与「长桁」是不同的结构件，站位不许重合。** 腹板贯穿两蒙皮 ⇒ 每加一道 +1 闭室；
   长桁贴单侧蒙皮、不贯穿 ⇒ **不**新增闭室。两者站位重合时关 4 会数不清面
   （`check_forms :: T6.refuses-on-stringer` 用 `web = 0.475 = stringer 站位` 反证必须 `raise`）。
2. **腹板必须落在两梁之间。** 站到前梁之前的 0.1c 就不是「闭室」而是一块悬空隔板 ——
   `T6.refuses-outside-spars` 钉死这一点。
3. **腹板把肋面也切开了。** 实测 `web1`（`n_ribs=5, n_web=1`）：38 面 = 梁 8 + 蒙皮 8×2 +
   腹板 4 + **肋 10**（不是 5）。所以族公式里 **单侧蒙皮面 ×(n_web+1) 与肋面 ×(n_web+1)**
   这两个因子必须都带上（见 `FEM-Bench-Aero/README.md` §4.1）。
4. **加腹板对薄翼型的 GJ 增益极小**（解析 +0.42 % / +1.76 %）⇒ **不能靠「刚度变大」判对错**。
   真正区分闭室数的是**剪流**：各闭室 `|qᵢ|` 相差 10–25 %，腹板承 `|qᵢ − qᵢ₊₁|`。
   这也是为什么 T6 的载荷是「弯曲 + **端部扭矩**」——闭室数只在扭转下可观测。

**网格不需要 cap**：腹板在弦向很薄，但落点离前后梁都远，默认尺寸下 minJ **0.5467–0.5784**、0 三角。
沿用 T1/T5 的同一条规矩——cap 只给「窄到默认尺寸撑不住的条带」声明。

**`_GROUP_ORDER` 新增了 `webs` 组**。这一项会让**每一条**翼盒 case 的 `regress_groups` 指纹
多一个键（既有组的面一个没动）⇒ 按 D10 先例**重签基线**（旧基线
`regress_baseline_groups_pre_t6.json`），重签前 0/9、重签后 9/9。

---

## 5. 踩过的坑（都固化在源码注释里）

### 5.1 CalculiX deck

1. **`*NODE FILE` 上不要加 `NSET=`** —— CalculiX 2.23 会写出**空的 DISP/FORC 块**，
   结果文件看着正常、其实一个位移都没有。
2. **壳结果要 `OUTPUT=3D`（D8 起）** —— 这条在 2026-10-03 被**推翻重写**，原因值得记住。
   原来的写法是 `OUTPUT=2D`，理由是"否则 CalculiX 把壳扩展成实体，9 个中面节点变 18 个，
   位移场跟中面理论没法直接比"。前半句对，后半句是**把方便当成了正确**：实测（4 单元板，
   `diagnostics/` 系列探针）表明 `OUTPUT=2D` 报的是**两个展开层的均值** ——
   `SXX = 0.24626 = (12.4841 + −11.9915)/2`，位移同样取均值。**纯弯板上下表面等值反号，
   均值恒为 0**，于是平板报出 `vM ≡ 0`，而真正决定尺寸的弯曲应力根本不在结果里。
   现在写 `OUTPUT=3D`，把 ±t/2 两层都留下，再由 `post.collapse_expanded_shell`
   折回中面（力按 **SUM**、位移/应力按**均值**；见 §5.6）。代价是要自己把展开标签映射回
   中面标签——展开后的节点号会整体偏移，不能靠编号对应，必须读 deck 自己的 `*NODE` 块。
3. **`*ELEMENT` 块的编号必须全局连续** —— 每个 ELSET 各自从 1 开始会让 CalculiX 报
   "element N is already defined"。

### 5.2 FRD 解析

- `DISP` 数据行**只写 3 个分量**（声明 4 个，magnitude 省略），按 `ncomp` 硬读会把整段吞掉。
- 节点号与负号会**粘连**成 `4-6.87068E-10`，必须按定宽字段读。

### 5.3 Abaqus deck / ODB

- **`OUTPUT=2D` / `OUTPUT=3D` 是 CalculiX 专有参数**，写进 Abaqus deck 会直接中止。
- **`ask_delete=OFF` 不是可选项**：没有它，只要上次留了作业文件，Abaqus 就停在
  交互式的"是否覆盖？"提示上，直到超时。
- **残留 `.lck` 会让作业中止，而 Abaqus 仍然返回 0**。原因写在 `<job>.msg` 里
  （不是 stdout、也不是 `.dat`）："Detected lock file … please confirm that no other
  applications are attempting to write to the output database"。批量跑几百个构型时，
  每一个受影响算例都会被"成功-然后-空结果"。适配层在启动前清掉自己输出目录里的锁文件
  （那个时刻它必然是陈旧的），并记进日志；同时不再只信退出码，而是要求**有可用的 ODB**
  并回读 `.msg`/`.dat` 报出真实原因。
- **`odbAccess` 是"像 dict"而不是 dict**，三种错法各不相同：
  `frame.fieldOutputs` 是 `Repository`（支持 `[]`、`keys()`，**没有** `.get()`）；
  `instance.elements` 是 `OdbMeshElementArray`（可迭代，没有 `keys()`）；
  `FieldOutput.getSubset(position=...)` 要**符号常量** `abaqusConstants.ELEMENT_NODAL`，
  传字符串会报 `position; found string, expecting ...`。
- **壳应力是 4 分量、不是 6 分量**：Abaqus 2026 实测 `S` 类型为 `TENSOR_3D_PLANAR`，
  分量为 `(S11, S22, S33, S12)`（壳理论平面应力，`S33≡0`）。而 FRD 的分量序是
  `(SXX, SYY, SZZ, SXY, SYZ, SZX)`——**两个剪切分量顺序相反**。所以必须**按分量标签**映射，
  按下标映射会在分量数变化时静默出错。
- **`ELEMENT_NODAL` 插值只暴露最外侧两个截面点**（默认 5 点 Simplex 截面下是 1 和 5）。
  取 `sorted(sp)[len//2]` 拿到的是**顶面**而不是中面——这是典型的"安静地给错答案"。
  正确做法是壳理论的膜应力：`(σ_下表面 + σ_上表面)/2`。
- **Abaqus 必须在不被沙箱隔离的 shell 里运行**（本机实测）。`pre.exe` 要往
  `%TEMP%\22207_<job>_<pid>` 写 scratch 目录，工作区之外；写入被拦时它**不报权限错**，
  而是以「**固定 ~19 s 延迟 + `Analysis Input File Processor exited with an error` +
  `.dat` 里一条错误都没有 + ODB 只有骨架没有帧**」的形式失败。定位过程：
  先用 1 个单元的最小卡片复现（与模型无关）→ 再 A/B 掉 `ask_delete`、路径空格、
  输出块、并行模式（都不是）→ 最后比对"隔离 / 不隔离"两次调用才锁定。

### 5.5 长桁的网格（本轮）

长桁是一片 **20 × 500 mm** 的窄条，gmsh 默认的 blossom 重组算法在这种长宽比上表现很差：

| 重组算法 | 单元 | minJ | 长桁 minJ | 三角 |
|---|---|---|---|---|
| 1（blossom，原默认） | 7118 | 0.350 | 0.398 | **444** |
| **3（blossom 全四边形）** | 7517 | **0.523** | **0.690** | **0** |
| 2（simple 全四边形） | 8115 | 0.245 ❌ | 0.245 | 0 |

用 `diagnostics/stringer_quality.py` 定位后确认：**坏单元几乎全在长桁上**（432/444），
蒙皮只是轻微下降（0.52–0.56）。

但全四边形**不是普遍更好**：对无长桁的盒段，blossom 反而给出更高的 minJ
（0.625 vs 0.573）。所以没有全局改默认值（那会作废所有既有验证数据），
而是让**网格阶段按模型自适应**（`MeshSpec.recombination_algorithm = 0` 表示自动：
有薄长桁条用 3，否则用 1），并把选择写进 mesh 报告的 notes。想强制时显式给值即可——
这也正是做「有无长桁」A/B 对比时保证两边网格策略一致的手段。

**第二道自适应（D10，同日）：数三角。** 上面这条只看**几何**，看不出 `chord800` 盒段的问题
—— 它在**后梁腹板的四个角**上各留一个三角（腹板高 58.4 mm ÷ 弦向尺寸 12 mm = 4.87 个单元，
不是整数，blossom 就用三角填掉剩下的角）。所以 `build_mesh` 现在**建完再数**：
三角数非 0 且 spec 未显式指定算法时，用 blossom 全四边形**重建一次**，并把
`escalated_from` / `recombination_algorithm` / `tri_count` 三个字段写进网格报告。实测代价：

| 模型 | 第一遍（alg 1） | 升级后（alg 3） |
|---|---|---|
| `n_ribs3_chord800` | 8 个三角，minJ 0.5973 | **0 个**，3696 单元（+0.5 %），minJ 0.5950 |
| `n_ribs5_chord800` | 16 个三角，minJ 0.5950 | **0 个**，4112 单元（+4.8 %），minJ 0.5950 |

被否掉的替代方案（`diagnostics/probe_tri3.py` 实测，五个模型 × 六种配置）：`Mesh.Recombine
OptimizeTopology` **一个三角都不动**（仍 8 / 16）；simple 全四边形要 +8.4 % / +14.1 %；
`Mesh.Algorithm = 8` 更糟 —— 18 / 28 个三角且 minJ 掉到 **0.024**，反而会把 **Jacobian**
那道闸弄挂。

其余 9 条算例第一遍就是 0 三角，**走完全相同的原路径、网格逐字节不变**（基线 5144 单元、
`n_ribs7_chord800` 4445 单元，均与归档一致；探针还顺带算出基线几何上 alg 3 得 5351 单元，
与归档里那条显式 `recombination_algorithm=3` 的对照算例**完全相同**）。关 1 的判据同时补上
`tri3 == 0`（`feagpt/meshing.build_mesh`），并在数据集验收里**直接从发运 deck 数**复核
（`verify_dataset.py` 第 8 项 `no_tri3` —— 数 `model.inp` 的 `TYPE=S3`，不依赖 gmsh）。

### 5.4 两个会话级别的 bug（本轮发现，已在修复后重跑全部数据）

**Bug 1 — 载荷被静默稀释。** gmsh 为曲面之外的曲线/点也生成节点，旧几何下本算例有
**396 个节点不连接任何单元**。载荷按"翼尖所有节点（190 个）"平摊，但其中只有 124 个
真正在模型里，于是实际只施加了 `500/190 × 124 = 326.32 N`。根部反力之和精确等于
**−326.32 N**——是静力平衡检查把它抓出来的，别的检查都发现不了。
Abaqus 更狠：它删掉这些节点后直接报 **67 个致命错误**（"集中力施加在未激活节点上"）中止。

> 注：上面 396 / 190 / 124 是**几何修复前**的诊断读数。Bug 2 改了梁腹板位置后几何随之变化，
> 当前复跑读数为**孤儿节点 408 个、翼尖载荷节点 142 个**，`*CLOAD` 合计 **500 N**（不再稀释）。

修复：`meshing.referenced_nodes()` 只保留被单元引用的节点。未被引用的节点不参与刚度，
删除是物理等价的，同时让 deck 对两个求解器都自洽。

**Bug 2 — 梁腹板是斜的，导致前后梁整个丢失。**
`_points_on_section()` 从余弦采样的网格里"挑" `x∈[0.25c, 0.70c]`，但余弦网格上根本没有
0.25/0.70 这两个点：上表面最近点是 `x=261.38`，下表面最近点是 `x=258.16`。把这两点连起来
得到的前梁**斜了 3.2 mm**（后梁斜 7.4 mm）。腹板一旦带上了弦向跨度，`dx ≤ tol` 的归类条件
就判不出来，8 块腹板全被塞进"上蒙皮"组——deck 里**完全没有 `E_FRONT_SPAR` / `E_REAR_SPAR`**，
上下蒙皮单元数还严重不对称（2471 vs 1694）。修复后两组梁腹板回归，上下蒙皮对称
（1856 / 1865）。

### 5.6 面分类器：从「事后反推」到「建面打标」（M2）

`build_wingbox` 建面之后要跑一次 `occ.fragment`，让翼肋、长桁与蒙皮共节点。布尔运算会把
输入面切碎并**重新编号**，所以「切完之后哪个面是什么」曾经是这样恢复的：拿每个输出面的
包围盒去猜——`dz≈0` 是肋、`dx≈0` 是梁/长桁、其余是蒙皮。

这个判据是**二值**的，实测余量 6 个数量级：

| 逻辑组 | dx 最大 (mm) | dz 最大 (mm) | 命中分支 |
|---|---|---|---|
| upper_skin | **450.0000** | 500.0 | else → 蒙皮 |
| front_spar | **0.0000** | 500.0 | dx ≤ 1e-6 → 梁 |
| ribs / root | 450.0 | **0.0000** | dz ≤ 1e-6 → 肋 |

在等直翼盒上很稳，但**它只能服务等直几何**：一旦截面沿展向变化（后掠/锥形，M3 的 T1），
梁腹板的 `dx` 从 0 变成非零中等值，判据立刻翻转，梁面掉进 `else` 被归成蒙皮——
**模型照样求解，三道数值门禁全过，没有一处会报警**。

改法（M2）：**建面时就打标**，让布尔运算自己把名字带过去。

1. 建每个面时同时记下 `face_tag → 逻辑名`（`named_inputs`）；
2. `fragment` 现在**保留 `outDimTagsMap`**（旧代码明写「deliberately ignore the map」），
   第 `i` 个输入变成的输出面继承它的逻辑名——因为 `named_inputs` 就是传给 `fragment`
   的实体顺序，索引天然对齐；
3. 映射先做**完整性自检**：`outDimTags` 里每个面必须被**恰好一个**输入认领
   （漏认领 / 重复认领都上报），再信任它；
4. 旧包围盒判据**降为交叉校验**（`_cross_check_tagging`），不再决定任何事，只报告分歧。

实测（探针 `diagnostics/fragment_map_probe.py`）：基线 21 个面、加长桁 69 个面，
`outDimTagsMap` 长度 == 输入数，每个面被认领恰好一次，**与包围盒判据零分歧**。

回归手段是 `regress_groups.py`：比较的不是计数，而是**每个逻辑组内逐面的 bbox 指纹**
（tag 无关，所以不会拿 gmsh 的重新编号当回归）。M2 改完 9 条种子 **9/9 逐位一致**。

### 5.7 展开壳折回中面：`OUTPUT=3D` 带来的四个坑（D8）

写 `OUTPUT=3D` 之后，FRD 里每个中面节点变成 ±t/2 两个节点，**原来那一套按中面标签做的读法
全部失效**。`post.collapse_expanded_shell` 把它们折回去，四处都不是显然的：

1. **展开后的节点号会整体偏移，不能靠编号对应。** 实测在一个 9 节点的小板上，1..9 变成了
   10..36，偏移量取决于节点总数。所以中面标签必须从 **deck 自己的 `*NODE` 块**读回来
   （`read_deck_nodes`），不能按顺序配。
2. **归属不能按 `(x, y)` 分列。** 平板上这样分是对的（6 mm 时 11761 列、3 mm 时 46432 列，
   **全部恰好 2 层、孤儿 0**），翼盒上
   完全错：上下蒙皮共用同一套 `(x, y)` 采样，而**肋是竖直面**，最坏一"列"住了 81 个节点。
   改成**最近中面节点**归属后，11296 个展开节点一个不剩、一个不重。
3. **一个中面节点不总是拥有两层。** 翼盒实测 4520 个节点 2 层、**534 个 4 层、20 个 6 层**
   （长桁腹板与蒙皮相交处、不同厚度面共边处）。`5074 × 2 = 10148 < 11296` 就是这件事的账。
4. **力要相加，位移/应力要取平均。** 这一条是**量出来的**，不是推出来的：4 单元板上
   `FORC(mid 5) = −25.0 = lo(−25.0) + hi(0.0)`，而 `DISP(mid 5) = −0.00300134` = 两层均值。
   对力用平均会让翼盒的全局合力从 ~0 变成 **−139.8 N**，平衡残差报 **29 %**。
   代码里由 `_FOLD_SUM = ("FORC", "RF")` 显式标出。

**坐标也要三个分量一起平均。** 第一版只平均了 z（因为"厚度方向是 z"），翼盒坐标就错了
**1.5 mm** —— 翼盒的**蒙皮法向是 y**（展向才是 z），只动 z 等于没动。改成逐分量均值后
坐标误差 **0.0**，且沿用 deck 自己的坐标。

**验收口径**：折叠后的中面 von Mises 必须**逐位复现旧的 `OUTPUT=2D` 值**。实测翼盒
**10.2824 vs 10.28**、3 mm 平板 **1.359 vs 1.35897**，位移 `0.956577` 逐位不变。这不是
"差不多"——它证明折回是**无损**的，新的外纤维通道是**加**上去的，不是替换掉的。

**外纤维本身有一个独立的解析见证**：`diagnostics/probe_d8_outer_fibre.py` 用 120×120×2 mm
板对 Navier 闭式解，同时用**两条互不依赖的路**验同一个数——闭式 `6Mx/t²`，以及把中心邻域的
位移场做二次最小二乘拟合反算 `−D(w,xx + ν w,yy)`。实测 3 mm：外纤维 **−0.15 %**、
位移拟合 **−0.58 %**，6 mm 分别 −1.03 % / −1.18 %（单调收敛）。日志落在数据集里
（`probe_d8_outer_fibre.log`）。

> 这个探针存在的**真正理由**是它抓到过我自己的错。闭式解的第一版把形状函数自带
> `sin(mπ/2)=s_m` 代了一次、又乘了一次 `s_m`，符号被算了两遍，双正弦级数退化成全正项，
> 参考值虚高 **37 %**（0.0705 → 0.0967），而它看起来**依然像一个平板公式**。是第二条见证
> （位移拟合）给出 0.0701 才让它暴露。**一条见证只会"验证"错数字，两条才能发现错。**

### 5.8 CalculiX 的壳是"假壳"：方程数 ≈ 14.9 × 节点数，于是有一道机器内存墙

这一条不是 bug，是**选型要知道的账** —— 而且它直接决定了柱壳族尺寸维能往哪个方向走。

**现象**：`fuselage_barrel` 的两个尺寸外推点 `D2000×L3000`（233,815 节点）与
`D1600×L3000`（188,674 节点）求解直接失败，返回 `0xC0000005`（访问违例），日志停在
PaStiX 打完 `N / nnz` 那一行。同一族更小的点全部正常。

**先证伪「这是 `OUTPUT=3D` 的代价」**（这是最像的嫌疑 —— D8 的外纤维就是靠它拿的）。
把 deck 里 `*NODE FILE, OUTPUT=3D` 与 `*EL FILE, OUTPUT=3D` 都改回无 `OUTPUT=3D`，
其余一字不动，实测：

```
number of equations       3489495     <- 分毫不变
nnz (full)              194129961     <- 分毫不变
<job>.12d 字节数           68750934     <- 分毫不变
```

而 `.12d` 里躺着一大片 `is expanded into a "C3D8I L" element with topology:` ——
**壳展开是 CalculiX 的固有行为**（它先期把壳摊成实体再分解），`OUTPUT=3D` 只决定往 `.frd`
写什么。所以这条路上**没有便宜可捡**。（复现：`_probe_b6/out3d_off/`）

**账本**（三点实测，"方程数 / 节点数" 一致到 3 位有效数字）：

| case | 壳节点 | 方程数 | 结果 |
|---|---|---|---|
| 基线 d2000_l2000 t3 | 158,524 | 2,359,690 | ok |
| d2000_l2000 t2（同网格） | 158,548 | 同量级 | ok，249 s |
| d1600_l2000 | 128,058 | ~1.91 M | ok，156 s |
| d1600_l3000 | 188,674 | 2,816,466 | ✗ `0xC0000005` |
| d2000_l3000 | 233,815 | 3,489,495 | ✗ 提交内存耗尽 |

⇒ **方程数 ≈ 14.9 × 壳节点数**，而 **节点数 ≈ 壳面积 / 85.2 mm²**。

**「提交内存耗尽」是量出来的，不是猜的**：那台机器 `MemTotal 16491000 kB` +
`SwapTotal 16866936 kB` ≈ 33 GB 提交上限；ccx 咬满时**连 shell 自己的 `ls` 都 fork 不出来**，
stderr 报 `exit code 0xC000012D`（正是 `STATUS_COMMITMENT_LIMIT`）+
`fork: Resource temporarily unavailable`。

**这条账怎么用**：想只查规模不必跑完 —— 起 ccx、读到 `number of equations` 就 `taskkill`，
省十几分钟（`_probe_b6/nread/` 就是这么量出基线的 2,359,690）。给柱壳加尺寸时，
先按 `节点数 ≈ 面积 / 85.2` 估一遍，再决定这个点值不值得发。

**它改了口径（D27）**：尺寸维改成**只朝收缩方向**外推。柱壳基线自己（158,524 节点）已经
贴着这道墙，而**长度只放大 20 %** 就触墙（`d2000_l2400` 建出 188,555 节点，与实测失败的
188,674 几乎重合）。这**不破任何已注册判据** —— 锚点 `D2000×L2000×t3` 只采样一次，
「比锚点小」与「比锚点大」的外推含量相同，而 D25 只要求"偏离锚点"，从不规定方向。
缺口记进 `manifest.limitations`，而不是悄悄丢掉。

⚠️ 这道上限**不是常数**：机器在那次崩溃后把页面文件从 16.87 GB 自动扩到 24.98 GB。
上面记的是**当时**的实测值，扩容后未再复测放大方向。

---

## 6. 验证

### 6.1 独立验证①：`verify_cantilever.py`

用**同一条链路**（mesh → deck → ccx → post，含生产的节点过滤）算一个薄壁矩形盒悬臂梁，
和三样东西对：静力平衡（不依赖任何解析模型的不变量）、解析解（Euler-Bernoulli 与
Timoshenko）、网格敏感性。

### 6.2 独立验证②：`verify_solvers.py`

同一模型分别用 CalculiX 和 Abaqus 求解后交叉比对。这是对求解器适配层最硬的检查——
两个**互相独立**的代码在物理结果上一致，不可能用"我们自己的代码有 bug"来解释。

检查项与各自的证明力：

| 检查 | 证明什么 |
|---|---|
| 节点标签集合 | 两个求解器读到的是**同一张网格**；deck 写错一位就会炸 |
| 节点坐标 | ODB 用 32 位浮点存坐标，残差与 `float32(ccx 坐标)` 逐位比对，**解释掉**而不是忽略 |
| 单元数（从 ODB 读） | 整个网格在 deck 往返中存活 |
| 最大位移 | 主物理响应 |
| 静力平衡 | **唯一不依赖任何一方内部约定的检查**；Load 稀释 bug 就是它抓到的 |
| 应力场（逐节点，不只比峰值） | 两个代码算的是同一个物理量的话，整个场都得对上 |

**这一节里有两个「约定陷阱」，都是 M3/T2 踩出来的，现在写死在代码里：**

**① 两个求解器对「力」的定义不同**（`FORCE_CONVENTION`）。把它俩当同一个量，会让一个平衡到
1e-5 的模型报出 **100 % 平衡残差**：

| | ccx `FORC`（`*NODE FILE, F`） | Abaqus `RF` |
|---|---|---|
| 内容 | 节点**总外力** = 外载 + 反力 | **纯反力**（自由节点恒为 0） |
| 全模型求和 | **0**（自平衡） | **外载**（支撑撑住了全部） |
| 实测（同一 36 N 面压） | −0.00001 N | **+36.00000 N** |

两者只在「支撑集不承担外载」时相等 —— 翼盒（500 N 在自由翼尖）成立，**分布压力不成立**。
所以 `--reaction-set all` 时两码各自对自己的目标值：ccx → 0，Abaqus → 外载。

**② 「四边反力应相等」对加筋板是错的。** 长桁沿 y 跑，所以 x 边（横跨长桁）与 y 边
（顺着长桁、还收长桁端的剪力）是**不同的构件**，实测各 3.33 N vs 14.65 N。
正确的对称性陈述是**对边相等**（实测 x0/x1 差 0.077 %、y0/y1 差 0.055 %）。
原来比四边，报出 77 % 的"误差" —— 那是在要求正确的物理为假。

同一次还修掉了两个纯属我自己算错的：平衡检查用了**去角点**的边集（四个角点合计 −0.62 N，
和压力集总修正项同量级，符号与经典简支板的 `2Mxy` 角点力一致），以及把「外载」写成
`−q·A` 却拿去和 `+q·A` 的反力比。

**③ 最坏的一个不是算错，是印错：门禁输出了一个它没有量过的数字。**
「Abaqus 膜场恒为 0」时那条说明原本以
`... where the codes agree within 1.2 %.` 结尾 —— 那个 **1.2 % 是写死的字符串**。它对当初
写下它的那个算例成立，在平板上是**编的**（真实差 **62.0 %**）：

```
ccx 1.2135 MPa (mid-surface, shear-dominated) vs abaqus outer fibre 3.1952 MPa -> 62.0 % apart
```

门禁自己的输出里出现没量过的数，比门禁漏报更危险 —— 读到日志的人会以为这件事已经查过了。
现在改成**当场算出来再印**，措辞也一并改了：不再声称「外层纤维那个数是可比数」，而是明说
**纯弯曲模型上没有任何一个单独的应力数字是跨求解器可比的，除非先把应力定义定下来**（待决 D8）。

### 6.3 独立验证③：`verify_panel.py`（M3/T2）

平板族的独立线，对着**闭式解 + 不变量**跑，而不是对着自己的实现：

| 检查 | 口径 |
|---|---|
| Navier 双正弦级数解 | 四边简支矩形板均布载荷，**独立于本工程**；两个网格尺寸都要跑，误差必须随加密下降（否则"离散化"就成了借口） |
| 全局平衡 | 全模型 `Σ FORC_z ≈ 0` —— **不含任何集总模型**，是最干净的那条 |
| 支撑反力 | `Σ_held FORC + 支撑上的压力集总 = q·A`；集总项按 `q·A_elem/节点数` 由**网格预测**（占 1.8 %，是容差的 10 倍，不能省） |
| 载荷面积 | 由 deck 自己的**单元连接**积分 `length×width`；抓「长桁也被加压了」（会多 10 %，而任何位移检查都看不出来） |
| 对边反力对称 | 对边相等（见 §6.2 ②） |
| 加筋效果 | 加筋板必须显著更刚（实测 **62.8×**）；一根**脱粘**的长桁只给 ~1×，而且照样解得出 |
| **外纤维应力 vs 闭式** | D8 的机制在这里第一次对上**独立于它**的数：`6Mx/t²` 取自同一条双正弦级数，在**离板中心最近的那个节点**上比，实测差 **−0.22 %**（3 mm 归档网格，节点 13221 @ (298.62, 299.4, 0.0)） |

最后一条刻意**不取模型最大值**：模型最大值落在支承边的剪切边界层上，比闭式解高约 **12 %**
（3 mm 素板 2.9682 vs 2.6455 MPa）——那是离散化的真实特征，不是闭式解描述的那个弯曲应力。
拿它做判据，等于拿网格伪迹做判据。

### 6.4 独立验证⑤：`verify_hole.py`（M5/T4）

开孔板族的独立线，对着**闭式解 + 不变量**跑。闭式解有两级：Kirsch（无限板 `Kt=3`）与
Howland（有限宽修正 `Kt_net = 3 − 3.13λ + 3.66λ² − 1.53λ³`）。

| 检查 | 口径 |
|---|---|
| Kt vs Howland（gross / net 双口径） | **只对 Howland 断言**（容差 2 %）；Kirsch 3.0000 **仅作参考** —— λ=0.1 时两口径相差 11.1 %，拿无限板解当判据是拿口径当模型 |
| 峰值位置 | 必须落在载荷法向直径（θ=90 / 270°）；跑到别处说明载荷加错了轴，而任何幅值检查都看不出 |
| 孔边收敛 | 12→96 段扫描：Kt 在 2.97–3.04 之间**非单调** ⇒ 容差（2 %）必须大于这种散布 |
| λ 趋势 | λ = 0.1 / 0.2 / 0.3 的 gross Kt 必须**单调升** ——「命中一个值是运气，复现排序才是模型」 |
| 全节点平衡 | `Σ FORC_x`：加载端 +4000 N、固支端 −4000 N、全模型 ≈0（实测三处均 **0.0000 %**） |
| 双码 | **位移 1 % + 孔边逐节点 vM 中位差 5 %**（峰值照印不判，见 `FEM-Bench-Aero/README.md` §7.15） |

**低 λ 为什么停在 0.1**：孔小到孔边目标尺寸 `π·d/n` 低于尺寸场地板 `max(size_chord/6, 0.5)` mm 时
builder **直接 `raise`**（不静默粗化）。0.5 mm 是**绝对硬地板** ⇒ 族默认（n=72）下 `d > 15.279 mm`，
任何远场下 `d ≥ 11.46 mm`。λ=0.05（d=10 mm）在这个族里**永不可建** —— 这是规则，不是缺陷。
`check_forms :: T4.edge-floor-envelope` 用 0.98·d_min 必拒、1.15·d_min 必建来钉死它。

**尺寸不变性探针（`_probe_b7/b7_size_invariance.py`，M5/batch7 · D28）**：Howland Kt **只看 λ
不看绝对尺寸**，所以同 λ=0.1 的 `600x300_d30`（batch7 尺寸点）与 `400x200_d20`（基线）的 Kt
理论上必须相同——「解析标尺不随试件移动」是尺寸外推**唯一能实际失败**的比较（柱壳比值律的
开孔板类比）。实测同码 Kt_gross 差 **ccx 0.629 % / abaqus 1.539 %**（容差 2 %）；尺寸点对
Howland **ccx +0.182 %**。**abaqus 峰值对 Howland −2.98 % 只印不判**（D8/D23 纪律：峰值是
恢复统计量——基线自身就 −1.48 %，d30 孔边单元绝对尺寸更大 1.31 vs 0.87 mm、平均化路径读得更低；
载荷/面积若真错，位移差 0.094 % 会先报警）。判据落盘 `_probe_b7/_b7_size_invariance.json`。

### 6.5 独立验证⑥：`verify_multi_cell.py`（M5/T6）

多闭室翼盒的独立线，对着 **Bredt-Batho 多闭室扭转**跑。对 `n` 个闭室：
解 `M q = 2 G θ a`（`M[i][i] = ∮ᵢ ds/t`、`M[i][j] = −(共享壁长)/t`），`GJ = 4 G aᵀ M⁻¹ a`；
`n = 1` 退化为经典 `GJ = 4GA²/∮ds/t`。**4 条 case**（1 / 2 等 / 3 等 / 2 偏心）× ccx；
`--with-abaqus` 再加双码。实测 **20 PASS / 0 FAIL**。

| 检查 | 口径 |
|---|---|
| GJ vs Bredt-Batho | 容差 5 %（实测 +0.216 % … +1.083 %）。⚠️ 单闭室那条是**中性对照**：它必须等于经典 Bredt |
| 扭转率 `θ'` 的测法 | **不用 z 切片**：蒙皮是非结构四边形网格、节点不落 z 平面。改在**无肋肋间跨**（z 1100–1400，两端各 trim 20 %）做 6 参数刚性转动最小二乘（`u_x = a_x + b_x z − θ(z)(y−yc)`、`u_y = a_y + b_y z + θ(z)(x−xc)`、`θ(z)=t₀+t₁z`），`GJ = T/\|t₁\|` —— 翘曲纯轴向 ⇒ 无偏 |
| 逐闭室剪流 | 上蒙皮按弦向区间取各闭室 vM **中位数**，比 `√3·qᵢ/t`（容差 5 %，实测最大差 0.659 %）。⚠️ **必须用全分量 `post.von_mises`**：翼盒蒙皮在 x-z 面，面内剪力是全局 `sxz`，`von_mises_inplane`（为 x-y 平板写的）会丢掉它（读 0.05 MPa vs 真值 6.1408 MPa） |
| 腹板净流 | 腹板取「`E_WEBS` 减去两蒙皮」的**独占节点**，比 `\|q₁−q₂\|/q₁`（容差 5 %）——直接验「腹板在传多少剪」 |
| 闭室数效应（反面） | `GJ(2)/GJ(1)` 与 `GJ(3)/GJ(1)` 同时报**模型值**与**解析值**，并把解析增益（+0.42 % / +1.76 %）印出来当证据：**GJ 单独分不出闭室数** |
| 全节点平衡 | 纯扭矩 ⇒ 自平衡，判据 `\|ΣFORC\| / max\|F_node\| ≤ 1e-3`（不用绝对容差，实测 5.6e-06–2.2e-05） |
| 双码 | GJ 0.184 %、逐闭室剪流 0.029 %（容差 5 %） |

### 6.6 独立验证⑦：`verify_barrel_size.py`（M5/batch6）

柱壳族的尺寸/壁厚维外推（D25）不能只靠族默认那**一个点**的闭式解——尺寸外推研究的解析标尺
如果自己不动，就不是标尺。这条线把**退化柱壳**（无长桁无框——那里 `pR/t` 与 `pR²/(Et)` 才是
精确答案；发运件带 8 长桁 3 框，闭式解对它不精确）在**每个实际发运的尺寸点**上重算，
并额外验 **FE 比值 vs 闭式比值**：一个系统性尺寸错误（deck 里半径写错、厚度读错位置），
即使每个单点都过容差，也会在比值律上现形。实测 **16 PASS / 0 FAIL**（5 点 × 4 项），
比值律四点最大偏差 **0.671 %**（d1800 的 w）；retired 的 `d1600_l2000` 留在报告里当判决轨迹。

---

## 7. 实测结果

环境：Windows / Python 3.13 / gmsh 4.15.2 / **CalculiX 2.23**（`ccx_static.exe`，静态链接）
/ **Abaqus 2026**（`D:\Program Files\SIMULIA`）。

### 7.1 主算例 `python run_pipeline.py --demo`

NACA4412 翼盒，chord 1000 mm，span 2000 mm，5 翼肋，铝 2024-T3，翼尖集中力 500 N（+Y）。

| 阶段 | 实测 |
|---|---|
| 几何 | 21 个壳面；中面面积 2,376,450 mm² |
| 网格 | gmsh 出 5482 节点 / 5144 单元（全 quad4）→ 过滤 408 个孤儿节点后 **5074 活跃节点**；最小缩放雅可比 0.625（门禁 0.30） |
| 求解（CalculiX） | rc=0，3.4–4.2 s；最大位移 **2.3654 mm**，外纤维 vM **10.60 MPa**（中面 10.28） |
| 求解（Abaqus） | rc=0，19–27 s；最大位移 **2.3739 mm**，膜应力 8.45 MPa，外表面峰值 11.78 MPa |

### 7.2 交叉验证 `python verify_solvers.py`

```
1) 节点标签      : ccx 5074 vs abaqus 5074 -> IDENTICAL
2) 节点坐标      : max |Δ| = 5.859e-05 mm  -> float32-consistent
3) 单元数        : abaqus assembled 5144 elements {'S4': 5144}
4) max |u|       : ccx 2.36544 vs abaqus 2.37390 mm  -> diff 0.356 %
5) max |UZ|      : ccx 0.10967 vs abaqus 0.11005 mm  -> diff 0.344 %
6) 静力平衡      : ccx    RY -500.00242 N  -> 残差 0.000485 %
                   abaqus RY -500.00046 N  -> 残差 0.000091 %
7) 应力          : 主口径 = 外纤维（D8）；逐节点中位差 0.31 %，p90 33.90 %
VERDICT: PASS - 7 checks
```

**应力口径（D8 后）**：两条独立路线各出一个外纤维数，**每个数都带着自己的归约方式印出来**：

| 数 | 值 (MPa) | 归约方式 |
|---|---|---|
| ccx 外纤维 | **10.6048** | 展开壳（`OUTPUT=3D`）两层取最差，**逐节点平均** |
| ccx 中面 | 10.2824 | 两层**均值**——即历史归档值，保留备查，不作定尺数 |
| abaqus 外纤维（逐单元） | 11.7809 | `ELEMENT_NODAL` 外插后**单元内最大值** |
| abaqus 外纤维（逐节点） | 8.6879 | 同上，再**节点平均** |

同口径比（ccx 逐节点 10.6048 vs abaqus 逐节点 8.6879）差 **18.08 %**，这不是可用判据——
von Mises 峰值落在梁肋交汇的几何奇异点上，只由各家的平滑/外插选择主导，本身随网格变化。
所以本工程把**逐节点中位差**（0.31 %）作为应力判据，峰值只作报告。
**外纤维是中面以外的新通道**：`OUTPUT=2D` 时代它根本不在结果里，见 §5.1 与 §5.6。

### 7.3 参数化扫描 `--sweep "airfoil.n_ribs=3,5,7" "airfoil.chord=800,1000"`

**6/6 全部成功**，单构型 2.7–4.3 s。面数与翼肋数严格对应
（`4 × (n_ribs − 1) + n_ribs`：3 肋 → 11 面，5 肋 → 21 面，7 肋 → 31 面）。

| 构型 | 单元数 | 活跃节点 | 最小 J | 最大位移 (mm) | 最大 vM (MPa) |
|---|---|---|---|---|---|
| ribs 3 / chord 800 | 3696 | 3679 | 0.5950 | 4.5402 | 15.96 |
| ribs 3 / chord 1000 | 4690 | 4668 | 0.5965 | 2.3723 | 10.16 |
| ribs 5 / chord 800 | 4112 | 4057 | 0.5950 | 4.5267 | 15.76 |
| ribs 5 / chord 1000 | 5144 | 5074 | 0.6249 | 2.3654 | 10.28 |
| ribs 7 / chord 800 | 4445 | 4352 | 0.5099 | 4.5123 | 15.39 |
| ribs 7 / chord 1000 | 5711 | 5593 | 0.6083 | 2.3580 | 10.43 |

两条 `chord 800` 的网格在 **D10**（2026-10-03）后重建：原网格在**后梁腹板四角**留了
8 / 16 个三角，现由「非零则升 blossom 全四边形」自动清除（代价 +0.5 % / +4.8 % 单元）。
其余四条**一个字节没动**——这条边界由 `diagnostics/hash_manifest.py` 实测确认。
`vM` 列是 **D8 口径的外纤维**（逐节点），不是中面值。

读数：**翼肋数对整体弯曲刚度影响很小**（800 mm 弦长下 3→7 肋，位移只降 0.5 %），
符合预期——翼肋抗的是截面畸变，不是整体弯曲；**弦长**才是主导（800→1000 mm，位移降约 48 %）。

### 7.4 独立验证①：`python verify_cantilever.py`

薄壁盒悬臂梁 600 × 60 × 60 mm，t = 2 mm，F = 500 N，铝 2024-T3。

| 检查 | 实测 |
|---|---|
| 静力平衡（不依赖任何解析模型） | 固支端 ΣRz = **−500.0000 N** vs 施加 +500 N → **残差 0.00001 %** |
| 挠度 vs 解析 | FE 1.91029 mm vs Timoshenko 1.75547 mm → **+8.82 %** |
| 网格敏感性 | 粗 / 细网格差 **1.97 %** |
| **厚壁对照** | t = 6 mm → 偏差降到 **+0.80 %** |

怎么读：平衡残差 1e-5 说明**数值实现没有错**；8.8 % 的挠度偏差不是误差，是**物理**——
薄壁盒弯曲时横截面会畸变（截面变"扁"），壳模型能捕捉、梁理论天生不能。把壁厚 2 mm 加到 6 mm，
畸变被抑制，偏差随即落到 0.8 %。这一条正是"独立复算才算结论"的用法。

### 7.5 加长桁（`--stringers 3`）

```
python run_pipeline.py --demo --stringers 3 --solver ccx    --out outputs_str
python run_pipeline.py --demo --stringers 3 --solver abaqus --out outputs_str_abaqus
```

几何：69 个壳面（基线 21），中面面积 2,616,450 mm²（基线 2,376,450，**+10.1 %**）。
每侧蒙皮 3 条长桁 → 蒙皮被弦向切成 4 条带，长桁本身又被 3 道内翼肋切成 4 段/条。

| 算例 | 长桁 | 重组算法 | 单元 | 活跃节点 | minJ | max ǀuǀ (mm) | max vM (MPa) |
|---|---|---|---|---|---|---|---|
| 基线（§7.1） | 0 | 1 | 5144 | 5074 | 0.6249 | 2.3654 | 10.28 |
| **对照组** | 0 | 3 | 5351 | 5281 | 0.5725 | 2.3649 | 10.32 |
| **加长桁** | 3 | 3 | 7517 | 7387 | 0.5228 | **2.2194** | **9.83** |

对照组 = `--sweep "mesh.recombination_algorithm=3"`，即**同样的求网格策略、只是不加长桁**。

读法：

- **对照组 vs 基线只差 0.02 %**（2.3649 vs 2.3654 mm）——重组算法对响应几乎中性，
  所以"加长桁"这一列的差异可以干净地归因给长桁本身，不是网格换了带来的。
- **加长桁 → 挠度 −6.15 %、峰值 vM −4.7 %**。方向合理：长桁贴蒙皮承担轴向载荷，
  增大弯曲刚度与承力面积。对照 §7.3——翼肋几乎不影响整体弯曲，长桁则直接影响。
- 交叉验证（`--case naca4412_wingbox_str3`）：**7/7 PASS**——
  节点 7387 完全一致、坐标 float32 一致、max|u| 差 **0.277 %**、
  平衡残差 **0.000364 % / 0.000281 %**、逐节点应力中位差 **0.48 %**。

### 7.6 加筋平板壁板（M3/T2）

600×600×2 mm 铝板，四边简支（约束平动、转动自由），面压 q = 1e-4 MPa（总载荷 36 N），
**3 mm 网格**（D9 起；原 6 mm，理由见 §8）。

| 算例 | 长桁 | 单元 | 活跃节点 | minJ | max ǀuǀ (mm) | 外纤维 vM | 中面 vM |
|---|---|---|---|---|---|---|---|
| `stiffened_panel_600x600` | 0 | 46031 | 46432 | 0.6167 | 0.96175 | **2.9682** | 1.3590 ↑ |
| `stiffened_panel_600x600_str3` | 3 blade | 50976 | 51401 | 0.5367 | **0.01526** | **1.7744** | 1.7689 |

↑ **中面这个数是横向剪切，不是弯曲应力**（见下）。D8 之前**归档里只有它**，所以整个平板族的
"最大应力"曾经是一个与弯曲无关的数。

**独立验证线 `verify_panel.py` —— 13/13 PASS**（不变量跑在**族默认 3 mm** 网格上，即归档网格）：

```
D = 54689.0 N.mm | Navier w_max = 0.96268 mm (0.00406 q a^4/D, tabulated 0.00406)
素板 [coarse 6 mm]  11560 单元 minJ 0.604 | w_max 0.95658 mm -> -0.634 % vs Navier
素板 [fine   3 mm]  46031 单元 minJ 0.617 | w_max 0.96175 mm -> -0.097 % vs Navier
素板收敛      : |err| 0.634 % -> 0.097 %
invariants at 3 mm (family default = the archived mesh)
素板   载荷面积 360000.0000 mm^2（精确）  全局平衡 +0.000002 N -> 0.00001 %
       支撑反力 35.99985 / 36.00000 N -> 0.0004 %   对边对称 x 0.983 % / y 0.582 %
加筋板 载荷面积 360000.0000 mm^2（精确，长桁没被压：否则 +36000 mm^2 = +10 %）
       全局平衡 -0.000002 N -> 0.00001 %  支撑反力 35.99916 / 36.00000 N -> 0.0023 %
       对边对称 x 0.209 % / y 0.028 %   加筋效果 63.0x
       （单跨 150×600 板当刚性支承的参照值 0.01187 mm —— 只印，不作判据）
外纤维应力   6 Mx/t^2 = 2.64554 MPa；中心最近节点 13221 @ (298.62, 299.4, 0.0)
             实测 2.63984 -> -0.22 %
             （模型最大值 2.9682 落在支承边剪切边界层，比闭式高 +12.2 %，只作报告）
```

**收敛 + 闭式解夹逼**（3 mm 网格）：

| | max ǀuǀ (mm) | 相对 Navier |
|---|---|---|
| Navier 精确解 | 0.96268 | — |
| CalculiX | 0.96175 | **−0.097 %** |
| Abaqus | 0.96490 | **+0.230 %** |

两码分列真值两侧 —— 所以跨解算器那 0.326 % 是各自的离散化误差，不是谁错。
6 mm 下这个差是 0.800 %，**是网格限制不是公式分歧**（加密后降到 0.326 %，见 §8）。
三份日志都在数据集里，按角色分开：`gate3_panel.log`（**3 mm 归档**，2/2 PASS）、
`gate3_panel_coarse6mm.log`（被 D9 取代的 6 mm 那一版，留作物证）、
`gate3_panel_fine.log`（3 mm 收敛探针）。

**应力口径：平板把问题暴露得最干净。** 峰值节点的中面张量实测是
`(2e-05, 2e-05, 5e-05, 0.0, −0.19867, 0.67184)`：

- 面内分量是 **0** —— 对：线弹性平板纯弯**没有膜作用**，Abaqus 读出的中面场正好是 0.0，
  两码在这一点上**完全一致**。
- 中面的 1.36 MPa **100 % 来自横向剪切** `SYZ/SZX`，集中在简支边的边界层。
  这就是 D8 判"中面值不可用"的实测依据。
- **弯曲应力在外纤维**：解析 `6 Mx/t² = 2.6455 MPa`，FE 外纤维在中心处实测见上表；
  D8 之前 ccx 侧根本没有这个数（`OUTPUT=2D` 把它平均掉了）。
- 同一个"外纤维峰值"，三个归约方式给出三个不同的数（3 mm 素板，全部实测）：
  ccx 外纤维**逐节点** **2.9682**（模型最大，在支承边）、Abaqus **逐单元最大** **3.5066**、
  Abaqus **逐节点平均** **3.0742** MPa。它们互不相同，因为归约方式不同 ——
  **Abaqus 一家之内**，逐单元就比逐节点平均高 **14.1 %**；换成两码**同归约**（都取逐节点）
  还是差 **3.448 %**。这正是**不许裸比峰值**的原因，也是 D8 要求「每个数标注定义」的原因。
  （这三行与 §7.2 的翼盒表同源，全部由 `verify_solvers.py` 当场算出并落盘在
  `gate3_panel.log`。）

> ⚠️ 这里原先写的是「两码差 1.2 %」——那个数是 §6.2 ③ 里那条**写死的**说明串带出来的，
> 不是量出来的。已改成本文这组实测值，工具也改成当场计算。

**顺带否掉一个我自己的假设**：看到这个就想当然认为「ccx 的 von Mises 含剪切、Abaqus 的膜不含，
所以把 ccx 也削成面内就会更接近」。实测**相反**——翼盒上
`ccx 全量 vs Abaqus 膜 = 中位差 0.33 %`，而 `ccx 面内 vs Abaqus 膜 = 4.90 %`。
被数据否掉的假设无权去改一个已经验过 9 条算例的判据，所以**已登记的判据没动**，
面内值只作**报告**（`post.von_mises_inplane`）。

---

## 7.1 算法侧 baseline 结论（M13 · D36 复跑）

**主目标继续变好，应力侧的「可学」证据反而变弱了。** 翼盒弯曲挠度 `max_disp` test MAPE **2.63 %**（M3q，
同一个 6 条 test 集；相对本 test 集的 MAPE 最优常数地板 **5.3 %**）；两个 `vM` 目标**从 D35 的 4.68 / 5.29 %
退到 5.56 / 6.29 %**，对物理对手的配对差只剩 −1.0 / −2.4 pp 且 CI 跨 0。
完整表与机制分析见 `../FEM-Bench-Aero/BASELINE.md`。

**⚠️ 跨里程碑比 MAPE 必须先对齐 test 集。** D35 把 `sweep20_taper060` 换边到 train，test 从 7 条变 6 条 ——
总 MAPE、常数地板、"相对地板比"全都跟着变。D34 的 6.18 % 与 D35 的 3.01 % **只有在同一个 6 条 test 集上
对照**（4.97 % → 3.01 %）才是可比的结论。见 `_probe_m12/same_test_set.py`。
**D36 的 test 集与 D35 完全相同**（一条未动，只往 train 加了 `sweep35`），所以 `3.01 → 2.63`、
`4.26 → 7.46` 这类对照可以直接读，见 `_probe_m13/d36_ab.json`。

**⚠️ 只报 test 平均 MAPE 会把「5 条不动 + 1 条崩」讲成「整体变差」。** D36 的一切退化都来自
`sweep40_taper040` 这一条（`max_w` +13.91 → **+33.37 %**，vM +8.67/+9.10 → **+14.53/+14.21 %**），
另外 5 条变动分别 ≤ 1.39 / 0.48 / 0.63 pp。**test 只有 6 条时，逐条 APE 必须一起给。**

**⚠️ D34-b（仍生效，限定 D32）**：`val` 只有 7 条、其中 `sweep>0` 仅 1 条，**不足以选模型形式**。
D35 后 val 5.79 → 6.86 %（主目标）而 test 4.97 → 3.01 %；D36 后 val 6.86 → **6.30 %**、test 3.01 → **2.63 %**。
**D36 之后 4 个目标里只 2 个的 val 与 test 一致**（D35 时 3 个）—— 而且 `val` 上 M2X 只有 **3.33 %**（test 11.47 %），
比学习器好三倍。**形式决策用「留最高站位」LOO，档位决策仍用 val。**

**目标口径 = D32（2026-10-24 老王拍板）**：主 `max_disp`、副 `max_w`（**只报不判**），应力峰值不设为可学目标。

机械性结论（数字均可从 `baseline_d36_final.json` 读回）：
- **`max_disp` 就是弯曲挠度，`max_w` 是展向位移**（2026-10-24 更正，M9）。本 deck 的 z 轴是展向
  （0–2002 mm）、载荷是 `*CLOAD, DOF 2` = y，所以 `max_w = max|DISP[2]|` 是展向分量。
  实测 `max|v|/max_disp` = **0.99899–0.99973**（15 条，浮动 0.07 %）⇒ 不需要换目标。
- **`max_w` 的低误差是脆弱的，所以只当副指标。** D31 数据上它 4.17 % 低于 `max_disp` 7.96 %，
  真因是对 `sweep` 不敏感（`sweep40_taper040` 上 ×1.716 vs ×4.171，敏感度 41 %）；
  **统一下掉 `sweep40` 后 `max_disp` 3.82 % < `max_w` 4.48 %**。D33 补一个 train 点后它从 **4.17 % 翻到 8.33 %**
  （主目标只动 0.22 pp）—— 「低误差来自没学到」的指标不能拿来判模型。诊断：`_probe_m9/diag_w_vs_disp.py`。
- **★ D35 把 `planform_out` 修好，D36 把它压到「不再是主要矛盾」**：`sweep40_taper040` 单点
  15.19 % → −3.18 %（D35）→ **+1.09 %**（D36）。现在最大误差落在 **`webpos_new` 5.92 %**（M3q）
  与 **`section_new` 5.49 %** —— 两组的共同点是 **train 各只有 1 条锚点**，与 D35 之前的 `planform_out` 同型。
- **★ D36：按 D35 自己写的下一步补了 35° 站，代价也一起付了。** 主目标 3.01 → **2.63 %**、
  val 6.86 → 6.30 %、`planform_out` 3.18 → 1.09 %、train LOO 3.736 → 3.684；
  但 `max_w` test **4.26 → 7.46 %**（maxAPE 13.9 → **33.4**）、vM 中/外 **4.68 / 5.29 → 5.56 / 6.29 %**。
  **配对差 −0.38 pp、CI [−1.07, +0.01] 仍跨 0** ⇒ 只能说方向一致的改善。
  机制的准确表述：`s²` 只有一个自由度，修 `max_disp` 时把 `max_w`/vM 在同一考点顶过头（§BASELINE §2.7）。
- **★ D36 之后 `sweep` 这一轴应当停手。** 三轮各付一次代价（D34 换基 ①、D35 补交互 ②、D36 补中间站），
  每轮都是「修一头、从另一头付」。三次基已被两侧判据对撞否掉（LOO 赢 4.8 pp、考点输 15 pp），
  交互列已被 5.3 倍外推否掉。**再往这条轴上投样本或改形式，边际收益为零。**
- **★ D34：`sweep` 项必须是二次的，但只对 `max_disp`。** `LOO@30`（零泄漏）**−22.14 % → −1.07 %**、
  `val` 单点 `sweep40` `−34.54 % → −3.17 %`。同一改动在 `max_w` 上 test **8.33 → 13.49**、最大 APE **65 %**（崩）
  ⇒ 只在主目标采纳。**三次基在 D34 被否**：当时 train 里 `sweep>0` 仅 3 行且几何相同 ⇒ 3 点定 3 参数**恰好可逆**。
  **★ D36 之后这条理由已失效**（train 有 6 个正后掠行），所以重测（`_probe_m13/sweep_form_d36.py`）：
  cubic 在 LOO@35 上赢（−2.24 % vs quad −7.07 %），却把 `sweep40_taper040` 从 +1.09 打到 **+16.08 %**。
  **两侧判据互斥 ⇒ 仍不换**（因 test 好而选 quad 是 D32 禁止的选择偏置；同日又改数据又改形式 = 混叠）。
- **★ D35：补交互锚点，同时暴露一个必然折中。** 改 D15 二分 + 补 `sweep30_taper080` 后，
  test 4.97 → **3.01 %**、`sweep40_taper040` 15.19 → **−3.18 %**；但 **val 5.79 → 6.86 %**、
  **纯 sweep 外推点（`sweep40`）−3.17 → −12.79 %**、train LOO 2.14 → 3.74。
  一个 `s²` 系数要同时管「纯后掠曲率」与「后掠×锥度」，只能折中。
- **★ 交互特征不落地（D35 实测）**：显式加 `s²(taper−1)` 列后 `sweep40_taper040` 崩到 **−36.54 %**、
  test 8.50 %。交互列在 train 上最大 0.45，外推到 40°×0.4 是 −2.4 = **5.3 倍外推** ⇒
  **「样本可估」≠「可外推」**。
- **★ 数据缺陷（D34 顺带查出，D35 后仍在）**：`n_web` 与 `web_pos` 在 train 上**完全共线**（奇异值 1.3e-15，
  train 只有 1 条带腹板算例），`is_T` 恒为 0 ⇒ **10 个特征实际只有 8 个可辨识方向**。
  这解释了 M7「`n_web` 1→2 外推 +14.5 %，第二不稳轴」—— 那条路在 train 上根本没有信息。
  **算条件数必须先标准化并按秩剔除，否则会得出「现有 M3 不可辨识」的错误结论**（本轮真踩过）。
- **跨目标比 MAPE 必须下掉同一条样本**：各目标剔各自最差会得出相反结论（各自剔 `max_w` 2.15 % 赢，
  统一下掉 `sweep40` 则 `max_disp` 3.82 % 赢）。
- **峰值是离散选择不是光滑函数**：`max_disp` 的 argmax 在 33 条里落在 **21 个不同节点**
  （`max_disp_node 21/33 distinct`，最多的是 node 495 出现 7 次 —— 正是本算例 abaqus 侧的峰值位置），
  所以任何光滑代理都拟合不了峰值的抖动。

## 8. 已知限制

- 几何是**薄壁壳（中面）**，不是实体。长桁截面已有 **blade / T** 两种，但没做帽型、没做端部削尖；
  没做接触；复材已由 T7 打样落地（CLT 等效单层，D29）。
- **网格已全四边形（D10，2026-10-03 修复）。** 关 1 的「零 tri3」在 M1–M3 期间**只写在话术里、
  从未被量过**：`meshing.py` 只查 minJ 与单元数。实测归档（`diagnostics/msh_quality.py --tree
  FEM-Bench-Aero/modeling`，以及 `diagnostics/tri3_map.py` 定位）发现两条 `chord=800` 盒段含
  **8 / 16 个 S3**，全部落在**后梁腹板四角**。早先记的「abaqus ODB 里的 S3R 是**两码读法不同**」
  **已证伪**——归档 `.msh` 与两棵树各自的 `model.inp` 里数字完全相同，是网格本身如此。
  **老王拍板 D10：能做到零就加约束**；已按「先建后数、非零则升 blossom 全四边形」实现
  （§5.5 第二道自适应），两条算例已重跑重导，`tri3 = 0` 同时成为关 1 判据与
  `verify_dataset.py` 的硬闸。D10 修复时 **11/11 零三角**，最差 minJ **0.5099**
  （`n_ribs7_chord800`）；**当前全树 40/40 零三角（全 quad4）**，最差 **0.4636**
  （`fuselage_barrel_d1600_l1600_str8_frm3`，2026-10-07）、最好 **0.6562**
  （`open_hole_panel_400x200_d20_offcentre`，2026-10-06）。
- **这一条修复有意动了两条归档算例。** 其余 9 条种子网格逐字节不变，但
  `regress_groups.py` 的指纹含 `n_elements`/`min_quality`/`element_types`，所以
  9 条种子的 M2 回归由 **9/9 → 7/9**，基线已重签（旧基线留档为
  `regress_baseline_groups_pre_d10.json`）。这不是静默漂移：两条的网格变化是本次变更的**目的**，
  且被 §5.5 的实测表逐项记账。
- 结构族有四个：**翼盒（等直 / 后掠 / 锥形 NACA4412，M5/T6 起含多闭室）**、
  **加筋平板壁板（矩形）**、**机身加筋柱壳段**（M5/T3：薄壁圆筒 + 周向均布 blade 长桁 + 环向框，
  多载荷组合）与 **开孔平板**（M5/T4：矩形光板单面挖圆孔，全库唯一有闭式解 Kt 的一族）。
  七种结构形式 T1–T7 **全部落地**——T7 复材走**架构 B 等效单层**（2026-10-11 老王拍板，D29）：
  CLT 均匀化为等效正交异性单层（`feagpt/laminate.py`，S4 不动），打样 1 条入库（41 条/树）；
  铺层族与厚度维待放量，层间/逐层应力不在数据集内。
- 柱壳的两条边界（**D19 / D22**）：长桁数只接受 `{0} ∪ [5, ∞)`（1–4 根会在框外弧留 16–22 个三角，
  五种修法实测全否）；长桁截面**只接受 `blade`**（T 截面建面器未做，拒绝而非静默降级成 blade）。
- 柱壳双码 max|u| 走 **D20** 口径（剔除端载环的结构峰值 + 沿轴剖面），不再是模型全域 max|u|。
- `pressure` 载荷沿壳法向，方向取决于单元定向 —— 且**柱壳蒙皮是回转面，法向与拉伸出来的翼盒/平板相反**，
  所以方向由族声明（`pressure_dload_sign`，D21），不再是 deck 里的硬编码。
- 长桁参数只有 `n_stringers(_per_skin) / stringer_height / stringer_thickness / stringer_kind /
  stringer_flange_width`，站位是等分，尚未做非等距布置或避开检修口。
- `pressure` 载荷沿壳法向，方向取决于单元定向；翼盒 demo 默认用**翼尖集中力**（方向明确），
  平板族**只用**面压（声明里没有可挂集中力的节点组，遇到会直接报错）。
- **`max von Mises` 在换求解器时会换数，不能直接拿来算裕度** —— 2026-10-03 的 **D8 已拍板**：
  归档口径 = **外表面峰值**，中面值弃用，且**两个求解器都要出外纤维**。
  - ccx 侧原来拿不到外纤维（`OUTPUT=2D` 报两层均值，纯弯板上恒为 0），现在走
    `*FILE, OUTPUT=3D` + `post.collapse_expanded_shell` 折回中面，外纤维留在
    `STRESS_PEAK`（§5.7）。
  - 两棵树现在**同名同定义**：`scalars.max_von_mises` = 外纤维，
    中面值另存 `max_von_mises_midsurface`，并带 `max_von_mises_definition: "outer fibre"`。
    原来「下游按同名取数会得出 Abaqus 侧零应力」的坑已经堵上；
    `verify_dataset.py` 现在把「定义存在且是 outer fibre」当**硬闸**，两棵树定义不一致直接 FAIL。
  - **归约方式仍是两码各自的选择**，所以峰值**跨码不可裸比**。实测（`odb.json` 的
    `stress_candidates_max_vm` 与折回后的 `STRESS_PEAK`），翼盒基线上：

    | 归约 | ccx | Abaqus | 说明 |
    |---|---|---|---|
    | 膜（逐节点平均） | 10.2824 ² | 8.4541 | Abaqus 侧 `membrane_node_averaged`，**它才是对应 ccx `OUTPUT=2D` 的量** |
    | 外纤维逐节点平均 | **10.6048** ← **归档** | 8.6879 | Abaqus 侧 `outer_fibre_node_averaged` |
    | 外纤维逐单元最大 | 取不到 ³ | **11.7809** ← **归档** | Abaqus 侧 `outer_fibre_elementwise_max`，来自 `STRESS_PEAK` |

    ² 翼盒的 `OUTPUT=2D` 值（10.2824）离外纤维只差 3 %，因为盒段蒙皮本身承担轴向
    （有膜作用）；**纯弯平板**上同一口径直接掉到 0（§7.6），那才是 D8 的原始触发场景。
    ³ FRD 的应力本来就是**逐节点**的（节点外推 + 共享节点平均），`OUTPUT=3D` 只是多给
    一个外表面层；**逐单元不做平均**的值 ccx 这条路径拿不到。所以两棵树**同名同定义
    （都是「外表面峰值」），但归约不同**——这正是 D8 要求的「每个数标注定义」要挡住的坑。

  - 两个归档值口径不同，**不能直接相减**：ccx 10.6048 vs Abaqus 逐单元 11.7809 差 **+11.1 %**，
    但那是「逐节点 vs 逐单元」造成的。换成**同归约**（都用逐节点平均）比，翼盒上是 **18.08 %**——
    而那落在梁肋交汇的**几何奇异点**上（单元 776），加密会继续变。所以
    **关 3 的应力判据从来不是峰值，而是逐节点中位差 0.31 %**。
- **平板族默认网格 6 → 3 mm（D9 已拍板）**。原 6 mm 下无长桁素板的关 3 余量只有 0.800 %
  （容差 1 %，其余 10 条都在 0.03–0.46 %），已证明是离散化；3 mm 降到 **0.326 %**，
  且解析解 0.96268 被两码夹住（ccx −0.097 % / abaqus +0.230 %）。
  **容差 1 % 没有放宽** —— 一不方便就放宽的闸就不是闸。代价是节点数 ×3.95。
- **两个求解器对「力」的定义不同**（ccx 总外力 vs Abaqus 纯反力，§6.2 ①）。分布载荷下
  全模型求和一为 0、一为外载，写检查时必须按码取目标值。
- Abaqus 分支**未做**：实体单元、接触、几何非线性（NLGEOM）、多步/多帧提取
  （当前只取最后一步最后一帧）。
- 单构型串行跑；批量靠 `run_batch` 循环，没有并行调度。
- 结果提取只到"峰值 + 逐节点"，没做插值到参考网格 / 场量对齐（那是 ML 数据集化下一步）。

---

## 9. 目录

```
feagpt/
  spec.py          # FEASpec —— 阶段间唯一契约（JSON）；StructureSpec 选结构族
  planning.py      # 自然语言 → FEASpec（规则版，LLM 挂载点已留）
  naca.py          # NACA 4 位翼型坐标
  geometry.py      # 结构族注册表 BUILDERS + 翼盒 builder + 平板 builder + 柱壳 builder（建面打标分类器）
  panel.py         # 加筋平板族：参数块 + 站位 + 支承规则 + 唯一 spec 工厂 make_spec()
  fuselage.py      # 机身柱壳族（M5/T3）：参数块 + 长桁角/框站位 + 包络拒绝（D19 长桁数 / D22 截面）+ make_spec()
  sections.py      # 长桁截面族：blade / T（T 且翼缘宽≤0 退化成 blade）
  meshing.py       # 曲率自适应网格 + 质量门禁 + 节点过滤
  inp_writer.py    # 双方言 deck 生成（ccx / abaqus），厚度/DOF/压力组按族声明
  solver.py        # 求解器适配层（ccx / abaqus，含 ODB→JSON 转换）
  abaqus_odb.py    # ODB 提取器，由 `abaqus python` 执行
  post.py          # 结果归纳（求解器无关）；含 collapse_expanded_shell（D8 展开壳折回中面）
                   #   + von_mises_inplane（诊断用）
  topology.py      # 语义真值：design/geometry 双读数 + 派生预期 + 关 4 比较器（按族分发）
  manifest.py      # ★ M4/M5 规则层：等价类（白/黑名单双推导）+ 角色 + 声明式留出区域 HOLDOUT_REGIONS
  pipeline.py      # 五阶段编排

run_pipeline.py        # CLI 入口
verify_cantilever.py   # 独立验证①：解析解 + 平衡 + 网格敏感性
verify_solvers.py      # 独立验证②：双求解器交叉验证（含 FORCE_CONVENTION、应力定义标注）
verify_panel.py        # 独立验证③：平板 Navier 闭式解 + 载荷/平衡/对称不变量 + 外纤维应力（M3/T2）
verify_barrel.py       # 独立验证④：柱壳环向膜应力 / 自由径向膨胀 / 梁弯应力 / 平衡 / D20 双码（M5/T3）
verify_hole.py         # 独立验证⑤：开孔板 Kirsch / Howland Kt + 孔边收敛 + 平衡 + λ 趋势 + 双码（M5/T4）
verify_multi_cell.py   # 独立验证⑥：多闭室翼盒 Bredt-Batho GJ + 逐闭室剪流 + 闭室数效应 + 双码（M5/T6）
verify_barrel_size.py  # 独立验证⑦：柱壳逐尺寸薄壁闭式解 + FE/闭式比值律（M5/batch6）
make_dataset.py        # 已有算例 → 数据集 case（补 .msh + truth.json，不重跑求解）
rerun_solver.py        # ★ 就地重跑归档算例（改了 deck 或网格才需要，D8/D9 用；带 --panel-mesh）
resummarize.py         # ★ 只从盘上 FRD/ODB-JSON 重推 results.json（改归约、不改求解，不花许可）
check_semantics.py     # 关 4 语义复核（从 truth.json 重算，不信存值）
verify_dataset.py      # 数据集验收：自洽性 + 跨树配对 + 树内去重 + 应力定义 + 零三角（硬闸）
dedup_dataset.py       # 剔除同树内重复模型（默认 dry-run，--apply 才删；history 累积不覆盖）
regress_groups.py      # M2 分组回归：逐面 bbox 指纹，改分类器后必须逐位一致
check_forms.py         # M3 退化自检：T5（翼缘宽→0）+ T2（长桁数→0）
make_manifest.py       # ★ M4：生成 manifest.json + MANIFEST.md（清单/索引；确定性，无时间戳）
eval_dataset.py        # ★ M4：独立复算 manifest 的每一处声明 + 5 道集级闸（含等价类泄漏闸）
diagnostics/           # 探针 + 由 `abaqus python` 执行的 ODB 结构探针
  inspect_odb.py       #   列出 instance/单元类型/step/frame/field 及分量标签
  stress_convention.py #   导出自上/下表面/中面的逐节点 von Mises
  stringer_quality.py  #   逐个几何组统计单元数/单元类型/最差雅可比（定位坏单元）
  fragment_map_probe.py#   观察 occ.fragment 的 outDimTagsMap 语义（M2 用）
  panel_bond_probe.py  #   平板蒙皮与长桁条能不能被布尔粘上（M3/T2 决策探针）
  panel_convergence.py #   平板 FE vs Navier 的网格收敛 + 软支承消融（M3/T2）
  t_stringer_probe.py  #   T 形为什么是 3 个面（M3/T5）
  forc_audit.py        #   FORC/RF 到底是什么量（用翼盒锚定，M3/T2）
  shell_stress_definition.py # OUTPUT=2D vs 展开后 的应力定义差异（M3/T2）
  probe_d8_outer_fibre.py #  ★ 外纤维 vs Navier 闭式 + 位移拟合双见证（D8）
  msh_quality.py       #  ★ 从**归档 .msh** 读回 minJ/单元类型（关 1 的证据，不靠重建）
  tri3_map.py          #  ★ 三角长在哪个面上、该面多窄（D10 定位：24 个全在后梁腹板四角）
  probe_tri3.py        #  ★ 五种 gmsh 配置逐个量：哪种清三角、代价多少（D10 选型）
  hash_manifest.py     #   全树哈希快照/比对——「没有静默漂移」的证据（M3/T2）
```

---

## 10. 导出数据集（M1 建，M2 整）

`make_dataset.py` 把已有算例重导为**规范 case 目录**，供 `FEM-Bench-Aero` 建模集使用。
**不重跑任何求解**——网格是确定性的，重建出的活跃节点数与归档 FRD 逐条一致。

```
<root>/modeling/<case_id>/   发布物：CalculiX（开源）+ 真值
<root>/_xval/<case_id>/      内部：Abaqus 交叉验证证据（商业许可，禁止发布）
```

一个 case 六件套：`spec.json` / `model.step` / `model.msh` / `model.inp` /
`model.results.json` / `truth.json`。导出的 `spec.json` 是**重新序列化的规范形**
（不是源文件逐字节拷贝），所以 M1 时代手写缺字段的 spec 会被补齐、两棵树归一。

**两道独立闸（抓不同的错）**：

| 闸 | 比什么 | 抓什么错 |
|---|---|---|
| 关 4 语义（`check_semantics.py`） | 由 spec 派生的应有几何计数 vs gmsh 实测计数 | 模型**建错**（如肋数不对）但数值门禁全过 |
| 结果–网格同源（`make_dataset.py` 内建） | 重建网格活跃节点数 vs 归档 `results.json.n_nodes` | spec 与结果**不同源**（字段语义过期） |
| 退化自检（`check_forms.py`） | 新形式参数取退化值后，逐面 bbox 指纹 vs 旧形式 | 新参数**根本没接上**（扫描出来全一个数），却一路过闸 |

关 4 只看几何自洽，**看不见**「新网格 + 旧结果」这种错配——所以两道闸都要有。
而**退化自检**是第三种错：模型对、结果对、门禁全过，但新加的参数是个空转字段。
它比关 4 更早发现这类问题，因为退化值本来就不该改动任何东西。

**去重口径**：`verify_dataset.py` 用 `model.msh` 哈希作模型指纹，**只在同一棵树内**判重复
（跨树同哈希是交叉验证的前提，不是重复）。M2 起这是**硬闸**（重复即判 CHECK），
清理用 `dedup_dataset.py`（默认 dry-run）。当前 **40 条/树、0 重复**。

> ⚠️ **重导后必须跟一次去重**：源目录 `outputs/` 保留着重合的 `..._n_ribs5_chord1000`
> （provenance 不动），所以 `make_dataset.py` 会把它重新导进来。顺序是
> **`make_dataset.py` → `dedup_dataset.py --apply`**；漏了的话 `verify_dataset.py` 会判 CHECK。
> M3/T2 又踩了一次，而且这次**多导进来两条探针目录**
> （`stiffened_panel_600x600_s0` / `_s3`，`.msh` 与描述性命名的两条**逐字节相同**）——
> 源目录里临时跑出来的算例要先迁到 `_superseded/` 再重导，否则去重闸会连着报两条。

**M2 重导结果**：全 18 条 case 的 `model.msh` / `model.inp` / `model.step` /
`model.results.json` **逐字节未变**（快照比对见 `m1_to_m2_hash_snapshot.json`），
只有 `spec.json`（多出 `structure` 块）与 `truth.json`（族标签 + spec 哈希）更新。

**M3/T5 入库结果**：加入 `naca4412_wingbox_str3_T`，两棵树 8 → 9 条；
去重后关 3 **9/9**、关 4 **18/18**、自洽 **18/18**、退化自检 **4/4**、
9 条种子分组回归 **9/9 逐位一致**（blade 路径一个字节都没动）。

**M3/T2 入库结果**：加入 `stiffened_panel_600x600`（无长桁）与
`stiffened_panel_600x600_str3`（3 根 blade 长桁），两棵树 9 → **11 条**；
关 4 **22/22 PASS**（翼盒 8 项／平板 4 项，两棵树各一遍）、
`verify_dataset.py` 自洽 **22/22 OK**、跨树网格 **11/11 一致**、树内重复 **0**、
退化自检 **8/8 PASS**（T2 4/4 + T5 4/4）、9 条种子分组回归 **9/9 逐位一致**。

随库留下三份平板关 3 日志，**按角色分开**：`gate3_panel_coarse6mm.log`（被 D9 取代的 6 mm 两条算例）、
`gate3_panel_fine.log`（素板 3 mm —— 证明 0.800 % 是离散化的**唯一依据**，必须落盘，不能只留在会话里）、
`gate3_panel.log`（**3 mm 归档**，2/2 PASS）。

**D8 / D9 重导结果（2026-10-03）**：ccx 侧 11 条全部重解重导；Abaqus 侧 9 条翼盒只重归纳
（`resummarize.py`，**不花许可**）+ 2 条平板重解重导。两棵树都回到 11 条（导出会把源目录里的
重复件带回来，所以重导**必须**跟一次 `dedup_dataset.py --apply`）。

- 对面 `_snap_abq_before.json`：**0 added / 0 removed / 30 changed**，**全部落在 `_xval/`**，
  `modeling/` **零变更**（9 翼盒 ×「结果 + 真值」；2 平板 × 整 6 卡）。
- 对面 `_snap_d8_before.json`（D8 前，全量）：**78 changed** = 13×`model.inp`
  （ccx 11 条加了 `*FILE, OUTPUT=3D`，加 Abaqus 2 条平板换了网格）、
  4×`model.msh`（**只有那两条平板**）、4×`spec.json`、22×`results.json`、22×`truth.json`、
  13×`model.step`（几何没变，变的是**文件头时间戳**）。
- **翼盒 `model.msh` 一个字节没动 ⇒ M2 那条「9 条种子逐字节不变」的硬闸活着。**

**D10 重跑重导结果（2026-10-03，同日第三轮）**：只动了两条 `chord800` 的网格 ——
它们原在后梁腹板四角各留一个三角（两树合计 24 个）。两条 ccx + 两条 abaqus 重解，
两棵树重导，再跑一次 `dedup_dataset.py --apply`。

- 对面 `_snap_abq_before.json`：**0 added / 0 removed / 46 changed**（132 文件）；
  按目录 `_xval 36 / modeling 10` —— **`modeling/` 那 10 处正是两条 chord800 × 5 个文件**
  （inp / msh / results / step / truth），其余 9 条 ccx 归档**一个字节没动**。
- 两条重解后**零三角**，`verify_solvers` 各 **PASS - 7 checks**：
  `ribs3_chord800` max|u| 差 0.224 %、逐节点中位差 0.12 %；`ribs5_chord800` 0.355 % / 0.25 %。
  验收：关 4 **22/22**、自洽 **22/22 OK**（含新第 8 项 `no_tri3`）、跨树网格 **11/11 一致**、
  关 3 翼盒 **9/9**、退化自检 **8/8**、树内重复 **0**。
- **分组回归如实报 7/9**：指纹含单元数与质量，两条 DIFF **只差 `mesh` 块** ——
  `counts` / `topology_geometry` / `groups` 全部 SAME，说明**几何分组零扰动**。
  **基线已重签**（复验 **9/9 PASS**），旧基线留档 `regress_baseline_groups_pre_d10.json`，
  7/9 的原始输出留档 `regress_groups_d10_before_resign.log`。

### 10.1 「没动归档」这件事要能被验证，而不是被相信

`inp_writer` / `pipeline` 为了支持第二结构族做了重构（BC 节点、厚度表、约束自由度、
压力作用组全部改成 builder 声明）。重构前后的正确断言不是「大概没影响」，而是
**一条老算例的字节都不许变**。`diagnostics/hash_manifest.py` 就是干这个的：

```
cd feagpt_repro
python diagnostics/hash_manifest.py write FEM-Bench-Aero/snap_before.json   # 动手前
#   ... 重构 + 重新导库 ...
python diagnostics/hash_manifest.py diff  snap_before.json FEM-Bench-Aero \
       --only modeling --only _xval --gate changed        # 只看算例，0 变更为通过
```

实测（快照 = T5 后 / T2 前的 116 文件全树）：

```
$ python diagnostics/hash_manifest.py diff ../_snap_before.json ../FEM-Bench-Aero --quiet
26 added, 0 removed, 5 changed (116 -> 142 files)
  added,   by directory: (tree root) 2, _xval 12, modeling 12
  changed, by directory: (tree root) 5
  changed, by file name: 1x README.md, 1x dedup_report.json, 1x gate3_panel.log, 1x gate4.json, 1x verify_report.json

$ python diagnostics/hash_manifest.py diff ../_snap_before.json ../FEM-Bench-Aero \
         --only modeling --only _xval --gate changed --quiet
24 added, 0 removed, 0 changed (108 -> 132 files)     # exit 0
```

读法：**108 个已归档模型文件，0 个变更**；新增的 24 个正好是 2 条新算例 ×6 文件 ×2 树；
全树视图里那 5 个 changed 全部落在**树根的报告文件**上（README / 去重报告 / 两道门禁日志），
一个都没有落进 `modeling/` 或 `_xval/`。`--gate changed` 让这件事有个退出码，
而不是靠人数 5 行输出。**重构对老算例是字节级中性的——这条现在是可复跑的，不是口头保证。**

> 诚实说明：`gate3_panel.log` 之所以在 changed 里，是因为 §6.2 ③ 那个「印了没量过的数」的缺陷
> 修完之后，我把平板日志**重新生成**了一遍。这正是这个视图的用处——它不会让你**忘记**自己动过什么。

> `--gate any`（默认）会在有任何增/删/改时退出 1，适合「本应完全不动」的重构；
> `--gate changed` 只对**幸存文件的字节变化**报警，增删只作报告——适合「加了新算例、
> 但不许碰老的」这种场景。`--only` 是作用域选择器，对两份快照同时生效。

---

## 11. 判定 / 索引 / 划分（M4）

`truth.json` 回答的是「**这一条**建得对不对」。M4 回答的是只有**跨 case** 才成立的问题：
哪些 case 是同一个模型、每条是干什么用的、谁进 train/val/test。三件产物，规则与执行分开：

| 产物 | 位置 | 干什么 |
|---|---|---|
| `feagpt/manifest.py` | 代码 | **规则层**：等价类、角色、划分表 |
| `make_manifest.py` | 代码 | 生成 `manifest.json`（机器读）+ `MANIFEST.md`（人读索引） |
| `eval_dataset.py` | 代码 | **独立复算** manifest 的每一处声明 + 5 道集级闸（带退出码） |
| `manifest.json` / `MANIFEST.md` / `eval_report.json` | `FEM-Bench-Aero/` | 产物：清单 / 索引 / 校验报告 |

```
cd feagpt_repro
python make_manifest.py --root ../FEM-Bench-Aero \
       --json ../FEM-Bench-Aero/manifest.json --md ../FEM-Bench-Aero/MANIFEST.md
python eval_dataset.py  --root ../FEM-Bench-Aero --json ../FEM-Bench-Aero/eval_report.json
```

### 11.1 等价类：什么叫「同一个模型」

划分的**单元是等价类，不是单条 case**。同一个模型的两条 case 若被分到 train 和 test 两边，
就是把答案递给了模型 —— 而**所有数值门禁一条都不会报警**。这是 M4 存在的首要理由。

等价类用**白名单**定义：结构族 + 几何 + 壁厚。明确排除 `mesh`（网格尺寸/算法）、`load`、
`bc`、`analysis`、`name`。理由是这些字段描述的是**怎么算**，不是**算什么**：同一条 case
换个网格尺寸不是另一个零件。而**壁厚算几何**，即使它不改变曲面 —— 两个只在蒙皮厚度上不同的
盒段是不同的零件，它们的 `model.msh` 却可能逐字节相同（去重闸看不见这个差别，只能用等价类看）。

两条互补规则各推一遍，**必须得到同一个划分**：

| 推导 | 规则 | 作用 |
|---|---|---|
| `geometry_class` | 白名单：只取几何字段 | 主口径。spec 以后长出新字段（求解器选项、报告开关）默认**不算**几何，不会把类打散 |
| `geometry_class_complement` | 黑名单：去掉一切「处理类」字段 | 交叉校验。两者划分不一致 ⇒ 某个字段的归属错了 |

同类成员还额外要求 `truth.json` 的 `design` 与几何读数**完全一致** —— 这是**跨文件佐证**：
类是从 `spec.json` 推出来的，这条要求它和几何构建实测对得上。

实测：**11 条 → 10 类**。唯一的多成员类是 `naca4412_wingbox` 与它自己的网格算法对照
（`..._recombination_algorithm3`，只差 `mesh.recombination_algorithm`）—— 两条只能同集。

### 11.2 角色：每条 case 是干什么用的

`infer_role` 是**有序判定**，第一条命中即返回。顺序本身是有意义的：

| 角色 | 判据 | 为什么单独拎出来 |
|---|---|---|
| `ablation` | `mesh.recombination_algorithm != 0` | 它研究的是**网格**不是结构；必须和它消融的几何待在同一集 |
| `degenerate` | 平板族且无长桁 | 退化成有闭式解（Navier）的光板 —— 和「扫描上的一个点」不是一回事 |
| `feature` | 有长桁 / 引入新截面 | bench 要考的泛化目标 |
| `baseline` | 族默认参数（各族的**中性值**都在 `manifest.py` 里显式声明：翼盒 5 肋/1000 弦、柱壳 8str/3frm、开孔板 λ=0.1 居中） | 所有定性的参照 |
| `sweep` | 其余 | 参数扫描点 |

`ablation` 排在最前：一条钉了网格算法的 case 是**网格实验**，叫成别的名字就会藏掉那个唯一
决定它该在哪边的性质。实测 `baseline 1 / ablation 1 / sweep 5 / feature 3 / degenerate 1`。

### 11.3 划分：声明式留出区域（M5 起由规则取代显式表）

M4 用的是一张**显式表**（case → split + 一句理由）：11 条样本下，划分是「模型该泛化到什么
形式」的判断，显式表是唯一能在看板上被逐行审阅的形状。到 200 条它就不 scale 了，所以 **M5
换成规则**。

**规则 = 每族声明「留出区域」**（`feagpt/manifest.py :: HOLDOUT_REGIONS`，声明）+ 一个
**首个命中即定、未命中默认 `train`** 的机制（`split_of(spec)`，代码）：

| 族 | 顺序 | 谓词 | → | 说明 |
|---|---|---|---|---|
| wingbox | 1 | 后掠 > 0 **且** 锥度 ≠ 1（D15） | **test** | 两个平面形状自由度同时动 = 新平面形状 |
| wingbox | 2 | 含长桁且截面形式 ∉ `FORMS_ANCHORED_IN_TRAIN`（blade） | **test** | 新截面形式 |
| wingbox | 3 | 肋 > 默认(5) **且** 弦 ≠ 默认(1000) | **test** | 双维外推 |
| wingbox | 4 | 腹板 > 1 **且** 偏离等分（D24） | **test** | 腹板数 × 位置双维（`_wingbox_web_double_extrapolation`，先于 offcentre——两者对偏心案一致，但双维语义更准） |
| wingbox | 5 | 有腹板且偏离等分（D24） | **test** | 新形式：闭室不等面积，Bredt-Batho 不再描述该截面 |
| wingbox | 6 | 腹板 > 1 且位置仍等分（D24） | **val** | 腹板数单维外推（肋规则的直接类比） |
| wingbox | 7 | 平面形状单维外推：后掠 > 20° 或 锥度 < 0.6（D16） | **val** | 平面形状维单维外推 |
| wingbox | 8 | 肋 > 默认(5) | **val** | 单维外推 |
| stiffened_panel | 1 | `(L,W) ≠ (600,600)`（D16 路 A：**任何**新尺寸，不限光板） | **val** | 尺寸维单维外推 |
| stiffened_panel | 2 | 长桁数 > 0 | **test** | 族内新形式 |
| fuselage_barrel | 1 | 长桁截面形式 ∉ train 已锚定（D18） | **test** | 新截面形式（今日无匹配 —— blade 已锚定） |
| fuselage_barrel | 2 | 长桁 > 8 **且** 框 > 3（D18） | **test** | 双维外推 |
| fuselage_barrel | 3 | 尺寸·壁厚 **≥2 维**同时 ≠ 精确锚点 `D2000×L2000×t3`（D25，含连续 × 计数组合） | **test** | 连续量双维外推 |
| fuselage_barrel | 4 | 长桁 或 框**之一**越界（D18） | **val** | 柱壳版 ribs 规则：单维外推 |
| fuselage_barrel | 5 | 尺寸·壁厚**单维**外推：直径 / 长度 / 壳厚之一 ≠ 锚点（D25） | **val** | 尺寸维单维外推 |
| open_hole_panel | 1 | 孔心偏离形心（D23） | **test** | 孔位置 = 离散形式轴：偏心即 test、任何 λ（Howland 只描述中心孔） |
| open_hole_panel | 2 | λ 与 (L,W) **同时** ≠ 精确锚点 λ 0.1 / 400×200（D28，两轴都用 `!=`，对齐 D25 读法） | **test** | 双维角点（声明前会先撞 λ val 谓词落 val——入库前补上，见 §7.19 同款缺陷类） |
| open_hole_panel | 3 | 居中且 λ > 0.1（D23） | **val** | 孔径比单维外推 |
| open_hole_panel | 4 | 居中且 (L,W) ≠ 400×200（D23 即声明，batch7 首条数据） | **val** | 尺寸维单维外推 |

⚠️ 表序**必须照 `manifest.py :: HOLDOUT_REGIONS` 的实际顺序**（「首个命中即定」——b7 就发现
本表旧版把柱壳 `single(val)` 排在 `size_double(test)` 之前、开孔板整族缺行：照旧表读，
「长桁 9 + D1800」会落 val 而代码判 test。改声明/加族时先改代码、再照 `HOLDOUT_REGIONS` 抄表）。

判据可陈述：**超过默认值即视为外推**；外推更深 / 引入新形式 → test，单维外推 → val，
其余 → train。**首个命中即定**，所以每族的「兼具」谓词都排在它的单维谓词前面 ——
这就是那条从 11 条里反推出来、又能推广到新 case / 新族的规则。

> ⚠️ 上表是 **D12 锁定的那 11 条**的划分（口径 A）：**train 7 / val 1 / test 3**，10 个等价类、
> **0 个跨 split**。三条 test 各考一种泛化：
>
> - `naca4412_wingbox_n_ribs7_chord800` —— **双维参数外推**（肋最多 + 弦最短）
> - `naca4412_wingbox_str3_T` —— **新截面形式**（T 形翼缘）
> - `stiffened_panel_600x600_str3` —— **第二族族内新形式**（光板 ⇒ 含长桁）
>
> **当前全树（40 条）的实测划分 = train 16 / val 13 / test 11**（翼盒 13/5/5、平板 1/2/1、柱壳 1/3/2、
> 开孔板 1/3/3），**39 个等价类 / 0 个跨 split**。`D12_LOCKED_SPLIT` 仍逐条成立（11/11），
> 规则新增声明不会改写它。
>
> **决策 D12（2026-10-04）** 锁定了「11 条怎么切」= 口径 A；**决策 D13** 定了「M4 显式表 → 规则」
> 的口径 = 声明式留出、未命中默认 train；**D15** 加「兼具平面形状 → test」；**D16** 加
> 「平面形状单维外推 / 平板尺寸单维外推 → val」；**D18** 加柱壳三条（单维 → val、双维 → test、新截面 → test）；
> **D23（2026-10-06）** 加开孔板三条：**偏心孔 = 新形式 → test**、λ 单维外推 → val、居中默认孔 → train
> （常驻闸 `check_forms :: T4.role-and-split` 锁口径）；**D24（2026-10-06）** 加多闭室翼盒三条，
> **按 D16 类推**：首实例（腹板 1，等分）→ train、腹板数单维外推（腹板 2，仍等分）→ val、
> **腹板偏心 = 新形式 → test**（常驻闸 `check_forms :: T6.role-and-split` 锁口径）。
> **D25（2026-10-07）** 加柱壳**尺寸·壁厚维**：判据是**精确锚点** `D2000×L2000×t3` 而不是阈值
> （计数维有 train 能「覆盖」的区间，连续维没有——锚点只采样了一次，两个方向的外推含量相同）；
> 单维 → val、≥2 维（含连续 × 计数组合）→ test。**D26** 钉死 T3 的网格 cap
> `0.4 × min(stringer_height, frame_height)` 与整体尺寸无关（尺寸点不需要改 cap）；
> **D27** 尺寸维**只朝收缩方向**外推（ccx 壳展开内存墙，见 §5.8），「放大臂」缺口记 `limitations`。
> **D28（2026-10-08）** 加开孔板**双维角点**谓词：λ 与 (L,W) **同时** ≠ 锚点（λ 0.1 / 400×200）→ test，
> 插在偏心 test 之后、两个 val 谓词**之前**；两轴都用 `!=`（对齐 D25 的「偏离即算」读法，
> λ 向下的点不被 `>` 漏接）。声明前这样的点会先撞 λ val 谓词落 val（「首个命中」的宽松读法，
> D16/D25 同款缺陷类）——b7 的 `600x300_d60` 是它管的第一条数据，入库前谓词已补上。
> **规则必须逐条复现 D12 的 A**：为杜绝「改声明悄悄改了旧划分」，`manifest.py` 冻结了
> `D12_LOCKED_SPLIT`，`eval_dataset` 用集级闸 `rule_reproduces_D12` 断言 —— 实测 **11/11 完全一致**，
> 所以 D12 无需重签。

**缺口如实记账**（写进 `manifest.json` 的 `limitations`，不藏）：

- **柱壳族 val 曾为空，batch6 已补齐（D25）**：batch3 只落了 train + test（`str8_frm3` / `str12_frm4`），
  柱壳量不到「单维外推」。batch6 用三条尺寸单维外推（d1800 / l1600 / t2 ⇒ **val**）+ 一条双维
  （d1600+l1600 ⇒ **test**）补上——柱壳的 val 现在量的是**连续尺寸维**的单维外推。
- **val 绝对数量仍偏少**：全树 13 条，且集中在「单维外推」上；**两个自由度同时外推的 test 只有 6 条**
  （`n_ribs7_chord800`、`fuselage_..._str12_frm4`、`fuselage_..._d1600_l1600`、`sweep20_taper060`、`sweep40_taper040`、
  `open_hole_..._600x300_d60`）。
- **开孔板尺寸维 val 已落地（batch7，D28 载体）**：`600x300_d30` 是尺寸维首条数据，
  独立证据 = **尺寸不变性探针**（同 λ 必同 Kt：ccx 0.629 % / abaqus 1.539 %，`_probe_b7/_b7_size_invariance.json`）。
  **开孔板厚度维未声明划分**（拍板：对齐平板族 D16 口径）：厚度 ≠ 2 而居中、λ 不变的点将按默认落 train，
  数据集暂无此类点；后续放量厚度维须先补声明（`make_manifest` limitations 已记账）。
- **柱壳尺寸维只有收缩臂（D27）**：放大方向被 ccx 内存墙挡住（§5.8），缺口记 `limitations`，不悄悄丢。
- **新族未声明 ⇒ `unassigned` ⇒ 失败**：这是「该补声明了」的信号，不是可以糊过去的默认值。
  （`every_case_assigned` 抓这个；顺带修了一个真 bug —— 早先 `eval_dataset` 遇到 `unassigned`
  会 `KeyError` 崩溃，即「校验器被它本该报告的情形打死」。）
- **柱壳的两条工具边界**（D19 长桁数包络拒绝 / D22 非 blade 截面拒绝）也写进 `limitations`，
  连同 D20 的「交叉判据换位移口径」一起，让下游看得见「这一族与另两族的判据不完全同构」。

### 11.4 闸会咬人（先证明，再算数）

`eval_dataset.py` 复算 **29 项**，每一项都从**磁盘重来一遍**（文件 sha / spec 哈希 / 等价类 /
角色 / 读数 / 三角数 / minJ），**不读 manifest 里的派生值来验它自己**：

```
$ python eval_dataset.py --root ../FEM-Bench-Aero
=== manifest vs recomputation (29 checks)
  [OK  ] recompute spec_sha256   ...   [OK  ] no_class_spans_splits
  ...  [OK  ] rule_reproduces_D12
cases 40  classes 39  splits {test:11, train:16, val:13}
  fuselage_barrel: {train:1, val:3, test:2}
  open_hole_panel: {train:1, val:3, test:3}
  stiffened_panel: {train:1, val:2, test:1}
  wingbox:        {train:13, val:5, test:5}
VERDICT: PASS
```

负向测试（都留了读数）：

1. **改产物**：手改 `manifest.json` 里一条 split ⇒ `recompute split` FAIL +
   `manifest_summary.splits` FAIL，退出码 2。
2. **拆等价类**：把基线与它的网格消融对照分到 train/test 两边 ⇒ `no_class_spans_splits` FAIL，
   点名 `a796c5b1d217` 跨 `["test","train"]`。
3. **改声明**（M5 新增）：把「单维外推」由 `val` 改判 `test` ⇒ `rule_reproduces_D12` FAIL，
   点名 `naca4412_wingbox_n_ribs7_chord1000: locked=val rule=test`。
4. **未声明族**（M5 新增）：清掉某族的声明 ⇒ `every_case_assigned` FAIL（点名那两条 case）
   + `rule_reproduces_D12` FAIL + `every_family_has_test` FAIL，**不再崩溃**。

**确定性**：`make_manifest` 无时间戳、无主机名，连跑两次（json 与 md）**逐字节一致** ——
「变没变」是一次 `diff`，不是回忆。看板那边还多一道：`_dash_check.js` 会把看板里的划分表
**读回 `manifest.json` 逐条比对**（`split` 与 `split_reason` 都比），防止看板印出没落盘的数。

### 11.5 被否掉的方案（也留读数）

最硬的等价类判据本该是「几何相同 ⇔ STEP 文件逐字节相同」——它完全绕开「哪些字段算几何」
这个人为主张。**实测不成立**：

```
$ head -3 naca4412_wingbox/model.step
FILE_NAME('Open CASCADE Shape Model','2026-10-03T09:47:34', ...

$ sha256sum naca4412_wingbox/model.step naca4412_wingbox_recombination_algorithm3/model.step
66f515b4…  naca4412_wingbox/model.step
10f8eae7…  naca4412_wingbox_recombination_algorithm3/model.step
# 剥掉时间戳再对一次，仍然不同：
25dea842…  vs  c813d6af…
```

- HEADER 带导出时间戳 ⇒ 裸 sha 必然不同；
- **剥掉时间戳后仍不同**（差 31 字节）—— 两个文件是**不同次导出**，导出本身有非确定项。

⇒ STEP 不能当几何指纹。改用 spec 字段双推导（§11.1），并把这次否掉的读数留在这里，
省得下次有人再走一遍。
