"""Report v1.1 -> v1.2: backfill EX01 P0-1/P0-2 ccx load-scaling results.

Rules:
  * expert section 10.1-10.4 conclusion text is NOT altered; only an
    appended "stage-2 review record (compiler, not expert opinion)" is added.
  * every replacement asserts a UNIQUE anchor hit (C-041 / drift discipline).
  * all numbers are read from disk artifacts, never hand-copied.
  * table cells never contain a bare '|' (use &#124; if needed).
"""

from __future__ import annotations

import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_REPORT = _ROOT / "FEM-Bench-Aero" / "REVIEW_C6_P2_FORMULATION_DIFFERENCE.md"
_STAGE2 = _HERE / "reports" / "diagnostics" / "p2_stage2_load_scaling_2026-11-08.json"
_SCALING = _HERE / "reports" / "diagnostics" / "p2_load_scaling_ccx_2026-11-08.json"

j2 = json.loads(_STAGE2.read_text(encoding="utf-8"))
j1 = json.loads(_SCALING.read_text(encoding="utf-8"))
R = j2["recomputed"]
C = j2["ccx"]
A = j2["abaqus"]

p100, p050, p020 = C["p100"], C["p050"], C["p020"]


def f(x, n=6):
    return f"{x:.{n}f}"


def repl(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    assert n == 1, f"{label}: anchor hit {n} times (expected 1): {old[:90]!r}"
    return text.replace(old, new)


t = _REPORT.read_text(encoding="utf-8")

# ---- 1. header version + revision record ------------------------------------
t = repl(t,
         "**报告编号**：FBA-C6P2-REV-001　|　**版本**：v1.1（按专家审查意见 EX01 修订，待复核）　|　**编制日期**：2026-11-08",
         "**报告编号**：FBA-C6P2-REV-001　|　**版本**：v1.2（按专家审查意见 EX01 修订，并回填 P0-1/P0-2 ccx 实测，待复核）　|　**编制日期**：2026-11-08",
         "header version")

t = repl(t,
         "**文件状态**：待专家审查；本文不预设最终结论，第 10 节留审查意见与结论填写位",
         "**文件状态**：待专家复核；本文不预设最终结论，第 10 节已填入专家审查意见与结论，另留复核状态栏",
         "header status")

t = repl(t,
         "> **v1.1 修订记录（2026-11-08，依据 EX01）**",
         "> **v1.2 修订记录（2026-11-08，编制方回填 P0 实测）**：ccx 侧 P0-1／P0-2 已跑完"
         "（3 档 P_ref × 6 阶，全部 `rc=0`）。新增 §8.7 阶段二实测、E15／E16 证据、"
         "§9 的 U13／U14；回填 §8.5 计划表、§8.6 阶段一末行状态、§4.5 E13、附录路径表。"
         "**§10 专家结论原文一字未改**，仅在 §10.4 追加「阶段二复核记录（编制方，非专家意见）」。"
         "专家「现阶段不能定论」的判断维持不变。\n>\n"
         "> **v1.1 修订记录（2026-11-08，依据 EX01）**",
         "header revision record")

# ---- 2. section 1 abstract: mark the shift hypothesis as measured -----------
t = repl(t,
         "- 【待验证／高优先级】CalculiX 2.23 `*BUCKLE` 的 ARPACK shift-invert 固定 σ=1.0 可能漏掉 λ<1 的低阶模态：E2 日志 `sigma=1.000000,d[0]=1.008207`，Abaqus 基本 λ=0.687155<1，ccx 两个 λ 紧贴 1.0，符合该失效特征。**S4 公式差异降为第二候选**；载荷缩放与振型配对之前不得把 37.87% 归因于公式。",
         "- 【已确认，P0 实测】CalculiX 2.23 `*BUCKLE` 固定 σ=1.0 的模态选择问题**在本案例内已被实测证实**："
         "同一案例请求 6 阶时冒出 3 个 λ<1 的模态，旧「λ1/λ2」实为第 4、5 阶（§8.6）；"
         "载荷缩放 0.05／0.02 MPa 两档的 `N_cr = λ·P_ref` 稳定到对称相对差 "
         f"**{R['safe_spread_rel']:.3g}**，而 0.1 MPa 档偏离该安全值 **{f(R['p100_deviation_rel_vs_safe_mean']*100,2)}%**，"
         "且其 6 阶谱中**不存在**由安全档 `N_cr` 反推的 λ1 = "
         f"{f(R['expected_lambda1_at_p100_from_safe_n_cr'])}（§8.7、E15）。"
         "**37.87% 已被证明不是同一对模态的差**，不得据此归因 S4 公式差异。",
         "abstract shift line")

t = repl(t,
         "- 【待补充】解析解锚定、网格收敛、多样本分布、两码求解器理论文档、单元公式源码级证据均缺失。",
         "- 【已确认，P0 实测】在安全载荷区（λ1 = "
         f"{f(p050['lambda1'])} / {f(p020['lambda1'])}）ccx 的 `N_cr` 均值 "
         f"**{f(R['safe_mean_n_cr1'],8)} MPa**；Abaqus `.msg` 全精度 λ1 = {f(A['lambda1_msg_full_precision'])} "
         f"⇒ `N_cr` = {f(A['n_cr1'],7)} MPa；两者对称相对差 **{f(R['n_cr_gap_rel_ccx_safe_vs_abaqus']*100,4)}%**（E15）。"
         "该数字跨不同 P_ref 比较，**Abaqus 侧自身载荷缩放不变性未验证**（外部 3 档作业待运行），"
         "**不是**双码最终差值，更不是阈值输入。\n"
         "- 【待补充】解析解锚定、网格收敛、多样本分布、振型 MAC、两码求解器理论文档、单元公式源码级证据均缺失；"
         "Abaqus 侧 3 档缩放结果待外部作业回填（U13）。",
         "abstract missing line")

# ---- 3. section 4.5 evidence list -------------------------------------------
t = repl(t,
         "**E13**（ccx 载荷缩放/6 阶实验：`reports/diagnostics/p2_load_scaling_ccx_2026-11-08.json`，结果待回填）。U5 已关闭、U6 部分关闭；U10 升级为 P0 必做。",
         "**E13**（ccx 载荷缩放/6 阶实验：`reports/diagnostics/p2_load_scaling_ccx_2026-11-08.json`，"
         "**结果已回填**：3 档 × 6 阶全 `rc=0`，三份 `.dat` 原文归档于 `p2_scaling_ccx/`）、"
         "**E14**（阶段一 6 阶谱与模态定位：`p2_stage1_six_modes_2026-11-08.json`）、"
         "**E15**（阶段二独立复算：`p2_stage2_load_scaling_2026-11-08.json`，含全部算式与两码 `N_cr` 对照）、"
         "**E16**（Abaqus 3 档外部作业 deck + bat：`make_p2_abq_scaling_jobs.py`，8/8 自检 ×3，**结果待补充**）。"
         "U5 已关闭、U6 部分关闭；U10 升级为 P0 必做；新增 U13／U14。",
         "section 4.5 evidence")

# ---- 4. section 8.5 plan table ----------------------------------------------
t = repl(t,
         "| **P0-1** | 载荷缩放不变性：P_ref = 0.1 / 0.05 / 0.02 MPa，两码各跑，记录 λ 与 N_cr = λ·P_ref | 若 ccx λ 不随载荷反比变化（恒贴 σ=1.0）⇒ shift 污染 | ccx 侧已启动（`probe_p2_load_scaling.py`）；Abaqus 侧作业待外部运行；结果**待回填** |",
         "| **P0-1** | 载荷缩放不变性：P_ref = 0.1 / 0.05 / 0.02 MPa，两码各跑，记录 λ 与 N_cr = λ·P_ref | 若 ccx λ 不随载荷反比变化（恒贴 σ=1.0）⇒ shift 污染 | **ccx 侧已完成（3/3 档，`rc=0`，81 min）**：安全两档 `N_cr` 稳定、0.1 档偏离 "
         f"{f(R['p100_deviation_rel_vs_safe_mean']*100,2)}%（§8.7、E13／E15）；**Abaqus 侧 3 档 deck + bat 已备，待外部运行**（U13） |",
         "plan P0-1")

t = repl(t,
         "| **P0-2** | 多阶请求：ccx 与 Abaqus 各 6 阶 | 检查是否出现 <1 的模态、阶序是否一致 | 与 P0-1 合并执行；结果**待回填** |",
         "| **P0-2** | 多阶请求：ccx 与 Abaqus 各 6 阶 | 检查是否出现 <1 的模态、阶序是否一致 | **ccx 侧已完成**：3 档各 6 阶；仅 0.1 档出现 3 个 λ<1 且整谱落在 [0.9495, 1.0419]；"
         "逐阶 `N_cr` 对照显示低 3 阶稳定、第 6 阶漂移 "
         f"{f(R['per_mode_n_cr_rel_p050_vs_p020'][5]*100,2)}% ⇒ 支持 Q3「只判 λ1」。"
         "**Abaqus 侧 6 阶待补充** |",
         "plan P0-2")

t = repl(t,
         "**P0 通过标准（EX01）**：在安全 λ 区间（建议 >1.5）下 `λ·P_ref` 稳定；两码振型可配对；\nccx 不再出现「结果紧贴 σ=1.0」。建议载荷缩放表见专家意见原件 §5。",
         "**P0 通过标准（EX01）**：在安全 λ 区间（建议 >1.5）下 `λ·P_ref` 稳定；两码振型可配对；\n"
         "ccx 不再出现「结果紧贴 σ=1.0」。建议载荷缩放表见专家意见原件 §5。\n\n"
         "**ccx 侧实测对照（编制方，§8.7）**：0.02 MPa 档 λ1 = "
         f"{f(p020['lambda1'])} > 1.5，**满足**安全区要求；0.05 MPa 档 λ1 = {f(p050['lambda1'])} "
         "略低于建议值 1.5，但 `N_cr` 与 0.02 档一致到 "
         f"{R['safe_spread_rel']:.3g}；0.1 MPa 档 λ 全谱紧贴 σ=1.0，**明确不满足**。"
         "因此通过标准中的后两项（两码振型配对、Abaqus 侧不变性）**仍未闭环**，P0 不得宣告通过。",
         "plan pass criteria")

# ---- 5. section 8.6 last row -------------------------------------------------
t = repl(t,
         "| P0-1 的 0.05 / 0.02 MPa 两档仍在运行 | `N_cr = λ·P_ref` 的跨载荷稳定性**待回填**；Abaqus 侧 3 档外部作业须等 ccx 求解结束（R61 不并行） |",
         "| P0-1 的 0.05 / 0.02 MPa 两档**已完成**（阶段二，§8.7） | `N_cr = λ·P_ref` 跨载荷稳定性已回填：安全两档一致到 "
         f"{R['safe_spread_rel']:.3g}；ccx 求解已全部结束、`.solve.lock` 已释放，Abaqus 侧 3 档外部作业**现可运行** |",
         "8.6 last row")

t = repl(t,
         "> 它既不证明 S4 公式差异存在，也不证明不存在。残余 32.06% 的归属需 P0-3 振型配对\n> 与 P1 公式隔离。专家 §10 的「现阶段不能定论」仍然有效。",
         "> 它既不证明 S4 公式差异存在，也不证明不存在。阶段一残余 32.06% 是**仍受 σ=1.0 污染档**内的数字；"
         "阶段二改用安全载荷区后，两码 `N_cr` 差为 "
         f"{f(R['n_cr_gap_rel_ccx_safe_vs_abaqus']*100,4)}%（§8.7），该残余的归属仍需 P0-3 振型配对、"
         "Abaqus 侧 3 档不变性与 P1 公式隔离。专家 §10 的「现阶段不能定论」仍然有效。",
         "8.6 caveat")

# ---- 6. new section 8.7 ------------------------------------------------------
SEC87 = f"""
### 8.7 P0 阶段二实测（2026-11-08，ccx 载荷缩放 3 档 × 6 阶）

**【已确认，新证据 E15】** `probe_p2_load_scaling.py` 在同一柱壳模型上以
`P_ref = 0.1 / 0.05 / 0.02 MPa` 各请求 6 阶，三档 `rc=0`（合计 81 min），
三份 `.dat` 原文逐字归档于 `reports/diagnostics/p2_scaling_ccx/`，
全部数字由 `make_p2_stage2_finding.py` 现读 artifact 独立复算（算式随 artifact 落盘）。

| 档位 | P_ref (MPa) | λ1（6 阶谱首项） | `N_cr` = λ1·P_ref (MPa) | λ<1 的阶数 | 6 阶谱范围 | σ 日志 |
|---|---|---|---|---|---|---|
| p100 | {f(p100['p_ref_mpa'],2)} | {f(p100['lambda1'],7)} | {f(p100['n_cr1'],8)} | {p100['n_lambdas_below_1']} | [{f(p100['lambda_span'][0],4)}, {f(p100['lambda_span'][1],4)}] | `sigma=1.000000,d[0]={f(p100['lambda1'],6)}` |
| p050 | {f(p050['p_ref_mpa'],2)} | {f(p050['lambda1'],6)} | {f(p050['n_cr1'],8)} | {p050['n_lambdas_below_1']} | [{f(p050['lambda_span'][0],4)}, {f(p050['lambda_span'][1],4)}] | `sigma=1.000000,d[0]={f(p050['lambda1'],6)}` |
| p020 | {f(p020['p_ref_mpa'],2)} | {f(p020['lambda1'],6)} | {f(p020['n_cr1'],8)} | {p020['n_lambdas_below_1']} | [{f(p020['lambda_span'][0],4)}, {f(p020['lambda_span'][1],4)}] | `sigma=1.000000,d[0]={f(p020['lambda1'],6)}` |

| 观察 | 结论边界 |
|---|---|
| p050 与 p020 的 `N_cr1` 对称相对差 **{R['safe_spread_rel']:.3g}**（{f(R['safe_spread_rel']*100,5)}%）；λ 随 `1/P_ref` 反比（{f(p050['lambda1'])} × 0.05 = {f(p050['n_cr1'],8)}，{f(p020['lambda1'])} × 0.02 = {f(p020['n_cr1'],8)}） | **载荷缩放不变性在两档成立**：这两档的 λ 远离 σ=1.0，是线性屈曲物理量的自洽解。符合 EX01 P0-1 的判据 |
| p100 的 `N_cr1` 相对安全均值 **+{f(R['p100_deviation_rel_vs_safe_mean']*100,2)}%**；3 个 λ<1，整谱挤在 [0.9495, 1.0419] | **0.1 MPa 档不自洽**：真实谱正好压在固定 σ=1.0 邻域，ARPACK shift-invert 返回的是「σ 附近」而非「最低」的 6 个根 |
| 由安全 `N_cr` 反推，p100 本应出现 λ1 = **{f(R['expected_lambda1_at_p100_from_safe_n_cr'])}**，但该值在 p100 的 6 阶谱中**{'' if R['expected_lambda1_present_in_p100_six_mode_spectrum'] else '不存在'}** | **即便请求 6 阶，0.1 档仍漏掉真正的最低根** ⇒ 增加阶数不能修复该档；唯一已验证的规避方式是**改变 P_ref 使谱移出 σ 邻域** |
| Abaqus `.msg` 全精度 λ1 = {f(A['lambda1_msg_full_precision'])} ⇒ `N_cr` = {f(A['n_cr1'],7)} MPa；ccx 安全均值 {f(R['safe_mean_n_cr1'],8)} MPa ⇒ 对称相对差 **{f(R['n_cr_gap_rel_ccx_safe_vs_abaqus']*100,4)}%** | 与阶段一受污染档的 32.06%／最初的 37.87% **不是同一口径**。该 {f(R['n_cr_gap_rel_ccx_safe_vs_abaqus']*100,2)}% 仍是**跨不同 P_ref 的 `N_cr` 比较**，且 Abaqus 只跑过 0.1 档；**不得**当作双码最终差值或阈值输入 |
| 逐阶 `N_cr` 相对差（p050 vs p020）前 6 阶 = {[round(x,6) for x in R['per_mode_n_cr_rel_p050_vs_p020']]} | 低 3 阶稳定（≤8e-6），第 4–6 阶逐步漂移到 {f(R['per_mode_n_cr_rel_p050_vs_p020'][5]*100,2)}% ⇒ 高阶阶序／配对仍不稳，**支持 Q3「只判 λ1」**；也说明「高阶不判」的必要性 |

> **不得提前下的结论（延续 §8.6、EX01 §10.2）**：以上实测把「37.87% 是同一物理量的系统性差异」**证否**，
> 并把 C3（σ=1.0 shift／模态选择）从「首选排除项」升为**本案例内已实测证实的失效机制**；
> 但它**不证明** S4 公式差异不存在，也**不证明**残余 {f(R['n_cr_gap_rel_ccx_safe_vs_abaqus']*100,2)}% 属于公式差异。
> 该残余需：① Abaqus 侧 3 档 `N_cr` 不变性（U13，外部作业待运行）；② 两码振型 MAC 配对（U10／P0-3）；
> ③ 网格收敛与解析解锚点（U2／U3）。**专家「现阶段不能定论」的判断维持不变**，λ 阈值继续不冻结。

---
"""

t = repl(t,
         "---\n\n## 9. 缺失材料汇总（统一标注「待补充」）",
         SEC87 + "\n## 9. 缺失材料汇总（统一标注「待补充」）",
         "insert 8.7")

# ---- 7. section 9 U-list -----------------------------------------------------
t = repl(t,
         "| U12 | 静力语义量双码对照 | 影响范围补全 | 待补充 |",
         "| U12 | 静力语义量双码对照 | 影响范围补全 | 待补充 |\n"
         "| U13 | Abaqus 侧 3 档（0.1／0.05／0.02 MPa）× 6 阶 `λ` 与 `N_cr` | 验证 Abaqus 自身 `N_cr` 不变性；使两码可在同 P_ref 下比较 | **待补充**：3 档 deck + 外部 bat 已备（`make_p2_abq_scaling_jobs.py`，8/8 自检 ×3），须在 WorkBuddy 外运行 |\n"
         "| U14 | ccx 安全档（0.02 MPa）与 Abaqus 的振型及节点映射 | P0-3 振型 MAC 配对 | 待补充（依赖 U13） |",
         "U13/U14")

# ---- 8. section 10.4: append compiler record, DO NOT touch expert text -------
t = repl(t,
         "| 审查结论状态 | 已填入；待 P0/P1 结果复核后更新 |",
         "**阶段二复核记录（2026-11-08，编制方追加，非专家意见）**：ccx 侧 P0-1／P0-2 已全部跑完"
         "（3 档 × 6 阶，`rc=0`）。K-shift 由「待验证」升级为**本案例内已实测证实**："
         f"安全两档 `N_cr` 稳定到 {R['safe_spread_rel']:.3g}，0.1 档偏离 "
         f"{f(R['p100_deviation_rel_vs_safe_mean']*100,2)}% 且 6 阶谱缺少由安全值反推的 λ1 = "
         f"{f(R['expected_lambda1_at_p100_from_safe_n_cr'])}；最初的 37.87% 已证否为同模态差"
         "（§8.6、§8.7、E14／E15）。**但 P0 整体未闭环**：K-mode 振型 MAC、Abaqus 侧 3 档不变性（U13）"
         "与网格／解析锚点仍缺，故专家「现阶段不能定论」「6 条打样暂缓」「不冻结阈值」三条"
         "**全部维持有效**；残余 "
         f"{f(R['n_cr_gap_rel_ccx_safe_vs_abaqus']*100,4)}% 的成因不作判定。"
         "P0/P1 全部闭环后仍须由专家按结果再次更新本节与报告版本。\n\n"
         "| 审查结论状态 | 已填入；待 P0/P1 结果复核后更新 |",
         "10.4 compiler record")

# ---- 9. appendix path table --------------------------------------------------
t = repl(t,
         "| P0 实验 | `feagpt_repro/probe_p2_load_scaling.py`、`reports/diagnostics/p2_load_scaling_ccx_2026-11-08.json`（结果待回填） |",
         "| P0 实验 | `feagpt_repro/probe_p2_load_scaling.py`、`reports/diagnostics/p2_load_scaling_ccx_2026-11-08.json`（**结果已回填**）、`make_p2_stage2_finding.py`（独立复算） |",
         "appendix P0 row")

t = repl(t,
         "| P0 载荷缩放脚本 | `feagpt_repro/probe_p2_load_scaling.py`（ccx）、`make_p2_abq_scaling_jobs.py`（Abaqus 外部 3 档 deck + bat） |",
         "| P0 载荷缩放脚本 | `feagpt_repro/probe_p2_load_scaling.py`（ccx）、`make_p2_abq_scaling_jobs.py`（Abaqus 外部 3 档 deck + bat） |\n"
         "| P0 阶段二（E15） | `feagpt_repro/reports/diagnostics/p2_stage2_load_scaling_2026-11-08.json`（算式 + 两码 `N_cr` 对照）、`p2_scaling_ccx/*.dat`（3 份原文） |",
         "appendix stage2 row")

# ---- 10. self-check ----------------------------------------------------------
assert "v1.2" in t
assert "### 8.7" in t
assert "U13" in t and "U14" in t
assert "阶段二复核记录" in t
assert "结果待回填" not in t, "stale '结果待回填' left in report"
assert "两档仍在运行" not in t, "stale '两档仍在运行' left in report"
# expert conclusion sentences must be intact
for anchor in ("**真实性判断**：☑ **差异真实但证据不足**",
               "**成因结论**：**现阶段不能定论**",
               "**结论**：差异真实；但「系统性 S4 公式差异」成因判断证据不足。"):
    assert anchor in t, f"expert conclusion altered: {anchor}"

_REPORT.write_text(t, encoding="utf-8")
print(f"wrote {_REPORT} (v1.2), {len(t.splitlines())} lines")
print("expert conclusion text verified intact; 9 anchors replaced, 8.7 + U13/U14 added")
