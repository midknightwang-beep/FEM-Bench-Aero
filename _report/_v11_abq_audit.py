import json, os, sys

root = r"F:\AI FEA Modeling DataSets\feagpt_repro\_v11\runs_abaqus"
rows = []
for d in sorted(os.listdir(root)):
    p = os.path.join(root, d)
    if not os.path.isdir(p):
        continue
    tj = os.path.join(p, d + ".truth.json")
    oj = os.path.join(p, d + ".odb.json")
    oj2 = os.path.join(p, d + ".odb.json")
    sz = os.path.getsize(oj2) if os.path.exists(oj2) else 0
    if not os.path.exists(tj):
        rows.append((d, "NO-TRUTH", None, None, None, sz))
        continue
    s = json.load(open(tj)).get("scalars", {})
    rows.append((d, "ok", s.get("n_nodes"), s.get("max_disp"),
                 s.get("max_von_mises"), sz))

hdr = "%-42s %-8s %9s %13s %11s %7s" % ("case", "state", "n_nodes", "max_disp", "max_vm", "odbMB")
print(hdr)
print("-" * len(hdr))
bad = 0
for d, st, nn, md, mv, sz in rows:
    okp = (st == "ok" and nn and md and md > 0 and sz > 100000)
    if not okp:
        bad += 1
    print("%-42s %-8s %9s %13s %11s %6.1f  %s" % (
        d, st,
        nn if nn is not None else "-",
        ("%.6g" % md) if isinstance(md, (int, float)) and md else "-",
        ("%.4f" % mv) if isinstance(mv, (int, float)) and mv else "-",
        sz / 1048576.0,
        "" if okp else "<== BAD"))
print()
print("TOTAL=%d  BAD=%d" % (len(rows), bad))
sys.exit(0 if bad == 0 else 1)
