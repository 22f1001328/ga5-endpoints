"""
Q5 - Agent Harness: Run Budget & Loop Guard
Input: {"budget_tokens": int, "steps": [{"step_number","tool","args","tokens_used"}, ...]}
Output: {"decision":"continue"|"halt","reason":"..."}

Rules:
  BUDGET: if sum(tokens_used) >= budget_tokens -> halt.
  LOOP (halt if either):
    (1) same tool 3+ times IN A ROW with functionally identical args
        - identical after: ignoring key order, ignoring whitespace-only diffs inside
          string values, ignoring any field literally named "client_ts".
    (2) trailing steps show 2-step cycle A,B,A,B,A,B repeating for 6+ trailing steps.
  - 2 identical in a row is NOT a loop.
  - changing meaningful arg (offset/page/run_id) = progress = continue.
  - budget and loop are independent; either alone halts.
"""
import json
import re


def _canon(value):
    """Canonicalize an args object:
       - drop any key literally named client_ts (recursively)
       - normalize whitespace-only differences inside string values
       - sort keys (via json sort_keys at the end)
    """
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k == "client_ts":
                continue
            out[k] = _canon(v)
        return out
    if isinstance(value, list):
        return [_canon(v) for v in value]
    if isinstance(value, str):
        # collapse any run of whitespace to a single space, strip ends
        return re.sub(r"\s+", " ", value).strip()
    return value


def _sig(step):
    """A comparable signature (tool + canonical args) for a step."""
    tool = step.get("tool")
    args = _canon(step.get("args", {}))
    return tool + "\u0000" + json.dumps(args, sort_keys=True, separators=(",", ":"))


def evaluate(body: dict) -> dict:
    budget = body.get("budget_tokens", 0)
    steps = body.get("steps", []) or []

    # --- Budget rule ---
    total = sum(int(s.get("tokens_used", 0)) for s in steps)
    if total >= budget:
        return {"decision": "halt",
                "reason": f"Cumulative tokens_used ({total}) has reached the budget ({budget})."}

    if not steps:
        return {"decision": "continue", "reason": "No steps yet; first step may proceed."}

    sigs = [_sig(s) for s in steps]

    # --- Loop rule (1): same signature 3+ times in a row (trailing) ---
    last = sigs[-1]
    run_len = 0
    for s in reversed(sigs):
        if s == last:
            run_len += 1
        else:
            break
    if run_len >= 3:
        return {"decision": "halt",
                "reason": f"Same tool/args repeated {run_len} times in a row (loop)."}

    # --- Loop rule (2): 2-step A,B cycle repeating for 6+ trailing steps ---
    if len(sigs) >= 6:
        # take trailing window and check the longest trailing alternation
        # pattern must be A,B,A,B,... with A != B, covering >= 6 trailing steps
        a = sigs[-1]
        b = sigs[-2]
        if a != b:
            # count how many trailing steps fit the alternating pattern ending at last
            count = 0
            expected = [a, b]  # positions from the end: -1->a, -2->b, -3->a, ...
            for i, s in enumerate(reversed(sigs)):
                if s == expected[i % 2]:
                    count += 1
                else:
                    break
            if count >= 6:
                return {"decision": "halt",
                        "reason": f"2-step A/B cycle repeating for {count} trailing steps (loop)."}

    return {"decision": "continue",
            "reason": "Under budget and no loop detected (arguments show progress)."}


if __name__ == "__main__":
    def mk(tool, args, tok=1000, n=0):
        return {"step_number": n, "tool": tool, "args": args, "tokens_used": tok}

    tests = []

    # budget exactly at boundary -> halt
    tests.append(({"budget_tokens": 20000, "steps": [
        mk("fetch_page", {"url": "https://example.com/1"}, 9000),
        mk("summarize", {"text": "..."}, 7000),
        mk("fetch_page", {"url": "https://example.com/2"}, 5000),
    ]}, "halt"))

    # legit pagination -> continue
    tests.append(({"budget_tokens": 20000, "steps": [
        mk("list_items", {"page": 1}, 1000),
        mk("list_items", {"page": 2}, 1000),
        mk("list_items", {"page": 3}, 1000),
    ]}, "continue"))

    # exactly 3 identical in a row -> halt
    tests.append(({"budget_tokens": 100000, "steps": [
        mk("search", {"q": "cats"}, 100),
        mk("search", {"q": "cats"}, 100),
        mk("search", {"q": "cats"}, 100),
    ]}, "halt"))

    # only 2 identical in a row -> continue
    tests.append(({"budget_tokens": 100000, "steps": [
        mk("search", {"q": "cats"}, 100),
        mk("search", {"q": "cats"}, 100),
    ]}, "continue"))

    # cosmetic diffs (key order, client_ts, whitespace) still a loop
    tests.append(({"budget_tokens": 100000, "steps": [
        mk("search", {"q": "cats", "lang": "en", "client_ts": 1}, 100),
        mk("search", {"lang": "en", "q": "cats", "client_ts": 2}, 100),
        mk("search", {"q": "cats  ", "lang": "en", "client_ts": 3}, 100),
    ]}, "halt"))

    # 6-step A/B cycle -> halt
    tests.append(({"budget_tokens": 100000, "steps": [
        mk("a", {"x": 1}, 100), mk("b", {"y": 2}, 100),
        mk("a", {"x": 1}, 100), mk("b", {"y": 2}, 100),
        mk("a", {"x": 1}, 100), mk("b", {"y": 2}, 100),
    ]}, "halt"))

    # empty history -> continue
    tests.append(({"budget_tokens": 100000, "steps": []}, "continue"))

    # decoy: same tool non-consecutive, genuinely different args -> continue
    tests.append(({"budget_tokens": 100000, "steps": [
        mk("poll", {"run_id": "a"}, 100),
        mk("poll", {"run_id": "b"}, 100),
        mk("poll", {"run_id": "c"}, 100),
        mk("poll", {"run_id": "d"}, 100),
    ]}, "continue"))

    # one below budget -> continue
    tests.append(({"budget_tokens": 20000, "steps": [
        mk("x", {"a": 1}, 9999), mk("y", {"a": 2}, 10000),
    ]}, "continue"))

    passed = 0
    for body, expect in tests:
        got = evaluate(body)["decision"]
        ok = got == expect
        passed += ok
        print(f"{'OK ' if ok else 'XX '} expect={expect:8} got={got:8}  {evaluate(body)['reason'][:60]}")
    print(f"\n{passed}/{len(tests)} passed")
