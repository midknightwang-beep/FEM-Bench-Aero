# -*- coding: utf-8 -*-
"""Render a print-optimized HTML file to PDF via Edge DevTools Protocol.

Usage: edge_pdf.py <input_html> <output_pdf> [landscape|portrait]
Defaults: A4 page, landscape on.
"""
import subprocess, time, json, base64, os, sys, urllib.request
import websocket

PORT = 9222
HERE = os.path.dirname(os.path.abspath(__file__))

html_path = sys.argv[1] if len(sys.argv) > 1 else "print_source.html"
out_path = sys.argv[2] if len(sys.argv) > 2 else "report.pdf"
orient = (sys.argv[3] if len(sys.argv) > 3 else "landscape").lower()
landscape = (orient != "portrait")

URL = "file:///" + os.path.abspath(html_path).replace("\\", "/")
OUT = os.path.abspath(out_path)
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

proc = subprocess.Popen(
    [EDGE, "--headless=new", "--remote-debugging-port=%d" % PORT,
     "--remote-allow-origins=*", "--no-sandbox", "--disable-gpu", URL],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def cleanup():
    try: proc.terminate()
    except Exception: pass

try:
    ver = None
    for _ in range(60):
        try:
            ver = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json/version" % PORT, timeout=2))
            break
        except Exception:
            time.sleep(0.5)
    if not ver:
        raise SystemExit("Edge remote debugging did not start")

    targets = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json/list" % PORT, timeout=2))
    target = None
    for t in targets:
        if t.get("type") == "page" and URL in t.get("url", ""):
            target = t; break
    if not target and targets:
        target = targets[0]
    ws_url = target["webSocketDebuggerUrl"]

    ws = websocket.create_connection(ws_url, timeout=60)

    def send(method, params=None, id=1):
        ws.send(json.dumps({"id": id, "method": method, "params": params or {}}))

    send("Page.enable", id=1)
    time.sleep(1.5)  # let layout/fonts settle

    # A4: 297x210 mm = 11.69 x 8.27 in ; margins 10 mm = 0.394 in
    params = {
        "paperWidth": 11.69, "paperHeight": 8.27,
        "marginTop": 0.394, "marginBottom": 0.394,
        "marginLeft": 0.394, "marginRight": 0.394,
        "printBackground": True, "landscape": landscape,
        "preferCSSPageSize": False,
    }
    send("Page.printToPDF", params, id=2)

    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 2:
            if "error" in msg:
                raise SystemExit("printToPDF error: " + str(msg["error"]))
            data = base64.b64decode(msg["result"]["data"])
            with open(OUT, "wb") as f:
                f.write(data)
            print("PDF written:", OUT, len(data), "bytes")
            break
    ws.close()
finally:
    cleanup()
