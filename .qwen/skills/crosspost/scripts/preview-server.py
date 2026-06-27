#!/usr/bin/env python3
"""Crosspost preview server: static files + POST /save write-back.

Serves <dir> and accepts POST /save (JSON body) -> writes <dir>/edits.json.
This is what makes the editable preview round-trip back to the agent without
the human copy-pasting: the page autosaves contenteditable edits to /save, the
agent reads edits.json.

Usage:
  preview-server.py <dir> [port]   # port 0 (default) => OS picks a free one
Binds 0.0.0.0 (home wifi + tailnet reachable). Prints the localhost URL.
"""
import sys, os, json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DIR = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 0


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=DIR, **k)

    def do_POST(self):
        if self.path.rstrip('/') == '/save':
            n = int(self.headers.get('Content-Length', 0))
            raw = self.rfile.read(n)
            try:
                json.loads(raw)  # validate; raise if garbage rather than save junk
                with open(os.path.join(DIR, 'edits.json'), 'wb') as f:
                    f.write(raw)
                self.send_response(200)
            except Exception:
                self.send_response(400)
            self.send_header('Content-Length', '0')
            self.end_headers()
        else:
            self.send_error(404)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def log_message(self, *a):
        pass


httpd = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
print(f"http://localhost:{httpd.server_address[1]}/preview.html", flush=True)
httpd.serve_forever()
