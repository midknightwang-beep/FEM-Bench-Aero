#!/usr/bin/env python
"""Re-check gate 4 (semantic topology) over an exported case set.

Reads each ``truth.json`` and re-runs the comparison from the stored *readings*.
The expectation is **re-derived** rather than taken from the stored verdict, so
a hand-edited truth cannot pass by assertion - which is the whole point of
keeping the two readings apart in the first place.

This is also the tool M2 leans on: its regression criterion ("nine seeds,
group-for-group identical") is exactly a gate-4 re-run over the new pipeline.

Usage::

    python check_semantics.py --root ../FEM-Bench-Aero
    python check_semantics.py --root ../FEM-Bench-Aero --json gate4.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feagpt import topology  # noqa: E402


def iter_truth(root: Path) -> list[Path]:
    files = sorted(root.glob("*/truth.json"))
    if not files:                       # allow pointing at modeling/ directly
        files = sorted(root.glob("*/*/truth.json"))
    return files


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="dataset root (or a tree inside it)")
    ap.add_argument("--json", help="also write a machine-readable report here")
    ap.add_argument("--quiet", action="store_true", help="summary only")
    args = ap.parse_args(argv)

    files = iter_truth(Path(args.root))
    if not files:
        print(f"no truth.json found under {args.root}")
        return 1

    report: list[dict] = []
    npass = 0
    for tp in files:
        doc = json.loads(tp.read_text(encoding="utf-8"))
        topo = doc.get("topology")
        if not topo:
            report.append({"case": tp.parent.name, "pass": False,
                           "error": "no topology block"})
            continue
        gate = topology.compare(topo)
        npass += bool(gate["pass"])
        row = {
            "case": doc.get("case_id", tp.parent.name),
            "solver": doc.get("solver"),
            "pass": gate["pass"],
            "checks": gate["checks"],
        }
        report.append(row)
        if not args.quiet:
            flag = "PASS" if gate["pass"] else "FAIL"
            n_ok = sum(c["pass"] for c in gate["checks"])
            print(f"  [{flag}] {row['case']:46s} {str(row['solver'] or '-'):6s} "
                  f"{n_ok}/{len(gate['checks'])}")
            for c in gate["checks"]:
                if not c["pass"]:
                    print(f"          {c['key']}: want {c['expected']} "
                          f"got {c['actual']}")

    print(f"\ngate4 semantic: {npass}/{len(files)} PASS")
    if args.json:
        Path(args.json).write_text(
            json.dumps({"n_cases": len(files), "n_pass": npass, "cases": report},
                       indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"report -> {args.json}")
    return 0 if npass == len(files) else 2


if __name__ == "__main__":
    raise SystemExit(main())
