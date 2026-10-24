"""Decide which through-thickness position CalculiX OUTPUT=2D reports.
Compares per node (not just the peak) against Abaqus top / bottom / membrane."""
import sys, json, math
from collections import defaultdict
from odbAccess import openOdb
import abaqusConstants as ac

FRD = ("S11", "S22", "S33", "S12", "S23", "S31")
ALIAS = {"S23": ("S32",), "S31": ("S13",)}

def vm(s):
    a,b,c,d,e,f = s
    return math.sqrt(0.5*((a-b)**2+(b-c)**2+(c-a)**2) + 3.0*(d*d+e*e+f*f))

def reorder(data, labels):
    idx = {str(l).upper(): i for i, l in enumerate(labels)}
    out=[]
    for w in FRD:
        j = idx.get(w)
        if j is None:
            for al in ALIAS.get(w, ()):
                if al in idx: j = idx[al]; break
        out.append(float(data[j]) if j is not None else 0.0)
    return out

odb = openOdb(sys.argv[1], readOnly=True)
try:
    inst = list(odb.rootAssembly.instances.values())[0]
    st = odb.steps[list(odb.steps.keys())[-1]]
    fr = st.frames[-1]
    s = fr.fieldOutputs["S"]
    nodal = s.getSubset(position=ac.ELEMENT_NODAL)
    labels = list(nodal.componentLabels)

    per = defaultdict(dict)
    for v in nodal.values:
        per[int(v.nodeLabel)][int(v.sectionPoint.number)] = reorder(v.data, labels)

    top={}; bot={}; mem={}
    for node, spmap in per.items():
        o = sorted(spmap.items())
        bot[node], top[node] = o[0][1], o[-1][1]
        mem[node] = [0.5*(x+y) for x, y in zip(bot[node], top[node])]

    out = {"top":{}, "bottom":{}, "membrane":{}}
    for tag, src in (("top",top),("bottom",bot),("membrane",mem)):
        out[tag] = {str(n): vm(v) for n, v in src.items()}
    json.dump(out, open(sys.argv[2], "w"))
    print("ABQ_NODES", len(per))
finally:
    odb.close()
