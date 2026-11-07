"""Standardised JSON specification - the contract between pipeline stages.

FeaGPT (Qi, Xu & Chu, 2025, arXiv:2510.21993) decouples its five stages
(planning, geometry, meshing, simulation, analysis) through a *structured
JSON specification*.  Reproducing that contract is the single most important
part of the reproduction, because it is what lets the natural-language layer
be swapped for a human, a rule engine, or a different LLM without touching
the engineering back-end.

Everything downstream of the planner consumes (and only consumes) an
:class:`FEASpec`.  Units follow the mm-tonne-s-MPa system used by
CalculiX/Abaqus so that no unit conversion is needed in the solver deck.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# leaf specs
# --------------------------------------------------------------------------- #


@dataclass
class MaterialSpec:
    """Isotropic linear-elastic material (mm-tonne-s-MPa)."""

    name: str = "Aluminium 2024-T3"
    youngs_modulus: float = 73100.0      # MPa
    poisson_ratio: float = 0.33
    density: float = 2.78e-9             # tonne/mm^3
    yield_strength: float | None = 345.0  # MPa, used only for reporting


@dataclass
class AirfoilSpec:
    """Parametric description of the wing box to be generated."""

    code: str = "4412"          # NACA 4-digit
    chord: float = 1000.0       # mm
    span: float = 2000.0        # mm
    skin_thickness: float = 3.0  # mm
    n_ribs: int = 5             # including both ends
    rib_thickness: float = 4.0   # mm
    spar_chordwise: tuple[float, float] = (0.25, 0.70)
    """Front / rear spar positions as fractions of chord."""
    n_stringers_per_skin: int = 0
    """Blade stringers on each of the upper and lower skin (0 = stiffener-free).

    Defaults to 0 so that the baseline case stays stiffener-free; switch them on
    explicitly (``--stringers N`` or ``airfoil.n_stringers_per_skin``) to study
    their effect.  Stringers are vertical webs running the full span, bonded to
    the skin along their top edge and free along the bottom - the usual
    idealisation of a blade (standing) stringer in a thin-walled box.
    """
    stringer_height: float = 20.0
    """Blade-stringer depth (mm).  Clamped to 35% of the local box height so a
    stringer can never reach the opposite skin."""
    stringer_thickness: float = 2.5
    """Stringer wall thickness (mm)."""
    stringer_kind: str = "blade"
    """Stringer cross-section family (M3 / task T5).

    ``"blade"`` is the M1/M2 shape - one vertical web - and stays the default so
    every archived case rebuilds unchanged.  ``"T"`` adds a flange across the
    free edge (see :data:`feagpt.sections.SECTIONS`); unknown kinds raise rather
    than fall back to blade.  The wing box keeps its stringer parameters here
    (legacy ``airfoil`` block, see :class:`StructureSpec`), whereas a family
    added from M3 onward carries them under ``structure.params``.
    """
    stringer_flange_width: float = 30.0
    """Flange width (mm) for flanged sections; ignored by ``blade``."""

    tip_chord_ratio: float = 1.0
    """Tip chord divided by root chord (``1.0`` = constant chord).  Task T1.

    Planform parameter of the swept / tapered wing box.  ``1.0`` is the
    **prismatic** value: with :attr:`sweep_deg` also at 0 the section does not
    vary along the span and the builder keeps the M1 extrusion path, which is
    what holds every archived case bit-identical.
    """
    sweep_deg: float = 0.0
    """Leading-edge sweep angle in degrees; positive = swept back.  Task T1.

    **The leading edge is the reference line (decision D14).**  The tip section
    is the root section scaled by :attr:`tip_chord_ratio` *about its leading
    edge*, then translated aft by ``span * tan(sweep_deg)``.  With taper the
    trailing edge therefore sweeps more than the leading edge, and the spars -
    pinned at ``spar_chordwise`` fractions of the chord - drift spanwise, which
    is the property T1 exists to exercise.

    The reference line was a genuine fork, not a default: with taper an
    LE-referenced and a quarter-chord-referenced angle give *different* shapes,
    and the quarter-chord reading would leave the front spar (at 0.25c) exactly
    straight - contradicting "the spars drift spanwise".  See
    ``check_forms.check_T1``.
    """
    web_chordwise: tuple[float, ...] = ()
    """Intermediate web stations as fractions of chord; task T6.

    A web runs the **full box height** - bonded to both skins - so it cuts the
    box's single cell into ``len(web_chordwise) + 1`` cells.  That is exactly
    what separates it from a stringer: a stringer is bonded to one skin only and
    adds no cell no matter how many of them there are
    (:attr:`n_stringers_per_skin`).  Two knobs that look alike, one structural
    dimension each.

    The empty tuple is the **neutral** value: no intermediate web, one cell, and
    the M1 geometry bit for bit - which is why every archived case keeps its
    mesh when the field arrives.

    Positions are stored rather than a count (contrast
    :attr:`n_stringers_per_skin`, which stores a count and derives its stations)
    because **position is a dimension of its own here**: moving a web off the
    even in-board spacing makes the cells unequal, which is a shape no analytic
    result in the chain describes - Bredt-Batho's yardstick is the symmetric,
    equally-divided box.  See :meth:`even_web_stations`,
    ``check_forms.check_T6`` and ``verify_multi_cell.py``.
    """

    @property
    def is_prismatic(self) -> bool:
        """True when the section does not vary along the span.

        The builder routes on this to reach the M1 extrusion path - the one
        every archived case was meshed and solved on.  A loft between two
        *identical* sections is geometrically the same shape but a different
        OCC surface, and it meshes differently (measured on the baseline size
        field: 4753 nodes / 4251 quads lofts vs 4418 / 4300 extrudes), so the
        neutral case must not be sent through it.
        """
        return self.tip_chord_ratio == 1.0 and self.sweep_deg == 0.0

    # ------------------------------------------------------------------ #
    # T6 derived readings - one definition, shared by geometry and the rule
    # ------------------------------------------------------------------ #
    # These live here rather than in the builder because **two** consumers must
    # agree on them: ``geometry.build_wingbox`` places the webs, and
    # ``manifest`` decides a case's role/side by asking whether the placement is
    # the even one.  Two copies of "even spacing" is one copy too many - they
    # would drift, and the drift would show up as a case silently changing side.
    @property
    def n_webs(self) -> int:
        """Number of intermediate webs (0 = single cell)."""
        return len(self.web_chordwise)

    @property
    def n_cells(self) -> int:
        """Cells the box section is divided into - the structural dimension.

        ``n_webs + 1``: the cell count is what the load path sees, and it is the
        quantity Bredt-Batho's torsion stiffness is a function of, so it is the
        reading a case is *about* rather than the web count that produces it.
        """
        return len(self.web_chordwise) + 1

    def even_web_stations(self, n: int | None = None) -> tuple[float, ...]:
        """The even, in-board spacing for ``n`` webs (default: the ones asked for).

        The position a web takes when the spec only asked for *count*: ``n``
        webs cutting the box into ``n + 1`` equal cells, strictly between the
        spars.  The analogue of ``n_stringers_per_skin`` -> ``_stringer_stations``
        for the stringers, and the reference the rules compare against - so
        "off-centre" means precisely "not this".
        """
        k = len(self.web_chordwise) if n is None else int(n)
        x_f, x_r = (float(v) for v in self.spar_chordwise)
        return tuple(x_f + (x_r - x_f) * (j + 1) / (k + 1) for j in range(k))

    @property
    def webs_are_even(self) -> bool:
        """True when every web sits at its even in-board station.

        False for the neutral (no-web) box: "the webs are evenly spaced" is a
        statement about webs that exist, and an empty box has none to space.
        """
        even = self.even_web_stations()
        if not self.web_chordwise:
            return False
        return all(abs(float(a) - float(b)) < 1e-9
                   for a, b in zip(self.web_chordwise, even))


@dataclass
class StructureSpec:
    """Which structural family the case describes (the M2 abstraction).

    ``family`` is the key into :data:`feagpt.geometry.BUILDERS` - it selects the
    builder, and nothing downstream of geometry needs to know about it, because
    every builder returns the same :class:`~feagpt.geometry.GeometryResult`.

    Where a family's parameters live
        The wing box (``family="wingbox"``) keeps its parameters in the legacy
        :class:`AirfoilSpec` block, so every M1 artefact still loads and rebuilds
        unchanged - moving them would have invalidated the whole archived set for
        no engineering gain.  Families added from M3 onward carry their own
        parameters under ``params``, which the family's builder interprets;
        nothing outside that builder reads them.  The two are not merged: a
        wing box simply *has* an ``airfoil`` block, and a stiffened panel will
        have ``params`` instead.
    """

    family: str = "wingbox"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class MeshSpec:
    """Gmsh controls.  Sizes are absolute lengths in mm."""

    element_order: int = 1          # 1 = linear shell, 2 = quadratic
    size_chord: float = 12.0        # target size on the airfoil section
    size_span: float = 25.0         # target size along the span
    refine_at_leading_edge: bool = True
    leading_edge_threshold: float = 1.6  # curvature multiplier triggering refinement
    min_jacobian: float = 0.30      # quality gate, abort below this
    algorithm_2d: int = 6           # gmsh Mesh.Algorithm (6 = Frontal-Delaunay)
    recombine: bool = True          # try to produce quads (S4)
    recombination_algorithm: int = 0
    """gmsh ``Mesh.RecombinationAlgorithm``: 1 = blossom, 3 = blossom full-quad.

    ``0`` means **auto**: the meshing stage picks 3 when the model contains thin
    stiffener strips (blade stringers) and 1 otherwise.  Blossom alone leaves
    triangles and badly shaped quads on a 20 x 500 mm strip (measured: min
    scaled Jacobian 0.40, 6 % triangles); full-quad fixes exactly that
    (0.69, no triangles) while leaving a stringer-free box untouched.  An
    explicit value overrides the automatic choice, which is what makes an
    apples-to-apples sweep possible.
    """


@dataclass
class LoadSpec:
    """Structural load.

    ``kind="tip_force"``
        Total force (N) split equally over the wing-tip nodes and applied along
        ``direction``.  The direction is explicit, so the sign of the response
        is unambiguous - this is the default for the demo case.
    ``kind="pressure"``
        Shell pressure (MPa) on the upper skin, applied along the shell normal.
        The sign therefore follows the element orientation, which is fine for
        magnitude studies but should be checked per model.
    """

    kind: str = "tip_force"         # "tip_force" | "pressure"
    magnitude: float = 500.0        # N for tip_force, MPa for pressure
    direction: tuple[float, float, float] = (0.0, 1.0, 0.0)


@dataclass
class BCSPEC:
    """Boundary conditions: the wing root is clamped."""

    root_surface: str = "root"
    clamp: bool = True


@dataclass
class AnalysisSpec:
    """Solver deck settings."""

    solver: str = "auto"            # "auto" | "ccx" | "abaqus"
    step_type: str = "static"       # "static" | "frequency" (C6-P1, 2026-11-07)
    incremental: bool = True
    initial_increment: float = 0.25
    total_time: float = 1.0
    outputs: tuple[str, ...] = ("U", "S")
    n_modes: int = 5                # frequency step only: number of eigenvalues


@dataclass
class FEASpec:
    """Top-level specification handed between every stage."""

    name: str = "naca4412_wingbox"
    description: str = "Automatically generated NACA4412 wing box"
    material: MaterialSpec = field(default_factory=MaterialSpec)
    structure: StructureSpec = field(default_factory=StructureSpec)
    airfoil: AirfoilSpec = field(default_factory=AirfoilSpec)
    mesh: MeshSpec = field(default_factory=MeshSpec)
    load: LoadSpec = field(default_factory=LoadSpec)
    bc: BCSPEC = field(default_factory=BCSPEC)
    analysis: AnalysisSpec = field(default_factory=AnalysisSpec)
    workdir: str = "outputs"
    extra: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # (de)serialisation - the actual "standardised JSON" contract
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, path: str | Path, indent: int = 2) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=indent, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FEASpec":
        # W4c 纠偏（专家第三轮 P0-1/R10）：静默降级禁令——顶层缺 structure/airfoil
        # 或 family 缺失/未知时必须 raise，绝不默认 wingbox（曾把包装候选解成默认翼盒）。
        if not isinstance(d, dict) or ("structure" not in d and "airfoil" not in d):
            raise ValueError(
                "not a FEASpec: top level must carry 'structure' (or legacy 'airfoil'); "
                f"got keys {sorted(d) if isinstance(d, dict) else type(d).__name__}")
        fam = (d.get("structure") or {}).get("family")
        from .geometry import BUILDERS  # 延迟导入避免环
        if fam not in BUILDERS:
            raise ValueError(
                f"structure.family missing or unknown: {fam!r}; registered: {sorted(BUILDERS)}")
        return cls(
            name=d.get("name", "fea_case"),
            description=d.get("description", ""),
            material=MaterialSpec(**d.get("material", {})),
            structure=StructureSpec(**d.get("structure", {})),
            airfoil=AirfoilSpec(**d.get("airfoil", {})),
            mesh=MeshSpec(**d.get("mesh", {})),
            load=LoadSpec(**d.get("load", {})),
            bc=BCSPEC(**d.get("bc", {})),
            analysis=AnalysisSpec(**d.get("analysis", {})),
            workdir=d.get("workdir", "outputs"),
            extra=d.get("extra", {}),
        )

    @classmethod
    def from_json(cls, path: str | Path) -> "FEASpec":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
