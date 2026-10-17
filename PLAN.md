# PLAN.md — Lineage

## Phase 0 — go/no-go (synthetic eval)
- [x] Repo skeleton, CLAUDE.md, SPEC.md, PLAN.md, .env.example
- [ ] Edit menu as pure functions (crop, rotate, filter, caption, jpeg)
- [ ] Seed fetcher (Met Open Access, CC0)
- [ ] Synthetic chain generator with saved ground truth
- [ ] Fingerprints (pHash + binarized CLIP)
- [ ] Engine with TEMPORARY fallback (brute-force candidates, crude cost, networkx arborescence)
- [ ] Stubs + pytest specs for candidates.py, arborescence.py, image_cost.py
- [ ] eval.py: tree accuracy overall / per edit type + per-cue direction table
- [ ] GATE: review numbers, decide go/no-go

## Phase 1 — backend API
- [ ] SQLite schema (items, edges cache), file storage
- [ ] POST /upload (image + true_parent), GET /pool, GET /tree, GET /accuracy
- [ ] Incremental recompute on upload
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
