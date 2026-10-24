"""D31 gate: prove the landed rule moves nothing, then read the batch's splits.

The previous probe (`probe_d31_wingbox_size.py`) carried its *own copy* of the
rule so it could run before the rule existed.  That copy is now a liability: a
probe that tests a copy proves nothing about the code that ships.  This one
imports ``split_of`` and compares against the archive, which is the only thing
the D12-frozen split cares about.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "feagpt_repro"))

from feagpt.spec import FEASpec                        # noqa: E402
from feagpt.manifest import split_of, infer_role        # noqa: E402

BENCH = ROOT / "FEM-Bench-Aero"
M8 = Path(__file__).resolve().parent


def main() -> int:
    # the archived split, as shipped in the manifest
    man = json.loads((BENCH / "manifest.json").read_text(encoding="utf-8"))
    shipped = {c["case_id"]: (c["split"], c["split_reason"]) for c in man["cases"]}

    print("=== 1. 落地后的规则 vs 冻结的 manifest(44 条) ===")
    drift = []
    for cid, (old_split, old_why) in sorted(shipped.items()):
        spec = FEASpec.from_json(BENCH / "modeling" / cid / "spec.json")
        new_split, new_why = split_of(spec)
        if new_split != old_split:
            drift.append((cid, old_split, new_split))
            print(f"  ! {cid}: {old_split} -> {new_split}  ({new_why})")
    print(f"  漂移 {len(drift)} 条 / {len(shipped)} 条")

    print("\n=== 2. 本批 8 条的落位 ===")
    rows = []
    for p in sorted(glob.glob(str(M8 / "naca4412_wingbox_size_*.spec.json"))):
        tag = os.path.basename(p).replace("naca4412_wingbox_", "").replace(".spec.json", "")
        spec = FEASpec.from_json(Path(p))
        sp, why = split_of(spec)
        rows.append(dict(tag=tag, span=float(spec.airfoil.span),
                         skin=float(spec.airfoil.skin_thickness),
                         role=infer_role(spec), split=sp, reason=why,
                         cls=None))
        print(f"  {tag:<24}span={spec.airfoil.span:>6.0f} "
              f"skin={spec.airfoil.skin_thickness:>4g}  "
              f"{rows[-1]['role']:<9}{sp:<6}{why}")

    want = {"size_span1600": "train", "size_span2400": "train",
            "size_skin2": "train", "size_skin4": "train",
            "size_span3000": "val", "size_skin1p5": "val",
            "size_span3000_skin1p5": "test", "size_span2400_skin2": "test"}
    bad = [r for r in rows if want.get(r["tag"]) != r["split"]]
    print(f"\n  与设计表不一致：{len(bad)} 条"
          + ("" if not bad else "  -> " + ", ".join(f"{b['tag']}={b['split']}" for b in bad)))

    ok = not drift and not bad
    out = M8 / "probe_d31_landed.json"
    out.write_text(json.dumps({
        "shipped_cases": len(shipped),
        "split_drift": len(drift),
        "drift_detail": drift,
        "batch": rows,
        "design_mismatch": len(bad),
        "pass": ok,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{'PASS' if ok else 'FAIL'}  -> {out.name}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
