"""D33 before/after: what did one extra train station actually buy?

Two baseline runs, same 7 val and same 7 test cases, same code, one difference:
train grew from 17 to 18 wing boxes (``sweep30`` added).  Everything below is a
*read* of ``baseline_d31.json`` and ``baseline_d33.json`` -- nothing is re-fitted
here, so the numbers cannot drift from the two reports.

Alignment is the one thing that can go wrong silently, so it is asserted rather
than assumed: the APE vectors are matched to case ids by the manifest's case
order, and the script checks that the case the report itself tags
``planform_out`` carries the APE the report itself records for that group.  If
those disagree, the ids and the numbers are misaligned and nothing else here is
worth reading.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "FEM-Bench-Aero"
OUT = Path(__file__).resolve().parent

TIERS = ("M1 beam(1p)", "M2X full-pow(7p)", "M3 ridge(10f)", "M5 hybrid(10f+phys)")
TARGETS = ("max_disp", "max_w", "max_von_mises_midsurface", "max_von_mises")


def main() -> int:
    a = json.loads((BENCH / "baseline_d31.json").read_text(encoding="utf-8"))
    b = json.loads((BENCH / "baseline_d33.json").read_text(encoding="utf-8"))
    man = json.loads((BENCH / "manifest.json").read_text(encoding="utf-8"))
    order = [c["case_id"] for c in man["cases"]
             if c["split"] == "test" and c["family"] == "wingbox"]
    fails: list[str] = []

    # ---- alignment self-check --------------------------------------------- #
    planform = a["test_groups"]["planform_out"][0]
    if planform not in order:
        fails.append(f"planform_out case {planform!r} not in the test order")
    else:
        i = order.index(planform)
        got = a["targets"]["max_disp"]["M5 hybrid(10f+phys)"]["ape_test"][i]
        want = a["test_group_ape"]["max_disp"]["planform_out"]["M5"]
        if abs(got - want) > 0.05:
            fails.append(f"APE/id misalignment: case-order says {got:.2f}, "
                         f"group table says {want:.2f} for {planform}")
    if fails:
        print("\n".join(fails))
        return 1

    doc: dict = {"digest": {"d31": a["dataset_digest"], "d33": b["dataset_digest"]},
                 "n": {"d31": a["n"], "d33": b["n"]},
                 "splits": {"d31": "17/7/7", "d33": "18/7/7"},
                 "test_order": order, "tiers": {}, "per_case": {}, "fails": fails}

    print("=" * 96)
    print("trainLOO / val / test MAPE before -> after  (same val 7, same test 7)")
    print(f"  {'target':<28}{'tier':<24}{'trainLOO':>15}{'val':>15}{'test':>15}")
    for tgt in TARGETS:
        doc["tiers"][tgt] = {}
        for tier in TIERS:
            ra, rb = a["targets"][tgt][tier], b["targets"][tgt][tier]
            pair = lambda k: f"{ra[k]:.2f}->{rb[k]:.2f}"
            print(f"  {tgt:<28}{tier:<24}{pair('train_loo_mape'):>15}"
                  f"{pair('val_mape'):>15}{pair('test_mape'):>15}")
            doc["tiers"][tgt][tier] = {
                k: {"before": round(ra[k], 2), "after": round(rb[k], 2),
                    "delta": round(rb[k] - ra[k], 2)}
                for k in ("train_loo_mape", "val_mape", "test_mape")}

    print("\nper-case test APE, M5 (the selected learner)")
    print(f"  {'case':<44}{'max_disp':>18}{'max_w':>18}")
    for tgt in ("max_disp", "max_w"):
        doc["per_case"][tgt] = {}
        ra = a["targets"][tgt]["M5 hybrid(10f+phys)"]["ape_test"]
        rb = b["targets"][tgt]["M5 hybrid(10f+phys)"]["ape_test"]
        for cid, e1, e2 in zip(order, ra, rb):
            doc["per_case"][tgt][cid] = {"before": round(e1, 2),
                                         "after": round(e2, 2),
                                         "delta": round(e2 - e1, 2)}
    for i, cid in enumerate(order):
        d1 = doc["per_case"]["max_disp"][cid]
        d2 = doc["per_case"]["max_w"][cid]
        print(f"  {cid:<44}{d1['before']:>7.1f}->{d1['after']:<7.1f}"
              f"{d2['before']:>7.1f}->{d2['after']:<7.1f}")

    print("\nby extrapolation mechanism, M5, max_disp (d31 -> d33)")
    doc["groups"] = {}
    for g, ids in a["test_groups"].items():
        v0 = a["test_group_ape"]["max_disp"][g]["M5"]
        v1 = b["test_group_ape"]["max_disp"][g]["M5"]
        doc["groups"][g] = {"n": len(ids), "before": v0, "after": v1,
                            "delta": round(v1 - v0, 2), "cases": ids}
        print(f"  {g:<16}n={len(ids)}  {v0:6.1f} -> {v1:6.1f}   {v1 - v0:+6.1f} pp")

    print("\nverdict")
    d = doc["tiers"]["max_disp"]["M5 hybrid(10f+phys)"]["test_mape"]
    w = doc["tiers"]["max_w"]["M5 hybrid(10f+phys)"]["test_mape"]
    print(f"  primary target max_disp  test {d['before']:.2f} -> {d['after']:.2f}"
          f"  ({d['delta']:+.2f} pp)")
    print(f"  secondary max_w          test {w['before']:.2f} -> {w['after']:.2f}"
          f"  ({w['delta']:+.2f} pp)  <- the station hurts the secondary target")
    doc["verdict"] = "PASS"
    p = OUT / "d33_vs_d31.json"
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
