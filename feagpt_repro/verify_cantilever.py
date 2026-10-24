#!/usr/bin/env python
"""Independent verification of the solver chain.

A wing-box result is not "validated" merely because the solver exited cleanly.
This script runs the *same* chain (geometry -> mesh -> deck -> CalculiX -> FRD
-> post) on a problem with closed-form answers and checks three independent
things:

1. **Static equilibrium** - the sum of the clamped-end reactions must equal the
   applied load.  A physical invariant; it does not depend on any analytical
   model of the structure, so it is the strongest of the three.
2. **Tip deflection** against two analytical values:
   * Euler-Bernoulli  ``delta = F L^3 / (3 E I)``
   * Timoshenko       ``delta = F L^3 / (3 E I) + F L / (G A_s)``
   with ``I`` for the thin-walled box and ``A_s`` the shear area of the webs.
   For a short beam the two differ by several percent, so both are reported and
   the *Timoshenko* value is used as the reference.
3. **Mesh sensitivity** - re-meshing finer must not move the answer much.

If this passes, the chain is trustworthy for the wing-box case; if it fails,
the wing-box numbers should not be quoted either.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feagpt import inp_writer, meshing, post, solver  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402


# --------------------------------------------------------------------------- #
# geometry: a thin-walled rectangular box beam, extruded along +x
# --------------------------------------------------------------------------- #
def make_box_beam(gmsh, length: float, width: float, height: float):
    occ = gmsh.model.occ
    p = {
        "c00": occ.addPoint(0.0, 0.0, -height / 2),
        "c10": occ.addPoint(0.0, width, -height / 2),
        "c11": occ.addPoint(0.0, width, height / 2),
        "c01": occ.addPoint(0.0, 0.0, height / 2),
    }
    edges = [
        occ.addLine(p["c00"], p["c10"]),   # bottom flange
        occ.addLine(p["c10"], p["c11"]),   # right web
        occ.addLine(p["c11"], p["c01"]),   # top flange
        occ.addLine(p["c01"], p["c00"]),   # left web
    ]
    occ.addCurveLoop(edges)
    occ.extrude([(1, e) for e in edges], length, 0.0, 0.0)
    occ.synchronize()
    return [tag for dim, tag in gmsh.model.getEntities(2)]


def analytical(force, length, width, height, thickness, youngs, poisson):
    """Thin-walled box: bending + shear tip deflection."""
    i_flanges = 2.0 * (width * thickness) * (height / 2.0) ** 2
    i_webs = 2.0 * (thickness * height**3 / 12.0)
    inertia = i_flanges + i_webs

    delta_bending = force * length**3 / (3.0 * youngs * inertia)
    shear_area = 2.0 * thickness * height            # webs carry the shear
    shear_modulus = youngs / (2.0 * (1.0 + poisson))
    delta_shear = force * length / (shear_modulus * shear_area)
    return {
        "inertia": inertia,
        "delta_EB": delta_bending,
        "delta_shear": delta_shear,
        "delta_total": delta_bending + delta_shear,
    }


# --------------------------------------------------------------------------- #
# one FE run through the production chain
# --------------------------------------------------------------------------- #
def run_case(tmpdir: Path, params: dict, force, mesh_size, verbose=False):
    import gmsh

    spec = FEASpec()
    spec.name = "verify_cantilever"
    spec.material.youngs_modulus = params["E"]
    spec.material.poisson_ratio = params["nu"]
    spec.airfoil.skin_thickness = params["t"]
    spec.mesh.size_chord = mesh_size
    spec.mesh.size_span = mesh_size
    spec.mesh.min_jacobian = 0.05
    spec.load.kind = "tip_force"
    spec.load.magnitude = force
    spec.load.direction = (0.0, 0.0, 1.0)          # transverse, +z

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 1 if verbose else 0)
    gmsh.model.add(spec.name)
    try:
        make_box_beam(gmsh, params["L"], params["b"], params["h"])
        report = meshing.build_mesh(gmsh, spec, None)
        extracted = meshing.extract_mesh(gmsh)

        # a single section group: every shell uses spec.airfoil.skin_thickness
        elements = {"upper_skin": []}
        for dim, tag in gmsh.model.getEntities(2):
            et, etags, enodes = gmsh.model.mesh.getElements(2, tag)
            for t, nodes in zip(et, enodes):
                name, npe, fam = meshing._GMSH_ELEM.get(t, (None, 0, None))
                if fam != "surface":
                    continue
                nodes = list(map(int, nodes))
                for i in range(len(nodes) // npe):
                    elements["upper_skin"].append((name, nodes[i * npe:(i + 1) * npe]))

        # Use the production node filter, so this really is the same chain and
        # not a slightly kinder variant of it: a load spread over nodes that no
        # element references would be quietly diluted here too.
        nodes, _dropped = meshing.referenced_nodes(extracted["nodes"], elements)

        root = [t for t, (x, y, z) in nodes.items() if abs(x) < 1e-6]
        tip = [t for t, (x, y, z) in nodes.items() if abs(x - params["L"]) < 1e-6]

        deck = inp_writer.write_ccx_inp(
            tmpdir / "cantilever.inp",
            {"nodes": nodes, "elements": elements},
            spec,
            groups={"root": root, "tip": tip},
        )
        gmsh.finalize()
        gmsh = None

        solved = solver.run(deck)
        if not solved.ok:
            return {"ok": False, "log": solved.log[-900:], "mesh": report.to_dict()}

        # load_any, not parse_frd: a deck written since D8 asks for OUTPUT=3D
        # (the expanded shell).  The expanded node labels are offset from the
        # deck's, so ``tip``/``root`` - which are deck labels - would match
        # nothing and every check below would read an empty field.
        data = post.load_any(solved.frd)
        disp = data["results"].get("DISP", {})
        forc = data["results"].get("FORC", {})

        tip_uz = [disp[n][2] for n in tip if n in disp]
        # CalculiX's RF block reports the *total nodal force*: free nodes carry
        # the applied load and only the clamped nodes carry reactions.  So the
        # invariant is sum(Rz over clamped nodes) == -F_applied, NOT
        # sum(Rz over all nodes) == 0.
        root_set = set(root)
        reaction_sum = sum(forc[n][2] for n in root_set if n in forc and len(forc[n]) > 2)

        return {
            "ok": True,
            "tip_deflection": max(tip_uz) if tip_uz else 0.0,
            "reaction_sum": reaction_sum,
            "n_elements": report.n_elements,
            "n_nodes": report.n_nodes,
            "min_quality": report.min_quality,
            "mesh_passed": report.passed,
            "raw": post.summarize(solved.frd),
        }
    finally:
        try:
            if gmsh is not None and gmsh.isInitialized():
                gmsh.finalize()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
def main() -> int:
    tmp = Path("outputs/_verify")
    tmp.mkdir(parents=True, exist_ok=True)

    # slender enough that shear contributes only a couple of percent
    params = dict(L=600.0, b=60.0, h=60.0, t=2.0, E=73100.0, nu=0.33)
    force = 500.0
    ref = analytical(force, params["L"], params["b"], params["h"], params["t"],
                     params["E"], params["nu"])

    print("=" * 74)
    print("Cantilever verification - thin-walled box beam, clamped at x = 0")
    print("=" * 74)
    print(f"  L={params['L']}  b={params['b']}  h={params['h']}  t={params['t']} mm | "
          f"F={force} N (transverse) | E={params['E']} MPa nu={params['nu']}")
    print(f"  I = {ref['inertia']:.1f} mm^4")
    print(f"  delta (Euler-Bernoulli) = {ref['delta_EB']:.5f} mm")
    print(f"  delta (shear term)      = {ref['delta_shear']:.5f} mm")
    print(f"  delta (Timoshenko)      = {ref['delta_total']:.5f} mm   <- reference")
    print()

    runs = {}
    for size, label in ((12.0, "coarse"), (6.0, "fine")):
        r = run_case(tmp, params, force, size)
        runs[label] = r
        if not r["ok"]:
            print(f"  [{label}] SOLVER FAILED\n{r.get('log', '')}")
            return 2
        d = r["tip_deflection"]
        err = (d - ref["delta_total"]) / ref["delta_total"] * 100.0
        print(f"  [{label:6s}] elem={r['n_elements']:5d} node={r['n_nodes']:5d} "
              f"minJ={r['min_quality']:.3f} | tip d={d:.5f} mm | "
              f"err vs Timoshenko = {err:+.2f} %")

    d_c, d_f = runs["coarse"]["tip_deflection"], runs["fine"]["tip_deflection"]
    mesh_change = abs(d_f - d_c) / d_c * 100.0

    # equilibrium: reactions at the clamped end must cancel the applied force
    r_sum = runs["fine"]["reaction_sum"]
    eq_err = abs(r_sum + force) / force * 100.0

    print()
    print("-" * 74)
    print(f"  1) equilibrium   : sum(Rz at clamp) = {r_sum:+.4f} N vs applied {force:+.1f} N "
          f"-> residual {eq_err:.5f} %")
    print(f"  2) deflection    : FE {d_f:.5f} mm vs Timoshenko {ref['delta_total']:.5f} mm "
          f"-> {abs(d_f-ref['delta_total'])/ref['delta_total']*100:.2f} %")
    print(f"  3) mesh sens.    : {mesh_change:.2f} % between coarse and fine")

    ok_eq = eq_err < 1.0
    ok_def = abs(d_f - ref["delta_total"]) / ref["delta_total"] * 100.0 < 10.0
    ok_mesh = mesh_change < 5.0
    verdict = ok_eq and ok_def and ok_mesh
    print(f"  VERDICT          : {'PASS' if verdict else 'CHECK'} "
          f"(equilibrium {'ok' if ok_eq else 'FAIL'}, "
          f"deflection {'ok' if ok_def else 'FAIL'}, "
          f"mesh {'ok' if ok_mesh else 'FAIL'})")

    # --- control: a thicker wall suppresses cross-section distortion ------ #
    # A thin-walled box is softer than Euler-Bernoulli predicts because the
    # section distorts as it bends - a shell model captures that, beam theory
    # by construction cannot.  Stiffening the wall should therefore close the
    # gap; if it does, the residual above is physics rather than a bug.
    print()
    print("  Control - thicker wall (t = 6 mm), same load and length:")
    p_thick = dict(params, t=6.0)
    ref_thick = analytical(force, p_thick["L"], p_thick["b"], p_thick["h"],
                           p_thick["t"], p_thick["E"], p_thick["nu"])
    r_thick = run_case(tmp, p_thick, force, 8.0)
    if r_thick["ok"]:
        d_t = r_thick["tip_deflection"]
        e_t = (d_t - ref_thick["delta_total"]) / ref_thick["delta_total"] * 100.0
        e_thin = abs(d_f - ref["delta_total"]) / ref["delta_total"] * 100.0
        print(f"     FE {d_t:.5f} mm vs Timoshenko {ref_thick['delta_total']:.5f} mm "
              f"-> {e_t:+.2f} %   (t = 2 mm gave {e_thin:.2f} %)")
    else:
        print(f"     control case failed: {r_thick.get('log', '')[:120]}")
    print("-" * 74)
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
