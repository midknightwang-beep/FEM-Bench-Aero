"""Render post-solve contour maps straight from shipped artifacts.

A contour map needs three things, all of which are already on disk:

  * node coordinates + quad connectivity -> ```model.msh```  (gmsh archive)
  * per-node field values                -> ``<case>.odb.json`` (Abaqus extract,
                                            DISP / STRESS / STRESS_PEAK blocks)

Fields plotted
  membrane von Mises   STRESS      = outermost section points, node-averaged
                                    (the quantity CalculiX OUTPUT=2D reports)
  outer-fibre peak     STRESS_PEAK = max von Mises over section points &
                                    elements, not averaged -- the sizing number (D8)
  displacement         |U|         = sqrt(ux^2+uy^2+uz^2)

Nothing is illustrative: the node ids of the mesh and of the ODB extract are the
same id space (verified by ``probe_contour_source.py``); undeformed geometry is
read back from the mesh, deformed geometry is ``x + scale*u``.

Output: ``figs/figC*.png``.

Run with the managed venv (numpy + gmsh + matplotlib).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

import gmsh

ROOT = Path(r"F:\AI FEA Modeling DataSets")
DS = ROOT / "FEM-Bench-Aero"
REPRO = ROOT / "feagpt_repro"
HERE = Path(__file__).resolve().parent
FIGS = HERE / "figs"
FIGS.mkdir(exist_ok=True)

gmsh.initialize(interruptible=False)
gmsh.option.setNumber("General.Terminal", 0)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.facecolor"] = "white"
plt.rcParams["savefig.facecolor"] = "white"

CMAP = "turbo"

# case_id -> odb.json written by the Abaqus run of that case
ODB = {
    "naca4412_wingbox": REPRO / "outputs_abaqus/naca4412_wingbox/naca4412_wingbox.odb.json",
    "naca4412_wingbox_sweep40":
        REPRO / "outputs_b2_abaqus/naca4412_wingbox_sweep40/naca4412_wingbox_sweep40.odb.json",
    "naca4412_wingbox_taper060":
        REPRO / "outputs_t1_abaqus/naca4412_wingbox_taper060/naca4412_wingbox_taper060.odb.json",
    "stiffened_panel_800x600_str3":
        REPRO / "outputs_b3_abaqus/stiffened_panel_800x600_str3/stiffened_panel_800x600_str3.odb.json",
    "fuselage_barrel_d2000_l2000_str8_frm3":
        REPRO / "outputs_b3_abaqus/fuselage_barrel_d2000_l2000_str8_frm3/"
        "fuselage_barrel_d2000_l2000_str8_frm3.odb.json",
    # --- used by the C5 contact sheet -------------------------------------
    "naca4412_wingbox_n_ribs3_chord800":
        REPRO / "outputs_abaqus/naca4412_wingbox_n_ribs3_chord800/"
        "naca4412_wingbox_n_ribs3_chord800.odb.json",
    "naca4412_wingbox_n_ribs9_chord1000":
        REPRO / "outputs_b2_abaqus/naca4412_wingbox_n_ribs9_chord1000/"
        "naca4412_wingbox_n_ribs9_chord1000.odb.json",
    "naca4412_wingbox_str3":
        REPRO / "outputs_str_abaqus/naca4412_wingbox_str3/naca4412_wingbox_str3.odb.json",
    "naca4412_wingbox_str5":
        REPRO / "outputs_b2_abaqus/naca4412_wingbox_str5/naca4412_wingbox_str5.odb.json",
    "naca4412_wingbox_sweep20":
        REPRO / "outputs_t1_abaqus/naca4412_wingbox_sweep20/naca4412_wingbox_sweep20.odb.json",
    "naca4412_wingbox_taper080":
        REPRO / "outputs_t1_abaqus/naca4412_wingbox_taper080/naca4412_wingbox_taper080.odb.json",
    "naca4412_wingbox_sweep20_taper060":
        REPRO / "outputs_t1_abaqus/naca4412_wingbox_sweep20_taper060/"
        "naca4412_wingbox_sweep20_taper060.odb.json",
    "naca4412_wingbox_sweep40_taper040":
        REPRO / "outputs_b2_abaqus/naca4412_wingbox_sweep40_taper040/"
        "naca4412_wingbox_sweep40_taper040.odb.json",
}


# --------------------------------------------------------------------------
# mesh (with the *original* node ids so the ODB extract can be keyed onto it)
# --------------------------------------------------------------------------
def load_mesh(cid: str):
    gmsh.clear()
    gmsh.open(str(DS / "modeling" / cid / "model.msh"))
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
    elems = np.vstack(rows)
    return ntag, coords, elems


# --------------------------------------------------------------------------
# fields
# --------------------------------------------------------------------------
def node_values(odb: dict, ntag: np.ndarray, block: str) -> np.ndarray:
    """Map one ODB node block onto the mesh node order (NaN where absent).

    Returns shape ``(n_nodes,)`` for scalars and ``(n_nodes, k)`` for the
    vector / tensor blocks (DISP has 3 components, STRESS has 6).
    """
    fv = odb["results"][block]
    ids = np.fromiter((int(k) for k in fv), dtype=np.int64, count=len(fv))
    arr = np.asarray(list(fv.values()), dtype=float)
    if arr.ndim == 1:
        arr = arr[:, None]
    order = np.argsort(ntag)
    snt = ntag[order]
    pos = np.clip(np.searchsorted(snt, ids), 0, len(snt) - 1)
    ok = snt[pos] == ids
    out = np.full((len(ntag), arr.shape[1]), np.nan)
    out[order[pos[ok]]] = arr[ok]
    return out


def von_mises(s: np.ndarray) -> np.ndarray:
    s11, s22, s33 = s[:, 0], s[:, 1], s[:, 2]
    s12, s13, s23 = s[:, 3], s[:, 4], s[:, 5]
    return np.sqrt(0.5 * ((s11 - s22) ** 2 + (s22 - s33) ** 2 + (s33 - s11) ** 2)
                   + 3.0 * (s12 ** 2 + s13 ** 2 + s23 ** 2))


def display_perm(cid: str):
    """Display-axis order.  The wing box is built with x = chord, y = aerofoil
    thickness, z = span; laying it flat (x, z, y) makes it read like a wing
    resting on the ground -- a top view then shows the planform and an oblique
    view shows the spanwise bending.  The other families are already in a
    natural orientation (panel in x-y, barrel section in x-y with z axial)."""
    if cid.startswith("naca4412_wingbox"):
        return (0, 2, 1)
    return (0, 1, 2)


STATS: dict = {}


class Case:
    """Everything one case needs, loaded once."""

    def __init__(self, cid: str):
        self.cid = cid
        self.ntag, raw, self.elems = load_mesh(cid)
        odb = json.loads(Path(ODB[cid]).read_text(encoding="utf-8"))
        self.vm = von_mises(node_values(odb, self.ntag, "STRESS"))
        self.vm_peak = von_mises(node_values(odb, self.ntag, "STRESS_PEAK"))
        d = node_values(odb, self.ntag, "DISP")
        del odb
        self.umag = np.linalg.norm(d, axis=1)
        # radial displacement (used by the barrel to show pressure dilation)
        th = np.arctan2(raw[:, 1], raw[:, 0])
        self.ur = d[:, 0] * np.cos(th) + d[:, 1] * np.sin(th)
        perm = display_perm(cid)
        self.coords = raw[:, perm]
        self.disp = d[:, perm]
        # only elements whose four nodes all carry a field value
        self.mask = ~np.isnan(self.vm[self.elems]).any(axis=1)
        self.maxd = float(np.nanmax(self.umag))
        self.scale = self._auto_scale()
        el = self.elems[self.mask]
        STATS[cid] = {
            "n_elems": int(len(el)),
            "max_umag": self.maxd,
            "max_vm_node": float(np.nanmax(self.vm)),
            "max_vm_elem": float(np.nanmax(np.nanmean(self.vm[el], axis=1))),
            "max_peak_node": float(np.nanmax(self.vm_peak)),
            "max_peak_elem": float(np.nanmax(np.nanmean(self.vm_peak[el], axis=1))),
            "ur_min": float(np.nanmin(self.ur)),
            "ur_max": float(np.nanmax(self.ur)),
            "defo_scale": self.scale,
        }
        print(f"  {cid}: {len(self.elems)} elems, {self.mask.sum()} with field, "
              f"max|u|={self.maxd:.4g}, maxVm={np.nanmax(self.vm):.4g}, "
              f"maxPeak={np.nanmax(self.vm_peak):.4g}, "
              f"ur=[{np.nanmin(self.ur):.4g},{np.nanmax(self.ur):.4g}], "
              f"defo scale x{self.scale:.0f}")

    def _auto_scale(self) -> float:
        ref = float(np.max(np.ptp(self.coords, axis=0)))
        return ref * 0.06 / self.maxd if self.maxd > 0 else 1.0

    def values(self, field):
        if isinstance(field, np.ndarray):
            return field
        return {"vm": self.vm, "peak": self.vm_peak,
                "umag": self.umag, "ur": self.ur}[field]

    def range(self, field):
        v = self.values(field)[self.elems[self.mask]]
        cq = np.nanmean(v, axis=1)
        return float(np.nanmin(cq)), float(np.nanmax(cq))

    # ---- drawing -------------------------------------------------------
    def contour(self, ax, field, deform: bool = False, scale=None,
                elev=22, azim=-58, vmin=None, vmax=None):
        vals = self.values(field)
        el = self.elems[self.mask]
        base = self.coords[el].astype(float)
        verts = base
        if deform:
            s = self.scale if scale is None else scale
            verts = base + s * self.disp[el]
        cq = np.nanmean(vals[el], axis=1)
        lo = float(np.nanmin(cq)) if vmin is None else vmin
        hi = float(np.nanmax(cq)) if vmax is None else vmax
        norm = Normalize(lo, hi)
        face = plt.get_cmap(CMAP)(norm(cq))
        pc = Poly3DCollection(verts, facecolors=face, edgecolors="none",
                              linewidths=0)
        ax.add_collection3d(pc)
        pts = verts.reshape(-1, 3)
        # the box aspect follows the *undeformed* extents so that scaling up the
        # displacement does not silently squash the model's proportions
        span0 = np.ptp(base.reshape(-1, 3), axis=0)
        lim = np.vstack([pts.min(axis=0), pts.max(axis=0)])
        pad = float(np.ptp(lim, axis=0).max()) * 0.02
        ax.set_xlim(lim[0, 0] - pad, lim[1, 0] + pad)
        ax.set_ylim(lim[0, 1] - pad, lim[1, 1] + pad)
        ax.set_zlim(lim[0, 2] - pad, lim[1, 2] + pad)
        ax.set_box_aspect(span0 + 1e-9)
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        return lo, hi


def colorbar(fig, ax, lo, hi, unit, label):
    sm = ScalarMappable(norm=Normalize(lo, hi), cmap=CMAP)
    cb = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.02, shrink=0.72)
    cb.set_label(f"{label}  ({unit})", fontsize=9)
    cb.ax.tick_params(labelsize=8)


def unit_label(field: str):
    return {"vm": ("MPa", "膜应力 von Mises"),
            "peak": ("MPa", "外表面峰值 von Mises"),
            "ur": ("mm", "径向位移 u_r"),
            "umag": ("mm", "位移幅值 |u|")}[field]


# --------------------------------------------------------------------------
# fig C1 -- baseline wing box, full field set
# --------------------------------------------------------------------------
def figC1(c):
    """Baseline wing box: the full post-solve field set, one 3/4 view each."""
    panel = [
        (0, "vm",   False, "(a) 膜应力  ·  变形前"),
        (1, "vm",   True,  "(b) 膜应力  ·  变形放大"),
        (2, "umag", True,  "(c) 位移幅值  ·  变形放大"),
        (3, "peak", False, "(d) 外表面峰值  ·  变形前"),
    ]
    fig = plt.figure(figsize=(13.6, 10.8))
    for i, fld, defo, sub in panel:
        ax = fig.add_subplot(2, 2, i + 1, projection="3d")
        lo, hi = c.contour(ax, fld, deform=defo, elev=22, azim=-58)
        u, lab = unit_label(fld)
        note = "（单元平均）" if fld != "umag" else ""
        ax.set_title(f"{sub}\nmax = {hi:.3g} {u}{note}", fontsize=10.5, pad=-2)
        colorbar(fig, ax, lo, hi, u, lab)
    fig.suptitle(f"图 C1  {c.cid} —— 求解后场云图"
                 f"（几何 model.msh + 逐节点场 odb.json；变形放大 ×{c.scale:.0f}）",
                 fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    fig.savefig(FIGS / "figC1_wingbox_field.png", dpi=150)
    plt.close(fig)
    print("figC1 ok")


# --------------------------------------------------------------------------
# fig C2 -- planform family: the same field across sweep / taper variants
# --------------------------------------------------------------------------
def figC2(cases: dict):
    ids = ["naca4412_wingbox", "naca4412_wingbox_sweep40",
           "naca4412_wingbox_taper060"]
    caps = {"naca4412_wingbox": "基线（无限后掠 / 等弦）",
            "naca4412_wingbox_sweep40": "后掠 40°",
            "naca4412_wingbox_taper060": "锥度 λ = 0.60"}
    # one common colour range so the three planforms are comparable
    hi = max(cases[i].range("vm")[1] for i in ids)
    fig = plt.figure(figsize=(15.5, 5.6))
    for k, cid in enumerate(ids):
        c = cases[cid]
        ax = fig.add_subplot(1, 3, k + 1, projection="3d")
        lo, _ = c.contour(ax, "vm", deform=False, elev=26, azim=-58,
                          vmin=0.0, vmax=hi)
        ax.set_title(f"{caps[cid]}\nmax = {c.range('vm')[1]:.3g} MPa", fontsize=10.5)
        if k == 2:
            colorbar(fig, ax, 0.0, hi, "MPa", "膜应力 von Mises")
    fig.suptitle("图 C2  平面形状族的膜应力云图（同一色标，来自各 case 的 odb.json）",
                 fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIGS / "figC2_planform_field.png", dpi=150)
    plt.close(fig)
    print("figC2 ok")


# --------------------------------------------------------------------------
# fig C3 -- stiffened panel
# --------------------------------------------------------------------------
def figC3(c):
    # a plate in pure bending has a near-zero *membrane* field, so the sizing
    # quantity (outer-fibre peak) is what actually shows the bending pattern
    panel = [
        (0, "peak", False, "(a) 外表面峰值 von Mises  ·  变形前", 46),
        (1, "umag", True,  "(b) 位移幅值  ·  变形放大", 34),
    ]
    fig = plt.figure(figsize=(13.6, 5.8))
    for i, fld, defo, sub, elev in panel:
        ax = fig.add_subplot(1, 2, i + 1, projection="3d")
        lo, hi = c.contour(ax, fld, deform=defo, elev=elev, azim=-58)
        u, lab = unit_label(fld)
        ax.set_title(f"{sub}\nmax = {hi:.3g} {u}", fontsize=10.5, pad=-2)
        colorbar(fig, ax, lo, hi, u, lab)
    fig.suptitle(f"图 C3  {c.cid} —— 加筋壁板求解后场云图"
                 f"（变形放大 ×{c.scale:.0f}；云图上的 4 个鼓包 = 4 个长桁隔舱）",
                 fontsize=12.5)
    fig.tight_layout(rect=(0, 0, 1, 0.925))
    fig.savefig(FIGS / "figC3_panel_field.png", dpi=150)
    plt.close(fig)
    print("figC3 ok")


# --------------------------------------------------------------------------
# fig C4 -- fuselage barrel: stress + pressure dilation (D21 evidence)
# --------------------------------------------------------------------------
def figC4(c):
    cq = np.nanmean(c.vm[c.elems[c.mask]], axis=1)
    p97 = float(np.percentile(cq, 97))
    peak = float(cq.max())
    # the stress field is dominated by a few frame/stringer hotspots; clip the
    # colour scale at P97 so the bulk of the shell is actually readable
    panel = [
        (0, "vm",   False, "(a) 膜应力  ·  变形前", 18),
        (1, "ur",   True,  "(b) 径向位移 u_r  ·  变形放大 ×2", 18),
        (2, "umag", True,  "(c) 位移幅值  ·  变形放大 ×2", 18),
    ]
    fig = plt.figure(figsize=(15.6, 5.9))
    for i, fld, defo, sub, elev in panel:
        ax = fig.add_subplot(1, 3, i + 1, projection="3d")
        sc = c.scale * 2.0 if i > 0 else None
        kw = {"vmin": 0.0, "vmax": p97} if fld == "vm" else {}
        lo, hi = c.contour(ax, fld, deform=defo, elev=elev, azim=-46,
                           scale=sc, **kw)
        u, lab = unit_label(fld)
        if fld == "vm":
            ax.set_title(f"{sub}\n色标上限 P97 = {p97:.0f} MPa（峰值 {peak:.0f} MPa）",
                         fontsize=10, pad=-2)
        else:
            ax.set_title(f"{sub}\n范围 {lo:.3g} … {hi:.3g} {u}", fontsize=10.5, pad=-2)
        colorbar(fig, ax, lo, hi, u, lab)
    fig.suptitle(f"图 C4  {c.cid} —— 机身柱壳求解后场云图"
                 f"（内压 + 端弯 + 端剪；径向整体外胀 = D21 内压方向判据的直接证据）",
                 fontsize=12.5)
    fig.tight_layout(rect=(0, 0, 1, 0.925))
    fig.savefig(FIGS / "figC4_barrel_field.png", dpi=150)
    plt.close(fig)
    print("figC4 ok")


# --------------------------------------------------------------------------
# fig C5 -- contact sheet: one displacement contour per shipped case
# --------------------------------------------------------------------------
CONTACT = [
    ("naca4412_wingbox", "基线 5肋·1000弦"),
    ("naca4412_wingbox_n_ribs3_chord800", "3肋·800弦"),
    ("naca4412_wingbox_n_ribs9_chord1000", "9肋·1000弦"),
    ("naca4412_wingbox_str3", "上蒙皮 3长桁"),
    ("naca4412_wingbox_str5", "上蒙皮 5长桁"),
    ("naca4412_wingbox_sweep20", "后掠 20°"),
    ("naca4412_wingbox_sweep40", "后掠 40°"),
    ("naca4412_wingbox_taper060", "锥度 λ=0.60"),
    ("naca4412_wingbox_taper080", "锥度 λ=0.80"),
    ("naca4412_wingbox_sweep20_taper060", "后掠20° + λ=0.60"),
    ("naca4412_wingbox_sweep40_taper040", "后掠40° + λ=0.40"),
    ("stiffened_panel_800x600_str3", "加筋壁板 800×600"),
]


def figC5():
    rows, cols = 3, 4
    fig = plt.figure(figsize=(15.6, 10.0))
    for k, (cid, note) in enumerate(CONTACT):
        c = Case(cid)
        ax = fig.add_subplot(rows, cols, k + 1, projection="3d")
        elev = 34 if cid.startswith("stiffened") else 24
        lo, hi = c.contour(ax, "umag", deform=True, elev=elev, azim=-58, vmin=0.0)
        ax.set_title(f"{note}\nmax |u| = {hi:.4g} mm", fontsize=9.5, pad=-4)
        del c
    fig.suptitle("图 C5  数据集多样性检查表 —— 每条算例的位移幅值云图"
                 "（子图各自归一化：蓝 = 0 → 红 = 该算例峰值；变形放大到跨度 6%）",
                 fontsize=12.5)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(FIGS / "figC5_contact_sheet.png", dpi=150)
    plt.close(fig)
    print("figC5 ok")


def main():
    print("loading cases ...")
    need = ["naca4412_wingbox", "naca4412_wingbox_sweep40",
            "naca4412_wingbox_taper060", "stiffened_panel_800x600_str3"]
    barrel = "fuselage_barrel_d2000_l2000_str8_frm3"
    cases = {cid: Case(cid) for cid in need}
    figC1(cases["naca4412_wingbox"])
    figC2(cases)
    figC3(cases["stiffened_panel_800x600_str3"])
    del cases
    b = Case(barrel)
    figC4(b)
    del b
    figC5()

    import datetime as _dt
    payload = {
        "meta": {
            "generated_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "geometry_source": "FEM-Bench-Aero/modeling/<case>/model.msh (gmsh)",
            "field_source": "feagpt_repro/<tree>/<case>/<case>.odb.json (Abaqus ODB extract)",
            "field_blocks": {
                "STRESS": "outermost section points, node-averaged (membrane)",
                "STRESS_PEAK": "max von Mises over section points & elements (sizing, D8)",
                "DISP": "nodal displacement U",
                "ur": "radial component ux*cos(t)+uy*sin(t), t=atan2(y,x)",
            },
            "vm_formula": "sqrt(0.5*((s11-s22)^2+(s22-s33)^2+(s33-s11)^2)+3*(s12^2+s13^2+s23^2))",
            "deformation_note": "displacement drawn as x + scale*u; scale chosen so "
                                "max|u| spans 6% of the model's largest extent",
        },
        "cases": STATS,
    }
    (HERE / "contour_data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote contour_data.json ({len(STATS)} cases)")


if __name__ == "__main__":
    main()
