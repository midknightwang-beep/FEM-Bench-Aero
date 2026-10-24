# 飞机结构强度分析有限元模型高效构建与更新（LLM + Agent）数据集调研报告

> 调研目标：为支撑"基于大语言模型（LLM）和智能体（Agent）实现飞机结构强度分析有限元模型高效构建与更新"研究，系统梳理可用的**开源/免费数据集**，并对**非开源/受限但高度适配的数据集**给出内容说明与场景适配性分析。
>
> 检索时间：2026-07-14 ｜ 标注约定：✅ 开源免费　💰 商业/受限（含免费但需注册、非商业许可等）

---

## 0. 研究方法与数据映射框架

本课题可拆解为三个能力环，每个能力环对数据的需求不同：

| 能力环 | 对数据的需求 | 本报告对应章节 |
|---|---|---|
| **A. 模型高效构建**（几何→网格→属性→求解） | 飞机结构几何/CAD、参数化建模序列、材料/强度属性 | §1、§3 |
| **B. 模型更新**（试验/监测数据驱动修正） | 全机/部件模态试验、振动/导波/声发射监测、损伤样本 | §2 |
| **C. LLM/Agent 训练与评测** | FEA 代码语料、结果解读基准、力学推理题、知识图谱 | §4 |

> 注意：所有数据集的**许可（License）与获取方式以官方源为准**，尤其涉及商业用途时务必再次核对条款。本报告对许可的标注基于检索时公开页面信息。

---

## 1. 飞机结构有限元模型"高效构建"相关数据

### 1.1 飞机结构几何与现成有限元模型（直接可用或可作基准）

| 数据集 | 内容 | 许可/获取 | 对场景的适配性 |
|---|---|---|---|
| **NASA CRM（Common Research Model）几何与网格** | 跨音速民航机基准构型的几何（IGS/CGNS 多分辨率）、基线/优化外形；ADODG 机翼优化基准 | ✅ CC BY 4.0；https://www.doi.org/10.17632/7jnyjdbvf9.1 ；NASA CRM 官网 | 构建机翼/机身 FEM 的"金标准"基准几何，便于批量生成参数化 FE 模型并校准 Agent |
| **NASA CRM Wingbox FEM 文件** | 翼盒有限元模型（V12/V14/V15、MATLAB 版、中面 IGES）；含材料、PSHELL、CONM2 等 | ✅ 公开（NASA）；https://commonresearchmodel.larc.nasa.gov/fem-file/wingbox-fem-files/ | 现成翼盒 FE 模型，可直接作为"构建目标"的真值或 Agent 输出对照 |
| **pCRM9 / uCRM（气动弹性机翼 NASTRAN 模型）** | pCRM9（密歇根大学/代尔夫特理工）NASTRAN SOL103 模态模型、材料/重量平衡/有限元文件；uCRM-9/13.5 高保真机翼气动-结构模型 | ✅ pCRM9 见 haidatas 镜像；uCRM ✅ CC BY 4.0（Mendeley Data） | 机翼模态分析的现成基准模型，适合做"模型构建→模态校核"闭环 |
| **OpenVSP（参数化飞机几何引擎）+ RAVEN/BD-6 模型** | 开源参数化几何工具；NASA RAVEN、BD-6 等 OpenVSP 模型（gltf，公开） | ✅ 开源（NASA）；https://github.com/OpenVSP/OpenVSP ；RAVEN https://www.nasa.gov?p=924228/ | **关键工具**：可用工程参数（展弦比、后掠角等）程序化生成飞机几何，是"自然语言/参数→FE 模型"自动构建管线的几何入口 |
| **GARTEUR 飞机模型** | 欧洲航宇院基准模型（翼展 2 m，铝结构+约束阻尼），参数与 FE 建模方法公开 | ✅ 基准（参数公开，需自建模型） | 模型修正（Model Updating）经典基准，可作"构建+更新"联合评测对象 |
| **AGARD 445.6 机翼** | 跨音速颤振标准试验机翼；实验模态频率（9.60/38.17 Hz…）与几何公开 | ✅ 实验数据公开；HiSA 校验案例 https://hisa.gitlab.io/archive/movingMesh/agard445/ | 气动弹性/颤振分析基准，适合"构建→气动弹性校核" |
| **X-56A MUTT（Multi-Utility Technology Testbed）** | NASA 高柔性长航时机翼无人机，模块化可换翼，含气动弹性/阵风载荷飞行数据 | ✅ NASA 公开；https://www.nasa.gov/aeronautics/x-56a-mutt/ | 高柔翼"模型不确定性大、需更新"的典型对象，贴近"柔性飞机结构模型更新" |

### 1.2 CAD 建模序列（支撑"从描述/草图自动生成模型"）

| 数据集 | 内容 | 许可/获取 | 对场景的适配性 |
|---|---|---|---|
| **Fusion 360 Gallery Dataset** | 8,625 条真实人类 CAD 设计序列（Sketch+Extrude 程序化表达）；另含 35,858 模型的分割子集 | ✅ 研究许可（GitHub）；https://github.com/AutodeskAILab/Fusion360GalleryDataset | 训练"从自然语言/草图→参数化 CAD→网格"的生成式 Agent 的核心语料 |
| **DeepCAD（Siemens）** | ~178,238 个 CAD 模型，统一以"草图+挤压"命令序列+参数表示 | ✅ 开源（Onshape 来源） | 规模较 Fusion360 大一个数量级，适合学习 CAD 命令序列生成 |
| **ABC Dataset** | 100 万+ CAD 模型（STEP/B-rep/Parasolid/STL），含精确曲面与参数化曲线 | ✅ MIT 许可（模型版权归创作者）；https://deep-geometry.github.io/abc-dataset/ | 几何深度学习/逆向建模/特征检测，用于从点云/网格重建可编辑 CAD |
| **SMCAD（Semantic Mechanical CAD）** | ~10,000 机械零件（STEP+网格+语义标签：齿轮、螺栓等） | ✅ 开源 | 带工程语义标签，适合让 Agent 理解"这是什么零件、如何建" |

---

## 2. 有限元模型"更新"相关数据（试验/监测/损伤）

### 2.1 全尺寸飞机模态试验 / 模型更新（**最贴合本课题**）

| 数据集 | 内容 | 许可/获取 | 对场景的适配性 |
|---|---|---|---|
| **Hawk T1A 全尺寸飞机 MIMO 模态试验** | 退役 BAE Hawk T1A 整机 MIMO 模态测试，含多种已知加载与损伤模拟工况，体现非线性与损伤敏感性 | ✅ CC BY 4.0（White Rose / Sheffield）；https://eprints.whiterose.ac.uk/221504/ | **强烈推荐**：全尺寸真实飞机、可控损伤、含数据集，是"试验数据驱动 FE 模型更新"Agent 的极少见全机级开放基准 |
| **M001：折叠翼尖机翼 GVT 数据 + NASTRAN 模型（2024）** | 5 个不同刚度机翼的地面振动试验（GVT）模态数据 + NASTRAN 模型；含"原始模型"与用 Simcenter 模型更新流程得到的"更新后模型" | ✅ 开放（4TU.ResearchData）；https://data.4tu.nl/datasets/984090ea-26fd-4809-8dac-f41367bf8916 | **强烈推荐**：直接提供"原始模型 vs 更新后模型"对照，是训练/评测"模型更新 Agent"的现成素材 |

### 2.2 结构健康监测 / 损伤检测基准（方法可迁移至飞机）

| 数据集 | 内容 | 许可/获取 | 对场景的适配性 |
|---|---|---|---|
| **复合材料全尺寸外翼导波 SHM 数据库（Bologna/Leonardo）** | ~4.5 m 复合材料外翼演示件，160 个压电换能器的导波与机电阻抗信号；含加载前/疲劳前/冲击前/冲击后 4 阶段 | ✅ 开放获取（原文 Mechanical Systems and Signal Processing） | 飞机复合材料结构损伤检测/表征的真实尺度数据，直接支撑"损伤信息→模型更新" |
| **CompInnova WP2（Cranfield）** | 复合材料层合板/层合件的超声相控阵（PA）C-scan 冲击损伤数据（CSV+图像），含材料与铺层信息 | ✅ 开放（Zenodo）；https://zenodo.org/records/4405276 | 复合材料损伤量化，补充模型更新的损伤证据来源 |
| **AIRSD（战斗机表面损伤）** | 8,091 张 640×640 飞机表面图像，11 类损伤（合成+真实） | ✅ 公开（Google Drive）；https://www.selectdataset.com/dataset/8a5ced822abf5ddf2e57233cd70aab7b | 视觉损伤检测，可作为多模态 Agent 的"损伤识别"输入 |
| **飞机复合材料声发射（AE）数据集** | 1,000 样本、14 特征列，用于复合材料损伤（基体开裂/纤维断裂等）分类 | ✅ 免费（Kaggle）；https://www.kaggle.com/datasets/ziya07/acoustic-emission-dataset | 时域信号特征化的损伤分类，适合监测类 Agent |
| **桥梁类（方法迁移）**：Ponte Moesa Campagnola、HBTA、挪威长跨桥、Z24、IASC-ASCE 钢框架 | 受控损伤、环境/疲劳监测、加速度/应变时序、模态参数 | ✅ 多开放：PMC https://doi.org/10.3929/ethz-b-000716850 ；HBTA https://dx.doi.org/10.5281/zenodo.14028239 ；ASCE-IASC http://wusceel.cive.wustl.edu/asce.shm | 虽非飞机，但提供了成熟的"模型更新/损伤识别"算法验证范式，可迁移到航空结构 |

### 2.3 通用 FE 模型更新基准

- **UCF Grid Benchmark**、**Canton Tower SHM**、**IASC-ASCE Phase II** 等：提供"先验 FE 模型 + 实测 FRF/模态"对照，是模型更新（刚度/质量参数辨识）的经典学术基准，宜作为算法预研的中介数据集。

---

## 3. 材料与强度属性数据（强度分析核心输入）

### 3.1 金属（航空铝合金 / 钛合金）

| 数据集 | 内容 | 许可/获取 | 对场景的适配性 |
|---|---|---|---|
| **Materials Project / OQMD / AFLOW / OPTIMADE** | 大规模材料计算数据库，提供弹性常数、相图、热力学等；OPTIMADE 统一 API 可跨库查询 | ✅ 开源 API（多数 CC/学术许可）；https://optimade.org | 为 FE 模型批量注入材料弹性参数（E、ν、密度），支撑 Agent 自动选材与属性填充 |
| **MMPDS（Metallic Materials Properties Development and Standardization）** | 全球航空金属（铝、钢、钛等）**统计许用值**（拉伸、疲劳、膨胀系数），FAA/DoD/NASA 认可 | 💰 商业（Matplus 数字库，含 API） | 见 §5 说明 |
| **MIL-HDBK-17（历史卷）** | MMPDS 前身，部分历史卷为美国政府公开文件 | ✅ 历史卷多可公开获取 | 低成本获取航空复材/金属许用值的替代来源 |

### 3.2 复合材料

| 数据集 | 内容 | 许可/获取 | 对场景的适配性 |
|---|---|---|---|
| **NCAMP 共享复材特性数据库** | 航空级复材（如 CYCOM 5320-1）层板/单层性能，经统计鉴定 | ✅ 免费（需在线注册）；https://www.niar.wichita.edu/NCAMPPortal/ | 飞机主结构复材属性权威来源，支撑复材 FE 建模 |
| **kompozity.info 复合材料数据库** | 十余种复材试验结果（超轻飞机主结构用） | ✅ 免费 Web 接口 | 轻量化航空复材属性补充 |
| **MaterialsMine（NanoMine / MetaMine）** | 纳米复合材料、力学超材料开放知识图谱与数据 | ✅ 开源；http://materialsmine.org | 复材/超材料属性与微结构数据 |
| **CLT-material-properties（开源工具）** | 经典层合理论（CLT）计算：刚度矩阵、失效准则（Tsai-Wu 等） | ✅ 开源（GitHub ScalableDesign） | 可直接嵌入 Agent 的"复材层合板强度校核"工具链 |

### 3.3 材料知识图谱 / 语料（供 LLM 内化领域知识）

| 数据集 | 内容 | 许可/获取 | 对场景的适配性 |
|---|---|---|---|
| **MatKG** | 材料科学最大知识图谱：7 万+实体、540 万三元组（材料-属性-工艺-应用） | ✅ 开放（CSV/RDF + 代码）；https://www.nature.com/articles/s41597-024-03039-z | 为 Agent 提供"材料→性能→工艺"结构化检索与推理底座 |
| **MatBERT** | 在 200 万篇材料科学论文上预训练的 BERT 权重（88 亿 token） | ✅ 开源权重（GitHub lbnlp/MatBERT） | 领域 LLM 初始化，提升 Agent 对材料/强度文本的理解与抽取 |

---

## 4. LLM / Agent 训练与评测基准（直接面向"FEA + LLM"）

| 数据集/基准 | 内容 | 许可/获取 | 对场景的适配性 |
|---|---|---|---|
| **ALL-FEM** | 1,000+ 经校验的 FEniCS 有限元脚本语料（固体/流体/多物理场），用于微调 3B–120B 模型 + 多智能体框架 | ✅ 开源（模型/数据集/基准）；https://fenics-llm.github.io/ | **核心**：FE 代码生成与"问题陈述→校验解"闭环 Agent 的直接训练/评测资源 |
| **FRAME（FEA Reasoning & AI-Agent Model Engine）** | FEA 结果解读开源基准：将应力云图+参数→结构化文本描述（识别应力集中、提取 von Mises 最大值、提出几何/材料修改建议） | ✅ 开源基准 | 训练/评测 Agent 的"看结果→提修改"推理能力，契合"自优化设计"闭环 |
| **FEM-Bench** | 计算力学代码生成评测（静/动力学、线性/非线性弹塑性等），客观可验证 | ✅ 开源（arXiv） | 评测 Agent 生成科学有效 FEM 代码的能力 |
| **StructuralEval** | 结构力学多模态评测：输入梁/刚架/桁架图片→输出标准结构定义 JSON，由 WASM 求解器（FrameCalc）物理验证 | ✅ 开源（HuggingFace superhatk/structural-eval-benchmark） | "图片→可计算结构模型"的视觉转译评测，贴合"从图纸/照片构建 FE 模型" |
| **SoM-1K（材料力学千题）** | 1,000 道材料力学题（含图），评测 LLM/VLM 领域推理 | ✅ 开源（arXiv 2509.21079） | 力学推理能力基线评测 |
| **OpenTO / OpenOAT（拓扑优化）** | 220 万优化结构（2M 无标签 + 700K 标注 BC/载荷/体积分数 + 15K 测试） | ⚠️ CC BY-NC-ND 4.0（**非商业、禁止演绎**）；https://hf-mirror.com/datasets/OpenTO/OpenOAT | 训练"载荷/约束→最优拓扑"生成模型；注意**不可商用、不可改数据集**。OAT 基础模型见 github ahnobari/OptimizeAnyTopology |

---

> 📌 上述四个 FEA+LLM 基准（ALL-FEM、FRAME、FEM-Bench、StructuralEval）的**深度解读、评测结果与场景适配性评分**见第 7 章。

## 5. 非开源 / 受限但高度适配的数据集（内容说明 + 适配性）

以下数据集**不直接免费**或其许可限制较强，但与该课题高度相关，故单独说明，便于在合规前提下获取或作为对照基准。

| 数据集 | 内容说明 | 许可/获取 | 与本场景的适配性 |
|---|---|---|---|
| **MMPDS（金属航空材料许用值）** | 全球商业/军用航空金属材料的**统计许用值**标准库（铝 7075/2050/7140、钛 Ti-6Al-4V 等），含拉伸、疲劳、热膨胀等，被 FAA/DoD/NASA 认可；MMPDS-26 新增增材制造条目并支持 API 集成 | 💰 商业（Matplus 数字库，独立在线库或 EDA 集成） | **适配度极高**：飞机结构强度分析选材与许用值的"黄金标准"。局限：需采购，且不可自由再分发；适合作为 Agent 的"权威校核知识源"（只读调用 API），不宜作为训练语料再分发 |
| **NCAMP 复材数据库** | 航空级复合材料单层/层板特性，经统计鉴定（与 Cytec 等合作） | ✅ 实际**免费但需注册**（niar.wichita.edu/NCAMPPortal） | 虽在部分渠道被标注为商业，但官方门户对个人免费开放，是复材 FE 建模的首选免费权威源 |
| **MaterialCenter Databanks（Hexagon）** | 集成多种材料库的单一入口：MMPDS 金属库、NCAMP 复材库、**MIL-HDBK-17 复材库（免费）**、JAHM 温度-曲线库、Senvol 增材制造库、Machine Design 选择器（免费）等 | 💰 商业平台（各库分开计价；部分子库免费） | 适合企业级"材料数据统一管理"，可作为 Agent 的材料数据后端；免费子库（MIL-HDBK-17、Machine Design）可直接利用 |
| **MatWeb / CES EduPack / ASM International** | 通用材料机械/物理属性聚合站（金属、聚合物、陶瓷等） | 💰 商业/教育许可 | 通用属性查询方便，但航空级精度与认证不及 MMPDS/NCAMP；可作快速查值，不宜作为认证依据 |
| **NAFEMS 标准基准书（P18 等）** | 经典 FEM 验证题（LE1 椭膜、LE6 斜板、LE10 厚板等），含解析解 | 💰 标准书付费（£15–45）；但**单个基准题与解法广泛免费**（Seamplex、Caesar Systems、ESRD 等网站提供） | 模型构建/求解器验证的必备基准；建议直接用各 solvers 社区免费发布的题目与参考解，无需购书 |
| **商业 FEA 模型库（Altair/ANSYS/Siemens 示例模型）** | 厂商随软件附带的大量工程示例 FE 模型（含航空结构案例） | 💰 随商业软件授权提供，通常不可外部分发 | 可作内部"构建目标"对照，但受 EULA 限制，不能公开再分发或作为训练集对外发布 |

> **适配性小结**：非开源数据中，**MMPDS（金属）与 NCAMP（复材）是飞机结构强度分析不可替代的权威属性源**。最佳实践是——以开源几何/模态/语料数据训练与评测 Agent，以 MMPDS/NCAMP 作为 Agent 运行时的"只读权威查值/校核"接口（通过官方 API 或授权库），而非将其打包进可分发训练集。

---

## 6. 推荐组合与落地建议

**A. "模型高效构建"数据栈**
- 几何入口：`OpenVSP` 参数化生成 + `NASA CRM / pCRM9 / uCRM` 基准外形
- 建模序列学习：`Fusion 360 Gallery` + `DeepCAD` + `ABC`（逆向/重建）
- 属性注入：`Materials Project/OPTIMADE` API（金属）、`NCAMP`（复材）、`CLT-material-properties`（层合计算）
- 目标：训练"自然语言/参数 → CAD → 网格 → 带属性 FE 模型"的生成式 Agent

**B. "模型更新"数据栈**
- 首选：`Hawk T1A` 全机模态试验 + `M001（CRM 折叠翼 GVT vs 更新后模型）` 作为端到端更新基准
- 补充：复合材料 `Bologna 外翼导波库` / `CompInnova` 提供损伤证据；`AGARD 445.6` / `X-56A` 提供气动弹性更新对象
- 方法迁移：桥梁类基准（PMC/HBTA/ASCE-IASC）打磨更新算法
- 目标：训练"试验/监测数据 → 参数修正建议 → 更新后 FE 模型"的更新 Agent

**C. "智能体"训练与评测栈**
- 代码生成/闭环：`ALL-FEM` + `FEM-Bench`
- 结果解读/自优化：`FRAME` + `StructuralEval`（视觉转译）
- 领域知识：`MatBERT`（初始化） + `MatKG`（结构化检索）
- 力学推理：`SoM-1K`
- 拓扑生成（非商用）：`OpenTO/OpenOAT`（注意 CC BY-NC-ND）

**许可红线提示**
1. `OpenTO/OpenOAT` 为 **CC BY-NC-ND**：不可商用、不可改数据集——仅限科研训练。
2. `MMPDS/MatWeb/ASM/NAFEMS 书` 不可自由再分发，作只读校核源。
3. `ABC` 模型版权归原创作者（Onshape），研究使用遵循其条款。
4. 所有 NASA/4TU/Zenodo/Nature Scientific Data 资源基本可自由使用（注意个别标注 CC BY 需署名）。

---

## 7. 重点解读：FEA+LLM 四大基准深度评估（ALL-FEM / FRAME / FEM-Bench / StructuralEval）

> 这四类数据集是当前"有限元分析 + 大语言模型/智能体"方向最成体系的开源资源。以下逐项解读其设计、规模、评测结果与对本课题（飞机结构强度 FEM 高效构建与更新）的适配性，并给出适配度评分（5 分制）。

### 7.1 ALL-FEM —— 自主有限元仿真系统（语料 + 多智能体框架）

**概述**：ALL-FEM（Agentic LLMs fine-tuned for Finite Element Methods，CMAME 2026, vol. 457, arXiv:2603.21011）提出一套"领域微调 LLM + 多智能体"的自主仿真系统，面向 FEniCS 代码生成，覆盖固体、流体与多物理场。

**数据与模型构成**：
- 语料：1,000+ 条**经校验的 FEniCS 脚本**，由 500+ 条专家整理代码 + 检索增强的多 LLM 流水线（生成并过滤不同 PDE、几何、边界条件变体）构成。
- 微调：用该语料微调 3B–120B 参数的开放权重模型；最佳模型为 GPT OSS 120B（OpenAI 开放权重）。
- 智能体框架：多个专职智能体协作——将问题建模为 PDE、生成代码、调试代码、可视化结果，并带运行时反馈闭环。

**评测结果**：
- 在 39 个基准问题上评测，覆盖线性/非线性弹性、塑性、牛顿/非牛顿流动、热流、流固耦合（FSI）、相分离、动域输运。
- 最佳微调模型（GPT OSS 120B）代码级成功率达 **71.79%**，优于非智能体部署的 GPT-5 Thinking。

**许可**：模型/数据集/基准随论文开源（研究用途）；具体 LICENSE 以仓库为准。GPT OSS 120B 为开放权重模型。

**与本研究场景适配性评估**：
- ✅ 价值：提供了"问题陈述 → 校验解"的**端到端自主仿真智能体蓝图**，以及可直接微调的 FEM 代码语料，是构建"建模 Agent"的方法论范本。
- ⚠️ 局限：① 基于 **FEniCS（变分形式 + dolfinx）**，与飞机结构强度常用的商业/专用 FEA（NASTRAN/Abaqus/ANSYS 的壳/梁/接触/非线性材料）差异较大，需做领域迁移与语料扩充；② 39 题偏"科学计算 PDE"，**不含航空结构几何、材料、载荷与模型更新**；③ 不直接涉及"从试验数据更新模型"。
- 适配度（5 分制）：模型构建方法 4.5；模型更新 1.5；多模态推理 2.0；航空专用 2.0；可直接训练 4.0；许可友好 4.0 → **综合 3.0**。

**使用建议**：将其智能体框架（PDE 建模→代码生成→调试→可视化）复用到本课题的"建模 Agent"；将 FEniCS 语料作为种子，结合本报告 §1–§3 的飞机几何/材料数据，扩充出航空结构专用的 FE 代码微调集。

### 7.2 FRAME —— FEA 结果解读与自优化智能体基准

**概述**：FRAME（Finite element Reasoning and AI-Agent Model Engine，OpenReview）提出一个**开源多模态基准**，专门评测/微调 VLM/LLM 对 FEA 结果（云图+参数）的解读与推理能力，并演示自优化设计智能体工作流。

**数据与任务构成**：
- 数据："数千个"数据点，系统整理自学术文献与内部仿真，覆盖**航空航天、汽车、生物力学**等领域。
- 配对形式：将可视化仿真输出（应力/应变/温度云图）+ 关键问题参数（材料、边界条件）→ 结构化文本描述。
- 三类任务：① 识别关键特征（应力集中、屈服、最大变形）；② 提取关键值（最大 von Mises 应力）；③ 提出可执行的几何/材料修改建议（如"增大圆角半径以降低应力集中"）。
- 质量：经人类专家评估（忠实性、物理准确性、完整性）验证。

**评测结果**：
- 评测多个主流通用多模态模型的零样本性能；在 FRAME 训练集上微调较小开源模型后指标略有提升。
- 经语义相似度 + ROBERTA 关键词准确率衡量，微调后的小模型**超过更大的通用基线**，证明领域数据的重要性。

**许可**：开源基准（论文随附，具体许可以仓库为准）。

**与本研究场景适配性评估**：
- ✅ 价值：① 直接覆盖**航空航天**领域；② 任务（读云图→提建议）正是飞机结构强度"模型解读/设计改进"环节所需；③ 提供"自优化 Agent 工作流"范式，可对接本报告 §2 的模型更新数据形成"解读→更新"闭环。
- ⚠️ 局限：① 属"结果解读/建议"而非"模型构建"或"模型更新（参数反演）"；② 数据为文献+内部仿真整理，量级与格式需自行对接；③ 不直接提供数值化的"更新后模型"。
- 适配度：模型构建 2.0；模型更新 3.0（作为解读前端）；多模态推理 4.5；航空专用 4.0；可直接训练 4.0；许可友好 4.0 → **综合 3.5**。

**使用建议**：将 FRAME 作为"FEA 结果理解"智能体头的训练/评测集；其"识别→提取→建议"三任务可改造为"读取强度分析结果→定位超限区→生成模型修正指令"的子 Agent。

### 7.3 FEM-Bench —— 计算力学代码生成结构化评测

**概述**：FEM-Bench（arXiv:2512.20732，2026-05）是面向"LLM 生成科学有效 FEM 代码"的结构化评测基准，强调客观可验证。

**数据与任务构成**：
- 33 个"入门但非平凡"任务，对齐研究生一年级计算力学课程，含三大类：
  - **FEM 1D**：离散化、单元装配、线弹性基础（一维网格、局部刚度矩阵）。
  - **FEM 2D**：几何、高阶插值、多维积分、单元级积分（形函数及导数、参考单元积分、几何映射）。
  - **MSA 3D（矩阵结构分析）**：题量最多，涵盖局部/全局坐标、单元刚度与荷载例程、全局装配、小位移线弹性求解、屈曲（特征值）分析。
- 每题配对参考实现、验证输入与 **pytest 单元测试**；采用递归数值匹配（容差内）的二值正确性判定。

**评测结果**（10 个模型，温度 0.1）：
- 函数编写最佳：Gemini 3 Pro，5 次尝试中 30/33 至少一次通过、26/33 五次全过。
- 单元测试编写最佳：GPT-5，平均联合成功率 **73.8%**。
- 其余模型表现差异显著，说明通用 LLM 对物理/数值约束仍不可靠。

**许可**：开源基准（arXiv + 代码仓库）。

**与本研究场景适配性评估**：
- ✅ 价值：① 提供**严格、可复现的代码级评测协议**（pytest + 数值容差），可直接用作本课题"建模 Agent 代码生成"的评测底座；② MSA 3D 部分与飞机骨架（梁/刚架）结构分析直接相关；③ 支持"函数生成 + 单元测试生成"双重评估，利于 Agent 自校验。
- ⚠️ 局限：① 任务为**教科书级**，远未达飞机结构（壳/接触/非线性/动力学）复杂度；② 仅评"写代码"，不含完整建模链路（几何→网格→属性→求解→解读）；③ 不涉及模型更新。
- 适配度：模型构建 3.5；模型更新 1.0；多模态推理 1.5；航空专用 2.5；可直接训练(评测) 4.5；许可友好 4.5 → **综合 3.0**。

**使用建议**：作为"建模 Agent"代码生成能力的**回归测试集**；在其之上扩展飞机结构专属题（壳单元、装配接触、复合材料层合、颤振/模态），形成本课题的专用 FEM-Bench-Aero。

### 7.4 StructuralEval —— 结构力学视觉转译评测（图片→结构模型）

**概述**：StructuralEval（HuggingFace，v1.0 共 25 题）是结构力学垂直评测基准，要求多模态模型把梁/刚架/桁架图片"翻译"为标准结构定义 JSON，再由 WASM 物理求解器 FrameCalc 做有限元验证。

**数据与任务构成**：
- 理念："AI 负责建模，引擎负责计算"。输入结构图片 → 输出 JSON（节点坐标、构件连接、支座类型、荷载）。
- 难度 1–5 级：L1–2 基础梁；L3 简单桁架/刚架；L4–5 复杂多跨刚架/大型桁架（含天津大学 2021 结构力学考研真题 frame_010）。
- 评测：JSON 送入 FrameCalc 做 FEA，比较 AI 的物理响应（支座反力、最大弯矩）与真值。
- 分级诊断评分：几何 0.0 → 支座 0.25 → 连接 0.50 → 荷载 0.75 → 完全正确 1.0；最终**加权准确率** = Σ(难度×诊断系数)/Σ总难度。

**评测结果**（榜单，2026-04-05，Retries=3）：
- Qwen3.5-35B-A3B **40.23%**；Qwen3-VL-32B-Instruct 35.16%；gemma-4-31B-it 33.98%；GLM-4.5V-INT8 19.53%。
- 当前模型整体偏低，说明"从图到可计算结构模型"仍是难点。

**许可**：**CC BY-NC 4.0（署名-非商业）**——禁止商用，免费使用须标注来源。⚠️ 商用研究需注意合规。

**与本研究场景适配性评估**：
- ✅ 价值：① 直接对应本课题"**模型高效构建**"中的"从工程图/照片自动建模"环节；② "图片→JSON→求解器验证"的闭环与评价机制可复用；③ 难度分级与诊断式评分利于定位 Agent 弱点。
- ⚠️ 局限：① 仅覆盖梁/刚架/桁架（杆系结构），不含飞机典型的**板壳/实体/复合材料**；② 图片为简化示意图，与真实飞机结构图（含尺寸标注、剖视）差距大；③ 非商业许可，限制产品化；④ 不涉及模型更新。
- 适配度：模型构建 4.0；模型更新 1.0；多模态推理 4.0；航空专用 2.5；可直接训练 3.5；许可友好 2.5（非商业）→ **综合 3.0**。

**使用建议**：作为"图纸/草图→结构模型"多模态 Agent 的评测基线；将题集扩展为含飞机结构元素（翼肋/长桁/框的板壳图、带标注工程图）的自建版，并复用其 WASM 验证思路。

### 7.5 四基准横向对比与本课题适配度总评

| 维度 | ALL-FEM | FRAME | FEM-Bench | StructuralEval |
|---|---|---|---|---|
| 核心定位 | 代码生成+自主仿真 | 结果解读+自优化 | 代码生成评测 | 视觉转译评测 |
| 模态 | 文本(代码) | 多模态(图+参数) | 文本(代码) | 多模态(图→JSON) |
| 是否覆盖航空 | 间接(通用PDE) | ✅ 明确含航空航天 | 间接(MSA3D) | 间接(杆系) |
| 模型构建 | ★★★★☆ | ★★☆ | ★★★★(评测) | ★★★★ |
| 模型更新 | ☆ | ★★★ | ☆ | ☆ |
| 多模态推理 | ★★ | ★★★★★ | ★★ | ★★★★ |
| 许可友好度 | 研究开源 | 开源 | 开源 | ⚠️ CC BY-NC |
| 综合适配(5) | 3.0 | 3.5 | 3.0 | 3.0 |

**关键缺口提示（重要）**：
1. **这四大基准均聚焦"构建/解读/代码生成"，没有一项直接覆盖本课题后半段的"有限元模型更新（试验/监测数据驱动的参数反演与修正）"**。模型更新所需数据见本报告 §2（Hawk T1A 全机模态、M001 CRM 折叠翼 GVT+更新后模型、复合材料导波库等）。
2. 四者均为**通用计算力学/结构**，缺少飞机专用几何、材料、载荷与认证语境；需结合 §1–§3 数据做领域化扩充。
3. 工具链差异：ALL-FEM/FEM-Bench 围绕 FEniCS/Python 科学计算；真实飞机结构强度多用 NASTRAN/Abaqus/ANSYS。落地时需桥接"LLM 生成的模型描述"与"商业 FEA 输入格式（BDF/INP/CATIA）"。

**落地组合建议**：
- "建模 Agent"：ALL-FEM 框架 + FEM-Bench 评测 + StructuralEval 的"图→模型"思路。
- "解读/更新 Agent"：FRAME 的"识别→提取→建议"头 + §2 的试验/监测数据形成"解读→更新"闭环。
- 领域化：以 §1–§3 的飞机几何/材料/工况为锚，将四基准扩展为 FEM-Bench-Aero / FRAME-Aero / StructuralEval-Aero。

---

## 8. 关键获取链接汇总

- NASA CRM / Wingbox FEM：`https://commonresearchmodel.larc.nasa.gov/fem-file/`
- uCRM（Mendeley）：见 `https://www.selectdataset.com/dataset/f1ae3590789a24f47bf68818b633f5e2`
- OpenVSP：`https://github.com/OpenVSP/OpenVSP` ｜ RAVEN：`https://www.nasa.gov?p=924228/`
- Fusion 360 Gallery：`https://github.com/AutodeskAILab/Fusion360GalleryDataset`
- ABC Dataset：`https://deep-geometry.github.io/abc-dataset/`
- Hawk T1A：`https://eprints.whiterose.ac.uk/221504/`
- M001 GVT+Nastran：`https://data.4tu.nl/datasets/984090ea-26fd-4809-8dac-f41367bf8916`
- Bologna 外翼导波库：检索 "open database guided waves composite full-scale outer wing demonstrator"
- CompInnova WP2：`https://zenodo.org/records/4405276`
- AIRSD：`https://www.selectdataset.com/dataset/8a5ced822abf5ddf2e57233cd70aab7b`
- 声发射 Kaggle：`https://www.kaggle.com/datasets/ziya07/acoustic-emission-dataset`
- Materials Project：`https://materialsproject.org` ｜ OPTIMADE：`https://optimade.org`
- NCAMP：`https://www.niar.wichita.edu/NCAMPPortal/`
- MatKG：`https://www.nature.com/articles/s41597-024-03039-z`
- MatBERT：`https://github.com/lbnlp/MatBERT`
- ALL-FEM：`https://fenics-llm.github.io/`
- FRAME（OpenReview）：`https://openreview.net/forum?id=2TdYc5V4jU`
- FEM-Bench：arXiv 检索 "FEM-Bench structured scientific reasoning benchmark"
- StructuralEval：`https://huggingface.co/datasets/superhatk/structural-eval-benchmark`
- SoM-1K：`https://arxiv.org/html/2509.21079v1`
- OpenTO/OpenOAT：`https://hf-mirror.com/datasets/OpenTO/OpenOAT`
- MMPDS：`https://www.matplus.eu/` ｜ NAFEMS P18：`https://www.nafems.org/publications/resource_center/p18/`

---

*本报告由公开网络检索整理，旨在为研究选题与数据获取提供地图。具体数据集的体量、格式、许可条款以各官方源最新发布为准。*
