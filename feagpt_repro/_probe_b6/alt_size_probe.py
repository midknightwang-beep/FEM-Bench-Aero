#!/usr/bin/env python
"""Measure the **mesh cost** of candidate T3 size points, without solving.

Why this exists
---------------
Batch 6's four T3 size cases were picked by 老王 as ``D1600 / L3000 / t2.0 /
D1600+L3000``.  Two of them (``L3000`` and ``D1600+L3000``) **cannot be solved
by CalculiX on this machine**: since CalculiX expands every shell into solids
before the factorisation, the equation count is ``~14.93 x shell nodes``, and the
PaStiX factorisation of the resulting 2.8M / 3.5M DOF system exhausts the
machine's commit limit (measured: 16.49 GB RAM + 16.87 GB swap, and a forked
``ls`` dying with ``0xC000012D`` = ``STATUS_COMMITMENT_LIMIT``).

So before proposing an alternative set of size points, measure what each one
costs.  This script builds the mesh only (``run_pipeline.py --mesh-only``) - no
solver, no licence, ~50 s per point - and prints the node count, which is the
single driver of the equation count.

Measured scaling used to read the table (three points agree to 3 significant
figures)::

    equations ~ 14.93 x shell nodes          (PastiX "number of equations")
    nodes     ~ shell area / 85.2 mm^2       (11.7 nodes per 1000 mm^2)

Usage::

    python _probe_b6/alt_size_probe.py            # build all points
    python _probe_b6/alt_size_probe.py --dry-run  # list them only
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPRO = HERE.parent
sys.path.insert(0, str(REPRO))

from feagpt import fuselage, manifest as M  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402

PYEXE = sys.executable
SPEC_DIR = HERE / "_alt_specs"
OUT_DIR = "_probe_b6/alt_out"

#: ``(params, label)``.  "shrink" = affordable by construction (smaller shell
#: area than the 13.52e6 mm^2 anchor); "grow" = probes how far the machine can
#: still go before the commit limit bites.
POINTS: tuple[tuple[dict, str], ...] = (
    ({"length": 1600.0}, "shrink: length down, the affordable analogue of L3000"),
    ({"diameter": 1600.0, "length": 1600.0}, "shrink: two-dimension corner, both down"),
    ({"length": 2400.0}, "grow: +20 % length - how much head-room is left?"),
    ({"diameter": 2200.0}, "grow: +10 % diameter - how much head-room is left?"),
)

NODES = re.compile(r"mesh\s*:\s*(\d+)\s*nodes")
AREA = re.compile(r"mid-surface area\s*([\d,]+)\s*mm\^2")


def name_for(params: dict) -> str:
    d = params.get("diameter", fuselage.FuselageParams.diameter)
    L = params.get("length", fuselage.FuselageParams.length)
    t = params.get("thickness", fuselage.FuselageParams.thickness)
    n = params.get("n_stringers", fuselage.FuselageParams.n_stringers)
    nf = params.get("n_frames", fuselage.FuselageParams.n_frames)
    parts = [f"d{d:g}", f"l{L:g}"]
    if t != fuselage.FuselageParams.thickness:
        parts.append(f"t{t:g}")
    parts += [f"str{n}", f"frm{nf}"]
    return "fuselage_barrel_" + "_".join(parts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--solver", default="--", help="unused; mesh-only run")
    args = ap.parse_args(argv)

    SPEC_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    print(f"{'case':38s} {'split':6s} {'area(mm2)':>12s} {'nodes':>8s} "
          f"{'eq(est)':>9s}  verdict")
    for params, label in POINTS:
        name = name_for(params)
        spec = fuselage.make_spec(name, workdir=OUT_DIR, **params)
        spec.description = f"T3 尺寸候选（cost probe）：{label}"
        spec_path = SPEC_DIR / f"{name}.spec.json"
        spec.to_json(spec_path)

        side, why = M.split_of(FEASpec.from_json(spec_path))

        if args.dry_run:
            print(f"  {name:36s} {side:6s} {'-':>12s} {'-':>8s} {'-':>9s}  {label}")
            continue

        r = subprocess.run(
            [PYEXE, str(REPRO / "run_pipeline.py"), "--spec", str(spec_path),
             "--out", OUT_DIR, "--mesh-only"],
            cwd=str(REPRO), capture_output=True, text=True,
        )
        txt = r.stdout
        m_n = NODES.search(txt)
        m_a = AREA.search(txt)
        nodes = int(m_n.group(1)) if m_n else None
        area = int(m_a.group(1).replace(",", "")) if m_a else None
        eq = round(14.93 * nodes) if nodes else None
        # The wall measured on this machine sits between the largest solve that
        # worked (158 548 nodes -> 2.37M eq) and the smallest that did not
        # (188 674 nodes -> 2.82M eq).
        verdict = ("?" if nodes is None else
                   "ok (<=158.5k measured ok)" if nodes <= 158548 else
                   "RISK (between the two measured walls)" if nodes <= 188674 else
                   "NO (measured no-go)")
        print(f"{'  ' if side else '!!'}{name:36s} {side:6s} "
              f"{(f'{area:,}' if area else '-'):>12s} "
              f"{(f'{nodes:,}' if nodes else '-'):>8s} "
              f"{(f'{eq:,}' if eq else '-'):>9s}  {verdict}")
        rows.append({"case": name, "params": params, "split": side, "why": why,
                     "label": label, "shell_area_mm2": area,
                     "n_nodes": nodes, "equations_est": eq, "rc": r.returncode})
        if not nodes:
            print(f"      (rc={r.returncode}) tail:\n{txt[-700:]}")

    out = HERE / "_alt_size_probe.json"
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
