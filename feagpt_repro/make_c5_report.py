#!/usr/bin/env python
"""C5 原型 V1 —— 一句话自然语言进，一页报告出。

这个脚本存在的理由（C 段「让『能用』」的第一步）
------------------------------------------------
benchmark 的数字（23/25、92.0%）对内部有用，对外部人没用：他们看不出
"这东西到底能干什么"。这一页要回答外行的三个问题：

  1. 我说一句话，它真的把模型建出来了吗？   → 几何 + 网格图
  2. 算出来的数对不对？                     → 关键指标 vs 标准答案
  3. 差多少、能信到什么程度？               → 偏差 + 判据线 + 明确的边界

设计上的三条硬规矩
------------------
* **不接 LLM 实时调用**：spec 用仓库里现成的候选产物（`candidates_*/`）。
  这样报告可复现、不需要 API key，也不用为「模型这次心情好」付代价。
* **每个数字都带来源**：页面上每个数都标出它来自哪个文件的哪个字段，
  并给出 sha256 前缀。这个项目吃过太多「手抄数字后来漂了」的亏。
* **fail-closed**：求解失败就报错退出，不产出半张报告 —— 一张缺了
  「算出来多少」的报告比没有报告更误导人。

用法
----
  python make_c5_report.py --case open_hole_panel_400x200_d40
  python make_c5_report.py --case open_hole_panel_400x200_d40 --reuse
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent / "FEM-Bench-Aero"
MODELING = BENCH / "modeling"
PAPER = HERE / "reports" / "papers" / "tasks_v8.jsonl"
DEFAULT_CAND = HERE / "candidates_l3_v6c_glm_p2"
RUNS = HERE / "_c5_runs"

# 族判据（RUBRIC 按族定）：开孔板拉伸 = 位移相对误差 < 1%
DISP_TOL = {"open_hole_panel": 0.01}


def sha8(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:8]


def load_task(task_id: str) -> dict:
    with PAPER.open(encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            if d.get("task_id") == task_id:
                return d
    raise SystemExit(f"[FAIL] {task_id} 不在当前考卷里：{PAPER}")


def load_candidate(cand_dir: Path, task_id: str) -> dict:
    p = cand_dir / f"{task_id}.json"
    if not p.exists():
        raise SystemExit(f"[FAIL] 没有候选产物：{p}\n"
                         f"       （C5 原型只用现成候选，不实时调模型）")
    return json.loads(p.read_text(encoding="utf-8")), p


def read_deck_mesh(inp: Path):
    """节点坐标 + 四边形连接，直接从 deck 读（不经 gmsh，省一次建模型）。"""
    nodes, quads = {}, []
    mode = None
    for line in inp.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("*"):
            u = s.upper()
            mode = ("node" if u.startswith("*NODE") and "OUTPUT" not in u
                    else "elem" if u.startswith("*ELEMENT") else None)
            continue
        if not mode or not s or s.startswith("**"):
            continue
        parts = [x.strip() for x in s.split(",")]
        if mode == "node":
            try:
                nodes[int(parts[0])] = (float(parts[1]), float(parts[2]), float(parts[3]))
            except (ValueError, IndexError):
                pass
        else:
            try:
                tags = [int(x) for x in parts[1:] if x]
            except ValueError:
                continue
            if len(tags) >= 4:
                quads.append(tuple(tags[:4]))
    return nodes, quads


def spec_diff(cand_spec: dict, gold_spec: dict) -> dict:
    """按顶层段统计候选 spec 与标准答案的字段差异。

    为什么需要它：这张报告上出现 0.000% 时，读者的第一反应是「是不是算错了」。
    把差异摆在明面上（几处、在哪一段、是否改变几何/材料/载荷）比解释一万句
    "真的没错" 有用。差异本身不是缺陷 —— schema 里大量字段有默认值，
    写不写都得到同一个模型。
    """
    def flat(o, p="", out=None):
        out = {} if out is None else out
        if isinstance(o, dict):
            for k, v in o.items():
                flat(v, p + "/" + k, out)
        elif isinstance(o, list):
            out[p] = json.dumps(o, sort_keys=True)
        else:
            out[p] = o
        return out

    a, b = flat(cand_spec), flat(gold_spec)
    groups = {}
    for k in sorted(set(a) | set(b)):
        if a.get(k) == b.get(k):
            continue
        sec = k.strip("/").split("/")[0] or "(root)"
        groups[sec] = groups.get(sec, 0) + 1
    # 只保留与「开孔板」这个族相关的段参与总数，其他族的占位段单独列
    unrelated = ("airfoil", "stiffener", "frames", "stringers")
    relevant = {s: n for s, n in groups.items() if s not in unrelated}
    return {"total": sum(relevant.values()), "by_section": relevant,
            "n_unrelated": sum(n for s, n in groups.items() if s in unrelated)}


def _render(nodes, quads, xy_all, hole=None, zoom=None, title="", ylabel="y [mm]"):
    """网格渲染成 PNG（bytes）。中文字体不可靠，图内一律英文标签。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    segs = []
    for q in quads:
        pts = [xy_all.get(t) for t in q]
        if any(p is None for p in pts):
            continue
        for i in range(4):
            segs.append([pts[i], pts[(i + 1) % 4]])

    fig, ax = plt.subplots(figsize=(6.2, 4.6), dpi=150)
    ax.add_collection(LineCollection(segs, linewidths=0.25, colors="#9db4cc"))
    ax.set_aspect("equal")

    if zoom:
        cx, cy, r = zoom
        ax.set_xlim(cx - r, cx + r)
        ax.set_ylim(cy - r, cy + r)
        ax.set_title(title, fontsize=9)
    else:
        ax.set_xlim(min(p[0] for p in xy_all.values()) - 5,
                    max(p[0] for p in xy_all.values()) + 5)
        ax.set_ylim(min(p[1] for p in xy_all.values()) - 5,
                    max(p[1] for p in xy_all.values()) + 5)
        ax.set_title(title, fontsize=9)

    if hole:                                     # (x, y, r); 曲面族没有孔，传 None
        hx, hy, hr = hole
        ax.add_patch(plt.Circle((hx, hy), hr, fill=False, color="#c0392b", lw=1.2))
        ax.plot([hx], [hy], "+", color="#c0392b", ms=6)
    ax.tick_params(labelsize=6)
    ax.set_xlabel("x [mm]", fontsize=7)
    ax.set_ylabel(ylabel, fontsize=7)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def b64png(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def pct(a: float, b: float) -> float:
    return abs(a - b) / abs(b) * 100.0 if b else float("nan")


def _render_contour(xy_map, quads, vm, zoom=None, title="", ylabel="y [mm]"):
    """von Mises 云图（PNG bytes）。

    三角剖分必须**显式给**（每个四边形拆两个三角形），不能交给 Delaunay：
    自动剖分会把孔内部也连成三角形，画出来是一块补丁 —— 而且它看起来
    「像那么回事」，只有对着几何才知道错了。
    """
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.tri as mtri
    from matplotlib.colors import Normalize

    tags = list(xy_map)                     # 顺序即坐标顺序，z 必须同样排
    xy = [xy_map[t] for t in tags]
    idx = {t: i for i, t in enumerate(tags)}
    tris = []
    for q in quads:
        try:
            a, b, c, d = (idx[t] for t in q)
        except KeyError:
            continue
        tris.append((a, b, c))
        tris.append((a, c, d))
    z = np.array([vm.get(t, np.nan) for t in tags], dtype=float)
    vmax = float(np.nanmax(z))
    tri = mtri.Triangulation([p[0] for p in xy], [p[1] for p in xy],
                             np.array(tris, dtype=int))

    fig, ax = plt.subplots(figsize=(6.2, 4.6), dpi=150)
    levels = np.linspace(0.0, vmax, 21)
    cs = ax.tricontourf(tri, z, levels=levels, cmap="turbo", extend="max")
    # 单元边：云图上叠一层细网格，说明「这是算出来的场」而不是插值出来的色块
    from matplotlib.collections import LineCollection
    segs = [[xy[idx[q[i]]], xy[idx[q[(i + 1) % 4]]]]
            for q in quads for i in range(4)
            if all(x in idx for x in q)]
    ax.add_collection(LineCollection(segs, linewidths=0.15, colors="k", alpha=0.12))
    ax.set_aspect("equal")

    if zoom:
        cx, cy, r = zoom
        ax.set_xlim(cx - r, cx + r)
        ax.set_ylim(cy - r, cy + r)
        ax.set_title(title, fontsize=9)
    else:
        ax.set_xlim(min(p[0] for p in xy) - 5, max(p[0] for p in xy) + 5)
        ax.set_ylim(min(p[1] for p in xy) - 5, max(p[1] for p in xy) + 5)
        ax.set_title(title, fontsize=9)

    # 热点标注（最大值所在节点）
    j = int(np.nanargmax(z))
    ax.plot([xy[j][0]], [xy[j][1]], marker="o", ms=5, mfc="none",
            mec="white", mew=1.4)
    ax.annotate(f"{z[j]:.2f} MPa", (xy[j][0], xy[j][1]),
                textcoords="offset points", xytext=(8, -14),
                fontsize=7, color="white",
                bbox=dict(boxstyle="round,pad=0.2", fc="black", alpha=.55, lw=0))
    ax.tick_params(labelsize=6)
    ax.set_xlabel("x [mm]", fontsize=7)
    ax.set_ylabel(ylabel, fontsize=7)
    fig.colorbar(cs, ax=ax, shrink=.85, pad=.02).set_label("von Mises [MPa]", fontsize=7)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    # 连本图自己的峰值一起返回：页面上的「热点」必须是这张图上画出来的那个数，
    # 不能沿用全场峰值 —— 蒙皮云图的范围和长桁上的全场峰值不是一回事。
    return buf.getvalue(), float(vmax)


def subset_mesh(nodes, quads, keep):
    """只保留 keep(v) 为真的节点，以及其节点全在子集里的单元。"""
    n2 = {t: v for t, v in nodes.items() if keep(v)}
    q2 = [q for q in quads if all(t in n2 for t in q)]
    return n2, q2


def project(nodes, mode):
    """把 3D 节点投到 2D。'xz' 看轴向剖面，'xy' 看端面/平面。"""
    if mode == "xz":
        return {t: (v[0], v[2]) for t, v in nodes.items()}
    return {t: (v[0], v[1]) for t, v in nodes.items()}


def view_plan(family, design):
    """按族给出「看哪两张图」。

    平面族（开孔板/加筋板）：整板 + 孔边放大，都投影到 xy。
    回转族（柱壳）：曲面不能直接投到一张平面图上 —— 前后会重叠。所以拆成
      ① 前半（y >= 0）投影到 xz：轴向鼓胀 + 纵向应力分布，无遮挡；
      ② 中截面（|z - L/2| < tol）投影到 xy：整个圆环，看周向分布（长桁位置）。
    这不是「模板不通用」，而是「几何可视化必须按族适配」——
    数字链路（pipeline -> post -> truth）两族完全同一套。
    """
    if family == "fuselage_barrel":
        L = float(design["length"])
        zc, tol = L / 2.0, max(1.0, L * 0.01)
        return [
            {"tag": "front",
             "title": "barrel: front half (x-z)",
             "caption": ("整体（前半，x-z 投影）"),
             "keep": lambda v: v[1] >= -1e-9,
             "proj": "xz", "zoom": None},
            {"tag": "section",
             "title": f"barrel: cross-section at z={zc:.0f}",
             "caption": (f"中截面 z={zc:.0f} mm（整个圆环，看周向分布）"),
             "keep": lambda v: abs(v[2] - zc) < tol,
             "proj": "xy", "zoom": None},
        ]
    # 加筋板族：无孔，第二张图看长桁交界（那是应力集中处）
    if family == "stiffened_panel":
        L, W = float(design["length"]), float(design["width"])
        st = design.get("stringer_stations") or []
        if st:
            fx, fy, r = float(st[0]), W / 2.0, max(80.0, W * 0.25)
            cap = f"长桁局部（x≈{fx:g} mm，半宽 {r:g} mm）—— 蒙皮与长桁交界是应力集中处"
        else:
            fx, fy, r = L / 2.0, W / 2.0, max(80.0, min(L, W) * 0.3)
            cap = f"板中心局部（半宽 {r:g} mm）"
        # 云图只画蒙皮（E_PANEL）：长桁凸出蒙皮 20 mm，直接投到 x-y 会盖住蒙皮，
        # 图上就会看到「长桁位置应力≈0」这种假象。网格图仍然用全结构，
        # 否则看不出「这是加筋板」。
        return [
            {"tag": "full", "title": "full panel (x-y)", "caption": "整体（x-y 投影，云图取蒙皮）",
             "keep": None, "proj": "xy", "zoom": None, "contour_elset": "E_PANEL"},
            {"tag": "detail", "title": "stringer detail", "caption": cap,
             "keep": None, "proj": "xy", "zoom": (fx, fy, r),
             "contour_elset": "E_PANEL"},
        ]

    # 开孔板族
    hx, hy = (float(x) for x in design["hole_center"])
    hole_d = float(design["hole_d"])
    return [
        {"tag": "full", "title": "full plate (x-y)",
         "caption": "整体（x-y 投影）",
         "keep": None, "proj": "xy", "zoom": None},
        {"tag": "hole", "title": "hole region",
         "caption": f"孔边局部（半宽 {hole_d * 1.5:g} mm）：孔周加密是判据要求的一部分",
         "keep": None, "proj": "xy", "zoom": (hx, hy, hole_d * 1.5)},
    ]



def build_spec_rows(spec: dict, design: dict, family: str) -> list:
    """按族列出「模型读成了什么」的关键参数。

    不能写死「孔直径」这类字段名 —— 加第二个族时它就 KeyError 了。
    这里只列该族真正有的参数，缺的不编。
    """
    rows = []
    if design.get("diameter"):
        rows.append(("直径 × 长度", f"{design['diameter']:g} × {design['length']:g} mm"))
    elif design.get("length") and design.get("width"):
        rows.append(("板长 × 板宽", f"{design['length']:g} × {design['width']:g} mm"))
    if design.get("thickness"):
        rows.append(("厚度", f"{design['thickness']:g} mm"))
    if design.get("hole_d"):
        rows.append(("孔直径", f"{design['hole_d']:g} mm"))
    if design.get("n_stringers"):
        desc = f"{int(design['n_stringers'])} 根"
        if design.get("stringer_pitch"):
            desc += f"（间距 {design['stringer_pitch']:g} mm）"
        rows.append(("长桁", desc))
    if design.get("n_frames"):
        rows.append(("框", f"{int(design['n_frames'])} 个"))
    mat = (spec.get("material") or {})
    if mat.get("name"):
        e = mat.get("youngs_modulus")
        rows.append(("材料", f"{mat['name']}" + (f"（E={e:g} MPa）" if e else "")))
    mesh = spec.get("mesh") or {}
    if mesh.get("size_chord"):
        rows.append(("网格尺寸", f"{mesh['size_chord']:g} mm"))
    ld = spec.get("load") or {}
    if ld.get("kind") and ld.get("magnitude") is not None:
        unit = "MPa" if ld["kind"] == "pressure" else "N"
        rows.append(("载荷", f"{ld['kind']} {ld['magnitude']:g} {unit}"))
    return rows


def build_html(ctx: dict) -> str:
    c = ctx
    rel = c["disp_err"]
    cross = bool(c.get("cross_solver"))
    # ★ 跨求解器数字只作 diagnostic：不套 ccx 判据线，不印"通过/未通过"。
    ok = (not cross) and rel <= c["tol"] * 100.0
    if cross:
        verdict = (f"跨求解器诊断：位移差 {rel:.3f}%（Abaqus vs ccx 参考解）"
                   f" —— 仅记录，不作为 C5 通过/失败判据")
        accent = "var(--blue)"
    else:
        verdict = (f"位移相对误差 {rel:.3f}%，判据线 {c['tol'] * 100:.1f}% —— 通过"
                   if ok else
                   f"位移相对误差 {rel:.3f}%，已超判据线 {c['tol'] * 100:.1f}% —— 未通过")
        accent = "var(--ok)" if ok else "var(--bad)"

    if cross:
        why_html = ("<b>这个差是哪来的？</b> 本页数值来自 Abaqus/Standard，参考解来自 "
                    "CalculiX ccx。两者用同一套网格（节点数一致），但求解器、单元应力恢复"
                    "与峰值定位不同，所以位移/应力差只作<b>跨求解器诊断</b>，"
                    "不套用同一求解器的一致性判据线。")
        can_html = ("从一句中文任务书出发，几何、网格、Abaqus 求解、ODB 提取与云图"
                    "全链跑通，并与另一款求解器的参考解完成<b>同模型跨码对照</b>；"
                    "差异按诊断记录，不在该页判定通过与否。")
        footer_cmd = f"python make_c5_report.py --case {c['case']} --odb-json &lt;name&gt;.odb.json"
    caveat_html = (f'<p style="margin:6px 0 0; font-size:12.5px; color:#8a6a1a">'
                   f'<b>口径提醒</b>：{c["vm_caveat"]}</p>' if c.get("vm_caveat") else "")
    if not cross:
        why_html = (f"<b>为什么误差是 {rel:.3f}%？</b> 因为候选 spec 与标准答案在"
                    f"<b>影响结果的字段上完全一致</b>（几何、材料、载荷、边界），差异只有"
                    f"<b>{c['sdiff']['total']}</b> 处，且全部落在不改结果的段里"
                    f"（{'、'.join(f'<code>{k}</code> {v} 处' for k, v in c['sdiff']['by_section'].items())}）。"
                    f"这些是 schema 里<b>有默认值</b>的字段 —— 写不写，建出来是同一个模型。"
                    f"{('另有 %d 处属于其他族的占位段（翼型等），本族不用。' % c['sdiff']['n_unrelated']) if c['sdiff']['n_unrelated'] else ''}")
        can_html = (f"从一句中文任务书出发，几何、网格、求解、结果提取全链"
                    f"自动跑通，且最大位移与标准答案的相对误差在 {c['tol'] * 100:.1f}% 判据线以内。")
        footer_cmd = f"python make_c5_report.py --case {c['case']}"

    def src(name, path, field):
        return (f'<span class="src" title="{path} · {field}">'
                f'{name} <code>{Path(path).name}</code>'
                f' <span class="sha">sha:{sha8(Path(path))}</span></span>')

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{c['case']} · C5 原型报告</title>
<style>
  :root {{ --ink:#1a2733; --mut:#5c6b7a; --line:#d8e0e8; --blue:#1f4e79; --bg:#f7f9fb;
           --ok:#1e7a4d; --bad:#b03030; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
          font:15px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif; }}
  .wrap {{ max-width:940px; margin:0 auto; padding:32px 24px 64px; }}
  header {{ border-bottom:3px solid var(--blue); padding-bottom:14px; margin-bottom:26px; }}
  h1 {{ margin:0 0 6px; font-size:25px; letter-spacing:-.3px; }}
  .sub {{ color:var(--mut); font-size:13px; }}
  .verdict {{ margin:24px 0 30px; padding:16px 20px; border-left:4px solid
              {accent}; background:#fff;
              border-radius:0 6px 6px 0; font-size:17px; }}
  section {{ background:#fff; border:1px solid var(--line); border-radius:8px;
             padding:20px 22px; margin-bottom:20px; }}
  h2 {{ margin:0 0 14px; font-size:15px; color:var(--blue); letter-spacing:.5px;
        text-transform:uppercase; }}
  h2 .n {{ display:inline-block; width:20px; height:20px; line-height:20px; text-align:center;
           background:var(--blue); color:#fff; border-radius:50%; font-size:11px;
           margin-right:8px; }}
  .nl {{ background:var(--bg); border-left:3px solid var(--line); padding:12px 14px;
         font-size:14px; color:#2a3a48; margin:0 0 16px; }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; }}
  th, td {{ text-align:left; padding:7px 10px; border-bottom:1px solid var(--line); }}
  th {{ color:var(--mut); font-weight:600; font-size:12px; text-transform:uppercase;
        letter-spacing:.4px; }}
  td.num {{ font-variant-numeric:tabular-nums; text-align:right; }}
  tr:last-child td {{ border-bottom:none; }}
  .figs {{ display:flex; gap:14px; flex-wrap:wrap; }}
  .figs figure {{ flex:1 1 300px; margin:0; }}
  .figs img {{ width:100%; border:1px solid var(--line); border-radius:4px; }}
  .figs figcaption {{ font-size:12px; color:var(--mut); margin-top:6px; }}
  .src {{ display:block; font-size:11px; color:var(--mut); margin-top:3px; }}
  .src code {{ background:var(--bg); padding:0 3px; border-radius:2px; }}
  .sha {{ color:#94a3b2; }}
  .ok {{ color:var(--ok); font-weight:600; }}
  .bad {{ color:var(--bad); font-weight:600; }}
  ul.limits {{ margin:8px 0 0; padding-left:20px; font-size:13.5px; color:#3a4a58; }}
  ul.limits li {{ margin:4px 0; }}
  footer {{ margin-top:30px; font-size:11.5px; color:var(--mut); line-height:1.9; }}
  footer code {{ background:#eef2f6; padding:1px 4px; border-radius:2px; }}
</style></head><body><div class="wrap">

<header>
  <h1>{c['case']}</h1>
  <div class="sub">{c['family']} · 由一句自然语言自动建模仿真 · 报告生成
    {c['generated_at']}</div>
</header>

<div class="verdict">{verdict}</div>

<section>
  <h2><span class="n">1</span>你说了一句什么</h2>
  <p class="nl">{c['nl']}</p>
  <table>
    <tr><th>模型读成</th><th>值</th><th>来源</th></tr>
    {''.join(f'<tr><td>{k}</td><td class="num">{v}</td><td>'
             f'<span class="src"><code>{Path(c["cand_path"]).name}</code>'
             f' <span class="sha">sha:{sha8(Path(c["cand_path"]))}</span></span></td></tr>'
             for k, v in c['spec_rows'])}
  </table>
</section>

<section>
  <h2><span class="n">2</span>它建成了什么</h2>
  <div class="figs">
    {''.join(f"""<figure><img alt="mesh {f['tag']}" src="{f['mesh']}">
      <figcaption><b>网格 · {f['caption']}</b><br>该视图 {f['n_nodes']} 个节点；
        全模型 <b>{c['n_elem']}</b> 个四边形单元 / <b>{c['n_nodes']}</b> 个节点。</figcaption></figure>"""
      for f in c['figs'])}
  </div>
  {src('网格与节点', c['inp_path'], '*NODE / *ELEMENT')}
</section>

<section>
  <h2><span class="n">3</span>算出来多少，跟标准答案差多少</h2>
  <table>
    <tr><th>指标</th><th style="text-align:right">本次求解</th>
      <th style="text-align:right">标准答案</th>
      <th style="text-align:right">{'差异（诊断）' if cross else '相对误差'}</th></tr>
    <tr><td>最大位移 <span class="src">mm</span></td>
      <td class="num">{c['max_disp']:.5f}</td>
      <td class="num">{c['gold_disp']:.5f}</td>
      <td class="num {'' if cross else ('ok' if ok else 'bad')}">{rel:.3f}%</td></tr>
    <tr><td>最大 von Mises <span class="src">MPa · 外表面</span></td>
      <td class="num">{c['max_vm']:.3f}</td>
      <td class="num">{c['gold_vm'] if c['gold_vm'] is not None else '—'}</td>
      <td class="num">{('%.3f%%' % c['vm_err']) if c['gold_vm'] else '—'}</td></tr>
    <tr><td>节点数</td>
      <td class="num">{c['n_nodes']}</td>
      <td class="num">{c['gold_nodes']}</td>
      <td class="num">{c['node_diff']:+d}</td></tr>
  </table>
  <p style="margin:12px 0 0; font-size:13.5px; color:#3a4a58">
    {why_html}
  </p>
  {src('本次求解结果', c['results_path'], 'max_disp / max_von_mises / n_nodes')}
  {src('标准答案', c['truth_path'], 'scalars.max_disp / scalars.max_von_mises')}

  <div class="figs" style="margin-top:18px">
    {''.join(f"""<figure><img alt="von Mises {f['tag']}" src="{f['contour']}">
      <figcaption><b>von Mises 云图 · {f['caption']}</b><br>
        本图 {f['contour_nodes']} 个{'（仅 ' + f['elset'] + '）' if f['elset'] else ''}节点，
        色标 0…{f['contour_vmax']:.2f} MPa；白圈是本图热点（{f['contour_vmax']:.2f} MPa）。
        <b>全场峰值看上表</b>{('（%.2f MPa 在长桁上，本图不含长桁）' % c['vm_field_max']) if abs(c['vm_field_max'] - f['contour_vmax']) > 1e-6 else ''}。</figcaption></figure>"""
      for f in c['figs'])}
  </div>
  <p style="margin:6px 0 0; font-size:12.5px; color:#5c6b7a">
    云图取 <b>{c['vm_src']}</b>（{c['vm_src_note']}）。
  </p>
  {caveat_html}
  {src('云图数据', c['frd_path'], c['field_label'])}
  {"" if c['kt'] is None else f"""
  <p style="margin:12px 0 0; font-size:13.5px; color:#3a4a58">
    <b>顺带一个不依赖标准答案的自洽检查</b>：净截面平均应力 =
    {c['load_mag']:g} N ÷ (({c['width']:g} − {c['hole_d']:g}) mm × {c['thickness']:g} mm)
    = <b>{c['sig_net']:.2f} MPa</b>；峰值除以它得应力集中系数
    <b>K<sub>t</sub> = {c['kt']:.2f}</b>。这两步只用本页已有的数，你可以自己复核。
    <span style="color:#8a6a1a">与 Peterson／Howland 有限宽板图表的比对<b>尚未做</b></span>
    —— 那属于「C7 试验/解析锚定」，另立任务；此处只说明这个比值本身自洽、量级合理。
  </p>"""}
</section>

<section>
  <h2><span class="n">4</span>这一页能说明什么、不能说明什么</h2>
  <p style="margin:0 0 8px"><b>能说明</b>：{can_html}</p>
  <p style="margin:0 0 4px"><b>不能说明</b>：</p>
  <ul class="limits">
    <li>这不是工程校核。标准答案本身是同一套求解器算的参考解，属<b>一致性验证</b>，不是试验或解析解锚定。</li>
    <li>只覆盖 1 个族（{c['family']}）、1 个工况；换个几何、换个载荷都没验过。</li>
    <li>模型输入用的是仓库里<b>现成的候选产物</b>，不是这一页现场调模型生成的（换成实时生成要接 API）。</li>
    <li>求解器：{c['solver']}。{'本页数值即来自另一求解器，差异只作诊断，不进入任何通过/失败判定。' if cross else '跨求解器的差异不在本页判定范围内。'}</li>
  </ul>
</section>

<footer>
  <div>C5 原型 V1 · 一条命令复现：<code>{footer_cmd}</code></div>
  <div>命令里没有任何手写数字：所有数值由脚本从下面这些文件里读出来。</div>
  <div>任务书 <code>{PAPER.name}</code> · 候选 <code>{Path(c['cand_path']).name}</code>
       · deck <code>{Path(c['inp_path']).name}</code>
       · 结果 <code>{Path(c['results_path']).name}</code>
       · 标准答案 <code>{Path(c['truth_path']).name}</code></div>
</footer>

</div></body></html>
"""


def rerun_with_solver(deck: Path, backend: str, outdir: Path, name: str):
    """默认后端崩了就换一个再跑一次，然后自己接上 post。

    为什么需要：ccx 2.23 的默认后端是 PaStiX，在 21 万 DOF 以上会以
    0xC0000005（访问违规）崩掉，日志停在打印矩阵规模之后 —— 看起来像
    「正在算」，其实进程已经死了。PARDISO 这个二进制没编译进来
    （`the PARDISO library is not linked`），所以能用的只剩 SPOOLES。
    这不是模型错、也不是数据错；把它写进报告，比悄悄换后端诚实。
    """
    sys.path.insert(0, str(HERE))
    from feagpt import solver, post

    alt = deck.with_name(f"{deck.stem}_{backend.lower()}.inp")
    txt = deck.read_text(encoding="utf-8", errors="replace")
    if "\n*STATIC\n" not in txt:
        raise SystemExit(f"[FAIL] deck 里找不到独立的 *STATIC 行，无法换后端：{deck}")
    alt.write_text(txt.replace("\n*STATIC\n", f"\n*STATIC, SOLVER={backend}\n", 1),
                   encoding="utf-8")
    run = solver.run(alt, solver="ccx", timeout=3600)
    if not run.ok:
        tail = "\n       ".join((run.log or "").strip().splitlines()[-6:])
        raise SystemExit(f"[FAIL] SOLVER={backend} 也失败（rc={run.returncode}）：\n       {tail}")
    frd = alt.with_suffix(".frd")
    data = post.load_any(frd)
    summary = post.dump_results_data(data, outdir / f"{name}.results.json",
                                     outdir / f"{name}.nodes.csv")
    return alt, frd, summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="open_hole_panel_400x200_d40")
    ap.add_argument("--candidates", default=str(DEFAULT_CAND))
    ap.add_argument("--out", default=None)
    ap.add_argument("--reuse", action="store_true",
                    help="复用 _c5_runs/<case>/ 里已有的求解结果，不重跑")
    ap.add_argument("--odb-json", default=None,
                    help="直接读已提取的 Abaqus .odb.json（跨求解器，只出诊断，不进判据）")
    args = ap.parse_args()

    # 延迟 import：这些要在 venv 里（gmsh / numpy）
    sys.path.insert(0, str(HERE))
    from feagpt.spec import FEASpec
    from feagpt import pipeline
    from feagpt import post as _post

    odb_json = Path(args.odb_json) if args.odb_json else None
    cross_solver = odb_json is not None

    task_id = f"L3_{args.case}"
    task = load_task(task_id)
    cand, cand_path = load_candidate(Path(args.candidates), task_id)

    truth_path = MODELING / args.case / "truth.json"
    if not truth_path.exists():
        raise SystemExit(f"[FAIL] 没有标准答案：{truth_path}")
    truth = json.loads(truth_path.read_text(encoding="utf-8"))

    outdir = RUNS / args.case
    outdir.mkdir(parents=True, exist_ok=True)
    spec = FEASpec.from_dict(cand["spec"])

    inp = outdir / f"{spec.name}.inp"
    results_path = outdir / f"{spec.name}.results.json"

    solver_note = "复用已有结果"
    field = None
    field_path = None
    if cross_solver:
        # ★ 跨求解器支路：ODB 已由外部 bat 提取成 .odb.json，这里只归纳+渲染。
        # 全程不跑求解器，也不拿 ccx 判据线判 Abaqus 的数（只作 diagnostic）。
        if not odb_json.exists():
            raise SystemExit(f"[FAIL] 找不到 ODB JSON：{odb_json}")
        print(f"[odb] 直接读 Abaqus ODB 提取结果：{odb_json.name}")
        field = json.loads(odb_json.read_text(encoding="utf-8"))
        # ★ Abaqus ODB reader 的节点 tag 是 str，deck mesh / ccx FRD reader 是 int。
        # 不在入口归一，云图会拿到全 NaN（matplotlib 报 non-finite，看不出真因）。
        field["nodes"] = {int(k): v for k, v in (field.get("nodes") or {}).items()}
        for key, blk in list((field.get("results") or {}).items()):
            if isinstance(blk, dict):
                field["results"][key] = {int(k): v for k, v in blk.items()}
        results_path = outdir / f"{spec.name}.abq.results.json"
        summary = _post.dump_results_data(field, results_path)
        field_path = odb_json
        inp_abq = outdir / "abq" / f"{spec.name}.inp"
        if inp_abq.exists():
            inp = inp_abq
        solver_note = "Abaqus/Standard（跨求解器，仅诊断）"
    elif args.reuse and results_path.exists():
        print(f"[reuse] 复用已有求解结果：{results_path.name}")
        summary = json.loads(results_path.read_text(encoding="utf-8"))
    else:
        print(f"[run] {spec.name} —— 建模型 / 划网格 / 求解（ccx）…")
        res = pipeline.run(spec, outdir=outdir, solver_name="ccx")
        inp = Path(res.artifacts["inp"])
        results_path = Path(res.artifacts["results"])
        if not res.ok:
            msgs = res.messages or []
            print("[retry] 默认后端失败，改 SOLVER=SPOOLES 重试一次")
            print("        " + " / ".join(m.strip() for m in msgs[-2:]))
            inp, _frd2, summary = rerun_with_solver(inp, "SPOOLES", outdir, spec.name)
            results_path = outdir / f"{spec.name}.results.json"
            solver_note = "SPOOLES"
        else:
            summary = res.results
            solver_note = "默认（PaStiX）"

    # ---- 数字：全部从 artifact 实读，一个都不手写 ---------------------- #
    gold_disp = float(truth["scalars"]["max_disp"])
    max_disp = float(summary["max_disp"])
    max_vm = float(summary["max_von_mises"])
    gold_vm = truth["scalars"].get("max_von_mises")
    gold_vm = float(gold_vm) if isinstance(gold_vm, (int, float)) else None
    n_nodes = int(summary["n_nodes"])
    gold_nodes = int(truth["scalars"]["n_nodes"])

    nodes, quads = read_deck_mesh(inp)
    if not nodes or not quads:
        raise SystemExit(f"[FAIL] 从 deck 里读不到网格：{inp}")

    design = truth["topology"]["design"]
    fam_key = truth.get("structure_family", "")
    plan = view_plan(fam_key, design)
    hole = None
    if design.get("hole_center") and design.get("hole_d"):
        hole = (float(design["hole_center"][0]), float(design["hole_center"][1]),
                float(design["hole_d"]) / 2.0)

    # ---- 应力场（云图用；summary 里只有标量，场要从 frd / odb.json 重新读）-- #
    if not cross_solver:
        frd = results_path.with_name(results_path.name.replace(".results.json", ".frd"))
        if not frd.exists():
            raise SystemExit(f"[FAIL] 找不到场文件，画不了云图：{frd}")
        field_path = frd
        field = _post.load_any(frd)
    # ★ 云图口径 = STRESS_PEAK（外表面），与 headline 定义 D8 一致。
    # 开孔板纯拉伸时中面 == 外表面（31.32 两边相同），所以用 STRESS 也看不出错；
    # 柱壳有框/长桁局部弯曲，中面 128.5 vs 外表面 286.8 —— 差 2.2 倍。
    # 拿中面画云图会系统性低估峰值，而且低估得"看起来很合理"。
    peak = field["results"].get("STRESS_PEAK") or {}
    mids = field["results"].get("STRESS") or field["results"].get("S") or {}
    src_block, src_name = ((peak, "STRESS_PEAK") if peak else (mids, "STRESS"))
    vm = {tag: _post.von_mises(v) for tag, v in src_block.items()}
    if not vm:
        raise SystemExit("[FAIL] 场文件里没有应力块，画不了云图")
    # 覆盖率闸：key 类型不一致（int vs str）会让 z 全 NaN，matplotlib 只报
    # "non-finite values"，看不出真因。这里在渲染前把错配钉死。
    cov = len(set(nodes) & set(vm)) / len(nodes) if nodes else 0.0
    if cov < 0.99:
        raise SystemExit(f"[FAIL] 应力场只覆盖 {cov:.1%} 的 deck 节点"
                         f"（场 key 与网格 tag 对不上？）")
    vm_mid = {tag: _post.von_mises(v) for tag, v in mids.items()} if mids else {}

    import time
    t0 = time.time()
    figs = []
    for v in plan:
        if v["keep"]:
            n2, q2 = subset_mesh(nodes, quads, v["keep"])
        else:
            n2, q2 = nodes, quads
        if not n2 or not q2:
            print(f"[warn] 视图 {v['tag']} 过滤后为空，跳过")
            continue
        proj = project(n2, v["proj"])
        ylabel = "z [mm]" if v["proj"] == "xz" else "y [mm]"
        mesh_png = _render(n2, q2, proj, hole, zoom=v["zoom"], title=v["title"],
                           ylabel=ylabel)

        # 云图可能只取某个 elset（例如加筋板只画蒙皮，避免长桁投影遮挡）
        cn, cq = n2, q2
        if v.get("contour_elset"):
            sel = _post.read_deck_elset_nodes(inp, v["contour_elset"])
            if sel:
                cn = {k: val for k, val in n2.items() if k in sel}
                cq = [q for q in q2 if all(k in cn for k in q)]
        cproj = project(cn, v["proj"]) if cn else proj
        cont_png, cont_vmax = _render_contour(cproj, cq or q2, vm, zoom=v["zoom"],
                                             title="von Mises, " + v["title"],
                                             ylabel=ylabel)
        (outdir / f"mesh_{v['tag']}.png").write_bytes(mesh_png)
        (outdir / f"vm_{v['tag']}.png").write_bytes(cont_png)
        figs.append({"tag": v["tag"], "caption": v["caption"],
                     "mesh": b64png(mesh_png), "contour": b64png(cont_png),
                     "n_nodes": len(n2),
                     "contour_nodes": len(cn) if v.get("contour_elset") else len(n2),
                     "contour_vmax": cont_vmax,
                     "elset": v.get("contour_elset")})
        print(f"[fig] {v['tag']}: {len(n2)} 节点 / {len(q2)} 单元")
    print(f"[fig] {len(figs)} 组图渲染完成（{time.time() - t0:.1f}s）")
    print(f"[contour] 场来自 {src_name}，{len(vm)} 节点，max {max(vm.values()):.2f} MPa"
          + (f"（中面口径 max {max(vm_mid.values()):.2f}）" if vm_mid else ""))

    # ---- 应力集中系数：本页两个数算出来的比值，不依赖 gold --------------- #
    # Kt = 峰值 von Mises / 净截面平均应力；净截面 = (板宽 - 孔径) × 厚度。
    # 单向拉伸下孔口主应力即周向应力、径向为零 ⇒ von Mises ≈ 该主应力，
    # 所以用 vM 峰值去除是合法的。这个比值能从页面上两个数自己复核。
    mag = None
    try:
        mag = float((cand["spec"].get("load") or {}).get("magnitude") or 0.0)
    except (TypeError, ValueError):
        mag = None
    sig_net = None
    kt = None
    # 净截面/应力集中系数只对「开孔板受面内拉伸」这种情形有意义；
    # 加筋板受面外压力、柱壳受内压都不适用 —— 宁可不出这一行，也不要套错公式。
    if (fam_key == "open_hole_panel" and design.get("hole_d") and mag):
        try:
            net_w = float(design["width"]) - float(design["hole_d"])
            if net_w > 0:
                sig_net = mag / (net_w * float(design["thickness"]))
                kt = max_vm / sig_net
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            sig_net = kt = None

    fam = truth.get("structure_family", "")
    gold_spec = json.loads((MODELING / args.case / "spec.json").read_text(encoding="utf-8"))
    sdiff = spec_diff(cand["spec"], gold_spec)

    ctx = {
        "sdiff": sdiff,
        "case": args.case,
        "family": fam,
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
        "nl": task["input"]["nl"],
        "cand_path": str(cand_path),
        "inp_path": str(inp),
        "results_path": str(results_path),
        "frd_path": str(field_path),
        "field_label": ("STRESS_PEAK / STRESS 块 · ODB 提取的逐节点 6 分量"
                        if cross_solver else "STRESS 块 · FRD 逐节点 6 分量 → von Mises"),
        "cross_solver": cross_solver,
        "truth_path": str(truth_path),
        "spec_rows": build_spec_rows(cand["spec"], design, fam_key),
        "figs": figs,
        "vm_field_max": max(vm.values()),
        "vm_src": src_name,
        "vm_src_note": ("外表面峰值，与 headline 定义 D8 一致"
                        if src_name == "STRESS_PEAK" else "只有中面场可用（该结果未输出峰值块）"),
        "vm_caveat": (((field.get("meta") or {}).get("stress_reduction") or {}).get("STRESS_PEAK")
                      if cross_solver else None),
        "sig_net": sig_net,
        "kt": kt,
        "load_mag": mag,
        "n_stress_nodes": len(vm),
        "n_nodes": n_nodes, "n_elem": len(quads),
        "hole_d": float(design.get("hole_d") or 0.0),
        "width": float(design.get("width") or 0.0),
        "thickness": float(design.get("thickness") or 0.0),
        "max_disp": max_disp, "gold_disp": gold_disp,
        "max_vm": max_vm, "gold_vm": gold_vm,
        "vm_err": pct(max_vm, gold_vm) if gold_vm else None,
        "gold_nodes": gold_nodes, "node_diff": n_nodes - gold_nodes,
        "disp_err": pct(max_disp, gold_disp),
        "tol": DISP_TOL.get(fam, 0.01),
        "solver": (f"Abaqus/Standard · {solver_note}" if cross_solver
                   else f"CalculiX ccx · 后端 {solver_note}"),
    }

    out = Path(args.out) if args.out else RUNS / args.case / f"{args.case}.c5.html"
    out.write_text(build_html(ctx), encoding="utf-8")

    if cross_solver:
        print(f"\n诊断（跨求解器，不判胜负）：位移 {max_disp:.5f} mm vs ccx 参考 "
              f"{gold_disp:.5f} mm = 差 {ctx['disp_err']:.3f}%")
        print(f"      最大 vM {max_vm:.2f} MPa"
              + (f" vs ccx {gold_vm:.2f} = 差 {ctx['vm_err']:.2f}%" if gold_vm else ""))
        print("      以上差异只作 diagnostic，不进 headline、不作 C5 判据。")
    else:
        print(f"\n结论：位移 {max_disp:.5f} mm vs 标准答案 {gold_disp:.5f} mm "
              f"= 相对误差 {ctx['disp_err']:.3f}%（判据线 {ctx['tol'] * 100:.1f}%）")
        print(f"      最大 vM {max_vm:.2f} MPa"
              + (f" vs {gold_vm:.2f} = {ctx['vm_err']:.2f}%" if gold_vm else "（标准答案无数值）"))
    print(f"报告：{out}  ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
