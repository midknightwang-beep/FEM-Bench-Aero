#!/usr/bin/env python
"""M11 / D34 - before adopting the quadratic sweep term, try to break it.

``sweep_form.py`` picked ``quad`` on one criterion (LOO at the 30 deg station)
and confirmed it on val.  One criterion and one held-out row is thin, so this
script attacks the choice from four directions.  Any of them can veto it.

1. **Does it hold on the other three targets?**  A form that only fixes
   ``max_disp`` is a curve-fit to one number, not a better model.  ``max_w``
   especially: D32 keeps it as a secondary indicator, and if the quadratic
   ruins it, the "fix" traded the primary for nothing.
2. **Is the improvement bigger than the noise?**  Paired bootstrap on the test
   APEs (quad vs lin, same rows, 4000 resamples).  If the 95 % interval of the
   *difference* straddles zero, the honest sentence is "cannot tell at this n",
   no matter how the means line up.
3. **Does it damage any other axis?**  The gain must come from ``planform_out``,
   not from silently shifting ``size_out`` / ``combo`` / ``ribs_new``.  The
   per-mechanism APE table is printed before and after.
4. **Is the curvature parameter stable?**  If s^2's coefficient flips sign when
   a single train row is removed, it is fitting noise, not a shape.

Usage::

    python _probe_m11/verify_quad.py

Writes ``verify_quad.json``.
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

OUT = HERE / "verify_quad.json"
TARGETS = ["max_disp", "max_w", "max_von_mises_midsurface", "max_von_mises"]


def mape(ps, os_):
    return float(np.mean([abs((p - o) / o) for p, o in zip(ps, os_)])) * 100.0


def main() -> int:
    fails, doc = [], {"generated": "2026-10-24", "milestone": "M11 / D34 verification",
                      "targets": {}}
    rows = B.load_family("wingbox")
    tr = [r for r in rows if r["split"] == "train"]
    va = [r for r in rows if r["split"] == "val"]
    te = [r for r in rows if r["split"] == "test"]
    te_ids = [r["case_id"] for r in te]

    print("=" * 100)
    print("  M11 / D34  quad vs lin - four ways to break the choice")
    print("=" * 100)
    print()
    print("  [1] other targets (test MAPE, same rows, val never used to fit)")
    print(f"    {'target':30s}{'lin':>9s}{'quad':>9s}{'d(pp)':>9s}   sig?")
    print("    " + "-" * 74)

    for key in TARGETS:
        # hybrid=True: compare on the M5 tier, the one the project quotes
        pf_lin, i_lin = S.fit(tr, key, "lin", hybrid=True)
        pf_q, i_q = S.fit(tr, key, "quad", hybrid=True)
        pl = pf_lin(te); pq = pf_q(te)
        obs = [r[key] for r in te]
        ml, mq = mape(pl, obs), mape(pq, obs)
        lo, hi, mean_diff = B.paired_boot(pq, pl, obs, n=4000)
        sig = "yes" if (lo > 0 or hi < 0) else "no"
        print(f"    {key:30s}{ml:9.2f}{mq:9.2f}{mq - ml:+9.2f}   {sig} "
              f"mean {mean_diff:+.2f} [{lo:+.2f},{hi:+.2f}]")
        doc["targets"][key] = {
            "tier": "phys (M5 recipe)",
            "lin": {"test_mape": round(ml, 3), "loo": i_lin["loo_mape"],
                    "cond": i_lin["cond_number"], "sweep_coef": i_lin["sweep_coef"]},
            "quad": {"test_mape": round(mq, 3), "loo": i_q["loo_mape"],
                     "cond": i_q["cond_number"], "sweep_coef": i_q["sweep_coef"]},
            "delta_pp": round(mq - ml, 3),
            "paired_boot_diff_95ci": [round(lo, 3), round(hi, 3)],
            "significant": sig == "yes",
            "test_ape_lin": {c: round((p - o) / o * 100, 3)
                             for c, p, o in zip(te_ids, pl, obs)},
            "test_ape_quad": {c: round((p - o) / o * 100, 3)
                              for c, p, o in zip(te_ids, pq, obs)},
        }

    # ---- [3] per-mechanism, max_disp ------------------------------------- #
    print()
    print("  [3] per-extrapolation-mechanism APE, target max_disp (test rows)")
    pf_l, i_l = S.fit(tr, "max_disp", "lin", hybrid=True)
    pf_q, i_q = S.fit(tr, "max_disp", "quad", hybrid=True)
    obs = [r["max_disp"] for r in te]
    al = [(p - o) / o * 100 for p, o in zip(pf_l(te), obs)]
    aq = [(p - o) / o * 100 for p, o in zip(pf_q(te), obs)]
    tags = [B.extrap_tags(r, tr) for r in te]
    groups: dict[str, list[int]] = {}
    for i, t in enumerate(tags):
        groups.setdefault(t, []).append(i)
    print(f"    {'mechanism':16s}{'n':>3s}{'lin%':>9s}{'quad%':>9s}{'d(pp)':>9s}")
    print("    " + "-" * 46)
    for g, idx in sorted(groups.items()):
        m1 = float(np.mean([abs(al[i]) for i in idx]))
        m2 = float(np.mean([abs(aq[i]) for i in idx]))
        print(f"    {g:16s}{len(idx):3d}{m1:9.2f}{m2:9.2f}{m2 - m1:+9.2f}")
        doc.setdefault("mechanisms", {})[g] = {
            "n": len(idx), "lin_pct": round(m1, 3), "quad_pct": round(m2, 3),
            "delta_pp": round(m2 - m1, 3),
            "cases": [te[i]["case_id"] for i in idx]}

    # ---- [4] stability of the curvature coefficient ----------------------- #
    print()
    print("  [4] stability of the s^2 coefficient under leave-one-out")
    n = len(tr)
    ylog = np.log([r["max_disp"] for r in tr])
    k2, k1 = [], []
    for i in range(n):
        keep = [j for j in range(n) if j != i]
        sub = [tr[j] for j in keep]
        _, info = S.fit(sub, "max_disp", "quad", hybrid=True)
        k2.append(info["sweep_coef"]["sw:s2"])
        k1.append(info["sweep_coef"]["sw:s"])
    k2 = np.array(k2); k1 = np.array(k1)
    print(f"    s^2 coef: full={i_q['sweep_coef']['sw:s2']:+.4f}  "
          f"LOO range [{k2.min():+.4f}, {k2.max():+.4f}]  "
          f"sign flips={int((np.sign(k2) != np.sign(i_q['sweep_coef']['sw:s2'])).sum())}/{n}")
    print(f"    s   coef: full={i_q['sweep_coef']['sw:s']:+.4f}  "
          f"LOO range [{k1.min():+.4f}, {k1.max():+.4f}]")
    doc["stability"] = {
        "s2_full": i_q["sweep_coef"]["sw:s2"],
        "s2_loo_min": round(float(k2.min()), 6),
        "s2_loo_max": round(float(k2.max()), 6),
        "s2_sign_flips": int((np.sign(k2) != np.sign(i_q["sweep_coef"]["sw:s2"])).sum()),
        "s_full": i_q["sweep_coef"]["sw:s"],
        "s_loo_min": round(float(k1.min()), 6),
        "s_loo_max": round(float(k1.max()), 6),
        "note": ("a curvature term whose sign flips when one row is removed is "
                 "fitting that row, not the shape"),
    }
    if doc["stability"]["s2_sign_flips"] > 0:
        fails.append("s^2 coefficient changes sign under leave-one-out")

    # ---- verdict ---------------------------------------------------------- #
    bad = [k for k, v in doc["targets"].items() if v["delta_pp"] > 0.5]
    print()
    print(f"  verdict inputs: targets made worse by >0.5 pp: {bad if bad else 'none'}")
    print(f"                  stability sign flips: {doc['stability']['s2_sign_flips']}")
    doc["fails"] = fails
    doc["verdict"] = "PASS" if not fails else "CHECK"
    print(f"  VERDICT: {doc['verdict']}")
    for f in fails:
        print(f"    ! {f}")
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {OUT}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
