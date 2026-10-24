#!/usr/bin/env python
"""Command-line entry point for the FeaGPT pipeline reproduction.

Examples
--------
Run the default NACA4412 wing box (geometry -> mesh -> CalculiX -> results)::

    python run_pipeline.py --demo

Drive it from a natural-language line::

    python run_pipeline.py --text "NACA4412 wing box, chord 1000 mm, span 2000 mm, 5 ribs, aluminium"

Re-run an explicit specification::

    python run_pipeline.py --spec outputs/naca4412_wingbox/naca4412_wingbox.spec.json

Parametric study (this is FeaGPT's "432 configurations", smaller)::

    python run_pipeline.py --sweep "airfoil.n_ribs=3,5,7" "airfoil.chord=800,1000"

Mesh only, no solver::

    python run_pipeline.py --demo --mesh-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Windows consoles default to a legacy code page; force UTF-8 for the report.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feagpt import pipeline, planning  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402


def _print_case(r) -> None:
    tag = "OK " if r.ok else "FAIL"
    print(f"[{tag}] {r.name}")
    if r.geometry:
        g = r.geometry
        print(f"        geometry : {g.get('backend')} | {g.get('n_surfaces')} surfaces | "
              f"mid-surface area {g.get('shell_area_mm2'):,.0f} mm^2")
    if r.mesh:
        m = r.mesh
        print(f"        mesh     : {m.get('n_nodes')} nodes, {m.get('n_elements')} shells, "
              f"{m.get('element_types')}, minJ {m.get('min_quality')}")
    if r.solve.get("solver"):
        print(f"        solver   : {r.solve.get('solver')} ({Path(r.solve.get('executable','')).name}) "
              f"rc={r.solve.get('returncode')} in {r.solve.get('wall_time_s')} s")
    if r.results:
        d = r.results.get("max_disp")
        s = r.results.get("max_von_mises")
        if d is not None:
            line = f"        results  : max |u| = {d:.4f} mm"
            if s is not None:
                line += f", max von Mises = {s:.2f} MPa"
            peak = r.results.get("max_von_mises_peak")
            if peak is not None and peak != s:
                line += f" (peak over shell section points {peak:.2f} MPa)"
            print(line)
    for msg in r.messages:
        print(f"        - {msg}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Runnable reproduction of the FeaGPT GMSA pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--demo", action="store_true", help="run the built-in NACA4412 case")
    ap.add_argument("--text", help="natural-language description")
    ap.add_argument("--spec", help="path to a spec JSON")
    ap.add_argument("--sweep", nargs="+", metavar="AXIS=V1,V2",
                    help="parametric sweep, e.g. airfoil.n_ribs=3,5,7")
    ap.add_argument("--out", default="outputs", help="output root directory")
    ap.add_argument("--mesh-only", action="store_true", help="stop after meshing")
    ap.add_argument("--deck-only", action="store_true",
                    help="stop after writing the input deck (no solve) -- used to "
                         "hand an Abaqus job to a shell outside the sandbox")
    ap.add_argument("--verbose", action="store_true", help="stream solver/gmsh output")
    ap.add_argument("--solver", choices=("auto", "ccx", "abaqus"), default=None,
                    help="solver backend; overrides analysis.solver in the spec "
                         "(auto = ccx if available, else abaqus)")
    ap.add_argument("--stringers", type=int, default=None, metavar="N",
                    help="blade stringers per skin (0 = stiffener-free, the default); "
                         "the case is renamed ..._strN so it does not clobber the baseline")
    args = ap.parse_args(argv)

    if args.spec:
        base = FEASpec.from_json(args.spec)
    elif args.text:
        base = planning.parse_text(args.text)
    else:
        base = FEASpec()  # the default NACA4412 wing box
        base.name = "naca4412_wingbox"
        base.description = "Default NACA4412 wing box (FeaGPT reproduction)"

    if args.stringers is not None:
        base.airfoil.n_stringers_per_skin = max(0, int(args.stringers))
        base.name = f"{base.name}_str{base.airfoil.n_stringers_per_skin}"
        base.description = (
            f"{base.description} | {base.airfoil.n_stringers_per_skin} blade "
            f"stringer(s) per skin, height {base.airfoil.stringer_height} mm, "
            f"t {base.airfoil.stringer_thickness} mm"
        )

    if args.sweep:
        axes: dict[str, list] = {}
        for token in args.sweep:
            axis, _, vals = token.partition("=")
            parsed: list = []
            for v in vals.split(","):
                v = v.strip()
                try:
                    parsed.append(int(v))
                except ValueError:
                    try:
                        parsed.append(float(v))
                    except ValueError:
                        parsed.append(v)
            axes[axis] = parsed
        specs = planning.sweep(base, axes)
    else:
        specs = [base]

    print(f"FeaGPT reproduction | {len(specs)} case(s) -> {args.out}\n")
    results = []
    for s in specs:
        r = pipeline.run(
            s,
            outdir=Path(args.out) / s.name,
            mesh_only=args.mesh_only,
            deck_only=args.deck_only,
            verbose=args.verbose,
            solver_name=args.solver,
        )
        _print_case(r)
        print()
        results.append(r.to_dict())

    summary_path = Path(args.out) / "batch_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    n_ok = sum(1 for r in results if r["ok"])
    print(f"{n_ok}/{len(results)} case(s) completed. Summary -> {summary_path}")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
