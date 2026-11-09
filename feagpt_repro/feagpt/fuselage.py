"""The fuselage-barrel family - its parameter block, its station layout and its
support rule (M5 / task T3).

What a "fuselage barrel" is here
--------------------------------
A thin-walled **circular cylinder** of diameter ``diameter`` and length
``length``, axis along ``z``, carrying

* ``n_stringers`` longitudinal (axial) blade stringers, evenly spaced around the
  circumference - each a radial web standing inward from the skin, running the
  full length;
* ``n_frames`` ring frames **including both ends**, each a flat annular web
  perpendicular to the axis at ``z = frame_z()``.

It is the third structural *family* of the dataset and, like the stiffened
panel, keeps its parameters in ``StructureSpec.params`` (the wing box still uses
the legacy ``airfoil`` block).

Why a separate module
---------------------
Same reason as :mod:`feagpt.panel`.  Three things have to agree about a barrel,
and they sit at different stages:

* the **parameter block** - read by the geometry builder;
* the **station layout** - the circumferential stringer angles and the axial
  frame positions, which gate 4 predicts and the geometry observation measures;
* the **support rule** - which nodes are on the two end frames, which the deck
  writer needs and which the cross-solver equilibrium check needs *again*, from
  a result file with no geometry in hand.

Keeping them in one module is what stops the builder and the gate from each
having their own opinion about where a frame is.

Parameters are refused, not defaulted
-------------------------------------
``parse_params`` raises on an unrecognised key, exactly as the panel's does: a
mis-spelled parameter would otherwise be silently ignored and the model would
quietly be a different one - the "runs fine, is wrong" failure gate 4 exists to
catch, and cheaper to catch here.

The stringer-count envelope, and why it is a *refusal* (D19, 2026-10-05)
-----------------------------------------------------------------------
This family does **not** mesh clean over every stringer count, and the gap is not
a tuning problem - it is measured, reproducible, and geometric:

* clean: ``n_stringers == 0`` (the plain shell, partitioned on
  :data:`MIN_SKIN_SEGMENTS`) and ``n_stringers >= 5``;
* not clean: **1 to 4 stringers**, which always leave a handful of triangles.

Measured at the family defaults (D2000 / L2000, 25x2.5 blade, 30x3 frame, size
25 mm, blossom, ``cap = 0.4 * min(h_str, h_frm)``): 3str/2frm -> 20 tri3,
4str/2frm -> 16, 4str/3frm -> 22, while 5str/2frm, 6str/2frm, 8str/3frm and
12str/4frm all read exactly 0.  Every triangle sits on the **frames**, on the
outer arc at ``r ~ R`` - the bond line between a frame sector and the skin patch.

The cause is a corner sliver.  A stringer web cuts the frame sector's radial edge
at ``r = R - h_str``, leaving a ``h_frm - h_str`` strip; at the declared cap that
is ``5 / 10 = half an element``, which cannot be quad-filled.  It is *not* only
the sliver: 8str/3frm carries the same half-element sliver and is still clean, so
the trigger is the combination of a **90 deg / 120 deg sector with the
half-element sliver**.  Sectors of 45 / 60 deg absorb it, which is why the whole
``>= 5`` range is clean.

Five repairs were built and measured; all were refused, so the envelope stands as
a property of the family rather than a defect to be papered over:

1. simple recombination (``RecombinationAlgorithm = 0``) - catastrophic
   (42 084 tri3 at 4str/2frm, 44 438 at 8str/3frm, skin included);
2. refining the **frame** meridians only - worse (16 -> 1 806);
3. refining **skin and frame together** - worst (16 -> 2 404), and it breaks a
   formerly-clean 5str/2frm (0 -> 2 332): a *bare* seam coexisting with stringer
   webs always goes bad, so the plain shell's clean seams do not extrapolate;
4. **a size field on the frames alone** - does not repair, it *moves* the
   triangles onto the stringers, and breaks the default specimen (8str/3frm
   0 -> 18); clean only at a couple of lucky field values (a coin toss);
5. **a per-face 2-D algorithm on the frames** - the quasi-structured-quad
   algorithm turns the default specimen's 0 into 96, and with recombination off
   the 4str/2frm count explodes to 307 594.

Every number, and the five command lines that recompute them, are in
``_m5_probe/t3_mesh_envelope.md``.

So :func:`_validate` **refuses** ``0 < n_stringers < 5`` outright - the same
posture the panel takes on a spec it cannot build correctly ("rather no model
than a wrong one").  The cost is bounded: the dataset's val members sit at 10 /
12 / 16 stringers and its train members at 5-8, so nothing planned is lost.  This
refusal is a property of the *builder*, not of the data format: it does not
touch ``spec_sha256`` and it does not perturb the cases already on disk.

The stringer *section*, and why the family ships blade only (D22, 2026-10-05)
------------------------------------------------------------------------------
The wing box and the panel both build flanged stringers: their builders call
:func:`feagpt.sections.section` and bond the strips with ``occ.fragment``
(:func:`feagpt.geometry._tag_stringer_faces`).  The barrel's does **not**.  It
emits one flat radial web per stringer by construction
(:func:`feagpt.geometry._radial_rect`) and never reads ``stringer_kind``, so the
kind was accepted, validated for *registration*, published as
``n_faces_per_stringer_section`` by ``topology._design_fuselage`` and **demanded**
by ``topology._expect_fuselage`` - a four-way claim with no implementation behind
it.

Measured (``_m5_probe/t3_tsection_probe.py``, 8 stringers / 3 frames / 25 mm):
the T-section barrel (flange 30 mm) and the blade barrel are **bit-identical** -
158 548 nodes, 157 972 elements, minJ 0.5159, the same 16 / 16 / 24 group counts
- while gate 4 required 48 stringer faces and observed 16.  So the failure was
never silent (gate 4 is section-aware, and that is exactly the M3 change that
made it so), but the capability was advertised in four places and existed in
none.

Refused now, by the D19 precedent: :func:`_validate` rejects any
``stringer_kind`` other than ``"blade"``, and ``check_forms.check_T3``'s
``section-kind-envelope`` half proves the refusal is live for every section the
registry knows about.  Two consequences worth stating out loud:

* ``KNOWN_KEYS`` still lists ``stringer_kind`` / ``stringer_flange_width`` - an
  explicit ``"blade"`` is legal, and a spec that spells out the default must
  keep parsing;
* ``manifest._fuselage_new_form`` ("a section form train has not anchored ->
  test") stays as a **declaration with no data**, which D15 already established
  is not dead code - it is the statement of a rule.  It simply cannot be
  satisfied until a builder exists, so the barrel family's first held-out case
  comes from :func:`manifest._fuselage_double_extrapolation` instead.
"""

from __future__ import annotations

import math

from dataclasses import asdict, dataclass

from . import sections

FAMILY = "fuselage_barrel"

#: Every key ``structure.params`` may carry for this family.
KNOWN_KEYS = (
    "diameter",
    "length",
    "thickness",
    "n_stringers",
    "stringer_height",
    "stringer_thickness",
    "stringer_kind",
    "stringer_flange_width",
    "n_frames",
    "frame_height",
    "frame_thickness",
)

#: Absolute mm.  A frame is a flat annulus at a single ``z``, so every node on
#: it shares that ``z`` to OCC's own precision; 1e-3 mm separates "on the frame"
#: from "one element away" with three orders to spare while sitting five above
#: the coordinate noise (same constant the panel uses, for the same reason).
FRAME_TOL = 1e-3

#: Mesh size (mm) the barrel is built at.  Sized from the circumference rather
#: than the wing box's chord: at 25 mm a 2000 mm barrel gets ~250 elements around
#: and ~80 along, which resolves the frame boundary layers without turning the
#: 2 m specimen into a million-node model.
DEFAULT_MESH_SIZE = 25.0

#: Nominal meridian count for a **stringer-free** barrel's skin.
#:
#: A stringered barrel is cut into one patch per stringer and the webs cover the
#: seams.  A stringer-free barrel has nothing to partition it, and leaving it as
#: one closed cylinder made its mesh quality a coin toss - measured minimum
#: scaled Jacobian 0.5033 / 0.2278 / 0.5109 / 0.2954 at caps 10 / 12 / 12.5 / 15
#: (``_m5_probe/t3_cap_sweep.py``, 2026-10-05).  So it is partitioned on this many
#: meridians instead: no closed surface survives in the family, and the same
#: barrel then reads 0.4713 / 0.5818 at caps 10 / 12 (``t3_seg_probe.py``), with
#: the seams bonded - the four skin seams are edges *shared* by two faces, not two
#: coincident ones (20 of 28 boundary curves are owned by two faces).
#:
#: It is a **meshing** partition, not a structural parameter: no stringer is
#: built on it and no stringer parameter may influence it - the stringer-free
#: model must be invariant to all of them (``check_forms.check_T3``).
#:
#: It lives in the family module rather than the builder because two stages have
#: to agree on it: the builder makes the patched skin, and
#: ``topology._expect_fuselage`` predicts how many faces that produces.  One
#: number, in one place, or they drift.
MIN_SKIN_SEGMENTS = 4

#: Fewest stringers the family can mesh clean (D19, 2026-10-05).
#:
#: Below this - i.e. 1 to 4 stringers - the frame sectors are 90 deg or 120 deg
#: wide and a stringer web leaves a half-element sliver on each frame's radial
#: edge, which cannot be quad-filled; the result is a handful of triangles on the
#: frame arcs (20 / 16 / 22 at 3str/2frm, 4str/2frm, 4str/3frm).  Five repairs
#: were built and measured and all were refused; the whole ``>= 5`` range is
#: clean.  Zero stringers is separately clean and is the degeneration target.
#: See the module docstring and ``_m5_probe/t3_mesh_envelope.md``.
MIN_STRINGERS = 5

#: Sign convention for the ``*DLOAD`` pressure on the **skin** (D21, 2026-10-05).
#:
#: ``*DLOAD ... P, <p>`` is a *signed* pressure along the shell normal, so the
#: physical meaning of a given number depends on which way each surface's normal
#: happens to point - and that is a property of how the surface was built, not of
#: the load.  Measured on the shipped path: the wing box's extruded skins and the
#: panel's ``addRectangle`` carry the normal the ``P, -p`` convention assumes, but
#: the barrel's skin - built by ``occ.revolve`` (:func:`feagpt.geometry._cyl_patch`)
#: - carries the opposite one.  With the writer's old hard-coded ``-abs(p)`` the
#: barrel came out pressurised from **outside**: ``verify_barrel.py`` read a
#: mid-surface radial growth of **-0.22725 mm** where the thin-wall closed form
#: ``p R^2 / (E t)`` says **+0.228 mm**, and every sampled mid-surface meridian
#: agreed in sign, so it was not a local artefact.
#:
#: ``+1.0`` therefore means "a positive ``magnitude`` must be written with a
#: positive sign to be an *internal* pressure".  It is declared here, next to the
#: pressure it describes, and read by
#: :attr:`feagpt.geometry.GeometryResult.pressure_dload_sign` - the writer keeps
#: no opinion of its own (``check_forms.check_T3`` proves it obeys).
PRESSURE_DLOAD_SIGN = 1.0

#: Internal pressure (MPa).  A real cabin differential is ~0.06 MPa; 0.05 is the
#: same order while keeping the membrane response small-deformation.  On the
#: default 2000 mm barrel at t = 3 mm the hoop stress is ``pR/t = 16.7 MPa`` and
#: the free radial growth ``pR^2/(Et) = 0.228 mm`` - both well inside the linear
#: regime this chain assumes.  The value is *declared*, not tuned to make a
#: number come out; the closed forms it is checked against are in
#: ``verify_barrel.py``.
DEFAULT_PRESSURE = 0.05

#: Default end loads for the combined T3 load case (see ``spec.extra``).
#:
#: Sized so each of the three components makes a comparable contribution rather
#: than letting pressure swamp the others - the point of a *combined* case is
#: that all three are exercised, and a secondary load two orders below the first
#: would pass every cross-solver check even if it were miswired.  On the default
#: barrel (R = 1000, t = 3, 8 blade stringers 25 x 2.5):
#:
#: * pressure 0.05 MPa -> hoop membrane 16.7 MPa (the anchor);
#: * shear 50 kN -> mean shear ``V / (pi R t)`` = 5.3 MPa;
#: * moment 50 kN.m -> outer-fibre bending ``M R / I`` = 5.2 MPa, with
#:   ``I = pi R^3 t + (n/2) A_s R_s^2`` = 9.67e9 mm^4.
#:
#: The magnitudes are of the order a transport fuselage section sees, and they
#: are declared rather than tuned: nothing here is chosen to make a number come
#: out, and the closed forms above are what ``verify_barrel.py`` checks the
#: solved field against.
DEFAULT_END_SHEAR = 5.0e4         # N, transverse, along +x at the free end
DEFAULT_END_MOMENT = 5.0e7        # N.mm, bending about +y at the free end


@dataclass(frozen=True)
class FuselageParams:
    """The barrel's parameter block, with the defaults a "typical" barrel uses.

    2000 mm diameter is the usual single-aisle cabin size and 2000 mm length
    (L/D = 1) makes a stubby, well-conditioned segment; 8 stringers at 45 deg
    and 3 frames (both ends plus one mid) is the sparsest layout that still has
    a mid frame to split the skin.  All declared, none tuned to a result.
    """

    diameter: float = 2000.0          # mm, mid-surface
    length: float = 2000.0            # mm, along z
    thickness: float = 3.0            # mm, skin
    n_stringers: int = 8              # axial blade webs, evenly around
    stringer_height: float = 25.0     # mm, stands inward
    stringer_thickness: float = 2.5   # mm
    stringer_kind: str = "blade"      # see feagpt.sections; **blade only** (D22)
    stringer_flange_width: float = 30.0
    n_frames: int = 3                 # including both ends
    frame_height: float = 30.0        # mm, annular web depth (radial)
    frame_thickness: float = 3.0      # mm

    # ------------------------------------------------------------------ #
    @property
    def radius(self) -> float:
        """Mid-surface radius (mm)."""
        return 0.5 * float(self.diameter)

    def stringer_angles(self) -> tuple[float, ...]:
        """Circumferential angles (rad) of the stringers, evenly spaced.

        ``n`` stringers divide the circle into ``n`` equal arcs, so stringer
        ``j`` sits at ``2*pi*j/n``.  Derived rather than declared: one parameter
        (``n_stringers``) is harder to leave inconsistent than two, and the
        derived value is what gate 4 checks the built geometry against.
        """
        n = int(self.n_stringers)
        if n <= 0:
            return ()
        step = 2.0 * math.pi / n
        return tuple(j * step for j in range(n))

    def frame_z(self) -> tuple[float, ...]:
        """Axial stations (mm) of the ring frames, **both ends included**.

        ``n`` frames divide the length into ``n - 1`` equal bays, so frame ``j``
        sits at ``length * j / (n - 1)``.  With the default 3 that is
        ``0 / 1000 / 2000`` - the two end frames plus one mid frame, which is the
        minimum layout with a frame that actually cuts the skin.  ``n = 2``
        (both ends only) is the degenerate barrel the closed-form check uses.
        """
        n = int(self.n_frames)
        if n == 0:
            # Frame-less (anchor) barrel: the two END stations are the physical
            # ends, not a single degenerate station.  Returning (0.0,) here made
            # the zL end-node set silently alias to z=0 in the builder's
            # bc_nodes callback - the anchor shell is the first n_frames=0 case
            # (2026-11-09, U3a), caught by reading the callback, not by running.
            return (0.0, float(self.length))
        if n == 1:
            return (0.0,)
        step = float(self.length) / (n - 1)
        return tuple(j * step for j in range(n))

    def bay_count(self) -> int:
        """Spanwise bays between frames; 0 for a frame-less (degenerate) barrel."""
        return max(int(self.n_frames) - 1, 0)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["radius"] = self.radius
        d["stringer_angles"] = [round(v, 9) for v in self.stringer_angles()]
        d["frame_z"] = [round(v, 6) for v in self.frame_z()]
        return d


def parse_params(spec) -> FuselageParams:
    """Read ``spec.structure.params`` into a validated :class:`FuselageParams`."""
    raw = dict(getattr(getattr(spec, "structure", None), "params", None) or {})
    unknown = sorted(set(raw) - set(KNOWN_KEYS))
    if unknown:
        raise ValueError(
            f"{FAMILY}: unknown parameter(s) {unknown}; understood: "
            f"{sorted(KNOWN_KEYS)}. Refusing to ignore them - a mis-spelled key "
            f"would silently build a different barrel."
        )
    p = FuselageParams(**{k: raw[k] for k in raw})
    # A frame-less barrel (n_frames = 0) is legal ONLY for the U3a anchor
    # diagnostic (2026-11-09).  For every normal/dataset spec it stays ILLEGAL
    # - the B2 refuse-rule table asserts exactly that (rule [fus_nfrm]
    # outside {'n_frames': 0} must raise), and widening the generator's
    # boundary flipped that negative control to red (measured: NC-75 T0).
    _validate(p, allow_frame_less=bool((getattr(spec, "extra", None) or {})
                                       .get("bc_kind")))
    return p


def _validate(p: FuselageParams, allow_frame_less: bool = False) -> None:
    for name in ("diameter", "length", "thickness",
                 "stringer_height", "stringer_thickness",
                 "frame_height", "frame_thickness"):
        v = float(getattr(p, name))
        if v <= 0.0:
            raise ValueError(f"{FAMILY}: {name} must be > 0, got {v}")
    n = int(p.n_stringers)
    if n < 0:
        raise ValueError(f"{FAMILY}: n_stringers must be >= 0, got {n}")
    nf = int(p.n_frames)
    # n_frames == 0 is the frame-less PLAIN shell: the U3a anchor case (2026-
    # 11-09) is the first legitimate user - the von Mises / DTMB formulas
    # assume an UNSTIFFENED cylinder, so the anchor must not carry frames or
    # stringers.  n_frames == 1 is still refused: one frame mid-span without
    # end frames has no coherent support story and no analytic counterpart.
    if nf < 2 and not (nf == 0 and allow_frame_less):
        raise ValueError(
            f"{FAMILY}: n_frames must be >= 2 (both ends are frames); got {nf}. "
            f"n_frames = 0 (frame-less plain shell) is accepted ONLY for the "
            f"U3a anchor diagnostic, which declares extra.bc_kind."
        )
    # D19 (2026-10-05): the stringer count is not free below five.  Measured at
    # the family defaults, 1-4 stringers always leave triangles (20 / 16 / 22 at
    # 3str/2frm, 4str/2frm, 4str/3frm) on the frame arcs, and five independent
    # repairs were built and refused - see the module docstring and
    # _m5_probe/t3_mesh_envelope.md.  Refused here rather than built wrong, the
    # same posture the panel takes on a spec it cannot build correctly.  Zero is
    # always allowed: the plain shell is the degeneration target.
    if 0 < n < MIN_STRINGERS:
        raise ValueError(
            f"{FAMILY}: n_stringers in 1..{MIN_STRINGERS - 1} is outside the "
            f"family's clean-mesh envelope (n_stringers = 0 or >= "
            f"{MIN_STRINGERS}); got {n}. Refusing to build a barrel whose frame "
            f"arcs would carry triangles - see the module docstring, D19."
        )
    r = p.radius
    # A web deeper than the radius would cross the axis - almost certainly a
    # unit or axis mistake, and it would still mesh.
    if float(p.stringer_height) >= r:
        raise ValueError(
            f"{FAMILY}: stringer_height {p.stringer_height} >= radius {r} - "
            f"check the units"
        )
    if float(p.frame_height) >= r:
        raise ValueError(
            f"{FAMILY}: frame_height {p.frame_height} >= radius {r} - "
            f"check the units"
        )
    # The section kind has to be registered, and the flange width matters: a
    # flanged section with flange_width <= 0 degenerates to a blade (see
    # feagpt.sections), so this also rejects a section the deck could not use.
    #
    # D22 (2026-10-05): the barrel ships **blade stringers only**, and unlike the
    # wing box and the panel that is a builder limitation, not a policy.  The
    # check above only proves the kind is *registered*; the builder
    # (``geometry.build_fuselage_barrel``) never reads it and emits one flat
    # ``_radial_rect`` per stringer.  Measured consequence of leaving that
    # unguarded: a T-section spec and the blade spec built **bit-identical
    # models** (158 548 nodes / 157 972 elements / minJ 0.5159 / same 16 / 16 /
    # 24 group counts) while ``topology._expect_fuselage`` demanded
    # ``n_faces_per_section = 3`` - gate 4 failed (expected 48 stringer faces,
    # observed 16), so the mismatch was never silent, but three separate places
    # (``KNOWN_KEYS``, this validator, ``_design_fuselage``) advertised a
    # capability that did not exist.  Refused here, per D19's precedent, until a
    # builder implements it.  Zero disturbance: no shipped case uses a non-blade
    # barrel, and this touches neither the spec format nor any hash.
    if str(p.stringer_kind) != "blade":
        raise ValueError(
            f"{FAMILY}: stringer_kind {p.stringer_kind!r} is not implemented by "
            f"the barrel builder - it emits one flat radial web per stringer "
            f"(a blade) and never reads the kind, so this spec would silently "
            f"build the blade model. Only 'blade' is accepted (D22, "
            f"2026-10-05); see _m5_probe/t3_tsection_probe.py for the "
            f"measurement."
        )
    sections.faces_per_section(p.stringer_kind, p.stringer_flange_width)


def make_spec(name: str, size: float | None = None, pressure: float | None = None,
              end_shear: float | None = None, end_moment: float | None = None,
              workdir: str = "outputs_fuselage", **params):
    """A ready-to-run fuselage-barrel :class:`~feagpt.spec.FEASpec`.

    One factory, so the verification line, the degeneration check and the
    parameter sweep all build *the same* barrel from one set of declared
    defaults - the alternative is each caller keeping its own copy of
    "2000 x 2000, 8 stringers, 3 frames", which is how a sweep comes to compare
    models that were never the same model.

    The **end loads** go into ``spec.extra`` rather than into the dataclass
    schema on purpose.  ``spec.to_dict()`` is the input to ``spec_sha256``, so
    adding a dataclass field would invalidate every archived case's hash and
    force a re-export of the whole dataset.  ``extra`` is an existing field, so
    a barrel's loads ride along without touching the twenty-three cases already
    on disk.

    ``params`` are :data:`KNOWN_KEYS` names and are the only supported geometry
    overrides - anything else raises, for the same reason
    :func:`parse_params` raises.
    """
    from .spec import FEASpec

    unknown = sorted(set(params) - set(KNOWN_KEYS))
    if unknown:
        raise ValueError(
            f"{FAMILY}.make_spec: unknown parameter(s) {unknown}; understood: "
            f"{sorted(KNOWN_KEYS)}"
        )

    spec = FEASpec()
    spec.name = name
    spec.description = (
        f"Fuselage barrel D{params.get('diameter', FuselageParams.diameter):g} x "
        f"L{params.get('length', FuselageParams.length):g} mm, "
        f"{params.get('n_stringers', FuselageParams.n_stringers)} stringer(s), "
        f"{params.get('n_frames', FuselageParams.n_frames)} frame(s)"
    )
    spec.structure.family = FAMILY
    block = {
        "diameter": FuselageParams.diameter,
        "length": FuselageParams.length,
        "thickness": FuselageParams.thickness,
        "n_stringers": FuselageParams.n_stringers,
        "n_frames": FuselageParams.n_frames,
    }
    block.update(params)
    spec.structure.params = block

    mesh_size = DEFAULT_MESH_SIZE if size is None else float(size)
    spec.mesh.size_chord = mesh_size
    spec.mesh.size_span = mesh_size
    # No leading edge to refine on a smooth cylinder.
    spec.mesh.refine_at_leading_edge = False

    spec.load.kind = "pressure"
    spec.load.magnitude = DEFAULT_PRESSURE if pressure is None else float(pressure)
    spec.load.direction = (0.0, 0.0, 1.0)   # unused by *DLOAD; kept explicit
    spec.bc.clamp = True
    spec.workdir = workdir

    # Combined T3 load case: internal pressure (above, on the skin) plus a
    # transverse shear and a bending moment at the free end.  Kept in ``extra``
    # so the deck writer can emit them without a schema change.
    spec.extra = {
        "end_shear": DEFAULT_END_SHEAR if end_shear is None else float(end_shear),
        "end_moment": DEFAULT_END_MOMENT if end_moment is None else float(end_moment),
        "shear_axis": [1.0, 0.0, 0.0],
        "moment_axis": [0.0, 1.0, 0.0],
    }
    return spec


def barrel_nodes(nodes: dict, params: FuselageParams, z: float,
                 tol: float = FRAME_TOL) -> list[int]:
    """Tags of the nodes on the ring frame at axial station ``z``.

    The support is *declared*, not inferred: a barrel is held at its two **end
    frames**, so the held set is every node whose ``z`` equals an end station.
    A frame is a flat annulus at one ``z``, and the skin it bonds to shares
    exactly those nodes after the boolean (measured, not assumed - the
    ``model`` half of ``check_forms.check_T3``), so this single rule selects both
    the ring web and the skin ring it carries.

    Like the panel's :func:`feagpt.panel.edge_nodes` it takes a **node table**,
    not a Gmsh session, so the cross-solver equilibrium check can re-apply the
    same rule to a result file with no geometry in hand.
    """
    z = float(z)
    return [t for t, (_x, _y, zc) in nodes.items() if abs(float(zc) - z) < tol]


def clamp_nodes(spec, nodes: dict) -> list[int]:
    """The barrel's clamp set for a spec - the family's own rule, from a node table.

    The clamped end is the ``z = 0`` frame (the free end carries the loads), so
    this is the root end of the cantilever the T3 load case describes.
    """
    p = parse_params(spec)
    return barrel_nodes(nodes, p, p.frame_z()[0])
