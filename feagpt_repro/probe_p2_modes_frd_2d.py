"""Re-run the C6-P2 ccx three-tier buckle jobs with OUTPUT=2D node output.

WHY (2026-11-08, node-mapping probe): the first frd batch was written by a
bare ``*NODE FILE``, which makes ccx 2.23 emit the EXPANDED 3D shell -- every
mid-surface node split into +/- t/2 surface nodes (skin t=3 -> r=800+/-1.5,
stringers t=2.5 -> +/-1.25) and fully renumbered: 103715 deck nodes became
213270 frd nodes (25..103739 -> 103740..446884, ZERO overlap with the Abaqus
ODB).  Two-code MAC (U10/U14) needs mid-surface shapes under the deck's own
labels, hence OUTPUT=2D.  Woonzee picked route A (re-solve) over the
collapse_expanded_shell route: the expanded-point count 109555 is ODD, so
some deck nodes expand into a group whose size != 2 (skin/stringer shared
nodes are the prime suspect) and the (top+bottom)/2 fold-back semantics
would be contaminated exactly there.

WHAT IS VERIFIED INLINE (fail-closed, no post-hoc):
  1. deck contains "*NODE FILE, OUTPUT=2D" and NO bare "*NODE FILE"
     (old template must not leak back);
  2. new .dat lambdas equal the archived 2026-11-08 lambdas per tier
     (output requests must not move eigenvalues; rel < 1e-9);
  3. the new .frd node id set EQUALS the deck *NODE id set (103715 nodes,
     exact set match -- the whole point of this re-run);
  4. the frd frame structure is unchanged (first frame lambda=0 static
     baseline + 6 eigenmode frames).

Serial solves (R61, solver lock).  Old _p2_scaling_ccx/ is left untouched
(archive-not-delete).  Outputs: _p2_scaling_ccx_2d/ and
reports/diagnostics/p2_scaling_ccx_2d/.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from feagpt.spec import FEASpec          # noqa: E402
from feagpt import pipeline, solver      # noqa: E402
from extract_buckle_dat import extract   # noqa: E402

_V11 = _HERE.parent / "FEM-Bench-Aero" / "modeling"
_JOBS = _HERE / "_p2_scaling_ccx_2d"
_ARCH = _HERE / "reports/diagnostics/p2_scaling_ccx_2d"
_OUT = _HERE / "reports/diagnostics/p2_modes_frd_2d_2026-11-08.json"
_PREV = _HERE / "reports/diagnostics/p2_load_scaling_ccx_2026-11-08.json"
BASE = "fuselage_barrel_d1600_l1600_str8_frm3"
P_REFS = [0.1, 0.05, 0.02]
N_MODES = 6


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def frd_node_ids(path: Path) -> set[int]:
    ids = set()
    with path.open(encoding="utf-8", errors="replace") as fh:
        in_nodes = False
        for line in fh:
            if line.startswith(" -1") or line.startswith("-1"):
                in_nodes = True
                ids.add(int(line[3:13]))
            elif in_nodes and (line.startswith(" -3") or line.startswith("-3")):
                break
    return ids


def deck_node_ids(path: Path) -> set[int]:
    ids = set()
    in_n = False
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if s.startswith("*"):
                in_n = s.upper().startswith("*NODE") and "OUTPUT" not in s.upper()
                continue
            if in_n and "," in s:
                try:
                    ids.add(int(s.split(",")[0]))
                except ValueError:
                    pass
    return ids


def frd_frame_lambda_count(path: Path) -> int:
    """Number of 100CL result blocks in the frd (static baseline + modes)."""
    n = 0
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith(" 100CL") or line.startswith("100CL"):
                n += 1
    return n


def check_deck(deck: Path) -> None:
    txt = deck.read_text(encoding="utf-8", errors="replace")
    assert "*NODE FILE, OUTPUT=2D" in txt, f"{deck.name}: OUTPUT=2D missing"
    for i, ln in enumerate(txt.splitlines()):
        if ln.strip().upper().startswith("*NODE FILE") and "OUTPUT=" not in ln.upper():
            raise AssertionError(f"{deck.name}:{i + 1}: bare *NODE FILE leaked")


def main() -> int:
    _JOBS.mkdir(parents=True, exist_ok=True)
    _ARCH.mkdir(parents=True, exist_ok=True)
    prev = json.loads(_PREV.read_text(encoding="utf-8"))
    prev_lambda = {r["tag"]: r["lambdas"] for r in prev["rows"]}

    rows = []
    for pref in P_REFS:
        tag = f"p{int(round(pref * 1000)):03d}"
        name = f"{BASE}_buckle_{tag}"
        d = json.loads((_V11 / BASE / "spec.json").read_text(encoding="utf-8"))
        d["name"] = name
        d["analysis"]["step_type"] = "buckle"
        d["analysis"]["buckling"] = {
            "n_modes": N_MODES,
            "reference_load": {"kind": "pressure", "magnitude": pref,
                               "pressure_sign": -1.0},
        }
        spec = FEASpec.from_dict(d)
        outdir = _JOBS / name
        outdir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        res = pipeline.run(spec, outdir=outdir, step_export=False,
                           deck_only=True, solver_name="ccx")
        deck = Path(res.artifacts["inp"])
        check_deck(deck)                       # gate 1: output request line
        run = solver.run(deck, solver="ccx", timeout=2400)
        dat = outdir / f"{name}.dat"
        frd = outdir / f"{name}.frd"
        if dat.exists():
            shutil.copyfile(dat, _ARCH / f"{name}.dat")
        lambdas, err = [], None
        if dat.exists():
            try:
                lambdas = extract(str(dat), "ccx", expect=N_MODES)["lambdas"]
            except Exception as exc:           # noqa: BLE001
                err = f"{type(exc).__name__}: {exc}"
        # gate 2: eigenvalues must be untouched by the output-request change
        lam_match = lambdas == prev_lambda.get(tag)
        # gate 3: frd node ids == deck node ids (THE point of this re-run)
        frd_ids = frd_node_ids(frd) if frd.exists() else set()
        deck_ids = deck_node_ids(deck)
        ids_match = frd_ids == deck_ids and len(frd_ids) > 0
        # gate 4: frame structure (1 static baseline + 6 modes)
        n_blocks = frd_frame_lambda_count(frd) if frd.exists() else -1
        row = {
            "p_ref_mpa": pref, "tag": tag,
            "solve_rc": run.returncode, "solve_ok": bool(run.ok),
            "wall_seconds": round(time.time() - t0, 1),
            "deck_sha256": sha(deck), "dat_archived": str(_ARCH / f"{name}.dat")
            if dat.exists() else None,
            "lambdas": lambdas, "lambdas_match_prev": lam_match,
            "frd_n_nodes": len(frd_ids), "deck_n_nodes": len(deck_ids),
            "frd_ids_match_deck": ids_match,
            "frd_100CL_blocks": n_blocks,
            "parse_error": err,
        }
        ok = (row["solve_ok"] and lam_match and ids_match
              and n_blocks == N_MODES + 1 and not err)
        row["status"] = "ok" if ok else "fail"
        rows.append(row)
        print(f"[{tag}] rc={run.returncode} lam_match={lam_match} "
              f"frd_nodes={len(frd_ids)}/{len(deck_ids)} "
              f"blocks={n_blocks} wall={row['wall_seconds']}s -> {row['status']}",
              flush=True)

    out = {
        "what": "C6-P2 ccx re-solve with *NODE FILE, OUTPUT=2D (mid-surface, "
                "deck node labels) for two-code mode-shape MAC",
        "date": "2026-11-08",
        "decision": "woonzee route A (re-solve) over collapse_expanded_shell "
                    "fold-back: expanded-point count 109555 is odd -> shared "
                    "skin/stringer nodes expand into groups of size != 2",
        "status": "diagnostic evidence; lambdas must equal the archived "
                  "2026-11-08 batch",
        "case": BASE, "p_refs_mpa": P_REFS, "n_modes_requested": N_MODES,
        "rows": rows,
        "repro": ["python probe_p2_modes_frd_2d.py"],
    }
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    all_ok = all(r["status"] == "ok" for r in rows)
    print(f"wrote {_OUT}; all_ok={all_ok}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
