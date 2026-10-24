"""Probe: what does gmsh's occ.fragment outDimTagsMap actually contain?

M2 replaces the bounding-box face classifier with build-time tagging carried
through ``occ.fragment``.  That only works if the map is a reliable
input-entity -> output-entity correspondence.  The gmsh doc is terse, so the
map is measured here rather than assumed:

* how many entries does it have (one per input entity?)
* does every output face appear exactly once (no double assignment)?
* does the mapped logical name agree with the old bounding-box classifier?

Run with the venv python from the repo root::

    python diagnostics/fragment_map_probe.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from feagpt import geometry as G  # noqa: E402
from feagpt.naca import NACA4  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE = ROOT / "outputs/naca4412_wingbox/naca4412_wingbox.spec.json"


def build_and_probe(spec: FEASpec):
    import gmsh

    af = NACA4.from_code(spec.airfoil.code)
    chord, span = float(spec.airfoil.chord), float(spec.airfoil.span)
    x_f, x_r = spec.airfoil.spar_chordwise
    n_surf = 120
    n_str = max(int(getattr(spec.airfoil, "n_stringers_per_skin", 0)), 0)
    str_stations = G._stringer_stations(x_f, x_r, n_str)
    occ = gmsh.model.occ

    up_sec = G._points_on_section(af, chord, x_f, x_r, n_surf, upper=True, extra=str_stations)
    lo_sec = G._points_on_section(af, chord, x_f, x_r, n_surf, upper=False, extra=str_stations)
    up_pts = [occ.addPoint(float(x), float(y), 0.0) for x, y in up_sec]
    lo_pts = [occ.addPoint(float(x), float(y), 0.0) for x, y in lo_sec]
    up_curve = G._add_curve(gmsh, up_pts)
    lo_curve = G._add_curve(gmsh, lo_pts)
    front_curve = occ.addLine(lo_pts[-1], up_pts[0])
    rear_curve = occ.addLine(up_pts[-1], lo_pts[0])
    occ.addCurveLoop([up_curve, rear_curve, lo_curve, front_curve])
    out = occ.extrude([(1, up_curve), (1, rear_curve), (1, lo_curve), (1, front_curve)],
                      0.0, 0.0, span, recombine=False)
    side = [tag for dim, tag in out if dim == 2]
    upper_skin, rear_web, lower_skin, front_web = side

    stringer_lines, stringer_meta = [], []
    if str_stations:
        up_grid, lo_grid = af.surface(n=n_surf, spacing="cosine")
        xg = up_grid[:, 0]
        h_req = float(getattr(spec.airfoil, "stringer_height", 20.0))
        for side_name, sec, sgn in (("upper", up_sec, -1.0), ("lower", lo_sec, +1.0)):
            for xs in str_stations:
                k = int(np.argmin(np.abs(sec[:, 0] / chord - xs)))
                x_mm, y_mm = float(sec[k, 0]), float(sec[k, 1])
                yu = float(np.interp(xs, xg, up_grid[:, 1]))
                yl = float(np.interp(xs, xg, lo_grid[:, 1]))
                h = min(h_req, 0.35 * (yu - yl) * chord)
                p_top = occ.addPoint(x_mm, y_mm, 0.0)
                p_bot = occ.addPoint(x_mm, y_mm + sgn * h, 0.0)
                stringer_lines.append(occ.addLine(p_top, p_bot))
                stringer_meta.append({"x": x_mm, "side": side_name, "box_mid": 0.5 * (yu + yl) * chord})
    str_faces = []
    if stringer_lines:
        out_s = occ.extrude([(1, ln) for ln in stringer_lines], 0.0, 0.0, span, recombine=False)
        str_faces = [tag for dim, tag in out_s if dim == 2]
    n_each = len(str_stations)

    rib_faces = []
    n_ribs = max(int(spec.airfoil.n_ribs), 2)
    for z in np.linspace(0.0, span, n_ribs):
        rp = [occ.addPoint(float(x), float(y), float(z)) for x, y in up_sec]
        rp += [occ.addPoint(float(x), float(y), float(z)) for x, y in lo_sec]
        r_up = G._add_curve(gmsh, rp[: len(up_sec)])
        r_lo = G._add_curve(gmsh, rp[len(up_sec):])
        r_front = occ.addLine(rp[-1], rp[0])
        r_rear = occ.addLine(rp[len(up_sec) - 1], rp[len(up_sec)])
        loop = occ.addCurveLoop([r_up, r_rear, r_lo, r_front])
        rib_faces.append(occ.addPlaneSurface([loop]))

    occ.synchronize()

    # ---- the tagged build order we intend to use ------------------------- #
    named_objects = (
        [("upper_skin", upper_skin), ("lower_skin", lower_skin),
         ("front_spar", front_web), ("rear_spar", rear_web)]
        + [("stringers_upper", t) for t in str_faces[:n_each]]
        + [("stringers_lower", t) for t in str_faces[n_each:]]
    )
    named_tools = [("ribs", t) for t in rib_faces]
    inputs = named_objects + named_tools

    out_dimtags, out_map = occ.fragment(
        [(2, t) for _, t in named_objects],
        [(2, t) for _, t in named_tools],
    )
    occ.synchronize()

    print(f"inputs: {len(inputs)}  (objects {len(named_objects)} / tools {len(named_tools)})")
    print(f"outDimTags: {len(out_dimtags)} entries; dims={Counter(d for d, _ in out_dimtags)}")
    print(f"outDimTagsMap: {len(out_map)} lists")
    print("first 6 map entries (created entity counts):",
          [len(m) for m in out_map[:6]])

    # every created face -> which input claimed it
    claim: dict[int, list[str]] = {}
    created_faces: list[int] = []
    for i, created in enumerate(out_map):
        if i < len(inputs):
            logical = inputs[i][0]
        else:
            logical = "<extra>"
        for dim, tag in created:
            if dim == 2:
                created_faces.append(tag)
                claim.setdefault(tag, []).append(logical)

    n_dup = sum(1 for v in claim.values() if len(v) > 1)
    all_faces = [t for d, t in out_dimtags if d == 2]
    unclaimed = [t for t in all_faces if t not in claim]
    print(f"\nfaces in outDimTags: {len(all_faces)}  claimed via map: {len(claim)}")
    print(f"claimed by >1 input: {n_dup}   unclaimed: {len(unclaimed)}")

    # cross-check against the OLD bounding-box classifier
    old = G._classify_faces(gmsh, all_faces, x_f * chord, x_r * chord,
                            stringer_stations=[(m["x"], m["box_mid"]) for m in stringer_meta])
    tag2old = {}
    for g, tags in old.items():
        for t in tags:
            tag2old.setdefault(t, []).append(g)

    disagree = []
    for t in all_faces:
        new = sorted(set(claim.get(t, ["<none>"])))
        prev = sorted(set(tag2old.get(t, ["<none>"])))
        if new != prev:
            disagree.append((t, new, prev))
    print(f"\ntag-vs-bbox disagreements: {len(disagree)}")
    for t, new, prev in disagree[:15]:
        bb = gmsh.model.getBoundingBox(2, t)
        print(f"  face {t:5d} tagged={new} bbox={prev} bb={tuple(round(v,2) for v in bb)}")

    print("\ntagged group sizes:",
          {g: sum(1 for t in claim if g in claim[t]) for g in
           ("upper_skin", "lower_skin", "front_spar", "rear_spar",
            "stringers_upper", "stringers_lower", "ribs")})


def main() -> int:
    import gmsh

    case = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CASE
    spec = FEASpec.from_json(case)
    print(f"=== probe {spec.name} (stringers/skin={spec.airfoil.n_stringers_per_skin})")
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("probe")
    try:
        build_and_probe(spec)
    finally:
        gmsh.finalize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
