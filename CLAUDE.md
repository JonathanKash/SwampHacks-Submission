# Lineage — project context for Claude Code

Hackathon project (SwampHacks XII, UF, Oct 16-18 2026). Read SPEC.md for the full spec and
PLAN.md for phase status. Optimize for a reliable live demo.

## What it does
Reconstructs the edit family tree of a pool of images: asymmetric cost(a -> b) ("how cheaply
is b a lossy function of a") over candidate pairs, then a minimum spanning arborescence.

## Stack and commands
- Python 3.13 backend in `backend/`, venv at `.venv/` (Windows: `.venv/Scripts/python`).
  Deps: numpy, opencv-python-headless, pillow, networkx, open_clip_torch (CPU torch), fastapi.
- Run tests: `.venv/Scripts/python -m pytest backend/tests -q`
- Phase 0 pipeline (from repo root):
  - `.venv/Scripts/python backend/scripts/fetch_seeds.py`   (Met Open Access CC0 images -> data/seeds)
  - `.venv/Scripts/python backend/scripts/gen_chains.py`    (synthetic chains + truth -> data/synthetic/<run>)
  - `.venv/Scripts/python backend/scripts/eval.py data/synthetic/<run>`
- Config and secrets live in `.env` (see `.env.example`); tunables in `backend/lineage/config.py`.
- Run the API: `.venv/Scripts/python -m uvicorn app:app --app-dir backend --port 8010` (8000 is taken on
  the dev machine). Frontend: `cd frontend && npm run dev` (proxies to 8010) or `npm run build`, after
  which FastAPI serves `frontend/dist` at `/` with SPA deep links.

## Layout
```
backend/lineage/
  config.py                      cost weights dict + env flags
  types.py                       Item / Fingerprint / Edge / TreeResult dataclasses
  core/engine.py                 Pool -> fingerprints -> candidates -> cached costs -> arborescence
  core/candidates.py             top-k candidate search (Hamming on pHash + CLIP codes)
  core/arborescence.py           our own Chu-Liu/Edmonds, cross-checked vs networkx in tests
  plugins/image_fingerprint.py   pHash + sign-binarized CLIP ViT-B/32 (embeddings cached in data/.cache)
  plugins/image_features.py      cheap information cues: blockiness, chroma, sharpness, levels
  plugins/image_cost.py          asymmetric cost per SPEC.md (ORB+RANSAC, coverage, color fit, cues, blobs)
  edits/image_edits.py           the fixed edit menu (crop/rotate/filter/caption/jpeg) as pure functions
backend/scripts/                 fetch_seeds.py, gen_chains.py, eval.py
backend/tests/                   pytest for candidates, arborescence (brute force + networkx), image cost
data/                            gitignored: seeds/, synthetic/, pool/
```

## Hard rules
- Keep the cost terms and the Edmonds algorithm readable with short "why" comments; judges
  will ask about every part. All cost weights/thresholds stay in config.py.
- The engine must never read an item's true parent. Truth lives only in generator output /
  the upload record and is used by the eval and accuracy endpoint.
- No secrets in code. `.env` only; keep `.env.example` current.
- Simple, readable code; judges will ask about every part. Prefer a few files over many.
- Every new library/API goes into the README credits. Keep the README "AI disclosure" honest.
- Commit after each working step.
