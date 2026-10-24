# -*- coding: utf-8 -*-
"""Markdown -> styled HTML for the technical design report (business-modern theme)."""
import re
from pathlib import Path

ROOT = Path(__file__).parent
MD = ROOT.parent / "stage1" / "final_draft.md"
SKELETON = Path("F:/AI FEA Modeling DataSets/output/20261017-fembench-delivery/stage2/formatted-FEM-Bench-Aero项目执行交付文档.html")
OUT = ROOT / "formatted-技术框架设计报告.html"

src = MD.read_text(encoding="utf-8").splitlines()

# ---- split head from body
skel = SKELETON.read_text(encoding="utf-8")
head = skel.split("</head>")[0] + "</head>\n"
extra_css = """
  .figure-slot { text-align: center; text-indent: 0; margin: var(--spacing-block) 0 0 0; }
  .fig-cap {
    text-align: center; text-indent: 0;
    font-size: var(--fs-small); color: var(--color-muted);
    margin: var(--spacing-cap, 0.3em) 0 var(--spacing-block);
  }
  table.data caption { text-align: left; }
  .lead { font-weight: 600; color: var(--color-heading); }
"""
head = head.replace("</style>", extra_css + "  </style>")

def inline(s: str) -> str:
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<span style=\"font-family:Consolas,monospace\">\1</span>", s)
    return s

# ---- parse markdown body (skip cover block: lines until first '## 一、')
start = next(i for i, l in enumerate(src) if l.startswith("## 一、"))
lines = src[start:]

chapters = []   # (title, id, [(sub_title, sub_id)])
cur = None
html_body = []
chapter_no = 0
table_no = 0
in_table = False
table_rows = []
in_list = None   # 'ul' | 'ol'
in_section = False
prev_appendix = False

def close_table():
    global in_table, table_rows, table_no
    if not in_table:
        return []
    out = []
    rows = table_rows
    header = rows[0]
    body = rows[1:]
    out.append("<table class=\"data\">")
    out.append(f"<caption>表 {chapter_no}-{table_no}　{header[0]}</caption>")
    out.append("<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr></thead>")
    out.append("<tbody>")
    for r in body:
        cells = "".join(f"<td>{inline(c)}</td>" for c in r)
        out.append(f"<tr>{cells}</tr>")
    out.append("</tbody></table>")
    in_table = False
    table_rows = []
    return out

def close_list():
    global in_list
    if in_list:
        out = f"</{in_list}>"
        in_list = None
        return [out]
    return []

for raw in lines:
    line = raw.rstrip()
    if not line.strip():
        html_body += close_table() + close_list()
        continue
    if line.strip() == "---":
        html_body += close_table() + close_list()
        continue

    # table row
    if line.lstrip().startswith("|"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            continue
        if not in_table:
            html_body += close_list()
            in_table = True
            table_no += 1
            table_rows = [cells]
        else:
            table_rows.append(cells)
        continue

    html_body += close_table()

    # h1 chapter
    if line.startswith("## "):
        html_body += close_list()
        is_appendix = line[3:].strip().startswith("附录")
        if in_section and not (is_appendix and prev_appendix) and chapter_no > 0:
            html_body.append("</section>")
        chapter_no += 1
        title = line[3:].strip()
        cid = f"section-{chapter_no}"
        if not (is_appendix and prev_appendix) and chapter_no > 0:
            html_body.append("<section>")
        prev_appendix = is_appendix
        html_body.append(f"<h1 class=\"chapter\" id=\"{cid}\">{inline(title)}</h1>")
        cur = {"title": title, "id": cid, "subs": []}
        chapters.append(cur)
        in_section = True
        table_no = 0
        continue

    # h2
    if line.startswith("### "):
        html_body += close_list()
        title = line[4:].strip()
        sid = f"{cur['id']}-{len(cur['subs']) + 1}"
        html_body.append(f"<h2 class=\"sub\" id=\"{sid}\">{inline(title)}</h2>")
        cur["subs"].append((title, sid))
        continue

    # figure marker
    m = re.fullmatch(r"〖FIG:([a-z_0-9]+)〗", line.strip())
    if m:
        html_body += close_list()
        html_body.append(f"<p class=\"figure-slot\">〖FIG:{m.group(1)}〗</p>")
        continue

    # figure caption
    if line.startswith("图 "):
        html_body.append(f"<p class=\"fig-cap\">{inline(line.strip())}</p>")
        continue

    # lists
    if line.startswith("- "):
        if in_list != "ul":
            html_body += close_list()
            html_body.append("<ul>")
            in_list = "ul"
        html_body.append(f"<li>{inline(line[2:].strip())}</li>")
        continue
    if re.match(r"^\d+\.\s", line.strip()):
        if in_list != "ol":
            html_body += close_list()
            html_body.append("<ol>")
            in_list = "ol"
        html_body.append(f"<li>{inline(re.sub(r'^\d+\.\s', '', line.strip()))}</li>")
        continue

    # paragraph
    html_body += close_list()
    html_body.append(f"<p>{inline(line.strip())}</p>")

html_body += close_table() + close_list()
if in_section:
    html_body.append("</section>")

# ---- build TOC
toc = ['<ol class="toc-list">']
for c in chapters:
    toc.append(f'<li><a href="#{c["id"]}">{inline(c["title"])}</a>')
    if c["subs"]:
        toc.append("<ol>")
        for t, sid in c["subs"]:
            toc.append(f'<li><a href="#{sid}">{inline(t)}</a></li>')
        toc.append("</ol>")
    toc.append("</li>")
toc.append("</ol>")

summary = """
  <section>
    <h1 class="chapter" id="section-0">摘要</h1>
    <div class="executive-summary">
      <p>核心结论</p>
      <p>本报告给出"基于大模型的交互式飞机有限元模型智能生成技术"的框架设计。框架以有限元分析契约（FEASpec）为唯一真相源，把工程口语收敛为受约束的结构化输入；以独立验证层（九道闸）判断模型是否可信，不依赖生成模型自评；以双求解器同构互证建立结果可信度，以契约哈希与回归基线保证可复现。</p>
    </div>
    <p>报告依次回答四个问题：为什么需要（需求背景与四个结构性矛盾）、别人做到哪一步（三代技术谱系与三条主流路线的能力边界）、我们怎么想（三条设计原则与四处关键取舍）、具体怎么做（六层架构、层间接口、七个模块方案与端到端时序）。能力边界在文中显式声明，边界外请求一律拒绝并说明原因。</p>
"""

cover = """
  <section role="cover">
    <div class="cover-body-pad"></div>
    <p class="cover-category">技术框架设计报告</p>
    <p class="cover-title">基于大模型的交互式飞机有限元模型<br>智能生成技术</p>
    <p class="cover-subtitle">需求背景 · 现状调研 · 设计思路 · 总体设计 · 具体方案</p>
    <p class="cover-meta">技术设计文档 ｜ 2026 年 10 月 ｜ 版本 V1.0</p>
  </section>

  <section role="cover">
    <nav class="doc-toc" aria-label="文档目录">
      <p class="toc-title">目 录</p>
      <ol class="toc-list"><li><a href="#section-0">摘要</a></li>%s
    </nav>
  </section>
""" % ("\n      ".join(toc)[len('<ol class="toc-list">'):])

doc = head + "<body>\n" + cover + summary + "\n".join(html_body) + "\n</body>\n</html>\n"
OUT.write_text(doc, encoding="utf-8")
print("written:", OUT, "chars:", len(doc))
print("chapters:", len(chapters), "figures:", doc.count("〖FIG:"), "tables:", doc.count("<table"))
