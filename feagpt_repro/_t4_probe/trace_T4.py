"""Get the full traceback behind ``T4.invocation`` so it is fixed by evidence."""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_forms  # noqa: E402


def attempt(label, fn):
    print(f"--- {label}", flush=True)
    try:
        out = fn()
    except Exception:
        traceback.print_exc()
        print(f"    ^ {label} RAISED", flush=True)
        return
    print(f"    -> {out!r}", flush=True)


attempt("_hole_gate_probe", check_forms._hole_gate_probe)
attempt("check_T4", check_forms.check_T4)
