"""Serves the customer app and forwards only the price feed to PesoWeb, so a phone needs just this one address and port.

    python serve.py            (app on http://0.0.0.0:8090, PesoWeb expected on http://127.0.0.1:5071)
"""
import sys
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
PESOWEB = "http://127.0.0.1:5071"
FORWARD = "/api/customer-app/"                       # nothing else of PesoWeb is reachable through here


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith(FORWARD):
            try:
                with urllib.request.urlopen(PESOWEB + self.path, timeout=15) as r:
                    body = r.read()
                    self.send_response(r.status)
                    self.send_header("Content-Type", r.headers.get("Content-Type", "application/json"))
            except urllib.error.HTTPError as e:
                body = e.read()
                self.send_response(e.code)
                self.send_header("Content-Type", "application/json")
            except Exception:
                body = b'{"message":"The store system is not reachable."}'
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def end_headers(self):
        if not self.path.startswith(FORWARD):
            self.send_header("Cache-Control", "no-cache")      # always the latest page and script
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).resolve().parent)
    print(f"Customer app on http://0.0.0.0:{PORT}  (price feed from {PESOWEB})")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
