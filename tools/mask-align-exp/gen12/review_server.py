#!/usr/bin/env python3
"""review_server — serves the gen12 dashboard + live players AND persists human review verdicts.
The dashboard POSTs {id:{gate,notes}} to /save on every change; we write it to gen12/review.json,
which the agent can read on demand ("pull the review data"). Static-serves everything else.
Usage: python3 review_server.py [port]   (default 0 = OS picks a free port; prints the URL)
"""
import http.server, socketserver, os, sys, json

DIR = os.path.dirname(os.path.abspath(__file__))
REVIEW = os.path.join(DIR, "review.json")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 0


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=DIR, **k)

    def do_POST(self):
        if self.path == "/save":
            try:
                n = int(self.headers.get("Content-Length", 0))
                data = self.rfile.read(n)
                json.loads(data or b"{}")                      # validate
                open(REVIEW, "wb").write(data)
                self.send_response(200); self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers(); self.wfile.write(b"ok")
            except Exception as e:
                self.send_response(400); self.end_headers(); self.wfile.write(str(e).encode())
        else:
            self.send_response(404); self.end_headers()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")          # never serve stale players/assets
        super().end_headers()

    def log_message(self, *a): pass


socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("0.0.0.0", PORT), H) as httpd:
    port = httpd.server_address[1]
    url = f"http://localhost:{port}/dashboard12.html"
    open(os.path.join(DIR, ".review-url"), "w").write(url)
    print(f"[review-server] {url}\n[review-server] verdicts → {REVIEW}", flush=True)
    httpd.serve_forever()
