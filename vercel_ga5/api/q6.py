from http.server import BaseHTTPRequestHandler
import json, hashlib, uuid

NORMALIZED_EMAIL = "22f1001328@ds.study.iitm.ac.in".strip().lower()
PROTOCOL_VERSION = "2024-11-05"
SESSION_ID = uuid.uuid4().hex

TOOL_DEF = {
    "name": "solve_challenge",
    "description": "Returns first 16 hex chars of SHA-256(challenge:email), reading "
                   "the challenge from the X-Exam-Challenge request header.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}


def _solve(challenge: str) -> str:
    return hashlib.sha256(f"{challenge}:{NORMALIZED_EMAIL}".encode()).hexdigest()[:16]


def _result(rid, result): return {"jsonrpc": "2.0", "id": rid, "result": result}
def _error(rid, code, msg): return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": msg}}


class handler(BaseHTTPRequestHandler):
    def _send(self, code, obj=None, raw=None, ctype="application/json"):
        if raw is not None:
            body = raw.encode()
        else:
            body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Mcp-Session-Id", SESSION_ID)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        # some clients probe with GET; return 200 empty
        self.send_response(200)
        self.send_header("Mcp-Session-Id", SESSION_ID)
        self.end_headers()

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send(200, _error(None, -32700, "Parse error"))

        messages = payload if isinstance(payload, list) else [payload]
        responses = []

        for msg in messages:
            method = msg.get("method")
            rid = msg.get("id")

            if method and method.startswith("notifications/"):
                continue

            if method == "initialize":
                responses.append(_result(rid, {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "tds-ga5-solver", "version": "1.0.0"},
                }))
            elif method == "tools/list":
                responses.append(_result(rid, {"tools": [TOOL_DEF]}))
            elif method == "tools/call":
                params = msg.get("params", {}) or {}
                if params.get("name") != "solve_challenge":
                    responses.append(_error(rid, -32602, f"Unknown tool: {params.get('name')}"))
                    continue
                challenge = self.headers.get("x-exam-challenge", "") or self.headers.get("X-Exam-Challenge", "")
                text = _solve(challenge)
                responses.append(_result(rid, {
                    "content": [{"type": "text", "text": text}],
                    "isError": False,
                }))
            elif method == "ping":
                responses.append(_result(rid, {}))
            else:
                if rid is not None:
                    responses.append(_error(rid, -32601, f"Method not found: {method}"))

        if not responses:
            # only notifications -> 202 accepted
            self.send_response(202)
            self.send_header("Mcp-Session-Id", SESSION_ID)
            self.end_headers()
            return

        body = responses[0] if len(responses) == 1 else responses
        accept = self.headers.get("accept", "") or self.headers.get("Accept", "")
        if "text/event-stream" in accept and "application/json" not in accept:
            sse = f"event: message\ndata: {json.dumps(body)}\n\n"
            return self._send(200, raw=sse, ctype="text/event-stream")
        return self._send(200, obj=body)
