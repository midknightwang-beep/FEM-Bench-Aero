"""M4 -- what makes two cases *the same model*, what each case is *for*, and
how the set is split.

Three questions, three answers.  None of them is a pipeline mechanic, which is
why they live in a module of their own instead of inside a script: they are
**dataset-design decisions**, and a decision that is buried in a script cannot
be reviewed, quoted, or enforced by a second tool.

1. Equivalence -- two cases describe the same model when they agree on the
   fields that *make* the model (shape and wall thicknesses) and differ only in
   fields that describe how it is *processed* (mesh size, solver, load, name).
   Rebuilding that pair with a different mesh size does not make it a different
   aircraft part.  This is the unit a split may not break.

2. Role -- why a case exists.  A case that pins the mesh algorithm is not a
   specimen of the structure; it is an ablation of the mesher, and it must ride
   along with the geometry it ablates.  A case with no stringers in a family
   whose whole point is stringers is a *degenerate* member (it collapses to
   something with a closed-form answer), not a point on a sweep.

3. Split -- which of train/val/test a case belongs to.  The **unit is the
   equivalence class, not the case**: splitting two same-model cases across
   train and test would hand the model the answer.  This is the concrete
   implementation of the "等价类不得跨集" rule.  Split is a **rule, not a
   table**: a case takes the first *declared holdout region* it matches, and a
   case matching none stays in train.  Declarations live per family; a family
   with no declaration yields ``unassigned``, which the checker fails.

Two independent derivations of the equivalence relation
-------------------------------------------------------
:func:`geometry_class` reads a **whitelist** of geometry fields;
:func:`geometry_class_complement` reads a **blacklist** -- every field of the
spec *except* the ones known to be about processing.  The two must produce the
same partition.  If they do not, some field's ownership is wrong (a geometry
field missing from the whitelist, or a non-geometry field wrongly excluded), and
that is exactly the kind of thing a single rule cannot see about itself.  The
checker lives in ``eval_dataset.py``; this module only exposes both.

Why a whitelist instead of a blacklist for the primary derivation: when the spec
grows a new non-geometric field (a solver option, a reporting flag), a blacklist
would silently drag it into the class and shatter every class that happens to
differ in it -- with no gate failing anywhere.  A whitelist ignores it by
default.  The blacklist exists only as the cross-check.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from . import fuselage, open_hole, panel
from .laminate import layup_from_params

# --------------------------------------------------------------------------- #
# 1. equivalence
# --------------------------------------------------------------------------- #


def family_of(spec) -> str:
    """Structure family of a case.  Thin alias so this module does not have to
    import all of ``topology`` for one string."""
    return str(getattr(getattr(spec, "structure", None), "family", "") or "wingbox")


def _canonical(obj):
    """Recursively normalise before hashing.

    Two normalisations matter, and both were earned rather than guessed:

    * **numbers lose their int/float spelling.**  ``chord: 1000`` and
      ``chord: 1000.0`` are the same model -- that is precisely the duplicate
      pair ``dedup_dataset.py`` removed by hand in M2 -- so they must land in
      the same equivalence class here.  ``json.dumps`` alone would keep them
      apart (``"1000"`` vs ``"1000.0"``).
    * **dict keys are sorted**, so field order in the JSON file is not part of
      the identity.
    """
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float)):
        f = float(obj)
        return int(f) if f.is_integer() else f
    if isinstance(obj, dict):
        return {k: _canonical(v) for k, v in sorted(obj.items())}
    if isinstance(obj, (list, tuple)):
        return [_canonical(v) for v in obj]
    return obj


def geometry_payload(spec) -> dict:
    """The whitelist: the fields that decide which model a case *is*.

    Per family, because where a family keeps its parameters is a family's own
    business: the wing box still uses the legacy ``airfoil`` block, while every
    family added from M3 onward (the stiffened panel, the fuselage barrel) uses
    ``structure.params``.  Wall thicknesses are geometry here even though they do
    not change the *surface*: two barrels that differ only in skin thickness are
    not the same part, and a split that separated them would be leaking a design
    variable even though the meshes are byte-identical.

    Branching on ``wingbox`` rather than on each new family is deliberate: a
    third family that forgets to be listed here would otherwise be hashed as
    ``asdict(airfoil)`` - which is *empty* for a barrel - and every barrel would
    collapse into one equivalence class, silently.  The default has to be the
    params branch, because that is where new families put things.
    """
    fam = family_of(spec)
    if fam == "wingbox":
        return {"family": fam, "geometry": asdict(spec.airfoil)}
    return {"family": fam, "geometry": dict(spec.structure.params)}


#: Top-level spec blocks that describe *processing*, not the model.
NON_GEOMETRY_TOP_LEVEL = (
    "name",        # a label
    "description",  # prose
    "material",    # constitutive law; changing it does not change the shape
    "mesh",        # how the model is discretised
    "load",        # what is applied to it
    "bc",          # how it is held
    "analysis",    # how it is solved
    "workdir",     # where it is written
    "extra",       # escape hatch
)


def geometry_payload_complement(spec) -> dict:
    """The blacklist: everything that is not known to be about processing."""
    d = spec.to_dict()
    for k in NON_GEOMETRY_TOP_LEVEL:
        d.pop(k, None)
    return d


def _digest(payload: dict) -> str:
    blob = json.dumps(_canonical(payload), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def geometry_class(spec) -> str:
    """Stable id of a case's equivalence class (whitelist derivation)."""
    return _digest(geometry_payload(spec))


def geometry_class_complement(spec) -> str:
    """Same relation, blacklist derivation -- the cross-check.

    The *ids* differ (different payloads); only the *partition* must agree.
    Comparing ids would be wrong, so ``eval_dataset.py`` compares the grouping.
    """
    return _digest(geometry_payload_complement(spec))


# --------------------------------------------------------------------------- #
# 2. role
# --------------------------------------------------------------------------- #

#: Parameters that make a wing box the family's default specimen.
WINGBOX_BASELINE = {
    "chord": 1000.0,
    "span": 2000.0,
    "skin_thickness": 3.0,
    "n_ribs": 5,
    "rib_thickness": 4.0,
    "spar_chordwise": (0.25, 0.7),
    "n_stringers_per_skin": 0,
    "stringer_kind": "blade",
    # T1 planar-shape knobs (D14), at their neutral values.  They belong in this
    # whitelist rather than simply being left out.  ``_is_wingbox_baseline`` is
    # ``all(got[k] == v)`` **over these keys**, so a swept box that still matches
    # chord/span/ribs would otherwise be labelled ``baseline`` next to the real
    # one.  Measured before the fix (2026-10-04): ``sweep_deg=20, n_str=0`` ->
    # ``_is_wingbox_baseline = True``, role ``baseline``.  Adding them here
    # changes the role of none of the eleven archived cases (all neutral) and
    # puts every swept/tapered box into ``sweep`` or its declared region.
    "tip_chord_ratio": 1.0,
    "sweep_deg": 0.0,
    # T6 cell-count knob, at its neutral value.  It belongs in this whitelist for
    # the reason the two T1 knobs do: ``_is_wingbox_baseline`` is
    # ``all(got[k] == v)`` **over the keys listed here**, so a multi-cell box
    # that keeps chord / span / ribs would be labelled the family's ``baseline``
    # next to the real one.  Measured before the fix
    # (``_m5_probe/t6_rule_prototype.py``): a one-web box came out
    # ``role=baseline``, ``split=train`` - a holdout shape sitting in train.
    "web_chordwise": (),
}

#: Parameters that make a fuselage barrel the family's default specimen (T3).
#: Same role the :data:`WINGBOX_BASELINE` plays: the neutral point a new barrel
#: is measured against, and the anchor ``infer_role`` reads to call a barrel the
#: family's ``baseline`` rather than a bare ``sweep`` point.  The values are the
#: ones :class:`feagpt.fuselage.FuselageParams` declares - restated here so the
#: *role* rule does not have to import the family just to compare numbers.
FUSELAGE_BASELINE = {
    "diameter": 2000.0,
    "length": 2000.0,
    "thickness": 3.0,
    "n_stringers": 8,
    "n_frames": 3,
    "stringer_kind": "blade",
}

ROLE_MEANING = {
    "baseline": "族的默认参数锚点（M2 回归基准）",
    "ablation": "显式钉住网格算法的对照（研究网格，不研究结构）",
    "sweep": "纯参数扫描点",
    "degenerate": "退化成员（如无长桁平板，可对解析解）",
    "feature": "含长桁 / 引入新截面形式",
}


def n_stringers(spec) -> int:
    """Stringer count of a case, whichever block the family keeps it in."""
    fam = family_of(spec)
    if fam in (panel.FAMILY, fuselage.FAMILY):
        return int(dict(spec.structure.params).get("n_stringers", 0) or 0)
    return int(getattr(spec.airfoil, "n_stringers_per_skin", 0) or 0)


def _is_wingbox_baseline(spec) -> bool:
    got = _canonical(asdict(spec.airfoil))
    want = _canonical(WINGBOX_BASELINE)
    return all(got.get(k) == v for k, v in want.items())


def _is_fuselage_baseline(spec) -> bool:
    """True when the barrel is the family's default specimen (the train anchor).

    Read through ``parse_params`` rather than off the raw ``params`` dict so the
    builder's defaults apply: a spec that leaves ``stringer_kind`` out is still
    the default (blade) barrel, and a raw-dict comparison would call it
    non-baseline just for omitting a key.
    """
    try:
        p = fuselage.parse_params(spec)
    except ValueError:
        return False
    got = _canonical(asdict(p))
    want = _canonical(FUSELAGE_BASELINE)
    return all(got.get(k) == v for k, v in want.items())


def infer_role(spec) -> str:
    """Why this case exists.  Ordered tests, first match wins.

    The ablation test is first on purpose: a case that pins the mesh algorithm
    is a *mesh* experiment, and calling it anything else would hide the one
    property that decides where it may be split (it must stay with the geometry
    it ablates).
    """
    if int(getattr(spec.mesh, "recombination_algorithm", 0) or 0) != 0:
        return "ablation"
    fam = family_of(spec)
    n_str = n_stringers(spec)
    if fam == panel.FAMILY:
        # A stringer-free panel is the degenerate end of a stiffened panel: it
        # collapses to a flat plate with a Navier closed-form solution
        # (verify_panel.py), which is a *different* reason to exist than "a
        # point on the stringer sweep".
        return "degenerate" if n_str == 0 else "feature"
    if fam == fuselage.FAMILY:
        # A stringer-free, two-frame barrel is the degenerate end here: it
        # collapses to a plain cylindrical shell with a closed-form
        # pressure-vessel answer (verify_barrel.py).  The default barrel (8
        # stringers, 3 frames) is the family's train anchor, and a new stringer
        # *section* is the feature signal - exactly as it is for the other two
        # families.
        nf = int(dict(spec.structure.params).get("n_frames", 2) or 2)
        if n_str == 0 and nf == 2:
            return "degenerate"
        if _is_fuselage_baseline(spec):
            return "baseline"
        kind = str(dict(spec.structure.params).get("stringer_kind", "blade") or "blade")
        if n_str > 0 and kind not in FORMS_ANCHORED_IN_TRAIN:
            return "feature"
        return "sweep"
    if fam == open_hole.FAMILY:
        # There is no ``degenerate`` member here: ``_validate`` refuses any hole
        # that is not strictly inside the plate, and the family's builder never
        # emits an uncut plate, so ``hole_d -> 0`` is a rejection rather than a
        # member with a closed-form answer.  The roles are therefore the default
        # coupon (``baseline``), an off-centre hole - a shape train has never
        # seen and the analytic yardstick does not describe (``feature``) - and
        # everything else (``sweep``).  Without this branch the coupon falls
        # through to the wing-box test below and, because ``OpenHoleParams``
        # specs carry a *default* ``AirfoilSpec`` - field-for-field
        # ``WINGBOX_BASELINE`` - came out ``baseline``; measured,
        # ``_m5_probe/t4_rule_prototype.py``.
        if _open_hole_offcentre(spec):
            return "feature"
        # T7 (D29): a laminate coupon is a point on the family's *material*
        # sweep - the same reading the multi-cell box's first instance gets
        # (sweep, with the anchor-geometry instance staying train via the
        # laminate predicates above).  "baseline" stays exclusive to the
        # aluminium anchor (_is_open_hole_baseline refuses layup specs).
        if "layup" in (spec.structure.params or {}):
            return "sweep"
        if _is_open_hole_baseline(spec):
            return "baseline"
        return "sweep"
    # T6: a box whose webs sit off the even spacing builds a section with
    # unequal cells - a form train has never seen - so it is the family's
    # ``feature``, the same reading the T stringer and the open-hole off-centre
    # coupon get.  An *evenly* divided box is a point on the cell-count sweep
    # and falls through to ``sweep`` below, exactly as a single planform knob
    # does.
    if _wingbox_web_offcentre(spec):
        return "feature"
    if n_str:
        return "feature"
    return "baseline" if _is_wingbox_baseline(spec) else "sweep"


# --------------------------------------------------------------------------- #
# 3. split
# --------------------------------------------------------------------------- #

TRAIN = "train"
SPLITS = ("train", "val", "test")

TARGET_RATIOS = {"train": 0.6, "val": 0.2, "test": 0.2}
"""What the split *would* be at a scale where 60/20/20 is reachable.  Quoted so
the current set's deviation from it is visible rather than silent; the deviation
is written into the manifest's ``limitations`` instead of being forgotten."""

#: Section forms whose *first* instance already sits in train -- the "form
#: anchor".  A member carrying one of these is a point on a sweep; a member
#: introducing a form that has no train instance is a generalisation target and
#: goes to test.  Data, not code, because adding a form is a dataset-design act.
FORMS_ANCHORED_IN_TRAIN = frozenset({"blade"})

WINGBOX_DEFAULT_RIBS = 5
WINGBOX_DEFAULT_CHORD = 1000.0


#: A wing box's two T1 planar-shape knobs in their neutral (prismatic) position.
PLANAR_SHAPE_NEUTRAL = (1.0, 0.0)

#: **D16 (2026-10-04).**  What *train* has learned, per dimension -- the
#: boundaries a single-dimension extrapolation must cross.  Train's widest
#: planform is ``sweep30`` and its thinnest tip is ``taper060``; its panel anchor
#: is the plain 600x600 coupon.  A single-knob case beyond one of these is the
#: planform / size analogue of the ribs rule (``n_ribs > 5`` -> val).  Declared
#: next to the neutral values they extend, because "what train has seen" is a
#: property of the dataset, not of a script.
#:
#: **D33 (2026-10-24)** moved the sweep bound 20 -> 30 by adding the station
#: ``sweep30`` to train.  Not a loosening of the exam: ``sweep40`` stays val and
#: ``sweep40_taper040`` stays test, so the axis still has an out-of-envelope
#: case to be measured on.  What changes is the *distance* 40 has to be
#: extrapolated over (20 deg -> 10 deg) and the number of stations the axis is
#: fitted through (3 -> 4).  Measured before landing: 0/52 archived cases change
#: side, D12 reproduces 11/11 (``_probe_m10/probe_d33_split.json``).
#:
#: **D36 (2026-10-24)** moved it 30 -> 35, for a reason that is not "more data":
#: D35 bought the interaction anchor ``sweep30_taper080`` and immediately paid
#: for it on the taper-neutral line (val ``sweep40`` -3.17 % -> -12.79 %, whole
#: val set 5.79 -> 6.86 %).  The model has **one** ``s^2`` coefficient and D35
#: handed it two jobs.  A station at the midpoint of 30 -> 40 lets the pure
#: curvature be measured on the axis that is damaged, without touching either
#: exam case.  Pre-registered before the solve (``_probe_m13/``): M5q predicted
#: 4.988 mm, a parabola through measured 0/10/20/30 predicted 5.137 mm; measured
#: **5.4293 mm** -- *above every estimate*, i.e. the whole 30..40 band is
#: under-predicted, not one station.  Measured before landing, 0/54 archived
#: cases change side, D12 reproduces 11/11 (``_probe_m13/d36_split_probe.json``).
WINGBOX_TRAIN_MAX_SWEEP = 35.0
WINGBOX_TRAIN_MIN_TIP_RATIO = 0.6

#: **D24 (2026-10-06).**  How many intermediate webs train has learned: the
#: family's first multi-cell box carries **one** (two cells).  The cell count is
#: the one *discrete* structural dimension this family has, so the anchor is a
#: count rather than a threshold.  Everything the two predicates
#: (:func:`_wingbox_web_offcentre`, :func:`_wingbox_web_single_extrapolation`)
#: compare against is this number - stated here, next to the fusion of T1/T3
#: anchors, because "what train has seen" is a property of the dataset.
WINGBOX_TRAIN_MAX_WEBS = 1
PANEL_TRAIN_SIZE = (600.0, 600.0)

#: **T3 (2026-10-05).**  What *train* has learned for the barrel family.  The
#: first barrel into the dataset is the default specimen - 8 stringers, 3 frames -
#: so those are the anchors a single-dimension extrapolation must cross.  Stated
#: as the same kind of object the wing box's ``WINGBOX_TRAIN_MAX_SWEEP`` and the
#: panel's ``PANEL_TRAIN_SIZE`` are: a property of the dataset, not of a script.
FUSELAGE_TRAIN_MAX_STRINGERS = 8
FUSELAGE_TRAIN_MAX_FRAMES = 3

#: **D25 (2026-10-06).**  The barrel's three *continuous* dimensions and the one
#: point train has actually seen: the default specimen ``D2000 x L2000 x t3``.
#: Exact-anchor rather than a max threshold, and deliberately so: a count
#: dimension has an interior train can be said to cover (``8`` learns "up to
#: eight", the D18 convention kept above), but a continuous dimension sampled
#: **once** has none - there is no interval the model has been shown.  So the
#: anchor is an equality and any movement off it is an extrapolation.
#:
#: Why this had to exist at all: before D25 the barrel's holdout regions read
#: ``n_stringers`` / ``n_frames`` only, so a new diameter, length or wall
#: thickness matched **nothing** and fell through to ``train`` (the default) -
#: silently, with every numeric gate still green.  That is the same class of
#: defect D16 found for the panel, and the same reason the panel got a size
#: region.
FUSELAGE_TRAIN_SIZE = (2000.0, 2000.0, 3.0)


def _fuselage_size_off_train(spec) -> list[str]:
    """Names of the barrel's continuous dimensions that sit off the anchor.

    Empty means "the default specimen", returned by the same comparison
    :func:`_is_fuselage_baseline` makes, so ``role`` and ``split`` cannot
    disagree about which barrel is the neutral one.
    """
    try:
        p = fuselage.parse_params(spec)
    except ValueError:
        return []
    d, L, t = float(p.diameter), float(p.length), float(p.thickness)
    out = []
    if d != FUSELAGE_TRAIN_SIZE[0]:
        out.append(f"直径 {d:g} ≠ {FUSELAGE_TRAIN_SIZE[0]:g}")
    if L != FUSELAGE_TRAIN_SIZE[1]:
        out.append(f"长度 {L:g} ≠ {FUSELAGE_TRAIN_SIZE[1]:g}")
    if t != FUSELAGE_TRAIN_SIZE[2]:
        out.append(f"壁厚 {t:g} ≠ {FUSELAGE_TRAIN_SIZE[2]:g}")
    return out


def _fuselage_counts_off_train(spec) -> list[str]:
    """The count dimensions (:func:`_fuselage_single_extrapolation`'s two)."""
    try:
        p = fuselage.parse_params(spec)
    except ValueError:
        return []
    out = []
    if int(p.n_stringers) > FUSELAGE_TRAIN_MAX_STRINGERS:
        out.append("n_stringers")
    if int(p.n_frames) > FUSELAGE_TRAIN_MAX_FRAMES:
        out.append("n_frames")
    return out


def _wingbox_planar_shape(spec) -> tuple[float, float]:
    """``(tip_chord_ratio, sweep_deg)``; defaults when the field is absent."""
    return (float(getattr(spec.airfoil, "tip_chord_ratio", 1.0) or 1.0),
            float(getattr(spec.airfoil, "sweep_deg", 0.0) or 0.0))


def _wingbox_swept_and_tapered(spec) -> str | None:
    """Both planar-shape knobs off-neutral at once -- the generalisation target.

    **D15 (2026-10-04).**  T1 ships four cases.  Three are single-degree points
    (sweep only, taper only): they stay in train, because the point of train is
    that the model may *learn* each knob.  The one case that moves both knobs at
    once is a shape train has never seen -- the same "new form -> test" signal
    the section-form (``str3_T``) and panel (``str3``) declarations already
    carry -- so it is declared a holdout region.  This is what makes the mixed
    "3 train + 1 test" split 老王 picked fall out of the rule rather than a table.

    **D35 (2026-10-24).**  D15's premise is the clause *"train 中两个自由度各只有
    单变量"* -- both knobs exist in train only at one non-neutral value each, so any
    combination is literally unseen.  D31 and D33 invalidated that premise: train
    now learns sweep at {0, 10, 20, 30} and taper at {0.6, 0.8, 0.9, 1.0}.  Under
    the old test, ``sweep20_taper060`` was flagged as a new shape even though
    **each of its two coordinates is a value train has seen** -- the only thing
    missing was the cross product.  Meanwhile D34's residual diagnosis
    (``_probe_m11/residual_diag.py``) found exactly that gap was fatal: train held
    **0** cases with ``sweep>0 & taper!=1``, so the interaction column
    ``s^2*(taper-1)`` was identically zero and could not be estimated at all.

    So the condition is split in two, the same way D31 splits a size axis into
    "outside the range = extrapolation" vs "off the anchor but inside = sweep
    point":

      * both knobs off-neutral **and at least one outside the train envelope**
        -> genuinely new shape -> holdout (test);
      * both knobs off-neutral **but both inside the envelope**
        -> an interior cross product -> not a holdout, falls through to train.

    Measured before landing, ``_probe_m12/d35_split_probe.py``: 53 archived cases,
    **exactly one** changes side -- ``sweep20_taper060`` test -> train;
    ``sweep40_taper040`` keeps test on both axes (40 > 30 and 0.4 < 0.6), so the
    planform exam still has its double-extrapolation case.  D12's frozen eleven
    contain no combination case, so the D12 reproducer assertion is untouched.
    """
    tr, sw = _wingbox_planar_shape(spec)
    if tr == PLANAR_SHAPE_NEUTRAL[0] or sw == PLANAR_SHAPE_NEUTRAL[1]:
        return None
    inside = (sw <= WINGBOX_TRAIN_MAX_SWEEP + 1e-9
              and tr >= WINGBOX_TRAIN_MIN_TIP_RATIO - 1e-9)
    if inside:
        # Both coordinates are values train has seen (D35): interior cross
        # product, not a new form.  Let it fall through so the size-axis rules
        # still get their say.
        return None
    return (f"新平面形状组合（后掠 {sw:g}° × 锥度 {tr:g} 兼具，"
            f"至少一轴出 train 值域 ≤{WINGBOX_TRAIN_MAX_SWEEP:g}° / "
            f"≥{WINGBOX_TRAIN_MIN_TIP_RATIO:g}）")


def _wingbox_new_form(spec) -> str | None:
    kind = str(getattr(spec.airfoil, "stringer_kind", "") or "")
    if n_stringers(spec) > 0 and kind not in FORMS_ANCHORED_IN_TRAIN:
        return f"新截面形式（train 里没有锚定 {kind!r} 形式）"
    return None


def _wingbox_double_extrapolation(spec) -> str | None:
    ribs = int(getattr(spec.airfoil, "n_ribs", WINGBOX_DEFAULT_RIBS))
    chord = float(getattr(spec.airfoil, "chord", WINGBOX_DEFAULT_CHORD))
    if ribs > WINGBOX_DEFAULT_RIBS and chord != WINGBOX_DEFAULT_CHORD:
        return (f"双维外推（肋 {ribs} > {WINGBOX_DEFAULT_RIBS} 且 "
                f"弦 {chord:g} ≠ {WINGBOX_DEFAULT_CHORD:g}）")
    return None


def _wingbox_single_extrapolation(spec) -> str | None:
    ribs = int(getattr(spec.airfoil, "n_ribs", WINGBOX_DEFAULT_RIBS))
    if ribs > WINGBOX_DEFAULT_RIBS:
        return f"单维外推（肋 {ribs} > {WINGBOX_DEFAULT_RIBS}，弦保持默认）"
    return None


# --------------------------------------------------------------------------- #
# T6 (D24, 2026-10-06) - the cell-count dimension
# --------------------------------------------------------------------------- #
def _wingbox_web_count(spec) -> tuple[int, bool]:
    """``(n_webs, evenly_spaced)``; ``(0, False)`` for every archived case.

    "Evenly spaced" is not a guess about intent - it is an equality against
    :meth:`feagpt.spec.AirfoilSpec.even_web_stations`, the **single** definition
    of the even in-board spacing (``geometry.build_wingbox`` places the webs by
    it, the rule compares against it).  Two copies of that definition would
    drift, and the drift would show up as a case silently changing side.

    False for a web-free box: "the webs are evenly spaced" is a statement about
    webs that exist, and the neutral box has none to space.
    """
    af = spec.airfoil
    try:
        return int(af.n_webs), bool(af.webs_are_even)
    except AttributeError:                  # a spec object built before T6
        return 0, False


def _wingbox_web_offcentre(spec) -> str | None:
    """Webs off the even in-board spacing -> test.

    **D24 (2026-10-06).**  The family's first multi-cell member is an evenly
    divided box.  Moving a web off that spacing is not extrapolating a number:
    the cells stop being equal, the shear-flow distribution stops being
    symmetric, and the analytic yardstick - Bredt-Batho on equally divided cells
    (``verify_multi_cell.py``) - no longer describes what was built.  That is
    the same "new form -> test" signal the off-centre hole (T4), the T stringer
    (T5) and the both-knobs planform (D15) carry.
    """
    n, even = _wingbox_web_count(spec)
    if n and not even:
        given = [round(float(v), 4) for v in spec.airfoil.web_chordwise]
        return (f"新形式：腹板偏离等分（给定 {given} ≠ 等分 "
                f"{[round(float(v), 4) for v in spec.airfoil.even_web_stations()]}；"
                f"闭室不再等面积，Bredt-Batho 不再描述该截面）")
    return None


def _wingbox_web_double_extrapolation(spec) -> str | None:
    """More webs **and** off their even spacing -> test (two knobs at once).

    The direct analogue of :func:`_wingbox_swept_and_tapered` (D15): both
    dimensions off-neutral at once is a shape train has never seen.  It must be
    declared **before** the single-dimension regions or it would fall through to
    them - which is why it leads :func:`_wingbox_web_offcentre` in the list even
    though the two agree on the off-centre case.
    """
    n, even = _wingbox_web_count(spec)
    if n > WINGBOX_TRAIN_MAX_WEBS and not even:
        return (f"双维外推（腹板 {n} > train 已学 {WINGBOX_TRAIN_MAX_WEBS} "
                f"且偏离等分）")
    return None


def _wingbox_web_single_extrapolation(spec) -> str | None:
    """More evenly spaced webs than train has learned -> val.

    **D24 (2026-10-06).**  Cell count is the family's own structural dimension,
    so this is the direct analogue of the ribs rule (``n_ribs > 5 -> val``), the
    planar single extrapolation (D16) and the barrel's count extrapolation
    (D18): the same knob pushed further, everything else neutral.  It is
    validation data rather than a holdout shape because the analytic comparison
    still applies - an evenly divided three-cell box is checked against
    Bredt-Batho exactly as the two-cell one is.
    """
    n, even = _wingbox_web_count(spec)
    if even and n > WINGBOX_TRAIN_MAX_WEBS:
        return (f"单维外推（腹板 {n} > train 已学 {WINGBOX_TRAIN_MAX_WEBS}，"
                f"位置仍等分）")
    return None


def _panel_new_form(spec) -> str | None:
    n = n_stringers(spec)
    if n > 0:
        return f"族内新形式（光板 ⇒ {n} 根长桁）"
    return None


def _wingbox_planar_single_extrapolation(spec) -> str | None:
    """One planform knob pushed past what train has learned -- the val analogue.

    **D16 (2026-10-04).**  Train learns each knob at non-neutral values
    (``sweep20``; ``taper060`` / ``taper080``).  Moving that *same* knob further
    while the other stays neutral is a single-dimension extrapolation, which is
    exactly what :func:`_wingbox_single_extrapolation` already means for ribs.
    Both knobs at once is **not** this region: :func:`_wingbox_swept_and_tapered`
    sits earlier in the list and claims it for test.
    """
    tr, sw = _wingbox_planar_shape(spec)
    if sw != 0.0 and tr == 1.0 and sw > WINGBOX_TRAIN_MAX_SWEEP:
        return (f"平面形状单维外推（后掠 {sw:g}° > train 已学 "
                f"{WINGBOX_TRAIN_MAX_SWEEP:g}°，锥度中性）")
    if tr != 1.0 and sw == 0.0 and tr < WINGBOX_TRAIN_MIN_TIP_RATIO:
        return (f"平面形状单维外推（锥度 {tr:g} < train 已学 "
                f"{WINGBOX_TRAIN_MIN_TIP_RATIO:g}，后掠中性）")
    return None


# --------------------------------------------------------------------------- #
# Wing-box size dimension (2026-10-24, D31)
# --------------------------------------------------------------------------- #

#: **D31 (2026-10-24).**  The wing box's two *continuous size* axes and the
#: range train is to cover on each.  Three stations apiece:
#: span 1600 / 2000 / 2400 and skin 2 / 3 / 4 mm.
#:
#: Why a range and not the exact anchor D25 used for the barrel: D25's own
#: argument is that a continuous dimension sampled **once** has no interior, so
#: an equality is the only honest reading.  Before this decision all 23 archived
#: boxes carried span = 2000 and skin = 3.0 -- one value each -- so a fit
#: assigned those axes coefficient 0.000 (measured, ``_probe_m7/learnability.py``)
#: and the physics prior ``u ~ span^3 / t`` degenerated into a constant factor
#: absorbed by the intercept.  Sampling the axis a few times *creates* the
#: interior, and then the range becomes the honest statement of what train has
#: seen - the D18 posture ("8 learns up to eight"), applied to a continuous axis.
#:
#: The endpoint values are set by measurement, not taste: the response is
#: ``u ~ span^3 / t`` to within 3.3 % over span 1600..3000 and to within 0.2 %
#: over skin 1.5..4 (``_probe_m8/physics_check.json``), so the three stations are
#: spread wide enough to pin both exponents without leaving the linear regime.
WINGBOX_TRAIN_SPAN = (1600.0, 2400.0)
WINGBOX_TRAIN_SKIN = (2.0, 4.0)

#: The size anchor the two axes are measured *from*.  Same job
#: :data:`WINGBOX_BASELINE` does for ``role``: the neutral point a combination
#: is "off" relative to.  Kept as its own tuple because a range cannot answer
#: "did this case move the axis?" - only "did it leave the range?".
WINGBOX_SIZE_ANCHOR = (2000.0, 3.0)


def _wingbox_size_axes_off(spec) -> tuple[list[str], list[str]]:
    """``(axes outside the train range, axes off the anchor)`` for a wing box.

    Two different questions, deliberately kept apart:

    * *outside the range* is an **extrapolation** - the case asks for something
      train was never shown, so it is val or test material.
    * *off the anchor but inside the range* is a **sweep point** - exactly what
      the four new train stations are: they move one axis off 2000 / 3.0 to
      teach the model that axis exists, and they must stay in train or the
      exercise is circular.

    Both lists are empty for every case archived before this decision (span and
    skin never moved), which is what makes the rule non-disruptive - measured,
    ``_probe_m8/probe_d31.json``, 0/23 cases change split.
    """
    if family_of(spec) != "wingbox":
        return [], []
    af = spec.airfoil
    span, skin = float(af.span), float(af.skin_thickness)
    out, off = [], []
    if not (WINGBOX_TRAIN_SPAN[0] - 1e-9 <= span <= WINGBOX_TRAIN_SPAN[1] + 1e-9):
        out.append(f"展长 {span:g} 出 train 区间 [{WINGBOX_TRAIN_SPAN[0]:g}, "
                   f"{WINGBOX_TRAIN_SPAN[1]:g}]")
    if not (WINGBOX_TRAIN_SKIN[0] - 1e-9 <= skin <= WINGBOX_TRAIN_SKIN[1] + 1e-9):
        out.append(f"壁厚 {skin:g} 出 train 区间 [{WINGBOX_TRAIN_SKIN[0]:g}, "
                   f"{WINGBOX_TRAIN_SKIN[1]:g}]")
    if abs(span - WINGBOX_SIZE_ANCHOR[0]) > 1e-9:
        off.append(f"展长 {span:g} ≠ {WINGBOX_SIZE_ANCHOR[0]:g}")
    if abs(skin - WINGBOX_SIZE_ANCHOR[1]) > 1e-9:
        off.append(f"壁厚 {skin:g} ≠ {WINGBOX_SIZE_ANCHOR[1]:g}")
    return out, off


def _wingbox_other_axes_off(spec) -> list[str]:
    """Axes D14/D24 already police, read at *their* anchors.

    ``chord`` is deliberately absent.  Chord 800 and 1000 are both in train, so
    chord is a train-interior axis like ribs 3/5 - moving it alone is not an
    extrapolation, and listing it here would re-label the three archived
    ``chord800`` boxes.  The chord x ribs interaction stays where D14 put it
    (:func:`_wingbox_double_extrapolation`).
    """
    af = spec.airfoil
    out = []
    if int(getattr(af, "n_ribs", WINGBOX_DEFAULT_RIBS)) > WINGBOX_DEFAULT_RIBS:
        out.append(f"肋 {int(af.n_ribs)} > {WINGBOX_DEFAULT_RIBS}")
    # NB: _wingbox_planar_shape returns (tip_chord_ratio, sweep_deg) -- in that
    # order.  Unpacking it as (sw, tr) silently reads every box as "tip ratio 0",
    # which trips the taper branch on every case; caught by
    # _probe_m8/check_d31_landed.py before this batch was archived.
    tr, sw = _wingbox_planar_shape(spec)
    if sw > WINGBOX_TRAIN_MAX_SWEEP:
        out.append(f"后掠 {sw:g}° > {WINGBOX_TRAIN_MAX_SWEEP:g}°")
    if tr < WINGBOX_TRAIN_MIN_TIP_RATIO:
        out.append(f"锥度 {tr:g} < {WINGBOX_TRAIN_MIN_TIP_RATIO:g}")
    n_web, _even = _wingbox_web_count(spec)
    if n_web > WINGBOX_TRAIN_MAX_WEBS:
        out.append(f"腹板 {n_web} > {WINGBOX_TRAIN_MAX_WEBS}")
    kind = str(getattr(af, "stringer_kind", "blade") or "blade")
    if n_stringers(spec) > 0 and kind not in FORMS_ANCHORED_IN_TRAIN:
        out.append(f"截面形式 {kind!r} 未在 train 锚定")
    return out


def _wingbox_size_double_extrapolation(spec) -> str | None:
    """Two wing-box dimensions at once -> test (D31).

    Three ways to get here, all the same judgement D14/D15 already make for
    ribs x chord and sweep x taper: the model is being asked for a corner of a
    table it has only seen one edge of.

    1. both size axes outside the range;
    2. one size axis outside the range *and* an already-policed axis off its
       anchor - the mixed case, which leaving to val would call
       "``span 3000 with 7 ribs``" a single-dimension extrapolation;
    3. both size axes off the anchor but still *inside* the range.  This is the
       interaction test: the four train stations each move exactly one axis, so
       a two-axis combination is a shape train has never seen even though every
       coordinate is in range.  Measured, the interaction is nearly
       multiplicative (``span2400_skin2`` is 0.06 % off the product of the two
       single-axis effects, ``_probe_m8/physics_check.json``), which makes the
       point a *fair* test rather than an impossible one - a model that learnt
       both axes separately should get it right, and if it does not, the fit has
       missed the multiplicative structure.
    """
    if family_of(spec) != "wingbox":
        return None
    out, off = _wingbox_size_axes_off(spec)
    others = _wingbox_other_axes_off(spec)
    if len(out) >= 2:
        return f"尺寸双维外推（{' 且 '.join(out)}）"
    if out and others:
        return (f"跨维外推（尺寸：{out[0]}；其他：{'、'.join(others)}）")
    if len(off) >= 2:
        return (f"尺寸双轴组合外推（{' 且 '.join(off)}；train 各站只动单轴，"
                f"交互项未见过）")
    return None


def _wingbox_size_single_extrapolation(spec) -> str | None:
    """One size axis outside the train range -> val (D31).

    The wing-box analogue of the barrel's D25 size rule and the panel's D16 size
    rule: push *one* continuous dimension past what train has been shown while
    everything else stays put.  Anything more is claimed by
    :func:`_wingbox_size_double_extrapolation` first.
    """
    if family_of(spec) != "wingbox":
        return None
    out, _off = _wingbox_size_axes_off(spec)
    if len(out) == 1:
        return f"尺寸单维外推（{out[0]}）"
    return None


def _panel_size_extrapolation(spec) -> str | None:
    """A panel at a size train has not seen -- the panel family's val.

    **D16 (2026-10-04), amended 2026-10-05.**  The panel family's only *train*
    anchor is the plain 600x600 coupon, so the plain panel is what the size
    dimension is measured from.  Its one stringered instance
    (``stiffened_panel_600x600_str3``) is D12-locked into test and therefore
    cannot anchor a val region without re-signing D12 -- which 老王 declined.

    The first version of this rule admitted **plain** panels only.  That left the
    whole val set stiffener-free, which is not a validation set for a family
    whose interesting behaviour is the stiffened one, so it was widened:
    **any** panel at a size train has not seen is a size-dimension
    extrapolation.  老王's call (路 A) was that *size is the panel's one
    continuous extrapolation dimension* and "stringered or not" is a discrete
    form axis, not a second dimension - so "stringered at a new size" is still a
    **single**-dimension extrapolation and belongs in val.

    This does not move the D12-locked case: ``600x600_str3`` is at the train
    size, so it misses this region and is still claimed by
    :func:`_panel_new_form` for test.  The ``rule_reproduces_D12`` gate is what
    proves that, and it is re-run after the amendment.
    """
    p = dict(getattr(getattr(spec, "structure", None), "params", None) or {})
    L = float(p.get("length", PANEL_TRAIN_SIZE[0]))
    W = float(p.get("width", PANEL_TRAIN_SIZE[1]))
    if (L, W) != PANEL_TRAIN_SIZE:
        return (f"平板尺寸单维外推（{L:g}x{W:g} ≠ train 已学 "
                f"{PANEL_TRAIN_SIZE[0]:g}x{PANEL_TRAIN_SIZE[1]:g}）")
    return None


def _fuselage_new_form(spec) -> str | None:
    """A barrel stringer in a section form train has not anchored -> test (T3).

    The same "new form -> test" signal the wing box's ``str3_T`` and the panel's
    ``str3`` carry, in the third family's vocabulary.  A blade is the anchored
    form; anything else (T, and whatever comes after) is a shape the model has
    not seen and must not be asked to extrapolate from.
    """
    try:
        p = fuselage.parse_params(spec)
    except ValueError:
        return None
    if int(p.n_stringers) > 0 and str(p.stringer_kind) not in FORMS_ANCHORED_IN_TRAIN:
        return f"新截面形式（train 里没有锚定 {p.stringer_kind!r} 形式）"
    return None


def _fuselage_single_extrapolation(spec) -> str | None:
    """One barrel dimension pushed past what train has learned -> val (T3).

    **D18 (2026-10-05).**  The barrel analogue of the ribs rule (单维外推 -> val):
    move *either* the stringer count *or* the frame count beyond the default
    specimen while the other stays put.  Both at once is **not** this region -
    :func:`_fuselage_double_extrapolation` sits earlier in the list and claims it
    for test, exactly as the wing box's ``_wingbox_swept_and_tapered`` precedes
    its planar val region.
    """
    try:
        p = fuselage.parse_params(spec)
    except ValueError:
        return None
    n, nf = int(p.n_stringers), int(p.n_frames)
    str_out = n > FUSELAGE_TRAIN_MAX_STRINGERS
    frm_out = nf > FUSELAGE_TRAIN_MAX_FRAMES
    if str_out and not frm_out:
        return (f"单维外推（长桁 {n} > train 已学 "
                f"{FUSELAGE_TRAIN_MAX_STRINGERS}，框数不变）")
    if frm_out and not str_out:
        return (f"单维外推（框 {nf} > train 已学 "
                f"{FUSELAGE_TRAIN_MAX_FRAMES}，长桁数不变）")
    return None


def _fuselage_double_extrapolation(spec) -> str | None:
    """Both barrel dimensions off the train envelope at once -> test (T3).

    **D18 (2026-10-05).**  Two independent extrapolations at once is a table the
    model has never seen a corner of, so it is a holdout shape rather than
    validation data - the same judgement ``_wingbox_double_extrapolation`` makes
    for ribs x chord and ``_wingbox_swept_and_tapered`` makes for the planform.
    """
    try:
        p = fuselage.parse_params(spec)
    except ValueError:
        return None
    n, nf = int(p.n_stringers), int(p.n_frames)
    if n > FUSELAGE_TRAIN_MAX_STRINGERS and nf > FUSELAGE_TRAIN_MAX_FRAMES:
        return (f"双维外推（长桁 {n} 与框 {nf} 同时超出 train 包络）")
    return None


def _fuselage_size_double_extrapolation(spec) -> str | None:
    """Two independent barrel extrapolations at once -> test (T3 / D25).

    Counts as "two" either two continuous dimensions moving together, or one
    continuous dimension moving *with* one count dimension - both are a corner of
    a table train has never seen, which is the judgement
    :func:`_fuselage_double_extrapolation` and
    :func:`_wingbox_swept_and_tapered` already make for their families.  Leaving
    the mixed case to the val region would call ``10 stringers at D1600`` a
    single-dimension extrapolation, which it plainly is not.

    Sits **ahead** of the two val regions in the match order for that reason.
    """
    size = _fuselage_size_off_train(spec)
    counts = _fuselage_counts_off_train(spec)
    if len(size) >= 2:
        return f"尺寸双维外推（{' 且 '.join(size)}）"
    if size and counts:
        return (f"跨维外推（尺寸：{size[0]}；计数：{'、'.join(counts)} 超出 "
                f"train 包络）")
    return None


def _fuselage_size_single_extrapolation(spec) -> str | None:
    """One continuous barrel dimension off the anchor -> val (T3 / D25).

    **D25 (2026-10-06).**  The barrel analogue of the panel's size rule: move
    *one* of diameter / length / wall thickness while the other two and both
    counts stay at the default specimen.  Anything more is claimed by
    :func:`_fuselage_size_double_extrapolation` first.
    """
    size = _fuselage_size_off_train(spec)
    if len(size) == 1:
        return f"尺寸单维外推（{size[0]}）"
    return None


# --------------------------------------------------------------------------- #
# T4 -- open-hole coupon (M5 / batch4, D23)
# --------------------------------------------------------------------------- #

#: **D23 (2026-10-06).**  The coupon's **train anchor**: the family's default
#: specimen, ``400 x 200 x 2 mm`` with a centred ``d = 20 mm`` hole
#: (``lambda = 0.1``).  Same role ``WINGBOX_DEFAULT_RIBS`` / ``PANEL_TRAIN_SIZE``
#: / ``FUSELAGE_TRAIN_MAX_STRINGERS`` play for the other three families.
OPEN_HOLE_BASELINE = {
    "length": 400.0,
    "width": 200.0,
    "thickness": 2.0,
    "hole_d": 20.0,
}

#: The ``lambda = d / width`` train has learned (from the anchor above).  A
#: *centred* coupon past it is a single-dimension extrapolation -> val.
OPEN_HOLE_TRAIN_LAMBDA = 0.1

#: The footprint train has learned.  Declared so the size dimension is a
#: declared region from the start rather than something discovered later - the
#: posture ``_wingbox_swept_and_tapered`` took before T1 arrived.
OPEN_HOLE_TRAIN_SIZE = (400.0, 200.0)

#: Hole-centre tolerance (mm) for "is the hole centred?".  The same scale
#: ``feagpt.open_hole.EDGE_TOL`` uses for "is the node on the edge?", i.e. four
#: orders below the smallest element the family's size field can produce.
OPEN_HOLE_CENTRE_TOL = 1e-6


def _open_hole_offcentre(spec) -> str | None:
    """An off-centre hole is a **new form** train has never seen -> test (D23).

    老王's call on 2026-10-06: the coupon's *continuous* dimension is ``lambda =
    d / width`` and the hole **position** is a *discrete form axis* - the same
    reading 路 A gave the panel ("size is the one continuous dimension; stringered
    or not is a discrete form axis"), so "off-centre at any lambda" is a new
    shape rather than the second corner of a 2-D grid.

    The physics agrees.  The family's whole yardstick - Kirsch, Howland, the Kt
    comparison in ``verify_hole.py`` - assumes the hole sits on the section's
    centre line.  Move it and the coupon is not extrapolating a number the model
    has seen, it is a shape no analytic result in the chain describes: exactly
    the signal ``str3_T`` / ``str3`` / the 12x4 barrel carry.
    """
    try:
        p = open_hole.parse_params(spec)
    except ValueError:
        return None
    cx, cy = p.center()
    mx, my = 0.5 * float(p.length), 0.5 * float(p.width)
    if abs(cx - mx) > OPEN_HOLE_CENTRE_TOL or abs(cy - my) > OPEN_HOLE_CENTRE_TOL:
        return (f"新形式：偏心孔（({cx:g}, {cy:g}) 偏离形心 ({mx:g}, {my:g})；"
                f"train 只有中心孔，偏心后 Howland 无解析对照）")
    return None


def _open_hole_lambda_extrapolation(spec) -> str | None:
    """A **centred** hole with ``lambda`` past what train has learned -> val (D23).

    The coupon's one continuous dimension, and the direct analogue of the ribs
    rule (``n_ribs > 5 -> val``), the wing box's planar single extrapolation
    (D16) and the barrel's count extrapolation (D18).  It is val rather than a
    holdout shape because the analytic comparison still applies: a centred
    ``lambda = 0.2`` coupon is checked against Howland exactly as the default is
    (measured: Kt_gross 3.1323 vs 3.1352, -0.09 %; ``verify_hole.py --trend``).

    The off-centre guard is not redundant with the region order - it makes this
    predicate mean what it says even if someone reorders the list, because a new
    *form* is test's business and never val's.
    """
    if _open_hole_offcentre(spec):
        return None
    try:
        p = open_hole.parse_params(spec)
    except ValueError:
        return None
    if p.lambda_ratio > OPEN_HOLE_TRAIN_LAMBDA + 1e-9:
        return (f"单维外推（孔径比 λ {p.lambda_ratio:.3f} > train 已学 "
                f"{OPEN_HOLE_TRAIN_LAMBDA:g}，孔仍居中）")
    return None


def _open_hole_size_extrapolation(spec) -> str | None:
    """A centred coupon at a footprint train has not seen -> val (D23).

    老王 asked for the size dimension to be declared from the start rather than
    added when the first case needs it, so it is here: the analogue of
    ``_panel_size_extrapolation`` (路 A) - size is a *second* continuous
    dimension whose first instance sits in train, so a coupon at another
    footprint is still a **single**-dimension extrapolation.  Like
    ``_wingbox_swept_and_tapered`` before T1, it matches nothing today and is the
    statement of a rule rather than dead code.
    """
    if _open_hole_offcentre(spec):
        return None
    try:
        p = open_hole.parse_params(spec)
    except ValueError:
        return None
    if (float(p.length), float(p.width)) != OPEN_HOLE_TRAIN_SIZE:
        return (f"尺寸单维外推（{p.length:g}x{p.width:g} ≠ train 已学 "
                f"{OPEN_HOLE_TRAIN_SIZE[0]:g}x{OPEN_HOLE_TRAIN_SIZE[1]:g}）")
    return None


def _open_hole_double_extrapolation(spec) -> str | None:
    """``lambda`` and the footprint move at once -> test (T4 / D28).

    **D28 (2026-10-08).**  The open-hole analogue of the barrel's D25 corner
    rule: two continuous dimensions moving together is a *corner* of the
    parameter space, and val regions that each learned one axis separately do
    not cover it.  Before this predicate existed such a coupon hit *both* val
    regions (lambda first, "first hit decides") and landed in **val** - the
    permissive reading, the same defect class D16 caught for the panel and
    D25 for the barrel, closed before any data could slip through it: the
    batch-7 corner point (``600x300 + d60``) would have been graded val.

    Both axes are tested "off the anchor" (``!=``), matching the barrel's D25
    reading: a lambda *below* train plus a new footprint is still two degrees
    of freedom moving at once, and the footprint alone already makes it an
    extrapolation.  The off-centre guard keeps the "new form is test's
    business, never val's" ordering robust to list reordering.
    """
    if _open_hole_offcentre(spec):
        return None
    try:
        p = open_hole.parse_params(spec)
    except ValueError:
        return None
    lam_off = abs(p.lambda_ratio - OPEN_HOLE_TRAIN_LAMBDA) > 1e-9
    size_off = (float(p.length), float(p.width)) != OPEN_HOLE_TRAIN_SIZE
    if lam_off and size_off:
        return (f"双维外推（λ {p.lambda_ratio:.3f} 与 {p.length:g}x{p.width:g} "
                f"同时 ≠ 锚点 λ {OPEN_HOLE_TRAIN_LAMBDA:g} / "
                f"{OPEN_HOLE_TRAIN_SIZE[0]:g}x{OPEN_HOLE_TRAIN_SIZE[1]:g}）")
    return None


def _is_open_hole_baseline(spec) -> bool:
    """True when the coupon is the family's default specimen (the train anchor).

    Read through ``parse_params`` so the builder's defaults apply, and judged on
    the *measured* centre rather than on ``hole_x``/``hole_y``: the family ships
    ``None`` as "centred", but an explicit ``(200, 100)`` builds the identical
    coupon (proved by ``check_forms.check_T4``'s ``default-centre`` half), and a
    role rule that called only one spelling baseline would be describing a
    spelling, not a model.

    Same shape as :func:`_is_fuselage_baseline`, and needed for the same reason
    the T1 planar knobs were: without it an open-hole coupon falls through to
    the wing-box test below, and because ``OpenHoleParams`` specs carry a
    *default* ``AirfoilSpec`` - field-for-field ``WINGBOX_BASELINE`` - it was
    labelled ``baseline`` next to the real one (measured,
    ``_m5_probe/t4_rule_prototype.py``).
    """
    try:
        p = open_hole.parse_params(spec)
    except ValueError:
        return False
    # T7 (D29): "baseline" names the *aluminium* train anchor.  A laminate
    # coupon on the same geometry is a different material - the point of the
    # family's material dimension - and must not wear the anchor's badge.
    if "layup" in (spec.structure.params or {}):
        return False
    if any(abs(float(getattr(p, k)) - float(v)) > OPEN_HOLE_CENTRE_TOL
           for k, v in OPEN_HOLE_BASELINE.items()):
        return False
    cx, cy = p.center()
    return (abs(cx - 0.5 * float(p.length)) < OPEN_HOLE_CENTRE_TOL
            and abs(cy - 0.5 * float(p.width)) < OPEN_HOLE_CENTRE_TOL)


# --- D30: the open-hole family's scalar axes -------------------------------- #
#: The anchor every open-hole axis is measured against: the aluminium default
#: coupon, and - for laminates - the ``[0/90]s`` stack at the same 2.0 mm.
OH_ANCHOR_LAMBDA = 0.1
OH_ANCHOR_SIZE = (400.0, 200.0)
OH_ANCHOR_THICKNESS = 2.0
OH_ANCHOR_LAYUP_CODE = "[0/90]s"


def open_hole_off_axes(spec) -> list[str]:
    """Which scalar axes this coupon has moved along, as human strings (D30).

    D30 (2026-10-24, the T7 build-out) turns the family's split rule from
    "how many *geometric* axes are off the anchor" into "how many *scalar
    axes of any kind* are off the anchor".  The family now has four:

    =========  ============================================================
    ``M``      stacking sequence - ``[0/90]s`` is the laminate anchor
    ``T``      wall thickness - the ply sum, 2.0 mm is the anchor
    ``L``      ``lambda_ratio`` - hole diameter over coupon width, 0.1
    ``S``      footprint ``(length, width)`` - 400 x 200
    =========  ============================================================

    The counting reading is the one D29 already used, just made explicit:
    a case on the anchor is ``train``, one axis off is ``val`` (single
    extrapolation), two or more is ``test`` (double extrapolation).  Measured
    against the shipped archive before it was adopted
    (``_probe_t7b/probe_d30_split.py``): **8/8** open-hole cases keep their
    declared split, so the new axes cost nothing that was already frozen.
    """
    p = open_hole.parse_params(spec)
    axes: list[str] = []

    lay = layup_from_params(spec.structure.params or {})
    t = lay.total_thickness if lay is not None else float(p.thickness)
    if lay is not None and lay.code != OH_ANCHOR_LAYUP_CODE:
        axes.append(f"铺层 {lay.code}≠{OH_ANCHOR_LAYUP_CODE}")
    if abs(t - OH_ANCHOR_THICKNESS) > 1e-9:
        axes.append(f"壁厚 t={t:g}≠{OH_ANCHOR_THICKNESS:g}")
    if abs(p.lambda_ratio - OH_ANCHOR_LAMBDA) > 1e-9:
        axes.append(f"λ={p.lambda_ratio:.4g}≠{OH_ANCHOR_LAMBDA:g}")
    if not (abs(float(p.length) - OH_ANCHOR_SIZE[0]) < 1e-9
            and abs(float(p.width) - OH_ANCHOR_SIZE[1]) < 1e-9):
        axes.append(f"尺寸 {float(p.length):g}x{float(p.width):g}"
                    f"≠{OH_ANCHOR_SIZE[0]:g}x{OH_ANCHOR_SIZE[1]:g}")
    return axes


def _open_hole_laminate_multi_axis(spec) -> str | None:
    """A **laminate** coupon off the anchor on two or more scalar axes -> test.

    Declared *ahead* of the single-axis rule and ahead of the all-aluminium
    corner rule so a composite corner is described by the predicate that names
    the material dimension - the one the model has least data on.
    """
    if "layup" not in (spec.structure.params or {}):
        return None
    axes = open_hole_off_axes(spec)
    if len(axes) >= 2:
        return "复材多维外推（" + " + ".join(axes) + "；D30 标量轴计数 ≥2）"
    return None


def _open_hole_laminate_single_axis(spec) -> str | None:
    """A **laminate** coupon exactly one scalar axis off the anchor -> val.

    The material axis is itself the new dimension, so the first laminate
    coupon *on the anchor* - ``[0/90]s`` at 2.0 mm on the 400x200 coupon -
    stays **train** (the T6 ``web1`` precedent: a form's first instance must
    be something the model sees).  One axis on top of that is the
    single-extrapolation reading every family shares.
    """
    if "layup" not in (spec.structure.params or {}):
        return None
    axes = open_hole_off_axes(spec)
    if len(axes) == 1:
        return "复材单维外推（" + axes[0] + "；D30 标量轴计数 =1）"
    return None


HOLDOUT_REGIONS: dict[str, tuple[tuple[str, object], ...]] = {
    "wingbox": (
        ("test", _wingbox_swept_and_tapered),
        ("test", _wingbox_new_form),
        ("test", _wingbox_double_extrapolation),
        ("test", _wingbox_web_double_extrapolation),
        ("test", _wingbox_web_offcentre),
        ("test", _wingbox_size_double_extrapolation),
        ("val", _wingbox_web_single_extrapolation),
        ("val", _wingbox_planar_single_extrapolation),
        ("val", _wingbox_single_extrapolation),
        ("val", _wingbox_size_single_extrapolation),
    ),
    panel.FAMILY: (
        ("val", _panel_size_extrapolation),
        ("test", _panel_new_form),
    ),
    fuselage.FAMILY: (
        ("test", _fuselage_new_form),
        ("test", _fuselage_double_extrapolation),
        ("test", _fuselage_size_double_extrapolation),
        ("val", _fuselage_single_extrapolation),
        ("val", _fuselage_size_single_extrapolation),
    ),
    open_hole.FAMILY: (
        ("test", _open_hole_offcentre),
        ("test", _open_hole_laminate_multi_axis),
        ("val", _open_hole_laminate_single_axis),
        ("test", _open_hole_double_extrapolation),
        ("val", _open_hole_lambda_extrapolation),
        ("val", _open_hole_size_extrapolation),
    ),
}
"""Per family, the declared holdout regions **in match order**.

A region is ``(side, predicate)``; the predicate returns a reason string when
the region applies, else ``None``.  **The first hit decides.**  A case that hits
no region stays in train -- that default is what lets the rule scale: declare
only the *interesting* regions, everything else is training data, and a new case
lands correctly without anyone touching a table.  A family with no entry here is
a declaration gap: its cases become ``unassigned`` and ``eval_dataset.py`` fails
the run -- the signal to declare the family, never to guess a default.

Replacing the M4 explicit table with this rule is **D12 continued**
(2026-10-04).  The rule was required to *reproduce* the D12-locked 口径 A on the
eleven cases present -- see :data:`D12_LOCKED_SPLIT`, which the checker asserts
against -- and it does, 11/11.  The judgement did not vanish when the table did;
it moved from eleven rows to four declarations, which is the shape that still
holds at two hundred cases.

**D15 (2026-10-04)** added the fifth declaration, ``_wingbox_swept_and_tapered``
(leading the wingbox list).  It matches **none** of the eleven locked cases -- so
``D12_LOCKED_SPLIT`` still reproduces 11/11 -- and exists so that T1's
both-knobs case is a held-out *shape* while its single-knob siblings stay in
train.  A declaration that matches nothing today is not dead code: it is the
statement of a rule, and T1 is the first data it governs.

**D16 (2026-10-04)** generalises the ribs rule (*单维外推 -> val, 双维外推 ->
test*) to the two dimensions the dataset grew since D12: the wing box
**planform** knobs and the **panel size**.  Two declarations were added --
``_wingbox_planar_single_extrapolation`` (val, after the three test regions so
that a two-knob case is still claimed by ``_wingbox_swept_and_tapered``) and
``_panel_size_extrapolation`` (val, ahead of the panel new-form region).  Both
were prototyped in memory before landing (``_m5_probe/d16_rule_prototype.py``,
VERDICT PASS): **0 side changes among the fifteen cases present, 11/11 D12**,
and the eight proposed batch cases land exactly 4 val / 3 train / 1 test.
老王's two calls that shape it: anchor the panel val on the *plain* coupon
(declining a D12 re-sign), and keep the first instance of each knob in train so
the model may learn it before it is extrapolated.

**2026-10-05** amends the panel val region (路 A): it no longer requires the
panel to be plain, so the val set can hold a *stiffened* panel at an unseen size
while ``600x600_str3`` stays D12-locked into test.  The same day adds the third
family's regions (``fuselage.FAMILY``) - **D18** - through the two predicates
``_fuselage_new_form`` and ``_fuselage_double_extrapolation`` (test) and
``_fuselage_single_extrapolation`` (val).  None of the twenty-three cases present
at the time matched any of them, which is the point: like
``_wingbox_swept_and_tapered`` they are a rule stated before the data that will
exercise it.  Two of them have since acquired data - the batch-3 barrel
``fuselage_barrel_d2000_l2000_str12_frm4`` (12 stringers **and** 4 frames, both
past the anchor) is the first case ``_fuselage_double_extrapolation`` claims,
and it lands in test, which is what the declaration said it would.

**D23 (2026-10-06)** declares the fourth family (``open_hole.FAMILY``).  老王's
three calls, each on a fork this family makes for the first time:

* **the hole position is a discrete form axis, not a second continuous one**, so
  an off-centre hole is ``test`` at *any* ``lambda`` - the reading 路 A gave the
  panel, applied to a family whose analytic yardstick stops applying the moment
  the hole leaves the centre line;
* **the first batch is small** - three cases, one per outcome - matching batch 3
  rather than opening with a sweep;
* **the size dimension is declared now** rather than when the first case needs
  it, so ``_open_hole_size_extrapolation`` is in the list from the start.

Prototyped in memory first (``_m5_probe/t4_rule_prototype.py``, VERDICT PASS):
**0 side changes among the twenty-six cases on disk, 11/11 D12**, and the three
proposed cases land 1 train / 1 val / 1 test.  The same prototype found the
declaration gap this paragraph closes: with no ``infer_role`` branch an open-hole
coupon was reported ``baseline`` (its spec carries a default ``AirfoilSpec``,
which is field-for-field ``WINGBOX_BASELINE``) and ``assign_split`` returned
``unassigned``.

**D24 (2026-10-06)** adds the cell-count dimension to the wing-box family - the
last structural dimension that had not moved (task T6).  老王's four calls:

* **multi-cell is a new form axis of the wing-box family, not a new family** -
  the box already owns the section, the ribs and the stringers, and a web is one
  more plane ``x = const`` in that same section.  Extending the family also
  keeps the whole existing chain (geometry, meshing, post, gate 4, the
  cross-solver comparison) in play instead of rebuilding it;
* **the load case is bending + end torque**, because a cell count is only
  observable in torsion: under pure bending a web merely adds web area, and the
  multi-cell and single-cell responses stay close enough that the case would
  measure nothing.  (Torque is emitted as an in-plane couple on the tip section,
  ``spec.extra["end_torque"]`` - the same arrangement the T3 barrel's end moment
  already uses.)
* **the split follows D16** - first instance in train, single-dimension
  extrapolation -> val, off-centre spacing -> test.  Three declarations spliced
  into the wing-box list, ordered so that the two-knob test region leads the
  single-knob ones, exactly as ``_wingbox_swept_and_tapered`` leads
  ``_wingbox_planar_single_extrapolation``;
* **the first batch is three cases**, one per outcome, matching batch 3 and
  batch 4 rather than opening with a sweep.

Prototyped in memory first (``_m5_probe/t6_rule_prototype.py``, VERDICT PASS):
**0 side changes among the twenty-nine cases on disk, 11/11 D12**, and the three
proposed cases land 1 train / 1 val / 1 test.  The prototype also re-measured
the trap T1 hit: with ``web_chordwise`` missing from ``WINGBOX_BASELINE`` a
one-web box came out ``role=baseline`` / ``split=train``, because
``_is_wingbox_baseline`` is an ``all()`` over the keys the whitelist *lists* -
so the new field had to be added there as well, at its neutral value.
"""


def split_of(spec) -> tuple[str, str]:
    """``(side, reason)`` for a case.

    ``unassigned`` means the family has no declared regions -- a failure the
    checker reports, never a silent default.
    """
    # v1.1（W5d：「真内插留出」）：用**显式声明**认领，先于族谓词。
    # 为什么不让族谓词去猜参数组合：内插点的特征就是「每个轴都落在包络内」，
    # 任何按数值写的谓词都会同时命中一堆既有 train 条（实测会把 D12 锁定的 11 条重新划分）。
    # 声明式的好处是**只认领点了名的案例**：新增 spec 打 tag 才进 exam，删 tag 就回 train。
    _tag = getattr(spec, 'extra', None) or {}
    if isinstance(_tag, dict) and str(_tag.get('split_tag') or '') == 'v11_interior_holdout':
        return "test", "v1.1 内插留出（spec.extra.split_tag = v11_interior_holdout，显式声明）"
    regions = HOLDOUT_REGIONS.get(family_of(spec))
    if regions is None:
        return "unassigned", f"族 {family_of(spec)!r} 未声明留出区域 —— 需补声明"
    for side, predicate in regions:
        why = predicate(spec)
        if why:
            return side, why
    return TRAIN, "落在训练包络内（未命中任何留出区域）"


def assign_split(spec) -> str:
    """``train`` / ``val`` / ``test`` / ``unassigned``."""
    return split_of(spec)[0]


def split_reason(spec) -> str:
    return split_of(spec)[1]


#: D12 (2026-10-04) locked the eleven-case split to 口径 A.  The rule above was
#: written to reproduce it, and the checker asserts it still does.  This frozen
#: copy exists so that editing a declaration -- the whole point of having
#: declarations -- cannot *silently* re-assign one of those cases: if it does,
#: ``eval_dataset.py`` fails and the change has to be acknowledged rather than
#: discovered later in a training run.
D12_LOCKED_SPLIT = {
    "naca4412_wingbox": "train",
    "naca4412_wingbox_recombination_algorithm3": "train",
    "naca4412_wingbox_n_ribs3_chord1000": "train",
    "naca4412_wingbox_n_ribs3_chord800": "train",
    "naca4412_wingbox_n_ribs5_chord800": "train",
    "naca4412_wingbox_str3": "train",
    "stiffened_panel_600x600": "train",
    "naca4412_wingbox_n_ribs7_chord1000": "val",
    "naca4412_wingbox_n_ribs7_chord800": "test",
    "naca4412_wingbox_str3_T": "test",
    "stiffened_panel_600x600_str3": "test",
}
