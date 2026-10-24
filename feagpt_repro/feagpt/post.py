"""Result extraction - the "Analysis" stage of the GMSA pipeline.

Two solvers, one reduction
--------------------------
CalculiX writes results to an **FRD** text file (the same artifact FeaGPT
consumes).  Abaqus writes a binary **ODB**, which
:mod:`feagpt.abaqus_odb` converts into a JSON document with exactly the same
shape.  Both therefore land on the *same* in-memory structure::

    {"nodes": {label: (x, y, z)},
     "results": {"DISP": {label: (ux, uy, uz)},
                 "FORC": {label: (rx, ry, rz)},
                 "STRESS": {label: (sxx, syy, szz, sxy, syz, szx)}}}

and everything from :func:`summarize_data` onwards is shared.  That is the
point: swapping the solver must not change how a result is interpreted, or a
cross-solver comparison stops meaning anything.

The FRD reader is deliberately tolerant: it does not assume a fixed number of
result components, so it works for DISP (4), STRESS (6) and anything else the
solver emits.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

# --------------------------------------------------------------------------- #
# FRD parsing
# --------------------------------------------------------------------------- #


def _frd_values(line: str, ncomp: int):
    """Parse one `` -1`` data line into ``(id, (values...))``.

    CalculiX uses fixed-width fields: 3 header characters, an I10 identifier,
    then 12-character floats.  Two traps, both found the hard way:

    * the identifier field and a following *negative* value can look glued
      together (``4-6.87068E-10``) - reading columns 3:13 still gives the id;
    * the number of values actually present can be **smaller** than ``ncomp``:
      DISP declares 4 components but writes only the three translations, and
      the consumer is expected to derive the magnitude.

    So we read as many complete 12-character fields as the line really holds,
    instead of assuming ``ncomp``.
    """
    try:
        ident = int(line[3:13])
    except ValueError:
        parts = line.split()
        if len(parts) < 2:
            return None
        return _split_fallback(parts, ncomp)

    body = line[13:]
    vals: list[float] = []
    for i in range(len(body) // 12 + 1):
        chunk = body[12 * i:12 * (i + 1)]
        if not chunk.strip():
            break
        try:
            vals.append(float(chunk))
        except ValueError:
            break
    if not vals:
        return None
    return ident, tuple(vals)


def _split_fallback(parts: list[str], ncomp: int):
    """Last-resort parser for writers that do not use fixed-width columns."""
    head = parts[1]
    for cut in range(1, len(head)):
        if head[cut] in "+-" and (head[cut - 1].isdigit() or head[cut - 1] == "E"):
            head = head[:cut]
            break
    try:
        ident = int(head)
    except ValueError:
        return None
    tail = " ".join(parts[2:])
    vals = []
    for tok in tail.split():
        try:
            vals.append(float(tok))
        except ValueError:
            break
    return (ident, tuple(vals)) if vals else None


def parse_frd(path) -> dict:
    """Parse an FRD file into ``{"nodes": {...}, "results": {name: {id: vals}}}``."""
    nodes: dict[int, tuple] = {}
    results: dict[str, dict[int, tuple]] = {}
    block: str | None = None
    ncomp = 0

    with open(path, "r", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip():
                continue

            if line.startswith("    2C") or line.lstrip().startswith("2C"):
                block, ncomp = "nodes", 3
                continue
            if line.startswith(" -4") or line.startswith("-4"):
                name = line[3:13].strip() or "RESULT"
                try:
                    ncomp = int(line[13:18])
                except ValueError:
                    ncomp = 0
                block = name
                results.setdefault(block, {})
                continue
            if line.startswith(" -3") or line.startswith("-3"):
                block = None
                continue
            if (line.startswith(" -1") or line.startswith("-1")) and block:
                parsed = _frd_values(line, ncomp)
                if parsed is None:
                    continue
                ident, vals = parsed
                if block == "nodes":
                    nodes[ident] = vals
                else:
                    results[block][ident] = vals
    return {"nodes": nodes, "results": results}


def load_results_json(path) -> dict:
    """Load the ODB-derived JSON into the same structure :func:`parse_frd` returns.

    JSON object keys are strings; the rest of this module keys everything by
    integer label, so the conversion happens once, here, rather than being
    smeared across every consumer.
    """
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    data = {
        "nodes": {int(k): tuple(v) for k, v in doc.get("nodes", {}).items()},
        "results": {
            name: {int(k): tuple(v) for k, v in blk.items()}
            for name, blk in doc.get("results", {}).items()
        },
    }
    if "meta" in doc:
        data["meta"] = doc["meta"]
    return data


def load_any(path, mid_nodes: dict | None = None) -> dict:
    """Load either an FRD file or an ODB-derived JSON, chosen by extension.

    An FRD whose deck asked for ``OUTPUT=3D`` is folded back to the mid-surface
    by :func:`collapse_expanded_shell`, using the ``*NODE`` block of the deck
    found beside it to restore the original node labels.  Doing that here rather
    than at every call site means the pipeline, both verification scripts and
    the dataset exporter all see an ordinary mid-surface result set without a
    single line of solver- or output-specific code.
    """
    path = Path(path)
    if path.suffix.lower() == ".json" or path.name.endswith(".odb.json"):
        return load_results_json(path)
    data = parse_frd(path)
    inp = path.with_suffix(".inp")
    if inp.exists() and deck_requests_expanded(inp):
        mids = mid_nodes if mid_nodes is not None else read_deck_nodes(inp)
        data = collapse_expanded_shell(data, mids, read_deck_thickness(inp))
    return data


# --------------------------------------------------------------------------- #
# reductions
# --------------------------------------------------------------------------- #
def von_mises(s: tuple) -> float:
    """von Mises stress from the 6-component symmetric stress vector.

    Component order is the FRD one - ``(sxx, syy, szz, sxy, syz, szx)`` - and
    the Abaqus reader normalises to it, so this one function serves both
    solvers.
    """
    sxx, syy, szz, sxy, syz, szx = (list(s) + [0.0] * 6)[:6]
    return math.sqrt(
        0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2)
        + 3.0 * (sxy**2 + syz**2 + szx**2)
    )


def von_mises_inplane(s: tuple) -> float:
    """von Mises from the **in-plane** components only - ``(sxx, syy, szz, sxy)``.

    Why this exists
    ---------------
    CalculiX' ``*EL FILE, OUTPUT=2D`` writes the full 6-component tensor, so
    :func:`von_mises` includes the transverse-shear terms ``syz`` / ``szx``.
    Abaqus' membrane reduction is built from ``S11 / S22 / S33 / S12`` and carries
    no transverse shear at all.  The two numbers are therefore *different
    quantities*, and on a flat plate under transverse pressure the difference is
    the entire answer: measured on the 600x600 stiffened panel, the peak
    mid-surface node reads ``(2e-05, 2e-05, 5e-05, 0.0, -0.19867, 0.67184)``.
    The in-plane stress is zero - correct, because a linear analysis of a flat
    plate in pure bending has no membrane action - and the whole 1.21 MPa is
    shear, sitting in the boundary layer along the supported edges.

    So "max von Mises" is not comparable across the two solvers for a shell model
    until this reduction is applied to both.  Measured, the transverse-shear
    share is 100 % of the peak on the plain panel, 1.3 % on the 3-stringer panel
    (where the stringers carry the load in bending and axial), and 17.8 % on the
    wing box (where the spar/rib junctions carry the shear).
    """
    sxx, syy, szz, sxy = (list(s) + [0.0] * 6)[:4]
    return math.sqrt(
        0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2)
        + 3.0 * sxy**2
    )


# --------------------------------------------------------------------------- #
# expanded-shell collapse (CalculiX OUTPUT=3D -> mid-surface view)
# --------------------------------------------------------------------------- #
def _xy_key(x, y, nd: int = 4):
    """Column key for grouping expanded-shell layers.

    The two layers sit at the *same* (x, y) as the mid-surface node, because
    the offset is along the shell normal and the thickness is small compared
    with the mesh size.  4 decimals is 0.1 um on this mm model - enough to
    group the pair without ever merging two genuinely different nodes.
    """
    return (round(float(x), nd), round(float(y), nd))


def read_deck_nodes(inp_path) -> dict[int, tuple]:
    """Read the ``*NODE`` block of a deck: ``{label: (x, y, z)}``.

    The expanded-shell result has lost the mid-surface labels, but the deck
    that produced it still carries them, so the labels can be recovered rather
    than invented.  That matters: everything downstream keys on node label, and
    inventing new ones would silently break the cross-solver node-by-node match.
    """
    nodes: dict[int, tuple] = {}
    reading = False
    for line in Path(inp_path).read_text(errors="replace").splitlines():
        s = line.strip()
        if s.startswith("*"):
            reading = s.upper().startswith("*NODE")
            continue
        if not reading or not s or s.startswith("**"):
            continue
        parts = [p for p in s.split(",") if p.strip()]
        if len(parts) < 4:
            continue
        try:
            nodes[int(parts[0])] = tuple(float(p) for p in parts[1:4])
        except ValueError:
            continue
    return nodes


def _elset_of(header: str) -> str | None:
    """The ``ELSET=`` value of a ``*ELEMENT`` header line, upper-cased."""
    for tok in header.replace(",", " ").split():
        if tok.upper().startswith("ELSET="):
            return tok.split("=", 1)[1].upper()
    return None


def read_deck_elset_nodes(inp_path, elset: str) -> set[int]:
    """Node labels of one deck element set - a ``*ELEMENT, ELSET=<name>`` block.

    Gate 4 counts the *faces* the geometry produced; this reads the *elements*
    the solver was actually handed.  A wall that exists in the geometry but
    never reaches the deck therefore cannot pass a check built on it, which is
    what makes it usable as the "the webs carry load" evidence for the
    multi-cell wing box: look the stress up on exactly the nodes the ``E_WEBS``
    block connects.
    """
    want = elset.upper()
    out: set[int] = set()
    reading = False
    for line in Path(inp_path).read_text(errors="replace").splitlines():
        s = line.strip()
        if s.startswith("*"):
            reading = (s.upper().startswith("*ELEMENT") and _elset_of(s) == want)
            continue
        if not reading or not s or s.startswith("**"):
            continue
        parts = [p for p in s.replace(",", " ").split() if p]
        for p in parts[1:]:            # first field is the element label
            try:
                out.add(int(p))
            except ValueError:
                break
    return out


def deck_requests_expanded(inp_path) -> bool:
    """Did this deck ask CalculiX for the expanded-shell (``OUTPUT=3D``) result?"""
    try:
        txt = Path(inp_path).read_text(errors="replace").upper()
    except OSError:
        return False
    return "OUTPUT=3D" in txt


def read_deck_thickness(inp_path) -> float:
    """Largest shell thickness declared in a deck's ``*SHELL SECTION`` cards.

    This is the bound that makes layer pairing unambiguous.  The two layers of
    one shell sit ``t`` apart (``+/- t/2``) and nothing else is that close:
    measured on the wing box, neighbours of a mid-surface node are at 1.5 mm
    (= 3.0/2) and 2.0 mm (= 4.0/2) and at no other distance, while the upper and
    lower skins sit tens of mm apart.  Read from the deck, so it stays a property
    of the model rather than a constant guessed here.
    """
    vals: list[float] = []
    lines = Path(inp_path).read_text(errors="replace").splitlines()
    for i, ln in enumerate(lines):
        if not ln.strip().upper().startswith("*SHELL SECTION"):
            continue
        for j in range(i + 1, min(i + 4, len(lines))):
            s = lines[j].strip()
            if not s or s.startswith("*"):
                continue
            try:
                vals.append(abs(float(s.split(",")[0])))
            except ValueError:
                pass
            break
    return max(vals) if vals else 0.0


def _pair_layers_by_column(nodes: dict) -> dict:
    """Fallback pairing: group by (x, y), keep the columns of exactly two.

    Correct on a flat plate (measured: all 11761 columns pair, zero ambiguity)
    and wrong on anything curved - which is why it is only the fallback for when
    the deck's node table is unavailable.
    """
    cols: dict[tuple, list[int]] = {}
    for lbl, xyz in nodes.items():
        cols.setdefault(_xy_key(xyz[0], xyz[1]), []).append(lbl)
    out: dict[int, tuple] = {}
    for labels in cols.values():
        if len(labels) != 2:
            continue
        labels.sort(key=lambda l: float(nodes[l][2]))
        out[labels[0]] = (labels[0], labels[-1])
    return out


def _group_layers_by_deck(nodes: dict, mid_nodes: dict, thickness: float):
    """Assign every expanded node to its nearest mid-surface node.

    A mid-surface node does **not** always own exactly two layers.  Where a
    stringer web meets the skin, or two shell surfaces of different thickness
    share a boundary, each surface contributes its own pair.  Measured on the
    wing box: 4520 nodes own 2 layers, 534 own 4 and 20 own 6 - and
    ``5074 * 2 = 10148`` falls short of the 11296 expanded nodes that actually
    exist.  Averaging only the closest two therefore silently drops the load on
    the remaining 1148 nodes: the raw result's global force sum is zero to
    1e-3 N, and after such a collapse it came out at **5217 N**.

    Nearest-mid-node assignment accounts for every expanded node exactly once,
    so the collapse conserves what the raw result conserves.  Returns
    ``(groups, orphans)`` with ``groups: {mid_label: [expanded labels]}``.

    A pure (x, y) column cannot be used instead: on the wing box the skins share
    their (x, y) sampling, and a rib is a *vertical* face whose nodes all sit on
    one (x, y) line - the worst column held 81 nodes.
    """
    if not thickness:
        return {}, []
    cell = max(thickness, 1.0)

    grid: dict[tuple, list[int]] = {}
    for lbl, (x, y, z) in mid_nodes.items():
        grid.setdefault(
            (int(x // cell), int(y // cell), int(z // cell)), []
        ).append(lbl)

    groups: dict[int, list[int]] = {}
    orphans: list[int] = []
    for elbl, (x, y, z) in nodes.items():
        cx, cy, cz = int(x // cell), int(y // cell), int(z // cell)
        best = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for mlbl in grid.get((cx + dx, cy + dy, cz + dz), ()):
                        mx, my, mz = mid_nodes[mlbl]
                        d = (x - mx) ** 2 + (y - my) ** 2 + (z - mz) ** 2
                        if best is None or d < best[0]:
                            best = (d, mlbl)
        if best is None:
            orphans.append(elbl)
            continue
        groups.setdefault(int(best[1]), []).append(elbl)
    return groups, orphans


def collapse_expanded_shell(data: dict, mid_nodes: dict | None = None,
                            thickness: float = 0.0) -> dict:
    """Fold an ``OUTPUT=3D`` (expanded-shell) result back onto the mid-surface.

    Why this exists
    ---------------
    Measured on a 4-element plate (``_probe_d8/probe3.py``):

    * ``*EL FILE, OUTPUT=2D`` reports the layer **mean** - the centre node reads
      ``SXX = 0.24626`` and ``(12.4841 + -11.9915) / 2 = 0.2463``.  The bending
      term is averaged away, which is precisely why a mid-surface von Mises is
      useless for sizing on a plate in pure bending: it is identically zero.
    * ``*EL FILE, OUTPUT=3D`` reports the **expanded** shell: every mid-surface
      node becomes two nodes at ``+/- t/2`` (9 -> 18 on the probe; the panel goes
      11761 -> 23522; the wing box 5074 -> 11296), and the mid-surface labels are
      gone - in the probe 1..9 became 10..36, an offset that depends on the node
      count and is therefore not a mapping to rely on.

    So the outer fibre is only reachable through ``OUTPUT=3D``, and the price is
    that the labels move.  This function pays that price exactly once: it pairs
    each mid-surface node with its two layers, averages them back to the
    mid-surface, takes the worse layer as the outer fibre, and relabels both onto
    the deck's own node ids.  The result is an ordinary mid-surface result set
    that *also* carries ``STRESS_PEAK`` - the same structure
    :mod:`feagpt.abaqus_odb` already emits - so nothing downstream has to know
    the mesh was ever expanded.

    Idempotent: a result that is already mid-surface pairs nothing and is
    returned unchanged, so it is safe to call on either solver's output.
    """
    nodes = data["nodes"]
    blocks = data["results"]

    orphans: list[int] = []
    if mid_nodes:
        groups, orphans = _group_layers_by_deck(nodes, mid_nodes, thickness)
    else:
        groups = {k: list(v) for k, v in _pair_layers_by_column(nodes).items()}
    if not groups:
        return data

    mid_nodes_out: dict[int, tuple] = {}
    mid_res: dict[str, dict[int, tuple]] = {b: {} for b in blocks}
    peak_res: dict[str, dict[int, tuple]] = {}
    layer_counts: dict[int, int] = {}
    for mlbl, layers in groups.items():
        n = len(layers)
        layer_counts[n] = layer_counts.get(n, 0) + 1
        # The deck still holds the true mid-surface coordinate; prefer it over
        # the mean of the layers, which is the same point only to print
        # precision.
        if mid_nodes and mlbl in mid_nodes:
            mid_nodes_out[mlbl] = tuple(mid_nodes[mlbl])
        else:
            pts = [nodes[l] for l in layers]
            mid_nodes_out[mlbl] = tuple(
                sum(p[i] for p in pts) / n for i in range(3)
            )
        for name, blk in blocks.items():
            vals = [blk[l] for l in layers if l in blk]
            if len(vals) == n:
                mid_res[name][mlbl] = _fold_layers(vals, name in _FOLD_SUM)
        # Outer fibre: the layer carrying the worst von Mises - the sizing
        # number (decision D8).  On a bending model it is the only one with a
        # nonzero in-plane component.
        sblk = blocks.get("STRESS") or {}
        cand = [l for l in layers if l in sblk]
        if cand:
            worst = max(cand, key=lambda l: von_mises(sblk[l]))
            for name, blk in blocks.items():
                if worst in blk:
                    peak_res.setdefault(name, {})[mlbl] = tuple(blk[worst])

    out = {
        "nodes": mid_nodes_out,
        "results": {b: v for b, v in mid_res.items() if v},
        "meta": dict(data.get("meta") or {}),
    }
    if peak_res.get("STRESS"):
        out["results"]["STRESS_PEAK"] = peak_res["STRESS"]
    out["meta"]["collapsed_from"] = "OUTPUT=3D expanded shell"
    out["meta"]["collapse"] = {
        "expanded_nodes": len(nodes),
        "mid_nodes_out": len(mid_nodes_out),
        "orphan_expanded_nodes": len(orphans),
        "missing_mid_nodes": (len(mid_nodes) - len(mid_nodes_out)) if mid_nodes else None,
        "layers_per_mid_node": dict(sorted(layer_counts.items())),
        "relabelled_to_deck_ids": bool(mid_nodes),
    }
    return out


#: Blocks whose layers must be **summed**, not averaged, when folding an
#: expanded shell back to the mid-surface.
#:
#: Measured on the 4-element plate (``_probe_d8/probe7.py``), where OUTPUT=2D
#: and OUTPUT=3D exist on an identical mesh::
#:
#:     FORC  mid 1 : 2D -2.279230  =  lo -4.264610  +  hi +1.985390   (split)
#:     FORC  mid 5 : 2D -25.000000 =  lo -25.000000 +  hi -0.000000
#:     DISP  mid 5 : 2D -0.00300134 = (lo -0.00300375 + hi -0.00299893)/2
#:     STRESS      : 2D  0.24626    = (12.4841 + -11.9915)/2
#:
#: The layers straddle the mid-surface at ``+/- t/2``, so displacement and
#: stress are symmetric about it and average back to the mid value.  Force is
#: not: the layers *split* the mid-surface node's force, so only the **sum**
#: restores it.  Applying the average rule to force silently breaks
#: equilibrium - it left the wing box's global force sum at -139.8 N instead of
#: its true zero.
_FOLD_SUM = ("FORC", "RF")


def _fold_layers(vals: list[tuple], rule_sum: bool) -> tuple:
    n = len(vals)
    if rule_sum:
        return tuple(sum(v[i] for v in vals) for i in range(len(vals[0])))
    return tuple(sum(v[i] for v in vals) / n for i in range(len(vals[0])))


def reaction_sum(data: dict, node_ids=None, comp: int = 2) -> float:
    """Sum one force component over ``node_ids`` (all nodes if ``None``).

    The clamped root is the only place where this is a meaningful equilibrium
    check, and it is meaningful for *both* solvers:

    * CalculiX FRD ``FORC`` reports the *total external* force at a node:
      free nodes carry the applied load, constrained ones the reaction, and the
      sum over **all** nodes is therefore zero (measured on the wing box:
      +500.00046 N at the loaded tip, -500.00017 N at the clamped root, 0.0003 N
      over the whole model).  Restrict it to the clamp;

      Caveat, measured: with a *distributed* load such as a pressure the clamped
      nodes carry part of the applied load as well, so summing FORC over them
      does **not** give the reaction - it is short by the pressure lumped onto
      those nodes.  verify_panel.py predicts that share geometrically and
      subtracts it.
    * Abaqus ``RF`` reports the *reaction* only, so free nodes are zero.

    Restricted to the root nodes the two agree, which is what makes the
    equilibrium residual a genuine cross-solver invariant.
    """
    forc = data["results"].get("FORC") or data["results"].get("RF") or {}
    ids = forc.keys() if node_ids is None else node_ids
    total = 0.0
    for nid in ids:
        v = forc.get(nid)
        if v is not None and len(v) > comp:
            total += float(v[comp])
    return total


def summarize_data(data: dict, tips: dict | None = None) -> dict:
    """Reduce an in-memory result set to the scalars a data-generation run needs."""
    nodes = data["nodes"]
    results = data["results"]

    summary: dict = {
        "n_nodes": len(nodes),
        "results": sorted(results.keys()),
    }

    disp = results.get("DISP") or results.get("U") or {}
    if disp:
        # the last component, when present, is the magnitude; otherwise derive
        # it.  CalculiX writes 4 components, Abaqus 3 - both handled.
        mag = {nid: (v[3] if len(v) >= 4 else math.sqrt(sum(c * c for c in v[:3])))
               for nid, v in disp.items()}
        nid_max = max(mag, key=mag.get)
        summary["max_disp"] = mag[nid_max]
        summary["max_disp_node"] = nid_max
        summary["max_disp_coord"] = list(nodes.get(nid_max, ()))
        summary["max_w"] = max((abs(v[2]) for v in disp.values() if len(v) > 2), default=0.0)

    # ---- stress ---------------------------------------------------------- #
    # Registered definition (decision D8, 2026-10-03): the headline von Mises is
    # the OUTER-FIBRE peak.  The mid-surface value is recorded too, but under a
    # name that cannot be mistaken for the sizing number, because on a bending
    # model it is not merely different - it is identically zero for a flat plate
    # in pure bending (measured: 0.0 MPa on the plain panel), so a consumer
    # reading it as "the stress" would conclude the part is unloaded.  Both
    # solvers reach this channel the same way: Abaqus from its section points,
    # CalculiX via the expanded OUTPUT=3D result folded by
    # collapse_expanded_shell.
    midsurface = results.get("STRESS") or results.get("S") or {}
    if midsurface:
        vm = {label: von_mises(v) for label, v in midsurface.items()}
        loc = max(vm, key=vm.get)
        summary["max_von_mises_midsurface"] = vm[loc]
        summary["max_vm_midsurface_location"] = loc

    peak = results.get("STRESS_PEAK") or {}
    if peak:
        vm_p = {label: von_mises(v) for label, v in peak.items()}
        loc_p = max(vm_p, key=vm_p.get)
        summary["max_von_mises"] = vm_p[loc_p]
        summary["max_vm_location"] = loc_p
        summary["max_vm_element"] = loc_p  # legacy key, same value
        summary["max_von_mises_peak"] = vm_p[loc_p]
        summary["max_vm_peak_location"] = loc_p
        summary["max_von_mises_definition"] = "outer fibre"
    elif midsurface:
        # No outer-fibre channel on this result.  Fall back so the key always
        # exists, and *say* it is a fallback rather than letting a mid-surface
        # value quietly pass for the outer fibre.
        summary["max_von_mises"] = summary["max_von_mises_midsurface"]
        summary["max_vm_location"] = summary["max_vm_midsurface_location"]
        summary["max_vm_element"] = summary["max_vm_midsurface_location"]
        summary["max_von_mises_definition"] = "mid-surface (FALLBACK - no peak channel)"

    meta = data.get("meta")
    if meta:
        summary["solver_meta"] = {
            k: meta[k]
            for k in ("source", "step", "section_points", "stress_components",
                      "stress_type", "n_elements", "element_types",
                      "available_fields")
            if k in meta
        }

    if tips:
        summary.update(tips)
    return summary


def summarize(frd_path, tips: dict | None = None) -> dict:
    """Reduce an FRD file to the scalars a data-generation run needs.

    Goes through :func:`load_any`, not :func:`parse_frd`: a deck written since
    D8 asks for ``OUTPUT=3D`` (the expanded shell), and the expanded node labels
    are offset from the deck's, so reducing it raw would report a field the
    deck's own nodes cannot be matched against.  ``load_any`` folds it back
    first.
    """
    return summarize_data(load_any(frd_path), tips)


def dump_results_data(data: dict, out_json, out_csv=None) -> dict:
    """Write the reduced summary to JSON (and optionally a per-node CSV)."""
    summary = summarize_data(data)
    out_json = Path(out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    if out_csv is not None:
        out_csv = Path(out_csv)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        disp = data["results"].get("DISP", {})
        lines = ["node,x,y,z,ux,uy,uz,umag"]
        for nid in sorted(data["nodes"]):
            xyz = data["nodes"][nid]
            d = disp.get(nid, (0.0, 0.0, 0.0, 0.0))
            umag = d[3] if len(d) >= 4 else math.sqrt(sum(c * c for c in d[:3]))
            lines.append(
                f"{nid},{xyz[0]:.6g},{xyz[1]:.6g},{xyz[2]:.6g},"
                f"{d[0]:.6g},{d[1]:.6g},{d[2]:.6g},{umag:.6g}"
            )
        out_csv.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def dump_results(frd_path, out_json, out_csv=None) -> dict:
    """FRD convenience wrapper (kept for the original call signature).

    ``load_any`` for the same reason as :func:`summarize`.
    """
    return dump_results_data(load_any(frd_path), out_json, out_csv)
