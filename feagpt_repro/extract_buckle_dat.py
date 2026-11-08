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


def extract(path: str | Path, dialect: str, expect: int | None = None) -> dict:
    """Parse a .dat file into a dict (same shape convention as extract_modal_dat)."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    modes = _parse(text, dialect)
    lambdas = [m["lambda"] for m in modes]
    seq_ok = [m["mode"] for m in modes] == list(range(1, len(modes) + 1))
    positive = all(x > 0 for x in lambdas)
    # repeated eigenvalues are physical -> non-decreasing, NOT strictly increasing
    nondecreasing = all(b >= a for a, b in zip(lambdas, lambdas[1:]))
    complete = (expect is None or len(modes) == expect) and seq_ok
    return {"dialect": dialect, "n_modes_found": len(modes),
            "modes": modes, "lambdas": lambdas,
            "positive": positive, "nondecreasing": nondecreasing,
            "complete": complete}


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


def self_test() -> int:
    ok = 0
    total = 12

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
    pin("abaqus real values (repeated root)", abs(a[0]["lambda"] - 0.68716) < 1e-9
        and a[0]["lambda"] == a[1]["lambda"])
    pin("repeated root is NOT flagged as non-monotonic",
        extract_from_text(_ABQ_REAL, "abaqus")["nondecreasing"] is True)
    pin("ccx scientific notation parsed", c[0]["lambda"] > 1.0)

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
    return {"n_modes_found": len(modes), "lambdas": lam,
            "positive": all(x > 0 for x in lam),
            "nondecreasing": all(b >= a for a, b in zip(lam, lam[1:])),
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
