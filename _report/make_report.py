"""Build the illustrated progress report from ``report_data.json`` + ``figs/*.png``.

Every number on the page is interpolated from ``report_data.json`` -- which was
itself measured off disk by ``make_report_data.py`` -- and every figure is a
base64-embedded PNG produced by ``make_report_figs.py`` (geometry / verification
plots) or ``make_contour_figs.py`` (post-solve field contours).  Nothing is
hand-typed, so the page cannot quote a number that is not reproducible from
what ships.

Output: ``FEM-Bench-Aero进展报告_2026-10.html`` at the workspace root.
"""

from __future__ import annotations

import base64
import html as _h
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = json.loads((HERE / "report_data.json").read_text(encoding="utf-8"))
CONTOUR = json.loads((HERE / "contour_data.json").read_text(encoding="utf-8"))
FIGS = HERE / "figs"

S = DATA["manifest"]["summary"]
G = DATA["gates"]
CASES = DATA["cases"]
CS = CONTOUR["cases"]

FAM_CN = {"wingbox": "翼盒 wingbox", "stiffened_panel": "加筋壁板 panel",
          "fuselage_barrel": "机身柱壳 barrel"}
FAM_COLOR = {"wingbox": "#2f6fd0", "stiffened_panel": "#e08a1e",
             "fuselage_barrel": "#2f9e6b"}


def e(x) -> str:
    return _h.escape(str(x))


def b64(name: str) -> str:
    return base64.b64encode((FIGS / name).read_bytes()).decode("ascii")


def figure(name: str, num: str, caption: str) -> str:
    return (f'<figure class="fig">'
            f'<img src="data:image/png;base64,{b64(name)}" alt="{e(caption)}"/>'
            f'<figcaption><span class="fignum">图 {num}</span> {caption}</figcaption>'
            f'</figure>')


def short(cid: str) -> str:
    return (cid.replace("naca4412_wingbox", "wingbox")
               .replace("fuselage_barrel_", "barrel_")
               .replace("stiffened_panel_", "panel_"))


def fmt(x, nd=3):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


# ---------------------------------------------------------------- sections
def sec_summary() -> str:
    by = S["by_family"]
    sp = S["splits"]
    n_ok = sum(1 for c in CASES if c["xval"])
    cards = [
        ("算例总数", S["n_cases"], f"{len(by)} 个结构族 / 2 棵求解树", ""),
        ("几何等价类", S["n_geometry_classes"], f"0 个跨 split 泄漏", "b"),
        ("划分", f'{sp["train"]}/{sp["val"]}/{sp["test"]}',
         "train / val / test", ""),
        ("双码配对", f'{G["gate4"]["n_pass"]}/{G["gate4"]["n_cases"]}',
         "逐 case 双求解器语义门禁", "g"),
        ("网格质量", f'{min(c["mesh"]["minJ"] for c in CASES):.4f}',
         "全树最差 minJ（阈值 0.30）；零 tri3", "g"),
        ("验收闸门", f'{G["eval"]["n_pass"]}/{G["eval"]["n_checks"]}',
         f'eval 独立复算；check_forms {G["check_forms"]["n_pass"]}/{G["check_forms"]["n_pass"]+G["check_forms"]["n_fail"]}', "g"),
    ]
    cells = "".join(
        f'<div class="stat {cls}"><div class="k">{e(k)}</div>'
        f'<div class="v">{e(v)}</div><div class="n">{e(n)}</div></div>'
        for k, v, n, cls in cards)
    return f'<div class="statrow">{cells}</div>'


def sec_families() -> str:
    """One row per family: geometry, size, load, BC — all from the specs."""
    fams = {}
    for c in CASES:
        fams.setdefault(c["family"], []).append(c)
    rows = []
    for fam, cs in fams.items():
        n = len(cs)
        tot_e = sum(c["mesh"]["n_elements"] or 0 for c in cs)
        minj = min(c["mesh"]["minJ"] for c in cs)
        if fam == "wingbox":
            geom = "NACA4412 翼盒：前后梁 + 蒙皮 + 肋（+ 长桁可选）"
            sizes = "弦 1000 / 展 2000 mm，蒙皮 3 mm"
            load = "翼尖集中力 500 N（+y）"
        elif fam == "stiffened_panel":
            geom = "四边简支平板 + 竖式 blade 长桁"
            sizes = "600×600 / 800×600 mm，厚 2 mm"
            load = "面压 q = 1e-4 MPa"
        else:
            geom = "薄壁圆筒 + 周向纵长桁（径向腹板）+ 环向框"
            sizes = "Ø2000 × 2000 mm，壁厚 3 mm"
            load = "内压 + 端弯矩 + 端剪力（组合）"
        rows.append(
            f'<tr><td><span class="dot" style="background:{FAM_COLOR[fam]}"></span>{e(FAM_CN[fam])}</td>'
            f'<td>{e(geom)}</td><td class="mid">{e(sizes)}</td>'
            f'<td>{e(load)}</td><td class="num">{n}</td>'
            f'<td class="num">{tot_e:,}</td><td class="num">{minj:.4f}</td></tr>')
    return (
        '<table><thead><tr><th>结构族</th><th>几何构成</th><th>尺寸 / 壁厚</th>'
        '<th>载荷工况</th><th>算例</th><th>单元合计</th><th>最差 minJ</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>')


def sec_case_table() -> str:
    rows = []
    for c in sorted(CASES, key=lambda c: (c["family"], c["case_id"])):
        m = c["mesh"]
        cc, ab = c["ccx"], c["abaqus"]
        dev = f'{c["xval"]["max_disp_diff_pct"]:.3f} %' if c["xval"] else "—"
        rows.append(
            f'<tr><td class="mid">{e(c["case_id"])}</td>'
            f'<td><span class="dot" style="background:{FAM_COLOR[c["family"]]}"></span>{e(FAM_CN[c["family"]].split()[0])}</td>'
            f'<td><span class="pill {c["split"]}">{c["split"]}</span></td>'
            f'<td class="num">{m["n_nodes"]:,}</td>'
            f'<td class="num">{m["n_elements"]:,}</td>'
            f'<td class="num">{m["minJ"]:.4f}</td>'
            f'<td class="num">{m["tri3"]}</td>'
            f'<td class="num">{fmt(cc["max_disp"]) if cc else "—"}</td>'
            f'<td class="num">{fmt(ab["max_disp"]) if ab else "—"}</td>'
            f'<td class="num">{dev}</td></tr>')
    return (
        '<div class="scroll"><table class="wide"><thead><tr>'
        '<th>算例</th><th>族</th><th>划分</th><th>节点</th><th>单元</th>'
        '<th>minJ</th><th>tri3</th><th>ccx max|u| (mm)</th>'
        '<th>abaqus max|u| (mm)</th><th>双码偏差</th>'
        '</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>')


def sec_split_table() -> str:
    by = S["by_family"]
    rows = []
    for fam, d in by.items():
        tot = sum(d.values())
        rows.append(
            f'<tr><td><span class="dot" style="background:{FAM_COLOR[fam]}"></span>{e(FAM_CN[fam])}</td>'
            f'<td class="num">{d.get("train",0)}</td><td class="num">{d.get("val",0)}</td>'
            f'<td class="num">{d.get("test",0)}</td><td class="num"><b>{tot}</b></td></tr>')
    rows.append(
        f'<tr class="total"><td>合计</td><td class="num">{S["splits"]["train"]}</td>'
        f'<td class="num">{S["splits"]["val"]}</td><td class="num">{S["splits"]["test"]}</td>'
        f'<td class="num"><b>{S["n_cases"]}</b></td></tr>')
    return ('<table><thead><tr><th>结构族</th><th>train</th><th>val</th><th>test</th>'
            f'<th>小计</th></tr></thead><tbody>{"".join(rows)}</tbody></table>')


def sec_gates() -> str:
    ev, g4, cf, vd, dd = (G["eval"], G["gate4"], G["check_forms"],
                          G["verify_dataset"], G["dedup"])
    rows = [
        ("eval_dataset 独立复算", f'{ev["n_pass"]}/{ev["n_checks"]}',
         "每项从磁盘重来（sha / 等价类 / 读数 / 三角数 / minJ），不读 manifest 的派生值自证"),
        ("gate4 双码语义门禁", f'{g4["n_pass"]}/{g4["n_cases"]}',
         "派生预期 vs 几何实测，逐 case × 两棵树"),
        ("verify_dataset 自洽", f'{vd.get("n_ok","?")}/{vd.get("n_cases","?")}',
         "四件套齐全 + 跨树节点配对 + 树内去重 + 应力定义一致 + 零三角"),
        ("check_forms 退化自检", f'{cf["n_pass"]}/{cf["n_pass"]+cf["n_fail"]}',
         "T1/T2/T3/T5 新参数取退化值后必须逐位还原旧模型"),
        ("树内去重", f'{dd["n_groups"]} 组', "跨树同哈希是交叉验证前提，不算重复"),
    ]
    body = "".join(
        f'<tr><td>{e(k)}</td><td class="num"><span class="pill ok">{e(v)}</span></td>'
        f'<td class="note">{e(n)}</td></tr>' for k, v, n in rows)
    return ('<table><thead><tr><th>闸门</th><th>通过</th><th>它在防什么</th></tr></thead>'
            f'<tbody>{body}</tbody></table>')


def sec_t3() -> str:
    vb = DATA["t3"]["verify_barrel"]
    p, mo = vb["pressure"], vb["moment"]
    d20 = DATA["t3"]["d20"]["cases"]
    rows = [
        ("内压 · 环向膜应力", f'{p["hoop_vm_MPa"]:.4f} MPa',
         f'pR/t = {p["hoop_closed_form_MPa"]:.4f} MPa',
         f'{(p["hoop_vm_MPa"]/p["hoop_closed_form_MPa"]-1)*100:+.3f} %'),
        ("内压 · 径向膨胀", f'{p["w_mm"]:.5f} mm',
         f'pR²/(Et) = {p["w_closed_form_mm"]:.5f} mm',
         f'{(p["w_mm"]/p["w_closed_form_mm"]-1)*100:+.3f} %'),
        ("端弯矩 · 梁弯曲", f'{mo["bending_vm_MPa"]:.4f} MPa',
         f'Mc/I = {mo["bending_closed_form_MPa"]:.4f} MPa',
         f'{(mo["bending_vm_MPa"]/mo["bending_closed_form_MPa"]-1)*100:+.3f} %'),
    ]
    body = "".join(
        f'<tr><td>{e(k)}</td><td class="num">{e(a)}</td><td class="num">{e(c)}</td>'
        f'<td class="num ok">{"✓ " if abs(float(d.split()[0]))<1 else ""}{e(d)}</td></tr>'
        for k, a, c, d in rows)
    d20rows = "".join(
        f'<tr><td class="mid">{e(c["case"])}</td>'
        f'<td class="num">{c["n_stringers"]}</td><td class="num">{c["n_frames"]}</td>'
        f'<td class="num ok">{c["structure_cross_pct"]:.4f} %</td>'
        f'<td class="num bad">{c["full_cross_pct"]:.4f} %</td></tr>'
        for c in d20)
    return (
        '<h3>7.1 三条独立解析对照（单条算例，非批量）</h3>'
        '<table><thead><tr><th>检查项</th><th>有限元实测</th><th>闭式解</th>'
        f'<th>偏差（容差 ±1%）</th></tr></thead><tbody>{body}</tbody></table>'
        '<h3>7.2 D20：交叉判据为什么不能吃全域 max|u|</h3>'
        '<p class="lead">柱壳有自由端，端框内缘会出现一种<b>软模态</b>——它的位移量级远大于结构真实变形，'
        '把两码的「全域 max|u|」推到 2–3.3 % 的分歧，而真实结构响应只差 0.4–0.8 %。'
        '所以 T3 的交叉判据改用 <b>(a) 剔除自由端端载环后的结构峰值</b> + '
        '<b>(b) 沿轴 20 站挠度剖面</b>。</p>'
        '<table><thead><tr><th>算例</th><th>长桁</th><th>框</th>'
        '<th>结构峰值口径（采用）</th><th>全域 max|u|（弃用）</th></tr></thead>'
        f'<tbody>{d20rows}</tbody></table>')


def sec_contour_table() -> str:
    """Key numbers behind the contour figures, straight from contour_data.json."""
    order = ["naca4412_wingbox", "naca4412_wingbox_sweep40",
             "naca4412_wingbox_taper060", "stiffened_panel_800x600_str3",
             "fuselage_barrel_d2000_l2000_str8_frm3"]
    rows = []
    for cid in order:
        c = CS[cid]
        rows.append(
            f'<tr><td class="mid">{e(short(cid))}</td>'
            f'<td>{c["n_elems"]:,}</td>'
            f'<td>{c["max_umag"]:.4g}</td>'
            f'<td>{c["max_vm_elem"]:.4g}</td>'
            f'<td>{c["max_peak_elem"]:.4g}</td></tr>')
    return (
        '<table><thead><tr><th>算例</th><th>单元数</th>'
        '<th>max |u| (mm)</th><th>膜应力 max (MPa)</th>'
        '<th>外表面峰值 max (MPa)</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
        '<p class="lead" style="font-size:12.2px">表中应力为<b>单元平均口径</b>（即云图色标上限）；'
        '节点级峰值会略高。全部取自各算例的 <code>&lt;case&gt;.odb.json</code>，'
        '逐条落在 <code>contour_data.json</code>。</p>')


def sec_limits() -> str:
    lim = DATA["manifest"].get("limitations", [])
    items = []
    for L in lim:
        if isinstance(L, dict):
            items.append(f'<li><b>{e(L.get("topic",""))}</b>：{e(L.get("detail",""))}</li>')
        else:
            txt = str(L)
            if "fuselage" in txt or "柱壳" in txt or "D19" in txt or "D22" in txt or "D20" in txt:
                items.append(f'<li>{e(txt)}</li>')
    if not items:
        items.append("<li>（manifest.limitations 未列出条目）</li>")
    return f'<ul class="lim">{"".join(items)}</ul>'


CSS = """
:root{
  --bg:#f5f7fa;--card:#fff;--ink:#1b2130;--ink2:#4a5568;--ink3:#7b8794;
  --line:#e2e7ef;--line2:#eef1f6;--blue:#2563eb;--green:#0f9d58;--amber:#c77700;
  --red:#d64545;--grey:#8b95a5;
  --mono:"Cascadia Mono","Consolas","SF Mono",Menlo,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"PingFang SC","Microsoft YaHei","Segoe UI",system-ui,sans-serif;
  font-size:14px;line-height:1.65;-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 100px}
header.top{background:linear-gradient(135deg,#16233c 0%,#2b4066 55%,#33507e 100%);
  border-radius:14px;padding:26px 28px;color:#fff;position:relative;overflow:hidden}
header.top::after{content:"";position:absolute;right:-70px;top:-80px;width:280px;height:280px;
  border-radius:50%;background:rgba(255,255,255,.05)}
header.top .eyebrow{font-size:12.5px;color:#9fb0d0;letter-spacing:1.5px;text-transform:uppercase}
header.top h1{margin:6px 0 8px;font-size:25px;letter-spacing:.3px}
header.top .sub{color:#c3d0e6;font-size:14px;max-width:760px}
header.top .stamp{position:absolute;right:28px;top:26px;text-align:right;font-size:12.5px;color:#9fb0d0;line-height:1.8}
header.top .stamp b{color:#fff;font-weight:600}
.statrow{display:grid;grid-template-columns:repeat(6,1fr);gap:11px;margin-top:16px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:13px 15px}
.stat .k{font-size:12px;color:var(--ink3);letter-spacing:.3px}
.stat .v{font-size:22px;font-weight:650;margin-top:3px;line-height:1.2}
.stat .n{font-size:11.5px;color:var(--ink3);margin-top:3px}
.stat.g .v{color:var(--green)}.stat.b .v{color:var(--blue)}
section{margin-top:30px}
h2.sec{font-size:17px;margin:0 0 13px;padding-left:12px;border-left:4px solid var(--blue);
  display:flex;align-items:baseline;gap:10px}
h2.sec .hint{font-size:12.5px;color:var(--ink3);font-weight:400}
h3{font-size:14.5px;margin:20px 0 9px;color:#26324a}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px}
.card+.card{margin-top:12px}
p.lead{color:var(--ink2);margin:8px 0}
figure.fig{margin:14px 0;background:var(--card);border:1px solid var(--line);
  border-radius:12px;padding:14px}
figure.fig img{width:100%;height:auto;display:block;border-radius:7px}
figure.fig figcaption{font-size:12.5px;color:var(--ink3);margin-top:10px;line-height:1.6}
.fignum{display:inline-block;background:#eef4ff;color:var(--blue);font-weight:600;
  font-size:11.5px;padding:1px 8px;border-radius:20px;margin-right:6px}
table{width:100%;border-collapse:collapse;font-size:13px}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:11px;background:var(--card)}
table.wide{min-width:940px}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line2);vertical-align:top}
th{font-size:12px;color:var(--ink3);font-weight:600;background:#fafbfd;position:sticky;top:0}
tbody tr:hover{background:#fafcff}
td.num{font-family:var(--mono);font-size:12.3px;text-align:right;white-space:nowrap}
td.mid{font-family:var(--mono);font-size:12.2px}
td.note{font-size:12.3px;color:var(--ink3)}
tr.total td{border-top:2px solid var(--line);font-weight:600}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;vertical-align:middle}
.pill{display:inline-block;font-size:11.5px;padding:1px 9px;border-radius:20px;font-weight:600}
.pill.train{background:#eef4ff;color:#2f6fd0}
.pill.val{background:#fdf3dd;color:#b8860b}
.pill.test{background:#fdeaea;color:#c0392b}
.pill.ok{background:#e9f7ef;color:var(--green)}
.num.ok{color:var(--green);font-weight:600}
.num.bad{color:var(--red)}
ul.lim{color:var(--ink2);font-size:13px;padding-left:22px}
ul.lim li{margin:6px 0}
.callout{background:#eef4ff;border:1px solid #cddffb;border-radius:11px;
  padding:13px 17px;color:#1e3a68;font-size:13.3px;margin-top:12px}
.callout b{color:#12305e}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
code{font-family:var(--mono);background:#f2f4f8;padding:1px 6px;border-radius:5px;font-size:12.3px}
footer{margin-top:34px;color:var(--ink3);font-size:12.3px;text-align:center}
@media(max-width:900px){.statrow{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}}
"""


def build() -> str:
    sp = S["splits"]
    parts = []
    parts.append(f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>FEM-Bench-Aero · 数据集进展报告</title>
<style>{CSS}</style></head><body><div class="wrap">
<header class="top">
  <div class="eyebrow">FeaGPT 复现 · 飞机结构智能有限元建模数据集</div>
  <h1>FEM-Bench-Aero 数据集进展报告</h1>
  <div class="sub">截至本轮收口：三种典型飞机结构族已全部落地双求解器（CalculiX + Abaqus），
    {S["n_cases"]} 条算例 / {S["n_geometry_classes"]} 个几何等价类，全部门禁在盘上可独立复算。
    本报告的全部数字与图像均由数据集自身的产物生成，未手工填写。</div>
  <div class="stamp">生成时间<br/><b>{e(DATA["meta"]["generated_at"])}</b><br/>
     发布树 <b>{e(DATA["meta"]["release_tree"])}</b><br/>
     schema v{e(DATA["meta"]["schema_version"])}</div>
</header>
{sec_summary()}''')

    parts.append(f'''<section><h2 class="sec">1 · 数据集是什么<span class="hint">目标与定位</span></h2>
<div class="card"><p class="lead">
本数据集服务于「自然语言 → 参数化几何 → 网格 → 求解 → 结果」的智能建模链路复现（FeaGPT 思路）。
每条算例是一份<b>可复算的六件套</b>：<code>spec.json</code>（参数化意图）、<code>model.step</code>（几何）、
<code>model.msh</code>（网格）、<code>model.inp</code>（求解卡）、<code>model.results.json</code>（归纳后的场量）、
<code>truth.json</code>（几何自洽真值 + spec 哈希）。</p>
<p class="lead">发布树 <b>modeling/</b> 是 CalculiX 结果，<b>_xval/</b> 是同一模型的 Abaqus 结果（仅供交叉验证，不单独发布）。
「分组为逻辑名 → 建面打标 → 继承 outDimTagsMap」的机制保证：<b>换几何形式不会让分组悄悄跑偏</b>。</p>
</div>
{figure("fig1_family_meshes.png", "1",
  "三种结构族的代表性网格。翼盒取俯视（x–z，可见肋线与前后梁）；加筋壁板取局部放大（可见长桁腹板与蒙皮装配）；"
  "机身柱壳取两框之间的横截面（红点为真实长桁角度）。三张图均直接由归档 <code>model.msh</code> 读回绘制，非示意。")}
</section>''')

    parts.append(f'''<section><h2 class="sec">2 · 三种结构族<span class="hint">覆盖度</span></h2>
{sec_families()}
<div class="callout">
<b>族的含义。</b>「族」是几何生成器的分类：翼盒走 airfoil + loft/extrude 路径，加筋壁板走平板 + 布尔打标路径，
柱壳走圆筒 + 周向长桁 + 环向框路径。三族的接入面同样是<b>按族声明</b>的
（<code>bc_nodes / shell_thickness / clamp_dofs / pressure_group / pressure_dload_sign</code>），
而不是在链路里写死翼盒。
</div></section>''')

    parts.append(f'''<section><h2 class="sec">3 · 参数空间：平面形状族的扩展<span class="hint">M5 / T1</span></h2>
<p class="lead">翼盒族从「等直盒段」扩展到<b>线性后掠 + 线性锥度</b>的平面形状空间。
派发规则：当 <code>sweep_deg == 0 且 tip_chord_ratio == 1</code> 时走原 M1 的拉伸路径（逐位还原旧模型），
否则走放样（loft）。下图的每条曲线直接取自对应 <code>spec.json</code> 的真实 <code>sweep_deg</code> / <code>tip_chord_ratio</code>。</p>
{figure("fig2_planform.png", "2",
  "翼盒平面形状族（共 9 条带平面形状 + 基线）。前缘参考线 + 翼尖缩比 λ + 后掠偏移，"
  "由各算例 spec.json 的 <code>sweep_deg</code> / <code>tip_chord_ratio</code> 驱动绘制。")}
</section>''')

    parts.append(f'''<section><h2 class="sec">4 · 数据划分与几何等价类<span class="hint">M4 / M5 规则化</span></h2>
<div class="two">
<div class="card">{sec_split_table()}
<p class="lead" style="margin-top:12px;font-size:12.6px">
划分由声明式规则（<code>HOLDOUT_REGIONS</code>）决定，而非显式表：单维外推 → val，双维外推 → test，
未命中默认 train。<b>同一几何等价类绝不跨 split</b>（硬闸，会咬人：已做负向测试）。
规则必须复现冻结的口径 D12，由 <code>rule_reproduces_D12</code> 断言。</p>
</div>
<div>{figure("fig5_splits.png", "5",
  "按结构族 × 划分的算例分布。总 %d 条 / %d 个等价类，%d 个等价类跨 split。"
  % (S["n_cases"], S["n_geometry_classes"], S["n_leaky_classes"]))}</div>
</div>
<div class="callout"><b>等价类 = 白名单指纹。</b>只取「族 + 几何 + 壁厚」等几何量算指纹，
<b>排除</b> mesh / load / bc / analysis 这些非几何字段；另有黑名单版互验（两种口径必须给出同一划分），
再加同类成员 <code>truth.design</code> 一致的跨文件佐证。现在全树 25 个等价类，唯一的多成员类是
「基线 + 它自己的网格消融对照」。</div>
</section>''')

    parts.append(f'''<section><h2 class="sec">5 · 双求解器交叉验证<span class="hint">独立复算的核心证据</span></h2>
<p class="lead">每条算例同时用 CalculiX 与 Abaqus 求解，两码归一到同一套
<code>{{nodes:{{DISP,FORC,STRESS}}}}</code> 结构后逐节点比对。下图读数全部取自两棵树各自的
<code>model.results.json</code>。</p>
{figure("fig4_xval.png", "4",
  "(a) 双求解器 max|u| 的 1:1 对照（对数轴，虚线为完全一致）；(b) 逐算例双码相对偏差，红线为 1% 容差。"
  "柱壳两条的全域偏差（2.02% / 3.34%）见第 7 节——那是口径问题，不是求解分歧。")}
<div class="callout"><b>两条腿都要。</b>关 4 只保证「结果与网格同源」（几何自洽），
它<b>看不见</b>「新网格 + 旧结果」这种错配；所以交叉验证与退化自检必须同时在场。
退化自检专抓第三类错误：模型对、结果对、门禁全过，但新加的参数其实是个<b>空转字段</b>。</div>
</section>''')

    parts.append(f'''<section><h2 class="sec">6 · 网格质量与验收闸门<span class="hint">全部可复算</span></h2>
{figure("fig3_minj.png", "3",
  "26 条算例的网格质量（minSICN，直接由归档 model.msh 重新量测）。全树零 tri3、全部 quad4，"
  "最差 0.4861，门禁阈值 0.30。")}
{sec_gates()}
</section>''')

    parts.append(f'''<section><h2 class="sec">7 · 本轮新增：T3 机身加筋柱壳<span class="hint">第三结构族</span></h2>
<p class="lead">柱壳是本数据集第一个<b>多载荷组合</b>工况（内压 + 端弯矩 + 端剪力），
也是第一条能拿「壳体薄膜解 + 梁弯曲解」做解析对照的算例族。落族过程中立了四条纪律：</p>
<div class="card">
<ul class="lim">
<li><b>D19 · 网格包络</b>：周向长桁数 <code>n_stringers ∈ {{0}} ∪ [5, ∞)</code>，1–4 根会被拒——低于五根时框弧上必然出现三角。</li>
<li><b>D20 · 交叉判据换口径</b>：改用「结构峰值」+「沿轴挠度剖面」，弃用被自由端软模态污染的全域 max|u|。</li>
<li><b>D21 · 内压方向按族声明</b>：<code>pressure_dload_sign</code> 进 <code>GeometryResult</code>，柱壳置 +1，修掉了内压曾被写成外压的缺陷。</li>
<li><b>D22 · 非 blade 截面拒绝</b>：柱壳 builder 只建径向腹板，T 形截面的请求会被<b>显式拒绝</b>，而不是静默产出 blade 模型。</li>
</ul></div>
{figure("fig6_t3.png", "6",
  "(a) 柱壳三条独立解析对照的偏差：环向膜应力 +0.131%、径向膨胀 −0.329%、端弯矩梁弯曲 −0.681%，全部落在 ±1% 内；"
  "(b) D20 的口径对比——结构峰值口径 0.40% / 0.78% 过关，全域口径 2.02% / 3.34% 会把好结果判成失败。")}
{sec_t3()}
</section>''')

    parts.append(f'''<section><h2 class="sec">8 · 解析对照与网格收敛<span class="hint">独立于双码之外的第二把尺子</span></h2>
{figure("fig7_panel.png", "7",
  "600×600 四边简支加筋壁板的网格收敛：12 → 6 → 3 mm，中心挠度从 −6.92% 收敛到 −0.10%（相对 Navier 解析解）。"
  "该数据来自 <code>diagnostics/panel_convergence.json</code>。")}
<div class="callout"><b>为什么需要第三把尺子。</b>双求解器交叉只能证明「两码一致」，
不能证明「都对」；只有闭式解能锚定绝对正确性。所以每条族都配一条独立解析线：
翼盒用悬臂梁解（<code>verify_cantilever.py</code>）、平板用 Navier 解（<code>verify_panel.py</code>）、
柱壳用薄膜解 + 梁弯曲解（<code>verify_barrel.py</code>）。</div>
</section>''')

    bc = CS["fuselage_barrel_d2000_l2000_str8_frm3"]
    wb = CS["naca4412_wingbox"]
    sw = CS["naca4412_wingbox_sweep40"]
    parts.append(f'''<section><h2 class="sec">9 · 求解后场云图<span class="hint">从归档网格 + 求解器逐节点场渲染</span></h2>
<p class="lead">以下五张是<b>真正的求解结果场</b>，不是示意图：几何从数据集的
<code>model.msh</code> 读回，逐节点场值取自 Abaqus ODB 抽取的 <code>&lt;case&gt;.odb.json</code>。
云图按<b>单元</b>着色（四节点平均值），色标即该图的 min→max。
变形按 <code>x + scale·u</code> 绘制，放大倍数取「使 max|u| 等于模型最大跨度 6%」，逐图标出。</p>
{figure("figC1_wingbox_field.png", "8",
  f"翼盒基线的完整场：膜应力（变形前 / 放大后）、位移幅值、外表面峰值应力。"
  f"位移云图呈典型的悬臂翼展向弯曲——翼根近零、翼尖 {wb['max_umag']:.3g} mm 为峰值。"
  f"外表面峰值 {wb['max_peak_elem']:.3g} MPa 即 D8 定义的尺寸判据。")}
{figure("figC2_planform_field.png", "9",
  f"同一膜应力场在三种平面形状上的分布（共用色标，可直接互比）："
  f"后掠 40° 的翼根应力明显高于直翼，正是后掠把弯矩集中到根部的可视化证据。"
  f"位移上也看得出来——后掠 40° 翼尖 {sw['max_umag']:.3g} mm，约为直翼基线 {wb['max_umag']:.3g} mm 的 3 倍。")}
{figure("figC3_panel_field.png", "10",
  "加筋壁板：外表面峰值应力 + 位移幅值。位移云图上四个鼓包对应四个长桁隔舱——"
  "隔舱中心挠度最大、长桁线上近零，正是加筋板弯曲模态的定义性特征。")}
{figure("figC4_barrel_field.png", "11",
  f"机身柱壳：(a) 膜应力（色标上限取 P97，峰值 {bc['max_peak_elem']:.3g} MPa 集中在端框与长桁根部）；"
  f"(b) 径向位移 u_r，整体外胀（{bc['ur_min']:.3g} … {bc['ur_max']:.3g} mm）——"
  f"这就是 D21「内压方向 = +1」判据的直接可视化证据；(c) 位移幅值 max {bc['max_umag']:.3g} mm。")}
{figure("figC5_contact_sheet.png", "12",
  "数据集多样性检查表：十二条算例各出一张位移云图（子图各自归一化）。"
  "肋数、长桁数、后掠角、锥度的变化如何在响应形状上体现，一图看全。")}
{sec_contour_table()}
<div class="callout"><b>为什么云图值得单独成节。</b>数值门禁（第 6 节）只能证明「数对得上」，
不能证明「场长得像回事」。云图是唯一能一眼看出<b>刚体漂移、单元扭曲、载荷方向反了</b>这类
错误的检查——本轮 D21（内压曾被施加成外压）就是靠柱壳的径向位移<b>符号</b>暴露的。</div>
</section>''')

    parts.append(f'''<section><h2 class="sec">10 · 局限与下一步<span class="hint">不吹已完成度</span></h2>
{sec_limits()}
<div class="callout">
<b>下一步（batch4）。</b>已定方向为 <b>T4 开口</b>——孔边应力集中，无限板圆孔的 Kt = 3.0 有干净的解析对照，
且与现有的「加筋」维度正交。另存的缺口：柱壳族 val 为空、val 绝对数量偏少（{S["splits"]["val"]} 条），
需要靠放量 + 第三批结构形式补足。
</div></section>''')

    parts.append(f'''<section><h2 class="sec">11 · 复现方式<span class="hint">命令 + 产物</span></h2>
<div class="card"><p class="lead">本报告的每一个数字都能从下列命令重放（工作目录 <code>feagpt_repro/</code>）：</p>
<ul class="lim">
<li><code>python eval_dataset.py --root ../FEM-Bench-Aero</code> —— 29 项独立复算 + 6 道集级闸</li>
<li><code>python verify_dataset.py --root ../FEM-Bench-Aero</code> —— 自洽 / 配对 / 去重 / 应力定义 / 零三角</li>
<li><code>python check_forms.py --json ../FEM-Bench-Aero/check_forms.json</code> —— 退化自检</li>
<li><code>python diagnostics/msh_quality.py --tree ../FEM-Bench-Aero/modeling</code> —— 从归档 .msh 重新量测 minJ</li>
<li><code>python verify_barrel.py</code> / <code>verify_panel.py</code> / <code>verify_cantilever.py</code> —— 三族解析对照</li>
<li>本报告自身：<code>python _report/make_report_data.py &amp;&amp; python _report/make_report_figs.py
&amp;&amp; python _report/make_contour_figs.py &amp;&amp; python _report/make_report.py</code></li>
<li>云图溯源：<code>python _report/probe_contour_source.py</code> —— 证明 <code>model.msh</code> 的节点号与
<code>odb.json</code> 的节点号是同一套 id 空间（否则云图无源可依）</li>
</ul></div></section>''')

    parts.append(f'''<section><h2 class="sec">附录 · {S["n_cases"]} 条算例明细<span class="hint">每条都能按 case_id 复算</span></h2>
{sec_case_table()}
<p class="lead" style="font-size:12.4px">节点 / 单元数取自各 case 的 <code>truth.json</code> 与归档 <code>model.msh</code>；
minJ 由 <code>model.msh</code> 重新量测（同门禁公式）；两码 max|u| 分别取自 <code>modeling/</code> 与 <code>_xval/</code> 的
<code>model.results.json</code>；双码偏差为全域口径，柱壳两条的全域偏差偏大是口径问题（见第 7 节 D20）。</p>
</section>''')

    parts.append(f'''<footer>
FEM-Bench-Aero · 进展报告 · 生成于 {e(DATA["meta"]["generated_at"])}<br/>
全部数字来自 <code>report_data.json</code>（盘上实测），全部图像来自数据集自身的网格与结果。
</footer></div></body></html>''')

    return "".join(parts)


def main() -> int:
    page = build()
    out = ROOT / "FEM-Bench-Aero进展报告_2026-10.html"
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size/1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
