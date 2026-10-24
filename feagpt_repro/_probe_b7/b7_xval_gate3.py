#!/usr/bin/env python
"""Gate 3 (cross-solver) for the batch-7 T4 size cases - the generic metric.

The open-hole family has **no** D20-style amendment: its peak sits on the hole
edge (a smooth interior boundary, not a load-application ring), so the dataset's
generic cross-solver criterion applies unchanged - ``max|u|`` gap < 1 % and the
per-node **median** hole-edge von Mises gap < 5 % (the median, not the peak:
both codes report the same physical membrane stress but reach it through
different recoveries, and on the hole edge the *peak* lands further apart than
the median - measured in ``_t4_probe/diag_cross_k.py`` and recorded in
``verify_hole.py``).  Kirsch/Howland ``Kt`` and the force balance are printed
beside them the way ``verify_hole.py`` prints Kirsch beside Howland: the
centred points must sit on Howland (2 % there is ``verify_hole``'s own gate,
repeated here as a print), the off-centre point has no closed form at all.

This reads what is already on disk; it runs neither solver.

Usage::

    python _probe_b7/b7_xval_gate3.py
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPRO = HERE.parent
sys.path.insert(0, str(REPRO))

from feagpt import open_hole, post                          # noqa: E402
from feagpt.spec import FEASpec                             # noqa: E402

SPECS = HERE / "_batch7_specs"

#: (name, ccx_root, abaqus_root).  All four shipped; no retired row this batch.
CASES = (
    ("open_hole_panel_600x300_d30", "outputs_b7", "outputs_b7_abaqus"),
    ("open_hole_panel_400x200_d50", "outputs_b7", "outputs_b7_abaqus"),
    ("open_hole_panel_600x300_d60", "outputs_b7", "outputs_b7_abaqus"),
    ("open_hole_panel_400x200_d40_offcentre", "outputs_b7", "outputs_b7_abaqus"),
)

TOL_DISP_PCT = 1.0     # dataset's generic cross-solver displacement gate
TOL_VM_MEDIAN_PCT = 5.0  # dataset's generic per-node von Mises median gate
TOL_KT_PCT = 2.0       # verify_hole's Howland gate, printed for centred rows


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b) * 100.0 if b else float("inf")


def _max_disp(data: dict) -> float:
    disp = data["results"].get("DISP") or {}
    best = 0.0
    for v in disp.values():
        m = v[3] if len(v) >= 4 else math.sqrt(sum(c * c for c in v[:3]))
        best = max(best, m)
    return best


def _kt(data: dict, spec: FEASpec) -> dict:
    p = open_hole.parse_params(spec)
    nodes = data["nodes"]
    stress = data["results"].get("STRESS") or {}
    if not stress:
        return {}
    cx, cy = p.center()
    rh = 0.5 * float(p.hole_d)
    vm = post.von_mises
    prof = []
    for t, (x, y, _z) in nodes.items():
        r = math.hypot(x - cx, y - cy)
        if abs(r - rh) < 1e-3 and t in stress:
            prof.append(vm(stress[t]))
    if not prof:
        return {}
    s_max = max(prof)
    F = float(spec.load.magnitude)
    return {"n_edge": len(prof),
            "sigma_max": s_max,
            "Kt_gross": s_max / open_hole.gross_stress(F, p),
            "Kt_net": s_max / open_hole.net_stress(F, p),
            "howland_net": open_hole.howland_kt_net(p.lambda_ratio),
            "howland_gross": open_hole.howland_kt_gross(p.lambda_ratio),
            "lambda": p.lambda_ratio}


def _edge_median_gap(data_c: dict, data_a: dict, spec: FEASpec) -> tuple[float, int]:
    p = open_hole.parse_params(spec)
    cx, cy = p.center()
    rh = 0.5 * float(p.hole_d)
    vm = post.von_mises

    def edge_vm(data):
        nodes, stress = data["nodes"], data["results"].get("STRESS") or {}
        out = {}
        for t, (x, y, _z) in nodes.items():
            r = math.hypot(x - cx, y - cy)
            if abs(r - rh) < 1e-3 and t in stress:
                out[t] = vm(stress[t])
        return out

    mc, ma = edge_vm(data_c), edge_vm(data_a)
    common = sorted(set(mc) & set(ma))
    rel = [_rel(ma[t], mc[t]) for t in common if mc[t] > 0]
    return (statistics.median(rel) if rel else float("inf")), len(common)


def _equilibrium(data: dict, spec: FEASpec) -> dict:
    """ccx-only force book-keeping (Abaqus writes RF, not FORC - D8 note)."""
    nodes = data["nodes"]
    forc = data["results"].get("FORC") or {}
    if not forc:
        return {}
    p = open_hole.parse_params(spec)
    F = float(spec.load.magnitude)
    fx = lambda tags: sum(forc[t][0] for t in tags if t in forc)
    return {"applied_N": fx(open_hole.end_nodes(nodes, p, "loaded")),
            "reaction_N": fx(open_hole.end_nodes(nodes, p, "fixed")),
            "global_N": sum(forc[t][0] for t in forc),
            "force_N": F}


def main() -> int:
    print(f"gate 3 (generic metric: max|u| < {TOL_DISP_PCT:g} %, "
          f"hole-edge vm median < {TOL_VM_MEDIAN_PCT:g} %) for batch-7")
    print("=" * 112)
    print(f"{'case':42s} {'max|u| ccx':>11s} {'max|u| abq':>11s} "
          f"{'disp %':>8s} {'vm med %':>9s} {'Kt_g ccx':>9s}  verdict")
    out: dict = {}
    bad: list[str] = []
    for name, croot, aroot in CASES:
        spec = FEASpec.from_json(SPECS / f"{name}.spec.json")
        cdir = REPRO / croot / name
        adir = REPRO / aroot / name
        ccx = post.load_any(cdir / f"{name}.frd")
        abq = post.load_results_json(adir / f"{name}.odb.json")

        uc, ua = _max_disp(ccx), _max_disp(abq)
        gap_u = _rel(ua, uc)
        med, n_common = _edge_median_gap(ccx, abq, spec)
        ok = gap_u < TOL_DISP_PCT and med < TOL_VM_MEDIAN_PCT

        kc = _kt(ccx, spec)
        ka = _kt(abq, spec)
        kt_note = ""
        if kc and ka:
            eg = _rel(kc["Kt_gross"], kc["howland_gross"])
            kt_note = (f" Kt_gross ccx {kc['Kt_gross']:.4f} / abq "
                       f"{ka['Kt_gross']:.4f} (Howland "
                       f"{kc['howland_gross']:.4f}, ccx {eg:+.2f} %)")
        eq = _equilibrium(ccx, spec)
        eq_note = ""
        if eq:
            ea = _rel(eq["applied_N"], eq["force_N"])
            er = _rel(eq["reaction_N"], -eq["force_N"])
            eg2 = abs(eq["global_N"]) / eq["force_N"] * 100.0
            eq_note = f"; eq (ccx) applied {ea:.4f}% / reaction {er:.4f}% / global {eg2:.2e}%"

        if not ok:
            bad.append(name)
        print(f"{name:42s} {uc:11.6f} {ua:11.6f} {gap_u:8.4f} {med:9.4f} "
              f"{(kc or {}).get('Kt_gross', float('nan')):9.4f}  "
              f"{'PASS' if ok else 'FAIL'}")
        print(f"{'':42s} edge nodes common {n_common}{kt_note}{eq_note}")
        out[name] = {"max_disp_ccx": round(uc, 6), "max_disp_abaqus": round(ua, 6),
                     "disp_gap_pct": round(gap_u, 5),
                     "vm_median_pct": round(med, 5),
                     "n_edge_common": n_common,
                     "kt_ccx": {k: round(v, 6) if isinstance(v, float) else v
                                for k, v in (kc or {}).items()},
                     "kt_abaqus": {k: round(v, 6) if isinstance(v, float) else v
                                   for k, v in (ka or {}).items()},
                     "equilibrium_ccx": eq,
                     "pass": ok}
    print("=" * 112)
    print(f"{len(CASES) - len(bad)}/{len(CASES)} batch-7 cases pass")
    (HERE / "_b7_gate3.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"report -> {HERE / '_b7_gate3.json'}")
    return 0 if not bad else 2


if __name__ == "__main__":
    raise SystemExit(main())
