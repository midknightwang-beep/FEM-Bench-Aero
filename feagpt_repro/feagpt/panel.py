"""The stiffened-panel family - its parameter block and its support rule (M3/T2).

What a "stiffened panel" is here
--------------------------------
A flat skin ``length x width`` in the z = 0 plane, with ``n_stringers`` blade
webs standing on it, running the full width.  Nothing else: no spars, no ribs,
no curvature.  It is the second structural *family* of the dataset (the first
was the wing box) and the first one whose parameters live in
``StructureSpec.params`` rather than in the legacy ``AirfoilSpec`` block.

Why this module exists separately from ``geometry.py``
------------------------------------------------------
Three things have to agree about a panel, and they sit at different stages:

* the **parameter block** - read by the geometry builder;
* the **station layout** - the stringer x positions, which gate 4 predicts and
  the geometry observation measures;
* the **support rule** - which nodes are on the four edges, which the deck
  writer needs and which the cross-solver equilibrium check needs *again*, from
  a result file, with no geometry in hand.

Keeping them in one module is what stops the builder and the gate from each
having their own opinion about where a stringer is.

Parameters are refused, not defaulted
-------------------------------------
``parse_params`` raises on an unrecognised key.  A mis-spelled parameter would
otherwise be silently ignored and the model would quietly be a different one -
the exact "runs fine, is wrong" failure that gate 4 exists to catch, and cheaper
to catch here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from . import sections

FAMILY = "stiffened_panel"

#: Every key ``structure.params`` may carry for this family.
KNOWN_KEYS = (
    "length",
    "width",
    "thickness",
    "n_stringers",
    "stringer_height",
    "stringer_thickness",
    "stringer_kind",
    "stringer_flange_width",
)

#: Absolute mm.  Used to decide "this node is on the edge".  The smallest mesh
#: edge on this model is a few mm (``Mesh.MeshSizeMin`` is at least 0.5 mm), so
#: 1e-3 mm separates "on the edge" from "one element inside" with three orders
#: of magnitude to spare, while sitting five orders above OCC's coordinate
#: noise.  Not tuned by hand: both bounds are properties of the mesh, not of
#: this model.
EDGE_TOL = 1e-3

#: Mesh size (mm) the panel cases are built at.  Not a taste: the convergence
#: study (``diagnostics/panel_convergence.py``) measured the FE centre deflection
#: against the Navier closed form on 12 / 6 / 3 mm as **-6.9 % / -0.63 % /
#: -0.10 %**, i.e. monotone upward convergence.
#:
#: Lowered to 3 mm on 2026-10-03 (decision D9).  At 6 mm the plain panel's
#: cross-solver max|u| gap was **0.800 %** against a 1 % gate - passing, but with
#: 0.2 points of margin, which is not a margin, it is a coincidence waiting to
#: expire.  At 3 mm the same gap is **0.326 %** and the exact Navier value
#: 0.96268 mm is bracketed by the two codes (ccx -0.097 %, Abaqus +0.230 %),
#: which is what a discretisation error is supposed to look like.  The gate
#: tolerance was deliberately NOT relaxed instead: one that gets loosened when it
#: is inconvenient stops being a gate.  Cost: 3.95x the nodes.
DEFAULT_MESH_SIZE = 3.0

#: Uniform pressure (MPa) that keeps the plate inside the small-deformation
#: regime.  The Navier solution gives ``w_max = 0.963 mm = 0.48 t`` on the
#: 600 x 600 x 2 mm coupon at this pressure, so linear plate theory - and
#: therefore this chain's own linear-static assumption - is valid.  The value
#: looks tiny next to a real cabin pressure; that is the deliberate price of
#: testing the *form* on a well-posed problem instead of a realistic load case.
DEFAULT_PRESSURE = 1e-4


@dataclass(frozen=True)
class PanelParams:
    """The panel's parameter block, with the defaults a "typical" panel uses.

    600 x 600 x 2 mm aluminium is the classic panel-test coupon size, and the
    stringer pitch that falls out of 3 stringers (150 mm) is the usual
    stiffener spacing for it.  Both are *declared*, not tuned to make a result
    come out: the pressure is what gets sized (see ``verify_panel.py``), because
    the pressure is a loading choice whereas the geometry is the specimen.
    """

    length: float = 600.0            # mm, along x
    width: float = 600.0             # mm, along y (the stringers run this way)
    thickness: float = 2.0           # mm, skin
    n_stringers: int = 3             # blade webs, full width
    stringer_height: float = 20.0    # mm, stands up in +z
    stringer_thickness: float = 2.5  # mm
    stringer_kind: str = "blade"     # see feagpt.sections
    stringer_flange_width: float = 30.0

    # ------------------------------------------------------------------ #
    def stations(self) -> tuple[float, ...]:
        """Chordwise... rather, *x* stations of the stringers, evenly spaced.

        ``n`` stringers divide the length into ``n + 1`` equal bays, so the
        stations are at ``length * (j + 1) / (n + 1)``.  Derived rather than
        declared: one parameter (``n_stringers``) is harder to leave
        inconsistent than two, and the derived value is what gate 4 checks the
        built geometry against.
        """
        n = int(self.n_stringers)
        if n <= 0:
            return ()
        step = float(self.length) / (n + 1)
        return tuple(step * (j + 1) for j in range(n))

    def pitch(self) -> float | None:
        """Stringer spacing (mm); ``None`` for a stiffener-free plate."""
        n = int(self.n_stringers)
        return float(self.length) / (n + 1) if n > 0 else None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["stringer_stations"] = [round(v, 6) for v in self.stations()]
        d["stringer_pitch"] = self.pitch()
        return d


def parse_params(spec) -> PanelParams:
    """Read ``spec.structure.params`` into a validated :class:`PanelParams`."""
    raw = dict(getattr(getattr(spec, "structure", None), "params", None) or {})
    unknown = sorted(set(raw) - set(KNOWN_KEYS))
    if unknown:
        raise ValueError(
            f"{FAMILY}: unknown parameter(s) {unknown}; understood: {sorted(KNOWN_KEYS)}. "
            f"Refusing to ignore them - a mis-spelled key would silently build a "
            f"different panel."
        )
    p = PanelParams(**{k: raw[k] for k in raw})
    _validate(p)
    return p


def _validate(p: PanelParams) -> None:
    for name in ("length", "width", "thickness",
                 "stringer_height", "stringer_thickness"):
        v = float(getattr(p, name))
        if v <= 0.0:
            raise ValueError(f"{FAMILY}: {name} must be > 0, got {v}")
    n = int(p.n_stringers)
    if n < 0:
        raise ValueError(f"{FAMILY}: n_stringers must be >= 0, got {n}")
    if n and float(p.stringer_height) >= float(p.width):
        # A stringer taller than the panel it stands on is almost certainly a
        # unit or axis mistake, and it would still mesh.
        raise ValueError(
            f"{FAMILY}: stringer_height {p.stringer_height} >= panel width "
            f"{p.width} - check the units"
        )
    # The section kind has to be registered, and the flange width matters: a
    # flanged section with flange_width <= 0 degenerates to a blade (see
    # feagpt.sections), so this also rejects a section the deck could not use.
    sections.faces_per_section(p.stringer_kind, p.stringer_flange_width)


def make_spec(name: str, n_stringers: int | None = None, size: float | None = None,
              pressure: float | None = None, workdir: str = "outputs_panel",
              **params):
    """A ready-to-run stiffened-panel :class:`~feagpt.spec.FEASpec`.

    One factory, so the verification line, the degeneration check and (M5) the
    parameter sweep all build *the same* panel from one set of declared
    defaults.  The alternative is each caller keeping its own copy of "600 x 600
    x 2, three blade stringers, 6 mm mesh", which is exactly how a sweep comes to
    compare models that were never the same model.

    ``params`` are :data:`KNOWN_KEYS` names and are the *only* supported
    overrides - anything else raises, for the same reason
    :func:`parse_params` raises: a mis-spelled knob that is silently ignored
    produces a run that looks fine and answers a different question.
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
        f"Stiffened panel {params.get('length', PanelParams.length)} x "
        f"{params.get('width', PanelParams.width)} mm, "
        f"{n_stringers if n_stringers is not None else PanelParams.n_stringers} "
        f"stringer(s)"
    )
    spec.structure.family = FAMILY
    block = {
        "length": PanelParams.length,
        "width": PanelParams.width,
        "thickness": PanelParams.thickness,
    }
    if n_stringers is not None:
        block["n_stringers"] = int(n_stringers)
    block.update(params)
    spec.structure.params = block

    mesh_size = DEFAULT_MESH_SIZE if size is None else float(size)
    spec.mesh.size_chord = mesh_size
    spec.mesh.size_span = mesh_size

    spec.load.kind = "pressure"
    spec.load.magnitude = DEFAULT_PRESSURE if pressure is None else float(pressure)
    spec.load.direction = (0.0, 0.0, -1.0)
    spec.workdir = workdir
    return spec


def edge_nodes(nodes: dict, params: PanelParams, tol: float = EDGE_TOL) -> list[int]:
    """Tags of the nodes on the panel's four supported edges.

    The support is *declared*, not inferred: the panel is simply supported along
    the outline of its ``length x width`` rectangle, so the supported set is
    every node whose ``(x, y)`` lies on that outline.  ``z`` is deliberately not
    tested - the stringer webs reach the boundary too, and they are part of the
    panel.

    This same rule has to be usable from a *result* file, not just from the
    build, which is why it takes a node table and not a Gmsh session: the
    cross-solver equilibrium check has only ``{label: (x, y, z)}`` in hand.
    """
    L, W = float(params.length), float(params.width)
    out: list[int] = []
    for tag, (x, y, _z) in nodes.items():
        if abs(x) < tol or abs(x - L) < tol or abs(y) < tol or abs(y - W) < tol:
            out.append(tag)
    return out


def clamp_nodes(spec, nodes: dict) -> list[int]:
    """The panel's clamp set for a spec - the family's own rule, from a node table."""
    return edge_nodes(nodes, parse_params(spec))

def split_anchor_edges(nodes: dict, params: PanelParams,
                       tol: float = EDGE_TOL) -> dict:
    """U3a plate anchor (2026-11-09): the Navier-plate edge groups.

    Returns the two LOADED edges (x = 0 and x = L, the short edges carrying
    the uniaxial compression) plus two in-plane datum nodes picked on the
    UNLOADED edge y = 0: the lowest-label node gets DOF 1,2 = 0, another node
    at a different x gets DOF 2 = 0.  Two x-separated y restraints kill the
    in-plane translations AND the rotation about z, without constraining the
    loaded edges (a datum on a loaded edge would fight its own CLOAD).
    """
    L, W = float(params.length), float(params.width)
    ex0, exL, y0 = [], [], []
    for tag, (x, y, _z) in nodes.items():
        if abs(x) < tol:
            ex0.append(tag)
        elif abs(x - L) < tol:
            exL.append(tag)
        if abs(y) < tol:
            y0.append(tag)
    if not ex0 or not exL or not y0:
        raise RuntimeError("anchor edge split found an empty edge set")
    # Datum nodes must sit on the UNLOADED edge MIDDLE, away from the corners:
    # the first build picked the lowest-label y=0 node, which happened to be
    # the (0,0) corner - i.e. exactly the reference node of the ex0 CLOAD, so
    # its DOF 1 lock silently swallowed that edge's whole force AND, through
    # the u_x coupling EQUATION, turned the whole x=0 edge into an axial
    # clamp (measured: lambda 1.959 -> F = 3917 N, -45.6 % vs analytic).
    mid = [t for t in y0
           if abs(nodes[t][0] - L / 2.0) < L / 4.0]
    assert len(mid) >= 2, "not enough mid-edge y=0 nodes for the datum pair"
    mid.sort(key=lambda t: nodes[t][0])
    datum_a = [mid[0]]
    datum_b = [t for t in mid if nodes[t][0] != nodes[datum_a[0]][0]][-1]
    return {"ex0": ex0, "exL": exL, "datum_a": datum_a, "datum_b": [datum_b]}

