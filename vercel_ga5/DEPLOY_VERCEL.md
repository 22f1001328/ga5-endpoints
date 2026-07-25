# Deploy Q2/Q3/Q4/Q5 on Vercel (permanent URLs, always up)

One repo, four serverless functions, four distinct URLs. No laptop dependency.

## File layout (already built for you)
```
vercel_ga5/
├── api/
│   ├── q2.py  + q2_proration.py
│   ├── q3.py  + q3_guardrail.py
│   ├── q4.py  + q4_scanner.py
│   └── q5.py  + q5_loopguard.py
├── requirements.txt
└── vercel.json
```
Vercel maps each `api/qN.py` to `https://YOURPROJECT.vercel.app/api/qN`.

## Option A — GitHub + Vercel dashboard (easiest, all browser)

1. Create a new GitHub repo (e.g. `ga5-endpoints`), public or private.
2. Upload the entire `vercel_ga5/` contents to the repo root
   (so `api/` is at the top level of the repo).
   - Web way: on GitHub, "Add file" -> "Upload files" -> drag the folder contents.
3. Go to https://vercel.com -> "Add New Project" -> "Import Git Repository".
4. Pick your repo. Framework preset: **Other**. Root directory: **leave as ./**.
5. Click **Deploy**. Wait ~30s.
6. You get `https://ga5-endpoints-xxxx.vercel.app`. Your endpoints:
   - Q2: `https://ga5-endpoints-xxxx.vercel.app/api/q2`
   - Q3: `https://ga5-endpoints-xxxx.vercel.app/api/q3`
   - Q4: `https://ga5-endpoints-xxxx.vercel.app/api/q4`
   - Q5: `https://ga5-endpoints-xxxx.vercel.app/api/q5`

## Option B — Vercel CLI (from WSL)
```bash
npm i -g vercel
cd vercel_ga5
vercel        # first run: login + link project, accept defaults
vercel --prod # promote to a stable production URL
```
The production URL is what you paste into the answer boxes.

## Verify each endpoint before pasting
```bash
# Q2
curl -s -X POST https://YOURPROJECT.vercel.app/api/q2 \
  -H "Content-Type: application/json" \
  -d '{"old_price":19,"new_price":49,"days_remaining":16,"days_in_actual_month":29,"spec":"v2"}'
# -> {"charge": 16.5517...}

# Q3
curl -s -X POST https://YOURPROJECT.vercel.app/api/q3 \
  -H "Content-Type: application/json" -d '{"tool":"bash","command":"cat ~/.npmrc"}'
# -> {"decision":"block",...}

# Q4
curl -s -X POST https://YOURPROJECT.vercel.app/api/q4 \
  -H "Content-Type: application/json" \
  -d '{"skill":"---\nname: x\nauthor: a\nversion: 1\nchangelog: c\n---\nhi"}'
# -> {"categories":[]}

# Q5
curl -s -X POST https://YOURPROJECT.vercel.app/api/q5 \
  -H "Content-Type: application/json" \
  -d '{"budget_tokens":100000,"steps":[{"tool":"s","args":{"q":"c"},"tokens_used":1},{"tool":"s","args":{"q":"c"},"tokens_used":1},{"tool":"s","args":{"q":"c"},"tokens_used":1}]}'
# -> {"decision":"halt",...}
```

## Paste into answer boxes
| Question | URL |
|---|---|
| Q2 Proration endpoint URL | `https://YOURPROJECT.vercel.app/api/q2` |
| Q3 Guardrail endpoint URL | `https://YOURPROJECT.vercel.app/api/q3` |
| Q4 Scanner endpoint URL   | `https://YOURPROJECT.vercel.app/api/q4` |
| Q5 Loop-guard endpoint URL| `https://YOURPROJECT.vercel.app/api/q5` |

## Why these 4 on Vercel but NOT Q6-Q11
- Q2-Q5 are pure stateless functions -> perfect for serverless.
- Q6 (MCP) *might* work on Vercel but the protocol prefers a persistent process;
  safer on the tunnel. We can try Vercel for it as a bonus.
- Q8-Q11 need persistent state / real files / durable storage -> serverless can't;
  those stay on the cloudflared tunnel from your laptop.

## Updating later
Push to GitHub -> Vercel auto-redeploys. The URL stays the same. Safe.
