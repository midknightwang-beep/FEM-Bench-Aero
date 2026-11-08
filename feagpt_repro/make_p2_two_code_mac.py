"""Convert external Abaqus mode-shape binaries -> npz + cross-code MAC (P0-3).

RUN AFTER the user has executed _p2_abq_scaling/run_p2_abq_modes_MANUAL.bat
outside WorkBuddy.  Uses the project venv python (numpy), NOT abaqus python.

Inputs:
  _p2_abq_scaling/<job>/<tag>_modes.{meta.json,nodes.bin,u.bin}
  reports/diagnostics/p2_ccx_modes_p020_2026-11-08.npz  (ccx safe tier)

Outputs:
  reports/diagnostics/p2_abq_modes_<tag>_2026-11-08.npz
  reports/diagnostics/p2_two_code_mac_2026-11-08.json   (U10/U14 evidence)

SCOPE: MAC is computed only after verifying the nodal label sets match
exactly (fail-closed otherwise).  This does NOT by itself close P0: mesh
convergence and analytical anchors (U2/U3) remain open.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_JOBS = _HERE / "_p2_abq_scaling"
_DIAG = _HERE / "reports" / "diagnostics"
_BASE = "fuselage_barrel_d1600_l1600_str8_frm3_buckle"
TAGS = ("p100", "p050", "p020")
CCX_NPZ = _DIAG / "p2_ccx_modes_p020_2026-11-08.npz"


def load_abq(tag: str):
    d = _JOBS / f"{_BASE}_{tag}_abq"
    m = json.loads((d / f"{tag}_modes.meta.json").read_text(encoding="utf-8"))
    nodes = np.fromfile(d / f"{tag}_modes.nodes.bin", dtype="<i8")
    raw = np.fromfile(d / f"{tag}_modes.u.bin", dtype="<f8")
    n_frames, n_nodes = m["n_u_frames"], m["n_nodes"]
    assert nodes.size == n_nodes
    assert raw.size == n_frames * n_nodes * 3, (raw.size, n_frames, n_nodes)
    u = raw.reshape(n_frames, n_nodes, 3).astype(np.float64)
    # L2-normalize each frame (MAC is scale invariant, but be explicit)
    for i in range(n_frames):
        u[i] /= np.linalg.norm(u[i])
    assert np.isfinite(u).all()
    return nodes, u, m


def mac_matrix(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    fa = A.reshape(A.shape[0], -1)
    fb = B.reshape(B.shape[0], -1)
    dot = fa @ fb.T
    na = np.linalg.norm(fa, axis=1)[:, None]
    nb = np.linalg.norm(fb, axis=1)[None, :]
    return (dot / (na * nb)) ** 2


def main() -> int:
    import sys
    missing = [p for p in [CCX_NPZ] +
               [_JOBS / f"{_BASE}_{t}_abq" / f"{t}_modes.{s}"
                for t in TAGS for s in ("meta.json", "nodes.bin", "u.bin")]
               if not p.is_file()]
    if missing:
        print("[FAILED] external Abaqus mode-shape job has not finished; missing:",
              file=sys.stderr)
        for p in missing[:4]:
            print(f"  {p}", file=sys.stderr)
        print("Run _p2_abq_scaling/run_p2_abq_modes_MANUAL.bat OUTSIDE WorkBuddy first.",
              file=sys.stderr)
        return 1
    z = np.load(CCX_NPZ)
    ccx_ids = z["node_ids_m1"]
    ccx_u = np.stack([z[f"u_m{i}"].astype(np.float64) for i in (1, 2, 3)])

    all_modes = {}
    for tag in TAGS:
        nodes, u, m = load_abq(tag)
        # fail-closed nodal mapping check
        if nodes.shape != ccx_ids.shape or not np.array_equal(nodes, ccx_ids):
            print(f"[FAILED] {tag}: Abaqus node labels do not match ccx "
                  f"({nodes.shape} vs {ccx_ids.shape}); MAC would be meaningless",
                  file=__import__("sys").stderr)
            return 1
        dest = _DIAG / f"p2_abq_modes_{tag}_2026-11-08.npz"
        arrays = {"node_ids": nodes}
        for i in range(u.shape[0]):
            arrays[f"u_m{i+1}"] = u[i].astype(np.float32)
        np.savez_compressed(dest, **arrays)
        all_modes[tag] = {"u": u, "meta": m, "npz": dest,
                          "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
                          "bytes": dest.stat().st_size}
        print(f"  {tag}: {u.shape[0]} frames x {u.shape[1]} nodes -> {dest.name}")

    # Two-code MAC on the SAFE tier only (0.02 MPa), ccx modes 1-3 vs abq 1-6
    M = mac_matrix(ccx_u, all_modes["p020"]["u"])
    out = {
        "what": "EX01 U10/U14: first TWO-CODE mode-shape MAC (ccx p020 vs Abaqus p020)",
        "date": "2026-11-08",
        "status": "diagnostic; P0 still open until U2/U3 (mesh + analytical anchors)",
        "domain": "same case, same P_ref = 0.02 MPa, same mesh / node labels",
        "node_ids_match": True,
        "n_nodes": int(ccx_ids.size),
        "ccx_modes": 3,
        "abaqus_modes": int(all_modes["p020"]["u"].shape[0]),
        "equations": {"MAC": "MAC(a,b) = (a·b)^2 / ((a·a)(b·b)) over flattened nodal U"},
        "mac_matrix_rows_ccx_cols_abq": M.tolist(),
        "ccx_best_abq_match": {},
        "abq_npz": {t: {"path": str(v["npz"]).replace("\\", "/"),
                        "sha256": v["sha256"], "bytes": v["bytes"]} for t, v in all_modes.items()},
        "repro": ["python make_p2_two_code_mac.py (after the external bat)"],
        "still_open": ["U2/U3 mesh convergence + analytical buckling anchor",
                       "EX01 D5: 6-case pilot deferred, lambda threshold frozen"],
    }
    for i, row in enumerate(M):
        j = int(np.argmax(row))
        out["ccx_best_abq_match"][f"ccx_m{i+1}"] = {
            "best_abq_mode": j + 1, "mac": float(row[j]),
            "paired": bool(row[j] >= 0.80)}
    dest = _DIAG / "p2_two_code_mac_2026-11-08.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("TWO-CODE MAC (rows ccx m1-3, cols abq m1-6):")
    for i, row in enumerate(M):
        print(f"  ccx_m{i+1}  " + " ".join(f"{v:.4f}" for v in row))
    print("best:", {k: (v["best_abq_mode"], round(v["mac"], 4))
                    for k, v in out["ccx_best_abq_match"].items()})
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
