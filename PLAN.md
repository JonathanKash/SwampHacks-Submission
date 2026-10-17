# PLAN.md — Lineage

## Phase 0 — go/no-go (synthetic eval)
- [x] Repo skeleton, CLAUDE.md, SPEC.md, PLAN.md, .env.example
- [x] Edit menu as pure functions (crop, rotate, filter, caption, jpeg)
- [x] Seed fetcher (Met Open Access v1.1 search, CC0) -> 6 seeds
- [x] Synthetic chain generator with saved ground truth (run1 seed 0: 94 items; run2 seed 1: 96 items)
- [x] Fingerprints (pHash + binarized CLIP ViT-B/32, embeddings cached on disk)
- [x] core/candidates.py: Hamming top-k (true parent in top-8: 98.9% / 97.8%)
- [x] core/arborescence.py: own Chu-Liu/Edmonds + virtual root, cross-checked vs networkx
- [x] plugins/image_cost.py: full spec + gated cues + edit-op MDL prior + specificity tie-break
- [x] 80 pytest tests passing
- [x] eval.py: tree accuracy overall / per edit type, candidate recall, error kinds, cue table
- [ ] GATE: review numbers, decide go/no-go

### Phase 0 numbers (2026-10-16, k=8, root_cost=3.5)
Weights were tuned by hand on run1; run2 (different seed) is held out.

| edit     | run1 (tuned)  | run2 (held out) | run3 (held out) |
|----------|---------------|-----------------|-----------------|
| overall  | 83.0% (73/88) | 71.1% (64/90)   | 81.1% (73/90)   |
| crop     | 82.6%         | 62.5%           | 81.0%           |
| rotate   | 81.2%         | 89.5%           | 87.5%           |
| caption  | 86.7%         | 71.4%           | 78.9%           |
| jpeg     | 70.0%         | 58.3%           | 73.7%           |
| filters  | 14/14         | 13/17           | 13/15           |
| roots    | 6/6           | 6/6             | 6/6             |

Error kinds (run1): grandparent 10, other relative 4, flipped 1.
Timing: 40-90 ms per pair cost on CPU; about 16 new pair costs per upload with k=8.

Reading: direction (the core claim) holds: roots are always found and direction flips are
rare. Most errors are the right family and the right direction but the wrong ancestor: a
crop of a crop is also one crop from the grandparent, a JPEG of a JPEG is also one JPEG
from the clean original, and chains of near-lossless edits tie. The edit-op prior fixed many
of these; the rest are close to ambiguous. The weakest edit is low-quality JPEG (invisible
when the parent is already a JPEG). Tuning on run1 alone overfit by ~20 points at first; the
cue gating added afterwards (tint on gray, grayscale entropy, blob weight) generalized.

Known levers if we want more: double-JPEG detection, a caption-aware crop check, more seeds
for tuning, k=12.

## Phase 1 — backend API (done 2026-10-16 ~23:30 ET)
- [x] SQLite schema (items with true parent, pair-cost cache), files + thumbnails on disk (lineage/store.py, lineage/pool.py)
- [x] FastAPI app.py: POST /api/items (upload), POST /api/edit (server-side menu edit incl. restyle), GET /api/pool, /api/random, /api/tree (accuracy inside), /api/tree?since= (204 polling), POST /api/reset
- [x] Incremental recompute on upload (costs cached per pair + persisted)
- [x] explain() plug-in (Codex-written: plugins/image_explain.py, 17 tests)
- [x] Gemini restyle plug-in (model ids verified via Gemini CLI 2026-10-16) + OpenCV local fallback when the key has no image quota
- [x] Pre-seed script (scripts/seed_pool.py) builds known chains through the Pool
- [x] Smoke-tested on a live uvicorn: upload, edit, tree, 204 polling, static images; 111 tests passing
- [ ] Restyle with a real Gemini image call (needs a billing-enabled key: current key returns quota 0)

## Phase 2 — /edit tablet page (done 2026-10-17 ~00:30 ET)
- [x] Vite + React + TS scaffold (Codex), typed API client, 2 s polling with 204 short-circuit
- [x] Guided flow: step bar, random image, one-edit menu with sub-choices, submit, before/after + verdict
      ("Lineage traced your edit back correctly" / "You fooled it", with the explain sentence)
- [x] Gemini restyle wired server-side (model name verified) with OpenCV fallback
- [x] Landing page at / explaining the idea, the pipeline and how to join the demo; shared nav
- [x] Evidence on every decision: both-direction costs, keypoint inliers, coverage, color fit, runner-up
      and margin, plus empirical precision per margin bucket from calibration.json (scripts/calibrate.py,
      run1+run2: <0.02 → 71%, 0.05–0.10 → 89%, ≥0.30 → 92%). No "guess" wording anywhere.
- [ ] Visual QA on a real tablet (portrait + landscape)

## Phase 3 — /tree big-screen view (done 2026-10-17 ~00:30 ET)
- [x] D3 forest, thumbnails, edge label pills (green/red, dashed = semantic), accuracy scoreboard,
      newest-node glow + callout, legend, details panel, live refresh with smooth transitions
- [ ] Visual QA on a 1080p TV at distance (font sizes, contrast)

## Phase 4 — ship
- [x] Pre-seed script with known chains
- [ ] Vultr VM + Caddy HTTPS + domain (assets ready in deploy/; needs a VM IP + domain from the team)
- [x] Pushed to github.com/JonathanKash/SwampHacks-Submission (2026-10-17)
- [ ] README: run, architecture, AI disclosure, credits (frontend + deploy sections still to finish)

## Phase 6 — industry mode: provenance audit (added 2026-10-17 ~01:30 ET)
Use case: newsroom verification desks, trust & safety, legal discovery, digital asset management
receive many versions of an image and need the original, what changed in each copy, how sure we
are, and an exportable report.
- [x] Cases API: create/list/delete, batch upload, per-case tree (mode "audit", no truth, summary with
      mean empirical precision + low-confidence count), JSON report download, per-case static images
- [x] Shared CLIP model across case pools; EXIF metadata hints per item (labelled unverified)
- [x] Evidence is descendant-aware: locally cheaper descendants are explained as rejected cycles;
      root reasons state that every relative is cheaper to derive from the original
- [x] /audit page (Codex): case list, drag-and-drop batch upload, confidence-colored tree, evidence +
      metadata panel, report download, print summary; landing "For industry" section; nav link
- [x] Live end-to-end check of the audit flow on the running server (6 shuffled versions -> correct 2-family tree, report OK)
- [x] Visual QA: Antigravity CLI has no browser, so Playwright screenshots (scratchpad/qa) reviewed by Claude.
      Found and fixed: /tree and /audit crashed to a black page (created_at number vs string in the D3 sort);
      added an ErrorBoundary; tightened the tablet header. Landing/edit/tree/audit all render correctly now.
- [x] Provenance path (original -> edit -> edit) in the tree and audit details panels
- [x] Deploy assets: deploy/Dockerfile (multi-stage node+python), docker-compose with Caddy auto-HTTPS, deploy/README.md
- [x] README AI disclosure covers Claude Code, Codex and Gemini (Antigravity) usage
- [ ] Web mode (reverse-image candidates via TinEye/SerpApi) if a provider key is available

## Phase 7 — overnight pass (2026-10-17, from ~00:30 ET)
- [x] USE_CLIP=false low-memory mode (pHash-only candidates) so the server runs in ~400 MB; health reports `clip`
- [x] UX research via Gemini (InVID, TinEye, C2PA Verify, Relativity): vocabulary "candidate original", "derived
      copy", "empirical precision" with reliability tiers; tamper-evident footprint; visual diff plates; report contents
- [x] Visual diff plates: /api/diff/{id} and /api/cases/{id}/diff/{id} (source aligned onto copy | copy | residual)
- [x] Footprint per item (SHA-256, dimensions, bytes, pHash); analyst on cases; tool version in reports
- [x] Self-contained HTML report with inventory table, how-to-read, method and limitations (/api/report.html, per case)
- [x] UI polish (Codex): favicon + titles, inline SVG icons, compact mobile nav, shimmer loading, button consistency
- [x] Frontend: diff toggle in panels, auditor vocabulary + reliability tiers, footprint block, analyst field,
      HTML report links, how-to-read explainer (Codex)
- [x] Smoke test extended to diff + HTML report + footprint
- [x] C2PA manifest presence recorded at ingest (unverified hint)
- [x] HTML report embeds a visual diff exhibit per derived copy; verdict page shows the evidence picture (Codex)
- [x] Accessibility pass (Codex, from Gemini's WCAG review): pill/border contrast, focus rings + focus
      management, aria-pressed toggles, live regions, labelled edges with non-color prefixes, keyboard
      file input, reduced motion; verified headlessly
- [x] Research notes archived in docs/research/ with provenance
- [x] Landing "How sure is it?" section renders the live calibration table (/api/calibration); word-level diff
      view for text decisions (Codex finished these just before hitting its usage limit, ~01:00 ET; reset ~02:41)
- [x] CSV decision ledger export (/api/report.csv, per case) with UI link; "compare with any image" diff in the
      audit panel; frontend unit tests (vitest: text diff, provenance path)
- [x] Tamper-evident JSON reports (sha256 stamp + optional HMAC via REPORT_SIGNING_KEY), POST /api/verify-report,
      "Verify a report" control on the audit page
- [x] Fixed DATA_DIR resolving against the shell cwd (server launched from another folder saw an empty pool)
- [x] Big-screen arrival overlay (source -> edit, verdict, precision; auto-dismiss; reduced motion)
- [x] Scan-to-join QR code on the TV and landing pages (visitors add edits from their phones); QR encodes the
      server's LAN URL (or PUBLIC_URL) when the page is opened via localhost
- [x] Phone-width (390px) check of the edit flow: no overflow, layout fine
- [x] Low-memory mode widens candidates to k=16 (pHash-only search missed a true parent at k=8)
- [x] Moderation: delete an image (demo pool or case) with child re-linking; documented in the runbook; UI control
      in the audit panel (and on /tree?admin=1) with an admin-token prompt; low-memory mode badge from /api/health
- [x] Per-client cooldown on /api/edit (EDIT_COOLDOWN_S) against tap spam from phones
- [x] /method page: every cost term with weight and direction logic, pipeline, evidence/calibration, limitations
- [x] "Load a sample case" (POST /api/cases/sample cuts one demo family into a case); tablet shows a live cooldown
      countdown on 429 and scrolls to the verdict (Codex, quota back ~03:40)
- [x] README screenshots refreshed from the current UI

## Phase 5 — second media type: text (started 2026-10-17 ~02:30 ET)
- [x] Media plug-in interface (lineage/media.py); Engine takes any plug-in; evidence accepts plug-in reasons
- [x] Stateless POST /api/text/tree and a /text page (paste versions, see the tree + evidence)
- [x] plugins/text_media.py (Codex): SimHash/MinHash fingerprints, word-loss cost, worded explain; semantic
      scale tuned so reworded summaries attach by meaning while unrelated text stays a separate root
- [x] Text decisions show raw margins (the precision table is calibrated on image chains only)
- [x] Experiment (rejected): AC-sparsity "estimated compression" cue from Gemini's research. Measured on
      run1/run2/run3: blockiness-only 81.8/68.9/81.1, sparsity-only 71.6/65.6/66.7, both 78.4/67.8/75.6
      vs committed 83.0/71.1/81.1. JPEG edit improved slightly with "both" but everything else lost
      3-5 points (the statistic also moves with contrast and blur). Reverted; committed cost unchanged.
- [x] docs/DEMO.md runbook (setup, script pointer, failure modes, numbers to quote)
- [x] Audit load test (2026-10-17): 30 shuffled versions from 3 seeds (9 random edits deep each) uploaded in
      29 s (1.0 s/image); 3 families found; 28/30 parents correct against hidden truth (93%)
- [x] Audit deep links (?case=) + copy link, report download on /tree, text margin note (Codex)
- [x] Calibration regenerated from run1+run2+run3 for larger per-bucket samples
- [ ] Known limitation (images): a caption painted over an existing caption can attach to the sibling;
      a "replaced content" blob rule was tried and reverted (it lowered run1/run2 accuracy)

## Phase 8 — spec v2: provenance + parent/child detection (from 2026-10-17 ~10:30 ET)
Decisions in SPEC.md (v2 section). Images first; audio/video only after images work fully.
- [x] Pairwise compare core (lineage/compare.py): parent-child / siblings / unrelated / inconclusive, calibrated
      confidence, benchmark accuracy for the detected edit type, signal table (pixel / semantic / metadata / gate),
      conflicts, unavailable signals, measured AI-edit indicators, limitations, reproducibility (tool version,
      weights hash, input SHA-256); POST /api/compare (files or ids, inline diff plates both ways)
- [x] Compression history: estimated JPEG quality from quantization tables at ingest (hint, never evidence)
- [x] CLI at scale (backend/lineage_cli.py): compare, tree FOLDER, place IMAGE --against FOLDER (recognises a late
      original: "NEW CANDIDATE ORIGINAL, explains N images"), batch-compare -> CSV; --no-clip for small machines
- [x] /compare page + "Why is this the parent?" button in audit/tree panels (Codex); verified end to end with
      Playwright on the Met painting vs its Gemini edit
- [x] Late true original: nodes.explains + tree.newest_took_over; overlay/audit callout (Codex); pool test
- [x] Decisive-cue analysis in compare (drop each term, see if the direction survives). A direction resting on
      the compact-content ("blobs") cue alone is symmetric (object added vs object removed) and now returns
      inconclusive unless the gained content is caption-like (two-tone >= 0.7, achromatic, contrast >= 100,
      measured on the strong residual mask: synthetic captions 0.83, pasted natural patch 0.10).
      Real Gemini edits (src01): object_remove was claimed backwards at "95%" before this rule, now
      inconclusive; object_add inconclusive; background_swap correct; watercolor restyle inconclusive.
- [x] Noise-consistency indicator (high-pass std inside vs outside the changed region) as a measured AI-edit
      indicator, never a verdict input
- [x] Meme corpus (agent): 38 families, 612 images (365 caption, 139 lowres, 45 crop, 13 screenshot), 13 rooted at
      a copy of the true source photo, the rest at the earliest template; manifest.resolved.json + README + tools.
- [x] Meme benchmark v1 (pHash-only, before fixes, 563 pairs): direction 24%, abstained 62%, WRONG PARENT CLAIMED 14%
      (crop 36%), root recovered 24% of families; calibration did NOT transfer: claimed >=0.30 bucket observed 66%.
      Diagnosis: (a) 205/563 pairs did not register: ORB at 1500 features spends them on the caption and leaves
      1-3 inliers for the photo (4000 features give 100+), and small/soft frames (Evil Kermit 325px) have almost no
      corners; (b) in 48/75 wrong claims the documented "original" has FEWER pixels than the variant (e.g. Distracted
      Boyfriend: KYM comp 880x440 vs Imgflip 1200x800), so the pixel truth is ambiguous; (c) the caption-side cue was
      92% right (n=53) on its own.
      Fixes: ORB 4000 + SIFT fallback; caption_removed cost term; harness now splits memes-true-source vs
      memes-template and tags pairs where the original is the smaller file. Synthetic regression after the fixes
      (pHash-only): 75.0 / 66.7 / 73.3 vs 76.1 / 67.8 / 73.3 before (within one item per run).
- [ ] Real-photo -> Gemini-edit corpus through Antigravity (driver benchmark/nanobanana/make_corpus.py;
      capability verified 10:37: Antigravity returned a genuine Gemini edit) -> parent/child benchmark per edit type
- [x] Benchmark harness v2 (benchmark/run_benchmark.py): per corpus and edit type: direction accuracy, wrong-parent-claimed,
      abstained (inconclusive/siblings/unrelated), family root recovery, calibration check, failure list.
      Synthetic pairwise, pHash-only mode: wrong parent claimed 3% / 4% / 2% on run1/2/3; abstained 3% / 14% / 30%;
      direction 93% / 81% / 68%. Calibration: claimed ≥0.30 bucket observed 99%, 0.05–0.30 observed 91%,
      0.02–0.05 observed 64% (n=11, over-claims; more data needed)
- [ ] Web candidates (reverse-image provider behind an env key) + add-by-URL for cases
- [ ] Audio, then video (after images work fully; internet samples)
- [x] Identify (2026-10-17 ~12:00): `Pool.place` (non-persisting placement: pHash candidates -> min cost parent,
      root walk, late-original check), `POST /api/identify`, knowledge-base case from the meme corpus
      (109 items: 38 originals + 2 variants each), `/identify` page (Codex). Live check on 4 unseen captions:
      2 placed in the right family with the documented original, 2 honestly "no family" (pHash-only mode).
- [x] Content Credentials: c2pa-python reads and validates manifests (tested on c2pa-rs fixtures: Valid,
      issuer, actions); shown as a metadata signal and, with generative-AI assertions, as an AI-edit indicator.
- [x] Meme benchmark v2 (after ORB 4000 + SIFT fallback + caption_removed term, pHash-only, 563 pairs):
      unrelated verdicts on captions 144 -> 58; abstained 62% -> 47%; direction 24% -> 31%; caption-side cue
      95% (n=59). BUT wrong parent claimed 14% -> 23%, and the synthetic ">= 0.30" bucket observed 58% (n=281)
      on web memes. Consequence: confidence now carries the same bucket's observed precision per corpus
      (calibration.corpora, written by benchmark/write_corpus_calibration.py) and the UI shows both numbers.
      Third pass running with family + "documented original is the smaller file" splits to separate ambiguous
      truth from real direction errors.
- [x] Two numbers everywhere (2026-10-17 ~12:45): calibration.corpora["web-memes"] from benchmark pass 2
      (>=0.30: 163/281 = 58%; 0.05-0.30: 8/15; 0.02-0.05: 1/3); confidence carries by_corpus; shared ConfidenceChip
      shows "92% on synthetic chains · 58% on web memes"; NumbersPanel on landing and method pages renders the live
      /api/calibration table (synthetic vs web memes, caption-side 30/30, per-edit chips).
- [x] Big-screen extras: Fool Lineage scoreboard (edits that fooled it / placed correctly) and an edit-history
      Replay overlay for the largest family (Codex). Health exposes web_search / identify_ready capability flags.
- [ ] Antigravity image quota resets ~15:40 ET: finish benchmark/nanobanana (make_corpus.py is idempotent).
- [x] CLIP-mode eval after the cost changes (ORB 4000 + SIFT fallback + caption_removed), k=8: run1 80.7% (was 83.0),
      run2 70.0% (was 71.1), run3 80.0% (was 81.1): one to two items per run, inside noise, kept because the same
      changes took web-meme registration failures from 205/563 to ~100 and fixed a real caption reversal.
- [x] Identify fast path: ORB-only scan of the candidates, SIFT only on the nearest four when nothing aligns
      (SIFT on every unrelated candidate made identify take 4-17 s under load). Knowledge base rebuilt with 5
      variants per family (223 items).
- [x] 13:00-14:00 ET: CLI `identify` against a case directory; placement unit test; smoke test covers compare,
      calibration corpora, identify and the new routes (ALL OK live); HTML report and CSV carry the web-memes
      precision; tree view zoom/pan with fit controls (223-item case readable); method page: decides vs informs,
      symmetry limitation, caption-removed row; deploy notes + Dockerfile copy benchmark/; CLAUDE.md refreshed.
- [x] Identify on 378 held-out meme copies (knowledge base: 223 items, pHash-only mode): 293 correct family (77.5%), 85 abstained, 0 wrong family; median 4.13 s, p90 5.3 s. By kind: crop 31/45, caption 255/314, other 5/6, screenshot 2/13.
- [x] Gemini edit corpus: 25 edits (4 photos x 6 instructions + Met object_add); the image quota ran out again at 16:30
      (src05-src08 pending; `make_corpus.py` resumes where it left off).
- [x] Meme benchmark pass 3 (family splits, 563 pairs, pHash-only): when the documented "original" is a SMALLER
      file than its variant (287 pairs, ambiguous truth) wrong parent claimed 31%, direction 20%, abstained 49%;
      when the documented original is at least as large (276 pairs, clean truth) wrong parent claimed 13%,
      direction 42%, abstained 45%; true-source families with clean truth: wrong 11%, direction 52% (n=90).
      Caption-side cue 100% on template families (n=27), 91% on true-source (n=32). We publish the
      conservative all-pairs number (58% in the top bucket) in the UI; the split is documented here and in Devpost.
- [x] Calibration now carries two web-meme columns: all pairs (>=0.30 bucket 163/281 = 58%) and clean truth
      (>=0.30 bucket 110/143 = 77%; 0.05-0.30: 6/9). Both are shown by the ConfidenceChip, NumbersPanel, HTML report
      and CSV; the chip's lowest number is the conservative one.
- [x] Gemini-edit benchmark, interim (23 edits from 4 photos + Met, pHash-only): direction 30%, abstained 44%,
      WRONG PARENT CLAIMED 26% (object_add 2/5, text_overlay 2/3, background_swap 1/4, style_change 1/4).
      Generative re-rendering changes resolution and every pixel slightly, which defeats the resolution cue
      (the model output is often larger than the source). Investigating a "re-rendered copy" gate.
- [x] Re-rendered gate + edit-ops rule (16:40): colour residual after alignment > 0.025 (synthetic edits max 0.022,
      Gemini restyles 0.03-0.09) -> inconclusive with a measured AI-edit indicator; a direction resting only on the
      edit-op count -> inconclusive. Gemini edits (25): wrong parent claimed 26% -> 8%, abstained 44% -> 72%.
      Synthetic pairwise: direction 89 / 84 / 79, wrong parent 6 / 4 / 2 %, abstained 6 / 11 / 19 %.
      Decisive-cue audit on synthetic claims: several cues 99% (n=145), blockiness 100% (39), entropy 84% (32),
      caption_removed 90% (10); edit_ops-only never occurs.

## What's next (after the hackathon)
- Audio (Chromaprint-style constellation fingerprints; trim/bandwidth/added-content costs) and video (keyframe
  hashing + per-keyframe image cost), both with internet samples and the same evidence/abstention rules.
- Internet originals: reverse-image provider behind SERPAPI_KEY (code and UI are in place, no key).
- Finish the Gemini edit corpus (quota) and re-measure per edit type; calibrate the "object add/remove" case if a
  measurable asymmetry appears (noise consistency showed ratio 1.5-2.3 on the first examples).
