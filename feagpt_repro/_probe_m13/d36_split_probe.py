"""D36 probe (in memory, before landing): does `sweep>30` -> `sweep>35` move anyone?

Same four questions D33's probe asked, so the answers are comparable:

1. does the current constant reproduce ``manifest.json`` for all N cases on
   disk? (if not the manifest is stale and nothing below means anything)
2. how many of those N change **side** when the bound moves to 35?
3. where does the new ``sweep35`` case land -- before and after?
4. does the D12-locked eleven still reproduce 11/11?

Why 35 and not, say, 32 or 36: the point exists to split two things that one
``s^2`` coefficient is currently forced to carry at once (D35's residue) --
the *pure sweep curvature* measured on taper-neutral cases (0/10/20/30 ->
40 val) and the *sweep x taper interaction* (20x0.6, 30x0.8 -> 40x0.4 test).
A station halfway between the last train station and the exam (30 -> 40) is
the only placement that shortens the pure-sweep extrapolation **without**
touching either exam case.  35 = midpoint, and it keeps ``sweep40`` and
``sweep40_taper040`` out of train, so the exam survives.

What this probe cannot tell you: whether the point is *worth* a solve.  That
is what ``predict_sweep35.py`` is for -- it states the model's prediction at
35 deg before the measurement exists.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "feagpt_repro"))

from feagpt import manifest as M          # noqa: E402
from feagpt.spec import FEASpec           # noqa: E402

BENCH = ROOT / "FEM-Bench-Aero"
OUT = Path(__file__).resolve().parent
NEW = OUT / "naca4412_wingbox_sweep35.spec.json"
NEW_ID = "naca4412_wingbox_sweep35"

OLD_MAX = 30.0
NEW_MAX = 35.0


def load_cases() -> list[tuple[str, FEASpec]]:
    man = json.loads((BENCH / "manifest.json").read_text(encoding="utf-8"))
    out = []
    for c in man["cases"]:
        p = BENCH / c["tree"] / c["case_id"] / "spec.json"
        out.append((c["case_id"], FEASpec.from_json(p)))
    return out


def snapshot() -> dict[str, tuple[str, str]]:
    out = {}
    for cid, spec in load_cases():
        out[cid] = M.split_of(spec)
    out[NEW_ID] = M.split_of(FEASpec.from_json(NEW))
    return out


def main() -> int:
    man = json.loads((BENCH / "manifest.json").read_text(encoding="utf-8"))
    frozen = {c["case_id"]: c["split"] for c in man["cases"]}
    fails: list[str] = []

    # -- 1. the live rule reproduces the published manifest ----------------- #
    before = snapshot()
    mismatch = [cid for cid, (side, _r) in before.items()
                if cid in frozen and side != frozen[cid]]
    print(f"[1] rule vs manifest: {len(frozen) - len(mismatch)}/{len(frozen)} agree")
    if mismatch:
        fails.append(f"manifest is stale for {mismatch}")

    # -- 2. move the bound in memory only ----------------------------------- #
    print(f"[2] temporarily setting WINGBOX_TRAIN_MAX_SWEEP = {OLD_MAX:g} -> {NEW_MAX:g}")
    moved, reworded = [], []
    M.WINGBOX_TRAIN_MAX_SWEEP = NEW_MAX
    try:
        after = snapshot()

        moved = [(cid, before[cid][0], after[cid][0])
                 for cid in before
                 if cid != NEW_ID and before[cid][0] != after[cid][0]]
        reworded = [(cid, before[cid][1], after[cid][1])
                    for cid in before
                    if cid != NEW_ID
                    and before[cid][0] == after[cid][0] and before[cid][1] != after[cid][1]]
        print(f"    side changes among the {len(before) - 1} archived cases: {len(moved)}")
        for cid, b, a in moved:
            print(f"      {cid:<46}{b:>6} -> {a}")
        print(f"    reason-text changes (same side): {len(reworded)}")
        for cid, b, a in reworded:
            print(f"      {cid:<46}{after[cid][0]:>6}  {b!r}\n"
                  f"      {'':<46}{'':>6} -> {a!r}")
        if moved:
            fails.append(f"{len(moved)} archived case(s) change side")

        # -- 3. where does the new station land? ---------------------------- #
        nb, na = before[NEW_ID], after[NEW_ID]
        print(f"[3] {NEW_ID}: old -> {nb[0]} ({nb[1]})")
        print(f"    {'':<{len(NEW_ID)}}  new -> {na[0]} ({na[1]})")
        if na[0] != "train":
            fails.append(f"new sweep35 lands in {na[0]}, not train")
        if nb[0] == "train":
            fails.append("sweep35 already trains under the old bound - "
                         "the constant is not what is gating it")

        # -- 4. D12 locked eleven ------------------------------------------- #
        d12 = {}
        for cid, want in M.D12_LOCKED_SPLIT.items():
            got = M.split_of(FEASpec.from_json(BENCH / "modeling" / cid / "spec.json"))[0]
            d12[cid] = {"want": want, "got": got, "ok": got == want}
        ok = sum(1 for v in d12.values() if v["ok"])
        print(f"[4] D12 locked split reproduces {ok}/{len(d12)}")
        if ok != len(d12):
            fails.append(f"D12 reproduces only {ok}/{len(d12)}")

        # -- the axis as the model will see it ------------------------------ #
        sw = {}
        for cid, spec in load_cases():
            if M.family_of(spec) != "wingbox":
                continue
            s = float(spec.airfoil.sweep_deg)
            sw.setdefault(s, {"train": [], "val": [], "test": []})
            sw[s][after[cid][0]].append(cid)
        sw.setdefault(NEW_MAX, {"train": [], "val": [], "test": []})
        sw[NEW_MAX][na[0]].append(NEW_ID)
        print("[5] sweep stations by side (after the change):")
        for s in sorted(sw):
            row = sw[s]
            print(f"    {s:>5.0f} deg   train {len(row['train']):>2}"
                  f"  val {len(row['val']):>2}  test {len(row['test']):>2}")
    finally:
        M.WINGBOX_TRAIN_MAX_SWEEP = OLD_MAX

    verdict = "PASS" if not fails else "CHECK"
    print(f"\nVERDICT: {verdict}  ({len(fails)} failure(s))")
    for f in fails:
        print(f"  - {f}")

    doc = {
        "probe": "D36 sweep station 35 deg",
        "constant": "WINGBOX_TRAIN_MAX_SWEEP",
        "old": OLD_MAX,
        "new": NEW_MAX,
        "archived_cases": len(before) - 1,
        "manifest_agrees": len(frozen) - len(mismatch),
        "side_changes": [{"case": c, "from": b, "to": a} for c, b, a in moved],
        "reason_text_changes": [{"case": c, "from": b, "to": a} for c, b, a in reworded],
        "new_case": {"before": {"side": nb[0], "reason": nb[1]},
                     "after": {"side": na[0], "reason": na[1]}},
        "d12": d12,
        "sweep_stations_after": {str(int(k)): v for k, v in sorted(sw.items())},
        "fails": fails,
        "verdict": verdict,
    }
    p = OUT / "d36_split_probe.json"
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {p}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
