#!/usr/bin/env python
"""Snapshot / diff file hashes under a tree - the "prove no silent drift" tool.

Why this exists
---------------
The dataset is re-exported from time to time (a new case joins, a spec field is
added, a builder changes).  Each time, the question that has to be answered is
*precise*: did anything happen besides the change I intended?  Reading a diff of
file names answers "did a case appear"; it does not answer "did an already
published case quietly change bytes", and the second is the one that invalidates
other people's work.

The project has been bitten by exactly that: adding a field to the spec
invalidated every ``spec_sha256`` in the archive, which was correct but had to be
*known* rather than discovered.  So the rule is: snapshot before, diff after, and
expect every difference to fall into a bucket you predicted.

Usage::

    python diagnostics/hash_manifest.py write FEM-Bench-Aero/snap_before.json
    python diagnostics/hash_manifest.py diff  FEM-Bench-Aero/snap_before.json

``diff`` groups the result into added / removed / changed and exits non-zero if
anything changed, so it can be used as a gate rather than read by eye.

The two questions this tool gets asked are different, so ``--gate`` picks which
one is fatal:

``--gate any`` (default)
    Nothing at all may differ.  Use right after a refactor that is supposed to be
    byte-for-byte neutral.

``--gate changed``
    Additions are expected (a new case just joined), removals are expected (a
    duplicate was retired), but **no surviving file may change**.  This is the
    one that answers "did the new structure family disturb the archive?" - and
    the answer has to be no for the *case files*.  Combine with ``--only`` to
    put the regenerated reports (which always change) out of scope::

        python diagnostics/hash_manifest.py diff snap.json FEM-Bench-Aero \\
               --only modeling --only _xval --gate changed

    The by-directory breakdown makes the same reading possible by eye.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def manifest(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = hashlib.sha256(
                p.read_bytes()).hexdigest()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)

    w = sub.add_parser("write")
    w.add_argument("manifest")
    w.add_argument("root", nargs="?", default=".")

    d = sub.add_parser("diff")
    d.add_argument("manifest")
    d.add_argument("root", nargs="?", default=".")
    d.add_argument("--quiet", action="store_true",
                   help="only print the summary counts")
    d.add_argument("--gate", choices=("any", "changed"), default="any",
                   help="'any' (default) fails on added/removed/changed; "
                        "'changed' fails only if a surviving file changed")
    d.add_argument("--only", action="append", metavar="PREFIX", default=None,
                   help="restrict the comparison to paths under this prefix "
                        "(repeatable); applied to both snapshots, so a file "
                        "that leaves the scope is not reported as removed")
    args = ap.parse_args(argv)

    root = Path(args.root)
    now = manifest(root)

    if args.mode == "write":
        Path(args.manifest).write_text(json.dumps(now, indent=1), encoding="utf-8")
        print(f"snapshot: {len(now)} files -> {args.manifest}")
        by_top: dict[str, int] = {}
        for k in now:
            by_top[k.split("/")[0]] = by_top.get(k.split("/")[0], 0) + 1
        print(f"          by top-level dir: {by_top}")
        return 0

    before = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    if args.only:
        def keep(d):
            return {k: v for k, v in d.items()
                    if any(k == p or k.startswith(p.rstrip("/") + "/")
                           for p in args.only)}
        before, now = keep(before), keep(now)

    added = sorted(set(now) - set(before))
    removed = sorted(set(before) - set(now))
    changed = sorted(k for k in set(before) & set(now) if before[k] != now[k])

    if not args.quiet:
        for tag, keys in (("ADDED  ", added), ("REMOVED", removed),
                          ("CHANGED", changed)):
            for k in keys:
                print(f"  {tag} {k}")
    print(f"{len(added)} added, {len(removed)} removed, {len(changed)} changed "
          f"({len(before)} -> {len(now)} files)")

    def by_dir(keys):
        buckets: dict[str, int] = {}
        for k in keys:
            top = k.split("/")[0] if "/" in k else "(tree root)"
            buckets[top] = buckets.get(top, 0) + 1
        return ", ".join(f"{d} {n}" for d, n in sorted(buckets.items()))

    if added:
        print(f"  added, by directory:   {by_dir(added)}")
    if removed:
        print(f"  removed, by directory: {by_dir(removed)}")
    if changed:
        # Two groupings, because the two questions are different: by directory
        # answers "did any *case* move?" (case files live under modeling/ and
        # _xval/), by file name answers "what kind of file was it?".
        print(f"  changed, by directory: {by_dir(changed)}")
        buckets: dict[str, int] = {}
        for k in changed:
            buckets[Path(k).name] = buckets.get(Path(k).name, 0) + 1
        print("  changed, by file name: "
              + ", ".join(f"{n}x {k}" for k, n in sorted(buckets.items())))

    if args.gate == "changed":
        return 1 if changed else 0
    return 1 if (added or removed or changed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
