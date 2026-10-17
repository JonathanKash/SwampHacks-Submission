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
- [x] Moderation: delete an image (demo pool or case) with child re-linking; documented in the runbook

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
