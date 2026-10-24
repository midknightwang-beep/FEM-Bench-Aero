#!/usr/bin/env python
"""Acceptance check for an exported FEM-Bench-Aero case set (M1).

Gate 4 asks "is the model built right?".  This asks the *other* question a
dataset must answer before it can ship: **is each case internally consistent** -
do the pieces in the directory describe one and the same model?

Eight per-case checks
---------------------
1. completeness   - the six canonical files are all present
2. spec<->truth   - ``truth.spec_sha256`` reproduces from ``spec.json``
                    (catches a spec edited after export)
3. scalars<->truth- ``truth.scalars`` equals ``model.results.json`` key-for-key
4. gate4 re-derive- re-run ``topology.compare`` from the stored readings and
                    confirm it matches the stored verdict (a hand-edited
                    ``semantic_gate`` cannot pass by assertion)
5. schema         - ``schema_version`` is one this tool understands
6. pairing        - every ``modeling/`` case has a matching ``_xval/`` case
7. stress defn    - ``max_von_mises`` declares an **outer-fibre** definition.
                    Added with D8: before it, the two trees stored different
                    quantities under that one key, so a consumer reading the
                    key by name got a number that meant something else.
8. no tri3        - the shipped deck contains no triangle elements.  Gate 1 has
                    said "min Jacobian >= 0.30 **and zero tri3**" since M1, but
                    only the Jacobian half was ever evaluated; on 2026-10-03
                    two wing boxes were found to ship 8 and 16 ``S3``.  It is
                    counted in ``model.inp``, not in ``model.msh``: the deck is
                    what both solvers read, and a text count needs no gmsh.

Checks 2, 4 and 8 are the ones with teeth: 2 and 4 recompute rather than trust,
so they fail on any hand edit; 8 reads the artifact that actually ships.  The
rest are cheap existence/identity guards.

Plus a set-level check
----------------------
``duplicates`` - cases describing the same **model**.  A dataset with
two copies of one model can split them across train and validation, which
leaks the answer.  The fingerprint is downstream of the geometry, so it catches
two specs that *look* different but build the same model - e.g. ``chord: 1000``
vs ``chord: 1000.0`` (int vs float, same shape).

**D25 (2026-10-06)** widened that fingerprint from ``model.msh`` alone to
``model.msh`` + the deck's ``*SHELL SECTION`` thickness table.  The mesh alone is
provably too coarse: a shell's wall thickness is not in the mesh, so the T3
pilot's ``D2000`` barrels at ``t=3`` and ``t=2`` ship byte-identical meshes
(hash ``cd2beb6ddb4a23809411``) and the old rule read them as one model - it
would have deleted a legitimate design variable.  See
:func:`model_sha256` / :func:`deck_shell_sections`.

Since M2 this is **enforced**, not merely reported: a duplicate inside a tree
fails the run.  The dataset-design decision it used to defer has been made (the
duplicate is removed, see ``dedup_dataset.py``); leaving the check advisory
would let M5's bulk generation quietly reintroduce the leak. A model shared
*across* trees is still not a duplicate - that is gate 3's premise.

Usage::

    python verify_dataset.py --root ../FEM-Bench-Aero
    python verify_dataset.py --root ../FEM-Bench-Aero --json verify.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feagpt import topology  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402

TREES = ("modeling", "_xval")
REQUIRED = ("spec.json", "model.inp", "model.step", "model.msh",
            "model.results.json", "truth.json")
SCHEMA_VERSION = topology.SCHEMA_VERSION


_TRI_KEYS = ("S3", "S6", "CPS3", "CPE3")


def deck_triangles(path: Path) -> int:
    """Count triangle elements in a CalculiX/Abaqus deck.

    Deliberately reads ``model.inp`` rather than ``model.msh``: the deck is the
    artifact both solvers actually consume, and counting ``TYPE=S3`` lines
    needs no gmsh session.  ``diagnostics/msh_quality.py`` reports the same
    number from the mesh (element type id 2) and the two agree by construction.
    """
    n = 0
    cur: str | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("*ELEMENT"):
            m = re.search(r"TYPE\s*=\s*([A-Za-z0-9]+)", line)
            cur = m.group(1).upper() if m else None
        elif line.startswith("*"):
            cur = None
        elif cur and line.strip():
            if cur in _TRI_KEYS:
                n += 1
    return n


def deck_shell_sections(path: Path) -> tuple[tuple[str, str], ...]:
    """``(element set, thickness)`` pairs exactly as the shipped deck writes them.

    **D25 (2026-10-06).**  The mesh alone does not identify a model.  A shell's
    wall thickness lives in the ``*SHELL SECTION`` card, not in the mesh, so two
    barrels differing only in ``t`` ship **byte-identical** ``model.msh`` -
    measured on the T3 pilot: ``D2000`` at ``t=3`` and ``t=2`` both hash
    ``cd2beb6ddb4a23809411`` (15,251,158 bytes).  Under the pre-D25 rule the
    duplicate gate read that pair as one model and ``dedup_dataset.py --apply``
    would have **deleted** one of them, discarding a legitimate design variable.

    Reading the deck (no gmsh, same spirit as :func:`deck_triangles`) keeps this
    on artifacts rather than on a re-derivation that could drift from what the
    solver actually read.
    """
    pairs: list[tuple[str, str]] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, line in enumerate(lines):
        if not line.upper().startswith("*SHELL SECTION"):
            continue
        m = re.search(r"ELSET\s*=\s*([^,\s]+)", line, re.I)
        name = m.group(1) if m else "?"
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        thickness = lines[j].strip() if j < len(lines) else ""
        pairs.append((name, thickness))
    return tuple(pairs)


def deck_elastic(path: Path) -> tuple[str, ...]:
    """The ``*ELASTIC`` card blocks exactly as the shipped deck writes them.

    **D29 (2026-10-11).**  Mesh bytes plus shell thicknesses still do not
    identify a model once the family has a *material* dimension: the T7
    laminate pilot ships a mesh byte-identical to the aluminium ``d20``
    coupon at the same t=2.0, and the duplicate gate read that pair as one
    model (``80695b4c759e`` measured on entry).  The elastic law lives in the
    ``*ELASTIC`` card, not in the mesh nor the section, so it is hashed too -
    one line for an isotropic solid, the 9 engineering constants for the
    composite equivalent.  Whitelist-style, same spirit as
    :func:`deck_shell_sections`: reading the deck keeps this on artifacts.
    """
    blocks: list[str] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        if not lines[i].upper().startswith("*ELASTIC"):
            i += 1
            continue
        head = lines[i].strip()
        data: list[str] = []
        j = i + 1
        while j < len(lines) and not lines[j].startswith("*"):
            if lines[j].strip():
                data.append(lines[j].strip())
            j += 1
        blocks.append(head + "|" + ";".join(data))
        i = j
    return tuple(blocks)


def model_sha256(case_dir: Path) -> str | None:
    """Fingerprint of the *model*: mesh bytes, wall thicknesses, elastic law.

    Whitelist-style: it changes when the discretisation, the shell sections
    **or the material law** change, and nothing else.  ``None`` when the case
    is incomplete.
    """
    msh = case_dir / "model.msh"
    inj = case_dir / "model.inp"
    if not msh.exists():
        return None
    h = hashlib.sha256()
    h.update(msh.read_bytes())
    if inj.exists():
        for name, t in deck_shell_sections(inj):
            h.update(b"\x00")
            h.update(f"{name}={t}".encode("utf-8"))
        for block in deck_elastic(inj):
            h.update(b"\x00")
            h.update(block.encode("utf-8"))
    return h.hexdigest()


def check_case(case_dir: Path) -> dict:
    """Run the per-case consistency checks.  Returns a report row."""
    row: dict = {"case": case_dir.name, "dir": str(case_dir),
                 "checks": {}, "ok": False, "notes": []}

    def fail(note: str):
        row["notes"].append(note)

    missing = [f for f in REQUIRED if not (case_dir / f).exists()]
    row["checks"]["completeness"] = not missing
    if missing:
        fail(f"missing files: {missing}")
        return row

    truth = json.loads((case_dir / "truth.json").read_text(encoding="utf-8"))
    results = json.loads((case_dir / "model.results.json").read_text(encoding="utf-8"))

    # 5. schema
    row["checks"]["schema"] = truth.get("schema_version") == SCHEMA_VERSION
    if not row["checks"]["schema"]:
        fail(f"schema_version {truth.get('schema_version')} != {SCHEMA_VERSION}")

    # 2. spec <-> truth (recompute the hash; do not trust the stored string)
    spec = FEASpec.from_json(case_dir / "spec.json")
    want_sha = topology.spec_sha256(spec)
    row["checks"]["spec_truth"] = truth.get("spec_sha256") == want_sha
    if not row["checks"]["spec_truth"]:
        fail("spec_sha256 does not reproduce from spec.json "
             "(spec edited after export?)")

    # 3. scalars <-> results
    row["checks"]["scalars_truth"] = truth.get("scalars") == results
    if not row["checks"]["scalars_truth"]:
        fail("truth.scalars != model.results.json")

    # 4. gate 4 re-derived
    topo = truth.get("topology") or {}
    if not topo:
        row["checks"]["gate4"] = False
        fail("no topology block in truth.json")
    else:
        gate = topology.compare(topo)
        stored = truth.get("semantic_gate") or {}
        row["checks"]["gate4"] = bool(gate["pass"])
        row["checks"]["gate4_verdict_matches"] = (
            stored.get("pass") == gate["pass"])
        if not gate["pass"]:
            bad = [c["key"] for c in gate["checks"] if not c["pass"]]
            fail(f"gate4 re-derive FAIL: {bad}")
        if not row["checks"]["gate4_verdict_matches"]:
            fail("stored semantic_gate verdict disagrees with re-derived one")

    scal = truth.get("scalars") or {}
    row["n_nodes"] = scal.get("n_nodes")
    row["max_disp"] = scal.get("max_disp")
    row["max_von_mises"] = scal.get("max_von_mises")
    row["n_surfaces"] = topo.get("geometry", {}).get("n_surfaces")
    row["family"] = truth.get("structure_family")
    row["solver"] = truth.get("solver")

    # 6. D8: the headline stress must declare what it is.  Before D8 the two
    # trees stored *different quantities* under the same key - ccx a full-tensor
    # node value, abaqus a membrane value that reads 0.0 on a flat plate in pure
    # bending - so a consumer taking ``max_von_mises`` by name got "the abaqus
    # side says there is no stress".  The definition now travels with the number,
    # and its absence is a failure rather than something to be discovered later.
    defn = scal.get("max_von_mises_definition")
    row["stress_definition"] = defn
    row["checks"]["stress_definition"] = bool(
        isinstance(defn, str) and defn.startswith("outer fibre"))
    if not row["checks"]["stress_definition"]:
        fail(f"max_von_mises does not declare an outer-fibre definition ({defn!r})")

    # 8. gate 1's other half.  The mesh builder now refuses to emit triangles
    # (it escalates to blossom full-quad, see feagpt/meshing.build_mesh), and
    # this re-checks the *shipped deck* so a stale export cannot pass by
    # predating the fix.
    tri = deck_triangles(case_dir / "model.inp")
    row["tri3"] = tri
    row["checks"]["no_tri3"] = tri == 0
    if tri:
        fail(f"model.inp ships {tri} triangle element(s); gate 1 requires 0")

    # Fingerprint of the built *model* (mesh + declared shell sections), for the
    # set-level duplicate check.  ``mesh_sha`` is kept separately because the
    # cross-tree pairing check really is about the mesh being the same artifact
    # in both trees.
    msh = case_dir / "model.msh"
    row["mesh_sha"] = hashlib.sha256(msh.read_bytes()).hexdigest()
    row["model_sha"] = model_sha256(case_dir)
    row["ok"] = all(row["checks"].values())
    return row


def find_duplicates(rows: list[dict]) -> list[dict]:
    """Group cases by **model** fingerprint; return the groups with >1 member.

    Call this **per tree**.  A mesh shared between ``modeling/`` and ``_xval/``
    is not a duplicate - it is the same model solved by two codes, which is
    exactly what gate 3 requires.  Only two cases inside one tree describing
    the same model are a real repeat.

    The fingerprint is ``model_sha`` (mesh + shell thickness), not ``mesh_sha``:
    **D25 (2026-10-06)** widened it after the T3 pilot showed two barrels differing
    only in wall thickness shipping identical meshes.  That pair is two models,
    not one; the old rule would have deleted one.  Two cases sharing a mesh *and*
    a thickness table still collide here, which is the case this gate exists for.
    """
    by_sha: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        key = r.get("model_sha") or r.get("mesh_sha")
        if key:
            by_sha[key].append(r["case"])
    dups = []
    for sha, cases in by_sha.items():
        if len(cases) > 1:
            dups.append({"model_sha256": sha, "cases": sorted(cases),
                         "n": len(cases)})
    return sorted(dups, key=lambda d: d["cases"])


def cross_tree_mesh_agreement(mod_rows: list[dict],
                              xva_rows: list[dict]) -> dict:
    """Positive evidence: paired cases whose two meshes are byte-identical.

    The mesh is built before the solver is chosen, so the two trees *should*
    carry the identical ``model.msh``.  Agreement confirms no per-solver
    geometry drift; disagreement would mean the two runs built different models
    and gate 3 was comparing apples to oranges.
    """
    m = {r["case"]: r["mesh_sha"] for r in mod_rows if r.get("mesh_sha")}
    x = {r["case"]: r["mesh_sha"] for r in xva_rows if r.get("mesh_sha")}
    shared = sorted(set(m) & set(x))
    agree = [c for c in shared if m[c] == x[c]]
    return {"n_paired": len(shared), "n_mesh_identical": len(agree),
            "mismatched": [c for c in shared if m[c] != x[c]],
            "pass": len(agree) == len(shared)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="FEM-Bench-Aero root directory")
    ap.add_argument("--json", help="also write a machine-readable report here")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root)
    report: dict = {"root": str(root), "trees": {}, "pairing": None}
    all_rows: list[dict] = []
    total_ok = 0
    total = 0

    for tree in TREES:
        base = root / tree
        if not base.is_dir():
            report["trees"][tree] = {"present": False}
            continue
        rows = [check_case(d) for d in sorted(base.iterdir()) if d.is_dir()]
        report["trees"][tree] = {
            "present": True,
            "n_cases": len(rows),
            "n_ok": sum(r["ok"] for r in rows),
            "cases": rows,
        }
        total += len(rows)
        total_ok += sum(r["ok"] for r in rows)
        all_rows.extend(rows)
        if not args.quiet:
            print(f"=== {tree}: {len(rows)} case(s)")
            for r in rows:
                flag = "OK  " if r["ok"] else "FAIL"
                mu = r.get("max_disp")
                mu_s = f"{mu:.4f}mm" if isinstance(mu, (int, float)) else "n/a"
                print(f"  [{flag}] {r['case']:46s} {str(r.get('solver') or '-'):6s}"
                      f" nodes={str(r.get('n_nodes')):>5s} max|u|={mu_s:>10s}")
                for note in r["notes"]:
                    print(f"         ! {note}")

    # 6. pairing between the publishable tree and the cross-check tree
    mod = report["trees"].get("modeling", {})
    xva = report["trees"].get("_xval", {})
    if mod.get("present") and xva.get("present"):
        ms = {r["case"] for r in mod["cases"]}
        xs = {r["case"] for r in xva["cases"]}
        report["pairing"] = {
            "modeling_only": sorted(ms - xs),
            "xval_only": sorted(xs - ms),
            "paired": len(ms & xs),
            "pass": ms == xs,
        }
        if not args.quiet:
            p = report["pairing"]
            print(f"\n=== pairing: {p['paired']} paired, "
                  f"{len(p['modeling_only'])} modeling-only, "
                  f"{len(p['xval_only'])} xval-only "
                  f"-> {'PASS' if p['pass'] else 'MISMATCH'}")

    # set-level: duplicate models *inside a tree* can leak across splits.
    # A mesh shared across trees is the opposite - it is gate 3's premise.
    dups: dict[str, list] = {}
    for tree in TREES:
        t = report["trees"].get(tree, {})
        dups[tree] = find_duplicates(t.get("cases", [])) if t.get("present") else []
    report["duplicates"] = dups

    xagree = None
    if mod.get("present") and xva.get("present"):
        xagree = cross_tree_mesh_agreement(mod["cases"], xva["cases"])
    report["cross_tree_mesh"] = xagree

    # Set-level, D8: the two trees must agree on *what the headline stress is*,
    # not only on the model.  Gate 3 compares the fields node by node, and that
    # comparison means nothing unless both sides are reporting the same
    # quantity - which, before D8, they were not.
    defs: dict = {}
    if mod.get("present") and xva.get("present"):
        m_def = {r.get("stress_definition") for r in mod["cases"]}
        x_def = {r.get("stress_definition") for r in xva["cases"]}
        good = (m_def == x_def and len(m_def) == 1
                and all(isinstance(d, str) and d.startswith("outer fibre")
                        for d in m_def))
        defs = {"modeling": sorted(str(d) for d in m_def),
                "xval": sorted(str(d) for d in x_def), "pass": good}
    report["stress_definition_agreement"] = defs

    n_dup = sum(d["n"] - 1 for tree in TREES for d in dups.get(tree, []))
    n_unique = len({(t, r["mesh_sha"]) for t in TREES
                    for r in report["trees"].get(t, {}).get("cases", [])
                    if r.get("mesh_sha")})
    if not args.quiet:
        for tree in TREES:
            ds = dups.get(tree, [])
            if ds:
                print(f"\n=== duplicate models in {tree}/: {len(ds)} group(s)")
                for d in ds:
                    print(f"  ! same model ({d['model_sha256'][:12]}): "
                          f"{', '.join(d['cases'])}")
            elif report["trees"].get(tree, {}).get("present"):
                print(f"\n=== duplicate models in {tree}/: none")
        if xagree:
            print(f"\n=== cross-tree mesh agreement: "
                  f"{xagree['n_mesh_identical']}/{xagree['n_paired']} identical "
                  f"-> {'PASS' if xagree['pass'] else 'MISMATCH'}")
        if defs:
            print(f"=== stress definition agreement (D8): modeling {defs['modeling']} "
                  f"vs xval {defs['xval']} -> {'PASS' if defs['pass'] else 'MISMATCH'}")

    report["summary"] = {
        "n_cases": total,
        "n_ok": total_ok,
        "n_unique_trees_meshes": n_unique,
        "n_duplicate_cases": n_dup,
        "duplicates_ok": n_dup == 0,
        "stress_definition_ok": bool(defs.get("pass", False)) if defs else None,
        # Pairing is check 6 in this tool's own contract, so it has to gate the
        # verdict.  It did not until 2026-10-24: ``_xval`` carried 41 cases
        # against ``modeling``'s 44 and the run still printed ``VERDICT: PASS``
        # - a check that only prints is not a check.  ``None`` (one tree
        # absent) stays neutral, because a single-tree run has nothing to pair.
        "pairing_ok": (None if report.get("pairing") is None
                       else bool(report["pairing"]["pass"])),
        "all_ok": (total_ok == total and total > 0 and n_dup == 0
                   and (not defs or bool(defs.get("pass")))
                   and (report.get("pairing") is None
                        or bool(report["pairing"]["pass"]))),
    }
    if not args.quiet:
        print(f"\ncase consistency: {total_ok}/{total} OK")
        print(f"duplicate models : {n_dup} (must be 0 within a tree)")
        print(f"VERDICT: {'PASS' if report['summary']['all_ok'] else 'CHECK'}")

    if args.json:
        Path(args.json).write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"report -> {args.json}")
    return 0 if report["summary"]["all_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
