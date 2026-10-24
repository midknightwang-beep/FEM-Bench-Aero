#!/usr/bin/env python
"""Decision probe: does ``occ.fragment`` bond blade stringers to a flat skin?

Why this has to be measured
---------------------------
The wing-box stringer is bonded to the skin along an edge that is an **exact
control point of the skin spline**, so the bond is exact by construction.  A
stiffened panel has no spline: the skin is one planar rectangle and the
stringer's foot line lies strictly **inside** it.  That is a different
topological situation, and the T5 lesson applies directly:

    two strips that merely touch in space share **0 nodes** after meshing, and a
    linear static solve still reports displacements as if nothing were wrong.

So the question "does the panel's skin actually split along the stringer foot,
and do the two then share nodes?" gets measured here, not assumed.

What is tried
-------------
``skin-objects``   ``fragment([skin], [strips])``          - skin as the object
``skin-tools``     ``fragment([skin] + strips, [])``        - everything an object
``plain``          no boolean at all (the control: the strips are separate)

What is reported, per variant
-----------------------------
* face count and how the skin was split (by bounding box);
* nodes **shared** between a stringer face and a skin face - the decisive
  number (0 = floating cantilever, which no numerical gate would catch);
* shared OCC boundary curves (the geometric side of the same question);
* the mesh quality gate reading.

Usage::

    python diagnostics/panel_bond_probe.py [--json panel_bond_probe.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from feagpt import meshing  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402

L = 600.0
W = 600.0
H = 20.0
T_STR = 2.5
STATIONS = (150.0, 300.0, 450.0)


def _build_raw(gmsh):
    """Skin rectangle + one blade strip per station.  Returns (skin, strips)."""
    occ = gmsh.model.occ
    skin = occ.addRectangle(0.0, 0.0, 0.0, L, W)
    lines = []
    for xs in STATIONS:
        # the strip's cross-section, in the plane y = 0: from the skin (z = 0)
        # up to the stringer height
        p0 = occ.addPoint(xs, 0.0, 0.0)
        p1 = occ.addPoint(xs, 0.0, H)
        lines.append(occ.addLine(p0, p1))
    out = occ.extrude([(1, ln) for ln in lines], 0.0, W, 0.0, recombine=False)
    strips = [tag for dim, tag in out if dim == 2]
    occ.synchronize()
    return skin, strips


def _face_nodes(gmsh) -> dict[int, set]:
    nodes: dict[int, set] = {}
    for dim, tag in gmsh.model.getEntities(2):
        et, etags, enodes = gmsh.model.mesh.getElements(2, tag)
        acc: set = set()
        for arr in enodes:
            acc.update(int(n) for n in arr)
        nodes[tag] = acc
    return nodes


def _bbox(gmsh, tag):
    return [round(float(v), 6) for v in gmsh.model.getBoundingBox(2, tag)]


def _run_variant(name: str, mode: str) -> dict:
    import gmsh

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add(f"panel_probe_{name}")
    try:
        skin, strips = _build_raw(gmsh)
        occ = gmsh.model.occ

        # NOTE: ``(tag, logical)``, the same order geometry._assign_from_map
        # uses.  Getting this the wrong way round reads a full, correct map as
        # an empty one - which is exactly what the first run of this probe did.
        named = [(skin, "panel")] + [(t, "stringers") for t in strips]

        map_ok = None
        if mode == "plain":
            made = dict(named)
        elif mode == "skin-objects":
            out_dimtags, out_map = occ.fragment([(2, skin)], [(2, t) for t in strips])
            occ.synchronize()
            made, map_ok = _read_map(out_dimtags, out_map, named)
        elif mode == "skin-tools":
            out_dimtags, out_map = occ.fragment(
                [(2, skin)] + [(2, t) for t in strips], [])
            occ.synchronize()
            made, map_ok = _read_map(out_dimtags, out_map, named)
        else:
            raise ValueError(mode)

        occ.synchronize()
        all_faces = sorted({t for d, t in gmsh.model.getEntities(2)})
        orphan = [t for t in all_faces if t not in made]

        # ---- mesh ------------------------------------------------------- #
        spec = FEASpec()
        spec.mesh.size_chord = 12.0
        spec.mesh.size_span = 12.0
        meshing._configure_size_field(gmsh, spec, None)
        gmsh.model.mesh.generate(2)
        fnodes = _face_nodes(gmsh)

        tagged: dict[int, str] = {}
        for tag, logical in made.items():
            tagged[tag] = logical
        skin_faces = [t for t, g in tagged.items() if g == "panel"]
        str_faces = [t for t, g in tagged.items() if g == "stringers"]

        shared: dict[int, int] = {}
        for s in str_faces:
            acc: set = set()
            for k in skin_faces:
                acc |= fnodes.get(s, set()) & fnodes.get(k, set())
            shared[s] = len(acc)

        # OCC side of the same question: boundary curves shared by a strip and
        # a skin face (wrapped, because getBoundary returns (dim, tag) tuples).
        occ_shared = 0
        skin_bnd = set()
        for k in skin_faces:
            for d, t in gmsh.model.getBoundary([(2, k)], oriented=False):
                skin_bnd.add((d, t))
        for s in str_faces:
            for d, t in gmsh.model.getBoundary([(2, s)], oriented=False):
                if (d, t) in skin_bnd:
                    occ_shared += 1

        report = {
            "variant": name,
            "mode": mode,
            "n_faces_total": len(all_faces),
            "n_skin_faces": len(skin_faces),
            "n_stringer_faces": len(str_faces),
            "n_unclaimed_faces": len(orphan),
            "map_complete": map_ok,
            "skin_face_boxes": sorted(_bbox(gmsh, t) for t in skin_faces),
            "stringer_shared_nodes": sorted(shared.values()),
            "stringer_faces_with_zero_shared_nodes": sum(1 for v in shared.values() if v == 0),
            "occ_shared_boundary_curves": occ_shared,
        }
        q = []
        for t in all_faces:
            et, etags, _ = gmsh.model.mesh.getElements(2, t)
            for arr in etags:
                q.extend(int(x) for x in arr)
        if q:
            quals = gmsh.model.mesh.getElementQualities(q, "minSICN")
            report["n_nodes"] = len(gmsh.model.mesh.getNodes()[0])
            report["n_elements"] = len(q)
            report["min_quality"] = round(min(float(v) for v in quals), 4)
        return report
    finally:
        gmsh.finalize()


def _read_map(out_dimtags, out_map, named_inputs):
    """Index ``outDimTagsMap`` the way ``geometry._assign_from_map`` does."""
    made: dict[int, str] = {}
    claim: dict[int, list] = {}
    for i, created in enumerate(out_map):
        if i >= len(named_inputs):
            break
        logical = named_inputs[i][1]
        for dim, tag in created:
            if dim == 2:
                made[tag] = logical
                claim.setdefault(tag, []).append(logical)
    faces = [t for d, t in out_dimtags if d == 2]
    complete = (len(claim) == len(faces)
                and all(len(v) == 1 for v in claim.values()))
    return made, complete


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", help="write the machine-readable report here")
    args = ap.parse_args(argv)

    results = []
    for name, mode in (("plain", "plain"),
                       ("skin-objects", "skin-objects"),
                       ("skin-tools", "skin-tools")):
        print(f"=== {name}")
        try:
            r = _run_variant(name, mode)
        except Exception as exc:                          # noqa: BLE001 - reported
            r = {"variant": name, "mode": mode,
                 "error": f"{type(exc).__name__}: {exc}"}
        results.append(r)
        if "error" in r:
            print(f"  ERROR: {r['error']}")
            continue
        print(f"  faces           : {r['n_faces_total']} "
              f"(skin {r['n_skin_faces']} + stringers {r['n_stringer_faces']}"
              + (f" + unclaimed {r['n_unclaimed_faces']}" if r['n_unclaimed_faces'] else "")
              + ")")
        if r["map_complete"] is not None:
            print(f"  outDimTagsMap   : complete={r['map_complete']}")
        print(f"  shared nodes    : {r['stringer_shared_nodes']} "
              f"| strips with 0 shared nodes: {r['stringer_faces_with_zero_shared_nodes']}")
        print(f"  shared curves   : {r['occ_shared_boundary_curves']}")
        print(f"  mesh            : {r.get('n_nodes')} nodes, {r.get('n_elements')} shells, "
              f"minJ {r.get('min_quality')}")

    if args.json:
        Path(args.json).write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nreport -> {args.json}")

    # verdict: a variant is usable when every strip shares nodes with the skin
    good = [r for r in results
            if r.get("stringer_faces_with_zero_shared_nodes") == 0
            and r.get("n_stringer_faces") == len(STATIONS)
            and r.get("n_skin_faces") == len(STATIONS) + 1]
    print()
    print(f"VERDICT: {'usable variants: ' + ', '.join(r['variant'] for r in good) if good else 'NONE - bonding failed'}")
    return 0 if good else 2


if __name__ == "__main__":
    raise SystemExit(main())
