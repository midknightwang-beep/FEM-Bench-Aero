"""Solver adapters - CalculiX and Abaqus.

FeaGPT drives CalculiX.  This reproduction drives **either** CalculiX (``ccx``)
or a locally installed Abaqus, because both are worth having: CalculiX is free
and portable, Abaqus is what the target engineering workflow actually uses.

The two solvers consume the same deck *language* but not the same dialect - see
:mod:`feagpt.inp_writer` - and, more importantly, they report results through
completely different channels:

* CalculiX writes an **FRD** text file;
* Abaqus writes a binary **ODB**, which can only be read from inside the Abaqus
  Python environment.

So the Abaqus branch runs in two steps: solve, then invoke
:mod:`feagpt.abaqus_odb` under ``abaqus python`` to convert the ODB into the
same intermediate JSON the FRD reader produces.  Downstream code is then
solver-agnostic.

Solver discovery order
----------------------
1. ``$FEAGPT_CCX`` / ``$FEAGPT_ABAQUS`` environment variables
2. ``tools/calculix/<version>/ccx_static.exe`` next to this package
3. ``ccx`` / ``ccx_2.*`` / ``abaqus`` / ``abaqus.bat`` on ``PATH``
4. known SIMULIA install roots
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent
_REPO_DIR = _PKG_DIR.parent

#: Abaqus-specific conversion script, executed by ``abaqus python``.
_ODB_SCRIPT = _PKG_DIR / "abaqus_odb.py"


@dataclass
class SolveResult:
    solver: str = ""
    executable: str = ""
    returncode: int = -1
    wall_time: float = 0.0
    inp: str = ""
    frd: str = ""
    odb: str = ""
    dat: str = ""
    sta: str = ""
    log: str = ""
    ok: bool = False
    # NOTE: this used to be named ``field``, which shadowed the dataclasses
    # ``field()`` helper inside the class body - harmless while it was the only
    # use, an immediate TypeError as soon as a second default_factory appeared.
    output_fields: list[str] = field(default_factory=list)
    # Abaqus only: the JSON produced from the ODB, in FRD-reader schema.
    results_json: str = ""
    extract_log: str = ""
    extract_seconds: float = 0.0
    solver_meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "solver": self.solver,
            "executable": self.executable,
            "returncode": self.returncode,
            "wall_time_s": round(self.wall_time, 3),
            "inp": self.inp,
            "frd": self.frd,
            "ok": self.ok,
        }
        if self.odb:
            d["odb"] = self.odb
            d["results_json"] = self.results_json
            d["extract_ok"] = bool(self.results_json)
            d["extract_s"] = round(self.extract_seconds, 3)
        return d


def dialect_for(solver_name: str) -> str:
    """Which deck dialect a solver speaks."""
    return "abaqus" if solver_name == "abaqus" else "ccx"


# --------------------------------------------------------------------------- #
# discovery
# --------------------------------------------------------------------------- #
def _calculix_candidates() -> list[Path]:
    cands: list[Path] = []
    env = os.environ.get("FEAGPT_CCX")
    if env:
        cands.append(Path(env))
    # Bundled download (tools/calculix/calculix_x.yy_4win/ccx_static.exe).
    # Walk up a few levels rather than assuming a fixed repo depth: the tools
    # tree usually sits beside the package, not inside it.
    roots, p = [], _PKG_DIR
    for _ in range(4):
        roots.append(p)
        p = p.parent
    for root in roots:
        base = root / "tools" / "calculix"
        if base.is_dir():
            for name in ("ccx_static.exe", "ccx_i4.exe", "ccx_dynamic.exe"):
                cands.extend(sorted(base.rglob(name)))
    for exe in ("ccx", "ccx_static", "ccx_i4", "ccx_2.23", "ccx_2.22"):
        found = shutil.which(exe)
        if found:
            cands.append(Path(found))
    return cands


def _abaqus_candidates() -> list[Path]:
    cands: list[Path] = []
    env = os.environ.get("FEAGPT_ABAQUS")
    if env:
        cands.append(Path(env))
    for exe in ("abaqus", "abaqus.bat"):
        found = shutil.which(exe)
        if found:
            cands.append(Path(found))
    # Common SIMULIA install roots.  The real layout is
    #   <root>/<Year>/Commands/abaqus.bat
    # with <root> frequently on a non-system drive and the path containing
    # spaces ("D:/Program Files/SIMULIA"), so probe a few and glob.
    roots = [
        Path("C:/SIMULIA"),
        Path("D:/SIMULIA"),
        Path("C:/Program Files/SIMULIA"),
        Path("D:/Program Files/SIMULIA"),
        Path("C:/Program Files (x86)/SIMULIA"),
        Path("D:/Program Files (x86)/SIMULIA"),
    ]
    for root in roots:
        if root.exists():
            cands.extend(sorted(root.rglob("Commands/abaqus.bat"))[-3:])
    return cands


def find_solver(prefer: str = "auto") -> tuple[str, Path] | None:
    """Return ``(name, executable_path)`` or ``None``."""
    order = ["ccx", "abaqus"] if prefer in (None, "", "auto") else [prefer, "ccx", "abaqus"]
    for want in order:
        if want == "ccx":
            for c in _calculix_candidates():
                if c.exists():
                    return "ccx", c
        elif want == "abaqus":
            for c in _abaqus_candidates():
                if c.exists():
                    return "abaqus", c
    return None


# --------------------------------------------------------------------------- #
# execution
# --------------------------------------------------------------------------- #
def _tail(path: Path, n: int = 40) -> str:
    """Last ``n`` lines of a text file, tolerant of encoding and absence."""
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-n:])


def _abaqus_diagnostics(job: Path) -> str:
    """Collect why an Abaqus job failed.

    Abaqus is unhelpful in two specific ways:

    * it **exits with code 0** on a job-level abort - a stale ``.lck`` lock
      file, for instance - so the exit code cannot be trusted as the success
      signal; and
    * the actual reason goes to ``<job>.msg`` (not stdout, not ``.dat``).

    So the caller must look for a usable ODB *and* consult these files, which is
    what this returns.
    """
    parts: list[str] = []
    msg = job.with_suffix(".msg")
    if msg.exists():
        for line in _tail(msg, 40).splitlines():
            if "Error" in line or "error" in line:
                parts.append(f"[.msg] {line.strip()}")
    dat = job.with_suffix(".dat")
    for line in _tail(dat, 60).splitlines():
        if "***ERROR" in line or "*** Error" in line:
            parts.append(f"[.dat] {line.strip()}")
    return "\n".join(parts[:12])


def _clear_stale_abaqus_lock(job: Path) -> str:
    """Remove a leftover ``.lck`` before launching an Abaqus job.

    Abaqus refuses to start when a lock file is present ("Detected lock file
    ... please confirm that no other applications are attempting to write to
    the output database"), and then exits **0**, so a batch run over hundreds of
    configurations would silently mark every affected case as successful-then-
    empty unless the lock is cleared.

    A lock file sitting in the pipeline's own output directory, in the moment
    before that same pipeline launches the job for the deck it has just written,
    is necessarily stale: no other process can legitimately be writing this
    job's ODB.  Removing it is therefore safe here - but it is still recorded in
    the log rather than done silently, because a stale lock usually means an
    earlier run was killed, and that is worth knowing.
    """
    lock = job.with_suffix(".lck")
    if not lock.exists():
        return ""
    try:
        lock.unlink()
        return f"removed stale Abaqus lock file {lock.name} before launch"
    except OSError as exc:  # pragma: no cover - permission dependent
        return f"could not remove stale lock file {lock.name}: {exc}"


def run(inp_path, solver: str | None = None, timeout: int = 1800,
        extract_timeout: int = 900) -> SolveResult:
    """Solve ``inp_path`` and return the artifacts that were produced."""
    inp_path = Path(inp_path).resolve()
    job = inp_path.with_suffix("")
    res = SolveResult(inp=str(inp_path))

    picked = find_solver(solver or "auto")
    if picked is None:
        res.log = "no solver found (looked for ccx and abaqus)"
        return res
    name, exe = picked
    res.solver, res.executable = name, str(exe)

    if name == "ccx":
        cmd = [str(exe), "-i", job.name]
    else:
        # ask_delete=OFF is not cosmetic: without it Abaqus stops on an
        # interactive "overwrite existing job files? [y/n]" prompt whenever a
        # previous run left artifacts behind, and the process hangs until the
        # timeout.  interactive keeps the solve in the foreground so the exit
        # code and console log belong to us.
        cmd = [str(exe), f"job={job.name}", "interactive", "cpus=1", "ask_delete=OFF"]
        note = _clear_stale_abaqus_lock(job)
        if note:
            res.log += note + "\n"

    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(job.parent),
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
        )
        res.returncode = proc.returncode
        res.log = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        res.log = f"solver timed out after {timeout}s"
        res.returncode = -9
    finally:
        res.wall_time = time.time() - t0

    for ext, attr in ((".frd", "frd"), (".odb", "odb"), (".dat", "dat"), (".sta", "sta")):
        p = job.with_suffix(ext)
        if p.exists():
            setattr(res, attr, str(p))

    if name == "ccx":
        res.ok = res.returncode == 0 and bool(res.frd)
        if not res.ok and not res.log:
            res.log = f"solver exited with code {res.returncode}"
        return res

    # ---- Abaqus: convert the ODB into the shared intermediate form ------- #
    solved = res.returncode == 0 and bool(res.odb)
    if not solved:
        diag = _abaqus_diagnostics(job)
        res.log = (res.log + "\n--- Abaqus diagnostics ---\n"
                   + (diag or _tail(job.with_suffix(".dat")) or _tail(job.with_suffix(".log"))))[-2000:]
        if not res.log:
            res.log = f"Abaqus exited with code {res.returncode}, no ODB produced"
        return res

    out_json = job.with_suffix(".odb.json")
    script = _ODB_SCRIPT
    if not script.exists():  # pragma: no cover - packaging safety net
        res.log += f"\nODB extractor missing at {script}"
        return res

    # **Delete any previous extraction before running the extractor.**
    #
    # The presence of ``out_json`` is the *only* evidence the chain has that the
    # ODB was read - ``res.ok`` and ``pipeline``'s choice of result source are
    # both derived from ``bool(res.results_json)``.  So a leftover file from an
    # earlier run silently stands in for a fresh one, and the failure mode is
    # "the previous run's numbers are reported as this run's".
    #
    # That is not hypothetical.  Measured on 2026-10-05 (batch 3, T3 pilot): the
    # Abaqus analysis stopped right after the input-file processor - the ``.dat``
    # ended at "END OF USER INPUT PROCESSING" with an 8 s JOB TIME SUMMARY, no
    # ``.sta``/``.msg`` was written, and the ``.lck`` stayed behind - i.e. the
    # documented silent-idle mode.  The extractor then had a frame-less ODB to
    # read, wrote nothing, and the run reported ``extract_ok: true`` with the
    # **four-hour-old** ``.odb.json``: the stale max|u| came out looking like a
    # fresh result.  Removing the file first turns that into a hard failure, which
    # is what it should have been.
    stale_removed = False
    if out_json.exists():
        try:
            out_json.unlink()
            stale_removed = True
        except OSError:  # pragma: no cover - defensive
            pass

    t0 = time.time()
    try:
        proc = subprocess.run(
            [str(exe), "python", str(script), str(job.with_suffix(".odb")), str(out_json)],
            cwd=str(job.parent),
            capture_output=True,
            text=True,
            timeout=extract_timeout,
            errors="replace",
        )
        res.extract_log = ((proc.stdout or "") + (proc.stderr or ""))[-4000:]
    except subprocess.TimeoutExpired:
        res.extract_log = f"ODB extraction timed out after {extract_timeout}s"
        return res
    finally:
        res.extract_seconds = time.time() - t0

    if out_json.exists():
        res.results_json = str(out_json)
        res.ok = True
    else:
        # An aborted job still leaves a (frame-less) ODB behind, so a crashing
        # extractor is usually a symptom and not the disease - report both, and
        # say explicitly that nothing stale was left to be mistaken for a result.
        diag = _abaqus_diagnostics(job)
        res.log = (res.log + "\n--- ODB extraction ---\n" + res.extract_log
                   + (f"\n(a stale {out_json.name} was removed before extraction)"
                      if stale_removed else "")
                   + "\n--- Abaqus diagnostics ---\n"
                   + (diag or "(none reported)"))[-3000:]
    return res
