"""Dataset card for the learnability probe (M7 stage 0).

Reads the *shipped* dataset (manifest.json is authoritative) and flattens each
case into (structural parameters -> scalar readings).  Nothing is solved here;
this is a read-only inventory so the probe can quote measured numbers instead
of remembered ones.

Run:  python _probe_m7/dataset_card.py [--json out.json]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT.parent / "FEM-Bench-Aero"

# Which spec slots carry the design variables, per family.
FAM_KEYS = {
    "open_hole_panel": ("structure.params", ["length", "width", "thickness", "hole_d"]),
    "stiffened_panel": ("structure.params", ["length", "width", "thickness", "n_stringers"]),
    "fuselage_barrel": ("structure.params", ["diameter", "length", "thickness",
                                            "n_stringers", "n_frames"]),
    "wingbox": ("airfoil", ["chord", "span", "skin_thickness", "n_ribs",
                            "rib_thickness", "n_stringers_per_skin",
                            "stringer_height", "stringer_thickness",
                            "sweep_deg", "tip_chord_ratio"]),
}


def load_case(case_dir: Path) -> tuple[dict, dict]:
    spec = json.loads((case_dir / "spec.json").read_text(encoding="utf-8"))
    truth = json.loads((case_dir / "truth.json").read_text(encoding="utf-8"))
    return spec, truth.get("scalars", truth)


def structural_params(spec: dict) -> dict:
    fam = spec["structure"]["family"]
    slot, keys = FAM_KEYS[fam]
    src = spec
    for part in slot.split("."):
        src = (src or {}).get(part) or {}
    out = {}
    for k in keys:
        v = src.get(k)
        out[k] = v if v is not None else 0.0
    # discrete topology knobs that are not plain scalars
    if fam == "wingbox":
        out["n_web"] = float(len(src.get("web_chordwise") or []))
        out["n_spar"] = float(len(src.get("spar_chordwise") or []))
        out["stringer_is_T"] = 1.0 if src.get("stringer_kind") == "T" else 0.0
    if fam == "open_hole_panel":
        p = spec["structure"]["params"]
        # centre-hole cases omit the key entirely; an off-centre hole names it.
        out["hole_x"] = float(p.get("hole_x", 0.5 * float(p["width"])))
        out["hole_y"] = float(p.get("hole_y", 0.5 * float(p["length"])))
        out["eccentricity"] = float(math.hypot(
            out["hole_x"] - 0.5 * float(p["width"]),
            out["hole_y"] - 0.5 * float(p["length"])))
        out["has_layup"] = 1.0 if "layup" in p else 0.0
        # longitudinal modulus actually seen by the coupon
        if "layup" in p:
            out["E_x"] = _laminate_ex(p["layup"])
        else:
            out["E_x"] = float(spec["material"]["youngs_modulus"])
    else:
        out["E_x"] = float(spec["material"]["youngs_modulus"])
    out["load_mag"] = float(spec["load"]["magnitude"])
    return out


def _laminate_ex(layup: dict) -> float:
    """Longitudinal modulus of the equivalent single layer (CLT, 0-deg axis)."""
    sys.path.insert(0, str(ROOT))
    from feagpt.laminate import LayupSpec, Ply, OrthotropicMaterialSpec
    from feagpt.laminate import equivalent_engineering_constants  # noqa: E402

    m = layup["material"]
    mat = OrthotropicMaterialSpec(
        name=m.get("name", "CFRP"), E1=m["E1"], E2=m["E2"], nu12=m["nu12"],
        G12=m["G12"], G23=m.get("G23", m["G12"]), G13=m.get("G13", m["G12"]),
        nu23=m.get("nu23", m["nu12"]),
        density=m.get("density", 1.6e-9),
    )
    plies = tuple(Ply(float(p["angle"]), float(p["thickness"])) for p in layup["plies"])
    return float(equivalent_engineering_constants(LayupSpec(plies=plies, material=mat))["EX"])


def scaling_exponent(xs, ys) -> float | None:
    """Least-squares slope of log y vs log x (single-variable scaling law)."""
    pts = [(math.log(x), math.log(y)) for x, y in zip(xs, ys)
           if x > 0 and y > 0]
    if len(pts) < 3 or len({p[0] for p in pts}) < 2:
        return None
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    if sxx < 1e-12:
        return None
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    return sxy / sxx


def pearson(xs, ys) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx < 1e-12 or syy < 1e-12:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy)


def main() -> int:
    man = json.loads((BENCH / "manifest.json").read_text(encoding="utf-8"))
    cases = {}
    for c in man["cases"]:
        if c["tree"] != "modeling":
            continue
        cid = c["case_id"]
        spec, sc = load_case(BENCH / "modeling" / cid)
        cases[cid] = {
            "family": c["family"],
            "split": c["split"],
            "geometry_class": c["geometry_class"],
            "params": structural_params(spec),
            "readings": {
                "max_disp": float(sc["max_disp"]),
                "max_von_mises": float(sc["max_von_mises"]),
                "n_nodes": int(sc.get("n_nodes", 0)),
            },
        }

    summary = {}
    for fam in FAM_KEYS:
        sub = {k: v for k, v in cases.items() if v["family"] == fam}
        if not sub:
            continue
        names = sorted({p for v in sub.values() for p in v["params"]})
        # a column is "varying" only if it actually moves inside the family
        varying = [p for p in names
                   if len({round(v["params"][p], 12) for v in sub.values()}) > 1]
        splits = {}
        for v in sub.values():
            splits[v["split"]] = splits.get(v["split"], 0) + 1
        powers = {}
        for p in varying:
            xs = [v["params"][p] for v in sub.values()]
            for out in ("max_disp", "max_von_mises"):
                ys = [v["readings"][out] for v in sub.values()]
                e = scaling_exponent(xs, ys)
                if e is not None and abs(e) > 0.15:
                    powers[f"{p}->{out}"] = round(e, 3)
        summary[fam] = {
            "n_cases": len(sub),
            "n_geometry_classes": len({v["geometry_class"] for v in sub.values()}),
            "splits": splits,
            "params_varying": varying,
            "n_varying_axes": len(varying),
            "notable_scaling_exponents": powers,
        }

    out = {"cases": cases, "summary": summary}
    print(json.dumps(summary, ensure_ascii=False, indent=1))

    for arg in sys.argv[1:]:
        if arg.startswith("--json="):
            Path(arg.split("=", 1)[1]).write_text(
                json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
            print("\n-> %s" % arg.split("=", 1)[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
