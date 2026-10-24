#!/usr/bin/env python
"""M11 / D34 - what the quadratic sweep term *cannot* fix, and why.

``verify_quad`` shows the form change moving ``planform_out`` from 25.70 % to
15.70 %.  A 15.70 % residual on the 40 deg + taper 0.4 corner is still the
largest number in the table, so the useful question is not "is quad better" but
"what is left".  This script answers it structurally.

The claim to test
-----------------
The sweep main effect and the sweep x taper interaction are two different
things.  A column for the interaction is ``s^2 * (taper - 1)`` -- non-zero only
on rows that have **both** sweep > 0 **and** taper != 1.  If train contains no
such row, that column is identically zero on train: the interaction is not
"poorly estimated", it is *unestimable*, and no change of basis can fix it.
Adding samples is then the only lever.

So the script counts those rows per split, and prints the residual of the chosen
form on every sweep>0 row grouped by the same criterion.  The expectation is a
clean split: taper-neutral rows land within a few percent, taper-off rows do
not, and the two taper-off rows are exactly the ones no train row resembles.

Usage::

    python _probe_m11/residual_diag.py

Writes ``residual_diag.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPRO = HERE.parent
sys.path.insert(0, str(REPRO))
sys.path.insert(0, str(HERE))

import baseline as B  # noqa: E402
import sweep_form as S  # noqa: E402

def _out_path() -> Path:
    """Output path, overridable so a re-run cannot silently clobber an archive.

    This script's *conclusion depends on the dataset*: it reports whether train
    holds rows that could estimate the interaction.  D34 ran it when the answer
    was "zero rows"; D35 changed the dataset, so the same command now answers
    "two rows".  Writing both to ``residual_diag.json`` would overwrite the D34
    evidence with a different fact and make the milestone record unreadable
    after the fact -- which is exactly what happened once.  Hence the default is
    a dated-by-caller name and never the archived one.
    """
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--out" and i + 1 < len(args):
            return HERE / args[i + 1]
        if a.startswith("--out="):
            return HERE / a.split("=", 1)[1]
    return HERE / "residual_diag_rerun.json"


OUT = _out_path()


def main() -> int:
    rows = B.load_family("wingbox")
    tr = [r for r in rows if r["split"] == "train"]
    va = [r for r in rows if r["split"] == "val"]
    te = [r for r in rows if r["split"] == "test"]

    print("=" * 92)
    print("  M11 / D34  what the quadratic sweep term cannot fix")
    print("=" * 92)

    # ---- 1. structural count --------------------------------------------- #
    def is_off(r):
        return r["sweep"] > 0 and abs(r["taper"] - 1.0) > 1e-9

    cnt = {}
    for name, part in (("train", tr), ("val", va), ("test", te)):
        cnt[name] = {
            "n": len(part),
            "sweep_gt0": sum(1 for r in part if r["sweep"] > 0),
            "sweep_gt0_and_taper_off": sum(1 for r in part if is_off(r)),
        }
    print()
    print("  [1] rows that can carry a sweep x taper interaction")
    print(f"    {'split':7s}{'n':>4s}{'sweep>0':>10s}{'sweep>0 & taper!=1':>21s}")
    for k, v in cnt.items():
        print(f"    {k:7s}{v['n']:4d}{v['sweep_gt0']:10d}{v['sweep_gt0_and_taper_off']:21d}")
    unidentifiable = cnt["train"]["sweep_gt0_and_taper_off"] == 0
    print(f"    => interaction column (s^2 * (taper-1)) is identically zero on "
          f"train: {unidentifiable}")

    # ---- 2. residual of the chosen form on every sweep>0 row -------------- #
    pf, info = S.fit(tr, "max_disp", "quad", hybrid=True)
    print()
    print(f"  [2] quad@phys residual, max_disp, every row with sweep>0")
    print(f"    {'case':42s}{'split':7s}{'sweep':>7s}{'taper':>7s}{'APE%':>9s}")
    recs = []
    for name, part in (("train", tr), ("val", va), ("test", te)):
        sw = [r for r in part if r["sweep"] > 0]
        if not sw:
            continue
        pred = pf(sw)
        for p, r in zip(pred, sw):
            a = (p - r["max_disp"]) / r["max_disp"] * 100
            recs.append({"case_id": r["case_id"], "split": name, "sweep": r["sweep"],
                         "taper": r["taper"], "ape_pct": round(a, 3),
                         "taper_off": is_off(r)})
            print(f"    {r['case_id']:42s}{name:7s}{r['sweep']:7.1f}{r['taper']:7.2f}{a:9.2f}")

    neutral = [abs(x["ape_pct"]) for x in recs
               if x["split"] != "train" and not x["taper_off"]]
    offd = [abs(x["ape_pct"]) for x in recs
            if x["split"] != "train" and x["taper_off"]]
    print()
    print(f"    held-out, taper neutral : {[round(a,2) for a in neutral]}  "
          f"max {max(neutral) if neutral else float('nan'):.2f} %")
    print(f"    held-out, taper != 1    : {[round(a,2) for a in offd]}  "
          f"max {max(offd) if offd else float('nan'):.2f} %")

    n_tr_inter = cnt["train"]["sweep_gt0_and_taper_off"]
    claim = ("the residual at the taper-off sweep corners is a sweep x taper "
             "interaction, and that interaction, not the sweep basis, is what "
             "remains -- "
             + ("it is structurally unestimable on this train set"
                if unidentifiable else
                f"train now holds {n_tr_inter} rows that can estimate it (D35), "
                "so it is estimable; whether it is also *extrapolable* is a "
                "separate question, measured in _probe_m12/interaction_feature"))
    doc = {
        "generated": "2026-10-24",
        "milestone": "M11 / D34 residual diagnosis",
        "claim": claim,
        "interaction_columns": cnt,
        "interaction_identifiable": not unidentifiable,
        "quad_phys_info": info,
        "residuals": recs,
        "held_out_taper_neutral_abs_pct": sorted(round(a, 3) for a in neutral),
        "held_out_taper_off_abs_pct": sorted(round(a, 3) for a in offd),
        "verdict": "PASS" if unidentifiable else "CHECK",
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print()
    print("  CONCLUSION")
    print(f"    sweep main effect  : fixed by the quadratic basis "
          f"(taper-neutral held-out max |APE| {max(neutral) if neutral else float('nan'):.2f} %)")
    print(f"    sweep x taper      : train has {n_tr_inter} rows that could "
          f"estimate it => "
          + ("unestimable, needs a *sample*, not a basis"
             if unidentifiable else
             f"ESTIMABLE since D35 (0 -> {n_tr_inter} rows)"))
    print(f"  wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
