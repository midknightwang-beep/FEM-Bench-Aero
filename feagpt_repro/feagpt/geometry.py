"""Parametric geometry generation for a NACA wing box (shell idealisation).

Back-end note
-------------
FeaGPT (Qi et al., 2025) generates geometry with FreeCAD's Python API and
emits STEP.  FreeCAD is not installed in this environment, so the *same*
parametric description is realised with Gmsh's built-in OpenCASCADE kernel.
The two back-ends produce the same class of artifact (a set of thin-walled
surfaces + an optional STEP), which is all the downstream stages consume.
The substitution is deliberate and is reported in the reproduction README -
it is not presented as identical to the paper.

Topology produced
-----------------
A "wing box" is the closed thin-walled cell between the front and rear spar:

        upper skin   (between front spar and rear spar)
        lower skin   (between front spar and rear spar)
        front spar web
        rear spar web
        n_ribs transverse ribs, perpendicular to the span

The front/rear spar positions come from ``AirfoilSpec.spar_chordwise``.  The
leading- and trailing-edge overhangs are outside the load-carrying box and are
omitted, which is standard wing-box practice.

The geometry is created inside an already-initialised Gmsh session; the
session lifetime is owned by :mod:`feagpt.pipeline`.
"""

from __future__ import annotations

import math

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import fuselage, open_hole, panel, sections
from .naca import NACA4
from .spec import FEASpec


@dataclass
class GeometryResult:
    """Handles returned to the meshing stage.

    This is the *only* thing a builder has to produce, which is what lets a new
    structural family be added without touching meshing, the deck writer or the
    post-processor - none of them know what a wing box is.

    It is also where a family **declares** the things that would otherwise be
    hard-coded for the wing box downstream: which groups are clamped and loaded
    (``bc_groups``), which nodes they are (``bc_nodes``), how thick each group's
    shell is (``shell_thickness``), which freedoms the clamp removes
    (``clamp_dofs``) and which face carries a pressure (``pressure_group``).
    Adding a family therefore means adding a builder, not editing the pipeline.
    """

    surfaces: dict[str, list[int]] = field(default_factory=dict)
    """Logical name -> list of OCC surface tags (gmsh dim=2).

    Group membership is decided at **build time** (each face is named as it is
    created and the name is carried through ``occ.fragment``), not inferred
    afterwards from a bounding box.  See :func:`_assign_from_map`.
    """

    span: float = 0.0
    chord: float = 0.0
    shell_area: float = 0.0          # mm^2 of mid-surface
    bounding_box: tuple = ()
    n_surfaces: int = 0
    n_curves: int = 0
    notes: list[str] = field(default_factory=list)
    """Diagnostics from the build itself (e.g. tag-vs-bounding-box cross-check).

    Surfaced by the pipeline so a classifier disagreement is *reported* rather
    than silently absorbed - the whole reason the old geometric classifier is
    kept at all (as a cross-check) instead of being deleted.
    """

    bc_groups: dict[str, str] = field(
        default_factory=lambda: {"clamp": "root", "load": "tip"})
    """Which logical group plays which boundary-condition role.

    Declared by the builder because it is family-specific: a wing box is clamped
    at its root rib and loaded at the tip, a stiffened panel is supported on all
    four edges, a fuselage barrel at both ring frames.  The pipeline reads the
    *names* from here instead of hard-coding ``"root"``/``"tip"``.
    """

    bc_nodes: Callable[[dict], dict[str, list[int]]] | None = None
    """Optional ``node table -> {group name: [node tags]}`` for the BC groups.

    ``None`` (the wing box) means "the root rib is everything at z ~ 0 and the
    tip everything at z ~ span", which is what :meth:`resolve_bc_nodes`
    reproduces.  A family that is supported somewhere else declares its own
    selector here, because the alternative - teaching the pipeline about a new
    family - is how a wing-box convention ends up silently applied to a plate.

    Note this cannot be a simple "take the root group's nodes": the wing box
    clamps every node on the z = 0 rib face, which is *more* than the nodes its
    ``root`` group contributes, so changing that rule would move archived
    numbers.  Hence a callback with the old rule as the default.
    """

    shell_thickness: dict[str, float] = field(default_factory=dict)
    """Logical group -> shell thickness (mm), when the family can say it.

    Empty means the writer falls back to the wing-box table read off
    ``spec.airfoil``.  A panel's groups are ``panel``/``stringers`` - names the
    wing-box table has never heard of - so without this the deck would come out
    with no section at all for the right group and a section for the wrong one.
    """

    clamp_dofs: tuple[int, int] = (1, 6)
    """Freedoms removed at the clamp group.  ``(1, 6)`` = fully clamped.

    A simply supported panel is ``(1, 3)``: translations held, rotations free,
    which is the condition Navier's solution of the plate problem assumes.
    """

    pressure_group: str = "upper_skin"
    """Logical group a ``*DLOAD`` pressure acts on (wing-box default)."""

    pressure_dload_sign: float = -1.0
    """Sign to write ``*DLOAD ... P`` with, for a positive ``load.magnitude``.

    Declared by the builder because a shell's normal orientation is a property of
    *how the surface was built*, and it is not the same for every family: the
    wing box's extruded skins and the panel's ``addRectangle`` point the way the
    ``P, -p`` convention assumes, whereas the barrel's revolved skin
    (:func:`_cyl_patch`) points the other way.  Hard-coding ``-abs(p)`` in the
    writer therefore pressurised the barrel from **outside** - measured, not
    supposed: ``verify_barrel.py`` read -0.22725 mm of radial growth against a
    +0.228 mm thin-wall closed form, with every sampled mid-surface meridian in
    agreement (D21, 2026-10-05).

    ``-1.0`` (the default, and every pre-T3 model) keeps the archived wing-box
    and panel decks byte-identical; only the fuselage barrel declares ``+1.0``
    (:data:`feagpt.fuselage.PRESSURE_DLOAD_SIGN`).
    """

    mesh_size_cap: float | None = None
    """Optional ceiling on the global mesh element size (mm).

    Declared by the builder when the model contains a strip the mesher cannot
    resolve at the default size.  Measured, not assumed: a T-section stringer's
    flange is cut in two by its web, and each 15 x 500 mm half makes blossom
    full-quad fail outright ("1D mesh cannot be divided by 2").  Widening the
    flange only trades one failure for another - minJ went 0.339 / 0.225 / 0.523
    / 0.314 at widths 40 / 50 / 60 / 80 mm, which is not a trend, it is a coin
    toss.  A cap derived from the strip's own width removes the luck; see
    ``diagnostics/t5_robustness.py``.

    ``None`` (the default, and every pre-M3 model) leaves the size field exactly
    as it was, which is what keeps the archived blade cases bit-identical.
    """

    curvature_target: float | None = None
    """Target elements **per 2*pi of curvature** for this model, or ``None``.

    Declared by the builder because how finely a curved boundary must be
    discretised is a property of the *feature*, not of the part: a wing box's
    leading edge wants the same treatment it has always had, while an open
    hole's peak stress lives in the gradient across its edge and stops moving
    only once the arc is cut fine enough.

    It is also the only knob that works.  On this toolchain a per-curve
    ``gmsh.model.mesh.setSize`` is silently ignored - measured
    (``_t4_probe/setsize_lab.py``): the call is accepted, ``getSizes`` reads
    back ``0.0``, and setting 1.0 mm and 2.0 mm on the same hole both produce
    the identical 24-segment edge.  ``Mesh.MeshSizeFromCurvature`` does move it
    (24 -> 24 segments, 48 -> 48).  So the family declares the number, and the
    size field applies it - see :func:`feagpt.meshing._configure_size_field`.

    ``None`` (the default, and every pre-T4 model) keeps the historical
    ``24 if refine_at_leading_edge else 0``, which is what holds every archived
    mesh bit-identical.
    """

    blossom_only: bool = False
    """True when this model must be meshed with **blossom** recombination.

    Declared by the builder for the same reason ``mesh_size_cap`` is: it is a
    property of *this* geometry that changes how it must be meshed, and no
    downstream stage could work it out from the logical group names.  Two real
    causes, both measured rather than assumed (``_m5_probe/t3_cap_sweep.py``,
    2026-10-05):

    * a **closed** surface cannot be full-quad recombined at all - gmsh aborts
      with ``Full-quad recombination not ready yet for periodic surfaces`` on a
      plain closed cylinder, and a stringer-free barrel's skin *is* one;
    * cutting the barrel into non-periodic patches does **not** rescue full-quad
      the way it was expected to.  Every stringered barrel aborts with ``1D mesh
      cannot be divided by 2`` -- on the shipped path, for every cap in the
      sweep.  The patches are not periodic, but their swept faces still leave
      full-quad a boundary mesh it cannot halve.

    So a model that declares this stays on **blossom** recombination, and the
    triangle escalation in :func:`feagpt.meshing.build_mesh` is skipped (with a
    note) rather than allowed to crash on a second pass - escalation's only
    target is exactly the algorithm that fails here.

    ``False`` (the default, and every pre-T3 model) leaves the choice exactly as
    it was.
    """

    # ------------------------------------------------------------------ #
    def resolve_bc_nodes(self, nodes: dict) -> dict[str, list[int]]:
        """The BC node sets for this model, by the family's own rule.

        Falls back to the wing-box rule, expressed here in one place so the
        pipeline no longer contains it - and so it can be re-used by
        ``verify_solvers.py``, which has a result file instead of a build.
        """
        if self.bc_nodes is not None:
            return self.bc_nodes(nodes)
        clamp = self.bc_groups.get("clamp", "root")
        load = self.bc_groups.get("load", "tip")
        span = float(self.span)
        return {
            clamp: [t for t, (_x, _y, z) in nodes.items() if abs(z) < 1e-6],
            load: [t for t, (_x, _y, z) in nodes.items() if abs(z - span) < 1e-6],
        }



# --------------------------------------------------------------------------- #
# back-end probe
# --------------------------------------------------------------------------- #
def geometry_backend() -> str:
    """Return ``"freecad"`` when a FreeCAD Python API is importable, else ``"gmsh-occ"``.

    The pipeline lets ``FEAGPT_GEOMETRY_BACKEND=freecad`` force the
    paper-faithful path on a machine that has FreeCAD installed.
    """
    import os

    forced = os.environ.get("FEAGPT_GEOMETRY_BACKEND", "").strip().lower()
    if forced in {"freecad", "gmsh-occ", "gmsh_occ"}:
        return "freecad" if forced == "freecad" else "gmsh-occ"
    try:  # pragma: no cover - environment dependent
        import FreeCAD  # noqa: F401

        return "freecad"
    except Exception:
        return "gmsh-occ"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _add_curve(gmsh, pts: list[int]) -> int:
    """A straight line for 2 points, an interpolating spline otherwise."""
    if len(pts) < 2:
        raise ValueError("a curve needs at least two points")
    if len(pts) == 2:
        return gmsh.model.occ.addLine(pts[0], pts[1])
    return gmsh.model.occ.addSpline(pts)


def _loft_pair(occ, curve_a: int, curve_b: int) -> int:
    """The ruled face between two section curves - task T1's surface primitive.

    ``addThruSections`` happily returns several faces when its inputs are not a
    clean pair, and on a shell every extra face is counted by gate 4 as a skin.
    So the count is asserted here rather than assumed: a wrong pairing should
    fail loudly at build time, not quietly change the deck.
    """
    wire_a = occ.addWire([curve_a], checkClosed=False)
    wire_b = occ.addWire([curve_b], checkClosed=False)
    out = occ.addThruSections([wire_a, wire_b], makeSolid=False,
                              makeRuled=True, maxDegree=1)
    faces = [tag for dim, tag in out if dim == 2]
    if len(faces) != 1:
        raise RuntimeError(
            f"loft between curves {curve_a} and {curve_b} produced "
            f"{len(faces)} faces, expected exactly 1"
        )
    return faces[0]


def _points_on_section(af: NACA4, chord: float, x0: float, x1: float, n: int, upper: bool,
                       extra=()):
    """Section points between chordwise stations ``x0`` and ``x1`` (fractions).

    The stations ``x0`` and ``x1`` are the *spar positions*, and they must be
    present **exactly**.  Selecting them out of a cosine-spaced sample does not
    guarantee that: the sampled grid contains no point at 0.25c or 0.70c, so the
    "nearest" point on the upper surface (x = 0.2614c) and the nearest on the
    lower surface (x = 0.2582c) are *different* points.  Joining those two with
    the spar line produces a **skewed** spar web - 3.2 mm of chordwise lean at
    the front spar, 7.4 mm at the rear - and, because the web then has a
    non-zero chordwise extent, the face classifier in :func:`_classify_faces`
    can no longer recognise it as a spar at all.  It was folded into the upper
    skin group and the model quietly lost both spar element sets.

    So the exact stations are prepended/appended and the intermediate points are
    interpolated.  The curve is otherwise unchanged, so the mesh resolution at
    the leading edge is untouched.

    ``extra``
        Additional stations that must also be interpolated **exactly**, for the
        same reason: a stringer is bonded to the skin along its top edge, so if
        its chordwise station is not an actual control point of the skin spline,
        the two faces meet along no shared edge and the boolean produces a
        sliver (or nothing at all).  Inserting the station here makes the spline
        pass through it by construction, so the stringer/skin junction is exact.
    """
    up, lo = af.surface(n=n, spacing="cosine")
    xs_grid = up[:, 0]                     # shared ascending grid, up and lo
    ys_grid = (up if upper else lo)[:, 1]

    interior = xs_grid[(xs_grid > x0 + 1e-9) & (xs_grid < x1 - 1e-9)]
    wanted = [float(v) for v in extra if x0 + 1e-9 < float(v) < x1 - 1e-9]
    if wanted:
        interior = np.unique(np.concatenate([interior, np.asarray(wanted)]))
    xs = np.concatenate([[x0], interior, [x1]])
    ys = np.interp(xs, xs_grid, ys_grid)
    sel = np.column_stack([xs, ys]) * chord

    if not upper:
        sel = sel[::-1]  # traverse lower surface rear -> front for loop closure
    return sel


def _stringer_stations(x0: float, x1: float, n: int) -> list[float]:
    """``n`` chordwise stations strictly between the spars, evenly spaced.

    Strictly inside, so a stringer never lands on a spar: the face classifier
    tells the two apart by chordwise position, and a stringer sitting on a spar
    station would be ambiguous.
    """
    n = int(n)
    if n <= 0:
        return []
    return [x0 + (x1 - x0) * (j + 1) / (n + 1) for j in range(n)]


def _surface_area(gmsh, tags) -> float:
    total = 0.0
    for t in tags:
        total += gmsh.model.occ.getMass(2, t)
    return total


# --------------------------------------------------------------------------- #
# main builder
# --------------------------------------------------------------------------- #
def build_wingbox(gmsh, spec: FEASpec, step_path=None) -> GeometryResult:
    """Create the wing-box shell geometry in the active Gmsh / OCC session.

    Two planforms, one contract (task T1)
        A **prismatic** box (constant chord, no sweep) builds the M1 geometry:
        four section curves extruded along the span.  A swept or tapered box
        builds the same four surfaces by **lofting** between the root section
        and a scaled-and-shifted tip section, and the stringers and ribs follow
        that same ruling.  Both branches return the same
        :class:`GeometryResult`, so nothing downstream knows which one ran.

        The prismatic request must never reach the loft code: a loft between two
        *identical* sections is geometrically the same shape but a different OCC
        surface, and it meshes differently (measured on the baseline size field:
        4753 nodes / 4251 quads vs 4418 / 4300).  Routing on
        :attr:`AirfoilSpec.is_prismatic` is what keeps every archived case
        bit-identical, and ``check_forms.check_T1`` is what proves the routing
        still happens.
    """
    af = NACA4.from_code(spec.airfoil.code)
    chord = float(spec.airfoil.chord)
    span = float(spec.airfoil.span)
    x_f, x_r = spec.airfoil.spar_chordwise
    n_surf = 120  # section sampling for the splines

    n_str = max(int(getattr(spec.airfoil, "n_stringers_per_skin", 0)), 0)
    str_stations = _stringer_stations(x_f, x_r, n_str)

    # ---- intermediate webs (T6): the cell-count dimension ---------------- #
    # Read off the airfoil block (this family keeps its parameters there, see
    # StructureSpec) and validated here rather than silently repaired: both
    # failure modes below produce a model that meshes and solves while being
    # something other than what was asked for.
    web_stations = sorted(float(v) for v in
                          (getattr(spec.airfoil, "web_chordwise", None) or ()))
    for w in web_stations:
        if not (x_f + 1e-9 < w < x_r - 1e-9):
            raise ValueError(
                f"web station {w!r} is not strictly between the spars "
                f"({x_f!r}, {x_r!r}): a web outside them would coincide with - "
                f"or cross - a spar web, and the resulting face is ambiguous")
    for w in web_stations:
        for s in str_stations:
            if abs(w - s) < 1e-9:
                raise ValueError(
                    f"web station {w!r} coincides with a stringer station: the "
                    f"two are different structural members sharing one plane, "
                    f"and one would silently swallow the other's faces")

    # ---- planform (T1): how the section changes along the span ---------- #
    prismatic = bool(getattr(spec.airfoil, "is_prismatic", True))
    tip_ratio = float(getattr(spec.airfoil, "tip_chord_ratio", 1.0))
    tip_offset = span * math.tan(math.radians(
        float(getattr(spec.airfoil, "sweep_deg", 0.0))))

    def section_at(z: float) -> tuple[float, float]:
        """Scale and chordwise shift of the section at spanwise station ``z``.

        Linear in ``z`` because the loft is ruled: the ruling connects points of
        equal curve parameter, and its z is ``v * span``.  Ribs and stringers
        therefore sit *exactly* on the lofted surfaces when they use this same
        interpolation - which is what lets ``fragment`` find shared edges
        instead of cutting slivers.
        """
        t = 0.0 if not span else float(z) / span
        return (1.0 + (tip_ratio - 1.0) * t, tip_offset * t)

    def profile(scale: float, offset: float):
        """Section points (upper, lower) at the given planform scale / shift.

        The tip section is the root section scaled about its leading edge
        (``x = 0``) - decision D14 - then translated aft, so scaling the chord
        is what ``_points_on_section`` is already doing.

        The web stations ride along in ``extra`` for the same reason the
        stringer stations do: a web joins the two skins, so its station must be
        an exact control point of *both* skin splines or the junction is not a
        shared edge.
        """
        want = list(str_stations) + web_stations
        up = _points_on_section(af, chord * scale, x_f, x_r, n_surf,
                                upper=True, extra=want)
        lo = _points_on_section(af, chord * scale, x_f, x_r, n_surf,
                                upper=False, extra=want)
        shift = np.array([offset, 0.0])
        return up + shift, lo + shift

    occ = gmsh.model.occ

    # ---- section curves (in the z = 0 plane) ---------------------------- #
    # stringer stations are inserted as control points of the skin splines (see
    # _points_on_section) so the stringer/skin junction is an exact shared edge
    up_sec, lo_sec = profile(1.0, 0.0)

    # Narrowest spar web over the planform.  A spar height scales with the local
    # section, so the spanwise minimum is the root height times the tip ratio
    # (when the tip is the smaller end).  This drives the size cap below.
    spar_h_root = min(float(up_sec[0, 1] - lo_sec[-1, 1]),     # front spar
                      float(up_sec[-1, 1] - lo_sec[0, 1]))     # rear spar
    spar_h_min = spar_h_root * min(1.0, tip_ratio)

    up_pts = [occ.addPoint(float(x), float(y), 0.0) for x, y in up_sec]
    lo_pts = [occ.addPoint(float(x), float(y), 0.0) for x, y in lo_sec]

    up_curve = _add_curve(gmsh, up_pts)              # front -> rear (upper skin)
    lo_curve = _add_curve(gmsh, lo_pts)              # rear -> front (lower skin)
    front_curve = occ.addLine(lo_pts[-1], up_pts[0])   # front spar (vertical)
    rear_curve = occ.addLine(up_pts[-1], lo_pts[0])    # rear spar (vertical)

    section_loop = occ.addCurveLoop([up_curve, rear_curve, lo_curve, front_curve])

    # ---- intermediate webs (T6) ------------------------------------------ #
    # A web is a vertical line joining the two skins at its station - built the
    # same way the two spars are, the only difference being that its endpoints
    # are located by *station* instead of taken as the section's first and last
    # points.  Because each station was inserted as a control point of both skin
    # splines (see `extra` in profile()), the web meets each skin along a shared
    # edge and **no boolean is needed** - the opposite of a stringer, which is a
    # separate strip bonded on afterwards.
    #
    # The lines are deliberately *not* added to `section_loop`: that loop must
    # stay the outer boundary, and a web inside it would break the face it
    # bounds.  They are extruded as curves of their own.
    web_idx: list[tuple[int, int]] = []
    web_lines: list[int] = []
    for xs in web_stations:
        ku = int(np.argmin(np.abs(up_sec[:, 0] / chord - xs)))
        kl = int(np.argmin(np.abs(lo_sec[:, 0] / chord - xs)))
        web_idx.append((ku, kl))
        web_lines.append(occ.addLine(up_pts[ku], lo_pts[kl]))

    # ---- the four shell surfaces ---------------------------------------- #
    if prismatic:
        # Extruding curves (dim=1) yields surfaces (dim=2) -> a shell, no volumes.
        # The webs are appended to the list *after* the four boundary curves, so
        # the M1 faces keep their order - and their tags - and a web-free box
        # passes exactly the list it always did.
        to_extrude = ([(1, up_curve), (1, rear_curve), (1, lo_curve), (1, front_curve)]
                      + [(1, ln) for ln in web_lines])
        out = occ.extrude(to_extrude, 0.0, 0.0, span, recombine=False)
        side = [tag for dim, tag in out if dim == 2]
        # order follows the input list: upper skin, rear web, lower skin, front web
        upper_skin, rear_web, lower_skin, front_web = side[0], side[1], side[2], side[3]
        web_faces = side[4:]
    else:
        up_t, lo_t = profile(tip_ratio, tip_offset)
        up_pts_t = [occ.addPoint(float(x), float(y), span) for x, y in up_t]
        lo_pts_t = [occ.addPoint(float(x), float(y), span) for x, y in lo_t]
        up_curve_t = _add_curve(gmsh, up_pts_t)
        lo_curve_t = _add_curve(gmsh, lo_pts_t)
        front_curve_t = occ.addLine(lo_pts_t[-1], up_pts_t[0])
        rear_curve_t = occ.addLine(up_pts_t[-1], lo_pts_t[0])
        occ.synchronize()
        # one ruled face per section curve, in the same upper / rear / lower /
        # front order the extrusion returns, so the logical names are shared
        upper_skin = _loft_pair(occ, up_curve, up_curve_t)
        rear_web = _loft_pair(occ, rear_curve, rear_curve_t)
        lower_skin = _loft_pair(occ, lo_curve, lo_curve_t)
        front_web = _loft_pair(occ, front_curve, front_curve_t)
        # The webs follow the section the same way the boundary curves do: their
        # endpoints are the *scaled* skin points at the same indices, because
        # profile() inserts the web stations into every section it builds.  So
        # the web is the ruling of the root web - the shared skin edges it needs
        # exist at the tip too, and fragment finds them.
        if web_lines:
            web_lines_t = [occ.addLine(up_pts_t[ku], lo_pts_t[kl])
                           for ku, kl in web_idx]
            occ.synchronize()
            web_faces = [_loft_pair(occ, a, b)
                         for a, b in zip(web_lines, web_lines_t)]
        else:
            web_faces = []

    # ---- blade stringers ------------------------------------------------ #
    # A stringer is a vertical web in a plane x = const, running the full span,
    # bonded to the skin along its top edge.  Its top vertex is taken straight
    # out of the section point list, so it *is* a control point of the skin
    # spline - not a re-interpolated approximation of one.
    stringer_lines: list[int] = []
    stringer_roles: list[str] = []
    stringer_meta: list[dict] = []
    n_faces_per_section = 0
    flange_half: float | None = None
    str_sections: list[tuple[float, float, float, float, object]] = []
    if str_stations:
        up_grid, lo_grid = af.surface(n=n_surf, spacing="cosine")
        xg = up_grid[:, 0]
        h_req = float(getattr(spec.airfoil, "stringer_height", 20.0))
        kind = str(getattr(spec.airfoil, "stringer_kind", "blade"))
        fw = float(getattr(spec.airfoil, "stringer_flange_width", 30.0))
        for side_name, sec, sgn in (("upper", up_sec, -1.0), ("lower", lo_sec, +1.0)):
            for xs in str_stations:
                k = int(np.argmin(np.abs(sec[:, 0] / chord - xs)))
                x_mm, y_mm = float(sec[k, 0]), float(sec[k, 1])
                yu = float(np.interp(xs, xg, up_grid[:, 1]))
                yl = float(np.interp(xs, xg, lo_grid[:, 1]))
                # never let a stringer reach the opposite skin
                h = min(h_req, 0.35 * (yu - yl) * chord)
                # The section decides the shape; the builder only extrudes the
                # strips it returns.  A blade returns one segment, so the point
                # order (and therefore the whole model) is identical to M2's.
                sg = sections.section(kind, x_mm, y_mm, sgn, h, flange_width=fw)
                if "flange" in sg.role:
                    # remember the strip's half-width: the mesher needs a size
                    # cap derived from it, not one tuned by hand (see
                    # GeometryResult.mesh_size_cap)
                    flange_half = 0.5 * fw
                stringer_roles.extend(sg.role)
                n_faces_per_section = sg.n_faces
                stringer_meta.append({
                    "x": x_mm,
                    "side": side_name,
                    "y_top": y_mm,
                    "y_bot": y_mm + sgn * h,
                    "height": h,
                    "box_mid": 0.5 * (yu + yl) * chord,
                    "section": sg.label,
                })
                # Carried to the tip by scaling the section's own anchor point,
                # its height and its flange width - i.e. the whole cross-section
                # scales with the local chord.  That makes the tip strip exactly
                # the ruling of the root strip, so the skin edge they share at
                # the root is shared at the tip too.
                str_sections.append((x_mm, y_mm, sgn, h, sg))

        def _strip_lines(scale: float, offset: float, z: float) -> list[int]:
            lines: list[int] = []
            for x_mm, y_mm, sgn, h, sg in str_sections:
                for p0, p1 in sg.segments:
                    pt0 = occ.addPoint(float(p0[0]) * scale + offset,
                                       float(p0[1]) * scale, z)
                    pt1 = occ.addPoint(float(p1[0]) * scale + offset,
                                       float(p1[1]) * scale, z)
                    lines.append(occ.addLine(pt0, pt1))
            return lines

        stringer_lines = _strip_lines(1.0, 0.0, 0.0)

    # Build the strips.  Their logical name is decided by construction, not
    # inferred: per skin, the first ``n_str_each`` stringers are the upper ones,
    # the rest lower - and a flanged section contributes several strips per
    # stringer (web first, then flange), which is why the roles are carried.
    if stringer_lines:
        if prismatic:
            out_s = occ.extrude([(1, ln) for ln in stringer_lines],
                                0.0, 0.0, span, recombine=False)
            strip_faces = [tag for dim, tag in out_s if dim == 2]
        else:
            # The same strip, lofted from the root profile to its scaled tip
            # profile.  The two lists are in creation order, so the pairs - and
            # therefore the roles assigned below - line up.
            tip_lines = _strip_lines(tip_ratio, tip_offset, span)
            occ.synchronize()
            strip_faces = [_loft_pair(occ, a, b)
                           for a, b in zip(stringer_lines, tip_lines)]
    else:
        strip_faces = []
    n_str_each = len(str_stations)

    # ---- bond the strips of each flanged stringer together -------------- #
    # See _tag_stringer_faces for why the boolean is needed and why it is
    # skipped for a blade.  The logical names are given per stringer, in build
    # order, so the same helper serves the wing box (upper then lower) and the
    # stiffened panel (one group).
    stringer_tagged = _tag_stringer_faces(
        gmsh, strip_faces, stringer_roles,
        ["stringers_upper"] * n_str_each + ["stringers_lower"] * n_str_each,
    )

    # ---- ribs: planar faces at spanwise stations ------------------------ #
    n_ribs = max(int(spec.airfoil.n_ribs), 2)
    z_stations = np.linspace(0.0, span, n_ribs)
    rib_faces: list[int] = []
    curves: dict[str, list[int]] = {"section": [up_curve, rear_curve, lo_curve, front_curve]}
    for z in z_stations:
        # The rib outline is the *local* section.  For a swept or tapered box
        # that is the same linear blend the surfaces were lofted with, so the
        # rib meets the skins and spars along shared edges instead of cutting
        # slivers - see section_at.
        rib_up, rib_lo = profile(*section_at(z))
        rib_pts = [occ.addPoint(float(x), float(y), float(z)) for x, y in rib_up]
        rib_pts += [occ.addPoint(float(x), float(y), float(z)) for x, y in rib_lo]
        # two splines (upper, lower) + two spar lines, all in the z = const plane
        r_up = _add_curve(gmsh, rib_pts[: len(up_sec)])
        r_lo = _add_curve(gmsh, rib_pts[len(up_sec):])
        # rib outline: upper (front->rear), rear spar, lower (rear->front), front spar
        r_front = occ.addLine(rib_pts[-1], rib_pts[0])
        r_rear = occ.addLine(rib_pts[len(up_sec) - 1], rib_pts[len(up_sec)])
        loop = occ.addCurveLoop([r_up, r_rear, r_lo, r_front])
        rib_faces.append(occ.addPlaneSurface([loop]))
        curves.setdefault("ribs", []).extend([r_up, r_rear, r_lo, r_front])

    occ.synchronize()

    # ---- make the ribs share nodes with the skins/spars ----------------- #
    # `fragment` splits the shell surfaces along the rib intersection curves, so
    # rib boundaries and skins share edges (and therefore nodes).
    #
    # The logical name of every face is fixed *here*, before the boolean, and
    # carried through ``outDimTagsMap`` (input entity -> the entities it became).
    # The earlier implementation instead threw the map away and re-inferred each
    # output face's group from its bounding box ("dz~0 -> rib, dx~0 -> spar,
    # else skin").  That test is **binary**: on an unswept box a spar's chordwise
    # extent is exactly 0.0 and a skin's is 450 mm - six orders of magnitude of
    # margin.  The moment the section varies along the span (swept/tapered, M3's
    # T1) a spar web acquires a non-zero chordwise extent and falls straight
    # through into the skin branch: the model still solves, and no numerical
    # gate notices.  Tagging is immune to that by construction.
    named_inputs: list[tuple[int, str]] = [
        (upper_skin, "upper_skin"),
        (lower_skin, "lower_skin"),
        (front_web, "front_spar"),
        (rear_web, "rear_spar"),
    ]
    # A web is one face, so unlike a flanged stringer it needs no internal
    # boolean and is named directly.  It is *not* folded into the spar groups:
    # gate 4 predicts ``n_spars * n_bays`` spar faces, and a web counted there
    # would inflate the spar reading while the cell count - the thing a
    # multi-cell case exists to exercise - went unrecorded.
    named_inputs += [(t, "webs") for t in web_faces]
    named_inputs += stringer_tagged
    named_tools: list[tuple[int, str]] = [(t, "ribs") for t in rib_faces]

    all_faces: list[int] = []
    tag_notes: list[str] = []
    if rib_faces:
        out_dimtags, out_map = occ.fragment(
            [(2, t) for t, _ in named_inputs],
            [(2, t) for t, _ in named_tools],
        )
        # fragment output tags only become queryable once the model is synced,
        # so sync here - before reading any bounding boxes.
        occ.synchronize()
        all_faces = [t for d, t in out_dimtags if d == 2]
        surfaces, tag_notes = _assign_from_map(all_faces, out_map, named_inputs + named_tools)
    else:
        # No boolean ran, so the build-time names are the final answer.
        surfaces = _assign_from_names(named_inputs)
        all_faces = [t for _logical, t in named_inputs]

    occ.synchronize()

    # ---- crossing check: does the geometry agree with the tags? --------- #
    # The bounding-box classifier is kept, but demoted: it no longer decides
    # anything.  It runs beside the tagging and reports disagreement, which is
    # the cheap way to notice that a builder produced a face whose shape does not
    # match what it claimed to be.
    if all_faces:
        tag_notes += _cross_check_tagging(
            gmsh, surfaces, x_f * chord, x_r * chord,
            stringer_stations=[(m["x"], m["box_mid"]) for m in stringer_meta],
            web_stations=[w * chord for w in web_stations],
            prismatic=prismatic,
        )

    # ---- tag the root and tip patches for boundary conditions ----------- #
    # This is the builder's own BC declaration, not a pipeline convention: a wing
    # box clamps its root rib, so `root` is split out here and named as such.
    surfaces = _tag_root_tip(gmsh, surfaces, span)

    # ---- optional STEP export (matches the FreeCAD stage's artifact) ---- #
    if step_path is not None:
        from pathlib import Path

        Path(step_path).parent.mkdir(parents=True, exist_ok=True)
        occ.synchronize()
        gmsh.write(str(step_path))

    all_shell = sorted({t for k, lst in surfaces.items() if k not in {"root", "tip"} for t in lst})
    area = _surface_area(gmsh, all_shell)

    # ---- mesh size cap: the T5 fix, applied to the spar webs ------------- #
    # A strip narrower than ~2x the global element size is what produced a
    # needle quad (taper 0.6: a 43.7 mm rear spar against a 25 mm size, minSICN
    # 0.0437 at the z = 1500 rib).  The remedy is T5's, with the same constant
    # expressed for a strip rather than a flange half (0.8 x a 15 mm half = 0.4 x
    # its 30 mm width).  Declared **only for a varying planform**: a prismatic
    # spar of the same height is a rectangle and meshes cleanly at the default
    # size - measured on the archive, where the 58.3 mm chord800 spar and the
    # 20 mm blade stringers both clear the gate - so declaring it there would
    # re-mesh published cases for no observed benefit.
    mesh_size_cap = (min(0.8 * flange_half, float(spec.mesh.size_chord))
                     if flange_half else None)
    if not prismatic:
        cap_spar = _SPAR_SIZE_CAP * spar_h_min
        if mesh_size_cap is None or cap_spar < mesh_size_cap:
            mesh_size_cap = cap_spar
        tag_notes.append(
            f"mesh size capped at {cap_spar:.2f} mm = {_SPAR_SIZE_CAP:g} x the "
            f"narrowest spar web ({spar_h_min:.2f} mm): on a varying planform the "
            f"web is a trapezoid, and a strip under ~2x the global element size "
            f"meshes into needles (see _m5_probe/t1_mesh_probe.py)"
        )

    xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(-1, -1)
    return GeometryResult(
        surfaces=surfaces,
        span=span,
        chord=chord,
        shell_area=float(area),
        bounding_box=(xmin, ymin, zmin, xmax, ymax, zmax),
        n_surfaces=len(gmsh.model.getEntities(2)),
        n_curves=len(gmsh.model.getEntities(1)),
        notes=tag_notes,
        bc_groups={"clamp": "root", "load": "tip"},
        mesh_size_cap=mesh_size_cap,
    )


_SURFACE_GROUPS = ("upper_skin", "lower_skin", "front_spar", "rear_spar", "webs",
                   "stringers_upper", "stringers_lower", "ribs", "root", "tip")

_SPAR_SIZE_CAP = 0.4
"""Size ceiling as a fraction of the narrowest spar web on a varying planform.

Same rule the T5 flange established, stated for a strip: the flange cap is
``0.8 x half the flange width``, i.e. ``0.4 x`` the strip's full width, and the
spar web is a strip.  Derived from a measured grid rather than picked:
``_m5_probe/t1_cap_probe.py`` sweeps planform and rib count and the cap turns
6/12 at the default size into 12/12, while leaving every prismatic case - and so
every case already in the archive - untouched."""

PANEL_GROUPS = ("panel", "stringers")
"""Logical groups of a stiffened panel: the skin patches and the blade webs."""

FUSELAGE_GROUPS = ("skin", "stringers", "frames")
"""Logical groups of a fuselage barrel: the cylindrical skin patches, the axial
longitudinal stringers and the ring frames.

The skin is named ``skin`` rather than ``panel`` so the two families' decks stay
readable.  The stringers are named ``stringers`` as they are on a panel, but
unlike a panel a barrel does **not** ride the mesher's ``stringers``-prefix
heuristic into full-quad - measured, full-quad aborts on this family's faces, so
the builder declares ``blossom_only`` and the heuristic is never reached (see
:attr:`GeometryResult.blossom_only` and ``_m5_probe/t3_cap_sweep.py``)."""


def _tag_stringer_faces(gmsh, strip_faces, roles, names) -> list[tuple[int, str]]:
    """Bond the strips of each flanged stringer and name every resulting face.

    ``names[i]`` is the logical group of stringer ``i``, in build order.

    Why the boolean is needed at all
        A blade is a single strip, so there is nothing to bond and the boolean is
        skipped entirely - which is what keeps the blade geometry bit-identical
        to M2's (regression is a hard gate).  A flanged section is several strips
        meeting along a line, and *merely touching in space is not enough*:
        measured (``diagnostics/t_stringer_probe.py``), two independent extrudes
        share **0 nodes** after meshing, so the flange is a floating cantilever
        that a linear static solve still reports as if it were fine.
        ``occ.fragment`` bonds them (shared edge + shared nodes) at the price of
        cutting each flange in two, which is why a T section is 3 faces, not 2.

    Why the map has to be checked
        ``outDimTagsMap`` is indexed by input order (webs first, then flanges),
        and the flange blocks are ``n_flange_per`` entries per stringer.  If that
        is not what the map contains, the roll-up would name faces by the wrong
        stringer and every downstream gate would still pass - so the count of
        claimed faces is compared against the boolean's own output and a
        mismatch raises.
    """
    web_faces = [t for t, r in zip(strip_faces, roles) if r == "web"]
    flange_faces = [t for t, r in zip(strip_faces, roles) if r == "flange"]
    if not strip_faces:
        return []                       # a stiffener-free model (n_stringers = 0)
    if not web_faces:
        raise RuntimeError("stringer build produced strips but no web among them")
    n_names = len(names)

    if not flange_faces:
        return [(t, names[i]) for i, t in enumerate(web_faces)]

    occ = gmsh.model.occ
    occ.synchronize()
    out_c, map_c = occ.fragment([(2, t) for t in web_faces],
                                [(2, t) for t in flange_faces])
    occ.synchronize()
    n_web = len(web_faces)
    n_flange_per = len(flange_faces) // n_names if n_names else 0
    tagged: list[tuple[int, str]] = []
    claimed: set[int] = set()
    for j, created in enumerate(map_c):
        if j < n_web:
            k = j
        elif n_flange_per:
            k = (j - n_web) // n_flange_per
        else:                                    # pragma: no cover - defensive
            k = j - n_web
        if not 0 <= k < n_names:
            raise RuntimeError(
                f"stringer bonding: map entry {j} rolls up to stringer {k}, "
                f"outside 0..{n_names - 1} - outDimTagsMap contract broken"
            )
        for dim, tag in created:
            if dim == 2:
                tagged.append((tag, names[k]))
                claimed.add(tag)
    after = {t for d, t in out_c if d == 2}
    if claimed != after:
        raise RuntimeError(
            f"stringer bonding: {len(after - claimed)} unclaimed, "
            f"{len(claimed - after)} stray face(s) - outDimTagsMap contract broken"
        )
    return tagged


def _assign_from_names(named_inputs, group_names=_SURFACE_GROUPS) -> dict[str, list[int]]:
    """Group surfaces directly from the build-time names (no boolean ran)."""
    groups: dict[str, list[int]] = {k: [] for k in group_names}
    for tag, logical in named_inputs:
        groups[logical].append(tag)
    return groups


def _assign_from_map(out_faces, out_map, named_inputs,
                     group_names=_SURFACE_GROUPS) -> tuple[dict, list[str]]:
    """Propagate build-time face names through ``occ.fragment``.

    ``outDimTagsMap[i]`` lists the entities that input entity ``i`` became.  An
    input that the boolean did not cut maps to itself; one that was split maps to
    its pieces.  Because ``named_inputs`` is in the exact order the entities were
    passed to ``fragment`` (objects first, then tools), index ``i`` gives the
    logical name to hand to every dim-2 entity that input produced.

    The map is checked for completeness before it is trusted: every face in
    ``outDimTags`` must be claimed by **exactly one** input.  An unclaimed face
    (missing from every list) or a doubly-claimed one means the map's contract
    is not what this code assumes - a wrong grouping that would otherwise be
    silently accepted - so it is reported to the caller.
    """
    groups: dict[str, list[int]] = {k: [] for k in group_names}
    claim: dict[int, list[str]] = {}
    for i, created in enumerate(out_map):
        if i >= len(named_inputs):
            break
        logical = named_inputs[i][1]
        for dim, tag in created:
            if dim == 2:
                groups[logical].append(tag)
                claim.setdefault(tag, []).append(logical)

    notes: list[str] = []
    unclaimed = [t for t in out_faces if t not in claim]
    double = {t: v for t, v in claim.items() if len(v) > 1}
    if unclaimed:
        notes.append(
            f"tagging incomplete: {len(unclaimed)} face(s) of {len(out_faces)} "
            f"unclaimed by outDimTagsMap {unclaimed[:5]}"
        )
    if double:
        notes.append(
            f"tagging ambiguous: {len(double)} face(s) claimed by >1 input "
            f"{dict(list(double.items())[:5])}"
        )
    notes.append(f"tagged {len(claim)}/{len(out_faces)} faces via outDimTagsMap")
    return groups, notes


def _cross_check_tagging(gmsh, surfaces, x_front, x_rear, stringer_stations=(),
                         web_stations=(), prismatic=True) -> list[str]:
    """Compare the tagged grouping against the old bounding-box classifier.

    Returns a list of notes; empty means perfect agreement.  A disagreement is
    not automatically a bug - but it *is* exactly the condition under which the
    old classifier would have produced a different (and, on non-prismatic
    geometry, wrong) answer, so it must not pass unnoticed.
    """
    tagged: dict[int, str] = {}
    for logical, tags in surfaces.items():
        for t in tags:
            tagged[t] = logical
    if not tagged:
        return []

    legacy = _classify_faces(gmsh, sorted(tagged), x_front, x_rear,
                             stringer_stations=stringer_stations,
                             web_stations=web_stations)
    legacy_of: dict[int, str] = {}
    for logical, tags in legacy.items():
        for t in tags:
            legacy_of[t] = logical

    mismatches = []
    skipped_flanged = 0
    for t, logical in sorted(tagged.items()):
        old = legacy_of.get(t)
        if old is None or old in {"root", "tip"}:
            continue          # root/tip are carved out later, by _tag_root_tip
        if logical.startswith("stringers_"):
            # A flanged section (T/L/hat) has strips whose chordwise extent is
            # *not* ~0: a flange is a horizontal strip, so the legacy
            # "dx~0 -> web" rule cannot classify it by construction.  That is a
            # limit of the old rule, not a tagging error, so the strip is
            # counted and skipped rather than reported as a disagreement -
            # otherwise the cross-check would cry wolf on every flanged model
            # and stop being useful for the blade models where it does work.
            bb = gmsh.model.getBoundingBox(2, t)
            if bb[3] - bb[0] > 1e-6:
                skipped_flanged += 1
                continue
        if old != logical:
            mismatches.append((t, logical, old))

    notes: list[str] = []
    if skipped_flanged:
        notes.append(
            f"tag/bbox cross-check: {skipped_flanged} flanged-stringer strip(s) are "
            f"outside the legacy dx~0 rule (expected for T/L/hat, not an error)"
        )
    if not prismatic:
        # Expected, and worth saying out loud rather than letting a reader
        # wonder: the legacy rule keys on a spar's chordwise extent being
        # exactly zero, which stops being true the moment the section varies
        # along the span - M2's whole rationale for tagging in the first place.
        notes.append(
            f"tag/bbox cross-check: non-prismatic planform - the legacy dx~0 "
            f"spar rule cannot hold here, so its {len(mismatches)} "
            f"disagreement(s) are expected; the build-time tags are authoritative"
        )
    if not mismatches:
        notes.append(f"tag/bbox cross-check: {len(tagged)} faces agree")
        return notes
    detail = ", ".join(f"face {t}: tagged={a} bbox={b}" for t, a, b in mismatches[:8])
    notes.append(f"tag/bbox cross-check: {len(mismatches)} disagreement(s) - {detail}")
    return notes


# --------------------------------------------------------------------------- #
# stiffened panel (M3 / T2) - the second structural family
# --------------------------------------------------------------------------- #
def build_stiffened_panel(gmsh, spec: FEASpec, step_path=None) -> GeometryResult:
    """Create a flat stiffened panel: one rectangular skin plus blade stringers.

    Topology produced
        A flat skin ``length x width`` in the z = 0 plane, with
        ``n_stringers`` blade webs standing on it (+z) and running the full
        width.  No spars, no ribs, no curvature.

    Why the skin ends up in pieces
        The stringer foot line lies strictly **inside** the skin, so the bond is
        a boolean, and the boolean is what splits the skin: an ``n``-stringer
        panel is ``n + 1`` skin faces plus ``n`` stringer faces.  That split is
        not cosmetic - it is the observable that proves the bond happened (see
        below), so gate 4 predicts it exactly rather than accepting any count.

    Measured before it was relied on (``diagnostics/panel_bond_probe.py``)
        Built with no boolean, the three strips share **0 nodes** with the skin:
        three floating cantilevers that a linear static solve still reports as
        fine.  ``occ.fragment`` gives **51** shared nodes and **3** shared
        boundary curves per strip and splits the skin into **4** faces.
        ``outDimTagsMap`` is complete (every output face claimed exactly once).

    Boundary conditions are declared here, not inferred downstream
        Four edges simply supported: translations held, rotations free
        (``clamp_dofs = (1, 3)``), which is the condition Navier's closed-form
        plate solution assumes.  The clamped set is selected by
        :func:`feagpt.panel.edge_nodes` from the node table, so the same rule
        can be re-applied to a result file by the cross-solver check.
    """
    p = panel.parse_params(spec)

    # A panel's load is a pressure on its skin.  Its BC declares no node group to
    # hang a concentrated force on, so a tip_force request would silently apply
    # *nothing* - refuse instead of producing a model with no load in it.
    kind = str(getattr(spec.load, "kind", ""))
    if kind != "pressure":
        raise ValueError(
            f"stiffened_panel supports load.kind='pressure' on the skin, got "
            f"{kind!r}: the panel has no tip/root node group to carry a "
            f"concentrated force, and silently applying zero load is worse than "
            f"failing."
        )

    occ = gmsh.model.occ

    # ---- skin: one planar rectangle -------------------------------------- #
    skin = occ.addRectangle(0.0, 0.0, 0.0, p.length, p.width)

    # ---- stringers: one strip per station --------------------------------- #
    # The cross-section comes from the same library the wing box uses.  It is
    # built in the section's own local frame (u = sideways offset from the foot,
    # v = away from the skin) and then mapped onto the panel: u -> x, v -> z.
    # So blade/T/L are available here for free, and a flanged section brings its
    # flange with it.
    stringer_lines: list[int] = []
    stringer_roles: list[str] = []
    flange_half: float | None = None
    for xs in p.stations():
        sg = sections.section(p.stringer_kind, 0.0, 0.0, 1.0, p.stringer_height,
                              flange_width=p.stringer_flange_width)
        if "flange" in sg.role:
            flange_half = 0.5 * float(p.stringer_flange_width)
        for (u0, v0), (u1, v1) in sg.segments:
            pt0 = occ.addPoint(float(xs) + float(u0), 0.0, float(v0))
            pt1 = occ.addPoint(float(xs) + float(u1), 0.0, float(v1))
            stringer_lines.append(occ.addLine(pt0, pt1))
        # one role per segment, in the same order as the lines above - the
        # section decides the shape, this builder only extrudes what it returns
        stringer_roles.extend(sg.role)

    stations = p.stations()
    if not stringer_lines:
        surfaces = _assign_from_names([(skin, "panel")], PANEL_GROUPS)
        tag_notes = ["no stringers requested: the panel is a single flat face"]
        all_shell = [skin]
    else:
        out_s = occ.extrude([(1, ln) for ln in stringer_lines],
                            0.0, p.width, 0.0, recombine=False)
        strip_faces = [tag for dim, tag in out_s if dim == 2]
        occ.synchronize()

        stringer_tagged = _tag_stringer_faces(
            gmsh, strip_faces, stringer_roles, ["stringers"] * len(stations))

        # ---- bond the stringers to the skin ------------------------------ #
        named_inputs: list[tuple[int, str]] = [(skin, "panel")] + stringer_tagged
        out_dimtags, out_map = occ.fragment(
            [(2, skin)], [(2, t) for t, _ in stringer_tagged])
        occ.synchronize()
        all_shell = [t for d, t in out_dimtags if d == 2]
        surfaces, tag_notes = _assign_from_map(
            all_shell, out_map, named_inputs, PANEL_GROUPS)

    occ.synchronize()

    if step_path is not None:
        from pathlib import Path

        Path(step_path).parent.mkdir(parents=True, exist_ok=True)
        occ.synchronize()
        gmsh.write(str(step_path))

    area = _surface_area(gmsh, all_shell)
    xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(-1, -1)
    return GeometryResult(
        surfaces=surfaces,
        # span/chord are the wing box's vocabulary; the panel keeps them filled
        # in for reporting only.  Its BC does not read them - it declares
        # bc_nodes, so a plate is never asked for its "span".
        span=float(p.width),
        chord=float(p.length),
        shell_area=float(area),
        bounding_box=(xmin, ymin, zmin, xmax, ymax, zmax),
        n_surfaces=len(gmsh.model.getEntities(2)),
        n_curves=len(gmsh.model.getEntities(1)),
        notes=tag_notes + [
            f"panel {p.length:g} x {p.width:g} x {p.thickness:g} mm, "
            f"{int(p.n_stringers)} x {p.stringer_kind} stringer(s), "
            f"pitch {p.pitch() if p.pitch() else 0:g} mm"
        ],
        bc_groups={"clamp": "edges"},
        bc_nodes=lambda nodes: {"edges": panel.edge_nodes(nodes, p)},
        shell_thickness={"panel": float(p.thickness),
                         "stringers": float(p.stringer_thickness)},
        clamp_dofs=(1, 3),
        pressure_group="panel",
        mesh_size_cap=(min(0.8 * flange_half, float(spec.mesh.size_chord))
                       if flange_half else None),
    )


# --------------------------------------------------------------------------- #
# T4 - open-hole panel (M5 / task T4)
# --------------------------------------------------------------------------- #
OPEN_HOLE_GROUPS = ("panel",)
"""Logical groups of an open-hole coupon: the plate, with its cut-out.

One group, deliberately - a hole is a *feature* of the plate, not a separate
part, so there is no second surface to name.  That is also why the group list
alone cannot prove the hole was cut: an uncut rectangle has exactly the same
list.  The observables that do prove it are read back in
:func:`feagpt.topology._observe_open_hole` - the curve count (4 without the
hole, 5 with it) and the hole diameter measured off its own boundary."""


def build_open_hole_panel(gmsh, spec: FEASpec, step_path=None) -> GeometryResult:
    """A flat rectangular coupon with one circular cut-out, in tension (T4).

    What is built
        A planar skin ``length x width`` in the z = 0 plane, **minus** a disc of
        diameter ``hole_d`` at ``(hole_x, hole_y)`` (centred by default).  One
        face, one load case: a total force along +x spread over the loaded end,
        the other end clamped.

    Why the cut is a ``cut`` and not a ``fragment``
        A stiffened panel's boolean bonds two *bodies*, so ``fragment`` is what
        makes them share a boundary and it is right.  A hole removes material
        from one body: there is nothing to bond, and ``fragment`` would only add
        an interior edge for no gain.  ``occ.cut`` leaves the plate as a single
        face whose outer wire is the rectangle's four curves and whose inner
        wire is the hole - which is precisely the topology a shell mesh wants.

    Measured before it was relied on (``_t4_probe/geom_probe.py``)
        On the default coupon the cut leaves **1 face / 5 curves**, and the
        shipped mesh is **4924 quad4, 0 tri3**, with the hole edge resolved by
        exactly **24 nodes at a uniform 15 deg** - set by
        ``Mesh.MeshSizeFromCurvature``, not by this builder.  The hole is
        therefore refined by the same mechanism that refines a wing box's
        leading edge, and no family-specific meshing rule is needed.

    Boundary conditions are declared here, not inferred downstream
        The clamped end is ``x = 0`` and the loaded end ``x = length``, selected
        by :func:`feagpt.open_hole.end_nodes` from a node table, so the same
        rule can be re-applied to a result file by the cross-solver check.  The
        clamp is fully fixed (``clamp_dofs = (1, 6)``): a shell carries a
        drilling freedom and out-of-plane translations too, and leaving those
        free would give the coupon rigid-body modes in a linear static step.
    """
    p = open_hole.parse_params(spec)

    # The coupon's load is an end tension.  A pressure request would have no
    # ``pressure_group`` on this family and would silently apply *nothing* -
    # refuse instead of producing a model with no load in it, the rule
    # ``build_stiffened_panel`` already follows for the mirror-image mistake.
    kind = str(getattr(spec.load, "kind", ""))
    if kind != "tip_force":
        raise ValueError(
            f"open_hole_panel supports load.kind='tip_force' along the coupon "
            f"axis, got {kind!r}: the family carries no pressure group, and "
            f"silently applying zero load is worse than failing."
        )

    occ = gmsh.model.occ

    plate = occ.addRectangle(0.0, 0.0, 0.0, float(p.length), float(p.width))
    cx, cy = p.center()
    disc = occ.addDisk(cx, cy, 0.0, 0.5 * float(p.hole_d), 0.5 * float(p.hole_d))
    out, _out_map = occ.cut([(2, plate)], [(2, disc)])
    occ.synchronize()

    faces = [t for d, t in out if d == 2]
    surfaces = _assign_from_names([(t, "panel") for t in faces], OPEN_HOLE_GROUPS)

    notes = [
        f"cut a d={p.hole_d:g} mm hole at ({cx:g}, {cy:g}); the plate stayed in "
        f"{len(faces)} face(s) (a hole is a feature, not a second part)"
    ]

    # ---- declare the hole-edge resolution -------------------------------- #
    # The hole is the *feature* this family exists to measure, and its peak
    # stress lives in the gradient across the edge: measured at the default
    # far-field size the hole would carry ~13 elements where it needs tens.  The
    # resolution is therefore declared as the model's curvature target rather
    # than left to the mesher's default - and *declared*, not set per curve,
    # because the per-curve route is silently ignored on this toolchain
    # (measured: ``_t4_probe/setsize_lab.py``); see
    # :attr:`GeometryResult.curvature_target`.
    arc = open_hole.hole_edge_size(p)
    floor = open_hole.mesh_size_floor(spec)
    if arc <= floor:
        # The size field floors every generated size at ``size_chord / 6``, so a
        # far field that is too coarse silently coarsens the one feature the
        # family exists to resolve - and the run would still look fine.  Refuse,
        # the same way ``parse_params`` refuses a mis-spelled key.
        raise ValueError(
            f"{open_hole.FAMILY}: hole-edge target {arc:.4f} mm is at or below "
            f"the size field's own floor {floor:.4f} mm "
            f"(MeshSizeMin = size_chord/6 = {spec.mesh.size_chord:g}/6). The "
            f"edge would be meshed finer than nothing and coarser than the "
            f"verified rule - lower mesh.size_chord."
        )
    notes.append(
        f"hole edge resolution declared at {open_hole.HOLE_ARC_DIVISIONS} "
        f"elements per revolution "
        f"({360.0 / open_hole.HOLE_ARC_DIVISIONS:g} deg of arc = {arc:.4f} mm); "
        f"size-field floor {floor:.4f} mm leaves "
        f"{100.0 * (arc / floor - 1.0):.0f} % margin"
    )

    if step_path is not None:
        from pathlib import Path

        Path(step_path).parent.mkdir(parents=True, exist_ok=True)
        occ.synchronize()
        gmsh.write(str(step_path))

    area = _surface_area(gmsh, faces)
    xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(-1, -1)
    analytic = (float(p.length) * float(p.width)
                - math.pi * (0.5 * float(p.hole_d)) ** 2)
    notes.append(
        f"open-hole coupon {p.length:g} x {p.width:g} x {p.thickness:g} mm, "
        f"hole d={p.hole_d:g} mm (lambda={p.lambda_ratio:.3f}, "
        f"net width {p.net_width:g} mm); mid-surface area {area:.2f} mm^2 vs "
        f"analytic {analytic:.2f} (a coupon whose hole was not cut would read "
        f"{p.length * p.width:.2f})"
    )

    return GeometryResult(
        surfaces=surfaces,
        # span/chord are the wing box's vocabulary; kept for reporting only, as
        # on the panel.  This family declares bc_nodes, so nothing downstream
        # ever asks the coupon for its "span".
        span=float(p.width),
        chord=float(p.length),
        shell_area=float(area),
        bounding_box=(xmin, ymin, zmin, xmax, ymax, zmax),
        n_surfaces=len(gmsh.model.getEntities(2)),
        n_curves=len(gmsh.model.getEntities(1)),
        notes=notes,
        bc_groups={"clamp": "fixed_end", "load": "loaded_end"},
        bc_nodes=lambda nodes: {
            "fixed_end": open_hole.end_nodes(nodes, p, "fixed"),
            "loaded_end": open_hole.end_nodes(nodes, p, "loaded"),
        },
        shell_thickness={"panel": float(p.thickness)},
        clamp_dofs=(1, 6),
        # The family's own resolution rule for its defining feature; see the
        # note above and GeometryResult.curvature_target.
        curvature_target=float(open_hole.HOLE_ARC_DIVISIONS),
    )


# --------------------------------------------------------------------------- #
# T3 - fuselage barrel (M5 / task T3)
# --------------------------------------------------------------------------- #
def _cyl_patch(occ, r: float, L: float, th0: float, th1: float) -> int:
    """One non-periodic cylinder patch, sweeping the generatrix from ``th0`` to ``th1``.

    Why the skin is **always** built in patches
        Two separate reasons, both measured, and the second one was only found
        after the first had already put the patches in place.

        *The boolean.*  A single extruded circle is one closed (periodic) face,
        and a radial web crossing its interior is the asymmetric ``fragment`` the
        T3 probe measured - the ring stays whole while the stringer is cut, so the
        two never share an edge.  Splitting the skin at the stringer half-planes
        makes each patch boundary *be* a stringer web, so the bond is
        shared-edge by construction.

        *The mesh.*  A closed cylinder cannot be full-quad recombined at all, and
        under blossom its minimum scaled Jacobian is not a function of the size
        cap in any usable sense - measured on the stringer-free barrel
        (``_m5_probe/t3_cap_sweep.py``, 2026-10-05): 0.5033 / 0.2278 / 0.5109 /
        0.2954 at caps 10 / 12 / 12.5 / 15.  Segmenting it removes the closed
        surface and the same barrel then reads 0.4713 / 0.5818 / ... at caps
        10 / 12 (``_m5_probe/t3_seg_probe.py``), and the segments are shared edges
        (20 of 28 boundary curves are owned by two faces, the four skin seams
        among them) - so the pieces are bonded, not four floating shells.  That is
        why the family carries **no** periodic surface at all, stringer-free
        included.

        It does **not** make full-quad recombination available: measured on the
        shipped path, a stringered barrel still aborts with ``1D mesh cannot be
        divided by 2`` under full-quad.  The family is meshed with **blossom**
        (see :attr:`GeometryResult.blossom_only`).

        When there are stringers the patch boundaries land exactly on their
        half-planes, so the seams are covered and no extra geometry appears.  When
        there are none the seams are free edges - a boundary of the shell, shared
        between the two patches, which changes no physics.
    """
    p0 = occ.addPoint(r * math.cos(th0), r * math.sin(th0), 0.0)
    p1 = occ.addPoint(r * math.cos(th0), r * math.sin(th0), L)
    ln = occ.addLine(p0, p1)
    out = occ.revolve([(1, ln)], 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, th1 - th0)
    faces = [t for d, t in out if d == 2]
    if len(faces) != 1:
        raise RuntimeError(
            f"skin patch {th0:.4f}->{th1:.4f}: revolve gave {len(faces)} face(s), expected 1"
        )
    return faces[0]


def _radial_rect(occ, r_out: float, r_in: float, theta: float,
                 z0: float, z1: float) -> int:
    """A flat radial web: the rectangle in the half-plane at angle ``theta``.

    Its four corners are the combinations of (``r_out`` / ``r_in``) x (``z0`` /
    ``z1``) at one fixed ``theta``, so they are coplanar and the face is a plane.
    This is the barrel's analogue of a blade stringer, and it is why a stringer
    bonds to the skin along an exact generatrix rather than a re-interpolated
    approximation of one - the outer two corners *are* the patch's own boundary
    points, since the patch is a member of the same azimuth set.
    """
    ct, st = math.cos(theta), math.sin(theta)
    pts = [
        occ.addPoint(r_out * ct, r_out * st, z0),
        occ.addPoint(r_out * ct, r_out * st, z1),
        occ.addPoint(r_in * ct, r_in * st, z1),
        occ.addPoint(r_in * ct, r_in * st, z0),
    ]
    lines = [occ.addLine(pts[i], pts[(i + 1) % 4]) for i in range(4)]
    return occ.addPlaneSurface([occ.addCurveLoop(lines)])


def _annular_sector(occ, r_out: float, r_in: float, z: float,
                    th0: float, th1: float) -> int:
    """One annular sector: the frame web between two adjacent meridians.

    Why a frame is built as sectors rather than as one ring
        A ring frame crosses every stringer, and the crossing is in the *interior*
        of the ring - whereas the wing box's ribs meet their spars along the rib's
        own **boundary**, which is why a rib stays one face.  A face-crossing-face
        intersection in the interior is what ``occ.fragment`` does *not* split
        symmetrically: measured (``_m5_probe/t3_frag_probe.py``) the ring web
        stays whole while the stringer is cut in two, so the two never share an
        edge and the stringer is left floating through the frame.

        Building the sectors directly removes the dependency on that behaviour:
        each sector's radial edges lie exactly on the meridian half-planes the
        skin is already cut on, so the frame and the stringer - or, on a
        stringer-free barrel, the frame and the skin seam - share an edge **by
        construction**, not by a boolean's grace.
    """
    def pt(r: float, th: float) -> int:
        return occ.addPoint(r * math.cos(th), r * math.sin(th), z)

    centre = occ.addPoint(0.0, 0.0, z)
    po0, po1 = pt(r_out, th0), pt(r_out, th1)
    pi0, pi1 = pt(r_in, th0), pt(r_in, th1)
    arc_out = occ.addCircleArc(po0, centre, po1)
    arc_in = occ.addCircleArc(pi1, centre, pi0)
    rad0 = occ.addLine(po0, pi0)
    rad1 = occ.addLine(po1, pi1)
    return occ.addPlaneSurface([occ.addCurveLoop([arc_out, rad1, arc_in, rad0])])


def _frame_faces(occ, r_out: float, r_in: float, z: float,
                 meridians: tuple[float, ...]) -> list[int]:
    """The frame web at station ``z``: one sector per meridian gap.

    ``meridians`` is the family's azimuth set - the stringer angles when there
    are stringers, and the nominal skin partitions when there are not - so the
    sectors always land on the same planes the skin is cut on, stringer-free
    included.  There is deliberately no "one full ring" branch: a full ring
    would be a face the skin seams merely touch, which is exactly the
    boundary-vs-interior mismatch :func:`_annular_sector` exists to avoid.
    """
    n = len(meridians)
    if n < 2:
        raise RuntimeError(
            f"a frame needs at least 2 meridians to be cut into sectors, got {n}"
        )
    faces: list[int] = []
    for j in range(n):
        th0 = meridians[j]
        th1 = meridians[(j + 1) % n] + (2.0 * math.pi if j == n - 1 else 0.0)
        faces.append(_annular_sector(occ, r_out, r_in, z, th0, th1))
    return faces


_STRIP_SIZE_CAP = 0.4
"""Size ceiling as a fraction of the **narrowest** barrel strip's full width.

The same rule T5 established for a flange (``0.8 x half width`` = ``0.4 x`` the
strip) and T1 reused for a spar web, applied to the barrel's strips - the axial
stringer web (``h_str``) and the frame sector (``h_frm``).  It is a *measured*
choice, not a picked one: the family's minimum scaled Jacobian is a sharp and
non-monotonic function of the cap (with ``h_str = 25`` the stringered barrel is
clean at 10 and 12.5 and leaves 48 triangles at 15; the stringer-free barrel
needs the segmentation of :func:`_cyl_patch` before any cap is safe at all), and
``0.4`` is the constant that clears the widest measured set -
``_m5_probe/t3_cap_sweep.py``, ``t3_cap_rule.py`` and ``t3_seg_probe.py``,
2026-10-05.

Why the stringer-free barrel uses ``h_frm`` alone
    It builds no stringer web, so ``h_str`` must not enter the cap: reading it
    would let a *stringer* parameter move a model that contains no stringer,
    which is exactly what ``check_forms.check_T3``'s invariance half forbids.
"""


def build_fuselage_barrel(gmsh, spec: FEASpec, step_path=None) -> GeometryResult:
    """Create the circular fuselage barrel: skin + axial stringers + ring frames.

    Topology produced
        1. **skin** - the side of a circular cylinder, radius ``r``, length ``L``
           along ``z``, built as **non-periodic patches** on one meridian set:
           one per stringer when there are stringers, and
           :data:`feagpt.fuselage.MIN_SKIN_SEGMENTS` of them when there are none
           (see :func:`_cyl_patch` for why the family carries no closed surface).
           A *surface*, not a volume - no end caps.
        2. **stringers** - ``n`` radial webs at the circumferential angles
           :meth:`feagpt.fuselage.FuselageParams.stringer_angles`, running the
           full length and standing inward from the skin.
        3. **frames** - ``n_frames`` annular webs perpendicular to the axis at
           :meth:`feagpt.fuselage.FuselageParams.frame_z`, standing inward, each
           cut into one sector per meridian.

    Why the boolean is not optional
        Merely touching in space is not a bond.  Measured on the panel
        (``diagnostics/panel_bond_probe.py``): independent extrudes share **0
        nodes**, so a stiffener is a floating cantilever that a linear static
        solve still reports as fine.  Here each stringer and each frame meets the
        skin, and each stringer crosses each frame, so all of them go through
        ``occ.fragment`` together - which is also what produces the family's
        whole grouping semantics: the skin is cut into ``n_seg x (n_frames - 1)``
        patches, each stringer into ``n_frames - 1`` strips and each frame into
        ``n_seg`` sectors, where ``n_seg`` is the stringer count (or
        :data:`feagpt.fuselage.MIN_SKIN_SEGMENTS` when there are none).

    How the barrel is held and loaded
        Declared here, not inferred downstream: clamped at the ``z = 0`` frame
        (``bc_groups["clamp"]``), loaded at the ``z = L`` frame
        (``bc_groups["load"]``), with internal pressure on ``skin``.  The load
        *values* ride in ``spec.extra`` and are emitted by the deck writer; the
        geometry only says *where*.
    """
    p = fuselage.parse_params(spec)
    r = p.radius
    L = float(p.length)
    occ = gmsh.model.occ

    str_angles = p.stringer_angles()
    h_str = float(p.stringer_height)
    h_frm = float(p.frame_height)

    # One meridian set for the whole model.  The skin patches, the stringer webs
    # and the frame sectors are all derived from it, which is what makes every
    # junction a shared edge rather than a coincidence.  A stringer-free barrel
    # gets the nominal partitions instead of an empty set, so it is never left as
    # a single closed surface (see MIN_SKIN_SEGMENTS and _cyl_patch).
    angles = str_angles or tuple(
        2.0 * math.pi * j / fuselage.MIN_SKIN_SEGMENTS
        for j in range(fuselage.MIN_SKIN_SEGMENTS))
    n_seg = len(angles)

    # ---- 1. skin: one non-periodic patch per meridian gap ---------------- #
    skin_faces = [
        _cyl_patch(occ, r, L, angles[j],
                   angles[(j + 1) % n_seg] + (2.0 * math.pi if j == n_seg - 1 else 0.0))
        for j in range(n_seg)
    ]

    # ---- 2. longitudinal stringers: one radial web per station ----------- #
    str_faces = [_radial_rect(occ, r, r - h_str, th, 0.0, L) for th in str_angles]

    # ---- 3. ring frames: one sector per meridian gap, per station -------- #
    frm_faces: list[int] = []
    for z in p.frame_z():
        frm_faces.extend(_frame_faces(occ, r, r - h_frm, z, angles))

    occ.synchronize()

    # ---- 4. bond everything to everything -------------------------------- #
    # Longitudinal members are the objects and the ring frames the tools,
    # matching the wing box's ribs-vs-skins/spars/stringers split.  The skin
    # patches already share their seams with the stringers' feet (both sit on
    # the stringer half-planes) and the frame sectors already carry their radial
    # edges on those same planes, so the boolean only has to cut in the axial
    # direction - the one it does symmetrically.
    named_inputs: list[tuple[int, str]] = (
        [(t, "skin") for t in skin_faces]
        + [(t, "stringers") for t in str_faces]
        + [(t, "frames") for t in frm_faces]
    )
    objects = [(2, t) for t in skin_faces] + [(2, t) for t in str_faces]
    tools = [(2, t) for t in frm_faces]
    if tools:
        out_dimtags, out_map = occ.fragment(objects, tools)
        occ.synchronize()
        all_shell = [t for d, t in out_dimtags if d == 2]
        surfaces, tag_notes = _assign_from_map(
            all_shell, out_map, named_inputs, FUSELAGE_GROUPS)
    else:                                    # pragma: no cover - defensive
        surfaces = _assign_from_names(
            [(t, "skin") for t in skin_faces], FUSELAGE_GROUPS)
        tag_notes = ["no frames requested"]
        all_shell = list(skin_faces)

    occ.synchronize()

    if step_path is not None:
        from pathlib import Path

        Path(step_path).parent.mkdir(parents=True, exist_ok=True)
        occ.synchronize()
        gmsh.write(str(step_path))

    area = _surface_area(gmsh, all_shell)
    xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(-1, -1)
    return GeometryResult(
        surfaces=surfaces,
        # span/chord are the wing box's vocabulary; the barrel keeps them filled
        # for reporting only.  Its BC does not read them - it declares bc_nodes.
        span=L,
        chord=float(2.0 * r),
        shell_area=float(area),
        bounding_box=(xmin, ymin, zmin, xmax, ymax, zmax),
        n_surfaces=len(gmsh.model.getEntities(2)),
        n_curves=len(gmsh.model.getEntities(1)),
        notes=tag_notes + [
            f"fuselage barrel D{2 * r:g} x L{L:g} x t{p.thickness:g} mm, "
            f"{int(p.n_stringers)} stringer(s), {int(p.n_frames)} frame(s)"
        ],
        bc_groups={"clamp": "z0", "load": "zL"},
        bc_nodes=lambda nodes: {
            "z0": fuselage.barrel_nodes(nodes, p, p.frame_z()[0]),
            "zL": fuselage.barrel_nodes(nodes, p, p.frame_z()[-1]),
        },
        shell_thickness={"skin": float(p.thickness),
                         "stringers": float(p.stringer_thickness),
                         "frames": float(p.frame_thickness)},
        clamp_dofs=(1, 6),
        pressure_group="skin",
        # D21: ``occ.revolve`` gives the skin patch the *opposite* normal to an
        # extruded wing-box skin / a flat panel, so a positive ``load.magnitude``
        # must be written with a positive sign to be internal pressure.  Measured
        # defect this fixes: with the writer's old ``-abs(p)`` the barrel read
        # -0.22725 mm of radial growth against a +0.228 mm closed form.
        pressure_dload_sign=fuselage.PRESSURE_DLOAD_SIGN,
        # The barrel's strips are the axial stringer webs (``h_str`` wide) and
        # the frame sectors (``h_frm`` wide).  Blossom needs at least two
        # elements *across* a strip or it fills the leftover with triangles -
        # the same failure the wing box's T5 flange cap exists for - and here the
        # cliff is sharp and measured: with ``h_str = 25`` the mesh is clean at
        # cap 12.5 and leaves 48 triangles at 15.  So the cap is the narrower
        # strip's full width times T5's own ``0.4`` constant, and it holds across
        # eight barrels - the default, a denser 12/4, a 16-stringer, a five-frame
        # and a shallower-web shape, i.e. the region D18 will generate
        # (``_m5_probe/t3_cap_sweep.py`` and ``t3_cap_rule.py``, 2026-10-05).
        #
        # A stringer-free barrel has no stringer strip, so ``h_str`` must not
        # enter the cap: reading it would let a *stringer* parameter move a model
        # that contains no stringer, which is exactly what
        # ``check_forms.check_T3``'s invariance half forbids.
        mesh_size_cap=_STRIP_SIZE_CAP * (min(h_str, h_frm) if str_angles else h_frm),
        # Blossom, unconditionally.  A single extruded circle is periodic and
        # full-quad refuses it outright; the segmented patches are not periodic
        # but still defeat it ("1D mesh cannot be divided by 2" on the shipped
        # path for every cap).  See GeometryResult.blossom_only.
        blossom_only=True,
    )


# --------------------------------------------------------------------------- #
# structure-family registry (M2)
# --------------------------------------------------------------------------- #
BUILDERS = {
    "wingbox": build_wingbox,
    "stiffened_panel": build_stiffened_panel,
    "fuselage_barrel": build_fuselage_barrel,
    "open_hole_panel": build_open_hole_panel,
}
"""Structure family -> builder.

A builder takes ``(gmsh, spec, step_path)`` and returns a
:class:`GeometryResult`.  That is the *entire* contract, and it is what lets a
new family be added without touching meshing / the deck writer / the
post-processor: they only ever see the logical group names and the bounding box.
"""


def build(gmsh, spec: FEASpec, step_path=None) -> GeometryResult:
    """Dispatch to the builder for ``spec.structure.family``.

    Unknown families raise instead of falling back to a default: silently
    building a wing box for a request that asked for a stiffened panel is
    precisely the class of error (runs fine, is wrong) the semantic gate exists
    to prevent.
    """
    family = str(getattr(getattr(spec, "structure", None), "family", "") or "wingbox")
    try:
        builder = BUILDERS[family]
    except KeyError:
        raise ValueError(
            f"unknown structure family {family!r}; registered: {sorted(BUILDERS)}"
        ) from None
    return builder(gmsh, spec, step_path)


def clamp_nodes(spec: FEASpec, nodes: dict) -> list[int]:
    """The clamped node set for a spec, from a node table alone.

    The counterpart of :meth:`GeometryResult.resolve_bc_nodes` for callers that
    hold a *result file* rather than a build - the cross-solver equilibrium check
    in ``verify_solvers.py``.  It lives here, next to the builders, so the rule
    is written once per family: a stiffened panel is supported on its four edges
    (:func:`feagpt.panel.edge_nodes`), a wing box clamps its root rib.

    Note what this replaces.  ``abs(z) < 1e-6`` is a *wing-box* statement - its
    root rib is the z = 0 plane - but it reads like a general rule, and applied
    to a flat panel it selects the entire skin, because the whole plate sits at
    z = 0.  An equilibrium check built on it would silently average reactions
    over free nodes.
    """
    family = str(getattr(getattr(spec, "structure", None), "family", "") or "wingbox")
    if family == panel.FAMILY:
        return panel.clamp_nodes(spec, nodes)
    if family == fuselage.FAMILY:
        return fuselage.clamp_nodes(spec, nodes)
    if family == open_hole.FAMILY:
        return open_hole.clamp_nodes(spec, nodes)
    return [t for t, (_x, _y, z) in nodes.items() if abs(z) < 1e-6]


def _classify_faces(gmsh, face_tags, x_front, x_rear, tol=1e-6, stringer_stations=(),
                    web_stations=()):
    """Assign every shell face to a logical group from its bounding box.

    After ``fragment`` we no longer know which input produced which output, so
    the faces are identified geometrically:

    * no spanwise extent (``dz ~ 0``)            -> a rib
    * no chordwise extent (``dx ~ 0``)           -> a *vertical* web: an
      intermediate **web** (at a web station), a **spar** (at a spar station)
      or a **stringer** (at a stringer station)
    * otherwise                                  -> upper / lower skin

    The troublesome case is the second one: a blade stringer is also a plane
    ``x = const``, so the original rule ("``dx ~ 0`` means spar") silently files
    every stringer as a spar.  The two are told apart by chordwise position -
    stringer stations were chosen strictly between the spars, so the sets cannot
    overlap.

    Which skin a stringer belongs to is decided against the **box mid-height**,
    not against ``y = 0``: NACA4412 is cambered, so on the lower skin at 0.59c
    the surface sits at ``y = -10.3 mm`` and a 20 mm stringer reaches
    ``y = +9.7 mm`` - its centre is *above* y = 0 while it is unambiguously a
    lower-skin stringer.  Comparing with the local mid-height has no such
    ambiguity.

    ``stringer_stations``
        ``[(x_mm, box_mid_y_mm), ...]`` for the expected stringers.
    """
    groups: dict[str, list[int]] = {
        k: [] for k in ("upper_skin", "lower_skin", "front_spar", "rear_spar",
                        "webs", "ribs", "stringers_upper", "stringers_lower",
                        "root", "tip")
    }
    stations = sorted((float(x), float(m)) for x, m in stringer_stations)
    # An intermediate web is the third kind of plane ``x = const`` and is told
    # apart the same way a stringer is - by chordwise position.  It lives in its
    # own group rather than being filed as the nearer spar, because the spar
    # count is what gate 4 predicts (``n_spars * n_bays``) and folding webs in
    # would inflate it.  The stations are exact control points of the skin
    # splines, so 1e-3 mm is six orders above the residual.
    webs = sorted(float(w) for w in web_stations)
    web_tol = 1e-3
    # A stringer is accepted when its face centre sits within this distance of a
    # station.  Bounded by the closest spar so a mis-generated face can never be
    # mistaken for one; the stations are exact control points, so in practice
    # the residual is ~1e-9.
    if stations:
        gap = min(min(abs(x - x_front), abs(x - x_rear)) for x, _ in stations)
        guard = max(0.05, min(0.4 * gap, 20.0))
    else:
        guard = 0.0

    for t in face_tags:
        xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(2, t)
        dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
        xc = 0.5 * (xmin + xmax)
        if dz <= tol:
            groups["ribs"].append(t)
        elif dx <= tol:
            if webs and min(abs(xc - w) for w in webs) <= web_tol:
                groups["webs"].append(t)
                continue
            hit = None
            for xs, mid in stations:
                if abs(xc - xs) <= guard:
                    hit = mid
                    break
            if hit is not None:
                ymid = 0.5 * (ymin + ymax)
                key = "stringers_upper" if ymid >= hit else "stringers_lower"
                groups[key].append(t)
            else:
                key = "front_spar" if abs(xc - x_front) <= abs(xc - x_rear) else "rear_spar"
                groups[key].append(t)
        else:
            key = "upper_skin" if 0.5 * (ymin + ymax) >= 0.0 else "lower_skin"
            groups[key].append(t)
    return groups


def _tag_root_tip(gmsh, surfaces, span):
    """Split rib faces into the root station (z~0) and the rest."""
    roots, ribs = [], []
    for t in surfaces["ribs"]:
        zmin, zmax = gmsh.model.getBoundingBox(2, t)[2], gmsh.model.getBoundingBox(2, t)[5]
        if abs((zmin + zmax) / 2.0) < 1e-6:
            roots.append(t)
        else:
            ribs.append(t)
    surfaces["root"] = roots
    surfaces["ribs"] = ribs
    return surfaces
