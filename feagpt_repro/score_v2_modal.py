"""Score v2 modal pilot candidates (C6-P1, same-code self-comparison).

Decided criteria (2026-11-07, option A, DESIGN_C6_P1_MODAL.md section 5):

  contract       FEASpec buildable -- rejection without silent degradation
                 (same contract idea as evaluate.py, minus the static-only
                 fuselage end_shear requirement)
  spec_fidelity  recursive FULL-KEY field diff vs the frozen v2 gold spec.
                 Generic recursion on purpose: a per-family field list can
                 silently skip keys it does not know (N-35 lesson).
                 Pilot grading is strict: extra keys are also red.
  pipeline       run_pipeline.py --solver ccx rc=0 (same code path as the
                 v1.1 evaluation, so candidate and reference share one
                 generator -- "same-code self-comparison")
  modal_f1       candidate f1 (extracted from the candidate's own ccx .dat)
                 vs truth.f_hz_ccx, relative diff < 1% -- PLUS spectrum
                 checks (10 modes, positive, strictly monotonic).
                 Modes 2+ are recorded, never judged (S4 formulation
                 divergence between codes; same code on both sides makes
                 this gate sound anyway).

CLI::

    python score_v2_modal.py --candidate-dir <dir>   # score a candidate set
    python score_v2_modal.py --self-test             # pure-function pins
    python score_v2_modal.py --smoke <task-id>       # gold spec as candidate

Results: eval_runs_v2/<task_id>/evaluation.json (same shape as evaluate.py).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_V2 = _ROOT / "FEM-Bench-Aero" / "modeling_v2"
_TASKS = _HERE / "tasks" / "tasks_v2_modal.jsonl"
_RUNS = _HERE / "eval_runs_v2"
_PY = sys.executable
F1_THRESHOLD_REL = 0.01
FLOAT_TOL_REL = 1e-6
N_MODES = 10


# ---------------------------------------------------------------------- #
# pure gates (self-testable without solving)
# ---------------------------------------------------------------------- #
def deep_diff(cand, gold, path="$"):
    """Recursive full-key diff.  Returns [(path, expected, actual), ...].

    Covers every key on both sides -- missing and extra keys are both red
    (N-35: a grader that only walks its own field list silently skips the
    rest).  Floats compare at relative tol 1e-6.
    """
    fails = []
    if isinstance(gold, dict):
        if not isinstance(cand, dict):
            return [(path, "object", type(cand).__name__)]
        for k in sorted(set(gold) - set(cand)):
            fails.append((f"{path}.{k}", _short(gold[k]), "<missing>"))
        for k in sorted(set(cand) - set(gold)):
            fails.append((f"{path}.{k}", "<extra>", _short(cand[k])))
        for k in sorted(set(gold) & set(cand)):
            fails += deep_diff(cand[k], gold[k], f"{path}.{k}")
    elif isinstance(gold, list):
        if not isinstance(cand, list) or len(cand) != len(gold):
            fails.append((path, f"list[{len(gold)}]",
                          f"{type(cand).__name__}[{len(cand)}]" if isinstance(cand, list) else type(cand).__name__))
        else:
            for i, (g, c) in enumerate(zip(gold, cand)):
                fails += deep_diff(c, g, f"{path}[{i}]")
    elif isinstance(gold, bool) or gold is None or isinstance(gold, str):
        if cand != gold:
            fails.append((path, _short(gold), _short(cand)))
    elif isinstance(gold, (int, float)):
        if not isinstance(cand, (int, float)) or isinstance(cand, bool):
            fails.append((path, gold, _short(cand)))
        elif abs(cand - gold) > FLOAT_TOL_REL * max(1.0, abs(gold)):
            fails.append((path, gold, cand))
    return fails


def _short(v):
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= 60 else s[:57] + "..."


def judge_modal_f1(f_hz: list, truth_scalars: dict) -> dict:
    """f1 gate + spectrum sanity.  Pure: no solver, no files."""
    ref = truth_scalars["f_hz_ccx"]
    checks = []
    if len(f_hz) != len(ref):
        checks.append(("n_modes", len(ref), len(f_hz)))
        return {"pass": False, "field": "modal_f1", "checks": checks}
    checks.append(("n_modes", len(ref), len(f_hz)))
    if any(x <= 0 for x in f_hz):
        checks.append(("positive", ">0", [x for x in f_hz if x <= 0][:3]))
    if any(b <= a for a, b in zip(f_hz, f_hz[1:])):
        checks.append(("monotonic", "strictly increasing", False))
    rel1 = abs(f_hz[0] - ref[0]) / ((f_hz[0] + ref[0]) / 2)
    checks.append(("f1_rel_diff", f"<{F1_THRESHOLD_REL:.0%}", round(rel1, 6)))
    ok = (len(f_hz) == len(ref) and all(x > 0 for x in f_hz)
          and all(b > a for a, b in zip(f_hz, f_hz[1:]))
          and rel1 < F1_THRESHOLD_REL)
    return {"pass": ok, "field": "modal_f1", "checks": checks,
            "f1_cand": f_hz[0], "f1_ref": ref[0],
            "f_hz_cand": f_hz, "note": "modes 2+ recorded, not judged"}


def load_gold_spec(case_name: str) -> dict:
    return json.loads((_V2 / case_name / f"{case_name}.spec.json")
                      .read_text(encoding="utf-8"))


def load_truth(case_name: str) -> dict:
    return json.loads((_V2 / case_name / "truth.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------- #
# full-chain evaluation
# ---------------------------------------------------------------------- #
def evaluate_one_v2(task: dict, cand_spec_path: Path, out_root: Path = _RUNS,
                    timeout: int = 1800) -> dict:
    task_id = task["task_id"]
    case_name = task["task_id"].split("V2_L1_", 1)[1]
    run_dir = out_root / task_id
    run_dir.mkdir(parents=True, exist_ok=True)
    result = {"task_id": task_id, "family": task["family"],
              "candidate_spec": str(cand_spec_path), "gates": {},
              "overall_pass": False}

    # unpack gen_candidates wrapper, same convention as evaluate.py
    raw = json.loads(Path(cand_spec_path).read_text(encoding="utf-8"))
    if "spec" in raw and "structure" not in raw:
        raw = raw["spec"] or {}
    raw.pop("workdir", None)

    # gate 0: contract
    try:
        from feagpt.spec import FEASpec
        FEASpec.from_dict(json.loads(json.dumps(raw)))
        result["gates"]["contract"] = {"pass": True, "field": "contract_buildable",
                                       "expected": "FEASpec constructable",
                                       "actual": "ok"}
    except Exception as e:
        result["gates"]["contract"] = {
            "pass": False, "field": "contract_buildable",
            "expected": "FEASpec constructable",
            "actual": f"{type(e).__name__}: {e}",
            "detail": "reject without silent degradation; no solve attempted"}
        result["failure_class"] = "model"
        _write(run_dir, result)
        return result

    # gate 1: spec_fidelity (recursive full-key vs frozen v2 gold)
    gold = load_gold_spec(case_name)
    gold.pop("workdir", None)
    fails = deep_diff(raw, gold)
    result["gates"]["spec_fidelity"] = {
        "pass": not fails, "field": "spec_fidelity (recursive full-key)",
        "expected": "all keys equal (float tol 1e-6)",
        "actual": f"{max(0, _n_keys(raw) - len(fails))}/{_n_keys(raw)} nodes clean",
        "n_fail": len(fails),
        "failed": [{"path": p, "expected": e, "actual": a}
                   for p, e, a in fails[:20]]}

    # gate 2: pipeline (same code path as v1.1 evaluation)
    cand_spec_path = run_dir / "candidate.spec.json"
    cand_spec_path.write_text(json.dumps(raw, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    t0 = time.time()
    proc = subprocess.run(
        [_PY, str(_HERE / "run_pipeline.py"), "--spec", str(cand_spec_path),
         "--out", str(run_dir), "--solver", "ccx"],
        capture_output=True, text=True, timeout=timeout, cwd=str(_HERE))
    result["pipeline_rc"] = proc.returncode
    result["wall_seconds"] = round(time.time() - t0, 1)
    if proc.returncode != 0:
        result["gates"]["pipeline"] = {
            "pass": False, "field": "run_pipeline", "expected": "rc=0",
            "actual": f"rc={proc.returncode}",
            "detail": (proc.stdout[-800:] + "\n" + proc.stderr[-800:])[-1200:]}
        result["failure_class"] = "pipeline"
        _write(run_dir, result)
        return result
    result["gates"]["pipeline"] = {"pass": True, "field": "run_pipeline",
                                   "expected": "rc=0", "actual": "rc=0"}

    # gate 3: modal_f1 (candidate's own ccx .dat vs frozen truth)
    truth = load_truth(case_name)
    dat = run_dir / case_name / f"{case_name}.dat"
    if not dat.exists():
        result["gates"]["modal_f1"] = {"pass": False, "field": "modal_f1",
                                       "expected": "candidate .dat",
                                       "actual": "missing"}
        _write(run_dir, result)
        return result
    sys.path.insert(0, str(_HERE))
    from extract_modal_dat import extract
    modes = extract(str(dat), "ccx", expect=N_MODES)["modes"]
    f_hz = [m["f_hz"] for m in modes]
    g3 = judge_modal_f1(f_hz, truth["scalars"])
    result["gates"]["modal_f1"] = g3

    result["overall_pass"] = all(g["pass"] for g in result["gates"].values())
    _write(run_dir, result)
    return result


def _n_keys(obj) -> int:
    if isinstance(obj, dict):
        return sum(1 + _n_keys(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(_n_keys(v) for v in obj)
    return 1


def _write(run_dir: Path, result: dict) -> None:
    out = run_dir / "evaluation.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    result["evaluation_json"] = str(out)


# ---------------------------------------------------------------------- #
# self-test: pure-function pins, BOTH directions (S-63)
# ---------------------------------------------------------------------- #
def self_test() -> int:
    ok = 0

    def pin(name, cond):
        nonlocal ok
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")
        if cond:
            ok += 1

    base = "naca4412_wingbox_modal"
    gold = load_gold_spec(base)
    gold.pop("workdir", None)
    truth = load_truth(base)

    # pin 1: gold vs gold -> zero diffs
    pin("self-diff clean", deep_diff(gold, gold) == [])

    # pin 2: any mutated leaf is caught (value drift)
    mut = json.loads(json.dumps(gold))
    mut["material"]["youngs_modulus"] *= 1.001
    pin("value drift caught", len(deep_diff(mut, gold)) == 1)

    # pin 3: extra key caught (strict pilot grading)
    mut = json.loads(json.dumps(gold))
    mut["analysis"]["comment"] = "self-invented"
    pin("extra key caught", any(p[0] == "$.analysis.comment" and p[1] == "<extra>"
                                for p in deep_diff(mut, gold)))

    # pin 4: missing key caught
    mut = json.loads(json.dumps(gold))
    del mut["analysis"]["n_modes"]
    pin("missing key caught", any(p[0] == "$.analysis.n_modes" and p[1] != "<extra>"
                                  for p in deep_diff(mut, gold)))

    # pin 5: modal_f1 green on the reference spectrum itself
    g = judge_modal_f1(truth["scalars"]["f_hz_ccx"], truth["scalars"])
    pin("modal_f1 ref-self green", g["pass"] is True)

    # pin 6: modal_f1 red when f1 drifts beyond 1% (reverse direction)
    f_bad = [x * 1.02 for x in truth["scalars"]["f_hz_ccx"]]
    g = judge_modal_f1(f_bad, truth["scalars"])
    pin("modal_f1 +2% drift red", g["pass"] is False)

    # pin 6b: f1 inside tolerance but non-monotonic still red
    f_mono = list(truth["scalars"]["f_hz_ccx"])
    f_mono[2] = f_mono[1] * 0.9
    g = judge_modal_f1(f_mono, truth["scalars"])
    pin("modal_f1 non-monotonic red", g["pass"] is False)

    # pin 7: wrong n_modes red
    g = judge_modal_f1(truth["scalars"]["f_hz_ccx"][:9], truth["scalars"])
    pin("modal_f1 short spectrum red", g["pass"] is False)

    # pin 8: threshold sides, unambiguous only.  For c = r*(1+d) the symmetric
    # relative diff is d/(1+d/2), so "over threshold" needs d > t/(1-t/2) --
    # d = t itself (or t*1.001) is still UNDER and legitimately green.
    r1 = truth["scalars"]["f_hz_ccx"][0]
    d_over = F1_THRESHOLD_REL / (1 - F1_THRESHOLD_REL / 2) * 1.001
    f_over = [r1 * (1 + d_over)] + truth["scalars"]["f_hz_ccx"][1:]
    pin("modal_f1 just-over-threshold red",
        judge_modal_f1(f_over, truth["scalars"])["pass"] is False)
    d_under = F1_THRESHOLD_REL * 0.999
    f_in = [r1 * (1 + d_under)] + truth["scalars"]["f_hz_ccx"][1:]
    pin("modal_f1 just-under-threshold green",
        judge_modal_f1(f_in, truth["scalars"])["pass"] is True)

    total = 10
    print(f"self-test {ok}/{total}")
    return 0 if ok == total else 1


# ---------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate-dir", help="directory of <task_id>.json candidates")
    ap.add_argument("--tasks", default=str(_TASKS))
    ap.add_argument("--out-root", default=str(_RUNS))
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--smoke", help="score the gold spec itself for this task-id")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    tasks = [json.loads(l) for l in Path(args.tasks).read_text(encoding="utf-8")
             .splitlines() if l.strip()]
    out_root = Path(args.out_root)

    if args.smoke:
        task = next(t for t in tasks if t["task_id"] == args.smoke)
        case_name = args.smoke.split("V2_L1_", 1)[1]
        spec = _V2 / case_name / f"{case_name}.spec.json"
        tmp = out_root / args.smoke / "gold_as_candidate.spec.json"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(spec.read_text(encoding="utf-8"), encoding="utf-8")
        r = evaluate_one_v2(task, tmp, out_root)
        print(json.dumps({k: r[k] for k in ("task_id", "pipeline_rc",
                                            "wall_seconds", "overall_pass")},
                         ensure_ascii=False))
        for gk, gv in r["gates"].items():
            print(f"  {gk}: pass={gv['pass']}")
        return 0 if r["overall_pass"] else 1

    if not args.candidate_dir:
        ap.error("need --candidate-dir (or --self-test / --smoke)")
    cdir = Path(args.candidate_dir)
    rows = []
    for task in tasks:
        cpath = cdir / f"{task['task_id']}.json"
        if not cpath.exists():
            rows.append({"task_id": task["task_id"], "state": "no_candidate"})
            continue
        r = evaluate_one_v2(task, cpath, out_root)
        rows.append({"task_id": task["task_id"],
                     "overall_pass": r["overall_pass"],
                     "gates": {k: v["pass"] for k, v in r["gates"].items()}})
    summary = out_root / "_summary_v2.json"
    n_ok = sum(1 for r in rows if r.get("overall_pass"))
    summary.write_text(json.dumps({"n_tasks": len(tasks), "n_pass": n_ok,
                                   "rows": rows}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    print(f"scored {len(tasks)}: pass {n_ok} -> {summary}")
    for r in rows:
        print(f"  {r['task_id']}: {r.get('overall_pass', r.get('state'))}")
    return 0 if n_ok == len(tasks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
