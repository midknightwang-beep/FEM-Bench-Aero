"""Assemble a CalculiX / Abaqus input deck.

Gmsh can export a bare mesh ``.inp``, but the *analysis* deck (sections,
material, boundary conditions, loads, step and output requests) has to be
composed explicitly.  Building it here rather than exporting from Gmsh keeps
the deck deterministic and diff-able, which is what makes it usable inside a
loop over hundreds of configurations.

Two dialects, one builder
-------------------------
CalculiX and Abaqus accept largely the same keyword language, and the parts
that matter physically (``*NODE``, ``*ELEMENT``, ``*SHELL SECTION``,
``*MATERIAL``/``*ELASTIC``, ``*BOUNDARY``, ``*STATIC``, ``*CLOAD``,
``*DLOAD``) are identical.  Keeping two separate writers would let the two
drift apart silently, so there is **one** builder with a ``dialect`` switch,
and the switch is applied at exactly three places:

1. the output-request block;
2. trailing commas on a few one-field data lines (Abaqus reads a trailing
   comma as "continued on the next line", CalculiX does not care);
3. the provenance line in ``*HEADING``.

Verified against CalculiX 2.23 and Abaqus 2026 on the same model - see
``verify_solvers.py``.

Units: mm, tonne, s, MPa, N.  Consistent, so no scaling factors appear in the
deck.
"""

from __future__ import annotations

from pathlib import Path

from .spec import FEASpec

DIALECTS = ("ccx", "abaqus")

#: Which logical group plays which boundary-condition role.  Supplied by the
#: geometry builder (``GeometryResult.bc_groups``) because it is family-specific;
#: the wing-box default is kept here so the historical two-argument call still
#: works.  It is threaded through instead of hard-coding ``"root"``/``"tip"`` so
#: that a family which clamps elsewhere cannot have its BC silently dropped.
DEFAULT_BC_GROUPS = {"clamp": "root", "load": "tip"}


def _group_thicknesses(spec: FEASpec) -> dict[str, float]:
    """Wing-box shell thickness per logical group.

    Kept as the *fallback*, and only that: a family whose groups are named
    differently, or whose thicknesses come from somewhere other than
    ``spec.airfoil``, declares its own table on
    :attr:`~feagpt.geometry.GeometryResult.shell_thickness` and the writer uses
    that instead.  The alternative - a chain of ``if family == ...`` here - is
    how the deck writer would come to know about every family.
    """
    t_skin = float(spec.airfoil.skin_thickness)
    t_rib = float(spec.airfoil.rib_thickness)
    t_str = float(getattr(spec.airfoil, "stringer_thickness", t_skin))
    return {
        "upper_skin": t_skin,
        "lower_skin": t_skin,
        "front_spar": t_skin,
        "rear_spar": t_skin,
        # T6: an intermediate web is a shear web like the two spars, so it takes
        # the skin thickness.  Leaving it out is *not* a silent omission - a
        # group with no entry here gets no ``*SHELL SECTION``, i.e. zero-thickness
        # shells, and ccx aborts in ``gen3delem`` naming an element but not the
        # group (measured on the first web1 run).  The guard in ``render`` names
        # the group before the solver is ever started.
        "webs": t_skin,
        "ribs": t_rib,
        "stringers_upper": t_str,
        "stringers_lower": t_str,
    }


def _fmt(v: float) -> str:
    """Compact fixed-format float that both solvers parse without locale issues."""
    return f"{v:.6g}"


def write_inp(
    path,
    mesh: dict,
    spec: FEASpec,
    groups: dict | None = None,
    dialect: str = "ccx",
    bc_groups: dict | None = None,
    thickness: dict | None = None,
    clamp_dofs: tuple[int, int] = (1, 6),
    pressure_group: str = "upper_skin",
    pressure_dload_sign: float = -1.0,
    ortho_material: dict | None = None,
) -> Path:
    """Write a complete solver input deck.

    Parameters
    ----------
    path :
        Destination ``.inp`` path.
    mesh :
        ``{"nodes": {tag: (x, y, z)}, "elements": {group: [(name, [n1, n2, ...])]}}``
    spec :
        The :class:`FEASpec` that produced the geometry.
    groups :
        Optional, ``{group name: [node_tags...]}`` for the BC groups.
    dialect :
        ``"ccx"`` (CalculiX) or ``"abaqus"``.
    bc_groups :
        Optional, ``{"clamp": <group name>, "load": <group name>}``.  Names the
        groups in ``groups`` that carry the clamp and the load, so the deck
        writer never hard-codes a family's BC naming.
    thickness :
        Optional, ``{logical group: thickness_mm}`` from the geometry builder.
        ``None`` falls back to the wing-box table (see
        :func:`_group_thicknesses`).
    clamp_dofs :
        Freedoms to fix at the clamp group.  ``(1, 6)`` = fully clamped (the
        wing box); a simply supported panel is ``(1, 3)`` - translations held,
        rotations free.
    pressure_group :
        Logical group a ``*DLOAD`` pressure acts on.  ``"upper_skin"`` for the
        wing box, ``"panel"`` for a stiffened panel, ``"skin"`` for a barrel.
    pressure_dload_sign :
        Sign to write ``*DLOAD ... P`` with for a positive ``load.magnitude``.
        Declared by the builder (see
        :attr:`feagpt.geometry.GeometryResult.pressure_dload_sign`); the writer
        holds no opinion of its own, because the correct sign depends on which
        way the family's surfaces happen to be oriented.  ``-1.0`` is the
        historical constant and reproduces the archived wing-box / panel decks.
    ortho_material :
        T7: an orthotropic equivalent single layer, as the dict produced by
        :func:`feagpt.laminate.equivalent_engineering_constants` (keys
        ``EX/EY/nuxy/GXY/E3/nu13/nu23/G13/G23/density/name``).  When given, the
        material block is written as ``*ELASTIC, TYPE=ENGINEERING CONSTANTS``
        (9 constants) and the deck carries the laminate's CLT membrane
        equivalent instead of ``spec.material``.  ``None`` - the archived
        cases - reproduces the isotropic block byte for byte.
    """
    if dialect not in DIALECTS:
        raise ValueError(f"unknown dialect {dialect!r}; expected one of {DIALECTS}")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    groups = groups or {}
    roles = {**DEFAULT_BC_GROUPS, **(bc_groups or {})}
    clamp_group = roles["clamp"]
    load_group = roles["load"]
    # T7: an orthotropic equivalent replaces the isotropic MaterialSpec at the
    # one place the writer consumes it - ``mat``.  Everything downstream (the
    # *SHELL SECTION material name, the *MATERIAL block) routes on the dict
    # vs dataclass branch in the blocks below; the isotropic path is untouched.
    mat = ortho_material if ortho_material is not None else spec.material
    nodes = mesh["nodes"]
    elements = mesh["elements"]
    # NOTE on trailing commas: Abaqus treats a trailing comma on a keyword data
    # line as "continued on the next line", so a stray one would swallow the
    # following keyword.  CalculiX tolerates it either way.  Neither deck uses
    # one, which keeps the two outputs textually identical apart from the
    # output-request block - so a diff of the two decks shows only real
    # differences.
    L: list[str] = []
    L.append("*HEADING")
    L.append(f" {spec.name} | {spec.description}")
    L.append(f" generated by feagpt_repro ({_dialect_label(dialect)})")

    # ---- nodes ---------------------------------------------------------- #
    L.append("*NODE, NSET=NALL")
    for tag in sorted(nodes):
        x, y, z = nodes[tag]
        L.append(f"{tag}, {_fmt(x)}, {_fmt(y)}, {_fmt(z)}")

    # ---- elements, grouped by logical surface --------------------------- #
    # Element ids come from one running counter.  Each *ELEMENT block would
    # otherwise restart at 1 and the solver reports "element N is already
    # defined" for the second group - which CalculiX did, the first time round.
    elset_members: list[str] = []
    eid = 0
    for group, elems in elements.items():
        if not elems:
            continue
        elset = f"E_{group.upper()}"
        elset_members.append(elset)
        by_type: dict[str, list[list[int]]] = {}
        for name, conn in elems:
            by_type.setdefault(name, []).append(conn)
        for name, rows in by_type.items():
            kw = _elem_keyword(name)
            L.append(f"*ELEMENT, TYPE={kw}, ELSET={elset}")
            for conn in rows:
                eid += 1
                L.append(f"{eid}, " + ", ".join(str(n) for n in conn))

    if elset_members:
        L.append("*ELSET, ELSET=EALL")
        L.append(", ".join(elset_members))
        L.append("**")

    # ---- sections ------------------------------------------------------- #
    thickness = thickness or _group_thicknesses(spec)
    # A group with elements but no declared thickness would be written without a
    # ``*SHELL SECTION`` - zero-thickness shells - and the failure would surface
    # inside the solver's expansion pass as a message naming an element but not
    # the missing group.  Refuse here instead, where the group name is still
    # known.  (The archived wing-box/panel/barrel decks have no such group, so
    # this changes no existing output.)
    missing_t = sorted(g for g, els in elements.items() if els and g not in thickness)
    if missing_t:
        raise ValueError(
            f"no shell thickness declared for element group(s) {missing_t}; "
            f"the deck would carry zero-thickness shells")
    for group, t in thickness.items():
        if not elements.get(group):
            continue
        L.append(
            f"*SHELL SECTION, ELSET=E_{group.upper()}, MATERIAL={_matname(mat)}, OFFSET=0."
        )
        L.append(_fmt(t))

    # ---- material ------------------------------------------------------- #
    L.append(f"*MATERIAL, NAME={_matname(mat)}")
    if isinstance(mat, dict):
        # T7 orthotropic equivalent single layer.  The 9 engineering constants
        # are exactly what both solvers parse (measured: ccx 2.23 probe B,
        # _probe_t7/t7_probe_b_ortho1.inp).  Row order is fixed by the keyword:
        # E1,E2,E3, nu12,nu13,nu23, G12,G13 / G23.
        L.append("*ELASTIC, TYPE=ENGINEERING CONSTANTS")
        L.append(f"{_fmt(mat['EX'])}, {_fmt(mat['EY'])}, {_fmt(mat['E3'])}, "
                 f"{_fmt(mat['nuxy'])}, {_fmt(mat['nu13'])}, {_fmt(mat['nu23'])}, "
                 f"{_fmt(mat['GXY'])}, {_fmt(mat['G13'])}")
        L.append(f"{_fmt(mat['G23'])}")
        L.append("*DENSITY")
        L.append(_fmt(mat["density"]))
    else:
        L.append("*ELASTIC")
        L.append(f"{_fmt(mat.youngs_modulus)}, {_fmt(mat.poisson_ratio)}")
        L.append("*DENSITY")
        L.append(_fmt(mat.density))

    # ---- boundary conditions -------------------------------------------- #
    # The set name follows the clamp group, so the deck text says which family
    # it describes; the freedom range is the builder's declaration, not a
    # constant - fixing 1..6 on a simply supported panel would clamp its edges
    # and turn a plate problem into something else entirely (and the deflection
    # would only be ~30 % smaller, which no numerical gate is looking at).
    root_nodes = groups.get(clamp_group, [])
    if root_nodes:
        nset = f"N{clamp_group.upper()}"
        L.append(f"*NSET, NSET={nset}")
        _emit_set(L, root_nodes)
        L.append("*BOUNDARY")
        L.append(f"{nset}, {int(clamp_dofs[0])}, {int(clamp_dofs[1])}, 0.0")

    # ---- step ----------------------------------------------------------- #
    if spec.analysis.step_type == "frequency":
        # C6-P1 (2026-11-07): eigenvalue step -- load-independent, so the load
        # block is omitted entirely; the BC block above stays outside the step,
        # which is valid for both dialects.  The eigenvalue table is printed to
        # .dat automatically by both solvers; the field request below is only
        # for mode shapes (frd / odb), never needed to read f1..f5.
        L.append("*STEP")
        n_modes = int(spec.analysis.n_modes)
        if dialect == "ccx":
            L.append("*FREQUENCY, SOLVER=ARPACK")
            # data line: number of eigenvalues, lower bound, upper bound
            L.append(f"{n_modes}, 0.0, 1.0e6")
            L.append("*NODE FILE")
            L.append("U")
        else:
            L.append("*FREQUENCY, EIGENSOLVER=LANCZOS")
            # data line: number of eigenvalues, low freq, high freq (0,0 = auto)
            L.append(f"{n_modes}, 0.0, 0.0")
            # *NODE FILE is results-file-only in Abaqus; field output -> ODB
            # (see _emit_output_requests docstring: the 2D abort lesson)
            L.append("*OUTPUT, FIELD, NUMBER INTERVAL=1")
            L.append("*NODE OUTPUT")
            L.append("U")
        L.append("*END STEP")
    else:
        L.append("*STEP, NLGEOM=NO")
        L.append("*STATIC")
        L.append(f"{_fmt(spec.analysis.initial_increment)}, {_fmt(spec.analysis.total_time)}")

        _emit_load(L, spec, elements, groups, load_group, pressure_group,
                   nodes, pressure_dload_sign)

        # ---- output requests ---------------------------------------------- #
        _emit_output_requests(L, dialect)
        L.append("*END STEP")

    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# dialect-specific blocks
# --------------------------------------------------------------------------- #
def _dialect_label(dialect: str) -> str:
    return {
        "ccx": "CalculiX deck, mm-tonne-s-MPa-N",
        "abaqus": "Abaqus deck, mm-tonne-s-MPa-N",
    }[dialect]


def _emit_output_requests(L: list[str], dialect: str) -> None:
    """Write the field-output request block for the chosen dialect.

    CalculiX
        ``OUTPUT=3D`` asks for the **expanded shell**: every mid-surface node
        becomes two nodes at ``+/- t/2``, so the result carries the outer fibre,
        which is the registered stress definition (D8, 2026-10-03).  The
        alternative, ``OUTPUT=2D``, keeps the mid-surface and reports the layer
        *mean* - measured on a 4-element plate that mean reproduces
        ``(top + bottom) / 2`` to 1.6e-4 relative, i.e. the bending term is
        averaged away and a plate in pure bending reports a von Mises of exactly
        zero.  The expanded result is folded back to the mid-surface (with the
        deck's own node labels restored) by
        :func:`feagpt.post.collapse_expanded_shell`, so downstream code still
        sees one mid-surface value per physical node.

        Do NOT put ``NSET=NALL`` on ``*NODE FILE``: with a node set specified,
        CalculiX 2.23 writes an empty DISP/FORC block (verified by experiment,
        not assumed).

    Abaqus
        ``*NODE FILE`` does not exist; the equivalent is ``*OUTPUT, FIELD``
        with ``*NODE OUTPUT`` / ``*ELEMENT OUTPUT`` sub-requests.  ``OUTPUT=2D``
        is a CalculiX-only parameter and makes Abaqus abort, which is exactly
        what happened on the first cross-solver attempt.

        Shell stress is stored per *section point*, so the reader picks the
        extreme one as ``STRESS_PEAK`` - see :mod:`feagpt.abaqus_odb`.
    """
    if dialect == "ccx":
        L.append("*NODE FILE, OUTPUT=3D")
        L.append("U, RF")
        L.append("*EL FILE, OUTPUT=3D")
        L.append("S, E")
    else:
        L.append("*OUTPUT, FIELD, NUMBER INTERVAL=1")
        L.append("*NODE OUTPUT")
        L.append("U, RF")
        L.append("*ELEMENT OUTPUT")
        L.append("S, E")


def _emit_load(L: list[str], spec: FEASpec, elements: dict, groups: dict,
               load_group: str = "tip", pressure_group: str = "upper_skin",
               nodes: dict | None = None,
               pressure_dload_sign: float = -1.0) -> float:
    """Write the load block; return the total applied force (N) for reporting.

    ``tip_force``
        Total force split equally over the ``load_group`` nodes, along the
        dominant direction component.
    ``pressure``
        Shell pressure (MPa) on ``pressure_group``, signed by
        ``pressure_dload_sign`` - the builder's declaration, not a writer
        constant.  See :attr:`feagpt.geometry.GeometryResult.pressure_dload_sign`
        for the measured reason the sign is family-specific (D21).

    A ``pressure`` case may *additionally* carry end loads in ``spec.extra``
    (``end_shear`` / ``end_moment``) - the fuselage barrel's combined load case
    (T3).  They act on the same ``load_group`` nodes (the free end frame) and are
    emitted as ``*CLOAD`` next to the ``*DLOAD``, so a single static step sees
    internal pressure + bending + shear together.  A wing box or panel carries
    no such keys and takes exactly the path it took before, byte for byte.
    """
    load = spec.load
    if load.kind == "tip_force":
        tip = groups.get(load_group, [])
        if not tip:
            return 0.0
        # pick the translational dof matching the dominant direction component
        # direction round-trips through JSON as a list, so normalise it first
        vec = [float(c) for c in (list(load.direction) + [0.0, 0.0, 0.0])[:3]]
        dof = max(range(3), key=lambda i: abs(vec[i])) + 1
        sign = 1.0 if vec[dof - 1] >= 0 else -1.0
        per_node = sign * abs(load.magnitude) / len(tip)
        rows: list[tuple[int, int, float]] = []
        if abs(float(load.magnitude)) > 0.0:
            rows.extend((nid, dof, per_node) for nid in tip)
        # T6: an optional in-plane couple on the same tip section.  Appended
        # *after* the force rows, and absent unless the spec asks for it, so a
        # case without the key emits the identical block it always did.
        rows.extend(_torque_rows(spec, tip, nodes))
        if not rows:
            return 0.0
        L.append("*CLOAD")
        for nid, d, val in rows:
            L.append(f"{nid}, {d}, {_fmt(val)}")
        return abs(load.magnitude)
    if load.kind == "pressure" and elements.get(pressure_group):
        # The magnitude is the *applied* pressure in MPa and the sign is the
        # builder's declaration (D21): a shell's normal orientation is a property
        # of how the surface was built, and the revolved barrel skin points the
        # opposite way to the extruded wing-box skin / the flat panel.  Hard-
        # coding ``-abs`` here pressurised the barrel from outside (-0.22725 mm
        # radial growth against a +0.228 mm closed form, verify_barrel.py).
        L.append("*DLOAD")
        L.append(f"E_{pressure_group.upper()}, P, "
                 f"{_fmt(pressure_dload_sign * abs(load.magnitude))}")
        return _emit_end_loads(L, spec, groups, load_group, nodes)
    return 0.0


def _torque_rows(spec: FEASpec, tip: list[int],
                 nodes: dict | None) -> list[tuple[int, int, float]]:
    """Emit an end torque as an in-plane couple on the tip section (T6).

    Why a couple and not nodal moments
        A single nodal moment on a shell produces a local spike no mesh
        resolves.  A torque about the spanwise axis is therefore built the way
        the barrel's end moment is (``_emit_end_loads``): as a **distributed**
        equivalent - here an in-plane tangential force ``F = t * r_perp`` about
        the section centroid, so its resultant moment about the axis is
        ``t * sum(r_i^2)``.

    Why the distribution is de-meaned and then rescaled
        The centroid is the *node* centroid, not the area centroid, so the raw
        tangential field leaves a small residual force.  Subtracting each
        component's mean makes ``sum(F) == 0`` **exactly**, which is what makes
        the result a pure couple rather than a couple with a force smuggled in.
        De-meaning changes the moment, so the field is then rescaled by
        ``M / M'`` - and because rescaling is homogeneous it leaves
        ``sum(F) == 0`` intact.  Both statements hold for the **rows this
        function returns**; formatted into the deck they inherit ``_fmt``'s
        output precision, so a re-summed block carries the same rounding every
        distributed load does (measured on the first web1 build: the couple's
        residual force 1.2e-4 N against the 500 N bending force, 2.4e-7
        relative).

    Axis
        ``extra["torque_axis_dof"]`` (default 3 = the spanwise ``z`` the wing box
        is extruded along).  Reads ``spec.extra["end_torque"]`` in N.mm; a case
        without the key contributes no rows at all.
    """
    extra = dict(getattr(spec, "extra", None) or {})
    torque = float(extra.get("end_torque", 0.0) or 0.0)
    if not torque or nodes is None:
        return []
    ids = [nid for nid in tip if nid in nodes]
    if len(ids) < 3:
        return []
    axis = int(extra.get("torque_axis_dof", 3) or 3)
    a1, a2 = {1: (1, 2), 2: (2, 0), 3: (0, 1)}[axis]     # in-plane dof pair

    pts = [nodes[nid] for nid in ids]
    c1 = sum(float(p[a1]) for p in pts) / len(pts)
    c2 = sum(float(p[a2]) for p in pts) / len(pts)
    r1 = [float(p[a1]) - c1 for p in pts]
    r2 = [float(p[a2]) - c2 for p in pts]

    f1 = [-v for v in r2]          # tangential: F_a1 = -r2, F_a2 = +r1
    f2 = list(r1)
    m1 = sum(f1) / len(f1)
    m2 = sum(f2) / len(f2)
    f1 = [v - m1 for v in f1]      # sum(F) == 0 exactly
    f2 = [v - m2 for v in f2]

    moment = sum(r1[i] * f2[i] - r2[i] * f1[i] for i in range(len(ids)))
    if abs(moment) < 1e-30:
        return []
    k = torque / moment            # rescale, preserving sum(F) == 0
    rows: list[tuple[int, int, float]] = []
    for i, nid in enumerate(ids):
        rows.append((nid, a1 + 1, k * f1[i]))
        rows.append((nid, a2 + 1, k * f2[i]))
    return rows


def _emit_end_loads(L: list[str], spec: FEASpec, groups: dict,
                    load_group: str, nodes: dict | None) -> float:
    """Emit a barrel's end shear and bending moment as ``*CLOAD`` (T3).

    Both act on the ``load_group`` nodes - the free end frame - and both must be
    *equivalent* distributions rather than point loads: a single nodal moment on
    a shell produces a local spike no mesh resolves, whereas a load spread over
    the ring is what a real end load looks like.

    * **shear** - an equal share ``V / n`` along ``shear_axis``.  Its resultant
      is exactly ``V`` by construction.
    * **moment** - an axial force ``F_i`` proportional to the node's distance
      from the ring's own centroid along the lever arm, scaled so that
      ``sum(F_i * lever_i) == M`` **numerically** rather than by assuming a
      uniform sampling.  Subtracting the mean makes ``sum(F_i) == 0`` exactly, so
      the distribution is a pure couple - no net axial force smuggled in.

    The barrel's axis is ``z`` (the builder extrudes the base circle along z), so
    a moment about ``x`` / ``y`` is carried by **axial** ``z`` forces with a lever
    arm along ``y`` / ``x``.  Returns the applied shear magnitude (N) for
    reporting; the moment contributes no net force.
    """
    extra = dict(getattr(spec, "extra", None) or {})
    shear = float(extra.get("end_shear", 0.0) or 0.0)
    moment = float(extra.get("end_moment", 0.0) or 0.0)
    if not (shear or moment):
        return 0.0
    tip = groups.get(load_group, [])
    if not tip:
        return 0.0

    rows: list[tuple[int, int, float]] = []

    if shear:
        vec = [float(c) for c in
               (list(extra.get("shear_axis") or (1.0, 0.0, 0.0)) + [0.0, 0.0, 0.0])[:3]]
        dof = max(range(3), key=lambda i: abs(vec[i])) + 1
        sign = 1.0 if vec[dof - 1] >= 0 else -1.0
        per = sign * abs(shear) / len(tip)
        rows.extend((nid, dof, per) for nid in tip)

    if moment and nodes is not None:
        vec = [float(c) for c in
               (list(extra.get("moment_axis") or (0.0, 1.0, 0.0)) + [0.0, 0.0, 0.0])[:3]]
        ax = max(range(3), key=lambda i: abs(vec[i])) + 1
        lever_dof = 2 if ax == 1 else 1      # about x -> lever y; about y -> lever x
        force_dof = 3                        # axial
        lev = {nid: float(nodes[nid][lever_dof - 1])
               for nid in tip if nid in nodes}
        if lev:
            mean = sum(lev.values()) / len(lev)
            centred = {nid: v - mean for nid, v in lev.items()}
            denom = sum(v * v for v in centred.values())
            if denom > 0.0:
                k = abs(moment) / denom
                sign = 1.0 if moment >= 0 else -1.0
                rows.extend((nid, force_dof, sign * k * c)
                            for nid, c in centred.items())

    if rows:
        L.append("*CLOAD")
        for nid, dof, val in rows:
            L.append(f"{nid}, {dof}, {_fmt(val)}")
    return abs(shear)


def _emit_set(L: list[str], tags: list[int], per_line: int = 16) -> None:
    for i in range(0, len(tags), per_line):
        L.append(", ".join(str(t) for t in tags[i:i + per_line]))


def _matname(mat) -> str:
    # T7: an orthotropic equivalent arrives as a plain dict (from
    # feagpt.laminate.equivalent_engineering_constants); the isotropic
    # MaterialSpec keeps arriving as the dataclass it always was.
    name = mat["name"] if isinstance(mat, dict) else mat.name
    return "".join(c if c.isalnum() else "_" for c in name).upper()[:20] or "MAT"


def _elem_keyword(name: str) -> str:
    return {"tri3": "S3", "quad4": "S4", "tri6": "S6", "quad9": "S9"}.get(name, "S4")


# --------------------------------------------------------------------------- #
# back-compatible entry points
# --------------------------------------------------------------------------- #
def write_ccx_inp(path, mesh: dict, spec: FEASpec, groups: dict | None = None) -> Path:
    """CalculiX deck (the historical entry point)."""
    return write_inp(path, mesh, spec, groups, dialect="ccx")


def write_abaqus_inp(path, mesh: dict, spec: FEASpec, groups: dict | None = None) -> Path:
    """Abaqus deck."""
    return write_inp(path, mesh, spec, groups, dialect="abaqus")
