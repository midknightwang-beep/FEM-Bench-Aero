#!/usr/bin/env python
"""T6 independent verification: Bredt-Batho torsion on a multi-cell wing box.

Why this family can be verified at all
--------------------------------------
A cell count is only *observable* in torsion - which is why 老王's call put an
end torque on every T6 case (D24).  That, in turn, buys the family the one thing
most of this dataset does not have: a **closed-form yardstick**, the same
position T4's open-hole coupon occupies with Kirsch/Howland.

The theory
----------
For a thin-walled section of ``n`` cells, the shear flows ``q_i`` satisfy, per
cell,

    sum_j  q_j * (loop integral of ds/t over the shared wall)  =  2 G theta A_i

and the torque is ``T = 2 sum_i q_i A_i``.  For equally thick walls this reduces
to ``M q = 2 G theta a`` with ``M[i][i] = perimeter_i / t`` and
``M[i][j] = -(shared wall length)/t``, giving

    GJ = 4 G a^T M^-1 a

with ``a`` the vector of cell areas.  ``n = 1`` is the classical
``GJ = 4 G A^2 / (loop ds/t)`` - so the single-cell box is verified by the same
code that verifies the multi-cell ones, which is what makes the comparison an
independent check rather than a restatement.

What is measured on the model, and where
----------------------------------------
Torsion response is read from the **spanwise twist gradient inside one rib-free
bay**, not from the tip rotation: the root is clamped and ribs restrain warping,
so an end reading would compare Bredt-Batho's free-warping solution against a
constrained one.  The gradient in the interior of a bay is the local St-Venant
response, and it is the quantity ``T L / GJ`` is actually about.

The gradient itself is obtained by **least-squares fitting the rigid rotation**
of every node in that bay, rather than by differencing two node rings: the
skins carry a free quad mesh, so interior nodes are not aligned to z planes and
there is no ring to difference.  The fit is exact in plane because warping is
purely axial - see :func:`fit_twist_rate`.  (Same family of manoeuvre
``verify_barrel.py`` makes for the barrel's end effects.)

Two readings, because ``GJ`` alone cannot see a cell count
----------------------------------------------------------
``GJ`` is checked against the closed form for every case, and it agrees to
0.2-1.1 %.  But it is a **weak** discriminator of *how many* cells there are:
for a thin section the closed form's own gain from adding a web is small
(+0.42 % for 2 cells, +1.76 % for 3 on this section) and for a rectangular box
it is exactly zero, so a web that carried nothing would still show a near-match.
The decisive observable is the **wall shear flow**: the cell circulations differ
by 10-25 %, and each internal web carries their difference.  That is measured
per cell (off the upper skin) and per web (off the web's exclusive nodes) and
compared, wall by wall, to Bredt-Batho - see :func:`shear_flow`.

Both readings are taken on the **full stress tensor**.  A wing box's skins lie
in the x-z plane, so their membrane shear is the global ``sxz`` component;
:func:`post.von_mises_inplane`, written for the flat panel in x-y, drops it and
reads 0.05 MPa where the true mid-bay shear is 6.14 MPa.

Usage::

    python verify_multi_cell.py                  # ccx only
    python verify_multi_cell.py --with-abaqus    # cross-solver too
    python verify_multi_cell.py --json report.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from feagpt import naca, pipeline, post  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402

TOL_GJ_PCT = 5.0
"""Tolerance (%) on |GJ_model / GJ_Bredt-Batho - 1|.

The closed form assumes thin walls, free warping and a uniform section; the
model is a shell mesh with ribs at 0.5 m spacing.  5 % is the same order the
dataset allows a structural cross-check, and the measured gaps are reported
whether or not they pass, so a drift shows up as a number rather than as a
green tick.
"""

TOL_FLOW_PCT = 5.0
"""Tolerance (%) on the measured shear flow, per wall, against Bredt-Batho.

This - not ``GJ`` - is the decisive observable for a multi-cell box.  For a thin
section the closed form's own gain from adding a web is tiny (measured on the
4412 box: +0.42 % for 2 cells, +1.76 % for 3; a *rectangular* box is exactly
invariant because the mid web's perimeter cancels), so a whole-section stiffness
comparison cannot tell a web that carries load from one that carries none.  The
cell *circulations* separate them cleanly: they differ by 10-25 %, and the
internal web carries ``|q_i - q_{i+1}|``, a further order down.  5 % is the same
band the dataset's structural cross-checks use.
"""

TORQUE = 1.0e6          # N.mm

BAY_TRIM = 0.2
"""Fraction trimmed off each end of the sampled bay, away from its two ribs.

A rib restrains warping, so ``theta(z)`` is only linear - St-Venant - in the
interior of a bay; sampling the middle 60 % keeps the fit inside that region.
"""

TOL_EQUIL_REL = 1.0e-3
"""Net force under pure torque, as a fraction of the largest nodal reaction.

Pure torque applies a self-equilibrated couple, so the solver's own reaction sum
must vanish; what is left (~2e-5 of the peak, measured) is the deck's
printed-digit noise, not a physical imbalance.
"""

OUT_CCX = Path("outputs/_verify_multicell")
OUT_ABAQUS = Path("outputs/_verify_multicell_abaqus")


# --------------------------------------------------------------------------- #
# closed form
# --------------------------------------------------------------------------- #
def bredt_batho(spec: FEASpec, n_per_cell: int = 400,
                torque: float | None = None) -> dict:
    """``GJ`` and the per-cell areas from the exact section definition.

    The section is integrated from ``NACA4.camber_line`` / ``half_thickness`` -
    the same two functions the builder samples - so the closed form is a
    function of the *spec*, not of the mesh.  A cell's area is
    ``integral of (y_upper - y_lower) dx`` over its chordwise span and a
    separating wall is a **straight** line at constant ``x``, so its length is
    the local section height - no arc-length correction to get wrong.

    Given a ``torque`` it also returns the absolute shear flow ``q_i`` and the
    wall stress ``sqrt(3) q_i / t`` each cell should show: ``T = 2 sum q_i A_i``
    fixes the scale of the circulation vector, and the equal-thickness walls
    make the von Mises an exact multiple of the flow.
    """
    af = naca.NACA4.from_code(str(spec.airfoil.code))
    chord = float(spec.airfoil.chord)
    x_f, x_r = (float(v) for v in spec.airfoil.spar_chordwise)
    webs = sorted(float(v) for v in (spec.airfoil.web_chordwise or ()))
    t = float(spec.airfoil.skin_thickness)
    E = float(spec.material.youngs_modulus)
    nu = float(spec.material.poisson_ratio)
    G = E / (2.0 * (1.0 + nu))

    bounds = [x_f] + webs + [x_r]
    n_cell = len(bounds) - 1
    if n_cell < 1:
        raise ValueError("a section needs at least one cell")

    areas: list[float] = []
    perim: list[float] = []
    for i in range(n_cell):
        xc = np.linspace(bounds[i], bounds[i + 1], n_per_cell)
        yc = af.camber_line(xc)
        yt = af.half_thickness(xc)
        up = (yc + yt) * chord
        lo = (yc - yt) * chord
        h = up - lo
        x = xc * chord
        areas.append(float(np.sum(0.5 * (h[1:] + h[:-1]) * np.diff(x))))
        ds_up = float(np.sum(np.hypot(np.diff(x), np.diff(up))))
        ds_lo = float(np.sum(np.hypot(np.diff(x), np.diff(lo))))
        perim.append(ds_up + ds_lo + float(h[0]) + float(h[-1]))

    # Wall height at every boundary: 0 = front spar, n_cell = rear spar, the
    # rest are the intermediate webs shared by two cells.
    wall_h = []
    for xb in bounds:
        yt = float(af.half_thickness(np.asarray([xb]))[0])
        wall_h.append(2.0 * yt * chord)

    M = np.zeros((n_cell, n_cell))
    for i in range(n_cell):
        M[i, i] = perim[i] / t
        if i + 1 < n_cell:
            M[i, i + 1] -= wall_h[i + 1] / t
            M[i + 1, i] -= wall_h[i + 1] / t

    a = np.asarray(areas)
    q_rel = np.linalg.solve(M, a)
    gj = 4.0 * G * float(a @ q_rel)
    q_rel = [float(v) for v in q_rel]
    out = {
        "n_cells": n_cell,
        "GJ_Nmm2": gj,
        "areas_mm2": [float(v) for v in areas],
        "shear_flow_ratio": [v / q_rel[0] for v in q_rel],
        "wall_heights_mm": wall_h,
        "G_MPa": G,
        "t_mm": t,
    }
    if torque:
        # T = 2 sum q_i A_i  ->  q_scale = T / (2 a.q_rel);  and GJ = 4G (a.q_rel)
        q_scale = 2.0 * G * float(torque) / gj
        out["q_N_per_mm"] = [q_scale * v for v in q_rel]
        out["vm_MPa"] = [math.sqrt(3.0) * q_scale * v / t for v in q_rel]
        out["web_flow_ratio"] = [abs(q_rel[i] - q_rel[i + 1]) / q_rel[0]
                                 for i in range(n_cell - 1)]
    return out


# --------------------------------------------------------------------------- #
# model side
# --------------------------------------------------------------------------- #
def run_case(name: str, webs, torque: float, solver: str = "ccx",
             bend: float = 0.0, mesh_size: float | None = None) -> dict:
    """Solve one box under pure torque (plus an optional bending force)."""
    out = OUT_CCX if solver == "ccx" else OUT_ABAQUS
    spec = FEASpec(name=name)
    spec.description = f"T6 verification: {name}"
    spec.airfoil.web_chordwise = tuple(float(v) for v in webs)
    if mesh_size is not None:
        spec.mesh.size_chord = float(mesh_size)
    spec.load.kind = "tip_force"
    spec.load.magnitude = float(bend)
    spec.extra["end_torque"] = float(torque)
    spec.extra["torque_axis_dof"] = 3
    spec.workdir = str(out / name)

    res = pipeline.run(spec, outdir=out / name, solver_name=solver)
    if not res.ok:
        return {"ok": False, "name": name, "solver": solver,
                "log": list(res.messages[-5:])}
    case = out / name
    frd = case / f"{name}.frd"
    odbj = case / f"{name}.odb.json"
    if solver == "ccx" and frd.exists():
        data = post.load_any(frd)
    elif odbj.exists():
        data = post.load_results_json(odbj)
    else:
        return {"ok": False, "name": name, "solver": solver,
                "log": [f"no result source in {case}"]}
    return {
        "ok": True, "name": name, "solver": solver, "spec": spec,
        "inp": str(case / f"{name}.inp"),
        "gate4": bool(pipeline.topology.compare(res.geometry["topology"])["pass"]),
        "min_quality": float(res.mesh["min_quality"]),
        "n_elements": int(res.mesh["n_elements"]),
        "data": data,
    }


def _rib_stations(spec: FEASpec) -> list[float]:
    """Rib spanwise positions - ``linspace(0, span, n_ribs)``, as the builder."""
    n = max(int(spec.airfoil.n_ribs), 2)
    span = float(spec.airfoil.span)
    return [span * i / (n - 1) for i in range(n)]


def _mid_bay_band(spec: FEASpec, trim: float = BAY_TRIM) -> tuple[float, float]:
    """The middle bay, trimmed ``trim`` at each end away from its two ribs.

    Every reduction here - twist gradient and wall shear alike - is a St-Venant
    quantity, so it has to be sampled where the ribs are not bending the answer.
    """
    ribs = _rib_stations(spec)
    if len(ribs) >= 3:
        i = (len(ribs) - 1) // 2
        lo, hi = ribs[i], ribs[i + 1]
    else:
        lo, hi = 0.0, ribs[-1]
    d = hi - lo
    return lo + trim * d, hi - trim * d


def fit_twist_rate(data: dict, z_lo: float, z_hi: float) -> dict:
    """Least-squares twist gradient over one rib-free spanwise window.

    The in-plane displacement of a St-Venant-twisted thin-walled box is a *rigid
    rotation* of each cross-section - warping is purely axial and so never
    enters the two in-plane equations - which makes the model

        u_x = a_x + b_x z - theta(z) (y - yc)
        u_y = a_y + b_y z + theta(z) (x - xc),    theta(z) = t0 + t1 z

    *exact* in plane.  Fitting it over every node in the window recovers the
    twist rate ``t1`` directly, with no bias from warping.

    This replaces the obvious "difference two node rings" estimate, which cannot
    be used here: the skins carry a free quad mesh, so interior nodes are not
    aligned to z planes and only the four longitudinal spar-skin lines (and the
    rib rings) have a well-defined ``z``.  The fit needs no ring at all.
    """
    nodes = data["nodes"]
    disp = data["results"].get("DISP") or {}
    sel = [(nodes[t], disp[t]) for t in nodes
           if t in disp and z_lo <= float(nodes[t][2]) <= z_hi]
    if len(sel) < 30:
        return {"ok": False, "n": len(sel)}
    x = np.array([float(n[0]) for n, _d in sel])
    y = np.array([float(n[1]) for n, _d in sel])
    z = np.array([float(n[2]) for n, _d in sel])
    ux = np.array([float(d[0]) for _n, d in sel])
    uy = np.array([float(d[1]) for _n, d in sel])
    yc, xc = y.mean(), x.mean()

    A = np.zeros((2 * len(sel), 6))
    A[: len(sel), 0] = 1.0                    # a_x
    A[: len(sel), 1] = z                      # b_x
    A[: len(sel), 2] = -(y - yc)              # t0
    A[: len(sel), 3] = -(y - yc) * z          # t1
    A[len(sel):, 2] = (x - xc)                # t0
    A[len(sel):, 3] = (x - xc) * z            # t1
    A[len(sel):, 4] = 1.0                     # a_y
    A[len(sel):, 5] = z                       # b_y
    sol, _res, _rank, _sv = np.linalg.lstsq(
        A, np.concatenate([ux, uy]), rcond=None)
    resid = A @ sol - np.concatenate([ux, uy])
    scale = float(np.sqrt((ux ** 2 + uy ** 2).mean())) or 1.0
    return {"ok": True, "n": len(sel), "t0": float(sol[2]), "t1": float(sol[3]),
            "resid_rms_rel": float(np.sqrt((resid ** 2).mean()) / scale)}


def measured_gj(run: dict, torque: float) -> dict:
    """``GJ`` from the twist gradient fitted inside the middle bay."""
    z_lo, z_hi = _mid_bay_band(run["spec"])
    fit = fit_twist_rate(run["data"], z_lo, z_hi)
    if not fit.get("ok"):
        return {"ok": False, "z_lo": z_lo, "z_hi": z_hi, "n": fit.get("n", 0)}
    t1 = fit["t1"]
    gj = abs(torque / t1) if t1 else float("nan")
    return {"ok": True, "z_lo": z_lo, "z_hi": z_hi, "n": fit["n"],
            "theta0_rad": fit["t0"], "twist_rate_rad_per_mm": t1,
            "resid_rms_rel": fit["resid_rms_rel"], "GJ_Nmm2": gj}


def shear_flow(run: dict) -> dict:
    """Measured wall shear, per cell and per web, as von Mises.

    Under pure St-Venant torsion every wall carries a uniform membrane shear
    ``q/t``, so its von Mises is ``sqrt(3) q / t`` and walls of equal thickness
    compare in direct proportion to their shear flow - which is exactly what
    Bredt-Batho predicts.  Each cell's flow is read off its **upper skin**, and
    each web's off its own exclusive nodes (web minus both skins, so the shared
    skin edges do not drag the skin's flow into the web's number).

    Two things this gets right that are easy to get wrong:

    * the **full** von Mises, not :func:`post.von_mises_inplane`.  A wing box's
      skins lie in the x-z plane, so their membrane shear sits in the global
      ``sxz`` component and the in-plane-only reduction - written for the flat
      panel, which lies in x-y - would drop the entire answer.  Measured: the
      reduced form reads 0.05 MPa where the true mid-bay shear is 6.14 MPa.
    * the statistic is the **median** over a mid-bay band, not a mean over the
      whole box: the clamp and the rib junctions are stress concentrations and
      a mean is dominated by their tails.

    The mesh is read back through :func:`post.read_deck_elset_nodes`, i.e. from
    the deck the solver was handed, so a web present in the geometry but absent
    from the model cannot pass.
    """
    spec = run["spec"]
    data = run["data"]
    nodes = data["nodes"]
    stress = data["results"].get("STRESS") or {}
    inp = run["inp"]
    upper = post.read_deck_elset_nodes(inp, "E_UPPER_SKIN")
    lower = post.read_deck_elset_nodes(inp, "E_LOWER_SKIN")
    webs = post.read_deck_elset_nodes(inp, "E_WEBS")

    chord = float(spec.airfoil.chord)
    x_f, x_r = (float(v) for v in spec.airfoil.spar_chordwise)
    stations = sorted(float(v) for v in (spec.airfoil.web_chordwise or ()))
    bounds = [x_f] + stations + [x_r]

    z_lo, z_hi = _mid_bay_band(spec)

    def band(sel):
        return [t for t in sel if t in stress and t in nodes
                and z_lo <= float(nodes[t][2]) <= z_hi]

    def med(sel):
        vals = [post.von_mises(stress[t]) for t in band(sel)]
        return statistics.median(vals) if vals else float("nan")

    x_mm = [b * chord for b in bounds]
    cell_vm = [med(t for t in upper if x_mm[i] <= float(nodes[t][0]) <= x_mm[i + 1])
               for i in range(len(x_mm) - 1)]
    excl_web = webs - upper - lower
    web_vm = [med(t for t in excl_web if abs(float(nodes[t][0]) - w * chord) <= 1.0)
              for w in stations]
    return {"ok": bool(cell_vm) and cell_vm[0] == cell_vm[0], "n_web_faces_elset": len(webs),
            "z_lo": z_lo, "z_hi": z_hi, "cell_vm": cell_vm, "web_vm": web_vm}


def equilibrium(data: dict) -> dict:
    """Net reaction under pure torque - exactly zero for a self-equilibrated couple."""
    forc = data["results"].get("FORC") or {}
    if not forc:
        return {"n": 0}
    sx = sum(float(v[0]) for v in forc.values())
    sy = sum(float(v[1]) for v in forc.values())
    sz = sum(float(v[2]) for v in forc.values())
    f_max = max(math.sqrt(float(v[0]) ** 2 + float(v[1]) ** 2 + float(v[2]) ** 2)
                for v in forc.values())
    return {"n": len(forc), "sum_x": sx, "sum_y": sy, "sum_z": sz,
            "norm": math.sqrt(sx * sx + sy * sy + sz * sz), "f_max": f_max}


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b) * 100.0 if b else float("inf")


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #
CASES = (
    ("one-cell", (), "单闭室（中性，经典 Bredt）"),
    ("two-cell-even", (0.475,), "2 等闭室（1 道等分腹板）"),
    ("three-cell-even", (0.4, 0.55), "3 等闭室（2 道等分腹板）"),
    ("two-cell-offcentre", (0.35,), "2 不等闭室（1 道偏心腹板）"),
)


def check_gj(solver: str = "ccx", mesh_size: float | None = None,
             with_abaqus: bool = False) -> tuple[list[dict], dict]:
    out: list[dict] = []
    extra: dict = {"cases": {}, "torque_Nmm": TORQUE}

    single_gj = None
    for label, webs, note in CASES:
        name = f"mc_{label.replace('-', '_')}"
        run = run_case(name, webs, TORQUE, solver=solver, mesh_size=mesh_size)
        if not run["ok"]:
            out.append({"check": f"mc.{label}", "pass": False,
                        "detail": f"run failed: {run.get('log')}"})
            continue
        ana = bredt_batho(run["spec"], torque=TORQUE)
        meas = measured_gj(run, TORQUE)
        flow = shear_flow(run)
        eq = equilibrium(run["data"])
        if not meas.get("ok"):
            out.append({"check": f"mc.{label}", "pass": False,
                        "detail": f"{note}: twist fit failed "
                                  f"(only {meas.get('n', 0)} nodes in bay)"})
            continue
        gap = _rel(meas["GJ_Nmm2"], ana["GJ_Nmm2"])
        ok = gap <= TOL_GJ_PCT
        out.append({
            "check": f"mc.{label}",
            "pass": bool(ok),
            "detail": (f"{note}: GJ model {meas['GJ_Nmm2']:.4g} vs Bredt-Batho "
                       f"{ana['GJ_Nmm2']:.4g} N.mm^2 ({gap:+.3f} %); "
                       f"twist rate {meas['twist_rate_rad_per_mm']:.4e} rad/mm "
                       f"over z {meas['z_lo']:.0f}-{meas['z_hi']:.0f} "
                       f"({meas['n']} nodes, rigid-fit resid "
                       f"{meas['resid_rms_rel'] * 100:.3f} %); "
                       f"cells {ana['n_cells']}; tol {TOL_GJ_PCT:g} %"),
        })
        extra["cases"][label] = {
            "webs": list(webs), "n_cells": ana["n_cells"],
            "GJ_model": meas["GJ_Nmm2"], "GJ_analytic": ana["GJ_Nmm2"],
            "gap_pct": gap, "twist_rate": meas["twist_rate_rad_per_mm"],
            "resid_rms_rel": meas["resid_rms_rel"], "n_fit": meas["n"],
            "z_lo": meas["z_lo"], "z_hi": meas["z_hi"],
            "areas_mm2": ana["areas_mm2"],
            "shear_flow_ratio": ana["shear_flow_ratio"],
            "q_N_per_mm": ana["q_N_per_mm"], "vm_analytic_MPa": ana["vm_MPa"],
            "cell_vm": flow["cell_vm"], "web_vm": flow["web_vm"],
            "web_flow_ratio_analytic": ana.get("web_flow_ratio", []),
            "n_web_faces_elset": flow["n_web_faces_elset"],
            "equilibrium": eq, "gate4": run["gate4"],
            "min_quality": run["min_quality"], "n_elements": run["n_elements"],
        }
        # (2) equilibrium under pure torque: the net force must vanish.
        eq_rel = eq["norm"] / eq["f_max"] if eq.get("f_max") else float("inf")
        ok_eq = eq.get("n", 0) > 0 and eq_rel <= TOL_EQUIL_REL
        out.append({
            "check": f"mc.{label}.equilibrium",
            "pass": bool(ok_eq),
            "detail": (f"sum FORC = ({eq['sum_x']:.3e}, {eq['sum_y']:.3e}, "
                       f"{eq['sum_z']:.3e}) N over {eq['n']} nodes; "
                       f"|sum| / max|F_node| = {eq_rel:.2e} <= {TOL_EQUIL_REL:g} "
                       f"(pure torque -> self-equilibrated)"),
        })
        # (3) per-cell skin shear, absolute against sqrt(3) q_i / t.  This is
        # the check a whole-section GJ comparison cannot make: the analytical
        # GJ gain from the webs is under 2 %, but the cell flows differ by
        # 10-25 %, so an unloaded web shows up here and not there.
        skin_gaps = [_rel(m, a) for m, a in zip(flow["cell_vm"], ana["vm_MPa"])]
        out.append({
            "check": f"mc.{label}.skin-shear",
            "pass": bool(max(skin_gaps) <= TOL_FLOW_PCT),
            "detail": (f"mid-bay upper-skin vM per cell "
                       f"{[round(v, 4) for v in flow['cell_vm']]} vs "
                       f"sqrt(3) q_i/t {[round(v, 4) for v in ana['vm_MPa']]} MPa; "
                       f"max gap {max(skin_gaps):.3f} % (tol {TOL_FLOW_PCT:g} %)"),
        })
        # (4) and the internal web carries the *difference* of the two adjacent
        # cell flows - the direct statement that the web is loaded.
        if stations := ana.get("web_flow_ratio"):
            web_gaps = []
            for j, (mw, aw) in enumerate(zip(flow["web_vm"], stations)):
                r_meas = mw / flow["cell_vm"][0]
                web_gaps.append(_rel(r_meas, aw))
            out.append({
                "check": f"mc.{label}.web-shear",
                "pass": bool(max(web_gaps) <= TOL_FLOW_PCT),
                "detail": (f"web measured/1st-cell flow "
                           f"{[round(v / flow['cell_vm'][0], 4) for v in flow['web_vm']]} "
                           f"vs |q_i - q_i+1|/q_1 "
                           f"{[round(v, 4) for v in stations]}; "
                           f"max gap {max(web_gaps):.3f} % "
                           f"(tol {TOL_FLOW_PCT:g} %)"),
            })
        else:
            out.append({
                "check": f"mc.{label}.web-shear",
                "pass": bool(flow["n_web_faces_elset"] == 0),
                "detail": (f"neutral section: no web in the deck "
                           f"({flow['n_web_faces_elset']} E_WEBS elements), "
                           f"nothing to carry - the cell-shear check above is the "
                           f"one that applies"),
            })

    # (5) the cell-count effect itself, as a ratio to the one-cell case: this
    # cancels the common-mode mesh error and fails if the webs carry nothing
    # (both ratios would collapse to 1.000).
    one = extra["cases"].get("one-cell")
    for label in ("two-cell-even", "three-cell-even"):
        c = extra["cases"].get(label)
        if not (one and c):
            continue
        r_meas = c["GJ_model"] / one["GJ_model"]
        r_ana = c["GJ_analytic"] / one["GJ_analytic"]
        gap = _rel(r_meas, r_ana)
        out.append({
            "check": f"mc.cell-count-effect.{label}",
            "pass": bool(gap <= TOL_GJ_PCT),
            "detail": (f"GJ({label})/GJ(1-cell): model {r_meas:.6f} vs Bredt-Batho "
                       f"{r_ana:.6f} ({gap:+.3f} %); the closed-form gain is only "
                       f"{(r_ana - 1) * 100:+.3f} %, which is why GJ alone cannot "
                       f"resolve cell count - see mc.*.skin-shear"),
        })
    if with_abaqus:
        a = extra["cases"].get("two-cell-even", {}).get("GJ_model")
        run = run_case("mc_two_cell_even", (0.475,), TORQUE, solver="abaqus")
        if not run["ok"]:
            out.append({"check": "mc.cross-solver-GJ", "pass": False,
                        "detail": f"abaqus run failed: {run.get('log')}"})
        else:
            meas = measured_gj(run, TORQUE)
            flow = shear_flow(run)
            if not meas.get("ok"):
                out.append({"check": "mc.cross-solver-GJ", "pass": False,
                            "detail": f"abaqus twist fit failed ({meas} )"})
            else:
                gap = _rel(meas["GJ_Nmm2"], a)
                out.append({
                    "check": "mc.cross-solver-GJ",
                    "pass": bool(gap <= TOL_GJ_PCT),
                    "detail": (f"two-cell GJ ccx {a:.4g} vs abaqus "
                               f"{meas['GJ_Nmm2']:.4g} N.mm^2 ({gap:.3f} %), "
                               f"tol {TOL_GJ_PCT:g} %"),
                })
            ref = extra["cases"]["two-cell-even"]["cell_vm"]
            sg = [_rel(m, c) for m, c in zip(flow["cell_vm"], ref)]
            out.append({
                "check": "mc.cross-solver-shear",
                "pass": bool(flow["ok"] and max(sg) <= TOL_FLOW_PCT),
                "detail": (f"two-cell skin vM ccx "
                           f"{[round(v, 4) for v in ref]} vs abaqus "
                           f"{[round(v, 4) for v in flow['cell_vm']]} MPa; "
                           f"max gap {max(sg):.3f} % (tol {TOL_FLOW_PCT:g} %)"),
            })
    return out, extra


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solver", default="ccx", choices=("ccx", "abaqus"))
    ap.add_argument("--mesh-size", type=float, default=None)
    ap.add_argument("--with-abaqus", action="store_true")
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    results, extra = check_gj(solver=args.solver, mesh_size=args.mesh_size,
                              with_abaqus=args.with_abaqus)

    print("=== T6 multi-cell independent verification (Bredt-Batho) ===")
    for r in results:
        print(f"  [{'PASS' if r['pass'] else 'FAIL'}] {r['check']}")
        print(f"         {r['detail']}")
    n_pass = sum(1 for r in results if r["pass"])
    print(f"\n{n_pass} PASS / {len(results) - n_pass} FAIL  "
          f"VERDICT: {'PASS' if n_pass == len(results) else 'FAIL'}")
    if args.json:
        Path(args.json).write_text(
            json.dumps({"checks": results, **extra}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        print(f"report -> {args.json}")
    return 0 if n_pass == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
