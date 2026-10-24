#!/usr/bin/env python
"""Independent verification of the open-hole coupon chain (M5 / task T4).

A coupon is not verified because ccx exited 0.  Gate 4 says the model *is* what
the spec asked for - one plate, one hole, the right diameter, read back off the
boundary - and nothing so far says the numbers are **right**.  So the same chain
(geometry -> mesh -> deck -> solver -> field) is run on a problem with a
documented answer, exactly as ``verify_barrel.py`` does for the barrel and
``verify_panel.py`` for the stiffened panel.

What can and cannot be checked against a closed form
----------------------------------------------------
There is no exact closed form for a hole in a *finite-width* strip.  What exists
is (a) Kirsch's infinite-plate solution, ``Kt = 3`` exactly, and (b) Howland's
tabulated finite-width correction, which this module carries as a fitted
polynomial.  So the check is against **Howland**, and Kirsch is printed beside it
but never asserted on - on a lambda = 0.1 coupon the two differ by 9 % in the net
convention, and a test that "failed" for being 9 % away from 3.0 would be testing
its own convention, not the model.

Both nominal-stress conventions are checked
-------------------------------------------
``Kt_gross`` divides the peak by ``F / (W t)`` - the force over the full section,
which is what the deck applies and what a far-field node reports.
``Kt_net`` divides by the section *through the hole*.  These are different
numbers for the same physical peak (3.02 vs 2.72 here), and a Kt quoted without
its convention is not a number.  Checking both is what stops a convention slip
from looking like a mesh error - which is exactly the mistake this file was
written after, in the family module itself.

Equilibrium, from the result file
---------------------------------
The load is a total force spread over the loaded end, so the model has three
things that must add up and are read off the *solved* field rather than assumed:
the applied end force sums to ``F``, the clamped end carries ``-F``, and the
whole model sums to zero.  A mesh that solved but applied the wrong load passes
every other check in this file.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

REPRO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPRO))

from feagpt import open_hole, pipeline, post    # noqa: E402

#: Tolerance (%) on Kt against Howland.  **Not** an arithmetic tolerance: a peak
#: stress read off a curved boundary moves by about +-1 % depending on where the
#: nodes land (measured, ``_t4_probe/t4_convergence.py``: 24 -> 96 divisions
#: scatter the factor over 2.97 - 3.04).  The tolerance has to be larger than
#: that scatter or the gate would fire on the discretisation rather than on the
#: model.  2 % leaves the measured residuals (0.2 - 0.8 %) a factor of two.
TOL_KT_PCT = 2.0

#: Tolerance (%) on the cross-solver **displacement** gap.  This is the field
#: that carries the model: one mesh, one load, so agreement here means the
#: geometry, the deck and the solve all agree, and whatever stress difference
#: is left over is *recovery*, not physics.
TOL_CROSS_DISP_PCT = 1.0

#: Tolerance (%) on the per-node **median** hole-edge membrane von Mises gap.
#: Deliberately a median, and deliberately not the peak.
#:
#: Why the peak is not the statistic here (measured, ``_t4_probe/diag_cross_k.py``,
#: on the shared mesh of this very check): both codes report the same physical
#: quantity - the membrane stress - but reach it through different recoveries.
#: CalculiX folds an ``OUTPUT=3D`` expanded shell back to the mid-surface (a
#: layer mean over an already node-averaged FRD field); Abaqus averages the two
#: outermost section points and then averages over the contributing elements
#: (``feagpt/abaqus_odb.py``).  On a flat field those agree to a 1.6 % median
#: (the figure that module records); on the hole edge - the steepest gradient
#: in the model - the *peak* lands 1.92 % apart while the *median* node lands
#: 2.32 % apart and the displacement field 0.15 %.  A peak is the most
#: discretisation-sensitive statistic there is, and comparing two recoveries
#: bare is the exact mistake D8 already recorded for the wing box (ccx 10.6048
#: / Abaqus element-wise 11.7809 / per-node 8.6879 - same name, same definition,
#: three numbers).  So this gate asserts the robust statistics and prints the
#: peak for reference, the way it prints Kirsch beside Howland.
#:
#: 5 % is not a new number: it is the dataset's own cross-solver stress
#: criterion (``eval_dataset.py``: per-node von Mises median < 5 %), so this
#: check and the dataset gate now measure the same thing.
TOL_CROSS_VM_MEDIAN_PCT = 5.0

#: Tolerance (%) on the force balances.
TOL_EQUILIBRIUM_PCT = 0.1


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b) * 100.0 if b else float("inf")


def _shipped_case(name: str, case_dir: Path, params: dict) -> dict | None:
    """Read a hand-run abaqus case's shipped artifacts, if they match *this* call.

    **D29 era (2026-10-11).**  The WorkBuddy sandbox injects ``tsbx.dll`` into
    the Abaqus solver process, so a solve started inside the agent dies with
    ``AbaqusException: 0`` and an empty ODB skeleton; the operator therefore
    runs the deck by hand (the manual-bat pattern, batch 6 onward).  When the
    artifacts of such a hand run are already on disk -- ``spec.json`` +
    ``odb.json`` + ``.msh`` -- this reads them instead of re-solving.  The gate
    quantities (the field and the spec) are exactly what shipped, and the mesh
    statistics are recomputed from the archived ``.msh``
    (``diagnostics.msh_quality``), so every number stays artifact evidence.

    Trust is *earned*: the on-disk spec is compared, JSON-normalised, against a
    fresh rebuild of the spec this call would have made.  Anything missing,
    stale, or from a different parameter set returns ``None`` and the caller
    falls through to the normal (inside the sandbox, doomed) solve path.
    """
    odbj = case_dir / f"{name}.odb.json"
    specj = case_dir / f"{name}.spec.json"
    mshf = case_dir / f"{name}.msh"
    if not (odbj.exists() and specj.exists() and mshf.exists()):
        return None
    from feagpt.spec import FEASpec
    try:
        shipped_spec = FEASpec.from_json(specj)
        want = open_hole.make_spec(name, **params)
    except Exception:
        return None
    # ``workdir`` is where the run happened, not what the model is - the
    # shipped spec records the real directory, the rebuild carries the default.
    # Strip it on both sides before comparing; everything else must match.
    def _model_dict(d: dict) -> dict:
        d = json.loads(json.dumps(d))
        d.pop("workdir", None)
        return d
    norm = lambda d: json.dumps(d, sort_keys=True)  # noqa: E731
    if norm(_model_dict(json.loads(specj.read_text(encoding="utf-8")))) \
            != norm(_model_dict(want.to_dict())):
        return None
    sys.path.insert(0, str(REPRO / "diagnostics"))
    try:
        import gmsh
        import msh_quality
        gmsh.initialize()   # msh_quality only initializes in its CLI main
        try:
            q = msh_quality.quality(mshf)
        finally:
            gmsh.finalize()
    finally:
        sys.path.pop(0)
    data = post.load_results_json(odbj)
    return {
        "ok": True, "name": name, "solver": "abaqus",
        "spec": shipped_spec,
        "n_nodes": len(data["nodes"]),
        "n_elements": q["n"],
        "element_types": q["types"],
        "tri_count": q["types"].get("tri3", 0),
        "min_quality": q["min"],
        "mesh_size": float(shipped_spec.mesh.size_chord),
        "division": int(open_hole.HOLE_ARC_DIVISIONS),
        # artifact path: gate 4 is not recomputed here; it is printed in the
        # report only and is never a gate input (the cross-solver gate sits on
        # the displacement and the hole-edge median, both read from the field).
        "gate4": None,
        "deck": str(case_dir / f"{name}.inp"),
        "source": str(odbj),
        "data": data,
    }


def run_case(name: str, solver: str, **params) -> dict:
    """Run one coupon through the real pipeline and read its field back.

    **Each solver gets its own output root**, for the reason ``verify_barrel.py``
    records at length: sharing one directory lets the Abaqus run overwrite the
    ccx deck, after which the reader prefers the stale FRD and compares a code
    against itself.
    """
    out = (Path("outputs/_verify_hole") if solver == "ccx"
           else Path("outputs/_verify_hole_abaqus"))
    case_dir = out / name
    if solver == "abaqus":
        shipped = _shipped_case(name, case_dir, params)
        if shipped is not None:
            return shipped
    spec = open_hole.make_spec(name, workdir=str(out / name), **params)
    res = pipeline.run(spec, outdir=out / name, solver_name=solver)
    if not res.ok:
        return {"ok": False, "name": name, "solver": solver,
                "log": res.messages[-5:]}
    case_dir = out / name
    frd = case_dir / f"{name}.frd"
    odbj = case_dir / f"{name}.odb.json"
    if solver == "ccx" and frd.exists():
        data, source = post.load_any(frd), str(frd)
    elif odbj.exists():
        data, source = post.load_results_json(odbj), str(odbj)
    else:
        return {"ok": False, "name": name, "solver": solver,
                "log": [f"no result source in {case_dir}"]}
    return {
        "ok": True, "name": name, "solver": solver, "spec": spec,
        "n_nodes": res.mesh["n_nodes"], "n_elements": res.mesh["n_elements"],
        "element_types": res.mesh["element_types"],
        "tri_count": res.mesh.get("tri_count"),
        "min_quality": res.mesh["min_quality"],
        "mesh_size": float(spec.mesh.size_chord),
        "division": int(open_hole.HOLE_ARC_DIVISIONS),
        "gate4": pipeline.topology.compare(res.geometry["topology"])["pass"],
        "deck": res.artifacts["inp"], "source": source, "data": data,
    }


def hole_edge(data: dict, p: "open_hole.OpenHoleParams") -> list[tuple[float, float]]:
    """``(angle_deg, von Mises)`` for every node on the hole boundary."""
    nodes = data["nodes"]
    stress = data["results"].get("STRESS") or {}
    if not stress:
        return []
    cx, cy = p.center()
    rh = 0.5 * p.hole_d
    vm = post.von_mises
    out: list[tuple[float, float]] = []
    for t, (x, y, _z) in nodes.items():
        r = math.hypot(x - cx, y - cy)
        if abs(r - rh) < 1e-3:
            th = math.degrees(math.atan2(y - cy, x - cx)) % 360.0
            out.append((th, vm(stress[t])))
    return out


def hole_edge_map(data: dict, p: "open_hole.OpenHoleParams"
                  ) -> dict[int, tuple[float, float]]:
    """``{node_label: (angle_deg, von Mises)}`` on the hole boundary.

    :func:`hole_edge` throws the label away because the single-coupon reduction
    only needs the profile.  A cross-solver *node-by-node* comparison needs the
    labels back, and re-deriving them at the call site would duplicate the
    ``|r - rh| < 1e-3`` radius test in two places.
    """
    nodes = data["nodes"]
    stress = data["results"].get("STRESS") or {}
    if not stress:
        return {}
    cx, cy = p.center()
    rh = 0.5 * p.hole_d
    vm = post.von_mises
    out: dict[int, tuple[float, float]] = {}
    for t, (x, y, _z) in nodes.items():
        r = math.hypot(x - cx, y - cy)
        if abs(r - rh) < 1e-3 and t in stress:
            out[t] = (math.degrees(math.atan2(y - cy, x - cx)) % 360.0,
                      vm(stress[t]))
    return out


def reduce_kt(run: dict) -> dict:
    """The coupon's Kt, both conventions, plus the peak's location."""
    p = open_hole.parse_params(run["spec"])
    prof = hole_edge(run["data"], p)
    if not prof:
        return {}
    th_hot, s_max = max(prof, key=lambda e: e[1])
    F = float(run["spec"].load.magnitude)
    sig_gross = open_hole.gross_stress(F, p)
    sig_net = open_hole.net_stress(F, p)
    lam = p.lambda_ratio
    return {
        "lambda": lam,
        "sigma_max": s_max,
        "peak_angle_deg": th_hot,
        "Kt_gross": s_max / sig_gross,
        "Kt_net": s_max / sig_net,
        "howland_net": open_hole.howland_kt_net(lam),
        "howland_gross": open_hole.howland_kt_gross(lam),
        "kirsch": open_hole.kirsch_kt(),
        "n_edge_nodes": len(prof),
    }


def equilibrium(run: dict) -> dict:
    """Force book-keeping read off the solved field (ccx ``FORC``)."""
    p = open_hole.parse_params(run["spec"])
    data = run["data"]
    nodes = data["nodes"]
    forc = data["results"].get("FORC") or {}
    if not forc:
        return {}
    F = float(run["spec"].load.magnitude)

    def fx(tags):
        return sum(forc[t][0] for t in tags if t in forc)

    fixed = open_hole.end_nodes(nodes, p, "fixed")
    loaded = open_hole.end_nodes(nodes, p, "loaded")
    return {
        "applied_N": fx(loaded),
        "reaction_N": fx(fixed),
        "global_N": sum(forc[t][0] for t in forc),
        "force_N": F,
    }


def max_disp(run: dict) -> float:
    """The largest nodal displacement magnitude in a run's result set.

    Both codes write DISP the same way, but CalculiX appends a fourth
    component (the magnitude) while Abaqus writes three, so it is derived when
    it is absent - the same rule :func:`feagpt.post.summarize_data` applies.
    """
    disp = run["data"]["results"].get("DISP") or {}
    best = 0.0
    for v in disp.values():
        m = v[3] if len(v) >= 4 else math.sqrt(sum(c * c for c in v[:3]))
        best = max(best, m)
    return best


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #
def check_kt(size: float | None = None, ccx_only: bool = False
             ) -> tuple[list[dict], dict]:
    """The default coupon: Kt against Howland, force balance, and the two codes."""
    out: list[dict] = []
    kw = {} if size is None else {"size": size}
    run = run_case("verify_hole_kt", "ccx", **kw)
    if not run["ok"]:
        return [{"check": "verify_hole.invocation", "pass": False,
                 "detail": f"ccx run failed: {run.get('log')}"}], {}

    kt = reduce_kt(run)
    if not kt:
        return [{"check": "verify_hole.invocation", "pass": False,
                 "detail": "no hole-edge nodes in the ccx result"}], {}

    lam = kt["lambda"]
    err_g = (kt["Kt_gross"] / kt["howland_gross"] - 1.0) * 100.0
    err_n = (kt["Kt_net"] / kt["howland_net"] - 1.0) * 100.0
    out.append({
        "check": "hole.kt-gross-vs-howland",
        "pass": abs(err_g) <= TOL_KT_PCT,
        "detail": (f"lambda={lam:.4f}: Kt_gross {kt['Kt_gross']:.4f} vs Howland "
                   f"{kt['howland_gross']:.4f} ({err_g:+.2f} %, tol "
                   f"{TOL_KT_PCT:g} %); Kirsch infinite-plate "
                   f"{kt['kirsch']:.4f} shown for reference only"),
    })
    out.append({
        "check": "hole.kt-net-vs-howland",
        "pass": abs(err_n) <= TOL_KT_PCT,
        "detail": (f"same peak in the net convention: Kt_net "
                   f"{kt['Kt_net']:.4f} vs {kt['howland_net']:.4f} "
                   f"({err_n:+.2f} %). The two conventions disagree with each "
                   f"other by "
                   f"{abs(kt['Kt_gross']/kt['Kt_net']-1)*100:.1f} % - both are "
                   f"right, both are checked"),
    })
    # The concentration must sit where Kirsch says it does: on the diameter
    # perpendicular to the load, i.e. theta = 90 or 270 deg.  A peak anywhere
    # else means the load is being applied along the wrong axis, which no
    # magnitude check would catch.
    th = kt["peak_angle_deg"]
    half_step = 180.0 / max(kt["n_edge_nodes"], 1)
    loc_ok = min(abs(th - 90.0), abs(th - 270.0)) <= half_step + 1e-6
    out.append({
        "check": "hole.peak-location",
        "pass": loc_ok,
        "detail": (f"peak at theta={th:.2f} deg, {kt['n_edge_nodes']} edge nodes "
                   f"(half-step {half_step:.2f} deg); Kirsch puts the maximum on "
                   f"the load-normal diameter (90 / 270 deg)"),
    })

    eq = equilibrium(run)
    if eq:
        ea = _rel(eq["applied_N"], eq["force_N"])
        er = _rel(eq["reaction_N"], -eq["force_N"])
        eg = abs(eq["global_N"]) / eq["force_N"] * 100.0
        out.append({
            "check": "hole.equilibrium",
            "pass": max(ea, er, eg) <= TOL_EQUILIBRIUM_PCT,
            "detail": (f"loaded end carries {eq['applied_N']:.6g} N vs applied "
                       f"{eq['force_N']:.6g} N ({ea:.4f} %); clamped end "
                       f"{eq['reaction_N']:.6g} N ({er:.4f} %); whole model "
                       f"{eq['global_N']:.3g} N ({eg:.4f} %)"),
        })

    extra = {
        "ccx": {**kt,
                "n_nodes": run["n_nodes"], "n_elements": run["n_elements"],
                "element_types": run["element_types"],
                "tri_count": run["tri_count"], "min_quality": run["min_quality"],
                "mesh_size": run["mesh_size"], "division": run["division"],
                "gate4": run["gate4"], "equilibrium": eq},
    }

    if not ccx_only:
        rb = run_case("verify_hole_kt", "abaqus", **kw)
        if not rb["ok"]:
            out.append({"check": "hole.cross-solver", "pass": False,
                        "detail": f"abaqus run failed: {rb.get('log')}"})
        else:
            kb = reduce_kt(rb)
            p_c = open_hole.parse_params(run["spec"])
            p_b = open_hole.parse_params(rb["spec"])
            # Displacement carries the model; the hole-edge median carries the
            # stress without the peak's discretisation sensitivity.
            ua, ub = max_disp(run), max_disp(rb)
            gap_u = _rel(ub, ua)
            mc = hole_edge_map(run["data"], p_c)
            mb = hole_edge_map(rb["data"], p_b)
            common = sorted(set(mc) & set(mb))
            rel = [_rel(mb[t][1], mc[t][1]) for t in common if mc[t][1] > 0]
            med = statistics.median(rel) if rel else float("inf")
            gap_g = _rel(kb["Kt_gross"], kt["Kt_gross"])
            gap_n = _rel(kb["Kt_net"], kt["Kt_net"])
            out.append({
                "check": "hole.cross-solver",
                "pass": (gap_u <= TOL_CROSS_DISP_PCT
                         and med <= TOL_CROSS_VM_MEDIAN_PCT),
                "detail": (
                    f"max |u| ccx {ua:.6f} vs abaqus {ub:.6f} mm "
                    f"({gap_u:.3f} %, tol {TOL_CROSS_DISP_PCT:g} %); hole-edge "
                    f"per-node median von Mises gap {med:.3f} % over "
                    f"{len(common)} nodes (tol {TOL_CROSS_VM_MEDIAN_PCT:g} %). "
                    f"Peak Kt_gross ccx {kt['Kt_gross']:.4f} vs abaqus "
                    f"{kb['Kt_gross']:.4f} ({gap_g:.3f} %) and Kt_net "
                    f"{kt['Kt_net']:.4f} vs {kb['Kt_net']:.4f} ({gap_n:.3f} %) "
                    f"are printed for reference only: a peak is a recovery "
                    f"statistic, not an invariant (D8), so the gate sits on the "
                    f"displacement and the median, not on it"),
            })
            extra["abaqus"] = {**kb, "n_nodes": rb["n_nodes"],
                               "n_elements": rb["n_elements"],
                               "tri_count": rb["tri_count"],
                               "min_quality": rb["min_quality"],
                               "gate4": rb["gate4"],
                               "cross": {"max_disp": ub, "gap_disp_pct": gap_u,
                                         "edge_vm_median_pct": med,
                                         "n_edge_common": len(common),
                                         "peak_kt_gross_gap_pct": gap_g,
                                         "peak_kt_net_gap_pct": gap_n}}
    return out, extra


def check_trend() -> tuple[list[dict], dict]:
    """Kt must move with lambda the way the theory says, not just sit near it.

    A single coupon matching Howland to 0.5 % could be luck.  The theory's
    *shape* is a stronger statement: against the gross section the factor
    **rises** with lambda (3.02 at lambda = 0.1, 3.14 at 0.2, 3.36 at 0.3),
    because the net section is being squeezed harder than the relief grows.
    Two or three coupons at different lambda either reproduce that ordering or
    they do not, and if they do not, matching one value means nothing.

    Why the lambdas stop at 0.1, and do not reach down to 0.05
    ----------------------------------------------------------
    The hole edge is the feature that carries the answer, and the mesher floors
    every generated element size at ``MeshSizeMin = max(size_chord / 6, 0.5)``
    mm.  The builder **refuses** a coupon whose edge target (``pi d / n``) falls
    at or below that floor rather than coarsening it silently.  The ``0.5 mm``
    term is absolute, so at ``n = 72`` divisions a hole smaller than
    ``0.5 * 72 / pi = 11.46 mm`` is unbuildable at **any** far field - and
    ``lambda = 0.05`` on this 200 mm coupon is a 10 mm hole.  So the low end is
    ``lambda = 0.1`` (d = 20 mm, edge 0.873 mm) and the probe runs at the family
    default 4 mm far field, with no special-casing of the size field at all:
    the original ``size = 2.0`` workaround here was written against a wrong
    model of the floor (``size_chord / 6`` without the hard ``0.5``) and did not
    actually clear it - the probe still died in the builder.
    """
    out: list[dict] = []
    base_p = open_hole.OpenHoleParams()
    lams = (0.1, 0.2, 0.3)
    runs = [run_case(f"verify_hole_lam{int(lam * 100):03d}", "ccx",
                     hole_d=round(lam * float(base_p.width), 6))
            for lam in lams]
    bad = [lam for lam, r in zip(lams, runs) if not r["ok"]]
    if bad:
        return [{"check": "hole.lambda-trend", "pass": False,
                 "detail": f"runs failed at lambda={bad}: "
                           f"{[r.get('log') for r in runs if not r['ok']]}"}], {}

    kts = [reduce_kt(r) for r in runs]
    rows = []
    ok = True
    prev = None
    for lam, kt in zip(lams, kts):
        want = open_hole.howland_kt_gross(lam)
        err = (kt["Kt_gross"] / want - 1.0) * 100.0
        rises = prev is None or kt["Kt_gross"] > prev
        ok = ok and abs(err) <= TOL_KT_PCT and rises
        rows.append(f"lambda={lam:g}: Kt_gross {kt['Kt_gross']:.4f} "
                    f"(Howland {want:.4f}, {err:+.2f} %"
                    + ("" if rises else ", NOT RISING") + ")")
        prev = kt["Kt_gross"]
    out.append({
        "check": "hole.lambda-trend",
        "pass": ok,
        "detail": "; ".join(rows)
                  + "; the gross-section factor must rise monotonically with "
                    "lambda - matching one coupon is luck, reproducing the "
                    "ordering is the model",
    })
    return out, {f"lambda_{int(lam * 100):03d}": kt
                 for lam, kt in zip(lams, kts)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=float, default=None,
                    help="far-field mesh size (mm); default is the family's own")
    ap.add_argument("--ccx-only", action="store_true",
                    help="skip the Abaqus half (much slower to start)")
    ap.add_argument("--trend", action="store_true",
                    help="also run the two-lambda trend probe")
    ap.add_argument("--json", help="write the machine-readable report here")
    args = ap.parse_args(argv)

    print("=== open-hole coupon: Kt vs the finite-width solution")
    rows, extra = check_kt(args.size, args.ccx_only)
    if args.trend:
        print("\n=== open-hole coupon: does Kt move with lambda?")
        rows_t, extra_t = check_trend()
        rows += rows_t
        extra["trend"] = extra_t

    npass = nfail = 0
    for r in rows:
        npass += bool(r["pass"])
        nfail += not r["pass"]
        print(f"  [{'PASS' if r['pass'] else 'FAIL'}] {r['check']}")
        print(f"         {r['detail']}")

    print(f"\nopen-hole verification: {npass} PASS, {nfail} FAIL")
    print(f"VERDICT: {'PASS' if nfail == 0 else 'FAIL'}")
    if args.json:
        Path(args.json).write_text(
            json.dumps({"n_pass": npass, "n_fail": nfail, "checks": rows,
                        "detail": extra}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        print(f"report -> {args.json}")
    return 0 if nfail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
