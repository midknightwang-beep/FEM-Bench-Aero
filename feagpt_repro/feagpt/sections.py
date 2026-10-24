"""Stringer cross-section library (M3 / task T5).

A stringer is idealised as a set of **flat shell strips**: each strip is a 2D
segment in the x-y plane, extruded along the span.  This is the abstraction that
turns "one hard-coded blade" into a family of sections - the builder no longer
knows what shape a stringer is, it just extrudes whatever segments the section
returns.

Why ``n_faces`` is not ``len(segments)``
----------------------------------------
Measured, not assumed (``diagnostics/t_stringer_probe.py``):

* Two flat strips that merely **touch in space are not connected**.  Built as
  two independent extrudes, a web and a flange share **0 nodes** after meshing,
  so the flange is a floating cantilever - and a linear static solve still
  returns "displacements", so no numerical gate notices.
* Running ``occ.fragment`` on them produces a shared edge *and* shared nodes
  (measured: 1 shared boundary curve and 11 shared nodes per face pair).
* The cost is that the flange is cut in two by the web: a **T section is 3
  faces** (1 web + 2 flange halves), not 2.

So the topology expectation cannot be derived from the number of segments -
it has to come from the section itself, which is what ``n_faces`` carries.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SectionGeometry:
    """One stringer section, in the wing-box x-y convention.

    Coordinates are absolute mm.  ``y_top`` is the bonded edge (the point on the
    skin); the section extends in the direction ``sgn`` (``-1`` down from the
    upper skin, ``+1`` up from the lower skin).
    """

    segments: tuple
    """``((p0, p1), ...)``. Each strip is a flat shell face once extruded."""

    role: tuple
    """``"web" | "flange"`` per segment, same order. Drives the boolean: webs are
    the objects, flanges the tools, so every flange is split by the web it
    hangs off."""

    n_faces: int
    """Faces in the section **after** the strips are bonded (see module docstring)."""

    label: str = "blade"


def blade(x_mm: float, y_top: float, sgn: float, h: float, **kw) -> SectionGeometry:
    """Standing (blade) stringer: a single vertical web.  The M1/M2 shape."""
    return SectionGeometry(
        segments=(((x_mm, y_top), (x_mm, y_top + sgn * h)),),
        role=("web",),
        n_faces=1,
        label="blade",
    )


def tee(x_mm: float, y_top: float, sgn: float, h: float,
        flange_width: float = 30.0, **kw) -> SectionGeometry:
    """T section: vertical web plus a flange across its free edge.

    The flange is centred on the web, so the boolean cuts it into two equal
    halves -> 3 faces (measured).

    Degeneration
        ``flange_width <= 0`` means *no flange*, and a flanged section with no
        flange **is a blade** - so it returns :func:`blade` verbatim rather than
        a zero-width strip.  This is a contract, not a convenience: it gives the
        family a defined way back to the M1/M2 shape, which is what makes the
        degradation self-check (:mod:`check_forms`) possible.  A zero-width
        flange built literally would be a degenerate surface - it would mesh
        nothing, or worse, mesh a sliver - and gate 4 could not tell the two
        outcomes apart.
    """
    if float(flange_width) <= 0.0:
        return blade(x_mm, y_top, sgn, h, **kw)
    y_bot = y_top + sgn * h
    half = 0.5 * float(flange_width)
    return SectionGeometry(
        segments=(
            ((x_mm, y_top), (x_mm, y_bot)),                  # web
            ((x_mm - half, y_bot), (x_mm + half, y_bot)),    # flange
        ),
        role=("web", "flange"),
        n_faces=3,
        label="T",
    )


SECTIONS = {
    "blade": blade,
    "T": tee,
    "t": tee,          # tolerate a lower-case spelling
}
"""Section kind -> builder.  M3 ships blade + T; L / hat / omega are additive
(their strips are just more segments) and are deliberately left to M5 so the
first batch stays verifiable."""


def section(kind: str, x_mm: float, y_top: float, sgn: float, h: float,
            **kw) -> SectionGeometry:
    """Dispatch to a section builder; unknown kinds raise rather than default.

    A silent fallback to ``blade`` would build a stringer with no flange for a
    request that asked for one - the exact "runs fine, is wrong" failure the
    semantic gate exists to catch.
    """
    try:
        builder = SECTIONS[kind]
    except KeyError:
        raise ValueError(
            f"unknown stringer section {kind!r}; registered: {sorted(SECTIONS)}"
        ) from None
    return builder(x_mm, y_top, sgn, h, **kw)


def faces_per_section(kind: str, flange_width: float | None = None) -> int:
    """How many shell faces one stringer of this section becomes.

    The topology expectation is a statement about *faces*, so it needs this
    number: a blade is 1, a T is 3 (web + the flange cut in two by the web - see
    the module docstring).  It is read off the section definition, **not**
    measured on a built model, or gate 4 would be checking the builder against
    itself.

    ``flange_width`` is passed through because the section is not fully
    determined by its name: ``T`` with ``flange_width <= 0`` degenerates to a
    blade and therefore contributes **1** face, not 3.  Leaving the width out
    here would make gate 4 demand 3 faces per stringer for a model that
    correctly has 1 - i.e. the gate would reject the *right* build.
    ``None`` (the default) means "use the section's own default width".
    """
    kw = {} if flange_width is None else {"flange_width": float(flange_width)}
    return section(kind, 0.0, 0.0, -1.0, 1.0, **kw).n_faces
