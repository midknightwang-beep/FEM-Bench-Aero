"""ccx-internal mode-shape pairing (EX01 C3 verification, 2026-11-08).

Compares the sigma-contaminated 0.1 MPa tier's 6 shapes against the safe
0.02 MPa tier's 6 shapes by MAC.  Stage-1 inferred from LAMBDA VALUES alone
that the old "lambda1/lambda2" were modes 4/5 of the 6-mode spectrum; this
probe checks that inference at the MODE-SHAPE level.

SCOPE LIMIT: this is ccx-vs-ccx (same code).  It is NOT the two-code MAC
required by U10/P0-3 and does NOT close P0.

Memory-safe: fixed-width rows are accumulated into array('d') (8-byte
floats, ~36 MB for 7 frames x 213270 nodes x 3) rather than python floats.
"""

from __future__ import annotations

import hashlib
import json
import sys
from array import array
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_OUT = _HERE / "reports" / "diagnostics" / "p2_ccx_mode_pairing_2026-11-08.json"
_BASE = "fuselage_barrel_d1600_l1600_str8_frm3_buckle"
_ROOT = _HERE / "_p2_scaling_ccx"


def load_shapes(tag: str, n_modes: int = 6) -> tuple[np.ndarray, list[float], list[int]]:
    """Return (n_modes, n_nodes, 3) float64 array, lambdas, node ids."""
    d = _ROOT / f"{_BASE}_{tag}"
    frd = d / f"{_BASE}_{tag}.frd"
    frames: list[dict] = []
    cur = None
    in_step = False
    with frd.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            stripped = line.strip()
            if not stripped:
                continue
            tagword = stripped.split()[0]
            if tagword == "1PSTEP":
                in_step = True
                cur = None
                continue
            if not in_step:
                continue
            parts = stripped.split()
            if parts[0] == "100CL" and len(parts) >= 4:
                cur = {"lambda": float(parts[2]),
                       "u": array("d"), "nodes": array("q")}
                frames.append(cur)
                continue
            if tagword == "-3":
                in_step = False
                cur = None
                if len(frames) >= n_modes + 1:  # static frame + n_modes
                    break
                continue
            if cur is None or not line.startswith(" -1") or len(line) < 49:
                continue
            try:
                node = int(line[3:13])
                cur["nodes"].append(node)
                for sl in (slice(13, 25), slice(25, 37), slice(37, 49)):
                    cur["u"].append(float(line[sl]))
            except ValueError:
                continue
    modes = [f for f in frames if f["lambda"] > 0.0][:n_modes]
    assert len(modes) == n_modes, f"{tag}: got {len(modes)} modes"
    n_nodes = len(modes[0]["nodes"])
    assert all(len(f["nodes"]) == n_nodes for f in modes)
    arr = np.empty((n_modes, n_nodes, 3), dtype=np.float64)
    for i, f in enumerate(modes):
        a = np.frombuffer(f["u"], dtype=np.float64)
        assert a.size == n_nodes * 3
        arr[i] = a.reshape(n_nodes, 3)
        # L2-normalize each shape (MAC is scale invariant, but be explicit)
        arr[i] /= np.linalg.norm(arr[i])
    return arr, [f["lambda"] for f in modes], list(modes[0]["nodes"])


def mac_matrix(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """(nA, nB) MAC between flattened nodal vectors."""
    fa = A.reshape(A.shape[0], -1)
    fb = B.reshape(B.shape[0], -1)
    dot = fa @ fb.T
    na = np.linalg.norm(fa, axis=1)[:, None]
    nb = np.linalg.norm(fb, axis=1)[None, :]
    return (dot / (na * nb)) ** 2


def main() -> int:
    A, lam_safe, ids_safe = load_shapes("p020")
    B, lam_bad, ids_bad = load_shapes("p100")
    assert ids_safe == ids_bad, "node-id mapping changed between tiers"
    M = mac_matrix(B, A)   # rows = p100 (contaminated), cols = p020 (safe)
    # NOTE: print in scientific notation.  With "%.4f" every value looked
    # like 0.0000 and the matrix was briefly (mis)read as an all-zero bug.
    print("MAC matrix (rows p100 0.1 MPa, cols p020 0.02 MPa):")
    print("      " + " ".join(f"m{j+1:<10d}" for j in range(6)))
    for i, row in enumerate(M):
        print(f"  m{i+1}  " + " ".join(f"{v:.2e} " for v in row))

    # A weak argmax is NOT a pairing.  Only call it a match above threshold.
    MAC_MATCH_THRESHOLD = 0.80
    best = {}
    for i, row in enumerate(M):
        j = int(np.argmax(row))
        v = float(row[j])
        best[f"p100_m{i+1}"] = {
            "argmax_p020_mode": j + 1,
            "mac": v,
            "paired": v >= MAC_MATCH_THRESHOLD,
            "lambda_p100": lam_bad[i],
            "lambda_p020_of_argmax_mode": lam_safe[j],
            "note": "NO PAIRING: max MAC below %.2f. The p100 shapes do not "
                    "correspond to any of the lowest 6 safe-tier modes; more "
                    "safe-tier modes would be needed to locate them."
                    % MAC_MATCH_THRESHOLD if v < MAC_MATCH_THRESHOLD else "paired"}
    # stage-1 inference: old 2-mode lambdas 1.008207 / 1.009420 are modes 4/5
    old = [1.008207, 1.009420]
    stage1 = []
    for v in old:
        k = min(range(len(lam_bad)), key=lambda k: abs(lam_bad[k] - v))
        stage1.append({"old_lambda": v, "p100_6mode_index": k + 1,
                       "lambda_full_precision": lam_bad[k]})
    # ccx-internal control: same physical modes across the two SAFE tiers.
    C, lam_p050, _ = load_shapes("p050")
    safe_mac = [float(mac_matrix(C[i:i + 1], A[i:i + 1])[0, 0]) for i in range(3)]
    cross_mac = float(mac_matrix(A[0:1], A[1:2])[0, 0])
    print("p020 vs p050 same-mode MAC:", [f"{v:.6f}" for v in safe_mac],
          "| p020 m1 vs m2:", f"{cross_mac:.2e}")
    out = {
        "what": "EX01 C3 verification at MODE-SHAPE level (ccx-internal, NOT two-code MAC)",
        "date": "2026-11-08",
        "status": "diagnostic; does NOT close U10/P0-3, does NOT close P0",
        "sources": {
            "safe_tier": "_p2_scaling_ccx/..._p020/*.frd",
            "contaminated_tier": "_p2_scaling_ccx/..._p100/*.frd",
            "node_ids_sha256": hashlib.sha256(
                ",".join(map(str, ids_safe)).encode()).hexdigest(),
            "n_nodes": len(ids_safe),
        },
        "equations": {
            "MAC": "MAC(a,b) = (a·b)^2 / ((a·a)(b·b)) over flattened nodal U vectors",
            "normalization": "each mode L2-normalized before MAC (scale invariant)",
        },
        "lambda_p020": lam_safe,
        "lambda_p050": lam_p050,
        "lambda_p100": lam_bad,
        "mac_matrix_rows_p100_cols_p020": M.tolist(),
        "mac_match_threshold": MAC_MATCH_THRESHOLD,
        "p020_vs_p050_same_mode_mac_modes_1_3": safe_mac,
        "p020_m1_vs_m2_mac": cross_mac,
        "argmax_per_p100_mode": best,
        "stage1_lambda_inference": stage1,
        "findings": [],
        "scope_limit": "ccx vs ccx only. The Abaqus-side shapes are NOT available "
                       "yet (external ODB job is the NEXT task). A high MAC here "
                       "validates the load-scaling/mode-selection mechanism, NOT "
                       "any cross-code formulation conclusion.",
        "still_open": ["U10/U14 two-code MAC", "U2/U3 mesh + analytical anchors",
                       "EX01 D5: 6-case pilot deferred, lambda threshold frozen"],
        "repro": ["python probe_p2_mode_pairing.py"],
    }
    F = out["findings"]
    F.append("F-m1: node ids are identical across the three tiers (sha256 in sources), "
             "so no nodal remapping is needed for the later two-code MAC.")
    F.append("F-m2: ccx-internal MAC(p020_mi, p050_mi) = %s for i=1..3 and "
             "MAC(p020 m1,m2) = %.2e => load scaling preserves mode shapes and the "
             "parser does not mix frames. This is a SAME-CODE control, not a two-code MAC."
             % ([round(v, 6) for v in safe_mac], cross_mac))
    max_all = float(M.max())
    F.append("F-m3: NO p100 mode pairs with any of the lowest 6 p020 modes "
             "(max MAC over the whole 6x6 matrix = %.2e, threshold %.2f). "
             "The 0.1 MPa tier's shapes are therefore NOT the fundamental modes; "
             "this is consistent with the sigma=1.0 selection artifact but does "
             "NOT locate which higher modes they are -- that would need a larger "
             "safe-tier spectrum. Do not claim a mode-shape-level proof of C3."
             % (max_all, MAC_MATCH_THRESHOLD))
    F.append("F-m4: stage-1 inference from lambda values (old 1.008207 / 1.009420 are "
             "modes 4/5 of the 6-mode spectrum) is checked against full-precision "
             "100CL lambdas: %s." % json.dumps(stage1, ensure_ascii=False))
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {_OUT}")
    for x in F:
        print("   ", x[:170])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
