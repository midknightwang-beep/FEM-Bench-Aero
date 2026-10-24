#!/usr/bin/env python
"""M4: write the dataset manifest and its human-readable index.

What a manifest is for
----------------------
``truth.json`` answers "is this one case built right?".  The manifest answers
the questions that only make sense *across* cases, and that a consumer would
otherwise have to reconstruct by walking the tree and guessing:

* **identity** -- which cases are the same model (equivalence class), which
  solve matters for splitting;
* **purpose** -- why each case exists (baseline / sweep / ablation / degenerate
  / feature);
* **split** -- which of train/val/test each case belongs to, and the reason, so
  the table can be reviewed rather than trusted;
* **provenance** -- a sha256 per shipped file, so a consumer can verify they
  have the bytes this manifest describes;
* **readings** -- the headline numbers per case (nodes, max|u|, peak vM,
  min Jacobian, triangle count), each read from the *archived* artefact rather
  than from a rebuild.

Scope: the **release tree** (``modeling/``).  ``_xval/`` is cross-check evidence
under a commercial licence and never ships, so it appears only as a pairing
count -- see ``verify_dataset.py`` for its own consistency gates.

Deterministic on purpose
------------------------
No timestamp, no host name: two runs over an unchanged tree produce
byte-identical output.  That makes "did anything change?" a ``diff`` rather than
a memory test, which is the same discipline ``diagnostics/hash_manifest.py``
applies to the tree itself.  ``eval_dataset.py`` then checks the manifest by
recomputing every declared field from disk instead of reading it back.

Usage::

    python make_manifest.py --root ../FEM-Bench-Aero
    python make_manifest.py --root ../FEM-Bench-Aero --json ../FEM-Bench-Aero/manifest.json --md ../FEM-Bench-Aero/MANIFEST.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feagpt import manifest as mf  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402
from verify_dataset import (REQUIRED, TREES, deck_triangles,  # noqa: E402
                            find_duplicates, model_sha256)

#: gmsh element-type ids -> the names this project uses.
_ELEM_NAME = {1: "line2", 2: "tri3", 3: "quad4", 4: "tet4", 5: "hex8",
              9: "tri6", 10: "quad9", 11: "quad8"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mesh_readings(msh: Path) -> dict:
    """min Jacobian, element count and mix -- read back from the archived mesh.

    Same ``minSICN`` reduction the gate uses (see ``diagnostics/msh_quality.py``),
    so the manifest number and the gate number are the same number, and neither
    depends on rebuilding the geometry.
    """
    import gmsh

    gmsh.clear()
    gmsh.open(str(msh))
    tags: list[int] = []
    counts: dict[int, int] = {}
    for dim, tag in gmsh.model.getEntities(2):
        et, etags, _ = gmsh.model.mesh.getElements(2, tag)
        for t, tg in zip(et, etags):
            counts[t] = counts.get(t, 0) + len(tg)
            tags.extend(tg)
    if not tags:
        return {"min_jacobian": None, "n_elements": 0, "element_types": {}}
    q = [float(v) for v in gmsh.model.mesh.getElementQualities(tags, "minSICN")]
    return {
        "min_jacobian": round(min(q), 4),
        "n_elements": len(tags),
        "element_types": {_ELEM_NAME.get(t, f"type{t}"): n
                          for t, n in sorted(counts.items())},
    }


def read_case(case_dir: Path, gmsh_on: bool) -> dict:
    """One manifest entry, every declared value read from the case directory."""
    spec = FEASpec.from_json(case_dir / "spec.json")
    truth = json.loads((case_dir / "truth.json").read_text(encoding="utf-8"))
    scal = truth.get("scalars") or {}
    gate = truth.get("semantic_gate") or {}

    mr = (mesh_readings(case_dir / "model.msh") if gmsh_on
          else {"min_jacobian": None, "n_elements": None, "element_types": {}})
    tri = deck_triangles(case_dir / "model.inp")

    files = {name: _sha(case_dir / name)
             for name in REQUIRED if (case_dir / name).exists()}

    return {
        "case_id": spec.name,
        "tree": "modeling",
        "family": mf.family_of(spec),
        "role": mf.infer_role(spec),
        "geometry_class": mf.geometry_class(spec),
        "split": mf.assign_split(spec),
        "split_reason": mf.split_reason(spec),
        "solver": truth.get("solver"),
        "spec_sha256": truth.get("spec_sha256"),
        "mesh_sha256": files.get("model.msh"),
        # D25: model identity = mesh + declared shell thickness.  Published so a
        # thickness-only variant is visibly a distinct model, not a repeat.
        "model_sha256": model_sha256(case_dir),
        "files": files,
        "readings": {
            "n_nodes": scal.get("n_nodes"),
            "max_disp": scal.get("max_disp"),
            "max_von_mises": scal.get("max_von_mises"),
            "max_von_mises_midsurface": scal.get("max_von_mises_midsurface"),
            "stress_definition": scal.get("max_von_mises_definition"),
            "min_jacobian": mr["min_jacobian"],
            "n_elements": mr["n_elements"],
            "element_types": mr["element_types"],
            "n_tri3": tri,
        },
        "gates": {
            "semantic_gate_pass": bool(gate.get("pass")),
            "semantic_gate_n_checks": len(gate.get("checks") or []),
            "no_tri3": tri == 0,
        },
    }


def build(root: Path) -> dict:
    base = root / "modeling"
    if not base.is_dir():
        raise SystemExit(f"no release tree at {base}")

    import gmsh
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    try:
        cases = [read_case(d, True) for d in sorted(p for p in base.iterdir() if p.is_dir())]
    finally:
        gmsh.finalize()

    # equivalence classes -> members, and the split each class was assigned to
    by_class: dict[str, list[str]] = defaultdict(list)
    for c in cases:
        by_class[c["geometry_class"]].append(c["case_id"])
    for c in cases:
        c["class_size"] = len(by_class[c["geometry_class"]])

    splits: dict[str, list[str]] = {s: [] for s in mf.SPLITS}
    for c in cases:
        splits.setdefault(c["split"], []).append(c["case_id"])
    for s in splits:
        splits[s].sort()

    by_family: dict[str, dict[str, int]] = {}
    for c in cases:
        fam = by_family.setdefault(c["family"], {s: 0 for s in mf.SPLITS})
        if c["split"] in fam:
            fam[c["split"]] += 1

    roles = Counter(c["role"] for c in cases)

    # duplicates *inside the release tree* -- the hazard a split can leak through.
    # D25: keyed on the model fingerprint (mesh + shell thickness), not the mesh.
    dups = find_duplicates([{"case": c["case_id"], "model_sha": c["model_sha256"]}
                            for c in cases])

    # classes whose members do not all share a split -- must be empty
    leaky = {cls: sorted(mems) for cls, mems in by_class.items()
             if len({next(c["split"] for c in cases if c["case_id"] == m) for m in mems}) > 1}

    xval = root / "_xval"
    paired = len({d.name for d in xval.iterdir() if d.is_dir()}) if xval.is_dir() else 0

    # Limitations are *computed*, not written down: a hard-coded "val 只有 1 条"
    # becomes a lie the moment a batch lands, and nothing would fail.  D17
    # (2026-10-04) grew the set to 23 by populating the D16 val regions, which is
    # exactly the edit that would have rotted a literal.
    n_val = sum(1 for c in cases if c["split"] == "val")
    want_val = round(mf.TARGET_RATIOS["val"] * len(cases))
    empty_val_fams = sorted(f for f, m in by_family.items() if m.get("val", 0) == 0)
    limitations = [
        f"val 共 {n_val} 条（{len(cases)} 条下 6:2:2 目标要求约 {want_val} 条）："
        "val 的绝对数量仍是样本量的限制，不是划分规则的缺陷。",
        (f"以下族在 val 为空：{'、'.join(empty_val_fams)}。"
         "族内还缺一个「train 已学档之外」的中间精度点。"
         if empty_val_fams else
         "每个族都有 val 样本，val 的族代表性完整。"),
        "当前划分是**规则**（feagpt/manifest.py :: HOLDOUT_REGIONS）而不是显式表："
        "每族声明留出区域，未命中区域即进 train。规则已按 D12 锁定口径 A 复现 11 条"
        "（见 manifest.py :: D12_LOCKED_SPLIT，由 eval_dataset 断言），"
        "并在 D15（后掠/锥形兼具 -> test）与 D16（单维外推 -> val）上扩展。",
    ]
    if "fuselage_barrel" in by_family:
        # D19 (2026-10-05).  Conditional on the family actually being present,
        # for the same reason the val count above is computed: a limitation about
        # a family that is not in the set is noise.
        limitations.append(
            "柱壳族（fuselage_barrel）的网格是**有包络的**（D19，2026-10-05）："
            "n_stringers 只接受 0 或 ≥ 5，1–4 根会在框的外弧（r ≈ R 的框/蒙皮粘结线）"
            "上留下三角（3str/2frm 20、4str/2frm 16、4str/3frm 22）。"
            "五种修法（simple 重组 / 只细分框经线 / 蒙皮与框一起细分 / 框专用尺寸场 / "
            "逐面 2-D 算法）已全部实测否决，故族 _validate 直接**拒绝**该区间，"
            "而不是建一个带三角的模型。数据集因此暂时拿不到 1–4 根长桁的柱壳；"
            "val 落在 10/12/16 根、train 落在 5–8 根，均未受影响。"
        )
        # D20 (2026-10-05).  The barrel's cross-solver criterion changed 口径;
        # a changed registered criterion is exactly the kind of thing that must
        # not live only in a script.
        limitations.append(
            "柱壳族（fuselage_barrel）的双码交叉判据口径 = **D20（2026-10-05）**："
            "门的量是「**剔除自由端端载环后的结构 max|u|**」（该环由族自己的 "
            "fuselage.barrel_nodes 圈定，不是写死的坐标带）与「沿轴 **截面形心挠度剖面**」"
            "（偏差对**尖端挠度**归一，避免近零截面把相对误差放大），两者容差仍 1 %。"
            "**模型全域 max|u| 仍如实印出，但不用于判绿/红**：实测 ccx 2.63102 vs abaqus "
            "2.67818 mm = 1.79 %，峰值落在**自由端框的内缘自由边**上（框建成 30×3 平环板，"
            "只沿 r = 1000 与蒙皮粘接），是「节点力压在自由壳边」的局部效应："
            "纯内压（光滑面力）两码只差 0.25 %，剔除该环后 0.42 %，"
            "把端载只压在筒壳环上（3226→644 节点）峰值仍在同一位置、差仅降到 1.11 %。"
        )
        # D21 (2026-10-05).  A corrected *load sign* changes every barrel result
        # in the set, so it belongs in the published limitations rather than only
        # in a commit message: a consumer comparing against a pre-D21 number has
        # to be able to find out why it moved.
        limitations.append(
            "柱壳族（fuselage_barrel）的内压方向 = **D21（2026-10-05）修正**："
            "`*DLOAD ... P` 是沿壳面法向的**带符号**压力，而壳体法向由建面方式决定 —— "
            "`occ.revolve` 建出的桶段蒙皮与拉伸翼盒蒙皮/平板矩形**法向相反**，"
            "所以写死 `-abs(p)` 的旧 deck 实际把桶段**由外向内压**："
            "实测中面径向位移 −0.22725 mm，而薄壁闭式解 w = pR²/(Et) = **+0.22800 mm**。"
            "符号现由建面器声明（GeometryResult.pressure_dload_sign，默认 −1 保证"
            "翼盒/平板 23 条零扰动，桶段声明 +1）。修正后实测 +0.22725 mm，差 −0.329 %。"
            "⚠️ 门禁读数：只有 `pressure.radial-growth` 抓得住这个符号错 —— "
            "`pressure.hoop-membrane` 比的是 von Mises，压/拉状态下都为正，符号错也照样 PASS。"
        )
        # D22 (2026-10-05).  A capability the family advertised and the builder
        # never had - published, because "the schema accepts it" is exactly what
        # a consumer would rely on.
        limitations.append(
            "柱壳族（fuselage_barrel）**只支持 blade 截面长桁**（D22，2026-10-05）："
            "建面器（geometry.build_fuselage_barrel）每条长桁只出一片平面径向腹板，"
            "**从不读 stringer_kind**，所以 T/L 等带翼缘截面会被静默建成 blade。"
            "实测 T(fw=30) 与 blade 逐位相同（158548 节点 / 157972 单元 / minJ 0.5159），"
            "而 topology 按 3 面/长桁要求 48 面、只观察到 16 —— gate 4 会 FAIL（非静默），"
            "但族 schema、_validate、_design_fuselage 三处都曾声称支持。"
            "现由 _validate **拒绝**非 blade（与 D19 同一 posture），"
            "并留档为待实现能力；副作用是 manifest._fuselage_new_form"
            "（新截面形式 → test）暂无数据可匹配，T3 的留出形态改由**双维外推**提供。"
        )
        # D27 (2026-10-06).  A scope limit imposed by the machine, published so
        # that "why is there no upward size arm?" has an answer on disk rather
        # than only in a commit message.
        limitations.append(
            "柱壳族（fuselage_barrel）的尺寸维**只朝收缩方向外推**（D27，2026-10-06）："
            "CalculiX 在分解前会把每个壳单元**展开成实体**（这**不是** `OUTPUT=3D` 的代价 —— "
            "关掉该参数后 `number of equations` 3489495、`nnz` 194129961、`.12d` 字节数 "
            "68750934 三项分毫不变），于是方程数 ≈ **14.9 × 壳节点数**（三点实测一致）。"
            "在本机 16491000 kB 内存 + 16866936 kB 交换（≈ 33 GB 提交上限）下，"
            "**实测可算的最大点是 158548 节点 / 2359690 方程，最小的失败点是 188674 节点 / "
            "2816466 方程**（返回 0xC0000005，而 fork 已先报 0xC000012D = "
            "STATUS_COMMITMENT_LIMIT）；柱壳基线自身（158524 节点 / 2359690 方程）已贴着这道墙。"
            "长度只放大 20 % 即触墙（d2000_l2400 建出 188555 节点）。"
            "故原计划的 D1600+L3000 与 L3000 两条被换成它们的收缩孪生点 "
            "（D1600+L1600 与 L1600）；缺的「放大臂」估计需 48 GB 级内存才能补（未实测）。"
            "⚠️ 该上限**不是常数**：Windows 在那次崩溃后把页面文件自动扩到 24975728 kB"
            "（≈ 41 GB 提交），上面记的是**当时**实测值；扩容后未再复测放大方向 —— "
            "即便可以，数十 GB 的常驻加重度换页也不适合当作可复现的数据集流水线。"
        )
    if "open_hole_panel" in by_family:
        # D28 (2026-10-08).  The corner rule declared with batch 7, and the one
        # dimension 老王 explicitly declined to declare this round - both belong
        # in the published limitations for the same reason D19-D22 do.
        limitations.append(
            "开孔板族（open_hole_panel）的双维外推 = **D28（2026-10-08）**："
            "λ 与 (L,W) 同时 ≠ 锚点（λ 0.1 / 400×200）→ **test**（插在偏心 test 之后、"
            "两个 val 谓词之前）。声明前这样的点会同时命中两个 val 谓词、按「首个命中」"
            "落 val —— 与柱壳 D25「双维 → test」哲学相悖的宽松读法，"
            "已在 batch7 角点（600×300+d60）入库前补上。"
        )
        limitations.append(
            "开孔板族（open_hole_panel）的**厚度维经实测判定退化、不作为样本轴入"
            "（D30，2026-10-24 老王拍板）**：在恒定名义应力口径下，载荷 "
            "`F = sigma * width * thickness` 与膜刚度 `E * thickness` 精确抵消，"
            "所以 `u = sigma * L / E` 与壁厚**无关**。实测（`_probe_t7b`）："
            "[0/90]s 2.0 mm → max|u| 0.05734516，1.0 mm → **0.05734516**（逐位相同）；"
            "[45/-45]s 0.22584988 vs 0.22585092；孔边峰值 vM 差 0.02%~0.09%，低于任何"
            "闸门容差。唯一的区分度是总反力（4000 N vs 2000 N）。因此厚度变体作为"
            "样本**零信息量**（模型只要会几何就能「预测」），未入库；它改立为常设自检 "
            "`check_forms :: T7.thickness-invariance`（断言载荷比恰为 2、等效模量与 t "
            "无关）——载荷若未按 t 缩放，两个厚度的位移会差 2 倍，这是很强的载荷口径"
            "探针。厚度要有可观测性必须引入弯曲/屈曲/面外载荷（`D ∝ t^3`），那属于新"
            "结构形式，不是本族的放量。"
        )
        # D29 (2026-10-11).  The material dimension, declared with the T7
        # pilot, plus the dedup-fingerprint extension it forced.
        limitations.append(
            "开孔板族的**材料维 = D29（2026-10-11）**：复材层合以 CLT 等效单层入库"
            "（老王拍板架构 B —— `*ELASTIC, TYPE=ENGINEERING CONSTANTS` 9 常数 + "
            "S4 均匀壳，两码同构；层间/逐层应力不进数据集，ccx COMPOSITE 卡只支持 "
            "S6/S8R 也不支持）。划分：复材首实例（锚点几何）→ sweep/**train**"
            "（T6 web1 先例），复材+几何单维 → val，双维 → test，偏心谓词优先。"
            "**去重指纹随之扩展**：model_sha256 在网格字节 + 壳厚之外加入 deck 的 "
            "`*ELASTIC` 块（材料律）——实测复材 [0/90]s d20 与铝 d20 网格逐字节同构、"
            "厚度同为 2.0，旧指纹判为同一模型（80695b4c759e），加材料块后 0 重复、"
            "老 40 条内部零新增重复（verify_dataset 实测）。"
            "等效单层的独立验证线 = `_probe_t7/verify_laminate.py`（加载端平均恒等式"
            "口径，TOL_EFF=3% 按实测链钉）：打样双码 E_eff 残差 −2.070% / −2.073%，"
            "两码差 0.003%，偏差为 4 mm 非结构 S4 对正交异性的系统离散。"
        )
        # D30 (2026-10-24).  The material axis build-out and the scalar-axis
        # counting rule it forced.
        limitations.append(
            "开孔板族的**划分判据 = D30（2026-10-24）标量轴计数**：本族四条标量轴 "
            "**M** 铺层（`[0/90]s` 为锚点）、**T** 壁厚（2.0 mm）、**L** "
            "`lambda_ratio`（0.1）、**S** 尺寸（400×200）；偏离锚点 **0 轴 → train、"
            "1 轴 → val、≥2 轴 → test**，偏心孔仍走独立 test 谓词（谓词优先）。"
            "D30 是 D29 的维数化重述而非推翻：实测（`_probe_t7b/probe_d30_split.py`）"
            "**8/8** 已入库开口板 case 的划分零变化，D12 复现。本批新增 3 条："
            "`cfrp45s`（[45/-45]s，M）→ val、`cfrpqi`（[0/45/-45/90]s 准各向同性，M）"
            "→ val、`cfrp45s_d40`（M+L）→ test；`cfrp090s` 仍是 0 轴锚点 → train。"
            "**可观测量分离度**：三种铺层 max|u| 分别为 0.0573 / 0.0778 / 0.2258 mm，"
            "孔边峰值 vM 49.02 / 30.31 / 42.82 MPa（准各向同性最低，符合孔边集中最弱）。"
            "**同时修掉 D29 契约的一处实现缺陷**：`LayupSpec.is_balanced` 原按角度 "
            "`% 180` 求和判定，会把 `-45°` 归一成 `135°` 而误拒合法平衡铺层 "
            "`[+45/-45]s`；改为**有符号配对**，并让 `a_matrix` 真算 A16/A26（原为硬写 "
            "0）、`validate_for_deck` 增加 `|A16|,|A26| < 1e-9*max(A11,A22,A66)` 的物理"
            "交叉校验。准各向同性铺层另用**各向同性恒等式 `G = E/(2(1+nu))`** 独立验 "
            "CLT（实测 20616.463 vs 20616.463，不依赖任何铺层公式）。"
        )
        # D31 (2026-10-24).  The wing-box size axes moved from exact anchors to
        # train *intervals* - the one place where the dataset deliberately
        # contradicts the D25 reading, because the anchors there were an
        # artefact of sampling only one point.
        limitations.append(
            "翼盒族的**尺寸维划分 = D31（2026-10-24）train 区间**："
            "`span` 与 `skin_thickness` 从 D25 式「精确锚点」扩为训练**区间** "
            "`WINGBOX_TRAIN_SPAN = (1600, 2400)`、`WINGBOX_TRAIN_SKIN = (2.0, 4.0)`。"
            "核心二分：**出区间 = 外推**（val 单轴出 / test 双轴出），"
            "**出锚点但仍在区间内 = 扫点**（train）。D25 的「连续维只采过一个点 ⇒ "
            "只能等号」不是错，是**采样不足的表现**——主动补档位就造出了 interior，"
            "区间才诚实（D18「8 学 up to 8」的连续版）。test 三入口：两轴同时出区间 / "
            "一轴出区间 + 他轴（ribs>5、sweep>20、tcr<0.6、webs>1、非锚定长桁）/ "
            "两轴出锚点但都在区间内（交互点）。**`chord` 绝不算「他轴」**（800/1000 "
            "两档都在 train，列进去会把 3 条 chord800 重贴成 test）。"
            "落地前实测（`_probe_m8/probe_d31_landed.json`）**44 条存量 0 漂移**；"
            "补 8 条后 52 条 / 51 类 / 21-17-14（翼盒 17-7-7）。"
            "**物理核对**（`_probe_m8/physics_check.json`）：壁厚严格 `1/t`"
            "（skin 1.5→4 位移 2.656 倍、偏差 0.30%）、展长三点指数 2.899"
            "（梁论 3，±3% 偏离来自 n_ribs 固定 5 致肋距随 span 变）、"
            "交互项 0.06%/0.17%（可忽略 ⇒ 区间内双轴交互点作 test 是公平的）。"
            "**厚度维在翼盒上可观测、在开口板上不可观测**（D30）——差别全在"
            "**载荷随不随该轴缩放**：开口板 `F ∝ t` 与膜刚度 `∝ t` 精确抵消，"
            "翼盒固定 500 N 无抵消。判定某轴是否退化，先问载荷口径。"
        )
    if "wingbox" in by_family:
        # D32 (2026-10-24).  老王's call on which scalar a wing-box surrogate is
        # graded against, after M9 measured that the "better" target was only
        # better because it dodged the one axis that fails.
        limitations.append(
            "翼盒族的**标量代理目标口径 = D32（2026-10-24 老王拍板）**："
            "主目标 `max_disp`（合位移；实测 `max|v|/max_disp` = **0.99899–0.99973**，"
            "浮动 0.07 % ⇒ 它本身就是弯曲挠度，不需要另立「法向挠度」），"
            "副目标 `max_w`（展向位移 `max|DISP[2]|`，**只报不判**，仅用于 `span` 指数的"
            "交叉检验）。**不把 `max_w` 定为代理目标**，四条实测理由"
            "（`_probe_m9/w_vs_disp_diag.json`、`baseline_d31.json`）："
            "① 它绕开了全库唯一会崩的轴 —— `sweep40_taper040` 上 `max_w` ×1.716 而 "
            "`max_disp` ×4.171，敏感度只有 **41 %**，用它考核等于挑了一个对数据集最大"
            "缺陷不敏感的量；② 量级仅弯曲位移的 **1.9 %–5.7 %**，是泊松耦合次级量，"
            "工程上不是关注对象；③ **跨族不可用**（开孔板纯面内 ≡ 0、加筋板近刚性 ≡ 1），"
            "一个只有翼盒能用的指标不能当族间统一目标；④ 与双码闸门口径分家"
            "（`verify_solvers.py` 按 `DISP` 三向量逐节点中位比，不按单分量）。"
            "**跨目标比 MAPE 必须下掉同一条样本**：各自剔各自最差会翻转结论 —— "
            "统一下掉 `sweep40` 时 `max_disp` **3.82 %** 优于 `max_w` **4.48 %**，"
            "分别剔则是 3.82 % vs 2.15 %。应力峰值（`vM` 中面/外表面）**不设为可学"
            "目标**：1 参数梁标度律已 10.39 %/12.22 %，最优 10 特征学习器 9.51 %/10.68 %，"
            "差 **0.88/1.54 pp** 且 4000 次 bootstrap 的 95 % CI 均跨 0；机制是峰值位置在"
            "31 条翼盒里散落在 **21/25 个不同节点**，**峰值是离散选择而非光滑泛函**。"
            "所以本数据集的应力真值用于**求解器验证**，不用于标量代理建模。"
        )
        # D33 (2026-10-24).  The sweep bound moved 20 -> 30 by adding a station,
        # not by shrinking the exam.
        limitations.append(
            "翼盒族的**后掠轴划分 = D33（2026-10-24 老王拍板）**："
            "`WINGBOX_TRAIN_MAX_SWEEP` 20° → **30°**，新增 train 站 "
            "`naca4412_wingbox_sweep30`（仅 `sweep_deg=30`，锥度中性 1.0、其余全锚定）。"
            "目的不是放宽考试而是**把唯一的外推机制变成可内插**：实测后掠响应**超线性**"
            "（相对 0° 的位移比 **1.000 / 1.094 / 1.340 / 1.853 / 2.965**，增量 "
            "+0.094 / +0.246 / +0.514 / +1.112 严格递增，`_probe_m10/physics_sweep_axis.json`），"
            "0–20° 割线外推到 40° 差 **−43.4 %**（与 M7 的 −41.5 % 同源，两种口径互证）。"
            "补 30° 后 `sweep40` 仍是 **val**、`sweep40_taper040` 仍是 **test**"
            "（考试点一个没删），但外推距离 20° → **10°**；`sweep30` 处二次趋势预测误差 "
            "**−6.2 %** ⇒ 该点确含新信息，不是冗余叠加；4 站拟合到 40° 的残差从 "
            "−22.9 %（3 站二次）降到 −14.1 %（4 站二次）/−7.2 %（4 站三次）。"
            "落地前实测（`_probe_m10/probe_d33_split.json`）**52 条存量 0 条换边**、"
            "D12 复现 **11/11**；落地后 **53 条 / 52 类 / 22-17-14**（翼盒 18-7-7）。"
        )
        # D34 (2026-10-24).  Model FORM, and the two things it cannot fix.
        limitations.append(
            "翼盒族的**代理模型形式口径 = D34（2026-10-24 老王拍板「改形式」）**："
            "`sweep` 项在 `log y` 中以 **二次**（而非线性）进入，基为 `s = sweep_deg/20` 的 "
            "`[s, s²]`，**过原点**（`sweep=0` 处修正恰为 0，无后掠是自然原点而非抛物线上任意一点）。"
            "判据：主判据是**零泄漏的 `LOO@30`**（从 train 删掉 30° 那行再预测它），"
            "保护是 train LOO 整体不得劣化 >15 %、条件数 <1e6，`val` 仅作确认，`test` 只报一次。"
            "实测（`_probe_m11/sweep_form.json`，M5 档口径）：`LOO@30` **−22.14 % → −1.07 %**、"
            "`val` 单点 `sweep40` **−34.54 % → −3.17 %**、test MAPE **7.74 % → 6.18 %**"
            "（CI [−4.46, +0.23]，**n=7 下跨 0，不显著**）、`planform_out` 组 **25.70 % → 15.70 %**。"
            "**三次基被否**：train 里 `sweep>0` 仅 3 行且几何完全相同 ⇒ `s²`/`s³` 只在这 3 行非零，"
            "3 点定 3 参数**恰好可逆**，三次式在那 3 行拟合到机器零、40° 分支全靠硬猜；"
            "实测四个指标全不如二次（`LOO@30` −1.07 → +6.02）。**「加站数就升阶」不是配方。**"
            "**该形式只对 `max_disp` 采纳**：同样改动在 `max_w` 上 val 6.01→**1.93** 但 test "
            "8.33→**13.49**、最大 APE 26.8→**65.1 %**（崩），vM 两目标同样 test 恶化；"
            "机制在系数上可见（`max_disp` 二次项 +0.064·s+0.232·s²，线性项为正、抛物线平缓；"
            "`max_w` 是 −0.069·s+0.214·s²，线性项为负、原点处向下弯）。"
            "**D34-b（对 D32 的限定）**：`val` 只有 7 条、其中 `sweep>0` 仅 1 条（taper 中性），"
            "在本轮 4 个目标上 `val` **一律**选中二次基而 `test` 只在 `max_disp` 上支持它 ⇒ "
            "**形式类决策不能用 val 选**，须用「留最高站位」LOO；D32 的「val 选」仍适用于**档位**选择。"
            "**剩余 15.7 % 不是形式问题**（`_probe_m11/residual_diag.json`）：train 中"
            "「`sweep>0` 且 `taper≠1`」的样本数 = **0** ⇒ 交互项 `s²·(taper−1)` 在 train 上"
            "恒等于零，**不是估不准而是不可估**；残差结构为 taper 中性 −3.17 %、"
            "两个 taper 角点 +13.31 / +15.70 %。**换任何基都学不到，只有补一条带锥度的后掠算例。**"
            "**副产品**：`n_web` 与 `web_pos` 在 train 上**完全共线**（奇异值 1.3e-15，"
            "train 只有 1 条带腹板算例 ⇒ 两列都只在同一行非零），`is_T` 恒为 0 ⇒ "
            "M3 的 10 个特征实际只有 **8 个可辨识方向**；这解释了 M7「`n_web` 1→2 外推 "
            "+14.5 % 为第二不稳轴」——那条路在 train 上根本没有信息。"
        )
    if n_val == 0:
        limitations.append("整个数据集没有 val 集。")

    return {
        "schema_version": 1,
        "generator": "make_manifest.py (feagpt_repro)",
        "release_tree": "modeling",
        "regenerate": "cd feagpt_repro && python make_manifest.py --root ../FEM-Bench-Aero "
                      "--json ../FEM-Bench-Aero/manifest.json --md ../FEM-Bench-Aero/MANIFEST.md",
        "split_rule": {
            "unit": "geometry equivalence class (feagpt.manifest.geometry_class)",
            "assignment": "declared holdout regions -- feagpt/manifest.py :: HOLDOUT_REGIONS "
                          "(first match wins; no match => train; undeclared family => unassigned)",
            "target_ratios": mf.TARGET_RATIOS,
            "constraints": [
                "same equivalence class => same split (no leakage)",
                "every family must have at least one test case",
                "every case must have an explicit split (unassigned fails the check)",
                "the rule must keep reproducing the D12-locked 口径 A on the eleven cases "
                "(manifest.py :: D12_LOCKED_SPLIT)",
            ],
        },
        "summary": {
            "n_cases": len(cases),
            "n_geometry_classes": len(by_class),
            "splits": {s: len(v) for s, v in splits.items()},
            "by_family": by_family,
            "roles": dict(sorted(roles.items())),
            "n_duplicate_models": sum(d["n"] - 1 for d in dups),
            "n_leaky_classes": len(leaky),
            "xval_cases_available": paired,
        },
        "classes": {cls: sorted(mems) for cls, mems in sorted(by_class.items())},
        "cases": cases,
        "limitations": limitations,
    }


def _md(man: dict) -> str:
    s = man["summary"]
    L: list[str] = []
    L.append("# FEM-Bench-Aero · 数据集清单（M4）")
    L.append("")
    L.append("由 `make_manifest.py` 生成，**确定性**（无时间戳，重跑字节一致）。"
             "机器可读版是 `manifest.json`。")
    L.append("")
    L.append(f"- 发布树 `modeling/`：**{s['n_cases']} 条 case**，"
             f"**{s['n_geometry_classes']} 个几何等价类**")
    L.append(f"- 划分：train **{s['splits'].get('train', 0)}** / "
             f"val **{s['splits'].get('val', 0)}** / test **{s['splits'].get('test', 0)}**"
             f"（目标比例 {mf.TARGET_RATIOS['train']:.0%}:{mf.TARGET_RATIOS['val']:.0%}:{mf.TARGET_RATIOS['test']:.0%}）")
    L.append(f"- 角色：`{', '.join(f'{k} {v}' for k, v in s['roles'].items())}`")
    L.append(f"- 树内重复模型 **{s['n_duplicate_models']}**；跨集泄漏的等价类 **{s['n_leaky_classes']}**")
    L.append(f"- 交叉验证证据（`_xval/`，商业许可，**不发布**）：{s['xval_cases_available']} 条")
    L.append("")
    L.append("> **等价类**：几何（形状 + 壁厚）相同的 case 归为一类。"
             "同一类的成员**必须**在同一 split —— 这是「等价类不得跨集」的落地。")
    L.append("")

    # split tables
    for split in mf.SPLITS:
        ids = [c for c in man["cases"] if c["split"] == split]
        if not ids:
            L.append(f"## {split} （0 条）")
            L.append("")
            continue
        L.append(f"## {split} （{len(ids)} 条）")
        L.append("")
        L.append("| case | 族 | 角色 | 等价类 | 节点 | max\\|u\\| (mm) | 峰值 vM | minJ | tri3 |")
        L.append("|---|---|---|---|---:|---:|---:|---:|---:|")
        for c in ids:
            r = c["readings"]
            mu = f"{r['max_disp']:.5f}" if isinstance(r["max_disp"], (int, float)) else "—"
            vm = f"{r['max_von_mises']:.4f}" if isinstance(r["max_von_mises"], (int, float)) else "—"
            mj = f"{r['min_jacobian']:.4f}" if isinstance(r["min_jacobian"], (int, float)) else "—"
            cls = c["geometry_class"][:8]
            if c["class_size"] > 1:
                cls += f"({c['class_size']})"
            L.append(f"| `{c['case_id']}` | {c['family']} | {c['role']} | `{cls}` | "
                     f"{r['n_nodes']} | {mu} | {vm} | {mj} | {r['n_tri3']} |")
        L.append("")
        L.append("<details><summary>分配理由</summary>")
        L.append("")
        for c in ids:
            L.append(f"- `{c['case_id']}` — {c['split_reason']}")
        L.append("")
        L.append("</details>")
        L.append("")

    # equivalence classes with >1 member
    multi = {k: v for k, v in man["classes"].items() if len(v) > 1}
    L.append(f"## 多成员等价类（{len(multi)} 个）")
    L.append("")
    if not multi:
        L.append("（无 —— 每条 case 都是独立几何）")
    else:
        for cls, mems in sorted(multi.items()):
            sp = {next(c["split"] for c in man["cases"] if c["case_id"] == m) for m in mems}
            L.append(f"- `{cls[:12]}` → {', '.join(f'`{m}`' for m in mems)}"
                     f"（split: {', '.join(sorted(sp))}）")
    L.append("")

    L.append("## 已知限制")
    L.append("")
    for lim in man["limitations"]:
        L.append(f"- {lim}")
    L.append("")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="FEM-Bench-Aero root directory")
    ap.add_argument("--json", help="write the machine-readable manifest here")
    ap.add_argument("--md", help="write the human-readable index here")
    args = ap.parse_args(argv)

    man = build(Path(args.root))
    s = man["summary"]
    print(f"cases {s['n_cases']}  classes {s['n_geometry_classes']}  "
          f"splits {s['splits']}  roles {s['roles']}")
    for cls, mems in sorted(man["classes"].items()):
        if len(mems) > 1:
            print(f"  class {cls[:12]}: {', '.join(mems)}")
    if s["n_leaky_classes"]:
        print(f"  !! {s['n_leaky_classes']} class(es) span more than one split")

    if args.json:
        Path(args.json).write_text(
            json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"manifest -> {args.json}")
    if args.md:
        Path(args.md).write_text(_md(man), encoding="utf-8")
        print(f"index    -> {args.md}")
    return 0 if s["n_leaky_classes"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
