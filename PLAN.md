# PLAN.md — Lineage

## Phase 0 — go/no-go (synthetic eval)
- [x] Repo skeleton, CLAUDE.md, SPEC.md, PLAN.md, .env.example
- [x] Edit menu as pure functions (crop, rotate, filter, caption, jpeg)
- [x] Seed fetcher (Met Open Access v1.1 search, CC0) -> 6 seeds
- [x] Synthetic chain generator with saved ground truth (run1: 94 items, 6 families, 3 chains each)
- [x] Fingerprints (pHash + binarized CLIP ViT-B/32, embeddings cached on disk)
- [x] Engine with TEMPORARY fallback (brute-force candidates, crude cost, networkx arborescence)
- [x] Stubs + pytest specs for candidates.py, arborescence.py, image_cost.py (60 tests, all NotImplementedError)
- [x] eval.py: tree accuracy overall / per edit type + per-cue direction table
- [ ] GATE: review numbers, decide go/no-go

### Phase 0 numbers (run1, TEMPORARY fallback cost, 2026-10-16)
Fallback cost = CLIP distance + one-directional cues (resolution, blockiness, chroma). No registration.

| edit        | tree accuracy |
|-------------|---------------|
| overall     | 51.1% (45/88) |
| caption     | 66.7% (10/15) |
| crop        | 56.5% (13/23) |
| jpeg        | 55.0% (11/20) |
| rotate      | 25.0% (4/16)  |
| filters     | 7/14 combined |
| roots found | 1/6           |

Errors: 10 direction flips, 8 grandparent, 18 other relative, 7 other family.

Direction cues on true parent->child pairs (right/tie/wrong):
- resolution: crop 23/0/0, rotate 16/0/0, everything else ties (perfect where it applies)
- blockiness: jpeg 17/1/2; noisy elsewhere; rotate 0/5/11 (interpolation smooths the grid: wrong way)
- sharpness: jpeg 17/0/3, rotate 15/1/0; caption 0/2/13 (text adds edges: wrong way)
- chroma: only grayscale/warm/cool react; small sample

Reading: the "edits destroy information" signal is real and clean for crop, rotate (resolution)
and jpeg (blockiness, sharpness). Caption and color filters have NO cheap one-directional cue;
they need the registered cost: coverage + per-channel color fit + blob term. Family separation
needs the semantic offset in the real cost (crude costs are all < 0.6, so root_cost never bites).

## Phase 1 — backend API
- [ ] SQLite schema (items, edges cache), file storage
- [ ] POST /upload (image + true_parent), GET /pool, GET /tree, GET /accuracy
- [ ] Incremental recompute on upload
- [ ] explain() plug-in from CostResult.features
- [ ] Team fills in candidates.py / arborescence.py / image_cost.py; flip USE_FALLBACK=false

## Phase 2 — /edit tablet page
- [ ] SPA scaffold, random image, edit menu, submit
- [ ] Gemini restyle (verify model name in docs first)

## Phase 3 — /tree big-screen view
- [ ] D3 tree, thumbnails, edge labels, accuracy counter, newest-node highlight, live refresh

## Phase 4 — ship
- [ ] Pre-seed script with known chains
- [ ] Vultr VM + Caddy HTTPS + domain
- [ ] README: run, architecture, AI disclosure, credits

## Phase 5 — stretch
- [ ] Text plug-ins (MinHash / word loss / explain)
