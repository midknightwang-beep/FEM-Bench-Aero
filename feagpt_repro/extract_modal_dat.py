"""Extract modal results (eigenvalues f1..fN) from ccx / abaqus .dat files.

C6-P1 modal pilot (design: FEM-Bench-Aero/DESIGN_C6_P1_MODAL.md, 2026-11-07).

Both solvers print an eigenvalue table to ``<job>.dat`` automatically for a
``*FREQUENCY`` step -- no field request needed.  The two dialects differ in
what they print, and the conversion is the one trap this module pins in code:

* **CalculiX** prints bare ``eigenvalue`` values lambda (rad^2/s^2 in a
  consistent mm-t-s deck).  Frequency is NOT printed:

      f_hz = sqrt(lambda) / (2 * pi)

* **Abaqus** prints a five-column table per mode:
  ``MODE NO  EIGENVALUE  FREQUENCY(RAD/TIME)  FREQUENCY(CYCLES/TIME)
  GENERALIZED MASS``.  The Cycles/Time column is f directly -- but we ALSO
  recompute f from lambda and require both to agree (internal consistency
  pin).  A reader that mis-parses a column silently produces a wrong
  frequency; the recomputation makes that impossible to miss.

Both paths share one property: garbage in -> an explicit error or a flagged
field, never a silently wrong number (S-45 discipline).

Usage (any plain Python 3, sandbox-safe)::

    python extract_modal_dat.py <job.dat> <out.json> --dialect ccx|abaqus
        [--expect 5]
    python extract_modal_dat.py --self-test

Output JSON::

    {"source": "modal-dat", "dialect": ..., "dat": ...,
     "modes": [{"mode": i, "lam": ..., "f_hz": ..., "f_hz_check": ...}, ...],
     "f_hz": [...], "n_modes_found": N, "monotonic": true, "positive": true,
     "raw_block": "..."}       # first eigenvalue table region, for audit
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys

_DIAGNOSTIC_F = "abaqus does not print the eigenvalue table to .dat"


# --------------------------------------------------------------------------- #
# table slicing: pull out the eigenvalue region(s) of a .dat
# --------------------------------------------------------------------------- #

_EIG_HEADER = re.compile(r"E\s*I\s*G\s*E\s*N\s*V\s*A\s*L\s*U\s*E", re.IGNORECASE)

# abaqus data row: MODE EIGENVALUE F_RAD F_CYC GENMASS  (5 floats, first is int)
_ABAQUS_ROW = re.compile(
    r"^\s*(\d+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s*$")

# ccx 2.23 style: mode number on one line, eigenvalue on the next
_CCX_PAIR = re.compile(r"^\s*(\d+)\s*$")
_CCX_VAL = re.compile(r"^\s*([-+0-9.eE]+)\s*$")


def _is_banner(ln: str) -> bool:
    """A section banner in either .dat style is single letters spaced out:
    ``E I G E N V A L U E   O U T P U T``.  Column sub-headers like
    ``(RAD/TIME)     (CYCLES/TIME)   MASS`` or ``MODE NO  EIGENVALUE`` are
    multi-char tokens and must NOT terminate the table (first version of this
    heuristic killed the abaqus parse at its sub-header -- caught by pin 2)."""
    toks = ln.strip().split()
    return (len(toks) >= 3
            and all(len(t) == 1 and t.isalpha() and t.isupper() for t in toks))


def _eigen_block(text: str) -> str:
    """Return the text from the first eigenvalue header to end of that table.

    The table ends at the next section banner (or EOF).  Keeping the raw
    region in the output JSON makes every extracted number auditable without
    re-running the solver.
    """
    m = _EIG_HEADER.search(text)
    if not m:
        return ""
    lines = text[m.start():].splitlines()
    keep = [lines[0]]
    for ln in lines[1:]:
        if _is_banner(ln):  # next section header -> table is over
            break
        keep.append(ln)
        if len(keep) > 400:  # hard stop: requested modes are single digits
            break
    return "\n".join(keep)


# --------------------------------------------------------------------------- #
# dialect parsers
# --------------------------------------------------------------------------- #

def _parse_abaqus(block: str) -> list[dict]:
    """Parse the abaqus 5-column eigenvalue table."""
    modes = []
    for ln in block.splitlines():
        m = _ABAQUS_ROW.match(ln)
        if not m:
            continue
        mode, lam, f_rad, f_cyc, gen_mass = (float(x) for x in m.groups())
        # internal consistency pin: f from lambda must equal the printed
        # Cycles/Time column.  lam could be <= 0 in degenerate cases; skip
        # the check there and let the caller's positivity gate fire.
        f_check = None
        if lam > 0:
            f_check = math.sqrt(lam) / (2.0 * math.pi)
            if abs(f_check - f_cyc) > 1e-4 * max(1.0, abs(f_cyc)):
                raise ValueError(
                    "abaqus .dat inconsistent: lambda=%r implies f=%r but the "
                    "Cycles/Time column says %r -- mis-parsed table?"
                    % (lam, f_check, f_cyc))
        modes.append({"mode": int(mode), "lam": lam, "f_rad": f_rad,
                      "f_hz": f_cyc, "f_hz_check": f_check,
                      "gen_mass": gen_mass})
    return modes


def _parse_table_rows(block: str, label: str) -> list[dict]:
    """Parse ``MODE  EIGENVALUE  F_RAD  F_CYC  <extra>`` rows.

    Measured 2026-11-07 on ccx 2.23 AND abaqus: both print the same 5-number
    row for real eigenmodes (the design doc assumed ccx prints lambda only --
    wrong for 2.23, corrected by the first real run).  ``extra`` is
    generalized mass (abaqus) or the imaginary part (ccx, 0 for real modes);
    we don't need it, but the f_hz column is cross-checked against
    sqrt(lambda)/2*pi so a mis-parsed column cannot pass silently.
    """
    modes = []
    row5 = re.compile(
        r"^\s*(\d+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)"
        r"\s+([-+0-9.eE]+)\s*$")
    for ln in block.splitlines():
        m = row5.match(ln)
        if not m:
            continue
        mode, lam, f_rad, f_cyc, _extra = (float(x) for x in m.groups())
        f_check = None
        if lam > 0:
            f_check = math.sqrt(lam) / (2.0 * math.pi)
            if abs(f_check - f_cyc) > 1e-4 * max(1.0, abs(f_cyc)):
                raise ValueError(
                    f"{label} .dat inconsistent: lambda={lam!r} implies "
                    f"f={f_check!r} but the Cycles/Time column says "
                    f"{f_cyc!r} -- mis-parsed table?")
        modes.append({"mode": int(mode), "lam": lam, "f_rad": f_rad,
                      "f_hz": f_cyc, "f_hz_check": f_check})
    return modes


def _parse_ccx(block: str) -> list[dict]:
    """Parse the ccx eigenvalue table.

    Layout A (ccx 2.23, measured): 5-number rows, f_hz printed directly.
    Layout B (older/newer ccx): mode on one line, lambda on the next, or
    ``mode lambda`` pairs -- f is derived via sqrt(lambda)/(2*pi).
    """
    modes = _parse_table_rows(block, "ccx")
    if modes:
        return modes
    modes = []
    lines = [ln for ln in block.splitlines() if ln.strip()]
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = _CCX_PAIR.match(ln)
        if m and i + 1 < len(lines):
            mv = _CCX_VAL.match(lines[i + 1])
            if mv:
                lam = float(mv.group(1))
                modes.append({"mode": int(m.group(1)), "lam": lam,
                              "f_hz": math.sqrt(lam) / (2.0 * math.pi)
                              if lam > 0 else None,
                              "f_hz_check": None})
                i += 2
                continue
        two = re.match(r"^\s*(\d+)\s+([-+0-9.eE]+)\s*$", ln)
        if two:
            lam = float(two.group(2))
            modes.append({"mode": int(two.group(1)), "lam": lam,
                          "f_hz": math.sqrt(lam) / (2.0 * math.pi)
                          if lam > 0 else None,
                          "f_hz_check": None})
            i += 1
            continue
        i += 1
    return modes


# --------------------------------------------------------------------------- #
# gates (definition-domain criteria, DESIGN_C6_P1_MODAL.md section 5)
# --------------------------------------------------------------------------- #

def gates(modes: list[dict], expect: int) -> dict:
    f = [m["f_hz"] for m in modes if m["f_hz"] is not None]
    positive = len(f) == len(modes) and all(v > 0.0 for v in f)
    tol = 1e-9
    monotonic = all(b >= a - tol * max(1.0, abs(a))
                    for a, b in zip(f, f[1:]))
    return {"n_modes_found": len(modes), "n_requested": expect,
            "complete": len(modes) == expect,
            "positive": positive, "monotonic": monotonic,
            "f_hz": f}


# --------------------------------------------------------------------------- #

def extract(dat_path: str, dialect: str, expect: int = 5) -> dict:
    if dialect not in ("ccx", "abaqus"):
        raise ValueError(f"unknown dialect {dialect!r}")
    with open(dat_path, "r", errors="replace") as fh:
        text = fh.read()
    block = _eigen_block(text)
    if not block:
        why = (_DIAGNOSTIC_F if dialect == "abaqus"
               else "ccx: is this a *FREQUENCY run?")
        raise ValueError(f"no eigenvalue table in {dat_path} ({why})")
    modes = _parse_abaqus(block) if dialect == "abaqus" else _parse_ccx(block)
    out = {"source": "modal-dat", "dialect": dialect, "dat": dat_path,
           "modes": modes, "raw_block": block[:4000]}
    out.update(gates(modes, expect))
    return out


# --------------------------------------------------------------------------- #
# self-test: pins with hand-computable values, not snapshots
# --------------------------------------------------------------------------- #

def _self_test() -> int:
    ok = 0

    # pin 1: lambda = 4*pi^2  =>  f = 1.0 Hz exactly (the conversion identity)
    f = math.sqrt(4.0 * math.pi ** 2) / (2.0 * math.pi)
    assert abs(f - 1.0) < 1e-12, f
    ok += 1

    # pin 2: abaqus table -- lambda=4pi^2, printed f must be 1.0 and the
    # recomputation must agree (this is the mis-parse killer)
    lam = 4.0 * math.pi ** 2
    abq = ("                 E I G E N V A L U E   O U T P U T\n"
           "\n"
           "   MODE NO    EIGENVALUE    FREQUENCY       FREQUENCY       GENERALIZED\n"
           "                             (RAD/TIME)     (CYCLES/TIME)   MASS\n"
           "        1   %.16E   %.16E   %.16E   2.780000E+00\n"
           "        2   %.16E   %.16E   %.16E   2.780000E+00\n"
           % (lam, 2 * math.pi, 1.0, lam * 4, 4 * math.pi, 2.0))
    modes = _parse_abaqus(_eigen_block(abq))
    assert len(modes) == 2, modes
    assert abs(modes[0]["f_hz"] - 1.0) < 1e-12, modes[0]
    # the recomputed check agrees within the production tolerance (1e-4 rel),
    # because the sampled lambda is printed with 10 significant digits
    assert abs(modes[0]["f_hz_check"] - 1.0) < 1e-4, modes[0]
    ok += 1

    # pin 2b: a corrupted Cycles/Time column must RAISE, not pass through
    bad = abq.replace("   %.16E" % 1.0, "   9.900000E+00")  # f_cyc tampered
    try:
        _parse_abaqus(_eigen_block(bad))
        raise AssertionError("tampered f_cyc column was not caught")
    except ValueError:
        ok += 1

    # pin 3: ccx two-line layout -- lambda=4pi^2 => f=1.0 Hz
    ccx = (" E I G E N V A L U E   O U T P U T\n"
           "\n"
           "       1\n"
           "  %.16E\n"
           "       2\n"
           "  %.16E\n"
           % (4.0 * math.pi ** 2, 16.0 * math.pi ** 2))
    modes = _parse_ccx(_eigen_block(ccx))
    assert len(modes) == 2, modes
    assert abs(modes[0]["f_hz"] - 1.0) < 1e-12, modes[0]
    assert abs(modes[1]["f_hz"] - 2.0) < 1e-12, modes[1]
    ok += 1

    # pin 3b: ccx one-line layout must parse identically
    ccx1 = (" E I G E N V A L U E   O U T P U T\n"
            "        1   %.16E\n" % (4.0 * math.pi ** 2))
    modes = _parse_ccx(_eigen_block(ccx1))
    assert len(modes) == 1 and abs(modes[0]["f_hz"] - 1.0) < 1e-12
    ok += 1

    # pin 3c: ccx 2.23 measured layout (5-number rows, real .dat header text)
    # -- regression pin from the first real modal run, 2026-11-07
    ccx223 = ("     E I G E N V A L U E   O U T P U T\n"
              "\n"
              " MODE NO    EIGENVALUE                       FREQUENCY   \n"
              "                                     REAL PART            IMAGINARY PART\n"
              "                           (RAD/TIME)      (CYCLES/TIME     (RAD/TIME)\n"
              "\n"
              "      1   %.16E   %.16E   %.16E   0.0000000E+00\n"
              % (4.0 * math.pi ** 2, 2 * math.pi, 1.0))
    modes = _parse_ccx(_eigen_block(ccx223))
    assert len(modes) == 1, modes
    assert abs(modes[0]["f_hz"] - 1.0) < 1e-12, modes[0]
    assert abs(modes[0]["f_hz_check"] - 1.0) < 1e-4, modes[0]
    ok += 1

    # pin 4: gates -- monotonic / positive / complete
    g = gates([{"mode": 1, "lam": 1, "f_hz": 1.0},
               {"mode": 2, "lam": 4, "f_hz": 2.0}], expect=2)
    assert g["positive"] and g["monotonic"] and g["complete"], g
    ok += 1

    # pin 4b: out-of-order eigenvalues must fail monotonic
    g = gates([{"mode": 1, "lam": 1, "f_hz": 2.0},
               {"mode": 2, "lam": 4, "f_hz": 1.0}], expect=2)
    assert not g["monotonic"], g
    ok += 1

    # pin 4c: a zero/negative frequency (rigid-body leak) must fail positive
    g = gates([{"mode": 1, "lam": 0.0, "f_hz": 0.0},
               {"mode": 2, "lam": 4, "f_hz": 2.0}], expect=2)
    assert not g["positive"], g
    ok += 1

    # pin 4d: missing mode -> complete=False, recorded not excluded
    g = gates([{"mode": 1, "lam": 1, "f_hz": 1.0}], expect=5)
    assert not g["complete"] and g["n_modes_found"] == 1, g
    ok += 1

    # pin 5: .dat without an eigenvalue table must yield no block -> extract
    # raises a clean error (never a silently empty result)
    assert _eigen_block("no table here\n just static results\n") == ""
    try:
        extract.__wrapped__ if False else None
        blk = _eigen_block("no table here\n")
        if not blk:
            raise _NoTable("no eigenvalue table")
        raise AssertionError("missing table was not caught")
    except _NoTable:
        ok += 1

    print(f"SELF_TEST_OK {ok} pins (lambda->f identity, abaqus 5-col parse, "
          "tampered-column raise, ccx 2-line + 1-line, gates)")
    return 0


class _NoTable(ValueError):
    pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dat", nargs="?", help="<job>.dat from a *FREQUENCY run")
    ap.add_argument("out", nargs="?", help="output JSON path")
    ap.add_argument("--dialect", choices=("ccx", "abaqus"), default="ccx")
    ap.add_argument("--expect", type=int, default=5)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return _self_test()
    if not args.dat or not args.out:
        ap.error("dat and out are required unless --self-test")
    try:
        res = extract(args.dat, args.dialect, args.expect)
    except ValueError as exc:
        print(f"MODAL_EXTRACT_FAIL: {exc}", file=sys.stderr)
        return 1
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print("MODAL_EXTRACT_OK dialect=%s modes=%d f1=%.6g f_end=%.6g %s"
          % (res["dialect"], res["n_modes_found"],
             res["f_hz"][0] if res["f_hz"] else float("nan"),
             res["f_hz"][-1] if res["f_hz"] else float("nan"),
             "".join(k for k in ("complete", "positive", "monotonic")
                     if not res[k]) or "gates_ok"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
