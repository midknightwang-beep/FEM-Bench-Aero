"""U3a plate anchor: Navier simply-supported plate vs the closed form.

WOONZEE DECISION (DESIGN 11.6.6, 2026-11-09): the anchor geometry moves from
the plain barrel to a flat plate.  Rationale: the von Mises barrel comparison
stalled at +11.1 % (two boundary rounds; the residual is shell-theory layer,
NOT mesh - 28->32 mm moves lambda 1.0 %), and the plain shell cannot be
refined further (blossom leaves triangles below 28 mm, escalation unavailable
by family declaration).  The plate anchor serves the SAME evidence purpose -
"the solver + our modelling chain reproduce a known analytic result" - with a
STRONGER analytic reference (Navier's exact closed form, not an approximate
formula) and a mesh path that has always passed the quality gate.

  geometry   600 x 600 x 2.0 mm flat plate (panel family, n_stringers = 0)
  material   2024-T3, E = 73100 MPa, nu = 0.33 (same spec as the barrel)
  BC         Navier SS: all four edges DOF 3 = 0, rotations free; in-plane
             datum on the UNLOADED y=0 edge (two nodes) kills rigid-body
             modes without touching the loaded edges
  load       uniaxial compression: *CLOAD on both loaded edges (x=0 and x=L),
             equal and opposite -> self-equilibrated; lambda * P_ref is the
             total buckling force, directly comparable with the closed form
  P_ref      2000 N -> lambda_cr ~ 3.6, away from the ccx sigma=1.0 zone
  analytic   F_cr = sigma_cr * b * t,  sigma_cr = 4*pi^2*D/b^2 (k = 4 for the
             square plate),  D = E*t^3 / (12*(1-nu^2))

Gates (fail-closed, recomputed in-process):
  G1  ccx solve ok + 6 lambdas
  G2  |lambda1*P_ref - F_analytic| / F_analytic <= 5 %
  G3  mode 1 has (m, n) = (1, 1): one half-wave along x AND along y,
      counted from the OUTPUT=2D frd centre lines

The Abaqus deck is generated alongside for the user's external bat.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from feagpt.spec import FEASpec          # noqa: E402
from feagpt import pipeline, solver      # noqa: E402
from extract_buckle_dat import extract   # noqa: E402

_V11 = _HERE.parent / "FEM-Bench-Aero" / "modeling"
_JOBS = _HERE / "_p2_anchor_plate"
_ARCH = _HERE / "reports/diagnostics"
_OUT = _ARCH / "p2_anchor_plate_2026-11-09.json"
BASE = "stiffened_panel_600x600"
NAME = "anchor_plate_600x600_t2_buckle_p2000"
P_REF = 2000.0
N_MODES = 6
MESH_SIZE = 15.0
THRESH_REL = 0.05


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def analytic_fcr(E: float, nu: float, a: float, b: float, t: float):
    """Navier closed form, square simply-supported plate, k = 4.

    Returns (sigma_cr, F_cr).  k = 4.00 holds for the square plate under
    uniaxial compression with all four edges simply supported.
    """
    D = E * t**3 / (12.0 * (1.0 - nu**2))
    sigma_cr = 4.0 * math.pi**2 * D / b**2
    return sigma_cr, sigma_cr * b * t


def half_waves(frd_path: Path, deck: Path, L: float, W: float) -> tuple:
    """(m, n) of mode 1: half-waves along x and y, from the centre lines.

    Radial-free check: out-of-plane w = uz.  Along the x centre line (y = W/2)
    the sign runs of uz give 2*m transitions; same along y for n.
    """
    from extract_buckle_frd import parse_file
    frames = parse_file(frd_path, max_frames=2)
    modes = [f for f in frames if f["lambda"] > 0.0]
    if not modes:
        raise RuntimeError("no eigenmode frame parsed from the frd")
    m1 = modes[0]
    coords = {}
    in_n = False
    for ln in deck.read_text(encoding="utf-8", errors="replace").splitlines():
        s = ln.strip()
        if s.startswith("*"):
            in_n = s.upper().startswith("*NODE") and "OUTPUT" not in s.upper()
            continue
        if in_n and "," in s:
            p2 = s.split(",")
            try:
                coords[int(p2[0])] = (float(p2[1]), float(p2[2]), float(p2[3]))
            except (ValueError, IndexError):
                pass

    def runs_along(axis: str, fixed: float) -> int:
        pts = []
        for nid, u in zip(m1["nodes"], m1["u"]):
            c = coords.get(nid)
            if c is None:
                continue
            x, y, _z = c
            if axis == "x" and abs(y - fixed) < W * 0.02:
                pts.append((x, u[2]))
            elif axis == "y" and abs(x - fixed) < L * 0.02:
                pts.append((y, u[2]))
        pts.sort()
        if len(pts) < 8:
            raise RuntimeError(f"centre line too sparse: {len(pts)} nodes ({axis})")
        signs = [1 if v > 0 else (-1 if v < 0 else 0) for _c, v in pts]
        return max(sum(1 for a, b in zip(signs, signs[1:])
                       if a != b and a != 0 and b != 0) // 2, 1)

    m = runs_along("x", W / 2.0)
    n = runs_along("y", L / 2.0)
    return m, n


def main() -> int:
    _JOBS.mkdir(parents=True, exist_ok=True)
    d = json.loads((_V11 / BASE / "spec.json").read_text(encoding="utf-8"))
    d["name"] = NAME
    d["structure"]["params"]["n_stringers"] = 0
    d["mesh"]["size_chord"] = MESH_SIZE
    d["mesh"]["size_span"] = MESH_SIZE
    d["analysis"]["step_type"] = "buckle"
    d["analysis"]["buckling"] = {
        "n_modes": N_MODES,
        "reference_load": {"kind": "edge_compression", "magnitude": P_REF,
                           "load_edge_groups": ["ex0", "exL"], "dof": 1},
    }
    d["extra"] = {"bc_kind": "ss_plate_navier", "anchor_split_edges": True}
    spec = FEASpec.from_dict(d)
    outdir = _JOBS / NAME
    outdir.mkdir(parents=True, exist_ok=True)

    # ccx deck first (the solving dialect); Abaqus deck in its own outdir -
    # the same-name overwrite lesson from the barrel anchor probe.
    res_ccx = pipeline.run(spec, outdir=outdir, step_export=False,
                           deck_only=True, solver_name="ccx")
    deck_ccx = Path(res_ccx.artifacts["inp"])
    outdir_abq = _JOBS / f"{NAME}_abq"
    outdir_abq.mkdir(parents=True, exist_ok=True)
    res_abq = pipeline.run(spec, outdir=outdir_abq, step_export=False,
                           deck_only=True, solver_name="abaqus")
    deck_abq = Path(res_abq.artifacts["inp"])
    for deck in (deck_ccx, deck_abq):
        t = deck.read_text(encoding="utf-8", errors="replace")
        assert "NEDGES, 3, 3, 0.0" in t, f"{deck.name}: SS plate BC line missing"
        assert "*CLOAD" in t, f"{deck.name}: edge compression missing"

    run = solver.run(deck_ccx, solver="ccx", timeout=2400)
    dat = outdir / f"{NAME}.dat"
    frd = outdir / f"{NAME}.frd"
    if dat.exists():
        shutil.copyfile(dat, _ARCH / f"{NAME}.dat")
    lambdas, err = [], None
    if dat.exists():
        try:
            lambdas = extract(str(dat), "ccx", expect=N_MODES)["lambdas"]
        except Exception as exc:                    # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"

    # analytic recomputation (in-process, never hand-copied)
    sigma_cr, f_analytic = analytic_fcr(
        float(spec.material.youngs_modulus), float(spec.material.poisson_ratio),
        float(spec.structure.params["length"]),
        float(spec.structure.params["width"]),
        float(spec.structure.params["thickness"]))

    f_num = lambdas[0] * P_REF if lambdas else None
    rel = (abs(f_num - f_analytic) / f_analytic) if f_num else None

    m_half = n_half = None
    mode_err = None
    if frd.exists():
        try:
            m_half, n_half = half_waves(frd, deck_ccx,
                                        float(spec.structure.params["length"]),
                                        float(spec.structure.params["width"]))
        except Exception as exc:                    # noqa: BLE001
            mode_err = f"{type(exc).__name__}: {exc}"

    g1 = bool(run.ok) and len(lambdas) == N_MODES and not err
    g2 = rel is not None and rel <= THRESH_REL
    g3 = (m_half, n_half) == (1, 1)
    out = {
        "what": "U3a plate anchor: Navier SS plate under uniaxial compression "
                "vs the exact closed form (ccx side)",
        "date": "2026-11-09",
        "decision": "woonzee route B (plate anchor) - DESIGN 11.6.6; barrel "
                    "route kept as physical-band statement only",
        "p_ref_n": P_REF, "n_modes": N_MODES, "mesh_size": MESH_SIZE,
        "deck_ccx_sha256": sha(deck_ccx),
        "deck_abq": str(deck_abq).replace("\\", "/"),
        "deck_abq_sha256": sha(deck_abq),
        "solve_rc": run.returncode, "solve_ok": bool(run.ok),
        "lambdas": lambdas, "parse_error": err,
        "analytic": {
            "sigma_cr_mpa": sigma_cr, "f_cr_n": f_analytic, "k": 4.0,
            "source": "Navier closed form for the simply-supported rectangular "
                      "plate, exact (not an approximate formula)",
        },
        "f_cr_num_n": f_num, "rel_dev_vs_analytic": rel,
        "gate_rel_threshold": THRESH_REL,
        "mode_half_waves": {"m_along_x": m_half, "n_along_y": n_half},
        "mode_error": mode_err,
        "status": "ok" if (g1 and g2 and g3) else "fail",
    }
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print(f"[plate] rc={run.returncode} lambdas={lambdas}")
    print(f"[plate] analytic sigma_cr={sigma_cr:.4f} MPa F_cr={f_analytic:.2f} N")
    print(f"[plate] F_num={f_num} rel={rel} (m,n)=({m_half},{n_half})")
    print(f"[plate] G1={g1} G2={g2} G3={g3} -> {out['status']}")
    print(f"Abaqus deck for the external bat: {deck_abq}")
    return 0 if out["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
