"""app-api : shows the text after /api/ in big letters, centred on the screen.

The Ingress rewrites  www.id-581.com/api/<ข้อความ>  ->  /<ข้อความ>  before it reaches this app,
so this server only has to read its own path.
Python standard library only (runs on the stock python:3.12-alpine image).
"""
import html
import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote_to_bytes

PORT = int(os.environ.get("PORT", "8080"))
POD = socket.gethostname()

PAGE = """<!doctype html>
<html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
*{{box-sizing:border-box;margin:0}}
body{{min-height:100vh;display:flex;flex-direction:column;background:#0f172a;color:#f8fafc;
     font-family:"Sarabun","Noto Sans Thai",Tahoma,sans-serif}}
main{{flex:1;display:flex;align-items:center;justify-content:center;padding:24px;text-align:center}}
h1{{font-size:clamp(2.5rem,11vw,9rem);line-height:1.15;font-weight:800;word-break:break-word;
    background:linear-gradient(90deg,#38bdf8,#a78bfa);-webkit-background-clip:text;background-clip:text;color:transparent}}
.hint{{font-size:clamp(1.2rem,3vw,2rem);color:#94a3b8;line-height:1.8}}
.hint code{{color:#e2e8f0;background:#1e293b;padding:2px 10px;border-radius:6px}}
footer{{text-align:center;font-size:13px;color:#64748b;padding:12px}}
footer code{{color:#cbd5e1}}
</style></head>
<body><main>{body}</main>
<footer>served by <b>app-api</b> · pod <code>{pod}</code> · path <code>{path}</code></footer>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "app-api/1.0"

    def do_GET(self):
        if self.path == "/healthz":
            return self._send(200, "ok\n", "text/plain")

        raw_path = self.path.split("?", 1)[0]
        # The request line is read as latin-1; turn it back into bytes, then
        # percent-decode and read as UTF-8 so Thai text works whether nginx
        # forwards it encoded (%E0%B8...) or as raw bytes.
        text = unquote_to_bytes(raw_path.encode("latin-1")).decode("utf-8", "replace")
        message = text.lstrip("/")

        if message:
            body = f"<h1>{html.escape(message)}</h1>"
            title = message[:60]
        else:
            body = ('<div class="hint">พิมพ์ข้อความต่อท้าย URL เช่น<br>'
                    '<code>www.id-581.com/api/สวัสดี Kubernetes</code></div>')
            title = "app-api"
        page = PAGE.format(title=html.escape(title), body=body,
                           pod=html.escape(POD), path=html.escape(text))
        self._send(200, page, "text/html; charset=utf-8")

    def _send(self, code, text, ctype):
        data = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Served-By", POD)
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    print(f"app-api listening on :{PORT} (pod {POD})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
