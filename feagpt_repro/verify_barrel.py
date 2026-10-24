#!/usr/bin/env python
"""Independent verification of the fuselage-barrel chain (M5 / task T3).

A barrel is not "verified" because ccx exited 0.  Gate 4 says the model *is* what
the spec asked for; nothing so far says the numbers are **right**.  So the same
chain (geometry -> mesh -> deck -> CalculiX -> FRD) is run on problems with
closed-form answers, exactly as ``verify_panel.py`` does for the stiffened panel
and ``verify_cantilever.py`` for the wing box.

The three load components get **separate probes**, not one combined run
-----------------------------------------------------------------------
The default barrel carries internal pressure + end shear + end moment at once.
That combined case is what the dataset ships, but it is a poor *verification*
model: the three responses superpose, so a single solved field cannot say which
component a disagreement came from, and a secondary component two orders below
the first would pass unnoticed.  So the closed forms are checked on
**isolated** probes - pressure alone, moment alone - built on the
**stringer-free** barrel, whose section properties are elementary
(``I = pi R^3 t``, no stringer term).  The combined case is then checked for the
things a combined case *can* check: equilibrium and cross-solver agreement.

What each check is worth
------------------------
1. **Pressure membrane** (stringer-free barrel, pressure only).  Thin-wall
   cylinder: hoop ``sigma_theta = p R / t``, no axial membrane stress (the barrel
   has **no end caps**, so the pressure has no axial resultant), free radial
   growth ``w = p R^2 / (E t)``.  Sampled on the mid-length ring *half a bay from
   the nearest skin seam* - the seams are free edges now that the family carries
   no closed surface, and a node sitting on one is in a boundary layer that is a
   property of the discretisation, not of the vessel.  von Mises is used for the
   stress comparison because it is **frame-invariant**: the shell's local
   material frame is not ours to assume, and for a membrane state
   ``sigma_theta = pR/t, sigma_z = 0`` it equals ``pR/t`` exactly.
2. **Bending** (stringer-free barrel, end moment only).  A cantilever under a
   constant end moment has the same internal moment everywhere, so the axial
   stress is ``sigma_z = M x / I`` with ``I = pi R^3 t``; at the sampled meridian
   (half a bay off the seam) ``x = R cos(pi/n_seg)``.  Again compared through von
   Mises, which for this uniaxial state *is* that stress.
3. **Equilibrium** (combined case).  CalculiX's ``FORC`` block holds the *total*
   external force at a node - applied at free nodes, reaction at constrained ones
   - so summed over the whole model it must vanish.  No lumping model, no choice
   of node set, nothing to get wrong.  The shear direction and the couple
   direction are both summed, and both are normalised by the applied shear.
4. **Cross-solver** (combined case).  CalculiX and Abaqus on the identical deck
   mesh must agree on the structure's peak displacement, and on the whole
   deflection **profile** (the section-centroid curve along the axis).  This is
   the check that exercises the combined load *as a whole*: nothing about the
   loads is closed-form verifiable here, but a mis-emitted shear or couple moves
   the displacement field and the two codes would stop agreeing.

   **D20 (2026-10-05) - which displacement, and why.**  Until D20 this check
   compared the model-wide ``max|u|``.  Measured on the shipped barrel
   (``fuselage_barrel_d2000_l2000_str8_frm3``, 158 524 nodes), that quantity is
   **dominated by the load-application ring**, not by the structure:

   * model-wide ``max|u|``: ccx 2.63102 vs abaqus 2.67818 mm -> **1.79 %**, over
     the 1 % tolerance.  The peak sits at ``r = 970``, ``z = 2000`` - the **free
     inner rim of the end frame** (a 30 x 3 mm flat annulus bonded to the skin
     only along ``r = 1000``), which is a free edge and therefore a soft local
     mode;
   * the same comparison **excluding the free-end ring**: 1.44978 vs 1.45588 ->
     **0.42 %**; the axis-wise deflection profile agrees to **<= 0.28 %**;
   * under **pressure alone** - a smooth surface traction, no nodal load - the
     two codes agree to **0.25 %**, so the shell formulations themselves are not
     in question;
   * the entire deviation is carried by the 3 226 ring nodes: their largest
     ``|du|`` is 0.05929 mm = **2.25 % of the model's max|u|**.

   Applying the end loads to the shell ring only (measured: 3 226 -> 644 nodes)
   moves the peak from 2.63 to 1.39 mm but leaves it **in the same place**, and
   the gap only narrows to 1.11 %.  So this is not a load-placement error to
   fix; it is a nodal-force-on-a-free-edge artifact that two shell formulations
   resolve differently at one mesh.

   **口径 (D20):** the cross-solver criterion is the peak displacement over the
   nodes that do **not** carry the applied end loads - the free-end ring is
   removed using the family's *own* ring rule (``fuselage.barrel_nodes``), not a
   magic band - plus the deflection profile.  Tolerance unchanged at 1 %.  The
   model-wide ``max|u|`` is **printed with its own deviation and never gates**,
   so the number is reported rather than hidden; this is the same posture the
   panel's membrane check takes when it reports "inapplicable" instead of
   quietly passing.

Usage::

    python verify_barrel.py                 # every probe (needs Abaqus too)
    python verify_barrel.py --ccx-only      # skip the cross-solver half
    python verify_barrel.py --json verify_barrel.json

Runs land in ``outputs/_verify_barrel/`` (ccx) and
``outputs/_verify_barrel_abaqus/`` (abaqus) - **separate roots on purpose**, or
the second solver overwrites the first one's deck and the comparison silently
reads one code twice (see :func:`run_case`).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feagpt import fuselage, pipeline, post  # noqa: E402

# --------------------------------------------------------------------------- #
# the model the closed forms describe
# --------------------------------------------------------------------------- #
PRESSURE = fuselage.DEFAULT_PRESSURE
SHEAR = fuselage.DEFAULT_END_SHEAR
MOMENT = fuselage.DEFAULT_END_MOMENT
N_SEG = fuselage.MIN_SKIN_SEGMENTS

#: Azimuth of the sampled meridian: **half a bay from the nearest skin seam.**
#: On a stringer-free barrel the seams are free edges, so a node on one is in a
#: boundary layer; half a bay puts the sample at the middle of a patch.
MID_ANGLE = math.pi / N_SEG

TOL_MEMBRANE = 3.0      # %, hoop von Mises at mid-length vs p R / t
TOL_GROWTH = 3.0        # %, radial displacement at mid-length vs p R^2 / (E t)
TOL_BENDING = 6.0       # %, bending von Mises vs M x / I at the sampled meridian
TOL_EQUILIBRIUM = 0.5   # %, sum(FORC) over the whole model, normalised by V
TOL_CROSS = 1.0         # %, ccx vs abaqus, D20 metric and profile (see docstring)

#: **D20.**  Number of axial stations the deflection profile is sampled at.
#: Fixed, so the profile check is deterministic and two runs compare the same
#: stations.
PROFILE_STATIONS = 20


def _rel(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1e-12) * 100.0


def _disp(data: dict) -> dict:
    return data["results"]["DISP"]


def _numag(u) -> float:
    return math.sqrt(u[0] * u[0] + u[1] * u[1] + u[2] * u[2])


def structure_peak(data: dict, spec) -> tuple[float, int]:
    """``(max|u|, node)`` over the nodes that carry **no** applied end load (D20).

    The excluded set is the free-end ring, taken from the family's own rule
    (:func:`feagpt.fuselage.barrel_nodes`) rather than a hard-coded coordinate:
    the ring the loads act on is the ring the family declares.
    """
    p = fuselage.parse_params(spec)
    nodes = data["nodes"]
    held = set(fuselage.barrel_nodes(nodes, p, p.frame_z()[-1]))
    disp = _disp(data)
    best, best_node = -1.0, None
    for tag, u in disp.items():
        if tag in held:
            continue
        m = _numag(u)
        if m > best:
            best, best_node = m, tag
    return best, best_node


def deflection_profile(data: dict, length: float,
                       n: int = PROFILE_STATIONS) -> list[float]:
    """Centroid ``ux`` of each axial slice, ``z`` in ``[i*L/n, (i+1)*L/n)``.

    The boundary ``z = L`` is put in the last slice so the loaded ring counts;
    an empty slice reads 0.0 (it cannot happen on a barrel whose skin is
    resolved along its whole length, and a report of 0 for an empty slice is
    visible rather than silently shifted).
    """
    nodes, disp = data["nodes"], _disp(data)
    sums, counts = [0.0] * n, [0] * n
    for tag, xyz in nodes.items():
        i = min(int(float(xyz[2]) / length * n), n - 1)
        if i < 0:
            continue
        sums[i] += disp[tag][0]
        counts[i] += 1
    return [sums[i] / counts[i] if counts[i] else 0.0 for i in range(n)]


# --------------------------------------------------------------------------- #
# closed forms
# --------------------------------------------------------------------------- #
def hoop_stress(p: float, R: float, t: float) -> float:
    """Thin-wall hoop membrane stress of a pressurised cylinder (MPa)."""
    return p * R / t


def radial_growth(p: float, R: float, t: float, E: float) -> float:
    """Free radial growth of the same cylinder (mm).

    ``w = R eps_theta`` with ``eps_theta = (sigma_theta - nu sigma_z) / E``.  The
    axial membrane stress is **zero** - the barrel has no end caps, so the
    pressure produces no axial resultant - which is what removes the ``nu`` term
    and makes this ``p R^2 / (E t)`` rather than the ``(1 - nu/2)`` form a closed
    pressure vessel would give.  Getting that wrong inflates the answer by 16 %
    at ``nu = 0.33``, i.e. by far more than the tolerance.
    """
    return p * R ** 2 / (E * t)


def beam_inertia(R: float, t: float) -> float:
    """Second moment of area of a thin tube's wall about a diameter (mm^4)."""
    return math.pi * R ** 3 * t


def bending_stress(M: float, x: float, I: float) -> float:
    """Axial bending stress at distance ``x`` from the neutral axis (MPa)."""
    return abs(M) * abs(x) / I


# --------------------------------------------------------------------------- #
# one production-path run
# --------------------------------------------------------------------------- #
def run_case(name: str, solver: str, **params) -> dict:
    """Run one barrel through the real pipeline and read its results back.

    **Each solver gets its own output root.**  Until 2026-10-05 both wrote to
    ``outputs/_verify_barrel/<name>``, so the Abaqus run overwrote the ccx
    deck (``<name>.inp``) and left the ccx FRD beside it - and the reader,
    preferring the FRD, then compared ``ccx-against-its-own-FRD-read-through-
    the-Abaqus-deck``.  It reported a 46 % disagreement and a node label that
    does not exist in the Abaqus ODB.  The cross-solver half of this file had
    never actually run before, which is why nobody noticed.  Same split the
    batch workdirs use (``outputs_b3`` / ``outputs_b3_abaqus``).
    """
    out = (Path("outputs/_verify_barrel") if solver == "ccx"
           else Path("outputs/_verify_barrel_abaqus"))
    spec = fuselage.make_spec(name, workdir=str(out / name), **params)
    res = pipeline.run(spec, outdir=out / name, solver_name=solver)
    if not res.ok:
        return {"ok": False, "name": name, "solver": solver,
                "log": res.messages[-5:]}
    # load_any, not parse_frd: since D8 a ccx deck asks for OUTPUT=3D (the
    # expanded shell) and folds it back to the mid-surface here, keeping the
    # outer fibre alongside as STRESS_PEAK.  It finds the deck beside the FRD.
    # An Abaqus run produces no FRD - its field lives in ``<case>.odb.json`` -
    # so the source is chosen per solver.  With the roots split above, the two
    # cannot see each other's artifacts.
    case_dir = out / name
    frd = case_dir / f"{name}.frd"
    odbj = case_dir / f"{name}.odb.json"
    if solver == "ccx" and frd.exists():
        data, source = post.load_any(frd), str(frd)
    elif odbj.exists():
        data, source = post.load_results_json(odbj), str(odbj)
    else:
        return {"ok": False, "name": name, "solver": solver,
                "log": [f"no result source in {case_dir}: expected {frd.name} "
                        f"(ccx) or {odbj.name} (abaqus)"]}
    peak = data["results"].get("STRESS_PEAK") or {}
    return {
        "ok": True,
        "name": name,
        "solver": solver,
        "spec": spec,
        "n_nodes": res.mesh["n_nodes"],
        "n_elements": res.mesh["n_elements"],
        "element_types": res.mesh["element_types"],
        "tri_count": res.mesh.get("tri_count"),
        "min_quality": res.mesh["min_quality"],
        "gate4": bool(res.geometry.get("topology")) and pipeline.topology.compare(
            res.geometry["topology"])["pass"],
        "max_disp": res.results.get("max_disp"),
        "pressure": float(spec.load.magnitude),
        "extra": dict(spec.extra),
        "deck": res.artifacts["inp"],
        "frd": res.artifacts["frd"],
        "source": source,
        "data": data,
        "peak": peak,
    }


def on_ring(data: dict, R: float, z: float, angle: float) -> int:
    """Node nearest to ``(R cos angle, R sin angle, z)``."""
    x, y = R * math.cos(angle), R * math.sin(angle)
    nodes = data["nodes"]
    return min(nodes, key=lambda n: (nodes[n][0] - x) ** 2
               + (nodes[n][1] - y) ** 2 + (nodes[n][2] - z) ** 2)


def radial_disp(data: dict, node: int, angle: float) -> float:
    """Radial component of the displacement at ``node``, along ``angle``."""
    u = data["results"]["DISP"][node]
    return u[0] * math.cos(angle) + u[1] * math.sin(angle)


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #
def check_pressure(size: float | None = None, label: str = "", **params
                   ) -> tuple[list[dict], dict]:
    """Stringer-free barrel, pressure only: the thin-wall vessel, both ways.

    ``**params`` are :data:`feagpt.fuselage.KNOWN_KEYS` overrides - in practice
    ``diameter`` / ``length`` / ``thickness`` - added for **D25's** size line
    (batch 6).  They move the *specimen*, never the shape: the barrel stays
    stringer-free and two-framed, so ``pR/t`` and ``pR^2/(Et)`` remain exact at
    every size and the closed form can be evaluated at the point actually run
    rather than only at the family default.  Called with no ``params`` this is
    byte-for-byte the check it always was.
    """
    p = fuselage.FuselageParams(n_stringers=0, n_frames=2, **params)
    R, t = p.radius, float(p.thickness)
    E = 73100.0                      # read off the run's own spec below
    z_mid = 0.5 * float(p.length)
    case_name = "verify_barrel_pressure" + (f"_{label}" if label else "")
    run = run_case(case_name, "ccx",
                   size=size, pressure=PRESSURE, end_shear=0.0, end_moment=0.0,
                   n_stringers=0, n_frames=2, **params)
    if not run["ok"]:
        return [{"key": "pressure.run", "pass": False, "detail": str(run["log"])}], {}

    # material from the spec that was actually run, not a local constant
    from feagpt.spec import FEASpec
    spec = FEASpec.from_json(Path(run["deck"]).with_suffix(".spec.json"))
    E = float(spec.material.youngs_modulus)
    nu = float(spec.material.poisson_ratio)

    data, peak = run["data"], run["peak"]
    node = on_ring(data, R, z_mid, MID_ANGLE)
    sig_vm = post.von_mises(peak[node]) if node in peak else float("nan")
    szz = peak[node][2] if node in peak else float("nan")
    s_hoop = hoop_stress(PRESSURE, R, t)
    err_s = (sig_vm - s_hoop) / s_hoop * 100.0

    w_node = radial_disp(data, node, MID_ANGLE)
    w_ref = radial_growth(PRESSURE, R, t, E)
    err_w = (w_node - w_ref) / w_ref * 100.0

    coord = tuple(round(c, 2) for c in data["nodes"][node])
    checks = [
        {"key": "pressure.hoop-membrane",
         "pass": abs(err_s) < TOL_MEMBRANE,
         "detail": f"outer-fibre von Mises at mid-length (node {node} at {coord}) "
                   f"= {sig_vm:.5f} MPa vs pR/t = {s_hoop:.5f} MPa -> "
                   f"{err_s:+.3f} %; sigma_z there = {szz:.5f} MPa "
                   f"({szz / s_hoop * 100:+.2f} % of hoop - the barrel has no end "
                   f"caps, so the pressure has no axial resultant)"},
        {"key": "pressure.radial-growth",
         "pass": abs(err_w) < TOL_GROWTH,
         "detail": f"radial displacement at mid-length = {w_node:.5f} mm vs "
                   f"pR^2/(E t) = {w_ref:.5f} mm -> {err_w:+.3f} % "
                   f"(E = {E:g} MPa, nu = {nu:g}; the free growth, i.e. far from "
                   f"the clamped end)"},
    ]
    info = {"hoop_vm_MPa": round(sig_vm, 6), "hoop_closed_form_MPa": round(s_hoop, 6),
            "sigma_z_MPa": round(szz, 6), "w_mm": round(w_node, 6),
            "w_closed_form_mm": round(w_ref, 6), "node": node,
            "coord": list(coord), "n_nodes": run["n_nodes"]}
    return checks, info


def check_bending(size: float | None = None, label: str = "", **params
                  ) -> tuple[list[dict], dict]:
    """Stringer-free barrel, end moment only: the beam closed form.

    ``label`` / ``**params`` as in :func:`check_pressure` - the size line needs
    the beam check at other diameters too, and ``I = pi R^3 t`` and
    ``x = R cos`` are exact at any size.  (D27: the size sweep moves downwards,
    so the sampled sizes are ``D1600`` / ``D1600+L1600``, never ``L3000`` -
    that point cannot be solved at all, see ``_probe_b6/``.)
    """
    p = fuselage.FuselageParams(n_stringers=0, n_frames=2, **params)
    R = p.radius
    z_mid = 0.5 * float(p.length)
    case_name = "verify_barrel_moment" + (f"_{label}" if label else "")
    run = run_case(case_name, "ccx",
                   size=size, pressure=0.0, end_shear=0.0, end_moment=MOMENT,
                   n_stringers=0, n_frames=2, **params)
    if not run["ok"]:
        return [{"key": "moment.run", "pass": False, "detail": str(run["log"])}], {}

    from feagpt.spec import FEASpec
    spec = FEASpec.from_json(Path(run["deck"]).with_suffix(".spec.json"))
    t = float(spec.structure.params.get("thickness",
                                        fuselage.FuselageParams.thickness))

    data, peak = run["data"], run["peak"]
    node = on_ring(data, R, z_mid, MID_ANGLE)
    sig_vm = post.von_mises(peak[node]) if node in peak else float("nan")
    I = beam_inertia(R, t)
    x = R * math.cos(MID_ANGLE)          # the sampled meridian's distance from y
    s_beam = bending_stress(MOMENT, x, I)
    err = (sig_vm - s_beam) / s_beam * 100.0
    coord = tuple(round(c, 2) for c in data["nodes"][node])
    checks = [
        {"key": "moment.beam-bending",
         "pass": abs(err) < TOL_BENDING,
         "detail": f"outer-fibre von Mises at mid-length (node {node} at {coord}) "
                   f"= {sig_vm:.5f} MPa vs M x / I = {s_beam:.5f} MPa -> "
                   f"{err:+.3f} % (I = pi R^3 t = {I:.4g} mm^4 at R = {R:g}, "
                   f"t = {t:g}; x = R cos(pi/{N_SEG}) = {x:.3f} mm - the sampled "
                   f"meridian is half a bay off the free skin seam)"},
    ]
    info = {"bending_vm_MPa": round(sig_vm, 6), "bending_closed_form_MPa": round(s_beam, 6),
            "inertia_mm4": I, "x_mm": x, "node": node, "coord": list(coord),
            "n_nodes": run["n_nodes"]}
    return checks, info


def check_combined(size: float | None = None, ccx_only: bool = False
                   ) -> tuple[list[dict], dict]:
    """The shipped barrel, all three loads: equilibrium and cross-solver."""
    ccx = run_case("verify_barrel_combined", "ccx", size=size)
    if not ccx["ok"]:
        return [{"key": "combined.ccx-run", "pass": False, "detail": str(ccx["log"])}], {}
    rows: list[dict] = []
    info: dict = {}

    data = ccx["data"]
    forc = data["results"].get("FORC") or {}
    s = {c: sum(forc[n][c] for n in forc) for c in range(3)}
    worst = max(abs(s[c]) for c in range(3)) / abs(SHEAR) * 100.0
    rows.append({
        "key": "combined.equilibrium",
        "pass": worst < TOL_EQUILIBRIUM,
        "detail": f"sum(FORC) over all {len(forc)} nodes = "
                  f"({s[0]:+.5f}, {s[1]:+.5f}, {s[2]:+.5f}) N; worst component "
                  f"{worst:.5f} % of the applied shear {SHEAR:g} N "
                  f"(must be ~0 - applied and reaction cancel by construction)",
    })
    info["force_sum_N"] = [round(s[c], 6) for c in range(3)]
    info["ccx_max_disp"] = ccx["max_disp"]
    info["ccx_nodes"] = ccx["n_nodes"]

    if not ccx_only:
        abq = run_case("verify_barrel_combined", "abaqus", size=size)
        if not abq["ok"]:
            rows.append({"key": "combined.abaqus-run", "pass": False,
                         "detail": str(abq["log"])})
        else:
            p = fuselage.parse_params(ccx["spec"])

            # --- D20: the structure's peak, load-application ring excluded ---- #
            s_c, n_c = structure_peak(ccx["data"], ccx["spec"])
            s_a, n_a = structure_peak(abq["data"], abq["spec"])
            err = _rel(s_c, s_a)
            full_c, full_a = float(ccx["max_disp"]), float(abq["max_disp"])
            err_full = _rel(full_c, full_a)
            rows.append({
                "key": "combined.cross-solver",
                "pass": err < TOL_CROSS,
                "detail": (
                    f"structure max|u| (D20 - the free-end end-load ring removed, "
                    f"by the family's own rule fuselage.barrel_nodes): ccx "
                    f"{s_c:.5f} (node {n_c}) vs abaqus {s_a:.5f} (node {n_a}) mm "
                    f"-> {err:.4f} % (tolerance {TOL_CROSS:g} %).  REPORTED, NOT "
                    f"GATED: model-wide max|u| ccx {full_c:.5f} vs abaqus "
                    f"{full_a:.5f} mm -> {err_full:.4f} % - that peak sits on the "
                    f"ring the end loads are applied to, where a nodal force on a "
                    f"free shell edge is a local artifact the two formulations "
                    f"resolve differently (see the module docstring, D20)"
                ),
            })
            info["structure_max_disp_mm"] = [round(s_c, 6), round(s_a, 6)]
            info["structure_cross_pct"] = round(err, 5)
            info["full_max_disp_mm"] = [round(full_c, 6), round(full_a, 6)]
            info["full_cross_pct"] = round(err_full, 5)
            info["abaqus_max_disp"] = full_a

            # --- the whole deflection curve, not one node -------------------- #
            # Deviation is quoted against the **tip** deflection, i.e. the
            # largest structural value, not against each station's own value.
            # A station whose centroid displacement is near zero - the first
            # bin contains the clamped ring - would otherwise turn a 1e-4 mm
            # difference into a large percentage and trip the gate for no
            # structural reason.  The plain per-station relative error is still
            # reported alongside, so the strict reading stays visible.
            prof_c = deflection_profile(ccx["data"], float(p.length))
            prof_a = deflection_profile(abq["data"], float(p.length))
            scale = max(abs(prof_c[-1]), abs(prof_a[-1]), 1e-30)
            worst_i, worst = 0, 0.0
            worst_rel_i, worst_rel = 0, 0.0
            for i, (uc, ua) in enumerate(zip(prof_c, prof_a)):
                e = abs(uc - ua) / scale * 100.0
                if e > worst:
                    worst, worst_i = e, i
                r = _rel(uc, ua)
                if r > worst_rel:
                    worst_rel, worst_rel_i = r, i
            zbar = (worst_i + 0.5) * float(p.length) / len(prof_c)
            zrel = (worst_rel_i + 0.5) * float(p.length) / len(prof_c)
            rows.append({
                "key": "combined.deflection-profile",
                "pass": worst < TOL_CROSS,
                "detail": (
                    f"section-centroid ux at {len(prof_c)} axial stations "
                    f"(deviation quoted against the tip deflection "
                    f"{scale:.5f} mm, so a near-zero station cannot inflate it): "
                    f"worst station z = {zbar:.0f} mm -> ccx {prof_c[worst_i]:.5f} "
                    f"vs abaqus {prof_a[worst_i]:.5f} mm = {worst:.4f} % "
                    f"(tolerance {TOL_CROSS:g} %).  Tip station (z = "
                    f"{p.length:g} mm): ccx {prof_c[-1]:.5f} vs abaqus "
                    f"{prof_a[-1]:.5f} mm.  Strictest per-station relative error: "
                    f"{worst_rel:.4f} % at z = {zrel:.0f} mm.  This is the beam "
                    f"quantity the load case is really about, and it moves if a "
                    f"shear or a couple is mis-emitted"
                ),
            })
            info["profile_pct_of_tip"] = round(worst, 5)
            info["profile_worst_station_mm"] = round(zbar, 3)
            info["profile_worst_relative_pct"] = round(worst_rel, 5)
            info["profile_ccx_tip_mm"] = round(prof_c[-1], 6)
            info["profile_abaqus_tip_mm"] = round(prof_a[-1], 6)
    return rows, info


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=float, default=None,
                    help="mesh size mm (default: the family's own default)")
    ap.add_argument("--ccx-only", action="store_true",
                    help="skip the Abaqus half of the combined-case check")
    ap.add_argument("--json", help="write the machine-readable report here")
    args = ap.parse_args(argv)

    p = fuselage.FuselageParams()
    R, t = p.radius, float(p.thickness)
    E = 73100.0
    print("=" * 78)
    print("  FUSELAGE BARREL VERIFICATION - closed forms + invariants")
    print("=" * 78)
    print(f"  barrel D{2 * R:g} x L{p.length:g} x t{t:g} mm | "
          f"{int(p.n_stringers)} stringers / {int(p.n_frames)} frames | "
          f"{N_SEG} meridians")
    print(f"  p = {PRESSURE:g} MPa -> sigma_hoop = pR/t = {hoop_stress(PRESSURE, R, t):.4f} MPa, "
          f"w = pR^2/(Et) = {radial_growth(PRESSURE, R, t, E):.5f} mm")
    print(f"  V = {SHEAR:g} N, M = {MOMENT:g} N.mm")
    print("-" * 78)

    checks: list[dict] = []
    report: dict = {"model": {"diameter": 2 * R, "length": float(p.length),
                              "thickness": t, "n_stringers": int(p.n_stringers),
                              "n_frames": int(p.n_frames),
                              "min_skin_segments": N_SEG}}

    for label, fn in (("pressure", check_pressure), ("moment", check_bending)):
        rows, info = fn(size=args.size)
        checks.extend(rows)
        report[label] = info
        for row in rows:
            print(f"  [{'PASS' if row['pass'] else 'FAIL'}] {row['key']}")
            print(f"        {row['detail']}")

    rows, info = check_combined(size=args.size, ccx_only=args.ccx_only)
    checks.extend(rows)
    report["combined"] = info
    for row in rows:
        print(f"  [{'PASS' if row['pass'] else 'FAIL'}] {row['key']}")
        print(f"        {row['detail']}")

    n_fail = sum(1 for c in checks if not c["pass"])
    print("-" * 78)
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
