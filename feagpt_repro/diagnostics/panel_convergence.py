#!/usr/bin/env python
"""Convergence probe: FE plain plate vs the Navier closed form, over mesh size.

The first production run of the plain 600 x 600 x 2 mm panel gave a centre
deflection of 0.8970 mm against a Navier value of 0.9627 mm - a 6.8 % deficit.
A deficit is the *expected* sign (a discrete model is stiffer than the continuum
it approximates, so it converges upwards), but 6.8 % is far too large to wave
through as "discretisation".  So it is measured over a range of sizes rather
than assumed, which separates the two possibilities:

* the gap **shrinks** with refinement -> discretisation, and the reported
  tolerance is set from the data;
* the gap **stays put** -> the model is wrong (boundary condition, thickness,
  load), and no tolerance would have made it right.

The same script also re-runs the plain plate with only ``w`` restrained on the
edges, which is the textbook "soft" simple support.  That separates "the plate
is under-supported" from "the elements are stiff": if the two agree, the
translation-only support is not the cause.

Usage::

    python diagnostics/panel_convergence.py [--json panel_convergence.json]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from feagpt import post  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402


def navier_wmax(a: float, b: float, q: float, t: float, E: float, nu: float,
                nmax: int = 401) -> float:
    """Navier double-sine solution, uniform load, all four edges simply supported.

        w = 16q/(pi^6 D) * sum_{m,n odd} (-1)^((m-1)/2+(n-1)/2)
                                     / (m n ((m/a)^2 + (n/b)^2)^2)

    Sanity anchor: for a square plate it must reproduce the tabulated
    0.00406 q a^4 / D.
    """
    D = E * t**3 / (12.0 * (1.0 - nu**2))
    s = 0.0
    for m in range(1, nmax + 1, 2):
        sm = 1.0 if ((m - 1) // 2) % 2 == 0 else -1.0
        for n in range(1, nmax + 1, 2):
            sn = 1.0 if ((n - 1) // 2) % 2 == 0 else -1.0
            s += sm * sn / (m * n * ((m / a) ** 2 + (n / b) ** 2) ** 2)
    return 16.0 * q / (math.pi**6 * D) * s


def run(size: float, clamp_dofs=(1, 3), tag: str = "") -> dict:
    """One full production-path run of the plain panel at a given mesh size."""
    from feagpt import geometry, inp_writer, meshing, pipeline, solver

    spec = FEASpec()
    spec.name = f"conv_{tag or f'{size:g}'}"
    spec.structure.family = "stiffened_panel"
    spec.structure.params = {
        "length": 600.0, "width": 600.0, "thickness": 2.0, "n_stringers": 0,
    }
    spec.mesh.size_chord = size
    spec.mesh.size_span = size
    spec.load.kind = "pressure"
    spec.load.magnitude = 1e-4

    outdir = Path("outputs/_panel_conv") / spec.name
    if clamp_dofs != (1, 3):
        # Patch the builder's declaration to run the ablation.  Done here, in a
        # probe, rather than by adding a knob to the production path for a
        # question that only needs asking once.
        real_build = geometry.build_stiffened_panel

        def patched(gmsh, sp, step_path=None, _real=real_build, _dofs=clamp_dofs):
            geo = _real(gmsh, sp, step_path)
            geo.clamp_dofs = _dofs
            return geo

        geometry.BUILDERS["stiffened_panel"] = patched
    try:
        res = pipeline.run(spec, outdir=outdir, solver_name="ccx")
    finally:
        geometry.BUILDERS["stiffened_panel"] = geometry.build_stiffened_panel

    if not res.ok:
        return {"ok": False, "log": res.messages[-3:], "size": size}
    frd = post.parse_frd(Path(res.artifacts["frd"]))
    keep = {t for t, m in spec.structure.params.items() if t in ("length", "width")} or []
    L = float(spec.structure.params.get("length", 600.0))
    W = float(spec.structure.params.get("width", 600.0))
    nodes = frd["nodes"]
    centre = min(nodes, key=lambda n: (nodes[n][0] - L / 2) ** 2 + (nodes[n][1] - W / 2) ** 2)
    uz = frd["results"]["DISP"][centre][2]
    return {
        "ok": True,
        "size": size,
        "clamp_dofs": list(clamp_dofs),
        "n_nodes": res.mesh["n_nodes"],
        "n_elements": res.mesh["n_elements"],
        "element_types": res.mesh["element_types"],
        "min_quality": res.mesh["min_quality"],
        "max_disp": res.results.get("max_disp"),
        "centre_uz": uz,
        "centre_coord": [round(v, 3) for v in nodes[centre]],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sizes", nargs="*", type=float, default=[12.0, 6.0, 3.0])
    ap.add_argument("--json", help="write the machine-readable report here")
    args = ap.parse_args(argv)

    L = W = 600.0
    q, t, E, nu = 1e-4, 2.0, 73100.0, 0.33
    ref = navier_wmax(L, W, q, t, E, nu)
    D = E * t**3 / (12.0 * (1.0 - nu**2))
    print("=" * 78)
    print("  Plain panel convergence vs Navier")
    print("=" * 78)
    print(f"  {L:g} x {W:g} x {t:g} mm | q = {q:g} MPa | E = {E:g} MPa nu = {nu}")
    print(f"  D = {D:.1f} N.mm | Navier w_max = {ref:.5f} mm "
          f"({ref / (q * L**4 / D):.5f} q a^4/D, tabulated 0.00406)")
    print("-" * 78)

    rows = []
    for size in args.sizes:
        r = run(size)
        rows.append(r)
        if not r["ok"]:
            print(f"  [{size:5g} mm] FAILED {r['log']}")
            continue
        err = (r["centre_uz"] - ref) / ref * 100.0
        print(f"  [{size:5g} mm] elem {r['n_elements']:5d} node {r['n_nodes']:5d} "
              f"{r['element_types']} minJ {r['min_quality']:.3f} | "
              f"centre uz {r['centre_uz']:+.5f} mm -> {err:+.2f} %")

    print()
    print("  Ablation - same plate, only w restrained on the edges (soft support):")
    soft = run(6.0, clamp_dofs=(3, 3), tag="soft")
    if soft["ok"]:
        err = (soft["centre_uz"] - ref) / ref * 100.0
        rows.append(soft)
        print(f"  [  soft] elem {soft['n_elements']:5d} node {soft['n_nodes']:5d} | "
              f"centre uz {soft['centre_uz']:+.5f} mm -> {err:+.2f} %")
    else:
        print(f"  soft run failed: {soft['log']}")

    print("-" * 78)
    if args.json:
        Path(args.json).write_text(
            json.dumps({"navier_wmax": ref, "runs": rows}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        print(f"  report -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
