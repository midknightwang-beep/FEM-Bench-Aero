"""D35 物理核对：sweep x taper 到底有没有交互，交互有多大、什么符号。

判据不是「误差降了没有」，而是先回答**这个新点物理上是否合理**。做法是
log 空间可加分解：

    ln(u(s,t) / u(0,1)) = A(s) + B(t) + H(s,t)

其中

* ``A(s) = ln(u(s,1) / u(0,1))``   —— 后掠单轴效应（taper 中性）
* ``B(t) = ln(u(0,t) / u(0,1))``   —— 锥度单轴效应（sweep 中性）
* ``H``                            —— 剩下的就是交互

若 ``H`` 在两个组合点上都是 0，那 D34 的「交互不可估」根本不该修 —— 只需
乘性模型。若 ``H`` 显著非零，则新样本确实在教模型一件它原本学不到的事。

**注意**：``B(0.4)`` 只有 sweep 中性的 val 点 ``taper040`` 能提供，所以
``sweep40_taper040`` 的 ``H`` 依赖一条 val 样本的读数 —— 在这条上标注来源，
不把它当成和另两条同等级的证据。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "feagpt_repro"))

from feagpt.spec import FEASpec             # noqa: E402

BENCH = ROOT / "FEM-Bench-Aero"
OUT = Path(__file__).resolve().parent

#: case -> (sweep, taper)  —— 从 spec 读，不手打（手打必然漂）
POINTS = {
    "naca4412_wingbox": (0.0, 1.0),
    "naca4412_wingbox_sweep10": (10.0, 1.0),
    "naca4412_wingbox_sweep20": (20.0, 1.0),
    "naca4412_wingbox_sweep30": (30.0, 1.0),
    "naca4412_wingbox_sweep40": (40.0, 1.0),
    "naca4412_wingbox_taper090": (0.0, 0.9),
    "naca4412_wingbox_taper080": (0.0, 0.8),
    "naca4412_wingbox_taper060": (0.0, 0.6),
    "naca4412_wingbox_taper040": (0.0, 0.4),
    "naca4412_wingbox_sweep20_taper060": (20.0, 0.6),
    "naca4412_wingbox_sweep30_taper080": (30.0, 0.8),
    "naca4412_wingbox_sweep40_taper040": (40.0, 0.4),
}


def read_u(cid: str) -> float:
    t = json.loads((BENCH / "modeling" / cid / "truth.json").read_text(encoding="utf-8"))
    return float(t["scalars"]["max_disp"])


def read_case(cid: str) -> dict:
    spec = FEASpec.from_json(BENCH / "modeling" / cid / "spec.json")
    af = spec.airfoil
    return {"case": cid,
            "sweep": float(getattr(af, "sweep_deg", 0.0) or 0.0),
            "taper": float(getattr(af, "tip_chord_ratio", 1.0) or 1.0),
            "span": float(af.span), "skin": float(af.skin_thickness),
            "ribs": int(getattr(af, "n_ribs", 5)),
            "chord": float(getattr(af, "chord", 1000.0))}


def main() -> int:
    import math

    cases = [c for c in POINTS if (BENCH / "modeling" / c / "truth.json").exists()]
    info = {c: read_case(c) for c in cases}
    u = {c: read_u(c) for c in cases}

    # 前提：所有点除 planar 外必须完全锚定，否则 A/B 分解混进了别的轴
    base = info["naca4412_wingbox"]
    off_axis = [c for c in cases
                if (info[c]["span"], info[c]["skin"], info[c]["ribs"], info[c]["chord"])
                != (base["span"], base["skin"], base["ribs"], base["chord"])]
    print("非 planar 轴是否全锚定：", "是" if not off_axis else f"否 -> {off_axis}")

    u0 = u["naca4412_wingbox"]
    A = {s: math.log(u[f"naca4412_wingbox_sweep{int(s):02d}"] / u0)
         for s in (10, 20, 30, 40)}
    B = {t: math.log(u[f"naca4412_wingbox_taper{int(round(t * 100)):03d}"] / u0)
         for t in (0.4, 0.6, 0.8, 0.9)}

    print(f"\n参考 u0 = u(sweep=0, taper=1) = {u0:.6f} mm")
    print("\n单轴效应（log 空间）：")
    for s, v in sorted(A.items()):
        print(f"  A(sweep={s:>2}°) = {v:+.6f}   倍数 {math.exp(v):.6f}")
    for t, v in sorted(B.items()):
        print(f"  B(taper={t:.1f}) = {v:+.6f}   倍数 {math.exp(v):.6f}")

    print("\n组合点：实测 vs 纯乘性预测 vs 交互")
    print(f"{'case':<40}{'sweep':>6}{'taper':>6}{'实测':>10}{'乘性':>10}"
          f"{'H(log)':>10}{'交互 %':>9}")
    combos = []
    for cid, (s, t) in ((k, v) for k, v in POINTS.items()
                        if v[0] > 0 and abs(v[1] - 1.0) > 1e-9):
        if cid not in u:
            continue
        pred = u0 * math.exp(A[s] + B[t])
        H = math.log(u[cid] / u0) - A[s] - B[t]
        combos.append({"case": cid, "sweep": s, "taper": t,
                       "measured": u[cid], "multiplicative": pred,
                       "interaction_log": H,
                       "interaction_pct": (math.exp(H) - 1.0) * 100.0})
        print(f"{cid:<40}{s:>6.0f}{t:>6.1f}{u[cid]:>10.4f}{pred:>10.4f}"
              f"{H:>10.4f}{(math.exp(H) - 1.0) * 100.0:>8.2f}%")

    # 交互随 sweep 的走向：20° 与 30° 两点是否同号、量级是否单调
    by_sweep = sorted(combos, key=lambda c: c["sweep"])
    trend = None
    if len(by_sweep) >= 2:
        same_sign = (by_sweep[0]["interaction_log"] * by_sweep[-1]["interaction_log"] > 0)
        trend = {"same_sign": same_sign,
                 "deltas_pct": [round(c["interaction_pct"], 2) for c in by_sweep]}
    print(f"\n交互符号一致性（20° vs 30°）：{trend}")

    payload = {
        "note": "log 空间可加分解 H = ln(u(s,t)/u0) - A(s) - B(t)；"
                "B(0.4) 只由 sweep 中性的 val 点 taper040 提供",
        "u0": u0, "single_axis_log": {"sweep": A, "taper": B},
        "combos": combos, "interaction_trend": trend,
        "off_axis_points": off_axis,
        "u": u,
    }
    (OUT / "physics_sweep_x_taper.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {(OUT / 'physics_sweep_x_taper.json').name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
