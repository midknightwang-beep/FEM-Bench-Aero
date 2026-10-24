#!/usr/bin/env python
"""Degeneration self-checks - one per structure form (M3).

Why every new form must carry one
---------------------------------
A new structure form is code that can *build*, *mesh* and *solve* a model that
is nevertheless **not the form the spec asked for**.  Gate 4 catches a wrong
*count*; the numerical gates catch a wrong *number*; neither catches a form
whose parameters were silently ignored, because a form with its new parameter
at a neutral value is supposed to look like the old form.

The cheapest trustworthy defence is to make that expectation executable.  Every
form declares a **degeneration**: the parameter values at which it must collapse
onto a form that is already trusted, and this tool requires the built model to
be - face for face - the old one.  A new parameter that is quietly unwired
fails here immediately, at a neutral value, instead of at M5 when someone
notices the sweep produced identical results.

What "face for face" means
--------------------------
Deliberately *not* a face count.  Counts agree while faces move.  The
fingerprint is the one ``regress_groups.py`` established: per logical group, the
sorted ``(xmin,ymin,zmin,xmax,ymax,zmax)`` box of every face, rounded to 6 dp.
It is tag-independent (gmsh renumbers after a boolean, tags are not stable) and
it moves if a single face in a group moves.  Mesh size / element count / minJ
ride along as a cross-check.

Registered checks
-----------------
``T1``  swept / tapered wing box.  Degeneration: ``sweep_deg = 0`` **and**
        ``tip_chord_ratio = 1`` must reproduce the shipped prismatic box exactly
        (the builder routes that request to the M1 extrusion path).  Because a
        neutral request never reads the planform parameters, the check adds a
        **wiring** half: a swept and a tapered model are built and the measured
        tip rib is compared with the closed form of the D14 convention.  See
        :func:`check_T1`.  Its ``role-and-split`` / ``D16-val-regions`` halves
        additionally pin the *dataset* consequences of the knobs (D15 / D16 and,
        for the both-knobs case, **D35**: single-knob inside the envelope ->
        train, beyond it -> val; both knobs inside the envelope -> train, at
        least one beyond -> test; a plain panel at an unseen size -> val).

``T5``  flanged stringer section.  Degeneration: ``flange_width <= 0`` must
        reproduce the blade wing box exactly.  The reference is a shipped case
        (``outputs_str/naca4412_wingbox_str3``), not a synthetic model, so the
        check is anchored to a model whose numbering and grouping are already
        regression-frozen.

``T2``  stiffened panel.  Degeneration: ``n_stringers = 0`` must reproduce a
        plain unstiffened plate - 1 skin face, 0 stringer faces - and must be
        *invariant* to every stringer parameter.  This is the first form whose
        degeneration target is not an older family but its own stiffener-free
        member; that member is the one with a closed-form answer, which
        ``verify_panel.py`` checks (see :func:`check_T2`).

``T3``  fuselage barrel.  Degeneration: ``n_stringers = 0`` **and**
        ``n_frames = 2`` must reproduce a plain cylindrical shell - 1 skin face,
        0 stringer faces, 2 frame faces - and must be invariant to every
        *stringer* parameter.  Like T2, the target is the family's own
        stiffener-free member, whose closed-form answer (the thin-wall pressure
        vessel) is checked by ``verify_barrel.py``.  What is new here is that the
        form has **two** structural counts (circumferential and axial), so the
        sensitivity half pins both, and that the bond which reveals them is a
        boolean across a curved skin.  **D25 (2026-10-06)** adds the family's
        three *continuous* dimensions (diameter / length / wall thickness): the
        anchor written out must reproduce the default specimen, each dimension
        must reach the model (two through the mesh, thickness through the deck's
        ``*SHELL SECTION`` table), and the size dimension must decide role and
        split - before D25 a new size matched no region and fell through to
        ``train`` silently.  See :func:`check_T3`.

``T4``  open-hole coupon.  No degeneration in the usual sense: the hole **is**
        the family and ``hole_d -> 0`` is a plate, not a coupon.  So the check
        makes the family **falsifiable** instead: the one wrong model it can
        hide - a plate with no hole in it - must be rejected by gate 4 (same
        discipline as ``_pressure_sign_probe``), and a coupon whose hole edge
        would fall at or below the mesher's size floor must be *refused* rather
        than silently coarsened.  See :func:`check_T4`.

``T6``  multi-cell wing box.  Degeneration: ``web_chordwise = ()`` must
        reproduce the M1 box **bit for bit** - which is also what protects the
        twenty published wing-box cases from the new field.  On top of that the
        check pins the thing a new structural dimension can get wrong: the cells
        read back off the geometry must equal what gate 4 predicted, gate 4's
        expectation must *depend* on the cell count, a web outside the spars or
        on a stringer station must be **refused**, and the knob must decide
        dataset role and split (D24).  See :func:`check_T6`.

Usage::

    python check_forms.py                       # every registered check
    python check_forms.py --only T5
    python check_forms.py --only T2 --mesh-size 12
    python check_forms.py --json check_forms.json

Each check runs at **its own** declared mesh size unless ``--mesh-size`` says
otherwise.  That is not a detail: the flag used to be named ``--panel-size`` and
defaulted to the *panel's* 3 mm, and ``main`` injected it into every check that
took a ``size`` - including ``check_T3``, whose family builds at 25 mm.  Measured
consequence (2026-10-05): ``check_forms.py --only T3`` ran the barrel at 3 mm,
i.e. ~1.4e6 elements per specimen instead of ~1.6e5, and died after 19.6 min with
a native ``OSError: exception: stack overflow`` -- while the same five builds at
the barrel's own 25 mm finished clean in 6.5 min.  A check's default is part of
the check; nothing else may quietly overwrite it.
"""

from __future__ import annotations

import argparse
import inspect
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feagpt import (  # noqa: E402
    fuselage, geometry, inp_writer, meshing, open_hole, panel, sections, topology,
)
from feagpt.spec import FEASpec  # noqa: E402

ROUND = 6
DEFAULT_REFERENCE = "outputs_str/naca4412_wingbox_str3"


# --------------------------------------------------------------------------- #
# shared machinery
# --------------------------------------------------------------------------- #
def fingerprint(spec: FEASpec) -> dict:
    """Build the model and read back the grouping, tag-independently.

    Same shape as ``regress_groups.fingerprint`` on purpose: a degeneration
    check and a regression check should be comparing the *same kind of thing*,
    or "identical" would mean two different things in two places.
    """
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
        return {
            "mesh": {
                "n_nodes": report.n_nodes,
                "n_elements": report.n_elements,
                "min_quality": round(report.min_quality, 4),
                "element_types": report.element_types,
                "passed": report.passed,
            },
            "groups": groups,
            "geometry": topo["geometry"],
            "design": topo["design"],
            "gate4": topology.compare(topo),
            "notes": list(geo.notes),
            # D25: the deck's per-group wall thicknesses.  A shell's thickness is
            # *not* in the mesh, so a check that only compares meshes would call
            # a thickness sweep an empty field.  Carried here so the size /
            # thickness check can see it without writing a deck.
            "shell_thickness": dict(getattr(geo, "shell_thickness", None) or {}),
            # D21: the family's own claim about which way ``*DLOAD`` must be
            # signed.  Carried here so the gate can read the *builder's*
            # declaration without a second build (see check_T3 step (c2)).
            "pressure_dload_sign": float(geo.pressure_dload_sign),
        }
    finally:
        gmsh.finalize()


def _group_diff(ref: dict, got: dict) -> list[str]:
    """Human-readable differences between two fingerprints (empty = identical)."""
    issues: list[str] = []
    if ref.get("mesh") != got.get("mesh"):
        issues.append(f"mesh: {ref.get('mesh')} != {got.get('mesh')}")
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
            f"only-in-ref={only_ref[:2]}{'...' if len(only_ref) > 2 else ''} "
            f"only-in-got={only_got[:2]}{'...' if len(only_got) > 2 else ''}"
        )
    return issues


def _result(name: str, passed: bool, detail: str) -> dict:
    return {"check": name, "pass": bool(passed), "detail": detail}


# --------------------------------------------------------------------------- #
# T5 - flanged stringer section
# --------------------------------------------------------------------------- #
def _reference_spec(reference: str) -> FEASpec:
    p = Path(reference)
    if p.is_dir():
        p = p / (p.name + ".spec.json")
    if not p.exists():
        raise FileNotFoundError(
            f"T5 reference case not found: {p} - it anchors the check, so it "
            f"must exist (see --reference)"
        )
    return FEASpec.from_json(p)


def check_T5(reference: str = DEFAULT_REFERENCE) -> list[dict]:
    """T with ``flange_width <= 0`` must reproduce the blade wing box exactly."""
    out: list[dict] = []

    # (a) definition level - no gmsh, so a failure here is unambiguous.
    blade_sec = sections.section("blade", 100.0, 5.0, -1.0, 20.0)
    deg_sec = sections.section("T", 100.0, 5.0, -1.0, 20.0, flange_width=0.0)
    same_def = (deg_sec.segments == blade_sec.segments
                and tuple(deg_sec.role) == tuple(blade_sec.role)
                and deg_sec.n_faces == blade_sec.n_faces == 1)
    out.append(_result(
        "T5.section-degeneration",
        same_def,
        f"T(flange_width=0) -> segments={deg_sec.segments} role={deg_sec.role} "
        f"n_faces={deg_sec.n_faces}; blade -> {blade_sec.segments} "
        f"{blade_sec.role} {blade_sec.n_faces}",
    ))

    # (b) the face count gate 4 will demand must follow the degeneration, or the
    # gate rejects the very build the degeneration produces.
    f_pairs = [
        ("blade", None, 1),
        ("T", 30.0, 3),
        ("T", 0.0, 1),
        ("T", -5.0, 1),
    ]
    bad = [(k, w, sections.faces_per_section(k, w), want)
           for k, w, want in f_pairs
           if sections.faces_per_section(k, w) != want]
    out.append(_result(
        "T5.faces-per-section",
        not bad,
        " ".join(f"{k}(w={w})->{sections.faces_per_section(k, w)}"
                 for k, w, _ in f_pairs) + (f"; WRONG {bad}" if bad else ""),
    ))

    # (c) build level - the real check.  Two models, one fingerprint.
    ref_spec = _reference_spec(reference)
    blade_fp = fingerprint(ref_spec)

    deg_spec = _reference_spec(reference)
    deg_spec.name = ref_spec.name + "_Tfw0"
    deg_spec.airfoil.stringer_kind = "T"
    deg_spec.airfoil.stringer_flange_width = 0.0
    deg_fp = fingerprint(deg_spec)

    issues = _group_diff(blade_fp, deg_fp)
    out.append(_result(
        "T5.build-degeneration",
        not issues,
        ("blade and T(fw=0) builds are identical: "
         f"{blade_fp['mesh']['n_nodes']} nodes, "
         f"{blade_fp['mesh']['n_elements']} shells, minJ "
         f"{blade_fp['mesh']['min_quality']}, "
         f"{len(blade_fp['groups'])} groups")
        if not issues else "; ".join(issues),
    ))

    # (d) and the degenerate model must still satisfy gate 4 *as itself* - i.e.
    # n_faces_per_stringer_section = 1, not 3.  This is what makes the
    # degeneration a usable configuration rather than a trap.
    gate = deg_fp["gate4"]
    want_sec = deg_fp["design"]["n_faces_per_stringer_section"]
    out.append(_result(
        "T5.degenerated-gate4",
        bool(gate["pass"]) and want_sec == 1,
        f"gate4 on T(fw=0) = {'PASS' if gate['pass'] else 'FAIL'} "
        f"({sum(c['pass'] for c in gate['checks'])}/{len(gate['checks'])} checks), "
        f"faces-per-stringer-section = {want_sec}",
    ))
    return out


# --------------------------------------------------------------------------- #
# T2 - stiffened panel
# --------------------------------------------------------------------------- #
PANEL_STATIONS_N3 = (150.0, 300.0, 450.0)
"""Where three stringers on a 600 mm skin must be.  Written out rather than
computed, so this check has its own opinion about the layout instead of
borrowing ``PanelParams.stations`` - the implementation under test."""


def check_T2(size: float = panel.DEFAULT_MESH_SIZE) -> list[dict]:
    """``n_stringers=0`` must collapse onto a plain unstiffened plate.

    What "degeneration" means for a *new family*
    -------------------------------------------
    T5 degenerates onto a form that was trusted before T5 existed (the M1/M2
    blade wing box).  T2 **is** the first new family, so there is no older model
    to collapse onto, and its degeneration is onto its own **stiffener-free
    member**.  That is not a weaker statement: the stiffener-free member is the
    one member of the family with a closed-form answer, and ``verify_panel.py``
    validates that exact model against the Navier plate solution (0.63 % at this
    mesh size, 0.10 % at 3 mm).  So this file checks the build-level half of the
    contract - that the model really *is* a plain plate - and ``verify_panel.py``
    checks the physics half.

    What each check is worth
    ------------------------
    ``definition``
        ``stations()``/``pitch()`` at n = 0 and n = 3.  No gmsh, so a failure is
        unambiguously a definition error, not a build error.
    ``model``
        The built n = 0 panel is exactly one skin face and no stringer faces.
        A plate with a stray zero-area sliver here would still mesh and solve.
    ``invariance``
        **The check with teeth.**  Every stringer parameter (height, thickness,
        kind, flange width) is changed at once while ``n_stringers`` stays 0, and
        the model must not move by a single face.  A stringer parameter that is
        read before the count is consulted leaks into the stringer-free panel -
        and every numerical gate would still pass, because the plate would still
        be a plate, just not the one the other parameters describe.
    ``sensitivity``
        For n = 1 and 3: skin faces ``n + 1``, stringer faces ``n``, measured
        stations equal to the predicted layout, mesh gate passed, gate 4 passed.
        This is the two-sided statement the panel needs - the count must *do*
        something (or the sweep is vacuous) and must do *the right* thing (or the
        model is not the spec).
    """
    out: list[dict] = []

    # (a) definition level - no gmsh, so a failure here is unambiguous.
    p0 = panel.PanelParams(n_stringers=0)
    p3 = panel.PanelParams(n_stringers=3)
    got3 = tuple(round(v, 6) for v in p3.stations())
    def_ok = (p0.stations() == () and p0.pitch() is None
              and got3 == PANEL_STATIONS_N3
              and abs(float(p3.pitch()) - 150.0) < 1e-9)
    out.append(_result(
        "T2.definition-degeneration",
        def_ok,
        f"n=0 -> stations {p0.stations()} pitch {p0.pitch()}; "
        f"n=3 -> stations {got3} pitch {p3.pitch():g} "
        f"(want {PANEL_STATIONS_N3} / 150)",
    ))

    # (b) build level - n = 0 is one skin face and no stringer faces, and gate 4
    # accepts it *as itself* (n_skin_faces = 1, not 4).
    plain = fingerprint(panel.make_spec("t2_plain", n_stringers=0, size=size))
    g = plain["geometry"]
    deg_ok = (g["n_skin_faces"] == 1 and g["n_stringer_faces"] == 0
              and g["n_surfaces"] == 1 and not g["stringer_stations"])
    out.append(_result(
        "T2.degenerate-model",
        deg_ok and bool(plain["gate4"]["pass"]),
        f"n=0 built: skin {g['n_skin_faces']} face(s), stringer "
        f"{g['n_stringer_faces']} face(s), {g['n_surfaces']} surface(s), "
        f"stations {g['stringer_stations']}; gate4 "
        f"{'PASS' if plain['gate4']['pass'] else 'FAIL'}; "
        f"{plain['mesh']['n_nodes']} nodes, minJ {plain['mesh']['min_quality']}",
    ))

    # (c) the stringer parameters must not reach a stiffener-free panel.
    variant = fingerprint(panel.make_spec(
        "t2_plain_variant", n_stringers=0, size=size,
        stringer_height=40.0, stringer_thickness=5.0,
        stringer_kind="T", stringer_flange_width=50.0))
    issues = _group_diff(plain, variant)
    out.append(_result(
        "T2.parameter-invariance",
        not issues,
        ("n=0 with height 20->40, thickness 2.5->5, blade->T(fw=50) is "
         "identical face for face"
         if not issues else "; ".join(issues)),
    ))

    # (d) sensitivity - n is wired, and it is wired to the right thing.
    wrong: list[str] = []
    seen: list[str] = []
    for n in (1, 3):
        pp = panel.PanelParams(n_stringers=n)
        fp = fingerprint(panel.make_spec(f"t2_s{n}", n_stringers=n, size=size))
        gg = fp["geometry"]
        want_skin, want_str = n + 1, n
        want_st = [round(v, 6) for v in pp.stations()]
        ok = (gg["n_skin_faces"] == want_skin
              and gg["n_stringer_faces"] == want_str
              and gg["stringer_stations"] == want_st
              and fp["gate4"]["pass"] and fp["mesh"]["passed"])
        seen.append(
            f"n={n}: skin {gg['n_skin_faces']}/{want_skin} "
            f"str {gg['n_stringer_faces']}/{want_str} "
            f"stations {gg['stringer_stations']} "
            f"mesh {'ok' if fp['mesh']['passed'] else 'FAIL'} "
            f"{fp['mesh']['element_types']} minJ {fp['mesh']['min_quality']} "
            f"gate4 {'PASS' if fp['gate4']['pass'] else 'FAIL'}"
        )
        if not ok:
            wrong.append(f"n={n}")
    out.append(_result(
        "T2.stringer-sensitivity",
        not wrong,
        "; ".join(seen) + (f"  <- WRONG {wrong}" if wrong else ""),
    ))
    return out


# --------------------------------------------------------------------------- #
# T1 - swept / tapered wing box
# --------------------------------------------------------------------------- #
DATASET_BASELINE = (Path(__file__).resolve().parent.parent / "FEM-Bench-Aero"
                    / "modeling" / "naca4412_wingbox" / "spec.json")
"""The shipped prismatic case, used as T1's degeneration anchor.

Deliberately the **dataset** copy rather than a pipeline output: T1's promise is
that it does not move the published case, so the published case is what it has
to be compared against."""

SWEEP_CASE = (1.0, 20.0)
"""``(tip_chord_ratio, sweep_deg)`` for the swept probe: no taper, so the tip
leading-edge shift is the only thing that can move."""

TAPER_CASE = (0.6, 0.0)
"""The tapered probe - the case that produced the needle quad before the spar
size cap existed, so it is kept as the one that must keep working."""


def _tip_rib_box(fp: dict):
    """The tip rib's bbox from a fingerprint: the rib with the largest zmin."""
    boxes = list((fp.get("groups") or {}).get("ribs") or [])
    return max(boxes, key=lambda b: b[2]) if boxes else None


def check_T1(baseline: str = str(DATASET_BASELINE)) -> list[dict]:
    """A swept / tapered box, and the prismatic box it must collapse onto.

    Read :func:`check_T5` first - the shape of this check, and the reason it
    exists, are the same.  What differs is *what can be checked*.

    Why the neutral case needs a routing rule
    -----------------------------------------
    A loft between two identical sections is the same shape as an extrusion but
    a different OCC surface, and it meshes differently on the same size field
    (measured: 4753 nodes / 4251 quads vs 4418 / 4300).  So a neutral request
    must never reach the loft path, and the builder routes on
    :attr:`AirfoilSpec.is_prismatic`.  That makes the classic degeneration check
    - "build the neutral model and compare" - weaker than it looks: it passes
    even when the planform parameters are unwired, because a neutral model never
    consults them.  Hence the second half of this check.

    What each check is worth
    ------------------------
    ``dispatch``
        ``is_prismatic`` at neutral and off-neutral values.  No gmsh, so a
        failure is a definition error, not a build error.
    ``neutral``
        The neutral box is face-for-face and node-for-node the shipped M1 case.
        This is the archive-protection half.
    ``wired``
        **The check with teeth.**  A swept and a tapered model are built and the
        *measured* tip rib is compared with the D14 closed form - tip chord
        ``(x_r - x_f) * chord * ratio``, tip leading edge
        ``x_f * chord * ratio + span * tan(sweep)``.  A parameter that is read
        but never applied, or applied about the wrong reference line
        (quarter-chord instead of leading edge), fails here and nowhere else.
    ``sensitivity``
        The swept model must differ from the neutral one at all - the two-sided
        statement, guarding an inverted dispatch.
    ``role-and-split``
        The planform knobs must decide *dataset* role and split as well as
        geometry.  Regression guard, and cheap (no gmsh): before D14 the role
        predicate ``_is_wingbox_baseline`` tested only the keys it listed, so a
        swept box whose chord/span/ribs still matched the default reported
        ``baseline`` next to the real one.  Measured then: ``sweep_deg=20`` ->
        ``_is_wingbox_baseline = True``.  Now a swept/tapered box is ``sweep``,
        the three single-knob cases stay in ``train``, and the both-knobs case
        is judged by **D35's** two-sided rule rather than D15's blanket "both ->
        test": both coordinates inside the learned envelope -> ``train`` (an
        interior cross product), at least one outside -> ``test`` (a new shape).
        Both ends are pinned here, because keeping only the ``test`` end would
        mean the rule change silently deleted the exam.
    ``D16-val-regions``
        The D16 generalisation (*单维外推 -> val, 双维 -> test*) must hold for
        the planform knobs and the panel size, not only for ribs.  Cheap (no
        gmsh).  A knob *beyond* what train has learned is val; *inside* it is
        interpolation (train); both knobs at once is the held-out shape (test);
        a plain coupon at an unseen size is the panel's val.
    """
    out: list[dict] = []

    # (a) definition level - no gmsh, so a failure here is unambiguous.
    from feagpt.spec import AirfoilSpec as _AF
    def_ok = (_AF().is_prismatic
              and _AF(tip_chord_ratio=1.0, sweep_deg=0.0).is_prismatic
              and not _AF(tip_chord_ratio=0.9).is_prismatic
              and not _AF(sweep_deg=5.0).is_prismatic)
    out.append(_result(
        "T1.dispatch-definition",
        def_ok,
        "neutral (ratio 1.0, sweep 0) -> prismatic; (0.9, 0) and (1.0, 5) -> loft",
    ))

    ref = _reference_spec(baseline)
    ref_fp = fingerprint(ref)
    chord = float(ref.airfoil.chord)
    span = float(ref.airfoil.span)
    x_f, x_r = ref.airfoil.spar_chordwise

    # (b) the neutral box *is* the shipped box, face for face.
    neutral = _reference_spec(baseline)
    neutral.tip_chord_ratio = 1.0
    neutral.sweep_deg = 0.0
    n_fp = fingerprint(neutral)
    issues = _group_diff(ref_fp, n_fp)
    out.append(_result(
        "T1.neutral-reproduces-M1",
        not issues,
        (f"neutral box == shipped case: {n_fp['mesh']['n_nodes']} nodes, "
         f"{n_fp['mesh']['n_elements']} shells, minJ "
         f"{n_fp['mesh']['min_quality']}, {len(ref_fp['groups'])} groups")
        if not issues else "; ".join(issues),
    ))

    # (c) the planform parameters actually reach the geometry.
    for label, (ratio, sweep) in (("swept", SWEEP_CASE), ("tapered", TAPER_CASE)):
        spec = _reference_spec(baseline)
        spec.name = ref.name + f"_T1{label}"
        spec.airfoil.tip_chord_ratio = ratio
        spec.airfoil.sweep_deg = sweep
        fp = fingerprint(spec)
        box = _tip_rib_box(fp)
        offset = span * math.tan(math.radians(sweep))
        want_chord = (x_r - x_f) * chord * ratio
        want_xmin = x_f * chord * ratio + offset
        got_chord = (box[3] - box[0]) if box else float("nan")
        got_xmin = box[0] if box else float("nan")
        ok = (box is not None
              and abs(got_chord - want_chord) < 1e-6
              and abs(got_xmin - want_xmin) < 1e-6
              and fp["mesh"]["passed"])
        out.append(_result(
            f"T1.{label}-is-wired",
            ok,
            f"ratio={ratio:g} sweep={sweep:g}: tip-rib chord {got_chord:.4f} "
            f"(want {want_chord:.4f}), tip LE x {got_xmin:.4f} "
            f"(want {want_xmin:.4f}), nodes {fp['mesh']['n_nodes']}, minJ "
            f"{fp['mesh']['min_quality']}",
        ))

    # (d) two-sided: the swept model is not the neutral one.
    spec = _reference_spec(baseline)
    spec.name = ref.name + "_T1sens"
    spec.airfoil.sweep_deg = SWEEP_CASE[1]
    fp = fingerprint(spec)
    moved = _group_diff(ref_fp, fp)
    out.append(_result(
        "T1.sensitivity",
        bool(moved),
        f"sweep {SWEEP_CASE[1]:g} deg moves the model: {len(moved)} "
        f"difference(s) vs neutral",
    ))

    # (e) the planform knobs decide dataset role and split too, not just shape.
    #     Cheap (no gmsh).  Guards the 2026-10-04 defect: a swept box was
    #     labelled ``baseline`` because ``_is_wingbox_baseline`` only tested the
    #     keys in its whitelist, and the two T1 knobs were not among them.
    from feagpt import manifest as _mf

    def _role_split(ratio, sweep):
        s = _reference_spec(baseline)
        s.airfoil.tip_chord_ratio = ratio
        s.airfoil.sweep_deg = sweep
        return _mf.infer_role(s), _mf.assign_split(s)

    got_rs = {
        "neutral": _role_split(1.0, 0.0),
        "sweep": _role_split(*SWEEP_CASE),
        "taper": _role_split(*TAPER_CASE),
        # D35 (2026-10-24): 组合不再一律判 test。两个坐标都在 train 已学值域内
        # （taper 0.6 ∈ [0.6, 1]、sweep 20 ≤ 30）时，缺席的只是交叉本身，
        # 不是任何一个轴 —— 内插交叉归 train。改 D15 前这里期望是 test。
        "both_in": _role_split(TAPER_CASE[0], SWEEP_CASE[1]),
        # 另一端：至少一轴出包络（taper 0.4 < 0.6 且 sweep 40 > 30）仍是新形式，
        # 必须继续判 test，否则这一改就把考卷删了而不是改公平。
        "both_out": _role_split(0.4, 40.0),
    }
    want_rs = {
        "neutral": ("baseline", "train"),
        "sweep": ("sweep", "train"),
        "taper": ("sweep", "train"),
        "both_in": ("sweep", "train"),
        "both_out": ("sweep", "test"),
    }
    out.append(_result(
        "T1.role-and-split",
        got_rs == want_rs,
        "; ".join(f"{k} {v[0]}/{v[1]}" for k, v in got_rs.items())
        + ("" if got_rs == want_rs else f"  (want {want_rs})"),
    ))

    # (f) D16 -- the planform knobs *and* the panel size must decide val too.
    #     单维外推 -> val, 双维 -> test, 包络内 -> train.  Cheap (no gmsh).
    got_d16 = {
        "sweep40(val)": _role_split(1.0, 40.0),
        "sweep10(train)": _role_split(1.0, 10.0),
        "taper040(val)": _role_split(0.4, 0.0),
        "taper090(train)": _role_split(0.9, 0.0),
        "both40x040(test)": _role_split(0.4, 40.0),
    }
    want_d16 = {
        "sweep40(val)": ("sweep", "val"),
        "sweep10(train)": ("sweep", "train"),
        "taper040(val)": ("sweep", "val"),
        "taper090(train)": ("sweep", "train"),
        "both40x040(test)": ("sweep", "test"),
    }
    # the pre-existing ribs val rule, unchanged by D16
    ribs9 = _reference_spec(baseline)
    ribs9.airfoil.n_ribs = 9
    got_d16["ribs9(val)"] = (_mf.infer_role(ribs9), _mf.assign_split(ribs9))
    want_d16["ribs9(val)"] = ("sweep", "val")
    # the panel family: a *plain* coupon at an unseen size is its val; the
    # default plain coupon stays the train anchor.
    big = panel.make_spec("d16_panel_800x600", n_stringers=0,
                          length=800.0, width=600.0)
    anchor = panel.make_spec("d16_panel_600x600", n_stringers=0)
    got_d16["plain800x600(val)"] = (_mf.infer_role(big), _mf.assign_split(big))
    want_d16["plain800x600(val)"] = ("degenerate", "val")
    got_d16["plain600x600(train)"] = (_mf.infer_role(anchor),
                                      _mf.assign_split(anchor))
    want_d16["plain600x600(train)"] = ("degenerate", "train")
    out.append(_result(
        "T1.D16-val-regions",
        got_d16 == want_d16,
        "; ".join(f"{k} {v[0]}/{v[1]}" for k, v in got_d16.items())
        + ("" if got_d16 == want_d16 else f"  (want {want_d16})"),
    ))
    return out


# --------------------------------------------------------------------------- #
# T6 - multi-cell wing box
# --------------------------------------------------------------------------- #
WEBS_EVEN_ONE = (0.475,)
"""One web at the baseline box's even in-board station.

Written out rather than computed, so this check has its own opinion about the
layout instead of borrowing :meth:`AirfoilSpec.even_web_stations` - the
implementation under test.  For the shipped spars at 0.25c / 0.70c:
``0.25 + (0.70 - 0.25) * 1/2 = 0.475``.
"""

WEBS_EVEN_TWO = (0.4, 0.55)
"""Two even webs: ``0.25 + 0.45 * 1/3`` and ``0.25 + 0.45 * 2/3``."""

WEBS_OFFCENTRE = (0.35,)
"""One web off the even station - unequal cells, which Bredt-Batho no longer
describes (``verify_multi_cell.py``)."""


def check_T6(baseline: str = str(DATASET_BASELINE)) -> list[dict]:
    """A multi-cell wing box, and the single-cell box it must collapse onto.

    Read :func:`check_T1` first - the shape is the same and so is the reason it
    exists.  What differs is what can go wrong.

    What each check is worth
    ------------------------
    ``cell-definition``
        ``n_cells = n_webs + 1`` and "evenly spaced" at neutral / even /
        off-centre values.  No gmsh, so a failure here is a definition error.
    ``neutral-reproduces-M1``
        The web-free box is face-for-face the shipped M1 case.  This is the
        archive-protection half, and it is the only thing standing between a new
        field on ``AirfoilSpec`` and the twenty published wing-box cases.
    ``cells-{one,two,off}``
        **The check with teeth.**  The webs the builder produced are read back
        off the geometry (``n_web_faces``, measured from the faces) and compared
        with what gate 4 predicted, and the predicted cell count must be the one
        requested.  A web that is never built, or is built but not tagged into
        its own group - in which case it is filed as the nearer spar and the
        spar count inflates - fails here.
    ``gate-sees-cells``
        gate 4's expectation must be a *function* of the cell count, not a
        constant.  Cheap (no gmsh): derive the expectation twice, from the true
        design and from one whose ``n_webs`` was tampered with, and require the
        two to differ.
    ``refuses-{outside-spars,on-stringer}``
        A web outside the spar range, and a web landing on a stringer station,
        must both be **refused** rather than silently built: the first is an
        ambiguous face (it would coincide with or cross a spar), the second is
        two different members sharing one plane.
    ``role-and-split``
        The cell-count knob must decide *dataset* role and split as well as
        geometry (D24).  Cheap (no gmsh).  An evenly divided box is a point on
        the cell-count sweep (first instance ``train``, more ``val``); an
        off-centre web is the family's ``feature`` and goes to ``test``; and a
        multi-cell box must **not** match ``WINGBOX_BASELINE`` - the ``all()``
        trap T1 hit, where the whitelist only examines the keys it lists.
    """
    out: list[dict] = []

    # (a) definition level - no gmsh, so a failure here is unambiguous.
    from feagpt.spec import AirfoilSpec as _AF
    a0, a1 = _AF(), _AF(web_chordwise=WEBS_EVEN_ONE)
    a2 = _AF(web_chordwise=WEBS_EVEN_TWO)
    ax = _AF(web_chordwise=WEBS_OFFCENTRE)
    def_ok = (
        (a0.n_webs, a0.n_cells, a0.webs_are_even) == (0, 1, False)
        and (a1.n_webs, a1.n_cells, a1.webs_are_even) == (1, 2, True)
        and (a2.n_webs, a2.n_cells, a2.webs_are_even) == (2, 3, True)
        and (ax.n_webs, ax.n_cells, ax.webs_are_even) == (1, 2, False)
        and a0.even_web_stations() == ()
        and all(abs(g - w) < 1e-12
                for g, w in zip(a1.even_web_stations(), WEBS_EVEN_ONE))
    )
    out.append(_result(
        "T6.cell-definition", def_ok,
        f"neutral {a0.n_webs}web/{a0.n_cells}cell even={a0.webs_are_even}; "
        f"one {a1.n_webs}/{a1.n_cells} even={a1.webs_are_even}; "
        f"two {a2.n_webs}/{a2.n_cells} even={a2.webs_are_even}; "
        f"off-centre {ax.n_webs}/{ax.n_cells} even={ax.webs_are_even}"))

    # (b) the web-free box *is* the shipped box, face for face.
    ref = _reference_spec(baseline)
    ref_fp = fingerprint(ref)
    neutral = _reference_spec(baseline)
    neutral.airfoil.web_chordwise = ()
    n_fp = fingerprint(neutral)
    issues = _group_diff(ref_fp, n_fp)
    out.append(_result(
        "T6.neutral-reproduces-M1", not issues,
        (f"web-free box == shipped case: {n_fp['mesh']['n_nodes']} nodes, "
         f"{n_fp['mesh']['n_elements']} shells, minJ "
         f"{n_fp['mesh']['min_quality']}, {len(ref_fp['groups'])} groups")
        if not issues else "; ".join(issues)))

    # (c) the cells actually reach the geometry, and gate 4 predicts them.
    for label, webs, want_cells in (("one", WEBS_EVEN_ONE, 2),
                                    ("two", WEBS_EVEN_TWO, 3),
                                    ("off", WEBS_OFFCENTRE, 2)):
        spec = _reference_spec(baseline)
        spec.name = ref.name + f"_T6{label}"
        spec.airfoil.web_chordwise = tuple(webs)
        fp = fingerprint(spec)
        des, geo, gate = fp["design"], fp["geometry"], fp["gate4"]
        n_bay = int(des["n_ribs"]) - 1
        want_web_faces = int(des["n_webs"]) * n_bay
        ok = (int(des["n_cells"]) == want_cells
              and int(geo["n_web_faces"]) == want_web_faces
              and bool(gate["pass"]))
        out.append(_result(
            f"T6.cells-{label}", ok,
            f"cells {des['n_cells']} (want {want_cells}), web faces "
            f"{geo['n_web_faces']} (want {des['n_webs']}x{n_bay}="
            f"{want_web_faces}), gate4 "
            f"{'PASS' if gate['pass'] else 'FAIL'} "
            f"({sum(c['pass'] for c in gate['checks'])}/{len(gate['checks'])})"))

    # (d) gate 4's expectation must *depend* on the cell count.
    des_true = dict(ref_fp["design"])
    des_true["n_webs"], des_true["n_cells"] = 1, 2
    des_tampered = dict(des_true)
    des_tampered["n_webs"], des_tampered["n_cells"] = 0, 1
    e_true = topology.derive_expectation(des_true)
    e_tampered = topology.derive_expectation(des_tampered)
    differ = sorted(k for k in e_true if e_true.get(k) != e_tampered.get(k))
    out.append(_result(
        "T6.gate-sees-cells", bool(differ),
        (f"expectation changes on n_webs 1 -> 0 in {differ}")
        if differ else "expectation is identical with and without webs - the "
                       "cell count is not in gate 4"))

    # (e) the two refusals - the gate has to bite, not shrug.
    for label, webs, n_str, why in (
            ("outside-spars", (0.1,), 0,
             "web at 0.1c, ahead of the 0.25c front spar"),
            ("on-stringer", WEBS_EVEN_ONE, 1,
             "web 0.475c == the single stringer station")):
        spec = _reference_spec(baseline)
        spec.name = ref.name + f"_T6refuse_{label}"
        spec.airfoil.web_chordwise = tuple(webs)
        spec.airfoil.n_stringers_per_skin = n_str
        try:
            fingerprint(spec)
            msg = None
        except ValueError as exc:
            msg = str(exc)
        out.append(_result(
            f"T6.refuses-{label}", msg is not None,
            why + " -> " + (f"refused: {msg[:88]}" if msg
                            else "NOT refused (the model was built)")))

    # (f) role and split (D24) - regression guard, no gmsh.
    from feagpt import manifest as _mf
    got: dict[str, tuple[str, str]] = {}
    want: dict[str, tuple[str, str]] = {}
    for label, webs, side, role in (("web1", WEBS_EVEN_ONE, "train", "sweep"),
                                    ("web2", WEBS_EVEN_TWO, "val", "sweep"),
                                    ("offcentre", WEBS_OFFCENTRE, "test", "feature")):
        s = _reference_spec(baseline)
        s.airfoil.web_chordwise = tuple(webs)
        got[label] = (_mf.infer_role(s), _mf.assign_split(s))
        want[label] = (role, side)
    probe = _reference_spec(baseline)
    probe.airfoil.web_chordwise = WEBS_EVEN_ONE
    baseline_trap = bool(_mf._is_wingbox_baseline(probe))
    out.append(_result(
        "T6.role-and-split",
        got == want and not baseline_trap,
        "; ".join(f"{k} {v[0]}/{v[1]}" for k, v in got.items())
        + f" | one-web matches WINGBOX_BASELINE: {baseline_trap} (must be False)"
        + ("" if got == want else f"  (want {want})")))
    return out


# --------------------------------------------------------------------------- #
# T3 - fuselage barrel
# --------------------------------------------------------------------------- #
FUSELAGE_DEGENERATE = {"n_stringers": 0, "n_frames": 2}
"""The barrel's degeneration target: no stringers, both ends framed.

With nothing between the two end frames the barrel is a plain cylindrical
shell, which is the pressure-vessel case with a closed-form hoop answer
(``verify_barrel.py``) - the same role the stiffener-free coupon plays for T2.
``n_frames = 2`` and not 1 because a frame at each end is the minimum the family
permits (``_validate`` refuses fewer), and the two end frames do not cut the
skin axially, so the skin stays one *bay*.

One bay is not one *face*: the family carries no closed surface, so a
stringer-free skin is still partitioned on
:data:`feagpt.fuselage.MIN_SKIN_SEGMENTS` meridians and its frames are cut into
sectors on the same meridians.  That is why the target below is ``4 / 0 / 8`` and
not ``1 / 0 / 2`` - the partition is a *meshing* device (a closed cylinder's
mesh quality is not a usable function of the size cap; see
``_m5_probe/t3_cap_sweep.py``), not a structural parameter.
"""

FUSELAGE_LAYOUTS = {
    (0, 2): (4, 0, 8),
    (5, 2): (5, 5, 10),
    (8, 3): (16, 16, 24),
    (12, 4): (36, 36, 48),
}
"""``(n_stringers, n_frames) -> (skin, stringer, frame) faces`` a *correct*
barrel has.  Written out rather than computed so this check has its own opinion
about the mapping instead of borrowing ``topology._expect_fuselage`` - the
implementation under test.  ``(8, 3)`` is the family's default specimen, so the
pair is also the "the knobs do something" anchor.


Why these four, and not (4, 2) (D19, 2026-10-05)
-----------------------------------------------
The stringer count is not free: the family refuses ``0 < n_stringers < 5``
(``fuselage.MIN_STRINGERS``) because 1-4 stringers leave triangles on the frame
arcs, and five repairs were built and refused - see
``fuselage.py``'s module docstring and ``_m5_probe/t3_mesh_envelope.md``.  So the
sensitivity row exercises the envelope the family actually has: the degenerate
point (0, 2), the first clean stringered layout (5, 2), the default specimen
(8, 3) and one val-scale layout (12, 4).  A row inside the refused range would
now raise before it could ever be measured, which is the point - the check has
to agree with the builder about what is buildable.


The mapping itself (why these numbers)
--------------------------------------
Let ``n_seg`` be the meridian count: ``n`` stringers when there are stringers,
and ``fuselage.MIN_SKIN_SEGMENTS`` (= 4) when there are none.  Then ``n_seg``
meridians cut the skin into ``n_seg`` circumferential patches and each frame into
``n_seg`` sectors, while the ``n_frames - 1`` **interior** frames cut the skin
and each stringer into ``n_frames - 1`` axial bays (the two end frames sit on the
skin's own boundary circles and cut nothing).  So ``(8, 3)`` is
``8 x 2 = 16`` skin, ``8 x 2 = 16`` stringer, ``3 x 8 = 24`` frame faces; the
stringer-free member is ``4 x 1 = 4`` skin, ``0`` stringer, ``2 x 4 = 8`` frames;
with one interior frame the stringered bays stay at one, so ``(5, 2)`` is
``5 / 5 / 10``; and ``(12, 4)`` has ``4 - 1 = 3`` bays, so
``12 x 3 = 36 / 36 / 4 x 12 = 48``.

The last row was written down wrong at first (``24 / 24 / 48``, the bays
forgotten) and the check caught it on its first run - which is the whole point of
hardcoding a *prediction* here instead of asking ``topology`` to predict itself.
"""


def _pressure_sign_probe() -> tuple[bool, str]:
    """The gmsh-free half of the T3 pressure-sign gate (D21, 2026-10-05).

    What it guards, and why the sign has to be a *family* declaration
    ----------------------------------------------------------------
    ``*DLOAD ... P, <p>`` is a **signed** pressure along the shell normal, and a
    shell's normal orientation is a property of how the surface was built, not of
    the physical load.  Measured on the shipped path: the wing box's extruded
    skins and the panel's ``addRectangle`` carry the normal the ``P, -p``
    convention assumes, while the barrel's skin - built by ``occ.revolve`` - does
    not.  With the writer's old hard-coded ``-abs(p)`` the barrel came out
    pressurised from *outside*: ``verify_barrel.py`` read a mid-surface radial
    growth of **-0.22725 mm** where the thin-wall closed form
    ``p R^2 / (E t)`` says **+0.228 mm**, and all eight mid-surface meridians
    agreed in sign (-0.227 / -0.180 / ...), so it was not a local artefact.

    So the sign is declared by the builder and carried into the deck, exactly as
    ``clamp_dofs`` / ``pressure_group`` / ``shell_thickness`` are - the writer no
    longer holds an opinion about a family's surface orientation.

    Three statements, in the order they can go wrong
    -----------------------------------------------
    1. ``fuselage.PRESSURE_DLOAD_SIGN`` is ``+1.0`` (the family's claim);
    2. the ``GeometryResult`` default is still ``-1.0`` - i.e. the wing box and
       the panel (23 archived cases) take byte-identical decks;
    3. the writer **obeys** the number it is handed: a synthetic 1-quad deck
       written at ``+1`` carries a positive pressure and the same deck at ``-1``
       a negative one.  Statement 1 without 3 is a comment; statement 3 without
       1 is a mechanism nobody points at the barrel.
    """
    declared = getattr(fuselage, "PRESSURE_DLOAD_SIGN", None)
    default = getattr(geometry.GeometryResult(), "pressure_dload_sign", None)
    bits = [f"fuselage.PRESSURE_DLOAD_SIGN = {declared!r} (want 1.0)",
            f"GeometryResult() default = {default!r} (want -1.0)"]

    # The writer half needs no mesh at all: one quad is enough for a *DLOAD line,
    # and building it by hand keeps this a definition-level probe.
    import tempfile

    spec = fuselage.make_spec("t3_sign_probe")
    mesh = {
        "nodes": {1: (1000.0, 0.0, 0.0), 2: (1000.0, 100.0, 0.0),
                  3: (1000.0, 100.0, 100.0), 4: (1000.0, 0.0, 100.0)},
        "elements": {"skin": [("quad4", [1, 2, 3, 4])]},
    }
    seen: dict[float, float] = {}
    try:
        with tempfile.TemporaryDirectory() as td:
            for sign in (1.0, -1.0):
                p = Path(td) / f"sign{sign:+.0f}.inp"
                inp_writer.write_inp(
                    p, mesh, spec,
                    groups={"z0": [], "zL": []},
                    dialect="ccx",
                    bc_groups={"clamp": "z0", "load": "zL"},
                    thickness={"skin": 3.0},
                    pressure_group="skin",
                    pressure_dload_sign=sign,
                )
                lines = p.read_text(encoding="utf-8").splitlines()
                i = lines.index("*DLOAD")
                seen[sign] = float(lines[i + 1].split(",")[2])
    except Exception as exc:                       # noqa: BLE001 - it is the finding
        return False, "; ".join(bits + [f"deck probe raised {type(exc).__name__}: {exc}"])

    bits.append(f"deck: sign=+1 -> P {seen[1.0]:+.6g} (want > 0), "
                f"sign=-1 -> P {seen[-1.0]:+.6g} (want < 0)")
    ok = (declared == 1.0 and default == -1.0
          and seen.get(1.0, 0.0) > 0.0 and seen.get(-1.0, 0.0) < 0.0)
    return ok, "; ".join(bits)


def check_T3(size: float = fuselage.DEFAULT_MESH_SIZE) -> list[dict]:
    """``n_stringers=0, n_frames=2`` must collapse onto a plain cylindrical shell.

    Read :func:`check_T2` first - the shape of this check, and why every family
    needs one, are the same.  What is *specific* to a barrel is what "the new
    parameters reach the model" means when there are two of them (a
    circumferential *count* and an axial *count*) and when the bond that reveals
    them is a boolean between a curved skin, radial webs and ring frames.

    What each check is worth
    ------------------------
    ``definition-degeneration``
        ``stringer_angles()`` / ``frame_z()`` / ``bay_count()`` at the
        degenerate point.  No gmsh, so a failure is unambiguously a definition
        error.
    ``stringer-envelope``
        **D19 (2026-10-05).**  The family refuses ``0 < n_stringers <
        MIN_STRINGERS`` (1-4 stringers leave triangles on the frame arcs), so
        every count in that range must actually raise and the boundary values
        (0, 5) must not.  Proves the refusal is a live gate rather than a
        commented-out intention: a written-down envelope that no code enforces
        is the same failure mode as a gate nobody runs.
    ``section-kind-envelope``
        **D22 (2026-10-05).**  The family ships **blade stringers only**: the
        builder emits one flat radial web per stringer and never reads
        ``stringer_kind``, so a T-section spec used to build a model
        bit-identical to the blade one while ``topology`` demanded three faces
        per stringer.  Every section the registry knows that is not ``blade``
        must therefore raise, and ``blade`` must still be accepted.
    ``degenerate-expectation``
        Gate 4's *derived* counts at the degenerate point must be ``1 / 0 / 2``.
        This is what stops a wrong formula from being self-consistent: the
        observation below is compared against this, not against itself.
    ``pressure-sign`` / ``pressure-sign-builder``
        **D21 (2026-10-05).**  The family declares ``pressure_dload_sign = +1``
        and the deck writer obeys it, because the barrel's revolved skin carries
        the *opposite* normal to the extruded wing-box skins and the flat panel -
        so the writer's old hard-coded ``-abs(p)`` pressurised the barrel from
        outside (measured: -0.22725 mm radial growth against a +0.228 mm closed
        form).  The first half is gmsh-free and proves the *mechanism*; the
        second reads the declaration off the build above and proves the *builder*
        points the mechanism at the barrel.
    ``degenerate-model``
        The built barrel is exactly one skin face, no stringer faces and two
        frame faces, on two distinct ``z`` planes, and gate 4 accepts it **as
        itself**.  A stray zero-area sliver here would still mesh and solve.
    ``parameter-invariance``
        **The check with teeth.**  Every *buildable* stringer parameter is moved
        at once (height 25 -> 40, thickness 2.5 -> 5, flange width 0 -> 50) while
        ``n_stringers`` stays 0, and the model must not move by a single face.
        (``blade -> T`` is no longer part of this - D22 refuses that spec at
        definition time, so it is asserted there, not here.)  This is not
        hypothetical: it is what caught the size cap being read from
        ``stringer_height`` on a barrel that builds no stringers - a stringer
        parameter leaking into a stringer-free model, which no numerical gate
        would have noticed because the model is still a valid cylinder, just not
        the one the other parameters describe.
    ``layout-sensitivity``
        For each ``(n, nf)`` in :data:`FUSELAGE_LAYOUTS`: the observed skin /
        stringer / frame counts equal the hardcoded prediction, the measured
        stringer *angles* number ``n``, the mesh gate passes and gate 4 passes.
        This is the two-sided statement the family needs - the two counts must
        *do* something (or the sweep is vacuous) and must do *the right* thing
        (or the model is not the spec).
    """
    out: list[dict] = []

    # (a) definition level - no gmsh, so a failure here is unambiguous.
    zero = fuselage.FuselageParams(n_stringers=0, n_frames=2)
    z_frames = tuple(round(v, 6) for v in zero.frame_z())
    def_ok = (zero.stringer_angles() == ()
              and z_frames == (0.0, 2000.0)
              and zero.bay_count() == 1)
    out.append(_result(
        "T3.definition-degeneration",
        def_ok,
        f"n_str=0 -> angles {zero.stringer_angles()}; n_frm=2 -> frame_z "
        f"{z_frames} (want (0.0, 2000.0)); bay_count {zero.bay_count()} (want 1)",
    ))

    # (a2) D19 - the stringer-count envelope must *refuse*, and refuse exactly.
    #      Definition level (no gmsh): a ValueError here is unambiguous, and the
    #      check would be worthless if _validate only carried the rule in a
    #      comment.
    env_refused: list[int] = []
    env_accepted: list[int] = []
    for k in range(1, fuselage.MIN_STRINGERS + 1):
        try:
            fuselage.parse_params(fuselage.make_spec(f"t3_env{k}", n_stringers=k))
        except ValueError:
            env_refused.append(k)
        else:
            env_accepted.append(k)
    env_ok = (env_refused == list(range(1, fuselage.MIN_STRINGERS))
              and env_accepted == [fuselage.MIN_STRINGERS])
    out.append(_result(
        "T3.stringer-envelope",
        env_ok,
        f"n_stringers 1..{fuselage.MIN_STRINGERS - 1} refused "
        f"{env_refused} (want {list(range(1, fuselage.MIN_STRINGERS))}); "
        f"n_stringers={fuselage.MIN_STRINGERS} accepted {env_accepted} "
        f"(want [{fuselage.MIN_STRINGERS}]) - D19: below five the frame arcs "
        f"carry triangles",
    ))

    # (a3) D21 - the declared internal pressure must be the *applied* internal
    #      pressure.  Definition level plus a one-quad deck, so the failure mode
    #      ("the family says inward, the deck writes outward") is reproducible in
    #      under a second rather than after a solve.
    sign_ok, sign_detail = _pressure_sign_probe()
    out.append(_result("T3.pressure-sign", sign_ok, sign_detail))

    # (a2b) D22 - a stringer *section* the barrel builder cannot build must be
    #       refused, not accepted-and-ignored.  Measured defect (2026-10-05):
    #       ``build_fuselage_barrel`` emits one flat ``_radial_rect`` per stringer
    #       and never reads ``stringer_kind``, so a T-section spec produced a
    #       model **bit-identical to the blade one** (158 548 nodes / 157 972
    #       elements / minJ 0.5159) while ``topology`` demanded 3 faces per
    #       stringer - gate 4 caught it (expected 48, observed 16) but the
    #       schema, ``_validate`` and ``_design_fuselage`` all claimed the
    #       capability.  Same posture as D19's stringer envelope: refuse.
    #       Definition level, so a ValueError here is unambiguous.
    refutable = sorted(k for k in sections.SECTIONS if k != "blade")
    unrefused: list[str] = []
    for k in refutable:
        try:
            fuselage.parse_params(fuselage.make_spec(f"t3_kind_{k}", stringer_kind=k))
        except ValueError:
            continue
        unrefused.append(k)
    blade_ok = True
    try:
        fuselage.parse_params(fuselage.make_spec("t3_kind_blade", stringer_kind="blade"))
    except ValueError:
        blade_ok = False
    kind_ok = not unrefused and blade_ok
    out.append(_result(
        "T3.section-kind-envelope",
        kind_ok,
        f"non-blade sections {refutable} all refused: "
        f"{'yes' if not unrefused else f'NO - accepted {unrefused}'}; blade "
        f"accepted: {'yes' if blade_ok else 'NO'} - D22: the barrel builder "
        f"builds a flat radial web per stringer, so a flanged request would "
        f"silently produce the blade model",
    ))

    # (b) the *derived* expectation at the degenerate point must be 4 / 0 / 8.
    deg_spec = fuselage.make_spec("t3_deg", size=size, **FUSELAGE_DEGENERATE)
    exp = topology.derive_expectation(topology.design_counts(deg_spec))
    want = FUSELAGE_LAYOUTS[(0, 2)]
    exp_ok = (exp["n_skin_faces"] == want[0]
              and exp["n_stringer_faces"] == want[1]
              and exp["n_frame_faces"] == want[2]
              and exp["n_frame_z_planes"] == 2
              and exp["n_surfaces"] == sum(want) and exp["stringer_angles"] == [])
    out.append(_result(
        "T3.degenerate-expectation",
        exp_ok,
        f"derived: skin {exp['n_skin_faces']}/{want[0]}, stringer "
        f"{exp['n_stringer_faces']}/{want[1]}, frames {exp['n_frame_faces']}/{want[2]}, "
        f"z-planes {exp['n_frame_z_planes']}/2, surfaces "
        f"{exp['n_surfaces']}/{sum(want)}, angles {exp['stringer_angles']}",
    ))

    # (c) build level - the degenerate barrel is exactly the derived model, and
    #     gate 4 accepts it *as itself*.
    plain = fingerprint(fuselage.make_spec("t3_plain", size=size,
                                           **FUSELAGE_DEGENERATE))
    g = plain["geometry"]
    deg_ok = (g["n_skin_faces"] == want[0] and g["n_stringer_faces"] == want[1]
              and g["n_frame_faces"] == want[2] and g["n_frame_z_planes"] == 2
              and g["n_surfaces"] == sum(want) and not g["stringer_angles"])
    out.append(_result(
        "T3.degenerate-model",
        deg_ok and bool(plain["gate4"]["pass"]),
        f"n_str=0/n_frm=2 built: skin {g['n_skin_faces']} face(s), stringer "
        f"{g['n_stringer_faces']}, frames {g['n_frame_faces']} on "
        f"{g['n_frame_z_planes']} z-plane(s), {g['n_surfaces']} surface(s), "
        f"angles {g['stringer_angles']}; gate4 "
        f"{'PASS' if plain['gate4']['pass'] else 'FAIL'}; "
        f"{plain['mesh']['n_nodes']} nodes, minJ {plain['mesh']['min_quality']}",
    ))

    # (c2) D21, builder half - the *barrel builder* must declare the sign, not
    #      merely the module constant.  Read off the build above, so this costs
    #      no extra geometry.  Without it, an unpropagated declaration would
    #      leave the constant correct and the deck wrong.
    got_sign = plain["pressure_dload_sign"]
    out.append(_result(
        "T3.pressure-sign-builder",
        got_sign == fuselage.PRESSURE_DLOAD_SIGN == 1.0,
        f"build_fuselage_barrel declared pressure_dload_sign = {got_sign:+.1f} "
        f"(want {fuselage.PRESSURE_DLOAD_SIGN:+.1f}) - the deck must see the "
        f"family's number, not the writer's default",
    ))

    # (d) the stringer parameters must not reach a stringer-free barrel.
    #      D22 (2026-10-05) removed one axis from this check: ``blade -> T`` can
    #      no longer even be *constructed*, so it is asserted where refusals
    #      belong (``T3.section-kind-envelope``) rather than here.  What remains
    #      is the buildable space - height / thickness / flange width - and it is
    #      the axis with teeth: the size cap used to be read from
    #      ``stringer_height`` on a barrel that builds no stringers.
    variant = fingerprint(fuselage.make_spec(
        "t3_plain_variant", size=size, stringer_height=40.0,
        stringer_thickness=5.0, stringer_flange_width=50.0,
        **FUSELAGE_DEGENERATE))
    issues = _group_diff(plain, variant)
    out.append(_result(
        "T3.parameter-invariance",
        not issues,
        ("n_str=0 with height 25->40, thickness 2.5->5, flange width 0->50 is "
         "identical face for face - no stringer parameter reaches a "
         "stringer-free barrel (the blade->T axis is D22's refusal, checked "
         "separately)"
         if not issues else "; ".join(issues)),
    ))

    # (e) sensitivity - both counts are wired, and wired to the right thing.
    wrong: list[str] = []
    seen: list[str] = []
    for (n, nf), (ws, wt, wf) in sorted(FUSELAGE_LAYOUTS.items()):
        fp = fingerprint(fuselage.make_spec(f"t3_s{n}f{nf}", size=size,
                                            n_stringers=n, n_frames=nf))
        gg = fp["geometry"]
        ok = (gg["n_skin_faces"] == ws and gg["n_stringer_faces"] == wt
              and gg["n_frame_faces"] == wf and len(gg["stringer_angles"]) == n
              and fp["gate4"]["pass"] and fp["mesh"]["passed"])
        seen.append(
            f"{n}str/{nf}frm: skin {gg['n_skin_faces']}/{ws} "
            f"str {gg['n_stringer_faces']}/{wt} frm {gg['n_frame_faces']}/{wf} "
            f"angles {len(gg['stringer_angles'])}/{n} "
            f"mesh {'ok' if fp['mesh']['passed'] else 'FAIL'} "
            f"{fp['mesh']['n_nodes']}n minJ {fp['mesh']['min_quality']} "
            f"gate4 {'PASS' if fp['gate4']['pass'] else 'FAIL'}"
        )
        if not ok:
            wrong.append(f"{n}/{nf}")
    out.append(_result(
        "T3.layout-sensitivity",
        not wrong,
        "; ".join(seen) + (f"  <- WRONG {wrong}" if wrong else ""),
    ))

    # (f) the continuous dimensions - D25 (2026-10-06).
    #     Two-sided, and the second side is the point: the anchor written out
    #     must reproduce the default specimen, and *each* dimension must reach
    #     the model.  For a shell, "reach the model" is two different things:
    #     diameter/length show up in the mesh, wall thickness does not - it lives
    #     only in the deck's ``*SHELL SECTION`` card.  That asymmetry is exactly
    #     why D25 widened the duplicate fingerprint to include the thickness
    #     table, so it is asserted rather than assumed.
    anchor = {"diameter": 2000.0, "length": 2000.0, "thickness": 3.0}
    base = fingerprint(fuselage.make_spec("t3_size_anchor", size=size))
    explicit = fingerprint(fuselage.make_spec("t3_size_anchor", size=size,
                                              **anchor))
    issues = _group_diff(base, explicit)
    if base.get("shell_thickness") != explicit.get("shell_thickness"):
        issues.append(f"shell thickness {base.get('shell_thickness')} != "
                      f"{explicit.get('shell_thickness')}")
    out.append(_result(
        "T3.size-degeneration",
        not issues,
        (f"the anchor D{anchor['diameter']:g} x L{anchor['length']:g} x "
         f"t{anchor['thickness']:g}, written out, is the default specimen "
         f"face for face and section for section "
         f"(shell {base.get('shell_thickness')})"
         if not issues else "; ".join(issues)),
    ))

    weak: list[str] = []
    seen_size: list[str] = []
    for key, off in (("diameter", 1600.0), ("length", 1600.0)):
        fp = fingerprint(fuselage.make_spec(
            f"t3_size_{key}", size=size, **dict(anchor, **{key: off})))
        moved_mesh = bool(_group_diff(base, fp))
        if not moved_mesh:
            weak.append(f"{key} -> {off:g} did not move the mesh")
        seen_size.append(f"{key} {anchor[key]:g}->{off:g}: mesh "
                         f"{'moved' if moved_mesh else 'SAME'} "
                         f"({fp['mesh']['n_nodes']}n)")
    tvar = fingerprint(fuselage.make_spec("t3_size_thickness", size=size,
                                          **dict(anchor, thickness=2.0)))
    t_base = base.get("shell_thickness") or {}
    t_off = tvar.get("shell_thickness") or {}
    if t_off.get("skin") == t_base.get("skin"):
        weak.append("thickness -> 2 did not reach the *SHELL SECTION table")
    seen_size.append(
        f"thickness {anchor['thickness']:g}->2: skin section "
        f"{t_base.get('skin')} -> {t_off.get('skin')}, mesh "
        f"{'SAME' if not _group_diff(base, tvar) else 'moved'} "
        f"({tvar['mesh']['n_nodes']}n)")
    out.append(_result(
        "T3.size-sensitivity",
        not weak,
        "; ".join(seen_size) + (f"  <- WRONG {weak}" if weak else ""),
    ))

    # (g) the size dimension decides dataset role and split - D25.
    #     gmsh-free: this is a statement about the *dataset*, and the failure it
    #     guards (a new size falling through to train, silently, with every
    #     numeric gate green) is invisible to any built model.
    #     The first four rows are **the four shipped batch-6 points** (D27); the
    #     rest re-read the same rule in the other direction and in the mixed
    #     size+count corner, so a future edit that makes the rule
    #     direction-sensitive fails here rather than only on real cases.
    from feagpt import manifest as _mf

    def _split(**kw):
        return _mf.split_of(fuselage.make_spec("t3_split_probe", size=size, **kw))

    expect = [
        ("default specimen", {}, "train"),
        # shipped: the size sweep moves downwards only (D27); the diameter val
        # is d1800 - d1600 retired 2026-10-07 (gate3 1.1349 %, see
        # make_batch6_specs.py)
        ("diameter 1800", {"diameter": 1800.0}, "val"),
        ("length 1600", {"length": 1600.0}, "val"),
        ("thickness 2", {"thickness": 2.0}, "val"),
        ("diameter 1600 + length 1600",
         {"diameter": 1600.0, "length": 1600.0}, "test"),
        # the same rule, read the other way up
        ("length 3000", {"length": 3000.0}, "val"),
        ("diameter 1600 + length 3000",
         {"diameter": 1600.0, "length": 3000.0}, "test"),
        ("diameter 1600 + thickness 2",
         {"diameter": 1600.0, "thickness": 2.0}, "test"),
        # the mixed case: one continuous dimension *and* one count
        ("stringers 10 + diameter 1600",
         {"n_stringers": 10, "diameter": 1600.0}, "test"),
        # a count inside the trained range, alone: still train
        ("stringers 6", {"n_stringers": 6}, "train"),
    ]
    got: list[str] = []
    wrong_split: list[str] = []
    for label, kw, want in expect:
        side, reason = _split(**kw)
        got.append(f"{label} -> {side}")
        if side != want:
            wrong_split.append(f"{label}: {side} != {want} ({reason})")
    out.append(_result(
        "T3.role-and-split",
        not wrong_split,
        "; ".join(got) + (f"  <- WRONG {wrong_split}" if wrong_split else ""),
    ))
    return out


# --------------------------------------------------------------------------- #
# T4 - open-hole coupon
# --------------------------------------------------------------------------- #
def _hole_gate_probe() -> tuple[bool, str]:
    """Prove the hole gate has teeth: an **uncut** plate must fail gate 4.

    Built by hand - one rectangle, no boolean - because the question is about
    the *gate*, not about the builder.  An open-hole coupon and an uncut
    rectangle have the same logical group and the same face count; what
    separates them is the **boundary**, four curves against five.  If
    ``_expect_open_hole`` did not predict that, a case could ship with no hole
    in it and gate 4 would stay green - so the check deliberately builds the
    wrong model and requires the gate to reject it.  (Same discipline as
    ``_pressure_sign_probe``: a gate is only worth what it has been shown to
    catch.)
    """
    import gmsh

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add("t4_gate_probe")
    try:
        occ = gmsh.model.occ
        occ.addRectangle(0.0, 0.0, 0.0, 400.0, 200.0)     # deliberately no hole
        occ.synchronize()
        faces = [t for _d, t in gmsh.model.getEntities(2)]
        geo = geometry.GeometryResult(
            surfaces={"panel": faces},
            n_surfaces=len(faces),
            n_curves=len(gmsh.model.getEntities(1)),
        )
        spec = open_hole.make_spec("t4_gate_probe")
        topo = topology.collect(gmsh, spec, geo)
        gate = topology.compare(topo)
        want = topology.derive_expectation(topo["design"])
        got = topo["geometry"]
        detail = (
            f"uncut plate reads n_curves_total {got['n_curves_total']} "
            f"(want {want['n_curves_total']}), n_hole_curves "
            f"{got['n_hole_curves']} (want {want['n_hole_curves']}), "
            f"hole_d_measured {got['hole_d_measured']} "
            f"(want {want['hole_d_measured']}) -> gate4 "
            + ("FAIL, as it must (the gate has teeth)"
               if not gate["pass"] else "PASS (BUG: the gate is blind)")
        )
        return (not gate["pass"]), detail
    finally:
        gmsh.finalize()


def check_T4(size: float | None = None) -> list[dict]:
    """The open-hole coupon's degeneration self-check (M5 / task T4).

    What "degeneration" means for this family
    -----------------------------------------
    T1 and T5 degenerate onto an *older* model, T2 and T3 onto a
    *stiffener-free* member of themselves.  T4 has neither: the hole **is** the
    family and ``hole_d -> 0`` is not a coupon, it is a plate.  So
    "degeneration" has to mean something else here, and what it means is that
    the family must be **falsifiable**:

    * ``gate-teeth`` builds the one wrong model this family can hide - a plate
      with no hole in it - and requires gate 4 to reject it.  Every other check
      in this file, and every numerical gate in the chain, would pass it;
    * ``definition`` pins the derived quantities (lambda, net width, edge
      margin) and, more importantly, that *illegal* coupons are refused rather
      than built: a hole breaking an edge is a slit, and lambda at or above 1/3
      is outside where the comparison this family is judged against is valid;
    * ``built-model`` checks the coupon is one face with five boundary curves
      and that gate 4 accepts it **as itself**;
    * ``hole-size`` and ``hole-position`` are the sensitivity half: the
      observed diameter and centre must follow the spec, measured off the
      boundary rather than read back from the spec;
    * ``edge-floor-envelope`` is the second falsifiability half.  The family
      **refuses** a coupon whose hole edge would fall at or below the mesher's
      size floor (``max(size_chord / 6, 0.5)`` mm), because a silently
      over-coarsened edge keeps the run looking fine while reporting a factor
      the family was never validated against.  This check builds one coupon just
      below that boundary - it must raise - and one just above it - it must
      build and still measure the hole.  The boundary is taken from
      :func:`feagpt.open_hole.min_buildable_hole_d`, i.e. from the family's own
      rule, so it moves with the resolution constant instead of pinning a magic
      diameter;
    * ``default-centre`` checks the declared default (``hole_x/y = None`` means
      centred) against explicit values - a default that quietly meant something
      else would move every case the dataset ships;
    * ``role-and-split`` pins the **dataset** consequences of the knobs (D23,
      2026-10-06): the default coupon is ``baseline``/``train``, a centred coupon
      past the train ``lambda`` or footprint is ``val``, and an off-centre hole is
      ``test`` at any ``lambda`` - because the hole *position* is a discrete form
      axis and the analytic yardstick stops applying off the centre line.  Cheap
      (no gmsh), and it is what stopped this family shipping with an ``infer_role``
      branch missing: without one the coupon was reported ``baseline`` next to the
      real wing-box baseline and its split came out ``unassigned``.

    The physics half lives in ``verify_hole.py``: the factor against Howland's
    finite-width solution in both nominal-stress conventions, the peak's
    location, and the force balance read off the solved field.
    """
    out: list[dict] = []
    kw = {} if size is None else {"size": size}

    # (a) the gate must have teeth.
    teeth_ok, teeth_detail = _hole_gate_probe()
    out.append(_result("T4.gate-teeth", teeth_ok, teeth_detail))

    # (b) definition level - no gmsh, so a failure here is unambiguous.
    p_def = open_hole.OpenHoleParams()
    cx, cy = p_def.center()
    defs_ok = (
        abs(p_def.lambda_ratio - 0.1) < 1e-12
        and abs(p_def.net_width - 180.0) < 1e-12
        and (round(cx, 6), round(cy, 6)) == (200.0, 100.0)
        and abs(p_def.edge_margin() - 90.0) < 1e-12
    )
    accepted: list[str] = []
    for label, bad in (
        ("lambda 0.4 >= 1/3", dict(hole_d=80.0)),
        ("hole breaks the edge", dict(hole_d=20.0, hole_x=5.0)),
        ("length < 2 * hole_d", dict(length=30.0, hole_d=20.0)),
        ("hole_d <= 0", dict(hole_d=0.0)),
    ):
        try:
            open_hole._validate(open_hole.OpenHoleParams(**bad))
            accepted.append(label)
        except ValueError:
            pass
    out.append(_result(
        "T4.definition",
        defs_ok and not accepted,
        f"default: lambda {p_def.lambda_ratio:.4f}, net width "
        f"{p_def.net_width:g} mm, centre ({cx:g}, {cy:g}), edge margin "
        f"{p_def.edge_margin():g} mm; illegal coupons refused: "
        + (", ".join(accepted) + " <- ACCEPTED (bug)" if accepted
           else "lambda>=1/3, hole-off-the-edge, short coupon, hole_d<=0"),
    ))

    # (c) the built coupon is one face, five curves, one hole - and gate 4
    # accepts it as itself.
    base = fingerprint(open_hole.make_spec("t4_default", **kw))
    g = base["geometry"]
    built_ok = (g["n_panel_faces"] == 1 and g["n_curves_total"] == 5
                and g["n_hole_curves"] == 1
                and abs(g["hole_d_measured"] - 20.0) < 1e-9
                and g["hole_center_measured"] == [200.0, 100.0])
    out.append(_result(
        "T4.built-model",
        built_ok and bool(base["gate4"]["pass"]) and base["mesh"]["passed"],
        f"default coupon: {g['n_panel_faces']} face(s), {g['n_curves_total']} "
        f"curve(s), {g['n_hole_curves']} hole, measured d "
        f"{g['hole_d_measured']:g} mm at {g['hole_center_measured']}; "
        f"gate4 {'PASS' if base['gate4']['pass'] else 'FAIL'}; "
        f"{base['mesh']['n_nodes']} nodes, {base['mesh']['n_elements']} shells, "
        f"minJ {base['mesh']['min_quality']}, tri {base['mesh']['element_types']}",
    ))

    # (d) sensitivity - the spec drives the hole, measured off the boundary.
    #     Both lambdas are *buildable*: the family refuses a coupon whose hole
    #     edge would fall at or below the mesher's size floor, which at 72
    #     divisions rules out a hole smaller than ~11.5 mm no matter the far
    #     field.  The envelope half below stands on that boundary explicitly.
    wrong: list[str] = []
    seen: list[str] = []
    w0 = float(open_hole.OpenHoleParams().width)
    for lam in (0.15, 0.25):
        d = round(lam * w0, 6)
        fp = fingerprint(open_hole.make_spec(f"t4_lam{int(lam * 100):02d}",
                                             hole_d=d, **kw))
        gg = fp["geometry"]
        ok = (gg["n_hole_curves"] == 1
              and abs(gg["hole_d_measured"] - d) < 1e-9
              and bool(fp["gate4"]["pass"]) and fp["mesh"]["passed"])
        seen.append(f"lambda={lam:g} (d={d:g}): measured "
                    f"{gg['hole_d_measured']:g} mm, curves "
                    f"{gg['n_curves_total']}, mesh "
                    f"{'ok' if fp['mesh']['passed'] else 'FAIL'}, gate4 "
                    f"{'PASS' if fp['gate4']['pass'] else 'FAIL'}")
        if not ok:
            wrong.append(f"lambda={lam:g}")
    out.append(_result(
        "T4.hole-size",
        not wrong,
        "; ".join(seen) + (f"  <- WRONG {wrong}" if wrong else ""),
    ))

    # (d2) the edge-size floor must be a *live gate*, not a comment.  A coupon
    #      whose hole edge would fall at or below ``MeshSizeMin`` must raise - if
    #      it were built, the edge would be silently coarser than the resolution
    #      the family was validated at, and every numerical gate would still be
    #      green.  The boundary comes from the family's own rule, so this check
    #      moves with ``HOLE_ARC_DIVISIONS`` rather than pinning a diameter.
    probe = open_hole.make_spec("t4_floor_probe", **kw)
    floor = open_hole.mesh_size_floor(probe)
    d_min = open_hole.min_buildable_hole_d(probe)
    below_d = round(0.98 * d_min, 6)
    above_d = round(1.15 * d_min, 6)
    refused = None
    try:
        fingerprint(open_hole.make_spec("t4_below_floor", hole_d=below_d, **kw))
    except ValueError as exc:
        refused = str(exc)
    env_ok = refused is not None and "floor" in refused
    above_note = "not attempted"
    if env_ok:
        above = fingerprint(open_hole.make_spec("t4_above_floor",
                                                hole_d=above_d, **kw))
        ag = above["geometry"]
        above_ok = (ag["n_hole_curves"] == 1
                    and abs(ag["hole_d_measured"] - above_d) < 1e-6
                    and bool(above["gate4"]["pass"]))
        env_ok = env_ok and above_ok
        above_note = (f"d={above_d:.3f} built, measured "
                      f"{ag['hole_d_measured']:.3f} mm, gate4 "
                      f"{'PASS' if above['gate4']['pass'] else 'FAIL'}")
    out.append(_result(
        "T4.edge-floor-envelope",
        env_ok,
        f"edge-size floor {floor:.4f} mm -> smallest buildable hole d "
        f"{d_min:.3f} mm (at {open_hole.HOLE_ARC_DIVISIONS} divisions); "
        + (f"d={below_d:.3f} refused (the floor is a live gate)" if refused
           else f"d={below_d:.3f} BUILT (bug: the floor is not enforced)")
        + f"; {above_note}",
    ))

    # (e) an off-centre hole is observed where the spec put it.
    off = fingerprint(open_hole.make_spec("t4_offcentre", hole_x=120.0,
                                          hole_y=60.0, **kw))
    gog = off["geometry"]
    off_ok = (gog["n_hole_curves"] == 1
              and abs(gog["hole_center_measured"][0] - 120.0) < 1e-9
              and abs(gog["hole_center_measured"][1] - 60.0) < 1e-9
              and bool(off["gate4"]["pass"]))
    out.append(_result(
        "T4.hole-position",
        off_ok,
        f"hole at (120, 60): measured centre {gog['hole_center_measured']}, "
        f"{gog['n_hole_curves']} hole curve(s), d {gog['hole_d_measured']:g} mm, "
        f"gate4 {'PASS' if off['gate4']['pass'] else 'FAIL'}",
    ))

    # (f) the declared default is the explicit centre.
    explicit = fingerprint(open_hole.make_spec("t4_centre_explicit",
                                               hole_x=200.0, hole_y=100.0, **kw))
    same = _group_diff(base, explicit)
    out.append(_result(
        "T4.default-centre",
        not same,
        ("hole_x/hole_y = None is identical to the explicit (200, 100)"
         if not same else "; ".join(same)),
    ))

    # (g) D23 -- the coupon's knobs must decide dataset role and split too, not
    #     just geometry.  Cheap (no gmsh).  Guards the declaration gap this
    #     family arrived with, measured in ``_m5_probe/t4_rule_prototype.py``:
    #     with no ``infer_role`` branch an open-hole coupon was reported
    #     ``baseline`` (its spec carries a default ``AirfoilSpec``, which is
    #     field-for-field ``WINGBOX_BASELINE``) and ``assign_split`` returned
    #     ``unassigned``.  老王's three calls (2026-10-06): the hole *position* is
    #     a discrete form axis, so an off-centre hole is ``test`` at any lambda;
    #     the first batch is small; and the size dimension is declared now.
    #     **D28 (2026-10-08)** adds the corner rule (lambda AND footprint both
    #     off the anchor -> test, ahead of the two val regions) with batch 7's
    #     four shipped points; the two ``probe`` rows pin the rule's *direction*
    #     (lambda below train is still off-the-anchor for D28, and a lambda-only
    #     dip with the footprint unchanged stays in train).
    from feagpt import manifest as _mf

    def _role_split(**params):
        s = open_hole.make_spec("t4_role_probe", **kw, **params)
        return _mf.infer_role(s), _mf.assign_split(s)

    got_d23 = {
        "default(train)": _role_split(),
        "lambda0.2(val)": _role_split(hole_d=40.0),
        "lambda0.3(val)": _role_split(hole_d=60.0),
        "offcentre(test)": _role_split(hole_x=120.0, hole_y=60.0),
        "800x200(val)": _role_split(length=800.0),
        "b7 size600x300d30(val)": _role_split(length=600.0, width=300.0, hole_d=30.0),
        "b7 lambda0.25(val)": _role_split(hole_d=50.0),
        "b7 D28 corner(test)": _role_split(length=600.0, width=300.0, hole_d=60.0),
        "b7 offcentre d40(test)": _role_split(hole_d=40.0, hole_x=120.0, hole_y=60.0),
        "probe D28 lambda-down+size(test)": _role_split(length=600.0, width=300.0, hole_d=18.0),
        "probe lambda-down only(train)": _role_split(hole_d=18.0),
    }
    want_d23 = {
        "default(train)": ("baseline", "train"),
        "lambda0.2(val)": ("sweep", "val"),
        "lambda0.3(val)": ("sweep", "val"),
        "offcentre(test)": ("feature", "test"),
        "800x200(val)": ("sweep", "val"),
        "b7 size600x300d30(val)": ("sweep", "val"),
        "b7 lambda0.25(val)": ("sweep", "val"),
        "b7 D28 corner(test)": ("sweep", "test"),
        "b7 offcentre d40(test)": ("feature", "test"),
        "probe D28 lambda-down+size(test)": ("sweep", "test"),
        "probe lambda-down only(train)": ("sweep", "train"),
    }
    out.append(_result(
        "T4.role-and-split",
        got_d23 == want_d23,
        "; ".join(f"{k} {v[0]}/{v[1]}" for k, v in got_d23.items())
        + ("" if got_d23 == want_d23 else f"  (want {want_d23})"),
    ))
    return out


def check_T7(size: float | None = None) -> list[dict]:
    """Task T7 - the composite layup contract, as degeneration checks.

    T7 (2026-10-11, 老王's calls: equivalent single layer / open-hole family's
    material dimension / [0/90]s first) is a **material dimension**, not a new
    geometry, so its checks are about the *contract*, not the shape - the
    geometry is T4's and ``check_T4`` already guards it.  All five checks are
    cheap (no gmsh):

    * ``clt-anchor`` pins the ``[0/90]s`` equivalent against the closed form -
      the same numbers the module self-test derives by hand (EX = EY =
      (Q11+Q22)/2 − Q12²/((Q11+Q22)/2), nu_xy = A12/A11, GXY = Q66).  A
      transform regression shows up here before any solver runs;
    * ``isotropic-degeneration`` is the family's road home: a single ply whose
      engineering constants describe an isotropic solid must collapse to the
      isotropic equivalent - exactly the ``MaterialSpec`` the archived
      aluminium cases carry;
    * ``contract-refusals`` proves the D29 refusals are live (non-symmetric,
      unbalanced, two-truth thickness, malformed ply all raise);
    * ``deck-card`` renders a minimal deck with the equivalent and asserts the
      ``*ELASTIC, TYPE=ENGINEERING CONSTANTS`` block carries the 9 constants -
      the one place the layup actually reaches a solver.  The isotropic path
      is asserted unchanged (no such card) so the 40 archived decks cannot
      drift;
    * ``layup-key-plumbing`` walks the params dict through ``make_spec`` and
      ``parse_params``: the layup key must survive the factory (description
      mentions it) while geometry consumers see exactly the T4 coupon.

    The physics half lives in ``_probe_t7/verify_laminate.py``: the far-field
    modulus against the CLT equivalent, measured with the loaded-end mean
    (Gauss identity), tolerances stamped from the 2026-10-11 pilot.
    """
    from feagpt import inp_writer as _iw
    from feagpt.laminate import (LayupSpec, OrthotropicMaterialSpec, Ply,
                                 equivalent_engineering_constants,
                                 layup_from_params, layup_to_params)

    out: list[dict] = []
    m = OrthotropicMaterialSpec()

    # (a) the [0/90]s anchor - hand-checkable closed form.
    lay = LayupSpec(plies=(Ply(0.0, 0.5), Ply(90.0, 0.5),
                           Ply(90.0, 0.5), Ply(0.0, 0.5)), material=m)
    eq = equivalent_engineering_constants(lay)
    q11, q22, q12, _q66 = None, None, None, None
    from feagpt.laminate import reduced_stiffness
    q11, q22, q12, q66 = reduced_stiffness(m)
    ex_closed = (q11 + q22) / 2.0 - q12 ** 2 / ((q11 + q22) / 2.0)
    anchor_ok = (abs(eq["EX"] - ex_closed) < 1e-6
                 and abs(eq["EY"] - eq["EX"]) < 1e-6
                 and abs(eq["nuxy"] - q12 / ((q11 + q22) / 2.0)) < 1e-9
                 and abs(eq["GXY"] - m.G12) < 1e-9
                 and eq["code"] == "[0/90]s")
    out.append(_result(
        "T7.clt-anchor",
        anchor_ok,
        f"[0/90]s EX=EY={eq['EX']:.2f} (closed {ex_closed:.2f}), "
        f"nuxy={eq['nuxy']:.6f}, GXY={eq['GXY']:g}",
    ))

    # (b) the road home: isotropic single ply -> the archived MaterialSpec.
    E, nu = 73100.0, 0.33
    G = E / (2.0 * (1.0 + nu))
    iso = OrthotropicMaterialSpec(name="Alu_equiv", E1=E, E2=E, E3=E,
                                  nu12=nu, nu13=nu, nu23=nu,
                                  G12=G, G13=G, G23=G, density=2.78e-9)
    eq_iso = equivalent_engineering_constants(
        LayupSpec(plies=(Ply(0.0, 2.0),), material=iso))
    iso_ok = (abs(eq_iso["EX"] - E) < 1e-6 * E
              and abs(eq_iso["nuxy"] - nu) < 1e-9
              and abs(eq_iso["GXY"] - G) < 1e-6 * G)
    out.append(_result(
        "T7.isotropic-degeneration",
        iso_ok,
        f"single isotropic ply -> EX={eq_iso['EX']:.1f} (want {E:g}), "
        f"nuxy={eq_iso['nuxy']:.4f} (want {nu:g}), GXY={eq_iso['GXY']:.1f} "
        f"(want {G:.1f})",
    ))

    # (c) the D29 refusals are live.
    refused: list[str] = []
    cases = {
        "non-symmetric": LayupSpec(plies=(Ply(0.0, 0.5), Ply(90.0, 0.5)),
                                   material=m),
        "unbalanced (+30 without -30)": LayupSpec(
            plies=(Ply(0.0, 0.5), Ply(30.0, 0.5), Ply(30.0, 0.5),
                   Ply(0.0, 0.5)), material=m),
        "two-truth thickness": None,   # exercised through layup_from_params
        "malformed ply": None,         # ditto
    }
    for label, l in cases.items():
        if l is None:
            continue
        try:
            equivalent_engineering_constants(l)
            refused.append(label)
        except ValueError:
            pass
    try:
        layup_from_params({"thickness": 2.5, "layup": layup_to_params(lay)})
        refused.append("two-truth thickness")
    except ValueError:
        pass
    try:
        layup_from_params({"thickness": 2.0,
                           "layup": {"plies": [{"angle": 0.0}],
                                     "material": {}}})
        refused.append("malformed ply")
    except ValueError:
        pass
    out.append(_result(
        "T7.contract-refusals",
        not refused,
        "all refused" if not refused else ", ".join(refused) + " <- ACCEPTED (bug)",
    ))

    # (d) the deck card - one render with the equivalent, one without.
    spec = open_hole.make_spec("t7_deck_probe", thickness=2.0,
                               layup=layup_to_params(lay))
    mesh = {"nodes": {1: (0.0, 0.0, 0.0), 2: (100.0, 0.0, 0.0),
                      3: (100.0, 100.0, 0.0), 4: (0.0, 100.0, 0.0)},
            "elements": {"panel": [("quad4", [1, 2, 3, 4])]}}
    groups = {"fixed": [1, 4], "loaded": [2, 3]}
    deck_ortho = _iw.write_inp(
        "_probe_tmp_t7_ortho.inp", mesh, spec, groups=groups,
        thickness={"panel": 2.0}, bc_groups={"clamp": "fixed", "load": "loaded"},
        ortho_material=eq)
    txt = Path(deck_ortho).read_text(encoding="utf-8")
    ortho_ok = ("*ELASTIC, TYPE=ENGINEERING CONSTANTS" in txt
                and f"{eq['EX']:.6g}" in txt and "75364.5" in txt
                and "ENGINEERING CONSTANTS" in txt)
    spec_alu = open_hole.make_spec("t7_deck_probe_alu")
    deck_alu = _iw.write_inp(
        "_probe_tmp_t7_alu.inp", mesh, spec_alu, groups=groups,
        thickness={"panel": 2.0},
        bc_groups={"clamp": "fixed", "load": "loaded"})
    txt_alu = Path(deck_alu).read_text(encoding="utf-8")
    iso_card_absent = "ENGINEERING CONSTANTS" not in txt_alu
    for p in (deck_ortho, deck_alu):
        Path(p).unlink(missing_ok=True)
    out.append(_result(
        "T7.deck-card",
        ortho_ok and iso_card_absent,
        "ortho deck carries 9-constant card (EX=75364.5 present); "
        "isotropic deck unchanged (no card)"
        if ortho_ok and iso_card_absent else
        f"ortho_ok={ortho_ok} iso_card_absent={iso_card_absent}",
    ))

    # (e) the layup key survives the factory and stays invisible to geometry.
    p_spec = spec  # from (d): has the layup key
    params_back = layup_from_params(p_spec.structure.params)
    geo = open_hole.parse_params(p_spec)
    plumbing_ok = (params_back is not None
                   and params_back.code == "[0/90]s"
                   and geo.length == 400.0 and geo.width == 200.0
                   and geo.hole_d == 20.0
                   and "layup" not in geo.to_dict())
    out.append(_result(
        "T7.layup-key-plumbing",
        plumbing_ok,
        f"factory description: '{p_spec.description[-24:]}' ; geometry "
        f"params {sorted(geo.to_dict())} carry no layup",
    ))
    # (f) D29 - the material dimension's dataset consequences, as a resident
    #     gate (same pattern as T4.role-and-split).  The anchor-geometry
    #     laminate stays train (T6 web1 precedent: a form's first instance is
    #     something the model sees); one geometric axis on top of the new
    #     material is val; both axes is test; an off-centre hole is feature/
    #     test before the laminate predicates are ever consulted; and the
    #     aluminium anchor must still read baseline - a laminate coupon wearing
    #     the anchor's badge would poison the baseline equivalence class.
    from feagpt import manifest as _mf2

    lay_params = layup_to_params(lay)  # resolve *here*: a shadowed assignment
                                       # inside the closure is what caused the
                                       # UnboundLocalError the first run caught.

    def _t7_role_split(**params):
        s = open_hole.make_spec("t7_role_probe", thickness=2.0,
                                layup=lay_params, **params)
        return _mf2.infer_role(s), _mf2.assign_split(s)

    def _alu_role_split(**params):
        s = open_hole.make_spec("t7_alu_role_probe", **params)
        return _mf2.infer_role(s), _mf2.assign_split(s)

    got_d29 = {
        "alu anchor(baseline)": _alu_role_split(),
        "laminate anchor(train)": _t7_role_split(),
        "laminate lambda val": _t7_role_split(hole_d=40.0),
        # size val pins lambda on the anchor (d scales with width: 30/300=0.1),
        # the same construction as the T4 D28 shipped point one section above.
        "laminate size val": _t7_role_split(length=600.0, width=300.0,
                                            hole_d=30.0),
        "laminate double(test)": _t7_role_split(length=600.0, width=300.0,
                                                hole_d=60.0),
        "laminate offcentre(feature/test)": _t7_role_split(hole_x=120.0,
                                                           hole_y=60.0),
    }
    want_d29 = {
        "alu anchor(baseline)": ("baseline", "train"),
        "laminate anchor(train)": ("sweep", "train"),
        "laminate lambda val": ("sweep", "val"),
        "laminate size val": ("sweep", "val"),
        "laminate double(test)": ("sweep", "test"),
        "laminate offcentre(feature/test)": ("feature", "test"),
    }
    out.append(_result(
        "T7.role-and-split",
        got_d29 == want_d29,
        "; ".join(f"{k} {v[0]}/{v[1]}" for k, v in got_d29.items())
        + ("" if got_d29 == want_d29 else f"  (want {want_d29})"),
    ))

    # (g) the two build-out stacks - same yardstick discipline as (a), for the
    #     angle-ply and quasi-isotropic stacks the D30 batch added (2026-10-24).
    #     Closed forms derived by hand; equality to 1e-6 absolute, not "close".
    from feagpt.laminate import a_matrix

    lap = LayupSpec(plies=(Ply(45.0, 0.5), Ply(-45.0, 0.5),
                           Ply(-45.0, 0.5), Ply(45.0, 0.5)), material=m)
    qi = LayupSpec(plies=(Ply(0.0, 0.25), Ply(45.0, 0.25), Ply(-45.0, 0.25),
                          Ply(90.0, 0.25), Ply(90.0, 0.25), Ply(-45.0, 0.25),
                          Ply(45.0, 0.25), Ply(0.0, 0.25)), material=m)

    def _per_thickness(l):
        a0, a1, a2 = a_matrix(l)
        t = l.total_thickness
        return a0[0] / t, a1[0] / t, a2[2] / t, a0[2] / t, a1[2] / t

    a11, a12, a66, a16, a26 = _per_thickness(lap)
    a11_c = (q11 + q22) / 4.0 + q12 / 2.0 + q66
    a12_c = (q11 + q22 - 4.0 * q66) / 4.0 + q12 / 2.0
    a66_c = (q11 + q22 - 2.0 * q12 - 2.0 * q66) / 4.0 + q66 / 2.0
    forty5_ok = (abs(a11 - a11_c) < 1e-6 and abs(a12 - a12_c) < 1e-6
                 and abs(a66 - a66_c) < 1e-6
                 and abs(a16) < 1e-9 and abs(a26) < 1e-9)
    out.append(_result(
        "T7.clt-angle-ply",
        forty5_ok,
        f"[+45/-45]s A11/t={a11:.4f} (closed {a11_c:.4f}), "
        f"A12/t={a12:.4f} ({a12_c:.4f}), A66/t={a66:.4f} ({a66_c:.4f}), "
        f"A16={a16:.2e} A26={a26:.2e} (angle pairing must zero them)",
    ))

    b11, b12, b66, b16, b26 = _per_thickness(qi)
    b11_c = (1.5 * (q11 + q22) + q12 + 2.0 * q66) / 4.0
    b12_c = (3.0 * q12 + (q11 + q22) / 2.0 - 2.0 * q66) / 4.0
    b66_c = ((q11 + q22) / 2.0 - q12 + 2.0 * q66) / 4.0
    eq_qi = equivalent_engineering_constants(qi)
    # the isotropic identity: a quasi-isotropic stack must satisfy G=E/(2(1+nu)),
    # a relation the CLT route is never told.  This is the independent witness
    # that the rotation, the A sum and the inversion are all right.
    g_iso = eq_qi["EX"] / (2.0 * (1.0 + eq_qi["nuxy"]))
    qi_ok = (abs(b11 - b11_c) < 1e-6 and abs(b12 - b12_c) < 1e-6
             and abs(b66 - b66_c) < 1e-6
             and abs(b16) < 1e-9 and abs(b26) < 1e-9
             and abs(eq_qi["GXY"] - g_iso) < 1e-6 * g_iso)
    out.append(_result(
        "T7.clt-quasi-isotropic",
        qi_ok,
        f"[0/+45/-45/90]s EX=EY={eq_qi['EX']:.3f} nuxy={eq_qi['nuxy']:.4f} "
        f"GXY={eq_qi['GXY']:.3f}; isotropic identity G=E/(2(1+nu)) -> "
        f"{g_iso:.3f}",
    ))

    # (h) D30 - the scalar-axis counting rule, on the axes this batch added.
    #     Same anchors the manifest declares; a case on the anchor is train,
    #     one axis off is val, two is test.
    lay45 = layup_to_params(lap)
    lay_qi = layup_to_params(qi)
    thin090 = LayupSpec(plies=(Ply(0.0, 0.25), Ply(90.0, 0.25),
                               Ply(90.0, 0.25), Ply(0.0, 0.25)), material=m)
    thin45 = LayupSpec(plies=(Ply(45.0, 0.25), Ply(-45.0, 0.25),
                              Ply(-45.0, 0.25), Ply(45.0, 0.25)), material=m)

    def _d30(name, layup, thickness, **params):
        s = open_hole.make_spec(name, thickness=thickness, layup=layup, **params)
        return _mf2.assign_split(s)

    got_d30 = {
        "090s anchor": _d30("d30a", lay_params, 2.0),
        "45s anchor": _d30("d30b", lay45, 2.0),
        "qi anchor": _d30("d30c", lay_qi, 2.0),
        "45s + lambda": _d30("d30d", lay45, 2.0, hole_d=40.0),
        "45s + thickness": _d30("d30e", layup_to_params(thin45), 1.0),
        "qi + thickness": _d30("d30f", layup_to_params(
            LayupSpec(plies=(Ply(0.0, 0.125), Ply(45.0, 0.125),
                             Ply(-45.0, 0.125), Ply(90.0, 0.125),
                             Ply(90.0, 0.125), Ply(-45.0, 0.125),
                             Ply(45.0, 0.125), Ply(0.0, 0.125)), material=m)),
            1.0),
    }
    want_d30 = {
        "090s anchor": "train",       # 0 axes: the laminate anchor itself
        "45s anchor": "val",          # M
        "qi anchor": "val",           # M
        "45s + lambda": "test",       # M + L
        "45s + thickness": "test",    # M + T
        "qi + thickness": "test",     # M + T
    }
    out.append(_result(
        "T7.d30-scalar-axes",
        got_d30 == want_d30,
        "; ".join(f"{k} {v}" for k, v in got_d30.items())
        + ("" if got_d30 == want_d30 else f"  (want {want_d30})"),
    ))

    # (i) the thickness axis is a *degeneration* check, not a dataset axis.
    #     Under the constant-nominal-stress convention the load is
    #     ``sigma * width * thickness`` and the membrane stiffness is
    #     ``E * thickness``: u = sigma*L/E with the thickness cancelling
    #     exactly.  Measured 2026-10-24 on the D30 batch (_probe_t7b):
    #     [0/90]s at 2.0 mm -> max|u| 0.05734516, at 1.0 mm -> 0.05734516,
    #     identical to the last digit; [45/-45]s 0.22584988 vs 0.22585092.
    #     So a thickness variant ships no new observable - it would be a
    #     free sample - and what it *is* good for is exactly this: proof that
    #     the load actually scales with t.  Get that wrong and the two
    #     thicknesses differ by 2x.  Checked here from the specs, no solve.
    s_thick = open_hole.make_spec("t7_t2", thickness=2.0, layup=lay_params)
    s_thin = open_hole.make_spec("t7_t1", thickness=1.0,
                                 layup=layup_to_params(thin090))
    load_ratio = s_thick.load.magnitude / s_thin.load.magnitude
    e_thick = equivalent_engineering_constants(lay)
    e_thin = equivalent_engineering_constants(thin090)
    same_e = all(abs(e_thick[k] - e_thin[k]) <= 1e-9 * abs(e_thick[k])
                 for k in ("EX", "EY", "GXY", "nuxy"))
    out.append(_result(
        "T7.thickness-invariance",
        abs(load_ratio - 2.0) < 1e-12 and same_e,
        f"load 2.0mm/1.0mm = {load_ratio:.12f} (must be 2 -> u independent of "
        f"t); EX/EY/GXY/nuxy unchanged with t ({e_thick['EX']:.3f} vs "
        f"{e_thin['EX']:.3f}); measured max|u| 0.05734516 vs 0.05734516 (D30 "
        f"batch, _probe_t7b) - thickness is a load-convention probe, not a "
        f"sample axis",
    ))
    return out


CHECKS = {
    "T1": check_T1,
    "T5": check_T5,
    "T2": check_T2,
    "T3": check_T3,
    "T4": check_T4,
    "T6": check_T6,
    "T7": check_T7,
}
"""Structure form -> degeneration check.  Add the form's check here when its
builder lands, so "new form" and "has a way back to the old form" stay one
thing rather than two."""
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", default=None,
                    help=f"run only these forms (registered: {sorted(CHECKS)})")
    ap.add_argument("--reference", default=DEFAULT_REFERENCE,
                    help="blade wing-box case used as the T5 anchor")
    ap.add_argument("--baseline", default=str(DATASET_BASELINE),
                    help="prismatic wing-box case used as the T1 anchor")
    ap.add_argument("--mesh-size", "--panel-size", dest="mesh_size", type=float,
                    default=None,
                    help="override the mesh size (mm) of *every* check that takes "
                         "one - T2's panel and T3's barrel alike. Left unset by "
                         "default so each check builds at its own declared size "
                         f"(T2 {panel.DEFAULT_MESH_SIZE:g}, "
                         f"T3 {fuselage.DEFAULT_MESH_SIZE:g} mm). --panel-size is "
                         "kept as an alias so existing scripts keep working.")
    ap.add_argument("--json", help="write the machine-readable report here")
    args = ap.parse_args(argv)

    names = args.only or sorted(CHECKS)
    unknown = [n for n in names if n not in CHECKS]
    if unknown:
        print(f"unknown form(s) {unknown}; registered: {sorted(CHECKS)}")
        return 1

    report: list[dict] = []
    npass = nfail = 0
    for name in names:
        print(f"=== {name} degeneration")
        fn = CHECKS[name]
        try:
            accepted = inspect.signature(fn).parameters
            kw = {}
            if "reference" in accepted:
                kw["reference"] = args.reference
            if "baseline" in accepted:
                kw["baseline"] = args.baseline
            # Only ever *override* a check's size when the caller asked for it.
            # Injecting the flag's default here is what silently ran T3 at the
            # panel's 3 mm (see the module docstring for the measured cost).
            if "size" in accepted and args.mesh_size is not None:
                kw["size"] = args.mesh_size
            if "size" in accepted:
                # A check may declare ``size = None`` to mean "build at *my*
                # family's own default" (T4 does; T2/T3 name a number).  Echoing
                # it must not assume the default is numeric - the first run of
                # ``--only T4`` died here with ``float(None)`` before the check
                # itself was ever entered.
                raw = kw.get("size", accepted["size"].default)
                if raw is None:
                    print("  (mesh size: the check's own family default)")
                else:
                    print(f"  (mesh size {float(raw):g} mm - "
                          + ("--mesh-size override)" if "size" in kw
                             else "the check's own default)"))
            rows = fn(**kw)
        except Exception as exc:                       # noqa: BLE001 - reported
            rows = [_result(f"{name}.invocation", False, f"{type(exc).__name__}: {exc}")]
        for r in rows:
            report.append({"form": name, **r})
            npass += r["pass"]
            nfail += not r["pass"]
            print(f"  [{'PASS' if r['pass'] else 'FAIL'}] {r['check']}")
            print(f"         {r['detail']}")

    print(f"\ndegeneration self-checks: {npass} PASS, {nfail} FAIL")
    print(f"VERDICT: {'PASS' if nfail == 0 else 'FAIL'}")
    if args.json:
        Path(args.json).write_text(
            json.dumps({"n_pass": npass, "n_fail": nfail, "checks": report},
                       indent=2, ensure_ascii=False),
            encoding="utf-8")
        print(f"report -> {args.json}")
    return 0 if nfail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
