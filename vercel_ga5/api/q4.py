from http.server import BaseHTTPRequestHandler
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from q4_scanner import scan


class handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            self._send(200, {"categories": scan(body.get("skill", ""))})
        except Exception as e:
            self._send(200, {"categories": [], "error": str(e)})

    def do_GET(self):
        self._send(200, {"ok": True, "endpoint": "q4 scanner"})
