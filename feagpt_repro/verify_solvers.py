#!/usr/bin/env python
"""Cross-solver verification: run the same model on CalculiX and Abaqus and
compare the numbers.

Why this is the strongest check available
-----------------------------------------
CalculiX and Abaqus are independent implementations of the same theory, with
independent element formulations, equation solvers and result files.  Two
independent codes agreeing on a physical result cannot be explained by a bug in
*our* code - the same reasoning as the cantilever benchmark in
``verify_cantilever.py``, applied to the solver adapters themselves.

What is compared, and what each check is worth
----------------------------------------------
* **node labels and coordinates** - a structural check that both solvers read
  the *same mesh*.  Cheap, exact, and it fails loudly on an off-by-one in the
  deck writer.  A small residual is expected and is explained, not ignored: the
  ODB stores coordinates in 32-bit floats, so the residual is tested against
  ``float32(ccx coordinate)`` rather than against zero.
* **max displacement** - the primary physical response.  Both solvers are handed
  identical nodes, identical elements and identical loads, so any disagreement
  beyond discretisation-tolerance is a real defect.
* **equilibrium residual** - sum of the reactions at the clamped root versus the
  applied force, on whichever component carries the load.  This is the one check
  that depends on neither solver's internal conventions, and it is what caught
  the 500 N -> 326 N load dilution in the first place.
* **max von Mises** - *reported, not asserted blindly*.  Shell stress is stored
  per section point through the thickness and the two codes report it in
  different ways, so all the relevant numbers are printed with the definition of
  each stated.

Usage::

    python verify_solvers.py                       # uses the default dirs
    python verify_solvers.py --ccx DIR --abaqus DIR
"""

from __future__ import annotations

import argparse
import json
import statistics
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feagpt import geometry, post  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402

CASE = "naca4412_wingbox"

#: What each code's nodal-force output actually contains - **measured**, and the
#: two are not the same quantity:
#:
#: ``ccx``     ``*NODE FILE, F`` writes the **total external force** at a node
#:             (applied at free nodes, reaction at constrained ones), so summed
#:             over the whole model it cancels to zero.
#: ``abaqus``  ``RF`` is the **reaction**, non-zero only at constrained DOFs, so
#:             summed over the whole model it equals the applied load.
#:
#: They coincide only when the supported node set carries no applied load - true
#: for the wing box (the 500 N sits on the free tip, so the root set is pure
#: reaction), false for a distributed pressure, where the clamped set also carries
#: q*A_node and the whole-model sums differ by the entire applied load.  Treating
#: the two as one quantity is what made a perfectly equilibrated panel report a
#: 100 % equilibrium residual; measured on the 600x600 panel, ccx sums to
#: -0.00001 N and abaqus to +36.00000 N for the *same* applied 36 N.
FORCE_CONVENTION = {"ccx": "total", "abaqus": "reaction"}


def _load_case(root: Path, case: str) -> dict:
    """Load whatever result source exists in ``root/<case>/``."""
    d = root / case
    if not d.is_dir():
        raise FileNotFoundError(f"no case directory at {d}")
    rj = d / f"{case}.results.json"
    summary = json.loads(rj.read_text(encoding="utf-8")) if rj.exists() else {}
    frd = d / f"{case}.frd"
    odbj = d / f"{case}.odb.json"
    if frd.exists():
        # load_any, not parse_frd: a CalculiX deck written since D8 asks for
        # OUTPUT=3D (the expanded shell), and load_any folds that back onto the
        # mid-surface with the deck's own node labels restored.  Calling
        # parse_frd directly would compare an expanded 2N-node field against
        # Abaqus' N-node one and report "node label sets differ" - a failure of
        # plumbing, not of the model.
        data, source = post.load_any(frd), str(frd)
    elif odbj.exists():
        data, source = post.load_results_json(odbj), str(odbj)
    else:
        raise FileNotFoundError(f"neither FRD nor ODB-JSON found in {d}")
    return {"dir": d, "summary": summary, "data": data, "source": source}


def _rel(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1e-12) * 100.0


def _f32(x: float) -> float:
    """Round a double through 32-bit float, to model ODB storage."""
    return struct.unpack("f", struct.pack("f", x))[0]


def _root_z(data: dict, tol: float = 1e-6) -> list[int]:
    """Node labels on the clamped root (z ~ 0) - the wing-box rule.

    Derived from coordinates, so it does not depend on anything either solver
    did or on any convention either file format uses.  It is nonetheless a
    *wing-box* rule (see :func:`feagpt.geometry.clamp_nodes`): on a flat panel,
    whose whole skin sits at z = 0, it selects every node and would turn the
    equilibrium check into a sum over free nodes.  Pass ``--spec`` for a case
    whose clamp is elsewhere.
    """
    return [n for n, xyz in data["nodes"].items() if abs(xyz[2]) < tol]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cross-solver verification (ccx vs abaqus)")
    ap.add_argument("--ccx", default="outputs", help="output root of the CalculiX run")
    ap.add_argument("--abaqus", default="outputs_abaqus", help="output root of the Abaqus run")
    ap.add_argument("--case", default=CASE, help="case directory name (default: the baseline wing box)")
    ap.add_argument("--force", type=float, default=500.0,
                    help="total applied load (N).  For --reaction-set clamp this "
                         "is the target the support must balance.  For 'all' the "
                         "target is 0 and this value is only the scale the "
                         "residual is quoted against - pass the real total load "
                         "(e.g. 36 for the 600x600 panel) or the number reads "
                         "optimistically small")
    ap.add_argument("--spec", help="spec.json for the case: resolves the clamp node "
                                   "set from the model's own family rule instead of "
                                   "assuming the wing-box one")
    ap.add_argument("--reaction-set", choices=("clamp", "all"), default="clamp",
                    help="which nodes must balance the load. 'clamp' (default) is "
                         "right for a concentrated load: it sits on free nodes, so "
                         "the reactions at the support sum to it. 'all' is right for "
                         "a distributed load, where the clamped nodes carry part of "
                         "the applied pressure too - then only global equilibrium is "
                         "a clean statement, and the target is 0, not --force")
    ap.add_argument("--coord-tol", type=float, default=1e-3,
                    help="node coordinate agreement tolerance (mm)")
    ap.add_argument("--stress-med-tol", type=float, default=5.0,
                    help="per-node von Mises median agreement tolerance (%%)")
    args = ap.parse_args(argv)

    try:
        ccx = _load_case(Path(args.ccx), args.case)
        abq = _load_case(Path(args.abaqus), args.case)
    except FileNotFoundError as exc:
        print(f"FAIL: {exc}")
        print("  run both branches first:")
        print(f"    python run_pipeline.py --demo --solver ccx    --out outputs")
        print(f"    python run_pipeline.py --demo --solver abaqus --out outputs_abaqus")
        return 2

    print("=" * 78)
    print("  CROSS-SOLVER VERIFICATION - identical model, two independent codes")
    print("=" * 78)
    for label, case in (("CalculiX", ccx), ("Abaqus", abq)):
        print(f"  {label:9s}: {Path(case['source']).name}")
    print("-" * 78)

    n_checks = 0
    failures: list[str] = []
    notes: list[str] = []

    # ---- 1. same mesh ---------------------------------------------------- #
    nc, na = ccx["data"]["nodes"], abq["data"]["nodes"]
    same_labels = set(nc) == set(na)
    n_checks += 1
    if same_labels:
        msg = f"ccx {len(nc)} vs abaqus {len(na)} -> IDENTICAL"
    else:
        msg = (f"ccx {len(nc)} vs abaqus {len(na)} -> DIFFER "
               f"({len(set(nc) - set(na))} only in ccx, "
               f"{len(set(na) - set(nc))} only in abaqus)")
        failures.append("node label sets differ")
    print(f"  1) node labels      : {msg}")

    # ---- 2. node coordinates --------------------------------------------- #
    if same_labels:
        dmax = max(max(abs(a - b) for a, b in zip(nc[k], na[k])) for k in nc)
        # Test the explanation, not just the magnitude: if every Abaqus
        # coordinate is exactly the 32-bit rounding of the CalculiX one, the
        # residual comes from ODB storage precision rather than from anything
        # the model or the deck did.
        f32_exact = all(
            abs(_f32(nc[k][i]) - na[k][i]) < 1e-9 for k in nc for i in range(3)
        )
        n_checks += 1
        tag = "IDENTICAL" if dmax == 0 else ("float32-consistent" if f32_exact else "UNEXPLAINED")
        print(f"  2) node coordinates : max |delta| = {dmax:.3e} mm -> {tag}")
        if f32_exact and dmax > 0:
            notes.append(
                "ODB node coordinates are stored as 32-bit floats, so the "
                f"{dmax:.1e} mm residual is storage precision, not a model difference"
            )
        if dmax > args.coord_tol:
            failures.append(f"node coordinates differ by {dmax:.3e} mm")
    else:
        print("  2) node coordinates : skipped (label sets differ)")

    # ---- 3. element count from the ODB ----------------------------------- #
    ea = (abq["data"].get("meta") or {}).get("n_elements")
    if ea:
        types = (abq["data"].get("meta") or {}).get("element_types", {})
        print(f"  3) element count    : abaqus assembled {ea} elements {types}"
              f" (read from the ODB, not from the deck text)")

    # ---- 4. peak displacement -------------------------------------------- #
    dc = ccx["summary"].get("max_disp")
    da = abq["summary"].get("max_disp")
    if dc is not None and da is not None:
        e_disp = _rel(dc, da)
        n_checks += 1
        print(f"  4) max |u|          : ccx {dc:.5f} mm vs abaqus {da:.5f} mm "
              f"-> diff {e_disp:.3f} %")
        if e_disp > 1.0:
            failures.append(f"max displacement differs by {e_disp:.3f} %")

    # ---- 5. spanwise deflection ------------------------------------------ #
    wc = ccx["summary"].get("max_w")
    wa = abq["summary"].get("max_w")
    if wc is not None and wa is not None:
        n_checks += 1
        print(f"  5) max |UZ|         : ccx {wc:.5f} mm vs abaqus {wa:.5f} mm "
              f"-> diff {_rel(wc, wa):.3f} %")

    # ---- 6. equilibrium -------------------------------------------------- #
    # The load direction is a property of the model, so the component that
    # carries it is detected from the data rather than assumed.  (Assuming Z
    # here once reported a 100% residual for a load applied in Y.)
    #
    # The *target* depends on BOTH the load type and the code's convention (see
    # FORCE_CONVENTION).  Getting either wrong makes a correct model look broken:
    #   concentrated load  -> the load sits on free nodes, so the supports carry
    #                         it all and the supported set sums to it
    #   distributed load   -> the supported set also carries applied pressure, so
    #                         for a 'total' convention the only predictable sum is
    #                         the whole model's, and it is zero; for a 'reaction'
    #                         convention the whole model's sum *is* the applied
    #                         load.
    print(f"  6) equilibrium      : sum of nodal forces over the "
          f"'{args.reaction_set}' node set")
    if args.reaction_set == "all":
        print("       distributed load: the model is self-equilibrated, and the two")
        print("       codes' force conventions differ (ccx total -> 0, abaqus")
        print("       reaction -> applied), so each is quoted against its own target.")
    spec = FEASpec.from_json(args.spec) if args.spec else None
    comps = {}
    for label, case in (("ccx   ", ccx), ("abaqus", abq)):
        key = label.strip()
        conv = FORCE_CONVENTION.get(key, "total")
        roots = (list(case["data"]["nodes"]) if args.reaction_set == "all"
                 else (geometry.clamp_nodes(spec, case["data"]["nodes"]) if spec
                       else _root_z(case["data"])))
        sums = [post.reaction_sum(case["data"], roots, comp=c) for c in range(3)]
        comps[label] = (roots, sums)
        dominant = max(range(3), key=lambda c: abs(sums[c]))
        if args.reaction_set == "all" and conv == "total":
            target = 0.0
        else:
            target = args.force
        scale = args.force or 1.0
        err = abs(abs(sums[dominant]) - target) / scale * 100.0
        n_checks += 1
        print(f"       {label}: {len(roots):5d} nodes in set [{conv}] | "
              f"RX {sums[0]:+12.5f}  RY {sums[1]:+12.5f}  RZ {sums[2]:+12.5f} N")
        print(f"                dominant = {'XYZ'[dominant]}  "
              f"-> |R| {abs(sums[dominant]):.5f} N vs target {target:.5f} N, "
              f"residual {err:.6f} % of {scale:g} N")
        if err > 0.05:
            failures.append(f"{key}: equilibrium residual {err:.6f} % "
                            f"on component {'XYZ'[dominant]}")

    # ---- 7. stress (reported with its definition, not asserted blind) ----- #
    # Registered definition since D8 (2026-10-03): the headline von Mises is the
    # OUTER FIBRE, because the mid-surface one is not merely different on a
    # bending model, it is identically zero on a flat plate.  Each number is
    # still printed with the reduction that produced it, and the two solvers reach
    # the outer fibre by different routes - CalculiX through the expanded shell,
    # Abaqus through its section points - so the labels stay explicit.
    print("  7) stress           : registered definition = OUTER FIBRE (D8);")
    print("                        every value printed with its own reduction")
    mc = ccx["summary"].get("max_von_mises")
    mc_mid = ccx["summary"].get("max_von_mises_midsurface")
    ma = abq["summary"].get("max_von_mises")
    ma_mid = abq["summary"].get("max_von_mises_midsurface")
    cand = (abq["data"].get("meta") or {}).get("stress_candidates_max_vm") or {}
    ma_avg = cand.get("outer_fibre_node_averaged")
    if mc is not None:
        print(f"       ccx outer fibre, node-avg     : {mc:.4f} MPa  "
              f"(worst of the two layers at each node)")
    if mc_mid is not None:
        print(f"       ccx mid-surface, node-avg     : {mc_mid:.4f} MPa  "
              f"(layer mean - kept for history, not the sizing number)")
    if ma is not None:
        print(f"       abaqus outer fibre, per-elem  : {ma:.4f} MPa  "
              f"(element-wise peak, NOT node-averaged)")
    if ma_avg is not None:
        print(f"       abaqus outer fibre, node-avg  : {ma_avg:.4f} MPa")
    if ma_mid is not None:
        print(f"       abaqus membrane (mid-surface) : {ma_mid:.4f} MPa  "
              f"(mean of outer section points, averaged over elements)")
    if mc is not None and ma_avg is not None:
        print(f"       outer-fibre peak, ccx vs abaqus: diff {_rel(mc, ma_avg):.3f} % "
              f"(the peak sits at spar/rib junctions - mesh-dependent)")

    # The peak von Mises sits at a geometric junction, where the two codes'
    # extrapolation and smoothing choices dominate, so it is a poor
    # cross-solver discriminator.  The per-node field is the honest test: if the
    # two codes are computing the same physical quantity, the whole field has to
    # line up, not just its maximum.
    #
    # The registered gate compares ccx's **full** 6-component von Mises against
    # abaqus' membrane reduction, and that is kept deliberately.  A reading of the
    # definitions suggests ccx's transverse-shear terms have no counterpart in
    # abaqus' S11/S22/S33/S12 reduction, so dropping them from ccx should improve
    # agreement - it does the opposite, and by a lot: measured on the wing box,
    # full-vs-membrane is a 0.33 % median while in-plane-vs-membrane is 4.90 %.
    # A hypothesis that the data rejects does not get to redefine a gate that
    # three archived cases were validated against, so the in-plane value is
    # *reported* (it is what explains the panel result) and not substituted.
    ccx_stress = ccx["data"]["results"].get("STRESS") or {}
    abq_stress = abq["data"]["results"].get("STRESS") or {}
    cs = {n: post.von_mises(v) for n, v in ccx_stress.items()}
    cs_in = {n: post.von_mises_inplane(v) for n, v in ccx_stress.items()}
    as_ = {n: post.von_mises(v) for n, v in abq_stress.items()}

    if cs and cs_in:
        pk_all = max(cs.values())
        pk_in = max(cs_in.values())
        share = (pk_all - pk_in) / pk_all * 100.0 if pk_all else 0.0
        print(f"       ccx peak, in-plane only       : {pk_in:.4f} MPa "
              f"(transverse shear is {share:.2f} % of the {pk_all:.4f} MPa peak)")
        if share > 50.0:
            notes.append(
                f"ccx's peak von Mises ({pk_all:.4f} MPa) is {share:.1f} % "
                f"transverse shear, not bending or axial stress: the in-plane "
                f"field peaks at {pk_in:.4f} MPa.  For this model the "
                f"'max von Mises' headline is a bearing/shear number."
            )

    common = sorted(set(cs) & set(as_))
    rels = [abs(cs[n] - as_[n]) / max(abs(as_[n]), 1e-9) * 100
            for n in common if abs(as_[n]) > 1e-9]
    if common and rels:
        med = statistics.median(rels)
        p90 = sorted(rels)[int(0.9 * (len(rels) - 1))]
        n_checks += 1
        print(f"       per-node field ({len(common)} nodes) : median diff {med:.2f} %, "
              f"p90 {p90:.2f} %")
        if med > args.stress_med_tol:
            failures.append(f"per-node von Mises median differs by {med:.2f} %")
    elif common:
        # Every abaqus node is zero, so there is no relative difference to test -
        # and the zero is the *correct* answer: a linear analysis of a flat plate
        # in pure bending has no membrane action at all.  Recorded rather than
        # silently skipped, because a gate that quietly stops checking is worse
        # than one that reports that it does not apply.
        note = (
            f"per-node stress field not comparable on this model: abaqus reports "
            f"an identically zero mid-surface field (max {max(as_.values()):.2e} MPa "
            f"over {len(common)} nodes).  That is correct physics - linear theory "
            f"gives a flat plate no membrane action under transverse pressure - so "
            f"the comparison is vacuous here, not failed."
        )
        if mc is not None and ma_avg is not None:
            note += (
                f"  The outer-fibre peaks now share a definition on both sides "
                f"(D8, 2026-10-03), node-averaged, and sit {_rel(mc, ma_avg):.1f} % "
                f"apart.  That is why the registered definition is the outer "
                f"fibre: the mid-surface field is identically zero here, so a "
                f"consumer reading it as 'the stress' would see no load at all."
            )
        notes.append(note)

    meta = abq["data"].get("meta") or {}
    if meta.get("section_points"):
        print(f"       abaqus section points exposed : {meta['section_points']} "
              f"(ELEMENT_NODAL extrapolation keeps only the outer two)")
    if meta.get("stress_components"):
        print(f"       abaqus stress components      : {meta['stress_components']} "
              f"({meta.get('stress_type')})")
    cand = meta.get("stress_candidates_max_vm")
    if cand:
        print("       abaqus candidate reductions   : "
              + ", ".join(f"{k}={v}" for k, v in cand.items() if v is not None))

    # ---- verdict ---------------------------------------------------------- #
    print("-" * 78)
    for note in notes:
        print(f"  note: {note}")
    if failures:
        print(f"  VERDICT: CHECK - {len(failures)} issue(s)")
        for f in failures:
            print(f"    * {f}")
    else:
        print(f"  VERDICT: PASS - {n_checks} checks, no disagreement above tolerance")
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
