"""Serveur de dev : sert site/ et fait suivre /api/* vers un backend (comme le rewrite Firebase Hosting).

    python3 dev/serve.py                      # API locale : uvicorn scene_api.main:app --port 8080
    API_URL=https://scene-api-....run.app python3 dev/serve.py   # ou le service Cloud Run déployé

Puis ouvrir http://localhost:5000/carte.html (ajouter ?mock=1 pour la maquette sans API).
"""

import os
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_URL = os.environ.get("API_URL", "http://localhost:8080").rstrip("/")
PORT = int(os.environ.get("PORT", "5000"))
SITE = Path(__file__).resolve().parent.parent / "site"


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if not self.path.startswith("/api/"):
            return super().do_GET()
        try:
            with urllib.request.urlopen(API_URL + self.path, timeout=120) as r:
                status, headers, body = r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            status, headers, body = e.code, e.headers, e.read()
        except OSError as e:
            self.send_error(502, f"API injoignable ({API_URL}) : {e}")
            return
        self.send_response(status)
        for k in ("Content-Type", "X-Bbox", "Retry-After"):
            if headers.get(k):
                self.send_header(k, headers[k])
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print(f"site/ sur http://localhost:{PORT}/carte.html, /api/* -> {API_URL}")
    ThreadingHTTPServer(("", PORT), partial(Handler, directory=str(SITE))).serve_forever()
