"""Task T7 - composite laminate: the layup contract and its CLT equivalent.

What T7 is, and what it deliberately is not
-------------------------------------------
T7 adds a **material/layup dimension** to the open-hole panel family (老王's
call, 2026-10-11): the same ``length x width`` coupon with the same circular
cut-out, but the skin is a fibre-reinforced laminate instead of isotropic
aluminium.  The *physical* skin is layered; what the deck carries is its
**classical-lamination-theory (CLT) equivalent single layer** - one
orthotropic shell section with the membrane stiffness the stack really has.

Why the equivalent single layer rather than a true layered card (D29)
---------------------------------------------------------------------
A true ``*SHELL SECTION, COMPOSITE`` on the CalculiX side exists (measured on
2.23, ``_probe_t7/t7_probe_e_s8r_composite.inp``) but **only accepts S6/S8R
second-order shells** - the whole dataset runs S4.  Going layered would mean
second-order meshing across the chain: mesher, gate-4 counters, post, ODB
extraction, and a ~4x node count into a solver that already hits a memory wall
(D27).  The dataset is a *structural modelling* benchmark: the observables it
gates are displacements and in-plane stress fields, and an equivalent single
layer reproduces those exactly for a symmetric, balanced stack (B = 0, no
membrane-bending coupling).  What it does not carry - ply-by-ply stress and
interlaminar quantities - is stated as a limitation in the manifest, not
swept under the rug.  Upgrading to true layered S8R is a possible later batch,
not a silent substitution.

The contract
------------
The layup travels in ``spec.structure.params["layup"]`` - a plain dict key,
**not** a dataclass field.  That is the whole point: ``asdict(FEASpec)``
round-trips dict values untouched, so the 40 archived specs (no such key) keep
their byte-identical JSON and their ``spec_sha256``.  This is the T6
``web_chordwise`` lesson applied in reverse.

Shape (mm-tonne-s-MPa)::

    "layup": {
        "plies": [{"angle": 0.0, "thickness": 0.5},
                  {"angle": 90.0, "thickness": 0.5},
                  {"angle": 90.0, "thickness": 0.5},
                  {"angle": 0.0, "thickness": 0.5}],
        "material": {"name": "CFRP_T300", "E1": 140000.0, "E2": 10000.0,
                     "E3": 10000.0, "nu12": 0.30, "nu13": 0.30, "nu23": 0.45,
                     "G12": 5000.0, "G13": 5000.0, "G23": 4000.0,
                     "density": 1.6e-9}
    }

Angles are degrees, measured from the coupon's x-axis (the load direction),
bottom ply first.  Two truths are refused: ``params["thickness"]`` must equal
the ply sum to floating-point tolerance, or :func:`layup_from_params` raises.

The yardstick
-------------
For a **symmetric, balanced** stack the membrane A-matrix is all that matters,
and for ``[0/90]s`` it is hand-checkable in closed form (the yardstick for
``verify_laminate.py``, in the same spirit Howland anchors T4)::

    A11 = A22 = (Q11 + Q22) t / 2        (0 deg and 90 deg plies split the
    A12 = Q12 t                          thickness equally; Q66 is invariant
    A66 = Q66 t                          under 90-degree rotation)

    EX = EY = (A11 - A12^2 / A22) / t,   nu_xy = A12 / A11,   GXY = Q66

The self-test in ``__main__`` pins these numbers; a regression there means
somebody touched the transform, not the material.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# contract objects
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class OrthotropicMaterialSpec:
    """Ply material, engineering constants (mm-tonne-s-MPa).

    The 9 constants are exactly what ``*ELASTIC, TYPE=ENGINEERING
    CONSTANTS`` eats; E3/nu13/nu23/G13/G23 do not enter the membrane CLT
    (plane stress) but the deck card needs them, so they travel with the
    contract rather than being invented at the writer.
    """

    name: str = "CFRP_T300"
    E1: float = 140000.0   # MPa, fibre direction
    E2: float = 10000.0    # MPa, transverse (in ply plane)
    E3: float = 10000.0    # MPa, through-thickness
    nu12: float = 0.30
    nu13: float = 0.30
    nu23: float = 0.45
    G12: float = 5000.0    # MPa
    G13: float = 5000.0    # MPa
    G23: float = 4000.0    # MPa
    density: float = 1.6e-9  # tonne/mm^3 (= 1600 kg/m^3)


@dataclass(frozen=True)
class Ply:
    """One layer: in-plane angle from the coupon x-axis, degrees; thickness mm."""

    angle_deg: float
    thickness: float


@dataclass(frozen=True)
class LayupSpec:
    """An ordered ply stack (bottom first) of one ply material."""

    plies: tuple[Ply, ...]
    material: OrthotropicMaterialSpec

    @property
    def total_thickness(self) -> float:
        return sum(p.thickness for p in self.plies)

    @property
    def is_symmetric(self) -> bool:
        """Midplane-symmetric stack (B = 0, no membrane-bending coupling)."""
        n = len(self.plies)
        return all(
            abs(a.angle_deg - b.angle_deg) < 1e-9
            and abs(a.thickness - b.thickness) < 1e-12
            for a, b in zip(self.plies, reversed(self.plies))
        ) if n else False

    @property
    def is_balanced(self) -> bool:
        """Every off-axis ply has a ``-theta`` partner of equal thickness.

        0 and 90 deg plies are self-balancing (an angle and its 90-degree
        mirror coincide with themselves up to axis swap, which the A-matrix
        averaging handles); ``+theta`` needs a ``-theta`` of the same total
        thickness.

        Angles are compared **as signed pairs**, not by magnitude: normalising
        ``-45`` to ``135`` (``% 180``) and then asking for equal thicknesses
        rejects ``[+45/-45]s``, which is the most common balanced stack there
        is.  Measured 2026-10-24 on the T7 build-out probe: ``[±45]s`` came back
        ``is_balanced = False`` while its A16/A26 were exactly zero - the
        implementation, not the physics, was wrong.  A ply at 135 deg *is* the
        -45 deg partner of a 45 deg ply (135 = 180 - 45), so the two are folded
        into the same key and the *signed* thicknesses are compared there.
        """
        pos: dict[float, float] = {}
        neg: dict[float, float] = {}
        for p in self.plies:
            a = float(p.angle_deg) % 180.0
            if abs(a) < 1e-9 or abs(a - 90.0) < 1e-9:
                continue
            if a > 90.0:                     # -theta, folded to its +|theta| key
                a = 180.0 - a
                neg[round(a, 6)] = neg.get(round(a, 6), 0.0) + float(p.thickness)
            else:                            # +theta
                pos[round(a, 6)] = pos.get(round(a, 6), 0.0) + float(p.thickness)
        return all(abs(pos.get(k, 0.0) - neg.get(k, 0.0)) < 1e-12
                   for k in set(pos) | set(neg))

    @property
    def code(self) -> str:
        """Compact human code, symmetric stacks abbreviated with an ``s``."""
        n = len(self.plies)
        angles = [int(round(p.angle_deg)) for p in self.plies]
        if self.is_symmetric and n >= 2:
            half = angles[: n // 2]
            return "[" + "/".join(str(a) for a in half) + "]s"
        return "[" + "/".join(str(a) for a in angles) + "]"


def layup_from_params(params: dict) -> LayupSpec | None:
    """Read ``structure.params["layup"]`` into a validated :class:`LayupSpec`.

    ``None`` when the key is absent - the archived, isotropic cases.  A present
    but malformed layup raises: a half-parsed stack that quietly fell back to
    aluminium would be a composite case solving an aluminium coupon.

    Also refuses two-truth drift: when the family block carries ``thickness``,
    it must equal the ply sum exactly (to 1e-9).  The shell thickness the deck
    writes is the builder's declaration; the layup is the material truth; if
    they disagree one of them is wrong and this fails loudly instead of
    picking one.
    """
    raw = (params or {}).get("layup")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("layup: expected an object with 'plies' and 'material'")

    mat = OrthotropicMaterialSpec(**(raw.get("material") or {}))
    plies = []
    for i, p in enumerate(raw.get("plies") or []):
        try:
            plies.append(Ply(angle_deg=float(p["angle"]),
                             thickness=float(p["thickness"])))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"layup: ply[{i}] needs numeric 'angle' and "
                             f"'thickness' ({exc!r})") from exc
    if not plies:
        raise ValueError("layup: 'plies' is empty")
    lay = LayupSpec(plies=tuple(plies), material=mat)

    t_params = (params or {}).get("thickness")
    if t_params is not None and abs(float(t_params) - lay.total_thickness) > 1e-9:
        raise ValueError(
            f"layup: params thickness {t_params} != ply sum "
            f"{lay.total_thickness}; two truths, refusing to pick one"
        )
    return lay


def layup_to_params(lay: LayupSpec) -> dict:
    """The JSON dict form that :func:`layup_from_params` reads back."""
    return {
        "plies": [{"angle": float(p.angle_deg), "thickness": float(p.thickness)}
                  for p in lay.plies],
        "material": {
            "name": lay.material.name, "E1": lay.material.E1,
            "E2": lay.material.E2, "E3": lay.material.E3,
            "nu12": lay.material.nu12, "nu13": lay.material.nu13,
            "nu23": lay.material.nu23, "G12": lay.material.G12,
            "G13": lay.material.G13, "G23": lay.material.G23,
            "density": lay.material.density,
        },
    }


# --------------------------------------------------------------------------- #
# CLT - reduced stiffnesses, A matrix, equivalent engineering constants
# --------------------------------------------------------------------------- #

def reduced_stiffness(mat: OrthotropicMaterialSpec) -> tuple[float, float, float, float]:
    """Plane-stress reduced stiffnesses ``(Q11, Q22, Q12, Q66)`` in material axes."""
    nu21 = mat.nu12 * mat.E2 / mat.E1
    denom = 1.0 - mat.nu12 * nu21
    return (mat.E1 / denom, mat.E2 / denom,
            mat.nu12 * mat.E2 / denom, mat.G12)


def rotated_stiffness(q: tuple[float, float, float, float],
                      angle_deg: float) -> tuple[float, float, float, float]:
    """Q-bar: the reduced stiffnesses rotated by the ply angle.

    Standard transformation (Jones, *Mechanics of Composite Materials*);
    ``Q66`` is invariant under 90-degree rotation, which is what makes the
    ``[0/90]s`` yardstick hand-checkable.
    """
    q11, q22, q12, q66 = q
    t = math.radians(angle_deg)
    c, s = math.cos(t), math.sin(t)
    c2, s2 = c * c, s * s
    c4, s4 = c2 * c2, s2 * s2
    q11b = q11 * c4 + 2.0 * (q12 + 2.0 * q66) * s2 * c2 + q22 * s4
    q22b = q11 * s4 + 2.0 * (q12 + 2.0 * q66) * s2 * c2 + q22 * c4
    q12b = (q11 + q22 - 4.0 * q66) * s2 * c2 + q12 * (c4 + s4)
    q66b = (q11 + q22 - 2.0 * q12 - 2.0 * q66) * s2 * c2 + q66 * (c4 + s4)
    return (q11b, q22b, q12b, q66b)


def qbar16_26(q: tuple[float, float, float, float],
              angle_deg: float) -> tuple[float, float]:
    """``(Qbar16, Qbar26)`` - the normal-shear coupling terms (Jones 2.85).

    These are the terms a single equivalent layer can only carry if they are
    zero: they shear the panel when it is pulled.  :func:`a_matrix` now sums
    them for real (it used to hard-write ``0.0``), so ``is_balanced``'s angle
    bookkeeping and the actual physics check each other instead of one of them
    being a comment.
    """
    q11, q22, q12, q66 = q
    t = math.radians(angle_deg)
    c, s = math.cos(t), math.sin(t)
    a = q11 - q12 - 2.0 * q66
    b = q12 - q22 + 2.0 * q66
    return (a * s * c ** 3 + b * s ** 3 * c,
            a * s ** 3 * c + b * s * c ** 3)


def a_matrix(lay: LayupSpec) -> tuple[list[float], list[float], list[float]]:
    """Membrane stiffness matrix ``A`` (force per unit width per unit strain)."""
    q = reduced_stiffness(lay.material)
    a = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    for p in lay.plies:
        q11, q22, q12, q66 = rotated_stiffness(q, p.angle_deg)
        q16, q26 = qbar16_26(q, p.angle_deg)
        t = p.thickness
        a[0][0] += q11 * t; a[0][1] += q12 * t; a[0][2] += q16 * t
        a[1][0] += q12 * t; a[1][1] += q22 * t; a[1][2] += q26 * t
        a[2][0] += q16 * t; a[2][1] += q26 * t; a[2][2] += q66 * t
    return (a[0], a[1], a[2])


def validate_for_deck(lay: LayupSpec) -> None:
    """Refuse layups the equivalent-single-layer route does not describe.

    A stack that is not **symmetric** has a nonzero B matrix: its membrane
    response then depends on bending, which a single equivalent layer cannot
    carry.  A stack that is not **balanced** carries normal-shear coupling
    (A16/A26 != 0): pulling along x shears it, and neither the isotropic
    toolchain nor the simple closed forms describe that.
    """
    if not lay.is_symmetric:
        raise ValueError(
            f"layup {lay.code}: not midplane-symmetric (B != 0); the equivalent "
            f"single-layer contract (D29) only covers symmetric stacks")
    if not lay.is_balanced:
        raise ValueError(
            f"layup {lay.code}: not balanced (A16/A26 != 0, normal-shear "
            f"coupling); the equivalent single-layer contract (D29) only "
            f"covers balanced stacks")
    # Cross-check the angle bookkeeping against the physics it stands for: a
    # stack the bookkeeping calls balanced but whose A16/A26 are not zero would
    # be solved as a shear-coupled panel by a deck that carries no 16/26 term.
    a0, a1, a2 = a_matrix(lay)
    scale = max(abs(a0[0]), abs(a1[1]), abs(a2[2]))
    leak = max(abs(a0[2]), abs(a1[2]))
    if leak > 1e-9 * scale:
        raise ValueError(
            f"layup {lay.code}: A16/A26 = {a0[2]:.6g}/{a1[2]:.6g} against a "
            f"diagonal scale {scale:.6g}; the stack is shear-coupled even "
            f"though its angles pair up - refusing rather than dropping the terms")


def equivalent_engineering_constants(lay: LayupSpec) -> dict:
    """CLT membrane equivalent of the stack, as deck-ready engineering constants.

    Returns ``{EX, EY, nuxy, GXY, E3, nu13, nu23, G13, G23, density,
    thickness, code}``.  In-plane values come from the A matrix; the
    interlaminar trio is the thickness-weighted mean of the ply values - a
    declared homogenisation (the card needs numbers; the membrane gate never
    reads them), not a claim about through-thickness physics.
    """
    validate_for_deck(lay)
    a0, a1, a2 = a_matrix(lay)
    det = (a0[0] * a1[1] - a0[1] * a1[0])
    if det <= 0.0:
        raise ValueError(f"layup {lay.code}: singular A matrix")
    # inverse of the 2x2 in-plane block + the shear term
    a11_inv = a1[1] / det
    a12_inv = -a0[1] / det
    a22_inv = a0[0] / det
    t = lay.total_thickness
    ex = 1.0 / (a11_inv * t)
    ey = 1.0 / (a22_inv * t)
    nuxy = -a12_inv / a11_inv
    # Shear: gamma = a66 * Nx with a66 = inv(A)[2][2] = 1/A66, and the mean
    # stress is Nx / t, so GXY = (Nx/t) / gamma = A66 / t.  (Writing the EX
    # pattern 1/(a66*t) here is exactly the slip this self-test exists for:
    # it reads 1/(Q66 t^2) and the single-ply check - GXY must collapse to
    # G12 - fails loudly.)
    gxy = a2[2] / t

    m = lay.material
    w = [p.thickness / t for p in lay.plies]
    mean = lambda f: sum(wi * getattr(m, f) for wi in w)
    return {
        "EX": ex, "EY": ey, "nuxy": nuxy, "GXY": gxy,
        "E3": m.E3, "nu13": m.nu13, "nu23": m.nu23,
        "G13": mean("G13"), "G23": mean("G23"),
        "density": m.density, "thickness": t, "code": lay.code,
        "name": f"{m.name}_{lay.code}",
    }


# --------------------------------------------------------------------------- #
# self-test - run me directly
# --------------------------------------------------------------------------- #

def _self_test() -> int:
    failures: list[str] = []

    def check(label: str, cond: bool, detail: str = "") -> None:
        print(f"  [{'ok  ' if cond else 'FAIL'}] {label}" + (f" :: {detail}" if detail else ""))
        if not cond:
            failures.append(label)

    m = OrthotropicMaterialSpec()
    t1 = 1.0

    # --- single 0-deg layer must collapse to the material's own constants ----
    uni = LayupSpec(plies=(Ply(0.0, t1),), material=m)
    eq = equivalent_engineering_constants(uni)
    check("single 0-deg ply: EX == E1", abs(eq["EX"] - m.E1) < 1e-6 * m.E1,
          f"EX={eq['EX']:.3f}")
    check("single 0-deg ply: nuxy == nu12", abs(eq["nuxy"] - m.nu12) < 1e-12,
          f"nuxy={eq['nuxy']:.6f}")
    check("single 0-deg ply: GXY == G12", abs(eq["GXY"] - m.G12) < 1e-9)

    # --- [0/90]s against the closed form -------------------------------------
    lay = LayupSpec(plies=(Ply(0.0, 0.5), Ply(90.0, 0.5),
                           Ply(90.0, 0.5), Ply(0.0, 0.5)), material=m)
    check("[0/90]s detected symmetric", lay.is_symmetric)
    check("[0/90]s detected balanced", lay.is_balanced)
    check("[0/90]s code", lay.code == "[0/90]s", lay.code)

    q11, q22, q12, q66 = reduced_stiffness(m)
    ex_closed = (q11 + q22) / 2.0 - q12 ** 2 / ((q11 + q22) / 2.0)
    eq2 = equivalent_engineering_constants(lay)
    check("[0/90]s EX == closed form", abs(eq2["EX"] - ex_closed) < 1e-6,
          f"EX={eq2['EX']:.4f} vs {ex_closed:.4f}")
    check("[0/90]s EY == EX (equally split 0/90)",
          abs(eq2["EY"] - eq2["EX"]) < 1e-6)
    nuxy_closed = q12 / ((q11 + q22) / 2.0)
    check("[0/90]s nuxy == A12/A11", abs(eq2["nuxy"] - nuxy_closed) < 1e-9,
          f"nuxy={eq2['nuxy']:.6f}")
    check("[0/90]s GXY == G12 (Q66 invariant under 90 deg)",
          abs(eq2["GXY"] - m.G12) < 1e-9)

    # --- [±45]s: the angle-ply stack the T7 build-out adds -------------------
    # Hand-derived (plane stress, all plies equal thickness t/4):
    #   A11 = A22 = t * ( (Q11+Q22)/4 + Q12/2 + Q66 )
    #   A12       = t * ( (Q11+Q22-4*Q66)/4 + Q12/2 )
    #   A66       = t * ( (Q11+Q22-2*Q12-2*Q66)/4 + Q66/2 )
    # and A16 = A26 = 0 because Qbar16(45) = -Qbar16(-45).
    lap = LayupSpec(plies=(Ply(45.0, 0.5), Ply(-45.0, 0.5),
                           Ply(-45.0, 0.5), Ply(45.0, 0.5)), material=m)
    check("[+45/-45]s detected balanced", lap.is_balanced,
          f"is_balanced={lap.is_balanced}")
    check("[+45/-45]s code", lap.code == "[45/-45]s", lap.code)
    a0, a1, a2 = a_matrix(lap)
    tp = lap.total_thickness
    a11_c = (q11 + q22) / 4.0 + q12 / 2.0 + q66
    a12_c = (q11 + q22 - 4.0 * q66) / 4.0 + q12 / 2.0
    a66_c = (q11 + q22 - 2.0 * q12 - 2.0 * q66) / 4.0 + q66 / 2.0
    check("[+45/-45]s A11/t == closed form", abs(a0[0] / tp - a11_c) < 1e-6,
          f"{a0[0]/tp:.4f} vs {a11_c:.4f}")
    check("[+45/-45]s A12/t == closed form", abs(a1[0] / tp - a12_c) < 1e-6,
          f"{a1[0]/tp:.4f} vs {a12_c:.4f}")
    check("[+45/-45]s A66/t == closed form", abs(a2[2] / tp - a66_c) < 1e-6,
          f"{a2[2]/tp:.4f} vs {a66_c:.4f}")
    check("[+45/-45]s A16 == A26 == 0 (angle pairing does the work)",
          abs(a0[2]) < 1e-9 and abs(a1[2]) < 1e-9,
          f"A16={a0[2]:.3e} A26={a1[2]:.3e}")

    # --- [0/±45/90]s: quasi-isotropic, a quarter of the thickness per angle --
    #   A11 = A22 = (t/4) * ( 1.5(Q11+Q22) + Q12 + 2Q66 )
    #   A12       = (t/4) * ( 3Q12 + (Q11+Q22)/2 - 2Q66 )
    #   A66       = (t/4) * ( (Q11+Q22)/2 - Q12 + 2Q66 )
    qi = LayupSpec(plies=(Ply(0.0, 0.25), Ply(45.0, 0.25), Ply(-45.0, 0.25),
                          Ply(90.0, 0.25), Ply(90.0, 0.25), Ply(-45.0, 0.25),
                          Ply(45.0, 0.25), Ply(0.0, 0.25)), material=m)
    check("[0/+45/-45/90]s detected balanced+symmetric",
          qi.is_balanced and qi.is_symmetric, qi.code)
    b0, b1, b2 = a_matrix(qi)
    tq = qi.total_thickness
    b11_c = (1.5 * (q11 + q22) + q12 + 2.0 * q66) / 4.0
    b12_c = (3.0 * q12 + (q11 + q22) / 2.0 - 2.0 * q66) / 4.0
    b66_c = ((q11 + q22) / 2.0 - q12 + 2.0 * q66) / 4.0
    check("[0/+45/-45/90]s A11/t == closed form", abs(b0[0] / tq - b11_c) < 1e-6,
          f"{b0[0]/tq:.4f} vs {b11_c:.4f}")
    check("[0/+45/-45/90]s A12/t == closed form", abs(b1[0] / tq - b12_c) < 1e-6,
          f"{b1[0]/tq:.4f} vs {b12_c:.4f}")
    check("[0/+45/-45/90]s A66/t == closed form", abs(b2[2] / tq - b66_c) < 1e-6,
          f"{b2[2]/tq:.4f} vs {b66_c:.4f}")
    check("[0/+45/-45/90]s A11 == A22 (quasi-isotropic in plane)",
          abs(b0[0] - b1[1]) < 1e-6 * b0[0], f"{b0[0]:.3f} vs {b1[1]:.3f}")
    eqq = equivalent_engineering_constants(qi)
    check("[0/+45/-45/90]s EX == EY", abs(eqq["EX"] - eqq["EY"]) < 1e-6 * eqq["EX"],
          f"EX={eqq['EX']:.3f} EY={eqq['EY']:.3f} GXY={eqq['GXY']:.3f} "
          f"nuxy={eqq['nuxy']:.4f}")
    # The independent invariant: a quasi-isotropic stack must satisfy the
    # *isotropic* identity G = E / (2 (1 + nu)).  Nothing in the CLT route is
    # told this; if the rotation, the A-matrix sum or the inversion were wrong,
    # EX/EY would still match each other and this would not.  It also pins the
    # expected nu ~ 1/3 rather than accepting whatever comes out.
    g_iso = eqq["EX"] / (2.0 * (1.0 + eqq["nuxy"]))
    check("[0/+45/-45/90]s GXY == EX/(2(1+nuxy)) [isotropic identity]",
          abs(eqq["GXY"] - g_iso) < 1e-6 * g_iso,
          f"GXY={eqq['GXY']:.4f} vs {g_iso:.4f}")

    # --- the pipeline-facing dict contract round-trips -----------------------
    params = {"thickness": 2.0, "layup": layup_to_params(lay)}
    back = layup_from_params(params)
    check("layup round-trip", back is not None
          and back.code == "[0/90]s"
          and abs(back.total_thickness - 2.0) < 1e-12)
    check("no layup key -> None", layup_from_params({"thickness": 2.0}) is None)
    bad = {"thickness": 2.5, "layup": layup_to_params(lay)}
    try:
        layup_from_params(bad)
        check("thickness mismatch refused", False, "no raise")
    except ValueError as e:
        check("thickness mismatch refused", "two truths" in str(e))

    # --- the D29 refusals are live -------------------------------------------
    unsym = LayupSpec(plies=(Ply(0.0, 0.5), Ply(90.0, 0.5)), material=m)
    unbal = LayupSpec(plies=(Ply(0.0, 0.5), Ply(30.0, 0.5),
                             Ply(30.0, 0.5), Ply(0.0, 0.5)), material=m)
    for label, l in (("non-symmetric refused", unsym),
                     ("unbalanced refused", unbal)):
        try:
            equivalent_engineering_constants(l)
            check(label, False, "no raise")
        except ValueError:
            check(label, True)

    print()
    if failures:
        print(f"{len(failures)} SELF-TEST(S) FAILED: {failures}")
        return 1
    print("ALL SELF-TESTS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
