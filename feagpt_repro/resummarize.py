#!/usr/bin/env python
"""Re-derive ``<case>.results.json`` from the result source already on disk.

Why this exists
---------------
A change to the *reduction* is not a change to the *solve*, and the two must not
be conflated - one costs seconds, the other costs a solver licence.

Two changes landed on 2026-10-03 and they are different in kind:

* **D8** moved the headline von Mises from the mid-surface to the outer fibre and
  added ``max_von_mises_midsurface`` beside it.  The wing box's Abaqus deck and
  mesh were untouched, so its ODB is still exactly the ODB the new reduction
  needs - re-solving would spend licence time to reproduce it byte for byte.
* **D9** changed the panel mesh, which does require a solve.

So the Abaqus wing boxes are re-summarised here rather than re-solved.

Usage::

    python resummarize.py --roots outputs_abaqus outputs_str_abaqus outputs_T_abaqus
    python resummarize.py --roots outputs --only naca4412_wingbox
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feagpt import post  # noqa: E402


def find_cases(roots) -> list[tuple[Path, Path, str]]:
    out: list[tuple[Path, Path, str]] = []
    for r in roots:
        for spec_path in sorted(Path(r).glob("*/*.spec.json")):
            if spec_path.parent.name.startswith("_"):
                continue
            name = spec_path.name[: -len(".spec.json")]
            if name != spec_path.parent.name:
                continue
            out.append((spec_path.parent, spec_path, name))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roots", nargs="+", required=True)
    ap.add_argument("--only", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    cases = find_cases(args.roots)
    if args.only:
        cases = [c for c in cases if c[2] in set(args.only)]
    print(f"{len(cases)} case(s) to re-summarise")
    if not cases:
        return 1

    n_ok = 0
    for case_dir, _spec_path, name in cases:
        if args.dry_run:
            print(f"  [dry] {name}")
            continue
        frd = case_dir / f"{name}.frd"
        odbj = case_dir / f"{name}.odb.json"
        src = frd if frd.exists() else (odbj if odbj.exists() else None)
        if src is None:
            print(f"  [SKIP] {name:46s} no .frd or .odb.json")
            continue
        data = post.load_any(src)
        summary = post.dump_results_data(
            data,
            case_dir / f"{name}.results.json",
            case_dir / f"{name}.nodes.csv",
        )
        n_ok += 1
        mu = summary.get("max_disp")
        print(f"  [OK ] {name:46s} src={src.name:12s} "
              f"|u|={mu if mu is None else round(mu, 5)}  "
              f"vM_out={summary.get('max_von_mises', float('nan')):.4f}  "
              f"vM_mid={summary.get('max_von_mises_midsurface', float('nan')):.4f}  "
              f"[{summary.get('max_von_mises_definition')}]")
    print(f"  -> {n_ok}/{len(cases)} re-summarised")
    return 0 if n_ok == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
