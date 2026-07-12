#!/usr/bin/env python3
"""review_server_round3 — sibling of review_server.py (NOT a modification of it, since that
server is the shared :8899 dashboard other agents/the user may have open right now — restarting
it to add a route would be disruptive). Serves the SAME gen12/ directory (so review-round3.html's
iframes to assets-<skin>/player.html work identically) plus a dedicated POST /save-round3 that
persists to review-round3-decisions.json (human-labeled-data — never silently drops a write).
Usage: python3 review_server_round3.py [port]   (default 0 = OS picks a free port)
"""
import http.server, socketserver, os, sys, json, time

DIR = os.path.dirname(os.path.abspath(__file__))
DECISIONS = os.path.join(DIR, "review-round3-decisions.json")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 0


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=DIR, **k)

    def do_POST(self):
        if self.path == "/save-round3":
            try:
                n = int(self.headers.get("Content-Length", 0))
                data = self.rfile.read(n)
                parsed = json.loads(data or b"{}")               # validate — never write garbage
                # human-labeled-data-rule: rolling .bak, never a bare silent overwrite of real verdicts
                if os.path.exists(DECISIONS):
                    bak = DECISIONS + f".bak-{time.strftime('%Y%m%dT%H%M%S')}"
                    try:
                        os.replace(DECISIONS, bak)
                    except OSError:
                        pass
                open(DECISIONS, "w").write(json.dumps(parsed, indent=2))
                self.send_response(200); self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers(); self.wfile.write(b"ok")
            except Exception as e:
                self.send_response(400); self.end_headers(); self.wfile.write(str(e).encode())
        else:
            self.send_response(404); self.end_headers()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a): pass


class ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


with ThreadingServer(("0.0.0.0", PORT), H) as httpd:
    port = httpd.server_address[1]
    url = f"http://localhost:{port}/review-round3.html"
    open(os.path.join(DIR, ".review-round3-url"), "w").write(url)
    print(f"[review-server-round3] {url}\n[review-server-round3] decisions → {DECISIONS}", flush=True)
    httpd.serve_forever()
