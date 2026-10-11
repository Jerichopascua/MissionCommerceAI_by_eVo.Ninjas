"""Serves the customer app and forwards only the customer-app part of PesoWeb's API, so a phone needs just this one address and port.

    python serve.py            (app on http://0.0.0.0:8090, PesoWeb expected on http://127.0.0.1:5071)
"""
import os
import sys
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
PESOWEB = "http://127.0.0.1:5071"
FORWARD = "/api/customer-app/"                       # nothing else of PesoWeb is reachable through here


class Handler(SimpleHTTPRequestHandler):
    def _forward(self):
        body = None
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            body = self.rfile.read(length)
        req = urllib.request.Request(PESOWEB + self.path, data=body, method=self.command)
        for h in ("Content-Type", "Authorization"):
            if self.headers.get(h):
                req.add_header(h, self.headers[h])
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                payload, status, ctype = r.read(), r.status, r.headers.get("Content-Type", "application/json")
        except urllib.error.HTTPError as e:
            payload, status, ctype = e.read(), e.code, "application/json"
        except Exception:
            payload, status, ctype = b'{"message":"The store system is not reachable."}', 502, "application/json"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path.startswith(FORWARD):
            return self._forward()
        super().do_GET()

    def do_POST(self):
        if self.path.startswith(FORWARD):
            return self._forward()
        self.send_error(404)

    def do_PUT(self):
        if self.path.startswith(FORWARD):
            return self._forward()
        self.send_error(404)

    def end_headers(self):
        if not self.path.startswith(FORWARD):
            self.send_header("Cache-Control", "no-cache")      # always the latest page and script
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent)
    print(f"Customer app on http://0.0.0.0:{PORT}  (store API from {PESOWEB})")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
