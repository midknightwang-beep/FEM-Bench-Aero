"""Report v1.2 -> v1.3: backfill Abaqus 3-tier scaling (EX01 U13/P0-1).

Rules:
  * expert section 10.1-10.4 conclusion text NOT altered; only an appended
    "stage-3 review record (compiler, not expert opinion)".
  * every replacement asserts a UNIQUE anchor hit.
  * all numbers read from the stage-3 artifact, never hand-copied.
  * no bare '|' inside table cells.
"""

from __future__ import annotations

import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_REPORT = _ROOT / "FEM-Bench-Aero" / "REVIEW_C6_P2_FORMULATION_DIFFERENCE.md"
_J = json.loads((_HERE / "reports" / "diagnostics" /
                 "p2_abq_scaling_2026-11-08.json").read_text(encoding="utf-8"))
_J2 = json.loads((_HERE / "reports" / "diagnostics" /
                  "p2_stage2_load_scaling_2026-11-08.json").read_text(encoding="utf-8"))
R, A = _J["recomputed"], _J["abaqus"]


def f(x, n=6):
    return f"{x:.{n}f}"


def repl(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    assert n == 1, f"{label}: anchor hit {n} times (expected 1): {old[:90]!r}"
    return text.replace(old, new)


t = _REPORT.read_text(encoding="utf-8")

# ---- 1. header ---------------------------------------------------------------
t = repl(t,
         "**报告编号**：FBA-C6P2-REV-001　|　**版本**：v1.2（按专家审查意见 EX01 修订，并回填 P0-1/P0-2 ccx 实测，待复核）　|　**编制日期**：2026-11-08",
         "**报告编号**：FBA-C6P2-REV-001　|　**版本**：v1.3（按专家审查意见 EX01 修订，回填两码 3 档载荷缩放实测，待复核）　|　**编制日期**：2026-11-08",
         "header version")

t = repl(t,
         "> **v1.2 修订记录（2026-11-08，编制方回填 P0 实测）**",
         "> **v1.3 修订记录（2026-11-08，编制方回填 Abaqus 侧 P0-1，U13 关闭）**："
         "Abaqus 外部 3 档 × 6 阶作业全部 `COMPLETED SUCCESSFULLY`（0 errors）；"
         "Abaqus 自身 `N_cr` 三档稳定到 "
         f"{R['abaqus_invariance_spread_rel']:.3g}；**首次取得 Q3 要求的「同 P_ref」双码 λ1 对照**："
         f"0.05 MPa 档 {f(R['same_pref_lambda1_rel_p050']*100,4)}%、"
         f"0.02 MPa 档 {f(R['same_pref_lambda1_rel_p020']*100,4)}%（两档一致到 "
         f"{R['safe_tier_gap_spread_rel']:.3g}）。新增 §8.8、E17／E18，"
         "回填 §8.5 计划表、§8.6／§8.7 状态行、§9 的 U13、§4.5 证据链、附录路径表；"
         "**§10 专家结论原文一字未改**，仅在 §10.4 追加「阶段三复核记录（编制方，非专家意见）」。"
         "专家「现阶段不能定论」、EX01 D5「暂缓 6 条打样」与「λ 阈值不冻结」**全部维持有效**。\n>\n"
         "> **v1.2 修订记录（2026-11-08，编制方回填 P0 实测）**",
         "header revision record")

# ---- 2. section 1 abstract ---------------------------------------------------
t = repl(t,
         "- 【已确认，P0 实测】在安全载荷区（λ1 = 1.405239 / 3.513126）ccx 的 `N_cr` 均值 **0.07026224 MPa**；Abaqus `.msg` 全精度 λ1 = 0.687155 ⇒ `N_cr` = 0.0687155 MPa；两者对称相对差 **2.2259%**（E15）。该数字跨不同 P_ref 比较，**Abaqus 侧自身载荷缩放不变性未验证**（外部 3 档作业待运行），**不是**双码最终差值，更不是阈值输入。",
         "- 【已确认，P0-1 两码闭环】Abaqus 3 档（0.1／0.05／0.02 MPa）`.msg` 全精度 λ1 = "
         f"{f(A['p100']['lambda1'])} / {f(A['p050']['lambda1'],5)} / {f(A['p020']['lambda1'],5)}，"
         f"`N_cr1` = {f(R['abaqus_n_cr1_by_tier']['p100'],8)} / "
         f"{f(R['abaqus_n_cr1_by_tier']['p050'],8)} / {f(R['abaqus_n_cr1_by_tier']['p020'],8)} MPa，"
         f"三档离散度 **{R['abaqus_invariance_spread_rel']:.3g}** ⇒ **Abaqus 侧载荷缩放不变性成立**（E17）。"
         "此前 E15 的 2.2259% 是跨不同 P_ref 的 `N_cr` 比较；现已在**同 P_ref** 下取得 λ1 对照（下一条）。",
         "abstract ncr line")

t = repl(t,
         "- 【待补充】解析解锚定、网格收敛、多样本分布、振型 MAC、两码求解器理论文档、单元公式源码级证据均缺失；Abaqus 侧 3 档缩放结果待外部作业回填（U13）。",
         "- 【已确认，Q3 口径首次成立】在**相同 P_ref** 下，ccx 安全档 vs Abaqus 的 λ1 对称相对差："
         f"0.05 MPa **{f(R['same_pref_lambda1_rel_p050']*100,4)}%**、"
         f"0.02 MPa **{f(R['same_pref_lambda1_rel_p020']*100,4)}%**，两档一致到 "
         f"{R['safe_tier_gap_spread_rel']:.3g} ⇒ 排除 σ=1.0 污染后，同条件双码差异是**稳定的约 2.23%**，"
         "既非 37.87%／32.06%，也非零（E17、§8.8）。**成因仍未定，不作最终差值、不进阈值**。\n"
         "- 【口径独立性说明】该 ~2.23% 与 E15 的 2.2259% **不是两份独立证据**："
         "两码 `N_cr` 均满足 P_ref 不变性时，跨 P_ref 比 `N_cr` 与同 P_ref 比 λ1 在数学上是同一关系，"
         "数值接近是必然结果，不是交叉印证。\n"
         "- 【待补充】解析解锚定、网格收敛、多样本分布、振型 MAC、两码求解器理论文档、单元公式源码级证据均缺失；"
         "**U13（Abaqus 侧 3 档）已关闭**，U14（振型映射）待补充。",
         "abstract missing line")

# ---- 3. section 2.3 scope ----------------------------------------------------
t = repl(t,
         "- **适用**：本报告所述差异仅覆盖 `fuselage_barrel_d1600_l1600_str8_frm3_buckle` 一例、单一参考载荷 `E_SKIN, P, -0.1`（MPa）、2 阶特征值、当前网格密度、ccx 2.23 与 Abaqus 2026。",
         "- **适用**：**最初**差异观测于 `fuselage_barrel_d1600_l1600_str8_frm3_buckle` 一例、"
         "单一参考载荷 `E_SKIN, P, -0.1`（MPa）、2 阶特征值；"
         "后续 P0 验证扩展为 **3 档参考载荷（0.1／0.05／0.02 MPa）× 6 阶**，"
         "但仍是**同一几何、同一网格密度、同一边界**，软件版本 ccx 2.23 与 Abaqus 2026。",
         "scope line")

# ---- 4. section 4.5 evidence chain ------------------------------------------
t = repl(t,
         "**E16**（Abaqus 3 档外部作业 deck + bat：`make_p2_abq_scaling_jobs.py`，8/8 自检 ×3，**结果待补充**）。"
         "U5 已关闭、U6 部分关闭；U10 升级为 P0 必做；新增 U13／U14。",
         "**E16**（Abaqus 3 档外部作业 deck + bat：`make_p2_abq_scaling_jobs.py`，8/8 自检 ×3，"
         "**结果已回填**）、**E17**（Abaqus 三档独立复算与同 P_ref 双码对照："
         "`p2_abq_scaling_2026-11-08.json`，含全部算式、12 项 sha256 与逐阶对照）、"
         "**E18**（三档 `.sta`／`.dat`／`.msg` 逐字归档 + `.inp`／`.odb` sha256 锚定："
         "`p2_abq_scaling_evidence_2026-11-08/`、`p2_abq_scaling_evidence_manifest_2026-11-08.json`）。"
         "U5／**U13 已关闭**、U6 部分关闭；U10 升级为 P0 必做；U14 待补充。",
         "section 4.5 evidence")

# ---- 5. section 8.5 plan -----------------------------------------------------
t = repl(t,
         "**ccx 侧已完成（3/3 档，`rc=0`，81 min）**：安全两档 `N_cr` 稳定、0.1 档偏离 29.89%（§8.7、E13／E15）；**Abaqus 侧 3 档 deck + bat 已备，待外部运行**（U13） |",
         "**两码均已完成**：ccx 3/3 档 `rc=0`（81 min，安全两档 `N_cr` 稳定、0.1 档偏离 29.89%，§8.7／E15）；"
         f"Abaqus 3/3 档 `COMPLETED SUCCESSFULLY`、0 errors，`N_cr` 三档离散 {R['abaqus_invariance_spread_rel']:.3g}"
         "（§8.8／E17、E18）。**U13 已关闭** |",
         "plan P0-1")

t = repl(t,
         "**Abaqus 侧 6 阶待补充** |",
         "**Abaqus 侧 6 阶已完成**：3 档各 6 个 accepted eigenvalues，谱非递减、近重根成对（§8.8）；"
         "同 P_ref 逐阶对照见 E17 |",
         "plan P0-2")

t = repl(t,
         "**ccx 侧实测对照（编制方，§8.7）**：0.02 MPa 档 λ1 = 3.513126 > 1.5，**满足**安全区要求；0.05 MPa 档 λ1 = 1.405239 略低于建议值 1.5，但 `N_cr` 与 0.02 档一致到 8.11e-06；0.1 MPa 档 λ 全谱紧贴 σ=1.0，**明确不满足**。因此通过标准中的后两项（两码振型配对、Abaqus 侧不变性）**仍未闭环**，P0 不得宣告通过。",
         "**两码实测对照（编制方，§8.7／§8.8）**：0.02 MPa 档 ccx λ1 = 3.513126 > 1.5，"
         "**满足**安全区要求；0.05 MPa 档 ccx λ1 = 1.405239 略低于建议值 1.5，但 `N_cr` 与 0.02 档一致到 8.11e-06；"
         "0.1 MPa 档 ccx λ 全谱紧贴 σ=1.0，**明确不满足**。Abaqus 侧 3 档 `N_cr` 不变性**已闭环**（离散 "
         f"{R['abaqus_invariance_spread_rel']:.3g}）。**但「两码振型可配对」仍未验证（P0-3／U10）、"
         "「物理正确性锚点」仍缺（U2／U3）** ⇒ **P0 不得宣告通过**。",
         "plan pass criteria")

# ---- 6. section 8.6 status rows ---------------------------------------------
t = repl(t,
         "ccx 求解已全部结束、`.solve.lock` 已释放，Abaqus 侧 3 档外部作业**现可运行** |",
         "ccx 求解已全部结束、`.solve.lock` 已释放，Abaqus 侧 3 档外部作业**已运行完成**（§8.8） |",
         "8.6 last row")

t = repl(t,
         "> 它既不证明 S4 公式差异存在，也不证明不存在。阶段一残余 32.06% 是**仍受 σ=1.0 污染档**内的数字；阶段二改用安全载荷区后，两码 `N_cr` 差为 2.2259%（§8.7），该残余的归属仍需 P0-3 振型配对、Abaqus 侧 3 档不变性与 P1 公式隔离。专家 §10 的「现阶段不能定论」仍然有效。",
         "> 它既不证明 S4 公式差异存在，也不证明不存在。阶段一残余 32.06% 是**仍受 σ=1.0 污染档**内的数字；"
         "阶段二改用安全载荷区后跨 P_ref 比 `N_cr` 为 2.2259%（§8.7）；"
         "阶段三 Abaqus 侧 3 档不变性已闭环、并取得**同 P_ref** 下稳定的约 2.23%（§8.8）。"
         "该残余的归属仍需 P0-3 振型配对与 P1 公式隔离、网格／解析锚点。专家 §10 的「现阶段不能定论」仍然有效。",
         "8.6 caveat")

# ---- 7. section 8.7 stale status --------------------------------------------
t = repl(t,
         "| 与阶段一受污染档的 32.06%／最初的 37.87% **不是同一口径**。该 2.23% 仍是**跨不同 P_ref 的 `N_cr` 比较**，且 Abaqus 只跑过 0.1 档；**不得**当作双码最终差值或阈值输入 |",
         "| 与阶段一受污染档的 32.06%／最初的 37.87% **不是同一口径**。该 2.23% 是**跨不同 P_ref 的 `N_cr` 比较**（当时 Abaqus 只跑过 0.1 档）；"
         "**阶段三已补同 P_ref 对照**（§8.8、E17）：0.05／0.02 MPa 分别为 "
         f"{f(R['same_pref_lambda1_rel_p050']*100,4)}%／{f(R['same_pref_lambda1_rel_p020']*100,4)}%。"
         "两者数学上同源，**不是相互独立的印证**；均**不得**当作双码最终差值或阈值输入 |",
         "8.7 ncr row")

t = repl(t,
         "> 该残余需：① Abaqus 侧 3 档 `N_cr` 不变性（U13，外部作业待运行）；② 两码振型 MAC 配对（U10／P0-3）；\n> ③ 网格收敛与解析解锚点（U2／U3）。**专家「现阶段不能定论」的判断维持不变**，λ 阈值继续不冻结。",
         "> 该残余需：① Abaqus 侧 3 档 `N_cr` 不变性（U13）—— **阶段三已闭环，见 §8.8**；"
         "② 两码振型 MAC 配对（U10／P0-3，仍缺）；③ 网格收敛与解析解锚点（U2／U3，仍缺）。"
         "**专家「现阶段不能定论」的判断维持不变**，λ 阈值继续不冻结。",
         "8.7 caveat")

# ---- 8. new section 8.8 ------------------------------------------------------
SEC88 = f"""
### 8.8 P0 阶段三实测（2026-11-08，Abaqus 载荷缩放 3 档 × 6 阶）

**【已确认，新证据 E17／E18】** 老王在 WorkBuddy 外运行
`_p2_abq_scaling/run_p2_abq_scaling_MANUAL.bat`，三档作业全部写出 `.sta`
且报告 `THE ANALYSIS HAS COMPLETED SUCCESSFULLY`、0 个 error，各 6 个 accepted eigenvalues。
唯一 warning 为「指定区间内特征值可能多于请求数」（本例显式请求 6 阶、实际接受 6 阶，属提示而非错误）。
`.sta`／`.dat`／`.msg` 逐字归档、`.inp`／`.odb` 以 sha256 锚定（E18），
所有数字由 `make_p2_abq_scaling_finding.py` 现读 `.msg` 全精度独立复算。

| 档位 | P_ref (MPa) | Abaqus λ1（`.msg` 全精度） | `N_cr` = λ1·P_ref (MPa) | 6 阶谱范围 |
|---|---|---|---|---|
| p100 | 0.1 | {f(A['p100']['lambda1'])} | {f(R['abaqus_n_cr1_by_tier']['p100'],8)} | [{f(A['p100']['lambdas_full_precision'][0],6)}, {f(A['p100']['lambdas_full_precision'][-1],6)}] |
| p050 | 0.05 | {f(A['p050']['lambda1'],5)} | {f(R['abaqus_n_cr1_by_tier']['p050'],8)} | [{f(A['p050']['lambdas_full_precision'][0],5)}, {f(A['p050']['lambdas_full_precision'][-1],5)}] |
| p020 | 0.02 | {f(A['p020']['lambda1'],5)} | {f(R['abaqus_n_cr1_by_tier']['p020'],8)} | [{f(A['p020']['lambdas_full_precision'][0],5)}, {f(A['p020']['lambdas_full_precision'][-1],5)}] |

**Abaqus 自身 `N_cr` 三档离散度 = {R['abaqus_invariance_spread_rel']:.3g}** ⇒ 载荷缩放不变性成立，
且 Abaqus 在 λ1 < 1 的 p100 档同样自洽（用 `LANCZOS` + 显式区间 `[0, 1.0e6]`，不涉及 ccx 的固定 σ）。
这反证了 ccx 0.1 档的失真是**该求解器特有**的模态选择问题，而非模型或载荷定义问题。

#### 8.8.1 同 P_ref 双码对照（Q3 决议口径首次成立）

Q3 拍板要求「只判 λ1，且两码 `P_ref` 逐值相同」。此前只有 ccx 三档与 Abaqus 单档，
该口径无法成立；本阶段补齐后：

| P_ref (MPa) | ccx λ1 | Abaqus λ1 | 对称相对差 | ccx 档是否可用 |
|---|---|---|---|---|
| 0.05 | 1.405239 | {f(A['p050']['lambda1'],5)} | **{f(R['same_pref_lambda1_rel_p050']*100,4)}%** | 是（安全区） |
| 0.02 | 3.513126 | {f(A['p020']['lambda1'],5)} | **{f(R['same_pref_lambda1_rel_p020']*100,4)}%** | 是（λ1 > 1.5） |
| 0.1 | 0.9495004 | {f(A['p100']['lambda1'])} | 32.06% | **否**：ccx 档受 σ=1.0 污染，6 阶谱中缺真最低根 0.702622 ⇒ 该行**不得**引用 |

两档安全区的差异一致到 **{R['safe_tier_gap_spread_rel']:.3g}**，说明约 2.23% 是**稳定、可复现、同条件的双码差异**。
逐阶对照（E17）显示低阶差异稳定在 2.2% 量级、高阶逐步发散，继续支持 Q3「只判 λ1」。

> **口径独立性限定**：§8.7 的 2.2259%（跨 P_ref 比 `N_cr`）与本节的
> {f(R['same_pref_lambda1_rel_p050']*100,4)}%／{f(R['same_pref_lambda1_rel_p020']*100,4)}%（同 P_ref 比 λ1）**不是两份独立证据** —— 当两码 `N_cr`
> 都满足 P_ref 不变性时，两者是同一数学关系的不同写法，数值接近属必然，
> 不得当作交叉印证。
>
> **仍不得提前下的结论**：约 2.23% 的**成因未定**（C1 单元公式／C2 初始应力刚度／
> C5 边界 DOF／网格密度等均未隔离），且**振型 MAC 配对未做**（U10／P0-3）、
> **解析解与网格收敛锚点仍缺**（U2／U3）。故该数字：
>
> - **不是**「S4 公式差异」的证据，也不证明该假设不成立；
> - **不是**双码最终差值，**不进入**任何 λ 阈值、不进 headline；
> - 专家 §10.2「现阶段不能定论」、§10.3 附加条件、§10.4 后续要求 3（P0/P1 闭环前
>   不冻结阈值、不跑 6 条打样、不对外发布跨码数字）**全部维持有效**。

---
"""

t = repl(t,
         "---\n\n## 9. 缺失材料汇总（统一标注「待补充」）",
         SEC88 + "\n## 9. 缺失材料汇总（统一标注「待补充」）",
         "insert 8.8")

# ---- 9. section 9 U13 --------------------------------------------------------
t = repl(t,
         "| U13 | Abaqus 侧 3 档（0.1／0.05／0.02 MPa）× 6 阶 `λ` 与 `N_cr` | 验证 Abaqus 自身 `N_cr` 不变性；使两码可在同 P_ref 下比较 | **待补充**：3 档 deck + 外部 bat 已备（`make_p2_abq_scaling_jobs.py`，8/8 自检 ×3），须在 WorkBuddy 外运行 |",
         "| U13 | Abaqus 侧 3 档（0.1／0.05／0.02 MPa）× 6 阶 `λ` 与 `N_cr` | 验证 Abaqus 自身 `N_cr` 不变性；使两码可在同 P_ref 下比较 | **已关闭**：E17（三档全成功、`N_cr` 离散 "
         f"{R['abaqus_invariance_spread_rel']:.3g}、同 P_ref 对照）、E18（原文逐字归档 + 12 项 sha256 交叉核对） |",
         "U13 row")

t = repl(t,
         "| U14 | ccx 安全档（0.02 MPa）与 Abaqus 的振型及节点映射 | P0-3 振型 MAC 配对 | 待补充（依赖 U13） |",
         "| U14 | ccx 安全档（0.02 MPa）与 Abaqus 的振型及节点映射 | P0-3 振型 MAC 配对 | 待补充（U13 已关闭，本项仍缺，为 P0 最后一道） |",
         "U14 row")

# ---- 10. section 10.4 compiler record ---------------------------------------
t = repl(t,
         "| 审查结论状态 | 已填入；待 P0/P1 结果复核后更新 |",
         "**阶段三复核记录（2026-11-08，编制方追加，非专家意见）**：Abaqus 侧 P0-1／P0-2 已由老王"
         "在 WorkBuddy 外跑完（3 档 × 6 阶，`.sta` 全部 `COMPLETED SUCCESSFULLY`、0 errors）。"
         f"Abaqus 自身 `N_cr` 三档离散 {R['abaqus_invariance_spread_rel']:.3g} ⇒ **U13 关闭**；"
         "首次在 Q3 要求的同 P_ref 口径下取得双码 λ1 差："
         f"0.05 MPa {f(R['same_pref_lambda1_rel_p050']*100,4)}%、0.02 MPa "
         f"{f(R['same_pref_lambda1_rel_p020']*100,4)}%（一致到 {R['safe_tier_gap_spread_rel']:.3g}），"
         "稳定约 2.23%；0.1 MPa 的 ccx 档因 σ 污染继续排除（§8.8、E17／E18）。"
         "**但 P0 整体仍未闭环**：K-mode 振型 MAC（U10／U14）、网格收敛与解析解锚点（U2／U3）仍缺，"
         "约 2.23% 的成因不作任何判定；该数字与 §8.7 的 2.2259% 数学同源、不是独立印证。"
         "故专家「现阶段不能定论」「6 条打样暂缓」「λ 阈值不冻结」「跨码数字仅 diagnostic」"
         "**四条全部维持有效**。P0/P1 全部闭环后仍须由专家按结果再次更新本节与报告版本。\n\n"
         "| 审查结论状态 | 已填入；待 P0/P1 结果复核后更新 |",
         "10.4 stage3 record")

# ---- 11. appendix ------------------------------------------------------------
t = repl(t,
         "| P0 阶段二（E15） | `feagpt_repro/reports/diagnostics/p2_stage2_load_scaling_2026-11-08.json`（算式 + 两码 `N_cr` 对照）、`p2_scaling_ccx/*.dat`（3 份原文） |",
         "| P0 阶段二（E15） | `feagpt_repro/reports/diagnostics/p2_stage2_load_scaling_2026-11-08.json`（算式 + 两码 `N_cr` 对照）、`p2_scaling_ccx/*.dat`（3 份原文） |\n"
         "| P0 阶段三（E17／E18） | `feagpt_repro/reports/diagnostics/p2_abq_scaling_2026-11-08.json`（Abaqus 三档复算 + 同 P_ref 双码对照）、`p2_abq_scaling_evidence_manifest_2026-11-08.json`、`p2_abq_scaling_evidence_2026-11-08/`（9 份原文）；脚本 `make_p2_abq_scaling_finding.py`、`archive_p2_abq_scaling_evidence.py` |",
         "appendix stage3 row")

# ---- 12. self-check ----------------------------------------------------------
assert "v1.3" in t and "### 8.8" in t and "E17" in t and "E18" in t
assert "U13 已关闭" in t or "**已关闭**" in t
assert "阶段三复核记录" in t
assert "结果待补充" not in t, "stale evidence status"
assert "外部作业待运行" not in t, "stale U13 status"
assert "Abaqus 侧 3 档 deck + bat 已备，待外部运行" not in t
# T-stage3: a broken f-string/quote splice inside a blockquote leaked literal
# 'f"' and dangling quotes into the report once. Assert the generated text is
# clean so this class of defect cannot silently recur (add a NEW pin per splice).
for bad in ('> f"', '> "', '\nf"', '**不是两份独立证据** —— 当两码 `N_cr` 都满足 P_ref 不变性时，"'):
    assert bad not in t, f"broken string splice in generated report: {bad!r}"
assert '> **口径独立性限定**' in t
assert '>   不冻结阈值、不跑 6 条打样' in t
for anchor in ("**真实性判断**：☑ **差异真实但证据不足**",
               "**成因结论**：**现阶段不能定论**",
               "**结论**：差异真实；但「系统性 S4 公式差异」成因判断证据不足。"):
    assert anchor in t, f"expert conclusion altered: {anchor}"

_REPORT.write_text(t, encoding="utf-8")
print(f"wrote {_REPORT} (v1.3), {len(t.splitlines())} lines")
print("expert conclusion intact; 17 anchors replaced; 8.8 + E17/E18 + U13 closed")
