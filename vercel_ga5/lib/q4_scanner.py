import re


def _split_frontmatter(text):
    m = re.match(r"\s*---\s*\n(.*?)\n---\s*\n?(.*)", text, re.DOTALL)
    if m:
        return m.group(1), m.group(2)
    return "", text


def _detect_hardcoded_secret(text: str) -> bool:
    t = text
    strong_patterns = [
        r"\bAKIA[0-9A-Z]{16}\b", r"\bASIA[0-9A-Z]{16}\b",
        r"\bsk-[A-Za-z0-9]{20,}\b", r"\bsk-proj-[A-Za-z0-9_\-]{20,}\b",
        r"\bghp_[A-Za-z0-9]{20,}\b", r"\bgho_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b",
        r"\bAIza[0-9A-Za-z_\-]{30,}\b", r"\bya29\.[A-Za-z0-9_\-]{20,}\b",
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b",
        r"https://hooks\.slack\.com/services/[A-Za-z0-9/]+",
        r"https://discord(?:app)?\.com/api/webhooks/[0-9]+/[A-Za-z0-9_\-]+",
        r"https://[a-z0-9.\-]+\.webhook\.office\.com/[A-Za-z0-9/@\-]+",
        r"https://outlook\.office\.com/webhook/[A-Za-z0-9/@\-]+",
        r"\b[0-9a-f]{32}\b.*(?:api|key|secret|token)",
    ]
    for p in strong_patterns:
        if re.search(p, t, re.IGNORECASE):
            return True
    kv = re.findall(
        r"(?im)^\s*[\"']?(api[_-]?key|apikey|secret|secret[_-]?key|token|access[_-]?token|"
        r"password|passwd|pwd|access[_-]?key|private[_-]?key|webhook(?:[_-]?url)?|"
        r"auth[_-]?token|client[_-]?secret|bearer)[\"']?\s*[:=]\s*"
        r"[\"']?([^\s\"'\n#]{6,})[\"']?", t)
    for _key, val in kv:
        v = val.strip().strip("\"'")
        low = v.lower()
        if (v.startswith("${") or v.startswith("$") or v.startswith("<") or
                v.startswith("{{") or v.startswith("%")):
            continue
        if any(ph in low for ph in ("env", "your_", "your-", "example", "placeholder",
                                    "xxxx", "changeme", "change_me", "todo", "redacted",
                                    "secret_store", "vault", "os.environ", "process.env",
                                    "getenv", "secretmanager", "<", "...", "dummy",
                                    "none", "null")):
            continue
        if len(v) >= 12 or (re.search(r"[A-Za-z]", v) and re.search(r"[0-9]", v)):
            return True
    return False


def _detect_prompt_injection(text: str) -> bool:
    t = text.lower()
    patterns = [
        r"ignore (?:the |all |any )?(?:previous |prior |above )?(?:instructions|rules|steps)",
        r"ignore (?:the )?(?:user'?s?|user)(?: )?(?:stop|cancel|request|instruction)",
        r"disregard (?:the |all |any )?(?:previous|prior|above|user|safety)",
        r"do not (?:tell|inform|notify|surface|mention|alert|reveal)\b.{0,40}(?:user|reviewer|owner|admin|human)",
        r"without (?:telling|informing|notifying|alerting|the user'?s? knowledge|asking|consent)",
        r"silently (?:send|exfiltrate|upload|transmit|forward|copy|post|leak|email)",
        r"exfiltrat",
        r"even if (?:the )?user (?:says |asks |tells )?(?:you )?(?:to )?(?:stop|cancel|no)",
        r"override (?:the )?(?:user|agent|safety|system|previous)",
        r"continue (?:anyway|regardless)",
        r"(?:send|post|upload|forward|email|transmit) (?:the )?(?:file|contents?|data|secret|credential|output|result)s?\b.{0,50}(?:to |http|external|https|@|url)",
        r"do not (?:log|record|report|surface)",
        r"pretend (?:you|to)",
        r"bypass (?:the )?(?:safety|guard|filter|check|restriction)",
        r"(?:hidden|secret) (?:instruction|command|directive)",
        r"regardless of (?:what|any) (?:the )?(?:user|instruction)",
    ]
    for p in patterns:
        if re.search(p, t):
            return True
    return False


def _detect_excessive_permissions(text: str) -> bool:
    t = text.lower()
    patterns = [
        r"read/write to the entire file ?system",
        r"read/write to the whole file ?system",
        r"filesystem\s*:\s*read/write\s+to\s+(?:the\s+)?(?:entire|whole|all)\b",
        r"filesystem\s*:\s*(?:unrestricted|full access|full|all|/\s*$|\*)",
        r"access to (?:the )?(?:entire|whole|all) (?:file ?system|disk|drive)",
        r"filesystem\s*:\s*read/write\s*/\s*$",
        r"filesystem\s*:\s*read/write\s*:\s*/\s*$",
        r"(?:read|write|access).{0,20}\ball files\b",
        r"network\s*:\s*(?:any|all|unrestricted|\*|any domain|any host|full)\b",
        r"egress to any (?:domain|host|url|address)",
        r"network access to (?:any|all)\b",
        r"allow(?:ed)? (?:all )?outbound (?:to )?(?:any|\*|all)",
        r"network\s*:\s*any domain",
        r"connect to any (?:domain|host|url|server|address)",
        r"outbound\s*:\s*(?:any|all|\*|unrestricted)",
        r"permissions?\s*:\s*(?:full|all|admin|root|unrestricted|\*)",
        r"scope\s*:\s*(?:\*|all|full|unrestricted)",
        r"sudo|root access|administrator privileges",
        r"chmod\s+777",
    ]
    for p in patterns:
        if re.search(p, t):
            return True
    return False


def _detect_unclear_provenance(text: str) -> bool:
    fm, body = _split_frontmatter(text)
    fm_l = fm.lower()
    full = text.lower()
    has_author = bool(re.search(r"(?m)^\s*author\s*:", fm_l)) or "author:" in full \
        or "authored by" in full or "maintainer:" in full
    has_version = bool(re.search(r"(?m)^\s*version\s*:", fm_l)) or "version:" in full \
        or bool(re.search(r"\bv\d+\.\d+", full))
    has_changelog = ("changelog" in full or "change log" in full or "history:" in fm_l)
    missing_all = not has_author and not has_version and not has_changelog
    silent_rewrite = (
        bool(re.search(r"(?:update|rewrite|bump|change|increment|overwrite|modify|edit).{0,40}version", full)) and
        bool(re.search(r"(?:silent|without (?:telling|surfacing|notifying|logging)|do not surface|do not mention|quietly)", full))
    )
    return missing_all or silent_rewrite


def scan(skill_text: str) -> list:
    cats = []
    if _detect_hardcoded_secret(skill_text):
        cats.append("hardcoded_secret")
    if _detect_prompt_injection(skill_text):
        cats.append("prompt_injection")
    if _detect_excessive_permissions(skill_text):
        cats.append("excessive_permissions")
    if _detect_unclear_provenance(skill_text):
        cats.append("unclear_provenance")
    return cats
