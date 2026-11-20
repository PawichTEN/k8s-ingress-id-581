"""app-research : shows the seminar research summary, and an edit page to save it back.

Routes (paths as seen by this app, after the Ingress rewrite):
  GET  /            -> view the summary      (www.id-581.com/research)
  GET  /edit        -> edit form             (admin.id-581.com/  -> rewritten to /edit)
  POST /edit        -> save, then redirect   (form on admin.id-581.com posts to /)
  GET  /raw         -> plain text of the summary
  GET  /healthz     -> health check

The summary is stored in DATA_FILE on a PersistentVolume, so it survives Pod restarts.
On first start the file is copied from SEED_FILE (a ConfigMap).
Python standard library only (runs on the stock python:3.12-alpine image).
"""
import html
import os
import shutil
import socket
import tempfile
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

PORT = int(os.environ.get("PORT", "8080"))
DATA_FILE = os.environ.get("DATA_FILE", "/data/research.md")
SEED_FILE = os.environ.get("SEED_FILE", "/seed/research.md")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://www.id-581.com/research")
MAX_BYTES = 200_000
POD = socket.gethostname()
BKK = timezone(timedelta(hours=7))

CSS = """
*{box-sizing:border-box;margin:0}
body{font-family:"Sarabun","Noto Sans Thai",Tahoma,sans-serif;background:#eef2f7;color:#1f2933;min-height:100vh;display:flex;flex-direction:column}
nav{background:#1f4e79;padding:12px 24px;display:flex;gap:20px;flex-wrap:wrap}
nav a{color:#fff;text-decoration:none;font-size:15px}
nav.admin{background:#9a3412}
main{flex:1;width:100%;max-width:860px;margin:28px auto;padding:0 16px}
article,.box{background:#fff;border-radius:14px;box-shadow:0 4px 18px rgba(31,78,121,.12);padding:34px 40px}
h1{font-size:26px;color:#1f4e79;margin-bottom:6px;line-height:1.4}
h2{font-size:20px;color:#2e5aac;margin:22px 0 6px}
p{font-size:17px;line-height:1.85;margin:10px 0;text-indent:2em}
ul{margin:8px 0 8px 2em;line-height:1.8}
.meta{font-size:13px;color:#7b8794;margin-bottom:14px}
textarea{width:100%;min-height:460px;font:15px/1.7 "Sarabun",Tahoma,sans-serif;padding:14px;border:1px solid #bcccdc;border-radius:10px}
button{margin-top:14px;background:#9a3412;color:#fff;border:0;border-radius:8px;padding:11px 28px;font-size:16px;cursor:pointer}
.ok{background:#ebfbee;color:#2b8a3e;border:1px solid #8ce99a;border-radius:8px;padding:10px 14px;margin-bottom:14px}
.tip{font-size:13px;color:#52606d;margin-top:10px;line-height:1.7}
footer{text-align:center;font-size:12px;color:#7b8794;padding:12px}
code{background:#f1f3f5;padding:1px 6px;border-radius:4px}
"""


def ensure_data():
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    if not os.path.exists(DATA_FILE):
        if os.path.exists(SEED_FILE):
            shutil.copyfile(SEED_FILE, DATA_FILE)
        else:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                f.write("# สรุปงานวิจัย\n\n(ยังไม่มีเนื้อหา)\n")


def read_text():
    ensure_data()
    with open(DATA_FILE, encoding="utf-8") as f:
        return f.read()


def write_text(text):
    # write to a temp file then rename, so a crash never leaves a half-written file
    d = os.path.dirname(DATA_FILE)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".research-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text.replace("\r\n", "\n"))
    os.replace(tmp, DATA_FILE)


def updated_at():
    t = datetime.fromtimestamp(os.path.getmtime(DATA_FILE), BKK)
    return t.strftime("%d/%m/%Y %H:%M:%S (UTC+7)")


def render(text):
    """Very small markdown subset: '# ', '## ', '- ' and blank-line paragraphs."""
    out, para, items = [], [], []

    def flush():
        if para:
            out.append("<p>" + html.escape(" ".join(para)) + "</p>")
            para.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{html.escape(i)}</li>" for i in items) + "</ul>")
            items.clear()

    for line in text.splitlines():
        s = line.strip()
        if not s:
            flush()
        elif s.startswith("## "):
            flush(); out.append(f"<h2>{html.escape(s[3:])}</h2>")
        elif s.startswith("# "):
            flush(); out.append(f"<h1>{html.escape(s[2:])}</h1>")
        elif s.startswith("- "):
            if para:
                flush()
            items.append(s[2:])
        else:
            if items:
                flush()
            para.append(s)
    flush()
    return "\n".join(out)


def count_words(text):
    """Rough word count. Thai has no spaces, so count Thai words as ~ chars/6."""
    body = "\n".join(l for l in text.splitlines() if not l.startswith("#"))
    thai = sum(1 for c in body if "฀" <= c <= "๿")
    latin = len([w for w in body.split() if any(c.isascii() and c.isalnum() for c in w)])
    return latin + round(thai / 6)


def page(title, nav, content):
    return f"""<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>
<style>{CSS}</style></head><body>{nav}<main>{content}</main>
<footer>served by <b>app-research</b> · pod <code>{html.escape(POD)}</code> · data <code>{html.escape(DATA_FILE)}</code></footer>
</body></html>"""


NAV_WWW = ('<nav><a href="/">Home</a><a href="/about">About</a><a href="/research">Research</a>'
           '<a href="/api/สวัสดี Kubernetes">API</a></nav>')
NAV_ADMIN = (f'<nav class="admin"><a href="/">admin.id-581.com · แก้ไขสรุปงานวิจัย</a>'
             f'<a href="{PUBLIC_URL}">ดูหน้า www.id-581.com/research →</a></nav>')


class Handler(BaseHTTPRequestHandler):
    server_version = "app-research/1.0"

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/healthz":
            return self._send(200, "ok\n", "text/plain")
        if path == "/raw":
            return self._send(200, read_text(), "text/plain; charset=utf-8")
        if path.startswith("/edit"):
            return self._edit(saved="saved=1" in query)
        if path in ("/", ""):
            text = read_text()
            body = (f'<article><div class="meta">ปรับปรุงล่าสุด {updated_at()} · '
                    f'ประมาณ {count_words(text)} คำ</div>{render(text)}</article>')
            return self._send(200, page("Research · id-581", NAV_WWW, body), "text/html; charset=utf-8")
        self._send(404, page("404", NAV_WWW, '<div class="box"><h1>404 Not Found</h1></div>'),
                   "text/html; charset=utf-8")

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if not path.startswith("/edit"):
            return self._send(405, "method not allowed\n", "text/plain")
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BYTES:
            return self._send(413, "too large\n", "text/plain")
        form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        text = form.get("content", [""])[0]
        if not text.strip():
            return self._send(400, "content is empty\n", "text/plain")
        write_text(text)
        print(f"saved {len(text)} chars to {DATA_FILE}", flush=True)
        # Redirect back to the admin home; the Ingress rewrites "/" to "/edit" again.
        self.send_response(303)
        self.send_header("Location", "/?saved=1")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _edit(self, saved):
        text = read_text()
        msg = '<div class="ok">✔ บันทึกเรียบร้อยแล้ว</div>' if saved else ""
        body = f"""<div class="box">{msg}
<h1>แก้ไขสรุปงานวิจัย</h1>
<div class="meta">ปรับปรุงล่าสุด {updated_at()} · ประมาณ {count_words(text)} คำ (เป้าหมาย 300–500 คำ)</div>
<form method="post" action="/">
<textarea name="content">{html.escape(text)}</textarea>
<button type="submit">บันทึก (Save)</button>
</form>
<div class="tip">รูปแบบ: บรรทัดที่ขึ้นต้นด้วย <code># </code> = หัวเรื่อง, <code>## </code> = หัวข้อย่อย,
<code>- </code> = รายการ, เว้นบรรทัดว่าง = ขึ้นย่อหน้าใหม่<br>
ไฟล์ถูกเก็บบน PersistentVolume จึงไม่หายเมื่อ Pod ถูกสร้างใหม่</div></div>"""
        self._send(200, page("Admin · id-581", NAV_ADMIN, body), "text/html; charset=utf-8")

    def _send(self, code, text, ctype):
        data = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Served-By", POD)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    ensure_data()
    print(f"app-research listening on :{PORT} (pod {POD}, data {DATA_FILE})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
