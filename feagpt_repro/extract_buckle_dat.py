"""Parse linear-buckling eigenvalues from ccx / Abaqus .dat files (C6-P2).

Real-machine layouts measured 2026-11-07/08 (both on the SAME barrel spec,
external pressure 0.1 MPa):

ccx 2.23 (.dat)::

         B U C K L I N G   F A C T O R   O U T P U T
     MODE NO       BUCKLING
                    FACTOR
          1   0.1008207E+01
          2   0.1009420E+01

Abaqus 2026 (.dat)::

                              E I G E N V A L U E    O U T P U T
 BUCKLING LOAD ESTIMATE = ("DEAD" LOADS) + EIGENVALUE * ("LIVE" LOADS).
          "DEAD" LOADS = TOTAL LOAD BEFORE  *BUCKLE STEP.
          "LIVE" LOADS = INCREMENTAL LOAD IN *BUCKLE STEP
 MODE NO      EIGENVALUE
       1      0.68716
       2      0.68716

NOTE: repeated eigenvalues are PHYSICAL (axisymmetric shells have paired
modes).  The spectrum check is therefore NON-DECREASING, not strictly
increasing -- the P1 frequency extractor's monotonic rule must not be copied
here.  Columns are whitespace-separated; a banner may appear before the real
table, so the parser anchors on the dialect-specific banner, not on the first
"MODE NO" in the file.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# banners are spread-out letter by letter, so match the tokens, not the string
_BANNER = {
    "ccx": re.compile(r"B\s*U\s*C\s*K\s*L\s*I\s*N\s*G\s+F\s*A\s*C\s*T\s*O\s*R\s+O\s*U\s*T\s*P\s*U\s*T"),
    "abaqus": re.compile(r"E\s*I\s*G\s*E\s*N\s*V\s*A\s*L\s*U\s*E\s+O\s*U\s*T\s*P\s*U\s*T"),
}
_MODE_HEADER = re.compile(r"^\s*MODE\s+NO\b", re.IGNORECASE)
_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[EeDd][-+]?\d+)?"
_ROW = re.compile(rf"^\s*(\d+)\s+({_NUM})\s*$")


def _parse(text: str, dialect: str) -> list[dict]:
    if dialect not in _BANNER:
        raise ValueError(f"unknown dialect {dialect!r}; expected one of {sorted(_BANNER)}")
    lines = text.splitlines()
    banner_idx = None
    for i, line in enumerate(lines):
        if _BANNER[dialect].search(line):
            banner_idx = i
            break
    if banner_idx is None:
        raise ValueError(f"no {dialect} buckling/eigenvalue OUTPUT banner found in .dat")

    header_idx = None
    for i in range(banner_idx + 1, len(lines)):
        if _MODE_HEADER.match(lines[i]):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("MODE NO header not found after the banner")

    modes: list[dict] = []
    for line in lines[header_idx + 1:]:
        m = _ROW.match(line)
        if m:
            idx = int(m.group(1))
            val = float(m.group(2).replace("D", "E").replace("d", "e"))
            modes.append({"mode": idx, "lambda": val, "f_hz": None})
            continue
        # a blank line before the first row is part of the header; a blank line
        # AFTER rows ends the table (Abaqus prints blank separators then prose)
        if modes and line.strip():
            break
    if not modes:
        raise ValueError("banner/header found but no eigenvalue data rows")
    return modes


def parse_ccx_text(text: str) -> list[dict]:
    return _parse(text, "ccx")


def parse_abaqus_text(text: str) -> list[dict]:
    return _parse(text, "abaqus")


_MSG_VAL = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[EeDd][-+]?\d+)?")


def parse_abaqus_msg(text: str) -> list[float]:
    """Full-precision eigenvalues from the last ACCEPTED EIGENVALUES block.

    Expert review FBA-C6P2-REV-001-EX01: the .dat table is rounded to 5
    decimals (two modes both print 0.68716), while .msg prints
    ``6.87155e-01  6.87161e-01  6.97166e-01``.  Use .msg for values; keep
    .dat only as a display/ordering check.
    """
    lines = text.splitlines()
    blocks = [i for i, x in enumerate(lines)
              if x.strip().upper() == "ACCEPTED EIGENVALUES"]
    if not blocks:
        raise ValueError("no ACCEPTED EIGENVALUES block in .msg")
    start = blocks[-1] + 1
    vals: list[float] = []
    for line in lines[start:]:
        s = line.strip()
        if not s:
            if vals:
                break
            continue
        nums = _MSG_VAL.findall(s)
        if not nums:
            break
        vals.extend(float(n.replace("D", "E").replace("d", "e")) for n in nums)
    if not vals:
        raise ValueError("ACCEPTED EIGENVALUES block has no numeric rows")
    return vals


def extract(path: str | Path, dialect: str, expect: int | None = None) -> dict:
    """Parse a .dat file into a dict (same shape convention as extract_modal_dat).

    Abaqus: if a sibling .msg exists, its full-precision eigenvalues replace
    the rounded .dat values (same order, first n modes).  ``precision`` says
    which source was used -- never silently treat a rounded .dat as exact.
    """
    dat = Path(path)
    text = dat.read_text(encoding="utf-8", errors="replace")
    modes = _parse(text, dialect)
    lambdas = [m["lambda"] for m in modes]
    precision = "dat (rounded)"
    msg_vals: list[float] = []
    if dialect == "abaqus":
        msg = dat.with_suffix(".msg")
        if msg.exists():
            try:
                msg_vals = parse_abaqus_msg(msg.read_text(encoding="utf-8", errors="replace"))
                lambdas = msg_vals[:len(modes)]
                for m, v in zip(modes, lambdas):
                    m["lambda"] = v
                precision = "msg (full precision)"
            except ValueError:
                pass
    seq_ok = [m["mode"] for m in modes] == list(range(1, len(modes) + 1))
    positive = all(x > 0 for x in lambdas)
    # repeated eigenvalues are physical; use a TOLERANCE, not >= on raw floats:
    # near-repeated roots (0.687155 / 0.687161) must not be flagged as noise,
    # and a tiny negative rounding drift must not be flagged as descending.
    tol = 1e-6
    nondecreasing = all(b >= a - tol * max(1.0, abs(a))
                        for a, b in zip(lambdas, lambdas[1:]))
    complete = (expect is None or len(modes) == expect) and seq_ok
    return {"dialect": dialect, "n_modes_found": len(modes),
            "modes": modes, "lambdas": lambdas,
            "positive": positive, "nondecreasing": nondecreasing,
            "complete": complete, "precision": precision,
            "msg_full_spectrum": msg_vals or None}


# --------------------------------------------------------------------------- #
# self-test: real-machine excerpts (verbatim) + both-direction mutations
# --------------------------------------------------------------------------- #
_CCX_REAL = """                            S T E P       1

         B U C K L I N G   F A C T O R   O U T P U T

     MODE NO       BUCKLING
                    FACTOR

          1   0.1008207E+01
          2   0.1009420E+01
"""
_ABQ_REAL = """                              E I G E N V A L U E    O U T P U T

 BUCKLING LOAD ESTIMATE = ("DEAD" LOADS) + EIGENVALUE * ("LIVE" LOADS).
          "DEAD" LOADS = TOTAL LOAD BEFORE  *BUCKLE STEP.
          "LIVE" LOADS = INCREMENTAL LOAD IN *BUCKLE STEP


 MODE NO      EIGENVALUE


       1      0.68716
       2      0.68716


          THE ANALYSIS HAS BEEN COMPLETED
"""
# verbatim .msg block from the real-machine job (expert review EX01)
_ABQ_MSG_REAL = """ NUMBER OF ACCEPTED EIGENVALUES    3

 ACCEPTED EIGENVALUES
   6.87155e-01  6.87161e-01  6.97166e-01

 FACTORIZATION WITH NEW SHIFT VALUE IS REQUIRED
"""


def self_test() -> int:
    ok = 0
    total = 17

    def pin(name: str, cond: bool) -> None:
        nonlocal ok
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")
        ok += cond

    c = _parse(_CCX_REAL, "ccx")
    a = _parse(_ABQ_REAL, "abaqus")
    pin("ccx real excerpt: 2 rows", len(c) == 2)
    pin("ccx real values", abs(c[0]["lambda"] - 1.008207) < 1e-9
        and abs(c[1]["lambda"] - 1.009420) < 1e-9)
    pin("abaqus real excerpt: 2 rows", len(a) == 2)
    # .dat values are ROUNDED to 5 decimals; do NOT use == for root equality
    pin("abaqus .dat rounded values (near-repeated, tolerance)",
        abs(a[0]["lambda"] - 0.68716) < 1e-9
        and abs(a[0]["lambda"] - a[1]["lambda"])
        <= 1e-6 * max(1.0, abs(a[0]["lambda"])))
    pin("repeated root is NOT flagged as non-monotonic",
        extract_from_text(_ABQ_REAL, "abaqus")["nondecreasing"] is True)
    pin("ccx scientific notation parsed", c[0]["lambda"] > 1.0)

    # EX01 P0-5: full precision comes from .msg, not the rounded .dat
    full = parse_abaqus_msg(_ABQ_MSG_REAL)
    pin("msg full-precision 3 values", len(full) == 3
        and abs(full[0] - 0.687155) < 1e-9
        and abs(full[1] - 0.687161) < 1e-9
        and abs(full[2] - 0.697166) < 1e-9)
    pin("msg values differ from .dat rounding",
        full[0] != a[0]["lambda"] and full[1] != a[1]["lambda"])
    pin("near-repeated roots are distinct in msg",
        full[0] != full[1] and abs(full[0] - full[1]) < 1e-4)
    pin("near-repeated roots pass tolerance check",
        extract_from_text(_ABQ_REAL, "abaqus")["nondecreasing"] is True
        and full[1] >= full[0] - 1e-6 * max(1.0, abs(full[0])))
    pin("msg block with no numeric rows raises",
        raises(lambda: parse_abaqus_msg("ACCEPTED EIGENVALUES\n\n text")))

    # mutations, both directions
    neg = _ABQ_REAL.replace("       1      0.68716", "       1      -0.68716")
    pin("negative lambda caught", extract_from_text(neg, "abaqus")["positive"] is False)
    short = _CCX_REAL.replace("          2   0.1009420E+01\n", "")
    pin("missing mode caught", extract_from_text(short, "ccx", expect=2)["complete"] is False)
    drop = _ABQ_REAL.replace("       1      0.68716", "       1      1.5").replace(
        "       2      0.68716", "       2      0.2")
    pin("descending spectrum caught",
        extract_from_text(drop, "abaqus")["nondecreasing"] is False)
    pin("prose before banner does not fool the parser",
        len(_parse("some header text with 1 2.5\n" + _CCX_REAL, "ccx")) == 2)
    pin("no banner raises", raises(lambda: _parse("random text", "abaqus")))
    pin("unknown dialect raises", raises(lambda: _parse(_CCX_REAL, "ansys")))
    print(f"self-test {ok}/{total}")
    return 0 if ok == total else 1


def extract_from_text(text: str, dialect: str, expect: int | None = None) -> dict:
    """Pure-function variant of extract() for self-test pins."""
    modes = _parse(text, dialect)
    lam = [m["lambda"] for m in modes]
    tol = 1e-6
    return {"n_modes_found": len(modes), "lambdas": lam,
            "positive": all(x > 0 for x in lam),
            "nondecreasing": all(b >= a - tol * max(1.0, abs(a))
                                 for a, b in zip(lam, lam[1:])),
            "complete": (expect is None or len(modes) == expect)
                        and [m["mode"] for m in modes] == list(range(1, len(modes) + 1))}


def raises(fn) -> bool:
    try:
        fn()
        return False
    except Exception:
        return True


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("dat", nargs="?", help=".dat file to parse")
    ap.add_argument("--dialect", choices=sorted(_BANNER), default="ccx")
    ap.add_argument("--expect", type=int, default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.dat:
        ap.error("need a .dat path (or --self-test)")
    print(json.dumps(extract(args.dat, args.dialect, args.expect),
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
