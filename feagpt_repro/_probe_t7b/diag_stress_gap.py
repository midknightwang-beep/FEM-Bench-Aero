#!/usr/bin/env python
"""Diagnose the ccx-vs-Abaqus von Mises gap on the T7 build-out coupons.

The three new laminate coupons agree on displacement to 0.004-0.16 %, but the
two ``[±45]s`` coupons read 32 % apart on *peak* von Mises while the
quasi-isotropic one reads 0.9 %.  Two very different explanations fit that
pattern, and they call for opposite responses:

* **peak sampling** - the hole-edge field of an angle-ply stack is steep, the
  two codes extrapolate integration-point stresses to nodes differently, and
  the single hottest node lands far apart while the field itself agrees.  Then
  the median is small, the peak is noise, and D8's "peaks are not compared
  bare" rule already covers it.
* **a real modelling difference** - the equivalent constants handed to one code
  are not the ones the other got, and the whole field is off.

This prints both readings node by node so the choice is made on numbers:
median relative gap, peak gap, and where each peak sits on the hole.
"""
from __future__ import annotations

import glob
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from feagpt import open_hole, post  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402


def _case_dir(root: Path, pattern: str) -> Path:
    """The one case directory under a run root (skips batch_summary.json)."""
    for p in sorted(root.glob(pattern)):
        if p.is_dir() and (p / f"{p.name}.spec.json").exists():
            return p
    raise FileNotFoundError(f"no case directory under {root} matching {pattern}")


def load_ccx(case: str) -> tuple[dict, FEASpec]:
    d = _case_dir(ROOT / f"_probe_t7b/outputs_{case}", "*")
    name = d.name
    spec = FEASpec.from_json(d / f"{name}.spec.json")
    return post.load_any(d / f"{name}.frd"), spec


def load_abaqus(case: str) -> tuple[dict, FEASpec]:
    d = _case_dir(ROOT / f"_probe_t7b/outputs_abaqus_{case}", "*")
    name = d.name
    spec = FEASpec.from_json(d / f"{name}.spec.json")
    return json.loads((d / f"{name}.odb.json").read_text(encoding="utf-8")), spec


def _archived_disp(run_root: Path) -> float:
    """The case's shipped ``max_disp`` from ``.results.json``."""
    for f in sorted(run_root.glob("*/*.results.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        return round(float(d["max_disp"]), 9)
    raise FileNotFoundError(f"no results.json under {run_root}")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out_json = None
    for a in sys.argv[1:]:
        if a.startswith("--json="):
            out_json = Path(a.split("=", 1)[1])
    cases = args or ["cfrp45s", "cfrpqi", "cfrp45s_d40"]
    vm = post.von_mises
    rc = 0
    rows = []
    for case in cases:
        ccx, spec_c = load_ccx(case)
        abq, spec_b = load_abaqus(case)
        p = open_hole.parse_params(spec_c)

        mc = open_hole_edge_map(ccx, p)
        mb = open_hole_edge_map(abq, p)
        common = sorted(set(mc) & set(mb))
        rel = [abs(mc[t][1] - mb[t][1]) / max(mb[t][1], 1e-12) * 100.0
               for t in common]
        med = statistics.median(rel)

        # global peaks, and where they sit
        sc = {t: vm(v) for t, v in (ccx["results"].get("STRESS") or {}).items()}
        sb = {t: vm(v) for t, v in (abq["results"].get("STRESS") or {}).items()}
        tc = max(sc, key=sc.get); tb = max(sb, key=sb.get)
        gpeak = abs(sc[tc] - sb[tb]) / max(sb[tb], 1e-12) * 100.0
        pc = ccx["nodes"].get(tc); pb = abq["nodes"].get(tb)
        ang = lambda q: (math.degrees(math.atan2(q[1] - p.center()[1],
                                                q[0] - p.center()[0])) % 360.0
                         if q else float("nan"))

        print(f"\n=== {case} ===")
        print(f"  hole-edge nodes compared : {len(common)}")
        print(f"  median |dvM|             : {med:.3f} %   <-- the gated number")
        print(f"  worst single node        : {max(rel):.1f} %")
        print(f"  global peak ccx          : {sc[tc]:.4f} MPa at node {tc} "
              f"(angle {ang(pc):.1f} deg)")
        print(f"  global peak abaqus       : {sb[tb]:.4f} MPa at node {tb} "
              f"(angle {ang(pb):.1f} deg)")
        print(f"  peak-to-peak gap         : {gpeak:.1f} %")
        if med > 5.0:
            print("  VERDICT: field is off - not a peak artefact")
            rc = 1
        else:
            print("  VERDICT: field agrees; the gap is peak sampling")
        rows.append({
            "case": case,
            "n_hole_edge_nodes": len(common),
            "median_abs_dvm_pct": round(med, 4),
            "worst_node_pct": round(max(rel), 3),
            "peak_ccx": {"vm": round(sc[tc], 4), "node": tc,
                         "angle_deg": round(ang(pc), 2)},
            "peak_abaqus": {"vm": round(sb[tb], 4), "node": tb,
                            "angle_deg": round(ang(pb), 2)},
            "peak_gap_pct": round(gpeak, 3),
            # Take the archived headline from results.json, not a re-reduction of
            # the node table: the two agree here but the *shipped* number is the
            # one a consumer reads, so that is the one this report quotes.
            "max_disp_ccx": _archived_disp(ROOT / f"_probe_t7b/outputs_{case}"),
            "max_disp_abaqus": _archived_disp(
                ROOT / f"_probe_t7b/outputs_abaqus_{case}"),
            "verdict": "median < 5 % -> field agrees" if med <= 5.0
                       else "field off",
        })
    if out_json:
        out_json.write_text(json.dumps({
            "purpose": "D30 双码交叉：位移差 + 孔边逐节点 vM 中位差（闸门口径）",
            "gate": "max|u| < 1 %；孔边逐节点 vM 中位差 < 5 %（verify_solvers 口径）",
            "rows": rows,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nreport -> {out_json}")
    return rc


def open_hole_edge_map(data: dict, p) -> dict:
    """Local copy of verify_hole.hole_edge_map (kept import-light on purpose).

    Node labels are normalised to ``int`` here: the FRD loader keys nodes by
    ``int`` while the ODB extractor writes JSON keys (``str``), so pairing them
    without normalising silently yields an empty intersection.
    """
    stress = data["results"].get("STRESS") or {}
    labels = {int(t): v for t, v in stress.items()}
    out = {}
    cx, cy = p.center()
    rh = 0.5 * p.hole_d
    vm = post.von_mises
    for t, (x, y, _z) in data["nodes"].items():
        r = math.hypot(x - cx, y - cy)
        n = int(t)
        if abs(r - rh) < 1e-3 and n in labels:
            out[n] = (math.degrees(math.atan2(y - cy, x - cx)) % 360.0,
                      vm(labels[n]))
    return out


if __name__ == "__main__":
    import math  # noqa: F401  (used inside main's lambdas)
    raise SystemExit(main())
