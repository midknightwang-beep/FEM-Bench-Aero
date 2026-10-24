"""End-to-end orchestration of the GMSA pipeline.

This is stage orchestration *without* the LLM:

    spec (JSON)  ->  geometry  ->  mesh (+gate)  ->  deck  ->  solve  ->  results

Each stage writes its artifact into the case directory and the collected
metadata is returned as a single JSON-serialisable record, so a batch run over
hundreds of configurations is just a loop over specs.

Deliberately no LLM in this module - that keeps the engineering chain testable
and deterministic, which is the whole point of pinning it down behind a
specification.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import geometry, inp_writer, laminate, meshing, post, solver, topology
from .spec import FEASpec


@dataclass
class RunResult:
    name: str = ""
    ok: bool = False
    spec: dict = field(default_factory=dict)
    geometry: dict = field(default_factory=dict)
    mesh: dict = field(default_factory=dict)
    solve: dict = field(default_factory=dict)
    results: dict = field(default_factory=dict)
    stage_seconds: dict = field(default_factory=dict)
    artifacts: dict = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "ok": self.ok,
            "spec": self.spec,
            "geometry": self.geometry,
            "mesh": self.mesh,
            "solve": self.solve,
            "results": self.results,
            "stage_seconds": {k: round(v, 3) for k, v in self.stage_seconds.items()},
            "artifacts": self.artifacts,
            "messages": self.messages,
        }


_GROUP_ORDER = ("upper_skin", "lower_skin", "front_spar", "rear_spar",
                "stringers_upper", "stringers_lower", "ribs")
"""Canonical element-group order.

Wing-box group names, first and in this order, because the order decides the
running element-id counter in the deck - and therefore the bytes of every
archived ``.inp``.  Groups a family adds (``panel``, ``stringers``) are appended,
so a newer family changes nothing for the wing box.
"""


def _collect_groups(gmsh, surfaces: dict) -> dict[str, list[int]]:
    """Map logical geometry groups to their mesh elements and nodes."""
    tag2group: dict[int, str] = {}
    for g, tags in surfaces.items():
        for t in tags:
            tag2group[t] = g

    order = list(_GROUP_ORDER)
    for g in surfaces:
        if g not in order and g not in ("root", "tip"):
            order.append(g)

    elements: dict[str, list] = {g: [] for g in order}
    for dim, tag in gmsh.model.getEntities(2):
        g = tag2group.get(tag)
        if g is None:
            continue
        # The root rib carries the wing-box clamp; its elements still belong to
        # the rib group, because the deck needs a section for them.  A family
        # whose BC group is not an element group at all (the panel's ``edges``
        # is a set of nodes on the skin) simply never appears here.
        key = "ribs" if g in {"ribs", "root"} else g
        if key not in elements:
            continue
        et, etags, enodes = gmsh.model.mesh.getElements(2, tag)
        for t, nodes in zip(et, enodes):
            name, npe, fam = meshing._GMSH_ELEM.get(t, (None, 0, None))
            if fam != "surface":
                continue
            nodes = list(map(int, nodes))
            n = len(nodes) // npe
            for i in range(n):
                elements[key].append((name, nodes[i * npe:(i + 1) * npe]))
    return elements


def run(
    spec: FEASpec,
    outdir=None,
    step_export: bool = True,
    mesh_only: bool = False,
    deck_only: bool = False,
    solver_name: str | None = None,
    verbose: bool = False,
) -> RunResult:
    """Execute the whole chain for one specification.

    ``deck_only`` stops right after the input deck is written and returns with
    an **empty** ``res.solve``.  It exists because one of the two solvers cannot
    be launched from inside the agent sandbox (see README §6: Abaqus aborts in
    the input processor with an empty ODB skeleton).  Writing the deck here and
    solving it outside is the only reliable split, and keeping it as an explicit
    flag matters: ``res.ok`` is True but no solve happened, so a caller that
    reads ``res.solve`` gets nothing rather than a half-filled dict it might
    mistake for a result.
    """
    import gmsh

    outdir = Path(outdir or spec.workdir)
    outdir = outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    res = RunResult(name=spec.name)
    res.spec = spec.to_dict()
    spec.to_json(outdir / f"{spec.name}.spec.json")

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 1 if verbose else 0)
    gmsh.option.setNumber("General.Verbosity", 2 if verbose else 1)
    gmsh.model.add(spec.name)
    try:
        # ---- 1. geometry ------------------------------------------------ #
        t0 = time.time()
        step_path = (outdir / f"{spec.name}.step") if step_export else None
        # Dispatch on the structure family (M2).  Everything below this line is
        # family-agnostic: it only ever sees GeometryResult.
        geo = geometry.build(gmsh, spec, step_path=step_path)
        res.stage_seconds["geometry"] = time.time() - t0
        res.geometry = {
            "backend": geometry.geometry_backend(),
            "structure_family": spec.structure.family,
            "bc_groups": dict(geo.bc_groups),
            "n_surfaces": geo.n_surfaces,
            "n_curves": geo.n_curves,
            "shell_area_mm2": round(geo.shell_area, 2),
            "bounding_box": [round(v, 3) for v in geo.bounding_box],
            "groups": {k: len(v) for k, v in geo.surfaces.items()},
        }
        res.messages.extend(geo.notes)
        res.artifacts["step"] = str(step_path) if step_path and step_path.exists() else ""

        # ---- 2. mesh ---------------------------------------------------- #
        t0 = time.time()
        report = meshing.build_mesh(gmsh, spec, geo)
        res.stage_seconds["mesh"] = time.time() - t0
        res.mesh = report.to_dict()
        res.messages.extend(report.notes)
        if not report.passed:
            gmsh.finalize()
            res.ok = False
            res.messages.append("aborted after mesh quality gate")
            return res

        # ---- 2b. mesh artefact + semantic topology ---------------------- #
        # The .msh is one of the four A-subset deliverables (spec / step / msh
        # / inp) and belongs to *both* paths.  It used to be written only on the
        # mesh-only branch, so a fully solved case was missing its mesh - the
        # very artefact the modelling subset consumes.
        msh_path = outdir / f"{spec.name}.msh"
        gmsh.write(str(msh_path))
        res.artifacts["mesh"] = str(msh_path)

        # Independent reading of what was actually built, for gate 4.  Taken
        # here because this is the last point where the built geometry and its
        # surface groups are still alive.
        topo = topology.collect(gmsh, spec, geo)
        res.geometry["topology"] = topo
        res.messages.append(topology.gate_summary(topology.compare(topo)))

        if mesh_only:
            gmsh.finalize()
            res.ok = True
            return res

        # ---- 3. deck ---------------------------------------------------- #
        # The solver is resolved *before* the deck is written, because the two
        # codes speak different dialects and the choice of solver therefore
        # determines what has to be written (see inp_writer).  Deciding it
        # inside solver.run() would mean writing a deck for the wrong code.
        t0 = time.time()
        extracted = meshing.extract_mesh(gmsh)
        elements = _collect_groups(gmsh, geo.surfaces)

        # Drop nodes that no element refers to (gmsh emits them for curves and
        # points that belong to no surface).  Skipping this dilutes any load
        # spread over "all nodes at the tip" and makes Abaqus abort outright -
        # see meshing.referenced_nodes for the full story.
        nodes, dropped = meshing.referenced_nodes(extracted["nodes"], elements)
        if dropped:
            res.messages.append(
                f"dropped {len(dropped)} unreferenced mesh node(s) "
                f"({len(extracted['nodes'])} -> {len(nodes)}); they carry no "
                f"stiffness but would dilute nodal loads and abort Abaqus"
            )

        prefer = solver_name or spec.analysis.solver
        picked = solver.find_solver(prefer)
        solver_resolved = picked[0] if picked else "ccx"
        dialect = solver.dialect_for(solver_resolved)

        # Boundary-condition node sets.  The *names* of the BC groups come from
        # the builder (geo.bc_groups) and so do the nodes themselves
        # (geo.resolve_bc_nodes): a wing box clamps its root rib (everything at
        # z ~ 0) and loads its tip, a stiffened panel supports its four edges.
        # The old expression lived here as `abs(z) < 1e-6`, which is a wing-box
        # convention wearing the disguise of a general rule - it would have
        # selected an entire flat panel (the whole skin sits at z = 0) as "the
        # clamped edge".  Its default reproduces those two lines exactly, which
        # is why the archived cases do not move.
        bc_node_groups = geo.resolve_bc_nodes(nodes)
        # T7: a layup in the family params converts to its CLT equivalent
        # single layer right here - the deck carries the equivalent, the spec
        # carries the true stack (two different files, two different truths,
        # linked by the total-thickness check inside layup_from_params).
        # Specs without the "layup" key - every archived case - take the
        # isotropic path byte-identically.
        layup = laminate.layup_from_params(spec.structure.params)
        ortho = (laminate.equivalent_engineering_constants(layup)
                 if layup is not None else None)
        deck = inp_writer.write_inp(
            outdir / f"{spec.name}.inp",
            {"nodes": nodes, "elements": elements},
            spec,
            groups=bc_node_groups,
            dialect=dialect,
            bc_groups=geo.bc_groups,
            thickness=geo.shell_thickness or None,
            clamp_dofs=geo.clamp_dofs,
            pressure_group=geo.pressure_group,
            # D21: which way ``*DLOAD ... P`` must be signed is the *builder's*
            # declaration, because it depends on how the family's surfaces were
            # built (a revolved barrel skin points opposite an extruded wing-box
            # skin).  Passing it here is what makes the family's claim reach the
            # deck; check_forms.check_T3 proves both halves.
            pressure_dload_sign=geo.pressure_dload_sign,
            ortho_material=ortho,
        )
        res.stage_seconds["deck"] = time.time() - t0
        res.artifacts["inp"] = str(deck)
        res.mesh["n_nodes_active"] = len(nodes)
        res.mesh["n_nodes_orphan"] = len(dropped)
        res.messages.append(f"deck written ({dialect}): {len(nodes)} active nodes, "
                            f"{sum(len(v) for v in elements.values())} shell elements "
                            f"in {sum(1 for v in elements.values() if v)} group(s)")

        gmsh.finalize()

        if deck_only:
            # Nothing has been solved.  Say so in the messages rather than
            # leaving res.solve as an empty dict that reads like "no fields".
            res.messages.append("deck-only: stopped before solve -- run the "
                                "solver outside the sandbox")
            res.ok = True
            return res

        # ---- 4. solve --------------------------------------------------- #
        t0 = time.time()
        solved = solver.run(deck, solver=solver_resolved)
        res.stage_seconds["solve"] = time.time() - t0
        res.solve = solved.to_dict()
        res.artifacts["frd"] = solved.frd
        res.artifacts["odb"] = solved.odb
        if not solved.ok:
            res.messages.append(f"solver failed: {solved.log[-400:]}")
            return res

        # ---- 5. results ------------------------------------------------- #
        # One reduction path for both solvers: FRD text for CalculiX, the
        # ODB-derived JSON for Abaqus.  Nothing downstream branches on solver.
        t0 = time.time()
        source = solved.results_json or solved.frd
        data = post.load_any(source)
        if data.get("meta"):
            res.solve["odb_meta"] = data["meta"].get("blocks", {})
        summary = post.dump_results_data(
            data,
            outdir / f"{spec.name}.results.json",
            out_json_csv := outdir / f"{spec.name}.nodes.csv",
        )
        res.stage_seconds["post"] = time.time() - t0
        res.results = summary
        res.artifacts["results"] = str(outdir / f"{spec.name}.results.json")
        res.artifacts["nodes_csv"] = str(out_json_csv)

        # ---- 6. semantic truth ------------------------------------------ #
        # Both topology readings plus the derived expectation and the scalar
        # truth, in one document.  Written last because it folds the result
        # scalars in with the geometry read back before solving.
        truth = topology.build_truth(spec, topo, summary, solver_resolved)
        truth_path = outdir / f"{spec.name}.truth.json"
        truth_path.write_text(
            json.dumps(truth, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        res.artifacts["truth"] = str(truth_path)
        res.ok = True
        return res
    finally:
        try:
            # gmsh may already be finalised on the early-return paths
            if gmsh.isInitialized():
                gmsh.finalize()
        except Exception:
            pass


def run_batch(specs, outroot=None, **kwargs) -> list[RunResult]:
    """Run several specs; each gets its own sub-directory."""
    outroot = Path(outroot or "outputs")
    out: list[RunResult] = []
    for s in specs:
        d = outroot / s.name
        out.append(run(s, outdir=d, **kwargs))
    return out
