"""Render the figures the progress report embeds -- from the dataset itself.

Every figure is drawn from a shipped artifact:

  * mesh figures read ``model.msh`` back through gmsh (the same archived mesh
    that ships in the dataset);
  * the planform figure reads the true ``sweep_deg`` / ``tip_chord_ratio`` out
    of each ``spec.json``;
  * the verification figures plot the numbers in ``report_data.json``, which
    was itself measured off disk by ``make_report_data.py``.

Nothing is hand-drawn or illustrative.  Output: ``figs/*.png`` next to this
file, which the report builder base64-embeds.

Run with the managed venv (needs numpy + gmsh + matplotlib).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Patch

ROOT = Path(r"F:\AI FEA Modeling DataSets")
DS = ROOT / "FEM-Bench-Aero"
HERE = Path(__file__).resolve().parent
FIGS = HERE / "figs"
FIGS.mkdir(exist_ok=True)

DATA = json.loads((HERE / "report_data.json").read_text(encoding="utf-8"))

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.facecolor"] = "white"
plt.rcParams["axes.facecolor"] = "white"
plt.rcParams["savefig.facecolor"] = "white"
plt.rcParams["axes.edgecolor"] = "#c9ced6"
plt.rcParams["axes.labelcolor"] = "#26303b"
plt.rcParams["text.color"] = "#26303b"
plt.rcParams["xtick.color"] = "#5b6572"
plt.rcParams["ytick.color"] = "#5b6572"
plt.rcParams["axes.titlesize"] = 13
plt.rcParams["font.size"] = 10

FAM = {"wingbox": "翼盒 wingbox", "stiffened_panel": "加筋壁板 panel",
       "fuselage_barrel": "机身柱壳 barrel"}
C = {"wingbox": "#2f6fd0", "stiffened_panel": "#e08a1e", "fuselage_barrel": "#2f9e6b"}
SPLIT = {"train": "#4c78c9", "val": "#e8b13c", "test": "#d9534f"}

import gmsh  # noqa: E402


# --------------------------------------------------------------------------
# mesh reading (gmsh -> node coords + 2-D element connectivity)
# --------------------------------------------------------------------------
def load_msh(path: Path):
    gmsh.clear()
    gmsh.open(str(path))
    ntag, ncoord, _ = gmsh.model.mesh.getNodes()
    ntag = np.asarray(ntag, dtype=np.int64)
    coords = np.asarray(ncoord, dtype=float).reshape(-1, 3)
    lookup = {int(t): i for i, t in enumerate(ntag)}
    rows = []
    for dim, tag in gmsh.model.getEntities(2):
        etypes, _, enodes = gmsh.model.mesh.getElements(2, tag)
        for et, en in zip(etypes, enodes):
            npe = gmsh.model.mesh.getElementProperties(et)[3]
            arr = np.asarray(en, dtype=np.int64).reshape(-1, npe)
            rows.append(np.vectorize(lookup.__getitem__)(arr))
    if not rows:
        return coords, np.zeros((0, 4), dtype=np.int64)
    elems = np.vstack(rows)
    return coords, elems


def edges_from_quads(elems: np.ndarray) -> np.ndarray:
    """Unique undirected edges of a quad (or mixed 2-D) element table."""
    pairs = []
    for e in elems:
        n = len(e)
        for i in range(n):
            pairs.append((e[i], e[(i + 1) % n]))
    if not pairs:
        return np.zeros((0, 2), dtype=np.int64)
    p = np.asarray(pairs, dtype=np.int64)
    p = np.sort(p, axis=1)
    return np.unique(p, axis=0)


def load_mesh_np(cid: str):
    return load_msh(DS / "modeling" / cid / "model.msh")


def draw_mesh(ax, coords, elems, plane=("x", "y"), mask=None, lw=0.25,
              color="#4c78c9", nodes=True, ns=0.4):
    idx = {"x": 0, "y": 1, "z": 2}
    a, b = idx[plane[0]], idx[plane[1]]
    if mask is not None:
        elems = elems[mask]
    if len(elems) == 0:
        return
    e = edges_from_quads(elems)
    segs = coords[e][:, :, (a, b)]
    ax.add_collection(LineCollection(segs, colors=color, linewidths=lw,
                                     alpha=0.75, zorder=2))
    if nodes:
        used = np.unique(elems.ravel())
        ax.scatter(coords[used, a], coords[used, b], s=ns, c="#1d4e89",
                   linewidths=0, zorder=3)


# --------------------------------------------------------------------------
# fig 1 -- one representative mesh per family, straight off the .msh
# --------------------------------------------------------------------------
def fig_family_meshes():
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.4))

    # --- wingbox: looking straight down (x-z), where ribs AND spars read -----
    ax = axes[0]
    coords, elems = load_mesh_np("naca4412_wingbox")
    draw_mesh(ax, coords, elems, plane=("x", "z"), color=C["wingbox"], lw=0.22)
    ax.set_aspect("equal")
    ax.set_xlabel("x 弦向 (mm)")
    ax.set_ylabel("z 展向 (mm)")
    ax.set_title("翼盒 wingbox（基线，5144 四边形）\n俯视 x–z：肋线 + 前后梁",
                 fontsize=10)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    # --- panel: zoomed so the stringer-to-skin joint is actually visible ----
    ax = axes[1]
    coords, elems = load_mesh_np("stiffened_panel_800x600_str3")
    draw_mesh(ax, coords, elems, plane=("x", "y"),
              color=C["stiffened_panel"], lw=0.5, ns=1.2)
    ax.set_xlim(90, 710)
    ax.set_ylim(140, 460)
    ax.set_aspect("equal")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.set_title("加筋壁板 panel（800×600，3 长桁）\n局部放大：长桁腹板 + 蒙皮",
                 fontsize=10)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    # --- barrel: cross-section between two frames + true stringer angles ----
    ax = axes[2]
    cid = "fuselage_barrel_d2000_l2000_str8_frm3"
    coords, elems = load_mesh_np(cid)
    cz = coords[elems][:, :, 2].mean(axis=1)
    mask = (cz > 1460) & (cz < 1540)
    draw_mesh(ax, coords, elems, plane=("x", "y"), mask=mask,
              color=C["fuselage_barrel"], lw=0.45, ns=0.7)
    tb = next(c for c in DATA["cases"] if c["case_id"] == cid)
    design = tb["truth"]["design"]
    R = design.get("diameter", 2000.0) / 2.0
    angs = design.get("stringer_angles", [])
    if angs:
        ax.plot([R * math.cos(a) for a in angs], [R * math.sin(a) for a in angs],
                "o", color="#d9534f", ms=5, zorder=6,
                label=f"{len(angs)} 根长桁")
        ax.legend(fontsize=8.5, frameon=False, loc="lower right")
    ax.set_aspect("equal")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.set_title("机身柱壳 barrel（Ø2000×2000，8 长桁 3 框）\nz≈1500 横截面，红点 = 长桁角度",
                 fontsize=10)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    fig.suptitle("图 1  三种结构族的代表性网格（由归档 model.msh 读回，非示意）",
                 fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIGS / "fig1_family_meshes.png", dpi=150)
    plt.close(fig)
    print("fig1 ok")


# --------------------------------------------------------------------------
# fig 2 -- wing planform family from the true spec parameters
# --------------------------------------------------------------------------
def fig_planform():
    ws = [c for c in DATA["cases"] if c["family"] == "wingbox"]
    ws = [c for c in ws if c["spec"]["airfoil"]]
    # distinct planforms only
    seen = {}
    for c in ws:
        af = c["spec"]["airfoil"]
        key = (round(af["sweep_deg"], 3), round(af["tip_chord_ratio"], 3))
        seen.setdefault(key, c)
    entries = sorted(seen.values(), key=lambda c: (c["spec"]["airfoil"]["sweep_deg"],
                                                   c["spec"]["airfoil"]["tip_chord_ratio"]))
    fig, ax = plt.subplots(figsize=(12.5, 6.0))
    cmap = plt.get_cmap("turbo")
    n = max(len(entries) - 1, 1)
    handles = []
    for i, c in enumerate(entries):
        af = c["spec"]["airfoil"]
        chord, span = af["chord"], af["span"]
        off = span * math.tan(math.radians(af["sweep_deg"]))
        ratio = af["tip_chord_ratio"]
        col = cmap(i / n)
        tag = c["case_id"].replace("naca4412_wingbox_", "").replace("naca4412_wingbox", "baseline")
        label = f"{tag}  (sweep {af['sweep_deg']:g}°, λ={ratio:g})"
        ln, = ax.plot([0.0, off], [0.0, span], color=col, lw=2.2, label=label)  # LE
        ax.plot([chord, off + chord * ratio], [0.0, span], color=col, lw=2.2)   # TE
        ax.plot([0.0, chord], [0.0, 0.0], color=col, lw=2.2)                    # root
        ax.plot([off, off + chord * ratio], [span, span], color=col, lw=2.2)    # tip
        handles.append(ln)
    ax.set_xlabel("x（弦向, mm）")
    ax.set_ylabel("z（展向, mm）")
    ax.set_title("图 2  翼盒平面形状族：前缘参考线 + 翼尖缩比 λ + 后掠\n"
                 "（每条曲线的 sweep_deg / tip_chord_ratio 直接取自对应 spec.json）")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(alpha=0.22, lw=0.5)
    ax.legend(handles=handles, fontsize=7.4, ncol=2, frameon=True, framealpha=0.92,
              loc="upper left", borderpad=0.6, labelspacing=0.35)
    fig.tight_layout()
    fig.savefig(FIGS / "fig2_planform.png", dpi=150)
    plt.close(fig)
    print("fig2 ok")


# --------------------------------------------------------------------------
# fig 3 -- measured minJ per case, straight from the archived .msh
# --------------------------------------------------------------------------
def fig_minj():
    cs = sorted([c for c in DATA["cases"] if c["mesh"]["minJ"]],
                key=lambda c: c["mesh"]["minJ"])
    names = [c["case_id"] for c in cs]
    vals = [c["mesh"]["minJ"] for c in cs]
    cols = [C[c["family"]] for c in cs]
    fig, ax = plt.subplots(figsize=(11, 8))
    y = np.arange(len(cs))
    ax.barh(y, vals, color=cols, height=0.72)
    ax.axvline(0.30, color="#d9534f", ls="--", lw=1.4)
    ax.text(0.305, len(cs) - 0.4, "关 1 阈值 0.30", color="#d9534f", fontsize=9, va="top")
    ax.set_yticks(y, [n.replace("naca4412_", "").replace("fuselage_barrel_", "barrel_")
                      .replace("stiffened_panel_", "panel_") for n in names], fontsize=8)
    ax.set_xlim(0, 0.72)
    ax.set_xlabel("minSICN（最小缩放雅可比，从归档 .msh 重新量测）")
    ax.set_title("图 3  26 条算例的网格质量：全 quad4、零 tri3，最低 0.4861（红线为门禁）")
    ax.legend(handles=[Patch(color=C[k], label=FAM[k]) for k in C], loc="lower right",
              fontsize=9, frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIGS / "fig3_minj.png", dpi=150)
    plt.close(fig)
    print("fig3 ok")


# --------------------------------------------------------------------------
# fig 4 -- cross-solver agreement, from both trees' model.results.json
# --------------------------------------------------------------------------
def fig_xval():
    cs = [c for c in DATA["cases"] if c["xval"] and c["ccx"] and c["abaqus"]]
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.6))
    ax = axes[0]
    for c in cs:
        ax.scatter(c["ccx"]["max_disp"], c["abaqus"]["max_disp"],
                   s=46, color=C[c["family"]], alpha=0.85,
                   edgecolors="white", linewidths=0.6, zorder=3)
    lo, hi = 0.02, 4.0
    ax.plot([lo, hi], [lo, hi], color="#8a939e", lw=1.2, ls="--", zorder=1)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xlabel("CalculiX  max|u| (mm)")
    ax.set_ylabel("Abaqus  max|u| (mm)")
    ax.set_title("(a) 双求解器 max|u| 1:1（虚线 = 完全一致）")
    ax.grid(alpha=0.2, which="both", lw=0.4)
    ax.legend(handles=[Patch(color=C[k], label=FAM[k]) for k in C], fontsize=8.5,
              loc="upper left", frameon=False)

    ax = axes[1]
    order = sorted(cs, key=lambda c: c["xval"]["max_disp_diff_pct"])
    names = [c["case_id"].replace("naca4412_", "").replace("fuselage_barrel_", "barrel_")
             .replace("stiffened_panel_", "panel_") for c in order]
    diffs = [c["xval"]["max_disp_diff_pct"] for c in order]
    cols = [C[c["family"]] for c in order]
    y = np.arange(len(order))
    ax.barh(y, diffs, color=cols, height=0.72)
    ax.axvline(1.0, color="#d9534f", ls="--", lw=1.4)
    ax.text(1.03, -0.4, "1% 容差", color="#d9534f", fontsize=9)
    ax.set_yticks(y, names, fontsize=8)
    ax.set_xlabel("|Abaqus − CalculiX| / CalculiX × 100 %  （全域 max|u|）")
    ax.set_title("(b) 逐算例双码偏差")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.suptitle("图 4  双求解器交叉验证（26 条，读数取自两棵树的 model.results.json）",
                 fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(FIGS / "fig4_xval.png", dpi=150)
    plt.close(fig)
    print("fig4 ok")


# --------------------------------------------------------------------------
# fig 5 -- split composition per family, from manifest.json
# --------------------------------------------------------------------------
def fig_splits():
    by = DATA["manifest"]["summary"]["by_family"]
    fams = list(by.keys())
    splits = ["train", "val", "test"]
    fig, ax = plt.subplots(figsize=(8.6, 5.2))
    x = np.arange(len(fams))
    bottom = np.zeros(len(fams))
    for s in splits:
        vals = np.array([by[f].get(s, 0) for f in fams], dtype=float)
        ax.bar(x, vals, bottom=bottom, color=SPLIT[s], label=s, width=0.55,
               edgecolor="white", linewidth=1.2)
        for xi, (v, b) in enumerate(zip(vals, bottom)):
            if v > 0:
                ax.text(xi, b + v / 2, f"{int(v)}", ha="center", va="center",
                        color="white", fontsize=10, fontweight="bold")
        bottom += vals
    ax.set_xticks(x, [FAM[f] for f in fams])
    ax.set_ylabel("算例数")
    ax.set_title("图 5  按结构族 × 划分的算例分布\n"
                 "总 26 条 / 25 个几何等价类；0 个等价类跨 split")
    ax.legend(title="split", frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIGS / "fig5_splits.png", dpi=150)
    plt.close(fig)
    print("fig5 ok")


# --------------------------------------------------------------------------
# fig 6 -- T3 barrel closed-form verification (verify_barrel_b3.json)
# --------------------------------------------------------------------------
def fig_t3():
    vb = DATA["t3"]["verify_barrel"]
    d20 = DATA["t3"]["d20"]
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.6))

    # (a) the three closed-form checks, shown as deviation (the absolute bars
    #     are indistinguishable at ~0.1-0.7 %, so deviation is the honest view)
    ax = axes[0]
    labels = ["环向膜应力\nσ = pR/t", "径向膨胀\nw = pR²/(Et)", "端弯矩弯曲\nσ = Mc/I"]
    pairs = [
        (vb["pressure"]["hoop_vm_MPa"], vb["pressure"]["hoop_closed_form_MPa"], "16.688 vs 16.667 MPa"),
        (vb["pressure"]["w_mm"], vb["pressure"]["w_closed_form_mm"], "0.22725 vs 0.22800 mm"),
        (vb["moment"]["bending_vm_MPa"], vb["moment"]["bending_closed_form_MPa"], "3.7258 vs 3.7513 MPa"),
    ]
    dev = [(m / c - 1) * 100 for m, c, _ in pairs]
    x = np.arange(3)
    ax.axhspan(-1, 1, color="#2f9e6b", alpha=0.10, zorder=0)
    ax.axhline(0, color="#7a828d", lw=0.9, zorder=1)
    ax.bar(x, dev, color=C["fuselage_barrel"], width=0.5, zorder=3)
    for xi, (d, (_, _, txt)) in enumerate(zip(dev, pairs)):
        ax.text(xi, d + (0.05 if d >= 0 else -0.05), f"{d:+.3f}%", ha="center",
                va="bottom" if d >= 0 else "top", fontsize=10, fontweight="bold")
        ax.text(xi, 1.16, txt, ha="center", fontsize=7.8, color="#5b6572")
    ax.set_xticks(x, labels, fontsize=9)
    ax.set_ylim(-1.5, 1.5)
    ax.set_ylabel("相对解析解的偏差 (%)")
    ax.set_title("(a) 三条独立解析对照的偏差（绿带 = ±1% 容差）")
    ax.axhline(1, color="#2f9e6b", ls=":", lw=1.1)
    ax.axhline(-1, color="#2f9e6b", ls=":", lw=1.1)

    # (b) why the barrel's cross-solver gate dropped the global-max metric
    ax = axes[1]
    cases = [c["case"] for c in d20["cases"]]
    struct = [c["structure_cross_pct"] for c in d20["cases"]]
    full = [c["full_cross_pct"] for c in d20["cases"]]
    x = np.arange(len(cases))
    ax.bar(x - 0.19, struct, width=0.36, color=C["fuselage_barrel"],
           label="结构峰值口径 (D20 采用)")
    ax.bar(x + 0.19, full, width=0.36, color="#c85a5a", label="全域 max|u| (弃用)")
    ax.axhline(1.0, color="#d9534f", ls="--", lw=1.4)
    ax.text(len(cases) - 0.5 + 0.42, 1.05, "1% 容差", color="#d9534f", fontsize=9, ha="right")
    for xi, (s, f) in enumerate(zip(struct, full)):
        ax.text(xi - 0.19, s + 0.05, f"{s:.2f}%", ha="center", fontsize=9, fontweight="bold")
        ax.text(xi + 0.19, f + 0.05, f"{f:.2f}%", ha="center", fontsize=9, color="#a33")
    ax.set_xticks(x, [f"{c.split('str')[1].split('_')[0]} 长桁\n{c.split('frm')[1]} 框"
                      for c in cases], fontsize=9.5)
    ax.set_ylim(0, 3.9)
    ax.set_ylabel("双码相对差 (%)")
    ax.set_title("(b) D20：全域口径为何不可用")
    ax.legend(fontsize=9, frameon=False, loc="upper left")
    for a in axes:
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
    fig.suptitle("图 6  T3 机身柱壳的独立解析对照（数据来自 verify_barrel_b3.json / t3_d20_batch3.json）",
                 fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIGS / "fig6_t3.png", dpi=150)
    plt.close(fig)
    print("fig6 ok")


# --------------------------------------------------------------------------
# fig 7 -- stiffened-panel Navier convergence (panel_convergence.json)
# --------------------------------------------------------------------------
def fig_panel():
    conv = DATA["panel"]["convergence"]
    runs = [r for r in conv["runs"] if r.get("clamp_dofs") == [1, 3]]
    runs = sorted(runs, key=lambda r: -r["size"])
    sizes = [r["size"] for r in runs]
    disp = [abs(r["centre_uz"]) for r in runs]
    nav = conv["navier_wmax"]
    fig, ax = plt.subplots(figsize=(8.6, 5.2))
    ax.axhline(nav, color="#2f9e6b", ls="--", lw=1.6,
               label=f"Navier 解析解 {nav:.4f} mm")
    xs = np.arange(len(sizes))
    ax.plot(xs, disp, "o-", color=C["stiffened_panel"], lw=2, ms=8,
            label="四边简支板中心挠度（ccx）")
    for xi, d in zip(xs, disp):
        ax.annotate(f"{d:.4f}\n({(d/nav-1)*100:+.2f}%)", (xi, d),
                    textcoords="offset points", xytext=(0, 11),
                    ha="center", fontsize=8.5, color="#8a5a00")
    ax.set_xticks(xs, [f"{s:g} mm" for s in sizes])
    ax.set_xlabel("网格尺寸（加密方向 →）")
    ax.set_ylabel("中心挠度 (mm)")
    ax.set_title("图 7  600×600 加筋壁板：网格收敛到 Navier 解析解\n"
                 "（数据来自 diagnostics/panel_convergence.json）")
    ax.legend(frameon=False)
    ax.grid(alpha=0.25, lw=0.5, which="both")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIGS / "fig7_panel.png", dpi=150)
    plt.close(fig)
    print("fig7 ok")


def main() -> int:
    gmsh.initialize()
    try:
        fig_family_meshes()
        gmsh.finalize()
    except Exception:
        gmsh.finalize()
        raise
    fig_planform()
    fig_minj()
    fig_xval()
    fig_splits()
    fig_t3()
    fig_panel()
    for p in sorted(FIGS.glob("*.png")):
        print(f"  {p.name:28s} {p.stat().st_size/1024:8.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
