"""Collect, straight off disk, every number the progress report quotes.

Nothing here is typed by hand.  Each field is either

  * read from a shipped artifact (``manifest.json`` / ``spec.json`` /
    ``truth.json`` / ``model.results.json``), or
  * measured now -- the mesh minSICN is re-read from the archived
    ``model.msh`` with the same function the gate uses
    (``diagnostics.msh_quality.quality``), so the report cannot quote a
    number that is not reproducible from what ships.

Output: ``report_data.json`` next to this file.  The report builder and its
checker both read that file, so the HTML and the disk cannot drift apart.

Run with the managed venv (needs gmsh)::

    C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe \
        _report/make_report_data.py
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

ROOT = Path(r"F:\AI FEA Modeling DataSets")
DS = ROOT / "FEM-Bench-Aero"
REPRO = ROOT / "feagpt_repro"
HERE = Path(__file__).resolve().parent

sys.path.insert(0, str(REPRO / "diagnostics"))
import gmsh                       # noqa: E402
from msh_quality import quality    # noqa: E402

_GMSH_ELEM = {1: "line2", 2: "tri3", 3: "quad4", 4: "tet4",
              5: "hex8", 9: "tri6", 10: "quad9"}

_TREES = {"ccx": "modeling", "abaqus": "_xval"}


def _read(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def _read_or(p: Path):
    return _read(p) if p.exists() else None


def _results(tree: str, case: str):
    p = DS / tree / case / "model.results.json"
    if not p.exists():
        return None
    d = _read(p)
    return {
        "max_disp": d.get("max_disp"),
        "max_von_mises": d.get("max_von_mises"),
        "max_von_mises_midsurface": d.get("max_von_mises_midsurface"),
        "max_von_mises_peak": d.get("max_von_mises_peak"),
        "n_nodes": d.get("n_nodes"),
        "solver_meta": d.get("solver_meta", {}),
    }


# spec fields worth carrying into the report, per family.
_WINGBOX_KEYS = ("chord", "span", "skin_thickness", "n_ribs", "rib_thickness",
                 "n_stringers_per_skin", "stringer_kind", "stringer_height",
                 "stringer_thickness", "tip_chord_ratio", "sweep_deg")


def _spec_brief(spec: dict) -> dict:
    st = spec.get("structure", {})
    af = spec.get("airfoil", {})
    return {
        "family": st.get("family"),
        "params": st.get("params", {}),
        "airfoil": {k: af.get(k) for k in _WINGBOX_KEYS},
        "mesh": spec.get("mesh", {}),
        "load": spec.get("load", {}),
        "extra": spec.get("extra", {}),
        "workdir": spec.get("workdir"),
    }


def main() -> int:
    man = _read(DS / "manifest.json")

    # ---- per-case sweep (mesh quality is measured, not remembered) --------
    gmsh.initialize()
    cases: list[dict] = []
    for cm in sorted(man["cases"], key=lambda c: (c["family"], c["case_id"])):
        cid = cm["case_id"]
        spec = _read(DS / "modeling" / cid / "spec.json")
        truth = _read(DS / "modeling" / cid / "truth.json")
        msh = DS / "modeling" / cid / "model.msh"
        q = quality(msh) if msh.exists() else {"min": None, "n": 0, "types": {}}
        types = {_GMSH_ELEM.get(t, f"type{t}"): n for t, n in q["types"].items()}
        tri3 = sum(n for k, n in types.items() if k.startswith("tri"))
        scal = truth.get("scalars", {})
        cases.append({
            "case_id": cid,
            "family": cm["family"],
            "role": cm["role"],
            "split": cm["split"],
            "split_reason": cm.get("split_reason", ""),
            "geometry_class": cm["geometry_class"],
            "spec_sha256": cm.get("spec_sha256"),
            "spec": _spec_brief(spec),
            "mesh": {
                "n_nodes": scal.get("n_nodes"),
                "n_elements": q["n"],
                "element_types": types,
                "tri3": tri3,
                "minJ": q["min"],
                "minJ_pass": (q["min"] is not None and q["min"] >= 0.30),
            },
            "truth": {
                "design": truth.get("topology", {}).get("design", {}),
                "geometry": truth.get("topology", {}).get("geometry", {}),
                "semantic_gate_pass": truth.get("semantic_gate", {}).get("pass"),
            },
            "ccx": _results(_TREES["ccx"], cid),
            "abaqus": _results(_TREES["abaqus"], cid),
        })
    gmsh.finalize()

    # ---- cross-solver pairing (from the shipped results, both trees) ------
    for c in cases:
        cc, ab = c["ccx"], c["abaqus"]
        if cc and ab and cc.get("max_disp") and ab.get("max_disp"):
            c["xval"] = {
                "max_disp_diff_pct": abs(ab["max_disp"] - cc["max_disp"])
                                    / cc["max_disp"] * 100.0,
                "vm_peak_diff_pct": (
                    abs(ab["max_von_mises_peak"] - cc["max_von_mises_peak"])
                    / cc["max_von_mises_peak"] * 100.0
                    if cc.get("max_von_mises_peak") else None),
                "n_nodes_equal": cc.get("n_nodes") == ab.get("n_nodes"),
            }
        else:
            c["xval"] = None

    # ---- dataset-level gates (read from their own reports) ---------------
    evalr = _read_or(DS / "eval_report.json") or {}
    verify = _read_or(DS / "verify_report.json") or {}
    gate4 = _read_or(DS / "gate4.json") or {}
    forms = _read_or(DS / "check_forms.json") or {}
    dedup = _read_or(DS / "dedup_report.json") or {}

    eval_checks = evalr.get("checks", [])
    gates = {
        "eval": {
            "n_checks": len(eval_checks),
            "n_pass": sum(1 for c in eval_checks if c.get("pass")),
            "checks": [{"key": c.get("key"), "pass": c.get("pass"),
                        "detail": c.get("detail", "")} for c in eval_checks],
            "failures": [c.get("key") for c in eval_checks if not c.get("pass")],
        },
        "verify_dataset": verify.get("summary", {}),
        "gate4": {"n_cases": gate4.get("n_cases"), "n_pass": gate4.get("n_pass")},
        "check_forms": {"n_pass": forms.get("n_pass"), "n_fail": forms.get("n_fail"),
                        "checks": [{"form": c.get("form"), "check": c.get("check"),
                                    "pass": c.get("pass"), "detail": c.get("detail", "")}
                                   for c in forms.get("checks", [])]},
        "dedup": {"n_groups": dedup.get("n_groups"),
                  "n_removed": dedup.get("n_removed")},
    }

    # ---- family-level T3 / panel verification (done once, quoted here) ---
    t3 = {
        "verify_barrel": _read_or(REPRO / "_m5_probe" / "verify_barrel_b3.json"),
        "d20": _read_or(REPRO / "_m5_probe" / "t3_d20_batch3.json"),
        "cap_rule": _read_or(REPRO / "_m5_probe" / "t3_cap_rule.json"),
    }
    panel = {
        "verify": _read_or(DS / "panel_verify.json"),
        "convergence": _read_or(REPRO / "diagnostics" / "panel_convergence.json"),
    }

    out = {
        "meta": {
            "generated_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "dataset_root": str(DS),
            "release_tree": man.get("release_tree"),
            "generator": man.get("generator"),
            "schema_version": man.get("schema_version"),
        },
        "manifest": {
            "summary": man.get("summary", {}),
            "split_rule": man.get("split_rule", {}),
            "limitations": man.get("limitations", []),
            "classes": man.get("classes", {}),
        },
        "gates": gates,
        "cases": cases,
        "t3": t3,
        "panel": panel,
    }
    outp = HERE / "report_data.json"
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # console receipt so the operator sees what was captured
    print(f"wrote {outp}  ({outp.stat().st_size} bytes)")
    print(f"  cases           : {len(cases)}")
    print(f"  splits          : {out['manifest']['summary'].get('splits')}")
    worst = min((c['mesh']['minJ'] for c in cases if c['mesh']['minJ']), default=None)
    print(f"  worst minJ      : {worst:.4f}" if worst else "  worst minJ      : -")
    tri = sum(c['mesh']['tri3'] for c in cases)
    print(f"  tri3 total      : {tri}")
    print(f"  eval / gate4    : {gates['eval'].get('n_pass')} / {gates['gate4']}")
    print(f"  check_forms     : {gates['check_forms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
