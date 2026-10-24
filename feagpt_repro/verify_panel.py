#!/usr/bin/env python
"""Independent verification of the stiffened-panel chain (M3 / task T2).

A panel is not "verified" because ccx exited 0.  Gate 4 says the model *is* what
the spec asked for; nothing so far says the numbers are **right**.  So the same
chain (geometry -> mesh -> deck -> CalculiX -> FRD) is run on a problem with a
closed-form answer, exactly as ``verify_cantilever.py`` does for the wing box.

The seven checks, and what each one is worth
--------------------------------------------
1. **Navier double-sine solution** of a simply supported rectangular plate,
   compared against the *stringer-free* panel.  Independent of our codebase,
   exact for the model it describes, and the strongest available statement about
   the whole new path: the four-edge support, the pressure load, the shell
   section and the results reduction all have to be right for it to pass.  Also
   run at a second, finer mesh size - the gap must shrink, or "discretisation"
   would be an excuse rather than an explanation.
2. **Total applied load, from the mesh.**  The loaded area is integrated from
   the deck's own element connectivity and node coordinates and must equal
   ``length x width``; so the pressure acts on the whole skin and *only* the
   skin.  Measured on the stiffened panel: 360000 mm^2, i.e. the stringers are
   not being pressurised (that would add 3 x 600 x 20 = 36000 mm^2, a 10 %
   overload no displacement check would notice).
3. **Global equilibrium.**  CalculiX's FORC block holds the *total* external
   force at a node - applied load at free nodes, reaction at constrained ones
   (measured on the wing box, where the load is along ``+y``: ``Fy`` is
   +500.00046 N over the loaded tip and -500.00017 N over the clamped root).
   Summed over the **whole model** the two cancel, so ``sum(FORC_z) ~ 0``.  This
   is the assumption-free equilibrium statement and it is checked first: no
   lumping model, no choice of node set, nothing to get wrong.
4. **The support carries the load.**  With a *distributed* load the held nodes
   also carry applied pressure, so ``FORC = applied + reaction = -q A_node + R``
   and the reaction is recovered by adding the quarter-element lumping back.
   ``q A_element/4`` per node is predicted from the mesh, not fitted; it is
   1.8 % of the load, i.e. small but ten times the tolerance, so it cannot be
   waived.  The node set here must be the **full outline, corners included** -
   the four corners carry -0.62 N between them, an amount comparable to the
   correction itself (see :func:`outline_nodes`).
5. **Reaction symmetry.**  The panel and its stringer layout are symmetric about
   both mid-lines, so *opposite* edges must carry equal load - and only opposite
   edges.  The stringers run along y, so the x-edges and the y-edges are
   different members carrying different load (measured 3.33 N vs 14.65 N), and a
   check that demanded all four be equal would be demanding that correct physics
   be false.
6. **Stiffening.**  The stiffened panel must be substantially stiffer than the
   plain one.  Measured ratio is ~63; a detached stringer (measured elsewhere to
   share **0 nodes** with the skin) would give ~1 and would still solve.
7. **Outer-fibre stress against the closed form (D8).**  The archive's stress is
   the **outer fibre**, which CalculiX only reaches through ``OUTPUT=3D``.  That
   machinery is checked here against ``6 Mx/t^2`` from the same double-sine
   series, at the node nearest the plate centre: measured within 0.5 %.  The
   model-wide maximum is deliberately *not* asserted on - it sits in the
   supported-edge shear layer and reads ~12 % above the closed form.

Usage::

    python verify_panel.py                       # production meshes
    python verify_panel.py --json verify_panel.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feagpt import panel, pipeline, post  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402

LENGTH = 600.0
WIDTH = 600.0
THICKNESS = 2.0
PRESSURE = 1e-4
#: Coarse step of the convergence sweep.  The sweep is ``SIZE -> SIZE/2`` and the
#: *fine* end must be the mesh the archive actually ships, so that the pair
#: brackets the production model instead of some historical one.  The family's
#: own default is the single source of truth for that (D9 moved the panel family
#: 6 -> 3 mm); hard-coding 3 here would silently drift the moment D9 is revisited.
SIZE = 2.0 * panel.DEFAULT_MESH_SIZE
TOL_NAVIER = 2.0            # %, measured 0.097 % at the production mesh (3 mm)
TOL_EQUILIBRIUM = 0.5       # %, measured 0.005 % (global) and 0.02 % (support)
TOL_SYMMETRY = 3.0          # %, opposite edges.  Measured 0.06-0.08 % on the
#                             stiffened panel, but 1.8 % on the plain plate: the
#                             frontal-Delaunay + blossom mesh is not
#                             mirror-symmetric about the mid-lines, so a square
#                             plate's four edge reactions are not either.  The
#                             tolerance is set by that mesh artefact, not by the
#                             physics, and 3 % still catches the 77 % a
#                             corner-to-corner comparison produced.
MIN_STIFFENING = 5.0        # w_plain / w_stiffened must exceed this
TOL_STRESS = 5.0            # %, outer-fibre stress vs Navier at the centre.
#                             Measured -0.15 % on a 120 mm probe plate and
#                             -0.22 % on the 600 mm production plate (3 mm,
#                             node 13221), so this is a loose bound on a tight
#                             agreement: it is set by how far the nearest node
#                             sits from the exact centre, not by the physics.


# --------------------------------------------------------------------------- #
# closed forms
# --------------------------------------------------------------------------- #
def navier_wmax(a: float, b: float, q: float, t: float, E: float, nu: float,
                nmax: int = 401) -> float:
    """Simply supported rectangular plate, uniform load - the Navier solution.

        w = 16q/(pi^6 D) * sum_{m,n odd} (-1)^((m-1)/2+(n-1)/2)
                                     / (m n ((m/a)^2 + (n/b)^2)^2)

    The signs matter: the load expansion has all-positive coefficients, but the
    *centre* of the plate is where successive terms alternate.  Dropping them
    (an easy mistake - it still looks like a plate solution) inflates w by ~35 %
    on a square plate.

    Anchor: for a square plate this must reproduce the tabulated
    ``0.00406 q a^4 / D``; :func:`main` prints the ratio so a regression in the
    formula is visible rather than silent.
    """
    D = E * t**3 / (12.0 * (1.0 - nu**2))
    s = 0.0
    for m in range(1, nmax + 1, 2):
        sm = 1.0 if ((m - 1) // 2) % 2 == 0 else -1.0
        for n in range(1, nmax + 1, 2):
            sn = 1.0 if ((n - 1) // 2) % 2 == 0 else -1.0
            s += sm * sn / (m * n * ((m / a) ** 2 + (n / b) ** 2) ** 2)
    return 16.0 * q / (math.pi**6 * D) * s


def subpanel_wmax(pitch: float, span: float, q: float, t: float, E: float,
                  nu: float) -> float:
    """The same closed form on one bay between two stringers.

    A *reported* number, not an assertion.  It assumes the stringers are rigid,
    which they are not, and it ignores the rotational restraint a 20 mm deep web
    gives the skin - so it is neither a strict upper nor a strict lower bound.
    It is printed because "the panel behaves like a plate spanning the stringer
    pitch" is the physical statement the case is meant to demonstrate, and a
    number is how that gets checked by eye.
    """
    return navier_wmax(pitch, span, q, t, E, nu)


def navier_sigma_max(a: float, b: float, q: float, t: float, nu: float,
                     nmax: int = 601) -> float:
    """Maximum bending stress at the centre of the same Navier plate.

    Differentiating the w series twice gives the central moment

        Mx = 16q/pi^4 * sum_{m,n odd} s_m s_n [(m/a)^2 + nu (n/b)^2]
                                    / (m n ((m/a)^2 + (n/b)^2)^2)

    with ``s_m = (-1)^((m-1)/2)``, and then ``sigma = 6 Mx / t^2``.  On a square
    plate ``Mx = My`` at the centre, so von Mises equals that same number.

    **The alternating sign is the whole subtlety, and it is where this function
    was first written wrong.**  ``w,xx`` at the centre already carries
    ``sin(m pi/2) = s_m`` from the *shape* function; substituting
    ``s_m`` for the sine and then multiplying by ``s_m`` again doubles the sign
    and turns the sum all-positive, which inflates it by ~37 % on a square
    plate (0.0705 -> 0.0967 on the 120 mm probe).  It still looks like a plate
    formula, which is why the probe's displacement fit is quoted beside it as
    an independent witness: 0.07014 from the FE deflection, 0.07055 here.
    """
    s = 0.0
    for m in range(1, nmax + 1, 2):
        sm = 1.0 if ((m - 1) // 2) % 2 == 0 else -1.0
        for n in range(1, nmax + 1, 2):
            sn = 1.0 if ((n - 1) // 2) % 2 == 0 else -1.0
            s += sm * sn * ((m / a) ** 2 + nu * (n / b) ** 2) / (
                m * n * ((m / a) ** 2 + (n / b) ** 2) ** 2)
    Mx = 16.0 * q / math.pi**4 * s
    return 6.0 * Mx / t**2


# --------------------------------------------------------------------------- #
# one production-path run
# --------------------------------------------------------------------------- #
def make_spec(name: str, n_stringers: int, size: float) -> FEASpec:
    """The production panel spec, from the family's own factory.

    A thin alias rather than a second definition, on purpose: the verification
    line and the shipped cases have to be *the same* panel, and a local copy of
    "600 x 600 x 2, blade stringers, 6 mm mesh" is precisely how the two come to
    differ.  The dimensions are still passed explicitly (rather than left to the
    family defaults) so this module's constants remain the ones a reader can
    check the closed forms against.
    """
    return panel.make_spec(name, n_stringers=n_stringers, size=size,
                           length=LENGTH, width=WIDTH, thickness=THICKNESS,
                           pressure=PRESSURE)


def run_case(name: str, n_stringers: int, size: float) -> dict:
    spec = make_spec(name, n_stringers, size)
    res = pipeline.run(spec, outdir=Path("outputs/_verify_panel") / name,
                       solver_name="ccx")
    if not res.ok:
        return {"ok": False, "name": name, "log": res.messages[-4:]}
    # load_any, not parse_frd: since D8 a ccx deck asks for OUTPUT=3D (the
    # expanded shell), whose node labels are offset from the deck's - and
    # check_case compares the FRD's fields against deck-derived node sets, so a
    # raw read would match nothing and the checks would pass on empty sets.
    # load_any folds the expanded shell back onto the mid-surface and keeps the
    # outer fibre alongside it as STRESS_PEAK.
    frd = post.load_any(Path(res.artifacts["frd"]))
    peak = frd["results"].get("STRESS_PEAK") or {}
    peak_vm = {n: post.von_mises(v) for n, v in peak.items()}
    cen = min(frd["nodes"],
              key=lambda n: (frd["nodes"][n][0] - LENGTH / 2) ** 2
                            + (frd["nodes"][n][1] - WIDTH / 2) ** 2)
    return {
        "ok": True,
        "name": name,
        "n_stringers": n_stringers,
        "size": size,
        "n_nodes": res.mesh["n_nodes"],
        "n_elements": res.mesh["n_elements"],
        "element_types": res.mesh["element_types"],
        "min_quality": res.mesh["min_quality"],
        "gate4": res.geometry["topology"] is not None and pipeline.topology.compare(
            res.geometry["topology"])["pass"],
        "max_disp": res.results.get("max_disp"),
        "max_w": res.results.get("max_w"),
        "max_vm_mid": res.results.get("max_von_mises_midsurface"),
        "peak_vm_centre": peak_vm.get(cen),
        "peak_vm_centre_node": cen,
        "peak_vm_centre_coord": frd["nodes"][cen],
        "peak_vm_max": max(peak_vm.values()) if peak_vm else None,
        "pressure": float(spec.load.magnitude),
        "deck": res.artifacts["inp"],
        "data": frd,
    }


# --------------------------------------------------------------------------- #
# an independent reading of the deck (no pipeline objects involved)
# --------------------------------------------------------------------------- #
def read_deck(path) -> tuple[dict, list[list[int]]]:
    """Parse *NODE and *ELEMENT straight out of the deck text."""
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


def quad_area(conn: list[int], nodes: dict) -> float:
    a = 0.0
    n = len(conn)
    for i in range(n):
        x1, y1 = nodes[conn[i]][0], nodes[conn[i]][1]
        x2, y2 = nodes[conn[(i + 1) % n]][0], nodes[conn[(i + 1) % n]][1]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def edge_membership(nodes: dict, tol: float = 1e-3):
    """Split the boundary nodes into four edges, corners excluded.

    The four sums are then *independent*, which is what makes them worth
    comparing.  They are **not**, however, the set the deck holds - see
    :func:`outline_nodes` for that, and for why the distinction matters.
    """
    xs = [v[0] for v in nodes.values()]
    ys = [v[1] for v in nodes.values()]
    lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)
    edges: dict[str, set] = {k: set() for k in ("x0", "x1", "y0", "y1")}
    for tag, (x, y, _z) in nodes.items():
        on_x0 = abs(x - lo_x) < tol
        on_x1 = abs(x - hi_x) < tol
        on_y0 = abs(y - lo_y) < tol
        on_y1 = abs(y - hi_y) < tol
        # corners belong to two edges; leaving them out of all four keeps the
        # sums independent, which is what makes the comparison meaningful
        if on_x0 and not (on_y0 or on_y1):
            edges["x0"].add(tag)
        if on_x1 and not (on_y0 or on_y1):
            edges["x1"].add(tag)
        if on_y0 and not (on_x0 or on_x1):
            edges["y0"].add(tag)
        if on_y1 and not (on_x0 or on_x1):
            edges["y1"].add(tag)
    return edges


def outline_nodes(nodes: dict, tol: float = 1e-3) -> set:
    """Every node on the four supported edges - corners **included**.

    This is the set the deck actually holds (``*BOUNDARY NEDGES, 1, 3``), and it
    is therefore the only set over which "the support carries the load" is a
    true statement.

    Using the corner-excluded split here instead was this script's first
    mistake, and it was not a cosmetic one: the four corner nodes carry
    **-0.62 N in total** (measured below on the stiffened panel), which is of the
    same order as the whole pressure-lumping correction being applied.  Draining
    a term the size of the effect under test is how a check comes to report a
    200 % error on a model that is in equilibrium to one part in 10^5.
    """
    xs = [v[0] for v in nodes.values()]
    ys = [v[1] for v in nodes.values()]
    lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)
    return {tag for tag, (x, y, _z) in nodes.items()
            if abs(x - lo_x) < tol or abs(x - hi_x) < tol
            or abs(y - lo_y) < tol or abs(y - hi_y) < tol}


# --------------------------------------------------------------------------- #
def check_case(run: dict, label: str, p: panel.PanelParams) -> tuple[list[dict], dict]:
    """Load/equilibrium/symmetry checks for one finished run."""
    checks: list[dict] = []
    nodes, elems = read_deck(run["deck"])
    frd = run["data"]
    forc = frd["results"].get("FORC") or {}
    # The pressure is read off the run's own spec, not off this module's
    # constant: if they ever disagree, the check should be comparing the load the
    # solver was actually given.
    q = float(run.get("pressure") or PRESSURE)
    area_declared = p.length * p.width
    str_area = (p.n_stringers * p.stringer_height * p.width
                if p.n_stringers else 0.0)

    # ---- 2. loaded area, from the mesh ---------------------------------- #
    area = sum(quad_area(c, nodes) for c in elems)
    err_area = abs(area - area_declared) / area_declared * 100.0
    checks.append({
        "key": f"{label}.loaded-area",
        "pass": err_area < 1e-6,
        "detail": f"mesh-integrated loaded area {area:.4f} mm^2 vs plate "
                  f"{area_declared:.1f} mm^2 -> {err_area:.2e} % "
                  f"(the stringers would add {str_area:.0f} mm^2, "
                  f"{str_area / area_declared * 100:.1f} %)",
    })

    # ---- 3a. global equilibrium, with no lumping model in the way -------- #
    # FORC holds the total external force at a node; applied at free nodes,
    # reaction at held ones.  Over the whole model the two must cancel, and that
    # statement needs no geometric assumption at all - which is exactly what
    # makes it the right first check.  (Anchored on the wing box, where FORC is
    # +500.00046 N over the loaded tip and -500.00017 N over the clamped root.)
    s_all = sum(forc[n][2] for n in forc if len(forc[n]) > 2)
    applied = q * area
    err_all = abs(s_all) / applied * 100.0
    checks.append({
        "key": f"{label}.global-sum",
        "pass": err_all < TOL_EQUILIBRIUM,
        "detail": f"sum(FORC_z) over all {len(forc)} nodes {s_all:+.6f} N vs "
                  f"applied {applied:.5f} N -> {err_all:.5f} % "
                  f"(must be ~0; no lumping model involved)",
    })

    # ---- 3b. the supported edge is what carries it ----------------------- #
    # At this point a lumping model *is* needed: the held nodes carry applied
    # pressure as well as reaction (FORC = applied + reaction = -q*A_node + R),
    # so the reaction is recovered by adding the quarter-element lumping back.
    # q*A_element/4 per node is the standard quad lumping, predicted from the
    # mesh rather than fitted, and it is 1.8 % of the load here - small, but ten
    # times the tolerance, so it cannot simply be waived.
    held = outline_nodes(nodes)
    a_e = 0.0
    for conn in elems:
        a_e += q * quad_area(conn, nodes) * sum(1 for t in conn if t in held) / len(conn)
    sum_held = sum(forc[n][2] for n in held if n in forc and len(forc[n]) > 2)
    reaction = sum_held + a_e
    err_eq = abs(reaction - applied) / applied * 100.0
    checks.append({
        "key": f"{label}.support-reaction",
        "pass": err_eq < TOL_EQUILIBRIUM,
        "detail": f"sum(FORC_z) over {len(held)} held edge nodes {sum_held:+.5f} N "
                  f"+ pressure lumped on them {a_e:+.5f} N = reaction "
                  f"{reaction:+.5f} N vs applied {applied:.5f} N "
                  f"-> {err_eq:.4f} %",
    })

    # ---- 4. reaction symmetry ------------------------------------------- #
    # The panel and its stringer layout are symmetric about both mid-lines, so
    # *opposite* edges must carry equal load.  All four must **not**: the
    # stringers run along y, so the x-edges (across the stringers) and the
    # y-edges (along them, taking the stringer shear) are different members
    # carrying different load - measured 3.33 N vs 14.65 N on the stiffened
    # panel.  Comparing all four, as the first draft did, therefore demanded
    # that correct physics be false.
    edges = edge_membership(nodes)
    sums = {k: sum(forc[n][2] for n in v if n in forc and len(forc[n]) > 2)
            for k, v in edges.items()}
    pairs = {"x0/x1": (sums["x0"], sums["x1"]), "y0/y1": (sums["y0"], sums["y1"])}
    dev = {k: abs(a - b) / max(abs(a), abs(b), 1e-12) * 100.0
           for k, (a, b) in pairs.items()}
    worst = max(dev.values())
    checks.append({
        "key": f"{label}.reaction-symmetry",
        "pass": worst < TOL_SYMMETRY,
        "detail": "edge sums " + ", ".join(f"{k} {v:+.4f}" for k, v in sums.items())
                  + f" N -> opposite-edge spread "
                  + ", ".join(f"{k} {v:.3f} %" for k, v in dev.items())
                  + f" (worst {worst:.3f} %)",
    })
    info = {"edge_reaction_sums": {k: round(v, 6) for k, v in sums.items()},
            "held_edges": {"n": len(held), "sum_forc_z": round(sum_held, 6),
                           "lumped_pressure": round(a_e, 6),
                           "reaction": round(reaction, 6)},
            "global_sum_fz": round(s_all, 9),
            "opposite_edge_dev_pct": {k: round(v, 6) for k, v in dev.items()}}
    return checks, info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sizes", type=float, default=SIZE,
                    help="mesh size for the plain-plate Navier check (mm)")
    ap.add_argument("--json", help="write the machine-readable report here")
    args = ap.parse_args(argv)

    E, nu = 73100.0, 0.33
    D = E * THICKNESS**3 / (12.0 * (1.0 - nu**2))
    nav = navier_wmax(LENGTH, WIDTH, PRESSURE, THICKNESS, E, nu)
    coeff = nav / (PRESSURE * LENGTH**4 / D)

    print("=" * 78)
    print("  STIFFENED PANEL VERIFICATION - closed form + invariants")
    print("=" * 78)
    print(f"  plate {LENGTH:g} x {WIDTH:g} x {THICKNESS:g} mm | q = {PRESSURE:g} MPa | "
          f"E = {E:g} MPa nu = {nu}")
    print(f"  D = {D:.1f} N.mm | Navier w_max = {nav:.5f} mm "
          f"({coeff:.5f} q a^4/D, tabulated 0.00406)")
    print("-" * 78)

    checks: list[dict] = []
    report: dict = {"navier_wmax": nav, "navier_coefficient": coeff, "runs": {}}

    # ---- 1. plain plate vs Navier, at two mesh sizes --------------------- #
    for size, label in ((args.sizes, "coarse"), (args.sizes / 2.0, "fine")):
        r = run_case(f"verify_panel_plain_{label}", 0, size)
        report["runs"][label] = {k: v for k, v in r.items() if k != "data"}
        if not r["ok"]:
            print(f"  [{label}] SOLVER FAILED {r['log']}")
            return 2
        err = (abs(r["max_w"]) - nav) / nav * 100.0
        checks.append({
            "key": f"plain/{label}.navier",
            "pass": abs(err) < TOL_NAVIER,
            "detail": f"{size:g} mm mesh, {r['n_elements']} elems, "
                      f"{r['element_types']} | w_max {abs(r['max_w']):.5f} mm vs Navier "
                      f"{nav:.5f} mm -> {err:+.3f} %",
        })
        report["runs"][label]["navier_err_pct"] = err
        print(f"  plain [{label:6s}] {size:4g} mm  elem {r['n_elements']:6d} "
              f"minJ {r['min_quality']:.3f} | w_max {abs(r['max_w']):.5f} mm -> "
              f"{err:+.3f} % vs Navier")

    coarse = report["runs"]["coarse"]["navier_err_pct"]
    fine = report["runs"]["fine"]["navier_err_pct"]
    conv = {"key": "plain.convergence", "pass": abs(fine) <= abs(coarse) + 1e-9,
            "detail": f"|err| coarse {abs(coarse):.3f} % -> fine {abs(fine):.3f} % "
                      f"(must not grow with refinement)"}
    checks.append(conv)
    print(f"  plain convergence   : |err| {abs(coarse):.3f} % -> {abs(fine):.3f} %")
    print("-" * 78)

    # ---- load / equilibrium / symmetry on both plates -------------------- #
    # These are *fresh* runs (different case names from the coarse/fine pair
    # above), so their records are stored under their own labels - the first
    # draft filed the rows under ``invariants`` and then read them back from
    # ``runs``, which is how a 3.5-minute verification ends in a KeyError two
    # lines before its verdict.
    #
    # They run at the **family default** mesh, not at the sweep's coarse end:
    # these are assertions about the model the dataset ships, and the stiffening
    # ratio in particular is mesh-dependent.  (Before D9 this was 6 mm purely
    # because ``args.sizes`` defaulted there, while the README quoted the result
    # as if it were the archived 3 mm plate.)
    print(f"  invariants at {panel.DEFAULT_MESH_SIZE:g} mm (family default = the archived mesh)")
    for n_str, name, label in ((0, "verify_panel_plain_sym", "plain"),
                               (3, "verify_panel_stiff_sym", "stiffened")):
        spec = make_spec(name, n_str, panel.DEFAULT_MESH_SIZE)
        r = run_case(name, n_str, panel.DEFAULT_MESH_SIZE)
        if not r["ok"]:
            print(f"  [{label}] SOLVER FAILED {r['log']}")
            return 2
        report["runs"][label] = {k: v for k, v in r.items() if k != "data"}
        rows, info = check_case(r, label, panel.parse_params(spec))
        checks.extend(rows)
        report.setdefault("invariants", {})[label] = info
        for row in rows:
            print(f"  [{'PASS' if row['pass'] else 'FAIL'}] {row['key']}: {row['detail']}")

    # ---- 5. stiffening ---------------------------------------------------- #
    w_plain = abs(report["runs"]["plain"]["max_w"])
    w_stiff = abs(report["runs"]["stiffened"]["max_w"])
    ratio = w_plain / w_stiff
    pitch = LENGTH / 4.0
    sub = subpanel_wmax(pitch, WIDTH, PRESSURE, THICKNESS, E, nu)
    checks.append({
        "key": "stiffened.stiffening",
        "pass": ratio > MIN_STIFFENING,
        "detail": f"w_plain {w_plain:.5f} / w_stiff {w_stiff:.5f} = {ratio:.1f}x "
                  f"(>= {MIN_STIFFENING:g}x required; a detached stringer gives ~1x). "
                  f"One bay {pitch:g} x {WIDTH:g} mm as a rigidly-supported plate "
                  f"would be {sub:.5f} mm - reported, not asserted",
    })
    report["stiffening"] = {"w_plain": w_plain, "w_stiff": w_stiff, "ratio": ratio,
                            "subpanel_wmax": sub, "pitch": pitch}
    print(f"  [{'PASS' if checks[-1]['pass'] else 'FAIL'}] {checks[-1]['key']}: "
          f"{checks[-1]['detail']}")
    print("-" * 78)

    # ---- 6. the outer-fibre channel (D8) ---------------------------------- #
    # D8 declares the archive's stress to be the **outer fibre**, and since
    # CalculiX can only reach it through OUTPUT=3D this is the one place where
    # that machinery meets a number that is right independently of it.  Without
    # this check D8 is only argued, not verified.
    #
    # Compared at the node nearest the plate centre, not at the model maximum.
    # The model maximum sits on a supported edge and reads ~12 % higher (2.9682
    # vs 2.6455 MPa on the 3 mm plain plate): that is the corner/edge shear
    # boundary layer, a real feature of the discretisation, not the bending
    # stress the closed form describes.  Asserting on it would be asserting on
    # a mesh artefact.
    sig_an = navier_sigma_max(LENGTH, WIDTH, PRESSURE, THICKNESS, nu)
    rp = report["runs"]["plain"]
    cen = rp.get("peak_vm_centre")
    err_s = (cen - sig_an) / sig_an * 100.0 if cen is not None else float("nan")
    pd = rp.get("peak_vm_centre_coord")
    checks.append({
        "key": "plain.outer-fibre-stress",
        "pass": cen is not None and abs(err_s) < TOL_STRESS,
        "detail": f"6 Mx/t^2 at the centre = {sig_an:.5f} MPa; FE outer-fibre vM "
                  f"at the node nearest the centre ({rp.get('peak_vm_centre_node')} "
                  f"at {tuple(round(c, 2) for c in pd) if pd else '?'}) = "
                  f"{cen if cen is None else round(cen, 5)} -> {err_s:+.2f} % "
                  f"| mid-surface channel reads "
                  f"{rp.get('max_vm_mid') if rp.get('max_vm_mid') is None else round(rp['max_vm_mid'], 5)} "
                  f"(shear-dominated, D8's reason for discarding it); model-wide "
                  f"outer-fibre max {round(rp['peak_vm_max'], 5) if rp.get('peak_vm_max') else '?'} "
                  f"MPa, {((rp['peak_vm_max'] - sig_an) / sig_an * 100) if rp.get('peak_vm_max') else float('nan'):+.1f} % "
                  f"above the closed form, on a supported edge",
    })
    print(f"  [{'PASS' if checks[-1]['pass'] else 'FAIL'}] {checks[-1]['key']}: "
          f"{checks[-1]['detail']}")
    print("-" * 78)

    n_fail = sum(1 for c in checks if not c["pass"])
    print(f"  {len(checks) - n_fail}/{len(checks)} checks passed")
    print(f"  VERDICT: {'PASS' if n_fail == 0 else 'FAIL - ' + str(n_fail) + ' check(s)'}")
    print("=" * 78)
    if args.json:
        report["checks"] = checks
        report["n_pass"] = len(checks) - n_fail
        report["n_fail"] = n_fail
        Path(args.json).write_text(
            json.dumps(report, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8")
        print(f"  report -> {args.json}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
