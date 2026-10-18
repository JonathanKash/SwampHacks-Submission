# Handoff prompt for another Claude instance

Paste everything below this line into a fresh Claude Code session opened in `C:\Users\jonjo\Documents\SWAMPHACKS`.

---

You are taking over **Lineage**, a finished hackathon project for SwampHacks XII (University of Florida, Oct 16–18 2026; Devpost closes Sunday Oct 18 at 08:00 ET). The repo is `C:\Users\jonjo\Documents\SWAMPHACKS`, pushed to `github.com/JonathanKash/SwampHacks-Submission`. Read `CLAUDE.md`, `PLAN.md` (full history, numbers, rejected experiments), `docs/DEMO.md` (runbook) and `docs/DEVPOST.md` (submission draft) before touching anything. Your job is to keep the live demo healthy, run the demo exactly as described below, and make only small, measured changes. Do not redesign anything.

## What Lineage is

Given a pile of image versions (originals, crops, captions, re-saves, restyles, AI edits), Lineage reconstructs the family tree: which file is the candidate original, who derived from whom, and which edit separates them. Every decision ships with its measurements and an empirically calibrated confidence, and when the pixels cannot tell, it says **inconclusive** instead of guessing. That honesty is the product.

How it works, in one paragraph each:

- **Asymmetric cost.** For a directed pair (a → b): align a onto b with ORB keypoints (4000 features, SIFT fallback), fit colour per channel, then charge for everything b has that a cannot supply. Terms live in `backend/lineage/config.py` `WEIGHTS`: coverage (uncovered area), colour-fit residual, JPEG blockiness gained, resolution gained, chroma gained from gray, entropy gained, compact content differences ("blobs"), caption removed (caption-like content present only on the source side), an edit-op description-length prior, and a tiny specificity tie-break. Every term only penalises the direction in which b would have *gained* information.
- **Tree.** Candidates come from 64-bit pHash (plus a 512-bit binarised CLIP code when CLIP is on). Our own Chu-Liu/Edmonds minimum spanning arborescence (`backend/lineage/core/arborescence.py`, cross-checked against networkx in tests) picks one parent per image; a virtual root with cost 3.5 lets unrelated images become separate families.
- **Evidence and calibration.** Each edge carries both-direction costs, inliers, coverage, runner-up margin, and an empirical precision from `backend/lineage/calibration.json`: how often decisions with that margin were right on synthetic edit chains (run1 tuned, run2/run3 held out) **and** on real web memes (two columns: all pairs, clean truth). Both numbers are shown everywhere; the lower one is the honest expectation.
- **Pairwise verdicts** (`backend/lineage/compare.py`): parent-child / siblings / unrelated / inconclusive, with a signal table, the cues the direction rested on, conflicts, unavailable signals, measured AI-edit indicators, limitations, and reproducibility (tool version, weights hash, SHA-256 of inputs). Gates: a direction resting only on a compact content difference (object added vs removed is symmetric) or only on the edit-op count is not claimed; an aligned pair whose colour residual after fitting exceeds 0.025 is a "re-rendered copy" (restyle, background swap, generative re-draw) and is inconclusive with an AI-edit indicator; margins below 0.05 are indistinguishable. A caption-side cue (achromatic, dark-and-bright, high-spread text-like content on one side only) is allowed to decide because it was right 30/30 on the benchmark.
- **Identify.** A knowledge-base audit case built from 38 documented meme originals (plus stored variants, 223 items) answers "which meme is this and where did it come from": family, the documented original with source note/date/links, the measured edit, and the same evidence report. It answers from the matched item's family label and abstains rather than guess.
- **Content Credentials.** C2PA manifests are read and validated with `c2pa-python` and shown as a metadata signal; generative-AI assertions become an AI-edit indicator.

## Stack and commands

Python 3.13 FastAPI backend in `backend/` (venv `.venv`), React/Vite/TypeScript frontend in `frontend/` served from `frontend/dist` by the backend with SPA deep links, SQLite + files under `data/`. Pages: `/` landing, `/edit` tablet flow, `/identify`, `/compare`, `/tree` big screen, `/audit` industry workspace, `/text` text mode, `/method` for judges (cost terms, decides-vs-informs, gates, live Numbers table).

- Tests: `.venv\Scripts\python -m pytest backend\tests -q` (134 pass) and `npm --prefix frontend run test -- --run` (9 pass). Build: `npm --prefix frontend run build` (must exit 0; TypeScript strict).
- Smoke test against a running server: `.venv\Scripts\python backend\scripts\smoke.py http://localhost:8010` (expects `ALL OK`).
- Start the server: `.\start.ps1 -LowMemory -PublicUrl https://jmklptp08.tail2caba9.ts.net` from the repo root (low-memory = pHash-only candidates; the laptop has 13.6 GB and CLIP mode is not safe next to a browser). Port 8010 (8000 is taken on this machine).
- CLI: `backend\lineage_cli.py` with `compare A B`, `tree FOLDER`, `place IMAGE --against FOLDER`, `identify IMAGE`, `batch-compare FOLDER`.
- Benchmarks: `benchmark/run_benchmark.py`, `benchmark/identify_eval.py`, `benchmark/weight_sweep.py`, `benchmark/margin_floor_experiment.py`, `benchmark/identify_recall_experiment.py`.

## Public access

- **Permanent link (use this):** `https://jmklptp08.tail2caba9.ts.net` via Tailscale Funnel from this laptop. Tailscale runs as a Windows service and the Funnel persists across reboots; only the Lineage server needs restarting after a reboot (command above). The QR code on `/tree` points phones at `/identify` there.
- Fallbacks: Cloudflare quick tunnel (`.\deploy\tunnel-watchdog.ps1` keeps one alive and rotates `PUBLIC_URL`; addresses get revoked after a while) and ngrok (`ngrok http 8010`, stable per session, interstitial page). A Vultr/Docker deploy exists in `deploy/` but is not set up.
- `/api/health` reports `ok`, `items`, `clip`, `public_url`, `identify_ready`, `web_search`.

## UI state after the overnight UX pass (2026-10-18, 02:30-04:00 ET)

Every page got a plain-language pass and a layout check at 1366 / 834 / 390 px (details in PLAN.md "UI/UX pass").
Things that moved: on `/tree` the JSON and HTML report buttons live under an **Export** menu, the mode chip reads
"pHash mode", and the node side panel overlays the canvas; the nav says "Text mode"; the compare pool picker names
edits ("Caption “me irl” · 9d8084bf"); on phones the landing shows "Open it on this phone" instead of a QR code.
The Identify knowledge-base case shows a **KB** chip on `/audit` and the server refuses to delete it (403) unless
`ADMIN_TOKEN` is set and sent. `start.ps1` warns when `ADMIN_TOKEN` is unset behind a public URL: set it in `.env`
before judges arrive, or anyone with the link can press "Remove this image".

## Laptop constraints you must respect

- Claude Code's memory watchdog kills background jobs (including the server) when free RAM drops near 1.5 GB. Run **one** heavy job at a time, never a benchmark next to a build, and check `/api/health` after any heavy job. Browser tabs are the swing factor; ask the owner to close spare tabs before the demo.
- Server restarts: kill the listener on 8010 first and confirm the port is free before starting; a start during a frontend build fails because Vite empties `dist`.
- Gemini via Antigravity (`agy -p`) can edit images but the quota is exhausted; the generative-edit corpus sits at 25 edits. No Gemini API key is configured. Codex is reachable through the `codex:codex-rescue` agent for frontend work; verify its builds yourself.

## Honest numbers (quote these, do not inflate)

- Tree accuracy on synthetic chains, pHash-only: run1 75.0%, run2 67.8%, run3 73.3% (CLIP mode about 80 / 70 / 80); roots 6/6; top-8 candidate recall 98.9%.
- Calibration, top margin bucket: 92% on synthetic chains, 56% on web memes all pairs, 73% on web memes with clean truth. The gap is the story: web "originals" are often smaller copies than their variants, and generative edits defeat pixel cues.
- Pairwise wrong-parent claims: synthetic 3–4%, generative edits 8% (was 26% before the gates), abstaining 68–76% on generative edits by design.
- Identify: 378 held-out meme copies, 78.8% correct family, 21% abstained, **0 wrong families**, median 3.1 s.
- Caption-side cue 30/30. 133 backend tests, 9 frontend tests, smoke and route sweeps green.

## The demo, exactly

Setup: big screen on `/tree` (`https://jmklptp08.tail2caba9.ts.net/tree`), a tablet on `/edit`, judges' phones scan the QR (lands on `/identify`). Before judges arrive run the checklist in `docs/DEMO.md`: server up in low-memory mode with the public URL, `identify_ready: true`, pool reseeded (`backend\scripts\seed_pool.py --families 3 --chains 2 --reset` then restart), the meme knowledge base present (`backend\scripts\build_meme_case.py --no-clip --variants 5` if `data/cases` was cleared), one phone test of Identify, Replay pressed once on the tree.

Two-minute script (`docs/DEVPOST.md`, "pitch v2"):

1. **0:00–0:20 Hook, judge's phone on `/identify`.** They upload any meme from their camera roll (or press "Try a sample instead"). Show the family card: documented original, source and date, the measured edit between their copy and it, match strength, the trust line ("on 378 held-out copies: 78.8% right, 21% abstained, 0 wrong families"). Press **Why?** to open the evidence. Line: "Every claim on this screen is a measurement."
2. **0:20–0:45 Compare, laptop on `/compare`.** Pick two demo-pool items (a photo and its captioned copy). Verdict, decisive cues, both diff plates. Then an object-removal pair: it says inconclusive. Line: "Adding and removing an object look the same from pixels alone, so we do not guess. That is a feature."
3. **0:45–1:10 Big screen `/tree`.** The forest reconstructed from pixels alone, the Fool Lineage scoreboard (edits that fooled it stay on the board), press **Replay** once. Invite the room to scan and try to fool it on the tablet.
4. **1:10–1:35 `/audit`.** Open "Live check: viral poster": cases, reliability tiers, SHA-256 footprints, Content Credentials, HTML/CSV reports with an integrity stamp, "Why is this the parent?", add-from-URL, reviewed flags and analyst notes.
5. **1:35–1:50 `/method`, Numbers table.** Two numbers for every claim: synthetic calibration and the same bucket re-measured on real web memes. Line: "The lower number is the honest expectation for unknown files; the benchmark told us where to fix the engine."
6. **1:50–2:00 Close.** "Lineage does not guess. It measures, it shows its work, and when the pixels cannot tell, it says so."

If something abstains live, say so proudly and show the evidence panel; if a judge's upload returns "No family matched", explain that nothing aligned pixel for pixel and offer the sample button. If the public link is down, run `.\start.ps1 -LowMemory -PublicUrl https://jmklptp08.tail2caba9.ts.net`; if Tailscale is down, `.\deploy\tunnel-watchdog.ps1` gives a Cloudflare address within a minute.

## Rules

- Measure before keeping any cost change: eval on run1 **and** held-out run2/run3 (`backend\scripts\eval.py data\synthetic\runN --no-clip`), plus the pairwise harness for wrong-parent rates; revert anything that raises wrong claims or lowers held-out accuracy; record rejected experiments in `PLAN.md`.
- Never present a precision number that is not in `calibration.json`; never add an AI-generation black-box detector; keep "inconclusive" as a first-class answer.
- Commit after each working step with the build/test exit code as the gate (not grep). No secrets in code; `.env.example` lists every variable.
- The AI disclosure in the README is accurate and must stay that way: Claude wrote the code under the team's direction, Codex built most of the frontend, Gemini (via Antigravity) edited the benchmark images.

## Open items you may pick up (in order)

1. Screenshot copies in Identify (2 of 13 identified): photos embedded small in tweet/page screenshots need a region or multi-scale registration pass.
2. Web-meme calibration columns: a benchmark pass under the 0.05 margin floor was running at handoff; if `benchmark/bench_memes6`-style results exist, write them with `benchmark/write_corpus_calibration.py results.json web-memes` and the clean-truth variant, then restart the server.
3. Finish the generative-edit corpus when the Gemini quota returns (`benchmark/nanobanana/make_corpus.py` is idempotent) and re-measure per edit type.
4. Audio and video plug-ins with the same evidence and abstention rules (only after images are judged solid).

What still needs the owner: the Devpost submission itself (video, final read of `docs/DEVPOST.md`, submit before Sunday 08:00 ET), a SerpApi key if internet reverse-image lookup is wanted, and closing browser tabs before the demo.
