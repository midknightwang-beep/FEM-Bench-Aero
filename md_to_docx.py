# -*- coding: utf-8 -*-
import re
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

SRC = r"C:\Users\22207\WorkBuddy\2026-07-14-12-15-00\飞机结构FEA数据集调研报告.md"
OUT = r"C:\Users\22207\WorkBuddy\2026-07-14-12-15-00\飞机结构FEA数据集调研报告.docx"

CJK = "Microsoft YaHei"
BASE = "1F2733"

doc = Document()

sec = doc.sections[0]
sec.page_height = Inches(11.69)
sec.page_width = Inches(8.27)
sec.left_margin = Inches(0.9)
sec.right_margin = Inches(0.9)
sec.top_margin = Inches(0.85)
sec.bottom_margin = Inches(0.85)

normal = doc.styles["Normal"]
normal.font.name = CJK
normal.font.size = Pt(10.5)
_rpr = normal._element.get_or_add_rPr()
_rfonts = _rpr.get_or_add_rFonts()
_rfonts.set(qn("w:eastAsia"), CJK)

def set_cjk(run, size=10.5, color=BASE, bold=False, italic=False):
    run.font.name = CJK
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    run.bold = bold
    run.italic = italic
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    rFonts.set(qn("w:eastAsia"), CJK)

def shade_border(par, fill="EEF3FB", border="1F5FD6"):
    pPr = par._p.get_or_add_pPr()
    shd = OxmlElement("w:shd"); shd.set(qn("w:val"),"clear"); shd.set(qn("w:color"),"auto"); shd.set(qn("w:fill"),fill)
    pPr.append(shd)
    pBdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left"); left.set(qn("w:val"),"single"); left.set(qn("w:sz"),"18"); left.set(qn("w:space"),"6"); left.set(qn("w:color"),border)
    pBdr.append(left); pPr.append(pBdr)

def add_runs(par, text):
    pattern = re.compile(r"(\*\*.+?\*\*|`.+?`)")
    for part in pattern.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            r = par.add_run(part[2:-2]); r.bold = True; set_cjk(r)
        elif part.startswith("`") and part.endswith("`"):
            r = par.add_run(part[1:-1]); r.font.name = "Consolas"; set_cjk(r)
        else:
            segs = part.split("\n")
            for i, s in enumerate(segs):
                if i > 0:
                    par.add_run().add_break()
                r = par.add_run(s); set_cjk(r)

def add_heading(text, level):
    h = doc.add_heading(level=level)
    r = h.add_run(text)
    set_cjk(r, size=16 if level == 0 else (14 if level == 1 else (12 if level == 2 else 11)),
            color="16324F" if level else "1F5FD6", bold=True)
    return h

def is_table_row(line):
    s = line.strip()
    return s.startswith("|") and s.endswith("|")

def parse_table(rows):
    data = []
    for i, row in enumerate(rows):
        if i == 1 and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", row):
            continue
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        data.append(cells)
    return data

def add_table(data):
    if not data:
        return
    t = doc.add_table(rows=0, cols=len(data[0]))
    t.style = "Table Grid"
    for ri, row in enumerate(data):
        cells = t.add_row().cells
        for ci, val in enumerate(row):
            cells[ci].text = ""
            p = cells[ci].paragraphs[0]
            add_runs(p, val)
            for r in p.runs:
                set_cjk(r, size=9.5)
            if ri == 0:
                tcPr = cells[ci]._tc.get_or_add_tcPr()
                shd = OxmlElement("w:shd"); shd.set(qn("w:val"),"clear"); shd.set(qn("w:color"),"auto"); shd.set(qn("w:fill"),"DCE6F5")
                tcPr.append(shd)
                for r in p.runs:
                    r.bold = True

lines = open(SRC, encoding="utf-8").read().splitlines()
i = 0
n = len(lines)

while i < n:
    line = lines[i]
    s = line.strip()
    if s == "":
        i += 1; continue
    if line.startswith("# "):
        add_heading(s[2:], 0); i += 1; continue
    if line.startswith("## "):
        add_heading(s[3:], 1); i += 1; continue
    if line.startswith("### "):
        add_heading(s[4:], 2); i += 1; continue
    if line.startswith("#### "):
        add_heading(s[5:], 3); i += 1; continue
    if re.match(r"^-{3,}$|^\*{3,}$", s):
        doc.add_paragraph(); i += 1; continue
    if line.lstrip().startswith(">"):
        buf = []
        while i < n and lines[i].lstrip().startswith(">"):
            buf.append(lines[i].lstrip()[1:].lstrip()); i += 1
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.15)
        p.paragraph_format.space_after = Pt(6)
        add_runs(p, "\n".join(buf))
        shade_border(p)
        continue
    if is_table_row(line):
        buf = []
        while i < n and is_table_row(lines[i]):
            buf.append(lines[i]); i += 1
        add_table(parse_table(buf))
        continue
    if re.match(r"^\d+\.\s", line):
        buf = []
        while i < n and re.match(r"^\d+\.\s", lines[i]):
            buf.append(re.sub(r"^\d+\.\s", "", lines[i])); i += 1
        for item in buf:
            p = doc.add_paragraph(style="List Number")
            add_runs(p, item)
        continue
    if re.match(r"^[-*]\s", line):
        buf = []
        while i < n and re.match(r"^[-*]\s", lines[i]):
            buf.append(re.sub(r"^[-*]\s", "", lines[i])); i += 1
        for item in buf:
            p = doc.add_paragraph(style="List Bullet")
            add_runs(p, item)
        continue
    # catch-all paragraph
    buf = [line]
    j = i + 1
    while (j < n and lines[j].strip() != ""
           and not lines[j].startswith(("#", "|", ">"))
           and not re.match(r"^\d+\.\s", lines[j])
           and not re.match(r"^[-*]\s", lines[j])):
        buf.append(lines[j]); j += 1
    txt = " ".join(x.strip() for x in buf)
    p = doc.add_paragraph()
    add_runs(p, txt)
    i = j
    continue

doc.save(OUT)
print("written", OUT)
