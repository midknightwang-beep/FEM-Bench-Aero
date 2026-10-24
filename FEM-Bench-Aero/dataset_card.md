# FEM-Bench-Aero · Dataset Card（v1.0-rc）

> **命名声明**：FEM-Bench-Aero 为本团队内部命名（当前范围为 A 建模集），与 GitHub 公开仓库 FEM-Bench 无关联；公开发布前将评估更名（2026-10-24 拍板③）。
> **数字来源**：本卡全部数字引用 `external_numbers.md`（由 `make_external_numbers.py` 从权威 JSON 自动生成），勿手抄。

## 1. 动机与定位

为「LLM 驱动的飞机结构有限元建模」提供**可信真值 + 判据体系**。数据集是手段，benchmark + verifier 才是产品（D37 方向转向）。当前定位：**答案册已可信，考卷接口在任务层建设**（`tasks/` + `evaluate.py`）。

## 2. 构成

| 项 | 值 | 来源 |
|---|---|---|
| 算例规模 | 55 条 × 2 棵求解器树 = 110 算例目录 | manifest.summary |
| 几何等价类 | 54（重复 0、跨 split 泄漏 0） | manifest.summary |
| 结构族 | wingbox 34 / open_hole_panel 11 / fuselage_barrel 6 / stiffened_panel 4 | manifest.cases 实算 |
| 结构形式 | T1–T7（后掠锥形翼盒、加筋壁板、机身柱壳、开孔板、长桁截面、多闭室、复材层合） | README |
| 材料 | 铝 2024-T3 ×51；CFRP 等效单层 ×4 | stage_audit |
| 划分（v1.0） | train 25 / val 17 / test 13 | manifest |
| 划分（任务层 v2） | train / val / **id_test**（6 条，翼盒 train 包络整类留出 28.6%）/ **extrapolation_test** | tasks/tasks.jsonl |

## 3. 判据体系（闸）

九道闸（网格 / 语义 / 平衡 / 双码 / 解析解 / 退化 / 去重 / 回归 / 契约自洽），判据与证据链见 `README.md` §5 与 `gates_all55_d36.json`。任务层评测（A1 题型）用其中三道：网格质量（minJ ≥ 0.30 且零 tri3）、语义（`topology.compare`）、物理保真（max_disp 相对偏差 < 1%，口径对齐双码位移判据）。

## 4. 已知限制（如实登记，引用前必读）

1. **vM 峰值网格未收敛**：锚点几何 12→6 mm 峰值仍 +12.9 %，应力真值带 ≥13 % 偏不安全低估（`_probe_m14/h_convergence.json`）。位移良定义（−0.48 %）。
2. **机器可读双码证据仅翼盒 34/34**：其余 21 条分族取证（关 3 机读化 = W3 任务）。不存在「55 条全部双码验证」的说法。
3. **v1.0 test 13 条全部为外推/新形式**（无 ID 内插点）；任务层已增设 id_test 补齐。
4. **发布树非翼盒 spec 带死 `airfoil` 块**（21 条，不生效字段）与 `chord` int 混入（5 条）：任务层 `normalize_spec` 已规范化，本体保持原样（避免 110 truth 重导）；schema.json 已拒绝死字段。
5. **`recombination_algorithm3` 为同几何网格鲁棒性对照样本**（max_disp 差 0.024 %），不参与样本量统计。
6. **Abaqus 树不发布**（许可），且 abaqus 非关键路径——发布树由 CalculiX 独立产出。
7. **复材为 CLT 等效单层**（架构 B），非逐层应力。
8. **代理模型基线已冻结为附录**（D37）：`baseline_d36_final.json` 仅作可学性证明，非产品 KPI；应力峰值不可学（峰值位置离散 28/34 节点）。

## 5. 许可

- 数据与判据：CC BY 4.0（规划）；
- CalculiX：GPL（求解器本体）；
- `_xval/` Abaqus 交叉树：不发布。

## 6. 引用方式

规模/闸门数字引用 `external_numbers.md`；基线数字引用 `baseline_d36_final.json` 并注明「附录口径，KPI 已换 TSR/FPR」。
