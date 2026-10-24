# FEM-Bench-Aero · SPEC（契约 / 导出 / 判定 / 划分）

> 从 `README.md` §10–11 拆出（W3-3，2026-10-24）。唯一契约 `spec.FEASpec`；
> 任务层校验另见 `../FEM-Bench-Aero/schema.json`。

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

