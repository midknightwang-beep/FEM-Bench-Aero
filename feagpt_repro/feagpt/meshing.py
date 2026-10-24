"""Mesh generation and quality gating.

FeaGPT applies *physics-aware adaptive* meshing through Gmsh, refining where
the geometry is critical (high curvature, thin walls).  That behaviour is
reproduced here with a Gmsh size field built from:

* a ``Curvature`` field - resolves the leading edge and the spar corners;
* a ``Threshold`` field on the distance to the section, which keeps the ribs
  from being meshed coarsely; and
* an absolute floor/ceiling from :class:`~feagpt.spec.MeshSpec`.

The stage is gated on three things: the minimum scaled Jacobian must clear the
threshold in the spec, the mesh must be non-empty, and it must contain **no
triangles**.  This is the "Jacobian and topology check" that FeaGPT reports for
all 432 NACA4412 configurations - here it is reproduced as an explicit abort
condition rather than a claim.

The triangle half of that sentence went unmeasured from M1 to M3 and turned out
to be false on two archived cases.  It is now measured, and :func:`build_mesh`
re-meshes with a stronger recombination algorithm instead of aborting when the
model is fixable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .spec import FEASpec


@dataclass
class MeshReport:
    n_nodes: int = 0
    n_elements: int = 0
    element_types: dict[str, int] = field(default_factory=dict)
    tri_count: int = 0
    """Triangle count, i.e. half of gate 1 that went unchecked from M1 to M3.

    It was always quoted as "zero tri3"; in 2026-10-03 it was finally *measured*
    and two archived cases failed it.  Stored rather than recomputed so the
    number ships inside ``truth.json`` with the mesh it describes.
    """
    min_quality: float = 0.0
    mean_quality: float = 0.0
    max_edge: float = 0.0
    min_edge: float = 0.0
    dof: int = 0
    passed: bool = False
    recombination_algorithm: int = 0
    """The gmsh recombination algorithm the surviving mesh was built with.

    Not always what the spec asked for: :func:`build_mesh` escalates ``1 -> 3``
    when the first pass leaves triangles, and this records which one produced
    the mesh that is actually in the archive.
    """
    escalated_from: int = 0
    """Non-zero when the escalation fired, holding the algorithm that failed."""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_nodes": self.n_nodes,
            "n_elements": self.n_elements,
            "element_types": self.element_types,
            "tri_count": self.tri_count,
            "min_quality": round(self.min_quality, 4),
            "mean_quality": round(self.mean_quality, 4),
            "max_edge": round(self.max_edge, 3),
            "min_edge": round(self.min_edge, 3),
            "dof": self.dof,
            "passed": self.passed,
            "recombination_algorithm": self.recombination_algorithm,
            "escalated_from": self.escalated_from,
            "notes": self.notes,
        }


# gmsh element type -> (name, nodes-per-element, family)
_GMSH_ELEM = {
    1: ("line2", 2, "line"),
    2: ("tri3", 3, "surface"),
    3: ("quad4", 4, "surface"),
    8: ("line3", 3, "line"),
    9: ("tri6", 6, "surface"),
    10: ("quad9", 9, "surface"),
}

# name -> CalculiX/Abaqus element keyword
_CCX_ELEM = {
    "tri3": "S3",
    "quad4": "S4",
    "tri6": "S6",
    "quad9": "S9",
}


def _configure_size_field(gmsh, spec: FEASpec, geom,
                          recombination_algorithm: int | None = None) -> None:
    """Curvature-driven adaptive sizing.

    FeaGPT refines where the geometry is critical (high curvature, thin walls).
    gmsh's dedicated ``Curvature`` *field* exposes no scriptable options in
    4.15 (verified: every documented option name is rejected), so the
    equivalent global controls are used instead:

    * ``Mesh.MeshSizeFromCurvature`` - N elements per 2*pi of curvature, which
      is what packs elements at the leading edge and the spar corners;
    * ``Mesh.MeshSizeExtendFromBoundary`` - propagates that spacing inwards;
    * ``Mesh.MeshSizeMin/Max`` - the absolute floor and ceiling from the spec.
    """
    ms = spec.mesh
    # A family may declare how finely its curved features must be cut (T4's
    # hole edge).  ``None`` - every pre-T4 model - keeps the historical
    # ``24 if refine_at_leading_edge else 0``, so no archived mesh moves.  This
    # is the *only* knob that works on this toolchain: a per-curve
    # ``gmsh.model.mesh.setSize`` is accepted and then ignored (measured, see
    # ``GeometryResult.curvature_target``).
    curvature = getattr(geom, "curvature_target", None)
    gmsh.option.setNumber(
        "Mesh.MeshSizeFromCurvature",
        float(curvature) if curvature else (24.0 if ms.refine_at_leading_edge else 0.0),
    )
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 1.0)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 1.0)
    gmsh.option.setNumber("Mesh.MeshSizeMin", max(ms.size_chord / 6.0, 0.5))
    # A builder may declare a ceiling when the model contains a strip the
    # default size cannot resolve (a T stringer's flange half, measured).  A
    # model that declares nothing - which is every pre-M3 case, and every blade
    # model - takes the unchanged path, keeping the archive bit-identical.
    size_max = float(ms.size_span)
    cap = getattr(geom, "mesh_size_cap", None)
    if cap:
        size_max = min(size_max, float(cap))
    gmsh.option.setNumber("Mesh.MeshSizeMax", size_max)
    gmsh.option.setNumber("Mesh.Algorithm", int(ms.algorithm_2d))
    if ms.recombine:
        gmsh.option.setNumber("Mesh.RecombineAll", 1)
        gmsh.option.setNumber(
            "Mesh.RecombinationAlgorithm",
            _recombination_algorithm(ms, geom)
            if recombination_algorithm is None else int(recombination_algorithm),
        )
    if ms.element_order == 2:
        gmsh.option.setNumber("Mesh.ElementOrder", 2)


def _recombination_algorithm(ms, geom) -> int:
    """Which gmsh recombination algorithm this model should use (``0`` = auto).

    A blade stringer is a long, thin strip (20 x 500 mm here).  Gmsh's default
    blossom recombination handles it poorly: measured on the 3-stringer box it
    left 6 % triangles and drove the minimum scaled Jacobian down to 0.40, with
    the worst elements **all** on the stringers (the skins stayed above 0.52).
    Blossom *full-quad* clears it completely - no triangles, stringer Jacobian
    0.69, at the cost of 6 % more elements.

    It is not a universal improvement, though: on the stringer-free box blossom
    alone gives a higher minimum Jacobian (0.625 vs 0.573), so the automatic
    choice is made per model rather than globally.  ``geom`` is the
    :class:`~feagpt.geometry.GeometryResult`, which is None in the standalone
    cantilever verification.

    This is the *first* of two decisions.  It sees only the geometry, and the
    ``chord800`` boxes showed that a model can look unremarkable here and still
    come out with triangles -- so :func:`build_mesh` counts them after the fact
    and escalates to full-quad if the count is not zero.  Keeping the two
    separate is deliberate: this one is cheap and decides the common case, the
    other costs a second mesh pass and only fires on the models that need it.
    """
    explicit = int(getattr(ms, "recombination_algorithm", 0))
    if explicit > 0:
        return explicit
    # A family may declare that full-quad is unavailable for its faces: a closed
    # (periodic) surface cannot be full-quad recombined at all ("Full-quad
    # recombination not ready yet for periodic surfaces"), and a fuselage
    # barrel's swept patches cannot either ("1D mesh cannot be divided by 2",
    # measured on the shipped path for every cap).  Declared by the builder as
    # ``blossom_only`` rather than sniffed here, because it is a property of the
    # geometry no logical group name could carry - and it must be pinned *before*
    # the strip heuristic below, which would otherwise pick 3 and crash before
    # the quality gate ever ran.
    if getattr(geom, "blossom_only", False):
        return 1
    surfaces = getattr(geom, "surfaces", None) or {}
    # Any group named ``stringers*`` holds long thin strips: the wing box's
    # ``stringers_upper``/``stringers_lower`` and the stiffened panel's
    # ``stringers``.  Matching the family-agnostic prefix keeps the wing box
    # exactly as it was while a new family gets the same treatment by naming
    # its strips the same way.
    has_strips = any(k.startswith("stringers") and v for k, v in surfaces.items())
    return 3 if has_strips else 1


def build_mesh(gmsh, spec: FEASpec, geom) -> MeshReport:
    """Generate the shell mesh and run the quality gate.

    Gate 1 is "min scaled Jacobian >= threshold **and no triangles**".  From M1
    to M3 only the first half was ever evaluated, and on 2026-10-03 the second
    half turned out to be false: the two ``chord800`` wing boxes shipped 8 and
    16 ``S3`` elements.  All 24 sit in the corners of the **rear spar web**
    (``x = 0.7 * chord``), which is 58.4 mm tall against a 12 mm chordwise size
    -- 4.87 elements across, and blossom recombination fills the leftover
    corner with a triangle.

    Patching those two cases by hand would leave the archive depending on
    somebody remembering which models are special, so the choice is made per
    model: mesh once with the algorithm the model asks for, count triangles,
    and if there are any -- and the spec did not pin an algorithm -- re-mesh
    once with blossom **full-quad**.  Measured on ``n_ribs3_chord800``, 8 -> 0
    triangles for +0.5 % elements at minJ 0.5973 -> 0.5950, and on
    ``n_ribs5_chord800`` 16 -> 0 for +4.8 %.  The alternatives were measured
    too and rejected (``diagnostics/probe_tri3.py``): ``Mesh.Recombine
    OptimizeTopology`` does not change a thing (still 8 / 16), simple full-quad
    costs +8.4 % / +14.1 %, and ``Mesh.Algorithm=8`` is far worse (18 / 28
    triangles and minJ 0.024, i.e. it would have failed the *Jacobian* gate).

    A model whose first pass is already clean takes exactly the old path and
    produces a bit-identical mesh: verified for every other archived case,
    including all nine M2 seed models (the ``chord1000`` boxes, the
    ``stringers*`` models that already select algorithm 3, and the panels).
    """
    explicit = int(getattr(spec.mesh, "recombination_algorithm", 0))
    algo = _recombination_algorithm(spec.mesh, geom)
    report = _mesh_and_census(gmsh, spec, geom, algo)
    if report.tri_count and explicit == 0 and algo != 3:
        if getattr(geom, "blossom_only", False):
            # The escalation is *unavailable*, not unwanted: escalation's only
            # target (full-quad) is exactly the algorithm that aborts on this
            # family's faces, so a second pass would raise instead of improving
            # anything.  Say so and let the gate report the triangles honestly
            # rather than crashing the run - "cannot be fixed here" is a
            # different statement from "was fixed".
            report.notes.append(
                f"kept {report.tri_count} triangle(s): full-quad escalation is "
                f"unavailable on this model's faces (declared by the builder)"
            )
        else:
            left = report.tri_count
            gmsh.model.mesh.clear()
            report = _mesh_and_census(gmsh, spec, geom, 3, escalated=True)
            report.escalated_from = algo
            report.notes.append(
                f"recombination escalated {algo} -> 3 (blossom full-quad): the "
                f"first pass left {left} triangle(s)"
            )
    return report


def _mesh_and_census(gmsh, spec: FEASpec, geom, algo: int,
                     escalated: bool = False) -> MeshReport:
    """One generate pass under ``algo``, then the census and the gate verdict."""
    _configure_size_field(gmsh, spec, geom, recombination_algorithm=algo)
    gmsh.model.mesh.generate(2)

    # ---- collect element statistics ------------------------------------- #
    report = MeshReport()
    report.recombination_algorithm = algo
    explicit = int(getattr(spec.mesh, "recombination_algorithm", 0))
    # The reason has to be read off *how* algo was picked, not off its value:
    # an escalated model ends up with algo 3 while having no stiffener strips,
    # and labelling that "chosen automatically for thin stiffener strips" would
    # be a claim about a geometry this model does not have.
    if explicit:
        algo_note = f"recombination algorithm {algo} (explicit)"
    elif escalated:
        algo_note = f"recombination algorithm {algo} (blossom full-quad, escalated)"
    elif algo == 3:
        algo_note = ("recombination algorithm 3 (blossom full-quad, chosen "
                     "automatically for thin stiffener strips)")
    else:
        algo_note = f"recombination algorithm {algo} (blossom)"
    report.notes.append(algo_note)
    node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
    report.n_nodes = len(node_tags)

    etypes: dict[int, int] = {}
    all_tags: list[int] = []
    for dim, tag in gmsh.model.getEntities(2):
        et, etags, _ = gmsh.model.mesh.getElements(2, tag)
        for t, tg in zip(et, etags):
            etypes[t] = etypes.get(t, 0) + len(tg)
            all_tags.extend(tg)

    report.n_elements = len(all_tags)
    report.element_types = {
        _GMSH_ELEM.get(t, (f"type{t}", 0, "?"))[0]: n for t, n in sorted(etypes.items())
    }
    # gmsh type 2 = tri3, 9 = tri6 (element_order 2).  The gate below is the
    # only place in the pipeline that has ever looked at this number.
    report.tri_count = sum(n for t, n in etypes.items() if t in (2, 9))
    # shell element with 6 dof/node would be 6 per node; CalculiX S4 uses 6.
    report.dof = report.n_nodes * 6

    # ---- quality (scaled Jacobian / minSICN in (-1, 1]) ----------------- #
    if all_tags:
        try:
            q = gmsh.model.mesh.getElementQualities(all_tags, "minSICN")
            q = [float(v) for v in q]
            report.min_quality = min(q)
            report.mean_quality = sum(q) / len(q)
        except Exception as exc:  # pragma: no cover
            report.notes.append(f"quality probe failed: {exc}")

    # ---- edge-length statistics ----------------------------------------- #
    # One ``getNodes()`` call for the whole model, then vectorised edge norms.
    # This replaces a per-node loop (``getNode`` called four times inside the
    # element loop): same arithmetic - the norm of each consecutive node pair,
    # which is exactly what the old loop accumulated - but the old form issues
    # ~4 FFI calls *per element*, i.e. ~6e5 on the fuselage barrel's
    # 1.6e5-element mesh, where it dominated the entire build (a single barrel
    # fingerprint took ~1 min at 25 mm, and the same builder at a mistaken 3 mm
    # - 1.4e6 elements - is what turned ``check_forms --only T3`` into a 19.6 min
    # run that ended in a native stack overflow; see check_forms' module
    # docstring).  ``max_edge`` / ``min_edge`` ride only in the working
    # ``batch_summary.json``; no archived case or gate reads them, so this is a
    # cost fix, not a change of any measured number.
    node_arr = np.asarray(node_tags, dtype=np.int64)
    coord_arr = np.asarray(node_coords, dtype=float).reshape(-1, 3)

    blocks: list[np.ndarray] = []
    for dim, tag in gmsh.model.getEntities(2):
        et, etags, enodes = gmsh.model.mesh.getElements(2, tag)
        for t, nodes in zip(et, enodes):
            _name, npe, fam = _GMSH_ELEM.get(t, ("?", 0, "?"))
            if fam != "surface" or npe <= 0:
                continue
            blocks.append(np.asarray(nodes, dtype=np.int64).reshape(-1, npe))
    if blocks:
        # Per block, not one vstack: a model may hold more than one surface
        # element type (a barrel that left triangles next to its quads), and
        # quad blocks and tri blocks have different widths.  Each block is still
        # computed in one vectorised pass.
        order = np.argsort(node_arr)
        emax, emin = 0.0, float("inf")
        for conn in blocks:
            pos = np.searchsorted(node_arr, conn, sorter=order)
            xyz = coord_arr[order[pos]]                  # (n_elem, npe, 3)
            seg = np.linalg.norm(xyz - np.roll(xyz, -1, axis=1), axis=2)
            if seg.size:
                emax = max(emax, float(seg.max()))
                emin = min(emin, float(seg.min()))
        if emin < float("inf"):
            report.max_edge = emax
            report.min_edge = emin

    # ---- gate ------------------------------------------------------------ #
    report.passed = (
        report.min_quality >= spec.mesh.min_jacobian
        and report.n_elements > 0
        and report.tri_count == 0
    )
    if not report.passed:
        reasons = []
        if report.min_quality < spec.mesh.min_jacobian:
            reasons.append(f"min scaled Jacobian {report.min_quality:.3f} "
                           f"< threshold {spec.mesh.min_jacobian:.2f}")
        if report.tri_count:
            reasons.append(f"{report.tri_count} triangle(s)")
        if report.n_elements <= 0:
            reasons.append("no elements")
        report.notes.append("quality gate FAILED: " + "; ".join(reasons))
    else:
        report.notes.append(
            f"quality gate passed: min scaled Jacobian {report.min_quality:.3f}, "
            f"{report.tri_count} triangle(s)"
        )
    return report


def element_keyword(name: str) -> str:
    """Map an internal element name to its CalculiX/Abaqus keyword."""
    return _CCX_ELEM.get(name, "S4")


def referenced_nodes(nodes: dict, elements: dict) -> tuple[dict, list[int]]:
    """Split mesh nodes into the ones some element uses, and the rest.

    Gmsh meshes *entities*, not just the surface we care about: it also emits
    nodes for curves and points that end up belonging to no surface element.
    On the NACA4412 wing box that is 396 nodes out of 4997 - real entries in the
    node table, connected to nothing.

    They are not harmless, and the failure mode is silent:

    * a load distributed over "all nodes at the tip" is spread across nodes that
      carry no stiffness, so the applied force is quietly diluted.  On the
      original wing box 500 N was divided over 190 tip nodes of which only 124
      existed in the model, and the root reactions summed to **326.32 N** - the
      equilibrium check caught it, nothing else would have;
    * CalculiX tolerated them, Abaqus did not: it deleted the 396 nodes, then
      aborted with 67 fatal errors "a concentrated load has been specified on
      node N, this node is not active in the model".

    A node no element references cannot affect the solution, so removing it is
    physics-neutral and makes the deck self-consistent for either solver.
    """
    used: set[int] = set()
    for group in elements.values():
        for _name, conn in group:
            used.update(conn)
    kept = {t: xyz for t, xyz in nodes.items() if t in used}
    dropped = sorted(set(nodes) - used)
    return kept, dropped


def extract_mesh(gmsh) -> dict[str, Any]:
    """Pull nodes and surface elements out of Gmsh into plain Python lists."""
    node_tags, coords, _ = gmsh.model.mesh.getNodes()
    nodes = {int(t): tuple(map(float, coords[3 * i:3 * i + 3])) for i, t in enumerate(node_tags)}

    elems: list[tuple[str, list[int]]] = []
    for dim, tag in gmsh.model.getEntities(2):
        et, etags, enodes = gmsh.model.mesh.getElements(2, tag)
        for t, nodes_arr in zip(et, enodes):
            name, npe, fam = _GMSH_ELEM.get(t, (None, 0, None))
            if fam != "surface":
                continue
            nodes_arr = list(map(int, nodes_arr))
            n = len(nodes_arr) // npe
            for i in range(n):
                elems.append((name, nodes_arr[i * npe:(i + 1) * npe]))
    return {"nodes": nodes, "elements": elems}
