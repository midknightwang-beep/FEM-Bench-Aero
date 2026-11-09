"""U3a: analytical anchor for the C6-P2 buckling line (2026-11-09, woonzee A/B/C).

The von Mises / DTMB formulas assume an UNSTIFFENED, SIMPLY-SUPPORTED cylinder
under HYDROSTATIC external pressure - three assumptions the shipped cantilever
case violates, so the anchor is an INDEPENDENT diagnostic case:

  geometry   D1600 x L1600 x t3, mid-surface r=800 (same family parameters,
             stringers/frames removed - n_frames=0 is legal since today)
  BC         SS-3 "rigid end rings": both end rings DOF 1,2 = 0, one ring
             DOF 3 = 0 (woonzee decision, DESIGN 11.6.4)
  load       hydrostatic: lateral pressure + axial end load N_x = P*r/2
             (*DLOAD + *CLOAD, scaled together by lambda)
  P_ref      0.01 MPa  ->  lambda_cr ~ 3, far from the ccx sigma=1.0 zone
  mesh       size 28 mm - measured: blossom minSICN is size-sensitive on the
             plain shell (25 -> 0.030 FAIL, 28 -> 0.441 pass; the 2026-10-05
             cap sweep saw the same non-monotonicity), 28 passes the 0.30 gate

Gates (fail-closed, all computed here, no hand-copied numbers):
  G1  ccx solve ok + 6 lambdas extracted
  G2  N_cr(1) = lambda1 * P_ref within 5 % of the analytic P_cr
      (analytic recomputed HERE from E/nu/r/L/t, never hand-copied)
  G3  first mode has 8 circumferential lobes (the analytic n=8 prediction),
      counted from the OUTPUT=2D frd mid-span ring
Gates G2/G3 use the CCX side; the Abaqus deck is generated alongside for the
user's external bat (same three gates run on it by check_p2_anchor_abq).
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
_JOBS = _HERE / "_p2_anchor"
_ARCH = _HERE / "reports/diagnostics"
_OUT = _ARCH / "p2_anchor_2026-11-09.json"
BASE = "fuselage_barrel_d1600_l1600_str8_frm3"
NAME = "anchor_unstiffened_d1600_l1600_t3_buckle_p010"
P_REF = 0.01
N_MODES = 6
MESH_SIZE = 28.0
THRESH_REL = 0.05


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def analytic_pcr(E: float, nu: float, r: float, L: float, t: float):
    """von Mises complete (SS ends, hydrostatic) minimised over lobes n,
    cross-checked against the Windenburg-Trilling / DTMB envelope.

    Sources: JOT paper eq.1 / Porto thesis 2.15 (n^2-1 form) for the complete
    formula; OSTI external-pressure design notes eq.19 / JOT eq.2 for DTMB.
    Both forms were cross-checked on this geometry BEFORE anything was run:
    0.029935 vs 0.029942 MPa (ratio 0.9998).
    """
    best = None
    best_n = None
    for n in range(2, 30):
        den1 = n**2 - 1 + 0.5 * (math.pi * r / L) ** 2
        t1 = 1.0 / (n**2 * (L / (math.pi * r)) ** 2 + 1) ** 2
        t2 = (t**2 / (12 * r**2 * (1 - nu**2))) * (
            n**2 - 1 + (math.pi * r / L) ** 2) ** 2
        p = E * (t / r) / den1 * (t1 + t2)
        if best is None or p < best:
            best, best_n = p, n
    p_dtmb = (2.42 * E * (t / (2 * r)) ** 2.5
              / ((1 - nu**2) ** 0.75
                 * ((L / (2 * r)) - 0.447 * (t / (2 * r)) ** 0.5)))
    return best, best_n, p_dtmb


def main() -> int:
    _JOBS.mkdir(parents=True, exist_ok=True)
    d = json.loads((_V11 / BASE / "spec.json").read_text(encoding="utf-8"))
    d["name"] = NAME
    d["structure"]["params"]["n_stringers"] = 0
    d["structure"]["params"]["n_frames"] = 0
    d["mesh"]["size_chord"] = MESH_SIZE
    d["mesh"]["size_span"] = MESH_SIZE
    d["analysis"]["step_type"] = "buckle"
    d["analysis"]["buckling"] = {
        "n_modes": N_MODES,
        "reference_load": {"kind": "hydrostatic_external", "magnitude": P_REF,
                           "pressure_sign": -1.0, "load_group": "zL",
                           "axial_load_group": "z0"},
    }
    d["extra"] = {"bc_kind": "ss3_ring"}
    spec = FEASpec.from_dict(d)
    outdir = _JOBS / NAME
    outdir.mkdir(parents=True, exist_ok=True)

    # --- decks for BOTH codes (Abaqus deck goes to the user's external bat) --
    # NOTE: pipeline writes the deck as <outdir>/<spec.name>.inp, so the two
    # dialects MUST go to different outdirs - a second run with the same
    # outdir silently overwrote the ccx deck with Abaqus cards and ccx died
    # with rc=201 ("EIGENSOLVER=LANCZOS: parameter not recognized").
    res_ccx = pipeline.run(spec, outdir=outdir, step_export=False,
                           deck_only=True, solver_name="ccx")
    deck_ccx = Path(res_ccx.artifacts["inp"])
    outdir_abq = _JOBS / f"{NAME}_abq"
    outdir_abq.mkdir(parents=True, exist_ok=True)
    res_abq = pipeline.run(spec, outdir=outdir_abq, step_export=False,
                           deck_only=True, solver_name="abaqus")
    deck_abq = Path(res_abq.artifacts["inp"])
    for deck in (deck_ccx, deck_abq):
        txt = deck.read_text(encoding="utf-8", errors="replace")
        assert "NZ0, 1, 2, 0.0" in txt and "NZL, 1, 2, 0.0" in txt, \
            f"{deck.name}: SS-3 boundary lines missing"
        assert "*CLOAD" in txt, f"{deck.name}: axial end load missing"

    # --- ccx solve (serial, R61) ------------------------------------------- #
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

    # --- analytic recomputation (never hand-copied) ------------------------ #
    p_analytic, n_analytic, p_dtmb = analytic_pcr(
        float(spec.material.youngs_modulus), float(spec.material.poisson_ratio),
        float(spec.structure.params["diameter"]) / 2.0,
        float(spec.structure.params["length"]),
        float(spec.structure.params["thickness"]))

    n_cr1 = lambdas[0] * P_REF if lambdas else None
    rel = (abs(n_cr1 - p_analytic) / p_analytic) if n_cr1 else None

    # --- G3: lobes of mode 1 from the OUTPUT=2D frd ------------------------ #
    lobes = None
    lobes_err = None
    if frd.exists():
        try:
            from extract_buckle_frd import parse_file
            frames = parse_file(frd, max_frames=2)
            modes = [f for f in frames if f["lambda"] > 0.0]
            m1 = modes[0]
            # node coordinates: parse the deck *NODE table
            coords = {}
            in_n = False
            for ln in deck_ccx.read_text(encoding="utf-8",
                                         errors="replace").splitlines():
                s = ln.strip()
                if s.startswith("*"):
                    in_n = s.upper().startswith("*NODE") and "OUTPUT" not in s.upper()
                    continue
                if in_n and "," in s:
                    p2 = s.split(",")
                    try:
                        coords[int(p2[0])] = (float(p2[1]), float(p2[2]),
                                              float(p2[3]))
                    except (ValueError, IndexError):
                        pass
            mid = [(nid, u) for nid, u in zip(m1["nodes"], m1["u"])
                   if nid in coords and abs(coords[nid][2] - 800.0) < 1.0]
            if len(mid) < 16:
                raise RuntimeError(f"mid ring too small: {len(mid)} nodes")
            import math as _math
            seq = []
            for nid, u in mid:
                x, y, _z = coords[nid]
                theta = _math.atan2(y, x)
                r = _math.hypot(x, y)
                ur = u[0] * (x / r) + u[1] * (y / r)
                seq.append((theta, ur))
            seq.sort()
            signs = [1 if v > 0 else (-1 if v < 0 else 0) for _t, v in seq]
            runs = sum(1 for a, b in zip(signs, signs[1:]) if a != b and a and b)
            lobes = max(runs // 2, 1)
        except Exception as exc:                    # noqa: BLE001
            lobes_err = f"{type(exc).__name__}: {exc}"

    g1 = bool(run.ok) and len(lambdas) == N_MODES and not err
    g2 = rel is not None and rel <= THRESH_REL
    g3 = lobes == n_analytic
    out = {
        "what": "U3a analytical anchor: unstiffened SS-hydrostatic barrel vs "
                "von Mises / DTMB (ccx side)",
        "date": "2026-11-09",
        "decisions": "SS-3 ring BC / 5 % threshold / mesh 1.4x plan per "
                     "DESIGN 11.6.4; anchor mesh size 28 (measured blossom "
                     "minSICN 0.441, only passing size in the 20-28 sweep)",
        "p_ref_mpa": P_REF, "n_modes": N_MODES,
        "deck_ccx_sha256": sha(deck_ccx),
        "deck_abq": str(deck_abq).replace("\\", "/"),
        "deck_abq_sha256": sha(deck_abq),
        "solve_rc": run.returncode, "solve_ok": bool(run.ok),
        "lambdas": lambdas, "parse_error": err,
        "analytic": {
            "von_mises_complete": p_analytic, "lobes_n": n_analytic,
            "dtmb_envelope": p_dtmb,
            "ratio_mises_dtmb": p_analytic / p_dtmb,
            "source": "JOT eq.1 / Porto 2.15 (complete); OSTI eq.19 / JOT eq.2 "
                      "(DTMB); recomputed in-process, not hand-copied",
        },
        "n_cr1_mpa": n_cr1, "rel_dev_vs_analytic": rel,
        "gate_rel_threshold": THRESH_REL,
        "lobes_num": lobes, "lobes_error": lobes_err,
        "status": "ok" if (g1 and g2 and g3) else "fail",
    }
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print(f"[anchor] rc={run.returncode} lambdas={lambdas}")
    print(f"[anchor] analytic P_cr={p_analytic:.6f} (n={n_analytic}) "
          f"DTMB={p_dtmb:.6f}")
    print(f"[anchor] N_cr1={n_cr1} rel={rel} lobes={lobes} (analytic n={n_analytic})")
    print(f"[anchor] G1={g1} G2={g2} G3={g3} -> {out['status']}")
    print(f"Abaqus deck for the external bat: {deck_abq}")
    return 0 if out["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
