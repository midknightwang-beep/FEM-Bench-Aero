"""Regenerate the dashboard's SPLITS block from manifest.json.

The dashboard is only allowed to *display* what the dataset says; every field in
``SPLITS.rows`` therefore has to come from ``manifest.json`` rather than from a
hand-typed table.  This script exists because that rule had quietly eroded:

* 28 of the 52 rows carried a ``cls`` hash that no longer matches
  ``manifest.geometry_class`` -- the class definition moved (D25 thickness table,
  D29 material block, D31 size axes) and the hand-typed copies did not;
* ``vm`` on the same rows came from an older reduction (it carried more digits
  than ``readings.max_von_mises`` and disagreed with it, e.g. 10.6048 vs
  10.4759 on ``naca4412_wingbox_sweep20``), so the column was mixing two
  definitions at once -- the exact failure D8 was created to prevent.

Nothing else on the page is touched: ``DECIDED``, ``REVIEW``, ``MILESTONES`` and
``GATES`` are curation (a human writes the prose), while ``SPLITS`` is data and
must be read back.

Usage::

    python _dash_sync_splits.py            # rewrite the block in place
    python _dash_sync_splits.py --check    # report drift, change nothing
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DASH = ROOT / "FEM-Bench-Aero项目进展看板.html"
MANIFEST = ROOT / "FEM-Bench-Aero" / "manifest.json"

FAM_ORDER = ["wingbox", "stiffened_panel", "fuselage_barrel", "open_hole_panel"]


def _num(x: float, nd: int) -> str:
    """Trim trailing zeros but keep at least one decimal place."""
    s = f"{x:.{nd}f}".rstrip("0")
    return s if s.endswith(".") is False else s + "0"


def build_rows(man: dict) -> list[dict]:
    rows = []
    for c in man["cases"]:
        r = c["readings"]
        rows.append({
            "id": c["case_id"],
            "fam": c["family"],
            "role": c["role"],
            "cls": c["geometry_class"],
            "clsN": c.get("class_size", 1),
            "nodes": r["n_nodes"],
            "u": float(r["max_disp"]),
            "vm": float(r["max_von_mises"]),
            "minj": float(r["min_jacobian"]),
            "split": c["split"],
            "why": c["split_reason"],
        })
    # keep the dashboard's reading order: family, then train/val/test, then id
    order = {f: i for i, f in enumerate(FAM_ORDER)}
    sorder = {"train": 0, "val": 1, "test": 2}
    rows.sort(key=lambda d: (order.get(d["fam"], 99), sorder[d["split"]], d["id"]))
    return rows


def render_block(rows: list[dict], man: dict) -> str:
    n_cases = man["summary"]["n_cases"]
    n_classes = man["summary"]["n_geometry_classes"]
    head = (f"  n_cases:{n_cases}, n_classes:{n_classes}, "
            f"n_leaky:{man['summary']['n_leaky_classes']}, "
            f"n_dup:{man['summary']['n_duplicate_models']}, xval:{n_cases},\n"
            f"  rows:[\n")
    body = []
    for d in rows:
        body.append(
            f"   {{id:{json.dumps(d['id'])}, fam:{json.dumps(d['fam'])}, "
            f"role:{json.dumps(d['role'])}, "
            f"cls:{json.dumps(d['cls'])}, clsN:{d['clsN']},\n"
            f"    nodes:{d['nodes']}, u:{_num(d['u'], 6)}, vm:{_num(d['vm'], 5)}, "
            f"minj:{_num(d['minj'], 4)}, split:{json.dumps(d['split'])},\n"
            f"    why:{json.dumps(d['why'], ensure_ascii=False)}}}")
    return head + ",\n".join(body) + "\n  ]"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = build_rows(man)
    html = DASH.read_text(encoding="utf-8")

    m = re.search(r"(const SPLITS = \{\n  target:\{[^}]*\},\n)(.*?)(\n\};)", html, re.S)
    if not m:
        print("cannot locate the SPLITS block")
        return 1
    new_block = render_block(rows, man)
    if args.check:
        same = m.group(2).strip() == new_block.strip()
        print(f"{'IN SYNC' if same else 'DRIFT'}  rows in manifest {len(rows)}")
        return 0 if same else 1

    html = html[:m.start(2)] + new_block + html[m.end(2):]
    DASH.write_text(html, encoding="utf-8")
    print(f"rewrote SPLITS: {len(rows)} rows, "
          f"{man['summary']['n_cases']} cases / "
          f"{man['summary']['n_geometry_classes']} classes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
