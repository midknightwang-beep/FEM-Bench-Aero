"""D35 落地复核：真 ``split_of`` 逐条重跑，换边清单必须与探针预测逐字一致。

探针（``d35_split_probe.py``）是 monkeypatch 模拟，预测「换边 1 条：
``sweep20_taper060`` test→train」。本脚本在规则真正落地后用**真函数**复核，
判据是「预测 == 实测」，不是「看起来差不多」。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "feagpt_repro"))

from feagpt import manifest as mf          # noqa: E402
from feagpt.spec import FEASpec           # noqa: E402

BENCH = ROOT / "FEM-Bench-Aero"
OUT = Path(__file__).resolve().parent


def main() -> int:
    man = json.loads((BENCH / "manifest.json").read_text(encoding="utf-8"))
    probe = json.loads((OUT / "d35_split_probe.json").read_text(encoding="utf-8"))
    predicted = {m["case"]: (m["old"], m["new"]) for m in probe["moved"]}

    rows, moved = [], []
    for c in man["cases"]:
        cid = c["case_id"]
        spec = FEASpec.from_json(BENCH / "modeling" / cid / "spec.json")
        side, why = mf.split_of(spec)
        rows.append({"case": cid, "split": side, "reason": why,
                     "family": mf.family_of(spec)})
        if side != c["split"]:
            moved.append({"case": cid, "manifest": c["split"], "now": side})

    got = {m["case"]: (m["manifest"], m["now"]) for m in moved}
    ok = got == predicted

    print(f"存量 {len(rows)} 条，换边 {len(moved)} 条")
    for m in moved:
        print(f"  {m['case']:<44}{m['manifest']:>6} -> {m['now']:<6}"
              f"  {dict((r['case'], r['reason']) for r in rows)[m['case']]}")
    print(f"\n预测 == 实测：{'PASS' if ok else 'FAIL'}")
    if not ok:
        print("  只在预测里:", set(predicted) - set(got))
        print("  只在实测里:", set(got) - set(predicted))
        print("  都有但不同:", {k: (predicted[k], got[k])
                                for k in set(predicted) & set(got)
                                if predicted[k] != got[k]})

    from collections import Counter
    cnt = Counter(r["split"] for r in rows)
    fam = {}
    for r in rows:
        fam.setdefault(r["family"], Counter())[r["split"]] += 1
    print("\n分布:", dict(sorted(cnt.items())))
    for f, c in sorted(fam.items()):
        print(f"  {f:<20}{dict(sorted(c.items()))}")

    # 关键格子：sweep>0 且 taper!=1 现在分布在哪
    spec_rows = []
    for r in rows:
        spec = FEASpec.from_json(BENCH / "modeling" / r["case"] / "spec.json")
        af = spec.airfoil
        sw = float(getattr(af, "sweep_deg", 0.0) or 0.0)
        tr = float(getattr(af, "tip_chord_ratio", 1.0) or 1.0)
        if sw > 0 and abs(tr - 1.0) > 1e-9:
            spec_rows.append({"case": r["case"], "split": r["split"],
                              "sweep": sw, "taper": tr})
    print("\n关键格子 sweep>0 & taper!=1：")
    for s in spec_rows:
        print(f"  {s['case']:<44}{s['split']:<6}sweep={s['sweep']:g} taper={s['taper']:g}")
    n_train = sum(1 for s in spec_rows if s["split"] == "train")
    print(f"  => train 交互样本 {n_train} 条（D34 时为 0）")

    (OUT / "d35_landed.json").write_text(
        json.dumps({"verdict": "PASS" if ok else "FAIL",
                    "n_cases": len(rows),
                    "moved": moved, "predicted": predicted,
                    "counts": dict(sorted(cnt.items())),
                    "families": {f: dict(sorted(c.items())) for f, c in fam.items()},
                    "interaction_cell": spec_rows,
                    "n_train_interaction": n_train,
                    "rows": rows}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\n-> {(OUT / 'd35_landed.json').name}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
