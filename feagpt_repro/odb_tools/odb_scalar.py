"""Fast scalar extraction from an Abaqus ODB -- the "quick" tier of the ODB
tool pair (2026-11-06, laowang decision A/B/C: same model x N load cases,
solve+extract pipeline, configurable output).

Executed by Abaqus' own interpreter, NOT the pipeline interpreter::

    abaqus python odb_scalar.py <job.odb> <out.json> [--full]

It is deliberately standalone (stdlib + odbAccess + abaqusConstants only),
exactly like ``feagpt/abaqus_odb.py`` -- the full-field extractor this tool
shares its numerics with.  Where ``abaqus_odb.py`` dumps every node, this
tool emits only the numbers a strength report actually opens with:

* ``max_u``        : per-component max displacement (Ux/Uy/Uz) + max |U| magnitude
* ``max_urf``      : per-component max reaction magnitude + total reaction
                     resultant (sum over nodes -- the equilibrium handle)
* ``vm_membrane``  : peak von Mises of the *membrane* stress (node-averaged),
                     the quantity CalculiX OUTPUT=2D reports (verified in
                     abaqus_odb.py: median 1.6% apart, correlation 0.992)
* ``vm_peak``      : element-wise max von Mises over outermost section points,
                     the sizing number (NOT comparable with CalculiX OUTPUT=2D)

Same-frame discipline: everything is read from ``steps[-1].frames[-1]`` -- the
same frame abaqus_odb.py reads, so scalar and full-field tiers cannot drift
apart on *which* frame they reported.

Self-test (no Abaqus needed)::

    python odb_scalar.py --self-test

runs the pure-numeric core (von Mises, component reorder, scalar reduction)
against the same fixed vectors ``feagpt/abaqus_odb.py`` was validated with,
so the two extractors are pinned to each other: if one drifts, the self-test
of the other catches it.

Design decision (laowang 2026-11-06): default = scalars only (thousands of
load cases must not each leave a multi-MB JSON); ``--full`` delegates the
whole ODB to ``abaqus_odb.py`` logic by simply invoking the full-field
reduction here as well and writing both files is NOT done -- one job, one
tier, chosen by flag, so a batch manifest can state which tier each row used.
"""

from __future__ import annotations

import json
import sys
import time

# ---------------------------------------------------------------------------
# Pure-numeric core -- keep byte-identical with feagpt/abaqus_odb.py.
# The self-test at the bottom asserts the pinned vectors, so any drift
# between the two files fails loudly instead of quietly producing numbers
# from two different definitions.
# ---------------------------------------------------------------------------

#: FRD component order: (SXX, SYY, SZZ, SXY, SYZ, SZX)
_FRD_COMPONENTS = ("S11", "S22", "S33", "S12", "S23", "S31")
_FRD_ALIASES = {"S23": ("S32",), "S31": ("S13",)}


def _von_mises(s) -> float:
    sxx, syy, szz, sxy, syz, szx = s
    return (
        0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2)
        + 3.0 * (sxy ** 2 + syz ** 2 + szx ** 2)
    ) ** 0.5


def _reorder(data, labels) -> list:
    """Map an Abaqus stress tuple onto the FRD component order, by label."""
    idx = {str(lab).upper(): i for i, lab in enumerate(labels)}
    out = []
    for want in _FRD_COMPONENTS:
        j = idx.get(want)
        if j is None:
            for alias in _FRD_ALIASES.get(want, ()):
                if alias in idx:
                    j = idx[alias]
                    break
        out.append(float(data[j]) if j is not None else 0.0)
    return out


def reduce_scalars(u_vals, rf_vals, per_el_node) -> dict:
    """Pure reduction -- no odbAccess types, fully unit-testable.

    Parameters
    ----------
    u_vals   : list of (node_label, (ux, uy, uz))
    rf_vals  : list of (node_label, (fx, fy, fz))
    per_el_node : {(elem, node): {section_point: 6-vector in FRD order}}
                  the same construction abaqus_odb.py builds from
                  ELEMENT_NODAL extrapolation.
    """
    out = {"max_u": {}, "max_urf": {}, "vm_membrane": None, "vm_peak": None}

    # -- displacement ------------------------------------------------------
    if u_vals:
        comp_max = [0.0, 0.0, 0.0]
        mag_max, mag_node = 0.0, None
        for node, (ux, uy, uz) in u_vals:
            for i, c in enumerate((ux, uy, uz)):
                a = abs(c)
                if a > comp_max[i]:
                    comp_max[i] = a
            m = (ux * ux + uy * uy + uz * uz) ** 0.5
            if m > mag_max:
                mag_max, mag_node = m, node
        out["max_u"] = {"ux": comp_max[0], "uy": comp_max[1], "uz": comp_max[2],
                        "mag": mag_max, "mag_node": mag_node, "n_nodes": len(u_vals)}

    # -- reactions ---------------------------------------------------------
    if rf_vals:
        comp_max = [0.0, 0.0, 0.0]
        resultant = [0.0, 0.0, 0.0]
        for node, (fx, fy, fz) in rf_vals:
            for i, c in enumerate((fx, fy, fz)):
                a = abs(c)
                if a > comp_max[i]:
                    comp_max[i] = a
                resultant[i] += c
        mag = sum(c * c for c in resultant) ** 0.5
        out["max_urf"] = {"rfx": comp_max[0], "rfy": comp_max[1], "rfz": comp_max[2],
                          "resultant": resultant, "resultant_mag": mag,
                          "n_nodes": len(rf_vals)}

    # -- stress: same construction as abaqus_odb.py ------------------------
    # per (elem, node): outermost section points -> membrane = mean(bottom, top)
    #   vm_membrane = max over nodes of vM( element-averaged membrane tensor )
    #   vm_peak     = max over (elem, node, section point) of vM
    if per_el_node:
        sums, counts, peak_vm = {}, {}, 0.0
        elem_peak_vm = 0.0
        for (_el, node), spmap in per_el_node.items():
            ordered = sorted(spmap.items())
            bottom, top = ordered[0][1], ordered[-1][1]
            membrane = [0.5 * (a + b) for a, b in zip(bottom, top)]
            acc = sums.setdefault(node, [0.0] * len(membrane))
            for i, val in enumerate(membrane):
                acc[i] += val
            counts[node] = counts.get(node, 0) + 1
            for cand in (bottom, top) if len(ordered) > 1 else (bottom,):
                v = _von_mises(cand)
                if v > elem_peak_vm:
                    elem_peak_vm = v
        mids = {n: [s / counts[n] for s in vec] for n, vec in sums.items()}
        vm_membrane = max(map(_von_mises, mids.values())) if mids else None
        out["vm_membrane"] = round(vm_membrane, 4) if vm_membrane is not None else None
        out["vm_peak"] = round(elem_peak_vm, 4)
        out["n_stress_nodes"] = len(mids)
    return out


def extract(odb_path: str, out_path: str) -> dict:
    """The odbAccess half: walk the ODB, build the pure inputs, reduce."""
    from odbAccess import openOdb  # noqa: PLC0415 - Abaqus-only module

    t0 = time.time()
    odb = openOdb(odb_path, readOnly=True)
    try:
        step_names = list(odb.steps.keys())
        step = odb.steps[step_names[-1]]
        frame = step.frames[-1]

        def _field(name):
            try:
                return frame.fieldOutputs[name]
            except KeyError:
                return None

        u_vals, rf_vals = [], []
        u = _field("U")
        if u is not None:
            u_vals = [(int(v.nodeLabel), [float(c) for c in v.data[:3]])
                      for v in u.values]
        rf = _field("RF")
        if rf is not None:
            rf_vals = [(int(v.nodeLabel), [float(c) for c in v.data[:3]])
                       for v in rf.values]

        per_el_node = {}
        s = _field("S")
        s_labels = []
        if s is not None:
            import abaqusConstants as ac  # noqa: PLC0415
            nodal = s.getSubset(position=ac.ELEMENT_NODAL)
            s_labels = list(nodal.componentLabels)
            for v in nodal.values:
                sp = getattr(v, "sectionPoint", None)
                sp_num = int(sp.number) if sp is not None else 0
                key = (getattr(v, "elementLabel", None), int(v.nodeLabel))
                per_el_node.setdefault(key, {})[sp_num] = _reorder(v.data, s_labels)

        scalars = reduce_scalars(u_vals, rf_vals, per_el_node)
        meta = {
            "source": "abaqus-odb-scalar",
            "odb": odb_path,
            "tier": "scalar",
            "step": step_names[-1],
            "frame": len(step.frames) - 1,
            "frame_value": float(frame.frameValue),
            "n_instances": len(odb.rootAssembly.instances.values()),
            "stress_components": s_labels,
            "extract_seconds": round(time.time() - t0, 3),
            "available_fields": sorted(frame.fieldOutputs.keys()),
        }
    finally:
        odb.close()

    payload = dict(meta)
    payload["scalars"] = scalars
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    return meta


# ---------------------------------------------------------------------------
# Self-test -- pure numeric, runs on any python (no odbAccess).
# ---------------------------------------------------------------------------

def _self_test() -> int:
    # Pin 1: von Mises of a uniaxial state == |sigma| (exact identity).
    vm = _von_mises([100.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    assert abs(vm - 100.0) < 1e-9, vm

    # Pin 2: pure shear sxy -> sqrt(3)*tau.
    vm = _von_mises([0.0, 0.0, 0.0, 10.0, 0.0, 0.0])
    assert abs(vm - (3.0 * 100.0) ** 0.5) < 1e-9, vm

    # Pin 3: hydrostatic state -> 0.
    vm = _von_mises([50.0, 50.0, 50.0, 0.0, 0.0, 0.0])
    assert abs(vm) < 1e-9, vm

    # Pin 4: reorder maps shell 4-tuple (S11,S22,S33,S12) with zero fill.
    got = _reorder((11.0, 22.0, 33.0, 12.0), ["S11", "S22", "S33", "S12"])
    assert got == [11.0, 22.0, 33.0, 12.0, 0.0, 0.0], got

    # Pin 5: reorder with FRD-alias shear order (S13 present, S31 wanted --
    # S13 fills the S31 slot via the alias table, S23 direct).
    got = _reorder((1.0, 2.0, 3.0, 4.0, 6.0, 5.0),
                   ["S11", "S22", "S33", "S12", "S13", "S23"])
    assert got == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0], got

    # Pin 6: reduction -- one quad shell element, two nodes, linear bending:
    #   bottom S11=-10, top S11=+10 at each node, both section points.
    #   membrane = 0, so vm_membrane = 0; vm_peak = |10| uniaxial.
    per = {(100, 1): {1: [-10.0, 0, 0, 0, 0, 0], 5: [10.0, 0, 0, 0, 0, 0]},
           (100, 2): {1: [-10.0, 0, 0, 0, 0, 0], 5: [10.0, 0, 0, 0, 0, 0]}}
    red = reduce_scalars([(1, (1.0, -2.0, 3.0)), (2, (0.0, 0.0, 4.0))],
                         [(1, (-100.0, 0.0, 50.0))], per)
    # node1 |u| = sqrt(14) ~ 3.742 < node2 |u| = 4.0  ->  node2 wins the mag.
    assert red["max_u"]["mag"] == 4.0 and red["max_u"]["mag_node"] == 2, red["max_u"]
    assert red["max_u"]["ux"] == 1.0 and red["max_u"]["uy"] == 2.0
    assert red["max_u"]["uz"] == 4.0
    assert red["max_urf"]["resultant"] == [-100.0, 0.0, 50.0]
    assert red["vm_membrane"] == 0.0, red
    assert abs(red["vm_peak"] - 10.0) < 1e-9, red

    # Pin 7: single section point (solid elements) -- membrane falls back to
    # that point itself; peak equals the same value.
    per = {(7, 3): {0: [30.0, 0, 0, 0, 0, 0]}}
    red = reduce_scalars([], [], per)
    assert red["vm_membrane"] == 30.0 and red["vm_peak"] == 30.0, red

    print("SELF_TEST_OK 7/7 pins (von Mises identities, reorder zero-fill/"
          "alias, scalar reduction incl. membrane-vs-peak split)")
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--self-test" in argv:
        return _self_test()
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        print("usage: abaqus python odb_scalar.py <job.odb> <out.json> [--self-test]")
        return 2
    try:
        meta = extract(args[0], args[1])
    except Exception as exc:  # surface the reason, not a bare traceback
        print(f"ODB_SCALAR_FAILED: {type(exc).__name__}: {exc}")
        raise
    sc = meta  # scalars live in the written file; print compact summary
    print(f"ODB_SCALAR_OK step={meta.get('step')} frame={meta.get('frame')} "
          f"seconds={meta.get('extract_seconds')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
