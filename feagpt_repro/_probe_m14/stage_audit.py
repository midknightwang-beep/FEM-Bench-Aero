"""M14 stage-gate audit -- collect every fact the go/no-go decision needs.

Design rules (same as the rest of the project):
  * read from disk, never from memory;
  * every number printed here is also written to JSON so the report can quote
    it and a reader can re-derive it;
  * "coverage" is measured per axis against the train envelope, because a
    value that exists in the dataset but only in val/test is *not* learned.

Run:  python _probe_m14/stage_audit.py
Out:  _probe_m14/stage_audit.json
"""
from __future__ import annotations

import collections
import json
import math
import statistics
from pathlib import Path

REPRO = Path(__file__).resolve().parents[1]
DATASET = REPRO.parent / "FEM-Bench-Aero"
OUT = Path(__file__).with_suffix(".json")


# --------------------------------------------------------------------------
# spec readers
# --------------------------------------------------------------------------
def load_specs() -> dict[str, dict]:
    out = {}
    for p in sorted((DATASET / "modeling").glob("*/spec.json")):
        out[p.parent.name] = json.load(open(p, encoding="utf-8"))
    return out


def flat_axes(spec: dict) -> dict[str, object]:
    """Design variables that actually vary, flattened to a name -> value map."""
    fam = spec["structure"]["family"]
    a: dict[str, object] = {}
    if fam == "wingbox":
        air = spec["airfoil"]
        for k in ("code", "chord", "span", "skin_thickness", "n_ribs",
                  "rib_thickness", "n_stringers_per_skin", "stringer_height",
                  "stringer_thickness", "stringer_kind", "stringer_flange_width",
                  "tip_chord_ratio", "sweep_deg"):
            a[k] = air.get(k)
        a["web_chordwise"] = tuple(air.get("web_chordwise") or ())
        a["spar_chordwise"] = tuple(air.get("spar_chordwise") or ())
        a["n_web"] = len(a["web_chordwise"])
        a["is_T"] = 1 if air.get("stringer_kind") == "T" else 0
    else:
        a.update(spec["structure"].get("params") or {})
        a.pop("layup", None)
    return a


def material_of(spec: dict) -> str:
    lay = (spec["structure"].get("params") or {}).get("layup")
    if lay:
        plies = lay.get("plies") or []
        angles = [p["angle"] for p in plies]
        return f"CFRP[{','.join(str(int(x)) for x in angles)}]"
    return spec["material"]["name"]


def mesh_of(spec: dict) -> tuple:
    m = spec.get("mesh") or {}
    return (m.get("size_chord"), m.get("size_span"), m.get("element_order"),
            m.get("refine_at_leading_edge"))


def load_of(spec: dict) -> tuple:
    l = spec["load"]
    return (l["kind"], float(l["magnitude"]), tuple(l.get("direction") or ()))


def main() -> dict:
    manifest = json.load(open(DATASET / "manifest.json", encoding="utf-8"))
    split_of = {c["case_id"]: c["split"] for c in manifest["cases"]}
    role_of = {c["case_id"]: c["role"] for c in manifest["cases"]}
    fam_of = {c["case_id"]: c["family"] for c in manifest["cases"]}
    cls_of = {c["case_id"]: c["geometry_class"] for c in manifest["cases"]}
    specs = load_specs()

    report: dict = {"n_cases": len(specs)}

    # ---------------- 1. per-family axis coverage -------------------------
    # For each family and each axis: the set of distinct values, per split.
    # A val/test value outside the train set is an extrapolation point.
    cover: dict = {}
    for cid, spec in specs.items():
        fam = fam_of.get(cid, spec["structure"]["family"])
        ax = flat_axes(spec)
        for name, val in ax.items():
            if isinstance(val, (list, dict)):
                continue
            key = f"{fam}::{name}"
            d = cover.setdefault(key, {"train": set(), "val": set(), "test": set()})
            d[split_of.get(cid, "?")].add(val)

    cover_out = {}
    for key, d in sorted(cover.items()):
        tr = sorted(x for x in d["train"] if x is not None)
        numeric = all(isinstance(x, (int, float)) for x in tr) and tr
        lo, hi = (min(tr), max(tr)) if numeric else (None, None)
        rec = {
            "n_train_values": len(tr),
            "train_values": tr[:12],
            "n_val_values": len(d["val"]),
            "n_test_values": len(d["test"]),
        }
        if numeric:
            rec["train_min"], rec["train_max"] = lo, hi
            rec["val_outside_envelope"] = sorted(
                x for x in d["val"] if x < lo or x > hi)
            rec["test_outside_envelope"] = sorted(
                x for x in d["test"] if x < lo or x > hi)
        else:
            rec["val_unseen"] = sorted(map(str, d["val"] - d["train"]))[:8]
            rec["test_unseen"] = sorted(map(str, d["test"] - d["train"]))[:8]
        cover_out[key] = rec
    report["axis_coverage"] = cover_out

    # ---------------- 2. which axes are constant across the whole family --
    const_axes = {}
    for fam in sorted(set(fam_of.values())):
        ids = [c for c in specs if fam_of[c] == fam]
        if not ids:
            continue
        axes = [flat_axes(specs[c]) for c in ids]
        names = set().union(*[set(a) for a in axes])
        consts = []
        for n in sorted(names):
            vals = {json.dumps(a.get(n), default=str) for a in axes}
            if len(vals) == 1 and len(ids) >= 3:
                consts.append({"axis": n, "value": json.loads(next(iter(vals)))})
        const_axes[fam] = {"n_cases_in_family": len(ids), "constant": consts}
    report["constant_axes_per_family"] = const_axes

    # ---------------- 3. load / material / mesh --------------------------
    report["load_cases"] = [
        {"family": f, "kind": k, "magnitude": m, "n": n}
        for (f, k, m), n in sorted(
            collections.Counter(
                (fam_of[c], *load_of(s)[:2]) for c, s in specs.items()
            ).items())
    ]
    report["materials"] = [
        {"name": k, "n": n} for k, n in
        sorted(collections.Counter(material_of(s) for s in specs.values()).items())
    ]
    meshes = collections.Counter(mesh_of(s) for s in specs.values())
    report["mesh_settings"] = [
        {"size_chord": k[0], "size_span": k[1], "order": k[2],
         "refine_le": k[3], "n": n} for k, n in sorted(meshes.items())
    ]

    # ---------------- 4. equivalence-class size distribution -------------
    sizes = collections.Counter(cls_of.values())
    report["class_size_hist"] = dict(sorted(collections.Counter(
        sizes.values()).items()))

    # ---------------- 5. mesh size / model scale ------------------------
    nodes = []
    for cid in specs:
        t = DATASET / "modeling" / cid / "truth.json"
        if not t.exists():
            continue
        d = json.load(open(t, encoding="utf-8"))
        nn = d.get("mesh", {}).get("n_nodes") or d.get("n_nodes")
        nodes.append({"case_id": cid, "family": fam_of[cid], "n_nodes": nn})
    nodes = [x for x in nodes if x["n_nodes"]]
    report["mesh_scale"] = {
        "n_cases_measured": len(nodes),
        "min_nodes": min(x["n_nodes"] for x in nodes) if nodes else None,
        "max_nodes": max(x["n_nodes"] for x in nodes) if nodes else None,
        "median_nodes": statistics.median([x["n_nodes"] for x in nodes]) if nodes else None,
        "by_family_max": {
            f: max(x["n_nodes"] for x in nodes if x["family"] == f)
            for f in {x["family"] for x in nodes}
        } if nodes else {},
    }

    # ---------------- 6. baseline numbers (read back, not recalled) -----
    bl = json.load(open(DATASET / "baseline_d36_final.json", encoding="utf-8"))
    bt = {}
    for tgt in ("max_disp", "max_w", "max_von_mises",
                "max_von_mises_midsurface"):
        rows = []
        for tier, r in bl["targets"][tgt].items():
            if tier == "_summary":
                continue
            rows.append({
                "tier": tier,
                "val": r["val_mape"], "test": r["test_mape"],
                "ci95": r.get("test_ci95"), "med": r["test_medape"],
                "max": r["test_maxape"],
            })
        bt[tgt] = {
            "tiers": rows,
            "summary": bl["targets"][tgt]["_summary"],
            "test_groups": bl.get("test_group_ape", {}).get(tgt, {}),
        }
    report["baseline"] = {
        "n": bl["n"], "n_classes": bl["n_classes"],
        "targets": bt,
        "test_groups": bl["test_groups"],
        "val_test_disagreement": bl["val_test_disagreement"],
    }

    # test-set statistical power: how wide is the 95 % CI on 6 points?
    md = bl["targets"]["max_disp"]["M5q hybrid+sweep^2"]
    ci = md.get("test_ci95") or [float("nan")] * 2
    report["test_power"] = {
        "n_test_wingbox": len(bl["test_groups"]) if isinstance(bl["test_groups"], list) else sum(
            len(v) for v in bl["test_groups"].values()) if isinstance(bl["test_groups"], dict) else None,
        "max_disp_M5q_test": md["test_mape"],
        "ci95": ci,
        "ci_width_pp": ci[1] - ci[0] if ci[0] == ci[0] else None,
        "ci_width_relative_to_point": (ci[1] - ci[0]) / md["test_mape"]
        if ci[0] == ci[0] and md["test_mape"] else None,
    }

    # ---------------- 7. solver / cross-code coverage -------------------
    xv = {}
    for f in sorted(DATASET.glob("_xval_d*.json")) + sorted(DATASET.glob("_xval_m8.json")):
        d = json.load(open(f, encoding="utf-8"))
        xv[f.name] = {k: d.get(k) for k in ("milestone", "verdict", "passed")
                      if k in d}
    report["xval_files"] = xv
    xy = sorted((DATASET / "_xval").glob("*/spec.json"))
    report["n_xval_cases"] = len(xy)
    report["xval_families"] = dict(collections.Counter(
        json.load(open(p, encoding="utf-8"))["structure"]["family"] for p in xy))

    # ---------------- 8. contract stability -----------------------------
    report["contract"] = {
        "spec_sha_present": all(c.get("spec_sha256") for c in manifest["cases"]),
        "mesh_sha_present": all(c.get("mesh_sha256") for c in manifest["cases"]),
        "n_distinct_spec_sha": len({c["spec_sha256"] for c in manifest["cases"]}),
        "schema_version": manifest["schema_version"],
        "split_rule_unit": manifest["split_rule"]["unit"],
    }

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str),
                   encoding="utf-8")
    return report


if __name__ == "__main__":
    r = main()
    print(f"written -> {OUT}")
    print("n_cases", r["n_cases"])
    print("\n== materials ==")
    for m in r["materials"]:
        print(f"  {m['name']:<34} x{m['n']}")
    print("\n== load cases ==")
    for l in r["load_cases"]:
        print(f"  {l['family']:<17}{l['kind']:<12}{l['magnitude']:<10} x{l['n']}")
    print("\n== mesh settings ==")
    for m in r["mesh_settings"]:
        print(f"  {m} ")
    print("\n== mesh scale ==", json.dumps(r["mesh_scale"], ensure_ascii=False))
    print("\n== class size hist ==", r["class_size_hist"])
    print("\n== test power ==", json.dumps(r["test_power"], ensure_ascii=False))
    print("\n== xval ==", r["n_xval_cases"], r["xval_families"])
    print("\n== wingbox axis coverage (train values) ==")
    for k, v in r["axis_coverage"].items():
        if k.startswith("wingbox::"):
            print(f"  {k:<34} n_tr={v['n_train_values']:<3} "
                  f"min={v.get('train_min')} max={v.get('train_max')} "
                  f"test_out={v.get('test_outside_envelope')}")
