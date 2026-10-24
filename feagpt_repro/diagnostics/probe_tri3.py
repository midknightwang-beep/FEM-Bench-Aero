"""Which gmsh setting clears the rear-spar triangles, and at what mesh cost.

Background
----------
Gate 1 has been *described* as "min Jacobian >= 0.30, **zero tri3**" since M1,
but :mod:`feagpt.meshing` only ever evaluated the Jacobian.  In 2026-10-03 the
triangles were found and located: all 24 of them sit on the **rear spar web**
(``x = 0.7 * chord``) of the two ``chord800`` wing boxes, at the corners of the
rib bays.  The web there is 58.4 mm tall and the chordwise mesh size is 12 mm,
so the across-web division is 4.87 elements -- not an integer, and gmsh's
blossom recombination fills the leftover corner with a triangle.

The sibling case ``naca4412_wingbox_recombination_algorithm3`` is the natural
control: identical geometry, ``recombination_algorithm = 3`` (blossom
*full-quad*), and **zero** triangles -- at +4 % elements.

This probe re-meshes the two offending specs in memory (no files written, no
solve) under several option sets and reports the element mix, so the choice of
"how to get to zero tri3" is made on measurements rather than on the gmsh
manual.  It is deliberately *not* a gate: it prints, it does not assert.

Usage::

    python diagnostics/probe_tri3.py                       # the two offenders
    python diagnostics/probe_tri3.py --case naca4412_wingbox
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from feagpt import geometry as geo_mod  # noqa: E402
from feagpt import meshing  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402

OFFENDERS = [
    ("naca4412_wingbox_n_ribs3_chord800", "outputs"),
    ("naca4412_wingbox_n_ribs5_chord800", "outputs"),
]

# name -> (recombination_algorithm override, extra gmsh options, algorithm_2d)
# ``recomb=None`` means "leave the spec alone", i.e. run exactly what ships,
# including the automatic 1 -> 3 escalation in ``build_mesh``.
VARIANTS: dict[str, dict] = {
    "alg1 (first pass)":    dict(recomb=1),
    "alg1 + optimize":      dict(recomb=1, opts={"Mesh.RecombineOptimizeTopology": 1}),
    "alg1 + algo8":         dict(recomb=1, algorithm=8),
    "alg2 simple-quad":     dict(recomb=2),
    "alg3 full-quad":       dict(recomb=3),
    "auto (as shipped)":    dict(recomb=None),
}


def probe_one(spec: FEASpec, variant: dict) -> dict:
    """Build geometry + mesh once under ``variant``; return the mesh census."""
    import gmsh

    recomb = variant.get("recomb")
    algorithm = variant.get("algorithm")
    opts = variant.get("opts") or {}

    saved = (spec.mesh.recombination_algorithm, spec.mesh.algorithm_2d)
    # Pin the algorithm instead of monkeypatching ``_recombination_algorithm``.
    # Two reasons: it is how a caller forces a choice in production anyway, and
    # pinning suppresses the automatic escalation in ``build_mesh`` (which only
    # fires when the spec leaves the algorithm at 0) - without that, the alg1
    # row would report 0 triangles because it had already been silently
    # re-meshed, and the probe would be measuring the fix instead of the
    # problem.  ``recomb=None`` deliberately does the opposite.
    if recomb is not None:
        spec.mesh.recombination_algorithm = recomb
    if algorithm is not None:
        spec.mesh.algorithm_2d = algorithm

    orig_cfg = meshing._configure_size_field

    def cfg(g, s, geo, recombination_algorithm=None):
        orig_cfg(g, s, geo, recombination_algorithm=recombination_algorithm)
        for k, v in opts.items():
            g.option.setNumber(k, v)

    meshing._configure_size_field = cfg

    try:
        gmsh.initialize()
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add(spec.name)
        geo = geo_mod.build(gmsh, spec)
        rep = meshing.build_mesh(gmsh, spec, geo)
        out = {
            "n_nodes": rep.n_nodes,
            "n_elements": rep.n_elements,
            "tri3": rep.tri_count,
            "minJ": rep.min_quality,
            "algo": rep.recombination_algorithm,
            "escalated_from": rep.escalated_from,
            "types": dict(rep.element_types),
        }
        gmsh.finalize()
        return out
    finally:
        meshing._configure_size_field = orig_cfg
        spec.mesh.recombination_algorithm, spec.mesh.algorithm_2d = saved


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", action="append", default=None,
                    help="case name (repeatable); default = the two offenders")
    ap.add_argument("--root", default="../FEM-Bench-Aero")
    args = ap.parse_args(argv)

    cases = [(c, None) for c in args.case] if args.case else list(OFFENDERS)
    root = Path(args.root)

    for case, src in cases:
        spec = FEASpec.from_json(f"{src or 'outputs'}/{case}/{case}.spec.json")
        print(f"\n=== {case}   (size_chord={spec.mesh.size_chord} "
              f"size_span={spec.mesh.size_span} algorithm_2d={spec.mesh.algorithm_2d})")
        base = None
        for vname, variant in VARIANTS.items():
            try:
                r = probe_one(spec, variant)
            except Exception as exc:  # noqa: BLE001 - a probe reports, never dies
                print(f"  {vname:20s} ERROR {type(exc).__name__}: {exc}")
                continue
            if base is None:
                base = r
            dn = (r["n_nodes"] - base["n_nodes"]) / base["n_nodes"] * 100.0
            de = (r["n_elements"] - base["n_elements"]) / base["n_elements"] * 100.0
            mark = "OK " if r["tri3"] == 0 else "tri3"
            esc = f" esc<-alg{r['escalated_from']}" if r["escalated_from"] else ""
            print(f"  {vname:20s} {mark} tri3={r['tri3']:>3d} algo={r['algo']}{esc} "
                  f"nodes={r['n_nodes']:>6d} ({dn:+5.1f} %) "
                  f"elems={r['n_elements']:>6d} ({de:+5.1f} %) minJ={r['minJ']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
