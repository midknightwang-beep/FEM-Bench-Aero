import re, io

SRC = r"C:\Users\22207\WorkBuddy\2026-07-14-12-15-00\飞机结构FEA数据集调研报告.html"
OUT = r"C:\Users\22207\WorkBuddy\2026-07-14-12-15-00\print_source.html"

html = open(SRC, encoding="utf-8").read()

# 1) Remove the sticky sidebar nav (useless on paper)
html = re.sub(r"<nav class=\"side\">.*?</nav>", "", html, flags=re.S)

# 2) Pre-render the comparison chart as static bars (no JS dependency)
scores = [("ALL-FEM", 3.0, "#1f5fd6"),
          ("FRAME", 3.5, "#0a8f6f"),
          ("FEM-Bench", 3.0, "#e08a1e"),
          ("StructuralEval", 3.0, "#9b59b6")]
bars = "".join(
    f'<div class="crow"><div class="lab">{n}</div>'
    f'<div class="bar" style="width:{v/5*100:.1f}%;background:{c}">'
    f'<span>{v:.1f} / 5</span></div></div>'
    for n, v, c in scores)
html = html.replace('<div class="chart" id="cmp"></div>',
                    f'<div class="chart" id="cmp">{bars}</div>')

# 3) Inject print CSS (landscape A4 so wide tables are fully covered) + force all panels visible
print_css = """
<style id="print-css">
@page { size: A4 landscape; margin: 10mm; }
@media print, screen {
  nav.side { display: none !important; }
  .wrap { display: block !important; min-height: 0 !important; }
  main { max-width: none !important; padding: 0 !important; }
  .tabs { display: none !important; }
  .panelbox { display: block !important; border: none !important; box-shadow: none !important; padding: 0 !important; margin: 10px 0 18px; }
  .panelbox + .panelbox { border-top: 2px dashed #cdd5e0 !important; padding-top: 12px !important; }
  table { font-size: 10.5px !important; box-shadow: none !important; }
  th, td { padding: 5px 7px !important; word-break: break-word !important; }
  .note, .warn { box-shadow: none !important; }
  section { margin-bottom: 16px !important; }
  header.hero { margin-bottom: 16px !important; }
}
</style>
"""
html = html.replace("</style>", print_css + "</style>", 1)

# 4) Drop the JS that only drives interactivity (harmless but cleaner for static render)
html = re.sub(r"<script>.*?</script>", "", html, flags=re.S)

open(OUT, "w", encoding="utf-8").write(html)
print("written", OUT, len(html), "bytes")
