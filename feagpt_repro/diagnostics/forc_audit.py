#!/usr/bin/env python
"""What does CalculiX's FORC block actually mean here?  (M3 / T2 audit)

Why this exists
---------------
``verify_panel.py`` asserted, for a distributed pressure load, that the sum of
``FORC_z`` over the *clamped* nodes plus the geometrically lumped pressure at
those nodes recovers the total applied load.  Measured, the sum over the panel's
edge nodes came back **+44.20 N** against an applied load of **-36.00 N**.  No
lumping convention can produce that: the lumped share at one ring of elements is
of order 1 N, not 8 N, and it cannot be negative.

An unexplained number is not a result.  So this script stops reasoning from the
narrative ("FORC = applied + reaction") and measures the convention directly on
a case whose answer is known exactly:

* the **wing box** carries a concentrated 500 N force along ``+y`` and a clamped
  root, so its FORC block must show the applied 500 N distributed over the loaded
  nodes and -500 N over the clamped ones, whichever component the load is in.
  Whatever it does here *defines* the convention.
* the **panel** carries the distributed pressure along ``-z``.  The same sums are
  computed and then read against the wing-box answer rather than against a guess.

It also re-reads the deck's own ``*DLOAD`` / ``*BOUNDARY`` blocks, so "36 N" and
"four edges are held" stop being assumptions about the deck writer.

Usage::

    python diagnostics/forc_audit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from feagpt import panel, post  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402

# --------------------------------------------------------------------------- #
# the two case directories.  The pipeline writes ``<outdir>/<name>/<name>.<ext>``
# - the case name appears twice - which is exactly the trap this script was
# first written into: pointing at the directory makes ``<path>.frd`` silently
# not exist.
# --------------------------------------------------------------------------- #
WING_DIR = ROOT / "outputs" / "naca4412_wingbox"
WING_NAME = "naca4412_wingbox"
PANEL_DIR = ROOT / "outputs" / "_verify_panel"
PANEL_CASES = (("plain", "verify_panel_plain_sym", 0),
               ("stiffened", "verify_panel_stiff_sym", 3))
TOL = 1e-3


def base(case_dir: Path, name: str, ext: str) -> Path:
    """Locate ``<name>.<ext>`` under ``case_dir``, nested or not.

    The pipeline writes ``<outdir>/<name>/<name>.<ext>``, but a case that was run
    with ``outdir`` already pointing at its own folder lands as
    ``<case_dir>/<name>.<ext>``.  Both exist in ``outputs/`` (the wing box uses
    the flat layout, the panel runs the nested one), and guessing wrong does not
    raise a useful error - it raises ``FileNotFoundError`` three levels away from
    the mistake.  So both are tried and neither is assumed.
    """
    nested = case_dir / name / f"{name}.{ext}"
    if nested.exists():
        return nested
    flat = case_dir / f"{name}.{ext}"
    if flat.exists():
        return flat
    raise FileNotFoundError(
        f"neither {nested} nor {flat} exists - wrong case dir or name?")


def deck_blocks(path: Path, keyword: str) -> list[str]:
    """The data lines of every ``*<keyword>`` block in the deck, verbatim."""
    out: list[str] = []
    inside = False
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("**"):
            continue
        if s.startswith("*"):
            inside = s.upper().startswith("*" + keyword.upper())
            if inside:
                out.append(s)          # keep the header, its options matter
            continue
        if inside and s:
            out.append("    " + s)
    return out


def read_mesh(path: Path) -> tuple[dict, list[list[int]]]:
    nodes: dict[int, tuple] = {}
    elems: list[list[int]] = []
    mode, cur = None, []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("**"):
            continue
        if s.startswith("*"):
            if mode == "elem" and cur:
                elems.extend(cur)
                cur = []
            u = s.upper()
            mode = ("node" if u.startswith("*NODE,")
                    else "elem" if u.startswith("*ELEMENT,") else None)
            continue
        if mode == "node":
            f = s.split(",")
            nodes[int(f[0])] = tuple(float(v) for v in f[1:4])
        elif mode == "elem":
            f = [t.strip() for t in s.split(",") if t.strip()]
            cur.append([int(v) for v in f[1:]])
    if cur:
        elems.extend(cur)
    return nodes, elems


def poly_area(conn, nodes) -> float:
    """Signed area of a polygon's xy projection (quads here, but general)."""
    a = 0.0
    n = len(conn)
    for i in range(n):
        x1, y1 = nodes[conn[i]][0], nodes[conn[i]][1]
        x2, y2 = nodes[conn[(i + 1) % n]][0], nodes[conn[(i + 1) % n]][1]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def sums(forc: dict, group: set, comp: int) -> float:
    return sum(forc[t][comp] for t in group if t in forc)


def vec_sum(forc: dict, group: set) -> tuple[float, float, float]:
    return tuple(sums(forc, group, c) for c in range(3))


def load_case(case_dir: Path, name: str) -> dict:
    spec_path = base(case_dir, name, "spec.json")
    return {"spec": FEASpec.from_json(spec_path),
            "spec_path": spec_path,
            "inp": base(case_dir, name, "inp"),
            "frd": base(case_dir, name, "frd")}


def report_wing() -> None:
    print("=" * 78)
    print("  WING BOX - concentrated load; this is where the convention is read off")
    print("=" * 78)
    c = load_case(WING_DIR, WING_NAME)
    spec = c["spec"]
    d = tuple(float(v) for v in spec.load.direction)
    print(f"  load: kind {spec.load.kind!r}, magnitude {spec.load.magnitude:g}, "
          f"direction {d}")
    for block in deck_blocks(c["inp"], "CLOAD"):
        print("  " + block)
    for block in deck_blocks(c["inp"], "BOUNDARY"):
        print("  " + block)

    frd = post.parse_frd(c["frd"])
    forc = frd["results"].get("FORC") or {}
    nodes = frd["nodes"]
    print(f"  FRD nodes {len(nodes)}, nodes carrying FORC {len(forc)}, "
          f"components {sorted({len(v) for v in forc.values()})}")
    span = float(spec.airfoil.span)
    root = {t for t, (_x, _y, z) in nodes.items() if abs(z) < TOL}
    tip = {t for t, (_x, _y, z) in nodes.items() if abs(z - span) < TOL}
    alln = set(forc)
    for label, grp in (("root (clamped)", root), ("tip  (loaded)", tip),
                       ("ALL ", alln)):
        v = vec_sum(forc, grp)
        print(f"  {label}  n {len(grp):6d}   "
              f"Fx {v[0]:+11.5f}  Fy {v[1]:+11.5f}  Fz {v[2]:+11.5f} N")
    proj_tip = sum(d[i] * vec_sum(forc, tip)[i] for i in range(3))
    proj_root = sum(d[i] * vec_sum(forc, root)[i] for i in range(3))
    print(f"  -> along the load direction: tip {proj_tip:+.5f} N, "
          f"root {proj_root:+.5f} N")
    print("  READ: the loaded nodes carry the applied force and the clamped ones")
    print("        its opposite; the model sums to zero.  Note the load is along")
    print("        y here - summing the z component, as the first draft did,")
    print("        reports zero for a perfectly correct run.")
    print()


def report_panel(label: str, name: str, n_stringers: int) -> None:
    print("=" * 78)
    print(f"  PANEL '{label}'  ({n_stringers} stringer(s), distributed pressure)")
    print("=" * 78)
    c = load_case(PANEL_DIR, name)
    spec, inp = c["spec"], c["inp"]
    p = panel.parse_params(spec)
    q = float(spec.load.magnitude)
    print(f"  declared: {p.length:g} x {p.width:g} x {p.thickness:g} mm, "
          f"q = {q:g} MPa, kind {spec.load.kind!r}, "
          f"direction {tuple(spec.load.direction)}")
    for block in deck_blocks(inp, "DLOAD"):
        print("  " + block)
    for block in deck_blocks(inp, "BOUNDARY")[:6]:
        print("  " + block)

    nodes, elems = read_mesh(inp)
    area = sum(poly_area(el, nodes) for el in elems)
    outline = {t for t, (x, y, _z) in nodes.items()
               if abs(x) < TOL or abs(x - p.length) < TOL
               or abs(y) < TOL or abs(y - p.width) < TOL}
    applied = q * area
    print(f"  deck mesh: {len(nodes)} nodes, {len(elems)} elements, "
          f"area {area:.3f} mm^2 -> applied {applied:.5f} N")
    print(f"  geometric outline: {len(outline)} nodes, "
          f"{len(nodes) - len(outline)} interior nodes")

    frd = post.parse_frd(c["frd"])
    forc = frd["results"].get("FORC") or {}
    free = set(forc) - outline
    print(f"  FRD nodes {len(frd['nodes'])}, nodes carrying FORC {len(forc)}")
    for lbl, grp in (("outline/held", outline), ("interior/free", free),
                     ("ALL ", set(forc))):
        v = vec_sum(forc, grp)
        print(f"  {lbl:14s} n {len(grp):6d}   "
              f"Fx {v[0]:+11.5f}  Fy {v[1]:+11.5f}  Fz {v[2]:+11.5f} N")
    print(f"  outline Fz / applied = {sums(forc, outline, 2) / applied:+.6f}")
    print()


def main() -> int:
    report_wing()
    for label, name, n in PANEL_CASES:
        report_panel(label, name, n)
    print("=" * 78)
    print("  How to read this")
    print("=" * 78)
    print("  * Wing box: FORC at a loaded node is the applied force, at a clamped")
    print("    node the reaction, and the model sums to zero.  That convention is")
    print("    what the panel equilibrium check assumed - it is not in doubt.")
    print("  * Panel: compare 'outline Fz' with 'applied'.  If the held edge does")
    print("    NOT carry ~the whole applied force, then the deck is not holding")
    print("    what it thinks it holds, and that is a geometry/BC bug, not a")
    print("    result-reduction bug.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
