"""Land P0-3 stage-A (ccx mode-shape parsing) into SOT docs and memory.

The expert-facing review report is deliberately NOT bumped: this stage is
tooling/evidence preparation, not a new expert conclusion.  U14 status is
updated to 'ccx side done, Abaqus external job prepared'.
"""

from __future__ import annotations

import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_J = json.loads((_HERE / "reports" / "diagnostics" /
                 "p2_ccx_mode_pairing_2026-11-08.json").read_text(encoding="utf-8"))
_M = json.loads((_HERE / "reports" / "diagnostics" /
                 "p2_ccx_modes_p020_2026-11-08.json").read_text(encoding="utf-8"))
SAFE = [round(x, 6) for x in _J["p020_vs_p050_same_mode_mac_modes_1_3"]]
MAXBAD = max(max(r) for r in _J["mac_matrix_rows_p100_cols_p020"])


def _marker(text: str) -> str:
    """Stable marker used to detect an already-landed edit/append."""
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("|") and len(s) > 12:
            return s[:60]
    return text.strip()[:60]


def edit(path, pairs):
    """Idempotent: if the new text is already present, treat as landed.

    The first run of this script aborted halfway because MEMORY.md's anchor
    had drifted from the injected session snapshot.  A landed script must be
    safely re-runnable, so 'already applied' is a pass, not a failure.
    """
    t = path.read_text(encoding="utf-8")
    n_done = 0
    for old, new, label in pairs:
        if _marker(new) in t:
            n_done += 1
            continue
        k = t.count(old)
        assert k == 1, f"{label}: anchor hit {k} times: {old[:80]!r}"
        t = t.replace(old, new)
        n_done += 1
    path.write_text(t, encoding="utf-8")
    print(f"  updated {path.relative_to(_ROOT)} ({n_done}/{len(pairs)} anchors OK)")


def append(path, text):
    t = path.read_text(encoding="utf-8")
    if _marker(text) in t:
        print(f"  already landed: {path.relative_to(_ROOT)}")
        return
    path.write_text(t.rstrip("\n") + "\n" + text, encoding="utf-8")
    print(f"  appended {path.relative_to(_ROOT)} (+{len(text.splitlines())} lines)")


# DESIGN: extend the 11.5 decision with stage-A completion
edit(_ROOT / "FEM-Bench-Aero" / "DESIGN_C6_P2_BUCKLE.md", [
    ("- **仍不变**：P0 未闭环前不冻结 λ 阈值、不跑 6 条打样、跨码数字仅 diagnostic（EX01 D5）。",
     "- **仍不变**：P0 未闭环前不冻结 λ 阈值、不跑 6 条打样、跨码数字仅 diagnostic（EX01 D5）。\n\n"
     "#### 11.5.1 阶段 A 已完成（2026-11-08 晚）\n\n"
     "- `extract_buckle_frd.py`（26/26 pins）：ccx 2.23 `.frd` 定宽解析；"
     "`100CL` 帧头给出 **9 位有效数 λ**（比 `.dat` 的 7 位更准），第 1 帧 λ=0 是静力基准场**不是模态**；"
     "三档各 7 帧（1 静力 + 6 模态），**6/6 全阶 λ 对齐** `.dat`，相对差 <1e-7。\n"
     "- 复用 `_p2_scaling_ccx/` 现成 `.frd`（buckle 分支已写 `*NODE FILE U`），"
     "**未重跑求解、未占 `.solve.lock`**；三档节点 ID 序列 sha256 完全相同（213270 节点）"
     " ⇒ 后续两码 MAC **无需节点重映射**。\n"
     "- 前 3 阶归一化振型归档 `reports/diagnostics/p2_ccx_modes_p020_2026-11-08.npz`"
     f"（{_M['full_npz_bytes']} B，float32）+ 三档摘要 JSON。\n"
     f"- ccx 内部配对（`p2_ccx_mode_pairing_2026-11-08.json`）：安全两档同阶 MAC = {SAFE}，"
     f"跨阶 ≈1e-9 ⇒ 载荷缩放保持振型、解析器不串档；**0.1 MPa 受污染档的 6 个振型与安全档最低 6 阶全不配对**"
     f"（全矩阵最大 MAC {MAXBAD:.2e}）⇒ 该档返回的不是基本模态；"
     "这与 σ=1.0 选择失效一致，但**不定位**它究竟是哪些高阶模态，也**不冒充双码 MAC**。\n"
     "- 阶段 B（Abaqus 侧）已备：`odb_tools/extract_buckle_odb.py`（`abaqus python` 读现有 3 份 `.odb`，"
     "**不重新求解**）、`_p2_abq_scaling/run_p2_abq_modes_MANUAL.bat`（外部 3 档）、"
     "`check_p2_abq_modes_meta.py`（6/6 pins 校验 meta/bin/sha）、"
     "`make_p2_two_code_mac.py`（bin→npz + 双码 MAC，节点标签不一致即 fail-closed）。"
     "**按 R61 串行**：bat 待老王在 WorkBuddy 外运行，跑完前双码 MAC 脚本干净失败。",
     "DESIGN 11.5"),
])

# ROADMAP
edit(_ROOT / "FEM-Bench-Aero" / "ROADMAP.md", [
    ("下一步 = **振型 MAC（P0-3／U14，P0 最后一道）→ 网格收敛 + 解析解锚点（U2/U3）**，"
     "P0 全闭环后才谈判据与 6 条打样",
     "**P0-3 阶段 A 已做完（2026-11-08 晚，按老王拍板顺序）**：ccx 侧振型解析 "
     "`extract_buckle_frd.py` 26/26 pins，复用现成 3 档 `.frd` 不重跑求解；"
     "三档 6/6 全阶 λ 对齐（`.frd` 9 位精度 vs `.dat` 7 位）、213270 节点 ID 三档一致 ⇒ 两码 MAC 免重映射；"
     f"安全两档同阶 MAC {SAFE}，0.1 污染档与安全档最低 6 阶全不配对（最大 {MAXBAD:.2e}）；"
     "前 3 阶振型归档 `p2_ccx_modes_p020_2026-11-08.npz`。"
     "**阶段 B 外部作业已备**：`_p2_abq_scaling/run_p2_abq_modes_MANUAL.bat`（读现有 3 份 `.odb`，不求解）；"
     "跑完 → `make_p2_two_code_mac.py` 出双码 MAC（U10／U14）→ 网格收敛 + 解析锚点（U2/U3），"
     "P0 全闭环后才谈判据与 6 条打样；报告版本不动（本阶段是工具链准备，不是新专家结论）",
     "ROADMAP C6"),
])

# DATA
append(_ROOT / "FEM-Bench-Aero" / "DATA.md", f"""

### 7.12 P0-3 阶段 A：ccx 侧振型解析（2026-11-08 晚）

- 按老王拍板「先把 ccx 侧振型解析做通，再配一次外部作业」，两阶段**串行不并行**；
  送审报告 `REVIEW_C6_P2_FORMULATION_DIFFERENCE.md` **保持 v1.3 不动**（本阶段是工具链与证据准备，非新专家结论）。
- **解析器** `feagpt_repro/extract_buckle_frd.py`（26/26 pins，含真机原文行复发 pin）：
  ccx 2.23 `.frd` 定宽 `[3:13]` 节点号 + 3×12 字符科学计数法；`1PSTEP`→`100CL` 分帧；
  **`100CL` 的 λ 是 9 位有效数**（`.dat` 仅 7 位）；**第 1 帧 λ=0 是静力基准场，不是模态**。
- **复用现成产物**：`_p2_scaling_ccx/` 三档 `.frd`（各 92.5 MB）已含 `*NODE FILE U`，
  **未重跑求解、未占 `.solve.lock`**。三档各 7 帧（1 静力 + 6 模态）、6/6 全阶 λ 对齐（相对差 <1e-7）、
  节点 ID 序列 sha256 三档完全相同（213270 节点）⇒ 后续两码 MAC **无需节点重映射**。
- **归档**：`reports/diagnostics/p2_ccx_modes_p020_2026-11-08.npz`（前 3 阶归一化振型，float32，
  {_M['full_npz_bytes']} B，sha256 随摘要 JSON）+ `p2_ccx_modes_<tag>_2026-11-08.json`（三档摘要）。
- **ccx 内部配对** `reports/diagnostics/p2_ccx_mode_pairing_2026-11-08.json`：
  安全两档同阶 MAC = {SAFE}、跨阶 ≈1e-9 ⇒ 载荷缩放保持振型、解析器不串档；
  0.1 MPa 受污染档的 6 个振型与安全档最低 6 阶**全不配对**（全矩阵最大 MAC {MAXBAD:.2e}）
  ⇒ 该档返回的不是基本模态；与 σ=1.0 选择失效一致，但**不定位**具体高阶模态、**不冒充双码 MAC**。
- **阶段 B 已备（待老王外部跑）**：`odb_tools/extract_buckle_odb.py`（`abaqus python` 读现有 3 份 `.odb`，
  **不重新求解**）、`_p2_abq_scaling/run_p2_abq_modes_MANUAL.bat`（外部 3 档 + 逐档校验）、
  `check_p2_abq_modes_meta.py`（6/6 pins：meta/二进制大小/sha256/帧数/节点端点）、
  `make_p2_two_code_mac.py`（bin→npz + 双码 MAC；**节点标签不一致即 fail-closed**，产物未齐时干净失败）。
- **口径不变**：P0 仍未闭环（U10/U14 双码 MAC、U2/U3 网格与解析锚点），
  6 条打样继续暂缓、λ 阈值不冻结、跨码数字仅 diagnostic。
""")

# MEMORY
edit(_ROOT / ".workbuddy" / "memory" / "MEMORY.md", [
    ("- **下一步 = P0 剩余两项**：① 振型 MAC（P0-3／U14，现为 P0 最后一道）；② 网格收敛 + 解析解锚点（U2/U3）。"
     "**P0 未闭环 ⇒ 6 条打样继续暂缓、λ 阈值不冻结**；跨码数字一律 diagnostic。",
     "- **P0-3 阶段 A 已做完（2026-11-08 晚）**：按老王拍板「先 ccx 侧振型解析，再配外部作业」。"
     "`extract_buckle_frd.py` 26/26 pins，复用现成 3 档 `.frd`（不重跑求解）；"
     "**`100CL` 帧头 λ 是 9 位精度、第 1 帧 λ=0 是静力场不是模态**；三档 6/6 全阶 λ 对齐、"
     "213270 节点 ID 三档一致 ⇒ 两码 MAC 免重映射。安全两档同阶 MAC ≈0.9999，"
     f"0.1 污染档与安全档最低 6 阶全不配对（最大 {MAXBAD:.2e}）。"
     "前 3 阶振型 npz 已归档。**阶段 B 外部 bat 已备**（读现有 3 份 `.odb` 不求解）。\n"
     "- **下一步 = P0 剩余两项**：① 老王在外部跑 `run_p2_abq_modes_MANUAL.bat` → 双码 MAC（U10/U14）；\n"
     "② 网格收敛 + 解析解锚点（U2/U3）。",
     "MEMORY next"),
])

# daily log
append(_ROOT / ".workbuddy" / "memory" / "2026-11-08.md", f"""

## 六节：P0-3 阶段 A（ccx 振型解析）+ 阶段 B 外部作业备好（2026-11-08 晚）

- **线名+实体**：C6-P2 / EX01 的 P0-3 振型 MAC 准备；老王拍板「先把 ccx 侧振型解析做通，再配一次外部作业」，串行不并行。
- **开工闸**：负控 87/87、claims 36/83/63、无锁、工作区干净。拍板即落盘 `DESIGN_C6_P2_BUCKLE.md` §11.5。
- **★ 复用现成产物**：`_p2_scaling_ccx/` 三档 `.frd`（各 92.5 MB）已含 `*NODE FILE U` ⇒ **不重跑求解、不占 `.solve.lock`**。
- **ccx 解析器** `extract_buckle_frd.py` 26/26 pins：定宽 `[3:13]` 节点号 + 3×12 字符；`1PSTEP`→`100CL` 分帧；
  **`100CL` 给 9 位有效数 λ**（`.dat` 只有 7 位）；**第 1 帧 λ=0 是静力基准场，不是模态**；
  三档各 7 帧（1 静力 + 6 模态），6/6 全阶 λ 对齐（相对差 <1e-7）。
- **踩坑（第三次同类）**：第一版解析器把自造 self-test 片段的 `1PSTEP` 写成 3 空格，真机是 **4 空格**
  ⇒ 26 pins 全绿却在真机上 `no frames parsed`。修法：改去缩进 tag 判定、`split` 解 `100CL`，
  self-test 片段换成真机原文缩进，并加 4 条「真机原样行」复发 pin。问句：**测试片段是不是从真机抄的？**
- **第二个坑**：`max_frames` 截断原本是空 `pass`（不生效）⇒ 修成 `-3` 处真 break，
  并拆出 `scan_frame_headers()` 轻量通道，让「全 6 阶 λ 对齐」与「只留前 3 阶振型」两件事分开做。
- **归档**：`p2_ccx_modes_p020_2026-11-08.npz`（前 3 阶归一化振型 float32，{_M['full_npz_bytes']} B）+ 三档摘要 JSON；
  三档节点 ID sha256 完全相同（213270 节点）⇒ 两码 MAC 免重映射。
- **ccx 内部配对** `p2_ccx_mode_pairing_2026-11-08.json`：p020 vs p050 同阶 MAC = {SAFE}、跨阶 ≈1e-9
  ⇒ 载荷缩放保持振型、解析器不串档；**p100 6 个振型与 p020 最低 6 阶全不配对**（最大 MAC {MAXBAD:.2e}）
  ⇒ 该档返回的不是基本模态。初次跑出「全零矩阵」其实是 `%.4f` 打印把 1e-7 量级抹成 0，
  并**把弱 argmax 硬说成配对** ⇒ 改科学计数法 + 0.80 阈值 + 客观表述：**不宣称 C3 已被振型级证明，也不定位是哪些高阶模态**。
  问句：**这个数是不是同一个物理量的数；弱证据有没有被包装成结论？**
- **阶段 B 已备（待老王外部跑）**：`odb_tools/extract_buckle_odb.py`（`abaqus python` 读现有 3 份 `.odb`，**不重新求解**；
  位置参数与已验证的 `odb_batch.py:180` 同构，避免 `--odb` 被 Abaqus 参数层吞掉）、
  `_p2_abq_scaling/run_p2_abq_modes_MANUAL.bat`、`check_p2_abq_modes_meta.py`（6/6 pins，
  含 sha/大小/帧数/节点端点四向变异）、`make_p2_two_code_mac.py`（bin→npz + 双码 MAC，
  节点标签不一致 fail-closed、产物未齐干净失败）。三档 deck 预检 8/8 自检 ×3：
  `*NODE OUTPUT U` 在、`OUTPUT=2D`/`NUMBER INTERVAL` 不在。
- **口径不变**：送审报告**保持 v1.3 不动**（本阶段是工具链准备，不是新专家结论）；
  P0 未闭环 ⇒ 6 条打样暂缓、λ 阈值不冻结、跨码数字仅 diagnostic。
- 检索词：P0-3 阶段 A、frd 100CL 9 位 λ、静力帧 λ=0、4 空格 1PSTEP、节点 ID 免重映射、
  p100 振型全不配对、阶段 B 外部 bat、双码 MAC 待跑。
""")

print("SOT docs + memory landed (report v1.3 intentionally unchanged)")
