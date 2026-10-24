#!/usr/bin/env python
"""Re-export existing pipeline runs as a FEM-Bench-Aero case set (M1).

Reads what the pipeline already produced (spec / step / inp / results), rebuilds
the mesh so the case is complete, and writes one self-contained directory per
specification::

    <root>/modeling/<case_id>/     CalculiX  - the *publishable* A-subset case
    <root>/_xval/<case_id>/        Abaqus    - internal cross-check evidence only

Why two trees
-------------
Abaqus is commercial.  Its ODB and everything derived from it may be used
internally to prove a model right (gate 3), but must **not** ship in a released
dataset.  Keeping it under ``_xval/`` makes that boundary impossible to cross by
accident: a release is ``modeling/`` and nothing else.

Why no solver runs
------------------
The mesh is deterministic - rebuilding a case reproduces the archived FRD's
active-node count exactly (verified on the seeds).  Re-export therefore needs no
solve at all: it writes the missing ``.msh`` and the semantic ``truth.json`` and
copies the rest.

Usage::

    python make_dataset.py --solver ccx    --cases outputs outputs_str      --root ../FEM-Bench-Aero
    python make_dataset.py --solver abaqus --cases outputs_abaqus outputs_str_abaqus --root ../FEM-Bench-Aero
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feagpt import geometry, meshing, pipeline, topology  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402

#: canonical file names inside a case directory (the four-piece set + truth)
FILE_MAP = {
    "spec": "spec.json",
    "inp": "model.inp",
    "step": "model.step",
    "msh": "model.msh",
    "results": "model.results.json",
    "truth": "truth.json",
}

TREE = {"ccx": "modeling", "abaqus": "_xval"}


def find_cases(roots) -> list[tuple[Path, Path, str]]:
    """Locate case directories: a dir named ``<name>`` holding ``<name>.spec.json``."""
    out: list[tuple[Path, Path, str]] = []
    for r in roots:
        for spec_path in sorted(Path(r).glob("*/*.spec.json")):
            if spec_path.parent.name.startswith("_"):
                continue  # helper dirs such as outputs/_verify
            name = spec_path.name[: -len(".spec.json")]
            if name != spec_path.parent.name:
                continue
            out.append((spec_path.parent, spec_path, name))
    return out


def _rebuild_mesh(spec: FEASpec, msh_path: Path) -> tuple[dict, int]:
    """Rebuild geometry + mesh, write ``model.msh``.

    Returns ``(topology_reading, n_active_nodes)``.  The active-node count comes
    from the same reduction the pipeline uses to write the deck, so it can be
    compared against the archived result's ``n_nodes`` - see :func:`export_case`
    for why that comparison matters.
    """
    import gmsh

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.option.setNumber("General.Verbosity", 1)
    gmsh.model.add(spec.name)
    try:
        geo = geometry.build(gmsh, spec)
        report = meshing.build_mesh(gmsh, spec, geo)
        if not report.passed:
            raise RuntimeError(
                f"mesh gate failed for {spec.name}: minJ {report.min_quality}"
            )
        gmsh.write(str(msh_path))
        topo = topology.collect(gmsh, spec, geo)
        extracted = meshing.extract_mesh(gmsh)
        elements = pipeline._collect_groups(gmsh, geo.surfaces)
        nodes, _ = meshing.referenced_nodes(extracted["nodes"], elements)
        return topo, len(nodes)
    finally:
        gmsh.finalize()


class SameSourceError(RuntimeError):
    """The archived result does not belong to the mesh the spec rebuilds."""


def export_case(case_dir: Path, spec_path: Path, name: str,
                root: Path, solver: str) -> tuple[dict, dict, int]:
    """Export one existing run into the case layout.  Returns (truth, scalars, n_active).

    Guards against a silent mismatch that the semantic gate cannot see: a case
    whose ``spec.json`` no longer builds the model its ``results.json`` came
    from.  That happens for real - the seven seeds written before the stringer
    parameter was wired up carry ``n_stringers_per_skin = 3`` while their
    geometry has no stringers at all.  Rebuilding now *does* add the stringers,
    so the fresh ``.msh`` and the archived result would describe two different
    models.  Node counts are the cheap, decisive discriminator, so a mismatch
    aborts the export instead of producing a case that looks complete.
    """
    spec = FEASpec.from_json(spec_path)
    target = root / TREE[solver] / name
    target.mkdir(parents=True, exist_ok=True)

    raw_res = case_dir / f"{name}.results.json"
    scalars = json.loads(raw_res.read_text(encoding="utf-8")) if raw_res.exists() else {}

    topo, n_active = _rebuild_mesh(spec, target / FILE_MAP["msh"])

    n_archived = scalars.get("n_nodes")
    if n_archived is not None and n_archived != n_active:
        raise SameSourceError(
            f"rebuilt mesh has {n_active} active nodes but the archived result "
            f"has {n_archived}: spec.json no longer builds the model that "
            f"results.json came from (stale semantics - re-run the solver)"
        )

    # Write the *canonical* spec, i.e. re-serialise rather than byte-copy the
    # source file.  Since M2 the spec carries a ``structure`` block; a verbatim
    # copy of a pre-M2 spec.json would omit it, and while the hash check would
    # still pass (both sides re-load and re-serialise), a consumer reading
    # spec.json would not see the field.  The dataset ships canonical specs.
    spec.to_json(target / FILE_MAP["spec"])
    for key, src_name in (("inp", f"{name}.inp"), ("step", f"{name}.step")):
        src = case_dir / src_name
        if src.exists():
            shutil.copyfile(src, target / FILE_MAP[key])
    if raw_res.exists():
        shutil.copyfile(raw_res, target / FILE_MAP["results"])

    truth = topology.build_truth(spec, topo, scalars, solver)
    (target / FILE_MAP["truth"]).write_text(
        json.dumps(truth, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return truth, scalars, n_active


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solver", choices=("ccx", "abaqus"), required=True)
    ap.add_argument("--cases", nargs="+", required=True,
                    help="existing pipeline output roots")
    ap.add_argument("--root", required=True, help="FEM-Bench-Aero root directory")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root)
    cases = find_cases(args.cases)
    tree = TREE[args.solver]
    print(f"[{args.solver}] {len(cases)} case(s) -> {root / tree}")
    if not cases:
        print("  (nothing found - check --cases)")
        return 1

    npass = 0
    nrej = 0
    for case_dir, spec_path, name in cases:
        if args.dry_run:
            print(f"  [dry] {name}")
            continue
        try:
            truth, scalars, n_active = export_case(
                case_dir, spec_path, name, root, args.solver)
        except SameSourceError as exc:
            nrej += 1
            print(f"  [REJECT] {name:42s} {exc}")
            continue
        gate = truth["semantic_gate"]
        npass += bool(gate["pass"])
        flag = "OK " if gate["pass"] else "FAIL"
        mu = scalars.get("max_disp")
        mu_s = f"{mu:.4f} mm" if isinstance(mu, (int, float)) else "n/a"
        print(f"  [{flag}] {name:46s} {len(gate['checks'])} checks  "
              f"nodes={n_active}  max|u|={mu_s}")

    if not args.dry_run:
        tail = f", {nrej} rejected (stale semantics)" if nrej else ""
        print(f"gate4 semantic: {npass}/{len(cases)} PASS{tail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
