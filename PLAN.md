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

## Phase 1 — backend API
- [ ] SQLite schema (items, edges cache), file storage
- [ ] POST /upload (image + true_parent), GET /pool, GET /tree, GET /accuracy
- [ ] Incremental recompute on upload
- [ ] explain() plug-in from CostResult.features (ops list + numbers)
- [ ] WebSocket or polling endpoint for the big screen

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
