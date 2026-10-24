#!/usr/bin/env python
"""D34 收口：把「关 1 网格质量」与「关 3 双码」从 52 条口径重测到 53 条口径。

为什么单独写这一个脚本
----------------------
看板上这两张卡的数值一直是 **52 / 52**（D31 时代的最后一次性重测），D33 补进
`sweep30` 之后数据集已是 53 条，而卡片上的字没人动过 —— 这就是「印没量过的
数字」。本脚本把两件事**当场重量**，并落盘成 JSON 供看板回读：

* **关 1**：`eval_dataset._recompute` 逐 case 从 `model.msh` / `model.inp`
  重算 `min_jacobian` 与 `n_tri3`（判据 minJ ≥ 0.30 且 tri3 == 0，D10）。
* **关 3**：`_probe_m8/xval_m8.check_one` 逐 case 比 ccx 与 abaqus 的逐节点场。

判据代码**一行不复制**：关 1 直接调 `eval_dataset` 里那份（与 `verify_dataset`
同源），关 3 直接把 `xval_m8._load` 重定向到真实 outputs 目录，`check_one` 本体
原样跑。这样两处判据永远只有一份实现。

只做后处理，**不起任何求解器**（FRD / odb.json 都是历史产物）。

用法::

    python _probe_m11/gate_all53.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPRO = HERE.parent
DATASET = REPRO.parent / "FEM-Bench-Aero"

#: ⚠️ 输出路径**永远带里程碑标签**。D34 跑出来的 `gates_all53_d34.json` 是一个
#: milestone 的证据，重跑本脚本不许把它冲掉（2026-10-24 已在 `residual_diag.py`
#: 上踩过一次：结论依赖数据集的脚本，重跑即毁档）。当前默认值服务数据集的最新
#: 状态（55 条）；要复刻历史口径请显式 `--out`。
OUT = DATASET / "gates_all55_d36.json"

sys.path.insert(0, str(REPRO))
sys.path.insert(0, str(REPRO / "_probe_m8"))

import eval_dataset as ED  # noqa: E402
import xval_m8 as X  # noqa: E402

MIN_J = 0.30


def _manifest_cases() -> list[str]:
    man = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    return [c["case_id"] for c in man["cases"]]


def _manifest_family() -> dict[str, str]:
    man = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    return {c["case_id"]: c["family"] for c in man["cases"]}


def gate1(cases: list[str]) -> dict:
    # 与 eval_dataset.check 同一条初始化链：msh_quality.quality 读 .msh 要先起 gmsh，
    # 否则每一行都打 "Gmsh has not been initialized" 并返回 min = None（静默全空）。
    import gmsh

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    rows = []
    try:
        for cid in cases:
            d = DATASET / "modeling" / cid
            if not (d / "truth.json").exists():
                rows.append({"case": cid, "missing": True})
                continue
            r = ED._recompute(d)
            rows.append({
                "case": cid,
                "min_jacobian": r["min_jacobian"],
                "n_tri3": r["n_tri3"],
            })
    finally:
        gmsh.finalize()
    have = [r for r in rows if not r.get("missing") and r.get("min_jacobian") is not None]
    worst = min(have, key=lambda r: r["min_jacobian"])
    tri3_cases = [r["case"] for r in rows if (r.get("n_tri3") or 0) > 0]
    return {
        "n_cases": len(cases),
        "n_measured": len(have),
        "worst_min_jacobian": worst["min_jacobian"],
        "worst_case": worst["case"],
        "n_below_threshold": sum(1 for r in have if r["min_jacobian"] < MIN_J),
        "n_tri3_cases": len(tri3_cases),
        "n_tri3_total": sum((r.get("n_tri3") or 0) for r in rows),
        "threshold": MIN_J,
        "pass": bool(len(have) == len(cases)
                     and all(r["min_jacobian"] >= MIN_J for r in have)
                     and not tri3_cases),
        "rows": rows,
    }


def _index_outputs() -> tuple[dict, dict]:
    """case -> 出现过它的 outputs 根目录名（含 ``_probe_*`` 下的批次目录）。

    布局是 ``outputs/<case>/<case>.frd``（不是平铺），所以 glob 要下探一层；
    而 ``xval_m8._load`` 要的正是**根目录**（它自己会拼 ``root/case/case.frd``）。
    """
    ccx: dict[str, list[str]] = {}
    abq: dict[str, list[str]] = {}
    roots = sorted(REPRO.glob("outputs*")) + sorted(REPRO.glob("_probe_*/outputs*"))
    for d in roots:
        if "retired" in d.name or not d.is_dir():
            continue
        for f in d.glob("*/*.frd"):
            ccx.setdefault(f.stem, []).append(str(d.relative_to(REPRO)))
        for f in d.glob("*/*.odb.json"):
            abq.setdefault(f.name[: -len(".odb.json")], []).append(str(d.relative_to(REPRO)))
    return ccx, abq


def gate3(cases: list[str]) -> dict:
    """只对翼盒族跑 ``xval_m8.check_one`` —— 那是它的适用域。

    ⚠️ 本函数第一版把 53 条**全部**塞进这个判据，结果柱壳/开孔板/加筋板
    整族报 FAIL（平衡残差 9900 % / 700 % / 100 %）。原因不是结构有问题，
    而是**载荷口径不同**：``xval_m8`` 里写死 ``LOAD_N = 500`` 与「根截面
    |z|<tol 反力求和」，那是翼盒端部集中力的口径；柱壳是「内压 + 端弯 +
    端剪」（D20 另立「剔端载环 + 20 站截面形心挠度剖面」）、开孔板是面内
    拉伸、加筋板是 1000 N 压/拉。**族专用判据不能跨族套用**，硬套只会造出
    一整片假 FAIL。所以本脚本把范围收窄到翼盒，其余族在 ``out_of_scope``
    里如实登记，并指明各自的证据来源。
    """
    ccx_idx, abq_idx = _index_outputs()
    cur: dict[str, str] = {}
    orig_load = X._load

    def _load(root: Path, case: str):  # noqa: ANN001
        # check_one 造的是 HERE/"outputs_<suffix>" 与 HERE/"outputs_abaqus_<suffix>"，
        # 只有第二种名字里带 abaqus —— 用这个区分两侧，然后把目录换成真实位置。
        which = "abq" if "abaqus" in Path(root).name else "ccx"
        return orig_load(REPRO / cur[which], case)

    X._load = _load  # type: ignore[assignment]
    X.HERE = REPRO

    rows, missing = [], []
    for cid in cases:
        c, a = ccx_idx.get(cid), abq_idx.get(cid)
        if not c or not a:
            missing.append({"case": cid,
                            "ccx_dirs": c or [], "abaqus_dirs": a or []})
            rows.append({"case": cid, "pass": False,
                         "failures": ["missing dual-solver evidence"]})
            continue
        cur["ccx"], cur["abq"] = c[0], a[0]
        try:
            r = X.check_one(cid)
        except Exception as exc:  # noqa: BLE001
            rows.append({"case": cid, "pass": False,
                         "failures": ["%s: %s" % (type(exc).__name__, exc)],
                         "dirs": {"ccx": c[0], "abaqus": a[0]}})
            continue
        r["dirs"] = {"ccx": c[0], "abaqus": a[0]}
        rows.append(r)

    X._load = orig_load  # type: ignore[assignment]

    ok = [r for r in rows if r.get("pass")]
    eq = [r["equilibrium"]["worst_residual_pct"] for r in ok]
    gap = [r["max_disp"]["gap_pct"] for r in ok if r["max_disp"]["gap_pct"] is not None]
    med = [r["stress_field"]["median_pct"] for r in ok
           if r["stress_field"]["median_pct"] is not None]
    p90 = [r["stress_field"]["p90_pct"] for r in ok
           if r["stress_field"]["p90_pct"] is not None]
    return {
        "scope": "wingbox only (xval_m8 判据的适用域：500 N 端部集中力 + 根截面反力平衡)",
        "n_cases": len(cases),
        "n_pass": len(ok),
        "n_missing": len(missing),
        "missing": missing,
        "pass": bool(len(ok) == len(cases)),
        "equilibrium_pct": {"min": min(eq) if eq else None,
                            "max": max(eq) if eq else None},
        "max_disp_gap_pct": {"min": min(gap) if gap else None,
                             "max": max(gap) if gap else None},
        "stress_median_pct": {"min": min(med) if med else None,
                              "max": max(med) if med else None},
        "stress_p90_pct": {"min": min(p90) if p90 else None,
                           "max": max(p90) if p90 else None},
        "failing": [{"case": r["case"], "failures": r.get("failures")}
                    for r in rows if not r.get("pass")],
        "rows": rows,
    }


#: 非翼盒族的双码证据来源。**不要**拿 xval_m8 去套它们（载荷口径不同）。
OUT_OF_SCOPE_EVIDENCE = {
    "fuselage_barrel": "D20 口径（剔端载环后的结构 max|u| + 20 站截面形心挠度剖面）；"
                       "证据为 b3/b6 批次的控制台核对，未落 JSON —— 如实记为"
                       "「有核对、无机器可读产物」",
    "open_hole_panel": "孔边逐节点 vM 中位差 + max|u| 1 % 口径（D8/D28）；"
                       "产物 _probe_b7/_b7_gate3.json、_t4_probe/verify_hole_full.json、"
                       "FEM-Bench-Aero/verify_hole_t7.json",
    "stiffened_panel": "平板双码；素板中面场在 Abaqus 侧恒为 0 ⇒ 逐节点场判据"
                       "「不适用」，工具如实报告而非假装通过（见关 3 说明）",
}


def main() -> int:
    global OUT
    if "--out" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--out") + 1]).resolve()
    cases = _manifest_cases()
    fam = _manifest_family()
    print("=" * 96)
    print("  关 1 + 关 3 全量重测（n = %d）" % len(cases))
    print("=" * 96)

    g1 = gate1(cases)
    print("\n[关 1] 网格质量")
    print("  测量 %d / %d 条；最差 minJ = %.4f (%s)；低于 %.2f 的 %d 条"
          % (g1["n_measured"], g1["n_cases"], g1["worst_min_jacobian"],
             g1["worst_case"], g1["threshold"], g1["n_below_threshold"]))
    print("  tri3 合计 %d，非零 case %d 条  => %s"
          % (g1["n_tri3_total"], g1["n_tri3_cases"],
             "PASS" if g1["pass"] else "FAIL"))

    g3 = gate3([c for c in cases if fam[c] == "wingbox"])
    print("\n[关 3] 双码（仅翼盒族 —— xval_m8 判据的适用域）")
    print("  通过 %d / %d 条；缺证据 %d 条  => %s"
          % (g3["n_pass"], g3["n_cases"], g3["n_missing"],
             "PASS" if g3["pass"] else "FAIL"))
    if g3["n_pass"]:
        e, d, m = (g3["equilibrium_pct"], g3["max_disp_gap_pct"],
                   g3["stress_median_pct"])
        print("  平衡残差 %.2e %% – %.2e %%；max|u| 差 %.3f %% – %.3f %%；"
              "vM 中位差 %.3f %% – %.3f %%"
              % (e["min"], e["max"], d["min"], d["max"], m["min"], m["max"]))
    for f in g3["failing"][:10]:
        print("   FAIL %-46s %s" % (f["case"], f["failures"]))
    print("  其余 %d 条不适用本判据（载荷口径不同），证据见 out_of_scope"
          % (len(cases) - g3["n_cases"]))

    payload = {
        "milestone": "M13/D36",
        "note": "关 1 用 eval_dataset._recompute（与 verify_dataset 同源，全 %d 条）；"
                "关 3 用 xval_m8.check_one（判据零复制）但**只对翼盒族**——"
                "族专用判据不能跨族套用，其余族登记为 out_of_scope。"
                "纯后处理，未起求解器。" % len(cases),
        "manifest": str(DATASET / "manifest.json"),
        "gate1_mesh_quality": g1,
        "gate3_dual_solver": g3,
        "out_of_scope": {fam_: OUT_OF_SCOPE_EVIDENCE[fam_]
                         for fam_ in ("fuselage_barrel", "open_hole_panel",
                                      "stiffened_panel")},
        "all_ok": bool(g1["pass"] and g3["pass"]),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("\nwritten -> %s" % OUT)
    print("VERDICT", "PASS" if payload["all_ok"] else "FAIL")
    return 0 if payload["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
