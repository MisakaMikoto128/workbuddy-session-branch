#!/usr/bin/env python3
"""用浏览器直测前端的 HTTP 模式：复用 app.Api 的真实后端逻辑。

启动后浏览器/Playwright 访问 http://127.0.0.1:PORT 即为真实后端，无需 mock。
前端 index.html 不改动；服务在返回页面时注入一段兼容 window.pywebview.api 的 shim。
"""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from app import Api, web_dir

API = Api()
METHODS = {"version", "list_sessions", "list_messages", "preview_branch", "do_branch"}

SHIM = """<script>
(function () {
  const methods = %(methods)s;
  const api = {};
  methods.forEach(function (name) {
    api[name] = function () {
      const args = Array.prototype.slice.call(arguments);
      return fetch('/api/' + name, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({args: args})
      }).then(function (r) { return r.json(); });
    };
  });
  window.pywebview = {api: api};
  setTimeout(function () {
    window.dispatchEvent(new Event('pywebviewready'));
  }, 60);
})();
</script>""" % {"methods": json.dumps(sorted(METHODS))}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[serve] " + (fmt % args) + "\n")

    def _send(self, code, body, ctype):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            html = (web_dir() / "index.html").read_text(encoding="utf-8")
            html = html.replace("</body>", SHIM + "\n</body>")
            self._send(200, html, "text/html; charset=utf-8")
        elif path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
        else:
            self._send(404, "not found", "text/plain; charset=utf-8")

    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            self._send(404, "not found", "text/plain; charset=utf-8")
            return
        name = path[len("/api/"):]
        if name not in METHODS:
            self._send(400, json.dumps({"ok": False, "error": "unknown api: " + name}), "application/json; charset=utf-8")
            return
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        args = body.get("args", [])
        try:
            result = getattr(API, name)(*args)
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        self._send(200, json.dumps(result, ensure_ascii=False), "application/json; charset=utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8777)
    a = p.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"serving on http://127.0.0.1:{a.port}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
