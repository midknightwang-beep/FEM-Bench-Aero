"""Dump the structure of a job's ODB: instances, element types, steps, frames,
field outputs and their component labels.

Run it with Abaqus' own interpreter::

    abaqus python diagnostics/inspect_odb.py <job.odb>

This is the tool that established what the extractor had to cope with: that a
shell ``S`` field is ``TENSOR_3D_PLANAR`` with four components (not six), that
``ELEMENT_NODAL`` extrapolation keeps only the two outer section points, and
that node coordinates come back in 32-bit floats.  Reach for it first when an
ODB does not contain what the reader expects.
"""
import sys
from odbAccess import openOdb
odb = openOdb(sys.argv[1], readOnly=True)
try:
    inst = list(odb.rootAssembly.instances.values())[0]
    print("instance:", inst.name)
    import collections
    print("element types:", dict(collections.Counter(e.type for e in inst.elements)))
    print("n elements:", len(inst.elements))
    print("n nodes:", len(inst.nodes))
    steps = list(odb.steps.keys())
    print("steps:", steps)
    st = odb.steps[steps[-1]]
    print("frames:", len(st.frames))
    fr = st.frames[-1]
    print("frameValue:", fr.frameValue)
    print("fieldOutputs:", sorted(fr.fieldOutputs.keys()))
    for name in sorted(fr.fieldOutputs.keys()):
        fo = fr.fieldOutputs[name]
        print("---", name, "| type:", fo.type, "| ncomp:", len(fo.componentLabels),
              "| labels:", list(fo.componentLabels))
        v0 = list(fo.values)[:2]
        for v in v0:
            sp = getattr(v, 'sectionPoint', None)
            print("     node=%s elem=%s ip=%s sp=%s data=%s" % (
                getattr(v,'nodeLabel',None), getattr(v,'elementLabel',None),
                getattr(v,'integrationPoint',None),
                (sp.number if sp is not None else None), list(v.data)))
        try:
            en = fo.getSubset(position='ELEMENT_NODAL')
            print("     ELEMENT_NODAL ncomp:", len(en.componentLabels), list(en.componentLabels))
            print("     ELEMENT_NODAL sample:", [list(x.data) for x in list(en.values)[:2]])
        except Exception as e:
            print("     getSubset ELEMENT_NODAL failed:", e)
finally:
    odb.close()
