"""Generate the C6-P1 modal pilot cases into FEM-Bench-Aero/modeling_v2/.

Design: FEM-Bench-Aero/DESIGN_C6_P1_MODAL.md (decided 2026-11-07).
v1.1 data is READ ONLY -- nothing under ``modeling/`` is ever written.

Each pilot case = a v1.1 wing-box spec with ``analysis.step_type`` switched to
``"frequency"`` (n_modes defaults to 5) and the name suffixed ``_modal``.
The mesh layer is bit-for-bit the same parametrization as v1.1 (single
variable = step type, R-A1); only the deck's step section changes.

Per case the script produces::

    modeling_v2/<name>_modal/
        <name>_modal.spec.json      # the full v2 spec (self-describing)
        <name>_modal.step           # geometry (same params as v1.1)
        <name>_modal.msh            # mesh (same params as v1.1)
        <name>_modal.inp            # ccx deck (*FREQUENCY, SOLVER=ARPACK)
        <name>_modal_abq.inp        # abaqus deck (*FREQUENCY, EIGENSOLVER=LANCZOS)

Usage (project venv -- gmsh lives there, R60)::

    python make_v2_modal_cases.py --deck        # generate 8 cases (no solve)
    python make_v2_modal_cases.py --solve-ccx   # run the 8 ccx decks (R61 lock)
    python make_v2_modal_cases.py --extract     # parse .dat -> .modal.json
    python make_v2_modal_cases.py --summary     # ccx-side table -> verify json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from feagpt.spec import FEASpec          # noqa: E402
from feagpt import pipeline, solver      # noqa: E402
from extract_modal_dat import extract    # noqa: E402

_ROOT = _HERE.parent                      # F:\AI FEA Modeling DataSets
_V11 = _ROOT / "FEM-Bench-Aero" / "modeling"
_V2 = _ROOT / "FEM-Bench-Aero" / "modeling_v2"

#: design doc section 2 -- baseline + seven single-variable axes.
#: (v1.1 case name,) -> v2 name is <case>_modal by convention.
CASES = [
    "naca4412_wingbox",
    "naca4412_wingbox_size_span2400",
    "naca4412_wingbox_n_ribs5_chord800",
    "naca4412_wingbox_size_skin2",
    "naca4412_wingbox_str3",
    "naca4412_wingbox_sweep20",
    "naca4412_wingbox_taper060",
    "naca4412_wingbox_web1",
]

N_MODES = 5


def v2_name(v11_name: str) -> str:
    return f"{v11_name}_modal"


def make_decks(v11_name: str) -> Path:
    """One case: v1.1 spec -> frequency spec -> ccx deck + abaqus deck."""
    src = _V11 / v11_name / "spec.json"
    if not src.exists():
        raise SystemExit(f"v1.1 spec missing: {src}")
    spec = FEASpec.from_json(src)
    spec.name = v2_name(v11_name)
    spec.analysis.step_type = "frequency"
    spec.analysis.n_modes = N_MODES

    outdir = _V2 / spec.name
    outdir.mkdir(parents=True, exist_ok=True)

    # ccx deck + mesh + step, written straight into the v2 case dir
    res = pipeline.run(spec, outdir=outdir, step_export=True, deck_only=True,
                       solver_name="ccx")
    ccx_deck = Path(res.artifacts["inp"])
    assert ccx_deck.exists() and ccx_deck.stat().st_size > 0

    # abaqus deck: same mesh, different dialect.  pipeline always names the
    # deck <spec.name>.inp, so build it in a scratch dir and move it over as
    # <name>_abq.inp (no silent overwrite of the ccx deck).
    with tempfile.TemporaryDirectory(prefix="v2_abq_deck_") as td:
        res_a = pipeline.run(spec, outdir=td, step_export=False, deck_only=True,
                             solver_name="abaqus")
        abq_deck = Path(res_a.artifacts["inp"])
        dest = outdir / f"{spec.name}_abq.inp"
        shutil.copyfile(abq_deck, dest)

    # the deck must say FREQUENCY and must NOT say STATIC -- the whole point
    # of the pilot, checked at the source instead of by faith
    for deck in (ccx_deck, dest):
        txt = deck.read_text(encoding="utf-8")
        assert "*FREQUENCY" in txt, f"{deck}: no *FREQUENCY"
        assert "*STATIC" not in txt, f"{deck}: *STATIC leaked into modal deck"
    print(f"[deck] {spec.name}: ccx {ccx_deck.stat().st_size} B, "
          f"abq {dest.stat().st_size} B")
    return outdir


def solve_ccx(v11_name: str) -> dict:
    """Run the ccx deck (R61 global lock inside solver.run); extract .dat."""
    name = v2_name(v11_name)
    outdir = _V2 / name
    deck = outdir / f"{name}.inp"
    t0 = time.time()
    res = solver.run(deck, solver="ccx", timeout=1800)
    row = {"case": name, "dialect": "ccx",
           "solve_seconds": round(time.time() - t0, 1),
           "rc": res.returncode, "frd": bool(res.frd), "dat": bool(res.dat)}
    if not res.ok:
        row["state"] = "solve_failed"
        row["log_tail"] = (res.log or "")[-500:]
        return row
    dat = outdir / f"{name}.dat"
    try:
        mres = extract(str(dat), "ccx", expect=N_MODES)
    except ValueError as exc:
        row["state"] = "extract_failed"
        row["error"] = str(exc)
        return row
    out_json = outdir / f"{name}.modal.json"
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(mres, fh, ensure_ascii=False, indent=1)
    row["state"] = "ok" if (mres["positive"] and mres["monotonic"]
                            and mres["complete"]) else "gate_failed"
    row["f_hz"] = mres["f_hz"]
    row["n_modes_found"] = mres["n_modes_found"]
    return row


def summary() -> int:
    rows = []
    for v11_name in CASES:
        p = _V2 / v2_name(v11_name) / f"{v2_name(v11_name)}.modal.json"
        if not p.exists():
            rows.append({"case": v2_name(v11_name), "state": "missing"})
            continue
        m = json.loads(p.read_text(encoding="utf-8"))
        rows.append({"case": m["dialect"] and v2_name(v11_name),
                     "dialect": m["dialect"],
                     "state": "ok" if (m["positive"] and m["monotonic"]
                                       and m["complete"]) else "gate_failed",
                     "f_hz": m["f_hz"],
                     "n_modes_found": m["n_modes_found"]})
    out = {"volume": "modeling_v2 (C6-P1 modal pilot)", "dialect": "ccx",
           "n_cases": len(CASES), "n_modes": N_MODES,
           "n_ok": sum(1 for r in rows if r.get("state") == "ok"),
           "rows": rows}
    dest = _V2 / "verify_v2_p1_ccx.json"
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"summary -> {dest}")
    return 0 if out["n_ok"] == len(CASES) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--deck", action="store_true", help="generate 8 cases")
    ap.add_argument("--solve-ccx", action="store_true",
                    help="run ccx on all 8 (serial, R61 lock)")
    ap.add_argument("--extract", action="store_true",
                    help="parse .dat files (done by --solve-ccx too)")
    ap.add_argument("--summary", action="store_true",
                    help="write verify_v2_p1_ccx.json from .modal.json files")
    ap.add_argument("--only", help="comma-separated v1.1 case subset")
    ap.add_argument("--n-modes", type=int, default=5,
                    help="eigenvalue count (default 5 = pilot; 10 = "
                         "mode-pairing re-test, open item 2026-11-07)")
    args = ap.parse_args(argv)
    global N_MODES
    if args.n_modes != 5:
        N_MODES = args.n_modes
    if not (args.deck or args.solve_ccx or args.extract or args.summary):
        ap.error("pick an action: --deck / --solve-ccx / --extract / --summary")
    cases = CASES
    if args.only:
        want = {w.strip() for w in args.only.split(",") if w.strip()}
        missing = want - set(CASES)
        if missing:
            ap.error(f"unknown cases: {sorted(missing)}")
        cases = [c for c in CASES if c in want]

    if args.deck:
        for c in cases:
            make_decks(c)
    if args.solve_ccx:
        bad = []
        for c in cases:
            row = solve_ccx(c)
            f_hz = row.get("f_hz") or []
            print(f"[solve] {row['case']}: {row.get('state')} "
                  f"f1={f_hz[0] if f_hz else None}")
            if row.get("state") != "ok":
                bad.append(row["case"])
        if args.summary or True:  # summary is cheap; always refresh it
            rc = summary()
        return 1 if bad else rc
    if args.extract:
        for c in cases:
            name = v2_name(c)
            dat = _V2 / name / f"{name}.dat"
            mres = extract(str(dat), "ccx", expect=N_MODES)
            (_V2 / name / f"{name}.modal.json").write_text(
                json.dumps(mres, ensure_ascii=False, indent=1),
                encoding="utf-8")
            f_hz = mres["f_hz"] or []
            print(f"[extract] {name}: {mres['n_modes_found']} modes, "
                  f"f1={f_hz[0]:.4g} Hz" if f_hz else
                  f"[extract] {name}: 0 modes")
    if args.summary:
        return summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
