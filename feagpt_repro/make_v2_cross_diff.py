"""Cross-diff ccx vs abaqus modal frequencies -> verify_v2_p1.json.

C6-P1 modal pilot, step 5 of DESIGN_C6_P1_MODAL.md.  Reads:

* ccx side:   FEM-Bench-Aero/modeling_v2/<case>/<case>.modal.json
              (written by make_v2_modal_cases.py --solve-ccx)
* abaqus side: <abq-dir>/<case>.dat  (real-machine runs; the eigenvalue
              table is parsed by extract_modal_dat.py --dialect abaqus)

Writes FEM-Bench-Aero/modeling_v2/verify_v2_p1.json:
per-case per-mode relative differences and the distribution stats
(median / p90 / max per mode order) that the threshold decision reads.

NO threshold judgement is made here -- 阈值先测后定 (design doc section 5);
this script measures, it does not pass or fail anything.

Usage (venv or any python3)::

    python make_v2_cross_diff.py --abq-dir "D:\\jobs\\case_20261107"
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from extract_modal_dat import extract          # noqa: E402
from make_v2_modal_cases import CASES, v2_name, _V2  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--abq-dir", required=True,
                    help="dir with the real-machine abaqus <case>.dat files")
    ap.add_argument("--out", default=str(_V2 / "verify_v2_p1.json"))
    args = ap.parse_args(argv)

    abq_dir = Path(args.abq_dir)
    rows, diffs_by_mode = [], {}
    n_ok = 0
    for v11 in CASES:
        name = v2_name(v11)
        ccx_json = _V2 / name / f"{name}.modal.json"
        abq_dat = abq_dir / f"{name}.dat"
        row = {"case": name}
        for label, p in (("ccx", ccx_json), ("abq", abq_dat)):
            if not p.exists():
                row["state"] = f"missing_{label}"
        if row.get("state"):
            rows.append(row)
            continue
        ccx = json.loads(ccx_json.read_text(encoding="utf-8"))
        try:
            abq = extract(str(abq_dat), "abaqus", expect=ccx["n_modes_found"])
        except ValueError as exc:
            row["state"] = "extract_failed_abq"
            row["error"] = str(exc)
            rows.append(row)
            continue
        if not abq["modes"]:
            row["state"] = "no_modes_abq"
            row["error"] = "abaqus table parsed to 0 modes"
            rows.append(row)
            continue
        if any((m.get("f_hz") or 0.0) <= 0.0 for m in abq["modes"]):
            # placeholder table: LANCZOS found nothing in the requested
            # interval (real-machine finding 2026-11-07: "5, 0.0, 0.0")
            row["state"] = "zero_modes_abq"
            row["error"] = "abaqus table contains non-positive frequencies " \
                           "(unconverged interval, not real modes)"
            rows.append(row)
            continue
        n = min(len(ccx["modes"]), len(abq["modes"]))
        if n == 0:
            row["state"] = "no_common_modes"
            rows.append(row)
            continue
        modes = []
        for i in range(n):
            fc, fa = ccx["modes"][i]["f_hz"], abq["modes"][i]["f_hz"]
            rel = abs(fa - fc) / ((fa + fc) / 2.0) if (fa + fc) else float("inf")
            modes.append({"mode": i + 1,
                          "f_ccx_hz": fc, "f_abq_hz": fa,
                          "rel_diff": rel})
            diffs_by_mode.setdefault(i + 1, []).append(rel)
        row.update({"state": "ok", "n_modes_compared": n,
                    "modes": modes,
                    "max_rel_diff": max(m["rel_diff"] for m in modes)})
        n_ok += 1
        rows.append(row)

    stats = {}
    for k, v in sorted(diffs_by_mode.items()):
        v_sorted = sorted(v)
        p90 = v_sorted[min(len(v_sorted) - 1,
                           int(round(0.9 * len(v_sorted))) - 1 or 0)]
        stats[f"mode_{k}"] = {
            "n": len(v), "median": statistics.median(v),
            "p90": p90, "max": max(v)}
    # --- decided threshold gate (2026-11-07, 老王拍板 A) -----------------
    # f1 (fundamental frequency) is judged hard at <1% relative difference
    # (measured: median 0.23%, max 0.73% over 8 cases).  Modes 2-5 are
    # RECORDED but NOT judged: high-order diffs (up to 16.4%) are dominated
    # by dense-spectrum mode-pairing ambiguity (skin2 cluster, web1 jump) --
    # open item, n_modes=10 re-run before any high-order threshold.
    F1_THRESHOLD = 0.01
    f1_rows = [{"case": r["case"], "rel_diff": r["modes"][0]["rel_diff"]}
               for r in rows if r.get("state") == "ok"]
    f1_bad = [x for x in f1_rows if x["rel_diff"] >= F1_THRESHOLD]
    f1_gate = {"judged": "f1 only (decided 2026-11-07, option A)",
               "threshold_rel": F1_THRESHOLD, "n_judged": len(f1_rows),
               "n_fail": len(f1_bad), "fails": f1_bad,
               "pass": len(f1_bad) == 0}
    out = {"volume": "modeling_v2 (C6-P1 modal pilot)",
           "n_cases": len(CASES), "n_ok": n_ok,
           "note": ("f1 judged at <1% (decided); modes 2-5 recorded only "
                    "-- mode-pairing open item (DESIGN_C6_P1_MODAL.md "
                    "section 5)"),
           "f1_gate": f1_gate,
           "rel_diff_stats_by_mode": stats, "rows": rows}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    print(json.dumps({"n_ok": n_ok, "f1_gate_pass": f1_gate["pass"],
                      "stats": stats}, ensure_ascii=False, indent=1))
    for r in rows:
        if r.get("state") != "ok":
            print(f"[!] {r['case']}: {r.get('state')} {r.get('error', '')}")
    print(f"verify -> {args.out}")
    return 0 if n_ok == len(CASES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
