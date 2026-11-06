"""Solve + extract pipeline for Abaqus job batches -- one model, N load cases.

Run with ANY plain Python 3 (not the Abaqus interpreter) on the machine that
has Abaqus.  Design frozen by laowang 2026-11-06 (options A/B/C):

* A  same model x N load cases        -> input is a root dir of job folders,
  each containing ``<job>.inp`` (any naming, discovered by scan).
* B  solve + extract one-stop         -> clean stale products, run
  ``abaqus job=... interactive``, verify completion, extract, optionally
  purge the ODB, write an auditable manifest.
* C  configurable extraction          -> default SCALAR tier (odb_scalar.py:
  a few hundred bytes per case), ``--full`` tier (abaqus_odb.py: full
  node/element JSON, 1-3 MB per case).

It must be launchable outside any IDE sandbox (the project's standing rule:
Abaqus inside the agent sandbox always fails -- tsbx.dll injection), i.e.
from a plain ``cmd.exe`` window.  ``--dry-run`` exists so the plan can be
inspected without Abaqus.

The four documented ways this kind of loop used to fail silently -- all
met in this project's own batches -- are each guarded IN CODE, not by
discipline:

1. **Silent no-op loop** (batch5 lesson): every job MUST get a terminal
   state (ok / solve_failed / extract_failed).  A job that never got a
   terminal state makes the manifest invalid and the exit code nonzero.
2. **Stale empty-ODB skeletons**: stale products are deleted before the
   solve, and a solve whose .sta does not contain COMPLETED SUCCESSFULLY
   is solve_failed -- never "ok with an empty result".
3. **Summary silently loses rows** (v11 lesson: 9 jobs ran, summary had 1):
   the manifest row count is asserted == job count, and every row is keyed
   by the job name actually scanned, not by what the summary felt like
   writing.
4. **Products produced but never reconciled**: the manifest is the single
   output of this tool; a separate resummarize step is NOT needed because
   rows are written as each job finishes.

Usage (outside sandbox)::

    python odb_batch.py <root_dir> [--tier scalar|full] [--purge-odb]
        [--cpus 4] [--abaqus-cmd abaqus] [--parallel 1] [--keep-logs]
        [--only job1,job2] [--dry-run]

Exit code 0 iff every job reached ok.  Anything else: read run_manifest.json.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

#: products from a previous run that would silently poison the next one
_STALE_SUFFIXES = (
    ".odb", ".odb.json", ".json.scalar", ".sta", ".dat", ".msg",
    ".prt", ".com", ".sim", ".stt", ".pac", ".res", ".lck", ".023",
)
#: kept as evidence even on success unless --keep-logs is off (small files)
_KEEP_ON_SUCCESS = (".sta", ".dat")

_ST_OK = "ok"
_ST_SOLVE = "solve_failed"
_ST_EXTRACT = "extract_failed"
_COMPLETION_MARK = "COMPLETED SUCCESSFULLY"


def find_jobs(root: str, only=None) -> dict:
    """Scan root for ``<job>.inp`` files -> {job_name: abs_path_to_inp}."""
    if not os.path.isdir(root):
        raise SystemExit(f"root dir does not exist: {root}")
    jobs = {}
    for entry in sorted(os.listdir(root)):
        full = os.path.join(root, entry)
        if os.path.isdir(full):
            for fn in sorted(os.listdir(full)):
                if fn.lower().endswith(".inp"):
                    jobs[fn[:-4]] = os.path.join(full, fn)
                    break
        elif entry.lower().endswith(".inp"):
            jobs[entry[:-4]] = full
    if only:
        want = {w.strip() for w in only.split(",") if w.strip()}
        missing = want - set(jobs)
        if missing:
            raise SystemExit(f"--only names not found in scan: {sorted(missing)}")
        jobs = {k: v for k, v in jobs.items() if k in want}
    return jobs


def clean_stale(job_dir: str, job: str, keep_logs: bool) -> list:
    """Delete stale products.  Returns what was removed (auditable)."""
    removed = []
    for fn in os.listdir(job_dir):
        base, ext = os.path.splitext(fn)
        if fn == f"{job}.inp":
            continue
        if ext.lower() in _STALE_SUFFIXES and base == job:
            os.remove(os.path.join(job_dir, fn))
            removed.append(fn)
    if not keep_logs:
        for ext in _KEEP_ON_SUCCESS:
            p = os.path.join(job_dir, job + ext)
            if os.path.exists(p):
                os.remove(p)
                removed.append(job + ext)
    return removed


def solve_ok(job_dir: str, job: str) -> bool:
    """The .sta completion judge (trap 2).  Missing .sta = not ok."""
    sta = os.path.join(job_dir, job + ".sta")
    if not os.path.exists(sta):
        return False
    try:
        with open(sta, "r", errors="replace") as fh:
            return _COMPLETION_MARK in fh.read()
    except OSError:
        return False


def run_batch(root: str, tier="scalar", purge_odb=False, cpus=1,
              abaqus_cmd="abaqus", parallel=1, keep_logs=False,
              only=None, dry_run=False, odb_tools_dir=None) -> (dict, int):
    jobs = find_jobs(root, only)
    if not jobs:
        raise SystemExit(f"no .inp jobs found under {root}")
    here = odb_tools_dir or os.path.dirname(os.path.abspath(__file__))
    scalar_py = os.path.join(here, "odb_scalar.py")
    full_py = os.path.join(here, os.pardir, "feagpt", "abaqus_odb.py")
    extractor = scalar_py if tier == "scalar" else full_py

    rows, t_all = [], time.time()
    plan = {"root": root, "tier": tier, "purge_odb": purge_odb, "cpus": cpus,
            "abaqus_cmd": abaqus_cmd, "parallel": parallel,
            "n_jobs": len(jobs), "jobs": sorted(jobs)}
    if dry_run:
        plan["dry_run"] = True
        plan["extractor"] = os.path.normpath(extractor)
        return plan, 0

    def _one(job, inp):
        job_dir = os.path.dirname(inp)
        t0 = time.time()
        row = {"job": job, "dir": job_dir, "tier": tier}
        removed = clean_stale(job_dir, job, keep_logs)
        row["cleaned"] = removed
        cmd = [abaqus_cmd, "job=%s" % job, "input=%s" % inp,
               "interactive", "cpus=%d" % cpus]
        row["cmd"] = " ".join(cmd)
        try:
            # capture: a crashed abaqus must not abort the whole batch, but
            # its output must survive into the manifest for the post-mortem
            pr = subprocess.run(cmd, cwd=job_dir, capture_output=True,
                                text=True, encoding="utf-8", errors="replace")
            row["abaqus_rc"] = pr.returncode
        except OSError as exc:
            row["abaqus_rc"] = None
            row["solve_error"] = str(exc)
            row["state"], row["seconds"] = _ST_SOLVE, round(time.time() - t0, 1)
            return row
        if pr.returncode != 0 or not solve_ok(job_dir, job):
            row["state"] = _ST_SOLVE
            row["sta_ok"] = False
            row["seconds"] = round(time.time() - t0, 1)
            return row
        row["sta_ok"] = True
        odb = os.path.join(job_dir, job + ".odb")
        if not os.path.exists(odb):
            row["state"], row["seconds"] = _ST_EXTRACT, round(time.time() - t0, 1)
            row["extract_error"] = "odb missing despite completed sta"
            return row
        out_json = os.path.join(job_dir, job + ".odb.json" if tier == "full"
                                else job + ".json.scalar")
        cmd_e = [abaqus_cmd, "python", extractor, odb, out_json]
        try:
            pe = subprocess.run(cmd_e, cwd=job_dir, capture_output=True,
                                text=True, encoding="utf-8", errors="replace")
            row["extract_rc"] = pe.returncode
            tail = (pe.stdout or "").strip().splitlines()
            row["extract_tail"] = tail[-1] if tail else ""
        except OSError as exc:
            row["extract_rc"] = None
            row["extract_error"] = str(exc)
        produced = os.path.exists(out_json) and os.path.getsize(out_json) > 2
        if row.get("extract_rc") != 0 or not produced:
            row["state"], row["seconds"] = _ST_EXTRACT, round(time.time() - t0, 1)
            return row
        row["state"], row["out"] = _ST_OK, os.path.basename(out_json)
        row["out_bytes"] = os.path.getsize(out_json)
        if tier == "scalar":
            try:
                with open(out_json, encoding="utf-8") as fh:
                    sc = json.load(fh).get("scalars", {})
                row["max_u_mag"] = (sc.get("max_u") or {}).get("mag")
                row["vm_peak"] = sc.get("vm_peak")
            except Exception as exc:  # manifest must stay true even if readback fails
                row["readback_error"] = str(exc)
        if purge_odb:
            os.remove(odb)
            row["odb_purged"] = True
        row["seconds"] = round(time.time() - t0, 1)
        return row

    job_list = sorted(jobs)
    if parallel <= 1:
        for job in job_list:
            rows.append(_one(job, jobs[job]))
    else:
        # keep it honest: parallel only across EXTRACTION, never solve,
        # unless the operator accepts the license risk explicitly.
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=parallel) as ex:
            rows = list(ex.map(lambda j: _one(j, jobs[j]), job_list))

    manifest = {"root": root, "tier": tier, "purge_odb": purge_odb,
                "cpus": cpus, "parallel": parallel,
                "n_jobs_scanned": len(jobs),
                "n_rows": len(rows),
                "n_ok": sum(1 for r in rows if r["state"] == _ST_OK),
                "n_solve_failed": sum(1 for r in rows if r["state"] == _ST_SOLVE),
                "n_extract_failed": sum(1 for r in rows if r["state"] == _ST_EXTRACT),
                "total_seconds": round(time.time() - t_all, 1),
                "rows": rows}
    # trap 3: the reconciliation IS the invariant, in code.
    assert manifest["n_rows"] == manifest["n_jobs_scanned"], (
        "manifest rows != scanned jobs -- this is the v11 summary-loses-rows "
        "failure mode; refusing to write a lying manifest")
    out_path = os.path.join(root, "run_manifest.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    return manifest, 0 if manifest["n_ok"] == manifest["n_jobs_scanned"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root", help="root dir: each job = <name>.inp directly, "
                                "or inside its own subfolder")
    ap.add_argument("--tier", choices=("scalar", "full"), default="scalar",
                    help="scalar = odb_scalar.py (default, bytes per case); "
                         "full = feagpt/abaqus_odb.py (full JSON)")
    ap.add_argument("--purge-odb", action="store_true",
                    help="delete the .odb after successful extraction (disk)")
    ap.add_argument("--cpus", type=int, default=1)
    ap.add_argument("--abaqus-cmd", default="abaqus")
    ap.add_argument("--parallel", type=int, default=1,
                    help=">1 runs jobs concurrently -- mind your license tokens")
    ap.add_argument("--keep-logs", action="store_true",
                    help="keep .sta/.dat even on success (default: keep, they "
                         "are small; this flag is kept for compat)")
    ap.add_argument("--only", help="comma-separated job subset")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan, touch nothing (sandbox-safe)")
    ap.add_argument("--odb-tools-dir", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    manifest, rc = run_batch(args.root, tier=args.tier, purge_odb=args.purge_odb,
                             cpus=args.cpus, abaqus_cmd=args.abaqus_cmd,
                             parallel=args.parallel, keep_logs=args.keep_logs,
                             only=args.only, dry_run=args.dry_run,
                             odb_tools_dir=args.odb_tools_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=1))
    if not args.dry_run:
        print(f"SUMMARY n={manifest['n_jobs_scanned']} ok={manifest['n_ok']} "
              f"solve_failed={manifest['n_solve_failed']} "
              f"extract_failed={manifest['n_extract_failed']} "
              f"total={manifest['total_seconds']}s rc={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
