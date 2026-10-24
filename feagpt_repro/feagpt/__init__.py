"""feagpt_repro - a runnable reproduction of the FeaGPT GMSA pipeline.

Reference
---------
Yupeng Qi, Ran Xu, Xu Chu.
"FeaGPT: an End-to-End agentic-AI for Finite Element Analysis."
arXiv:2510.21993 (2025).  https://arxiv.org/abs/2510.21993

What is reproduced
------------------
* the **standardised-JSON contract** between stages  (``spec.py``)
* **parametric geometry generation**                  (``geometry.py``)
* **physics-aware adaptive meshing** with a quality gate (``meshing.py``)
* **deck generation, CalculiX and Abaqus dialects**   (``inp_writer.py``)
* **solver execution** (CalculiX *and* Abaqus)        (``solver.py``)
* **result extraction, solver-agnostic**              (``post.py``)
* **end-to-end orchestration**                        (``pipeline.py``)

Note that ``abaqus_odb.py`` is deliberately **not** in ``__all__``: it is not a
library module, it is a script executed by Abaqus' own interpreter (because
``odbAccess`` only exists there).  Importing it from here would fail.

What is *not* reproduced
------------------------
The LLM "project manager" and the vector knowledge base of the planning stage.
Their output is a structured JSON specification, so the planning stage is
replaced by a deterministic rule-based planner (:mod:`feagpt.planning`) whose
output has exactly the same shape.  Substituting a real LLM later changes only
that one module.  Geometry is generated with Gmsh's OpenCASCADE kernel instead
of FreeCAD's Python API (FreeCAD is not installed here); both produce the same
class of artifact for the meshing stage.
"""

__version__ = "0.1.0"
__all__ = [
    "naca",
    "spec",
    "planning",
    "geometry",
    "meshing",
    "inp_writer",
    "solver",
    "post",
    "pipeline",
]
