"""Simulate Vercel's invocation of each api/*.py handler via a fake socket."""
import sys, json, io
sys.path.insert(0, "api")

import q2, q3, q4, q5


class FakeRequest:
    """Minimal stand-in for the handler's rfile/wfile/headers."""
    def __init__(self, body: bytes):
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.headers = {"Content-Length": str(len(body))}
        self._status = None

    # BaseHTTPRequestHandler methods the handler calls:
    def send_response(self, code): self._status = code
    def send_header(self, *a): pass
    def end_headers(self): pass


def invoke(module, body_obj):
    body = json.dumps(body_obj).encode()
    h = module.handler.__new__(module.handler)   # bypass __init__ (no real socket)
    fr = FakeRequest(body)
    h.rfile = fr.rfile
    h.wfile = fr.wfile
    h.headers = fr.headers
    h.send_response = fr.send_response
    h.send_header = fr.send_header
    h.end_headers = fr.end_headers
    h.do_POST()
    status = fr._status
    out = fr.wfile.getvalue().decode()
    return status, json.loads(out)


# Q2
s, r = invoke(q2, {"old_price":19,"new_price":49,"days_remaining":16,"days_in_actual_month":29,"spec":"v2"})
print("Q2", s, r, "OK" if abs(r["charge"]-16.5517)<0.01 else "FAIL")

# Q3
s, r = invoke(q3, {"tool":"bash","command":"cat ~/.npmrc"})
print("Q3", s, r["decision"], "OK" if r["decision"]=="block" else "FAIL")
s, r = invoke(q3, {"tool":"http_request","method":"GET","url":"https://api.github.com.evil.com/x"})
print("Q3", s, r["decision"], "OK" if r["decision"]=="block" else "FAIL")

# Q4
s, r = invoke(q4, {"skill":"---\nname: x\nauthor: a\nversion: 1\nchangelog: c\npermissions:\n  filesystem: read/write limited to ./data\n---\nhi"})
print("Q4", s, r, "OK" if r["categories"]==[] else "FAIL")

# Q5
s, r = invoke(q5, {"budget_tokens":100000,"steps":[{"tool":"s","args":{"q":"c"},"tokens_used":1}]*3})
print("Q5", s, r["decision"], "OK" if r["decision"]=="halt" else "FAIL")
