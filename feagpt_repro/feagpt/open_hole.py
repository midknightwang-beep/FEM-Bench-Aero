"""The open-hole panel family - its parameter block and its rules (M5 / task T4).

What an "open-hole panel" is here
---------------------------------
A flat rectangular skin ``length x width`` in the z = 0 plane with a single
**circular cut-out** on its centre line, loaded in **in-plane tension** along
``x``.  Nothing else: no stringers, no pressure, no curvature.  It is the first
family whose interesting number is not a deflection but a **stress
concentration factor**, and the first whose grid requirement is set by a
*feature* rather than by the part's overall size.

Why this family exists at all
----------------------------
Every family so far answers "does the load path come out right" - a tip
deflection, a plate deflection, a barrel dilation - and all of those are
*global* quantities that a slightly wrong mesh barely moves.  A hole edge is the
opposite: the answer lives in one node, the gradient is steep, and a mesh that
is perfectly adequate 20 mm away can be off by 30 % *at* the hole.  It is the
one form in the dataset that puts the mesher itself on trial, which is exactly
why it is worth a family rather than a variant of the panel.

The yardstick: Kirsch, and why the number is **not** 3.0
--------------------------------------------------------
Kirsch (1898) gives the infinite-plate solution: uniaxial tension ``sigma`` at
infinity, hoop stress at the hole edge ``sigma_theta = 3 sigma`` at the two
points on the diameter perpendicular to the load.  So the textbook
stress-concentration factor is

    Kt = sigma_max / sigma_nominal = 3.0

and it is quoted everywhere as "a hole triples the stress".  That 3.0 is an
**infinite-plate** number, and a finite coupon is not one: the hole removes
section, so the stress that matters is higher than the gross value, and the
free edges relieve it again.  The two effects do not cancel, and on the sizes a
test coupon actually uses they leave a factor well below three.

Two nominal stress conventions therefore have to be kept apart, and mixing them
is the standard way to "confirm" a wrong answer:

``gross``   ``sigma_gross = F / (width * thickness)`` - force over the *full*
            section.  This is what the deck applies, so it is what the FE
            result can be reduced against without any assumption.
``net``     ``sigma_net = F / ((width - hole_d) * thickness)`` - force over the
            section *through the hole*.  ``sigma_gross * (1 - lambda)``.

Howland's finite-width solution is tabulated on the **net** section, so the
comparison below converts it.  For the default geometry here
(``lambda = d / width = 0.1``):

    Kt_net   = 3 - 3.13 lambda + 3.66 lambda^2 - 1.53 lambda^3  = 2.720
    Kt_gross = Kt_net / (1 - lambda)                            = 3.024

The two conventions do not agree about whether this coupon "shows 3.0", and
**both readings are correct**:

* against the **gross** stress the factor is 3.024, i.e. 0.8 % *above*
  Kirsch's 3.0 - close enough that a run which simply compares to 3.0 looks
  validated and is not;
* against the **net** stress it is 2.720, i.e. 9.3 % *below* 3.0, and the
  finite-width relief lives entirely in the net reading.

Neither is the "true Kt": what is true is that a stress-concentration factor
without its nominal-stress convention is not a number.  So the family carries
both, the validator prints both, and every reported Kt names its section.  The
resolution that *is* a mesh question - how finely the hole arc must be
discretised before the peak stops moving - is converged in ``verify_hole.py``
rather than assumed here.

Scale check
-----------
``6 mm`` coupon scale, ``2 mm`` skin, ``20 mm`` hole, aluminium 2024-T3.  At the
default nominal stress (``10 MPa`` gross) the hole edge sits near ``24 MPa``
against a ``345 MPa`` yield, so the whole field is linear-elastic and the
linear-static assumption the chain makes is valid - the same argument the
``stiffened_panel`` family records for its pressure.

Parameters are refused, not defaulted
-------------------------------------
``parse_params`` raises on an unrecognised key, for the reason
:mod:`feagpt.panel` sets out: a mis-spelled knob that is silently ignored
produces a run that looks fine and answers a different question.

What is *not* buildable, and why that is a rule rather than a nuisance
---------------------------------------------------------------------
The mesher floors every generated element size at
``MeshSizeMin = max(size_chord / 6, 0.5)`` mm, and the hole edge is the one
feature this family exists to resolve.  A coupon whose hole edge target would
fall at or below that floor is therefore **refused** rather than quietly
coarsened (:func:`feagpt.geometry.build_open_hole_panel`): a silently
over-coarsened edge keeps the run looking fine while the factor it reports is no
longer the one the family was validated against.

The consequence is an envelope, and it is worth stating as one:
:func:`min_buildable_hole_d` is ``15.3 mm`` at the family defaults - and because
the ``0.5 mm`` term in the floor is absolute, **no** far field makes a hole
smaller than ``0.5 * 72 / pi = 11.46 mm`` buildable at 72 divisions.  That is
why the trend probe in ``verify_hole.py`` moves ``lambda`` between 0.1 and 0.3
instead of down to 0.05: at ``W = 200 mm`` a ``lambda = 0.05`` hole is 10 mm
across and cannot be built at this resolution at all (found the hard way - a
trend probe built on it died in the builder).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

FAMILY = "open_hole_panel"

#: Every key ``structure.params`` may carry for this family.
#:
#: T7 (2026-10-11): ``"layup"`` is the family's material dimension - a
#: composite stack (see :mod:`feagpt.laminate`).  It travels in the params
#: dict **as a key, not as an :class:`OpenHoleParams` field**: the dataclass
#: describes the geometry (and its dict lands in truth.json, which must not
#: move), while the layup is a material truth the pipeline converts to a CLT
#: equivalent before the deck is written.  Specs without the key - every
#: archived case - are untouched by its existence here.
KNOWN_KEYS = (
    "length",
    "width",
    "thickness",
    "hole_d",
    "hole_x",
    "hole_y",
    "layup",
)

#: The geometry keys - the ones an :class:`OpenHoleParams` actually carries.
GEOMETRY_KEYS = tuple(k for k in KNOWN_KEYS if k != "layup")

#: Absolute mm, as in :mod:`feagpt.panel` - see :data:`feagpt.panel.EDGE_TOL`.
EDGE_TOL = 1e-3

#: Mesh size (mm) the open-hole cases are built at, i.e. the **far field** -
#: the hole edge is set independently (see :data:`HOLE_ARC_DIVISIONS`).
#:
#: 4 mm rather than the panel's 3 mm is a size-field interaction, not taste.
#: Gmsh clamps every generated size to ``MeshSizeMin = size_chord / 6``, so a
#: 5 mm far field would floor the size field at 0.83 mm against a hole edge
#: target of 0.873 mm - a 5 % margin, which is not a margin.  4 mm puts the
#: floor at 0.667 mm and leaves 31 %; the far field is otherwise unremarkable,
#: because on this model the answer lives at the hole and nowhere else.
DEFAULT_MESH_SIZE = 4.0

#: Nominal **gross-section** stress (MPa) the default load produces.  The load
#: is applied as a total force ``sigma * width * thickness`` spread over the
#: loaded end, so this number is exact by construction and needs no measurement
#: to state.
DEFAULT_GROSS_STRESS = 10.0

#: How many elements the hole circumference is divided into: ``72`` = one per
#: 5 deg of arc.
#:
#: This is the family's resolution rule and the one number that decides whether
#: the family measures anything.  The peak stress of an open hole is a
#: **gradient**: 20 mm away a 5 mm mesh is excellent, and *at* the edge it can
#: be 30 % low.  So the resolution is declared by the builder rather than left
#: to a mesher default, and it is applied through
#: ``Mesh.MeshSizeFromCurvature`` - the per-curve ``setSize`` route is silently
#: ignored on this toolchain (measured, ``_t4_probe/setsize_lab.py``).
#:
#: Why 72 and not the classical 24 (15 deg).  Converged on the default coupon
#: (``_t4_probe/t4_convergence.py``; Kt_gross against Howland's 3.0245):
#:
#:   divisions   arc      Kt_gross   vs Howland
#:   12          30 deg   2.7545      -8.9 %   under-resolved
#:   24          15 deg   2.9897      -1.2 %   <- the textbook default
#:   36          10 deg   2.9887      -1.2 %
#:   48          7.5 deg  2.9709      -1.8 %
#:   72          5 deg    3.0373      +0.4 %   <- shipped
#:   96          3.75 deg 3.0291      +0.2 %
#:
#: The sequence is **not monotone**: a peak read off a curved boundary depends
#: on where the nodes land, and that scatter is about +-1 %.  24 divisions
#: leaves the result sitting 1.2 % low, which is the size of the gate this
#: family is judged against - so it is not enough, and saying "the textbook
#: uses 15 deg" would be dressing a margin up as a convention.  From 72 up the
#: scatter band (+0.4 / +0.2 %) contains the analytic value, and refining
#: further buys nothing: 72 is the coarsest resolution that is *inside* the
#: band, which is what "converged" is supposed to mean.
#:
#: Cost of the finer arc: 3613 -> 5123 elements on the default coupon (+42 %),
#: i.e. a few thousand shells.  It is not a trade worth making the other way.
HOLE_ARC_DIVISIONS = 72


def hole_edge_size(p: "OpenHoleParams",
                   divisions: int | None = None) -> float:
    """Target element size (mm) on the hole edge for a given discretisation."""
    n = int(HOLE_ARC_DIVISIONS if divisions is None else divisions)
    return math.pi * float(p.hole_d) / float(n)


def mesh_size_floor(spec) -> float:
    """``MeshSizeMin`` the mesher will impose, given a spec's far-field size.

    Mirrors :func:`feagpt.meshing._configure_size_field` exactly (``max(size_chord
    / 6, 0.5)``).  It is duplicated here rather than imported because the builder
    has to answer "will my hole edge survive the size field's own floor?" and
    that question is about this family's feature, not about the mesher.

    The ``0.5 mm`` term is a **hard** floor, not a scaled one, so lowering
    ``mesh.size_chord`` stops helping below ``size_chord = 3 mm``.
    """
    return max(float(spec.mesh.size_chord) / 6.0, 0.5)


def min_buildable_hole_d(spec, divisions: int | None = None) -> float:
    """Smallest hole diameter whose edge target clears the size field's floor.

    :func:`hole_edge_size` is ``pi d / n`` and the mesher floors every generated
    size at :func:`mesh_size_floor`, so a hole is buildable exactly when
    ``pi d / n > floor``, i.e. ``d > floor n / pi``.

    At the family default (``n = 72``, ``size_chord = 4 mm`` -> floor 0.6667 mm)
    that is ``d > 15.28 mm``.  Because the floor carries a hard ``0.5 mm`` term,
    the lower bound can never go below ``0.5 * 72 / pi = 11.46 mm`` however small
    ``size_chord`` is made.

    Stated here rather than inline in a comment because two independent checks
    stand *on* this boundary - ``check_forms.check_T4`` builds one coupon just
    below it and one just above - and a boundary written down twice is a boundary
    that will eventually disagree with itself.
    """
    n = int(HOLE_ARC_DIVISIONS if divisions is None else divisions)
    return mesh_size_floor(spec) * float(n) / math.pi


@dataclass(frozen=True)
class OpenHoleParams:
    """The open-hole coupon, with the defaults a "typical" case uses.

    400 x 200 x 2 mm aluminium with a 20 mm central hole - i.e. ``lambda =
    d/width = 0.1``.  The coupon is twice as long as it is wide so the loaded
    ends are far from the hole (Saint-Venant), and ``lambda`` is held at the
    value where the finite-width correction is both well documented and small
    enough to be worth stating (see the module docstring).
    """

    length: float = 400.0            # mm, along x (the load direction)
    width: float = 200.0             # mm, along y (the net section)
    thickness: float = 2.0           # mm, skin
    hole_d: float = 20.0             # mm, hole diameter
    hole_x: float | None = None      # mm, hole centre; None = mid-length
    hole_y: float | None = None      # mm, hole centre; None = mid-width

    # ------------------------------------------------------------------ #
    def center(self) -> tuple[float, float]:
        """Hole centre (mm); ``None`` on either axis means "centred"."""
        cx = 0.5 * float(self.length) if self.hole_x is None else float(self.hole_x)
        cy = 0.5 * float(self.width) if self.hole_y is None else float(self.hole_y)
        return cx, cy

    @property
    def lambda_ratio(self) -> float:
        """``d / width`` - the only parameter the finite-width correction sees."""
        return float(self.hole_d) / float(self.width)

    @property
    def net_width(self) -> float:
        """Section width through the hole (mm): ``width - hole_d``."""
        return float(self.width) - float(self.hole_d)

    def edge_margin(self) -> float:
        """Smallest distance from the hole edge to a plate edge (mm)."""
        cx, cy = self.center()
        r = 0.5 * float(self.hole_d)
        return min(cx - r, float(self.length) - cx - r,
                   cy - r, float(self.width) - cy - r)

    def to_dict(self) -> dict:
        d = asdict(self)
        cx, cy = self.center()
        d["hole_center"] = [round(cx, 6), round(cy, 6)]
        d["lambda"] = round(self.lambda_ratio, 9)
        d["net_width"] = round(self.net_width, 6)
        return d


# --------------------------------------------------------------------------- #
# the analytic yardsticks
# --------------------------------------------------------------------------- #
def kirsch_kt() -> float:
    """Kirsch (1898) infinite-plate stress-concentration factor: exactly 3."""
    return 3.0


def howland_kt_net(lam: float) -> float:
    """Finite-width ``Kt`` on the **net** section, ``lam = d / width``.

    The four-term Howland fit (Howland 1930; as tabulated in Peterson's *Stress
    Concentration Factors*, eq. for a circular hole in a finite-width strip):

        Kt_net = 3 - 3.13 lam + 3.66 lam^2 - 1.53 lam^3

    Accurate to well under 1 % for ``lam <= 1/3``, which covers every geometry
    this family is meant to build.  It is a **fit to a tabulated solution, not
    a closed form** - recorded as such so nobody later quotes it to four digits
    or pushes ``lam`` past where it holds.
    """
    lam = float(lam)
    return 3.0 - 3.13 * lam + 3.66 * lam ** 2 - 1.53 * lam ** 3


def howland_kt_gross(lam: float) -> float:
    """Same solution expressed against the **gross** section.

    The FE result is reduced against ``sigma_gross`` (the force is applied over
    the full width and that is what a node-averaged stress field reports far
    from the hole), so the comparison needs the factor in the same convention.
    The conversion *raises* the number, because removing section at the hole
    means ``sigma_net > sigma_gross``:

        ``sigma_net = sigma_gross / (1 - lam)``
        ``Kt_gross = sigma_max / sigma_gross
                   = (sigma_max / sigma_net) * (sigma_net / sigma_gross)
                   = Kt_net / (1 - lam)``

    Getting this backwards - multiplying by ``(1 - lam)``, which reads
    naturally and is wrong - makes a correct finite-width result look like a
    20 % mesh error against the analytic value while it is really within 3 %.
    That is not a hypothetical: it is the mistake this docstring was written
    after.
    """
    lam = float(lam)
    return howland_kt_net(lam) / (1.0 - lam)


def gross_stress(force_n: float, p: "OpenHoleParams") -> float:
    """``F / (width * thickness)`` - the nominal stress the deck applies (MPa)."""
    return float(force_n) / (float(p.width) * float(p.thickness))


def net_stress(force_n: float, p: "OpenHoleParams") -> float:
    """``F / (net_width * thickness)`` - the nominal stress through the hole (MPa)."""
    return float(force_n) / (float(p.net_width) * float(p.thickness))


# --------------------------------------------------------------------------- #
# parse / validate
# --------------------------------------------------------------------------- #
def parse_params(spec) -> OpenHoleParams:
    """Read ``spec.structure.params`` into a validated :class:`OpenHoleParams`.

    The ``layup`` key (T7) is *not* geometry and is not consumed here: the
    pipeline reads it through :func:`feagpt.laminate.layup_from_params`.  It is
    accepted (not "unknown") so a composite spec passes the refusal gate, but
    the :class:`OpenHoleParams` this returns describes the coupon's shape only.
    """
    raw = dict(getattr(getattr(spec, "structure", None), "params", None) or {})
    unknown = sorted(set(raw) - set(KNOWN_KEYS))
    if unknown:
        raise ValueError(
            f"{FAMILY}: unknown parameter(s) {unknown}; understood: "
            f"{sorted(KNOWN_KEYS)}. Refusing to ignore them - a mis-spelled key "
            f"would silently build a different coupon."
        )
    p = OpenHoleParams(**{k: raw[k] for k in raw if k in GEOMETRY_KEYS})
    _validate(p)
    return p


def _validate(p: OpenHoleParams) -> None:
    for name in ("length", "width", "thickness", "hole_d"):
        v = float(getattr(p, name))
        if v <= 0.0:
            raise ValueError(f"{FAMILY}: {name} must be > 0, got {v}")

    # The hole has to sit strictly inside the plate, with *no* reliance on
    # floating-point luck: a hole tangent to an edge leaves a zero-width neck
    # that meshes into slivers and whose stress is singular, so it is refused
    # rather than built.
    margin = p.edge_margin()
    if margin <= 0.0:
        cx, cy = p.center()
        raise ValueError(
            f"{FAMILY}: hole d={p.hole_d} at ({cx}, {cy}) is not inside the "
            f"{p.length} x {p.width} plate (edge margin {margin:g} mm <= 0)"
        )
    # A hole the size of the plate is not a coupon, it is a slit.  The finite-
    # width fit is also only good to lambda = 1/3, so the envelope is declared
    # here instead of being discovered by a validator that disagrees with the
    # geometry builder.
    lam = p.lambda_ratio
    if lam >= 1.0 / 3.0:
        raise ValueError(
            f"{FAMILY}: d/width = {lam:.4f} >= 1/3; the finite-width correction "
            f"this family is validated against is only accurate below that"
        )
    if float(p.length) < 2.0 * float(p.hole_d):
        # The loaded ends then sit within a hole diameter of the cut-out and the
        # stress there is dominated by the end constraint, so the coupon stops
        # measuring a stress concentration at all.
        raise ValueError(
            f"{FAMILY}: length {p.length} < 2 * hole_d {2*p.hole_d}; the loaded "
            f"end would fall inside the hole's Saint-Venant zone"
        )


def make_spec(name: str, size: float | None = None,
              gross_stress: float | None = None,
              workdir: str = "outputs_hole", **params):
    """A ready-to-run open-hole :class:`~feagpt.spec.FEASpec`.

    One factory, so the verification line, the degeneration check and the
    parameter sweep all build *the same* coupon from one set of declared
    defaults - the argument :func:`feagpt.panel.make_spec` records applies
    unchanged here.

    The load is a **total force** ``gross_stress * width * thickness`` (N)
    applied along +x over the loaded end, so the nominal stress it produces is
    exact by construction and the *same* number for every mesh.
    """
    from .spec import FEASpec

    unknown = sorted(set(params) - set(KNOWN_KEYS))
    if unknown:
        raise ValueError(
            f"{FAMILY}.make_spec: unknown parameter(s) {unknown}; understood: "
            f"{sorted(KNOWN_KEYS)}"
        )

    block = {k: OpenHoleParams.__dataclass_fields__[k].default
             for k in ("length", "width", "thickness", "hole_d")}
    block.update(params)
    # T7: the layup stays in the params dict (it is a material truth, not an
    # OpenHoleParams field) and the validation coupon below sees geometry only.
    layup = block.get("layup")
    tmp = OpenHoleParams(**{k: block[k] for k in GEOMETRY_KEYS if k in block})
    _validate(tmp)

    spec = FEASpec()
    spec.name = name
    spec.description = (
        f"Open-hole coupon {tmp.length:g} x {tmp.width:g} x {tmp.thickness:g} mm, "
        f"hole d={tmp.hole_d:g} mm (lambda={tmp.lambda_ratio:.3f}), tension"
    )
    if layup is not None:
        from .laminate import layup_from_params
        code = layup_from_params(block).code
        spec.description += f", laminate {code}"
    spec.structure.family = FAMILY
    spec.structure.params = block

    mesh_size = DEFAULT_MESH_SIZE if size is None else float(size)
    spec.mesh.size_chord = mesh_size
    spec.mesh.size_span = mesh_size

    sigma = DEFAULT_GROSS_STRESS if gross_stress is None else float(gross_stress)
    spec.load.kind = "tip_force"
    spec.load.magnitude = sigma * float(tmp.width) * float(tmp.thickness)
    spec.load.direction = (1.0, 0.0, 0.0)
    spec.workdir = workdir
    return spec


# --------------------------------------------------------------------------- #
# boundary conditions - the family's own rule
# --------------------------------------------------------------------------- #
def end_nodes(nodes: dict, p: OpenHoleParams, which: str,
              tol: float = EDGE_TOL) -> list[int]:
    """Tags of the nodes on the clamped / loaded end.

    ``which="fixed"`` selects ``x = 0``, ``"loaded"`` selects ``x = length``.
    Declared rather than inferred, and expressed against a node table rather
    than a gmsh session, so the cross-solver equilibrium check can re-apply the
    same rule to a result file - the reason :func:`feagpt.panel.edge_nodes`
    takes a node table too.

    The hole is strictly inside the plate (``_validate``), so no hole-edge node
    can land on either end and the two sets are disjoint.
    """
    x_target = 0.0 if which == "fixed" else float(p.length)
    return [tag for tag, (x, _y, _z) in nodes.items()
            if abs(float(x) - x_target) < tol]


def clamp_nodes(spec, nodes: dict) -> list[int]:
    """The clamp set for a spec - the family's own rule, from a node table."""
    return end_nodes(nodes, parse_params(spec), "fixed")


def load_nodes(spec, nodes: dict) -> list[int]:
    """The loaded-end set for a spec - the family's own rule, from a node table."""
    return end_nodes(nodes, parse_params(spec), "loaded")


def hole_edge_nodes(nodes: dict, p: OpenHoleParams, shell: float = 1e-6
                    ) -> list[int]:
    """Tags of the nodes *on* the hole boundary.

    The Kt reduction needs the hole edge and nothing else: a global maximum
    would be free to pick up the end constraint or a corner, and the whole point
    of the family is that one specific edge carries the answer.  Membership is
    ``|r - d/2| < shell`` with ``r`` measured from the hole centre, which is a
    property of the *geometry*, not of the group names - so a run whose hole was
    built somewhere else reports an empty set rather than a plausible number.
    """
    cx, cy = p.center()
    r_hole = 0.5 * float(p.hole_d)
    out: list[int] = []
    for tag, (x, y, _z) in nodes.items():
        r = ((float(x) - cx) ** 2 + (float(y) - cy) ** 2) ** 0.5
        if abs(r - r_hole) < shell:
            out.append(tag)
    return out


def hole_edge_tol(p: OpenHoleParams) -> float:
    """Radius band (mm) that counts as "on the hole edge".

    The boundary nodes are written exactly on the circle, so the tolerance only
    has to beat OCC's coordinate noise (about 1e-9 mm) - but a band that is too
    tight silently selects nothing on a mesh that moved a node by a rounding
    step.  ``1e-3 mm`` is the same three-orders-of-magnitude margin
    :data:`EDGE_TOL` uses for the plate edges, and it is four orders below the
    smallest element the size field can produce here.
    """
    return EDGE_TOL
