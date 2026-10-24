"""Stage 1 - Engineering Analysis Planning.

FeaGPT's planner is a knowledge-augmented LLM (Gemini 2.5 Pro) that turns
free-form engineering text into a structured JSON specification, retrieving a
validated template from a vector knowledge base when the semantic similarity
exceeds ``sigma > 0.85`` and otherwise synthesising a new definition.

Reproducing the *LLM* is not the point of this repository; reproducing the
*contract* is.  This module therefore implements a small deterministic parser
that emits the very same :class:`~feagpt.spec.FEASpec`, and marks precisely
where an LLM call would be inserted.  Swapping in a real model is a
single-function change and nothing downstream notices.
"""

from __future__ import annotations

import re

from .spec import AnalysisSpec, AirfoilSpec, FEASpec, LoadSpec, MaterialSpec, MeshSpec

# --------------------------------------------------------------------------- #
# knowledge base (FeaGPT keeps this in a vector index; here it is a dict)
# --------------------------------------------------------------------------- #
MATERIAL_LIBRARY: dict[str, MaterialSpec] = {
    "aluminium": MaterialSpec("Aluminium 2024-T3", 73100.0, 0.33, 2.78e-9, 345.0),
    "aluminum": MaterialSpec("Aluminium 2024-T3", 73100.0, 0.33, 2.78e-9, 345.0),
    "alu": MaterialSpec("Aluminium 2024-T3", 73100.0, 0.33, 2.78e-9, 345.0),
    "steel": MaterialSpec("Steel AISI 4340", 210000.0, 0.30, 7.85e-9, 470.0),
    "titanium": MaterialSpec("Titanium Ti-6Al-4V", 113800.0, 0.342, 4.43e-9, 880.0),
    "cfrp": MaterialSpec("CFRP homogenised", 135000.0, 0.30, 1.60e-9, None),
    "carbon": MaterialSpec("CFRP homogenised", 135000.0, 0.30, 1.60e-9, None),
    "composite": MaterialSpec("CFRP homogenised", 135000.0, 0.30, 1.60e-9, None),
}

# airfoil keyword -> NACA code, used when the text names a section by family
AIRFOIL_ALIASES = {"naca4412": "4412", "naca0012": "0012", "naca2412": "2412"}


# --------------------------------------------------------------------------- #
# planner
# --------------------------------------------------------------------------- #
def parse_text(text: str) -> FEASpec:
    """Turn a one-line engineering description into a :class:`FEASpec`.

    Examples that parse:
        "NACA4412 wing box, chord 1000 mm, span 2000 mm, 5 ribs, aluminium"
        "naca0012 wing, chord 800mm span 1500mm ribs 3 steel"
    """
    spec = FEASpec()
    low = text.lower()

    # --- airfoil -------------------------------------------------------- #
    m = re.search(r"naca\s*0?(\d{4})", low)
    if m:
        spec.airfoil.code = m.group(1)
    else:
        for alias, code in AIRFOIL_ALIASES.items():
            if alias in low.replace(" ", ""):
                spec.airfoil.code = code
                break

    # --- dimensions ----------------------------------------------------- #
    spec.airfoil.chord = _find_dimension(low, ("chord", "c="), spec.airfoil.chord)
    spec.airfoil.span = _find_dimension(low, ("span", "b="), spec.airfoil.span)
    spec.airfoil.skin_thickness = _find_dimension(
        low, ("skin", "skin_thickness"), spec.airfoil.skin_thickness
    )

    m = re.search(r"(\d+)\s*(?:ribs?|翼肋)", low)
    if m:
        spec.airfoil.n_ribs = max(2, int(m.group(1)))

    m = re.search(r"(\d+)\s*(?:stringers?|长桁)", low)
    if m:
        spec.airfoil.n_stringers_per_skin = int(m.group(1))

    # --- material ------------------------------------------------------- #
    for key, mat in MATERIAL_LIBRARY.items():
        if key in low:
            spec.material = mat
            break

    # --- load ----------------------------------------------------------- #
    m = re.search(r"pressure\s*[:=]?\s*([\d.]+)\s*mpa", low)
    if m:
        spec.load.kind = "pressure"
        spec.load.magnitude = float(m.group(1))
    m = re.search(r"([\d.]+)\s*mpa", low)
    if m and "pressure" not in low:
        spec.load.kind = "pressure"
        spec.load.magnitude = float(m.group(1))

    spec.name = f"naca{spec.airfoil.code}_wingbox"
    spec.description = text.strip()
    return spec

    # ------------------------------------------------------------------ #
    # LLM HOOK
    # ------------------------------------------------------------------ #
    # To use a real model, replace the body above with:
    #
    #     payload = retrieve_templates(text, top_k=3)      # vector search
    #     prompt  = build_prompt(text, payload)            # sigma > 0.85 reuse
    #     data    = call_llm(prompt)                       # -> dict
    #     return FEASpec.from_dict(data)
    #
    # Nothing downstream changes, because everything downstream reads FEASpec.


def _find_dimension(text: str, keys: tuple[str, ...], default: float) -> float:
    for key in keys:
        m = re.search(rf"{re.escape(key)}\s*[:=]?\s*([\d.]+)\s*(mm)?", text)
        if m:
            return float(m.group(1))
    return default


# --------------------------------------------------------------------------- #
# parametric sweeps (FeaGPT's "432 configurations")
# --------------------------------------------------------------------------- #
def expand(axis: str, values: list) -> list[tuple[str, object]]:
    """Turn ``"airfoil.n_ribs"`` + values into (path, value) pairs."""
    return [(axis, v) for v in values]


def sweep(base: FEASpec, axes: dict[str, list]) -> list[FEASpec]:
    """Cartesian product of parameter axes, each returning a derived spec.

    ``axes`` maps a dotted attribute path to the values to enumerate, e.g.::

        {"airfoil.n_ribs": [3, 5, 7], "airfoil.chord": [800, 1000]}
    """
    import copy
    import itertools

    paths = list(axes.keys())
    combos = list(itertools.product(*(axes[p] for p in paths)))
    specs: list[FEASpec] = []
    for i, combo in enumerate(combos):
        s = copy.deepcopy(base)
        tag = []
        for path, value in zip(paths, combo):
            obj, _, attr = path.rpartition(".")
            target = getattr(s, obj) if obj else s
            setattr(target, attr, value)
            tag.append(f"{attr}{value}")
        s.name = f"{base.name}_{'_'.join(tag)}"
        s.extra["sweep_index"] = i
        specs.append(s)
    return specs
