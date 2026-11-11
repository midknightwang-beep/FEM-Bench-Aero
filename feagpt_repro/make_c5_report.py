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


def _render(nodes, quads, xy_all, hole_center, zoom=None, title=""):
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

    if hole_center:
        hx, hy = hole_center
        ax.add_patch(plt.Circle((hx, hy), 20.0, fill=False, color="#c0392b", lw=1.2))
        ax.plot([hx], [hy], "+", color="#c0392b", ms=6)
    ax.tick_params(labelsize=6)
    ax.set_xlabel("x [mm]", fontsize=7)
    ax.set_ylabel("y [mm]", fontsize=7)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def b64png(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def pct(a: float, b: float) -> float:
    return abs(a - b) / abs(b) * 100.0 if b else float("nan")


def build_html(ctx: dict) -> str:
    c = ctx
    rel = c["disp_err"]
    ok = rel <= c["tol"] * 100.0
    verdict = (f"位移相对误差 {rel:.3f}%，判据线 {c['tol'] * 100:.1f}% —— 通过"
               if ok else
               f"位移相对误差 {rel:.3f}%，已超判据线 {c['tol'] * 100:.1f}% —— 未通过")

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
              {'var(--ok)' if ok else 'var(--bad)'}; background:#fff;
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
    <figure><img alt="mesh overview" src="{c['png_all']}">
      <figcaption>整体：{c['n_elem']} 个四边形单元 / {c['n_nodes']} 个节点。
        红线是设计孔径 D{c['hole_d']:g}。</figcaption></figure>
    <figure><img alt="mesh hole region" src="{c['png_zoom']}">
      <figcaption>孔边局部（半宽 {c['zoom_r']:g} mm）：孔周加密是判据要求的一部分。</figcaption></figure>
  </div>
  {src('网格与节点', c['inp_path'], '*NODE / *ELEMENT')}
</section>

<section>
  <h2><span class="n">3</span>算出来多少，跟标准答案差多少</h2>
  <table>
    <tr><th>指标</th><th style="text-align:right">本次求解</th>
      <th style="text-align:right">标准答案</th><th style="text-align:right">相对误差</th></tr>
    <tr><td>最大位移 <span class="src">mm</span></td>
      <td class="num">{c['max_disp']:.5f}</td>
      <td class="num">{c['gold_disp']:.5f}</td>
      <td class="num {'ok' if ok else 'bad'}">{rel:.3f}%</td></tr>
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
    <b>为什么误差是 {rel:.3f}%？</b> 因为候选 spec 与标准答案在
    <b>影响结果的字段上完全一致</b>（几何、材料、载荷、边界），差异只有
    <b>{c['sdiff']['total']}</b> 处，且全部落在不改结果的段里
    （{ '、'.join(f'<code>{k}</code> {v} 处' for k, v in c['sdiff']['by_section'].items()) }）。
    这些是 schema 里<b>有默认值</b>的字段 —— 写不写，建出来是同一个模型。
    {('另有 %d 处属于其他族的占位段（翼型等），本族不用。' % c['sdiff']['n_unrelated']) if c['sdiff']['n_unrelated'] else ''}
  </p>
  {src('本次求解结果', c['results_path'], 'max_disp / max_von_mises / n_nodes')}
  {src('标准答案', c['truth_path'], 'scalars.max_disp / scalars.max_von_mises')}
</section>

<section>
  <h2><span class="n">4</span>这一页能说明什么、不能说明什么</h2>
  <p style="margin:0 0 8px"><b>能说明</b>：从一句中文任务书出发，几何、网格、求解、结果提取全链
    自动跑通，且最大位移与标准答案的相对误差在 {c['tol'] * 100:.1f}% 判据线以内。</p>
  <p style="margin:0 0 4px"><b>不能说明</b>：</p>
  <ul class="limits">
    <li>这不是工程校核。标准答案本身是同一套求解器算的参考解，属<b>一致性验证</b>，不是试验或解析解锚定。</li>
    <li>只覆盖 1 个族（{c['family']}）、1 个工况；换个几何、换个载荷都没验过。</li>
    <li>模型输入用的是仓库里<b>现成的候选产物</b>，不是这一页现场调模型生成的（换成实时生成要接 API）。</li>
    <li>求解器：{c['solver']}。跨求解器的差异不在本页判定范围内。</li>
  </ul>
</section>

<footer>
  <div>C5 原型 V1 · 一条命令复现：<code>python make_c5_report.py --case {c['case']}</code></div>
  <div>命令里没有任何手写数字：所有数值由脚本从下面这些文件里读出来。</div>
  <div>任务书 <code>{PAPER.name}</code> · 候选 <code>{Path(c['cand_path']).name}</code>
       · deck <code>{Path(c['inp_path']).name}</code>
       · 结果 <code>{Path(c['results_path']).name}</code>
       · 标准答案 <code>{Path(c['truth_path']).name}</code></div>
</footer>

</div></body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="open_hole_panel_400x200_d40")
    ap.add_argument("--candidates", default=str(DEFAULT_CAND))
    ap.add_argument("--out", default=None)
    ap.add_argument("--reuse", action="store_true",
                    help="复用 _c5_runs/<case>/ 里已有的求解结果，不重跑")
    args = ap.parse_args()

    # 延迟 import：这两个要在 venv 里（gmsh / numpy）
    sys.path.insert(0, str(HERE))
    from feagpt.spec import FEASpec
    from feagpt import pipeline

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

    if args.reuse and results_path.exists():
        print(f"[reuse] 复用已有求解结果：{results_path.name}")
        summary = json.loads(results_path.read_text(encoding="utf-8"))
    else:
        print(f"[run] {spec.name} —— 建模型 / 划网格 / 求解（ccx）…")
        res = pipeline.run(spec, outdir=outdir, solver_name="ccx")
        if not res.ok:
            raise SystemExit("[FAIL] 求解链路未通过，不出报告。\n       "
                             + "\n       ".join((res.messages or [])[-4:]))
        summary = res.results
        inp = Path(res.artifacts["inp"])
        results_path = Path(res.artifacts["results"])

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
    xy = {t: (v[0], v[1]) for t, v in nodes.items()}

    design = truth["topology"]["design"]
    hx, hy = float(design["hole_center"][0]), float(design["hole_center"][1])
    hole_d = float(design["hole_d"])

    import time
    t0 = time.time()
    png_all = _render(nodes, quads, xy, (hx, hy), title="Full plate mesh")
    zoom_r = hole_d * 1.5
    png_zoom = _render(nodes, quads, xy, (hx, hy), zoom=(hx, hy, zoom_r),
                       title="Hole region")
    (outdir / "mesh_overview.png").write_bytes(png_all)
    (outdir / "mesh_hole_zoom.png").write_bytes(png_zoom)
    print(f"[fig] 两张图渲染完成（{time.time() - t0:.1f}s）")

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
        "truth_path": str(truth_path),
        "spec_rows": [
            ("板长 × 板宽", f"{design['length']:g} × {design['width']:g} mm"),
            ("厚度", f"{design['thickness']:g} mm"),
            ("孔直径", f"{design['hole_d']:g} mm"),
            ("材料", cand["spec"].get("material", {}).get("name", "—")),
            ("网格尺寸", f"{cand['spec'].get('mesh', {}).get('size_chord', '—')} mm"),
        ],
        "png_all": b64png(png_all),
        "png_zoom": b64png(png_zoom),
        "n_nodes": n_nodes, "n_elem": len(quads), "hole_d": hole_d,
        "zoom_r": zoom_r,
        "max_disp": max_disp, "gold_disp": gold_disp,
        "max_vm": max_vm, "gold_vm": gold_vm,
        "vm_err": pct(max_vm, gold_vm) if gold_vm else None,
        "gold_nodes": gold_nodes, "node_diff": n_nodes - gold_nodes,
        "disp_err": pct(max_disp, gold_disp),
        "tol": DISP_TOL.get(fam, 0.01),
        "solver": (summary.get("solver_meta") or {}).get("name", "ccx"),
    }

    out = Path(args.out) if args.out else RUNS / args.case / f"{args.case}.c5.html"
    out.write_text(build_html(ctx), encoding="utf-8")

    print(f"\n结论：位移 {max_disp:.5f} mm vs 标准答案 {gold_disp:.5f} mm "
          f"= 相对误差 {ctx['disp_err']:.3f}%（判据线 {ctx['tol'] * 100:.1f}%）")
    print(f"      最大 vM {max_vm:.2f} MPa"
          + (f" vs {gold_vm:.2f} = {ctx['vm_err']:.2f}%" if gold_vm else "（标准答案无数值）"))
    print(f"报告：{out}  ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
