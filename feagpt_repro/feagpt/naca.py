"""NACA 4-digit airfoil geometry.

Reference
---------
Abbott & von Doenhoff, *Theory of Wing Sections*, NACA Report 824 (1945),
and the standard NACA 4-digit definitions.

This module is pure NumPy with no external dependencies, so airfoil
coordinates can be generated independently of the meshing back-end.  That
independence is deliberate: it lets us cross-check the geometry that the CAD
kernel produces against a closed-form source.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _chordwise_spacing(n: int, spacing: str) -> np.ndarray:
    """Return ``n`` chordwise stations in ``[0, 1]``.

    ``cosine`` packs points towards the leading edge, which is where the
    curvature is highest and where a uniform grid would be poorest.
    """
    if n < 2:
        raise ValueError("need at least 2 chordwise stations")
    xi = np.linspace(0.0, 1.0, n)
    if spacing == "cosine":
        return 0.5 * (1.0 - np.cos(np.pi * xi))
    if spacing == "uniform":
        return xi
    raise ValueError(f"unknown spacing {spacing!r} (use 'cosine' or 'uniform')")


@dataclass(frozen=True)
class NACA4:
    """A NACA 4-digit airfoil defined by ``(m, p, t)``.

    Parameters
    ----------
    m :
        Maximum camber as a fraction of chord (0.04 for the ``44xx`` family).
    p :
        Chordwise position of maximum camber as a fraction of chord (0.4).
    t :
        Maximum thickness as a fraction of chord (0.12).
    trailing_edge_open :
        ``True``  -> original open-TE coefficient ``-0.1015``.
        ``False`` -> closed-TE coefficient ``-0.1036`` so the upper and lower
        surfaces meet exactly at ``x = 1`` (required for a watertight shell).
    """

    m: float
    p: float
    t: float
    trailing_edge_open: bool = False

    # ------------------------------------------------------------------ #
    # constructors / helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def from_code(cls, code: str, trailing_edge_open: bool = False) -> "NACA4":
        """Build from a 4-digit code such as ``"4412"``."""
        code = str(code).strip()
        if len(code) == 5 and code.startswith("0"):
            code = code[1:]  # tolerate "04412" style
        if len(code) != 4 or not code.isdigit():
            raise ValueError(f"expected a 4-digit NACA code, got {code!r}")
        m = int(code[0]) / 100.0
        p = int(code[1]) / 10.0
        t = int(code[2:]) / 100.0
        if m > 0.0 and p == 0.0:
            raise ValueError(
                f"NACA {code}: camber m={m} requires a non-zero camber position"
            )
        return cls(m=m, p=p, t=t, trailing_edge_open=trailing_edge_open)

    @property
    def code(self) -> str:
        return f"{int(round(self.m * 100))}{int(round(self.p * 10))}{int(round(self.t * 100)):02d}"

    # ------------------------------------------------------------------ #
    # thickness / camber distributions
    # ------------------------------------------------------------------ #
    def half_thickness(self, x) -> np.ndarray:
        """Half thickness distribution ``y_t(x)``, x normalised to chord."""
        x = np.asarray(x, dtype=float)
        a4 = -0.1015 if self.trailing_edge_open else -0.1036
        return 5.0 * self.t * (
            0.2969 * np.sqrt(np.clip(x, 0.0, None))
            - 0.1260 * x
            - 0.3516 * x**2
            + 0.2843 * x**3
            + a4 * x**4
        )

    def camber_line(self, x) -> np.ndarray:
        """Mean camber line ``y_c(x)``."""
        x = np.asarray(x, dtype=float)
        y = np.zeros_like(x)
        if self.m == 0.0:
            return y
        p = self.p
        fwd = x < p
        aft = ~fwd
        y[fwd] = (self.m / p**2) * (2.0 * p * x[fwd] - x[fwd] ** 2)
        y[aft] = (self.m / (1.0 - p) ** 2) * (
            (1.0 - 2.0 * p) + 2.0 * p * x[aft] - x[aft] ** 2
        )
        return y

    def camber_slope(self, x) -> np.ndarray:
        """``dy_c/dx``.  Continuous at ``x = p`` by construction."""
        x = np.asarray(x, dtype=float)
        if self.m == 0.0:
            return np.zeros_like(x)
        p = self.p
        dy = np.empty_like(x)
        fwd = x < p
        aft = ~fwd
        dy[fwd] = (2.0 * self.m / p**2) * (p - x[fwd])
        dy[aft] = (2.0 * self.m / (1.0 - p) ** 2) * (p - x[aft])
        return dy

    # ------------------------------------------------------------------ #
    # surfaces
    # ------------------------------------------------------------------ #
    def surface(self, n: int = 161, spacing: str = "cosine"):
        """Return ``(upper, lower)`` as ``(n, 2)`` arrays in chord units.

        Both start at the leading edge (``x = 0``) and end at the trailing
        edge (``x = 1``).  For a closed trailing edge the two points coincide.
        """
        xc = _chordwise_spacing(n, spacing)
        yt = self.half_thickness(xc)
        yc = self.camber_line(xc)
        theta = np.arctan(self.camber_slope(xc))
        sin_t, cos_t = np.sin(theta), np.cos(theta)

        xu = xc - yt * sin_t
        yu = yc + yt * cos_t
        xl = xc + yt * sin_t
        yl = yc - yt * cos_t

        upper = np.column_stack([xu, yu])
        lower = np.column_stack([xl, yl])
        return upper, lower

    def closed_outline(self, n: int = 161, spacing: str = "cosine") -> np.ndarray:
        """Closed loop: upper TE -> LE -> lower TE (``2n - 1`` points).

        The leading-edge point is shared, so the two surfaces are welded into a
        single watertight wire suitable for a shell mid-surface.
        """
        upper, lower = self.surface(n=n, spacing=spacing)
        upper = upper[::-1]        # TE -> LE
        lower = lower[1:]          # skip duplicated LE
        return np.vstack([upper, lower])

    # ------------------------------------------------------------------ #
    # self-check
    # ------------------------------------------------------------------ #
    def area(self, n: int = 4001) -> float:
        """Cross-sectional area in chord^2, by the trapezoidal rule."""
        outline = self.closed_outline(n=n, spacing="cosine")
        x, y = outline[:, 0], outline[:, 1]
        return float(0.5 * np.abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


if __name__ == "__main__":  # pragma: no cover - smoke test
    af = NACA4.from_code("4412")
    up, lo = af.surface(n=11)
    print(f"NACA {af.code}  m={af.m} p={af.p} t={af.t}")
    print("max half-thickness :", af.half_thickness(np.array([0.3]))[0])
    print("closed-TE gap      :", abs(up[-1, 1] - lo[-1, 1]))
    print("outline points     :", af.closed_outline(n=161).shape)
    print("section area       :", af.area())
