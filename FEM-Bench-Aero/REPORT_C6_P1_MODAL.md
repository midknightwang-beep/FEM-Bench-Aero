# C6-P1 模态打样收口报告（2026-11-07）

> 范围：C6 的 **P1 阶段**（模态先行、独立 v2 线、8 条翼盒打样）。
> 性质：**pilot / diagnostic**。全部数字不进对外 headline，headline 仍是 C-032。
> 数字出处一律指向 git 追踪的 artifact（见 §9），本文件不手抄可复算的量。

## 0. 一句话结论

模态题**可解、可判、可复现**：两模型在修正后的同一条管线上，凡是物理求解跑通的条目
f1 相对差全部为 0.0；剩下的失分不在模态求解，而在 **spec 转写的字段保真**
（模型自创材料键、润色 description）。同时，第一轮实测反过来揪出并修掉了
三处我方考卷/判分缺陷——这是打样轮最有价值的产出。

## 1. 范围与拍板链

| 日期 | 拍板 | 内容 |
|---|---|---|
| 2026-11-06 晚 | C6 四点 | P1 模态先行 / 形态 A 独立 v2 线 / 6–8 条打样 / λ 与 f 阈值先测后定 |
| 2026-11-07 | C6-P1 四点 | `modeling_v2/` 根目录 / 8 条选材 / ARPACK / odb_batch solve 段复用 |
| 2026-11-07 | 阈值方案 A | **f1 < 1% 硬判**；高阶只记不判 |
| 2026-11-07 | 高阶差异方案 A | 高阶差异定性为**公式级**（ccx 膨胀实体 vs abq 真壳，假设未验证）；收口 f1 + **同码自比** + 不立项深挖 |
| 2026-11-07 深夜 | 死键方案 A | **修卷剥键 + 重冻结**（详见 §5） |

## 2. 实现链

| 环节 | 文件 | 关键验证 |
|---|---|---|
| spec 扩展 | `feagpt/spec.py` | `n_modes`（默认 5，零扰动）；静力基准 deck 与 v1.1 存档 sha 逐字节一致 |
| 双码 deck | `feagpt/inp_writer.py` | ccx `*FREQUENCY` + `NODE FILE U`；abaqus `*FREQUENCY, EIGENSOLVER=LANCZOS` + `*OUTPUT, FIELD`（**无 NUMBER INTERVAL**，模态步非法）；`5, 0.0, 1.0e5`（`0,0` 不是自动移位，是占位零值） |
| 谱提取 | `extract_modal_dat.py` | 13 pins；ccx 5 列 / abaqus 6 列、横幅先于真表的误命中已修；真机 pin √38832=197.06 → 31.363 Hz |
| 8 条打样 | `make_v2_modal_cases.py` | `--deck / --solve-ccx / --extract / --summary / --n-modes`；10 模态复测 8/8 唯一 diff = 数据行 5→10 |
| 双码交叉差 | `make_v2_cross_diff.py` | 40 对逐序号；f1 median 0.23%、max 0.73%（8/8 < 1%）；f2–f5 0.1%–16.4% |
| 真值 / 考卷 / 判分 | `make_v2_truth.py` / `make_v2_tasks.py` / `score_v2_modal.py` | truth 全部现读生成；判分器四闸（contract / 递归全键 spec_fidelity / pipeline / modal_f1），self-test **10/10**，gold 自比冒烟四闸全绿 |

**ODB 真机验收**（同日）：`stiffened_panel_600x600_s0/_s3` 2/2 ok，36 N 平衡自证
（RF 合力 vs 解析 ~1e-8）；三坑（WinError 2 → `--abaqus-cmd`；ccx 血统 inp 的
`OUTPUT=2D` 原生 Abaqus 不认 → 验收副本剥参数；`.sta` 闸实战首拦截假 rc=0）
见 `README_ODB_TOOLS.md`「真机验收实录」。

## 3. 判据口径（写死，不许口头放宽）

1. **f1 对称相对差 < 1%** 为唯一频率硬判；阈值边界数学：`c=r(1+d)` 时
   `rel = d/(1+d/2)`，超阈需 `d > t/(1-t/2) = 1.00503%`（这个边界 pin 修过三次）。
2. **高阶（f2+）只记不判**：两码的 S4 公式级差异未消；不做跨码配对、不排名。
3. **同码自比**：候选 spec 与参考 spec 走同一条 `run_pipeline` + 同一 ccx，
   公式差异在差值中自动抵消（实测 f1_rel 全 0.0）。
4. **spec_fidelity 递归全键**（N-35 教训）：不按族列清单，缺键与多键双向都红；
   打样轮严格判，不留豁免名单。
5. **谱健全性**：10 阶、正值、严格单调递增，与 f1 并列成闸。
6. **headline 不切**：v2 全部数字 diagnostic，不与 v8 卷、L2/L3 指标并列成表。

## 4. 卷冻结与考卷接入

- 冻结集：`FEM-Bench-Aero/modeling_v2/SHA256SUMS.txt`（**74 文件**，复算 74/74）；
  8 条 case 各含 spec / step / msh / inp / _abq.inp / dat / _abq.dat / modal.json / truth.json。
- 考卷：`feagpt_repro/tasks/tasks_v2_modal.jsonl`（8 条，L1 形状），
  `input.spec_normalized` 现读 gold（只去 `workdir`）。
- 候选生成：`gen_candidates_v2.js` 的 L1 分支复刻 v1.1 L1 呈现（拆块 + name/description
  逐字照抄 + analysis 三块照抄）；SYS 一个字节未动（`6b90daf0`），
  与 v1.1 L1 同 prompt sha。
- `--no-schema-validate`：`schema_task.json` 的 mesh/analysis 键集合比 v2 gold 窄
  （`element_order` 等 7 键 + `n_modes` 被判 additionalProperties），
  修复循环会把「照抄 gold」逼成删键 ⇒ 判分权威交给 FEASpec contract 闸。
  **默认不传参时行为逐字节不变**。
- 分发加固：冻结件统一 CRLF 后再生成清单（换机 clone 后 sha 才对得上）；
  `SHA256SUMS.txt` 在 `.gitattributes` 钉 `eol=lf`（否则 `sha256sum -c` 读到 `\r` 找不到文件）。

## 5. 第一轮实测：修掉的三处我方缺陷

第一轮 glm 0/8、ds 0/8，但 **contract / pipeline 16/16 全过**、凡是 name 抄对的条目
f1_rel 都是 0.0 —— 红的全不在模型能力，而在我们出的卷与判分链：

| # | 缺陷 | 实锤 | 修法 |
|---|---|---|---|
| 1 | 考卷 strip `airfoil` | 生成脚本注释声称「v1.1 convention」，实测 v1.1 L1 wingbox **39/39 全带 airfoil**；考卷不给几何，模型照抄也必红 | `_STRIP_TOP` 只留 `workdir`，考卷重生成，8/8 与 gold 逐键一致 |
| 2 | gold 死键 31 个 | 8/8 带长桁细节键（7 条 `n_stringers_per_skin=0` 死键 + str3 的 `stringer_flange_width` 被 `blade()` 忽略且 SYS 禁止），另有 `extra.sweep_index` / `end_torque` / `torque_axis_dof` 自创键 ⇒ 模型守 SYS 不写反被判红（判据 supply 链断裂） | `make_v2_strip_dead_keys.py` 剥键；**deck sha 8/8 逐位一致**证明对求解输入零影响（truth 无需重出、不占求解锁）；SHA256SUMS 重算 74/74 |
| 3 | 模型 name 劫持产物路径 | run_pipeline 按 spec.name 建目录，name 错 ⇒ 判分器按 case_name 找不到 `.dat`，7/8 条 modal_f1 假红 | 判分器 pipeline 闸前 `raw["name"]=case_name` 归一（spec_fidelity 先判 name，归一只修路径不改判定） |

### 修正后的第一轮成绩

| 模型 | 通过 | 红因 | f1_rel |
|---|---|---|---|
| deepseek-v4-pro | **8/8** | 无 | 全 0.0 |
| glm-5.3-flash | **6/8** | 材料块自创键 `E`（contract 拒）+ description 措辞漂移 | 跑通条目全 0.0 |

成绩单：`reports/diagnostics/v2_modal_pilot_run1_2026-11-07.json`。

## 6. 第二遍稳定性归因

同卷、同 prompt sha、同模型、同参数（temperature=0、max_turns=3）独立重跑 glm 8 条：

| 条目 | 第一遍 | 第二遍 | 稳定性 |
|---|---|---|---|
| 其余 6 条 | 绿 | 绿 | stable_green |
| `naca4412_wingbox_modal`（`E` 键） | 红 | 绿 | **fluctuating：单次波动** |
| `naca4412_wingbox_taper060_modal`（description） | 红 | 红 | **stable 2/2：系统性行为** |

- **E 键错误**只在第一遍出现（temperature=0 的云服务仍有非确定性）⇒ 不是稳定缺陷。
- **description 漂移**两遍逐字相同（`NACA4412` → `NACA 4412`）：呈现已明写「逐字照抄」，
  模型仍对自然语言字段做「顺手润色」⇒ **元数据字段保真是系统性弱点，不是噪声**。
- 两遍 f1_rel 全 0.0；glm 总分 **6/8 → 7/8**。
- 按「两遍区间重叠不得排名」纪律：**glm 记为 `[6,7]/8`，任一遍都不得单独引用为成绩**；
  ds 8/8 只有一遍，pilot 不对外，同样不单独引用。

对照表：`reports/diagnostics/v2_modal_pilot_stability_2026-11-07.json`。
其中 `freeze_bridge` 段说明：第一遍成绩单里的冻结 sha `0aa7e3e3` 是运行后、提交前
EOL 规范化**之前**的值；规范化只改行尾与清单内容（74/74 重算），卷语义与 deck 字节未变，
两遍同卷，不回写已入库的第一遍 artifact。

## 7. 诚实边界与未决

1. **S4 假设未验证**：ccx 的 S4 是否内部膨胀成 3D 实体、abaqus 是否真壳 Mindlin，
   只作解释性假设，按拍板不立项深挖；高阶差异因此不进任何判据。
2. **L1 呈现 = 转写题**：本轮考的是「把给定 spec 原样转写并跑通模态求解」，
   不是自主建模、不是从 NL 发现需求。不能把 8/8 读成「模型会做模态分析」。
3. **description 该不该硬判，尚未拍板**：它不影响任何求解结果。
   继续硬判 ⇒ glm 稳定 7/8；改为元数据豁免 ⇒ 需另配「防豁免放水」的反向闸（R69）。
   **这是收口后的第一个岔路口，建议先拍板再扩卷。**
4. **glm 波动**：temperature=0 非确定性已实测；pilot 若要出可比数字，
   两模型都需多遍并报区间/一致率（参考拒答卷 C-042 的口径）。
5. **ODB / Abaqus 侧**：8 条打样的 abaqus 谱只作交叉差诊断，判分链只用 ccx；
   真机验收只在 2 条加筋板静力案例上做过。

## 8. 门禁状态（收口时）

- 负控 **87/87**；`check_claims` **36 claims / 83 artifacts / 63 语义项全过**；
  `check_commit.py --audit` 通过；`roadmap_selfcheck.py` ok。
- 提交：`2345332`（第一轮 + 三处缺陷修正 + 卷重冻结），已推送。

## 9. 可复现命令

```bash
cd F:/AI FEA Modeling DataSets/feagpt_repro
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
cd ../FEM-Bench-Aero/modeling_v2 && sha256sum -c SHA256SUMS.txt   # 74/74
cd ../../feagpt_repro
"$PY" score_v2_modal.py --self-test                               # 10/10
node gen_candidates_v2.js --tasks tasks/tasks_v2_modal.jsonl --levels L1 \
  --limit 8 --out candidates_v2_modal_<tag> --model <id> --no-schema-validate
"$PY" score_v2_modal.py --candidate-dir candidates_v2_modal_<tag> \
  --out-root eval_runs_v2_<tag>
"$PY" negative_controls.py && "$PY" check_claims.py --json "$TEMP/check_claims_preflight.json"
```

## 10. 执行摘要

- **P1 目标已达成**：双码模态打样 8 条、阈值实测后定、卷冻结、考卷接入、LLM 两模型首测全链走通。
- **关键结论**：模态求解本身零问题（f1_rel 全 0.0）；第一轮 0/8 是三处我方缺陷，已全部修正并有硬证据（deck sha 8/8 逐位一致）；修正后 ds 8/8、glm `[6,7]/8`。
- **真正的发现**：剩下的失分集中在 spec 元数据字段保真（模型润色 description）、以及 temperature=0 下的单次波动；这两条决定下一轮的判据口径，不决定模型能力。
- **下一单建议（待老王拍板）**：① description 是否继续硬判（推荐：继续硬判，不为一个字段开口子；代价是 glm 稳定 7/8）；② 之后才是 C6-P2 扩卷（柱壳/加筋板 + 自主建模题）。**先①后②，不并行。**
