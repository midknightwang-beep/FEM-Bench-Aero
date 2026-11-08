"""Parse CalculiX 2.23 *BUCKLE mode shapes from a .frd file (C6-P2 P0-3).

Real-machine facts (2026-11-08, p020 / p050 / p100 scaling jobs):
  * Pre-step section starts with "    2C  <n_nodes> ..." then " -1" lines
    carrying nodal COORDINATES (not mode shapes) -- must be skipped.
  * Each result frame is introduced by "   1PSTEP ...", then a
    "  100CL  <idx> <value> <n_nodes> ..." line whose <value> is the
    buckling factor (lambda) for that frame in FULL precision (9 s.f.),
    vs 7 s.f. in .dat.
  * Frame 1 has value 0.00000E+00: the static/pre-buckling reference
    displacement field, NOT a mode -> must be excluded.
  * Frames 2..N+1 carry the N requested mode shapes, in the same order as
    the .dat BUCKLING FACTOR OUTPUT table.
  * Data rows are FIXED WIDTH (no separator between negative numbers):
      " -1<10-char node id><12-char ux><12-char uy><12-char uz>"
    i.e. [3:13] node id, [13:25], [25:37], [37:49].

This parser streams the file line by line (92 MB per job) and keeps only the
requested modes in memory. It has a self-test with real-machine excerpts and
negative pins. Nothing here edits a frozen artifact.

Usage:
  python extract_buckle_frd.py --self-test
  python extract_buckle_frd.py <file.frd> --dat <file.dat> --modes 3 --json <out.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

NODE_SLICE = slice(3, 13)
COMP_SLICES = (slice(13, 25), slice(25, 37), slice(37, 49))
_DATA_PREFIX = " -1"


def _tag(line: str) -> str:
    """Leading-space-insensitive record tag.

    REAL-MACHINE FIX (2026-11-08): the first parser hard-coded 3 spaces
    before 1PSTEP because the hand-written self-test fragment used 3; the
    actual ccx 2.23 .frd uses **4**.  The parser then found zero frames on
    the real file while all 22 self-test pins were green -- exactly the
    'validating my parser with my own invented input' trap.  Match by tag
    after lstrip, and keep the fixed-width data row slicing below untouched.
    """
    return line.lstrip().split()[0] if line.strip() else ""


def _parse_cl(line: str) -> tuple[int, float, int] | None:
    """Parse the 100CL frame header: index, lambda, n_nodes."""
    parts = line.strip().split()
    if len(parts) < 4 or parts[0] != "100CL":
        return None
    try:
        return int(parts[1]), float(parts[2]), int(parts[3])
    except ValueError:
        return None


def _parse_data(line: str) -> tuple[int, tuple[float, float, float]] | None:
    if not line.startswith(_DATA_PREFIX) or len(line.rstrip("\r\n")) < 49:
        return None
    s = line.rstrip("\r\n")
    try:
        node = int(s[NODE_SLICE])
        comps = tuple(float(s[c]) for c in COMP_SLICES)
        return node, comps  # type: ignore[return-value]
    except ValueError:
        return None


def parse_frames(lines, max_frames: int | None = None) -> list[dict]:
    """Stream an iterable of lines; return frames with lambda + nodal U.

    A frame is: 1PSTEP -> 100CL -> (-4 DISP ... -5 ...) -> -1 rows -> -3.
    Nodal coordinate lines before the first 1PSTEP are ignored.
    """
    frames: list[dict] = []
    cur: dict | None = None
    in_step = False
    for raw in lines:
        line = raw.rstrip("\r\n")
        tag = _tag(line)
        if tag == "1PSTEP":
            in_step = True
            cur = None
            continue
        if not in_step:
            continue
        cl = _parse_cl(line)
        if cl is not None:
            idx, lam, n_nodes = cl
            cur = {"cl_index": idx, "lambda": lam, "n_nodes_declared": n_nodes,
                   "nodes": [], "u": []}
            frames.append(cur)
            continue
        if tag == "-3":
            in_step = False
            cur = None
            # True streaming cut-off: the file is ~92 MB with 7 frames x
            # 213k nodes.  Keeping only frame 1 (static) + the first N mode
            # frames avoids ~1.5 million python floats per extra frame.
            if max_frames and len(frames) >= max_frames:
                break
            continue
        if cur is None:
            continue
        d = _parse_data(line)
        if d is not None:
            node, comps = d
            cur["nodes"].append(node)
            cur["u"].append(comps)
    return frames


def parse_file(path: str | Path, max_frames: int | None = None) -> list[dict]:
    p = Path(path)
    with p.open("r", encoding="utf-8", errors="replace") as fh:
        return parse_frames(fh, max_frames=max_frames)


def scan_frame_headers(path: str | Path) -> list[dict]:
    """Cheap pass: read ONLY 100CL headers (all frames, zero nodal data).

    Lets us align ALL requested modes against the .dat table without ever
    holding more than a handful of floats in memory.
    """
    out: list[dict] = []
    with Path(path).open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            cl = _parse_cl(line)
            if cl is not None:
                idx, lam, n_nodes = cl
                out.append({"cl_index": idx, "lambda": lam,
                            "n_nodes_declared": n_nodes})
    return out


def norm_l2(u) -> float:
    return math.sqrt(sum(float(x) ** 2 for row in u for x in row))


def normalize(u) -> list[list[float]]:
    """Unit-L2 mode shape (MAC is scale invariant, but keep it explicit)."""
    n = norm_l2(u)
    if n == 0.0:
        raise ValueError("zero-norm mode shape")
    return [[float(x) / n for x in row] for row in u]


def mac(u, v) -> float:
    """Modal Assurance Criterion between two same-length nodal vectors."""
    dot = sum(float(a) * float(b) for ra, rb in zip(u, v) for a, b in zip(ra, rb))
    nu, nv = norm_l2(u), norm_l2(v)
    if nu == 0.0 or nv == 0.0:
        return 0.0
    return (dot * dot) / (nu * nu * nv * nv)


def load_dat(path: str | Path) -> list[float]:
    """Read the 6-mode .dat table (independent source for lambda alignment)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from extract_buckle_dat import parse_ccx_text
    txt = Path(path).read_text(encoding="utf-8", errors="replace")
    rows = parse_ccx_text(txt)
    return [r["lambda"] for r in rows]


def align(frames: list[dict], dat_lambdas: list[float], tol_rel: float = 5e-6) -> dict:
    """Cross-check frame lambdas (full precision) against the .dat table."""
    modes = [f for f in frames if f["lambda"] > 0.0]
    static = [f for f in frames if f["lambda"] == 0.0]
    checks = []
    ok = True
    for i, (f, d) in enumerate(zip(modes, dat_lambdas), 1):
        rel = abs(f["lambda"] - d) / ((f["lambda"] + d) / 2.0)
        good = rel <= tol_rel
        ok &= good
        checks.append({"mode": i, "frd_lambda": f["lambda"], "dat_lambda": d,
                       "rel": rel, "aligned": good})
    if len(modes) != len(dat_lambdas):
        ok = False
    return {"ok": ok, "n_static_frames": len(static), "n_mode_frames": len(modes),
            "n_dat_modes": len(dat_lambdas), "checks": checks,
            "tol_rel": tol_rel}


# ---------------------------------------------------------------------------
# self-test: real-machine excerpts + negative pins
# ---------------------------------------------------------------------------
# Indentation below is copied from the REAL p020 .frd (4 spaces before
# 1PSTEP, 2 before 100CL).  Earlier the fragment used 3 spaces and all 22
# pins passed while the real file produced zero frames.  Do not "tidy" it.
_FRAGMENT = """    1C
    2C                        4                     1
 -1         1 0.00000E+00 0.00000E+00 0.00000E+00
 -3
    1PSTEP                         1           1           1
  100CL  101 0.00000E+00      4                     4    1           1
 -4  DISP        4    1
 -5  D1          1    2    1    0
 -1         1 8.51464E-06-4.50510E-22 3.83078E-36
 -1         2-8.51464E-06 4.50510E-22-3.83078E-36
 -1         3 1.00000E-01 2.00000E-01 3.00000E-01
 -1         4-1.00000E-01-2.00000E-01-3.00000E-01
 -3
    1PSTEP                         2           1           1
  100CL  102 3.513125628      4                     4    2           1
 -4  DISP        4    1
 -1         1 1.00000E+00 0.00000E+00 0.00000E+00
 -1         2 0.00000E+00 1.00000E+00 0.00000E+00
 -1         3 0.00000E+00 0.00000E+00 1.00000E+00
 -1         4 1.00000E+00 1.00000E+00 1.00000E+00
 -3
    1PSTEP                         3           1           1
  100CL  103 3.517130875      4                     4    3           1
 -4  DISP        4    1
 -1         1 0.00000E+00 0.00000E+00 1.00000E+00
 -1         2 0.00000E+00 1.00000E+00 0.00000E+00
 -1         3 1.00000E+00 0.00000E+00 0.00000E+00
 -1         4 1.00000E+00 1.00000E+00 1.00000E+00
 -3
"""

# Two byte-exact lines lifted from the real p020 .frd (recurrence pins).
_REAL_PSTEP_LINE = "    1PSTEP                         1           1           1          "
_REAL_CL_LINE = "  100CL  102 3.513125628      213270                     4    2           1"

_REAL_DAT = """     B U C K L I N G   F A C T O R   O U T P U T
 MODE NO       BUCKLING
                FACTOR
      1   0.3513126E+01
      2   0.3517131E+01
"""


def self_test() -> int:
    pins: list[tuple[str, bool]] = []

    def pin(name, cond):
        pins.append((name, bool(cond)))

    fr = parse_frames(_FRAGMENT.splitlines())
    pin("3 frames parsed", len(fr) == 3)
    pin("frame1 lambda = 0 (static)", fr[0]["lambda"] == 0.0)
    pin("frame2 lambda full precision", abs(fr[1]["lambda"] - 3.513125628) < 1e-12)
    pin("frame3 lambda full precision", abs(fr[2]["lambda"] - 3.517130875) < 1e-12)
    pin("coordinate -1 row before PSTEP excluded",
        all(n not in (-1,) for f in fr for n in f["nodes"]))
    pin("4 nodes in each frame", all(len(f["nodes"]) == 4 for f in fr))
    pin("node ids parsed", fr[1]["nodes"] == [1, 2, 3, 4])
    pin("negative adjacent numbers parsed (fixed width)",
        abs(fr[0]["u"][1][0] + 8.51464e-06) < 1e-15)
    pin("3 components parsed", len(fr[0]["u"][0]) == 3)
    pin("declared n_nodes matches data rows",
        all(f["n_nodes_declared"] == len(f["nodes"]) for f in fr))

    a = align(fr, load_dat_from_text(_REAL_DAT))
    pin("align: 1 static + 2 mode frames",
        a["n_static_frames"] == 1 and a["n_mode_frames"] == 2)
    pin("align: all lambdas match .dat", a["ok"] is True)
    pin("align: rel below tol", all(c["rel"] < 5e-6 for c in a["checks"]))

    # negative pins: wrong .dat must fail
    bad = align(fr, [3.6, 3.517])
    pin("align: wrong .dat detected", bad["ok"] is False)
    bad2 = align(fr, [3.513125628])   # fewer modes than frames
    pin("align: mode-count mismatch detected", bad2["ok"] is False)

    # MAC / normalization
    u = fr[1]["u"]
    nu = normalize(u)
    pin("normalize -> unit L2", abs(norm_l2(nu) - 1.0) < 1e-12)
    pin("MAC(self,self) = 1", abs(mac(u, u) - 1.0) < 1e-12)
    pin("MAC(orthogonal) = 0", abs(mac([[1, 0, 0]], [[0, 1, 0]])) < 1e-12)
    pin("MAC(self, 2*self) = 1 (scale invariant)",
        abs(mac(u, [[2 * x for x in row] for row in u]) - 1.0) < 1e-12)
    pin("MAC zero vector = 0", mac([[0, 0, 0]], [[1, 0, 0]]) == 0.0)

    # empty / malformed
    pin("no frames in empty text", parse_frames("".splitlines()) == [])
    pin("malformed 100CL ignored",
        parse_frames(["   1PSTEP  1 1 1", "  100CL  xx 1 4", " -3"]) == [])
    # Recurrence pins from REAL-MACHINE lines (4-space 1PSTEP / 2-space 100CL)
    pin("real 1PSTEP line recognized", _tag(_REAL_PSTEP_LINE) == "1PSTEP")
    real_cl = _parse_cl(_REAL_CL_LINE)
    pin("real 100CL line parsed", real_cl == (102, 3.513125628, 213270))
    pin("real lines produce a frame",
        len(parse_frames([_REAL_PSTEP_LINE, _REAL_CL_LINE, " -3"])) == 1)
    pin("3-space legacy prefix ALSO recognized (indent-insensitive)",
        len(parse_frames(["   1PSTEP  1 1 1",
                          "  100CL  102 3.513125628      4   4  2  1", " -3"])) == 1)

    n_ok = sum(1 for _, ok in pins if ok)
    for name, ok in pins:
        print(f"  [{'ok' if ok else 'FAIL'}] {name}")
    print(f"self-test: {n_ok}/{len(pins)} pins")
    return 0 if n_ok == len(pins) else 1


def load_dat_from_text(txt: str) -> list[float]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from extract_buckle_dat import parse_ccx_text
    return [r["lambda"] for r in parse_ccx_text(txt)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("frd", nargs="?", help="CalculiX .frd file")
    ap.add_argument("--dat", help="companion .dat for lambda alignment")
    ap.add_argument("--modes", type=int, default=3, help="how many modes to emit")
    ap.add_argument("--json", dest="out", help="output artifact path")
    ap.add_argument("--full-npz", help="optional: write full float32 mode shapes to a .npz")
    ap.add_argument("--compact", action="store_true",
                    help="summary only (no node_ids / u arrays in the JSON)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.frd:
        print("need a .frd path (or --self-test)", file=sys.stderr)
        return 2

    p = Path(a.frd)
    # Pass 1: cheap header scan -> align ALL modes against the .dat table.
    headers = scan_frame_headers(p)
    dat_lambdas = load_dat(a.dat) if a.dat else []
    if dat_lambdas:
        alignment = align(
            [{"lambda": h["lambda"], "nodes": [], "u": []} for h in headers],
            dat_lambdas)
    else:
        alignment = {"ok": None, "reason": "no --dat"}
    # Pass 2: keep only frame 1 (static) + first N mode shapes in memory.
    frames = parse_file(p, max_frames=a.modes + 1)
    if not frames:
        print("no frames parsed", file=sys.stderr)
        return 1

    modes = [f for f in frames if f["lambda"] > 0.0][:a.modes]
    out = {
        "what": "C6-P2 P0-3: ccx *BUCKLE mode shapes parsed from .frd",
        "source_frd": str(p).replace("\\", "/"),
        "source_frd_sha256": hashlib.sha256(p.read_bytes()).hexdigest() if p.stat().st_size < 200 * 1024 * 1024 else None,
        "source_dat": str(a.dat).replace("\\", "/") if a.dat else None,
        "n_frames_all": len(headers),
        "n_static_frames_all": sum(1 for h in headers if h["lambda"] == 0.0),
        "n_mode_frames_all": sum(1 for h in headers if h["lambda"] > 0.0),
        "n_frames_kept_in_memory": len(frames),
        "lambda_all_modes_frd": [h["lambda"] for h in headers if h["lambda"] > 0.0],
        "lambda_alignment": alignment,
        "note": "frame 1 (lambda=0) is the static reference field, NOT a mode; "
                "100CL gives 9 s.f. lambda vs 7 s.f. in .dat. "
                "Node ids come from the deck and are shared by both codes (E6 parity).",
        "modes": [],
    }
    for i, f in enumerate(modes, 1):
        u = f["u"]
        nu = normalize(u)
        rec = {
            "mode": i,
            "lambda_frd_full_precision": f["lambda"],
            "lambda_dat": dat_lambdas[i - 1] if i - 1 < len(dat_lambdas) else None,
            "n_nodes": len(f["nodes"]),
            "node_ids_sha256": hashlib.sha256(
                (",".join(map(str, f["nodes"]))).encode()).hexdigest(),
            "l2_norm_raw": norm_l2(u),
            "max_abs_component": max(abs(x) for row in u for x in row),
            "u_normalized_sha256": hashlib.sha256(
                json.dumps(nu, separators=(",", ":")).encode()).hexdigest(),
            "sample_first_3_nodes": [{"node": n, "u": list(row)}
                                     for n, row in zip(f["nodes"][:3], nu[:3])],
        }
        if not a.compact:
            rec["u_normalized"] = nu
            rec["node_ids"] = f["nodes"]
        out["modes"].append(rec)
    if a.full_npz:
        import numpy as np
        npz = Path(a.full_npz)
        npz.parent.mkdir(parents=True, exist_ok=True)
        arrays = {}
        for i, f in enumerate(modes, 1):
            nu = normalize(f["u"])
            arrays[f"node_ids_m{i}"] = np.asarray(f["nodes"], dtype=np.int64)
            arrays[f"u_m{i}"] = np.asarray(nu, dtype=np.float32)
        np.savez_compressed(npz, **arrays)
        out["full_npz"] = str(npz).replace("\\", "/")
        out["full_npz_sha256"] = hashlib.sha256(npz.read_bytes()).hexdigest()
        out["full_npz_bytes"] = npz.stat().st_size
    if a.out:
        dest = Path(a.out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {dest} ({dest.stat().st_size} bytes)")
    print(json.dumps({k: v for k, v in out.items() if k != "modes"},
                     ensure_ascii=False, indent=1))
    for m in out["modes"]:
        print(f"  mode {m['mode']}: lambda={m['lambda_frd_full_precision']} "
              f"nodes={m['n_nodes']} L2={m['l2_norm_raw']:.4g}")
    return 0 if (alignment.get("ok") is not False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
