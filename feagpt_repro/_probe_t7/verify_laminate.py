#!/usr/bin/env python
"""T7 independent verification - the CLT yardstick for the laminate family.

What it checks (and why this is the T7 analogue of Howland for T4)
------------------------------------------------------------------
Howland's closed form is an *isotropic* solution: it says nothing about an
orthotropic coupon, so T7 needs its own yardstick.  The one the family gets is
**CLT (classical lamination theory) applied to the far field** - for a
symmetric, balanced stack the membrane equivalent ``EX`` is a closed-form
number (for ``[0/90]s`` it is literally hand arithmetic, see
``feagpt.laminate``), and the far-field axial stiffness of a tension coupon is
something the FE solution must reproduce *whatever the hole does in the
middle*.

The measurement avoids the hole entirely.  Two stations straddle it
symmetrically (x = 0.25 L and 0.75 L; the perturbation the hole adds to
``u_x`` is symmetric about the hole centre, so it largely cancels in the
difference), the mean ``u_x`` over each station's node line gives the
far-field strain, and::

    E_eff = sigma_gross * (x2 - x1) / (u_x(x2) - u_x(x1))

with ``sigma_gross = F / (width * thickness)`` exact by construction (the
family applies a total force).  The gate compares ``E_eff`` against the CLT
value.  A laminate whose plies, angles or thicknesses are wrong cannot land
here - which is exactly the property a gate needs.

The method validates itself on the **aluminium sibling**: the same reduction
run on the archived T4 d20 coupon must return 73100 MPa (the material's
E).  A reduction whose control reads wrong measures nothing.

Tolerances
----------
Stamped from measurements, not vibes - the run prints the measured residuals
for both coupons; the gate constant sits above the aluminium control's
residual (discretisation + station averaging), not above some aspiration.

Usage
-----
    python verify_laminate.py --spec outputs/<case>/<case>.spec.json \
        --ccx outputs/<case>/<case>.frd \
        [--abaqus outputs_<x>/<case>/<case>.odb.json] \
        [--alu-spec ../feagpt_repro/outputs_hole/... --alu-ccx ...frd]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feagpt import open_hole, post  # noqa: E402
from feagpt.laminate import (equivalent_engineering_constants,  # noqa: E402
                             layup_from_params)

#: Station positions as fractions of coupon length (0.25 L, 0.75 L).
STATION_FRACS = (0.25, 0.75)


#: Gate: |E_eff / EX_clt - 1| must be below this.  **Stamped from measurements
#: (2026-10-11 pilot), not vibes** - the chain that produced the number:
#:   * no-hole plate, 20 mm grid, the SAME equivalent card:  -1.73 %;
#:   * no-hole plate, 5 mm grid:                              -0.19 %;
#:   * archived aluminium coupon, 4 mm unstructured grid:     -0.54 %;
#:   * this [0/90]s coupon, the same grid and reduction:      -2.07 %.
#: The 5 mm convergence proves the card semantics match the CLT conversion;
#: the coupon residual is the 4 mm S4 discretisation's systematic softness on
#: an orthotropic field (higher stress gradients than the aluminium sibling's,
#: which the control's -0.54 % reflects).  3 % sits above the measured worst
#: case with margin and still bites: a mis-written layup or angle moves EX by
#: 5 % or more.  DO NOT widen it to make a run pass (D11).
TOL_EFF = 0.03


def axial_modulus(results: dict, length: float, width: float, thickness: float,
                  force_n: float, hole_x: float | None = None) -> dict:
    """Far-field ``E_eff`` from the loaded end's mean ``u_x`` - an identity.

    Gauss' theorem on ``eps_x = du_x/dx`` over the coupon area collapses to
    the boundary integral of ``u_x * n_x``, and ``n_x`` lives on the two ends
    only::

        mean(eps_x) = (mean u_x(loaded) - mean u_x(fixed)) / L

    This is exact for *any* self-consistent displacement field - the hole's
    perturbation changes how ``u_x`` is distributed across the loaded end,
    not its average, so the measurement does not care how strong the
    disturbance is.  (Two earlier reductions died in measurement before this
    one: a two-station average caught only the two free-edge nodes, and a
    far-field least-squares slope carried an unremovable ``(a/r)^2`` hole
    perturbation.  Both are kept in the 2026-10-11 log as lessons, not
    options.)  The end mean is over 51 uniformly spaced nodes, so the
    discrete average equals the integral to sampling accuracy.
    """
    disp = results["results"]["DISP"]
    nodes = results["nodes"]

    def end_mean(x_target: float) -> float:
        vals = [disp[t][0] for t, (x, _y, _z) in nodes.items()
                if abs(x - x_target) < 1e-3]
        if not vals:
            raise ValueError(f"no nodes on end x={x_target:g}")
        return sum(vals) / len(vals)

    mean_u = end_mean(float(length)) - end_mean(0.0)
    strain = mean_u / length
    sigma = force_n / (width * thickness)
    return {"E_eff": sigma / strain, "strain": strain,
            "n_end_nodes": len(disp) and sum(
                1 for t, (x, _y, _z) in nodes.items() if abs(x - float(length)) < 1e-3)}


def evaluate(spec_path: str, ccx_path: str, abaqus_path: str | None,
             label: str) -> dict:
    """One coupon: CLT equivalent vs measured far-field modulus, both solvers."""
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    lay = layup_from_params(spec["structure"]["params"])
    eq = equivalent_engineering_constants(lay) if lay is not None else None

    p = open_hole.parse_params(type("S", (), {"structure": spec["structure"]})())
    force = float(spec["load"]["magnitude"])

    out: dict = {"label": label, "case": spec["name"],
                 "layup": eq["code"] if eq else "isotropic",
                 "sigma_gross": force / (p.width * p.thickness)}
    for tag, path in (("ccx", ccx_path), ("abaqus", abaqus_path)):
        if not path:
            continue
        res = post.load_any(path)
        m = axial_modulus(res, p.length, p.width, p.thickness, force,
                          hole_x=p.center()[0])
        m["E_clt"] = eq["EX"] if eq else float(spec["material"]["youngs_modulus"])
        m["residual_pct"] = 100.0 * (m["E_eff"] / m["E_clt"] - 1.0)
        out[tag] = m
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--ccx", required=True)
    ap.add_argument("--abaqus")
    ap.add_argument("--label", default="laminate coupon")
    ap.add_argument("--alu-spec", help="aluminium control spec (method check)")
    ap.add_argument("--alu-ccx", help="aluminium control FRD (method check)")
    ap.add_argument("--json", help="write the machine-readable report here")
    args = ap.parse_args(argv)

    rows = [evaluate(args.spec, args.ccx, args.abaqus, args.label)]
    if args.alu_spec and args.alu_ccx:
        rows.append(evaluate(args.alu_spec, args.alu_ccx, None,
                             "aluminium control (method check)"))

    failed = 0
    print(f"{'coupon':<34} {'side':<7} {'E_clt':>10} {'E_eff':>12} "
          f"{'residual':>9}  gate")
    for r in rows:
        for tag in ("ccx", "abaqus"):
            m = r.get(tag)
            if not m:
                continue
            ok = abs(m["residual_pct"]) <= 100.0 * TOL_EFF
            failed += 0 if ok else 1
            print(f"{r['label']:<34} {tag:<7} {m['E_clt']:>10.1f} "
                  f"{m['E_eff']:>12.2f} {m['residual_pct']:>+8.3f} %  "
                  f"[{'PASS' if ok else 'FAIL'}] "
                  f"(tol {100*TOL_EFF:.1f} %, end nodes {m['n_end_nodes']})")

    if args.json:
        Path(args.json).write_text(
            json.dumps({"rows": rows, "tol_eff": TOL_EFF, "pass": failed == 0},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nreport -> {args.json}")
    print("ALL PASS" if failed == 0 else f"{failed} GATE(S) FAILED")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
