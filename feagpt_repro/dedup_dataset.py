#!/usr/bin/env python
"""Prune duplicate *models* from an exported case set.

Two cases in one tree describing the same model - same ``model.msh`` **and** same
declared shell thicknesses - are one model, not two.  That is not a modelling
error - it is a split hazard: a naive random
split can put the two copies on opposite sides of train/validation, which
leaks the answer.  ``verify_dataset.py`` reports such groups; this tool removes
them.

Scope, deliberately narrow
--------------------------
**D25 (2026-10-06)** widened the fingerprint from ``model.msh`` alone to
``model.msh`` + the ``*SHELL SECTION`` thickness table (see
:func:`verify_dataset.model_sha256`).  The mesh alone was tried and is provably
too coarse: the T3 pilot's ``D2000`` barrels at ``t=3`` and ``t=2`` ship
**byte-identical** meshes, so the old rule would have deleted a legitimate design
variable as a "duplicate".  Two specs that *look* different but build the same
model (``chord: 1000`` vs ``1000.0``) are still caught, and two specs that differ
in a way that changes the mesh **or** the wall thickness are kept.

Only **inside** a tree.  A mesh shared between ``modeling/`` and ``_xval/`` is
gate 3's premise (one model, two solvers), not a duplicate.

Nothing is deleted by default.  Run without ``--apply`` to see the plan; the
redundant case directories are removed only with ``--apply``, and the survivor
is printed either way.

Usage::

    # show what would go
    python dedup_dataset.py --root ../FEM-Bench-Aero

    # pin the survivor of a group, then apply
    python dedup_dataset.py --root ../FEM-Bench-Aero \
        --keep naca4412_wingbox --apply
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_dataset import TREES, find_duplicates, model_sha256  # noqa: E402

DEFAULT_KEEP = None

#: Keys the run itself produces.  Anything else found in an existing report is
#: provenance and is carried over verbatim (see the ``--json`` write path).
_OWNED_KEYS = {"root", "apply", "trees", "removed", "n_groups", "n_removed"}


def _model_fingerprint(case_dir: Path) -> str | None:
    """Mesh + shell thickness; delegates so the two tools cannot diverge."""
    return model_sha256(case_dir)


def scan(root: Path) -> dict[str, list[dict]]:
    """Per tree, the duplicate groups with a proposed survivor for each."""
    out: dict[str, list[dict]] = {}
    for tree in TREES:
        base = root / tree
        if not base.is_dir():
            continue
        rows = []
        for case in sorted(d for d in base.iterdir() if d.is_dir()):
            sha = _model_fingerprint(case)
            if sha:
                rows.append({"case": case.name, "sha": sha})
        groups = []
        by_sha: dict[str, list[str]] = defaultdict(list)
        for r in rows:
            by_sha[r["sha"]].append(r["case"])
        for sha, cases in sorted(by_sha.items()):
            if len(cases) > 1:
                groups.append({"sha256": sha, "cases": sorted(cases)})
        out[tree] = groups
    return out


def choose_survivor(cases: list[str], pins: list[str]) -> str:
    """Pinned name if it is in the group, else the sorted-first case.

    Sorted-first is only a tie-break; the point of ``--keep`` is that the choice
    of survivor is a dataset-design decision, so it can always be forced.
    """
    for p in pins:
        if p in cases:
            return p
    return sorted(cases)[0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="dataset root (holds modeling/ and _xval/)")
    ap.add_argument("--keep", nargs="*", default=[],
                    help="case name(s) that must survive if in a duplicate group")
    ap.add_argument("--apply", action="store_true",
                    help="actually delete the redundant case directories")
    ap.add_argument("--json",
                    help="write the plan/report here; an existing file's "
                         "'history' is preserved and appended to")
    ap.add_argument("--note", default="",
                    help="free-text label recorded with this run's history entry")
    args = ap.parse_args(argv)

    root = Path(args.root)
    groups = scan(root)
    report = {"root": str(root), "apply": bool(args.apply), "trees": {}, "removed": []}

    n_groups = 0
    for tree, gs in groups.items():
        report["trees"][tree] = []
        for g in gs:
            n_groups += 1
            keep = choose_survivor(g["cases"], args.keep)
            drop = [c for c in g["cases"] if c != keep]
            entry = {"sha256": g["sha256"], "cases": g["cases"],
                     "keep": keep, "drop": drop}
            report["trees"][tree].append(entry)
            print(f"[{tree}] same model {g['sha256'][:12]}: {', '.join(g['cases'])}")
            print(f"        keep: {keep}")
            for c in drop:
                target = root / tree / c
                if args.apply:
                    shutil.rmtree(target)
                    report["removed"].append(f"{tree}/{c}")
                    print(f"        removed: {tree}/{c}")
                else:
                    print(f"        would remove: {tree}/{c}   (rerun with --apply)")

    if n_groups == 0:
        print("no duplicate models found - nothing to do")

    report["n_groups"] = n_groups
    report["n_removed"] = len(report["removed"])
    print(f"\nduplicate groups: {n_groups}; "
          f"{'removed' if args.apply else 'would remove'}: {len(report['removed'])} case dir(s)")

    if args.json:
        # **Append, do not overwrite.**  A dedup report is provenance: "which
        # case was dropped, and which one was kept in its place".  Overwriting it
        # with the next run's snapshot destroys exactly the record a reader is
        # looking for once the duplicates are gone - and the next run *always*
        # finds nothing, because the previous run already did the work.  That is
        # not hypothetical: regenerating this file to refresh its counts silently
        # erased the M2 removal record, which then had to be reconstructed by
        # hand.  So the run's own result stays at the top level (so older readers
        # keep working) and every run that actually removed something also
        # appends to ``history``.
        path = Path(args.json)
        if path.exists():
            try:
                old = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                old = {}
            # Carry over everything this run does not itself produce: the
            # history log, and any hand-written provenance (which duplicate
            # group was resolved, why, which local rule pinned the survivor).
            # Only the keys that *are* this run's output get replaced.
            for k, v in old.items():
                if k not in _OWNED_KEYS:
                    report.setdefault(k, v)
        if report["removed"]:
            report.setdefault("history", []).append({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "note": args.note or "",
                "removed": list(report["removed"]),
                "keep": {t: sorted({e["keep"] for e in es})
                         for t, es in report["trees"].items() if es},
                "n_groups": n_groups,
            })
        report.setdefault("history", [])
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        print(f"report -> {args.json} "
              f"({len(report['removed'])} removed this run, "
              f"{len(report['history'])} event(s) on record)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
