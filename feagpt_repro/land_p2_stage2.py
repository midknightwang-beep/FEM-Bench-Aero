"""Land EX01 P0 stage-2 results into SOT docs and memory (2026-11-08).

All replacements assert a UNIQUE anchor. Numbers are read from the stage-2
artifact, never hand-copied. No shell heredoc => no backtick substitution.
"""

from __future__ import annotations

import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_J = json.loads((_HERE / "reports" / "diagnostics" /
                 "p2_stage2_load_scaling_2026-11-08.json").read_text(encoding="utf-8"))
R, C, A = _J["recomputed"], _J["ccx"], _J["abaqus"]


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


safe = f"{R['safe_spread_rel']:.3g}"
dev = f"{R['p100_deviation_rel_vs_safe_mean'] * 100:.2f}%"
gap = f"{R['n_cr_gap_rel_ccx_safe_vs_abaqus'] * 100:.4f}%"
exp = f"{R['expected_lambda1_at_p100_from_safe_n_cr']:.6f}"

# ---------------------------------------------------------------- DESIGN ----
edit(_ROOT / "FEM-Bench-Aero" / "DESIGN_C6_P2_BUCKLE.md", [
    ("- **结果待回填**：P0-1/P0-2 的 λ、`N_cr`、是否出现 <1 模态；P0-3 振型 MAC 仍待补充。",
     "- **P0-1／P0-2 ccx 侧已完成（2026-11-08，见送审报告 §8.7、E15）**：3 档 × 6 阶全 `rc=0`；"
     f"安全两档（0.05／0.02 MPa）`N_cr1` = {f(C['p050']['n_cr1'],8)} / {f(C['p020']['n_cr1'],8)} MPa，"
     f"对称相对差 {safe}；0.1 MPa 档 {f(C['p100']['n_cr1'],8)} MPa 偏离 {dev}，"
     f"且 6 阶谱中不存在由安全 `N_cr` 反推的 λ1 = {exp} ⇒ **σ=1.0 邻域档即便 6 阶仍漏真最低根**。"
     f"ccx 安全 `N_cr` 与 Abaqus 单档 `N_cr` = {f(A['n_cr1'],7)} MPa 相差 {gap}（跨 P_ref，仅 diagnostic）。"
     "逐阶 `N_cr` 低 3 阶稳定、第 6 阶漂移 "
     f"{f(R['per_mode_n_cr_rel_p050_vs_p020'][5]*100,2)}% ⇒ 支持 Q3「只判 λ1」。\n"
     "- **仍未闭环**：P0-3 振型 MAC；**Abaqus 侧 3 档 × 6 阶**（deck + 外部 bat 已备，8/8 自检 ×3，"
     "ccx 求解已结束、锁已释放 ⇒ 现可运行）；网格收敛／解析解锚点。"
     "**P0 不得宣告通过，6 条打样继续暂缓（D5），λ 阈值继续不冻结。**",
     "DESIGN 11.4"),
])

# --------------------------------------------------------------- ROADMAP ----
edit(_ROOT / "FEM-Bench-Aero" / "ROADMAP.md", [
    ("下一步 = P0（载荷缩放/6 阶/振型 MAC）闭环后再谈判据与打样 | 数据层新一轮（**不是** v1.1 的补丁） |",
     "**P0 阶段一／二 ccx 侧已闭环（2026-11-08）**：6 阶请求实测证实 ccx 2 阶漏掉 3 个 λ<1 模态（旧值实为第 4、5 阶）；"
     f"载荷缩放 0.05／0.02 MPa 两档 `N_cr` 稳定到 {safe}、0.1 档偏离 {dev} 且谱中缺 λ1={exp} ⇒ "
     f"**37.87% 已证否为同一对模态的差异**；ccx 安全 `N_cr` 与 Abaqus 单档相差 {gap}（跨 P_ref，仅 diagnostic）；"
     "送审报告升至 v1.2（§8.7、E15、U13/U14，专家结论原文未改）；"
     "下一步 = **Abaqus 外部 3 档 bat（现可运行，ccx 全停）→ 振型 MAC（P0-3）→ 网格/解析锚点**，"
     "P0 全闭环后才谈判据与 6 条打样 | 数据层新一轮（**不是** v1.1 的补丁） |",
     "ROADMAP C6"),
])

# ------------------------------------------------------------------ DATA ----
append(_ROOT / "FEM-Bench-Aero" / "DATA.md", f"""

### 7.10 P0 阶段二回填与报告 v1.2（2026-11-08）

- **送审件升版**：`REVIEW_C6_P2_FORMULATION_DIFFERENCE.md` **v1.2**（620 行），新增 §8.7 阶段二实测、
  E14／E15／E16、U13／U14；§8.5 计划表与 §8.6 末行状态回填；**§10 专家结论原文一字未改**，
  仅在 §10.4 追加「阶段二复核记录（编制方，非专家意见）」。禁用词／表格竖线／14 项数字对账全绿。
- **ccx 载荷缩放 3 档 × 6 阶**（`probe_p2_load_scaling.py`，81 min，全 `rc=0`）：
  `reports/diagnostics/p2_load_scaling_ccx_2026-11-08.json` + 三份 `.dat` 原文
  （`p2_scaling_ccx/`）；独立复算 `p2_stage2_load_scaling_2026-11-08.json`（算式随盘）。
- **已确认事实**：安全档 `N_cr1` = {f(C['p050']['n_cr1'],8)} / {f(C['p020']['n_cr1'],8)} MPa
  （对称相对差 **{safe}**）；0.1 档 {f(C['p100']['n_cr1'],8)} MPa 偏离 **{dev}**，
  6 阶谱中**无**由安全值反推的 λ1 = **{exp}**；Abaqus `.msg` 全精度 λ1 = {f(A['lambda1_msg_full_precision'])}
  ⇒ `N_cr` = {f(A['n_cr1'],7)} MPa，与 ccx 安全均值差 **{gap}**（**跨 P_ref，Abaqus 侧不变性未验，不作双码最终差值**）。
- **口径不变**：C3 由「首选排除」升为「本案例内已实测证实」，但**专家「现阶段不能定论」维持有效**；
  K-mode MAC、Abaqus 3 档、U2/U3 锚点仍缺 ⇒ **P0 未闭环、6 条打样继续暂缓、λ 阈值不冻结**。
- **Abaqus 外部作业现可运行**：`feagpt_repro/_p2_abq_scaling/run_p2_abq_scaling_MANUAL.bat`（3 档 × 6 阶，
  8/8 自检 ×3）；ccx 求解已全部结束、`.solve.lock` 已释放（R61 允许）。
""")

# ---------------------------------------------------------------- MEMORY ----
edit(_ROOT / ".workbuddy" / "memory" / "MEMORY.md", [
    ("- **专家决议**：S1 同码自比采纳但须过 solver-health 闸",
     f"- **★ P0 阶段二已实测（2026-11-08）**：ccx 3 档 × 6 阶全 `rc=0`；安全档（0.05／0.02 MPa）"
     f"`N_cr` 稳定到 {safe}，0.1 档偏离 {dev}、且 6 阶谱中无安全值反推的 λ1={exp} ⇒ "
     "**37.87% 已证否为同模态差**；换安全载荷后与 Abaqus 单档 `N_cr` 仅差 "
     f"{gap}（跨 P_ref，仅 diagnostic，Abaqus 自身不变性未验）。逐阶 `N_cr` 低 3 阶稳、第 6 阶漂 "
     f"{f(R['per_mode_n_cr_rel_p050_vs_p020'][5]*100,2)}% ⇒ 只判 λ1。报告 v1.2（§8.7／E15，专家结论原文未改）。"
     "**长期坑已实锤**：ccx 2.23 `*BUCKLE` 只要真谱压在 σ=1.0 邻域，请求 6 阶仍返回「σ 附近」而非「最低」的根；"
     "唯一已验规避 = 改 P_ref 把谱移出 σ 邻域。C3 证实 ≠ 公式差异存在/不存在的结论。\n"
     "- **专家决议**：S1 同码自比采纳但须过 solver-health 闸",
     "MEMORY stage2"),
    ("- **下一步 = P0 闭环**（载荷缩放 0.1/0.05/0.02 两码 6 阶 + 振型 MAC），之后才谈判据与打样。",
     "- **下一步 = P0 剩余三项**：① Abaqus 外部 3 档 bat（ccx 已停、锁已释放，**现可运行**）；"
     "② 振型 MAC（P0-3／U10）；③ 网格收敛 + 解析解锚点（U2/U3）。"
     "**P0 未闭环 ⇒ 6 条打样继续暂缓、λ 阈值不冻结**；跨码数字一律 diagnostic。",
     "MEMORY next"),
])

# ------------------------------------------------------------- daily log ----
append(_ROOT / ".workbuddy" / "memory" / "2026-11-08.md", f"""

## 四节：P0 阶段二 ccx 载荷缩放收口 + 报告 v1.2（2026-11-08 下午）

- **线名+实体**：C6-P2 专家审查 EX01 的 P0-1/P0-2，`probe_p2_load_scaling.py` 三档 × 6 阶 ccx 求解（81 min，全 `rc=0`）；送审报告 v1.2。
- **★ 决定性结果**：0.05／0.02 MPa 两档 `N_cr1` = {f(C['p050']['n_cr1'],8)} / {f(C['p020']['n_cr1'],8)} MPa，
  对称相对差 **{safe}**（λ 严格随 1/P_ref 反比）⇒ 载荷缩放不变性在安全 λ 区成立；
  0.1 MPa 档 `N_cr1` = {f(C['p100']['n_cr1'],8)} MPa，偏离安全均值 **{dev}**，3 个 λ<1、整谱挤在 [0.9495,1.0419]；
  由安全 `N_cr` 反推该档应有 λ1 = **{exp}**，但 6 阶谱中**不存在** ⇒ **即便 6 阶仍漏真最低根**，
  增加阶数修不了，唯一已验规避是改 P_ref 让谱移出 σ=1.0 邻域。EX01 的 C3 从「首选排除」升为「本案例内已实测证实」。
- **与 Abaqus 对照**：`.msg` 全精度 λ1 = {f(A['lambda1_msg_full_precision'])} ⇒ `N_cr` = {f(A['n_cr1'],7)} MPa；
  ccx 安全均值 {f(R['safe_mean_n_cr1'],8)} MPa ⇒ 对称相对差 **{gap}**。
  **口径边界**：跨不同 P_ref 比 `N_cr`（线性屈曲下应 P_ref 无关），且 Abaqus 只跑过 0.1 一档、自身不变性未验
  ⇒ **不是双码最终差值、不进阈值**；与阶段一受污染档的 32.06%／最初 37.87% 不同口径，不可并列。
- **逐阶证据**：p050 vs p020 的 `N_cr` 逐阶相对差 = {[round(x,6) for x in R['per_mode_n_cr_rel_p050_vs_p020']]}；
  低 3 阶 ≤8e-6、第 6 阶 {f(R['per_mode_n_cr_rel_p050_vs_p020'][5]*100,2)}% ⇒ 高阶配对仍不稳，支持 Q3「只判 λ1」。
- **产物**：`p2_load_scaling_ccx_2026-11-08.json`（3 档主表）+ 3 份 `.dat` 原文（`p2_scaling_ccx/`）+
  `p2_stage2_load_scaling_2026-11-08.json`（独立复算，全部算式随盘）+ `make_p2_stage2_finding.py`；
  `apply_p2_stage2_revisions.py` 把报告升 v1.2（9 处唯一命中替换 + §8.7 + U13/U14，620 行，
  **§10 专家结论原文用断言保护未改**）；DESIGN §11.4 / ROADMAP C6 / DATA §7.10 / MEMORY 同步。
- **闸与纪律**：ccx 结束后 `.solve.lock` 自动释放、无孤儿进程 ⇒ 上轮因合法锁判红的 **S-47 转绿**；
  负控 87/87、claims 36/83/63、roadmap 自检全绿。第一批 21 文件此前只暂存未提交，本批一并收口。
- **仍未闭环（不许提前定论）**：P0-3 振型 MAC、Abaqus 侧 3 档 × 6 阶（deck + bat 已备、8/8 自检 ×3，
  **ccx 全停后现可交给老王在 WorkBuddy 外跑**）、网格收敛 + 解析解锚点。
  **专家「现阶段不能定论」维持有效；6 条打样继续暂缓、λ 阈值不冻结。**
- 检索词：P0 阶段二、载荷缩放不变性、N_cr 稳定 8.11e-06、p100 偏离 29.89%、λ1=0.702622 缺席、
  残余 2.2259%、报告 v1.2、S-47 转绿、Abaqus 3 档 bat 可运行。
""")

print("all SOT docs + memory landed")
