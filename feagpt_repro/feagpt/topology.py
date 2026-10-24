"""Semantic topology truth - the yardstick behind gate 4.

Why this module exists
----------------------
A model can *run*, *mesh* and *solve* while being **built wrong**.  Ask for five
ribs and three stringers and you may quietly get four ribs - and every one of the
three numerical gates still passes, because not one of them looks at what the
model *is*.  So structure semantics needs its own yardstick, and that yardstick
must be **independent of the code that built the model**, or it only proves the
builder agrees with itself.

Two readings, kept apart
------------------------
``design``
    What the specification *asks for* - pure counts read off ``FEASpec``.
    This is the input, not an observation.
``geometry``
    What the built model *actually contains*, read back from gmsh after
    ``fragment``.  This is an observation, and it is the one that can disagree.

The gate does **not** compare the two directly - they are different kinds of
number.  It derives, from ``design``, the geometry counts a *correct* model must
have (:func:`derive_expectation`), then compares those against the observed
``geometry``.  A wrong build trips it; a right build passes it.

Why the expectation is derived, not copied
------------------------------------------
Copying ``design`` into ``truth`` and comparing it back to itself proves nothing.
The value is entirely in the **mapping** from "five ribs, three stringers" to
"21 shell faces" - that mapping is the thing a wrong builder cannot fake, and it
is also the thing that must be re-derived (per structure family) when new forms
arrive in M2/M3.

The root-rib trap
-----------------
The clamped root rib is deliberately kept in its own group (``root``) so the
boundary condition can target it.  Counting ``len(groups["ribs"])`` alone
therefore reports **one rib too few** - four for a five-rib box.  That is not a
detail to paper over; it is precisely why the two readings stay separate and why
the expectation is derived rather than read off the group dictionary.
:func:`collect` folds ``root`` and ``tip`` back into the rib count.
"""

from __future__ import annotations

import hashlib
import json
import math

from . import fuselage, open_hole, panel, sections

SCHEMA_VERSION = 1
DEFAULT_FAMILY = "wingbox"
"""Structure family used when a spec does not name one.

M1 shipped this as ``"wingbox_unswept"``, read out of ``spec.extra`` as a
placeholder.  M2 promotes the family to a real spec field
(:class:`feagpt.spec.StructureSpec`) and normalises the label to the builder
registry's key (``"wingbox"``).  The ``extra`` lookup is kept as a fallback so
any spec that still carries the old key keeps resolving.
"""


def _family(spec) -> str:
    """Structure family of a case: the spec field, else the legacy ``extra`` key."""
    structure = getattr(spec, "structure", None)
    family = str(getattr(structure, "family", "") or "").strip()
    if family:
        return family
    return str(spec.extra.get("structure_family", DEFAULT_FAMILY))


# --------------------------------------------------------------------------- #
# the two readings
# --------------------------------------------------------------------------- #
def design_counts(spec) -> dict:
    """Counts the specification asks for - the *input* reading.

    Family-aware since M3: what "the spec asks for" is a different question for
    a wing box (ribs, spars, stringers), for a stiffened panel (a plate, its
    stringers and their stations) and for a fuselage barrel (a cylinder, its
    axial stringers and its ring frames), so the reading is derived from the
    family's own parameter block rather than from a wing-box-shaped one.
    """
    fam = _family(spec)
    if fam == panel.FAMILY:
        return _design_panel(spec)
    if fam == fuselage.FAMILY:
        return _design_fuselage(spec)
    if fam == open_hole.FAMILY:
        return _design_open_hole(spec)
    return _design_wingbox(spec)


def _design_wingbox(spec) -> dict:
    af = spec.airfoil
    n_str = int(af.n_stringers_per_skin)
    kind = str(getattr(af, "stringer_kind", "blade"))
    fw = float(getattr(af, "stringer_flange_width", 0.0) or 0.0)
    return {
        "family": _family(spec),
        "n_ribs": int(af.n_ribs),
        "n_spars": len(af.spar_chordwise),
        "n_webs": int(getattr(af, "n_webs", 0)),
        "n_cells": int(getattr(af, "n_cells", 1)),
        "web_stations": [round(float(v) * float(af.chord), 6)
                         for v in (getattr(af, "web_chordwise", None) or ())],
        "n_skins": 2,
        "n_stringers_per_skin": n_str,
        "n_stringers_upper": n_str,
        "n_stringers_lower": n_str,
        # Strips per stringer, from the section definition (blade 1, T 3).  Part
        # of the *input* reading because it is asked for by the spec, not
        # observed - the observation is in collect().
        #
        # The flange width goes in because the section is not determined by its
        # name alone: T with flange_width <= 0 degenerates to a blade and is 1
        # face, not 3 (see feagpt.sections).  Asking for 3 there would make
        # gate 4 reject a build that is correct.
        "n_faces_per_stringer_section": (
            sections.faces_per_section(kind, fw) if n_str else 0
        ),
        "stringer_section": kind,
        "stringer_flange_width": fw,
    }


def _design_panel(spec) -> dict:
    """What a stiffened panel's spec asks for.

    The stations go in because a panel's geometry is not described by a *count*
    of stringers alone: three stringers in the wrong places are still three
    stringers, and every count-based gate would pass.  They are derived here
    (from ``n_stringers``, see :meth:`feagpt.panel.PanelParams.stations`) rather
    than declared, so there is one number to get wrong, not two.
    """
    p = panel.parse_params(spec)
    n = int(p.n_stringers)
    return {
        "family": panel.FAMILY,
        "length": float(p.length),
        "width": float(p.width),
        "thickness": float(p.thickness),
        "n_stringers": n,
        "n_faces_per_stringer_section": (
            sections.faces_per_section(p.stringer_kind, p.stringer_flange_width)
            if n else 0
        ),
        "stringer_section": str(p.stringer_kind),
        "stringer_flange_width": float(p.stringer_flange_width),
        "stringer_pitch": p.pitch(),
        "stringer_stations": [round(v, 6) for v in p.stations()],
    }


def _design_fuselage(spec) -> dict:
    """What a fuselage barrel's spec asks for (M5 / task T3).

    The frame stations and the stringer angles go in because a barrel's geometry
    is not described by *counts* alone: eight stringers at the wrong angles are
    still eight stringers, and every count-based gate would pass.  Both are
    derived here (from ``n_stringers`` / ``n_frames``, see
    :class:`feagpt.fuselage.FuselageParams`) rather than declared, so there is
    one number to get wrong, not two - and the derived values are what gate 4
    checks the built geometry against.
    """
    p = fuselage.parse_params(spec)
    n = int(p.n_stringers)
    return {
        "family": fuselage.FAMILY,
        "diameter": float(p.diameter),
        "length": float(p.length),
        "thickness": float(p.thickness),
        "n_stringers": n,
        "n_faces_per_stringer_section": (
            sections.faces_per_section(p.stringer_kind, p.stringer_flange_width)
            if n else 0
        ),
        "stringer_section": str(p.stringer_kind),
        "stringer_flange_width": float(p.stringer_flange_width),
        "stringer_angles": [round(v, 9) for v in p.stringer_angles()],
        "n_frames": int(p.n_frames),
        "frame_z": [round(v, 6) for v in p.frame_z()],
    }


def _design_open_hole(spec) -> dict:
    """What an open-hole coupon's spec asks for (M5 / task T4).

    The hole *centre* and the *diameter* go in as well as the counts, for the
    reason the fuselage records its stringer angles: a hole of the right size in
    the wrong place is still a hole, and every count-based gate would pass.  The
    derived ``lambda`` and ``net_width`` ride along because they are what the
    analytic comparison is a function of, and deriving them here keeps one
    definition of "net section" instead of one per consumer.
    """
    p = open_hole.parse_params(spec)
    return {
        "family": open_hole.FAMILY,
        "length": float(p.length),
        "width": float(p.width),
        "thickness": float(p.thickness),
        "hole_d": float(p.hole_d),
        "hole_center": [round(v, 6) for v in p.center()],
        "lambda": round(p.lambda_ratio, 9),
        "net_width": round(p.net_width, 6),
    }


def collect(gmsh, spec, geo) -> dict:
    """Read the topology off the built geometry - the *observation* reading.

    Deliberately does not trust ``geo.surfaces`` group names alone: for the wing
    box the rib count folds in ``root`` and ``tip`` (see the module docstring)
    and the discrete rib positions are recorded as ``z`` planes, because "five
    ribs" is really a statement about *where* the ribs are, not how many faces
    survived fragmentation.  Same idea for a panel: the stringer *stations* are
    read back off the faces, not copied from the spec.
    """
    if _family(spec) == panel.FAMILY:
        geometry = _observe_panel(gmsh, geo)
    elif _family(spec) == fuselage.FAMILY:
        geometry = _observe_fuselage(gmsh, geo)
    elif _family(spec) == open_hole.FAMILY:
        geometry = _observe_open_hole(gmsh, geo)
    else:
        geometry = _observe_wingbox(gmsh, geo)
    return {"design": design_counts(spec), "geometry": geometry}


def _observe_wingbox(gmsh, geo) -> dict:
    """What the built wing box actually contains.

    ``web_stations`` is **measured**, not copied: an intermediate web is a plane
    ``x = const`` spanning the cells' full height, so its station is the centre
    of its bounding box - read off the built face rather than taken from the
    spec, which is what makes it an observation the builder could fail.  A web
    is cut by the ribs into one face per bay, and every piece lies on the same
    plane, so the set collapses to the ``n_webs`` distinct stations.
    """
    surfaces = geo.surfaces

    def n(key: str) -> int:
        return len(surfaces.get(key) or [])

    rib_z: list[float] = []
    for key in ("ribs", "root", "tip"):
        for t in surfaces.get(key) or []:
            bb = gmsh.model.getBoundingBox(2, t)
            rib_z.append(round(bb[2], 6))
    rib_z = sorted(set(rib_z))

    web_x: list[float] = []
    for t in surfaces.get("webs") or []:
        bb = gmsh.model.getBoundingBox(2, t)
        web_x.append(round(0.5 * (bb[0] + bb[3]), 6))

    return {
        "n_surfaces": int(geo.n_surfaces),
        "n_spar_faces": n("front_spar") + n("rear_spar"),
        "n_skin_faces_upper": n("upper_skin"),
        "n_skin_faces_lower": n("lower_skin"),
        "n_rib_faces": n("ribs") + n("root") + n("tip"),
        "n_stringer_faces_upper": n("stringers_upper"),
        "n_stringer_faces_lower": n("stringers_lower"),
        "n_web_faces": n("webs"),
        "n_rib_z_planes": len(rib_z),
        "rib_z_planes": rib_z,
        "web_stations": sorted(set(web_x)),
    }


def _observe_panel(gmsh, geo) -> dict:
    """What the built panel actually contains.

    ``stringer_stations`` is measured, not copied: a stringer **web** is the
    strip whose chordwise extent is zero (a flange is a horizontal strip, so it
    is not), and its station is the centre of its bounding box.  Reading it back
    from the bounding boxes rather than from the group name is what makes it an
    observation the builder could fail - a builder that ignored ``n_stringers``
    would report fewer stations than the spec asked for.
    """
    surfaces = geo.surfaces

    def n(key: str) -> int:
        return len(surfaces.get(key) or [])

    stations: list[float] = []
    for t in surfaces.get("stringers") or []:
        bb = gmsh.model.getBoundingBox(2, t)
        if bb[3] - bb[0] <= 1e-6:
            stations.append(round(0.5 * (bb[0] + bb[3]), 6))

    return {
        "n_surfaces": int(geo.n_surfaces),
        "n_skin_faces": n("panel"),
        "n_stringer_faces": n("stringers"),
        "stringer_stations": sorted(set(stations)),
    }


def _observe_fuselage(gmsh, geo) -> dict:
    """What the built barrel actually contains (M5 / task T3).

    ``n_frame_z_planes`` is the number of **distinct z planes** the frame faces
    sit on, deliberately not ``len(surfaces["frames"])``: one ring frame is cut
    into ``n_str`` arcs by the stringers, so the face count is ``n_str`` times
    the frame count, and reading faces directly would report a five-frame barrel
    as forty.  The plane count *is* the statement "how many frames", and it is
    measured off the geometry rather than copied from the spec.

    ``stringer_angles`` is measured the same way the panel measures its stringer
    stations: a stringer is a radial web whose circumferential extent is zero,
    and its angle is read from the mid-point of its bounding box.  Every piece a
    frame cut off a stringer lies on the same radial line, so the pieces share an
    angle and the set collapses to the ``n_str`` distinct ones.  A builder that
    ignored ``n_stringers`` would report fewer.
    """
    surfaces = geo.surfaces

    def n(key: str) -> int:
        return len(surfaces.get(key) or [])

    z_planes: list[float] = []
    for t in surfaces.get("frames") or []:
        bb = gmsh.model.getBoundingBox(2, t)
        z_planes.append(round(bb[2], 6))

    angles: list[float] = []
    for t in surfaces.get("stringers") or []:
        bb = gmsh.model.getBoundingBox(2, t)
        xc = 0.5 * (bb[0] + bb[3])
        yc = 0.5 * (bb[1] + bb[4])
        angles.append(round(math.atan2(yc, xc) % (2.0 * math.pi), 9))

    return {
        "n_surfaces": int(geo.n_surfaces),
        "n_skin_faces": n("skin"),
        "n_stringer_faces": n("stringers"),
        "n_frame_faces": n("frames"),
        "n_frame_z_planes": len(sorted(set(z_planes))),
        "frame_z_planes": sorted(set(z_planes)),
        "stringer_angles": sorted(set(angles)),
    }


def _observe_open_hole(gmsh, geo) -> dict:
    """What the built coupon actually contains (M5 / task T4).

    The whole point of this reading is that it can prove the **hole exists**.
    The group list cannot: an uncut rectangle is one face called ``panel``, and
    so is a plate with a hole in it, so a builder that silently skipped the
    boolean would produce the same groups and the same numbers as one that did
    not.  What changes is the *boundary*: four curves without the hole, five
    with it, and the fifth one is a closed wire whose bounding box sits strictly
    inside the plate.

    So the observation measures the cut-out off its own boundary - which curve
    is enclosed by the plate's overall bounding box, and how wide it is - rather
    than reading ``hole_d`` back off the spec.  ``hole_d_measured`` is the width
    of that enclosed curve's bounding box, i.e. the diameter of the hole that is
    actually in the mesh, and the comparison against ``design["hole_d"]`` is the
    statement "the cut-out is the size the spec asked for".
    """
    surfaces = geo.surfaces
    xmin, ymin, _zmin, xmax, ymax, _zmax = gmsh.model.getBoundingBox(-1, -1)
    tol = 1e-6
    hole_d = 0.0
    n_hole = 0
    hole_c = [0.0, 0.0]
    for _dim, t in gmsh.model.getEntities(1):
        bb = gmsh.model.getBoundingBox(1, t)
        enclosed = (bb[0] > xmin + tol and bb[1] > ymin + tol
                    and bb[3] < xmax - tol and bb[4] < ymax - tol)
        if enclosed:
            n_hole += 1
            hole_d = max(hole_d, bb[3] - bb[0])
            hole_c = [0.5 * (bb[0] + bb[3]), 0.5 * (bb[1] + bb[4])]
    return {
        "n_surfaces": int(geo.n_surfaces),
        "n_panel_faces": len(surfaces.get("panel") or []),
        "n_curves_total": int(geo.n_curves),
        "n_hole_curves": n_hole,
        "hole_d_measured": round(hole_d, 6),
        "hole_center_measured": [round(v, 6) for v in hole_c],
    }


# --------------------------------------------------------------------------- #
# derived expectation - the mapping that gives the gate its teeth
# --------------------------------------------------------------------------- #
def derive_expectation(design: dict) -> dict:
    """Geometry a *correct* model must have, per design intent.

    This mapping is what gives gate 4 its teeth, and it is **family-specific**:
    "five ribs, three stringers" says nothing about a plate, and "three
    stringers at 150/300/450 mm on a 600 mm skin" says nothing about a box, and
    "eight stringers and three frames on a 2000 mm barrel" says nothing about
    either.  So the family's own mapping is used.  An unknown family is *not*
    silently sent to the wing box - :func:`design_counts` has already raised for
    it.
    """
    fam = str(design.get("family"))
    if fam == panel.FAMILY:
        return _expect_panel(design)
    if fam == fuselage.FAMILY:
        return _expect_fuselage(design)
    if fam == open_hole.FAMILY:
        return _expect_open_hole(design)
    return _expect_wingbox(design)


def _expect_wingbox(design: dict) -> dict:
    """Geometry counts a *correct* wing box must have.

    ``n_ribs - 1`` spanwise bays: ``n_ribs`` ribs divide the span into
    ``n_ribs - 1`` panels.  ``n_stringers + 1`` chordwise panels per skin: every
    stringer adds one chordwise cut.  Every spar/stringer web runs the full span
    and is therefore cut into one face per bay.

    Cell-aware since T6: an **intermediate web** is a plane ``x = const`` that
    spans the section's full height, so it cuts three things and leaves two
    alone - and each factor is a statement about the boolean, not a convention:

    * it cuts each **skin** into one more chordwise panel, so a skin has
      ``(n_stringers + 1) * (n_webs + 1) * n_bays`` faces;
    * it cuts each **rib** into one face per cell, so the rib count is
      ``n_ribs * (n_webs + 1)`` - measured on the first build: 5 ribs -> 10
      faces for a one-web box, which is exactly what ``fragment`` must produce
      when a plane crosses a plane;
    * it is itself cut by the ribs into ``n_webs * n_bays`` faces;
    * it leaves the **spars** and the **stringers** alone, because all three are
      planes ``x = const`` and parallel planes do not meet.  (A web station is
      refused if it coincides with a stringer station - see
      ``geometry.build_wingbox`` - so this is guaranteed rather than assumed.)

    ``n_webs = 0`` collapses every factor to 1, so the M1/M2 expectation is
    unchanged term for term.

    Section-aware since M3: a stringer contributes ``n_faces_per_stringer_section``
    strips, not one.  A blade is 1 so every M1/M2 expectation is unchanged; a T
    is 3, and leaving that factor out is exactly how a flanged model would pass
    the numerical gates while its semantics were wrong.
    """
    nr = int(design["n_ribs"])
    n_str = int(design["n_stringers_per_skin"])
    n_sec = int(design.get("n_faces_per_stringer_section") or 1)
    n_web = int(design.get("n_webs") or 0)
    n_cell = n_web + 1
    n_bay = max(nr - 1, 0)
    n_chord = n_str + 1
    n_spar = int(design["n_spars"]) * n_bay
    n_skin_side = n_chord * n_cell * n_bay
    n_str_side = n_str * n_sec * n_bay
    n_rib = nr * n_cell
    n_web_faces = n_web * n_bay
    return {
        "n_spar_faces": n_spar,
        "n_skin_faces_upper": n_skin_side,
        "n_skin_faces_lower": n_skin_side,
        "n_rib_faces": n_rib,
        "n_stringer_faces_upper": n_str_side,
        "n_stringer_faces_lower": n_str_side,
        "n_web_faces": n_web_faces,
        "n_rib_z_planes": nr,
        "web_stations": [round(float(v), 6)
                         for v in (design.get("web_stations") or [])],
        "n_surfaces": n_spar + 2 * n_skin_side + 2 * n_str_side + n_rib + n_web_faces,
    }


def _expect_panel(design: dict) -> dict:
    """Geometry a *correct* stiffened panel must have.

    ``n`` stringers divide the skin into ``n + 1`` bays, and the **bond** is
    what does the dividing - so ``n + 1`` skin faces is not a bookkeeping
    convention, it is the observable of a bond that actually happened.  Measured
    (``diagnostics/panel_bond_probe.py``): built with no boolean the skin stays
    whole and the strips share **0 nodes** with it, so a model that solves
    happily can have 1 skin face and three floating cantilevers.  This
    expectation is what turns that into a gate failure rather than a shrug.

    ``stringer_stations`` is carried through from the design reading because it
    is a *geometric* prediction (where the stringers must be), not a count, and
    the observation measures it independently off the built faces.
    """
    n = int(design["n_stringers"])
    n_sec = int(design.get("n_faces_per_stringer_section") or 1)
    n_skin = n + 1
    n_str_faces = n * n_sec
    return {
        "n_skin_faces": n_skin,
        "n_stringer_faces": n_str_faces,
        "stringer_stations": [round(v, 6) for v in design["stringer_stations"]],
        "n_surfaces": n_skin + n_str_faces,
    }


def _expect_fuselage(design: dict) -> dict:
    """Geometry a *correct* fuselage barrel must have (M5 / task T3).

    Every factor follows from what the boolean does, and each has a physical
    meaning rather than being a bookkeeping convention:

    * the skin is cut by the ``n_seg`` meridians into ``n_seg`` circumferential
      patches, and by the ``n_frames - 1`` **interior** frames into
      ``n_frames - 1`` axial bays - so it has ``n_seg * (n_frames - 1)`` faces.
      The two **end** frames sit on the skin's own boundary circles and do not
      cut it; counting them would demand ``n_frames`` bays, one more than exist;
    * each stringer runs the full length and is cut by the same interior frames
      into ``n_frames - 1`` strips, and a section may itself be several faces
      (``n_faces_per_stringer_section``, 1 for a blade), giving
      ``n_str * n_faces_per_section * (n_frames - 1)``;
    * each frame is one flat web, cut by the ``n_seg`` meridians into ``n_seg``
      sectors, giving ``n_frames * n_seg``.

    ``n_seg`` is the **meridian count**: the stringer count when there are
    stringers, and :data:`feagpt.fuselage.MIN_SKIN_SEGMENTS` when there are none.
    The stringer-free member is *not* left as one closed cylinder - the family
    carries no periodic surface at all (see
    :func:`feagpt.geometry._cyl_patch`), so its skin is partitioned too and its
    frames are cut into sectors on the same meridians.  The ``or`` is what makes
    the degenerate member fall out of the *same* formula as the general one
    instead of being special-cased into a second, separately-wrong rule.

    ``n_frame_z_planes`` and ``stringer_angles`` are carried through from the
    *design* reading because they are geometric predictions (which z, which
    angle), not counts, and the observation measures them independently off the
    built faces.

    The degenerate member - ``n_stringers = 0`` and ``n_frames = 2`` - collapses
    this to a plain cylindrical shell (in ``MIN_SKIN_SEGMENTS`` patches, with two
    frames of ``MIN_SKIN_SEGMENTS`` sectors each), which is the pressure-vessel
    case with a closed-form answer; ``check_forms.check_T3`` asserts it.
    """
    n_str = int(design["n_stringers"])
    nf = int(design["n_frames"])
    n_sec = int(design.get("n_faces_per_stringer_section") or 1)
    bay = max(nf - 1, 0)
    # Meridian count: one per stringer, or the nominal partitions when the barrel
    # is stringer-free (it is never left as a single closed surface).
    nc = n_str if n_str > 0 else int(fuselage.MIN_SKIN_SEGMENTS)
    n_skin = nc * bay
    n_str_faces = n_str * n_sec * bay
    n_frame_faces = nf * nc
    return {
        "n_skin_faces": n_skin,
        "n_stringer_faces": n_str_faces,
        "n_frame_faces": n_frame_faces,
        "n_frame_z_planes": nf,
        "stringer_angles": [round(v, 9) for v in design["stringer_angles"]],
        "n_surfaces": n_skin + n_str_faces + n_frame_faces,
    }


def _expect_open_hole(design: dict) -> dict:
    """Geometry a *correct* open-hole coupon must have (M5 / task T4).

    Every factor here is the answer to "did the boolean actually run", because
    that is the one thing an open-hole model can get wrong while solving
    perfectly:

    * ``n_panel_faces`` is **1**.  Not a count of parts - it is the statement
      that the hole did not split the plate.  A cut that went wrong (a hole
      tangent to an edge, or one that clipped a corner) leaves more than one
      face, and the mesh would happily follow it;
    * ``n_curves_total`` is **5**: the rectangle's four edges plus the hole's
      one circle.  This is the number that separates "plate with a hole" from
      "plate", and an uncut coupon - which passes every other check in this
      document - fails it;
    * ``n_hole_curves`` is **1**, counted as the curves whose bounding box is
      enclosed by the plate's own.  Counting them this way is what lets
      ``hole_d_measured`` mean something: it is the width of *that* wire, not a
      number read back off the spec;
    * ``hole_d_measured`` carries the design's ``hole_d`` through as a
      *geometric* prediction (how wide the cut-out must be), the same way
      ``_expect_panel`` carries its stringer stations.

    The four edges are literal because a rectangle has four by definition; the
    ``+ 1`` is the hole.
    """
    return {
        "n_surfaces": 1,
        "n_panel_faces": 1,
        "n_curves_total": 4 + 1,
        "n_hole_curves": 1,
        "hole_d_measured": round(float(design["hole_d"]), 6),
        "hole_center_measured": [round(float(v), 6)
                                 for v in design["hole_center"]],
    }


def compare(topo: dict) -> dict:
    """Run gate 4: derived expectation (from design) vs observation (geometry)."""
    expected = derive_expectation(topo["design"])
    actual = topo["geometry"]
    checks = []
    for key, want in expected.items():
        got = actual.get(key)
        checks.append({
            "key": key,
            "expected": want,
            "actual": got,
            "pass": bool(got == want),
        })
    return {"pass": all(c["pass"] for c in checks), "checks": checks}


def gate_summary(gate: dict) -> str:
    """One-line human-readable verdict for logs."""
    if gate["pass"]:
        return f"gate4 semantic PASS ({len(gate['checks'])} checks)"
    bad = [c for c in gate["checks"] if not c["pass"]]
    detail = "; ".join(
        f"{c['key']}: want {c['expected']} got {c['actual']}" for c in bad
    )
    return f"gate4 semantic FAIL ({len(bad)}/{len(gate['checks'])}): {detail}"


# --------------------------------------------------------------------------- #
# truth document
# --------------------------------------------------------------------------- #
def spec_sha256(spec) -> str:
    """Stable hash of the spec - lets a consumer detect a changed input."""
    blob = json.dumps(spec.to_dict(), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_truth(spec, topo: dict, scalars: dict | None = None,
                solver: str | None = None) -> dict:
    """Assemble the ``truth.json`` document for one case.

    The document carries both readings *and* the derived expectation, so a
    consumer can re-run the comparison without rebuilding the geometry - which
    is what makes M2's regression ("nine seeds, group-for-group identical")
    checkable from the artefact alone.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": spec.name,
        "structure_family": topo["design"]["family"],
        "spec_sha256": spec_sha256(spec),
        "topology": {
            "design": topo["design"],
            "geometry": topo["geometry"],
            "expected_geometry": derive_expectation(topo["design"]),
        },
        "scalars": scalars or {},
        "solver": solver,
        "semantic_gate": compare(topo),
    }
