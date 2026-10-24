#!/usr/bin/env python
"""What *EL FILE, OUTPUT=2D actually reports for a shell - measured, not assumed.

Why this exists
---------------
``inp_writer`` writes ``*EL FILE, OUTPUT=2D``, and the reason given in its
docstring is that without it CalculiX expands shells to solids and reports two
nodes per mid-surface node.  That is true (measured below: the FRD node count
exactly doubles).  What was *not* known is which stress comes out of each
variant, and it matters a great deal:

    on a bending-dominated model the two differ by a factor of ~300.

``OUTPUT=2D`` reports the **mid-surface (membrane)** stress.  For a thin plate in
bending the mid-surface stress is *zero* - all the stress lives at z = +/-t/2 -
so the sizing quantity is simply absent from the output.  A model can therefore
be built, meshed, solved, pass all four gates and report a peak stress that is
not the stress an engineer would size against.

Measured here (600 x 600 x 2 mm simply supported plate, q = 1e-4 MPa, 6 mm mesh):

    OUTPUT=2D   centre node at z = 0    sigma = (0, 0, 0, 0, ~0, ~0)  vM = 0.008
    no OUTPUT   centre nodes at z = -1  sigma = (2.634, 2.633, ...)   vM = 2.633
    classical   sigma_max = 6 M/t^2 at the centre                     vM = 2.587

so the expanded output is right to +1.8 % and the 2D output is off by two and a
half orders of magnitude *because it is answering a different question*.

Consequence for the dataset
---------------------------
The deck convention is **not** changed here - switching the wing box archive to
the expanded form would change the FRD node set and break the node-label
identity that gate 3 (cross-solver) rests on.  The finding is recorded instead:
``truth.json`` now carries ``stress_definition``, so a consumer of the field data
cannot mistake a membrane value for a surface value.  Which definition the
archive should ultimately use is a decision, not an implementation detail.

Usage::

    python diagnostics/shell_stress_definition.py [--case outputs_panel/stiffened_panel_600x600_s0]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from feagpt import post, solver  # noqa: E402

DEFAULT_CASE = "outputs_panel/stiffened_panel_600x600_s0"

VARIANTS = {
    "2d": ("*NODE FILE, OUTPUT=2D\nU, RF", "*EL FILE, OUTPUT=2D\nS, E"),
    "expanded": ("*NODE FILE\nU, RF", "*EL FILE\nS, E"),
}


def _centre_node(nodes: dict, a: float, b: float) -> int:
    return min(nodes, key=lambda n: (nodes[n][0] - a / 2) ** 2 + (nodes[n][1] - b / 2) ** 2)


def run_variant(inp: Path, outdir: Path, name: str, node_kw: str, el_kw: str) -> dict:
    text = inp.read_text(encoding="utf-8")
    text = text.replace("*NODE FILE, OUTPUT=2D\nU, RF", node_kw)
    text = text.replace("*EL FILE, OUTPUT=2D\nS, E", el_kw)
    outdir.mkdir(parents=True, exist_ok=True)
    deck = outdir / f"{name}.inp"
    deck.write_text(text, encoding="utf-8")
    res = solver.run(deck)
    if not res.ok:
        return {"variant": name, "ok": False, "log": res.log[-400:]}
    frd = post.parse_frd(res.frd)
    nodes = frd["nodes"]
    stress = frd["results"].get("STRESS", {})
    if not stress:
        return {"variant": name, "ok": True, "n_nodes": len(nodes), "stress": None}
    vm = {n: post.von_mises(v) for n, v in stress.items()}
    c = _centre_node(nodes, 600.0, 600.0)
    top = max(vm, key=vm.get)
    return {
        "variant": name,
        "ok": True,
        "n_nodes": len(nodes),
        "centre_node": c,
        "centre_coord": [round(v, 4) for v in nodes[c]],
        "centre_stress": [round(v, 5) for v in stress[c]],
        "centre_vm": round(vm[c], 5),
        "max_vm": round(vm[top], 5),
        "max_vm_coord": [round(v, 3) for v in nodes[top]],
        "n_nodes_at_midsurface": sum(1 for v in nodes.values() if abs(v[2]) < 1e-9),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", default=DEFAULT_CASE,
                    help="pipeline output case directory holding <name>.inp")
    ap.add_argument("--q", type=float, default=1e-4, help="applied pressure (MPa)")
    ap.add_argument("--t", type=float, default=2.0, help="shell thickness (mm)")
    ap.add_argument("--json", help="write the machine-readable report here")
    args = ap.parse_args(argv)

    case = Path(args.case)
    inp = case / (case.name + ".inp")
    if not inp.exists():
        print(f"no deck at {inp} - run the case first")
        return 2

    # classical square-plate centre stress: sigma = 6M/t^2, M = 0.0479 q a^2
    theory = 6.0 * 0.0479 * args.q * 600.0**2 / args.t**2
    print("=" * 78)
    print("  Shell stress definition - what *EL FILE, OUTPUT=2D reports")
    print("=" * 78)
    print(f"  deck: {inp}")
    print(f"  classical centre surface stress = 6M/t^2 = {theory:.4f} MPa")
    print("-" * 78)

    rows = []
    base = None
    for name, (nk, ek) in VARIANTS.items():
        r = run_variant(inp, Path("outputs/_stress_def"), name, nk, ek)
        rows.append(r)
        if not r.get("ok"):
            print(f"  [{name:9s}] FAILED {r.get('log')}")
            continue
        if base is None:
            base = r
        print(f"  [{name:9s}] {r['n_nodes']:6d} nodes | centre {r['centre_coord']} "
              f"sigma {tuple(r['centre_stress'])} -> vM {r['centre_vm']:.4f} | "
              f"max vM {r['max_vm']:.4f} at {r['max_vm_coord']}")
    print("-" * 78)
    print(f"  node count ratio expanded/2d = "
          f"{rows[1]['n_nodes'] / rows[0]['n_nodes']:.3f} (2.0 = one extra node per "
          f"mid-surface node)")
    print(f"  classical vs expanded  : {abs(rows[1]['centre_vm'] - theory) / theory * 100:.2f} %")
    print("  VERDICT: OUTPUT=2D reports the MID-SURFACE stress; the outer-fibre")
    print("           stress requires dropping OUTPUT=2D (and doubles the node set).")

    if args.json:
        Path(args.json).write_text(
            json.dumps({"classical_centre_vm": theory, "variants": rows},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  report -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
