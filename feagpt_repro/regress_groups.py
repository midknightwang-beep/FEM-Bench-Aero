#!/usr/bin/env python
"""M2 regression: the face *grouping* must not move.

M2 replaces the face classifier.  The old one inferred each face's logical
group from its bounding box; the new one *tags faces as they are built* and
carries the tag through ``occ.fragment`` via ``outDimTagsMap``.  That is a
change of mechanism, and a change of mechanism is exactly the kind of edit that
silently renames a group of faces while every numerical gate still passes.

So the grouping gets its own regression, and it is deliberately **not** a count
comparison.  Counts can agree while the *faces* move (one rib face swapping
sides, a spar face absorbed into a skin).  The fingerprint here is per group:

* the ``(xmin,ymin,zmin,xmax,ymax,zmax)`` box of every face, rounded to 6 dp and
  sorted - a tag-independent signature of *which* faces are in the group;
* the topology counters from :func:`feagpt.topology.collect` (a cheap
  cross-check that also catches a changed rib-plane set).

Face tags themselves are deliberately excluded: gmsh renumbers after a boolean
operation, so tags are not stable across code changes and comparing them would
report noise, not regressions.

Usage::

    # before touching the classifier - freeze the reference
    python regress_groups.py --save regress_baseline_groups.json

    # after the rewrite - must be identical
    python regress_groups.py --check regress_baseline_groups.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feagpt import geometry, meshing, topology  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402

ROUND = 6


def _spec_paths(roots) -> list[Path]:
    out: list[Path] = []
    for r in roots:
        for p in sorted(Path(r).glob("*/*.spec.json")):
            if p.parent.name.startswith("_"):
                continue
            if p.name != p.parent.name + ".spec.json":
                continue
            out.append(p)
    return out


def fingerprint(spec: FEASpec) -> dict:
    """Rebuild the model and read back what the classifier decided."""
    import gmsh

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add(spec.name)
    try:
        geo = geometry.build(gmsh, spec)
        report = meshing.build_mesh(gmsh, spec, geo)
        topo = topology.collect(gmsh, spec, geo)

        groups: dict[str, list] = {}
        for name, tags in geo.surfaces.items():
            boxes = []
            for t in tags:
                bb = gmsh.model.getBoundingBox(2, t)
                boxes.append([round(float(v), ROUND) for v in bb])
            boxes.sort()
            groups[name] = boxes

        # a per-group face-count view of the *tagged* classifier result
        counts = {k: len(v) for k, v in geo.surfaces.items()}
        return {
            "mesh": {
                "n_nodes": report.n_nodes,
                "n_elements": report.n_elements,
                "min_quality": round(report.min_quality, 4),
                "element_types": report.element_types,
                "passed": report.passed,
            },
            "counts": counts,
            "topology_geometry": topo["geometry"],
            "groups": groups,
        }
    finally:
        gmsh.finalize()


def _diff(ref: dict, got: dict) -> list[str]:
    """Human-readable list of every difference between two fingerprints."""
    issues: list[str] = []
    for key in ("mesh", "counts", "topology_geometry"):
        if ref.get(key) != got.get(key):
            issues.append(f"{key}: {ref.get(key)} != {got.get(key)}")
    rg, gg = ref.get("groups") or {}, got.get("groups") or {}
    if set(rg) != set(gg):
        issues.append(f"group names differ: {sorted(rg)} vs {sorted(gg)}")
    for name in sorted(set(rg) & set(gg)):
        a, b = rg[name], gg[name]
        if a == b:
            continue
        only_ref = [x for x in a if x not in b]
        only_got = [x for x in b if x not in a]
        issues.append(
            f"group {name}: {len(a)} vs {len(b)} faces; "
            f"only-in-ref={only_ref[:3]}{'...' if len(only_ref) > 3 else ''} "
            f"only-in-got={only_got[:3]}{'...' if len(only_got) > 3 else ''}"
        )
    return issues


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", nargs="*", default=["outputs", "outputs_str"],
                    help="pipeline output roots holding <case>/<case>.spec.json")
    ap.add_argument("--save", help="write the reference fingerprint here")
    ap.add_argument("--check", help="compare against a saved reference")
    ap.add_argument("--json", help="write the observed fingerprints here")
    args = ap.parse_args(argv)
    if not args.save and not args.check:
        ap.error("give --save or --check")

    specs = _spec_paths(args.cases)
    if not specs:
        print("no specs found; check --cases")
        return 1

    observed: dict[str, dict] = {}
    for p in specs:
        spec = FEASpec.from_json(p)
        observed[spec.name] = fingerprint(spec)
        print(f"  fingerprinted {spec.name}")

    if args.json:
        Path(args.json).write_text(json.dumps(observed, indent=2), encoding="utf-8")
        print(f"fingerprints -> {args.json}")

    if args.save:
        Path(args.save).write_text(json.dumps(observed, indent=2), encoding="utf-8")
        print(f"reference saved -> {args.save} ({len(observed)} cases)")
        return 0

    ref = json.loads(Path(args.check).read_text(encoding="utf-8"))
    nbad = 0
    for name, got in observed.items():
        if name not in ref:
            print(f"  [NEW ] {name} (not in reference)")
            continue
        issues = _diff(ref[name], got)
        if issues:
            nbad += 1
            print(f"  [DIFF] {name}")
            for i in issues:
                print(f"         - {i}")
        else:
            print(f"  [SAME] {name}")
    for name in ref:
        if name not in observed:
            print(f"  [GONE] {name} (in reference, not observed)")

    print(f"\ngrouping regression: {len(observed) - nbad}/{len(observed)} identical")
    print(f"VERDICT: {'PASS' if nbad == 0 else 'FAIL'}")
    return 0 if nbad == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
