#!/usr/bin/env python
"""Re-run archived cases **in place**, through one solver.

Why this exists next to ``make_dataset.py``
-------------------------------------------
``make_dataset.py`` re-exports what the pipeline already produced: it rebuilds
the mesh and copies the archived deck and results.  That is enough when only the
*metadata* changes (M1: truth.json; M2: the spec's ``structure`` block).  It is
not enough when the **deck** or the **mesh** changes, because the archived
``results.json`` then belongs to a deck that no longer exists.

Two such changes landed together on 2026-10-03:

* **D8** - the CalculiX output request moved from ``OUTPUT=2D`` (mid-surface
  layer mean) to ``OUTPUT=3D`` (expanded shell, which carries the outer fibre).
  That rewrites every ``.inp`` and therefore every CalculiX result.
* **D9** - the panel family's default mesh dropped 6 mm -> 3 mm, which rewrites
  the panel mesh and therefore both panel results **and** their Abaqus
  cross-check.

Abaqus wing-box cases are deliberately *not* re-run: their output request and
their mesh are both unchanged, so re-solving them would burn an hour to
reproduce identical numbers.

Usage::

    python rerun_solver.py --solver ccx
    python rerun_solver.py --solver abaqus --only stiffened_panel_600x600
    python rerun_solver.py --solver ccx --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feagpt import panel, pipeline  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402

SOLVER_ROOTS = {
    "ccx": ("outputs", "outputs_str", "outputs_T", "outputs_panel"),
    "abaqus": ("outputs_abaqus", "outputs_str_abaqus", "outputs_T_abaqus",
               "outputs_panel_abaqus"),
}

#: The M2 duplicate.  Dedup removes it from the dataset, so re-solving it would
#: only spend time to produce a case that is deleted one step later.
SKIP = {"naca4412_wingbox_n_ribs5_chord1000"}

#: When only the mesh recipe changed (D9), the untouched solver's cases need not
#: be re-run.  Abaqus wing boxes fall in that bucket.
ABAQUS_ONLY = {"stiffened_panel_600x600", "stiffened_panel_600x600_str3"}


def find_cases(roots) -> list[tuple[Path, Path, str]]:
    out: list[tuple[Path, Path, str]] = []
    for r in roots:
        for spec_path in sorted(Path(r).glob("*/*.spec.json")):
            if spec_path.parent.name.startswith("_"):
                continue
            name = spec_path.name[: -len(".spec.json")]
            if name != spec_path.parent.name:
                continue
            out.append((spec_path.parent, spec_path, name))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solver", choices=("ccx", "abaqus"), required=True)
    ap.add_argument("--only", nargs="+", help="restrict to these case names")
    ap.add_argument("--panel-mesh", type=float, default=panel.DEFAULT_MESH_SIZE,
                    help="mesh size (mm) to stamp onto stiffened_panel specs; "
                         "specs carry concrete values, not the factory default, "
                         "so D9's 6 mm -> 3 mm has to be applied here")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    cases = find_cases(SOLVER_ROOTS[args.solver])
    if args.only:
        cases = [c for c in cases if c[2] in set(args.only)]
    if args.solver == "abaqus":
        keep = ABAQUS_ONLY if args.only is None else set(args.only)
        cases = [c for c in cases if c[2] in keep]
    cases = [c for c in cases if c[2] not in SKIP]

    print(f"[{args.solver}] {len(cases)} case(s) to re-run")
    if not cases:
        print("  (nothing matched)")
        return 1

    n_ok = 0
    for case_dir, spec_path, name in cases:
        if args.dry_run:
            print(f"  [dry] {name}")
            continue
        spec = FEASpec.from_json(spec_path)
        # D9: the panel family's default mesh moved 6 mm -> 3 mm.  An archived
        # spec records the concrete value it was built with, not the factory
        # default, so it has to be refreshed here - otherwise the re-run would
        # faithfully rebuild the very mesh we decided to refine.
        if spec.structure.family == panel.FAMILY:
            spec.mesh.size_chord = spec.mesh.size_span = float(args.panel_mesh)
        res = pipeline.run(spec, outdir=case_dir, solver_name=args.solver)
        ok = res.ok
        n_ok += bool(ok)
        m = res.mesh or {}
        s = res.results or {}
        collapse = (s.get("solver_meta") or {})
        mu = s.get("max_disp")
        vmo = s.get("max_von_mises")
        vmm = s.get("max_von_mises_midsurface")
        print(f"  [{'OK ' if ok else 'FAIL'}] {name:46s} "
              f"nodes={m.get('n_nodes_active', '?')} minJ={m.get('min_quality', 0):.4f} "
              f"|u|={mu if mu is None else round(mu, 5)} "
              f"vM_out={vmo if vmo is None else round(vmo, 4)} "
              f"vM_mid={vmm if vmm is None else round(vmm, 4)}")
        if not ok:
            for msg in res.messages[-3:]:
                print(f"         ! {msg[:160]}")
    print(f"  -> {n_ok}/{len(cases)} solved")
    return 0 if n_ok == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
