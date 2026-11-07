"""Generate ``tasks/tasks_v2_modal.jsonl`` — the C6-P1 modal pilot exam.

Each task mirrors the v1.1 L1 shape: ``input.spec_normalized`` is the full
normalized parameter table (the gold spec minus ``workdir``/``airfoil``);
the model's job is to turn it into a runnable FEASpec.  Everything is read
from the frozen v2 artifacts at run time (R-A3: no hand-copied numbers).

Usage::

    python make_v2_tasks.py           # (re)write tasks/tasks_v2_modal.jsonl
    python make_v2_tasks.py --check   # verify the existing file matches
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from make_v2_modal_cases import CASES  # noqa: E402

_ROOT = _HERE.parent
_V2 = _ROOT / "FEM-Bench-Aero" / "modeling_v2"
_OUT = _HERE / "tasks" / "tasks_v2_modal.jsonl"

#: gold-only keys that must NOT leak into the task input (v1.1 convention)
_STRIP_TOP = ("workdir", "airfoil")


def build_task(base: str) -> dict:
    name = f"{base}_modal"
    spec = json.loads((_V2 / name / f"{name}.spec.json").read_text(encoding="utf-8"))
    spec_input = {k: v for k, v in spec.items() if k not in _STRIP_TOP}
    if spec_input.get("analysis", {}).get("step_type") != "frequency":
        raise SystemExit(f"{name}: input analysis.step_type != frequency")
    if spec_input.get("analysis", {}).get("n_modes") != 10:
        raise SystemExit(f"{name}: input analysis.n_modes != 10")
    return {
        "task_id": f"V2_L1_{name}",
        "family": "naca4412_wingbox_modal",
        "input_level": "L1",
        "input_source": "v2_modal_pilot",
        "input": {"spec_normalized": spec_input},
        "truth_ref": f"modeling_v2/{name}/truth.json",
        "gates": ["spec_fidelity", "modal_f1"],
        "split_v2": "pilot",
        "split_reason": "C6-P1 模态打样（2026-11-07 冻结，SHA256SUMS 74 文件）",
    }


def main(argv=None) -> int:
    tasks = [build_task(b) for b in CASES]
    blob = "".join(json.dumps(t, ensure_ascii=False) + "\n" for t in tasks)
    if argv and "--check" in argv:
        cur = _OUT.read_text(encoding="utf-8") if _OUT.exists() else ""
        print("tasks check:", "MATCH" if cur == blob else "DIFFER")
        return 0 if cur == blob else 1
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(blob, encoding="utf-8")
    print(f"wrote {_OUT} ({len(tasks)} tasks)")
    for t in tasks:
        print(f"  {t['task_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
