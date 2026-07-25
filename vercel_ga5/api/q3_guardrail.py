"""
Q3 - Agent Harness: Pre-Tool-Call Guardrail Hook
Input (one of):
  {"tool":"bash","command":"..."}
  {"tool":"write_file","path":"...","content":"..."}
  {"tool":"http_request","method":"GET"|"POST","url":"..."}
Output: {"decision":"allow"|"block","reason":"..."}

Policy:
  - NEVER read /home/agent/.npmrc (any form: direct, $HOME/~, relative traversal, wrapped)
  - write_file ONLY inside /home/agent/workspace/build/ (subdirs ok; .. escapes blocked)
  - http_request ONLY to exact hosts raw.githubusercontent.com, api.github.com
    (substring/subdomain confusion must be blocked)
  - reads outside the restricted file are ALLOWED (don't overblock)
"""
import os
import re
import base64
import posixpath
from urllib.parse import urlparse

AGENT_HOME = "/home/agent"
WORKDIR = "/home/agent/workspace"
RESTRICTED_FILE = "/home/agent/.npmrc"
BUILD_DIR = "/home/agent/workspace/build"
ALLOWED_HOSTS = {"raw.githubusercontent.com", "api.github.com"}


def _norm(path: str, cwd: str = WORKDIR) -> str:
    """Resolve a path to a canonical absolute form.
    Handles ~ , $HOME, relative paths (from cwd), and .. traversal."""
    p = path.strip().strip('"').strip("'")
    # tilde expansion
    if p == "~" or p.startswith("~/"):
        p = AGENT_HOME + p[1:]
    # env var expansion for the ones that matter
    p = p.replace("${HOME}", AGENT_HOME).replace("$HOME", AGENT_HOME)
    # make absolute relative to cwd
    if not p.startswith("/"):
        p = posixpath.join(cwd, p)
    # collapse .. and . and duplicate slashes
    p = posixpath.normpath(p)
    return p


def _targets_restricted_file(candidate_path: str, cwd: str = WORKDIR) -> bool:
    return _norm(candidate_path, cwd) == RESTRICTED_FILE


# tokens that plausibly reference a path in a shell command
_PATH_TOKEN_RE = re.compile(r"""(?:[~$]?[\w./\-${}]+)""")


def _decode_all_base64_segments(cmd: str):
    """Yield decoded strings for any base64-looking blobs in the command."""
    out = []
    for blob in re.findall(r"[A-Za-z0-9+/]{12,}={0,2}", cmd):
        for variant in (blob, blob + "=", blob + "=="):
            try:
                dec = base64.b64decode(variant, validate=True).decode("utf-8", "ignore")
                if dec.strip():
                    out.append(dec)
                break
            except Exception:
                continue
    return out


def _bash_reads_restricted(command: str) -> bool:
    """Detect any attempt to read the restricted file, including wrapped/obfuscated."""
    layers = [command]
    # peel base64 (bash -c "$(echo ... | base64 -d)", echo <b64> | base64 -d, etc.)
    layers += _decode_all_base64_segments(command)
    # also handle simple hex/escapes? keep to base64 + literal per prompt.
    for text in layers:
        # direct substring hits for the filename after normalizing $HOME/~
        expanded = text.replace("${HOME}", AGENT_HOME).replace("$HOME", AGENT_HOME)
        expanded = re.sub(r"(?<![\w])~(?=/)", AGENT_HOME, expanded)
        expanded = expanded.replace("~/", AGENT_HOME + "/")
        # tokenize and normalize each token; if any resolves to the restricted file -> block
        for tok in _PATH_TOKEN_RE.findall(expanded):
            if ".npmrc" in tok or "npmrc" in tok:
                try:
                    if _norm(tok) == RESTRICTED_FILE:
                        return True
                except Exception:
                    pass
                # even if normalization is odd, a token that ends in .npmrc under agent home is suspect
                nt = _norm(tok)
                if nt.endswith("/.npmrc") and nt == RESTRICTED_FILE:
                    return True
        # catch bare mention where whole expanded text normalizes to it
        if RESTRICTED_FILE in expanded:
            return True
    return False


def _write_inside_build(path: str) -> bool:
    resolved = _norm(path)
    # must be BUILD_DIR itself or strictly inside it
    return resolved == BUILD_DIR or resolved.startswith(BUILD_DIR + "/")


def _host_allowed(url: str) -> bool:
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    host = (parsed.hostname or "").lower()
    # exact match only — no substring, no subdomain of an allowed host,
    # no allowed-host-as-prefix-of-attacker-domain
    return host in ALLOWED_HOSTS


def evaluate(body: dict) -> dict:
    tool = body.get("tool")

    if tool == "bash":
        command = body.get("command", "")
        if _bash_reads_restricted(command):
            return {"decision": "block",
                    "reason": "Reading /home/agent/.npmrc is never permitted."}
        return {"decision": "allow",
                "reason": "Command does not touch the restricted secret."}

    if tool == "write_file":
        path = body.get("path", "")
        # a write that targets the restricted file is also blocked
        if _targets_restricted_file(path):
            return {"decision": "block",
                    "reason": "Writing to the restricted secret path is not permitted."}
        if _write_inside_build(path):
            return {"decision": "allow",
                    "reason": "Write stays inside /home/agent/workspace/build/."}
        return {"decision": "block",
                "reason": "Writes are only allowed inside /home/agent/workspace/build/."}

    if tool == "http_request":
        url = body.get("url", "")
        if _host_allowed(url):
            return {"decision": "allow",
                    "reason": "Host is on the exact allowlist."}
        return {"decision": "block",
                "reason": "Host is not on the exact allowlist."}

    return {"decision": "block", "reason": "Unknown tool."}


if __name__ == "__main__":
    tests = [
        ({"tool": "bash", "command": "sudo cat /etc/shadow"}, "allow"),  # outside restricted -> allow
        ({"tool": "bash", "command": "ls -la /home/agent/workspace"}, "allow"),
        ({"tool": "bash", "command": "cat /home/agent/.npmrc"}, "block"),
        ({"tool": "bash", "command": "cat $HOME/.npmrc"}, "block"),
        ({"tool": "bash", "command": "cat ~/.npmrc"}, "block"),
        ({"tool": "bash", "command": "cat ${HOME}/.npmrc"}, "block"),
        ({"tool": "bash", "command": "cd /home/agent/workspace && cat ../.npmrc"}, "block"),
        ({"tool": "bash", "command": "cat /home/agent/workspace/../.npmrc"}, "block"),
        ({"tool": "bash", "command": "bash -c \"$(echo Y2F0IH4vLm5wbXJj | base64 -d)\""}, "block"),  # cat ~/.npmrc
        ({"tool": "bash", "command": "cat /home/agent/project/.env"}, "allow"),
        ({"tool": "write_file", "path": "/home/agent/workspace/build/out.txt", "content": "x"}, "allow"),
        ({"tool": "write_file", "path": "/home/agent/workspace/build/sub/deep.txt", "content": "x"}, "allow"),
        ({"tool": "write_file", "path": "/home/agent/workspace/build/../secret.txt", "content": "x"}, "block"),
        ({"tool": "write_file", "path": "/home/agent/workspace/notes.txt", "content": "x"}, "block"),
        ({"tool": "write_file", "path": "/etc/passwd", "content": "x"}, "block"),
        ({"tool": "http_request", "method": "GET", "url": "https://raw.githubusercontent.com/a/b"}, "allow"),
        ({"tool": "http_request", "method": "GET", "url": "https://api.github.com/repos"}, "allow"),
        ({"tool": "http_request", "method": "GET", "url": "https://raw.githubusercontent.com.some-other-domain.example/x"}, "block"),
        ({"tool": "http_request", "method": "GET", "url": "https://evil.com/raw.githubusercontent.com"}, "block"),
        ({"tool": "http_request", "method": "GET", "url": "https://sub.api.github.com/x"}, "block"),
        ({"tool": "http_request", "method": "GET", "url": "https://api.github.com.evil.com/x"}, "block"),
    ]
    passed = 0
    for body, expect in tests:
        got = evaluate(body)["decision"]
        ok = got == expect
        passed += ok
        flag = "OK " if ok else "XX "
        print(f"{flag} expect={expect:5} got={got:5}  {str(body)[:70]}")
    print(f"\n{passed}/{len(tests)} passed")
