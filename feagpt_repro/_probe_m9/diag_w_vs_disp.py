"""M9 diagnostic: is ``max_w`` a legitimate scalar proxy target for the wingbox family?

Context
-------
The M8 baseline reported ``max_w`` test MAPE 4.17 % against ``max_disp`` 7.96 %,
and I recommended making ``max_w`` *the* wingbox proxy target.  Before that went
into the decision log it had to survive two questions:

  (a) what IS max_w, physically?   ``post.py:576`` computes ``max(|DISP[2]|)``,
      i.e. the **z component**.  In this deck z is the SPAN axis and the load is
      ``*CLOAD, DOF 2`` = **y**.  So max_w is the SPANWISE displacement, not the
      bending deflection.  Bending deflection is max|v| (y), and it equals
      max_disp to within 0.07 %.

  (b) is 4.17 % a smaller error on the same question, or a smaller error because
      the question changed?  Both targets are computed on the same 7 test cases,
      so the honest comparison drops the SAME case from both, not each model's
      own worst case.

Verdict is written to ``w_vs_disp_diag.json`` next to this file.

Run:  python diag_w_vs_disp.py
Reads only shipped truth.json / model.results.json / .frd and baseline_d31.json.
No solver is invoked.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
ROOT = REPO.parent / "FEM-Bench-Aero"
sys.path.insert(0, str(REPO))

from feagpt.post import parse_frd  # noqa: E402

BASE_FRD = REPO / "outputs" / "naca4412_wingbox" / "naca4412_wingbox.frd"
D31 = [("span1600", 1600, 3.0), ("span2400", 2400, 3.0), ("span3000", 3000, 3.0),
       ("skin1p5", 2000, 1.5), ("skin2", 2000, 2.0), ("skin4", 2000, 4.0)]


def comp_peaks(path: Path) -> tuple[float, float, float]:
    """(max|u|_2, max|v|, max|w|) read off the shipped .frd."""
    disp = parse_frd(str(path))["results"]["DISP"]
    eu = max(math.sqrt(sum(c * c for c in v)) for v in disp.values())
    ev = max(abs(v[1]) for v in disp.values())
    ew = max(abs(v[2]) for v in disp.values())
    return eu, ev, ew


def loglog_slope(pairs):
    xs = [math.log(a) for a, _ in pairs]
    ys = [math.log(b) for _, b in pairs]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    return sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / sum((a - mx) ** 2 for a in xs)


def main() -> int:
    out: dict = {"probe": "M9 / max_w as wingbox proxy target", "checks": {}}
    fails: list[str] = []

    # ---- 1. which axis is which, and which DOF is loaded ------------------ #
    m = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    wb = [c for c in m["cases"] if c["family"] == "wingbox"]
    base = next(c for c in wb if c["case_id"] == "naca4412_wingbox")
    d = parse_frd(str(BASE_FRD))
    nodes, disp = d["nodes"], d["results"]["DISP"]
    rng = {ax: (min(v[i] for v in nodes.values()), max(v[i] for v in nodes.values()))
           for i, ax in enumerate("xyz")}
    rib_z = json.loads((ROOT / "modeling" / "naca4412_wingbox" / "truth.json")
                       .read_text(encoding="utf-8"))["topology"]["geometry"]["rib_z_planes"]
    out["checks"]["axes"] = {
        "bbox": {k: [round(a, 2), round(b, 2), round(b - a, 2)] for k, (a, b) in rng.items()},
        "rib_z_planes": rib_z,
        "z_is_span": abs(rng["z"][1] - 2000.0) < 10.0,
        "load_dof": 2,
        "load_axis": "y",
    }
    if not out["checks"]["axes"]["z_is_span"]:
        fails.append("z is not the span axis; max_w interpretation invalid")

    eu, ev, ew = comp_peaks(BASE_FRD)
    out["checks"]["base_case_peaks"] = {
        "max_disp": round(eu, 6), "max_v_y": round(ev, 6), "max_w_z": round(ew, 6),
        "v_over_u": round(ev / eu, 5), "w_over_u": round(ew / eu, 5),
    }

    # ---- 2. max|v| == max_disp ?  (over every case with an .frd on disk) -- #
    frds = sorted(REPO.glob("outputs/naca4412_wingbox*/*.frd"))
    frds += sorted(REPO.glob("_probe_m8/outputs_size_*/naca4412_*/*.frd"))
    ratios = []
    for f in frds:
        a, b, _ = comp_peaks(f)
        ratios.append(b / a)
    out["checks"]["max_v_equals_max_disp"] = {
        "n_frd": len(frds), "min": round(min(ratios), 6), "max": round(max(ratios), 6),
        "spread_pct": round((max(ratios) / min(ratios) - 1) * 100, 4),
    }
    if max(ratios) / min(ratios) - 1 > 0.01:
        fails.append("max|v| no longer tracks max_disp within 1 %")

    # ---- 3. power-law exponents: max_w is a DIFFERENT quantity ------------ #
    pts = {"base": (2000.0, 3.0, (eu, ev, ew))}
    for tag, sp, sk in D31:
        f = REPO / "_probe_m8" / f"outputs_size_{tag}" / f"naca4412_wingbox_size_{tag}" / \
            f"naca4412_wingbox_size_{tag}.frd"
        pts[tag] = (sp, sk, comp_peaks(f))
    span = [(pts[t][0], pts[t][2]) for t in ("span1600", "base", "span2400", "span3000")]
    skin = [(pts[t][1], pts[t][2]) for t in ("skin1p5", "skin2", "base", "skin4")]
    expo = {}
    for i, nm in enumerate(("max_disp", "max_v_y", "max_w_z")):
        expo[nm] = {"span": round(loglog_slope([(a, b[i]) for a, b in span]), 4),
                    "skin": round(loglog_slope([(a, b[i]) for a, b in skin]), 4)}
    out["checks"]["exponents"] = expo
    out["checks"]["exponents"]["beam_theory"] = {"span": 3.0, "skin": -1.0}
    # max_w must NOT behave like the bending quantity, otherwise the whole
    # distinction collapses and the recommendation is moot.
    if abs(expo["max_w_z"]["span"] - expo["max_disp"]["span"]) < 0.3:
        fails.append("max_w follows the same span power as max_disp")

    # ---- 4. sensitivity to sweep: does max_w dodge the hard axis? ---------- #
    def truth(cid):
        p = ROOT / "modeling" / cid / "truth.json"
        t = json.loads(p.read_text(encoding="utf-8"))["scalars"]
        s = json.loads((ROOT / "modeling" / cid / "spec.json")
                       .read_text(encoding="utf-8"))["airfoil"]
        return s["sweep_deg"], s["tip_chord_ratio"], t["max_disp"], t["max_w"]

    b0 = truth("naca4412_wingbox")
    sweep_tbl = {}
    for cid in ("naca4412_wingbox_sweep10", "naca4412_wingbox_sweep20",
                "naca4412_wingbox_sweep40", "naca4412_wingbox_taper040",
                "naca4412_wingbox_sweep20_taper060",
                "naca4412_wingbox_sweep40_taper040"):
        sw, tp, u, w = truth(cid)
        sweep_tbl[cid.replace("naca4412_wingbox_", "")] = {
            "sweep": sw, "taper": tp,
            "disp_x_base": round(u / b0[2], 3), "w_x_base": round(w / b0[3], 3)}
    out["checks"]["sweep_sensitivity"] = sweep_tbl
    hard = sweep_tbl["sweep40_taper040"]
    out["checks"]["hard_case_amplification"] = {
        "disp_x": hard["disp_x_base"], "w_x": hard["w_x_base"],
        "w_is_less_sensitive_by": round(1 - (hard["w_x_base"] - 1) / (hard["disp_x_base"] - 1), 3),
    }

    # ---- 5. same-sample comparison on the test errors ---------------------- #
    bl = json.loads((ROOT / "baseline_d31.json").read_text(encoding="utf-8"))
    te = [c["case_id"] for c in wb if c["split"] == "test"]
    tier = "M5 hybrid(10f+phys)"
    ape = {k: bl["targets"][k][tier]["ape_test"]
           for k in ("max_disp", "max_w", "max_von_mises_midsurface")}
    n = len(te)
    i5 = te.index("naca4412_wingbox_sweep40_taper040")
    per_case = {}
    for i, cid in enumerate(te):
        per_case[cid] = {k: ape[k][i] for k in ape}
    out["checks"]["per_case_ape"] = per_case

    def mean(v):
        return round(sum(v) / len(v), 3)

    same = {k: mean([v for j, v in enumerate(ape[k]) if j != i5]) for k in ape}
    full = {k: mean(v) for k, v in ape.items()}
    drop_own = {k: mean(sorted(v)[:-1]) for k, v in ape.items()}
    out["checks"]["test_comparison"] = {
        "all_cases": full,
        "drop_sweep40_from_BOTH": same,
        "drop_each_targets_own_worst": drop_own,
        "note": "cross-target MAPE must drop the SAME case, not each model's own worst",
    }
    out["checks"]["verdict_on_max_w"] = {
        "wins_on_mean_with_hard_case": full["max_w"] < full["max_disp"],
        "wins_on_mean_without_it": same["max_w"] < same["max_disp"],
        "conclusion": (
            "max_w's advantage is produced by ONE test case (sweep40_taper040). "
            "Remove it from both targets and max_disp is better.  max_w is the "
            "spanwise displacement (span^%.2f), which is 2.4x less sensitive to "
            "sweep than the bending deflection -- so it masks the single worst "
            "defect of the dataset instead of measuring it."
            % expo["max_w_z"]["span"]),
    }

    # ---- 6. can max_w even be used on the other families? ------------------ #
    fam = {}
    for f, pat in (("open_hole_panel", "open_hole*"), ("fuselage_barrel", "*barrel*"),
                   ("stiffened_panel", "*stiffened*")):
        rows = []
        for cid in sorted({c["case_id"] for c in m["cases"] if c["family"] == f}):
            t = json.loads((ROOT / "modeling" / cid / "truth.json")
                           .read_text(encoding="utf-8"))["scalars"]
            u, w = t["max_disp"], t.get("max_w")
            rows.append((cid, u, w, (w / u) if u else None))
        r = [x[3] for x in rows if x[3] is not None]
        fam[f] = {"n": len(rows),
                  "w_over_u_min": round(min(r), 6) if r else None,
                  "w_over_u_max": round(max(r), 6) if r else None}
    out["checks"]["cross_family_usability"] = fam
    if not (fam["open_hole_panel"]["w_over_u_max"] == 0.0):
        fails.append("open_hole max_w is not exactly zero; re-check the claim")

    # ---- 7. w/u spread over the whole wingbox family ---------------------- #
    ru = []
    for c in wb:
        t = json.loads((ROOT / c["tree"] / c["case_id"] / "truth.json")
                       .read_text(encoding="utf-8"))["scalars"]
        ru.append(t["max_w"] / t["max_disp"])
    out["checks"]["wingbox_w_over_u"] = {
        "n": len(ru), "min": round(min(ru), 5), "max": round(max(ru), 5),
        "spread": round(max(ru) / min(ru), 3),
    }

    out["fails"] = fails
    out["verdict"] = "PASS" if not fails else "CHECK"
    (HERE / "w_vs_disp_diag.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- console ---------------------------------------------------------- #
    print("axes:", out["checks"]["axes"]["bbox"], " z is span:", out["checks"]["axes"]["z_is_span"])
    print("base peaks:", out["checks"]["base_case_peaks"])
    print("max|v|/max|u| over %d frd: %.6f .. %.6f (spread %.4f %%)"
          % (len(frds), min(ratios), max(ratios),
             (max(ratios) / min(ratios) - 1) * 100))
    print("\n%-14s %10s %10s" % ("", "span exp", "skin exp"))
    for nm in ("max_disp", "max_v_y", "max_w_z"):
        print("%-14s %10.4f %10.4f" % (nm, expo[nm]["span"], expo[nm]["skin"]))
    print("%-14s %10.3f %10.3f" % ("beam theory", 3.0, -1.0))
    print("\nsweep sensitivity (x base):")
    for k, v in sweep_tbl.items():
        print("  %-22s disp x%.3f   w x%.3f" % (k, v["disp_x_base"], v["w_x_base"]))
    print("\n%-36s %10s %10s %10s" % ("test case", "max_disp", "max_w", "vM mid"))
    for cid in te:
        r = per_case[cid]
        print("%-36s %9.1f%% %9.1f%% %9.1f%%"
              % (cid.replace("naca4412_wingbox_", ""), r["max_disp"], r["max_w"],
                 r["max_von_mises_midsurface"]))
    print("%-36s %9.1f%% %9.1f%% %9.1f%%" % ("MEAN (all 7)", full["max_disp"],
                                             full["max_w"], full["max_von_mises_midsurface"]))
    print("%-36s %9.1f%% %9.1f%% %9.1f%%" % ("MEAN (drop sweep40 from BOTH)",
                                             same["max_disp"], same["max_w"],
                                             same["max_von_mises_midsurface"]))
    print("%-36s %9.1f%% %9.1f%% %9.1f%%" % ("MEAN (drop each own worst)",
                                             drop_own["max_disp"], drop_own["max_w"],
                                             drop_own["max_von_mises_midsurface"]))
    print("\ncross-family max_w/max_disp:", json.dumps(fam, ensure_ascii=False))
    print("wingbox w/u: %.5f .. %.5f (x%.2f, n=%d)"
          % (out["checks"]["wingbox_w_over_u"]["min"], out["checks"]["wingbox_w_over_u"]["max"],
             out["checks"]["wingbox_w_over_u"]["spread"], len(ru)))
    print("\nVERDICT:", out["verdict"], fails if fails else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
