"""Land EX01 P0-1 Abaqus-side stage-3 results into SOT docs and memory.

Unique-anchor replacements; all numbers read from disk artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_J = json.loads((_HERE / "reports" / "diagnostics" /
                 "p2_abq_scaling_2026-11-08.json").read_text(encoding="utf-8"))
R, A = _J["recomputed"], _J["abaqus"]


def f(x, n=6):
    return f"{x:.{n}f}"


def edit(path: Path, pairs: list[tuple[str, str, str]]) -> None:
    t = path.read_text(encoding="utf-8")
    for old, new, label in pairs:
        n = t.count(old)
        assert n == 1, f"{label}: anchor hit {n} times: {old[:80]!r}"
        t = t.replace(old, new)
    path.write_text(t, encoding="utf-8")
    print(f"  updated {path.relative_to(_ROOT)} ({len(pairs)} anchors)")


def append(path: Path, text: str) -> None:
    t = path.read_text(encoding="utf-8")
    path.write_text(t.rstrip("\n") + "\n" + text, encoding="utf-8")
    print(f"  appended {path.relative_to(_ROOT)} (+{len(text.splitlines())} lines)")


spread = f"{R['abaqus_invariance_spread_rel']:.3g}"
g50 = f"{R['same_pref_lambda1_rel_p050']*100:.4f}%"
g20 = f"{R['same_pref_lambda1_rel_p020']*100:.4f}%"
gapspread = f"{R['safe_tier_gap_spread_rel']:.3g}"

# ---------------------------------------------------------------- DESIGN ----
edit(_ROOT / "FEM-Bench-Aero" / "DESIGN_C6_P2_BUCKLE.md", [
    ("- **仍未闭环**：P0-3 振型 MAC；**Abaqus 侧 3 档 × 6 阶**（deck + 外部 bat 已备，8/8 自检 ×3，"
     "ccx 求解已结束、锁已释放 ⇒ 现可运行）；网格收敛／解析解锚点。",
     "- **U13 已关闭（2026-11-08 下午，阶段三）**：Abaqus 3 档 × 6 阶外部作业全部 "
     "`COMPLETED SUCCESSFULLY`、0 errors；`N_cr1` = "
     f"{f(R['abaqus_n_cr1_by_tier']['p100'],8)} / {f(R['abaqus_n_cr1_by_tier']['p050'],8)} / "
     f"{f(R['abaqus_n_cr1_by_tier']['p020'],8)} MPa，三档离散 **{spread}** ⇒ "
     "Abaqus 自身载荷缩放不变性成立（E17／E18，`.sta`/`.dat`/`.msg` 逐字归档 + 12 项 sha256）。"
     "**Q3 口径首次成立**：同 P_ref 下双码 λ1 对称相对差 0.05 MPa **" + g50 +
     "**、0.02 MPa **" + g20 + "**，一致到 " + gapspread + " ⇒ 稳定约 2.23%；"
     "0.1 MPa 的 ccx 档继续排除（σ 污染，6 阶谱缺真最低根 0.702622）。\n"
     "  **诚实边界**：该 ~2.23% 与 §11.4 的跨 P_ref 2.2259% **数学同源，不是独立印证**；"
     "成因未定（C1/C2/C5/网格未隔离），不作最终差值、不进阈值、不进 headline。\n"
     "- **仍未闭环**：P0-3 振型 MAC（U10／U14，现为 P0 最后一道）；网格收敛／解析解锚点（U2/U3）。",
     "DESIGN 11.4"),
])

# --------------------------------------------------------------- ROADMAP ----
edit(_ROOT / "FEM-Bench-Aero" / "ROADMAP.md", [
    ("下一步 = **Abaqus 外部 3 档 bat（现可运行，ccx 全停）→ 振型 MAC（P0-3）→ 网格/解析锚点**，"
     "P0 全闭环后才谈判据与 6 条打样",
     "**阶段三 Abaqus 侧 3 档已跑完（2026-11-08 下午）**：`.sta` 全 `COMPLETED SUCCESSFULLY`、0 errors，"
     f"Abaqus 自身 `N_cr` 三档离散 **{spread}**（U13 关闭）；**Q3 同 P_ref 口径首次成立**，"
     f"双码 λ1 差 0.05 MPa **{g50}** / 0.02 MPa **{g20}**（一致到 {gapspread}）⇒ 排除 σ 污染后"
     "稳定约 **2.23%**，成因未定、不进阈值；报告 v1.3（§8.8、E17/E18，专家 §10 原文未改）；"
     "下一步 = **振型 MAC（P0-3／U14，P0 最后一道）→ 网格收敛 + 解析解锚点（U2/U3）**，"
     "P0 全闭环后才谈判据与 6 条打样",
     "ROADMAP C6"),
])

# ------------------------------------------------------------------ DATA ----
append(_ROOT / "FEM-Bench-Aero" / "DATA.md", f"""

### 7.11 阶段三：Abaqus 侧载荷缩放闭环与报告 v1.3（2026-11-08 下午）

- **送审件升版**：`REVIEW_C6_P2_FORMULATION_DIFFERENCE.md` **v1.3**（674 行），新增 §8.8 阶段三、
  §8.8.1 同 P_ref 双码对照、E17／E18；U13 **已关闭**、U14 标为 P0 最后一道；
  回填 §8.5 计划表、§8.6／§8.7 状态行、§4.5 证据链、§2.3 适用范围、附录路径表。
  **§10 专家结论原文一字未改**，仅在 §10.4 追加「阶段三复核记录（编制方，非专家意见）」。
- **Abaqus 3 档 × 6 阶**（老王在 WorkBuddy 外跑 `run_p2_abq_scaling_MANUAL.bat`）：三档 `.sta` 全部
  `COMPLETED SUCCESSFULLY`、0 errors、各 6 个 accepted eigenvalues；唯一 warning 是「区间内特征值
  可能多于请求数」（显式请求 6 阶、接受 6 阶，属提示）。
  `N_cr1` = {f(R['abaqus_n_cr1_by_tier']['p100'],8)} / {f(R['abaqus_n_cr1_by_tier']['p050'],8)} /
  {f(R['abaqus_n_cr1_by_tier']['p020'],8)} MPa，三档离散 **{spread}** ⇒ **Abaqus 自身不变性成立**，
  且 λ1<1 的 0.1 档同样自洽（LANCZOS + 显式区间 `[0, 1.0e6]`，不涉及 ccx 的固定 σ）。
- **Q3 口径首次成立**：同 P_ref 下双码 λ1 对称相对差 0.05 MPa **{g50}**、0.02 MPa **{g20}**，
  一致到 {gapspread} ⇒ 排除 σ 污染后差异稳定约 **2.23%**；0.1 MPa 的 ccx 档**继续排除**
  （谱中缺真最低根 0.702622），该档 32.06% 不得引用。
- **口径独立性**：§7.10 的 2.2259%（跨 P_ref 比 `N_cr`）与本节同 P_ref 的 {g50}/{g20}
  是同一数学关系的不同写法，**不是两份独立证据**，不得当交叉印证。
- **产物**：`reports/diagnostics/p2_abq_scaling_2026-11-08.json`（算式 + 12 项 sha256 + 逐阶对照）、
  `p2_abq_scaling_evidence_manifest_2026-11-08.json`、`p2_abq_scaling_evidence_2026-11-08/`
  （9 份 `.sta`/`.dat`/`.msg` 原文）；脚本 `make_p2_abq_scaling_finding.py`、
  `archive_p2_abq_scaling_evidence.py`、`apply_p2_stage3_revisions.py`。
- **口径不变**：成因未定；**P0 未闭环**（MAC／网格／解析锚点仍缺）⇒ 6 条打样继续暂缓（D5）、
  λ 阈值不冻结、跨码数字仅 diagnostic。专家「现阶段不能定论」维持有效。
""")

# ---------------------------------------------------------------- MEMORY ----
edit(_ROOT / ".workbuddy" / "memory" / "MEMORY.md", [
    ("- **下一步 = P0 剩余三项**：① Abaqus 外部 3 档 bat（ccx 已停、锁已释放，**现可运行**）；"
     "② 振型 MAC（P0-3／U10）；③ 网格收敛 + 解析解锚点（U2/U3）。",
     "- **U13 已关闭（2026-11-08 下午，阶段三）**：Abaqus 3 档 × 6 阶外部作业全成功，"
     f"自身 `N_cr` 三档离散 **{spread}**（LANCZOS + 显式区间，不受 σ=1.0 影响）；"
     "**Q3 同 P_ref 口径首次成立**：双码 λ1 差 0.05 MPa **" + g50 + "**、0.02 MPa **" + g20 +
     "**，一致到 " + gapspread + " ⇒ 排除 σ 污染后稳定约 **2.23%**；0.1 MPa ccx 档继续排除。"
     "报告 v1.3（§8.8、E17/E18，专家 §10 原文未改）。**★ 口径独立性**：与跨 P_ref 的 2.2259% "
     "数学同源、不是独立印证。**成因仍未定**，不作最终差值、不进阈值。\n"
     "- **下一步 = P0 剩余两项**：① 振型 MAC（P0-3／U14，现为 P0 最后一道）；"
     "② 网格收敛 + 解析解锚点（U2/U3）。",
     "MEMORY next"),
])

# ------------------------------------------------------------- daily log ----
append(_ROOT / ".workbuddy" / "memory" / "2026-11-08.md", f"""

## 五节：P0 阶段三 Abaqus 三档闭环 + 报告 v1.3（2026-11-08 下午）

- **线名+实体**：EX01 的 U13／P0-1 Abaqus 侧载荷缩放，`run_p2_abq_scaling_MANUAL.bat`（老王在 WorkBuddy 外跑，3 档 × 6 阶）；送审报告 v1.3。
- **★ 三档全绿**：`.sta` 全部 `THE ANALYSIS HAS COMPLETED SUCCESSFULLY`、0 errors、各 6 个 accepted eigenvalues；
  `.msg` 全精度 λ1 = {f(A['p100']['lambda1'])} / {f(A['p050']['lambda1'],5)} / {f(A['p020']['lambda1'],5)}
  ⇒ `N_cr1` = {f(R['abaqus_n_cr1_by_tier']['p100'],8)} / {f(R['abaqus_n_cr1_by_tier']['p050'],8)} /
  {f(R['abaqus_n_cr1_by_tier']['p020'],8)} MPa，**三档离散 {spread}** ⇒ Abaqus 自身 `N_cr` 不变性成立。
  λ1<1 的 0.1 档同样自洽 ⇒ ccx 0.1 档失真是**该求解器特有**的 σ=1.0 模态选择问题，不是模型/载荷定义问题。
- **★ Q3 口径首次成立**：同 P_ref 下双码 λ1 对称相对差 0.05 MPa **{g50}**、0.02 MPa **{g20}**，
  一致到 {gapspread} ⇒ 排除 σ 污染后是**稳定约 2.23%** 的同条件差异；0.1 MPa ccx 档（谱缺 0.702622）继续排除，
  该档 32.06% 不得引用。**口径独立性**：与四节的跨 P_ref 2.2259% 数学同源、不是两份独立证据。
- **诚实边界**：~2.23% 成因未定（C1 单元公式／C2 初始应力刚度／C5 边界 DOF／网格均未隔离）；
  振型 MAC、网格收敛、解析锚点仍缺 ⇒ **P0 未闭环、专家「现阶段不能定论」有效、
  6 条打样继续暂缓、λ 阈值不冻结、跨码数字仅 diagnostic**。
- **产物**：`p2_abq_scaling_2026-11-08.json`（算式 + sha256 + 逐阶对照）、
  `p2_abq_scaling_evidence_manifest_2026-11-08.json`（12/12 sha256 交叉核对）、
  `p2_abq_scaling_evidence_2026-11-08/`（9 份原文）；脚本 `make_p2_abq_scaling_finding.py`、
  `archive_p2_abq_scaling_evidence.py`、`apply_p2_stage3_revisions.py`；报告 v1.3（674 行，§8.8／E17/E18，U13 关闭）。
- **★★ 踩坑（第二次同类）**：`apply_p2_stage3_revisions.py` 的 §8.8 引用块混用 f-string 与普通字符串拼接，
  把裸 `f"`／悬空引号／断行写进报告（首次执行后实读才发现）。修法：① 脚本根因改为单一 f-string；
  ② 报告正文用精确 Edit 修复；③ 脚本加防复发断言（禁用 `> f"`、`> "` 等 4 类残留）；
  ④ **等价性验证**——从 git 取 v1.2 原文重跑脚本，与磁盘 v1.3 逐字节比对，第一次只差 4 行折行、
  统一后 `byte-identical=True`。问句：**交付件能不能由入库脚本逐字节重建？**
- **数值微差如实记录**：新 6 阶 p100 λ1 = {f(A['p100']['lambda1'])}，旧 2 阶作业 0.687155，差 1e-6
  （请求阶数不同），两者都远离 ccx p100 的 0.9495004。
- **闸**：负控 87/87、claims 36/83/63、roadmap 自检、EOL 0、提交闸 G0–G6。
- 检索词：U13 关闭、Abaqus 三档全绿、N_cr 离散 1.46e-06、同 P_ref 2.2255%/2.2261%、
  报告 v1.3、f-string 拼接污染、等价性验证、P0 最后一道 MAC。
""")

print("all SOT docs + memory landed")
