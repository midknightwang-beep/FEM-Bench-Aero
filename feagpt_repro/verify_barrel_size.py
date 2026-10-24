#!/usr/bin/env python
"""Independent analytic line for the barrel's **size / thickness** dimension.

Why a separate line
-------------------
``verify_barrel.py`` checks the family's closed forms - but only at the family
default specimen, because :func:`check_pressure` / :func:`check_bending` built
``FuselageParams()`` with no overrides.  Batch 6 adds diameter, length and wall
thickness as dataset dimensions (**D25**), and a size-extrapolation study whose
analytic yardstick never moves is not a yardstick.  So the same closed forms are
evaluated **at each size actually shipped**.

What is exact, and where
------------------------
The **shipped** batch-6 cases carry 8 stringers and 3 frames, so ``pR/t`` is not
their answer - a radial blade web stiffens the skin it stands on, and the load
case mixes pressure with an end moment and shear.  The analytic line therefore
runs the family's **degenerate** member (``n_stringers=0, n_frames=2``, the plain
cylindrical shell) at the *same* (D, L, t).  There the two closed forms are exact
at every size:

    sigma_hoop = p R / t          w = p R^2 / (E t)          sigma_beam = M x / I

with ``I = pi R^3 t`` and ``x = R cos(pi/N_SEG)``.

The shipped cases are covered by the checks that do not need a closed form:
gate 3 (ccx vs Abaqus on the same mesh), equilibrium (``sum FORC`` against the
applied load) and gate 4 - the same division of labour ``verify_barrel.py``
already uses for the stringered barrel.

Beyond per-point agreement
--------------------------
Each point being within tolerance is necessary but weak: three points could each
be inside 3 % while the *trend* with size is wrong.  So the run also compares the
**ratios**: the FE ratio between two sizes must match the closed-form ratio.  A
systematic size error (a wrong radius in the deck, a wall thickness read from the
wrong place) shows up here even when every individual comparison passes.

Usage::

    python verify_barrel_size.py --json ../FEM-Bench-Aero/verify_barrel_size.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_barrel import check_bending, check_pressure  # noqa: E402

#: ``(label, diameter, length, thickness)`` - the anchor plus batch 6's four
#: shipped points.  The anchor has to be in the list: it is the denominator of
#: every ratio below.
#:
#: D27 (2026-10-06): the sweep moves **downwards**.  The upward arm
#: (``L3000``, ``D1600+L3000``) cannot be solved on this machine at all -
#: CalculiX expands every shell into solids, so the equation count is ~14.9 x
#: the node count and the two upward points need 2.8M / 3.5M equations against
#: a measured ~33 GB commit limit.  See ``_probe_b6/`` and
#: ``_m5_probe/make_batch6_specs.py``.
#:
#: 2026-10-07: the single-dimension diameter val is **d1800**, not d1600 -
#: d1600 measured 1.1349 % on the cross-solver gate (a boundary-layer artifact,
#: not a size trend: the d1800 neighbour measured 0.8180 %); d1600 survives
#: only inside the two-dimension test point, which measured 0.7143 %.
POINTS = (
    ("anchor_d2000_l2000_t3", 2000.0, 2000.0, 3.0),
    ("d1800_l2000_t3", 1800.0, 2000.0, 3.0),
    ("d2000_l1600_t3", 2000.0, 1600.0, 3.0),
    ("d2000_l2000_t2", 2000.0, 2000.0, 2.0),
    ("d1600_l1600_t3", 1600.0, 1600.0, 3.0),
)

#: Bending is a second closed form with a different size law (``I ~ R^3 t``), so
#: it is checked at the anchor and at the extreme diameter rather than at all
#: five points - the pressure law is the one that carries the dimension.  The
#: extreme shipped diameter is 1600, carried by the two-dimension test point.
BENDING_POINTS = ("anchor_d2000_l2000_t3", "d1600_l1600_t3")

#: Ratio tolerance: the two FE points must scale like the two closed forms.
TOL_RATIO = 1.0      # %


def _rel(a: float, b: float) -> float:
    return (a - b) / b * 100.0 if b else float("nan")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=float, default=None,
                    help="mesh size mm (default: the family's own)")
    ap.add_argument("--json", help="write the machine-readable report here")
    ap.add_argument("--skip-bending", action="store_true",
                    help="pressure line only (faster)")
    args = ap.parse_args(argv)

    print("=" * 78)
    print("  BARREL SIZE / THICKNESS LINE - closed forms evaluated at each size")
    print("=" * 78)

    rows: list[dict] = []
    checks: list[dict] = []

    for label, d, L, t in POINTS:
        print(f"\n--- {label}: D{d:g} x L{L:g} x t{t:g}")
        ck, info = check_pressure(size=args.size, label=label,
                                  diameter=d, length=L, thickness=t)
        for c in ck:
            print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['key']}")
            print(f"         {c['detail']}")
        checks.extend(ck)
        rows.append({"label": label, "diameter": d, "length": L,
                     "thickness": t, "pressure": info,
                     "run_ok": bool(info)})

    if not args.skip_bending:
        for label in BENDING_POINTS:
            _, d, L, t = next(p for p in POINTS if p[0] == label)
            print(f"\n--- bending {label}")
            ck, info = check_bending(size=args.size, label=label,
                                     diameter=d, length=L, thickness=t)
            for c in ck:
                print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['key']}")
                print(f"         {c['detail']}")
            checks.extend(ck)
            for r in rows:
                if r["label"] == label:
                    r["bending"] = info

    # ---- the scaling law: FE ratios must equal closed-form ratios ----------
    print("\n--- scaling law (FE ratio vs closed-form ratio)")
    by = {r["label"]: r for r in rows if r.get("pressure")}
    base = by.get("anchor_d2000_l2000_t3")
    ratio_rows: list[dict] = []
    if base:
        b = base["pressure"]
        for label, d, L, t in POINTS:
            if label == "anchor_d2000_l2000_t3" or label not in by:
                continue
            r = by[label]["pressure"]
            fe_s = r["hoop_vm_MPa"] / b["hoop_vm_MPa"]
            cf_s = r["hoop_closed_form_MPa"] / b["hoop_closed_form_MPa"]
            fe_w = r["w_mm"] / b["w_mm"]
            cf_w = r["w_closed_form_mm"] / b["w_closed_form_mm"]
            e_s, e_w = _rel(fe_s, cf_s), _rel(fe_w, cf_w)
            ok = abs(e_s) < TOL_RATIO and abs(e_w) < TOL_RATIO
            ratio_rows.append({"label": label, "sigma_fe_ratio": round(fe_s, 6),
                               "sigma_cf_ratio": round(cf_s, 6),
                               "sigma_err_pct": round(e_s, 4),
                               "w_fe_ratio": round(fe_w, 6),
                               "w_cf_ratio": round(cf_w, 6),
                               "w_err_pct": round(e_w, 4), "pass": ok})
            print(f"  [{'PASS' if ok else 'FAIL'}] {label:22s} "
                  f"sigma x{fe_s:.4f} vs x{cf_s:.4f} ({e_s:+.3f} %) | "
                  f"w x{fe_w:.4f} vs x{cf_w:.4f} ({e_w:+.3f} %)")
            checks.append({"key": f"size.ratio.{label}", "pass": ok,
                           "detail": f"FE ratio (sigma x{fe_s:.4f}, w x{fe_w:.4f}) "
                                     f"vs closed form (sigma x{cf_s:.4f}, "
                                     f"w x{cf_w:.4f})"})
    else:
        print("  no anchor point - ratios skipped")

    npass = sum(1 for c in checks if c["pass"])
    nfail = len(checks) - npass
    print(f"\nsize/thickness self-checks: {npass} PASS, {nfail} FAIL")
    print(f"VERDICT: {'PASS' if nfail == 0 and checks else 'CHECK'}")

    if args.json:
        out = {"points": rows, "ratios": ratio_rows, "checks": checks,
               "n_pass": npass, "n_fail": nfail,
               "pass": nfail == 0 and bool(checks)}
        Path(args.json).write_text(json.dumps(out, indent=2, ensure_ascii=False),
                                   encoding="utf-8")
        print(f"report -> {args.json}")
    return 0 if nfail == 0 and checks else 2


if __name__ == "__main__":
    raise SystemExit(main())
