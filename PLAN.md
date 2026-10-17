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

| edit     | run1 (tuned)  | run2 (held out) |
|----------|---------------|-----------------|
| overall  | 83.0% (73/88) | 71.1% (64/90)   |
| crop     | 82.6%         | 62.5%           |
| rotate   | 81.2%         | 89.5%           |
| caption  | 86.7%         | 71.4%           |
| jpeg     | 70.0%         | 58.3%           |
| filters  | 14/14         | 13/17           |
| roots    | 6/6           | 6/6             |

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
- [ ] Vultr VM + Caddy HTTPS + domain
- [x] Pushed to github.com/JonathanKash/SwampHacks-Submission (2026-10-17)
- [ ] README: run, architecture, AI disclosure, credits (frontend + deploy sections still to finish)

## Phase 5 — stretch
- [ ] Text plug-ins (MinHash / word loss / explain)
