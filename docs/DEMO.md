# Demo-day runbook

Everything below assumes the server is running on the demo laptop on port 8010 and the tablet
and TV are on the same network (or the Vultr deployment at your domain).

## 30 minutes before

Shortcut: `.\start.ps1` from the repo root builds the frontend if needed, seeds an empty pool and
starts the server. The manual steps:

```
# fresh pool with three known families (stop the server first if it is running)
.venv\Scripts\python backend\scripts\seed_pool.py --families 3 --chains 2 --reset
.venv\Scripts\python -m uvicorn app:app --app-dir backend --host 0.0.0.0 --port 8010
```

- TV / projector: `http://<laptop-ip>:8010/tree` in a full-screen browser (F11). Leave it; it polls every 2 s.
- Tablet: `http://<laptop-ip>:8010/edit`, add to home screen so it opens full-screen. The TV header and the
  landing page show a QR code to the same URL, so visitors can join from their own phones (same Wi-Fi).
- Judge laptop or second screen: `http://<laptop-ip>:8010/` (about) and `/audit`.
- Have 6 to 8 versions of one photo in a folder for the audit demo (export a few from the pool:
  `data/pool/*.png`, or use `data/synthetic/run1/f0_*.png`).
- Check `GET /api/health` returns `ok: true` and the right item count.

## The 2-minute script

See `docs/DEVPOST.md`, section "2-minute demo pitch". Beats: one idea -> tablet edit -> tree
updates with evidence -> audit batch upload -> calibrated confidence -> industry ask -> close.

## Things that can go wrong

- **AI restyle returns a local stylization** instead of a Gemini image: the key has no image
  quota (billing). The edit still works and the stored params say `model: local-opencv`.
- **Tree accuracy dips** after several edits of the same kind on the same image: siblings with
  the same edit are genuinely ambiguous; say so, the evidence panel shows the margin.
- **Caption over a caption** attaches to the sibling: known limitation, documented in PLAN.md.
- **The TV page goes dark**: an error boundary now shows the message and a Reload button; reload.
- **Port 8000 is taken** on the dev laptop; everything is on 8010.
- **Memory**: the server holds one CLIP model (~1.5 GB). Do not run `eval.py` / `calibrate.py` next to
  it on a 16 GB laptop during the demo; each loads its own copy.
- **Remove one bad upload** (moderation): `curl -X DELETE -H "X-Admin-Token: $ADMIN_TOKEN" http://localhost:8010/api/items/<id>`
  (ids are visible in the tree details panel). Children are re-linked to its parent and the tree rebuilds.
- **Reset mid-event**: `POST /api/reset` with header `X-Admin-Token: <ADMIN_TOKEN>` (if set), then
  rerun `seed_pool.py` and restart the server.

## Numbers to quote

From PLAN.md (synthetic chains, 6 CC0 seeds, 3 chains each): run1 83.0% (tuned), run2 71.1% and
run3 81.1% (held out); roots found 6/6 on every run; true parent inside the top-8 candidates
98.9%; empirical precision by margin: >= 0.30 about 96%, < 0.02 about 66%. 116 tests.
Audit load test: 30 shuffled versions from 3 originals, 9 edits deep, uploaded in 29 s; 3 families
found; 28 of 30 parents correct against the hidden truth (93%).

## Pre-submission checklist (Devpost closes Sun Oct 18, 08:00 ET)

- [ ] Repo public: https://github.com/JonathanKash/SwampHacks-Submission (README, AI disclosure, credits current)
- [ ] `python backend/scripts/smoke.py http://localhost:8010` prints ALL OK (or against the deployed URL)
- [ ] Devpost text pasted from `docs/DEVPOST.md`; "Built with" list matches README credits
- [ ] 2-minute video or live demo rehearsed with the script in `docs/DEVPOST.md`
- [ ] Screenshots: landing, /edit verdict, /tree with panel, /audit (take fresh ones from the running app)
- [ ] Team members added on Devpost; tracks selected
- [ ] `.env` never committed; `GEMINI_API_KEY` present on the demo machine if restyle should hit Gemini


## Compare two files ("Why is this the parent?")

1. Open `/compare`, drop any two images, press Compare.
2. Read the verdict line first: parent-child, siblings, unrelated or inconclusive. Inconclusive is a real
   answer: the system found no measurable asymmetry it is calibrated for (for example an object added or
   removed: pixels alone cannot say which).
3. Press "Why is this the parent?" for the signal table, both diff plates, conflicts, unavailable signals,
   measured AI-edit indicators, limitations and the reproducibility block (tool version, weights hash, SHA-256).
4. The same button sits in the audit and tree side panels for any derived copy.
5. CLI equivalent: `python backend/lineage_cli.py compare A.jpg B.jpg --json`.


## Identify a meme (audience participation)

1. Before the demo: `.venv\Scripts\python backend\scriptsuild_meme_case.py --no-clip` (about 2 minutes; the
   case appears in Audit as "Meme originals · 38 families").
2. Visitors open `/identify` from the QR code, upload any meme from their phone, press Identify.
3. Talk track: the family card is the documented original with its date and source; "Your copy" shows the
   measured edit; "Why?" opens the same evidence report as everywhere else. If it says "No family matched",
   say so: it means nothing aligned pixel for pixel, and that is the honest answer.


## Run the server from your own terminal (important)
Start it in a PowerShell window you own, not from a Claude Code session: Claude Code's memory watchdog kills its own
background jobs when the laptop runs low on RAM, and that took the demo server down several times on Oct 17-18.
```
cd C:\Users\jonjo\Documents\SWAMPHACKS
.\start.ps1 -LowMemory -PublicUrl https://jmklptp08.tail2caba9.ts.net
```
Leave the window open. Close spare browser tabs first; the machine has 13.6 GB and the browser is the swing factor.

## Pre-demo checklist (Oct 17 additions)

- [ ] `.venv\Scripts\python backend\scriptsuild_meme_case.py --no-clip --variants 5` (about 5 minutes) and
      confirm `/api/health` reports `identify_ready: true`.
- [ ] Set `ADMIN_TOKEN=<secret>` in `.env` before sharing the public link (start.ps1 warns if it is missing). Without it
      any visitor can press "Remove this image" or delete an audit case; the Identify knowledge base is refused either
      way. The UI asks for the token once (session only) when you remove something yourself.
- [ ] Open `/identify` on a phone via the QR code, upload a meme, confirm the family card and the "Why?" report.
      If nobody has a meme handy, "Try a sample instead" loads a stored copy (expect a near-identical match).
- [ ] On the phone, the nav collapses to a Menu button; check it opens and closes.
- [ ] Open `/method`, confirm the Numbers table shows both the synthetic column and the web-memes column.
- [ ] Open `/compare`, run two files, confirm the verdict chip shows two numbers.
- [ ] Open `/tree` on the big screen, press Replay once, check the Fool Lineage scoreboard.
- [ ] If the Gemini image quota has reset, run `benchmark/nanobanana/make_corpus.py` to finish the edit corpus
      (optional; the benchmark reads whatever exists).


## Public link without a server (Cloudflare quick tunnel)

```
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:8010
```
The `https://<words>.trycloudflare.com` URL printed after a few seconds serves the running app. Set it as
`PUBLIC_URL` when starting the server so the QR code on `/tree` points visitors there. The URL changes on every
restart; a persistent hostname needs a Cloudflare account, a domain on Cloudflare DNS and a named tunnel
(`cloudflared tunnel login / create / route dns`, then `cloudflared service install`), or the Vultr deploy.

Quick tunnels get revoked by Cloudflare after a while (seen twice on demo day: after ~5 h and after ~45 min).
For the event, run the watchdog instead of starting the tunnel by hand: `.\deploy	unnel-watchdog.ps1` keeps a
tunnel up, restarts the server with the new `PUBLIC_URL` when the address changes, and writes the current address to
`data\public_url.txt`. Keep ngrok (`ngrok http 8010`) as a second link; it has an interstitial page but a stable session.


## Permanent public link (Tailscale Funnel)
Enabled on 2026-10-17. The address https://jmklptp08.tail2caba9.ts.net is fixed and the Funnel persists across reboots (Tailscale runs as a
service). After a reboot only the server needs starting: `.\start.ps1 -LowMemory -PublicUrl https://jmklptp08.tail2caba9.ts.net`.
To turn the public exposure off: `tailscale funnel --https=443 off`.
