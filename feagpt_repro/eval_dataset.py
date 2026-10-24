#!/usr/bin/env python
"""M4: check the manifest by recomputing it, and gate the split against leakage.

``make_manifest.py`` *declares* things: this case's equivalence class, its role,
its split, the sha256 of its files, its headline readings.  This tool asks the
only question worth asking about a declaration -- **does it still hold on disk?**
-- by recomputing every one of those fields from the case directories and
comparing.  A hand-edited manifest, a case that was re-solved without re-running
the manifest, or a holdout declaration edited to move one member of a class away
from its class-mates all show up here.

What is re-derived, and from where
----------------------------------
======================  =========================================
declared                recomputed from
======================  =========================================
``spec_sha256``         ``spec.json`` via ``topology.spec_sha256``
``mesh_sha256``         the bytes of ``model.msh``
``files[*]``            the bytes of each of the six canonical files
``geometry_class``      ``spec.json`` via the whitelist rule
``role``                ``spec.json`` via the ordered role tests
``readings.n_tri3``     ``model.inp`` (``TYPE=S3`` count, no gmsh)
``readings.min_jacobian``  ``model.msh`` via ``diagnostics/msh_quality.py``
``readings.n_nodes`` ...  ``truth.json``'s scalars block
======================  =========================================

The first four come from files the manifest itself never touches, so agreement
is evidence rather than tautology.

The gates
---------
Beyond field-by-field agreement, six set-level conditions must hold.  They are
the reason M4 exists; a manifest that merely describes a leaky split is not a
manifest, it is a warning label.

1. **no leakage** -- no equivalence class spans more than one split.
2. **class partition agrees** -- the whitelist and blacklist derivations of the
   equivalence relation produce the same grouping.  If they disagree, some
   field's geometry/processing ownership is wrong.
3. **same class => same design** -- members of one class carry the same
   ``truth.json`` design *and* geometry readings.  This is the cross-file
   corroboration: the class was defined from ``spec.json``, and this checks it
   against what the geometry builder actually produced.
4. **every family has a test case** -- otherwise the split cannot measure
   generalisation for that family at all.
5. **every case is assigned** -- an ``unassigned`` case means the family has no
   declared holdout regions (the M5 signal: declare the family, do not guess).
6. **the rule reproduces D12** -- the M5 rule replaced the M4 explicit table, and
   it must keep placing the locked eleven exactly as 口径 A did.  A declaration
   edit that silently re-assigns one of them fails here.

Usage::

    python eval_dataset.py --root ../FEM-Bench-Aero
    python eval_dataset.py --root ../FEM-Bench-Aero --json ../FEM-Bench-Aero/eval_report.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "diagnostics"))

from feagpt import manifest as mf  # noqa: E402
from feagpt import topology  # noqa: E402
from feagpt.spec import FEASpec  # noqa: E402
from verify_dataset import (REQUIRED, deck_triangles, find_duplicates,  # noqa: E402
                            model_sha256)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _recompute(case_dir: Path) -> dict:
    """Everything the manifest declares, recomputed from disk."""
    from msh_quality import quality  # the independent M3 gate-1 reader

    spec = FEASpec.from_json(case_dir / "spec.json")
    truth = json.loads((case_dir / "truth.json").read_text(encoding="utf-8"))
    scal = truth.get("scalars") or {}
    topo = truth.get("topology") or {}
    mq = quality(case_dir / "model.msh") if (case_dir / "model.msh").exists() else {"min": None}
    mj = mq.get("min")
    if mj is None or mj != mj:  # None or NaN
        mj = None
    else:
        mj = round(float(mj), 4)
    return {
        "case_id": spec.name,
        "family": mf.family_of(spec),
        "role": mf.infer_role(spec),
        "geometry_class": mf.geometry_class(spec),
        "geometry_class_alt": mf.geometry_class_complement(spec),
        "split": mf.assign_split(spec),
        "spec_sha256": topology.spec_sha256(spec),
        "spec_sha256_stored": truth.get("spec_sha256"),
        "mesh_sha256": _sha(case_dir / "model.msh"),
        "model_sha256": model_sha256(case_dir),
        "files": {n: _sha(case_dir / n) for n in REQUIRED if (case_dir / n).exists()},
        "missing": [n for n in REQUIRED if not (case_dir / n).exists()],
        "n_tri3": deck_triangles(case_dir / "model.inp"),
        "min_jacobian": mj,
        "design": json.dumps(topo.get("design"), sort_keys=True, ensure_ascii=False),
        "geometry_reading": json.dumps(
            {k: v for k, v in (topo.get("geometry") or {}).items()
             if k != "skeleton"}, sort_keys=True, ensure_ascii=False),
        "scalars": scal,
    }


def _class_partition(pairs) -> dict[str, frozenset]:
    """case -> class, folded into a canonical 'which cases sit together' map."""
    groups: dict[str, set[str]] = defaultdict(set)
    for case, cls in pairs:
        groups[cls].add(case)
    return frozenset(frozenset(v) for v in groups.values())


def check(root: Path, manifest_path: Path) -> dict:
    man = json.loads(manifest_path.read_text(encoding="utf-8"))
    declared = {c["case_id"]: c for c in man["cases"]}
    base = root / "modeling"
    on_disk = sorted(d.name for d in base.iterdir() if d.is_dir())

    import gmsh
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    try:
        actual = {name: _recompute(base / name) for name in on_disk}
    finally:
        gmsh.finalize()

    checks: list[dict] = []

    def add(key, ok, detail=""):
        checks.append({"key": key, "pass": bool(ok), "detail": detail})

    # --- 0. coverage: manifest and disk describe the same set of cases -------
    add("case_set_matches", set(declared) == set(actual),
        f"manifest {len(declared)} vs disk {len(actual)}; "
        f"only-in-manifest={sorted(set(declared) - set(actual))} "
        f"only-on-disk={sorted(set(actual) - set(declared))}")

    # --- 1. per-case: every declared field, recomputed ----------------------
    bad = defaultdict(list)
    for name, a in actual.items():
        d = declared.get(name)
        if not d:
            continue
        if d.get("spec_sha256") != a["spec_sha256"]:
            bad["spec_sha256"].append(name)
        if a["spec_sha256"] != a["spec_sha256_stored"]:
            bad["truth_internal_sha"].append(name)
        if d.get("mesh_sha256") != a["mesh_sha256"]:
            bad["mesh_sha256"].append(name)
        if d.get("geometry_class") != a["geometry_class"]:
            bad["geometry_class"].append(name)
        if d.get("role") != a["role"]:
            bad["role"].append(name)
        if d.get("split") != a["split"]:
            bad["split"].append(name)
        if d.get("family") != a["family"]:
            bad["family"].append(name)
        if a["missing"]:
            bad["completeness"].append(f"{name}:{a['missing']}")
        dfiles = d.get("files") or {}
        if dfiles != a["files"]:
            diff = sorted(set(dfiles) ^ set(a["files"])) or \
                sorted(k for k in dfiles if dfiles.get(k) != a["files"].get(k))
            bad["files"].append(f"{name}:{diff}")
        dr = d.get("readings") or {}
        for key in ("n_nodes", "max_disp", "max_von_mises"):
            if dr.get(key) != a["scalars"].get(key):
                bad[f"readings.{key}"].append(name)
        if dr.get("n_tri3") != a["n_tri3"]:
            bad["readings.n_tri3"].append(name)
        if dr.get("min_jacobian") != a["min_jacobian"]:
            bad["readings.min_jacobian"].append(name)

    for key in ("spec_sha256", "truth_internal_sha", "mesh_sha256", "geometry_class",
                "role", "split", "family", "completeness", "files",
                "readings.n_nodes", "readings.max_disp", "readings.max_von_mises",
                "readings.n_tri3", "readings.min_jacobian"):
        n_bad = len(bad.get(key, []))
        label = f"recompute {key}"
        if key == "truth_internal_sha":
            label = "truth.json spec_sha256 self-consistent"
        add(label, n_bad == 0,
            "" if not n_bad else f"{n_bad} case(s): {bad[key][:3]}")

    # --- 2. equivalence: whitelist vs blacklist must give the same partition -
    wl = _class_partition((n, a["geometry_class"]) for n, a in actual.items())
    bl = _class_partition((n, a["geometry_class_alt"]) for n, a in actual.items())
    add("equivalence_whitelist_eq_blacklist", wl == bl,
        f"whitelist has {len(wl)} class(es), blacklist {len(bl)}")

    # --- 3. same class => same design & geometry reading (cross-file) -------
    by_cls = defaultdict(list)
    for n, a in actual.items():
        by_cls[a["geometry_class"]].append(a)
    incoherent = []
    for cls, mems in by_cls.items():
        if len({m["design"] for m in mems}) > 1:
            incoherent.append(f"{cls[:8]}: design differs")
        if len({m["geometry_reading"] for m in mems}) > 1:
            incoherent.append(f"{cls[:8]}: geometry reading differs")
    add("same_class_same_design", not incoherent, "; ".join(incoherent))

    # --- 4. the leakage gate: no class spans two splits ---------------------
    leaks = []
    for cls, mems in by_cls.items():
        splits = {m["split"] for m in mems}
        if len(splits) > 1:
            leaks.append({"class": cls, "cases": sorted(m["case_id"] for m in mems),
                          "splits": sorted(splits)})
    add("no_class_spans_splits", not leaks,
        "" if not leaks else json.dumps(leaks, ensure_ascii=False))

    # --- 5. every family has a test case -----------------------------------
    fam_test: dict[str, int] = defaultdict(int)
    for a in actual.values():
        if a["split"] == "test":
            fam_test[a["family"]] += 1
    fams = {a["family"] for a in actual.values()}
    missing_fam = sorted(f for f in fams if fam_test.get(f, 0) == 0)
    add("every_family_has_test", not missing_fam,
        f"families without a test case: {missing_fam}" if missing_fam else "")

    # --- 6. every case assigned -------------------------------------------
    unassigned = sorted(n for n, a in actual.items() if a["split"] == "unassigned")
    add("every_case_assigned", not unassigned,
        f"unassigned: {unassigned}" if unassigned else "")

    # --- 6b. the rule must keep reproducing the D12-locked 口径 A -----------
    # Replacing the M4 explicit table with a rule (M5) is only safe if the rule
    # still places the eleven cases exactly as D12 locked them.  A declaration
    # edit that silently re-assigns one of them must fail here, not surface
    # later in a training run.
    drift = sorted(f"{n}: locked={mf.D12_LOCKED_SPLIT[n]} rule={actual[n]['split']}"
                   for n in mf.D12_LOCKED_SPLIT
                   if n in actual and actual[n]["split"] != mf.D12_LOCKED_SPLIT[n])
    vanished = sorted(n for n in mf.D12_LOCKED_SPLIT if n not in actual)
    add("rule_reproduces_D12", not drift and not vanished,
        "" if not (drift or vanished) else f"drifted={drift} vanished={vanished}")

    # --- 7. no duplicate models inside the release tree --------------------
    # D25: the model fingerprint is mesh + declared shell thickness, so a
    # thickness variant is not mistaken for a repeat of its own baseline.
    dups = find_duplicates([{"case": n, "model_sha": a["model_sha256"]}
                            for n, a in actual.items()])
    add("no_duplicate_models", not dups,
        "" if not dups else json.dumps(dups, ensure_ascii=False))

    # --- summary: split / family / role counts, from disk ------------------
    splits: dict[str, list[str]] = defaultdict(list)
    fams_split: dict[str, dict[str, int]] = {}
    for n, a in actual.items():
        splits[a["split"]].append(n)
        # Pre-seed every split with 0: a family with an empty val is a fact
        # worth stating, and "absent key" and "zero" should not look different.
        # An undeclared family yields "unassigned", which is *not* in SPLITS --
        # count it rather than crash, so the checker reports the declaration gap
        # (via every_case_assigned) instead of dying on the condition it exists
        # to report.
        fam = fams_split.setdefault(a["family"], {s: 0 for s in mf.SPLITS})
        fam[a["split"]] = fam.get(a["split"], 0) + 1

    summary = {
        "n_cases": len(actual),
        "n_geometry_classes": len(by_cls),
        "splits": {k: sorted(v) for k, v in sorted(splits.items())},
        "by_family": {f: dict(v) for f, v in sorted(fams_split.items())},
        "roles": dict(sorted(Counter(a["role"] for a in actual.values()).items())),
        "n_leaky_classes": len(leaks),
        "n_duplicate_models": sum(d["n"] - 1 for d in dups),
    }
    # cross-check the counts the manifest published
    ms = man.get("summary", {})
    for key, got in (("n_cases", summary["n_cases"]),
                     ("n_geometry_classes", summary["n_geometry_classes"]),
                     ("n_leaky_classes", summary["n_leaky_classes"]),
                     ("n_duplicate_models", summary["n_duplicate_models"]),
                     ("roles", summary["roles"]),
                     ("by_family", summary["by_family"])):
        add(f"manifest_summary.{key}", ms.get(key) == got,
            f"manifest {ms.get(key)} vs recomputed {got}")
    add("manifest_summary.splits",
        {k: v for k, v in (ms.get("splits") or {}).items()} ==
        {k: len(v) for k, v in summary["splits"].items()},
        f"manifest {ms.get('splits')} vs recomputed "
        f"{ {k: len(v) for k, v in summary['splits'].items()} }")

    return {"root": str(root), "manifest": str(manifest_path),
            "checks": checks, "summary": summary,
            "failures": [c for c in checks if not c["pass"]]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="FEM-Bench-Aero root directory")
    ap.add_argument("--manifest", help="manifest to check "
                    "(default: <root>/manifest.json)")
    ap.add_argument("--json", help="write the report here")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root)
    manifest = Path(args.manifest) if args.manifest else root / "manifest.json"
    if not manifest.exists():
        print(f"no manifest at {manifest}; run make_manifest.py first")
        return 1

    rep = check(root, manifest)
    if not args.quiet:
        print(f"=== manifest vs recomputation ({len(rep['checks'])} checks)")
        for c in rep["checks"]:
            flag = "OK  " if c["pass"] else "FAIL"
            print(f"  [{flag}] {c['key']}"
                  + (f"  :: {c['detail']}" if c["detail"] else ""))
        s = rep["summary"]
        print(f"\ncases {s['n_cases']}  classes {s['n_geometry_classes']}  "
              f"splits {{{', '.join(f'{k}:{len(v)}' for k, v in s['splits'].items())}}}")
        for fam, d in s["by_family"].items():
            print(f"  {fam}: {{{', '.join(f'{k}:{v}' for k, v in d.items())}}}")
        print(f"roles {s['roles']}")
        nfail = len(rep["failures"])
        print(f"\nVERDICT: {'PASS' if nfail == 0 else f'{nfail} CHECK(S) FAILED'}")

    if args.json:
        Path(args.json).write_text(
            json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"report -> {args.json}")
    return 0 if not rep["failures"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
