"""M14 -- wing-box h-convergence: how much of the 2.63 % is discretisation?

Why this exists
---------------
The other three families all have an independent yardstick:
  * stiffened panel  -> Navier closed form, and a measured 12/6/3 mm ladder
                        (-6.9 % / -0.63 % / -0.10 %);
  * open-hole panel  -> Kirsch / Howland Kt + a hole-edge mesh ladder;
  * barrel           -> thin-wall w = pR^2/(Et), -0.329 %.
The **wing box has none** -- it carries the primary target (`max_disp`), 34 of
55 cases, and every one of them is meshed at size_chord=12 / size_span=25.  The
cross-solver gate proves ccx and abaqus agree *on that mesh*; it says nothing
about the mesh being fine enough.  So "2.63 % MAPE" currently means "2.63 %
against a 12/25 mm ccx solution", not "against the continuous solution".

This probe refines the baseline wing box only (the cheap, well-behaved case),
3 levels, and reports the observed convergence order.  It does not re-solve the
dataset -- it prices the unknown.

Run:  python _probe_m14/h_convergence.py [--levels 12,8,6]
Out:  _probe_m14/h_convergence.json  +  _probe_m14/outputs/<case>/
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

REPRO = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
DATASET = REPRO.parent / "FEM-Bench-Aero"
PY = sys.executable


def make_spec(size_chord: float, size_span: float) -> Path:
    src = json.load(open(DATASET / "modeling" / "naca4412_wingbox" / "spec.json",
                         encoding="utf-8"))
    tag = f"h{size_chord:g}x{size_span:g}".replace(".", "p")
    src["name"] = f"naca4412_wingbox_{tag}"
    src["description"] = (f"h-refinement probe of the baseline wing box at "
                          f"size_chord={size_chord} / size_span={size_span}")
    src["mesh"]["size_chord"] = size_chord
    src["mesh"]["size_span"] = size_span
    out = HERE / f"{src['name']}.spec.json"
    out.write_text(json.dumps(src, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def solve(spec: Path) -> Path:
    """Run one ccx solve.  Sequential by construction -- never run two solvers."""
    out = HERE / "outputs"
    cmd = [PY, str(REPRO / "run_pipeline.py"), "--spec", str(spec),
           "--out", str(out), "--solver", "ccx"]
    print("  $", " ".join(cmd[1:]), flush=True)
    r = subprocess.run(cmd, cwd=REPRO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    tail = (r.stdout or "")[-600:] + (r.stderr or "")[-600:]
    (HERE / f"_solve_{spec.stem}.log").write_text(tail, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit(f"solve failed rc={r.returncode}\n{tail}")
    case = spec.stem.replace(".spec", "")
    t = out / case / f"{case}.truth.json"
    if not t.exists():
        raise SystemExit(f"no truth.json at {t}\n{tail}")
    return t


def main() -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", default="12,8,6",
                    help="comma separated size_chord (= size_span / ~2)")
    a = ap.parse_args()
    levels = [float(x) for x in a.levels.split(",")]

    rows = []
    for sc in levels:
        ss = round(sc * 2.0, 6)
        spec = make_spec(sc, ss)
        print(f"[level] size_chord={sc} size_span={ss}", flush=True)
        t = solve(spec)
        d = json.load(open(t, encoding="utf-8"))
        s = d["scalars"]
        rows.append({
            "size_chord": sc, "size_span": ss,
            "case_id": d["case_id"],
            "n_nodes": s["n_nodes"],
            "max_disp": s["max_disp"],
            "max_w": s["max_w"],
            "max_vm_mid": s["max_von_mises_midsurface"],
            "max_vm_out": s["max_von_mises"],
            "max_disp_node": s["max_disp_node"],
            "max_vm_node": s["max_vm_location"],
        })

    # Richardson-style estimate: fit u = u_inf + C * h^p on the last three levels.
    # With three points and two unknowns (u_inf, C) per fixed p, we report the
    # observed order by scanning p, plus the two-level difference which is the
    # honest "how much would another refinement move the answer" number.
    rows.sort(key=lambda r: -r["size_chord"])  # coarse -> fine
    out = {"levels": rows, "metric": "max_disp"}
    if len(rows) >= 2:
        diffs = []
        for a_, b_ in zip(rows, rows[1:]):
            diffs.append({
                "from": a_["size_chord"], "to": b_["size_chord"],
                "rel_change_pct": (b_["max_disp"] - a_["max_disp"]) / a_["max_disp"] * 100.0,
                "n_nodes_ratio": b_["n_nodes"] / a_["n_nodes"],
            })
        out["successive_changes"] = diffs
    if len(rows) >= 3:
        # observed order p from the two successive differences
        (r1, r2, r3) = rows[0], rows[1], rows[2]
        e12 = r2["max_disp"] - r1["max_disp"]
        e23 = r3["max_disp"] - r2["max_disp"]
        ratio = abs(e12 / e23) if e23 else float("nan")
        h12 = r1["size_chord"] / r2["size_chord"]
        out["observed_order"] = {
            "e_coarse_mid": e12, "e_mid_fine": e23,
            "error_ratio": ratio,
            "h_ratio": h12,
            "p_est": math.log(ratio) / math.log(h12) if ratio > 0 else float("nan"),
        }
        # monotone? a converged quantity must move monotonically toward a limit
        out["monotone"] = (e12 * e23) > 0
        # extrapolated limit via the last two points assuming the observed order
        p = out["observed_order"]["p_est"]
        if p == p and p > 0.1:
            h2, h3 = r2["size_chord"], r3["size_chord"]
            try:
                u_inf = r3["max_disp"] + (r3["max_disp"] - r2["max_disp"]) / (
                    (h2 / h3) ** p - 1.0)
                out["richardson_limit"] = {
                    "u_inf": u_inf,
                    "baseline_12mm_error_pct": (r1["max_disp"] - u_inf) / u_inf * 100.0,
                    "finest_error_pct": (r3["max_disp"] - u_inf) / u_inf * 100.0,
                }
            except ZeroDivisionError:
                pass
    (HERE / "h_convergence.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = main()
    print("\n=== levels ===")
    for l in r["levels"]:
        print(f"  h={l['size_chord']:<5} nodes={l['n_nodes']:<7} "
              f"max_disp={l['max_disp']:.8f}  max_w={l['max_w']:.6f}  "
              f"vM_mid={l['max_vm_mid']:.4f}")
    print("\n=== successive ===")
    for d in r.get("successive_changes", []):
        print(f"  {d['from']}->{d['to']}: {d['rel_change_pct']:+.4f} %  "
              f"(nodes x{d['n_nodes_ratio']:.2f})")
    print("\n=== order ===", json.dumps(r.get("observed_order", {}), ensure_ascii=False))
    print("monotone:", r.get("monotone"))
    print("richardson:", json.dumps(r.get("richardson_limit", {}), ensure_ascii=False))
    print("written -> _probe_m14/h_convergence.json")
